from __future__ import annotations

from decimal import Decimal

from fastapi.testclient import TestClient
from sqlalchemy import text
from sqlalchemy.orm import Session

from tests.helpers import trade_body


def _statement_trade(**overrides):
    body = {
        "trade_id": "T1",
        "symbol": "BTC-USD",
        "side": "BUY",
        "quantity": "10",
        "price": "100",
        "traded_at": "2026-01-01T10:00:00Z",
    }
    body.update(overrides)
    return body


def test_spec_example_reports_mismatch_and_missing(client: TestClient) -> None:
    assert (
        client.post(
            "/trades",
            json=trade_body(trade_id="T1", quantity="10", price="100"),
        ).status_code
        == 201
    )
    assert (
        client.post(
            "/trades",
            json=trade_body(
                trade_id="T2",
                quantity="5",
                price="101",
                traded_at="2026-01-01T11:00:00Z",
            ),
        ).status_code
        == 201
    )

    response = client.post(
        "/reconcile",
        json={
            "venue": "binance",
            "trades": [
                _statement_trade(trade_id="T1", quantity="10", price="100"),
                _statement_trade(
                    trade_id="T2",
                    quantity="6",
                    price="101",
                    traded_at="2026-01-01T11:00:00Z",
                ),
                _statement_trade(
                    trade_id="T3",
                    quantity="1",
                    price="99",
                    traded_at="2026-01-01T12:00:00Z",
                ),
            ],
        },
    )
    assert response.status_code == 200
    body = response.json()

    missing_ids = {t["trade_id"] for t in body["missing"]}
    assert missing_ids == {"T3"}

    assert len(body["mismatched"]) == 1
    mismatch = body["mismatched"][0]
    assert mismatch["trade_id"] == "T2"
    qty_diff = next(d for d in mismatch["diffs"] if d["field"] == "quantity")
    assert Decimal(qty_diff["stored"]) == Decimal("5")
    assert Decimal(qty_diff["statement"]) == Decimal("6")
    assert body["extra"] == []


def test_stored_trade_absent_from_statement_is_reported_as_extra(
    client: TestClient,
) -> None:
    assert client.post("/trades", json=trade_body(trade_id="T1")).status_code == 201
    assert client.post("/trades", json=trade_body(trade_id="T2")).status_code == 201

    response = client.post(
        "/reconcile",
        json={
            "venue": "binance",
            "trades": [_statement_trade(trade_id="T1")],
        },
    )
    assert response.status_code == 200
    extra_ids = {t["trade_id"] for t in response.json()["extra"]}
    assert extra_ids == {"T2"}
    assert response.json()["missing"] == []
    assert response.json()["mismatched"] == []


def test_extra_is_scoped_to_statement_venue(client: TestClient) -> None:
    assert (
        client.post(
            "/trades",
            json=trade_body(venue="binance", trade_id="B1"),
        ).status_code
        == 201
    )
    assert (
        client.post(
            "/trades",
            json=trade_body(venue="coinbase", trade_id="C1"),
        ).status_code
        == 201
    )

    response = client.post(
        "/reconcile",
        json={
            "venue": "coinbase",
            "trades": [
                _statement_trade(trade_id="C1"),
            ],
        },
    )
    assert response.status_code == 200
    body = response.json()
    assert body["extra"] == []
    assert body["missing"] == []
    assert body["mismatched"] == []
    assert all(t["venue"] != "binance" for t in body["extra"])


def test_numeric_equivalence_is_not_a_mismatch(client: TestClient) -> None:
    assert (
        client.post(
            "/trades",
            json=trade_body(trade_id="T1", quantity="100", price="10"),
        ).status_code
        == 201
    )
    response = client.post(
        "/reconcile",
        json={
            "venue": "binance",
            "trades": [
                _statement_trade(trade_id="T1", quantity="100.00", price="10.00"),
            ],
        },
    )
    assert response.status_code == 200
    body = response.json()
    assert body["mismatched"] == []
    assert body["missing"] == []
    assert body["extra"] == []


def test_reconciliation_is_read_only(client: TestClient, db_session: Session) -> None:
    assert client.post("/trades", json=trade_body(trade_id="T1")).status_code == 201
    assert client.post("/trades", json=trade_body(trade_id="T2")).status_code == 201

    before_trades = db_session.execute(
        text("SELECT venue, trade_id, symbol, side, quantity, price, traded_at FROM trades ORDER BY trade_id")
    ).all()
    before_positions = db_session.execute(
        text("SELECT symbol, quantity, avg_cost, realized_pnl FROM positions ORDER BY symbol")
    ).all()

    perfect = client.post(
        "/reconcile",
        json={
            "venue": "binance",
            "trades": [
                _statement_trade(trade_id="T1"),
                _statement_trade(trade_id="T2"),
            ],
        },
    )
    assert perfect.status_code == 200
    assert perfect.json()["missing"] == []
    assert perfect.json()["extra"] == []
    assert perfect.json()["mismatched"] == []

    empty = client.post("/reconcile", json={"venue": "binance", "trades": []})
    assert empty.status_code == 200
    assert {t["trade_id"] for t in empty.json()["extra"]} == {"T1", "T2"}

    db_session.expire_all()
    after_trades = db_session.execute(
        text("SELECT venue, trade_id, symbol, side, quantity, price, traded_at FROM trades ORDER BY trade_id")
    ).all()
    after_positions = db_session.execute(
        text("SELECT symbol, quantity, avg_cost, realized_pnl FROM positions ORDER BY symbol")
    ).all()
    assert after_trades == before_trades
    assert after_positions == before_positions
