"""Pesquisa: alternância Ibovespa ↔ CDI. Compara 4 regras com CDI e com comprar-e-segurar.

Uso (a partir de `api/`):
    uv run python -m ft.backtest.timing_run
"""

import logging
import sys
from datetime import date

import pandas as pd

from ft.backtest.engine import Costs
from ft.backtest.momentum import curve_stats
from ft.backtest.momentum_run import WF_LOOKBACK_YEARS, _compound, yearly_returns
from ft.backtest.run import split_date
from ft.backtest.timing import rules, signal, simulate
from ft.config import get_settings
from ft.data import repository as repo
from ft.db.connection import connect

logger = logging.getLogger("ft.timing")
START = date(1995, 1, 2)


def run() -> int:
    settings = get_settings()
    logging.basicConfig(level=settings.log_level, format="%(message)s")
    with connect(settings) as conn:
        rows = conn.execute(
            """
            select c.date, c.close from ft.candles_daily c join ft.assets a on a.id = c.asset_id
            where a.ticker = 'IBOV' order by c.date
            """
        ).fetchall()
        cdi = repo.cdi_rates(conn, date(1994, 1, 1))

    index = pd.Series([float(v) for _, v in rows], index=[d for d, _ in rows])
    rate = pd.Series(cdi).sort_index() / 100
    rate = rate.reindex(index.index).fillna(0.0)  # dia sem CDI publicado: sem rendimento
    cdi_factor = (1 + rate).cumprod()

    keep = [d >= START for d in index.index]
    end = index.index[-1]
    split = split_date(START, end)
    periods = {"total": (START, end), "dentro": (START, split), "fora": (split, end)}

    curves: dict[str, pd.Series] = {}
    switches: dict[str, int] = {}
    for rule in rules():
        sig = signal(index, cdi_factor, rule)
        curve, n = simulate(index[keep], rate[keep], sig[keep], Costs())
        curves[rule.name()] = curve
        switches[rule.name()] = n
    always, _ = simulate(index[keep], rate[keep], pd.Series(True, index=index.index)[keep], Costs())
    only_cdi = 100_000 * cdi_factor[keep] / cdi_factor[keep].iloc[0]

    years = (end - START).days / 365.25
    logger.info("Ibovespa × CDI | %s a %s | fora da amostra desde %s", START, end, split)
    logger.info("%-42s %8s %20s %20s %20s", "estratégia", "trocas/a", "total", "dentro", "fora")
    for name, curve in [
        ("Só CDI", only_cdi),
        ("Comprar e segurar Ibovespa", always),
        *curves.items(),
    ]:
        cells = []
        for a, b in periods.values():
            s = curve_stats(curve, a, b)
            cells.append(f"{s['cagr_pct']:6.2f}% / -{s['max_drawdown_pct']:4.1f}%")
        per_year = switches.get(name, 0) / years
        logger.info("%-42s %8.1f %20s %20s %20s", name, per_year, *cells)

    yearly = {name: yearly_returns(c) for name, c in curves.items()}
    cdi_y = yearly_returns(only_cdi)
    acc = acc_cdi = 1.0
    beat = n_years = 0
    logger.info("\nwalk-forward (melhor regra dos %d anos anteriores):", WF_LOOKBACK_YEARS)
    for y in sorted(cdi_y):
        window = tuple(w for w in range(y - WF_LOOKBACK_YEARS, y) if w >= START.year)
        if len(window) < WF_LOOKBACK_YEARS:
            continue
        best = max(yearly, key=lambda v, ws=window: _compound(yearly[v], ws))
        r = yearly[best].get(y, 0.0)
        acc *= 1 + r
        acc_cdi *= 1 + cdi_y[y]
        beat += r > cdi_y[y]
        n_years += 1
        logger.info("  %d  %-40s %7.2f%%  (CDI %5.2f%%)", y, best, r * 100, cdi_y[y] * 100)
    logger.info(
        "  %.2f%%/ano vs CDI %.2f%%/ano | anos acima do CDI: %d de %d",
        (acc ** (1 / n_years) - 1) * 100,
        (acc_cdi ** (1 / n_years) - 1) * 100,
        beat,
        n_years,
    )
    logger.info("\nImposto de renda não modelado: cada troca realiza ganho tributável [VERIFICAR].")
    return 0


if __name__ == "__main__":
    sys.exit(run())
