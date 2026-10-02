import numpy as np

from ft.backtest.setups import Donchian
from ft.signals import live
from tests.test_backtest_engine import make_bars


def breakout_bars():
    rows = [(10, 10.5, 9.5, 10)] * 40 + [(10, 13, 10, 12.8)]  # rompe a máxima de 20 no fim
    bars = make_bars(rows)
    bars.volume[:] = 1000.0
    bars.volume[-1] = 5000.0
    bars.regime = np.ones(len(rows), dtype=bool)
    return bars


def test_scan_emits_signal_for_operable_strategy(monkeypatch):
    setup = Donchian()
    monkeypatch.setattr(
        live,
        "operable_strategies",
        lambda conn: [(7, "S4", "padrão", setup.params, "observation", None)],
    )
    [sig] = live.scan(None, {"TEST3": breakout_bars()})
    assert sig["strategy_id"] == 7 and sig["status"] == "observation"
    assert sig["order_kind"] == "open"  # Donchian entra na abertura seguinte
    assert sig["ref_price"] == 12.8
    assert sig["stop_distance"] > 0


def test_scan_respects_regime_filter(monkeypatch):
    setup = Donchian(regime_filter=True)
    monkeypatch.setattr(
        live, "operable_strategies", lambda conn: [(7, "S4", "x", setup.params, "approved", None)]
    )
    bars = breakout_bars()
    bars.regime[-1] = False
    assert live.scan(None, {"TEST3": bars}) == []


def test_no_operable_strategies_no_signals(monkeypatch):
    monkeypatch.setattr(live, "operable_strategies", lambda conn: [])
    assert live.scan(None, {"TEST3": breakout_bars()}) == []


def test_daily_summary_lists_signals_and_disclaimer():
    from ft.alerts.telegram import daily_summary

    sig = {
        "ticker": "PETR4",
        "setup": "S4",
        "status": "observation",
        "order_kind": "open",
        "entry_level": None,
        "ref_price": 49.77,
    }
    text = daily_summary({"update": {"assets": 93}}, [sig], "staging")
    assert "PETR4" in text and "OBSERVAÇÃO" in text and "não é recomendação" in text
    assert "nenhum" in daily_summary({"update": {"assets": 93}}, [], "staging")


def test_telegram_send_skips_when_not_configured():
    from ft.alerts.telegram import send
    from ft.config import Settings

    assert send(Settings(_env_file=None), "oi") is False
