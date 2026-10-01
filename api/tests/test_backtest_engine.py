"""Cenários sintéticos para as regras de execução do motor (docs/ARQUITETURA.md §7.1)."""

from dataclasses import dataclass, field
from datetime import date, timedelta

import numpy as np
import pandas as pd
import pytest

from ft.backtest.data import adjust, cut_at_last_break
from ft.backtest.engine import Bars, Costs, Exit, Order, run_asset
from ft.backtest.metrics import ApprovalCriteria, compute, evaluate

NO_COSTS = Costs(fee_pct_per_side=0.0, slippage_pct_per_side=0.0)


def make_bars(rows: list[tuple[float, float, float, float]]) -> Bars:
    start = date(2020, 1, 1)
    arr = np.array(rows, dtype="float64")
    return Bars(
        ticker="TEST3",
        dates=[start + timedelta(days=i) for i in range(len(rows))],
        open=arr[:, 0],
        high=arr[:, 1],
        low=arr[:, 2],
        close=arr[:, 3],
        volume=np.full(len(rows), 1000.0),
    )


@dataclass
class Scripted:
    """Setup de teste: emite as ordens dadas nos índices indicados."""

    orders: dict[int, Order]
    exits: dict[int, Exit] = field(default_factory=dict)
    code: str = "T"

    def prepare(self, bars):
        return {}

    def signal(self, t, bars, ind):
        return self.orders.get(t)

    def update_pending(self, t, order, bars, ind):
        return order

    def manage(self, t, pos, bars, ind):
        return self.exits.get(t)


def test_stop_entry_fills_at_level_and_exits_at_target():
    bars = make_bars(
        [
            (10, 10.5, 9.5, 10),  # 0: sinal
            (10, 11.2, 10.2, 11),  # 1: rompe 11.0 → entra a 11.0 (mínima acima do stop)
            (11, 13.5, 10.8, 13),  # 2: alvo 13.0 (2R, risco 1.0)
        ]
    )
    setup = Scripted({0: Order(kind="stop", level=11.0, stop=10.0, target_r=2.0, expires=1)})
    [trade] = run_asset(setup, bars, NO_COSTS)
    assert trade.entry_price == 11.0
    assert trade.exit_price == 13.0
    assert trade.exit_reason == "alvo"
    assert trade.r_multiple == pytest.approx(2.0)


def test_gap_up_entry_pays_the_open():
    bars = make_bars([(10, 10.5, 9.5, 10), (11.5, 12, 11.4, 11.8), (11.8, 12, 11.7, 11.9)])
    setup = Scripted({0: Order(kind="stop", level=11.0, stop=10.0, expires=1)})
    [trade] = run_asset(setup, bars, NO_COSTS)
    assert trade.entry_price == 11.5  # abriu acima do nível: paga a abertura


def test_gap_down_through_stop_exits_at_open():
    bars = make_bars(
        [
            (10, 10.5, 9.5, 10),
            (10, 11.2, 10.5, 11),  # entra a 11.0, stop 10.0
            (9.0, 9.5, 8.5, 9.2),  # abre em 9.0, abaixo do stop
        ]
    )
    setup = Scripted({0: Order(kind="stop", level=11.0, stop=10.0, expires=1)})
    [trade] = run_asset(setup, bars, NO_COSTS)
    assert trade.exit_price == 9.0
    assert trade.r_multiple == pytest.approx(-2.0)  # perdeu 2R por causa do gap


def test_stop_and_target_same_candle_counts_as_stop():
    bars = make_bars(
        [
            (10, 10.5, 9.5, 10),
            (10, 11.2, 10.5, 11),  # entra 11.0; stop 10.0; alvo 13.0
            (11, 13.5, 9.8, 12),  # toca alvo e stop
        ]
    )
    setup = Scripted({0: Order(kind="stop", level=11.0, stop=10.0, target_r=2.0, expires=1)})
    [trade] = run_asset(setup, bars, NO_COSTS)
    assert trade.exit_reason == "stop"
    assert trade.r_multiple == pytest.approx(-1.0)


def test_entry_candle_checks_stop_but_not_target():
    bars = make_bars(
        [
            (10, 10.5, 9.5, 10),
            (10, 13.5, 10.2, 13),  # entra 11.0 e a máxima passa do alvo 13.0 no mesmo candle
            (13, 13.2, 12.5, 12.8),  # alvo só é avaliado a partir daqui
        ]
    )
    setup = Scripted({0: Order(kind="stop", level=11.0, stop=10.0, target_r=2.0, expires=1)})
    [trade] = run_asset(setup, bars, NO_COSTS)
    assert trade.exit_reason == "alvo"
    assert trade.exit_date == bars.dates[2]
    assert trade.exit_price == 13.0  # abriu exatamente no alvo


def test_unfilled_stop_order_expires():
    bars = make_bars([(10, 10.5, 9.5, 10), (10, 10.8, 9.9, 10.2), (10.2, 11.5, 10, 11)])
    setup = Scripted({0: Order(kind="stop", level=11.0, stop=10.0, expires=1)})
    assert run_asset(setup, bars, NO_COSTS) == []  # rompeu só no candle 2, já expirada


def test_close_entry_and_scripted_exit_with_costs():
    bars = make_bars([(10, 10.5, 9.5, 10), (10, 10.6, 9.8, 10.4), (10.4, 11, 10.2, 11)])
    costs = Costs(fee_pct_per_side=0.001, slippage_pct_per_side=0.0)
    setup = Scripted({0: Order(kind="close", stop=9.0)}, exits={2: Exit("close", "saida")})
    [trade] = run_asset(setup, bars, costs)
    pnl = 11 - 10 - (10 + 11) * 0.001
    assert trade.r_multiple == pytest.approx(pnl / 1.0)
    assert trade.exit_reason == "saida"


def test_no_price_stop_uses_risk_unit():
    bars = make_bars([(10, 10.5, 9.5, 10), (10, 10.2, 5.0, 9.0), (9, 9.5, 8.8, 9.5)])
    setup = Scripted({0: Order(kind="close", risk_distance=2.0)}, exits={2: Exit("close", "saida")})
    [trade] = run_asset(setup, bars, NO_COSTS)
    assert trade.exit_reason == "saida"  # mínima 5.0 não estopa: não há stop de preço
    assert trade.r_multiple == pytest.approx((9.5 - 10) / 2.0)


def test_open_position_closed_at_end_of_data():
    bars = make_bars([(10, 10.5, 9.5, 10), (10, 10.6, 9.8, 10.4)])
    [trade] = run_asset(Scripted({0: Order(kind="close", stop=9.0)}), bars, NO_COSTS)
    assert trade.exit_reason == "fim_dos_dados"


def test_adjust_scales_ohlc_by_adj_factor():
    frame = pd.DataFrame(
        {"open": [10.0], "high": [12.0], "low": [9.0], "close": [10.0], "adj_close": [5.0]}
    )
    out = adjust(frame)
    assert out[["open", "high", "low", "close"]].iloc[0].tolist() == [5.0, 6.0, 4.5, 5.0]


def test_cut_at_last_break_keeps_segment_after_gap():
    frame = pd.DataFrame({"date": [date(2019, 1, 1), date(2019, 1, 2), date(2025, 6, 1)]})
    out = cut_at_last_break(frame)
    assert out["date"].tolist() == [date(2025, 6, 1)]


def test_metrics_and_approval():
    bars = make_bars([(10, 10.5, 9.5, 10)] * 3)
    trades = [
        _trade(bars, r, day)
        for day, r in enumerate([1.0, -1.0, 2.0, -1.0, 1.5] * 16)  # 80 trades
    ]
    split = trades[40].entry_date  # 40 dentro e 40 fora da amostra
    metrics, approval = evaluate(trades, split, ApprovalCriteria())
    m = metrics["out_of_sample"]
    assert m["trades"] == 40
    assert metrics["in_sample"]["trades"] == 40
    assert m["expectancy_r"] == pytest.approx(0.5)
    assert m["profit_factor"] == pytest.approx(4.5 / 2.0)
    assert m["win_rate"] == pytest.approx(60.0)
    assert approval["approved"] is True
    assert compute([])["trades"] == 0


def test_approval_fails_without_in_sample_reference():
    bars = make_bars([(10, 10.5, 9.5, 10)] * 3)
    trades = [_trade(bars, r, day) for day, r in enumerate([1.0, -0.5] * 20)]
    _, approval = evaluate(trades, trades[0].entry_date, ApprovalCriteria())
    assert approval["checks"]["no_severe_degradation"] is False
    assert approval["approved"] is False


def _trade(bars, r, day):
    from ft.backtest.engine import Trade

    d = date(2020, 1, 1) + timedelta(days=day)
    return Trade("TEST3", d, 10.0, d, 10.0 + r, 9.0, None, r, r * 10, 1, "x")
