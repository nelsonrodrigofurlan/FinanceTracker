"""Sinais dos setups em cenários mínimos (indicadores injetados à mão)."""

import numpy as np
import pytest

from ft.backtest.engine import Position
from ft.backtest.setups import IFR2, Donchian, Pullback, Setup91, Setup123, describe, variants
from tests.test_backtest_engine import make_bars

NAN = float("nan")


def bars_from_lows(lows, highs=None, closes=None):
    highs = highs or [lo + 1 for lo in lows]
    closes = closes or [lo + 0.5 for lo in lows]
    return make_bars([(c, h, lo, c) for lo, h, c in zip(lows, highs, closes, strict=True)])


def test_ifr2_signal_requires_trend_and_oversold():
    bars = bars_from_lows([10, 10, 10])
    s = IFR2(rsi_max=10, stop_atr=None)
    ind = {"rsi2": np.array([50, 5, 5.0]), "trend": np.array([5, 5, 20.0]), "atr": np.ones(3)}
    assert s.signal(0, bars, ind) is None  # IFR alto
    order = s.signal(1, bars, ind)
    assert order.kind == "close" and order.stop_distance is None and order.risk_distance == 2.0
    assert s.signal(2, bars, ind) is None  # abaixo da MMA200


def test_ifr2_exit_and_time_stop():
    bars = bars_from_lows([10] * 10, closes=[10, 10, 12] + [10] * 7)
    s = IFR2(exit="max2", time_stop=7)
    ind = {"max2": np.array([NAN, NAN, 11.5] + [20.0] * 7), "sma5": np.full(10, NAN)}
    pos = Position(entry_idx=0, entry_price=10, stop=-np.inf, initial_stop=8, target=None)
    assert s.manage(2, pos, bars, ind).reason == "saida_max2"
    assert s.manage(7, pos, bars, ind).reason == "stop_tempo"
    assert s.manage(5, pos, bars, ind) is None


def test_91_turn_up_and_rearm():
    bars = bars_from_lows([10, 9, 9.5, 10])
    s = Setup91()
    ind = {"ema": np.array([10, 9.8, 9.9, 10.0])}
    assert s.signal(1, bars, ind) is None
    order = s.signal(2, bars, ind)  # 9.9 > 9.8 <= 10 → virou para cima
    assert order.level == pytest.approx(bars.high[2] + 0.01)
    rearmed = s.update_pending(3, order, bars, ind)  # média segue subindo
    assert rearmed.level == pytest.approx(bars.high[3] + 0.01)
    ind_down = {"ema": np.array([10, 9.8, 9.9, 9.85])}
    assert s.update_pending(3, order, bars, ind_down) is None  # deixou de subir: cancela


def test_91_turn_down_raises_stop():
    bars = bars_from_lows([10, 11, 12, 11.5])
    s = Setup91()
    ind = {"ema": np.array([10, 11, 12, 11.9])}
    pos = Position(entry_idx=1, entry_price=11, stop=9.99, initial_stop=9.99, target=None)
    s.manage(3, pos, bars, ind)
    assert pos.stop == pytest.approx(11.5 - 0.01)


def test_123_pattern():
    bars = bars_from_lows([10, 9, 9.5])  # mínima do meio menor que as vizinhas
    s = Setup123(trend_sma=None)
    order = s.signal(2, bars, s.prepare(bars))
    assert order.stop == pytest.approx(9 - 0.01)
    assert order.level == pytest.approx(10.5 + 0.01)
    assert s.signal(2, bars_from_lows([10, 9.5, 9]), s.prepare(bars)) is None


def test_pullback_touch_of_ema():
    bars = bars_from_lows([10] * 7, closes=[10.4] * 7)
    s = Pullback(slope_lookback=5)
    ind = {"ema": np.array([9, 9, 9, 9, 9, 9.5, 10.02]), "trend": np.full(7, 5.0)}
    order = s.signal(6, bars, ind)  # mínima 10 <= 10.02*1.005 e fechamento 10.4 > 10.02
    assert order is not None and order.target_r == 2.0
    ind["ema"][6] = 10.5  # fechamento abaixo da média: sem sinal
    assert s.signal(6, bars, ind) is None


def test_donchian_breakout_with_volume():
    bars = bars_from_lows([10, 10], closes=[10.5, 12])
    bars.volume[:] = [1000, 2000]
    s = Donchian()
    ind = {"hh": np.array([NAN, 11.0]), "avgvol": np.array([NAN, 1000.0]), "atr": np.ones(2)}
    order = s.signal(1, bars, ind)
    assert order.kind == "open" and order.stop_distance == 2.0
    bars.volume[1] = 1200
    assert s.signal(1, bars, ind) is None  # volume insuficiente


def test_variants_have_readable_names():
    names = [describe(v) for v in variants()]
    assert "padrão" in names
    assert len(names) == len(set((v.code, n) for v, n in zip(variants(), names, strict=True)))
