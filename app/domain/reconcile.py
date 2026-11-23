from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from typing import Any, Literal


@dataclass(frozen=True, slots=True)
class TradeView:
    venue: str
    trade_id: str
    symbol: str
    side: Literal["BUY", "SELL"]
    quantity: Decimal
    price: Decimal
    traded_at: datetime


@dataclass(frozen=True, slots=True)
class FieldDiffView:
    field: str
    stored: Any
    statement: Any


@dataclass(frozen=True, slots=True)
class MismatchView:
    trade_id: str
    diffs: tuple[FieldDiffView, ...]


@dataclass(frozen=True, slots=True)
class ReconcileResult:
    missing: tuple[TradeView, ...]
    extra: tuple[TradeView, ...]
    mismatched: tuple[MismatchView, ...]


def _serialize_value(value: Any) -> Any:
    if isinstance(value, Decimal):
        return format(value, "f")
    if isinstance(value, datetime):
        return value.isoformat()
    return value


def diff_trades(stored: TradeView, statement: TradeView) -> tuple[FieldDiffView, ...]:
    diffs: list[FieldDiffView] = []
    checks: list[tuple[str, Any, Any]] = [
        ("symbol", stored.symbol, statement.symbol),
        ("side", stored.side, statement.side),
        ("quantity", stored.quantity, statement.quantity),
        ("price", stored.price, statement.price),
        ("traded_at", stored.traded_at, statement.traded_at),
    ]
    for field, left, right in checks:
        if field in {"quantity", "price"}:
            if Decimal(left) != Decimal(right):
                diffs.append(
                    FieldDiffView(
                        field=field,
                        stored=_serialize_value(Decimal(left)),
                        statement=_serialize_value(Decimal(right)),
                    )
                )
        elif left != right:
            diffs.append(
                FieldDiffView(
                    field=field,
                    stored=_serialize_value(left),
                    statement=_serialize_value(right),
                )
            )
    return tuple(diffs)


def reconcile_trades(
    *,
    stored: list[TradeView],
    statement: list[TradeView],
) -> ReconcileResult:
    stored_by_id = {t.trade_id: t for t in stored}
    statement_by_id = {t.trade_id: t for t in statement}

    missing = tuple(
        statement_by_id[tid]
        for tid in statement_by_id.keys() - stored_by_id.keys()
    )
    extra = tuple(
        stored_by_id[tid] for tid in stored_by_id.keys() - statement_by_id.keys()
    )
    mismatched: list[MismatchView] = []
    for tid in stored_by_id.keys() & statement_by_id.keys():
        diffs = diff_trades(stored_by_id[tid], statement_by_id[tid])
        if diffs:
            mismatched.append(MismatchView(trade_id=tid, diffs=diffs))

    return ReconcileResult(
        missing=missing,
        extra=extra,
        mismatched=tuple(mismatched),
    )
