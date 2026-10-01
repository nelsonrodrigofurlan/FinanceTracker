"""Composição do IBrX-100 a partir do endpoint que alimenta o site da B3.

Não é API oficial documentada: se falhar, o pipeline reutiliza o último snapshot salvo.
"""

import base64
import json
import re
import urllib.request

URL = "https://sistemaswebb3-listados.b3.com.br/indexProxy/indexCall/GetPortfolioDay/{payload}"
# Raiz de 4 caracteres começando por letra (pode conter dígito, ex.: B3SA3) + número.
TICKER_RE = re.compile(r"^[A-Z][A-Z0-9]{3}\d{1,2}$")


def build_url(index: str = "IBXX") -> str:
    payload = {
        "language": "pt-br",
        "pageNumber": 1,
        "pageSize": 200,
        "index": index,
        "segment": "1",
    }
    encoded = base64.b64encode(json.dumps(payload).encode()).decode()
    return URL.format(payload=encoded)


def parse_portfolio(data: dict) -> dict[str, str | None]:
    """Retorna {ticker: nome da empresa} em ordem alfabética de ticker."""
    names: dict[str, str | None] = {}
    for item in data.get("results", []):
        ticker = str(item.get("cod", "")).strip().upper()
        if TICKER_RE.match(ticker):
            name = " ".join(str(item.get("asset") or "").split()) or None
            names[ticker] = name
    if len(names) < 50:
        raise ValueError(f"Composição suspeita: só {len(names)} tickers válidos")
    return dict(sorted(names.items()))


def fetch_ibrx100(timeout: float = 20) -> dict[str, str | None]:
    url = build_url()
    if not url.startswith("https://"):
        raise ValueError("URL da B3 precisa ser https")
    request = urllib.request.Request(url, headers={"User-Agent": "FinanceTracker/0.1"})  # noqa: S310
    with urllib.request.urlopen(request, timeout=timeout) as response:  # noqa: S310
        return parse_portfolio(json.load(response))
