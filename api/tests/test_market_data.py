from datetime import date, datetime

import pandas as pd
import pytest

from ft.config import Settings
from ft.data.market_time import B3_TZ, last_complete_date
from ft.data.quality import clean_candles
from ft.data.yahoo import DailyHistory, normalize
from ft.db.connection import DatabaseConfigError, assert_db_matches_project
from ft.pipeline import has_new_events
from ft.universe.b3 import parse_portfolio
from ft.universe.selection import LiquidityCriteria, average_fin_volume, select_liquid


def candles(rows: list[tuple]) -> pd.DataFrame:
    df = pd.DataFrame(rows, columns=["date", "open", "high", "low", "close", "adj_close", "volume"])
    return df.set_index("date")


# --- horário de corte do candle diário ---------------------------------------------------


def test_before_cutoff_uses_previous_day():
    now = datetime(2026, 10, 1, 15, 0, tzinfo=B3_TZ)
    assert last_complete_date(now) == date(2026, 9, 30)


def test_after_cutoff_uses_today():
    now = datetime(2026, 10, 1, 18, 30, tzinfo=B3_TZ)
    assert last_complete_date(now) == date(2026, 10, 1)


# --- qualidade -----------------------------------------------------------------------------


def test_clean_keeps_valid_rows():
    df = candles([(date(2026, 9, 1), 10, 11, 9, 10.5, 10.4, 1000)])
    out, report = clean_candles(df)
    assert len(out) == 1
    assert report.total_dropped == 0


@pytest.mark.parametrize(
    "row,reason",
    [
        ((date(2026, 9, 1), 10, 9, 11, 10, 10, 1000), "maxima_menor_que_minima"),
        ((date(2026, 9, 1), 10, 10.2, 9, 10.5, 10.5, 1000), "maxima_inconsistente"),
        ((date(2026, 9, 1), 10, 11, 10.2, 10.1, 10.1, 1000), "minima_inconsistente"),
        ((date(2026, 9, 1), 0, 11, 9, 10, 10, 1000), "preco_nao_positivo"),
        ((date(2026, 9, 1), 10, 11, 9, float("nan"), 10, 1000), "valor_ausente"),
        ((date(2026, 9, 1), 10, 11, 9, 10, 10, -5), "volume_negativo"),
    ],
)
def test_clean_drops_invalid_rows(row, reason):
    out, report = clean_candles(candles([row]))
    assert out.empty
    assert report.dropped == {reason: 1}


# --- normalização do Yahoo ----------------------------------------------------------------


def yahoo_frame() -> pd.DataFrame:
    idx = pd.DatetimeIndex(
        [datetime(2026, 9, 29), datetime(2026, 9, 30), datetime(2026, 10, 1)], tz=B3_TZ
    )
    return pd.DataFrame(
        {
            "Open": [10.0, 10.5, 11.0],
            "High": [11.0, 11.0, 11.5],
            "Low": [9.5, 10.0, 10.8],
            "Close": [10.5, 10.8, 11.2],
            "Adj Close": [10.4, 10.7, 11.2],
            "Volume": [1000, 2000, 300],
            "Dividends": [0.0, 0.25, 0.0],
            "Stock Splits": [0.0, 0.0, 0.0],
        },
        index=idx,
    )


def test_normalize_drops_partial_candle_and_extracts_events():
    history = normalize(yahoo_frame(), up_to=date(2026, 9, 30))
    assert list(history.candles.index) == [date(2026, 9, 29), date(2026, 9, 30)]
    assert list(history.candles.columns) == [
        "open",
        "high",
        "low",
        "close",
        "adj_close",
        "volume",
    ]
    assert history.dividends.to_dict() == {date(2026, 9, 30): 0.25}
    assert history.splits.empty


def test_normalize_rejects_unexpected_format():
    with pytest.raises(ValueError, match="colunas esperadas"):
        normalize(yahoo_frame().drop(columns=["Adj Close"]), up_to=date(2026, 10, 1))


# --- eventos corporativos ---------------------------------------------------------------


def history_with(dividends: dict, splits: dict | None = None) -> DailyHistory:
    return DailyHistory(
        candles=pd.DataFrame(),
        dividends=pd.Series(dividends, dtype="float64"),
        splits=pd.Series(splits or {}, dtype="float64"),
    )


def test_new_dividend_requires_full_reload():
    known = {(date(2026, 4, 23), "dividend")}
    fetched = history_with({date(2026, 4, 23): 0.66, date(2026, 9, 30): 0.7})
    assert has_new_events(fetched, known) is True


def test_known_events_do_not_trigger_reload():
    known = {(date(2026, 4, 23), "dividend")}
    assert has_new_events(history_with({date(2026, 4, 23): 0.66}), known) is False


def test_new_split_requires_full_reload():
    assert has_new_events(history_with({}, {date(2026, 9, 1): 2.0}), set()) is True


# --- universo -----------------------------------------------------------------------------


def test_parse_portfolio_filters_and_sorts():
    results = [{"cod": f"TK{chr(65 + i // 26)}{chr(65 + i % 26)}3"} for i in range(60)]
    results += [{"cod": "invalido"}, {"cod": " petr4 ", "asset": "PETROBRAS  "}]
    results += [{"cod": "B3SA3"}, {"cod": "KLBN11"}]
    names = parse_portfolio({"results": results})
    tickers = list(names)
    assert "PETR4" in tickers
    assert "B3SA3" in tickers  # raiz com dígito
    assert "KLBN11" in tickers  # unit
    assert "INVALIDO" not in tickers
    assert tickers == sorted(tickers)
    assert names["PETR4"] == "PETROBRAS"
    assert names["B3SA3"] is None


def test_parse_portfolio_rejects_suspicious_composition():
    with pytest.raises(ValueError, match="suspeita"):
        parse_portfolio({"results": [{"cod": "PETR4"}]})


def test_average_requires_full_window():
    series = pd.Series([1.0] * 10)
    assert average_fin_volume(series, window=21) is None


def test_select_liquid_applies_threshold():
    criteria = LiquidityCriteria(min_avg_fin_volume=30e6, window=3)
    selected, averages = select_liquid(
        {
            "LIQD3": pd.Series([40e6, 35e6, 30e6]),
            "ILIQ3": pd.Series([5e6, 6e6, 7e6]),
            "NOVA3": pd.Series([90e6]),  # histórico curto demais
        },
        criteria,
    )
    assert selected == ["LIQD3"]
    assert averages["NOVA3"] is None


# --- trava do banco -----------------------------------------------------------------------


def settings(**kw) -> Settings:
    return Settings(_env_file=None, **kw)


def test_db_guard_accepts_matching_project():
    assert_db_matches_project(
        settings(
            supabase_project_ref="abcdefghijklmnopqrst",
            supabase_db_url="postgresql://postgres:x@db.abcdefghijklmnopqrst.supabase.co:5432/postgres",
        )
    )


def test_db_guard_rejects_other_project():
    with pytest.raises(DatabaseConfigError, match="não pertence"):
        assert_db_matches_project(
            settings(
                supabase_project_ref="abcdefghijklmnopqrst",
                supabase_db_url="postgresql://postgres:x@db.zzzzzzzzzzzzzzzzzzzz.supabase.co:5432/postgres",
            )
        )


def test_db_guard_rejects_missing_url():
    with pytest.raises(DatabaseConfigError):
        assert_db_matches_project(settings(supabase_project_ref="abc"))
