"""Base de pesquisa SEM viés de sobrevivência e com tratamento CONSERVADOR de lacunas.

Fonte: COTAHIST oficial da B3 (inclui empresas que saíram da bolsa) + eventos de ações da B3.
Regras (aprovadas pelo usuário em 2026-10-02, "opção 1 — teste conservador"):
1. Universo ponto a ponto: só pode operar a ação nos meses em que ela estava no top-100 de
   liquidez (ver universe.py). Identidade por ISIN.
2. Desdobramento/grupamento/bonificação cadastrados na B3: aplicados se o preço confirmar.
3. Saltos de abertura > +80% ou < −44% sem evento cadastrado:
   - regra rígida (razão a ≤4% de um fator comum E volume em ações muda na mesma proporção,
     ±1,5x, de forma sustentada): tratado como desdobramento/grupamento;
   - QUEDA ambígua: mantida como movimento real (a perda fica);
   - ALTA ambígua: neutralizada (o ganho é removido).
   As duas escolhas ambíguas só podem prejudicar a estratégia.
4. Dividendos e cisões NÃO são incorporados (nenhuma fonte oficial gratuita para empresas
   canceladas) → retornos subestimados de forma uniforme.
5. Ação que para de negociar: posição encerrada no último preço disponível.
"""

import logging
import math
import pickle
from collections import Counter
from dataclasses import dataclass
from datetime import date
from pathlib import Path

import numpy as np
import pandas as pd

from ft.backtest.engine import Bars
from ft.research.adjust import ShareEvent, adjust_series, fetch_company_events
from ft.research.cotahist import load_years
from ft.research.universe import UniverseRule, daily_fin_volume, monthly_members

logger = logging.getLogger("ft.research.dataset")

CACHE_DIR = Path(__file__).resolve().parents[3] / "data" / "cache"
JUMP_UP, JUMP_DOWN = 1.8, 1 / 1.8
COMMON_FACTORS = [2, 3, 4, 5, 6, 8, 10, 20, 25, 50, 100, 200, 500, 1000, 10000]
PRICE_TOLERANCE = 0.04  # desdobramentos reais auditados: 0%–3,2%; AMER3 2023 (queda): 6,7%
VOLUME_TOLERANCE = 1.5  # volume em ações deve mudar ~k vezes (k/1,5 a 1,5k)
VOLUME_WINDOW = 20


@dataclass
class ResearchData:
    bars: dict[str, Bars]  # chave = ISIN; Bars.ticker = último ticker; Bars.tradable = elegível
    labels: dict[str, str]  # ISIN → último ticker
    members: dict[date, list[str]]  # fim de mês → ISINs elegíveis
    report: dict


def classify_jump(
    ratio: float, volume_before: float, volume_after: float
) -> tuple[str, float | None]:
    """('split', multiplicador de ações) | ('real', None) | ('neutralize', None)."""
    best = min(
        COMMON_FACTORS + [1 / k for k in COMMON_FACTORS],
        key=lambda k: abs(math.log(ratio) + math.log(k)),
    )
    price_ok = abs(ratio * best - 1) <= PRICE_TOLERANCE
    volume_ok = (
        volume_before > 0
        and volume_after > 0
        and abs(math.log(volume_after / volume_before) - math.log(best))
        <= math.log(VOLUME_TOLERANCE)
    )
    if price_ok and volume_ok:
        return "split", best
    return ("real", None) if ratio < 1 else ("neutralize", None)


def resolve_jumps(series: pd.DataFrame, mode: str = "conservative") -> tuple[pd.DataFrame, Counter]:
    """Aplica a regra 3 aos saltos que sobraram após os eventos cadastrados.

    mode="optimistic" (só para teste de LIMITE): quedas ambíguas também são neutralizadas.
    """
    out = series.copy()
    counts: Counter = Counter()
    ratios = out["open"].shift(-1) / out["close"]
    vol = out["volume"]
    for i, (day, r) in enumerate(ratios.items()):
        if not np.isfinite(r) or r <= 0 or JUMP_DOWN < r < JUMP_UP:
            continue
        before = vol.iloc[max(0, i - VOLUME_WINDOW) : i + 1].median()
        after = vol.iloc[i + 1 : i + 1 + VOLUME_WINDOW].median()
        kind, mult = classify_jump(float(r), float(before), float(after))
        if mode == "optimistic" and kind == "real":
            kind = "neutralize"
        counts[kind] += 1
        if kind == "real":
            continue
        multiplier = mult if kind == "split" else 1 / float(r)  # neutraliza: remove o salto
        mask = out.index <= day
        for col in ("open", "high", "low", "close"):
            out.loc[mask, col] = out.loc[mask, col] / multiplier
        out.loc[mask, "volume"] = out.loc[mask, "volume"] * multiplier
    return out, counts


def eligibility(dates: list[date], isin: str, members: dict[date, list[str]]) -> np.ndarray:
    """Elegível no dia d se estava no universo do último fim de mês ANTERIOR a d."""
    month_ends = sorted(members)
    member_sets = {m: set(v) for m, v in members.items()}
    out = np.zeros(len(dates), dtype=bool)
    j = -1
    for i, d in enumerate(dates):
        while j + 1 < len(month_ends) and month_ends[j + 1] < d:
            j += 1
        out[i] = j >= 0 and isin in member_sets[month_ends[j]]
    return out


def build(
    first_year: int = 2004,
    last_year: int = 2026,
    use_cache: bool = True,
    mode: str = "conservative",
) -> ResearchData:
    cache = CACHE_DIR / f"research_dataset_v1_{mode}.pkl"
    if use_cache and cache.exists():
        with cache.open("rb") as fh:
            return pickle.load(fh)  # noqa: S301 — cache local gerado por este módulo

    raw = load_years(first_year, last_year)
    members = monthly_members(daily_fin_volume(raw), UniverseRule())
    ever = set().union(*members.values())
    sub = raw[raw["isin"].isin(ever)]

    events: dict[str, list[ShareEvent]] = {}
    api_missing = []
    for root in sorted({t[:4] for t in sub["ticker"].unique()}):
        try:
            for e in fetch_company_events(root):
                events.setdefault(e.isin, []).append(e)
        except Exception:  # noqa: BLE001 — empresa sem cadastro na API
            api_missing.append(root)

    bars: dict[str, Bars] = {}
    labels: dict[str, str] = {}
    totals: Counter = Counter()
    for isin, g in sub.groupby("isin"):
        # Mais de um ticker no mesmo dia para o mesmo ISIN: fica o de maior volume.
        g = g.sort_values("fin_volume").groupby("date").last().sort_index()
        series = g[["open", "high", "low", "close", "volume"]].astype("float64")
        series, log = adjust_series(series, events.get(isin, []))
        totals["eventos_aplicados"] += sum(e["applied"] for e in log)
        totals["eventos_rejeitados"] += sum(not e["applied"] for e in log)
        series, jumps = resolve_jumps(series, mode)
        totals.update({f"saltos_{k}": v for k, v in jumps.items()})
        dates = list(series.index)
        b = Bars(
            ticker=str(g["ticker"].iloc[-1]),
            dates=dates,
            open=series["open"].to_numpy(),
            high=series["high"].to_numpy(),
            low=series["low"].to_numpy(),
            close=series["close"].to_numpy(),
            volume=series["volume"].to_numpy(),
        )
        b.tradable = eligibility(dates, isin, members)
        bars[isin] = b
        labels[isin] = b.ticker

    report = {
        "isins": len(bars),
        "modo": mode,
        "empresas_sem_cadastro_b3": len(api_missing),
        **totals,
        "regras": __doc__,
    }
    data = ResearchData(bars, labels, members, report)
    cache.parent.mkdir(parents=True, exist_ok=True)
    with cache.open("wb") as fh:
        pickle.dump(data, fh)
    return data
