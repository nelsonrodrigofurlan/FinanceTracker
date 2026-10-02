"""Setups S1–S5 (especificação em docs/ARQUITETURA.md §6). Todos long-only.

Parâmetros são hipóteses a testar, não valores definitivos. Cada setup expõe `params` para
que o resultado salvo seja reproduzível.
"""

from dataclasses import asdict, dataclass

import numpy as np
import pandas as pd

from ft.backtest.engine import TICK, Bars, Exit, Order, Position
from ft.indicators import core as ind


def _series(values: np.ndarray) -> pd.Series:
    return pd.Series(values, dtype="float64")


def _valid(*values: float) -> bool:
    return all(np.isfinite(v) for v in values)


def _rolling_max_prev(values: np.ndarray, n: int) -> np.ndarray:
    """Máximo dos n candles ANTERIORES (exclui o atual)."""
    return _series(values).shift(1).rolling(n, min_periods=n).max().to_numpy()


def _rolling_min_prev(values: np.ndarray, n: int) -> np.ndarray:
    return _series(values).shift(1).rolling(n, min_periods=n).min().to_numpy()


class _Base:
    code = ""

    @property
    def params(self) -> dict:
        return asdict(self)  # type: ignore[call-overload]

    def update_pending(self, t, order, bars, ind_):  # noqa: ANN001
        return order

    def manage(self, t, pos, bars, ind_):  # noqa: ANN001
        return None


# --- S1: IFR2 (Larry Connors) — reversão à média -------------------------------------------
@dataclass
class IFR2(_Base):
    rsi_max: float = 10.0
    trend_sma: int = 200
    entry: str = "close"  # "close" | "open"
    exit: str = "max2"  # "max2": fecha acima da máx. dos 2 anteriores | "sma5": acima da MMA5
    time_stop: int = 7
    stop_atr: float | None = None  # None = sem stop de preço (original de Connors)
    risk_atr: float = 2.0  # unidade R quando não há stop de preço
    code: str = "S1"

    def prepare(self, bars: Bars) -> dict:
        c = _series(bars.close)
        return {
            "rsi2": ind.rsi(c, 2).to_numpy(),
            "trend": ind.sma(c, self.trend_sma).to_numpy(),
            "sma5": ind.sma(c, 5).to_numpy(),
            "atr": ind.atr(_series(bars.high), _series(bars.low), c, 14).to_numpy(),
            "max2": _rolling_max_prev(bars.high, 2),
        }

    def signal(self, t, bars, i):  # noqa: ANN001
        c, rsi2, trend, atr = bars.close[t], i["rsi2"][t], i["trend"][t], i["atr"][t]
        if not _valid(rsi2, trend, atr) or c <= trend or rsi2 >= self.rsi_max:
            return None
        return Order(
            kind="close" if self.entry == "close" else "open",
            stop_distance=self.stop_atr * atr if self.stop_atr else None,
            risk_distance=self.risk_atr * atr,
        )

    def manage(self, t, pos, bars, i):  # noqa: ANN001
        c = bars.close[t]
        if self.exit == "max2" and _valid(i["max2"][t]) and c > i["max2"][t]:
            return Exit("close", "saida_max2")
        if self.exit == "sma5" and _valid(i["sma5"][t]) and c > i["sma5"][t]:
            return Exit("close", "saida_mma5")
        if t - pos.entry_idx >= self.time_stop:
            return Exit("close", "stop_tempo")
        return None


# --- S2: 9.1 (Larry Williams) — retomada de tendência --------------------------------------
@dataclass
class Setup91(_Base):
    ema_n: int = 9
    code: str = "S2"

    def prepare(self, bars: Bars) -> dict:
        return {"ema": ind.ema(_series(bars.close), self.ema_n).to_numpy()}

    def _turned_up(self, e: np.ndarray, t: int) -> bool:
        return t >= 2 and _valid(e[t], e[t - 1], e[t - 2]) and e[t] > e[t - 1] <= e[t - 2]

    def signal(self, t, bars, i):  # noqa: ANN001
        if not self._turned_up(i["ema"], t):
            return None
        return Order(kind="stop", level=bars.high[t] + TICK, stop=bars.low[t] - TICK)

    def update_pending(self, t, order, bars, i):  # noqa: ANN001
        e = i["ema"]
        if not (_valid(e[t], e[t - 1]) and e[t] > e[t - 1]):
            return None  # média deixou de subir: cancela
        # Não executou e a média segue subindo: referência passa a ser o novo candle.
        return Order(kind="stop", level=bars.high[t] + TICK, stop=bars.low[t] - TICK)

    def manage(self, t, pos, bars, i):  # noqa: ANN001
        e = i["ema"]
        turned_down = t >= 2 and _valid(e[t], e[t - 1], e[t - 2]) and e[t] < e[t - 1] >= e[t - 2]
        if turned_down:
            pos.stop = max(pos.stop, bars.low[t] - TICK)  # sai na perda da mínima do candle
        return None


# --- S3: Pullback na MME21 — continuação -------------------------------------------------
@dataclass
class Pullback(_Base):
    ema_n: int = 21
    slope_lookback: int = 5
    tolerance: float = 0.005
    trend_sma: int = 200
    exit: str = "target"  # "target" (alvo em R) | "trail3" (mínima dos 3 últimos)
    target_r: float = 2.0
    validity: int = 1
    code: str = "S3"

    def prepare(self, bars: Bars) -> dict:
        c = _series(bars.close)
        return {
            "ema": ind.ema(c, self.ema_n).to_numpy(),
            "trend": ind.sma(c, self.trend_sma).to_numpy(),
            "min3": _series(bars.low).rolling(3, min_periods=3).min().to_numpy(),
        }

    def signal(self, t, bars, i):  # noqa: ANN001
        e, trend = i["ema"], i["trend"]
        if t < self.slope_lookback or not _valid(e[t], e[t - self.slope_lookback], trend[t]):
            return None
        c, lo = bars.close[t], bars.low[t]
        trending = c > trend[t] and e[t] > e[t - self.slope_lookback]
        touched = lo <= e[t] * (1 + self.tolerance) and c > e[t]
        if not (trending and touched):
            return None
        return Order(
            kind="stop",
            level=bars.high[t] + TICK,
            expires=t + self.validity,
            stop=lo - TICK,
            target_r=self.target_r if self.exit == "target" else None,
        )

    def manage(self, t, pos, bars, i):  # noqa: ANN001
        if self.exit == "trail3" and t > pos.entry_idx and _valid(i["min3"][t]):
            pos.stop = max(pos.stop, i["min3"][t] - TICK)
        return None


# --- S4: Rompimento Donchian com volume ----------------------------------------------------
@dataclass
class Donchian(_Base):
    breakout_n: int = 20
    exit_n: int = 10
    volume_mult: float = 1.5
    stop_atr: float = 2.0
    code: str = "S4"

    def prepare(self, bars: Bars) -> dict:
        vol = _series(bars.volume.astype("float64"))
        return {
            "hh": _rolling_max_prev(bars.high, self.breakout_n),
            "ll": _rolling_min_prev(bars.low, self.exit_n),
            "avgvol": vol.shift(1).rolling(20, min_periods=20).mean().to_numpy(),
            "atr": ind.atr(
                _series(bars.high), _series(bars.low), _series(bars.close), 20
            ).to_numpy(),
        }

    def signal(self, t, bars, i):  # noqa: ANN001
        hh, avgvol, atr = i["hh"][t], i["avgvol"][t], i["atr"][t]
        if not _valid(hh, avgvol, atr) or avgvol <= 0:
            return None
        if bars.close[t] > hh and bars.volume[t] > self.volume_mult * avgvol:
            return Order(kind="open", stop_distance=self.stop_atr * atr)
        return None

    def manage(self, t, pos, bars, i):  # noqa: ANN001
        if _valid(i["ll"][t]) and bars.close[t] < i["ll"][t]:
            return Exit("close", "saida_minima_n")
        return None


# --- S5: 123 de compra (Stormer) -------------------------------------------------------------
@dataclass
class Setup123(_Base):
    trend_sma: int | None = 200  # None = sem filtro de tendência
    exit: str = "target"  # "target" | "trail3"
    target_r: float = 2.0
    validity: int = 1
    code: str = "S5"

    def prepare(self, bars: Bars) -> dict:
        c = _series(bars.close)
        trend = (
            ind.sma(c, self.trend_sma).to_numpy() if self.trend_sma else np.full(len(bars), -np.inf)
        )
        return {
            "trend": trend,
            "min3": _series(bars.low).rolling(3, min_periods=3).min().to_numpy(),
        }

    def signal(self, t, bars, i):  # noqa: ANN001
        if t < 2:
            return None
        lo = bars.low
        trend = i["trend"][t]
        if self.trend_sma and (not _valid(trend) or bars.close[t] <= trend):
            return None
        if not (lo[t - 1] < lo[t - 2] and lo[t - 1] < lo[t]):
            return None
        return Order(
            kind="stop",
            level=bars.high[t] + TICK,
            expires=t + self.validity,
            stop=lo[t - 1] - TICK,
            target_r=self.target_r if self.exit == "target" else None,
        )

    def manage(self, t, pos, bars, i):  # noqa: ANN001
        if self.exit == "trail3" and t > pos.entry_idx and _valid(i["min3"][t]):
            pos.stop = max(pos.stop, i["min3"][t] - TICK)
        return None


SETUP_CLASSES = {"S1": IFR2, "S2": Setup91, "S3": Pullback, "S4": Donchian, "S5": Setup123}


def from_params(code: str, params: dict) -> _Base:
    """Reconstrói o setup exatamente com os parâmetros gravados no laboratório."""
    cls = SETUP_CLASSES[code]
    try:
        setup = cls(**params)
    except TypeError as exc:
        raise ValueError(f"Parâmetros incompatíveis com o setup {code}: {exc}") from exc
    if setup.code != code:
        raise ValueError(f"Parâmetros de {setup.code} não correspondem ao setup {code}")
    return setup


def describe(setup: _Base) -> str:
    """Nome legível da variante (parâmetros que diferem do padrão)."""
    default = type(setup)()
    diffs = [
        f"{k}={v}" for k, v in setup.params.items() if k != "code" and getattr(default, k) != v
    ]
    return "padrão" if not diffs else ", ".join(diffs)


def variants() -> list[_Base]:
    """Grade pequena de variações (evita sobre-otimização: poucos parâmetros, valores clássicos)."""
    out: list[_Base] = []
    for rsi_max in (5.0, 10.0):
        for exit_ in ("max2", "sma5"):
            for stop_atr in (None, 2.0):
                out.append(IFR2(rsi_max=rsi_max, exit=exit_, stop_atr=stop_atr))
    out.append(Setup91())
    for exit_ in ("target", "trail3"):
        out.append(Pullback(exit=exit_))
    for n, x in ((20, 10), (55, 20)):
        out.append(Donchian(breakout_n=n, exit_n=x))
    for trend in (200, None):
        for exit_ in ("target", "trail3"):
            out.append(Setup123(trend_sma=trend, exit=exit_))
    return out


__all__ = [
    "IFR2",
    "Setup91",
    "Pullback",
    "Donchian",
    "Setup123",
    "variants",
    "describe",
    "Position",
]
