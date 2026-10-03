"""Validação walk-forward e estabilidade anual.

Walk-forward: para cada ano Y, escolhe a variante com maior expectativa nos `lookback` anos
anteriores (com pelo menos `min_trades` trades nessa janela) e registra o resultado dela no
ano Y. O ano Y nunca participa da escolha → mede a vantagem como seria operada de verdade,
incluindo o viés de escolher parâmetros.
"""

from dataclasses import dataclass

# per_year[variant][year] = (n_trades, soma_R)
PerYear = dict[str, dict[int, tuple[int, float]]]


@dataclass(frozen=True)
class WalkForwardParams:
    lookback: int = 5
    min_trades: int = 30


def _window(per_variant: dict[int, tuple[int, float]], years: range) -> tuple[int, float]:
    n = sum(per_variant.get(y, (0, 0.0))[0] for y in years)
    s = sum(per_variant.get(y, (0, 0.0))[1] for y in years)
    return n, s


DEFAULT_PARAMS = WalkForwardParams()


def walk_forward(per_year: PerYear, p: WalkForwardParams = DEFAULT_PARAMS) -> dict:
    all_years = sorted({y for v in per_year.values() for y in v})
    if not all_years:
        return {"params": p.__dict__, "years": [], "trades": 0, "expectancy_r": None}

    rows = []
    for year in range(all_years[0] + p.lookback, all_years[-1] + 1):
        window = range(year - p.lookback, year)
        candidates = []
        for variant, data in per_year.items():
            n, s = _window(data, window)
            if n >= p.min_trades:
                candidates.append((s / n, variant))
        if not candidates:
            continue
        best_e, best = max(candidates)
        n_y, s_y = per_year[best].get(year, (0, 0.0))
        rows.append(
            {
                "year": year,
                "chosen_variant": best,
                "lookback_expectancy_r": round(best_e, 4),
                "trades": n_y,
                "total_r": round(s_y, 2),
                "expectancy_r": round(s_y / n_y, 4) if n_y else None,
                # Se o melhor do passado já era negativo, um operador racional não operaria.
                "would_trade": best_e > 0,
            }
        )

    traded = [r for r in rows if r["would_trade"]]
    n = sum(r["trades"] for r in traded)
    total = sum(r["total_r"] for r in traded)
    positive_years = sum(1 for r in traded if r["total_r"] > 0)
    return {
        "params": p.__dict__,
        "years": rows,
        "trades": n,
        "total_r": round(total, 2),
        "expectancy_r": round(total / n, 4) if n else None,
        "years_traded": len(traded),
        "years_positive": positive_years,
    }


def yearly_stability(per_year_one: dict[int, tuple[int, float]]) -> list[dict]:
    return [
        {
            "year": y,
            "trades": n,
            "total_r": round(s, 2),
            "expectancy_r": round(s / n, 4) if n else None,
        }
        for y, (n, s) in sorted(per_year_one.items())
    ]
