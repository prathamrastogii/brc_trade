from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field, field_validator

from app.schemas.decimals import StrictDecimal


class TradeCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    venue: str = Field(min_length=1)
    trade_id: str = Field(min_length=1)
    symbol: str = Field(min_length=1)
    side: Literal["BUY", "SELL"]
    quantity: StrictDecimal
    price: StrictDecimal
    traded_at: AwareDatetime

    @field_validator("venue", mode="before")
    @classmethod
    def normalize_venue(cls, value: Any) -> Any:
        if isinstance(value, str):
            return value.strip().lower()
        return value

    @field_validator("symbol", mode="before")
    @classmethod
    def normalize_symbol(cls, value: Any) -> Any:
        if isinstance(value, str):
            return value.strip().upper()
        return value

    @field_validator("side", mode="before")
    @classmethod
    def normalize_side(cls, value: Any) -> Any:
        if isinstance(value, str):
            return value.strip().upper()
        return value

    @field_validator("trade_id", mode="before")
    @classmethod
    def strip_trade_id(cls, value: Any) -> Any:
        if isinstance(value, str):
            return value.strip()
        return value

    @field_validator("quantity", "price")
    @classmethod
    def must_be_positive(cls, value: StrictDecimal) -> StrictDecimal:
        if value <= 0:
            raise ValueError("must be greater than zero")
        return value


class TradeResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    venue: str
    trade_id: str
    symbol: str
    side: Literal["BUY", "SELL"]
    quantity: StrictDecimal
    price: StrictDecimal
    traded_at: datetime
