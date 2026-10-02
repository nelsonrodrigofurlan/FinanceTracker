"""Job diário (Cloud Run Job): universo → coleta → (F5: scanner) → (F6: alertas).

Uso (a partir de `api/`):
    uv run python -m ft.pipeline
"""

import argparse
import logging
import sys
from collections.abc import Callable
from datetime import date, timedelta

import psycopg

from ft import __version__
from ft.alerts import telegram
from ft.config import get_settings
from ft.data import repository as repo
from ft.data.bcb import fetch_cdi
from ft.data.market_time import now_b3
from ft.data.quality import clean_candles
from ft.data.yahoo import DailyHistory, fetch_daily
from ft.db.connection import connect
from ft.universe.b3 import fetch_ibrx100
from ft.universe.selection import LiquidityCriteria, select_liquid

logger = logging.getLogger("ft.pipeline")

INCREMENTAL_OVERLAP_DAYS = 10

Fetcher = Callable[[str, date | None], DailyHistory]


def has_new_events(history: DailyHistory, known: set[tuple[date, str]]) -> bool:
    """Provento/desdobramento novo muda o ajuste de todo o histórico → exige recarga completa."""
    fetched = {(d, "dividend") for d in history.dividends.index}
    fetched |= {(d, "split") for d in history.splits.index}
    return bool(fetched - known)


def update_asset(
    conn: psycopg.Connection, asset_id: int, ticker: str, fetch: Fetcher = fetch_daily
) -> dict:
    last = repo.last_candle_date(conn, asset_id)
    mode = "full"
    if last is None:
        history = fetch(ticker, None)
    else:
        history = fetch(ticker, last - timedelta(days=INCREMENTAL_OVERLAP_DAYS))
        mode = "incremental"
        if has_new_events(history, repo.known_events(conn, asset_id)):
            history = fetch(ticker, None)
            mode = "full_reload_new_event"

    candles, report = clean_candles(history.candles)
    history = DailyHistory(candles=candles, dividends=history.dividends, splits=history.splits)
    written = repo.upsert_history(conn, asset_id, history)
    conn.commit()
    return {"mode": mode, "rows": written, "dropped": report.dropped}


def refresh_universe(
    conn: psycopg.Connection,
    today: date,
    criteria: LiquidityCriteria,
    fetch: Fetcher = fetch_daily,
    fetch_candidates: Callable[[], dict[str, str | None]] = fetch_ibrx100,
    force: bool = False,
) -> dict:
    """Recalcula o universo uma vez por mês. Retorna estatísticas."""
    snapshot = repo.latest_snapshot(conn)
    same_month = snapshot and (snapshot[0].year, snapshot[0].month) == (today.year, today.month)
    if same_month and not force:
        return {"refreshed": False, "selected": len(snapshot[2])}

    try:
        names = fetch_candidates()
        candidates = list(names)
        source = "b3_ibrx100"
    except Exception as exc:  # noqa: BLE001
        if not snapshot:
            raise RuntimeError("Sem composição do IBrX-100 e sem snapshot anterior") from exc
        logger.warning("B3 indisponível (%s); reutilizando candidatos do último snapshot", exc)
        candidates, source = snapshot[1], "snapshot_anterior"
        names = dict.fromkeys(candidates)

    fin_volumes, errors = {}, {}
    for ticker in candidates:
        try:
            asset_id = repo.ensure_asset(conn, ticker, name=names.get(ticker))
            update_asset(conn, asset_id, ticker, fetch)
            fin_volumes[ticker] = repo.fin_volume_series(conn, asset_id, criteria.window)
        except Exception as exc:  # noqa: BLE001 — um ativo com problema não derruba o job
            conn.rollback()
            errors[ticker] = f"{type(exc).__name__}: {exc}"[:200]
            logger.warning("universo: %s ignorado (%s)", ticker, exc)

    selected, averages = select_liquid(fin_volumes, criteria)
    repo.save_snapshot(conn, today, {**criteria.as_dict(), "source": source}, candidates, selected)
    repo.set_active(conn, set(selected))
    conn.commit()
    return {
        "refreshed": True,
        "source": source,
        "candidates": len(candidates),
        "selected": len(selected),
        "errors": errors,
    }


CDI_START = date(2005, 1, 1)


def update_cdi(conn: psycopg.Connection) -> dict:
    """CDI (BCB). Falha aqui não derruba a coleta de preços: só fica registrada."""
    try:
        last = repo.last_cdi_date(conn)
        start = last + timedelta(days=1) if last else CDI_START
        today = now_b3().date()
        if start > today:
            return {"rows": 0}
        rows = repo.upsert_cdi(conn, fetch_cdi(start, today))
        conn.commit()
        return {"rows": rows}
    except Exception as exc:  # noqa: BLE001
        conn.rollback()
        logger.warning("CDI não atualizado: %s", exc)
        return {"error": f"{type(exc).__name__}: {exc}"[:200]}


def run(fetch: Fetcher = fetch_daily, force_universe: bool = False, notify: bool = True) -> int:
    settings = get_settings()
    logging.basicConfig(level=settings.log_level, format="%(asctime)s %(levelname)s %(message)s")
    logger.info("pipeline start version=%s env=%s", __version__, settings.app_env)

    with connect(settings) as conn:
        run_id = repo.start_run(conn, "daily")
        stats: dict = {}
        try:
            for ticker, (asset_type, name) in repo.BENCHMARKS.items():
                repo.ensure_asset(conn, ticker, asset_type, is_benchmark=True, name=name)
            conn.commit()

            stats["cdi"] = update_cdi(conn)

            stats["universe"] = refresh_universe(
                conn, now_b3().date(), LiquidityCriteria(), fetch, force=force_universe
            )

            updated, errors = {}, {}
            for asset_id, ticker in repo.active_assets(conn):
                try:
                    updated[ticker] = update_asset(conn, asset_id, ticker, fetch)
                except Exception as exc:  # noqa: BLE001
                    conn.rollback()
                    errors[ticker] = f"{type(exc).__name__}: {exc}"[:200]
                    logger.warning("coleta: %s falhou (%s)", ticker, exc)
            stats["update"] = {
                "assets": len(updated),
                "rows": sum(u["rows"] for u in updated.values()),
                "full_reloads": sorted(t for t, u in updated.items() if u["mode"] != "incremental"),
                "errors": errors,
            }
            stats["quality"] = {"missing_sessions": repo.missing_sessions(conn)}
            from ft.signals.live import run_daily  # import tardio: evita ciclo com o laboratório

            live = run_daily(conn)
            stats["signals"] = {k: v for k, v in live.items() if k != "new"}
            if stats["quality"]["missing_sessions"]:
                logger.warning("pregões faltando: %s", stats["quality"]["missing_sessions"])
            repo.finish_run(conn, run_id, "success", stats)
            if notify:
                telegram.send(
                    settings, telegram.daily_summary(stats, live["new"], settings.app_env)
                )
            logger.info(
                "pipeline ok: %s", {k: v for k, v in stats["update"].items() if k != "errors"}
            )
            return 0
        except Exception as exc:
            conn.rollback()
            message = f"{type(exc).__name__}: {exc}"[:1000]
            repo.finish_run(conn, run_id, "failed", stats, message)
            if notify:
                telegram.send(settings, telegram.failure_message(settings.app_env, message))
            logger.exception("pipeline falhou")
            return 1


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Job diário de dados de mercado")
    parser.add_argument(
        "--force-universe", action="store_true", help="recalcula o universo mesmo já feito no mês"
    )
    parser.add_argument("--sem-alerta", action="store_true", help="não envia Telegram")
    args = parser.parse_args()
    sys.exit(run(force_universe=args.force_universe, notify=not args.sem_alerta))
