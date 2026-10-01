"""Filtro de liquidez do universo.

Critério: média do volume financeiro dos últimos N pregões >= mínimo, com N pregões disponíveis.
Volume financeiro é aproximado por close * volume (Yahoo não fornece o valor oficial).
"""

from dataclasses import dataclass

import pandas as pd


@dataclass(frozen=True)
class LiquidityCriteria:
    min_avg_fin_volume: float = 30_000_000.0
    window: int = 21

    def as_dict(self) -> dict:
        return {"min_avg_fin_volume": self.min_avg_fin_volume, "window": self.window}


def average_fin_volume(fin_volume: pd.Series, window: int) -> float | None:
    """Média dos últimos `window` pregões; None se houver menos pregões que o exigido."""
    recent = fin_volume.dropna().sort_index().tail(window)
    if len(recent) < window:
        return None
    return float(recent.mean())


def select_liquid(
    fin_volume_by_ticker: dict[str, pd.Series], criteria: LiquidityCriteria
) -> tuple[list[str], dict[str, float | None]]:
    averages = {
        ticker: average_fin_volume(series, criteria.window)
        for ticker, series in fin_volume_by_ticker.items()
    }
    selected = sorted(
        t for t, avg in averages.items() if avg is not None and avg >= criteria.min_avg_fin_volume
    )
    return selected, averages
