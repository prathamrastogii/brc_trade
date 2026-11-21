# DECISIONS.md — Running decision log

Living notebook for the Trade Recorder & PnL Service.
Update after every phase. Distill into `DESIGN.md` near the end — do not reconstruct from memory.

---

## Status snapshot

| # | Decision | Status | Notes |
|---|---|---|---|
| 1 | FastAPI | Locked | HTTP API framework |
| 2 | Average cost (not FIFO) | Locked | Spec asks for avg cost; isolate in pure function |
| 3 | Poetry for packaging | Locked | Pin via poetry.lock; reviewer runs app with Poetry locally |
| 4 | Docker Postgres only (app runs locally) | Locked | Real DB constraints/locks; API via Poetry/uvicorn — not containerized |
| 5 | Sync layered monolith (no queue) | Locked | Oversell needs sync reject; correctness from DB not topology |
| 6 | Sync SQLAlchemy + psycopg | Locked | Simpler transaction/lock reasoning |
| 7 | SQLAlchemy Core / explicit SQL for ingest | Locked | Defend `ON CONFLICT` + `FOR UPDATE` in interview |
| 8 | `SELECT … FOR UPDATE` on position row | Locked | Serializes trades per symbol |
| 9 | Position per symbol (all venues) | Locked | Matches spec wording; state in DESIGN.md |
| 10 | Arrival-order processing | Locked | No timestamp re-sequencing; limitation documented |
| 11 | Normalize on write | Locked | `venue` → lowercase, `symbol` → uppercase, `side` → uppercase BUY/SELL |
| 12 | Alembic migrations on startup | Locked | `alembic upgrade head` in FastAPI lifespan |
| 13 | Three tables: trades, positions, prices | Locked | One table cannot support ledger + lockable position + marks |
| 14 | Behavior contracts (errors / decimals / reconcile) | Locked | See Behavior contracts below |
| 15 | Batch ingest endpoint | Deferred | Skip unless time remains |
| 16 | FIFO cost basis | Out of scope | Possible later via domain swap |
| 17 | `logging` everywhere; no `print` | Locked | Central `setup_logging`; `getLogger(__name__)` per module |
| 18 | Separate `TEST_DATABASE_URL` | Locked | Pytest uses `brc_trade_test` + truncate; app/manual use `brc_trade` |

---

## Chronological log

### Phase 0 seed (planning)

**Context:** Trade Recorder & PnL Service (FastAPI + Postgres). Priorities: concurrency correctness at the DB, Decimal/financial correctness, and design judgment captured in DESIGN.md.

#### Architecture

- **Decision:** Synchronous layered monolith — API → Service (owns transaction) → Domain (pure) + Repository (explicit SQL). No message queue.
- **Why:** Callers need immediate accept/reject (oversell). Queues are at-least-once, still need DB idempotency/locks, and add infra/test burden without removing races.
- **Trade-off:** Throughput bounded by single Postgres. Scaling path (for DESIGN.md): partition by symbol, one consumer per partition, unique constraint as safety net, async result via status/callback.

#### Cost basis

- **Decision:** Average cost. Position state per symbol: `(quantity, avg_cost, realized_pnl)`.
- **Why:** Spec asks for average cost; only three numbers per symbol; time goes into concurrency correctness.
- **Trade-off:** Cannot attribute which lot was sold; realized/unrealized split differs from FIFO (total PnL same). Mitigation: pure `apply_trade` so FIFO can be added later.

#### Packaging & runtime

- **Decision:** Poetry for the app locally; Docker Compose for **Postgres only**. Tests hit real Postgres.
- **Why:** Pin exact versions; real DB constraints/locks under evaluation. App process stays under local control (uvicorn), not nested in a container.
- **Trade-off:** Reviewer needs Poetry (or equivalent) locally; Docker only for the database — document in README.

#### Concurrency primitives

- **Idempotency:** `UNIQUE (venue, trade_id)` + `INSERT … ON CONFLICT DO NOTHING RETURNING`. Never check-then-insert in Python.
- **Oversell:** One transaction: lock position (`FOR UPDATE`), insert trade, apply domain, rollback if qty would go negative. Same-symbol SELLs serialize; different symbols do not block each other.
- **Unique key is `(venue, trade_id)`**, not venue+symbol+qty — payload fields must not be part of the identity.

#### Identifier normalization

- **Decision:** Normalize on write — `venue.strip().lower()`, `symbol.strip().upper()` — before unique-key checks and storage.
- **Why:** Avoid duplicate keys from casing (`Binance` vs `binance`); reconcile matches stay consistent.
- **Trade-off:** Original client casing is not preserved. Document that clients must not rely on case.

#### Migrations

- **Decision:** Alembic. FastAPI lifespan runs `alembic upgrade head` (idempotent if already at head).
- **Why:** Startup upgrade avoids a hand-rolled “if table exists” path that drifts from migration history.
- **Trade-off:** Slightly more setup than a single `schema.sql`. Worth it for clarity of evolution.

#### Schema (three tables)

| Table | Role |
|---|---|
| `trades` | Immutable ledger; PK `(venue, trade_id)` |
| `positions` | Mutable per-symbol state; locked with `FOR UPDATE` |
| `prices` | Latest mark per symbol for unrealized PnL |

**Why not one table:** Ledger history, lockable aggregated position, and mark prices are different lifecycles. Deriving position only from trades loses a single lock target. Putting `latest_price` on `positions` couples marks to having a position.

**Column sketch (money = NUMERIC → Python Decimal):**

```
trades:     venue, trade_id, symbol, side, quantity, price, traded_at, created_at
positions:  symbol PK, quantity, avg_cost, realized_pnl
prices:     symbol PK, price, updated_at
```

#### Behavior contracts

| Topic | Choice |
|---|---|
| Identical duplicate | 200 with existing trade |
| Duplicate, different payload | 409 `DUPLICATE_MISMATCH` |
| Oversell | 409 `OVERSELL`; nothing stored; position unchanged |
| No latest price | unrealized = `null` (not 0) |
| Decimals | strings accepted; floats / NaN / Inf rejected; no rounding in compute; API serializes as full-precision strings (`format(..., "f")`). Fixed-scale quantize deferred unless a product scale is required. |
| Timestamp | timezone-aware; store `timestamptz` |
| Reconcile | match `(venue, trade_id)`; missing / extra / mismatched with field diffs; Decimal numeric compare; extra scoped to statement venue. Optional window filters **stored** trades only (statement rows outside the window that exist in DB → `missing`) |
| Errors | `{ code, message, details }` with machine-readable codes |

#### Processing order

- **Decision:** Arrival order (processing order), not trade-timestamp order.
- **Why:** Backdated trades would force replay and could invalidate earlier oversell decisions.
- **Trade-off / limitation:** Out-of-order venue timestamps are not re-sequenced. Fix path: event-sourced replay (note in DESIGN.md).

#### Logging

- **Decision:** Standard library `logging` only; no `print()` in application code.
- **How:** `app/logging_config.setup_logging(level)` once at startup; each module `logger = get_logger(__name__)`. Level via `LOG_LEVEL` (default `INFO`).
- **Why:** Structured, level-filterable output for local run and interviews; avoids ad-hoc prints that get left in.

#### Explicitly deferred / out of scope (MVP)

- Batch ingest endpoint
- FIFO lots / per-(venue, symbol) positions
- Queues / async workers
- CI workflow (nice-to-have if time remains)

---

## Phase checklist (append notes below as you go)

- [x] Phase 0 — Seed notebooks
- [x] Phase 1 — Scaffold (Poetry, Docker, Alembic, empty FastAPI)
- [x] Phase 2 — Schema + domain unit tests
- [x] Phase 3 — Ingest transaction + concurrency tests
- [x] Phase 4 — Prices / positions / PnL APIs + worked example
- [x] Phase 5 — Reconcile
- [x] Phase 6 — README + DESIGN.md + final AI_USAGE pass

### Phase notes

#### Phase 1 scaffold

- Poetry 2.5.2 + Python 3.12; `virtualenvs.in-project = true` → `.venv/`
- Layout: `app/{api,schemas,services,domain,db}`, Alembic, Docker Compose (**Postgres 16 only**)
- App is **not** containerized — run with `poetry run uvicorn` locally
- Startup: FastAPI lifespan calls `alembic upgrade head` (`app/db/migrate.py`)
- Baseline revision `0001_phase1_baseline` is empty; tables in Phase 2
- Verified: Compose brings up Postgres; local uvicorn → `/health` ok; Alembic applied; `pytest` green
- Settings via `DATABASE_URL` / `.env` (`pydantic-settings`)
- Follow-up: removed app service + `Dockerfile` so Docker only supports Postgres
- Follow-up: logging standard — `app/logging_config.py`, `LOG_LEVEL` setting; no `print()` in app code; modules use `logger = get_logger(__name__)`

#### Phase 2 schema + domain

- Tables: `trades`, `positions`, `prices` via Alembic `0002_trades_positions_prices` (revision id kept ≤32 chars for `alembic_version`)
- Core definitions in `app/db/tables.py`; `alembic/env.py` uses `metadata` for autogenerate
- Domain: `apply_trade` / `unrealized_pnl` in `app/domain/avg_cost.py`; `OversellError` on sell > qty; qty→0 clears avg_cost
- Unit tests: `tests/test_domain_avg_cost.py` (§1 suite) — worked example + boundaries; no DB

#### Phase 3 ingest

- `POST /trades`: lock position (`FOR UPDATE`) → `INSERT ON CONFLICT DO NOTHING RETURNING` → domain apply → update position
- Contracts implemented: 201 create, 200 identical duplicate, 409 `DUPLICATE_MISMATCH`, 409 `OVERSELL` (full rollback; trade_id reusable)
- Side normalized to uppercase (`buy` → `BUY`); venue lower / symbol upper
- Strict decimals: JSON floats / NaN / Inf rejected (strings/ints only)
- Errors: `{code, message, details}` via handlers in `app/api/errors.py`
- Tests: §2 validation, §3 idempotency (incl. 20-way concurrent dup), §3b oversell (incl. 5-way concurrent sells ×20)

#### Phase 4 prices / positions / PnL

- `PUT /prices/{symbol}` upsert mark; `GET /positions/{symbol}`; `GET /pnl/{symbol}`
- Missing position → 404 `NOT_FOUND`; no mark → `unrealized_pnl` / `mark_price` are `null` (not 0)
- Position is per symbol across venues (confirmed via §4 test)
- HTTP worked example: qty 15, avg 105, realized 75, unrealized 300
- Follow-up fixes: whitespace-only symbol path → 422 `VALIDATION_ERROR`; multi-symbol PnL total test; softened “quantize at output” to full-precision string serialize; status table Docker/Poetry wording aligned

#### Phase 5 reconcile

- `POST /reconcile`: venue + statement trades (+ optional `window_start` / `window_end`)
- Match on `(venue, trade_id)`; buckets missing / extra / mismatched with field diffs
- Decimal numeric compare (`100` == `100.00`); extra scoped to statement venue (+ window)
- Pure diff in `app/domain/reconcile.py`; service is read-only
- §5 acceptance tests green

#### Separate test database

- `TEST_DATABASE_URL` → `brc_trade_test`; conftest forces `DATABASE_URL` to that for pytest only
- Truncate guarded: refuses if engine URL does not contain `brc_trade_test`
- `docker/init-databases.sh` creates test DB on fresh volumes; existing volume needs one-time `CREATE DATABASE`

#### Phase 6 polish

- Wrote `DESIGN.md` + expanded README
- Documented reconcile window semantics (filters stored only)
- Added window test + §6 invariant subset (replay, rejects, concurrent buys, duplicates, fractional)
- Arrival-order replay uses `created_at` (tie-break venue, trade_id); concurrent invariant is BUY-only to avoid interleaving vs sequential SELL plans