# F2 slice-01 — controlled staging inventory-receive vertical slice (plan)

**Status:** `PLANNING ONLY — NOT APPROVED, NOT IMPLEMENTED` (reviewed, one
correction pass applied)
**Pinned commit:** `main` `5898959`
**Scope:** plan an audit-verified, least-privilege, staging-only path that
creates the first inventory item in an empty shop through the real
application contract. No code, branch, privilege change, migration, flag,
Neon/Railway/Clerk contact, or write of any kind accompanies this plan.

---

## 1. Audit of every stock-increasing path

Approved 13-table staging schema (D-028): `shops`, `shop_members`,
`inventory_item`, `purchase_record`, `sale`, `acquisition_lot`,
`inventory_event`, `inventory_truth_cutover`,
`inventory_channel_observation`, `refund_record`, `return_record`,
`inventory_exception`, `inventory_adjustment`.

### A. Intake / staging commit
- Endpoints: `POST /api/v1/admin/intake/staging`,
  `POST /staging/{staging_id}/commit`, `POST /staging/commit-all`
  (`routers/admin.py` 136, 165, 179). Auth: `get_shop_context` (any member).
- Tables: `staging_item` (insert/read/delete), `inventory_item`,
  pricing helpers read `system_settings`/shipping rules; truth pair via
  source `staging_commit` (`core.py` 224).
- Schema: **`staging_item` is absent from the 13 tables and is on the
  forbidden list** (`inventory_live_schema/migrator.py` line 366 raises on
  it); `system_settings` also absent.
- Privileges today: SELECT-only for `stashtab_api`.
- Truth effect: lot+event pair, key `staging_commit:{shop}:{id}`.
- Gates: cutover `complete` required (`ensure_inventory_mutations_ready`).
- First SKU: yes in product terms, but missing supporting tables raise an
  uncontrolled 500 (`ProgrammingError`) rather than a clean error.
- Verdict: **DISQUALIFIED** — contradicts D-027 decisions 2–3.

### B. Trade receive (`POST /staging/apply-trades`, `logic/trades.py`)
- Auth: any member. Tables: `pending_trades`, `staging_item`,
  `inventory_item`, `purchase_record`, **`sync_outbox`**, truth pair
  `purchase_record`.
- Schema: `pending_trades`, `staging_item`, `sync_outbox` all absent;
  first two forbidden. Violates priority 5 (`sync_outbox`).
- Verdict: **DISQUALIFIED.**

### C. Purchase-record receive (direct)
- Accepted frozen logic exists: `record_purchase_receive` (`core.py` 193),
  canonical key `purchase_record:{shop}:{purchase_record.id}` (DESIGN.md
  §2 locks `source_pk` to `purchase_record.id`), atomic lot+event pair in
  one transaction, idempotent five-step retry rules, PG-proven in
  `tests/test_pg_acceptance.py` (receive at 287/335/467/498, conflicting
  retry `PermanentPairError` at 530, reconcile-zero at 451/482/599).
- **It never creates `inventory_item`** — the item is created by the
  caller. First-item proof: the accepted new-item branch of
  `logic/trades.py` lines 248–285 creates `InventoryItem`, flushes,
  inserts `PurchaseRecord`, then dual-writes; the new endpoint reuses
  exactly that pattern (§2).
- No HTTP endpoint exposes direct receive.
- Verdict: logic approved; endpoint + client-key resolution missing.

### D. Admin quantity adjustment (`PATCH /inventory/{item_id}`)
- Auth: any member; `Idempotency-Key` header → `core_adjust.apply_adjustment`
  (slice-03 accepted, on `main` via `c3647a4`).
- Tables: `inventory_item.stock` (update), `inventory_adjustment`,
  `inventory_event` — all present.
- Gates: `_reject_if_truth_frozen` → 503 `FEATURE_NOT_READY` until cutover
  complete (admin.py 1141).
- First SKU: **no** — 404 without an existing item. Fails priority 1.
- Verdict: **DISQUALIFIED as the receive slice.** Remains the authorized,
  evidence-preserving future correction path (requires its own later
  privilege unlock — §2 rollback note).

### E. CSV import (`POST /import`, `/import/patch-conditions`)
- Writes through `staging_item` (absent/forbidden). **DISQUALIFIED.**

### F. Other paths
- `POST /sales/placeholder-trade` → `pending_trades` (absent). Disqualified.
- `POST /inventory-truth/cutover` (owner-only): opens truth; on an empty
  shop writes only the cutover row `complete` — creates no inventory.
  Required precondition, not a receive path (§2 cutover procedure).
- Price approve/reject, resticker, label: no stock effect; several touch
  `sync_outbox`/`system_settings` (absent). Out of scope.

**Audit conclusion:** no existing endpoint satisfies priority 1 using
only the 13 approved tables. The smallest valid design adds **no table**,
one additive nullable column (§2), and a thin endpoint reusing accepted
frozen logic.

---

## 2. Proposal

### Chosen endpoint (new — requires named implementation unlock)
`POST /api/v1/admin/inventory/receive` in `routers/admin.py`.

**Request** (JSON): `{ "sku": str, "name": str, "quantity": int,
"unit_cost": number, "set_name"?: str, "sequence_number"?: str }` plus a
**required** `Idempotency-Key` header.

**Validation** (422 on failure): `sku` 1–50 chars, `name` 1–100 chars
(column limits), `set_name` ≤100, `sequence_number` ≤50; `quantity`
integer 1..1000; `unit_cost` 0.00..99999.99 rounded to 2 decimals;
`Idempotency-Key` UUIDv4 (36 chars).

**Authorization:** `get_shop_context` — verified Clerk bearer + shop
membership; `owner` **or** `staff` (ordinary receive, matching
DIRECTIVE-SLICE-03 wording for ordinary single-item operations). Cutover
itself stays owner-only. No frontend-only role restriction anywhere.

**Response** (200): `{ "success": true, "result": "created" | "no_op",
"inventory_item_id": int, "sku": str, "stock": int,
"purchase_record_id": int }`. **Errors (generic, no stack traces):**
401 no/invalid token; 403 not a member; 404 unknown shop hint conflict;
422 validation; 409 same key with a different payload; 503
`FEATURE_NOT_READY` when cutover is not complete; unclassified failures
return a generic 500 body with no SQL detail.

**Sequence, one transaction (commit only at the end):**
1. `ensure_inventory_mutations_ready` (503 until cutover `complete`).
2. Resolve `Idempotency-Key`: lookup `purchase_record` by
   `(shop_id, client_idempotency_key)`. Found → verify payload match
   (409 on mismatch) → return the original result as `no_op`, touching
   nothing else.
3. Insert `InventoryItem` (first SKU) or bump `stock` + weighted `cost`
   for an existing `(shop_id, sku)` — mirror of the accepted new-item
   branch `logic/trades.py` 248–285, **without** `SyncOutbox`.
4. Insert `PurchaseRecord` with `client_idempotency_key`, flush.
5. `record_purchase_receive` — frozen atomic lot+event dual-write.
   Concurrent duplicate on the partial unique index is treated as a
   retry (reload winner, `no_op`).

No Shopify, worker, notification, payment, Watch, price-approval, or
`sync_outbox` write. No external provider call. Money is snapshot
`float` per the live column contract; the truth lot stores
`Numeric(12,2)` per frozen DESIGN.md §3.

### Schema change — exactly one additive column
`purchase_record` gains `client_idempotency_key VARCHAR(36) NULL` plus a
partial unique index `UNIQUE (shop_id, client_idempotency_key) WHERE
client_idempotency_key IS NOT NULL` — the exact pattern already approved
on `inventory_adjustment` (`models_truth.py` 275–278, 347). No new
table. D-027 needs no amendment beyond recording this dependency per its
decision 4. The frozen canonical key is **unchanged**:
`purchase_record:{shop}:{purchase_record.id}`.

### Exact runtime grants (reviewed migrator, staging only)
For `stashtab_api`, replacing SELECT-only on exactly these objects:

| Object | Grants |
|---|---|
| `inventory_item` | `SELECT`, `INSERT`, `UPDATE (stock, cost)` |
| `purchase_record` | `SELECT`, `INSERT` |
| `acquisition_lot` | `SELECT`, `INSERT` |
| `inventory_event` | `SELECT`, `INSERT` |
| `inventory_item_id_seq`, `purchase_record_id_seq`, `acquisition_lot_id_seq`, `inventory_event_id_seq` | `USAGE` |

Column-scoped `UPDATE (stock, cost)` is the containment mechanism: every
other inventory write (price approve/reject, resticker, label, PATCH
price) fails closed on privilege. The runtime retains **no** `DELETE`,
`TRUNCATE`, DDL, `CREATEROLE`, ownership, or ability to assume/inherit
the migrator role (`_RUNTIME_ROLES` separation, MIGRATOR-ROLE-
PROVISIONING-GATE). All other 9 staging tables stay SELECT-only;
`_assert_select_only` becomes a per-table policy assert that fails any
deviation. Worker/readonly roles untouched (no table access).

### Append-only evidence protections (proof)
- Truth tables receive `INSERT + SELECT` only — no UPDATE/DELETE exists
  to grant; `_write_pair` (`core.py` 67–185) inserts only, never
  modifies rows.
- `inventory_item.stock`/`cost` are the operational snapshot by frozen
  design (`core.py` docstring: "Snapshot ... remain the operational
  source; this module never recomputes them") — updating them is not
  evidence mutation; every change stays derivable from events.
- No compensating path in this slice deletes or mutates evidence (§2
  rollback note).

### Route surface after cutover becomes `complete` (analysis)
`ensure_inventory_mutations_ready` stops raising for that shop. Effects:

| Route | Logically enabled? | Stays unavailable via |
|---|---|---|
| New receive endpoint | Yes (intended) | — |
| `PATCH /inventory/{id}` quantity | Gate passes | Missing `INSERT` on `inventory_adjustment` → controlled 503; no quantity UI exists |
| `/inventory/{id}/reverse-adjust` | Gate passes | Same missing grant → controlled 503; frontend locked |
| `/staging/apply-trades`, intake, commit, CSV import | Gate passes | Missing tables (`pending_trades`, `staging_item`, `sync_outbox`) → controlled 503; all frontend-locked |
| Price approve/reject, approve-under-5 | No cutover gate | Column-scoped privilege denial (`shop_listing_price`, `needs_update`) + missing `sync_outbox` → controlled 503; Price Updates screen is read-only |
| Resticker / label / settings / Shopify | No cutover gate | Column-scoped privilege denial or missing tables → controlled 503; all frontend-locked |

**Controlled-failure requirement (new code in the same unlock):** one
FastAPI exception handler maps SQLAlchemy `InsufficientPrivilege` and
`ProgrammingError` (undefined table) to 503 `FEATURE_NOT_READY` with a
generic body. Today only `FeatureNotReadyError` is handled
(`main.py` 43–51); without this handler those routes would leak raw
database 500s. No SQL text or role names appear in responses.

### Flags / cutover state
No feature flag exists for receive; the gate **is** cutover state.
Cutover `complete` is set on the single synthetic staging shop only;
every other shop keeps no cutover row → fail-closed 503, unchanged.

**Cutover procedure (named unlock, owner role):**
1. Pre-checks: synthetic shop exists with the executing owner as member;
   `GET /admin/inventory` count = 0; `/inventory-truth/reconcile`
   returns zero mismatches (vacuous for empty shop); staging build
   pinned to the merge SHA.
2. Owner executes `POST /api/v1/admin/inventory-truth/cutover`
   `{generation: 1}`; actor is the verified Clerk owner identity
   (`get_shop_context`); the cutover row stores `frozen_at`/`status` —
   it has **no actor column**, so the acting Clerk user id and request
   timestamp are recorded in the acceptance document (known audit gap,
   reported honestly).
3. Verify: `/inventory-truth/status` shows `complete`; reconcile = 0.
   Timeout is not green.
4. Recovery: a failed receive never touches the cutover row; cutover
   stays `complete` and receive is retryable. A cutover left in
   `locking` re-enters the same procedure on rerun (`run_cutover`);
   `failed_permanent` stops and requires a new owner decision.

### Synthetic test record and retention policy
One dedicated staging test shop; SKU `F2-TEST-0001`, name
"F2 Synthetic Test Card — staging proof", quantity 2, unit_cost 0.01.
**Default adopted:** retain `F2-TEST-0001` and all its evidence rows
(purchase record, lot, event) permanently as clearly labeled staging
proof; never present it as production data. No deletion, ever.

### Idempotency and concurrency proofs (frozen DESIGN.md §2)
1. **Same key, same payload:** step 2 resolves the existing purchase
   record → `no_op`; exactly one item/stock bump, one purchase row, one
   lot, one event.
2. **Same key, different payload:** step 2 payload mismatch → 409;
   if the mismatch somehow reaches the pair level, `PermanentPairError`
   → 409. Never silent, never merged (PG-proven, test_pg_acceptance 530).
3. **Concurrent identical requests:** one transaction wins the partial
   unique index; the loser's unique violation is treated as retry →
   reload → `no_op` (DESIGN §2 rule 5; `_write_pair` savepoint).
4. **Partial failure:** one commit at the end; any failure rolls back
   snapshot, purchase row, and pair together; `_write_pair`'s savepoint
   additionally isolates pair-only unique collisions.
5. **Retry after timeout:** client resends same key → resolves to the
   committed winner (`no_op`) or executes fresh if the winner never
   committed. No double stock bump is possible.

### Atomicity and reconciliation proof
Snapshot update, `purchase_record`, lot, and event commit in ONE
transaction; nothing is visible before commit. After success,
`GET /api/v1/admin/inventory-truth/reconcile` must return
`unaccounted_qty = 0` (event-derived remaining == snapshot stock —
`reconcile_shop`, `core.py` 419–445). Equivalent PG proofs already pass
twice on fresh DBs (slice-01 acceptance 14/14; test_pg_acceptance 451,
482, 599). The slice-11 screen shows the matched state; timeout is
never green.

### Rollback / correction (corrected by review)
The earlier "reverse-adjust rollback" claim is **removed**:
`reverse_adjustment` only reverses events that have an
`inventory_adjustment` row (`core_adjust.py` 236–241) — a bare `receive`
event has none, so that compensating path is not proven for receives.
This slice ships **no compensating write and no deletion**. If a receive
must ever be corrected, the authorized route is a slice-03 signed
adjustment (`PATCH` with `stock_delta`, reason code, verified actor,
append-only evidence) under a separately named privilege unlock
(`INSERT` on `inventory_adjustment`); until then corrections stay
privilege-denied, which is the intended containment.

---

## 3. Governance classification (review finding)

- **No frozen inventory-truth amendment is required**: receive-first
  dual-write, canonical key format, retry rules, and cutover semantics
  are used exactly as frozen; truth table shapes are untouched.
- **New staging-plan decision required (D-0xx, additive):** the
  `purchase_record.client_idempotency_key` column + partial unique
  index, and the least-privilege grant policy replacing SELECT-only on
  the four named objects — recorded like D-027/D-028, staging-only.
- **Named implementation unlock:** the endpoint, the controlled-failure
  handler, and migrator changes (directive + acceptance pattern).
- **Named provisioning unlock:** reviewed migrator run on staging Neon
  (migrator role; runtime role never applies schema).
- **Named cutover unlock:** gen-1 cutover on the synthetic shop.

### Startup schema creation stays off (proof)
`init_db()` and `bootstrap_legacy_schema` raise in staging/production
(`database.py` 43–63, `startup_schema_mutation_forbidden`); truth models
live on `TruthBase`, invisible to application `create_all`
(`models_truth.py` header). The additive column and grants are applied
**only** by the reviewed migrator/owner workflow.

### PostgreSQL acceptance tests (required before acceptance)
1. Permissions as `stashtab_api`: INSERT/UPDATE(stock,cost) succeed on
   the four objects; DELETE/TRUNCATE on any staging table denied;
   UPDATE on `inventory_item.price`/`sticker_price` denied; readonly
   role denied everything; `SET ROLE stashtab_migrator` denied.
2. First-SKU receive in an empty shop → item, purchase row, lot, event
   present; reconcile zero.
3. Idempotent retry → `no_op`, counts unchanged; conflicting retry →
   409/`PermanentPairError`.
4. Concurrent identical receives (two sessions) → exactly one pair.
5. Injected failure mid-transaction → zero rows committed.
6. Cross-shop denial: other shop's token/hint → 403/404, zero data leak.
7. Unrelated routes after cutover (approve-update, resticker, PATCH
   price, apply-trades) → controlled 503 `FEATURE_NOT_READY`, never a
   raw privilege/undefined-table 500.
8. Missing cutover on a second shop → receive 503, fail-closed.

---

## 4. Remaining human decisions and named unlocks

1. **D-0xx staging decision:** approve the additive
   `client_idempotency_key` column + partial unique index on
   `purchase_record`, and the four-object least-privilege grant policy
   (column-scoped UPDATE, no DELETE/TRUNCATE/DDL, staging only).
2. **Named implementation unlock:** thin receive endpoint + controlled
   503 error handler + migrator changes, per this plan.
3. **Named provisioning unlock:** reviewed migrator apply on staging
   Neon; production stays SELECT-only behind
   MIGRATOR-ROLE-PROVISIONING-GATE.
4. **Named cutover unlock:** gen-1 cutover on the synthetic shop with
   the §2 pre-checks and acceptance-recorded actor evidence; decide
   whether standing gate 4 (runbook) applies pre-staging.
5. **Retention confirmation:** keep `F2-TEST-0001` and its evidence
   permanently as labeled staging proof.

Frozen inventory-truth 1.2.0 already authorizes the receive-first
dual-write, canonical keys, retry rules, and cutover semantics used
here; it does **not** authorize the HTTP surface, the additive column,
or the privilege change — those are the decisions above. No production
authorization is granted anywhere in this plan.

**This plan changes nothing. No branch, code, migration, flag, cloud
contact, or write has occurred.**
