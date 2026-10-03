from datetime import date, timedelta

import numpy as np
import pandas as pd

from ft.research.universe import UniverseRule, daily_fin_volume, monthly_members


def days(n: int) -> list[date]:
    out, d = [], date(2020, 1, 1)
    while len(out) < n:
        if d.weekday() < 5:
            out.append(d)
        d += timedelta(days=1)
    return out


def test_daily_fin_volume_sums_tickers_of_same_isin():
    raw = pd.DataFrame(
        {
            "date": [date(2020, 1, 2)] * 3,
            "isin": ["X", "X", "Y"],
            "fin_volume": [10.0, 5.0, 7.0],
        }
    )
    out = daily_fin_volume(raw)
    assert out.loc[date(2020, 1, 2), "X"] == 15.0


def test_members_use_only_past_data_and_min_days():
    dates = days(45)  # janeiro + fevereiro
    vol = pd.DataFrame(index=dates, columns=["BIG", "SMALL", "RARE", "LATE"], dtype="float64")
    vol["BIG"] = 100.0
    vol["SMALL"] = 10.0
    vol.loc[dates[::5], "RARE"] = 1000.0  # muito volume, mas negocia pouco
    vol.loc[dates[30] :, "LATE"] = 1000.0  # só começa a negociar em fevereiro
    members = monthly_members(vol, UniverseRule(top_n=2, window=10, min_days=8))
    jan_end = max(d for d in dates if d.month == 1)
    assert members[jan_end] == ["BIG", "SMALL"]  # RARE excluída (poucos dias), LATE ainda sem dados
    last = dates[-1]
    assert members[last][0] == "LATE"  # em fevereiro LATE já é a mais líquida


def test_missing_days_count_as_zero_volume():
    dates = days(10)
    vol = pd.DataFrame({"A": [100.0] * 10, "B": [150.0] * 9 + [np.nan]}, index=dates)
    members = monthly_members(vol, UniverseRule(top_n=1, window=10, min_days=9))
    # B: média (9×150 + 0)/10 = 135 > 100
    assert members[dates[-1]] == ["B"]
