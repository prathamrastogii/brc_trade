from __future__ import annotations

from decimal import Decimal

from sqlalchemy.orm import Session

from app.db import repository as repo
from app.domain.reconcile import TradeView, reconcile_trades
from app.logging_config import get_logger
from app.schemas.reconcile import (
    FieldDiff,
    MismatchItem,
    ReconcileRequest,
    ReconcileResponse,
    TradeSnapshot,
)

logger = get_logger(__name__)


def _row_to_view(row) -> TradeView:
    return TradeView(
        venue=row.venue,
        trade_id=row.trade_id,
        symbol=row.symbol,
        side=row.side,
        quantity=Decimal(row.quantity),
        price=Decimal(row.price),
        traded_at=row.traded_at,
    )


def _view_to_snapshot(view: TradeView) -> TradeSnapshot:
    return TradeSnapshot(
        venue=view.venue,
        trade_id=view.trade_id,
        symbol=view.symbol,
        side=view.side,
        quantity=view.quantity,
        price=view.price,
        traded_at=view.traded_at,
    )


def reconcile(session: Session, request: ReconcileRequest) -> ReconcileResponse:
    rows = repo.list_trades_for_venue(
        session,
        request.venue,
        window_start=request.window_start,
        window_end=request.window_end,
    )
    stored = [_row_to_view(row) for row in rows]
    statement = [
        TradeView(
            venue=request.venue,
            trade_id=t.trade_id,
            symbol=t.symbol,
            side=t.side,
            quantity=t.quantity,
            price=t.price,
            traded_at=t.traded_at,
        )
        for t in request.trades
    ]
    result = reconcile_trades(stored=stored, statement=statement)
    logger.info(
        "Reconcile venue=%s stored=%s statement=%s missing=%s extra=%s mismatched=%s",
        request.venue,
        len(stored),
        len(statement),
        len(result.missing),
        len(result.extra),
        len(result.mismatched),
    )
    return ReconcileResponse(
        venue=request.venue,
        missing=[_view_to_snapshot(t) for t in result.missing],
        extra=[_view_to_snapshot(t) for t in result.extra],
        mismatched=[
            MismatchItem(
                trade_id=m.trade_id,
                diffs=[
                    FieldDiff(field=d.field, stored=d.stored, statement=d.statement)
                    for d in m.diffs
                ],
            )
            for m in result.mismatched
        ],
    )
