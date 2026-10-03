"""Diário de trades REAIS. O usuário registra o que operou na corretora; o app só calcula.

- Long-only (como o resto do app). Stop planejado abaixo da entrada; alvo acima.
- R = resultado líquido ÷ risco planejado ((entrada − stop) × quantidade). Sem stop → sem R.
- Imposto de renda NÃO calculado [VERIFICAR regras antes de implementar].
- Trade ligado a sinal de estratégia não aprovada é aceito, mas sinalizado.
"""

import re
from datetime import date
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, HTTPException, Path, Response
from pydantic import BaseModel, Field, field_validator, model_validator

from ft.auth import CurrentUser, require_user
from ft.data.market_time import now_b3
from ft.db.pool import get_pool

router = APIRouter(prefix="/journal", tags=["journal"])

TICKER_RE = re.compile(r"^[A-Z][A-Z0-9]{3}\d{1,2}F?$")
Emotion = Literal["calmo", "confiante", "ansioso", "com_medo", "euforico", "impaciente"]


def _not_future(day: date) -> date:
    if day > now_b3().date():
        raise ValueError("data no futuro")
    return day


class JournalEntryIn(BaseModel):
    ticker: str
    signal_id: int | None = Field(default=None, ge=1)
    entry_date: date
    entry_price: float = Field(gt=0, le=1_000_000)
    quantity: int = Field(gt=0, le=10_000_000)
    stop_planned: float | None = Field(default=None, gt=0)
    target_planned: float | None = Field(default=None, gt=0)
    entry_fees: float = Field(default=0, ge=0, le=1_000_000)
    reason: str | None = Field(default=None, max_length=2000)
    emotion: Emotion | None = None

    @field_validator("ticker")
    @classmethod
    def _ticker(cls, v: str) -> str:
        v = v.strip().upper()
        if not TICKER_RE.match(v):
            raise ValueError("ticker inválido")
        return v

    @field_validator("entry_date")
    @classmethod
    def _entry_date(cls, v: date) -> date:
        return _not_future(v)

    @model_validator(mode="after")
    def _levels(self) -> "JournalEntryIn":
        if self.stop_planned is not None and self.stop_planned >= self.entry_price:
            raise ValueError("stop planejado precisa ficar abaixo da entrada")
        if self.target_planned is not None and self.target_planned <= self.entry_price:
            raise ValueError("alvo planejado precisa ficar acima da entrada")
        return self


class JournalCloseIn(BaseModel):
    exit_date: date
    exit_price: float = Field(gt=0, le=1_000_000)
    exit_fees: float = Field(default=0, ge=0, le=1_000_000)
    exit_notes: str | None = Field(default=None, max_length=2000)

    @field_validator("exit_date")
    @classmethod
    def _exit_date(cls, v: date) -> date:
        return _not_future(v)


class JournalTrade(BaseModel):
    id: int
    ticker: str
    signal_id: int | None
    strategy_status: str | None
    entry_date: date
    entry_price: float
    quantity: int
    stop_planned: float | None
    target_planned: float | None
    entry_fees: float
    reason: str | None
    emotion: str | None
    exit_date: date | None
    exit_price: float | None
    exit_fees: float
    exit_notes: str | None
    status: Literal["open", "closed"]
    pnl: float | None
    return_pct: float | None
    r_multiple: float | None
    planned_risk: float | None
    holding_days: int | None


class JournalSummary(BaseModel):
    open_count: int
    closed_count: int
    win_rate: float | None
    total_pnl: float
    avg_r: float | None
    with_stop_pct: float | None  # disciplina: trades com stop definido antes de entrar
    non_approved_count: int  # ligados a estratégia não aprovada


class Journal(BaseModel):
    trades: list[JournalTrade]
    summary: JournalSummary


def compute(row: dict) -> dict:
    """Resultado de um trade (puro). Custos (taxas) entram no resultado líquido."""
    entry, qty = row["entry_price"], row["quantity"]
    stop = row.get("stop_planned")
    planned_risk = (entry - stop) * qty if stop is not None else None
    out = {"planned_risk": round(planned_risk, 2) if planned_risk is not None else None}
    if row.get("exit_price") is None:
        return {
            **out,
            "status": "open",
            "pnl": None,
            "return_pct": None,
            "r_multiple": None,
            "holding_days": None,
        }
    cost = entry * qty + row.get("entry_fees", 0)
    pnl = row["exit_price"] * qty - row.get("exit_fees", 0) - cost
    return {
        **out,
        "status": "closed",
        "pnl": round(pnl, 2),
        "return_pct": round(pnl / cost * 100, 2),
        "r_multiple": round(pnl / planned_risk, 2) if planned_risk else None,
        "holding_days": (row["exit_date"] - row["entry_date"]).days,
    }


def summarize(trades: list[JournalTrade]) -> JournalSummary:
    closed = [t for t in trades if t.status == "closed"]
    with_r = [t.r_multiple for t in closed if t.r_multiple is not None]
    return JournalSummary(
        open_count=sum(1 for t in trades if t.status == "open"),
        closed_count=len(closed),
        win_rate=round(sum(1 for t in closed if (t.pnl or 0) > 0) / len(closed) * 100, 1)
        if closed
        else None,
        total_pnl=round(sum(t.pnl or 0 for t in closed), 2),
        avg_r=round(sum(with_r) / len(with_r), 2) if with_r else None,
        with_stop_pct=round(sum(1 for t in trades if t.stop_planned) / len(trades) * 100, 1)
        if trades
        else None,
        non_approved_count=sum(
            1 for t in trades if t.strategy_status and t.strategy_status != "approved"
        ),
    )


COLUMNS = (
    "j.id, j.ticker, j.signal_id, st.status, j.entry_date, j.entry_price, j.quantity, "
    "j.stop_planned, j.target_planned, j.entry_fees, j.reason, j.emotion, j.exit_date, "
    "j.exit_price, j.exit_fees, j.exit_notes"
)
FROM = (
    "from ft.journal_trades j left join ft.signals s on s.id = j.signal_id "
    "left join ft.strategies st on st.id = s.strategy_id"
)
NUMERIC = ("entry_price", "stop_planned", "target_planned", "entry_fees", "exit_price", "exit_fees")


def _to_trade(r: tuple) -> JournalTrade:
    keys = (
        "id",
        "ticker",
        "signal_id",
        "strategy_status",
        "entry_date",
        "entry_price",
        "quantity",
        "stop_planned",
        "target_planned",
        "entry_fees",
        "reason",
        "emotion",
        "exit_date",
        "exit_price",
        "exit_fees",
        "exit_notes",
    )
    row = dict(zip(keys, r, strict=True))
    for k in NUMERIC:
        row[k] = float(row[k]) if row[k] is not None else None
    return JournalTrade(**row, **compute(row))


def _fetch(conn, user_id: str, trade_id: int | None = None) -> list[JournalTrade]:  # noqa: ANN001
    sql = f"select {COLUMNS} {FROM} where j.user_id = %s"
    params: list = [user_id]
    if trade_id is not None:
        sql += " and j.id = %s"
        params.append(trade_id)
    sql += " order by j.exit_date is not null, coalesce(j.exit_date, j.entry_date) desc, j.id desc"
    return [_to_trade(r) for r in conn.execute(sql, params).fetchall()]


@router.get("")
def list_journal(user: Annotated[CurrentUser, Depends(require_user)]) -> Journal:
    with get_pool().connection() as conn:
        trades = _fetch(conn, user.user_id)
    return Journal(trades=trades, summary=summarize(trades))


@router.post("", status_code=201)
def create_entry(
    body: JournalEntryIn, user: Annotated[CurrentUser, Depends(require_user)]
) -> JournalTrade:
    with get_pool().connection() as conn:
        if body.signal_id is not None:
            found = conn.execute("select 1 from ft.signals where id = %s", (body.signal_id,))
            if not found.fetchone():
                raise HTTPException(status_code=422, detail="Sinal não encontrado")
        (new_id,) = conn.execute(
            """
            insert into ft.journal_trades (user_id, ticker, signal_id, entry_date, entry_price,
                quantity, stop_planned, target_planned, entry_fees, reason, emotion)
            values (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s) returning id
            """,
            (
                user.user_id,
                body.ticker,
                body.signal_id,
                body.entry_date,
                body.entry_price,
                body.quantity,
                body.stop_planned,
                body.target_planned,
                body.entry_fees,
                body.reason,
                body.emotion,
            ),
        ).fetchone()
        conn.commit()
        return _fetch(conn, user.user_id, new_id)[0]


@router.put("/{trade_id}/close")
def close_entry(
    body: JournalCloseIn,
    user: Annotated[CurrentUser, Depends(require_user)],
    trade_id: Annotated[int, Path(ge=1)],
) -> JournalTrade:
    with get_pool().connection() as conn:
        [current] = _fetch(conn, user.user_id, trade_id) or [None]
        if current is None:
            raise HTTPException(status_code=404, detail="Trade não encontrado")
        if body.exit_date < current.entry_date:
            raise HTTPException(status_code=422, detail="Saída anterior à entrada")
        conn.execute(
            """
            update ft.journal_trades set exit_date = %s, exit_price = %s, exit_fees = %s,
                exit_notes = %s, updated_at = now()
            where id = %s and user_id = %s
            """,
            (
                body.exit_date,
                body.exit_price,
                body.exit_fees,
                body.exit_notes,
                trade_id,
                user.user_id,
            ),
        )
        conn.commit()
        return _fetch(conn, user.user_id, trade_id)[0]


@router.delete("/{trade_id}", status_code=204)
def delete_entry(
    user: Annotated[CurrentUser, Depends(require_user)],
    trade_id: Annotated[int, Path(ge=1)],
) -> Response:
    with get_pool().connection() as conn:
        deleted = conn.execute(
            "delete from ft.journal_trades where id = %s and user_id = %s returning id",
            (trade_id, user.user_id),
        ).fetchone()
        conn.commit()
    if not deleted:
        raise HTTPException(status_code=404, detail="Trade não encontrado")
    return Response(status_code=204)
