"""Dados para backtest: preços ajustados por proventos e desdobramentos.

- OHLC ajustado = OHLC × (adj_close / close) do mesmo dia (mantém a forma do candle).
- Quebra de série: intervalo > MAX_GAP_DAYS sem candle (ex.: NATU3 2019→2025) → usa só o
  trecho após a última quebra (antes disso é outra estrutura societária / outro papel).
- Cache local opcional em data/cache (fora do git) para não baixar ~500 mil linhas a cada run.
"""

import logging
import pickle
from datetime import date
from pathlib import Path

import numpy as np
import pandas as pd
import psycopg

from ft.backtest.engine import Bars

logger = logging.getLogger("ft.backtest.data")

MAX_GAP_DAYS = 30
CACHE_VERSION = "v2"  # v2: inclui regime do Ibovespa
REGIME_INDEX = "IBOV"
REGIME_SMA = 200
CACHE_DIR = Path(__file__).resolve().parents[3] / "data" / "cache"


def adjust(frame: pd.DataFrame) -> pd.DataFrame:
    factor = frame["adj_close"] / frame["close"]
    out = frame.copy()
    for col in ("open", "high", "low", "close"):
        out[col] = frame[col] * factor
    return out


def cut_at_last_break(frame: pd.DataFrame, max_gap_days: int = MAX_GAP_DAYS) -> pd.DataFrame:
    dates = pd.to_datetime(frame["date"])
    gaps = dates.diff().dt.days
    breaks = np.flatnonzero(gaps.to_numpy() > max_gap_days)
    if len(breaks) == 0:
        return frame
    return frame.iloc[breaks[-1] :].reset_index(drop=True)


def to_bars(ticker: str, frame: pd.DataFrame) -> Bars:
    return Bars(
        ticker=ticker,
        dates=list(frame["date"]),
        open=frame["open"].to_numpy(dtype="float64"),
        high=frame["high"].to_numpy(dtype="float64"),
        low=frame["low"].to_numpy(dtype="float64"),
        close=frame["close"].to_numpy(dtype="float64"),
        volume=frame["volume"].to_numpy(dtype="float64"),
    )


def load_universe(
    conn: psycopg.Connection, start: date, use_cache: bool = True
) -> tuple[dict[str, Bars], dict]:
    """Ações ativas do universo (sem ETFs de referência). Retorna (bars, informações)."""
    last = conn.execute("select max(date) from ft.candles_daily").fetchone()[0]
    cache_file = CACHE_DIR / f"universe_{CACHE_VERSION}_{start.isoformat()}_{last.isoformat()}.pkl"
    if use_cache and cache_file.exists():
        logger.info("usando cache %s", cache_file.name)
        with cache_file.open("rb") as fh:
            return pickle.load(fh)  # noqa: S301 — arquivo local gerado por este módulo

    rows = conn.execute(
        """
        select a.ticker, c.date, c.open, c.high, c.low, c.close, c.adj_close, c.volume
        from ft.candles_daily c
        join ft.assets a on a.id = c.asset_id
        where a.active and not a.is_benchmark and c.date >= %s
        order by a.ticker, c.date
        """,
        (start,),
    ).fetchall()
    frame = pd.DataFrame(
        rows, columns=["ticker", "date", "open", "high", "low", "close", "adj_close", "volume"]
    )
    for col in ("open", "high", "low", "close", "adj_close", "volume"):
        frame[col] = frame[col].astype("float64")

    regime = load_regime(conn, start)
    bars: dict[str, Bars] = {}
    cut: dict[str, str] = {}
    for ticker, group in frame.groupby("ticker", sort=True):
        group = group.reset_index(drop=True)
        trimmed = cut_at_last_break(group)
        if len(trimmed) < len(group):
            cut[ticker] = str(trimmed["date"].iloc[0])
        b = to_bars(str(ticker), adjust(trimmed))
        # Dia sem informação de regime conta como "mercado em baixa" (conservador).
        b.regime = np.array([regime.get(d, False) for d in b.dates], dtype=bool)
        bars[ticker] = b

    info = {
        "tickers": sorted(bars),
        "series_cut_at": cut,
        "last_date": last.isoformat(),
        "regime": f"{REGIME_INDEX} acima da MMA{REGIME_SMA} ({len(regime)} pregões com regime)",
        "note": (
            "Universo = ações líquidas de HOJE aplicadas ao passado: há viés de sobrevivência "
            "(empresas que saíram da bolsa não estão no teste). Resultados tendem a ser otimistas."
        ),
    }
    if use_cache:
        CACHE_DIR.mkdir(parents=True, exist_ok=True)
        with cache_file.open("wb") as fh:
            pickle.dump((bars, info), fh)
    return bars, info


def regime_from_closes(closes: pd.Series, n: int = REGIME_SMA) -> dict:
    """{data: True se o fechamento estiver acima da MMA n}. Sem MMA calculável → ausente."""
    sma = closes.rolling(n, min_periods=n).mean()
    valid = sma.notna()
    return {
        d: bool(c > s)
        for d, c, s in zip(closes.index[valid], closes[valid], sma[valid], strict=True)
    }


def load_regime(conn: psycopg.Connection, start: date) -> dict:
    """Regime diário do Ibovespa, com ~1,5 ano extra antes de `start` para aquecer a MMA."""
    rows = conn.execute(
        """
        select c.date, c.close from ft.candles_daily c
        join ft.assets a on a.id = c.asset_id
        where a.ticker = %s and c.date >= %s::date - 550 order by c.date
        """,
        (REGIME_INDEX, start),
    ).fetchall()
    if not rows:
        raise RuntimeError(f"Sem candles de {REGIME_INDEX}: rode o pipeline antes do laboratório")
    closes = pd.Series([float(c) for _, c in rows], index=[d for d, _ in rows], dtype="float64")
    return regime_from_closes(closes)
