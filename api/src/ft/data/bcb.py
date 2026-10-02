"""CDI diário do Banco Central (SGS, série 12) — fonte oficial e gratuita.

Verificado em 2026-10-02:
- URL: https://api.bcb.gov.br/dados/serie/bcdata.sgs.12/dados?formato=json&dataInicial=dd/mm/aaaa&dataFinal=dd/mm/aaaa
- Valor em % ao dia útil (ex.: "0.064893" em 03/01/2005).
- Séries diárias aceitam janela de no máximo 10 anos por consulta (HTTP 406 acima disso).
"""

import json
import urllib.request
from datetime import date, datetime, timedelta

URL = (
    "https://api.bcb.gov.br/dados/serie/bcdata.sgs.12/dados"
    "?formato=json&dataInicial={start}&dataFinal={end}"
)
CHUNK_YEARS = 5


def parse(payload: list[dict]) -> dict[date, float]:
    out: dict[date, float] = {}
    for item in payload:
        day = datetime.strptime(item["data"], "%d/%m/%Y").date()
        rate = float(item["valor"])
        if not 0 <= rate < 1:  # % ao dia; acima de 1%/dia é dado corrompido
            raise ValueError(f"CDI fora da faixa esperada em {day}: {rate}")
        out[day] = rate
    return out


def chunks(start: date, end: date, years: int = CHUNK_YEARS) -> list[tuple[date, date]]:
    """Blocos por ano-calendário (evita problema com 29/02) dentro do limite de 10 anos."""
    out = []
    cursor = start
    while cursor <= end:
        stop = min(date(cursor.year + years - 1, 12, 31), end)
        out.append((cursor, stop))
        cursor = stop + timedelta(days=1)
    return out


def fetch_cdi(start: date, end: date, timeout: float = 30) -> dict[date, float]:
    result: dict[date, float] = {}
    for a, b in chunks(start, end):
        url = URL.format(start=a.strftime("%d/%m/%Y"), end=b.strftime("%d/%m/%Y"))
        request = urllib.request.Request(url, headers={"User-Agent": "FinanceTracker/0.1"})  # noqa: S310
        with urllib.request.urlopen(request, timeout=timeout) as response:  # noqa: S310
            result.update(parse(json.load(response)))
    return result
