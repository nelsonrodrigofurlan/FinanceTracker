"""Indicadores técnicos — implementação própria, com fórmulas explícitas.

Convenções (iguais às usadas nos setups e no backtest):
- MMA(n): média aritmética dos últimos n valores; indefinida (NaN) antes de n valores.
- MME(n): alfa = 2 / (n + 1); semente = MMA dos n primeiros valores; NaN antes disso.
- IFR(n) de Wilder: médias de ganhos/perdas com suavização 1/n, semeadas pela média
  simples das n primeiras variações. Sem perdas no período → 100; sem variação → 50.
"""

import numpy as np
import pandas as pd


def sma(values: pd.Series, n: int) -> pd.Series:
    _check_period(n)
    return values.rolling(window=n, min_periods=n).mean()


def ema(values: pd.Series, n: int) -> pd.Series:
    _check_period(n)
    data = values.to_numpy(dtype="float64")
    out = np.full(len(data), np.nan)
    if len(data) < n:
        return pd.Series(out, index=values.index)
    alpha = 2.0 / (n + 1)
    out[n - 1] = data[:n].mean()
    for i in range(n, len(data)):
        out[i] = alpha * data[i] + (1 - alpha) * out[i - 1]
    return pd.Series(out, index=values.index)


def rsi(values: pd.Series, n: int) -> pd.Series:
    _check_period(n)
    data = values.to_numpy(dtype="float64")
    out = np.full(len(data), np.nan)
    if len(data) <= n:
        return pd.Series(out, index=values.index)

    change = np.diff(data)
    gains = np.where(change > 0, change, 0.0)
    losses = np.where(change < 0, -change, 0.0)

    avg_gain = gains[:n].mean()
    avg_loss = losses[:n].mean()
    out[n] = _rsi_value(avg_gain, avg_loss)
    for i in range(n, len(change)):
        avg_gain = (avg_gain * (n - 1) + gains[i]) / n
        avg_loss = (avg_loss * (n - 1) + losses[i]) / n
        out[i + 1] = _rsi_value(avg_gain, avg_loss)
    return pd.Series(out, index=values.index)


def _rsi_value(avg_gain: float, avg_loss: float) -> float:
    if avg_loss == 0:
        return 50.0 if avg_gain == 0 else 100.0
    return 100.0 - 100.0 / (1.0 + avg_gain / avg_loss)


def _check_period(n: int) -> None:
    if n < 1:
        raise ValueError("Período precisa ser >= 1")
