# AI_USAGE.md — Usage log

Living notebook for the Trade Recorder & PnL Service.

---

## Summary

| Area | AI role | My role                                                                                |
|---|---|----------------------------------------------------------------------------------------|
| Requirements & concepts | Clarified symbol vs venue, avg cost vs FIFO, why queues are wrong | Confirmed understanding                                                                |
| Architecture & decisions | Core SQL, FOR UPDATE, 3 tables, normalize, Alembic, test DB split | Accepted / locked each decision, Proposed layered monolith                                                      |
| Implementation | Scaffolded layers, ingest SQL, domain, APIs, most tests under my direction | Reviewed critical paths (lock/`ON CONFLICT`, PnL math, concurrency, reconcile windows) |
| Docs | Helped structure DECISIONS / DESIGN / README / this file | DESIGN.md distilled from DECISIONS for submit                                          |

---

## How AI was used

### Planning (pre-code)

- Walked through the requirements: ingest, idempotency, positions, PnL, oversell, reconcile, Decimal rules.
- Clarified: unique key is `(venue, trade_id)`; positions/PnL/oversell are per symbol; avg cost vs FIFO only changes realized/unrealized split (total PnL same on the worked example).
- Rejected queue-based async worker as overkill for sync oversell rejection and for concurrency correctness.
- Locked stack and contracts into a build plan; Phase 0 created this log and `DECISIONS.md`.

### Implementation phases

#### Phase 0 — Notebooks

- AI drafted `DECISIONS.md` and `AI_USAGE.md` from the planning conversation.
- Treated as living notebooks updated each phase.

#### Phase 1 — Scaffold

- AI scaffolded Poetry/`pyproject.toml`, Docker Compose, Alembic baseline, FastAPI lifespan migration runner, `/health`, settings/session wiring.
- I own: verifying Postgres via Compose, local uvicorn `/health`, lifespan → `run_migrations()`.
- Follow-up: Docker = **Postgres only**; app via Poetry/uvicorn. Logging standard (no `print`).

#### Phase 2 — Schema + domain

- AI implemented Core tables, Alembic `0002`, pure average-cost `apply_trade` / `unrealized_pnl`, and §1 unit tests.
- I own: BUY blend, SELL realize, zero reset, OversellError; revision ids ≤32 chars.
- Hit: first revision id truncated `alembic_version` — shortened to `0002_trades_positions_prices`.

#### Phase 3 — Ingest

- AI implemented schemas, repository SQL, ingest service, `POST /trades`, error handlers, §2/§3/§3b tests.
- I own: lock→insert→apply transaction; oversell rollback leaves `trade_id` free; concurrent outcomes.
- Hit: validation handler crashed on `ValueError` in error `ctx` — sanitized for JSON.

#### Phase 4 — PnL APIs

- AI added price upsert, position/PnL reads, §4 tests including HTTP worked example.
- I own: unrealized = null without mark; avg-cost realized/unrealized split.
- Follow-up: whitespace path → 422; multi-symbol PnL totals; clarified serialize vs quantize.

#### Phase 5 — Reconcile

- AI implemented reconcile schemas, pure diff, `POST /reconcile`, §5 tests.
- I own: missing vs extra vs mismatched; venue-scoped extras.
- Follow-up: `TEST_DATABASE_URL` / `brc_trade_test` so pytest truncate does not wipe manual data.

#### Phase 6 — Polish

- AI drafted `DESIGN.md`, expanded README, window test, §6 invariant subset.
- I own: window semantics (“filters stored only”), and that concurrent invariant uses BUY-only because interleaved SELL plans are not arrival-safe under `created_at` ties.
- Hit: concurrent BUY/SELL replay failed when `created_at` collided and lexical `trade_id` reordered SELL before BUY — fixed with zero-padded ids + BUY-only concurrent case.

---

## Prompts / turns that mattered (high level)

| Topic | Outcome |
|---|---|
| Avg cost vs FIFO on worked example | Same total PnL (375); avg → realized 75 / unrealized 300 |
| Queue vs sync monolith | Chose sync; queue as DESIGN scaling note |
| Normalize + Alembic | Normalize on write; Alembic on startup |
| Three tables | trades + positions + prices |
| Test DB wipe | `TEST_DATABASE_URL` → `brc_trade_test` |
| Reconcile window | Documented stored-only filter |

---

## Phase checklist

- [x] Phase 0 — Seed this file + DECISIONS.md
- [x] Phase 1 — Scaffold
- [x] Phase 2 — Schema + domain
- [x] Phase 3 — Ingest
- [x] Phase 4 — PnL APIs
- [x] Phase 5 — Reconcile
- [x] Phase 6 — Polish