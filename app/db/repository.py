from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.engine import Row
from sqlalchemy.orm import Session

from app.db.tables import positions, prices, trades
from app.domain.models import PositionState


def lock_position(session: Session, symbol: str) -> PositionState:
    session.execute(
        insert(positions)
        .values(
            symbol=symbol,
            quantity=Decimal("0"),
            avg_cost=Decimal("0"),
            realized_pnl=Decimal("0"),
        )
        .on_conflict_do_nothing(index_elements=[positions.c.symbol])
    )
    row = session.execute(
        select(positions).where(positions.c.symbol == symbol).with_for_update()
    ).one()
    return PositionState(
        symbol=row.symbol,
        quantity=Decimal(row.quantity),
        avg_cost=Decimal(row.avg_cost),
        realized_pnl=Decimal(row.realized_pnl),
    )


def try_insert_trade(
    session: Session,
    *,
    venue: str,
    trade_id: str,
    symbol: str,
    side: str,
    quantity: Decimal,
    price: Decimal,
    traded_at: datetime,
) -> Row | None:
    stmt = (
        insert(trades)
        .values(
            venue=venue,
            trade_id=trade_id,
            symbol=symbol,
            side=side,
            quantity=quantity,
            price=price,
            traded_at=traded_at,
        )
        .on_conflict_do_nothing(index_elements=[trades.c.venue, trades.c.trade_id])
        .returning(trades)
    )
    return session.execute(stmt).one_or_none()


def get_trade(session: Session, venue: str, trade_id: str) -> Row:
    return session.execute(
        select(trades).where(
            trades.c.venue == venue,
            trades.c.trade_id == trade_id,
        )
    ).one()


def update_position(session: Session, state: PositionState) -> None:
    session.execute(
        positions.update()
        .where(positions.c.symbol == state.symbol)
        .values(
            quantity=state.quantity,
            avg_cost=state.avg_cost,
            realized_pnl=state.realized_pnl,
        )
    )


def trade_payload_matches(
    row: Row,
    *,
    symbol: str,
    side: str,
    quantity: Decimal,
    price: Decimal,
    traded_at: datetime,
) -> bool:
    return (
        row.symbol == symbol
        and row.side == side
        and Decimal(row.quantity) == quantity
        and Decimal(row.price) == price
        and row.traded_at == traded_at
    )


def get_position(session: Session, symbol: str) -> PositionState | None:
    row = session.execute(
        select(positions).where(positions.c.symbol == symbol)
    ).one_or_none()
    if row is None:
        return None
    return PositionState(
        symbol=row.symbol,
        quantity=Decimal(row.quantity),
        avg_cost=Decimal(row.avg_cost),
        realized_pnl=Decimal(row.realized_pnl),
    )


def upsert_price(session: Session, symbol: str, price: Decimal) -> Row:
    stmt = (
        insert(prices)
        .values(symbol=symbol, price=price)
        .on_conflict_do_update(
            index_elements=[prices.c.symbol],
            set_={"price": price, "updated_at": func.now()},
        )
        .returning(prices)
    )
    return session.execute(stmt).one()


def get_price(session: Session, symbol: str) -> Row | None:
    return session.execute(
        select(prices).where(prices.c.symbol == symbol)
    ).one_or_none()


def list_trades_for_venue(
    session: Session,
    venue: str,
    *,
    window_start: datetime | None = None,
    window_end: datetime | None = None,
) -> list[Row]:
    stmt = select(trades).where(trades.c.venue == venue)
    if window_start is not None:
        stmt = stmt.where(trades.c.traded_at >= window_start)
    if window_end is not None:
        stmt = stmt.where(trades.c.traded_at <= window_end)
    return list(session.execute(stmt.order_by(trades.c.traded_at, trades.c.trade_id)).all())


def list_all_trades_arrival_order(session: Session) -> list[Row]:
    return list(
        session.execute(
            select(trades).order_by(trades.c.created_at, trades.c.venue, trades.c.trade_id)
        ).all()
    )


def list_all_positions(session: Session) -> list[Row]:
    return list(session.execute(select(positions).order_by(positions.c.symbol)).all())

