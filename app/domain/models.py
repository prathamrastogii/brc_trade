from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from enum import StrEnum


class Side(StrEnum):
    BUY = "BUY"
    SELL = "SELL"


@dataclass(frozen=True, slots=True)
class PositionState:
    symbol: str
    quantity: Decimal
    avg_cost: Decimal
    realized_pnl: Decimal

    @classmethod
    def empty(cls, symbol: str) -> PositionState:
        zero = Decimal("0")
        return cls(symbol=symbol, quantity=zero, avg_cost=zero, realized_pnl=zero)


@dataclass(frozen=True, slots=True)
class TradeFill:
    symbol: str
    side: Side
    quantity: Decimal
    price: Decimal
