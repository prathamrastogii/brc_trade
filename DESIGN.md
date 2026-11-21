# DESIGN.md — Trade Recorder & PnL Service

Polished design write-up for reviewers. Running decision history lives in `DECISIONS.md`.

## Problem

Internal ledger for multi-venue trading: ingest trades idempotently, maintain per-symbol positions, report realized/unrealized PnL, reject oversells, and reconcile venue statements against stored trades. Money must use `Decimal` (never float). Cost-basis method must be explicit.

## Architecture

Synchronous layered monolith — one FastAPI process, one Postgres:

```
API (routes, Pydantic, error mapping)
  → Service (owns the transaction)
      → Domain (pure functions)
      → Repository (SQLAlchemy Core / explicit SQL)
```

No message queue. Callers need an immediate accept/reject (especially oversell). Queues are at-least-once, still require DB idempotency and locking, and add infra/test cost without removing races.

**Scaling path (not implemented):** partition work by symbol (one consumer per partition), keep `UNIQUE (venue, trade_id)` as a safety net, return async results via status endpoint or callback.

## Cost basis: average cost

Position state per symbol (across all venues): `(quantity, avg_cost, realized_pnl)`.

| Action | Effect |
|---|---|
| BUY | `qty' = qty + q`; blend `avg' = (qty·avg + q·price) / qty'` |
| SELL | realize `(price − avg) · q`; `qty' = qty − q`; if `qty' = 0` then `avg' = 0` |
| Unrealized | `(mark − avg) · qty`; **`null` if no mark** (never coerce to 0) |

**Why average cost:** Spec asks for average cost; three numbers per symbol keeps the focus on concurrency correctness. FIFO changes only the realized/unrealized split (worked-example total PnL is the same). Logic is isolated in `apply_trade` so FIFO could be swapped later.

## Schema

| Table | Role |
|---|---|
| `trades` | Immutable ledger; PK `(venue, trade_id)` |
| `positions` | Mutable per-symbol state; locked with `FOR UPDATE` |
| `prices` | Latest mark per symbol |

Money columns are `NUMERIC` → Python `Decimal`.

## Ingest concurrency

One transaction per trade:

1. Ensure position row exists; `SELECT … FOR UPDATE`
2. `INSERT … ON CONFLICT DO NOTHING RETURNING`
3. If no row returned: load existing — identical payload → **200**; else → **409 `DUPLICATE_MISMATCH`**
4. Else apply domain; on oversell → rollback → **409 `OVERSELL`** (no trade row; `trade_id` reusable)
5. Else update position and commit → **201**

Idempotency is enforced by the unique constraint, not check-then-insert in Python. Oversell races on the same symbol are serialized by the row lock; different symbols do not block each other.

## API surface

| Method | Path | Notes |
|---|---|---|
| `GET` | `/health` | Liveness |
| `POST` | `/trades` | Ingest (idempotent) |
| `PUT` | `/prices/{symbol}` | Upsert mark |
| `GET` | `/positions/{symbol}` | 404 if unknown |
| `GET` | `/pnl/{symbol}` | unrealized may be `null` |
| `POST` | `/reconcile` | Read-only diff |

Errors: `{ "code", "message", "details" }` with codes such as `VALIDATION_ERROR`, `OVERSELL`, `DUPLICATE_MISMATCH`, `NOT_FOUND`.

**Normalization on write:** venue → lower, symbol → upper, side → `BUY`/`SELL`.

**Decimals:** JSON floats / NaN / Inf rejected; strings (and ints) accepted; compute without rounding; responses serialize as full-precision strings. Fixed-scale quantize is deferred.

**Timestamps:** timezone-aware only (`timestamptz`).

## Reconciliation

Match on `(venue, trade_id)`. Report `missing` (in statement, not in stored set), `extra` (in stored set, not in statement), `mismatched` (same key, field-level diffs). Decimals compared numerically (`100` == `100.00`).

**Window semantics:** optional `window_start` / `window_end` filter **stored** trades only. Statement rows are not filtered. A trade that exists in the DB outside the window but appears on the statement is reported as **missing** — the statement is compared to the ledger slice you asked for. Document this when using windows; clients should align statement contents with the window.

Extras are scoped to the statement venue (and window when provided), so other venues never appear as extra.

## Processing order

Trades are applied in **arrival order**, not by `traded_at`. Re-sequencing by venue timestamp would require replay and could invalidate earlier oversell decisions. Out-of-order timestamps are a known limitation; an event-sourced replay is the future fix.

## Trade-offs and limitations

- Avg cost cannot attribute sold lots; FIFO not implemented
- Same-symbol throughput serialized by row lock
- No batch ingest, no async workers, no CI workflow in MVP
- App not containerized (Docker = Postgres only); Poetry required locally
- Pytest uses a separate DB (`TEST_DATABASE_URL` / `brc_trade_test`) so truncate never wipes manual `brc_trade` data

## Testing

- Domain unit tests (avg-cost math, Decimal exactness)
- API validation, idempotency, oversell (including concurrent cases) against real Postgres
- Positions / PnL (worked example), reconcile (§5), window behavior, position replay invariants (§6 subset)
