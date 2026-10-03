from datetime import date, datetime, time
from zoneinfo import ZoneInfo

B3_TZ = ZoneInfo("America/Sao_Paulo")

# Depois deste horário o candle do dia é considerado fechado (pregão regular + call de fechamento).
DAILY_CANDLE_FINAL_AFTER = time(18, 30)


def now_b3() -> datetime:
    return datetime.now(B3_TZ)


def last_complete_date(now: datetime | None = None) -> date:
    """Último dia cujo candle diário pode ser considerado fechado.

    Antes de 18h30 (horário de Brasília) o candle de hoje ainda pode ser parcial.
    Não sabe de feriados: se hoje não houve pregão, simplesmente não haverá candle de hoje.
    """
    now = (now or now_b3()).astimezone(B3_TZ)
    if now.time() >= DAILY_CANDLE_FINAL_AFTER:
        return now.date()
    return date.fromordinal(now.date().toordinal() - 1)
