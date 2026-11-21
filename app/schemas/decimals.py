from __future__ import annotations

from decimal import Decimal, InvalidOperation
from typing import Annotated, Any

from pydantic import BeforeValidator, PlainSerializer


def _parse_strict_decimal(value: Any) -> Decimal:
    if isinstance(value, bool):
        raise ValueError("boolean is not a valid decimal")
    if isinstance(value, float):
        raise ValueError("float values are not allowed; send quantity/price as strings")
    if isinstance(value, Decimal):
        if not value.is_finite():
            raise ValueError("NaN and Infinity are not allowed")
        return value
    if isinstance(value, int):
        return Decimal(value)
    if isinstance(value, str):
        text = value.strip()
        if not text:
            raise ValueError("empty string is not a valid decimal")
        lowered = text.lower()
        if lowered in {"nan", "inf", "+inf", "-inf", "infinity", "+infinity", "-infinity"}:
            raise ValueError("NaN and Infinity are not allowed")
        try:
            parsed = Decimal(text)
        except InvalidOperation as exc:
            raise ValueError("invalid decimal string") from exc
        if not parsed.is_finite():
            raise ValueError("NaN and Infinity are not allowed")
        return parsed
    raise ValueError("invalid decimal type")


def _serialize_decimal(value: Decimal) -> str:
    return format(value, "f")


StrictDecimal = Annotated[
    Decimal,
    BeforeValidator(_parse_strict_decimal),
    PlainSerializer(_serialize_decimal, return_type=str),
]
