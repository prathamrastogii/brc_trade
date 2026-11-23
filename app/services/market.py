from __future__ import annotations

from decimal import Decimal

from sqlalchemy.orm import Session

from app.db import repository as repo
from app.domain import unrealized_pnl
from app.logging_config import get_logger
from app.schemas.market import PnLResponse, PositionResponse, PriceResponse
from app.services.exceptions import NotFoundError

logger = get_logger(__name__)


def set_price(session: Session, symbol: str, price: Decimal) -> PriceResponse:
    row = repo.upsert_price(session, symbol, price)
    logger.info("Set mark price symbol=%s price=%s", symbol, price)
    return PriceResponse(symbol=row.symbol, price=row.price, updated_at=row.updated_at)


def get_position(session: Session, symbol: str) -> PositionResponse:
    state = repo.get_position(session, symbol)
    if state is None:
        raise NotFoundError(
            f"No position for symbol {symbol}",
            details={"symbol": symbol},
        )
    return PositionResponse(
        symbol=state.symbol,
        quantity=state.quantity,
        avg_cost=state.avg_cost,
        realized_pnl=state.realized_pnl,
    )


def get_pnl(session: Session, symbol: str) -> PnLResponse:
    state = repo.get_position(session, symbol)
    if state is None:
        raise NotFoundError(
            f"No position for symbol {symbol}",
            details={"symbol": symbol},
        )
    price_row = repo.get_price(session, symbol)
    mark = Decimal(price_row.price) if price_row is not None else None
    return PnLResponse(
        symbol=state.symbol,
        quantity=state.quantity,
        avg_cost=state.avg_cost,
        realized_pnl=state.realized_pnl,
        unrealized_pnl=unrealized_pnl(state, mark),
        mark_price=mark,
    )
