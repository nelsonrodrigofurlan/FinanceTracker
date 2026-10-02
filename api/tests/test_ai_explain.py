import numpy as np
import pandas as pd
import pytest

from ft.ai.explain import SYSTEM_PROMPT, build_messages, call_model, context_hash, market_context
from ft.config import Settings


def candles(n=260):
    close = np.linspace(10, 20, n)
    return pd.DataFrame(
        {
            "open": close,
            "high": close * 1.01,
            "low": close * 0.99,
            "close": close,
            "volume": np.full(n, 1000.0),
        }
    )


def test_market_context_fields():
    ctx = market_context(candles(), ibov_above_sma200=True)
    assert ctx["ultimo_fechamento"] == 20.0
    assert ctx["distancia_mma200_pct"] > 0  # tendência de alta
    assert ctx["volume_vs_media_20"] == pytest.approx(1.0)
    assert ctx["ibovespa_acima_mma200"] is True


def test_prompt_forbids_changing_levels_and_advice():
    assert "NUNCA proponha, altere" in SYSTEM_PROMPT
    assert "não é recomendação de investimento" in SYSTEM_PROMPT
    msgs = build_messages({"ativo": "PETR4"})
    assert msgs[0]["role"] == "system" and "PETR4" in msgs[1]["content"]


def test_context_hash_is_stable():
    assert context_hash({"a": 1, "b": 2}) == context_hash({"b": 2, "a": 1})


def test_call_model_requires_configuration():
    with pytest.raises(RuntimeError, match="não configurado"):
        call_model(Settings(_env_file=None), [])
