"""Rotas de estratégias, sinais e carteira simulada. Todas exigem usuário autenticado com 2FA."""

import math
from datetime import date
from typing import Annotated

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from ft.auth import CurrentUser, require_user
from ft.db.pool import get_pool
from ft.lab_api import SETUP_NAMES
from ft.settings_api import UserSettings, load_settings

router = APIRouter(tags=["signals"])


class Strategy(BaseModel):
    id: int
    setup_code: str
    setup_name: str
    variant: str
    status: str
    sim_start_date: date | None
    evidence: dict


@router.get("/strategies")
def list_strategies(_user: Annotated[CurrentUser, Depends(require_user)]) -> list[Strategy]:
    with get_pool().connection() as conn:
        rows = conn.execute(
            """
            select id, setup_code, variant, status, sim_start_date, evidence
            from ft.strategies
            order by case status when 'approved' then 0 when 'observation' then 1 else 2 end,
                     setup_code, variant
            """
        ).fetchall()
    return [
        Strategy(
            id=r[0],
            setup_code=r[1],
            setup_name=SETUP_NAMES.get(r[1], r[1]),
            variant=r[2],
            status=r[3],
            sim_start_date=r[4],
            evidence=r[5],
        )
        for r in rows
    ]


def position_size(entry: float | None, risk_per_share: float | None, s: UserSettings) -> int | None:
    """Quantidade pelos AJUSTES DO USUÁRIO; None se faltarem ajustes ou dados."""
    if not s.complete or not entry or not risk_per_share or risk_per_share <= 0 or entry <= 0:
        return None
    by_risk = s.sim_capital * s.risk_pct / 100 / risk_per_share
    by_cap = s.sim_capital * s.max_position_pct / 100 / entry
    return max(int(math.floor(min(by_risk, by_cap))), 0)


class Signal(BaseModel):
    id: int
    ticker: str
    signal_date: date
    setup_code: str
    setup_name: str
    variant: str
    status: str
    order_kind: str
    entry_estimate: float | None
    entry_is_estimate: bool
    stop_estimate: float | None
    target_estimate: float | None
    risk_per_share: float | None
    quantity: int | None
    evidence: dict


@router.get("/signals/latest")
def latest_signals(user: Annotated[CurrentUser, Depends(require_user)]) -> list[Signal]:
    with get_pool().connection() as conn:
        settings = load_settings(conn, user.user_id)
        rows = conn.execute(
            """
            select s.id, s.ticker, s.signal_date, st.setup_code, st.variant, st.status,
                   s.order_kind, s.entry_level, s.ref_price, s.stop, s.stop_distance,
                   s.risk_distance, s.target_r, st.evidence
            from ft.signals s join ft.strategies st on st.id = s.strategy_id
            where st.status in ('approved', 'observation')
              and s.signal_date = (select max(signal_date) from ft.signals)
            order by st.status, s.ticker
            """
        ).fetchall()
    out = []
    for (
        sid,
        ticker,
        day,
        code,
        variant,
        status,
        kind,
        level,
        ref,
        stop,
        stop_dist,
        risk_dist,
        target_r,
        evidence,
    ) in rows:
        entry = float(level) if kind == "stop" else float(ref)
        if stop is not None:
            stop_v = float(stop)
        elif stop_dist is not None:
            stop_v = entry - float(stop_dist)
        else:
            stop_v = None
        risk = (entry - stop_v) if stop_v is not None else (float(risk_dist) if risk_dist else None)
        target = entry + float(target_r) * risk if target_r and risk else None
        out.append(
            Signal(
                id=sid,
                ticker=ticker,
                signal_date=day,
                setup_code=code,
                setup_name=SETUP_NAMES.get(code, code),
                variant=variant,
                status=status,
                order_kind=kind,
                entry_estimate=round(entry, 2),
                entry_is_estimate=kind == "open",
                stop_estimate=round(stop_v, 2) if stop_v is not None else None,
                target_estimate=round(target, 2) if target else None,
                risk_per_share=round(risk, 4) if risk else None,
                quantity=position_size(entry, risk, settings),
                evidence=evidence,
            )
        )
    return out


class SimTrade(BaseModel):
    setup_code: str
    variant: str
    ticker: str
    entry_date: date
    entry_price: float
    initial_stop: float
    target: float | None
    exit_date: date | None
    exit_price: float | None
    exit_reason: str | None
    r_multiple: float
    bars: int
    status: str


class SimBook(BaseModel):
    open: list[SimTrade]
    closed: list[SimTrade]
    closed_count: int
    total_r: float
    win_rate: float | None


@router.get("/sim/book")
def sim_book(_user: Annotated[CurrentUser, Depends(require_user)]) -> SimBook:
    with get_pool().connection() as conn:
        rows = conn.execute(
            """
            select st.setup_code, st.variant, t.ticker, t.entry_date, t.entry_price,
                   t.initial_stop, t.target, t.exit_date, t.exit_price, t.exit_reason,
                   t.r_multiple, t.bars, t.status
            from ft.sim_trades t join ft.strategies st on st.id = t.strategy_id
            order by coalesce(t.exit_date, t.entry_date) desc, t.ticker
            """
        ).fetchall()
    trades = [
        SimTrade(
            setup_code=r[0],
            variant=r[1],
            ticker=r[2],
            entry_date=r[3],
            entry_price=float(r[4]),
            initial_stop=float(r[5]),
            target=float(r[6]) if r[6] is not None else None,
            exit_date=r[7],
            exit_price=float(r[8]) if r[8] is not None else None,
            exit_reason=r[9],
            r_multiple=float(r[10]),
            bars=r[11],
            status=r[12],
        )
        for r in rows
    ]
    closed = [t for t in trades if t.status == "closed"]
    wins = sum(1 for t in closed if t.r_multiple > 0)
    return SimBook(
        open=[t for t in trades if t.status == "open"],
        closed=closed[:100],
        closed_count=len(closed),
        total_r=round(sum(t.r_multiple for t in closed), 2),
        win_rate=round(wins / len(closed) * 100, 1) if closed else None,
    )
