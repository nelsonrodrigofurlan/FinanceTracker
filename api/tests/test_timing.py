from datetime import date, timedelta

import numpy as np
import pandas as pd
import pytest

from ft.backtest.engine import Costs
from ft.backtest.timing import ETF_FEE_PER_YEAR, TRADING_DAYS, TimingRule, signal, simulate

NO_COSTS = Costs(0.0, 0.0)


def idx(n):
    return [date(2020, 1, 1) + timedelta(days=i) for i in range(n)]


def test_position_lags_signal_by_two_closes():
    d = idx(5)
    index = pd.Series([100, 110, 121, 133.1, 146.41], index=d)  # +10% ao dia
    in_eq = pd.Series([True, False, False, False, False], index=d)  # sinal só no dia 0
    curve, switches = simulate(index, pd.Series(0.0, index=d), in_eq, NO_COSTS)
    fee = ETF_FEE_PER_YEAR / TRADING_DAYS
    # dia 1: ainda em renda fixa (troca no fechamento do dia 1); dia 2: em ações; dia 3: sai
    assert curve.iloc[1] == pytest.approx(100_000)
    assert curve.iloc[2] == pytest.approx(100_000 * (1.10 - fee))
    assert curve.iloc[3] == pytest.approx(curve.iloc[2])
    assert switches == 2


def test_switch_costs_applied():
    d = idx(4)
    index = pd.Series([100.0] * 4, index=d)
    in_eq = pd.Series([True] * 4, index=d)
    curve, switches = simulate(index, pd.Series(0.0, index=d), in_eq, Costs(0.001, 0.0))
    assert switches == 1
    fee = ETF_FEE_PER_YEAR / TRADING_DAYS
    assert curve.iloc[-1] == pytest.approx(100_000 * (1 - fee - 0.001) * (1 - fee))


def test_sma_daily_signal():
    d = idx(5)
    index = pd.Series([10, 10, 10, 12, 8.0], index=d)
    sig = signal(index, pd.Series(1.0, index=d), TimingRule("sma_daily", 3))
    assert sig.tolist() == [False, False, False, True, False]


def test_abs_momentum_compares_with_cdi():
    d = [date(2020, m, 28) for m in range(1, 13)] + [date(2021, 1, 28)]
    d = sorted(d + [x + timedelta(days=1) for x in d])  # 2 pregões por mês
    n = len(d)
    index = pd.Series(np.linspace(100, 110, n), index=d)  # ~+10% no período
    cdi_fast = pd.Series(np.linspace(1, 1.5, n), index=d)  # renda fixa +50%
    sig = signal(index, cdi_fast, TimingRule("abs_momentum", 1))
    assert not sig.any()  # ações nunca rendem mais que o CDI aqui
