from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy.orm import Session

from app.db import repository as repo
from app.domain import OversellError, Side, TradeFill, apply_trade
from app.logging_config import get_logger
from app.schemas.trades import TradeCreate, TradeResponse
from app.services.exceptions import DuplicateMismatchError, OversellServiceError

logger = get_logger(__name__)


@dataclass(frozen=True, slots=True)
class IngestResult:
    trade: TradeResponse
    created: bool


def _row_to_response(row) -> TradeResponse:
    return TradeResponse(
        venue=row.venue,
        trade_id=row.trade_id,
        symbol=row.symbol,
        side=row.side,
        quantity=row.quantity,
        price=row.price,
        traded_at=row.traded_at,
    )


def ingest_trade(session: Session, payload: TradeCreate) -> IngestResult:
    position = repo.lock_position(session, payload.symbol)

    inserted = repo.try_insert_trade(
        session,
        venue=payload.venue,
        trade_id=payload.trade_id,
        symbol=payload.symbol,
        side=payload.side,
        quantity=payload.quantity,
        price=payload.price,
        traded_at=payload.traded_at,
    )

    if inserted is None:
        existing = repo.get_trade(session, payload.venue, payload.trade_id)
        if not repo.trade_payload_matches(
            existing,
            symbol=payload.symbol,
            side=payload.side,
            quantity=payload.quantity,
            price=payload.price,
            traded_at=payload.traded_at,
        ):
            logger.warning(
                "Duplicate mismatch venue=%s trade_id=%s",
                payload.venue,
                payload.trade_id,
            )
            raise DuplicateMismatchError(
                "Trade with this venue and trade_id already exists with a different payload",
                details={
                    "venue": payload.venue,
                    "trade_id": payload.trade_id,
                },
            )
        logger.info(
            "Idempotent hit venue=%s trade_id=%s",
            payload.venue,
            payload.trade_id,
        )
        return IngestResult(trade=_row_to_response(existing), created=False)

    fill = TradeFill(
        symbol=payload.symbol,
        side=Side(payload.side),
        quantity=payload.quantity,
        price=payload.price,
    )
    try:
        new_position = apply_trade(position, fill)
    except OversellError as exc:
        logger.warning(
            "Oversell symbol=%s available=%s requested=%s",
            exc.symbol,
            exc.available,
            exc.requested,
        )
        raise OversellServiceError(
            "SELL would take position below zero",
            details={
                "symbol": exc.symbol,
                "available": str(exc.available),
                "requested": str(exc.requested),
            },
        ) from exc

    repo.update_position(session, new_position)
    logger.info(
        "Ingested venue=%s trade_id=%s symbol=%s side=%s",
        payload.venue,
        payload.trade_id,
        payload.symbol,
        payload.side,
    )
    return IngestResult(trade=_row_to_response(inserted), created=True)
