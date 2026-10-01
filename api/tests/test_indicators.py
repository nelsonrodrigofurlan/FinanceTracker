import math

import pandas as pd
import pytest

from ft.indicators.core import ema, rsi, sma

S = pd.Series([10.0, 11.0, 12.0, 11.0, 13.0, 14.0])


def test_sma_hand_computed():
    out = sma(S, 3)
    assert math.isnan(out[0]) and math.isnan(out[1])
    assert out[2] == pytest.approx(11.0)  # (10+11+12)/3
    assert out[3] == pytest.approx(34 / 3)  # (11+12+11)/3
    assert out[5] == pytest.approx(38 / 3)  # (11+13+14)/3


def test_ema_seeded_with_sma():
    out = ema(S, 3)  # alfa = 0.5
    assert math.isnan(out[1])
    assert out[2] == pytest.approx(11.0)  # semente = MMA(3)
    assert out[3] == pytest.approx(0.5 * 11 + 0.5 * 11.0)  # 11.0
    assert out[4] == pytest.approx(0.5 * 13 + 0.5 * 11.0)  # 12.0
    assert out[5] == pytest.approx(0.5 * 14 + 0.5 * 12.0)  # 13.0


def test_rsi_wilder_hand_computed():
    # variações: +1, +1, -1, +2, +1
    out = rsi(S, 2)
    assert math.isnan(out[0]) and math.isnan(out[1])
    # semente: ganho médio (1+1)/2 = 1, perda média 0 → 100
    assert out[2] == pytest.approx(100.0)
    # i=2 (variação -1): ganho = (1*1+0)/2 = 0.5; perda = (0*1+1)/2 = 0.5 → RS=1 → 50
    assert out[3] == pytest.approx(50.0)
    # variação +2: ganho = (0.5+2)/2 = 1.25; perda = (0.5+0)/2 = 0.25 → RS=5 → 83.333
    assert out[4] == pytest.approx(100 - 100 / 6)
    # variação +1: ganho = (1.25+1)/2 = 1.125; perda = 0.125 → RS=9 → 90
    assert out[5] == pytest.approx(90.0)


def test_rsi_flat_series_is_50():
    assert rsi(pd.Series([5.0] * 5), 2).iloc[-1] == pytest.approx(50.0)


def test_rsi_bounded():
    series = pd.Series([100 + ((i * 7) % 11) - 5 for i in range(200)], dtype="float64")
    values = rsi(series, 14).dropna()
    assert ((values >= 0) & (values <= 100)).all()


def test_short_series_returns_nan():
    assert ema(pd.Series([1.0, 2.0]), 3).isna().all()
    assert rsi(pd.Series([1.0, 2.0]), 2).isna().all()


def test_invalid_period():
    with pytest.raises(ValueError):
        sma(S, 0)
