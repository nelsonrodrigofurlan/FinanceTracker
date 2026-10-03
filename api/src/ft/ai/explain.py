"""Explicação de sinais por IA (OpenRouter, API compatível com OpenAI).

Regras (CLAUDE.md, inegociável nº 4): a IA EXPLICA números já calculados; nunca cria nem altera
entrada, stop ou alvo; não faz recomendação de investimento. O contexto enviado tem só dados de
mercado públicos e métricas do laboratório — nenhum dado pessoal.

Formato da resposta verificado em 2026-10-02: `model` traz o modelo efetivo (o apelido
~anthropic/claude-sonnet-latest resolveu para anthropic/claude-sonnet-5.5) e `usage.cost` o
custo em USD quando a requisição envia {"usage": {"include": true}}.
"""

import hashlib
import json
import logging
import urllib.request

import pandas as pd

from ft.config import Settings
from ft.indicators import core as ind

logger = logging.getLogger("ft.ai")

SYSTEM_PROMPT = """Você é um analista técnico experiente escrevendo para um investidor pessoa física
no Brasil. Explique o sinal abaixo em português claro, objetivo e sem jargão desnecessário.

Regras obrigatórias:
- Use SOMENTE os números fornecidos. Não invente preços, notícias, fundamentos ou eventos.
- NUNCA proponha, altere ou arredonde entrada, stop, alvo ou quantidade. Cite-os como estão.
- Não faça recomendação de compra ou venda e não diga o que a pessoa "deve" fazer.
- Se o status for "observation", diga explicitamente que a estratégia está apenas em
  observação (modo simulado) e não passou em todos os critérios do laboratório.
- Seja honesto sobre a evidência: se a vantagem histórica for pequena ou negativa, diga.

Estrutura (títulos curtos, no máximo ~220 palavras no total):
1. O que o setup identificou
2. Contexto do ativo (tendência, posição em relação às médias, volatilidade, mercado)
3. Evidência histórica da estratégia (laboratório)
4. O que invalidaria o sinal
Termine com: "Ferramenta de análise; não é recomendação de investimento."
"""


def market_context(candles: pd.DataFrame, ibov_above_sma200: bool | None) -> dict:
    """Indicadores do último pregão a partir de candles (date, open, high, low, close, volume)."""
    c = candles["close"].astype("float64")
    last = float(c.iloc[-1])
    sma200 = ind.sma(c, 200).iloc[-1]
    ema21 = ind.ema(c, 21).iloc[-1]
    rsi14 = ind.rsi(c, 14).iloc[-1]
    atr14 = ind.atr(candles["high"], candles["low"], c, 14).iloc[-1]
    vol = candles["volume"].astype("float64")

    def pct(a: float, b: float) -> float | None:
        return round((a / b - 1) * 100, 2) if pd.notna(b) and b else None

    return {
        "ultimo_fechamento": round(last, 2),
        "retorno_20_pregoes_pct": pct(last, c.iloc[-21]) if len(c) > 21 else None,
        "retorno_60_pregoes_pct": pct(last, c.iloc[-61]) if len(c) > 61 else None,
        "distancia_mma200_pct": pct(last, sma200),
        "distancia_mme21_pct": pct(last, ema21),
        "ifr14": round(float(rsi14), 1) if pd.notna(rsi14) else None,
        "atr14_pct_do_preco": round(float(atr14) / last * 100, 2) if pd.notna(atr14) else None,
        "volume_vs_media_20": round(float(vol.iloc[-1] / vol.iloc[-21:-1].mean()), 2)
        if len(vol) > 21 and vol.iloc[-21:-1].mean() > 0
        else None,
        "ibovespa_acima_mma200": ibov_above_sma200,
    }


def build_messages(context: dict) -> list[dict]:
    payload = json.dumps(context, ensure_ascii=False, default=str, indent=1)
    return [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": f"Dados do sinal (JSON):\n{payload}"},
    ]


def context_hash(context: dict) -> str:
    raw = json.dumps(context, sort_keys=True, ensure_ascii=False, default=str)
    return hashlib.sha256(raw.encode()).hexdigest()


def call_model(settings: Settings, messages: list[dict], max_tokens: int = 1200) -> dict:
    key = settings.openrouter_api_key.get_secret_value()
    if not key or not settings.ai_model:
        raise RuntimeError("OpenRouter não configurado (OPENROUTER_API_KEY / AI_MODEL)")
    body = {
        "model": settings.ai_model,
        "messages": messages,
        "max_tokens": max_tokens,
        "temperature": 0.2,
        "usage": {"include": True},
    }
    url = settings.openrouter_base_url.rstrip("/") + "/chat/completions"
    if not url.startswith("https://"):
        raise RuntimeError("OPENROUTER_BASE_URL precisa ser https")
    request = urllib.request.Request(  # noqa: S310 — URL https validada acima
        url,
        data=json.dumps(body).encode(),
        headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
    )
    with urllib.request.urlopen(request, timeout=90) as response:  # noqa: S310
        data = json.load(response)
    usage = data.get("usage") or {}
    return {
        "model": data.get("model") or settings.ai_model,
        "content": data["choices"][0]["message"]["content"].strip(),
        "usage": {
            "prompt_tokens": usage.get("prompt_tokens"),
            "completion_tokens": usage.get("completion_tokens"),
            "cost_usd": usage.get("cost"),
        },
    }
