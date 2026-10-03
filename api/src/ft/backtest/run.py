"""Roda o laboratório: todas as variantes de setups no universo e grava os resultados.

Uso (a partir de `api/`):
    uv run python -m ft.backtest.run                 # todas as variantes
    uv run python -m ft.backtest.run --setup S1      # só um setup
    uv run python -m ft.backtest.run --no-cache      # recarrega candles do banco
"""

import argparse
import logging
import sys
import time
from datetime import date, timedelta

import numpy as np
from psycopg.types.json import Jsonb

from ft.backtest.data import load_universe
from ft.backtest.engine import ENGINE_VERSION, Costs, Trade, run_asset
from ft.backtest.metrics import ApprovalCriteria, evaluate
from ft.backtest.setups import describe, variants
from ft.config import get_settings
from ft.db.connection import connect

logger = logging.getLogger("ft.backtest")

PERIOD_START = date(2005, 1, 1)
IN_SAMPLE_FRACTION = 0.7
WARMUP_BARS = 200  # nenhum sinal antes de existir MMA200


def split_date(start: date, end: date, fraction: float = IN_SAMPLE_FRACTION) -> date:
    return start + timedelta(days=int((end - start).days * fraction))


def save_run(
    conn,
    setup,
    variant: str,
    costs: Costs,
    start: date,
    end: date,
    split: date,
    universe: dict,
    metrics: dict,
    approval: dict,
    trades: list[Trade],
) -> int:  # noqa: ANN001
    run_id = conn.execute(
        """
        insert into ft.backtest_runs (setup_code, variant, params, costs, period_start,
            period_end, split_date, universe, metrics, approved, approval, engine_version)
        values (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s) returning id
        """,
        (
            setup.code,
            variant,
            Jsonb(setup.params),
            Jsonb(costs.as_dict()),
            start,
            end,
            split,
            Jsonb(universe),
            Jsonb(metrics),
            approval["approved"],
            Jsonb(approval),
            ENGINE_VERSION,
        ),
    ).fetchone()[0]
    with conn.cursor() as cur:
        cur.executemany(
            """
            insert into ft.backtest_trades (run_id, ticker, entry_date, entry_price, exit_date,
                exit_price, initial_stop, target, r_multiple, return_pct, bars, exit_reason, sample)
            values (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            """,
            [
                (
                    run_id,
                    t.ticker,
                    t.entry_date,
                    t.entry_price,
                    t.exit_date,
                    t.exit_price,
                    t.initial_stop,
                    t.target,
                    t.r_multiple,
                    t.return_pct,
                    t.bars,
                    t.exit_reason,
                    "in" if t.entry_date < split else "out",
                )
                for t in trades
            ],
        )
    conn.commit()
    return run_id


def load_b3_universe(conn) -> tuple[dict, dict]:  # noqa: ANN001
    """Base B3 ponto a ponto, conservadora (ft/research/dataset.py) + regime do Ibovespa."""
    from ft.backtest.data import load_regime
    from ft.research.dataset import build

    data = build()
    regime = load_regime(conn, PERIOD_START)
    for b in data.bars.values():
        b.regime = np.array([regime.get(d, False) for d in b.dates], dtype=bool)
    last = max(b.dates[-1] for b in data.bars.values())
    universe = {
        "base": "b3_ponto_a_ponto_conservadora",
        "tickers": sorted(data.labels.values()),
        "last_date": last.isoformat(),
        "report": {k: v for k, v in data.report.items() if k != "regras"},
        "note": (
            "Base oficial B3 (COTAHIST) com universo ponto a ponto (top-100 de liquidez por mês, "
            "inclui empresas que saíram da bolsa). Conservadora: sem dividendos; quedas ambíguas "
            "mantidas, altas ambíguas neutralizadas. Resultados tendem a ser PESSIMISTAS."
        ),
    }
    return data.bars, universe


def run(
    setup_filter: str | None, use_cache: bool, regime: bool | None = None, base: str = "yahoo"
) -> int:
    settings = get_settings()
    logging.basicConfig(level=settings.log_level, format="%(asctime)s %(message)s")
    costs, criteria = Costs(), ApprovalCriteria()

    with connect(settings) as conn:
        t0 = time.perf_counter()
        if base == "b3":
            bars_by_ticker, universe = load_b3_universe(conn)
        else:
            bars_by_ticker, universe = load_universe(conn, PERIOD_START, use_cache=use_cache)
        logger.info("universo: %d ativos (%.1fs)", len(bars_by_ticker), time.perf_counter() - t0)
        end = date.fromisoformat(universe["last_date"])
        split = split_date(PERIOD_START, end)

        for setup in variants(regime):
            if setup_filter and setup.code != setup_filter:
                continue
            t0 = time.perf_counter()
            trades: list[Trade] = []
            for bars in bars_by_ticker.values():
                trades.extend(run_asset(setup, bars, costs, start_idx=WARMUP_BARS))
            trades = [t for t in trades if t.entry_date >= PERIOD_START]
            metrics, approval = evaluate(trades, split, criteria)
            variant = describe(setup)
            run_id = save_run(
                conn,
                setup,
                variant,
                costs,
                PERIOD_START,
                end,
                split,
                universe,
                metrics,
                approval,
                trades,
            )
            oos = metrics["out_of_sample"]
            logger.info(
                "%s [%s] run=%d trades=%d | fora da amostra: n=%s E=%sR PF=%s acerto=%s%% → %s"
                " (%.1fs)",
                setup.code,
                variant,
                run_id,
                len(trades),
                oos.get("trades"),
                oos.get("expectancy_r"),
                oos.get("profit_factor"),
                oos.get("win_rate"),
                "APROVADO" if approval["approved"] else "reprovado",
                time.perf_counter() - t0,
            )
    return 0


def main() -> None:
    parser = argparse.ArgumentParser(description="Laboratório de backtest")
    parser.add_argument("--setup", choices=["S1", "S2", "S3", "S4", "S5"])
    parser.add_argument("--no-cache", action="store_true")
    parser.add_argument(
        "--regime",
        choices=["todas", "com", "sem"],
        default="todas",
        help="variantes com filtro de regime do Ibovespa, sem, ou todas",
    )
    parser.add_argument("--base", choices=["yahoo", "b3"], default="yahoo")
    args = parser.parse_args()
    regime = {"todas": None, "com": True, "sem": False}[args.regime]
    sys.exit(run(args.setup, use_cache=not args.no_cache, regime=regime, base=args.base))


if __name__ == "__main__":
    main()
