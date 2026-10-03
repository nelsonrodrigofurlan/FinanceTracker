from datetime import date

import pandas as pd
import pytest

from ft.research.adjust import ShareEvent, adjust_series, parse_events


def payload(label, factor, last="25/04/2008", isin="BRXXXXACNPR0"):
    return [
        {
            "stockDividends": [
                {"label": label, "factor": factor, "lastDatePrior": last, "isinCode": isin}
            ]
        }
    ]


@pytest.mark.parametrize(
    "label,factor,multiplier",
    [
        ("DESDOBRAMENTO", "100,00000000000", 2.0),
        ("DESDOBRAMENTO", "300,00000000000", 4.0),
        ("BONIFICACAO", "3,00000000000", 1.03),
        ("GRUPAMENTO", "0,10000000000", 0.1),
    ],
)
def test_parse_factor_semantics(label, factor, multiplier):
    [event] = parse_events(payload(label, factor))
    assert event.share_multiplier == pytest.approx(multiplier)
    assert event.last_date_prior == date(2008, 4, 25)


def test_ignores_other_events():
    assert parse_events(payload("CIS RED CAP", "100,0")) == []


def series(rows):
    idx = [date(2020, 1, d) for d in range(1, len(rows) + 1)]
    return pd.DataFrame(rows, columns=["open", "high", "low", "close", "volume"], index=idx)


def test_confirmed_split_adjusts_past_prices_and_volume():
    s = series([(20, 21, 19, 20, 100), (20, 20, 19, 20, 100), (10, 11, 9.8, 10.5, 200)])
    event = ShareEvent("X", "DESDOBRAMENTO", date(2020, 1, 2), 2.0)
    out, log = adjust_series(s, [event])
    assert log[0]["applied"] is True
    assert out.loc[date(2020, 1, 1), "close"] == pytest.approx(10.0)
    assert out.loc[date(2020, 1, 1), "volume"] == pytest.approx(200)
    assert out.loc[date(2020, 1, 3), "close"] == pytest.approx(10.5)  # após o evento: intacto


def test_event_not_reflected_in_price_is_skipped():
    s = series([(20, 21, 19, 20, 100), (20, 20, 19, 20, 100), (19.6, 20, 19, 19.8, 100)])
    event = ShareEvent("X", "GRUPAMENTO", date(2020, 1, 2), 0.01)  # teórico ×100
    out, log = adjust_series(s, [event])
    assert log[0]["applied"] is False
    pd.testing.assert_frame_equal(out, s.astype("float64"))  # preços intactos
