from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field, field_validator, model_validator

from app.schemas.decimals import StrictDecimal


class StatementTrade(BaseModel):
    model_config = ConfigDict(extra="forbid")

    trade_id: str = Field(min_length=1)
    symbol: str = Field(min_length=1)
    side: Literal["BUY", "SELL"]
    quantity: StrictDecimal
    price: StrictDecimal
    traded_at: AwareDatetime

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


class ReconcileRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    venue: str = Field(min_length=1)
    trades: list[StatementTrade]
    window_start: AwareDatetime | None = None
    window_end: AwareDatetime | None = None

    @field_validator("venue", mode="before")
    @classmethod
    def normalize_venue(cls, value: Any) -> Any:
        if isinstance(value, str):
            return value.strip().lower()
        return value

    @model_validator(mode="after")
    def validate_window_and_unique_ids(self) -> ReconcileRequest:
        if self.window_start is not None and self.window_end is not None:
            if self.window_start > self.window_end:
                raise ValueError("window_start must be <= window_end")
        ids = [t.trade_id for t in self.trades]
        if len(ids) != len(set(ids)):
            raise ValueError("statement trades must have unique trade_id values")
        return self


class TradeSnapshot(BaseModel):
    model_config = ConfigDict(extra="forbid")

    venue: str
    trade_id: str
    symbol: str
    side: Literal["BUY", "SELL"]
    quantity: StrictDecimal
    price: StrictDecimal
    traded_at: datetime


class FieldDiff(BaseModel):
    model_config = ConfigDict(extra="forbid")

    field: str
    stored: Any
    statement: Any


class MismatchItem(BaseModel):
    model_config = ConfigDict(extra="forbid")

    trade_id: str
    diffs: list[FieldDiff]


class ReconcileResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    venue: str
    missing: list[TradeSnapshot]
    extra: list[TradeSnapshot]
    mismatched: list[MismatchItem]
