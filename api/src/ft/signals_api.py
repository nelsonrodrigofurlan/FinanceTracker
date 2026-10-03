"""Rotas de estratégias, sinais e carteira simulada. Todas exigem usuário autenticado com 2FA."""

import logging
import math
from datetime import date, datetime
from typing import Annotated

import pandas as pd
from fastapi import APIRouter, Depends, HTTPException, Path
from psycopg.types.json import Jsonb
from pydantic import BaseModel

from ft.ai.explain import build_messages, call_model, context_hash, market_context
from ft.auth import CurrentUser, require_user
from ft.config import get_settings
from ft.db.pool import get_pool
from ft.lab_api import SETUP_NAMES
from ft.settings_api import UserSettings, load_settings

router = APIRouter(tags=["signals"])
logger = logging.getLogger("ft.signals_api")


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


# --- Explicação por IA ----------------------------------------------------------------------


class Explanation(BaseModel):
    signal_id: int
    model: str
    content: str
    cost_usd: float | None
    created_at: datetime


def _signal_context(conn, signal_id: int) -> dict | None:  # noqa: ANN001
    row = conn.execute(
        """
        select s.ticker, s.signal_date, s.order_kind, s.entry_level, s.ref_price, s.stop,
               s.stop_distance, s.risk_distance, s.target_r, st.setup_code, st.variant,
               st.status, st.evidence
        from ft.signals s join ft.strategies st on st.id = s.strategy_id where s.id = %s
        """,
        (signal_id,),
    ).fetchone()
    if not row:
        return None
    (
        ticker,
        day,
        kind,
        level,
        ref,
        stop,
        stop_dist,
        risk_dist,
        target_r,
        code,
        variant,
        status,
        evidence,
    ) = row
    candles = conn.execute(
        """
        select c.date, c.open, c.high, c.low, c.close, c.volume from ft.candles_daily c
        join ft.assets a on a.id = c.asset_id
        where a.ticker = %s and c.date <= %s order by c.date desc limit 260
        """,
        (ticker, day),
    ).fetchall()
    frame = pd.DataFrame(candles[::-1], columns=["date", "open", "high", "low", "close", "volume"])
    for col in ("open", "high", "low", "close", "volume"):
        frame[col] = frame[col].astype("float64")
    ibov = conn.execute(
        """
        select c.close from ft.candles_daily c join ft.assets a on a.id = c.asset_id
        where a.ticker = 'IBOV' and c.date <= %s order by c.date desc limit 200
        """,
        (day,),
    ).fetchall()
    ibov_regime = (
        float(ibov[0][0]) > sum(float(v) for (v,) in ibov) / len(ibov) if len(ibov) == 200 else None
    )
    return {
        "ativo": ticker,
        "data_do_sinal": day,
        "estrategia": {"codigo": code, "nome": SETUP_NAMES.get(code, code), "variante": variant},
        "status_da_estrategia": status,
        "ordem": {
            "tipo": kind,
            "nivel_entrada": float(level) if level is not None else None,
            "preco_referencia": float(ref),
            "stop": float(stop) if stop is not None else None,
            "stop_distancia": float(stop_dist) if stop_dist is not None else None,
            "unidade_risco_sem_stop": float(risk_dist) if risk_dist is not None else None,
            "alvo_em_R": float(target_r) if target_r is not None else None,
        },
        "evidencia_laboratorio": evidence,
        "contexto_de_mercado": market_context(frame, ibov_regime),
    }


@router.get("/signals/{signal_id}/explain")
def get_explanation(
    _user: Annotated[CurrentUser, Depends(require_user)],
    signal_id: Annotated[int, Path(ge=1)],
) -> Explanation | None:
    with get_pool().connection() as conn:
        row = conn.execute(
            """
            select signal_id, model, content, usage, created_at from ft.ai_analyses
            where signal_id = %s order by created_at desc limit 1
            """,
            (signal_id,),
        ).fetchone()
    if not row:
        return None
    return Explanation(
        signal_id=row[0],
        model=row[1],
        content=row[2],
        cost_usd=(row[3] or {}).get("cost_usd"),
        created_at=row[4],
    )


@router.post("/signals/{signal_id}/explain")
def create_explanation(
    user: Annotated[CurrentUser, Depends(require_user)],
    signal_id: Annotated[int, Path(ge=1)],
) -> Explanation:
    existing = get_explanation(user, signal_id)
    if existing is not None:
        return existing  # uma explicação por sinal: evita custo repetido
    with get_pool().connection() as conn:
        context = _signal_context(conn, signal_id)
        if context is None:
            raise HTTPException(status_code=404, detail="Sinal não encontrado")
        try:
            result = call_model(get_settings(), build_messages(context))
        except Exception as exc:
            logger.warning("IA indisponível: %s", type(exc).__name__)
            raise HTTPException(status_code=503, detail="Explicação indisponível") from exc
        row = conn.execute(
            """
            insert into ft.ai_analyses (signal_id, model, prompt_hash, content, usage)
            values (%s, %s, %s, %s, %s) returning created_at
            """,
            (
                signal_id,
                result["model"],
                context_hash(context),
                result["content"],
                Jsonb(result["usage"]),
            ),
        ).fetchone()
        conn.commit()
    return Explanation(
        signal_id=signal_id,
        model=result["model"],
        content=result["content"],
        cost_usd=result["usage"].get("cost_usd"),
        created_at=row[0],
    )
