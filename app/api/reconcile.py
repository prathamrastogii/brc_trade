from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.db.deps import get_db
from app.schemas.reconcile import ReconcileRequest, ReconcileResponse
from app.services.reconcile import reconcile

router = APIRouter(tags=["reconcile"])


@router.post("/reconcile", response_model=ReconcileResponse)
def post_reconcile(
    payload: ReconcileRequest,
    session: Session = Depends(get_db),
) -> ReconcileResponse:
    return reconcile(session, payload)
