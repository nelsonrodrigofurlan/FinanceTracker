"""Fonte de dados: Yahoo Finance (gratuita, não oficial — pode falhar ou mudar).

Convenções do Yahoo (verificadas em 2026-10-01 com yfinance 1.7.0):
- `Close` já vem ajustado por desdobramentos; `Adj Close` também por proventos.
- Índice em America/Sao_Paulo; o candle do dia aparece durante o pregão (parcial).
"""

import logging
import time
from dataclasses import dataclass
from datetime import date

import pandas as pd
import yfinance as yf

from ft.data.market_time import last_complete_date

logger = logging.getLogger("ft.data.yahoo")

SOURCE = "yahoo"
COLUMNS = {
    "Open": "open",
    "High": "high",
    "Low": "low",
    "Close": "close",
    "Adj Close": "adj_close",
    "Volume": "volume",
    "Dividends": "dividends",
    "Stock Splits": "splits",
}


def to_yahoo_symbol(ticker: str) -> str:
    return f"{ticker.upper()}.SA"


@dataclass
class DailyHistory:
    candles: pd.DataFrame  # índice: date; colunas open, high, low, close, adj_close, volume
    dividends: pd.Series  # índice: date
    splits: pd.Series  # índice: date


def normalize(raw: pd.DataFrame, up_to: date) -> DailyHistory:
    missing = [c for c in COLUMNS if c not in raw.columns]
    if missing:
        raise ValueError(f"Resposta do Yahoo sem colunas esperadas: {missing}")

    df = raw.rename(columns=COLUMNS)[list(COLUMNS.values())].copy()
    df.index = pd.to_datetime(df.index).date
    df.index.name = "date"
    df = df[df.index <= up_to]  # descarta candle parcial do dia

    dividends = df["dividends"][df["dividends"] != 0]
    splits = df["splits"][df["splits"] != 0]
    candles = df.drop(columns=["dividends", "splits"])
    return DailyHistory(candles=candles, dividends=dividends, splits=splits)


def fetch_daily(
    ticker: str,
    start: date | None = None,
    retries: int = 3,
    pause_seconds: float = 2.0,
) -> DailyHistory:
    """Busca candles diários. `start=None` busca o histórico completo."""
    symbol = to_yahoo_symbol(ticker)
    up_to = last_complete_date()
    last_error: Exception | None = None

    for attempt in range(1, retries + 1):
        try:
            history_kwargs = {"interval": "1d", "auto_adjust": False, "actions": True}
            if start is None:
                raw = yf.Ticker(symbol).history(period="max", **history_kwargs)
            else:
                raw = yf.Ticker(symbol).history(start=start.isoformat(), **history_kwargs)
            if raw is None or raw.empty:
                raise LookupError(f"Yahoo não retornou dados para {symbol}")
            return normalize(raw, up_to)
        except Exception as exc:  # noqa: BLE001 — fonte externa instável
            last_error = exc
            logger.warning("yahoo %s tentativa %d/%d falhou: %s", symbol, attempt, retries, exc)
            time.sleep(pause_seconds * attempt)

    raise RuntimeError(f"Falha ao buscar {symbol}") from last_error
