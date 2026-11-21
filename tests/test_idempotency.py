from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed
from decimal import Decimal
from threading import Barrier

from fastapi.testclient import TestClient
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.db.session import get_session_factory
from app.schemas.trades import TradeCreate
from app.services.ingest import ingest_trade
from tests.helpers import get_position, trade_body


def test_duplicate_trade_creates_one_row_and_returns_original(
    client: TestClient, db_session: Session
) -> None:
    body = trade_body()
    first = client.post("/trades", json=body)
    second = client.post("/trades", json=body)

    assert first.status_code == 201
    assert second.status_code == 200
    assert first.json() == second.json()
    assert db_session.execute(text("SELECT COUNT(*) FROM trades")).scalar_one() == 1


def test_duplicate_does_not_apply_to_position_twice(
    client: TestClient, db_session: Session
) -> None:
    body = trade_body(quantity="10", price="100")
    assert client.post("/trades", json=body).status_code == 201
    assert client.post("/trades", json=body).status_code == 200

    db_session.expire_all()
    pos = get_position(db_session, "BTC-USD")
    assert pos is not None
    assert Decimal(pos.quantity) == Decimal("10")


def test_same_trade_id_on_different_venues_are_distinct(
    client: TestClient, db_session: Session
) -> None:
    a = client.post("/trades", json=trade_body(venue="binance", trade_id="T1"))
    b = client.post("/trades", json=trade_body(venue="coinbase", trade_id="T1"))
    assert a.status_code == 201
    assert b.status_code == 201
    assert db_session.execute(text("SELECT COUNT(*) FROM trades")).scalar_one() == 2


def test_same_key_different_payload_returns_409_duplicate_mismatch(
    client: TestClient, db_session: Session
) -> None:
    first = client.post("/trades", json=trade_body(trade_id="T1", quantity="10"))
    assert first.status_code == 201

    second = client.post("/trades", json=trade_body(trade_id="T1", quantity="12"))
    assert second.status_code == 409
    assert second.json()["code"] == "DUPLICATE_MISMATCH"

    db_session.expire_all()
    row = db_session.execute(
        text("SELECT quantity FROM trades WHERE venue='binance' AND trade_id='T1'")
    ).one()
    assert Decimal(row.quantity) == Decimal("10")
    pos = get_position(db_session, "BTC-USD")
    assert Decimal(pos.quantity) == Decimal("10")


def test_concurrent_duplicates_create_one_trade() -> None:
    barrier = Barrier(20)
    payload = TradeCreate.model_validate(trade_body(trade_id="CONC-1"))

    def worker() -> tuple[bool, str]:
        barrier.wait()
        session = get_session_factory()()
        try:
            result = ingest_trade(session, payload)
            session.commit()
            return result.created, "ok"
        except Exception as exc:  # noqa: BLE001
            session.rollback()
            return False, type(exc).__name__
        finally:
            session.close()

    created_flags: list[bool] = []
    with ThreadPoolExecutor(max_workers=20) as pool:
        futures = [pool.submit(worker) for _ in range(20)]
        for fut in as_completed(futures):
            created, _ = fut.result()
            created_flags.append(created)

    assert sum(1 for flag in created_flags if flag) == 1
    assert sum(1 for flag in created_flags if not flag) == 19

    session = get_session_factory()()
    try:
        assert session.execute(text("SELECT COUNT(*) FROM trades")).scalar_one() == 1
        pos = get_position(session, "BTC-USD")
        assert Decimal(pos.quantity) == Decimal("10")
    finally:
        session.close()


def test_normalization_collapses_venue_and_symbol_case(
    client: TestClient, db_session: Session
) -> None:
    first = client.post(
        "/trades",
        json=trade_body(venue="Binance", symbol="btc-usd", trade_id="N1"),
    )
    second = client.post(
        "/trades",
        json=trade_body(venue="binance", symbol="BTC-USD", trade_id="N1"),
    )
    assert first.status_code == 201
    assert second.status_code == 200
    assert first.json()["venue"] == "binance"
    assert first.json()["symbol"] == "BTC-USD"
    assert db_session.execute(text("SELECT COUNT(*) FROM trades")).scalar_one() == 1
