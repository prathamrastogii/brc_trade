from __future__ import annotations

from decimal import Decimal

from fastapi.testclient import TestClient

from tests.helpers import trade_body


def test_worked_example_via_http(client: TestClient) -> None:
    assert (
        client.post(
            "/trades",
            json=trade_body(trade_id="W1", quantity="10", price="100"),
        ).status_code
        == 201
    )
    assert (
        client.post(
            "/trades",
            json=trade_body(trade_id="W2", quantity="10", price="110"),
        ).status_code
        == 201
    )
    assert (
        client.post(
            "/trades",
            json=trade_body(trade_id="W3", side="SELL", quantity="5", price="120"),
        ).status_code
        == 201
    )
    assert (
        client.put("/prices/BTC-USD", json={"price": "125"}).status_code == 200
    )

    position = client.get("/positions/BTC-USD").json()
    assert Decimal(position["quantity"]) == Decimal("15")
    assert Decimal(position["avg_cost"]) == Decimal("105")
    assert Decimal(position["realized_pnl"]) == Decimal("75")

    pnl = client.get("/pnl/BTC-USD").json()
    assert Decimal(pnl["realized_pnl"]) == Decimal("75")
    assert Decimal(pnl["unrealized_pnl"]) == Decimal("300")
    assert Decimal(pnl["mark_price"]) == Decimal("125")


def test_symbols_are_isolated(client: TestClient) -> None:
    assert (
        client.post(
            "/trades",
            json=trade_body(trade_id="B1", symbol="BTC-USD", quantity="10", price="100"),
        ).status_code
        == 201
    )
    assert (
        client.post(
            "/trades",
            json=trade_body(trade_id="E1", symbol="ETH-USD", quantity="3", price="50"),
        ).status_code
        == 201
    )

    btc = client.get("/positions/BTC-USD").json()
    eth = client.get("/positions/ETH-USD").json()
    assert Decimal(btc["quantity"]) == Decimal("10")
    assert Decimal(eth["quantity"]) == Decimal("3")
    assert Decimal(btc["avg_cost"]) == Decimal("100")
    assert Decimal(eth["avg_cost"]) == Decimal("50")


def test_positions_aggregate_across_venues(client: TestClient) -> None:
    assert (
        client.post(
            "/trades",
            json=trade_body(
                venue="binance",
                trade_id="V1",
                symbol="BTC-USD",
                quantity="5",
                price="100",
            ),
        ).status_code
        == 201
    )
    assert (
        client.post(
            "/trades",
            json=trade_body(
                venue="coinbase",
                trade_id="V1",
                symbol="BTC-USD",
                quantity="5",
                price="100",
            ),
        ).status_code
        == 201
    )

    position = client.get("/positions/BTC-USD").json()
    assert Decimal(position["quantity"]) == Decimal("10")
    assert Decimal(position["avg_cost"]) == Decimal("100")


def test_unrealized_is_null_when_no_price_set(client: TestClient) -> None:
    assert (
        client.post(
            "/trades",
            json=trade_body(trade_id="P1", quantity="10", price="100"),
        ).status_code
        == 201
    )
    pnl = client.get("/pnl/BTC-USD").json()
    assert pnl["unrealized_pnl"] is None
    assert pnl["mark_price"] is None
    assert Decimal(pnl["realized_pnl"]) == Decimal("0")


def test_price_update_changes_unrealized_not_realized(client: TestClient) -> None:
    assert (
        client.post(
            "/trades",
            json=trade_body(trade_id="R1", quantity="10", price="100"),
        ).status_code
        == 201
    )
    assert (
        client.post(
            "/trades",
            json=trade_body(trade_id="R2", side="SELL", quantity="5", price="120"),
        ).status_code
        == 201
    )
    assert client.put("/prices/BTC-USD", json={"price": "125"}).status_code == 200
    first = client.get("/pnl/BTC-USD").json()
    realized = Decimal(first["realized_pnl"])
    assert realized == Decimal("100")
    assert Decimal(first["unrealized_pnl"]) == Decimal("125")

    assert client.put("/prices/BTC-USD", json={"price": "130"}).status_code == 200
    second = client.get("/pnl/BTC-USD").json()
    assert Decimal(second["realized_pnl"]) == realized
    assert Decimal(second["unrealized_pnl"]) == Decimal("150")


def test_missing_position_returns_404(client: TestClient) -> None:
    pos = client.get("/positions/NOPE-USD")
    assert pos.status_code == 404
    assert pos.json()["code"] == "NOT_FOUND"

    pnl = client.get("/pnl/NOPE-USD")
    assert pnl.status_code == 404
    assert pnl.json()["code"] == "NOT_FOUND"


def test_total_pnl_equals_realized_plus_unrealized_across_symbols(
    client: TestClient,
) -> None:
    assert (
        client.post(
            "/trades",
            json=trade_body(trade_id="T1", symbol="BTC-USD", quantity="10", price="100"),
        ).status_code
        == 201
    )
    assert (
        client.post(
            "/trades",
            json=trade_body(
                trade_id="T2",
                symbol="BTC-USD",
                side="SELL",
                quantity="4",
                price="110",
            ),
        ).status_code
        == 201
    )
    assert client.put("/prices/BTC-USD", json={"price": "120"}).status_code == 200

    assert (
        client.post(
            "/trades",
            json=trade_body(trade_id="E1", symbol="ETH-USD", quantity="2", price="50"),
        ).status_code
        == 201
    )
    assert client.put("/prices/ETH-USD", json={"price": "60"}).status_code == 200

    btc = client.get("/pnl/BTC-USD").json()
    eth = client.get("/pnl/ETH-USD").json()

    btc_realized = Decimal(btc["realized_pnl"])
    btc_unrealized = Decimal(btc["unrealized_pnl"])
    eth_realized = Decimal(eth["realized_pnl"])
    eth_unrealized = Decimal(eth["unrealized_pnl"])

    assert btc_realized == Decimal("40")
    assert btc_unrealized == Decimal("120")
    assert eth_realized == Decimal("0")
    assert eth_unrealized == Decimal("20")

    btc_total = btc_realized + btc_unrealized
    eth_total = eth_realized + eth_unrealized
    assert btc_total == Decimal("160")
    assert eth_total == Decimal("20")
    assert btc_total + eth_total == Decimal("180")


def test_whitespace_symbol_path_returns_422(client: TestClient) -> None:
    for path in ("/positions/%20", "/pnl/%20", "/prices/%20"):
        if path.startswith("/prices"):
            response = client.put(path, json={"price": "100"})
        else:
            response = client.get(path)
        assert response.status_code == 422, path
        assert response.json()["code"] == "VALIDATION_ERROR"
