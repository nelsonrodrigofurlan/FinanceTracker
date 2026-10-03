"""Validação de candles antes de gravar.

Linha inválida é descartada e reportada, nunca corrigida.
"""

from dataclasses import dataclass, field

import pandas as pd

PRICE_COLS = ["open", "high", "low", "close", "adj_close"]


@dataclass
class QualityReport:
    dropped: dict[str, int] = field(default_factory=dict)

    def add(self, reason: str, count: int) -> None:
        if count:
            self.dropped[reason] = self.dropped.get(reason, 0) + count

    @property
    def total_dropped(self) -> int:
        return sum(self.dropped.values())


def clean_candles(df: pd.DataFrame) -> tuple[pd.DataFrame, QualityReport]:
    """Remove linhas que violam regras básicas de OHLC. Espera colunas normalizadas."""
    report = QualityReport()
    out = df.copy()

    rules: list[tuple[str, pd.Series]] = [
        ("valor_ausente", out[PRICE_COLS + ["volume"]].isna().any(axis=1)),
        ("preco_nao_positivo", (out[PRICE_COLS] <= 0).any(axis=1)),
        ("volume_negativo", out["volume"] < 0),
        ("maxima_menor_que_minima", out["high"] < out["low"]),
        ("maxima_inconsistente", out["high"] < out[["open", "close"]].max(axis=1)),
        ("minima_inconsistente", out["low"] > out[["open", "close"]].min(axis=1)),
    ]
    for reason, mask in rules:
        mask = mask.reindex(out.index, fill_value=False)
        report.add(reason, int(mask.sum()))
        out = out[~mask]

    duplicated = out.index.duplicated(keep="last")
    report.add("data_duplicada", int(duplicated.sum()))
    out = out[~duplicated]
    return out.sort_index(), report
