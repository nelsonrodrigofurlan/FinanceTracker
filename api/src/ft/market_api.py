"""Rotas de leitura de dados de mercado. Todas exigem usuário autenticado com 2FA."""

import math
from datetime import date, datetime, timedelta
from typing import Annotated

import pandas as pd
from fastapi import APIRouter, Depends, HTTPException, Path, Query
from pydantic import BaseModel

from ft.auth import CurrentUser, require_user
from ft.db.pool import get_pool
from ft.indicators import core as ind

router = APIRouter(prefix="/market", tags=["market"])


class LastRun(BaseModel):
    status: str
    started_at: datetime
    finished_at: datetime | None
    assets_updated: int | None
    errors: int | None


class MarketStatus(BaseModel):
    active_assets: int
    benchmarks: int
    last_candle_date: date | None
    universe_ref_date: date | None
    universe_selected: int | None
    universe_candidates: int | None
    last_run: LastRun | None


@router.get("/status")
def market_status(_user: Annotated[CurrentUser, Depends(require_user)]) -> MarketStatus:
    with get_pool().connection() as conn:
        active, benchmarks = conn.execute(
            "select count(*) filter (where active), count(*) filter (where is_benchmark)"
            " from ft.assets"
        ).fetchone()
        (last_candle,) = conn.execute("select max(date) from ft.candles_daily").fetchone()
        snapshot = conn.execute(
            "select ref_date, cardinality(selected), cardinality(candidates)"
            " from ft.universe_snapshots order by ref_date desc limit 1"
        ).fetchone()
        run = conn.execute(
            "select status, started_at, finished_at, stats from ft.pipeline_runs"
            " order by started_at desc limit 1"
        ).fetchone()

    last_run = None
    if run:
        update = (run[3] or {}).get("update", {})
        last_run = LastRun(
            status=run[0],
            started_at=run[1],
            finished_at=run[2],
            assets_updated=update.get("assets"),
            errors=len(update.get("errors", {})) if update else None,
        )
    return MarketStatus(
        active_assets=active,
        benchmarks=benchmarks,
        last_candle_date=last_candle,
        universe_ref_date=snapshot[0] if snapshot else None,
        universe_selected=snapshot[1] if snapshot else None,
        universe_candidates=snapshot[2] if snapshot else None,
        last_run=last_run,
    )


# --- Ativos e candles ------------------------------------------------------------------

TICKER_PATTERN = r"^[A-Z][A-Z0-9]{3}\d{1,2}$"
RANGE_DAYS: dict[str, int | None] = {
    "6m": 183,
    "1y": 365,
    "3y": 3 * 365,
    "5y": 5 * 365,
    "max": None,
}
WARMUP_CALENDAR_DAYS = 600  # ≈ 410 pregões antes do início da janela exibida


class AssetSummary(BaseModel):
    ticker: str
    name: str | None
    type: str
    is_benchmark: bool
    last_date: date | None
    last_close: float | None
    change_pct: float | None
    avg_fin_volume_21: float | None


@router.get("/assets")
def list_assets(_user: Annotated[CurrentUser, Depends(require_user)]) -> list[AssetSummary]:
    with get_pool().connection() as conn:
        rows = conn.execute(
            """
            with ranked as (
                select c.asset_id, c.date, c.close, c.fin_volume,
                       row_number() over (partition by c.asset_id order by c.date desc) rn
                from ft.candles_daily c
                join ft.assets a on a.id = c.asset_id and a.active
                where c.date >= current_date - 60
            )
            select a.ticker, a.name, a.type, a.is_benchmark,
                   max(r.date) filter (where r.rn = 1),
                   max(r.close) filter (where r.rn = 1),
                   max(r.close) filter (where r.rn = 2),
                   avg(r.fin_volume) filter (where r.rn <= 21)
            from ft.assets a
            left join ranked r on r.asset_id = a.id
            where a.active
            group by a.ticker, a.name, a.type, a.is_benchmark
            order by a.is_benchmark desc, a.ticker
            """
        ).fetchall()
    result = []
    for ticker, name, kind, bench, last_date, last, prev, avg_fv in rows:
        change = (float(last) / float(prev) - 1) * 100 if last and prev else None
        result.append(
            AssetSummary(
                ticker=ticker,
                name=name,
                type=kind,
                is_benchmark=bench,
                last_date=last_date,
                last_close=float(last) if last is not None else None,
                change_pct=round(change, 2) if change is not None else None,
                avg_fin_volume_21=float(avg_fv) if avg_fv is not None else None,
            )
        )
    return result


class Candle(BaseModel):
    time: date
    open: float
    high: float
    low: float
    close: float
    volume: int


class Point(BaseModel):
    time: date
    value: float


class CandlesResponse(BaseModel):
    ticker: str
    name: str | None
    range: str
    candles: list[Candle]
    indicators: dict[str, list[Point]]


@router.get("/candles/{ticker}")
def get_candles(
    _user: Annotated[CurrentUser, Depends(require_user)],
    ticker: Annotated[str, Path(pattern=TICKER_PATTERN)],
    range: Annotated[str, Query(pattern="^(6m|1y|3y|5y|max)$")] = "1y",  # noqa: A002
) -> CandlesResponse:
    with get_pool().connection() as conn:
        asset = conn.execute(
            "select id, name from ft.assets where ticker = %s", (ticker,)
        ).fetchone()
        if not asset:
            raise HTTPException(status_code=404, detail="Ativo não encontrado")
        days = RANGE_DAYS[range]
        # Carrega só a janela + aquecimento (~400 pregões) para MMA200/MME/IFR estáveis.
        lookback = None if days is None else days + WARMUP_CALENDAR_DAYS
        rows = conn.execute(
            """
            select date, open, high, low, close, volume from ft.candles_daily
            where asset_id = %(id)s
              and (%(lookback)s::int is null or date >= (
                    select max(date) from ft.candles_daily where asset_id = %(id)s
                  ) - %(lookback)s::int)
            order by date
            """,
            {"id": asset[0], "lookback": lookback},
        ).fetchall()

    frame = pd.DataFrame(rows, columns=["date", "open", "high", "low", "close", "volume"])
    frame = frame.astype({c: "float64" for c in ("open", "high", "low", "close")})
    close = frame["close"]
    indicators = {
        "sma200": ind.sma(close, 200),
        "ema21": ind.ema(close, 21),
        "ema9": ind.ema(close, 9),
        "rsi2": ind.rsi(close, 2),
        "rsi14": ind.rsi(close, 14),
    }

    if days is not None and not frame.empty:
        start = frame["date"].iloc[-1] - timedelta(days=days)
        visible = frame["date"] >= start
    else:
        visible = pd.Series(True, index=frame.index)

    view = frame[visible]
    return CandlesResponse(
        ticker=ticker,
        name=asset[1],
        range=range,
        candles=[
            Candle(
                time=r.date,
                open=round(r.open, 4),
                high=round(r.high, 4),
                low=round(r.low, 4),
                close=round(r.close, 4),
                volume=int(r.volume),
            )
            for r in view.itertuples()
        ],
        indicators={
            name: [
                Point(time=d, value=round(float(v), 4))
                for d, v in zip(frame["date"][visible], series[visible], strict=True)
                if not math.isnan(v)
            ]
            for name, series in indicators.items()
        },
    )
