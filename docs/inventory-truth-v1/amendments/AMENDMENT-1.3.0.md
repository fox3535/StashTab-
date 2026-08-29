# STASHTAB-INVENTORY-TRUTH-001 / AMENDMENT-1.3.0 — human vote packet

**Amendment identifier:** `STASHTAB-INVENTORY-TRUTH-001 / AMENDMENT-1.3.0`
**Status:** `PROPOSED — NOT APPROVED — NOT FROZEN`
**Parent:** version `1.2.0` (frozen 2026-08-24; manifest
`docs/inventory-truth-v1/freezes/FREEZE-1.2.0.json`)
**Proposed resulting version:** `1.3.0`
**Frozen v1.0.0 / v1.1.0 / v1.2.0 bodies:** not edited by this packet.
This draft is additive-only with respect to versions 1.0.0, 1.1.0, and
1.2.0: no frozen sentence is deleted or rewritten; every change is an
appended envelope section, an appended acceptance list, or a pointer
record, applied only after a later human vote.
**Rule:** CONTRACT §6 (versioned proposal, independent review against
the frozen bodies, updated acceptance tests where behavior changes,
named human approval, new semantic version and new freeze record).
**Does not authorize implementation, schema apply, privilege change,
cutover, merge to `main`, production DDL, or deploy.**

This packet is exact and closed. There are no optional forks.

Planning basis: `docs/frontend-recovery-v1/PLAN-F2-SLICE-01-CONTROLLED-
RECEIVE.md` (reviewed plan; planning only, not approved), on branch
`planning/f2-controlled-receive-amendment-1.3.0`.

## 0. Compatibility result (bounded check)

Checked against frozen DESIGN/MIGRATION/TESTS v1.2.0, CONTRACT v1.2.0,
AMENDMENT-1.1.0/1.2.0, slice-01/02/03 acceptances, and the restored F2
plan.

| Constraint | Result |
| --- | --- |
| Remaining = `SUM(quantity_delta)` | Preserved. Receive writes one `receive` event; equation untouched. |
| Canonical key grammar `{source}:{shop_id}:{source_pk}` | Unchanged. `purchase_record` keeps `source_pk = purchase_record.id`. No new source, no new suffix. |
| Live-table migration compatibility ("indexes only, not column rewrites") | Extended additively by exactly one nullable column + one partial unique index, authorized only by this amendment's vote. No column rewrite, no type change, no drop. |
| Additive envelopes (1.1.0 outbound, 1.2.0 adjust) | Unchanged; a third envelope section is appended. |
| `create_all` must not create truth tables | Unchanged. The live column belongs to the live migrator, not application metadata. |
| Append-only truth evidence + migrator-only DDL | Same discipline; truth tables gain INSERT+SELECT runtime grants only, never UPDATE/DELETE. |
| AMENDMENT-1.2.0 decision 2 ("New items require a later receive/lot path") | This amendment is exactly that later receive path, lot-required, receive-first. |
| Cutover order and fail-closed receive | Unchanged. Live receive still rejected until a completed gen:1 cutover for that shop. |
| Plan §3 wording ("no amendment required") | Reconciled: truth semantics indeed need no amendment; the amendment vehicle is required because a live-table column exceeds the frozen migration envelope. Owner chose this vehicle. No frozen text is contradicted. |

**Blocker:** none for the vote. Implementation remains blocked until the
vote plus four later named unlocks (§17).

## 1. Closed decisions incorporated (owner, pre-vote)

1. Additive `purchase_record.client_idempotency_key` column with
   shop-scoped partial uniqueness for non-null keys.
2. Receive authorization is verified Clerk bearer + shop membership;
   `owner` and `staff` may receive. The first staging smoke uses an
   owner.
3. Only the plan's exact least-privilege grants: column-scoped
   `UPDATE (stock, cost)`, the named INSERT/SELECT grants, and exact
   sequence USAGE. No DELETE, TRUNCATE, DDL, ownership, role
   administration, or migrator-role assumption.
4. Retain `F2-TEST-0001` and all its evidence permanently as clearly
   labeled staging proof. Never delete or rewrite evidence.
5. Implementation, staging privilege/schema apply, and cutover remain
   three separate named unlocks.
6. No production authorization is granted.

## 2. Affected frozen clauses (exact)

On approval only, apply the diffs in §14 to:

- `MIGRATION.md` — appended F2 controlled-receive envelope section and
  one additive compatibility sentence for the live column.
- `TESTS.md` — appended F2 acceptance-test list.
- `CONTRACT.md` — header version pointer, §7 gate-state line, and new
  §10 freeze-record pointer (no self-hash; §2, §8, §9 stay unchanged).
- `DESIGN.md` — **no diff.** Canonical sources, key grammar, retry
  rules, and quantity types are untouched.

## 3. Canonical truth source keys — confirmation

`purchase_record:{shop}:{purchase_record_id}` remains the sole and
unchanged truth source key for receives (DESIGN.md §2 locks `source_pk`
to `purchase_record.id`; backfill A shares the same key). The new
client key:

- lives on the **live** `purchase_record` row only;
- is never concatenated into a truth idempotency key;
- introduces no new `source`, no new suffix, and no key-grammar change;
- resolves retries to the same `purchase_record.id`, which keeps the
  live dual-write and any future backfill on identical keys.

## 4. `purchase_record.client_idempotency_key` (closed)

Migrator-only DDL on the live parent table:

| Property | Value |
| --- | --- |
| Column | `client_idempotency_key VARCHAR(36) NULL` |
| Constraint | `UNIQUE (shop_id, client_idempotency_key) WHERE client_idempotency_key IS NOT NULL` (partial, shop-scoped) |
| Index name | `uq_purchase_record_shop_client_key` |
| Pattern source | identical to the approved `inventory_adjustment` partial unique (AMENDMENT-1.2.0 §4 / MIGRATION slice-03 envelope) |
| Existing rows | stay NULL; backfill never writes the column |

**Payload-hash / idempotency evidence relationship.** No second column
is added. The canonical receive payload is the field tuple
`(sku, quantity, unit_cost)` rounded and ordered exactly as validated
(§5). Its evidence digest is `SHA-256` of that canonical tuple, computed
client-side for logs and recomputed server-side on replay from the
stored `purchase_record` columns (`sku`, `quantity`, `cost_per_unit`).
Replay with a different digest for the same `(shop_id,
client_idempotency_key)` returns 409 and writes nothing. The digest is
evidence-correlation only; the truth pair's authority remains the frozen
canonical key on `(shop_id, idempotency_key)` in lot and event.

**Migration order (one reviewed live-schema migrator transaction):**
1. `ALTER TABLE purchase_record ADD COLUMN IF NOT EXISTS
   client_idempotency_key VARCHAR(36)`;
2. `CREATE UNIQUE INDEX IF NOT EXISTS uq_purchase_record_shop_client_key
   ...` (partial);
3. runtime grant apply per §7;
4. policy assert (per-table privilege verification replacing the
   SELECT-only assert for exactly the four named objects).
Rerun is a no-op. Injected mid-failure leaves no partial column/index
or grant drift; the transaction commits all or nothing. Live parents
are altered before any truth-table step, preserving the frozen order
(live parents → truth DDL → grants).

## 5. Thin controlled-receive endpoint (closed contract)

`POST /api/v1/admin/inventory/receive` in `routers/admin.py` — new
surface, authorized only by the vote plus the later implementation
unlock.

**Authentication / authorization:** verified Clerk bearer +
`require_membership` via `get_shop_context`; `owner` or `staff` may
receive (ordinary operation per DIRECTIVE-SLICE-03 wording). `X-Shop-Id`
remains an untrusted hint. The dev bypass that `get_shop_context` can
honor when explicitly allowed MUST be off in staging (fail-closed
identity, D-025). Cutover stays owner-only. No frontend-only role
restriction.

**Request (JSON) + required header:**

| Field | Type | Rule |
| --- | --- | --- |
| `sku` | str | 1–50 chars, required |
| `name` | str | 1–100 chars, required |
| `quantity` | int | 1..1000, required |
| `unit_cost` | number | 0.00..99999.99, rounded 2dp, required |
| `set_name` | str | ≤100, optional |
| `sequence_number` | str | ≤50, optional |
| `Idempotency-Key` header | UUIDv4 (36 chars) | required |

**One transaction, commit only at the end:**
1. `ensure_inventory_mutations_ready` → 503 until cutover `complete`.
2. Resolve `Idempotency-Key` against
   `(shop_id, client_idempotency_key)`; found → digest match → return
   original result `no_op` (touch nothing); digest mismatch → 409.
3. Insert `InventoryItem` (first SKU) or bump `stock` + weighted `cost`
   for an existing `(shop_id, sku)` — mirror of the accepted new-item
   branch `logic/trades.py` 248–285, **without** `SyncOutbox`. The item
   is created by this step; `record_purchase_receive` never creates
   items.
4. Insert `PurchaseRecord` with `client_idempotency_key`, flush.
5. `record_purchase_receive` — frozen atomic lot+event dual-write.

**Response (200):** `{ "success": true, "result": "created" | "no_op",
"inventory_item_id": int, "sku": str, "stock": int,
"purchase_record_id": int }`.

**Status codes (generic failures, no stack traces, no SQL text, no role
names):** 401 no/invalid token; 403 not a member; 404 shop-hint
conflict path; 422 validation; 409 key conflict; 503 `FEATURE_NOT_READY`
when cutover is not complete; unclassified failure → generic 500 body.

**Exclusions (never written by this endpoint):** Shopify, workers,
notifications, payments, Watch, price approval, `sync_outbox`, CSV,
trade tables, checkout/sales, adjustments. No external provider call.

## 6. Atomicity and replay semantics (closed)

- **Atomic:** snapshot update/bump, `purchase_record`, lot, and event
  commit in ONE transaction; nothing visible before commit.
- **Idempotent replay:** same key, same payload → `no_op`; exactly one
  item/stock effect, one purchase row, one lot, one event.
- **Conflict:** same key, different payload → 409 at step 2; if a
  mismatch ever reached the pair level, `PermanentPairError` → 409.
  Never silent, never merged.
- **Concurrency:** one transaction wins the partial unique index; the
  loser's ENTIRE uncommitted transaction — including its item insert or
  stock bump — rolls back (commit-at-end design), the request then
  re-resolves by client key against the winner and returns `no_op`
  (DESIGN §2 rule 5; `_write_pair` savepoint). No in-transaction reload
  of a dirty snapshot is permitted.
- **Timeout:** client timeout never commits twice — resend resolves by
  key to `no_op` or executes fresh if nothing committed. Timeout is
  never reported as green.
- **Partial failure:** any failure rolls back all four objects; the
  pair savepoint additionally isolates pair-only unique collisions.
- **Reconciliation proof:** after success,
  `GET /api/v1/admin/inventory-truth/reconcile` returns
  `unaccounted_qty = 0` (event-derived remaining == snapshot stock).

## 7. Runtime grant envelope (closed, staging only)

For `stashtab_api`, replacing SELECT-only on exactly these objects:

| Object | Grants |
| --- | --- |
| `inventory_item` | `SELECT`, `INSERT`, `UPDATE (stock, cost)` |
| `purchase_record` | `SELECT`, `INSERT` |
| `acquisition_lot` | `SELECT`, `INSERT` |
| `inventory_event` | `SELECT`, `INSERT` |
| `inventory_item_id_seq`, `purchase_record_id_seq`, `acquisition_lot_id_seq`, `inventory_event_id_seq` | `USAGE` |

The runtime retains **no** `DELETE`, `TRUNCATE`, DDL, `CREATEROLE`,
ownership, or ability to assume/inherit the migrator role. All other
staging tables stay SELECT-only; worker/readonly roles untouched.
Column-scoped `UPDATE (stock, cost)` is the containment mechanism for
every unrelated inventory write.

**Append-only protections:** truth tables receive INSERT+SELECT only;
`_write_pair` inserts only; snapshot `stock`/`cost` remain the
operational source by frozen design. No path in this amendment deletes
or rewrites evidence.

## 8. Controlled fail-closed behavior after cutover (closed)

One FastAPI exception handler maps SQLAlchemy `InsufficientPrivilege`
and `ProgrammingError` (undefined table) to 503 `FEATURE_NOT_READY`
with a generic body. Every unrelated route logically affected by
cutover `complete` stays unavailable:

| Route | Contained by |
| --- | --- |
| `PATCH /inventory/{id}` quantity, `/inventory/{id}/reverse-adjust` | missing `INSERT` on `inventory_adjustment` → controlled 503 |
| apply-trades, intake, staging commit, CSV import | missing tables → controlled 503; frontend-locked |
| price approve/reject, approve-under-5, resticker, label, PATCH price | column-scoped privilege denial and/or missing tables → controlled 503; read-only or locked frontend |

No raw database privilege 500 may surface on these routes after
cutover.

## 9. Staging-only cutover procedure (closed)

1. Pre-checks: synthetic shop exists with the executing owner as
   member; `GET /admin/inventory` count = 0; reconcile returns zero
   mismatches; staging build pinned to the merge SHA.
2. Owner executes `POST /api/v1/admin/inventory-truth/cutover`
   `{generation: 1}` (owner-only gate unchanged). The cutover row has
   no actor column; the acting Clerk user id and request timestamp are
   recorded in the acceptance document (known audit gap, stated).
3. Verify `/inventory-truth/status` shows `complete` and reconcile = 0.
   Timeout is not green.
4. Recovery: failed receives never touch the cutover row; a `locking`
   row re-enters the same procedure; `failed_permanent` stops and
   requires a new owner decision.

Cutover `complete` is set on the single synthetic staging shop only.
Every other shop keeps no cutover row → fail-closed 503.

## 10. Staging-proof retention policy (closed)

One dedicated staging test shop; SKU `F2-TEST-0001`, name
"F2 Synthetic Test Card — staging proof", quantity 2, unit_cost 0.01.
Retained permanently with all evidence rows (purchase record, lot,
event) as clearly labeled staging proof; never presented as production
data; never deleted or rewritten. Rollback never deletes evidence (§12).

## 11. Unchanged objects

Canonical key grammar and all existing source keys; quantity equation;
receive/loss/reverse typing; outbound ledger; adjustment evidence and
reason registry; Sale rows; weighted-average cost; cutover order and
freeze semantics; truth table shapes; notification envelope.

## 12. Migration and rollback

Migration: §4 order, one atomic reviewed-migrator transaction per
concern (column+index; grants), rerun no-op, injected mid-failure
leaves nothing partial. Startup `create_all` stays off in
staging/production (`startup_schema_mutation_forbidden`); the column is
applied only by the migrator/owner workflow.

**Rollback (evidence-preserving):** disable the route (remove route
registration or return 503 `FEATURE_NOT_READY` unconditionally) and
revoke the four-object grants back to SELECT-only via the reviewed
migrator. The `client_idempotency_key` column may remain populated and
unused; truth rows, purchase rows, and the cutover row remain as
evidence. No DELETE, no column drop, no WA rebuild from lots.

## 13. Acceptance-test additions (exact list)

Append to TESTS.md:

1. Permissions as `stashtab_api`: INSERT/UPDATE(stock,cost) succeed on
   the four objects; DELETE/TRUNCATE denied on every staging table;
   UPDATE on `inventory_item.price`/`sticker_price` denied; readonly
   role denied everything; `SET ROLE stashtab_migrator` denied.
2. First-SKU receive in an empty shop → item, purchase row, lot, event
   present; truth key `purchase_record:{shop}:{purchase_record.id}`;
   reconcile zero.
3. Idempotent replay (same key, same payload) → `no_op`; counts
   unchanged. Conflicting replay (same key, different digest) → 409,
   zero writes.
4. Concurrent identical receives (two sessions) → exactly one pair.
5. Injected failure mid-transaction → zero rows committed.
6. Cross-shop denial: other shop's token/hint → 403/404, zero data
   leak.
7. Unrelated routes after cutover (approve-update, resticker, PATCH
   price, apply-trades, reverse-adjust) → controlled 503
   `FEATURE_NOT_READY`, never a raw privilege/undefined-table 500.
8. Missing cutover on a second shop → receive 503, fail-closed; missing
   `Idempotency-Key` header → 422, zero writes.

PostgreSQL: permissions, concurrency, idempotency, atomic failure,
append-only — twice on fresh disposable databases. API-level: the same
eight through the endpoint with a synthetic Clerk membership.

## 14. Exact diffs (apply only after vote)

### DESIGN.md

No diff. Canonical sources, grammar, and retry rules are unchanged.

### MIGRATION.md

```diff
--- a/docs/inventory-truth-v1/MIGRATION.md
+++ b/docs/inventory-truth-v1/MIGRATION.md
@@ Compatibility, item 1
 1. Additive unique indexes `(shop_id, id)` on live `inventory_item`,
    `purchase_record`, `sale` — **indexes only**, not column rewrites.
+   Exception authorized only by AMENDMENT-1.3.0: one additive nullable
+   column `purchase_record.client_idempotency_key VARCHAR(36)` plus the
+   partial unique `uq_purchase_record_shop_client_key`; no type change,
+   no rewrite, no drop.
@@ after the Slice-03 additive envelope section
+## F2 controlled-receive envelope (AMENDMENT-1.3.0)
+
+Same locked discipline. Staging only. Live migrator adds the nullable
+client key column and partial unique on `purchase_record` before any
+truth step; rerun no-op; injected failure leaves nothing partial.
+Runtime grant envelope for `stashtab_api` replaces SELECT-only on
+exactly `inventory_item` (SELECT, INSERT, UPDATE (stock, cost)),
+`purchase_record` (SELECT, INSERT), `acquisition_lot` (SELECT, INSERT),
+`inventory_event` (SELECT, INSERT), plus USAGE on their four identity
+sequences. No DELETE, TRUNCATE, DDL, ownership, or migrator assumption.
+Truth keys unchanged: `purchase_record:{shop_id}:{purchase_record.id}`.
+Live receive still requires a completed gen:1 cutover for that shop;
+unrelated writes after cutover fail with controlled 503
+FEATURE_NOT_READY, never raw privilege errors. Rollback disables the
+route and revokes grants; evidence rows remain.
```

### TESTS.md

```diff
--- a/docs/inventory-truth-v1/TESTS.md
+++ b/docs/inventory-truth-v1/TESTS.md
@@
+## F2 controlled-receive acceptance tests (AMENDMENT-1.3.0)
+
+The 8 tests listed in `amendments/AMENDMENT-1.3.0.md` §13. PostgreSQL
+permissions/concurrency/idempotency/atomic-failure/append-only twice on
+disposable databases; API-level equivalents with synthetic membership.
```

### CONTRACT.md (pointer only; no self-hash)

```diff
--- a/docs/inventory-truth-v1/CONTRACT.md
+++ b/docs/inventory-truth-v1/CONTRACT.md
@@ header version line
-**Version:** `1.0.0` → `1.1.0` → `1.2.0` (AMENDMENT-1.2.0 approved; hashes in freezes/FREEZE-1.2.0.json)
+**Version:** `1.0.0` → `1.1.0` → `1.2.0` → `1.3.0` (AMENDMENT-1.3.0 approved; hashes in freezes/FREEZE-1.3.0.json)
@@ §7 current gate state — append
+AMENDMENT-1.3.0 APPROVED; F2 CONTROLLED RECEIVE IMPLEMENTATION BLOCKED
+PENDING NAMED UNLOCKS
@@ after §9
+## 10. Amendment 1.3.0 freeze record
+
+Resulting contract version: **1.3.0**.
+Approved amendment: `AMENDMENT-1.3.0`.
+Freeze manifest: `docs/inventory-truth-v1/freezes/FREEZE-1.3.0.json`.
+Byte hashes, algorithm, freeze timestamp, and file list live only in
+that manifest. This file does not store its own SHA-256.
+The §2 v1.0.0, §8 v1.1.0, and §9 v1.2.0 records remain unchanged.
```

## 15. Proposed freeze-manifest process (after approval, not now)

Non-self-hashing, per `freezes/MANIFEST-SPEC.md` discipline:

1. Apply §14 diffs (MIGRATION, TESTS, CONTRACT pointer). CONTRACT §10
   carries no timestamp and no self-hash.
2. Hash exact repository bytes (`git hash-object --no-filters` or raw
   `read_bytes()`) of: `CONTRACT.md`, `DESIGN.md`, `MIGRATION.md`,
   `TESTS.md`, `amendments/AMENDMENT-1.3.0.md`. SHA-256, lowercase hex,
   no transcoding.
3. Write `docs/inventory-truth-v1/freezes/FREEZE-1.3.0.json` with
   contract id/version, `freeze_timestamp`, `approved_amendments`
   (1.1.0, 1.2.0, 1.3.0), previous-freeze pointer to CONTRACT §9 /
   v1.2.0, algorithm, canonical-byte rule, and the five file hashes.
   The manifest does not list or hash itself.
4. Do not edit hashed files after step 2. Update
   `scripts/validate_inventory_truth_freeze.py` expectations for
   version `1.3.0` in the same freeze step, then run it against the new
   manifest.
5. Keep CONTRACT §2, §8, §9 byte-for-byte as historical records.

## 16. Explicit exclusions

Frontend receive UI, CSV import/adjust, trade UI, checkout, sales
writes, quantity adjustments, Shopify, notifications, payments, Watch,
workers, `sync_outbox`, seed scripts, direct manual inserts, and any
production authorization. The first staging smoke uses an owner actor.

## 17. Remaining unlocks and production gates

Separate, later, named — none granted by this vote:

1. **Implementation unlock:** endpoint, controlled-503 handler, model
   column, migrator changes (directive + acceptance pattern).
2. **Provisioning unlock:** reviewed migrator apply on staging Neon
   (column, index, grants); migrator role only.
3. **Cutover unlock:** gen-1 cutover on the synthetic shop (§9).
4. **Production unlock:** not proposed; production stays SELECT-only
   behind MIGRATOR-ROLE-PROVISIONING-GATE and every standing deployment
   gate in GATES.md (runbook, audit logging, break-glass, zero recon).

## 18. Recommendation

Approve AMENDMENT-1.3.0 as the governance vehicle for the F2
controlled-receive slice: it authorizes exactly one additive live
column, one partial unique, one least-privilege grant envelope, and one
thin endpoint — with truth semantics untouched and evidence append-only.
Do not implement, provision, or cut over in the same vote.
