from datetime import date, timedelta

import numpy as np
import pandas as pd
import pytest

from ft.backtest.engine import Costs
from ft.backtest.momentum import (
    MomentumParams,
    curve_stats,
    month_end_positions,
    scores_at,
    simulate,
    variants,
)

NO_COSTS = Costs(fee_pct_per_side=0.0, slippage_pct_per_side=0.0)


def business_days(start: date, n: int) -> list[date]:
    out, d = [], start
    while len(out) < n:
        if d.weekday() < 5:
            out.append(d)
        d += timedelta(days=1)
    return out


def test_month_end_positions_excludes_last_incomplete_month():
    dates = [date(2020, 1, 30), date(2020, 1, 31), date(2020, 2, 3), date(2020, 2, 4)]
    assert month_end_positions(dates) == [1]


def test_scores_skip_most_recent_month():
    n = 60
    idx = list(range(n))
    # A sobe forte no mês mais recente (ignorado); B sobe antes disso.
    a = [10.0] * 39 + [10.0] * 0 + list(np.linspace(10, 20, 21))
    b = list(np.linspace(10, 15, 39)) + [15.0] * 21
    close = pd.DataFrame({"A": a, "B": b}, index=idx)
    scores = scores_at(close, n - 1, lookback_months=2)  # janela: pregões 17 → 38
    assert scores.index[0] == "B"
    assert scores["A"] == pytest.approx(0.0)


def test_simulate_buys_top_at_next_open_and_charges_costs():
    dates = business_days(date(2020, 1, 1), 70)
    up = np.linspace(10, 20, 70)
    flat = np.full(70, 10.0)
    close = pd.DataFrame({"UP": up, "FLAT": flat}, index=dates)
    open_ = close.copy()
    p = MomentumParams(lookback_months=2, top_n=1)

    curve = simulate(close, open_, p, NO_COSTS, cdi=None, regime=None)
    ends = month_end_positions(dates)
    first_trade = next(e for e in ends if e >= 42) + 1  # precisa de 2 meses de histórico
    # Antes do primeiro rebalanceamento executado: tudo em caixa.
    assert curve.iloc[first_trade - 1] == pytest.approx(100_000)
    # Depois: patrimônio acompanha UP (comprado na abertura de first_trade).
    expected = 100_000 * up[-1] / up[first_trade]
    assert curve.iloc[-1] == pytest.approx(expected, rel=1e-6)

    with_costs = simulate(close, open_, p, Costs(0.001, 0.0), cdi=None, regime=None)
    assert with_costs.iloc[-1] < curve.iloc[-1]


def test_regime_filter_keeps_cash():
    dates = business_days(date(2020, 1, 1), 70)
    close = pd.DataFrame({"UP": np.linspace(10, 20, 70)}, index=dates)
    p = MomentumParams(lookback_months=2, top_n=1, regime_filter=True)
    curve = simulate(close, close, p, NO_COSTS, cdi=None, regime={d: False for d in dates})
    assert curve.iloc[-1] == pytest.approx(100_000)


def test_curve_stats_and_variants():
    dates = [date(2020, 1, 1), date(2020, 7, 1), date(2021, 1, 1)]
    stats = curve_stats(pd.Series([100.0, 80.0, 121.0], index=dates), dates[0], dates[-1])
    assert stats["max_drawdown_pct"] == pytest.approx(20.0)
    assert stats["total_return_pct"] == pytest.approx(21.0)
    assert len(variants()) == 8


def test_only_eligible_assets_are_ranked():
    dates = business_days(date(2020, 1, 1), 70)
    close = pd.DataFrame(
        {"UP": np.linspace(10, 20, 70), "FLAT_UP": np.linspace(10, 12, 70)}, index=dates
    )
    eligible = pd.DataFrame({"UP": False, "FLAT_UP": True}, index=dates)
    p = MomentumParams(lookback_months=2, top_n=1)
    curve = simulate(close, close, p, NO_COSTS, None, None, eligible=eligible)
    # comprou FLAT_UP (UP fora do universo): resultado acompanha FLAT_UP, não UP
    assert curve.iloc[-1] < 100_000 * 20 / 15


def test_delisted_position_is_sold_at_last_price():
    dates = business_days(date(2020, 1, 1), 70)
    gone = np.linspace(10, 20, 70)
    gone[55:] = np.nan  # deixa de negociar no pregão 55
    close = pd.DataFrame({"GONE": gone}, index=dates)
    p = MomentumParams(lookback_months=2, top_n=1)
    curve = simulate(close, close, p, NO_COSTS, None, None)
    assert curve.iloc[-1] == pytest.approx(curve.iloc[56])  # patrimônio congelado em caixa
