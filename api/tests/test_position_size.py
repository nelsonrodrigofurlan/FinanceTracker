from ft.settings_api import UserSettings
from ft.signals_api import position_size

FULL = UserSettings(sim_capital=10_000, risk_pct=1, max_positions=5, max_position_pct=20)


def test_size_by_risk_and_cap():
    assert position_size(10.0, 1.0, FULL) == 100  # R$100 de risco / R$1 por ação
    assert position_size(10.0, 0.1, FULL) == 200  # risco daria 1000; teto de 20% = R$2.000


def test_no_size_without_complete_settings():
    assert position_size(10.0, 1.0, UserSettings(sim_capital=10_000)) is None


def test_no_size_with_invalid_inputs():
    assert position_size(None, 1.0, FULL) is None
    assert position_size(10.0, 0.0, FULL) is None
