from __future__ import annotations

from app.services.exceptions import ValidationServiceError


def normalize_symbol_path(symbol: str) -> str:
    cleaned = symbol.strip().upper()
    if not cleaned:
        raise ValidationServiceError(
            "symbol must not be empty or whitespace-only",
            details={"symbol": symbol},
        )
    return cleaned
