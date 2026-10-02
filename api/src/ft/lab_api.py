"""Rotas do laboratório (leitura). Todas exigem usuário autenticado com 2FA."""

from datetime import date, datetime
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Path, Query
from pydantic import BaseModel

from ft.auth import CurrentUser, require_user
from ft.backtest.portfolio import (
    CdiIndex,
    PortfolioParams,
    SimTrade,
    benchmark,
    cdi_series,
    simulate,
)
from ft.backtest.walkforward import WalkForwardParams, walk_forward, yearly_stability
from ft.data import repository as repo
from ft.db.pool import get_pool

router = APIRouter(prefix="/lab", tags=["lab"])

SETUP_NAMES = {
    "S1": "IFR2 (Connors)",
    "S2": "9.1 (Larry Williams)",
    "S3": "Pullback na MME21",
    "S4": "Rompimento Donchian",
    "S5": "123 de compra",
}


class RunSummary(BaseModel):
    id: int
    setup_code: str
    setup_name: str
    variant: str
    approved: bool
    created_at: datetime
    split_date: date
    in_sample: dict
    out_of_sample: dict


class EquityPoint(BaseModel):
    time: date
    value: float


class TradeRow(BaseModel):
    ticker: str
    entry_date: date
    entry_price: float
    exit_date: date
    exit_price: float
    r_multiple: float
    return_pct: float
    bars: int
    exit_reason: str
    sample: str


class RunDetail(RunSummary):
    params: dict
    costs: dict
    period_start: date
    period_end: date
    universe: dict
    approval: dict
    metrics_all: dict
    equity: list[EquityPoint]
    by_ticker: list[dict]
    recent_trades: list[TradeRow]


def _summary(row) -> RunSummary:  # noqa: ANN001
    run_id, code, variant, approved, created, split, metrics = row
    return RunSummary(
        id=run_id,
        setup_code=code,
        setup_name=SETUP_NAMES.get(code, code),
        variant=variant,
        approved=approved,
        created_at=created,
        split_date=split,
        in_sample=metrics.get("in_sample", {}),
        out_of_sample=metrics.get("out_of_sample", {}),
    )


@router.get("/runs")
def list_runs(_user: Annotated[CurrentUser, Depends(require_user)]) -> list[RunSummary]:
    """Execução mais recente de cada (setup, variante)."""
    with get_pool().connection() as conn:
        rows = conn.execute(
            """
            select distinct on (setup_code, variant)
                   id, setup_code, variant, approved, created_at, split_date, metrics
            from ft.backtest_runs
            order by setup_code, variant, created_at desc
            """
        ).fetchall()
    runs = [_summary(r) for r in rows]
    runs.sort(key=lambda r: r.out_of_sample.get("expectancy_r") or -999, reverse=True)
    return runs


@router.get("/runs/{run_id}")
def get_run(
    _user: Annotated[CurrentUser, Depends(require_user)],
    run_id: Annotated[int, Path(ge=1)],
) -> RunDetail:
    with get_pool().connection() as conn:
        row = conn.execute(
            """
            select id, setup_code, variant, approved, created_at, split_date, metrics,
                   params, costs, period_start, period_end, universe, approval
            from ft.backtest_runs where id = %s
            """,
            (run_id,),
        ).fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Execução não encontrada")
        # Curva em R: soma acumulada por data de saída (um ponto por dia).
        equity = conn.execute(
            """
            select exit_date, sum(sum(r_multiple)) over (order by exit_date)
            from ft.backtest_trades where run_id = %s
            group by exit_date order by exit_date
            """,
            (run_id,),
        ).fetchall()
        by_ticker = conn.execute(
            """
            select ticker, count(*), round(avg(r_multiple), 3), round(sum(r_multiple), 2),
                   round(100.0 * avg((r_multiple > 0)::int), 1)
            from ft.backtest_trades where run_id = %s
            group by ticker order by sum(r_multiple) desc
            """,
            (run_id,),
        ).fetchall()
        recent = conn.execute(
            """
            select ticker, entry_date, entry_price, exit_date, exit_price, r_multiple,
                   return_pct, bars, exit_reason, sample
            from ft.backtest_trades where run_id = %s
            order by exit_date desc, ticker limit 50
            """,
            (run_id,),
        ).fetchall()

    summary = _summary(row[:7])
    return RunDetail(
        **summary.model_dump(),
        params=row[7],
        costs=row[8],
        period_start=row[9],
        period_end=row[10],
        universe={k: v for k, v in row[11].items() if k != "tickers"}
        | {"count": len(row[11].get("tickers", []))},
        approval=row[12],
        metrics_all=row[6].get("all", {}),
        equity=[EquityPoint(time=d, value=round(float(v), 2)) for d, v in equity],
        by_ticker=[
            {
                "ticker": t,
                "trades": n,
                "expectancy_r": float(e),
                "total_r": float(s),
                "win_rate": float(w),
            }
            for t, n, e, s, w in by_ticker
        ],
        recent_trades=[
            TradeRow(
                ticker=r[0],
                entry_date=r[1],
                entry_price=float(r[2]),
                exit_date=r[3],
                exit_price=float(r[4]),
                r_multiple=float(r[5]),
                return_pct=float(r[6]),
                bars=r[7],
                exit_reason=r[8],
                sample=r[9],
            )
            for r in recent
        ],
    )


# --- Estabilidade, walk-forward e carteira ------------------------------------------------


def _per_year_latest(conn, setup_code: str | None = None) -> dict:  # noqa: ANN001
    rows = conn.execute(
        """
        with latest as (
            select distinct on (setup_code, variant) id, setup_code, variant
            from ft.backtest_runs order by setup_code, variant, created_at desc
        )
        select l.setup_code, l.variant, extract(year from t.entry_date)::int,
               count(*), sum(t.r_multiple)
        from latest l join ft.backtest_trades t on t.run_id = l.id
        where %(code)s::text is null or l.setup_code = %(code)s
        group by 1, 2, 3
        """,
        {"code": setup_code},
    ).fetchall()
    per: dict = {}
    for code, variant, year, n, total in rows:
        per.setdefault(code, {}).setdefault(variant, {})[year] = (int(n), float(total))
    return per


@router.get("/walkforward")
def walkforward(_user: Annotated[CurrentUser, Depends(require_user)]) -> list[dict]:
    with get_pool().connection() as conn:
        per = _per_year_latest(conn)
    result = []
    for code in sorted(per):
        wf = walk_forward(per[code], WalkForwardParams())
        result.append({"setup_code": code, "setup_name": SETUP_NAMES.get(code, code), **wf})
    return result


@router.get("/runs/{run_id}/yearly")
def run_yearly(
    _user: Annotated[CurrentUser, Depends(require_user)],
    run_id: Annotated[int, Path(ge=1)],
) -> list[dict]:
    with get_pool().connection() as conn:
        rows = conn.execute(
            """
            select extract(year from entry_date)::int, count(*), sum(r_multiple)
            from ft.backtest_trades where run_id = %s group by 1 order by 1
            """,
            (run_id,),
        ).fetchall()
    return yearly_stability({int(y): (int(n), float(s)) for y, n, s in rows})


@router.get("/runs/{run_id}/portfolio")
def run_portfolio(
    _user: Annotated[CurrentUser, Depends(require_user)],
    run_id: Annotated[int, Path(ge=1)],
    risk_pct: Annotated[float, Query(gt=0, le=5)] = 1.0,
    max_positions: Annotated[int, Query(ge=1, le=30)] = 5,
    max_position_pct: Annotated[float, Query(gt=0, le=100)] = 20.0,
) -> dict:
    with get_pool().connection() as conn:
        rows = conn.execute(
            """
            select ticker, entry_date, exit_date, entry_price, initial_stop, r_multiple
            from ft.backtest_trades where run_id = %s
            """,
            (run_id,),
        ).fetchall()
        if not rows:
            raise HTTPException(status_code=404, detail="Execução sem trades")
        start = min(r[1] for r in rows)
        rates = repo.cdi_rates(conn, start)
        bova = repo.benchmark_adj_close(conn, "BOVA11", start)

    trades = [SimTrade(t, e, x, float(p), float(s), float(r)) for t, e, x, p, s, r in rows]
    params = PortfolioParams(
        risk_pct=risk_pct, max_positions=max_positions, max_position_pct=max_position_pct
    )
    cdi = CdiIndex(rates) if rates else None
    result = simulate(trades, params, cdi)
    end = max(r[2] for r in rows)
    result["cash_earns_cdi"] = cdi is not None
    result["benchmarks"] = {
        "cdi": benchmark(cdi_series(cdi), params.initial_capital, start, end)
        if cdi
        else {"available": False},
        "bova11": benchmark(bova, params.initial_capital, start, end),
    }
    return result
