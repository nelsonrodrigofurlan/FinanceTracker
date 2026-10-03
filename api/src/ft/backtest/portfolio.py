"""Simulação de carteira: capital limitado, risco fixo por trade e número máximo de posições.

Parte da lista de trades de um backtest (cada trade já tem R líquido de custos) e decide quais
uma conta real conseguiria fazer:
- Trades processados em ordem de entrada; no mesmo dia, ordem alfabética de ticker
  (determinístico; não usa informação futura para escolher).
- Quantidade = min(risco, teto por posição, caixa) — em ações inteiras (mercado fracionário).
- Trade pulado se já houver `max_positions` abertas, ou se a quantidade calculada for zero.
- Resultado do trade = quantidade × R × (entrada − stop inicial), realizado na data de saída.
- Patrimônio considerado é o realizado (sem marcação a mercado das posições abertas).
- Com `cdi` informado, o caixa parado rende CDI dia a dia (como conta com liquidez diária).
"""

import bisect
from dataclasses import dataclass
from datetime import date

import numpy as np


@dataclass(frozen=True)
class PortfolioParams:
    initial_capital: float = 100_000.0
    risk_pct: float = 1.0  # % do patrimônio arriscado por trade (até o stop)
    max_positions: int = 5
    max_position_pct: float = 20.0  # teto de cada posição em % do patrimônio

    def as_dict(self) -> dict:
        return {
            "initial_capital": self.initial_capital,
            "risk_pct": self.risk_pct,
            "max_positions": self.max_positions,
            "max_position_pct": self.max_position_pct,
        }


@dataclass(frozen=True)
class SimTrade:
    ticker: str
    entry_date: date
    exit_date: date
    entry_price: float
    initial_stop: float
    r_multiple: float


class CdiIndex:
    """Índice acumulado do CDI: fator(d) = produto de (1 + taxa/100) até a data d."""

    def __init__(self, rates: dict[date, float]):
        self.dates = sorted(rates)
        self.values = np.cumprod([1 + rates[d] / 100 for d in self.dates])

    def at(self, day: date) -> float:
        i = bisect.bisect_right(self.dates, day) - 1
        return float(self.values[i]) if i >= 0 else 1.0

    def growth(self, start: date, end: date) -> float:
        return self.at(end) / self.at(start) if end > start else 1.0


def simulate(trades: list[SimTrade], p: PortfolioParams, cdi: CdiIndex | None = None) -> dict:
    ordered = sorted(trades, key=lambda t: (t.entry_date, t.ticker))
    equity = p.initial_capital
    cash = p.initial_capital
    open_pos: list[tuple[date, float, float]] = []  # (saída, custo da posição, resultado)
    curve: list[tuple[date, float]] = []
    taken = skipped_slots = skipped_size = 0
    interest_total = 0.0
    last_accrual = ordered[0].entry_date if ordered else None

    def accrue(day: date) -> None:
        """Rende o caixa parado pelo CDI entre a última data processada e `day`."""
        nonlocal cash, equity, last_accrual, interest_total
        if cdi is None or last_accrual is None or day <= last_accrual:
            return
        interest = cash * (cdi.growth(last_accrual, day) - 1)
        cash += interest
        equity += interest
        interest_total += interest
        last_accrual = day

    def settle_until(day: date) -> None:
        nonlocal equity, cash, open_pos
        due = sorted((x for x in open_pos if x[0] <= day), key=lambda x: x[0])
        for exit_day, cost, pnl in due:
            accrue(exit_day)
            cash += cost + pnl
            equity += pnl
            curve.append((exit_day, equity))
        open_pos = [x for x in open_pos if x[0] > day]
        accrue(day)

    for t in ordered:
        settle_until(t.entry_date)
        if len(open_pos) >= p.max_positions:
            skipped_slots += 1
            continue
        risk_per_share = t.entry_price - t.initial_stop
        if risk_per_share <= 0 or t.entry_price <= 0:
            skipped_size += 1
            continue
        qty = min(
            np.floor(equity * p.risk_pct / 100 / risk_per_share),
            np.floor(equity * p.max_position_pct / 100 / t.entry_price),
            np.floor(cash / t.entry_price),
        )
        if qty < 1:
            skipped_size += 1
            continue
        cost = qty * t.entry_price
        cash -= cost
        open_pos.append((t.exit_date, cost, qty * t.r_multiple * risk_per_share))
        taken += 1

    if open_pos:
        settle_until(max(x[0] for x in open_pos))

    if not curve:
        return {"params": p.as_dict(), "trades_taken": 0, "curve": []}

    values = np.array([v for _, v in curve])
    peak = np.maximum.accumulate(np.concatenate(([p.initial_capital], values)))[1:]
    drawdown = float(((peak - values) / peak).max() * 100)
    first, last = ordered[0].entry_date, curve[-1][0]
    years = max((last - first).days / 365.25, 1e-9)
    multiple = equity / p.initial_capital
    cagr = (multiple ** (1 / years) - 1) * 100 if multiple > 0 else -100.0

    # Um ponto por dia (último valor do dia).
    daily: dict[date, float] = {}
    for d, v in curve:
        daily[d] = v
    return {
        "params": p.as_dict(),
        "trades_taken": taken,
        "trades_skipped_no_slot": skipped_slots,
        "trades_skipped_size": skipped_size,
        "final_equity": round(equity, 2),
        "total_return_pct": round((multiple - 1) * 100, 2),
        "cagr_pct": round(cagr, 2),
        "max_drawdown_pct": round(drawdown, 2),
        "years": round(years, 2),
        "cash_interest": round(interest_total, 2),
        "curve": [{"time": d.isoformat(), "value": round(v, 2)} for d, v in daily.items()],
    }


def benchmark(series: dict[date, float], initial: float, start: date, end: date) -> dict:
    """Comprar e segurar (ou só CDI): série de valores normalizada para `initial`."""
    points = [(d, v) for d, v in sorted(series.items()) if start <= d <= end]
    if len(points) < 2:
        return {"available": False}
    base = points[0][1]
    values = np.array([v / base * initial for _, v in points])
    peak = np.maximum.accumulate(values)
    years = max((points[-1][0] - points[0][0]).days / 365.25, 1e-9)
    multiple = values[-1] / initial
    step = max(len(points) // 400, 1)  # curva resumida (~400 pontos) para o gráfico
    curve = [
        {"time": d.isoformat(), "value": round(float(v), 2)}
        for i, ((d, _), v) in enumerate(zip(points, values, strict=True))
        if i % step == 0 or i == len(points) - 1
    ]
    return {
        "available": True,
        "start": points[0][0].isoformat(),
        "cagr_pct": round((multiple ** (1 / years) - 1) * 100, 2),
        "total_return_pct": round((multiple - 1) * 100, 2),
        "max_drawdown_pct": round(float(((peak - values) / peak).max() * 100), 2),
        "curve": curve,
    }


def cdi_series(cdi: CdiIndex) -> dict[date, float]:
    return dict(zip(cdi.dates, (float(v) for v in cdi.values), strict=True))
