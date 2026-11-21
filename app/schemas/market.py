from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, field_validator

from app.schemas.decimals import StrictDecimal


class PriceUpsert(BaseModel):
    model_config = ConfigDict(extra="forbid")

    price: StrictDecimal

    @field_validator("price")
    @classmethod
    def must_be_positive(cls, value: StrictDecimal) -> StrictDecimal:
        if value <= 0:
            raise ValueError("must be greater than zero")
        return value


class PriceResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    symbol: str
    price: StrictDecimal
    updated_at: datetime


class PositionResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    symbol: str
    quantity: StrictDecimal
    avg_cost: StrictDecimal
    realized_pnl: StrictDecimal


class PnLResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    symbol: str
    quantity: StrictDecimal
    avg_cost: StrictDecimal
    realized_pnl: StrictDecimal
    unrealized_pnl: StrictDecimal | None
    mark_price: StrictDecimal | None
