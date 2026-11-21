from __future__ import annotations

import random
from concurrent.futures import ThreadPoolExecutor, as_completed
from decimal import Decimal
from threading import Barrier

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.db import repository as repo
from app.db.session import get_session_factory
from app.domain import PositionState, Side, TradeFill, apply_trade
from app.schemas.trades import TradeCreate
from app.services.ingest import ingest_trade
from tests.helpers import trade_body


def _replay_positions(session: Session) -> dict[str, PositionState]:
    states: dict[str, PositionState] = {}
    for row in repo.list_all_trades_arrival_order(session):
        symbol = row.symbol
        states.setdefault(symbol, PositionState.empty(symbol))
        states[symbol] = apply_trade(
            states[symbol],
            TradeFill(
                symbol=symbol,
                side=Side(row.side),
                quantity=Decimal(row.quantity),
                price=Decimal(row.price),
            ),
        )
    return states


def _assert_replay_matches_db(session: Session) -> None:
    session.expire_all()
    replayed = _replay_positions(session)
    stored_rows = repo.list_all_positions(session)
    stored = {
        row.symbol: PositionState(
            symbol=row.symbol,
            quantity=Decimal(row.quantity),
            avg_cost=Decimal(row.avg_cost),
            realized_pnl=Decimal(row.realized_pnl),
        )
        for row in stored_rows
    }
    assert set(replayed) == set(stored)
    for symbol, expected in replayed.items():
        actual = stored[symbol]
        assert actual.quantity == expected.quantity, symbol
        assert actual.avg_cost == expected.avg_cost, symbol
        assert actual.realized_pnl == expected.realized_pnl, symbol


def _random_valid_batch(
    *,
    n: int,
    symbols: list[str],
    seed: int,
    max_decimals: int = 2,
) -> list[dict]:
    rng = random.Random(seed)
    open_qty: dict[str, Decimal] = {s: Decimal("0") for s in symbols}
    trades: list[dict] = []
    for i in range(n):
        symbol = rng.choice(symbols)
        if open_qty[symbol] == 0 or rng.random() < 0.55:
            side = "BUY"
            qty = _rand_qty(rng, max_decimals)
            open_qty[symbol] += qty
        else:
            side = "SELL"
            qty = _rand_qty(rng, max_decimals, max_value=open_qty[symbol])
            if qty <= 0:
                side = "BUY"
                qty = _rand_qty(rng, max_decimals)
                open_qty[symbol] += qty
            else:
                open_qty[symbol] -= qty
        price = _rand_qty(rng, max_decimals, min_value=Decimal("1"), max_value=Decimal("500"))
        trades.append(
            trade_body(
                trade_id=f"R-{seed}-{i:05d}",
                symbol=symbol,
                side=side,
                quantity=format(qty, "f"),
                price=format(price, "f"),
                traded_at=f"2026-01-01T10:{i % 60:02d}:00Z",
            )
        )
    return trades


def _rand_qty(
    rng: random.Random,
    max_decimals: int,
    *,
    min_value: Decimal = Decimal("0.00000001"),
    max_value: Decimal | None = None,
) -> Decimal:
    if max_value is not None and max_value <= 0:
        return Decimal("0")
    scale = 10**max_decimals
    hi = int((max_value if max_value is not None else Decimal("20")) * scale)
    lo = max(1, int(min_value * scale))
    if hi < lo:
        return Decimal("0")
    return Decimal(rng.randint(lo, hi)) / Decimal(scale)


def test_replay_of_randomized_batch_matches_stored_positions(
    client: TestClient, db_session: Session
) -> None:
    batch = _random_valid_batch(n=120, symbols=["BTC-USD", "ETH-USD", "SOL-USD"], seed=42)
    for body in batch:
        assert client.post("/trades", json=body).status_code == 201, body
    _assert_replay_matches_db(db_session)


def test_invariant_holds_after_rejected_trades(
    client: TestClient, db_session: Session
) -> None:
    batch = _random_valid_batch(n=40, symbols=["BTC-USD", "ETH-USD"], seed=7)
    for body in batch:
        assert client.post("/trades", json=body).status_code == 201

    assert client.post("/trades", json=trade_body(quantity="0")).status_code == 422
    assert (
        client.post(
            "/trades",
            json=trade_body(
                trade_id="OVER-1",
                symbol="BTC-USD",
                side="SELL",
                quantity="999999",
                price="1",
            ),
        ).status_code
        == 409
    )
    _assert_replay_matches_db(db_session)


def test_invariant_holds_after_concurrent_submissions(db_session: Session) -> None:
    batch = [
        trade_body(
            trade_id=f"CBUY-{i:05d}",
            symbol=["BTC-USD", "ETH-USD", "SOL-USD"][i % 3],
            side="BUY",
            quantity="1.25",
            price="100",
            traded_at=f"2026-01-02T10:00:{i % 60:02d}Z",
        )
        for i in range(60)
    ]
    barrier = Barrier(8)

    def worker(chunk: list[dict]) -> None:
        barrier.wait()
        for body in chunk:
            session = get_session_factory()()
            try:
                ingest_trade(session, TradeCreate.model_validate(body))
                session.commit()
            finally:
                session.close()

    chunks = [batch[i::8] for i in range(8)]
    with ThreadPoolExecutor(max_workers=8) as pool:
        futures = [pool.submit(worker, chunk) for chunk in chunks]
        for fut in as_completed(futures):
            fut.result()

    _assert_replay_matches_db(db_session)


def test_invariant_holds_with_duplicates_in_the_stream(
    client: TestClient, db_session: Session
) -> None:
    batch = _random_valid_batch(n=50, symbols=["BTC-USD"], seed=3)
    for body in batch:
        assert client.post("/trades", json=body).status_code == 201
    for body in batch[::3]:
        assert client.post("/trades", json=body).status_code == 200
    _assert_replay_matches_db(db_session)


def test_invariant_holds_with_fractional_decimal_quantities(
    client: TestClient, db_session: Session
) -> None:
    batch = _random_valid_batch(
        n=80,
        symbols=["BTC-USD", "ETH-USD"],
        seed=123,
        max_decimals=8,
    )
    for body in batch:
        assert client.post("/trades", json=body).status_code == 201, body
    _assert_replay_matches_db(db_session)
