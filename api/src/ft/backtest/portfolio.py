"""Simulação de carteira: capital limitado, risco fixo por trade e número máximo de posições.

Parte da lista de trades de um backtest (cada trade já tem R líquido de custos) e decide quais
uma conta real conseguiria fazer:
- Trades processados em ordem de entrada; no mesmo dia, ordem alfabética de ticker
  (determinístico; não usa informação futura para escolher).
- Quantidade = min(risco, teto por posição, caixa) — em ações inteiras (mercado fracionário).
- Trade pulado se já houver `max_positions` abertas, ou se a quantidade calculada for zero.
- Resultado do trade = quantidade × R × (entrada − stop inicial), realizado na data de saída.
- Patrimônio considerado é o realizado (sem marcação a mercado das posições abertas).
"""

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


def simulate(trades: list[SimTrade], p: PortfolioParams) -> dict:
    ordered = sorted(trades, key=lambda t: (t.entry_date, t.ticker))
    equity = p.initial_capital
    cash = p.initial_capital
    open_pos: list[tuple[date, float, float]] = []  # (saída, custo da posição, resultado)
    curve: list[tuple[date, float]] = []
    taken = skipped_slots = skipped_size = 0

    def settle_until(day: date) -> None:
        nonlocal equity, cash, open_pos
        due = sorted((x for x in open_pos if x[0] <= day), key=lambda x: x[0])
        for exit_day, cost, pnl in due:
            cash += cost + pnl
            equity += pnl
            curve.append((exit_day, equity))
        open_pos = [x for x in open_pos if x[0] > day]

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
        "curve": [{"time": d.isoformat(), "value": round(v, 2)} for d, v in daily.items()],
    }
