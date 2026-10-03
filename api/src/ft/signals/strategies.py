"""Classificação das estratégias a partir do laboratório (regra objetiva, sem escolha manual).

- approved:    a execução passou em todos os critérios formais de aprovação.
- observation: não passou, mas o walk-forward do setup é positivo E a carteira de referência
               (risco 1%, 5 posições, teto 20%, caixa no CDI) rendeu mais que o CDI
               NO PERÍODO FORA DA AMOSTRA (o período inteiro deixaria anos antigos "comprarem"
               o resultado — exatamente o viés que a divisão 70/30 existe para evitar).
               → entra só na operação SIMULADA; operação real bloqueada no app.
- rejected:    demais casos.

Uso (a partir de `api/`):
    uv run python -m ft.signals.strategies
"""

import logging
import sys
from datetime import date

import psycopg
from psycopg.types.json import Jsonb

from ft.backtest.evaluation import (
    REFERENCE_PARAMS,
    per_year_latest,
    portfolio_with_benchmarks,
    run_trades,
)
from ft.backtest.walkforward import WalkForwardParams, walk_forward
from ft.config import get_settings
from ft.data.market_time import now_b3
from ft.db.connection import connect

logger = logging.getLogger("ft.strategies")


def classify(
    run_approved: bool,
    wf_expectancy: float | None,
    portfolio_cagr: float | None,
    cdi_cagr: float | None,
) -> str:
    if run_approved:
        return "approved"
    wf_ok = wf_expectancy is not None and wf_expectancy > 0
    beats_cdi = portfolio_cagr is not None and cdi_cagr is not None and portfolio_cagr > cdi_cagr
    return "observation" if wf_ok and beats_cdi else "rejected"


def _latest_runs(conn: psycopg.Connection) -> list[tuple]:
    return conn.execute(
        """
        select distinct on (setup_code, variant)
               id, setup_code, variant, params, approved, metrics, split_date
        from ft.backtest_runs order by setup_code, variant, created_at desc
        """
    ).fetchall()


def _walkforward_by_setup(conn: psycopg.Connection) -> dict[str, dict]:
    per_setup = per_year_latest(conn)
    return {code: walk_forward(per, WalkForwardParams()) for code, per in per_setup.items()}


def refresh(conn: psycopg.Connection, today: date) -> list[dict]:
    wf = _walkforward_by_setup(conn)
    out = []
    for run_id, code, variant, params, approved, metrics, split in _latest_runs(conn):
        oos_trades = [t for t in run_trades(conn, run_id) if t.entry_date >= split]
        portfolio = portfolio_with_benchmarks(conn, oos_trades, REFERENCE_PARAMS)
        cdi = (portfolio or {}).get("benchmarks", {}).get("cdi", {})
        status = classify(
            approved,
            wf.get(code, {}).get("expectancy_r"),
            (portfolio or {}).get("cagr_pct"),
            cdi.get("cagr_pct"),
        )
        evidence = {
            "run_id": run_id,
            "oos": metrics.get("out_of_sample", {}),
            "walkforward_expectancy_r": wf.get(code, {}).get("expectancy_r"),
            "walkforward_trades": wf.get(code, {}).get("trades"),
            "reference_portfolio": REFERENCE_PARAMS.as_dict(),
            "portfolio_period": f"fora da amostra (desde {split.isoformat()})",
            "portfolio_cagr_pct": (portfolio or {}).get("cagr_pct"),
            "portfolio_max_drawdown_pct": (portfolio or {}).get("max_drawdown_pct"),
            "cdi_cagr_pct": cdi.get("cagr_pct"),
        }
        conn.execute(
            """
            insert into ft.strategies (setup_code, variant, params, status, source_run_id,
                                       evidence, sim_start_date)
            values (%(code)s, %(variant)s, %(params)s, %(status)s, %(run)s, %(evidence)s,
                    case when %(status)s in ('approved', 'observation') then %(today)s end)
            on conflict (setup_code, variant) do update set
                params = excluded.params,
                status = excluded.status,
                source_run_id = excluded.source_run_id,
                evidence = excluded.evidence,
                decided_at = now(),
                -- mantém a data de início enquanto seguir operável; zera se for reprovada
                sim_start_date = case
                    when excluded.status = 'rejected' then null
                    else coalesce(ft.strategies.sim_start_date, excluded.sim_start_date)
                end
            """,
            {
                "code": code,
                "variant": variant,
                "params": Jsonb(params),
                "status": status,
                "run": run_id,
                "evidence": Jsonb(evidence),
                "today": today,
            },
        )
        out.append({"setup": code, "variant": variant, "status": status, **evidence})
    conn.commit()
    return out


def main() -> int:
    settings = get_settings()
    logging.basicConfig(level=settings.log_level, format="%(message)s")
    with connect(settings) as conn:
        for row in refresh(conn, now_b3().date()):
            logger.info(
                "%-3s %-40s %-12s WF=%s carteira=%s%% CDI=%s%%",
                row["setup"],
                row["variant"][:40],
                row["status"],
                row["walkforward_expectancy_r"],
                row["portfolio_cagr_pct"],
                row["cdi_cagr_pct"],
            )
    return 0


if __name__ == "__main__":
    sys.exit(main())
