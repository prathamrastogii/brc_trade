from __future__ import annotations

from fastapi import APIRouter, Depends, Path
from sqlalchemy.orm import Session

from app.db.deps import get_db
from app.api.path_params import normalize_symbol_path
from app.schemas.market import (
    PnLResponse,
    PositionResponse,
    PriceResponse,
    PriceUpsert,
)
from app.services import market as market_service

router = APIRouter(tags=["market"])


@router.put("/prices/{symbol}", response_model=PriceResponse)
def put_price(
    payload: PriceUpsert,
    symbol: str = Path(min_length=1),
    session: Session = Depends(get_db),
) -> PriceResponse:
    return market_service.set_price(session, normalize_symbol_path(symbol), payload.price)


@router.get("/positions/{symbol}", response_model=PositionResponse)
def read_position(
    symbol: str = Path(min_length=1),
    session: Session = Depends(get_db),
) -> PositionResponse:
    return market_service.get_position(session, normalize_symbol_path(symbol))


@router.get("/pnl/{symbol}", response_model=PnLResponse)
def read_pnl(
    symbol: str = Path(min_length=1),
    session: Session = Depends(get_db),
) -> PnLResponse:
    return market_service.get_pnl(session, normalize_symbol_path(symbol))
