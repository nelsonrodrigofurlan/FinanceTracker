from datetime import date, timedelta

import pytest
from pydantic import ValidationError

from ft.journal_api import JournalCloseIn, JournalEntryIn, JournalTrade, compute, summarize


def entry(**kw):
    base = {
        "ticker": "petr4",
        "entry_date": date(2026, 9, 1),
        "entry_price": 10.0,
        "quantity": 100,
        "stop_planned": 9.0,
    }
    base.update(kw)
    return JournalEntryIn(**base)


def test_entry_normalizes_ticker_and_accepts_fractional():
    assert entry().ticker == "PETR4"
    assert entry(ticker="PETR4F").ticker == "PETR4F"


@pytest.mark.parametrize(
    "kw",
    [
        {"ticker": "PETROBRAS"},
        {"stop_planned": 10.5},  # stop acima da entrada (long-only)
        {"target_planned": 9.5},  # alvo abaixo da entrada
        {"quantity": 0},
        {"entry_price": -1},
        {"entry_date": date.today() + timedelta(days=30)},  # futuro
        {"emotion": "raiva"},
    ],
)
def test_entry_validation(kw):
    with pytest.raises(ValidationError):
        entry(**kw)


def test_close_rejects_future_date():
    with pytest.raises(ValidationError):
        JournalCloseIn(exit_date=date.today() + timedelta(days=30), exit_price=11)


def row(**kw):
    base = {
        "entry_price": 10.0,
        "quantity": 100,
        "stop_planned": 9.0,
        "entry_fees": 1.0,
        "exit_price": None,
        "exit_fees": 0.0,
        "entry_date": date(2026, 9, 1),
        "exit_date": None,
    }
    base.update(kw)
    return base


def test_compute_open_trade():
    out = compute(row())
    assert out["status"] == "open" and out["pnl"] is None
    assert out["planned_risk"] == 100.0  # (10 − 9) × 100


def test_compute_closed_trade_with_fees_and_r():
    out = compute(row(exit_price=12.0, exit_fees=1.0, exit_date=date(2026, 9, 11)))
    # 1200 − 1 − (1000 + 1) = 198 → 1,98R ; 198/1001 = 19,78%
    assert out["pnl"] == pytest.approx(198.0)
    assert out["r_multiple"] == pytest.approx(1.98)
    assert out["return_pct"] == pytest.approx(19.78)
    assert out["holding_days"] == 10


def test_compute_without_stop_has_no_r():
    out = compute(row(stop_planned=None, exit_price=9.0, exit_date=date(2026, 9, 2)))
    assert out["r_multiple"] is None and out["pnl"] < 0


def trade(pnl, r, stop=9.0, status="closed", strategy=None):
    return JournalTrade(
        id=1,
        ticker="PETR4",
        signal_id=None,
        strategy_status=strategy,
        entry_date=date(2026, 9, 1),
        entry_price=10,
        quantity=100,
        stop_planned=stop,
        target_planned=None,
        entry_fees=0,
        reason=None,
        emotion=None,
        exit_date=date(2026, 9, 2) if status == "closed" else None,
        exit_price=11 if status == "closed" else None,
        exit_fees=0,
        exit_notes=None,
        status=status,
        pnl=pnl,
        return_pct=None,
        r_multiple=r,
        planned_risk=100,
        holding_days=1,
    )


def test_summary_counts_discipline_and_non_approved():
    s = summarize(
        [
            trade(100, 1.0),
            trade(-50, -0.5, strategy="observation"),
            trade(None, None, stop=None, status="open"),
        ]
    )
    assert s.closed_count == 2 and s.open_count == 1
    assert s.win_rate == 50.0
    assert s.total_pnl == 50.0
    assert s.avg_r == 0.25
    assert s.with_stop_pct == pytest.approx(66.7)
    assert s.non_approved_count == 1
