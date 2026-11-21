from __future__ import annotations

from typing import Any

from sqlalchemy import select, text
from sqlalchemy.orm import Session

from app.db.tables import positions, trades


def trade_body(**overrides: Any) -> dict[str, Any]:
    body: dict[str, Any] = {
        "venue": "binance",
        "trade_id": "T-1001",
        "symbol": "BTC-USD",
        "side": "BUY",
        "quantity": "10",
        "price": "100",
        "traded_at": "2026-01-01T10:00:00Z",
    }
    body.update(overrides)
    return body


def count_trades(session: Session) -> int:
    return int(session.execute(text("SELECT COUNT(*) FROM trades")).scalar_one())


def get_position(session: Session, symbol: str):
    return session.execute(
        select(positions).where(positions.c.symbol == symbol)
    ).one_or_none()


def list_trades(session: Session):
    return list(session.execute(select(trades)).all())
