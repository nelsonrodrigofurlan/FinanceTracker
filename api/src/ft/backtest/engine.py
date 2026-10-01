"""Motor de backtest candle a candle, um ativo por vez, uma posição por vez (long-only).

Regras de execução (docs/ARQUITETURA.md §7.1):
- Sem olhar o futuro: o sinal usa dados até o candle t; execução em t (fechamento) ou depois.
- Ordem stop de compra: executa se máxima >= nível; preço = max(nível, abertura) (gap a favor
  não é "presente": paga-se a abertura).
- Stop de proteção: executa se mínima <= stop; preço = min(stop, abertura) (gap contra o stop
  sai na abertura).
- Alvo: executa se máxima >= alvo; preço = max(alvo, abertura).
- Stop e alvo no mesmo candle → assume o stop (conservador).
- No candle de entrada só o stop é verificado (não se credita alvo atingido no mesmo candle).
- Custos: slippage piora entrada e saída; taxas incidem sobre o valor de compra e de venda.
"""

from dataclasses import dataclass, field
from datetime import date
from typing import Literal, Protocol

import numpy as np

TICK = 0.01
ENGINE_VERSION = "1.0.0"


@dataclass(frozen=True)
class Costs:
    fee_pct_per_side: float = 0.000274  # B3: negociação 0,00500% + CCP 0,02240%
    slippage_pct_per_side: float = 0.001
    brokerage_per_order: float = 0.0  # Clear: corretagem zero (valor fixo por ordem não modelado)

    def as_dict(self) -> dict:
        return {
            "fee_pct_per_side": self.fee_pct_per_side,
            "slippage_pct_per_side": self.slippage_pct_per_side,
            "brokerage_per_order": self.brokerage_per_order,
        }


@dataclass
class Bars:
    """Arrays de um ativo (preços ajustados), na ordem cronológica."""

    ticker: str
    dates: list[date]
    open: np.ndarray
    high: np.ndarray
    low: np.ndarray
    close: np.ndarray
    volume: np.ndarray

    def __len__(self) -> int:
        return len(self.dates)


@dataclass
class Order:
    """Ordem de entrada pendente.

    kind:
      - "close": compra no fechamento do candle de sinal (executa na hora).
      - "open":  compra na abertura do próximo candle.
      - "stop":  compra se o preço atingir `level` até o candle `expires` (inclusive).
    O stop de proteção é absoluto (`stop`) ou relativo ao preço executado (`stop_distance`).
    `risk_distance` define a unidade R quando o setup opera sem stop de preço.
    """

    kind: Literal["close", "open", "stop"]
    level: float | None = None
    expires: int | None = None
    stop: float | None = None
    stop_distance: float | None = None
    risk_distance: float | None = None
    target_r: float | None = None
    meta: dict = field(default_factory=dict)


@dataclass
class Position:
    entry_idx: int
    entry_price: float
    stop: float  # stop ativo (pode subir); -inf = sem stop de preço
    initial_stop: float  # define 1R
    target: float | None
    meta: dict = field(default_factory=dict)


@dataclass
class Exit:
    kind: Literal["close", "next_open"]
    reason: str


@dataclass(frozen=True)
class Trade:
    ticker: str
    entry_date: date
    entry_price: float
    exit_date: date
    exit_price: float
    initial_stop: float
    target: float | None
    r_multiple: float
    return_pct: float
    bars: int
    exit_reason: str


class Setup(Protocol):
    code: str

    def prepare(self, bars: Bars) -> dict[str, np.ndarray]: ...

    def signal(self, t: int, bars: Bars, ind: dict[str, np.ndarray]) -> Order | None: ...

    def update_pending(
        self, t: int, order: Order, bars: Bars, ind: dict[str, np.ndarray]
    ) -> Order | None: ...

    def manage(
        self, t: int, pos: Position, bars: Bars, ind: dict[str, np.ndarray]
    ) -> Exit | None: ...


def _finalize(
    bars: Bars, pos: Position, exit_idx: int, raw_exit: float, reason: str, costs: Costs
) -> Trade:
    entry_eff = pos.entry_price * (1 + costs.slippage_pct_per_side)
    exit_eff = raw_exit * (1 - costs.slippage_pct_per_side)
    fees = (entry_eff + exit_eff) * costs.fee_pct_per_side
    pnl = exit_eff - entry_eff - fees
    risk = pos.entry_price - pos.initial_stop
    return Trade(
        ticker=bars.ticker,
        entry_date=bars.dates[pos.entry_idx],
        entry_price=round(pos.entry_price, 4),
        exit_date=bars.dates[exit_idx],
        exit_price=round(raw_exit, 4),
        initial_stop=round(pos.initial_stop, 4),
        target=round(pos.target, 4) if pos.target is not None else None,
        r_multiple=round(pnl / risk, 4),
        return_pct=round(pnl / entry_eff * 100, 4),
        bars=exit_idx - pos.entry_idx,
        exit_reason=reason,
    )


def _open_position(order: Order, t: int, fill: float) -> Position | None:
    if order.stop is not None:
        stop = order.stop
    elif order.stop_distance is not None:
        stop = fill - order.stop_distance
    else:
        stop = float("-inf")

    if np.isfinite(stop):
        initial = stop
    elif order.risk_distance is not None:
        initial = fill - order.risk_distance
    else:
        return None  # sem stop e sem unidade de risco: não dá para medir em R

    if not np.isfinite(initial) or initial >= fill or initial <= 0:
        return None  # stop acima do preço executado (gap) ou inválido: trade descartado
    target = fill + order.target_r * (fill - initial) if order.target_r else None
    return Position(t, fill, stop, initial, target, dict(order.meta))


def run_asset(setup: Setup, bars: Bars, costs: Costs, start_idx: int = 0) -> list[Trade]:
    """Simula um setup em um ativo. `start_idx` evita sinais antes do aquecimento."""
    ind = setup.prepare(bars)
    o, h, lo, c = bars.open, bars.high, bars.low, bars.close
    trades: list[Trade] = []
    pending: Order | None = None
    pos: Position | None = None

    for t in range(start_idx, len(bars)):
        entered_now = False

        if pos is None and pending is not None:
            fill = None
            if pending.kind == "open":
                fill = o[t]
            elif pending.kind == "stop" and h[t] >= pending.level:
                fill = max(pending.level, o[t])
            if fill is not None:
                pos = _open_position(pending, t, float(fill))
                pending = None
                entered_now = pos is not None
            elif pending.kind == "open" or (pending.expires is not None and t >= pending.expires):
                pending = None
            else:
                pending = setup.update_pending(t, pending, bars, ind)

        if pos is not None:
            stop_hit = lo[t] <= pos.stop
            target_hit = (not entered_now) and pos.target is not None and h[t] >= pos.target
            if stop_hit:
                price = min(pos.stop, o[t]) if not entered_now else pos.stop
                trades.append(_finalize(bars, pos, t, float(price), "stop", costs))
                pos = None
                continue
            if target_hit:
                trades.append(_finalize(bars, pos, t, float(max(pos.target, o[t])), "alvo", costs))
                pos = None
                continue
            decision = setup.manage(t, pos, bars, ind)
            if decision is not None:
                if decision.kind == "close":
                    trades.append(_finalize(bars, pos, t, float(c[t]), decision.reason, costs))
                    pos = None
                elif t + 1 < len(bars):
                    trades.append(
                        _finalize(bars, pos, t + 1, float(o[t + 1]), decision.reason, costs)
                    )
                    pos = None
            continue

        if pending is None:
            order = setup.signal(t, bars, ind)
            if order is None:
                continue
            if order.kind == "close":
                pos = _open_position(order, t, float(c[t]))
            else:
                pending = order

    if pos is not None:
        last = len(bars) - 1
        trades.append(_finalize(bars, pos, last, float(c[last]), "fim_dos_dados", costs))
    return trades
