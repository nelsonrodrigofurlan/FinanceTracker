from datetime import date

import pytest

from ft.backtest.portfolio import PortfolioParams, SimTrade, simulate
from ft.backtest.walkforward import WalkForwardParams, walk_forward

# --- walk-forward ----------------------------------------------------------------------------


def test_walk_forward_uses_only_past_years():
    per_year = {
        # A foi ótima no passado e ruim no ano testado; B o contrário.
        "A": {2010: (40, 20.0), 2011: (40, 20.0), 2012: (40, -40.0)},
        "B": {2010: (40, -4.0), 2011: (40, -4.0), 2012: (40, 40.0)},
    }
    out = walk_forward(per_year, WalkForwardParams(lookback=2, min_trades=30))
    [row] = out["years"]
    assert row["year"] == 2012
    assert row["chosen_variant"] == "A"  # escolha feita sem ver 2012
    assert row["expectancy_r"] == pytest.approx(-1.0)
    assert out["expectancy_r"] == pytest.approx(-1.0)


def test_walk_forward_skips_when_past_best_is_negative():
    per_year = {"A": {2010: (40, -4.0), 2011: (40, -4.0), 2012: (40, 40.0)}}
    out = walk_forward(per_year, WalkForwardParams(lookback=2, min_trades=30))
    assert out["years"][0]["would_trade"] is False
    assert out["trades"] == 0 and out["expectancy_r"] is None


def test_walk_forward_requires_min_trades_in_window():
    per_year = {"A": {2010: (5, 5.0), 2011: (5, 5.0), 2012: (40, 4.0)}}
    out = walk_forward(per_year, WalkForwardParams(lookback=2, min_trades=30))
    assert out["years"] == []


# --- carteira --------------------------------------------------------------------------------


def trade(ticker, entry, exit_, price=10.0, stop=9.0, r=1.0):
    return SimTrade(ticker, entry, exit_, price, stop, r)


def test_position_sized_by_risk():
    p = PortfolioParams(initial_capital=10_000, risk_pct=1, max_positions=5, max_position_pct=100)
    out = simulate([trade("A", date(2020, 1, 1), date(2020, 1, 10), r=2.0)], p)
    # risco R$100 / R$1 por ação = 100 ações; ganho 2R = 2 × 100 × 1 = R$200
    assert out["final_equity"] == pytest.approx(10_200)
    assert out["trades_taken"] == 1


def test_position_capped_by_max_position_pct():
    p = PortfolioParams(initial_capital=10_000, risk_pct=5, max_positions=5, max_position_pct=10)
    # pelo risco: 500 ações; pelo teto de 10%: R$1.000 / R$10 = 100 ações
    out = simulate([trade("A", date(2020, 1, 1), date(2020, 1, 10), r=1.0)], p)
    assert out["final_equity"] == pytest.approx(10_100)


def test_max_positions_skips_extra_signals():
    p = PortfolioParams(initial_capital=10_000, risk_pct=1, max_positions=1, max_position_pct=100)
    trades = [
        trade("A", date(2020, 1, 1), date(2020, 1, 10)),
        trade("B", date(2020, 1, 2), date(2020, 1, 5)),  # sem vaga
        trade("C", date(2020, 1, 10), date(2020, 1, 12)),  # vaga liberada no mesmo dia
    ]
    out = simulate(trades, p)
    assert out["trades_taken"] == 2
    assert out["trades_skipped_no_slot"] == 1


def test_drawdown_measured_on_realized_equity():
    p = PortfolioParams(initial_capital=10_000, risk_pct=1, max_positions=1, max_position_pct=100)
    trades = [
        trade("A", date(2020, 1, 1), date(2020, 1, 2), r=2.0),  # 10.200
        trade("B", date(2020, 1, 3), date(2020, 1, 4), r=-1.0),  # perde 1% de 10.200
    ]
    out = simulate(trades, p)
    assert out["max_drawdown_pct"] == pytest.approx(1.0, abs=0.01)


# --- CDI e comparações ------------------------------------------------------------------


def test_idle_cash_earns_cdi():
    from ft.backtest.portfolio import CdiIndex

    # 1% ao dia em 3 dias úteis (valor exagerado para facilitar a conta)
    cdi = CdiIndex({date(2020, 1, 2): 1.0, date(2020, 1, 3): 1.0, date(2020, 1, 6): 1.0})
    p = PortfolioParams(initial_capital=10_000, risk_pct=1, max_positions=5, max_position_pct=100)
    # Trade com resultado zero: só os juros mudam o patrimônio.
    trades = [trade("A", date(2020, 1, 1), date(2020, 1, 6), r=0.0)]
    out = simulate(trades, p, cdi)
    # Posição de 100 ações × R$10 = R$1.000 imobilizados; R$9.000 rendem 3 dias a 1%.
    assert out["cash_interest"] == pytest.approx(9_000 * (1.01**3 - 1), abs=0.01)  # centavos


def test_benchmark_cagr_and_drawdown():
    from ft.backtest.portfolio import benchmark

    series = {date(2020, 1, 1): 100.0, date(2020, 7, 1): 80.0, date(2021, 1, 1): 121.0}
    out = benchmark(series, 1_000, date(2020, 1, 1), date(2021, 1, 1))
    assert out["total_return_pct"] == pytest.approx(21.0)
    assert out["max_drawdown_pct"] == pytest.approx(20.0)
    assert out["cagr_pct"] == pytest.approx(21.0, abs=0.1)  # ~1 ano
