"""Pesquisa de momentum: roda as 8 variantes e compara com CDI e BOVA11 por período.

Uso (a partir de `api/`):
    uv run python -m ft.backtest.momentum_run
"""

import logging
import sys
from datetime import timedelta

import pandas as pd

from ft.backtest.data import load_regime, load_universe
from ft.backtest.engine import Costs
from ft.backtest.momentum import (
    build_eligibility,
    build_matrices,
    curve_stats,
    simulate,
    variants,
)
from ft.backtest.portfolio import CdiIndex
from ft.backtest.run import PERIOD_START, split_date
from ft.config import get_settings
from ft.data import repository as repo
from ft.db.connection import connect

logger = logging.getLogger("ft.momentum")
WF_LOOKBACK_YEARS = 5


def yearly_returns(curve: pd.Series) -> dict[int, float]:
    out = {}
    years = sorted({d.year for d in curve.index})
    for y in years:
        seg = curve[[d.year == y for d in curve.index]]
        prev = curve[[d.year < y for d in curve.index]]
        base = prev.iloc[-1] if len(prev) else seg.iloc[0]
        out[y] = seg.iloc[-1] / base - 1
    return out


def _compound(returns: dict[int, float], years: tuple[int, ...]) -> float:
    acc = 1.0
    for y in years:
        acc *= 1 + returns.get(y, 0.0)
    return acc


def walk_forward(yearly: dict[str, dict[int, float]], first_year: int) -> list[dict]:
    """Escolhe, a cada ano, a variante com maior retorno acumulado nos 5 anos anteriores."""
    years = sorted({y for v in yearly.values() for y in v})
    rows = []
    for y in years:
        window = [w for w in range(y - WF_LOOKBACK_YEARS, y) if w >= first_year]
        if len(window) < WF_LOOKBACK_YEARS:
            continue

        best = max(yearly, key=lambda v, years=tuple(window): _compound(yearly[v], years))
        rows.append({"year": y, "variant": best, "return": yearly[best].get(y, 0.0)})
    return rows


def run(base: str = "yahoo", mode: str = "conservative") -> int:
    settings = get_settings()
    logging.basicConfig(level=settings.log_level, format="%(message)s")
    costs = Costs()
    with connect(settings) as conn:
        if base == "b3":
            from ft.research.dataset import build

            data = build(mode=mode)
            bars = data.bars
            info = {"note": "Base B3 ponto a ponto, conservadora (ver ft/research/dataset.py)."}
            logger.info("base B3: %s", {k: v for k, v in data.report.items() if k != "regras"})
        else:
            bars, info = load_universe(conn, PERIOD_START)
        regime = load_regime(conn, PERIOD_START)
        cdi = CdiIndex(repo.cdi_rates(conn, PERIOD_START))
        bova = repo.benchmark_adj_close(conn, "BOVA11", PERIOD_START)

    close, open_ = build_matrices(bars)
    close = close[[d >= PERIOD_START - timedelta(days=400) for d in close.index]]
    open_ = open_.reindex(close.index)
    eligible = build_eligibility(bars, close.index)
    dates = list(close.index)
    end = dates[-1]
    start = next(d for d in dates if d >= PERIOD_START)  # antes disso: só aquecimento
    split = split_date(PERIOD_START, end)
    cdi_c = pd.Series([cdi.at(d) for d in dates], index=dates)
    bova_c = pd.Series(bova).sort_index()

    periods = {"total": (start, end), "dentro": (start, split), "fora": (split, end)}
    logger.info(
        "universo %d ações | %s a %s | fora da amostra desde %s", len(bars), start, end, split
    )
    for name, (a, b) in periods.items():
        c = curve_stats(cdi_c, a, b)
        bv = curve_stats(bova_c, max(a, bova_c.index[0]), b)
        logger.info(
            "  CDI %-6s %6.2f%%/ano | BOVA11 %6.2f%%/ano queda %5.1f%% (desde %s)",
            name,
            c["cagr_pct"],
            bv["cagr_pct"],
            bv["max_drawdown_pct"],
            bv["start"],
        )

    yearly: dict[str, dict[int, float]] = {}
    logger.info("\n%-32s %18s %18s %18s", "variante", "total", "dentro", "fora")
    for p in variants():
        curve = simulate(close, open_, p, costs, cdi, regime, eligible=eligible)
        curve = curve[[d >= start for d in curve.index]]
        yearly[p.name()] = yearly_returns(curve)
        cells = []
        for a, b in periods.values():
            s = curve_stats(curve, a, b)
            cells.append(f"{s['cagr_pct']:6.2f}% / -{s['max_drawdown_pct']:4.1f}%")
        logger.info("%-32s %18s %18s %18s", p.name(), *cells)

    cdi_y = yearly_returns(cdi_c)
    wf = walk_forward(yearly, start.year)
    acc = acc_cdi = 1.0
    beat = 0
    logger.info("\nwalk-forward (escolhe pelo retorno dos %d anos anteriores):", WF_LOOKBACK_YEARS)
    for r in wf:
        acc *= 1 + r["return"]
        acc_cdi *= 1 + cdi_y[r["year"]]
        beat += r["return"] > cdi_y[r["year"]]
        logger.info(
            "  %d  %-32s %7.2f%%  (CDI %5.2f%%)",
            r["year"],
            r["variant"],
            r["return"] * 100,
            cdi_y[r["year"]] * 100,
        )
    n = len(wf)
    logger.info(
        "  acumulado: %.1f%% vs CDI %.1f%% | anos acima do CDI: %d de %d"
        " | %.2f%%/ano vs %.2f%%/ano",
        (acc - 1) * 100,
        (acc_cdi - 1) * 100,
        beat,
        n,
        (acc ** (1 / n) - 1) * 100,
        (acc_cdi ** (1 / n) - 1) * 100,
    )
    logger.info("\n%s", info["note"])
    return 0


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Pesquisa de momentum")
    parser.add_argument("--base", choices=["yahoo", "b3"], default="yahoo")
    parser.add_argument("--modo", choices=["conservative", "optimistic"], default="conservative")
    args = parser.parse_args()
    sys.exit(run(args.base, args.modo))
