"""Métricas de backtest em R (múltiplos do risco inicial) e critérios de aprovação."""

from dataclasses import dataclass
from datetime import date

import numpy as np

from ft.backtest.engine import Trade


def compute(trades: list[Trade]) -> dict:
    n = len(trades)
    if n == 0:
        return {"trades": 0}
    r = np.array([t.r_multiple for t in trades])
    wins, losses = r[r > 0], r[r <= 0]
    gross_win, gross_loss = wins.sum(), -losses.sum()

    ordered = sorted(trades, key=lambda t: (t.exit_date, t.ticker))
    curve = np.cumsum([t.r_multiple for t in ordered])
    peak = np.maximum.accumulate(np.concatenate(([0.0], curve)))[1:]
    max_dd = float((peak - curve).max())

    streak = longest = 0
    for value in (t.r_multiple for t in ordered):
        streak = streak + 1 if value <= 0 else 0
        longest = max(longest, streak)

    avg_win = float(wins.mean()) if len(wins) else 0.0
    avg_loss = float(-losses.mean()) if len(losses) else 0.0
    return {
        "trades": n,
        "win_rate": round(len(wins) / n * 100, 2),
        "avg_win_r": round(avg_win, 4),
        "avg_loss_r": round(avg_loss, 4),
        "payoff": round(avg_win / avg_loss, 4) if avg_loss else None,
        "expectancy_r": round(float(r.mean()), 4),
        "profit_factor": round(float(gross_win / gross_loss), 4) if gross_loss else None,
        "total_r": round(float(r.sum()), 2),
        "max_drawdown_r": round(max_dd, 2),
        "max_consecutive_losses": longest,
        "avg_bars": round(float(np.mean([t.bars for t in trades])), 2),
        "avg_return_pct": round(float(np.mean([t.return_pct for t in trades])), 4),
    }


@dataclass(frozen=True)
class ApprovalCriteria:
    min_oos_trades: int = 30
    min_oos_expectancy_r: float = 0.0
    min_oos_profit_factor: float = 1.3
    max_degradation: float = 0.5  # expectativa fora da amostra >= 50% da de dentro

    def as_dict(self) -> dict:
        return {
            "min_oos_trades": self.min_oos_trades,
            "min_oos_expectancy_r": self.min_oos_expectancy_r,
            "min_oos_profit_factor": self.min_oos_profit_factor,
            "max_degradation": self.max_degradation,
        }


def evaluate(trades: list[Trade], split: date, criteria: ApprovalCriteria) -> tuple[dict, dict]:
    ins = [t for t in trades if t.entry_date < split]
    outs = [t for t in trades if t.entry_date >= split]
    metrics = {"all": compute(trades), "in_sample": compute(ins), "out_of_sample": compute(outs)}

    m_in, m_out = metrics["in_sample"], metrics["out_of_sample"]
    exp_in = m_in.get("expectancy_r")
    exp_out = m_out.get("expectancy_r")
    pf_out = m_out.get("profit_factor")
    checks = {
        "oos_trades": m_out.get("trades", 0) >= criteria.min_oos_trades,
        "oos_expectancy": exp_out is not None and exp_out > criteria.min_oos_expectancy_r,
        "oos_profit_factor": pf_out is not None and pf_out >= criteria.min_oos_profit_factor,
        "no_severe_degradation": (
            exp_out is not None
            and exp_in is not None
            and (exp_in <= 0 or exp_out >= criteria.max_degradation * exp_in)
        ),
    }
    approval = {"criteria": criteria.as_dict(), "checks": checks, "approved": all(checks.values())}
    return metrics, approval
