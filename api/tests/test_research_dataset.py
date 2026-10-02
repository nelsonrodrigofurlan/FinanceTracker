from datetime import date

import pandas as pd
import pytest

from ft.research.dataset import classify_jump, eligibility, resolve_jumps


def test_split_requires_price_and_volume_agreement():
    assert classify_jump(0.5, 1000, 2000) == ("split", 2)  # 1:2 com volume dobrando
    assert classify_jump(0.25, 1000, 3900) == ("split", 4)
    assert classify_jump(10.0, 1000, 100) == ("split", 0.1)  # grupamento 10:1


def test_ambiguous_drop_is_kept_as_real_loss():
    # Americanas 11/01/2023: −77% (perto de 1/4) mas fora da tolerância de 5%
    assert classify_jump(0.2333, 1000, 3860) == ("real", None)
    # razão perfeita de 1:2 mas sem mudança de volume → queda real
    assert classify_jump(0.5, 1000, 1000) == ("real", None)


def test_ambiguous_rise_is_neutralized():
    assert classify_jump(2.07, 1000, 17000) == ("neutralize", None)


def test_resolve_jumps_neutralizes_unexplained_gain():
    idx = [date(2020, 1, d) for d in range(1, 5)]
    s = pd.DataFrame(
        {
            "open": [10, 10, 25, 25.0],
            "high": [10, 10, 26, 26.0],
            "low": [10, 10, 24, 24.0],
            "close": [10, 10, 25, 25.0],
            "volume": [100, 100, 5000, 5000.0],
        },
        index=idx,
    )
    out, counts = resolve_jumps(s)
    assert counts["neutralize"] == 1
    # o ganho de +150% de 2 → 3 desaparece: fechamento anterior escalado para 25
    assert out.loc[idx[1], "close"] == pytest.approx(25.0)
    assert out.loc[idx[2], "close"] == pytest.approx(25.0)


def test_eligibility_uses_previous_month_end_only():
    members = {date(2020, 1, 31): ["A"], date(2020, 2, 28): []}
    days = [date(2020, 1, 31), date(2020, 2, 3), date(2020, 2, 28), date(2020, 3, 2)]
    assert eligibility(days, "A", members).tolist() == [False, True, True, False]
