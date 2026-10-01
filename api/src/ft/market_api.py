"""Rotas de leitura de dados de mercado. Todas exigem usuário autenticado com 2FA."""

from datetime import date, datetime
from typing import Annotated

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from ft.auth import CurrentUser, require_user
from ft.db.connection import connect

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
    with connect() as conn:
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
