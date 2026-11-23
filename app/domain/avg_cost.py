from __future__ import annotations

from decimal import Decimal

from app.domain.exceptions import OversellError
from app.domain.models import PositionState, Side, TradeFill

ZERO = Decimal("0")


def apply_trade(position: PositionState, trade: TradeFill) -> PositionState:
    if trade.symbol != position.symbol:
        raise ValueError(
            f"Symbol mismatch: position={position.symbol!r} trade={trade.symbol!r}"
        )
    if not isinstance(trade.quantity, Decimal) or not isinstance(trade.price, Decimal):
        raise TypeError("trade quantity and price must be Decimal")
    if trade.quantity <= ZERO or trade.price <= ZERO:
        raise ValueError("trade quantity and price must be positive")

    if trade.side is Side.BUY:
        return _apply_buy(position, trade)
    if trade.side is Side.SELL:
        return _apply_sell(position, trade)
    raise ValueError(f"Unsupported side: {trade.side!r}")


def _apply_buy(position: PositionState, trade: TradeFill) -> PositionState:
    new_qty = position.quantity + trade.quantity
    if position.quantity == ZERO:
        new_avg = trade.price
    else:
        cost_basis = (position.quantity * position.avg_cost) + (trade.quantity * trade.price)
        new_avg = cost_basis / new_qty
    return PositionState(
        symbol=position.symbol,
        quantity=new_qty,
        avg_cost=new_avg,
        realized_pnl=position.realized_pnl,
    )


def _apply_sell(position: PositionState, trade: TradeFill) -> PositionState:
    if trade.quantity > position.quantity:
        raise OversellError(
            symbol=position.symbol,
            available=position.quantity,
            requested=trade.quantity,
        )
    realized_delta = (trade.price - position.avg_cost) * trade.quantity
    new_qty = position.quantity - trade.quantity
    new_avg = ZERO if new_qty == ZERO else position.avg_cost
    return PositionState(
        symbol=position.symbol,
        quantity=new_qty,
        avg_cost=new_avg,
        realized_pnl=position.realized_pnl + realized_delta,
    )


def unrealized_pnl(position: PositionState, mark_price: Decimal | None) -> Decimal | None:
    if mark_price is None:
        return None
    if not isinstance(mark_price, Decimal):
        raise TypeError("mark_price must be Decimal or None")
    return (mark_price - position.avg_cost) * position.quantity
