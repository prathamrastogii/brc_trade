from __future__ import annotations

from fastapi import APIRouter, Depends, Response, status
from sqlalchemy.orm import Session

from app.db.deps import get_db
from app.logging_config import get_logger
from app.schemas.trades import TradeCreate, TradeResponse
from app.services.ingest import ingest_trade

router = APIRouter(tags=["trades"])
logger = get_logger(__name__)


@router.post(
    "/trades",
    response_model=TradeResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_trade(
    payload: TradeCreate,
    response: Response,
    session: Session = Depends(get_db),
) -> TradeResponse:
    result = ingest_trade(session, payload)
    if not result.created:
        response.status_code = status.HTTP_200_OK
    return result.trade
