# Trade Recorder & PnL Service

FastAPI + Postgres ledger with **average-cost** PnL, DB-enforced idempotency and oversell checks, and venue statement reconciliation.

## Quick start

Docker runs **Postgres only**. The API runs locally via Poetry.

```bash
cp .env.example .env
docker compose up -d
poetry install
poetry run uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

- Health: http://localhost:8000/health  
- OpenAPI: http://localhost:8000/docs  

Migrations run automatically on app startup (`alembic upgrade head`).

### Environment

| Variable | Purpose |
|---|---|
| `DATABASE_URL` | App / manual testing (`brc_trade`) |
| `TEST_DATABASE_URL` | Pytest only (`brc_trade_test`) — truncated between tests |
| `LOG_LEVEL` | Logging level (default `INFO`) |

Fresh Compose volumes create both databases via `docker/init-databases.sh`. On an **existing** volume:

```bash
docker compose exec db psql -U brc -d brc_trade -c "CREATE DATABASE brc_trade_test;"
```

### Tests

```bash
poetry run pytest
```

Requires Docker Postgres and `brc_trade_test`. Pytest never truncates `brc_trade`.

## API summary

| Method | Path | Purpose |
|---|---|---|
| `GET` | `/health` | Liveness |
| `POST` | `/trades` | Ingest trade (idempotent on `venue`+`trade_id`) |
| `PUT` | `/prices/{symbol}` | Set latest mark price |
| `GET` | `/positions/{symbol}` | Quantity, avg cost, realized PnL |
| `GET` | `/pnl/{symbol}` | Realized + unrealized (`null` if no mark) |
| `POST` | `/reconcile` | Diff a venue statement vs stored trades |

**Example ingest**

```bash
curl -s localhost:8000/trades -H 'Content-Type: application/json' -d '{
  "venue": "binance",
  "trade_id": "T-1001",
  "symbol": "BTC-USD",
  "side": "BUY",
  "quantity": "10",
  "price": "100",
  "traded_at": "2026-01-01T10:00:00Z"
}'
```

Send quantities/prices as **strings** (JSON floats are rejected). Timestamps must be timezone-aware.

Errors use `{ "code", "message", "details" }` (`VALIDATION_ERROR`, `OVERSELL`, `DUPLICATE_MISMATCH`, `NOT_FOUND`, …).

## Assumptions

- Cost basis: **average cost**; position is **per symbol across venues**
- Unique trade identity: `(venue, trade_id)`
- Arrival-order processing (not `traded_at` order)
- Reconcile window filters **stored** trades only (see `DESIGN.md`)

## Docs

- [`DESIGN.md`](DESIGN.md) — design, concurrency, trade-offs
- [`DECISIONS.md`](DECISIONS.md) — running decision log
- [`AI_USAGE.md`](AI_USAGE.md) — how AI was used
