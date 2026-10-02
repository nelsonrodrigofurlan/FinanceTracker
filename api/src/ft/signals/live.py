"""Scanner diário e carteira simulada — mesmo motor e mesmos setups do laboratório.

Ao vivo usa o preço REAL (ajustado só por desdobramentos, como o Yahoo entrega `close`), não o
ajustado por dividendos: na vida real a ação cai no dia "ex" e isso pode acionar o stop.
Só estratégias com status 'approved' ou 'observation' geram sinais/simulação.
"""

import logging
from datetime import date

import numpy as np
import psycopg

from ft.backtest.data import load_regime
from ft.backtest.engine import Bars, Costs, run_asset
from ft.backtest.setups import from_params

logger = logging.getLogger("ft.signals.live")

LIVE_SESSIONS = 420  # aquecimento suficiente para MMA200 / ATR / médias
OPERABLE = ("approved", "observation")


def operable_strategies(conn: psycopg.Connection) -> list[tuple]:
    return conn.execute(
        """
        select id, setup_code, variant, params, status, sim_start_date
        from ft.strategies where status = any(%s) order by setup_code, variant
        """,
        (list(OPERABLE),),
    ).fetchall()


def load_live_bars(conn: psycopg.Connection, sessions: int = LIVE_SESSIONS) -> dict[str, Bars]:
    rows = conn.execute(
        """
        with ranked as (
            select a.ticker, c.date, c.open, c.high, c.low, c.close, c.volume,
                   row_number() over (partition by a.id order by c.date desc) rn
            from ft.candles_daily c join ft.assets a on a.id = c.asset_id
            where a.active and a.type = 'stock'
        )
        select ticker, date, open, high, low, close, volume from ranked
        where rn <= %s order by ticker, date
        """,
        (sessions,),
    ).fetchall()
    grouped: dict[str, list] = {}
    for r in rows:
        grouped.setdefault(r[0], []).append(r[1:])
    if not grouped:
        return {}
    first = min(v[0][0] for v in grouped.values())
    regime = load_regime(conn, first)
    bars = {}
    for ticker, data in grouped.items():
        arr = np.array([[float(x) for x in d[1:]] for d in data])
        dates = [d[0] for d in data]
        b = Bars(ticker, dates, arr[:, 0], arr[:, 1], arr[:, 2], arr[:, 3], arr[:, 4])
        b.regime = np.array([regime.get(d, False) for d in dates], dtype=bool)
        bars[ticker] = b
    return bars


def scan(conn: psycopg.Connection, bars: dict[str, Bars]) -> list[dict]:
    """Sinais do último pregão de cada ativo, para cada estratégia operável."""
    found = []
    for sid, code, variant, params, status, _start in operable_strategies(conn):
        setup = from_params(code, params)
        for ticker, b in bars.items():
            t = len(b) - 1
            if t < 1:
                continue
            if getattr(setup, "regime_filter", False) and not b.regime[t]:
                continue
            order = setup.signal(t, b, setup.prepare(b))
            if order is None:
                continue
            found.append(
                {
                    "strategy_id": sid,
                    "setup": code,
                    "variant": variant,
                    "status": status,
                    "ticker": ticker,
                    "signal_date": b.dates[t],
                    "order_kind": order.kind,
                    "entry_level": order.level,
                    "ref_price": float(b.close[t]),
                    "stop": order.stop,
                    "stop_distance": order.stop_distance,
                    "risk_distance": order.risk_distance,
                    "target_r": order.target_r,
                    "expires_after": (order.expires - t) if order.expires is not None else None,
                }
            )
    return found


def save_signals(conn: psycopg.Connection, signals: list[dict]) -> int:
    with conn.cursor() as cur:
        cur.executemany(
            """
            insert into ft.signals (strategy_id, ticker, signal_date, order_kind, entry_level,
                ref_price, stop, stop_distance, risk_distance, target_r, expires_after)
            values (%(strategy_id)s, %(ticker)s, %(signal_date)s, %(order_kind)s,
                %(entry_level)s, %(ref_price)s, %(stop)s, %(stop_distance)s, %(risk_distance)s,
                %(target_r)s, %(expires_after)s)
            on conflict (strategy_id, ticker, signal_date) do nothing
            """,
            signals,
        )
    conn.commit()
    return len(signals)


def rebuild_sim_book(conn: psycopg.Connection, bars: dict[str, Bars], costs: Costs) -> int:
    """Recalcula a carteira simulada de cada estratégia desde a sua data de início."""
    total = 0
    for sid, code, _variant, params, _status, start in operable_strategies(conn):
        conn.execute("delete from ft.sim_trades where strategy_id = %s", (sid,))
        if start is None:
            continue
        setup = from_params(code, params)
        rows = []
        for b in bars.values():
            first = next((i for i, d in enumerate(b.dates) if d >= start), None)
            if first is None:
                continue
            for tr in run_asset(setup, b, costs, start_idx=first):
                is_open = tr.exit_reason == "fim_dos_dados"
                rows.append(
                    (
                        sid,
                        tr.ticker,
                        tr.entry_date,
                        tr.entry_price,
                        tr.initial_stop,
                        tr.target,
                        None if is_open else tr.exit_date,
                        tr.exit_price,
                        None if is_open else tr.exit_reason,
                        tr.r_multiple,
                        tr.bars,
                        "open" if is_open else "closed",
                    )
                )
        if rows:
            with conn.cursor() as cur:
                cur.executemany(
                    """
                    insert into ft.sim_trades (strategy_id, ticker, entry_date, entry_price,
                        initial_stop, target, exit_date, exit_price, exit_reason, r_multiple,
                        bars, status)
                    values (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    """,
                    rows,
                )
        total += len(rows)
    conn.commit()
    return total


def run_daily(conn: psycopg.Connection, today: date | None = None) -> dict:
    bars = load_live_bars(conn)
    signals = scan(conn, bars)
    saved = save_signals(conn, signals)
    book = rebuild_sim_book(conn, bars, Costs())
    return {"assets": len(bars), "signals": saved, "sim_trades": book, "new": signals}
