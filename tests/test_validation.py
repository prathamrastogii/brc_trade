from __future__ import annotations

from decimal import Decimal

from fastapi.testclient import TestClient
from sqlalchemy import text
from sqlalchemy.orm import Session

from tests.helpers import trade_body


def test_invalid_quantity_or_price_returns_422(client: TestClient) -> None:
    cases = [
        {"quantity": "0"},
        {"quantity": "-1"},
        {"quantity": "abc"},
        {"quantity": "NaN"},
        {"quantity": "Infinity"},
        {"price": "0"},
        {"price": "-1"},
        {"price": "abc"},
        {"price": "NaN"},
        {"price": "Infinity"},
    ]
    for override in cases:
        response = client.post("/trades", json=trade_body(**override))
        assert response.status_code == 422, override
        assert response.json()["code"] == "VALIDATION_ERROR"


def test_invalid_side_returns_422(client: TestClient) -> None:
    for side in ("HOLD", ""):
        response = client.post("/trades", json=trade_body(side=side))
        assert response.status_code == 422
        assert response.json()["code"] == "VALIDATION_ERROR"

    response = client.post("/trades", json=trade_body(side="buy", trade_id="T-BUY"))
    assert response.status_code == 201
    assert response.json()["side"] == "BUY"


def test_missing_or_empty_fields_rejected(client: TestClient) -> None:
    required = ["venue", "trade_id", "symbol", "side", "quantity", "price", "traded_at"]
    for field in required:
        body = trade_body()
        del body[field]
        response = client.post("/trades", json=body)
        assert response.status_code == 422, field

    for field in ("venue", "trade_id", "symbol", "side"):
        response = client.post("/trades", json=trade_body(**{field: ""}))
        assert response.status_code == 422, field


def test_naive_timestamp_rejected(client: TestClient) -> None:
    bad = client.post("/trades", json=trade_body(traded_at="2026-01-01T10:00:00"))
    assert bad.status_code == 422
    assert bad.json()["code"] == "VALIDATION_ERROR"

    good = client.post(
        "/trades",
        json=trade_body(trade_id="T-AWARE", traded_at="2026-01-01T10:00:00Z"),
    )
    assert good.status_code == 201


def test_rejected_requests_leave_database_unchanged(
    client: TestClient, db_session: Session
) -> None:
    before_trades = db_session.execute(text("SELECT COUNT(*) FROM trades")).scalar_one()
    before_positions = db_session.execute(text("SELECT COUNT(*) FROM positions")).scalar_one()

    invalid_bodies = [
        trade_body(quantity="0"),
        trade_body(price="-1"),
        trade_body(quantity=10.5),
        trade_body(side="HOLD"),
        trade_body(traded_at="2026-01-01T10:00:00"),
        {k: v for k, v in trade_body().items() if k != "symbol"},
    ]
    for body in invalid_bodies:
        response = client.post("/trades", json=body)
        assert response.status_code == 422

    db_session.expire_all()
    after_trades = db_session.execute(text("SELECT COUNT(*) FROM trades")).scalar_one()
    after_positions = db_session.execute(text("SELECT COUNT(*) FROM positions")).scalar_one()
    assert after_trades == before_trades == 0
    assert after_positions == before_positions == 0
    assert isinstance(Decimal("10.5"), Decimal)
