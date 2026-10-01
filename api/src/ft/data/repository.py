"""Acesso ao banco para dados de mercado (schema `ft`)."""

from datetime import date
from decimal import Decimal

import pandas as pd
import psycopg
from psycopg.types.json import Jsonb

from ft.data.yahoo import SOURCE, DailyHistory, to_yahoo_symbol

BENCHMARKS = {
    "BOVA11": ("etf", "ISHARES IBOVESPA"),
    "SMAL11": ("etf", "ISHARES SMALL CAP"),
}


def _dec(value: float, places: int) -> Decimal:
    return Decimal(str(round(float(value), places)))


def ensure_asset(
    conn: psycopg.Connection,
    ticker: str,
    asset_type: str = "stock",
    is_benchmark: bool = False,
    name: str | None = None,
) -> int:
    row = conn.execute(
        """
        insert into ft.assets (ticker, yahoo_symbol, type, is_benchmark, name)
        values (%s, %s, %s, %s, %s)
        on conflict (ticker) do update set
            name = coalesce(excluded.name, ft.assets.name), updated_at = now()
        returning id
        """,
        (ticker, to_yahoo_symbol(ticker), asset_type, is_benchmark, name),
    ).fetchone()
    return int(row[0])


def last_candle_date(conn: psycopg.Connection, asset_id: int) -> date | None:
    row = conn.execute(
        "select max(date) from ft.candles_daily where asset_id = %s", (asset_id,)
    ).fetchone()
    return row[0] if row else None


def upsert_history(conn: psycopg.Connection, asset_id: int, history: DailyHistory) -> int:
    candles = history.candles
    rows = [
        (
            asset_id,
            day,
            _dec(r.open, 4),
            _dec(r.high, 4),
            _dec(r.low, 4),
            _dec(r.close, 4),
            _dec(r.adj_close, 8),
            int(r.volume),
            _dec(float(r.close) * float(r.volume), 2),
            SOURCE,
        )
        for day, r in candles.iterrows()
    ]
    with conn.cursor() as cur:
        cur.executemany(
            """
            insert into ft.candles_daily
                (asset_id, date, open, high, low, close, adj_close, volume, fin_volume, source)
            values (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            on conflict (asset_id, date) do update set
                open = excluded.open, high = excluded.high, low = excluded.low,
                close = excluded.close, adj_close = excluded.adj_close,
                volume = excluded.volume, fin_volume = excluded.fin_volume,
                source = excluded.source, updated_at = now()
            """,
            rows,
        )
        events = [
            (asset_id, d, "dividend", _dec(v, 8), SOURCE) for d, v in history.dividends.items()
        ]
        events += [(asset_id, d, "split", _dec(v, 8), SOURCE) for d, v in history.splits.items()]
        if events:
            cur.executemany(
                """
                insert into ft.corporate_events (asset_id, date, type, value, source)
                values (%s, %s, %s, %s, %s)
                on conflict (asset_id, date, type) do update set value = excluded.value
                """,
                events,
            )
    return len(rows)


def known_events(conn: psycopg.Connection, asset_id: int) -> set[tuple[date, str]]:
    rows = conn.execute(
        "select date, type from ft.corporate_events where asset_id = %s", (asset_id,)
    ).fetchall()
    return {(d, t) for d, t in rows}


def fin_volume_series(conn: psycopg.Connection, asset_id: int, sessions: int) -> pd.Series:
    rows = conn.execute(
        """
        select date, fin_volume from ft.candles_daily
        where asset_id = %s order by date desc limit %s
        """,
        (asset_id, sessions),
    ).fetchall()
    return pd.Series({d: float(v) for d, v in rows}, dtype="float64")


def latest_snapshot(conn: psycopg.Connection) -> tuple[date, list[str], list[str]] | None:
    row = conn.execute(
        """
        select ref_date, candidates, selected from ft.universe_snapshots
        order by ref_date desc limit 1
        """
    ).fetchone()
    return (row[0], list(row[1]), list(row[2])) if row else None


def save_snapshot(
    conn: psycopg.Connection,
    ref_date: date,
    criteria: dict,
    candidates: list[str],
    selected: list[str],
) -> None:
    conn.execute(
        """
        insert into ft.universe_snapshots (ref_date, criteria, candidates, selected)
        values (%s, %s, %s, %s)
        on conflict (ref_date) do update set
            criteria = excluded.criteria,
            candidates = excluded.candidates,
            selected = excluded.selected
        """,
        (ref_date, Jsonb(criteria), candidates, selected),
    )


def set_active(conn: psycopg.Connection, active_tickers: set[str]) -> None:
    """Ativo = selecionado no universo atual ou referência de mercado. Nada é apagado."""
    conn.execute(
        "update ft.assets set active = (ticker = any(%s) or is_benchmark), updated_at = now()",
        (sorted(active_tickers),),
    )


def active_assets(conn: psycopg.Connection) -> list[tuple[int, str]]:
    return [
        (int(i), t)
        for i, t in conn.execute(
            "select id, ticker from ft.assets where active order by ticker"
        ).fetchall()
    ]


def start_run(conn: psycopg.Connection, job: str) -> int:
    row = conn.execute(
        "insert into ft.pipeline_runs (job, status) values (%s, 'running') returning id", (job,)
    ).fetchone()
    conn.commit()
    return int(row[0])


def finish_run(
    conn: psycopg.Connection, run_id: int, status: str, stats: dict, error: str | None = None
) -> None:
    conn.execute(
        """
        update ft.pipeline_runs
        set status = %s, stats = %s, error = %s, finished_at = now()
        where id = %s
        """,
        (status, Jsonb(stats), error, run_id),
    )
    conn.commit()


def missing_sessions(
    conn: psycopg.Connection, lookback_days: int = 60, quorum: float = 0.8
) -> dict[str, list[str]]:
    """Pregões recentes ausentes por ativo ativo.

    Um dia conta como pregão se pelo menos `quorum` dos ativos ativos têm candle nele
    (evita depender de calendário de feriados externo).
    """
    rows = conn.execute(
        """
        with active as (select id, ticker from ft.assets where active),
        recent as (
            select c.asset_id, c.date from ft.candles_daily c
            join active a on a.id = c.asset_id
            where c.date >= current_date - %s
        ),
        sessions as (
            select date from recent group by date
            having count(*) >= %s * (select count(*) from active)
        )
        select a.ticker, s.date
        from active a cross join sessions s
        where not exists (
            select 1 from recent r where r.asset_id = a.id and r.date = s.date
        )
        order by a.ticker, s.date
        """,
        (lookback_days, quorum),
    ).fetchall()
    result: dict[str, list[str]] = {}
    for ticker, day in rows:
        result.setdefault(ticker, []).append(day.isoformat())
    return result
