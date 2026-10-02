"""Momentum entre ações (cross-sectional), rebalanceamento mensal — simulação de carteira.

Regras (definidas antes de ver resultados):
- No último pregão de cada mês (dia D), pontua cada ação pelo retorno de
  D−(L meses) até D−(1 mês) — "L−1": ignora o mês mais recente (reversão de curto prazo).
  1 mês = 21 pregões. Exige preço válido nos dois pontos e em D.
- Compra as N maiores pontuações com pontuação > 0, pesos iguais; o resto fica no caixa.
- Execução na ABERTURA do pregão seguinte a D (sem olhar o futuro).
- Filtro de regime opcional: em D com Ibovespa abaixo da MMA200, zera a carteira (caixa).
- Custos: taxa B3 + slippage sobre o valor negociado (só o que muda).
- Caixa rende CDI dia a dia. Posição marcada a mercado pelo fechamento ajustado.
- Preços ajustados por proventos (retorno total). Frações de ação permitidas (pesquisa).
"""

import bisect
from dataclasses import asdict, dataclass
from datetime import date

import numpy as np
import pandas as pd

from ft.backtest.engine import Bars, Costs
from ft.backtest.portfolio import CdiIndex

SESSIONS_PER_MONTH = 21


@dataclass(frozen=True)
class MomentumParams:
    lookback_months: int = 12
    top_n: int = 10
    regime_filter: bool = False
    code: str = "M1"

    def name(self) -> str:
        parts = [f"{self.lookback_months}-1 meses", f"top {self.top_n}"]
        if self.regime_filter:
            parts.append("regime IBOV")
        return ", ".join(parts)

    def as_dict(self) -> dict:
        return asdict(self)


def variants() -> list[MomentumParams]:
    return [
        MomentumParams(lookback_months=lb, top_n=n, regime_filter=rg)
        for lb in (6, 12)
        for n in (5, 10)
        for rg in (False, True)
    ]


def build_matrices(bars: dict[str, Bars]) -> tuple[pd.DataFrame, pd.DataFrame]:
    closes = {t: pd.Series(b.close, index=b.dates) for t, b in bars.items()}
    opens = {t: pd.Series(b.open, index=b.dates) for t, b in bars.items()}
    close = pd.DataFrame(closes).sort_index()
    open_ = pd.DataFrame(opens).reindex(close.index)
    return close, open_


def month_end_positions(dates: list[date]) -> list[int]:
    """Índices do último pregão de cada mês (exceto o mês corrente/incompleto no fim)."""
    out = []
    for i in range(len(dates) - 1):
        if (dates[i].year, dates[i].month) != (dates[i + 1].year, dates[i + 1].month):
            out.append(i)
    return out


def scores_at(close: pd.DataFrame, i: int, lookback_months: int) -> pd.Series:
    skip = SESSIONS_PER_MONTH
    start = SESSIONS_PER_MONTH * lookback_months
    if i - start < 0:
        return pd.Series(dtype="float64")
    now, recent, past = close.iloc[i], close.iloc[i - skip], close.iloc[i - start]
    valid = now.notna() & recent.notna() & past.notna() & (past > 0)
    return (recent[valid] / past[valid] - 1).sort_values(ascending=False)


def simulate(
    close: pd.DataFrame,
    open_: pd.DataFrame,
    p: MomentumParams,
    costs: Costs,
    cdi: CdiIndex | None,
    regime: dict[date, bool] | None,
    initial: float = 100_000.0,
) -> pd.Series:
    """Retorna a curva diária de patrimônio (índice = datas)."""
    dates = list(close.index)
    rebalance_at = set(month_end_positions(dates))
    unit_cost = costs.fee_pct_per_side + costs.slippage_pct_per_side
    last_close = close.ffill()

    cash = initial
    shares: dict[str, float] = {}
    pending: list[str] | None = None  # nova carteira decidida em D, executada em D+1
    equity = np.empty(len(dates))

    for i, day in enumerate(dates):
        if i > 0 and cdi is not None:
            cash *= cdi.growth(dates[i - 1], day)

        if pending is not None:
            prices = open_.iloc[i].fillna(last_close.iloc[i])
            value = cash + sum(q * prices[t] for t, q in shares.items())
            target_each = value / p.top_n if pending else 0.0
            new_shares: dict[str, float] = {}
            traded = 0.0
            for t in set(shares) | set(pending):
                price = prices.get(t, np.nan)
                if not np.isfinite(price) or price <= 0:
                    if t in shares:  # sem preço para vender hoje: mantém até haver
                        new_shares[t] = shares[t]
                    continue
                current = shares.get(t, 0.0) * price
                target = target_each if t in pending else 0.0
                traded += abs(target - current)
                if target > 0:
                    new_shares[t] = target / price
            invested = sum(q * prices[t] for t, q in new_shares.items())
            cash = value - invested - traded * unit_cost
            shares = new_shares
            pending = None

        marks = last_close.iloc[i]
        equity[i] = cash + sum(q * marks[t] for t, q in shares.items())

        if i in rebalance_at:
            if p.regime_filter and not (regime or {}).get(day, False):
                pending = []
            else:
                ranked = scores_at(close, i, p.lookback_months)
                pending = list(ranked[ranked > 0].index[: p.top_n])

    return pd.Series(equity, index=dates)


def curve_stats(curve: pd.Series, start: date, end: date) -> dict:
    seg = curve[(curve.index >= start) & (curve.index <= end)]
    if len(seg) < 2:
        return {}
    values = seg.to_numpy()
    peak = np.maximum.accumulate(values)
    years = max((seg.index[-1] - seg.index[0]).days / 365.25, 1e-9)
    multiple = values[-1] / values[0]
    return {
        "start": seg.index[0].isoformat(),
        "end": seg.index[-1].isoformat(),
        "cagr_pct": round((multiple ** (1 / years) - 1) * 100, 2),
        "max_drawdown_pct": round(float(((peak - values) / peak).max() * 100), 2),
        "total_return_pct": round((multiple - 1) * 100, 2),
    }


def cdi_curve(cdi: CdiIndex, dates: list[date]) -> pd.Series:
    return pd.Series([cdi.at(d) for d in dates], index=dates)


def nearest_index(dates: list[date], day: date) -> int:
    return max(bisect.bisect_left(dates, day), 0)
