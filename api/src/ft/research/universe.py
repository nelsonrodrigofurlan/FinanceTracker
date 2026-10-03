"""Universo histórico ponto a ponto (sem viés de sobrevivência), a partir do COTAHIST.

Em cada fim de mês: as `top_n` ações (por ISIN) com maior volume financeiro médio nos
`window` pregões anteriores, negociadas em pelo menos `min_days` deles. ISIN é a identidade
(sobrevive a troca de ticker, ex.: VIIA3 → BHIA3). Dia sem negócio conta volume zero.
"""

from dataclasses import dataclass
from datetime import date

import pandas as pd


@dataclass(frozen=True)
class UniverseRule:
    top_n: int = 100
    window: int = 21
    min_days: int = 15


def daily_fin_volume(raw: pd.DataFrame) -> pd.DataFrame:
    """Matriz datas × ISIN de volume financeiro (soma dos tickers do mesmo ISIN no dia)."""
    grouped = raw.groupby(["date", "isin"], sort=True)["fin_volume"].sum()
    return grouped.unstack("isin").sort_index()


def month_ends(dates: list[date]) -> list[date]:
    return [
        d
        for d, nxt in zip(dates, dates[1:], strict=False)
        if (d.year, d.month) != (nxt.year, nxt.month)
    ] + ([dates[-1]] if dates else [])


def monthly_members(volume: pd.DataFrame, rule: UniverseRule = UniverseRule()) -> dict:  # noqa: B008
    """{fim_de_mês: [ISINs]} — só usa dados até o próprio fim de mês."""
    traded = volume.notna().astype(int).rolling(rule.window, min_periods=rule.window).sum()
    avg = volume.fillna(0.0).rolling(rule.window, min_periods=rule.window).mean()
    out = {}
    for d in month_ends(list(volume.index)):
        eligible = avg.loc[d][traded.loc[d] >= rule.min_days].dropna()
        out[d] = list(eligible.sort_values(ascending=False).index[: rule.top_n])
    return out


def isin_labels(raw: pd.DataFrame) -> pd.DataFrame:
    """ISIN → último ticker, nome e datas de primeira/última negociação."""
    ordered = raw.sort_values("date")
    last = ordered.groupby("isin").last()[["ticker", "name", "date", "codbdi"]]
    first = ordered.groupby("isin")["date"].first()
    return last.rename(columns={"date": "last_date"}).assign(first_date=first)
