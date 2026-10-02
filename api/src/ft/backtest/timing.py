"""Alternância Ibovespa ↔ CDI por tendência (market timing do índice).

Regras (definidas antes dos resultados):
- Sinal calculado no fechamento do dia t; a nova posição só vale a partir do fechamento de t+1
  (o retorno de t→t+1 ainda é da posição antiga) — execução conservadora.
- Em ações: retorno diário do índice Ibovespa (proxy do BOVA11), menos 0,10% a.a. de taxa de
  administração do BOVA11 (regulamento BlackRock, verificado em 2026-10-02).
- Em renda fixa: CDI do dia (BCB SGS 12).
- Cada troca custa taxa B3 + slippage (Costs) sobre o patrimônio.
- Imposto de renda NÃO modelado (cada troca realiza ganho tributável) — [VERIFICAR].
"""

from dataclasses import dataclass
from datetime import date

import numpy as np
import pandas as pd

from ft.backtest.engine import Costs

ETF_FEE_PER_YEAR = 0.0010
TRADING_DAYS = 252


@dataclass(frozen=True)
class TimingRule:
    kind: str  # "sma_daily" | "sma_monthly" | "abs_momentum"
    n: int  # pregões (sma_daily) ou meses (sma_monthly, abs_momentum)

    def name(self) -> str:
        return {
            "sma_daily": f"Ibov > MMA{self.n} (diário)",
            "sma_monthly": f"Ibov > média de {self.n} meses (mensal)",
            "abs_momentum": f"retorno {self.n}m Ibov > CDI (mensal)",
        }[self.kind]


def rules() -> list[TimingRule]:
    return [
        TimingRule("sma_daily", 200),
        TimingRule("sma_daily", 100),
        TimingRule("sma_monthly", 10),
        TimingRule("abs_momentum", 12),
    ]


def _month_end_mask(dates: list[date]) -> np.ndarray:
    out = np.zeros(len(dates), dtype=bool)
    for i in range(len(dates) - 1):
        out[i] = (dates[i].year, dates[i].month) != (dates[i + 1].year, dates[i + 1].month)
    return out


def signal(index: pd.Series, cdi_factor: pd.Series, rule: TimingRule) -> pd.Series:
    """True = em ações, decidido no fechamento de cada dia (NaN → renda fixa)."""
    dates = list(index.index)
    if rule.kind == "sma_daily":
        sma = index.rolling(rule.n, min_periods=rule.n).mean()
        return (index > sma).fillna(False)

    month_end = _month_end_mask(dates)
    if rule.kind == "sma_monthly":
        monthly = index[month_end]
        sma = monthly.rolling(rule.n, min_periods=rule.n).mean()
        decision = monthly > sma
    else:  # abs_momentum: retorno do índice em n meses > retorno do CDI em n meses
        monthly = index[month_end]
        cdi_m = cdi_factor[month_end]
        decision = (monthly / monthly.shift(rule.n)) > (cdi_m / cdi_m.shift(rule.n))
        decision = decision.where(monthly.shift(rule.n).notna(), False)
    # Decisão mensal vale até o próximo fim de mês.
    return decision.reindex(index.index).ffill().fillna(False).astype(bool)


def simulate(
    index: pd.Series,
    cdi_daily_rate: pd.Series,
    in_equity: pd.Series,
    costs: Costs,
    initial: float = 100_000.0,
) -> tuple[pd.Series, int]:
    """Curva de patrimônio e número de trocas. `cdi_daily_rate` em fração (0,0005 = 0,05%)."""
    eq_ret = index.pct_change().fillna(0.0) - ETF_FEE_PER_YEAR / TRADING_DAYS
    rf_ret = cdi_daily_rate.reindex(index.index).fillna(0.0)
    # Posição vigente no retorno do dia t = decisão tomada no fechamento de t-2
    # (sinal em t-2, troca efetivada no fechamento de t-1).
    position = in_equity.shift(2).fillna(False).astype(bool)
    daily = np.where(position, eq_ret, rf_ret)
    switches = position.ne(position.shift(1)).to_numpy(copy=True)
    switches[0] = False
    unit_cost = costs.fee_pct_per_side + costs.slippage_pct_per_side
    # Troca = vender um lado e comprar o outro; renda fixa sem custo de corretagem/B3.
    daily = daily - np.where(switches, unit_cost, 0.0)
    curve = initial * np.cumprod(1 + daily)
    return pd.Series(curve, index=index.index), int(switches.sum())
