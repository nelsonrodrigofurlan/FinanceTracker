"""Avaliação de uma execução do laboratório como carteira, comparada a CDI e BOVA11.

Usado pela tela do laboratório e pela classificação de estratégias (mesmo cálculo nos dois).
"""

import psycopg

from ft.backtest.portfolio import (
    CdiIndex,
    PortfolioParams,
    SimTrade,
    benchmark,
    cdi_series,
    simulate,
)
from ft.data import repository as repo

# Carteira de REFERÊNCIA para classificar estratégias. Não é o risco do usuário.
REFERENCE_PARAMS = PortfolioParams(risk_pct=1.0, max_positions=5, max_position_pct=20.0)


def run_trades(conn: psycopg.Connection, run_id: int) -> list[SimTrade]:
    rows = conn.execute(
        """
        select ticker, entry_date, exit_date, entry_price, initial_stop, r_multiple
        from ft.backtest_trades where run_id = %s
        """,
        (run_id,),
    ).fetchall()
    return [SimTrade(t, e, x, float(p), float(s), float(r)) for t, e, x, p, s, r in rows]


def portfolio_with_benchmarks(
    conn: psycopg.Connection, trades: list[SimTrade], params: PortfolioParams
) -> dict | None:
    if not trades:
        return None
    start = min(t.entry_date for t in trades)
    end = max(t.exit_date for t in trades)
    rates = repo.cdi_rates(conn, start)
    bova = repo.benchmark_adj_close(conn, "BOVA11", start)

    cdi = CdiIndex(rates) if rates else None
    result = simulate(trades, params, cdi)
    result["cash_earns_cdi"] = cdi is not None
    result["benchmarks"] = {
        "cdi": benchmark(cdi_series(cdi), params.initial_capital, start, end)
        if cdi
        else {"available": False},
        "bova11": benchmark(bova, params.initial_capital, start, end),
    }
    return result


def per_year_latest(conn: psycopg.Connection, setup_code: str | None = None) -> dict:
    """(setup → variante → ano → (n, soma R)) da execução mais recente de cada variante."""
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
