from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed
from decimal import Decimal
from threading import Barrier

from fastapi.testclient import TestClient
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.db.session import get_session_factory
from app.schemas.trades import TradeCreate
from app.services.exceptions import OversellServiceError
from app.services.ingest import ingest_trade
from tests.helpers import get_position, trade_body


def test_oversell_returns_409_and_leaves_position_unchanged(
    client: TestClient, db_session: Session
) -> None:
    assert client.post(
        "/trades", json=trade_body(trade_id="B1", quantity="10", side="BUY")
    ).status_code == 201

    response = client.post(
        "/trades",
        json=trade_body(trade_id="S1", quantity="15", side="SELL", price="100"),
    )
    assert response.status_code == 409
    assert response.json()["code"] == "OVERSELL"

    db_session.expire_all()
    pos = get_position(db_session, "BTC-USD")
    assert Decimal(pos.quantity) == Decimal("10")
    assert (
        db_session.execute(
            text("SELECT COUNT(*) FROM trades WHERE trade_id='S1'")
        ).scalar_one()
        == 0
    )


def test_rejected_sell_does_not_burn_trade_id(client: TestClient) -> None:
    assert client.post(
        "/trades", json=trade_body(trade_id="B1", quantity="10", side="BUY")
    ).status_code == 201

    rejected = client.post(
        "/trades",
        json=trade_body(trade_id="S1", quantity="15", side="SELL", price="100"),
    )
    assert rejected.status_code == 409

    assert client.post(
        "/trades", json=trade_body(trade_id="B2", quantity="10", side="BUY")
    ).status_code == 201

    accepted = client.post(
        "/trades",
        json=trade_body(trade_id="S1", quantity="15", side="SELL", price="100"),
    )
    assert accepted.status_code == 201


def test_sell_with_no_position_is_rejected(
    client: TestClient, db_session: Session
) -> None:
    response = client.post(
        "/trades",
        json=trade_body(trade_id="S0", side="SELL", quantity="1", price="100"),
    )
    assert response.status_code == 409
    assert response.json()["code"] == "OVERSELL"

    db_session.expire_all()
    assert db_session.execute(text("SELECT COUNT(*) FROM trades")).scalar_one() == 0
    assert get_position(db_session, "BTC-USD") is None


def test_concurrent_sells_never_oversell() -> None:
    setup = get_session_factory()()
    try:
        ingest_trade(
            setup,
            TradeCreate.model_validate(
                trade_body(trade_id="SEED", side="BUY", quantity="10", price="100")
            ),
        )
        setup.commit()
    finally:
        setup.close()

    for _ in range(20):
        engine_session = get_session_factory()()
        try:
            engine_session.execute(text("TRUNCATE TABLE trades, positions, prices CASCADE"))
            engine_session.commit()
            ingest_trade(
                engine_session,
                TradeCreate.model_validate(
                    trade_body(trade_id="SEED", side="BUY", quantity="10", price="100")
                ),
            )
            engine_session.commit()
        finally:
            engine_session.close()

        barrier = Barrier(5)

        def worker(idx: int) -> str:
            barrier.wait()
            session = get_session_factory()()
            try:
                ingest_trade(
                    session,
                    TradeCreate.model_validate(
                        trade_body(
                            trade_id=f"S{idx}",
                            side="SELL",
                            quantity="3",
                            price="100",
                        )
                    ),
                )
                session.commit()
                return "ok"
            except OversellServiceError:
                session.rollback()
                return "oversell"
            finally:
                session.close()

        outcomes: list[str] = []
        with ThreadPoolExecutor(max_workers=5) as pool:
            futures = [pool.submit(worker, i) for i in range(5)]
            for fut in as_completed(futures):
                outcomes.append(fut.result())

        assert outcomes.count("ok") == 3, outcomes
        assert outcomes.count("oversell") == 2, outcomes

        check = get_session_factory()()
        try:
            pos = get_position(check, "BTC-USD")
            assert Decimal(pos.quantity) == Decimal("1")
        finally:
            check.close()


def test_oversell_on_one_symbol_does_not_affect_others(
    client: TestClient, db_session: Session
) -> None:
    assert client.post(
        "/trades",
        json=trade_body(trade_id="BTC-B", symbol="BTC-USD", quantity="10", side="BUY"),
    ).status_code == 201
    assert client.post(
        "/trades",
        json=trade_body(trade_id="ETH-B", symbol="ETH-USD", quantity="8", side="BUY"),
    ).status_code == 201

    rejected = client.post(
        "/trades",
        json=trade_body(
            trade_id="BTC-S",
            symbol="BTC-USD",
            side="SELL",
            quantity="15",
            price="100",
        ),
    )
    assert rejected.status_code == 409

    db_session.expire_all()
    eth = get_position(db_session, "ETH-USD")
    assert Decimal(eth.quantity) == Decimal("8")
    btc = get_position(db_session, "BTC-USD")
    assert Decimal(btc.quantity) == Decimal("10")
