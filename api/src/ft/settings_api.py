"""Ajustes do usuário (modo simulado). Valores de risco são SEMPRE decisão do usuário:
não existem valores padrão — sem ajustes, o app mostra sinais sem calcular quantidade."""

from typing import Annotated

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field

from ft.auth import CurrentUser, require_user
from ft.db.pool import get_pool

router = APIRouter(prefix="/settings", tags=["settings"])


class UserSettings(BaseModel):
    sim_capital: float | None = Field(default=None, gt=0, le=1_000_000_000)
    risk_pct: float | None = Field(default=None, gt=0, le=5)
    max_positions: int | None = Field(default=None, ge=1, le=30)
    max_position_pct: float | None = Field(default=None, gt=0, le=100)

    @property
    def complete(self) -> bool:
        return None not in (
            self.sim_capital,
            self.risk_pct,
            self.max_positions,
            self.max_position_pct,
        )


def load_settings(conn, user_id: str) -> UserSettings:  # noqa: ANN001
    row = conn.execute(
        """
        select sim_capital, risk_pct, max_positions, max_position_pct
        from ft.user_settings where user_id = %s
        """,
        (user_id,),
    ).fetchone()
    if not row:
        return UserSettings()
    capital, risk, positions, max_pct = row
    return UserSettings(
        sim_capital=float(capital) if capital is not None else None,
        risk_pct=float(risk) if risk is not None else None,
        max_positions=positions,
        max_position_pct=float(max_pct) if max_pct is not None else None,
    )


@router.get("")
def get_settings_route(user: Annotated[CurrentUser, Depends(require_user)]) -> UserSettings:
    with get_pool().connection() as conn:
        return load_settings(conn, user.user_id)


@router.put("")
def put_settings(
    body: UserSettings, user: Annotated[CurrentUser, Depends(require_user)]
) -> UserSettings:
    with get_pool().connection() as conn:
        conn.execute(
            """
            insert into ft.user_settings
                (user_id, sim_capital, risk_pct, max_positions, max_position_pct)
            values (%s, %s, %s, %s, %s)
            on conflict (user_id) do update set
                sim_capital = excluded.sim_capital,
                risk_pct = excluded.risk_pct,
                max_positions = excluded.max_positions,
                max_position_pct = excluded.max_position_pct,
                updated_at = now()
            """,
            (
                user.user_id,
                body.sim_capital,
                body.risk_pct,
                body.max_positions,
                body.max_position_pct,
            ),
        )
        conn.commit()
        return load_settings(conn, user.user_id)
