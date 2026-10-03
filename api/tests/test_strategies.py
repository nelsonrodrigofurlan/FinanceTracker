import pytest

from ft.backtest.setups import Donchian, from_params, variants
from ft.signals.strategies import classify


@pytest.mark.parametrize(
    "approved,wf,cagr,cdi,expected",
    [
        (True, -0.5, 1.0, 10.0, "approved"),  # critério formal manda
        (False, 0.40, 15.1, 10.4, "observation"),  # WF positivo e bate o CDI
        (False, 0.40, 8.9, 10.4, "rejected"),  # WF positivo mas perde do CDI
        (False, -0.01, 15.0, 10.4, "rejected"),  # bate o CDI mas WF negativo
        (False, None, 15.0, 10.4, "rejected"),  # sem walk-forward
        (False, 0.40, 15.0, None, "rejected"),  # sem CDI para comparar
    ],
)
def test_classify(approved, wf, cagr, cdi, expected):
    assert classify(approved, wf, cagr, cdi) == expected


def test_from_params_roundtrip_for_all_variants():
    for setup in variants():
        rebuilt = from_params(setup.code, setup.params)
        assert rebuilt == setup


def test_from_params_rejects_mismatched_code():
    with pytest.raises(ValueError):
        from_params("S1", Donchian().params)
