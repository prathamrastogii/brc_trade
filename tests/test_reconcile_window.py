from __future__ import annotations

from fastapi.testclient import TestClient

from tests.helpers import trade_body


def test_out_of_window_stored_trade_on_statement_is_missing(client: TestClient) -> None:
    assert (
        client.post(
            "/trades",
            json=trade_body(
                trade_id="T1",
                traded_at="2026-01-01T10:00:00Z",
            ),
        ).status_code
        == 201
    )
    assert (
        client.post(
            "/trades",
            json=trade_body(
                trade_id="T2",
                traded_at="2026-01-01T12:00:00Z",
            ),
        ).status_code
        == 201
    )

    response = client.post(
        "/reconcile",
        json={
            "venue": "binance",
            "window_start": "2026-01-01T09:00:00Z",
            "window_end": "2026-01-01T11:00:00Z",
            "trades": [
                {
                    "trade_id": "T1",
                    "symbol": "BTC-USD",
                    "side": "BUY",
                    "quantity": "10",
                    "price": "100",
                    "traded_at": "2026-01-01T10:00:00Z",
                },
                {
                    "trade_id": "T2",
                    "symbol": "BTC-USD",
                    "side": "BUY",
                    "quantity": "10",
                    "price": "100",
                    "traded_at": "2026-01-01T12:00:00Z",
                },
            ],
        },
    )
    assert response.status_code == 200
    body = response.json()
    assert {t["trade_id"] for t in body["missing"]} == {"T2"}
    assert body["extra"] == []
    assert body["mismatched"] == []
