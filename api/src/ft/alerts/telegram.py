"""Alertas no Telegram (Bot API, texto simples, sem dados sensíveis).

Token e chat id vêm de variáveis de ambiente (Secret Manager no Cloud Run). Falha no envio é
registrada no log e nunca derruba o pipeline.
"""

import json
import logging
import urllib.parse
import urllib.request

from ft.config import Settings

logger = logging.getLogger("ft.alerts")
MAX_LEN = 3800  # limite do Telegram é 4096 caracteres


def send(settings: Settings, text: str) -> bool:
    token = settings.telegram_bot_token.get_secret_value()
    chat = settings.telegram_chat_id
    if not token or not chat:
        logger.info("Telegram não configurado; alerta não enviado")
        return False
    if len(text) > MAX_LEN:
        text = text[: MAX_LEN - 20] + "\n… (mensagem cortada)"
    data = urllib.parse.urlencode({"chat_id": chat, "text": text}).encode()
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    try:
        request = urllib.request.Request(url, data=data)  # noqa: S310 — URL fixa da API
        with urllib.request.urlopen(request, timeout=20) as response:  # noqa: S310
            return bool(json.load(response).get("ok"))
    except Exception as exc:  # noqa: BLE001
        # Não logar a URL: contém o token.
        logger.warning("falha ao enviar alerta no Telegram: %s", type(exc).__name__)
        return False


ORDER_LABEL = {
    "open": "compra na abertura",
    "close": "compra no fechamento",
    "stop": "stop de compra",
}


def daily_summary(stats: dict, signals: list[dict], env: str) -> str:
    update = stats.get("update", {})
    lines = [f"FinanceTracker ({env}) — coleta diária concluída"]
    lines.append(f"Ativos atualizados: {update.get('assets', 0)}")
    if stats.get("cdi", {}).get("error"):
        lines.append("Atenção: CDI não atualizado hoje (fonte do Banco Central indisponível).")
    missing = stats.get("quality", {}).get("missing_sessions") or {}
    if missing:
        lines.append(f"Pregões faltando na fonte: {', '.join(sorted(missing))}")
    errors = update.get("errors") or {}
    if errors:
        lines.append(f"Ativos com erro: {', '.join(sorted(errors))}")
    if not signals:
        lines.append("Sinais: nenhum (nenhuma estratégia aprovada ou em observação gerou sinal).")
    else:
        lines.append(f"Sinais: {len(signals)}")
        for s in signals:
            tag = "OBSERVAÇÃO (só simulado)" if s["status"] == "observation" else "APROVADO"
            level = f" acima de {s['entry_level']:.2f}" if s.get("entry_level") else ""
            lines.append(
                f"• {s['ticker']} — {s['setup']} [{tag}] {ORDER_LABEL.get(s['order_kind'], '')}"
                f"{level} (ref. {s['ref_price']:.2f})"
            )
    lines.append("Ferramenta de análise; não é recomendação de investimento.")
    return "\n".join(lines)


def failure_message(env: str, error: str) -> str:
    return f"FinanceTracker ({env}) — FALHA na coleta diária.\n{error[:500]}"
