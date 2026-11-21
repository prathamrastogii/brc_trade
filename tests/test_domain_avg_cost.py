from __future__ import annotations

from decimal import Decimal

import pytest

from app.domain import (
    OversellError,
    PositionState,
    Side,
    TradeFill,
    apply_trade,
    unrealized_pnl,
)


def D(value: str) -> Decimal:
    return Decimal(value)


def _buy(symbol: str, qty: str, price: str) -> TradeFill:
    return TradeFill(symbol=symbol, side=Side.BUY, quantity=D(qty), price=D(price))


def _sell(symbol: str, qty: str, price: str) -> TradeFill:
    return TradeFill(symbol=symbol, side=Side.SELL, quantity=D(qty), price=D(price))


def _assert_decimals(position: PositionState) -> None:
    assert type(position.quantity) is Decimal
    assert type(position.avg_cost) is Decimal
    assert type(position.realized_pnl) is Decimal


def test_worked_example_produces_expected_position() -> None:
    symbol = "BTC-USD"
    pos = PositionState.empty(symbol)
    pos = apply_trade(pos, _buy(symbol, "10", "100"))
    pos = apply_trade(pos, _buy(symbol, "10", "110"))
    pos = apply_trade(pos, _sell(symbol, "5", "120"))

    assert pos.quantity == D("15")
    assert pos.avg_cost == D("105")
    assert pos.realized_pnl == D("75")
    assert unrealized_pnl(pos, D("125")) == D("300")
    _assert_decimals(pos)


def test_sell_does_not_change_average_cost() -> None:
    symbol = "ETH-USD"
    pos = PositionState(
        symbol=symbol,
        quantity=D("10"),
        avg_cost=D("100"),
        realized_pnl=D("0"),
    )
    pos = apply_trade(pos, _sell(symbol, "4", "130"))

    assert pos.quantity == D("6")
    assert pos.avg_cost == D("100")
    assert pos.realized_pnl == D("120")
    _assert_decimals(pos)


def test_selling_to_zero_resets_average_cost() -> None:
    symbol = "BTC-USD"
    pos = PositionState.empty(symbol)
    pos = apply_trade(pos, _buy(symbol, "10", "100"))
    pos = apply_trade(pos, _sell(symbol, "10", "110"))

    assert pos.quantity == D("0")
    assert pos.avg_cost == D("0")
    assert pos.realized_pnl == D("100")

    pos = apply_trade(pos, _buy(symbol, "5", "200"))
    assert pos.quantity == D("5")
    assert pos.avg_cost == D("200")
    _assert_decimals(pos)


def test_sell_below_average_gives_negative_realized_pnl() -> None:
    symbol = "BTC-USD"
    pos = PositionState.empty(symbol)
    pos = apply_trade(pos, _buy(symbol, "10", "100"))
    pos = apply_trade(pos, _sell(symbol, "5", "90"))

    assert pos.realized_pnl == D("-50")
    assert pos.quantity == D("5")
    assert pos.avg_cost == D("100")
    _assert_decimals(pos)


def test_oversell_boundary_and_decimal_exactness() -> None:
    symbol = "BTC-USD"
    pos = PositionState(
        symbol=symbol,
        quantity=D("10"),
        avg_cost=D("100"),
        realized_pnl=D("0"),
    )

    exact = apply_trade(pos, _sell(symbol, "10", "110"))
    assert exact.quantity == D("0")
    assert exact.avg_cost == D("0")
    _assert_decimals(exact)

    with pytest.raises(OversellError) as exc_info:
        apply_trade(pos, _sell(symbol, "10.000001", "110"))
    assert exc_info.value.available == D("10")
    assert exc_info.value.requested == D("10.000001")

    tiny = PositionState.empty(symbol)
    tiny = apply_trade(tiny, _buy(symbol, "0.1", "1"))
    tiny = apply_trade(tiny, _buy(symbol, "0.2", "1"))
    assert tiny.quantity == D("0.3")
    assert type(tiny.quantity) is Decimal
    assert not isinstance(tiny.quantity, float)

    dust = apply_trade(PositionState.empty(symbol), _buy(symbol, "0.00000001", "1"))
    assert dust.quantity == D("0.00000001")
    assert type(dust.quantity) is Decimal

    assert unrealized_pnl(exact, None) is None
