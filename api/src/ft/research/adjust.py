"""Ajuste de desdobramentos, grupamentos e bonificações para as séries brutas do COTAHIST.

Fonte dos eventos: API pública da B3 (listedCompaniesProxy/GetListedSupplementCompany,
campo `stockDividends`). Semântica do campo `factor`, verificada em 2026-10-02 contra
preços reais (PETR 2008, ITUB 2018/2025, MGLU 2020/2024):
  DESDOBRAMENTO f → ações × (1 + f/100)      (100 = 1→2; 300 = 1→4)
  BONIFICACAO   f → ações × (1 + f/100)      (3 = +3%)
  GRUPAMENTO    f → ações × f                 (0,1 = 10→1)
`lastDatePrior` = último dia "com" (preços até essa data são ajustados).

Nem todo evento cadastrado altera a cotação (ex.: "grupamento" ITUB de 2011 sem efeito no
preço). Por isso o ajuste só é aplicado se a variação observada (abertura seguinte ÷ último
fechamento "com") estiver mais perto do fator teórico do que de "nenhum evento".
Cisões e dividendos NÃO são ajustados aqui.
"""

import base64
import json
import logging
import math
import time
import urllib.request
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path

import pandas as pd

logger = logging.getLogger("ft.research.adjust")

URL = (
    "https://sistemaswebb3-listados.b3.com.br/listedCompaniesProxy/CompanyCall/"
    "GetListedSupplementCompany/{payload}"
)
CACHE_DIR = Path(__file__).resolve().parents[3] / "data" / "cache" / "b3_events"
SHARE_EVENTS = {"DESDOBRAMENTO", "BONIFICACAO", "GRUPAMENTO"}


@dataclass(frozen=True)
class ShareEvent:
    isin: str
    label: str
    last_date_prior: date
    share_multiplier: float  # nº de ações depois ÷ antes

    @property
    def price_factor(self) -> float:
        return 1 / self.share_multiplier


def _br_float(value: str) -> float:
    return float(value.replace(".", "").replace(",", "."))


def parse_events(payload: list) -> list[ShareEvent]:
    out = []
    for company in payload or []:
        for e in company.get("stockDividends") or []:
            label = (e.get("label") or "").upper()
            if label not in SHARE_EVENTS:
                continue
            f = _br_float(e["factor"])
            mult = f if label == "GRUPAMENTO" else 1 + f / 100
            if mult <= 0:
                continue
            day = datetime.strptime(e["lastDatePrior"], "%d/%m/%Y").date()
            out.append(ShareEvent(e["isinCode"], label, day, mult))
    return out


def fetch_company_events(code: str, pause: float = 0.3) -> list[ShareEvent]:
    """Eventos de uma empresa (raiz de 4 letras do ticker), com cache local em JSON."""
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    cache = CACHE_DIR / f"{code}.json"
    if cache.exists():
        payload = json.loads(cache.read_text(encoding="utf-8"))
    else:
        b = base64.b64encode(json.dumps({"issuingCompany": code, "language": "pt-br"}).encode())
        url = URL.format(payload=b.decode())
        request = urllib.request.Request(url, headers={"User-Agent": "FinanceTracker/0.1"})  # noqa: S310
        with urllib.request.urlopen(request, timeout=60) as response:  # noqa: S310
            payload = json.load(response)
        cache.write_text(json.dumps(payload), encoding="utf-8")
        time.sleep(pause)  # gentileza com a API pública
    return parse_events(payload)


def confirmed(event: ShareEvent, series: pd.DataFrame) -> tuple[bool, float | None]:
    """Confirma o evento pelo preço: (aplicar?, razão observada)."""
    before = series[series.index <= event.last_date_prior]
    after = series[series.index > event.last_date_prior]
    if before.empty or after.empty:
        return False, None
    observed = after["open"].iloc[0] / before["close"].iloc[-1]
    if observed <= 0:
        return False, None
    dist_event = abs(math.log(observed) - math.log(event.price_factor))
    dist_none = abs(math.log(observed))
    return dist_event < dist_none, observed


def adjust_series(series: pd.DataFrame, events: list[ShareEvent]) -> tuple[pd.DataFrame, list]:
    """Aplica os eventos confirmados (preços ÷, volume em ações ×) ao período anterior."""
    out = series.astype("float64")  # ajustes geram frações mesmo com entrada inteira
    log = []
    for e in sorted(events, key=lambda x: x.last_date_prior):
        ok, observed = confirmed(e, series)
        log.append(
            {
                "isin": e.isin,
                "label": e.label,
                "date": e.last_date_prior.isoformat(),
                "theoretical": round(e.price_factor, 6),
                "observed": round(observed, 6) if observed else None,
                "applied": ok,
            }
        )
        if not ok:
            continue
        mask = out.index <= e.last_date_prior
        for col in ("open", "high", "low", "close"):
            out.loc[mask, col] = out.loc[mask, col] * e.price_factor
        if "volume" in out:
            out.loc[mask, "volume"] = out.loc[mask, "volume"] * e.share_multiplier
    return out, log
