"""Leitura da série histórica oficial da B3 (COTAHIST) — inclui empresas que saíram da bolsa.

Layout verificado no documento oficial "SeriesHistoricas_Layout.pdf" (B3, revisão 01 de
13/04/2017). Registro 01 tem 245 posições; posições abaixo são 1-based inclusivas do documento.
Preços no formato (11)V99 (2 decimais implícitos) e cotados por FATCOT ações (1 ou 1000).

Uso exclusivo de PESQUISA (backtest sem viés de sobrevivência). Cache local em
api/data/cache/cotahist (fora do git e fora do Supabase).
"""

import io
import logging
import urllib.request
import zipfile
from pathlib import Path

import pandas as pd

logger = logging.getLogger("ft.research.cotahist")

URL = "https://bvmf.bmfbovespa.com.br/InstDados/SerHist/COTAHIST_A{year}.ZIP"
CACHE_DIR = Path(__file__).resolve().parents[3] / "data" / "cache" / "cotahist"

# (nome, início, fim) — posições 1-based inclusivas, como no documento da B3.
FIELDS = [
    ("tipreg", 1, 2),
    ("date", 3, 10),
    ("codbdi", 11, 12),
    ("codneg", 13, 24),
    ("tpmerc", 25, 27),
    ("nomres", 28, 39),
    ("especi", 40, 49),
    ("preabe", 57, 69),
    ("premax", 70, 82),
    ("premin", 83, 95),
    ("premed", 96, 108),
    ("preult", 109, 121),
    ("totneg", 148, 152),
    ("quatot", 153, 170),
    ("voltot", 171, 188),
    ("fatcot", 211, 217),
    ("codisi", 231, 242),
]

MERCADO_VISTA = "010"
# Lote padrão + códigos de empresas em dificuldade (essenciais contra o viés de sobrevivência).
BDI_ACOES = {"02", "05", "06", "07", "08", "09"}
ESPECIES_ACOES = ("ON", "PN", "UNT")


def parse_line(line: str) -> dict | None:
    if len(line) < 245 or not line.startswith("01"):
        return None
    raw = {name: line[a - 1 : b] for name, a, b in FIELDS}
    if raw["tpmerc"] != MERCADO_VISTA or raw["codbdi"] not in BDI_ACOES:
        return None
    especi = raw["especi"].strip()
    if not especi.startswith(ESPECIES_ACOES):
        return None
    fatcot = int(raw["fatcot"]) or 1
    price = lambda field: int(raw[field]) / 100 / fatcot  # noqa: E731
    return {
        "date": pd.Timestamp(raw["date"]).date(),
        "ticker": raw["codneg"].strip(),
        "isin": raw["codisi"].strip(),
        "name": raw["nomres"].strip(),
        "especi": especi,
        "codbdi": raw["codbdi"],
        "open": price("preabe"),
        "high": price("premax"),
        "low": price("premin"),
        "close": price("preult"),
        "trades": int(raw["totneg"]),
        "volume": int(raw["quatot"]),
        "fin_volume": int(raw["voltot"]) / 100,
    }


def parse_text(text: str) -> pd.DataFrame:
    rows = [r for r in (parse_line(line) for line in text.splitlines()) if r is not None]
    return pd.DataFrame(rows)


def download(year: int, force: bool = False) -> Path:
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    target = CACHE_DIR / f"COTAHIST_A{year}.ZIP"
    if target.exists() and not force:
        return target
    url = URL.format(year=year)
    request = urllib.request.Request(url, headers={"User-Agent": "FinanceTracker/0.1"})  # noqa: S310
    with urllib.request.urlopen(request, timeout=300) as response:  # noqa: S310
        data = response.read()
    if not data.startswith(b"PK"):
        raise ValueError(f"{url} não retornou um ZIP")
    target.write_bytes(data)
    logger.info("baixado %s (%.1f MB)", target.name, len(data) / 1e6)
    return target


def load_year(year: int, force_download: bool = False) -> pd.DataFrame:
    parsed = CACHE_DIR / f"acoes_{year}.pkl"
    if parsed.exists() and not force_download:
        return pd.read_pickle(parsed)  # noqa: S301 — cache local gerado por este módulo
    with zipfile.ZipFile(download(year, force=force_download)) as zf:
        [name] = zf.namelist()
        text = io.TextIOWrapper(zf.open(name), encoding="latin-1").read()
    frame = parse_text(text)
    frame.to_pickle(parsed)
    return frame


def load_years(first: int, last: int) -> pd.DataFrame:
    return pd.concat([load_year(y) for y in range(first, last + 1)], ignore_index=True)
