# DIRECTIVE (PLANNING ONLY — NOT IMPLEMENTED) — slice-03-adjustments

**Contract:** `STASHTAB-INVENTORY-TRUTH-001` v1.2.0 (frozen)
**Slice:** `slice-03-adjustments`
**Status:** `PLAN FROZEN against contract v1.2.0 — IMPLEMENTATION BLOCKED`
**Predecessor:** `slice-02-outbound-events` (`COMPLETED — NOT MERGED — NOT DEPLOYED`)
**Pinned review commit:** `1a54722` on `feature/inventory-truth-slice-02` (base `132f0f5`)
**Owner decisions recorded:** 2026-08-24 (seven approved planning decisions)

Do not implement, migrate, merge, push, or edit frozen contract bodies
until a named human freeze/amendment vote.

## Owner-approved decisions (binding)

1. **Input and storage.** The API may accept an absolute target for a
   verified count, or an explicit signed delta. Absolute input must never
   write the snapshot directly. Lock the inventory row, read current
   quantity, compute one signed delta, validate, then atomically write the
   adjustment event and the resulting snapshot. Persist quantity-before,
   signed delta, and quantity-after as audit evidence.
2. **Authorization.** Verified shop owners and authorized staff may make
   ordinary single-item adjustments. Bulk CSV adjustment is owner-only
   until a later reviewed bulk-adjust permission exists. Every
   adjustment records verified actor, shop, reason code, source,
   timestamp, and correlation/idempotency key. Caller-supplied user or
   shop headers are not identity.
3. **Negative inventory.** Adjustments must never make remaining negative.
   Reject the whole operation with no event and no snapshot change.
   Existing Shopify oversale exception behaviour is unchanged.
4. **Idempotency.** Individual PATCH/adjust requests require a client
   UUID, unique per shop. The UI mints one key per user intent and reuses
   it on retries. Same key + identical payload returns the original result.
   Same key + different payload is a conflict. CSV uses a durable upload
   UUID plus deterministic row identity; reruns cannot repeat a delta.
5. **Cycle counts.** This slice may record a completed count’s variance
   through the adjustment mechanism. Campaigns, assignments,
   scheduling, locations, and count-session UI are out of scope.
6. **Cost.** Quantity adjustments cannot change acquisition-lot cost,
   PurchaseRecord cost, or weighted-average cost. Cost correction needs a
   separate accounting-controlled design.
7. **Contract governance.** Compare this plan to frozen v1.1.0. Anything
   outside that envelope is Amendment 1.2.0. Frozen bodies are not edited
   before a human vote.
8. **Anomaly alerts (approved defaults).** Alert after commit when
   |delta| ≥ 100, or |delta| ≥ 50% of on-hand and on-hand ≥ 10, or a SKU
   in one shop has more than 10 adjustments in 24 hours. Defaults are
   configurable, not accounting rules. Alert failure cannot roll back,
   acknowledge, or hide the adjustment. Same idempotency-key retries
   cannot stack alerts. An alert is review evidence only.
9. **CSV new items (approved).** Slice-03 must not create inventory.
   A CSV with a new-item quantity row fails validation and applies
   nothing. No silent skip. No lotless create.
10. **Staff reversals (approved).** Authorized staff may reverse another
    authorized user’s individual adjustment in the same shop. Reverse
    records original actor and reversing actor, inserts one opposite
    event, never edits history, fully reverses an original at most once,
    and fails if remaining would go negative. CSV/bulk reversal stays
    outside this permission.
11. **Price-only PATCH during freeze (approved).** Price-only PATCH
    remains allowed and must not change quantity or any cost field.
    Mixed price-plus-quantity requests fail atomically while frozen.

## Current mutation-path inventory (repository search)

Search: `.stock =` / `.stock -=` under `services/api` plus admin/CSV
callers. Partner `vendor/` desktop code is not a live SaaS writer.

| ID | Path | Classification |
| --- | --- | --- |
| R1 | Staging commit `intake.py` `existing.stock = total_qty` and new-row `stock=` | Slice-01 receive dual-write. Out of this slice. |
| R2 | Trade receive `trades.py` `existing_item.stock = total_qty` and new-row `stock=` | Slice-01 receive. Out of this slice. |
| S1 | POS `sales.py` `item.stock -= finalized.quantity` | Slice-02 sell. Out of this slice. |
| S2 | Shopify pull `sync_worker.py` `locked_item.stock = stock_before - removed` | Slice-02 sell / oversale. Out of this slice. |
| A1 | Admin PATCH `/admin/inventory/{item_id}` `item.stock = payload.stock` | **In scope.** Silent absolute overwrite; frozen 503 today. |
| A2 | CSV `import_engine.py` existing row `existing.stock = quantity` | **In scope.** Silent absolute overwrite; frozen today. |
| A3 | CSV new row `stock=quantity` | **Blocked in this slice.** File fails validation; apply nothing. New items are receive/lot, not adjust. |
| A4 | Admin PATCH price/sticker/sync without `stock` | Not a quantity path. Unchanged; no adjust key required. |
| A5 | CSV existing-row cost write `existing.cost = …` | **Contain, do not apply in this slice.** Cost correction is out of scope. |
| F1 | Shopify push `shopify_consistency.py` reads `item.stock` | Read/push only. Side effect of snapshot, not a second source. |
| F2 | Collectr recon | Report only. |
| D1 | `seed_dev.py` | Dev fixture only; not a production writer. |
| T* | Tests constructing `stock=` | Test fixtures; grep allow-list. |

After this slice the only remaining `InventoryItem.stock` writes must be:
receive apply, sell apply, reverse-apply of those, and the single adjust
writer. Partner vendor tree stays unused.

## Proposed data and API model

Keep writing one `inventory_event` (`event_type='adjust'` or
`event_type='reverse'`). Live staff shrinkage/damage/theft do **not** use
`event_type='loss'` because frozen DESIGN requires `lot_id` for `loss`,
and inventing or consuming lots would touch cost layers. Loss-class
reasons still never create `Sale` rows.

New migrator-only append-only table `inventory_adjustment` (TruthBase):

- shop_id, id
- inventory_event_id (composite FK)
- inventory_item_id
- sku
- qty_before, qty_delta, qty_after (integers; after = before + delta)
- input_mode: `absolute` or `signed`
- reason_code (registry; required)
- reason_note (optional free text; never a substitute for the code)
- source: `admin_patch` | `csv` | `cycle_count_variance` | `reverse`
- actor_clerk_user_id (verified membership; required)
- client_idempotency_key (UUID string)
- csv_upload_id, csv_row_identity (nullable)
- reverses_event_id (nullable; required for source=reverse)
- payload_hash (canonical hash of item, mode, target or delta, reason)
- created_at insert-only

Constraints: unique `(shop_id, client_idempotency_key)` for PATCH keys;
unique `(shop_id, csv_upload_id, csv_row_identity)` for CSV; check
`qty_after = qty_before + qty_delta`; `qty_after >= 0`;
`qty_delta != 0` except idempotent replay (replay returns the stored row
and does not insert). Append-only triggers + TRUNCATE deny like other
truth tables. `create_all` must not create it.

Canonical event keys (Amendment 1.2.0):

- `admin_adjust:{shop_id}:{idempotency_uuid}`
- `csv_adjust:{shop_id}:{upload_uuid}:{row_identity}`
- `count_adjust:{shop_id}:{idempotency_uuid}` (completed-count variance
  posted through the same PATCH/adjust API with reason
  `cycle_count_variance`)
- reverse: existing grammar `reverse_{orig_source}:{shop_id}:{orig_pk}`

Lot_id is NULL (lotless, same as sell). Cost columns are not touched.

### PATCH compatibility

Keep `PATCH /admin/inventory/{item_id}`.

- Price/sticker/sync-only: unchanged; no freeze beyond today’s rules.
- Quantity change requires:
  - verified shop context (not headers)
  - owner or staff
  - `Idempotency-Key` header (UUID)
  - `reason_code`
  - either `stock` (absolute target) **or** `stock_delta` (signed), not
    both
- Server: `SELECT … FOR UPDATE` the item; qty_before = current stock;
  if absolute, delta = target − before; validate integer, delta ≠ 0,
  after >= 0; insert event + adjustment + snapshot in one transaction.
- Zero computed delta (absolute target equals current) is a no-op
  success only when it is an idempotent replay of an existing key with
  the same payload; a new key with delta 0 is rejected as a client
  error (nothing to apply).

### CSV compatibility

Keep the existing quantity column as an **absolute counted target**, not
a direct snapshot assignment. New required field: `reason_code` (or a
single upload-level reason applied to every row). Optional note column.

Owner-only. Validate the entire file first. Then apply in **one shop
transaction** (all-or-nothing). Any invalid row fails the file; no partial
snapshot or event writes.

Duplicate SKUs in one upload:

- Same identity, same target quantity → collapse to one row.
- Same identity, different targets → fail the whole file.
- Unknown SKU / new-item quantity row → fail the whole file; apply
  nothing. Slice-03 does not create inventory.

Corrected files: caller must mint a **new** upload UUID. Row identity is
stable (SKU, or the existing match key used by import). The new file
computes fresh deltas from the locked live quantity. It cannot reuse the
previous upload UUID to apply a second delta. If the operator needs to
undo the previous upload, they reverse those events; they do not re-send
the old UUID.

Existing-row **cost** columns in CSV are ignored with a counted skip;
they are not applied.

## Authorization matrix

Identity: signed token + `ShopMember` row. `X-Shop-Id` / `X-Clerk-User-Id`
are hints only.

| Action | owner | staff | cashier/public | notes |
| --- | --- | --- | --- | --- |
| Single PATCH/adjust | yes | yes | no | actor = verified clerk id |
| Reverse a single adjust | yes | yes | no | may reverse another user’s event; both actors recorded; one full reverse only |
| CSV bulk | yes | **no** | no | until a later permission review |
| Reverse a CSV batch | yes | no | no | one reverse per original event, same owner rule |
| Price-only PATCH | yes | yes | no | unchanged |
| Header-only identity | never | never | never | fail closed |

Missing actor or membership → 401/403, no write.

## Reason-code registry

Closed set. Free text may supplement (`reason_note`) and must not replace
the code. Unknown codes fail closed.

| Code | Typical sign | Event type | Sale row | Meaning |
| --- | --- | --- | --- | --- |
| `count_correction` | ± | adjust | no | Verified count vs snapshot; cause unknown |
| `data_entry_error` | ± | adjust | no | Operator typed the wrong number |
| `shrinkage` | − | adjust | no | Known missing product (loss-class) |
| `damage` | − | adjust | no | Unsellable units (loss-class) |
| `theft` | − | adjust | no | Known theft (loss-class) |
| `found` | + | adjust | no | Previously missing units located |
| `cycle_count_variance` | ± | adjust | no | Variance from a completed count |
| `csv_correction` | ± | adjust | no | Bulk file correction |
| `reverse_of` | opposite | reverse | no | Required on reversals; must reference original event id |

Shrinkage, damage, and theft always use negative deltas, never `Sale`.
Positive `found` is not a receive lot and does not change cost.

## Idempotency model

Shop-scoped unique key on the adjustment table and matching
`inventory_event.idempotency_key`.

PATCH: client UUID. Replay with same payload → return stored
qty_before/delta/after and HTTP 200. Same UUID, different payload_hash →
409 conflict, no write.

CSV: durable upload UUID + row identity. Re-post of the same upload is a
full no-op of already-applied rows (the atomic transaction either created
all of them or none). A new upload UUID is a new intent.

## CSV atomicity (chosen)

**Validate the complete file, then commit all rows in one transaction.**

Reasons: owner-only bulk path; fail-closed; no half-applied counts;
reconciliation stays explainable. A 500-row file that fails on row 499
rolls back entirely. The client retries with a repaired file and a new
upload UUID if any row was previously committed (which it was not, if
the transaction rolled back). If a client retries an in-flight timeout
with the **same** upload UUID, the unique keys make a second apply
impossible.

## Concurrency model

One `SELECT … FOR UPDATE` (and `populate_existing`) on the inventory
row before reading qty_before. Concurrent sale and adjust serialize on
that row. The loser sees the committed quantity and either applies a
still-valid delta or fails the negative check. Observation/sell unique
keys remain the outbound retry path. No lost update.

## Reversal and reconciliation

Reverse inserts a new event (`event_type='reverse'`) and a new
adjustment row: qty_delta = −original.qty_delta, qty_before = locked
current, qty_after = before + delta, `reverses_event_id` set, original
actor and reversing actor both stored. Original rows are never updated
or deleted. One original adjustment may be fully reversed only once
(unique on original event). Reverse of a reverse is out of this slice.

If reverse would drive remaining negative, reject (same as decision 3).
CSV/bulk reversal is not granted by the staff-reverse permission.

Recon:

```
event_remaining(shop, sku) = SUM(quantity_delta)
unaccounted if event_remaining != inventory_item.stock
```

Reports break down by reason_code and source. Loss-class reasons
(`shrinkage`, `damage`, `theft`) must have zero associated `Sale` rows.
Timeout is not green.

## Freeze / cutover

While the shop cutover row is locking/frozen: quantity PATCH and CSV
quantity apply stay 503. Price-only PATCH remains allowed and must not
touch quantity or cost fields. A mixed price-plus-quantity PATCH fails
atomically while frozen. After freeze lifts, adjust dual-write is on. Production
inventory-truth cutover still requires this slice to be complete
(`GATES.md` owner decision 5), plus standing deployment gates. Rollback
flips cutover to locking; snapshot and Sale stay; adjust history remains
append-only.

## Audit and alert thresholds (approved defaults)

Every accepted adjust is an audit record (actor, shop, reason, source,
key, before/delta/after, timestamp).

After the adjustment transaction commits, raise a non-blocking
`inventory_exception` kind `adjust_anomaly` when:

- |delta| ≥ 100 units, or
- |delta| ≥ 50% of qty_before when qty_before ≥ 10, or
- more than 10 quantity adjustments on the same SKU in one shop in 24 hours

These are initial configurable defaults, not accounting rules. Alert
failure cannot roll back, acknowledge, or hide the adjustment. Retries
of the same idempotency key cannot stack alerts. An alert is review
evidence; it does not reverse or block the adjustment.

## Removal / containment of silent overwrites

A1/A2 go through the adjust writer only. A3 (CSV new-item) fails the
file. A5 CSV cost-on-existing is contained (skip). Grep gate updates the allow-list from
`item.stock = payload.stock` / `existing.stock = quantity` to the single
adjust-writer assignment after lock-and-delta. Partner vendor files are
explicitly excluded.

## Amendment requirement

**Amendment 1.2.0 is required.** Frozen v1.1.0 already allows
`event_type='adjust'` and reverse grammar, but it does not list adjust
canonical keys, the `inventory_adjustment` evidence table, reason-code
check constraint, CSV upload uniqueness, `adjust_anomaly` exception
kind, or lotless live staff adjustments. See
`amendments/AMENDMENT-1.2.0.md`. Do not edit DESIGN/MIGRATION/TESTS until
the vote.

## Acceptance tests (plan)

1. Absolute PATCH 10→7: lock, delta −3, event+adjustment+snapshot 7; Sale
   count unchanged; cost unchanged.
2. Signed PATCH delta −3 from 10: same stored evidence.
3. Absolute input is never assigned to snapshot without the computed
   delta path (unit assertion on the writer).
4. Same UUID + same payload: no second event; original after-qty returned.
5. Same UUID + different payload: 409; snapshot unchanged.
6. Missing UUID: 400; no write.
7. after would be −1: 409/422; no event; snapshot unchanged.
8. Shrinkage/damage/theft: negative adjust; zero Sale; cost unchanged.
9. `found`: positive adjust; not a receive lot; cost unchanged.
10. Reverse: new opposite event; original intact; snapshot restored when
    valid.
11. Reverse that would go negative: rejected.
12. Concurrent adjust vs sell: both commit without lost update; remaining
    >= 0.
13. Frozen shop quantity PATCH/CSV: 503; no rows.
14. Staff CSV: 403; owner CSV of three valid rows: three events, atomic.
15. CSV invalid row: zero events, snapshot unchanged.
16. CSV duplicate identity conflicting targets: file rejected.
17. CSV duplicate identity identical targets: one event.
18. CSV rerun same upload UUID: no additional delta.
19. CSV corrected file new UUID: deltas from current live qty; previous
    events untouched.
20. CSV existing cost column ignored; WA/lot/PurchaseRecord cost unchanged.
21. Price-only PATCH still works without Idempotency-Key.
22. Header-only identity cannot adjust.
23. `create_all` does not create `inventory_adjustment`.
24. Runtime role cannot UPDATE/DELETE/TRUNCATE adjustment rows; failed
    attempts leave rows intact.
25. Grep gate: no unclassified `stock=` writers in `services/api/app`.
26. Recon by reason/source matches snapshot.
27. After-commit |delta|≥100 records one `adjust_anomaly`; retry of the
    same key does not stack a second alert; alert failure leaves the
    adjustment intact.
28. CSV new-item quantity row: whole file rejected; zero events.
29. Staff reverse of another staff’s adjust: both actors stored; original
    intact; second reverse of the same original is 409.
30. Frozen mixed price-plus-quantity PATCH: 503; price and quantity
    unchanged.

PostgreSQL: run concurrency, freeze, CSV atomicity, and append-only
twice on fresh disposable databases.

## Residual genuine human decisions

None for this plan. Implementation unlock is the remaining vote.

## Freeze recommendation

This plan is **FROZEN** against `STASHTAB-INVENTORY-TRUTH-001` v1.2.0
(manifest `docs/inventory-truth-v1/freezes/FREEZE-1.2.0.json`).
Implementation remains blocked until a separate named unlock.
Do not overwrite the 1.2.0 freeze record; later changes need a new
amendment and a new manifest.
