# STASHTAB-INVENTORY-TRUTH-001 / AMENDMENT-1.2.0 — human vote packet

**Amendment identifier:** `STASHTAB-INVENTORY-TRUTH-001 / AMENDMENT-1.2.0`
**Parent:** version `1.1.0` (frozen 2026-08-23; hashes in CONTRACT §8)
**Proposed resulting version:** `1.2.0`
**Status:** `PROPOSED — CLOSED TEXT — AWAITING HUMAN VOTE`
**Frozen v1.1.0 bodies:** not edited by this packet
**Rule:** CONTRACT §6 (versioned proposal, independent review already
recorded for the plan, named human approval, new freeze hashes)
**Does not authorize implementation, production DDL, merge, or deploy**

This packet is exact and closed. There are no optional forks.

## 0. Compatibility result (bounded check)

Checked against frozen DESIGN/MIGRATION/TESTS v1.1.0, slice-01
acceptance, and slice-02 acceptance.

| Constraint | Result |
| --- | --- |
| Remaining = SUM(quantity_delta) | Preserved. Adjust/reverse deltas enter the same sum. |
| Receive / opening / shrinkage `:gen:1` keys | Unchanged. |
| Backfill `loss` is lot-required and creates no Sale | Preserved. Live staff loss-class uses `adjust`, not `event_type=loss`. |
| Sell / observation / refund / return keys | Unchanged. |
| Shopify oversale exception path | Unchanged. Adjust cannot go negative. |
| `create_all` cannot create truth tables | Extended only by listing `inventory_adjustment`. |
| Append-only + migrator-only DDL | Same discipline as 1.1.0. |
| PATCH/CSV quantity freeze until adjust slice | This amendment is that slice’s contract; freeze behavior stays until implementation unlock. |
| Weighted-average / lot / PurchaseRecord cost | Not written by adjust. |
| Sale rows | Not written by adjust or loss-class reasons. |

**Blocker:** none for the vote. Implementation remains blocked until vote
plus a later named unlock.

## 1. Closed decisions incorporated

1. Anomaly defaults: |delta| ≥ 100; or |delta| ≥ 50% of on-hand and
   on-hand ≥ 10; or more than 10 adjustments for one SKU in one shop in
   24 hours. Configurable defaults, not accounting rules. Fire after
   commit. Failure cannot roll back, acknowledge, or hide. Same
   idempotency key cannot stack alerts. Alert does not reverse or block.
2. CSV new-item rows fail the file and apply nothing. No skip. No
   lotless create. New items require a later receive/lot path.
3. Staff may reverse another authorized user’s individual adjustment in
   the same shop. Both actors recorded. One full reverse per original.
   Fail if remaining would go negative. CSV/bulk reverse not granted here.
4. Price-only PATCH allowed during freeze. It must not change quantity or
   any cost field. Mixed price-plus-quantity fails atomically while frozen.

## 2. Affected frozen clauses (exact)

On approval only, apply the diffs in §14 to:

- `DESIGN.md` §1 (quantity types / live insert authorization)
- `DESIGN.md` §2 (canonical sources)
- `DESIGN.md` new §2b (adjustment evidence + reason registry + freeze)
- `MIGRATION.md` additive envelope and freeze sentence
- `TESTS.md` slice-03 tests
- `CONTRACT.md` §7–§8 version/hash record (new freeze record; §2 v1.0.0
  and §8 v1.1.0 records stay)

## 3. Canonical keys (complete)

Grammar unchanged: `{source}:{shop_id}:{source_pk}`; characters
`[A-Za-z0-9_.:-]`; max 255; only suffix still `:gen:{n}` (not used here).

| Source | Key | Example |
| --- | --- | --- |
| Admin/staff PATCH | `admin_adjust:{shop_id}:{idempotency_uuid}` | `admin_adjust:9b1f8c2a-1111-4222-8333-444455556666:550e8400-e29b-41d4-a716-446655440000` |
| CSV existing-SKU row | `csv_adjust:{shop_id}:{upload_uuid}:{row_identity}` | `csv_adjust:9b1f8c2a-1111-4222-8333-444455556666:7c2d9e10-aaaa-4bbb-8ccc-ddddeeeeffff:SKU-123` |
| Completed-count variance | `count_adjust:{shop_id}:{idempotency_uuid}` | `count_adjust:9b1f8c2a-1111-4222-8333-444455556666:550e8400-e29b-41d4-a716-446655440000` |
| Reverse (full, once) | `reverse_{orig_source}:{shop_id}:{orig_pk}` | `reverse_admin_adjust:9b1f8c2a-1111-4222-8333-444455556666:550e8400-e29b-41d4-a716-446655440000` |

`orig_pk` is the original idempotency UUID (PATCH/count) or
`{upload_uuid}:{row_identity}` (CSV). No `:seq` on adjustment reverses.
A second reverse of the same original is rejected.

Enforcement:

- All keys unique on `inventory_event (shop_id, idempotency_key)`
- PATCH/count also unique on `inventory_adjustment (shop_id, client_idempotency_key)`
- CSV also unique on `inventory_adjustment (shop_id, csv_upload_id, csv_row_identity)`
- Reverse also unique on `inventory_adjustment (shop_id, reverses_event_id)` where `reverses_event_id IS NOT NULL`

## 4. `inventory_adjustment` schema (closed)

Migrator-only. Joins `TRUTH_TABLE_NAMES`. Not imported by application
metadata. `create_all` must not create it.

| Column | Type | Null | Notes |
| --- | --- | --- | --- |
| id | INTEGER PK identity | no | |
| shop_id | VARCHAR(36) | no | |
| inventory_event_id | INTEGER | no | |
| inventory_item_id | INTEGER | no | |
| sku | VARCHAR(50) | no | |
| qty_before | INTEGER | no | locked on-hand before apply |
| qty_delta | INTEGER | no | signed; 0 forbidden on insert |
| qty_after | INTEGER | no | |
| input_mode | VARCHAR(16) | no | `absolute` or `signed` |
| reason_code | VARCHAR(32) | no | registry |
| reason_note | TEXT | yes | non-authoritative |
| source | VARCHAR(32) | no | `admin_patch` \| `csv` \| `cycle_count_variance` \| `reverse` |
| actor_clerk_user_id | VARCHAR(64) | no | verified membership |
| original_actor_clerk_user_id | VARCHAR(64) | yes | required when source=`reverse` |
| client_idempotency_key | VARCHAR(36) | yes | required when source in (`admin_patch`,`cycle_count_variance`) |
| csv_upload_id | VARCHAR(36) | yes | required when source=`csv` |
| csv_row_identity | VARCHAR(120) | yes | required when source=`csv` |
| payload_hash | VARCHAR(64) | no | SHA-256 hex of canonical payload |
| reverses_event_id | INTEGER | yes | required when source=`reverse` |
| created_at | TIMESTAMPTZ | no | insert-only |

Checks:

- `qty_after = qty_before + qty_delta`
- `qty_after >= 0`
- `qty_delta <> 0`
- `input_mode IN ('absolute','signed')`
- `source IN ('admin_patch','csv','cycle_count_variance','reverse')`
- `reason_code IN ('count_correction','data_entry_error','shrinkage','damage','theft','found','cycle_count_variance','csv_correction','reverse_of')`
- loss-class: `reason_code IN ('shrinkage','damage','theft')` ⇒ `qty_delta < 0`
- `found` ⇒ `qty_delta > 0`
- `reverse_of` ⇒ `source='reverse' AND reverses_event_id IS NOT NULL AND original_actor_clerk_user_id IS NOT NULL`
- `source='reverse'` ⇒ `reason_code='reverse_of'`

Uniques:

- `uq_adj_shop_id (shop_id, id)`
- `uq_adj_shop_event (shop_id, inventory_event_id)`
- `uq_adj_shop_client_key (shop_id, client_idempotency_key)` (PostgreSQL/SQLite partial: where key IS NOT NULL)
- `uq_adj_shop_csv_row (shop_id, csv_upload_id, csv_row_identity)` (partial: csv_upload_id IS NOT NULL)
- `uq_adj_shop_reverse_once (shop_id, reverses_event_id)` (partial: reverses_event_id IS NOT NULL)

Indexes: `(shop_id, sku, created_at)`, `(shop_id, actor_clerk_user_id, created_at)`

Composite FKs `ON DELETE RESTRICT`:

- `(shop_id, inventory_event_id)` → `inventory_event (shop_id, id)`
- `(shop_id, inventory_item_id)` → `inventory_item (shop_id, id)`
- `(shop_id, reverses_event_id)` → `inventory_event (shop_id, id)` when not null

Append-only: same UPDATE/DELETE row triggers and BEFORE TRUNCATE deny
as slice-02 outbound tables. Runtime role: no UPDATE/DELETE/TRUNCATE.
Failed attempts leave rows intact. Only the provisioned migrator role
may perform authorized lifecycle DDL. `MIGRATOR-ROLE-PROVISIONING-GATE`
still blocks production apply.

## 5. Event insert rules

Live staff/owner quantity change: `inventory_event.event_type='adjust'`,
`lot_id` NULL, `sale_id` NULL. Reverse: `event_type='reverse'`, `lot_id`
NULL, `reverses_event_id` set.

Do not insert `event_type='loss'` on these paths. Backfill shrinkage
`loss` keys and lot requirement are unchanged.

Writer algorithm (closed): lock inventory item; read qty_before;
if absolute, qty_delta = target − qty_before; else qty_delta is the
signed input; if qty_delta = 0 on a new key → reject; if qty_after < 0
→ reject with no writes; insert event + adjustment + snapshot in one
transaction. Never assign the client absolute target onto `stock`.

## 6. Idempotency and payload conflict

Canonical payload = `inventory_item_id | input_mode | target_or_delta | reason_code`.
`payload_hash` is SHA-256 of that string.

Same shop + key + same hash → return original evidence, no insert, no
snapshot change, no new anomaly.

Same shop + key + different hash → 409, no write.

CSV row key is `csv_adjust:{shop_id}:{upload_uuid}:{row_identity}`.
`row_identity` is the existing import match key (SKU). Duplicate identities
in one file: identical targets collapse to one row; conflicting targets
fail the file.

CSV transaction: validate entire file including “no new SKU / no create
row”; then apply all remaining rows in one transaction. Any failure
rolls back all. New-item quantity row is a validation failure of the
file, not a skip.

Corrected CSV requires a new `upload_uuid`. Deltas always from locked
live quantity. Reuse of an old upload UUID cannot apply a second delta.

## 7. Reverse-of

One full reverse per original adjustment event. Unique
`(shop_id, reverses_event_id)` enforces this.

Reverse payload: qty_delta = −original.qty_delta; qty_before = locked
current; qty_after = before + delta; reason_code=`reverse_of`;
actor_clerk_user_id = reversing verified user; original_actor_clerk_user_id
= original.actor_clerk_user_id.

If qty_after < 0 → reject, no rows. Reverse of a reverse is rejected in
this slice. CSV/bulk reverse is not authorized by staff reverse.

## 8. `adjust_anomaly`

Extend `inventory_exception.kind` check with `'adjust_anomaly'`.

Identity:

- Size or percent trigger: `exception_ref = inventory_event.idempotency_key`
  (shop + kind + ref unique). Retry of that key finds the existing row
  and does not insert a second.
- Frequency trigger: `exception_ref = 'adjust_freq:' || sku || ':' || window_start`
  where `window_start` is UTC floor of now to 24h. One open row per
  shop/SKU/window. Later qualifying adjusts in the same window do not
  insert another row.

Lifecycle: inserted in a **separate** transaction after the adjustment
commits. Status starts `open`. This amendment does not auto-resolve.
Alert/notification failure cannot change exception status, roll back
the adjustment, or hide the evidence row.

Thresholds (defaults, configurable, not accounting rules):

- |qty_delta| ≥ 100
- |qty_delta| ≥ 0.5 * qty_before AND qty_before ≥ 10
- count(adjust+reverse events for shop+sku in prior 24h) > 10

## 9. Authorization

Verified token + `shop_members` row. Headers are not identity.

- owner or staff: single adjust and reverse of a single adjust in that shop
- owner only: CSV quantity apply
- price-only PATCH: owner or staff; no quantity/cost mutation
- missing actor → fail closed

## 10. Freeze

While cutover is locking/frozen:

- quantity PATCH → 503, no writes
- CSV quantity → 503, no writes
- price-only PATCH allowed; must not write stock, lot cost,
  PurchaseRecord cost, or InventoryItem.cost
- mixed price+quantity → 503 for the whole request

## 11. Unchanged objects

Receive keys, outbound keys, observation ledger, refund/return records,
Sale rows, lots, PurchaseRecords, cost fields, Shopify oversale
exceptions, `:gen:1` backfill.

## 12. Migration and rollback

One atomic migrator transaction: create table, constraints, indexes,
FKs, append-only triggers, TRUNCATE deny, `TRUTH_TABLE_NAMES` add.
Rerun is no-op. Injected mid-failure leaves no partial table.

Rollback of the slice: stop dual-write; snapshot/Sale/PurchaseRecord
unchanged; `inventory_adjustment` rows remain evidence or the table is
dropped only by authorized migrator lifecycle. No WA rebuild from lots.

Recon after dual-write: `SUM(quantity_delta)` including adjust/reverse
must equal snapshot; timeout is not green; loss-class reasons have zero
Sale rows.

## 13. Acceptance-test additions (exact list)

Append to TESTS.md:

1. Absolute PATCH 10→7 writes adjust −3, snapshot 7, Sale/cost unchanged.
2. Signed PATCH −3 from 10 stores the same before/delta/after.
3. Writer never assigns client absolute onto stock.
4. Idempotent replay: no second event; original after returned; no second anomaly.
5. Same key different payload: 409; snapshot unchanged.
6. Missing UUID: 400; no write.
7. after < 0: reject; no event.
8. shrinkage/damage/theft: negative adjust; zero Sale; cost unchanged.
9. found: positive adjust; no lot; cost unchanged.
10. Reverse: opposite event; both actors; original intact.
11. Second reverse of same original: 409.
12. Reverse that would go negative: reject.
13. Concurrent adjust vs sell: no lost update; remaining ≥ 0.
14. Frozen quantity PATCH/CSV: 503.
15. Frozen mixed PATCH: 503; price and quantity unchanged.
16. Frozen price-only PATCH: price updates; quantity/cost unchanged.
17. Staff CSV: 403.
18. Owner CSV three valid existing SKUs: three events, one transaction.
19. CSV invalid row: zero events.
20. CSV conflicting duplicate SKU: file rejected.
21. CSV identical duplicate SKU: one event.
22. CSV new-item row: file rejected; zero events; no item created.
23. CSV same upload replay: no extra delta.
24. CSV new upload UUID: deltas from live qty.
25. CSV cost column ignored.
26. Header-only identity cannot adjust.
27. `create_all` does not create `inventory_adjustment`.
28. Runtime role UPDATE/DELETE/TRUNCATE denied; rows intact.
29. Grep gate: no unclassified stock writers in `services/api/app`.
30. Recon by reason/source matches snapshot.
31. Anomaly after commit for |delta|≥100; delivery failure leaves adjust committed and exception open.

PostgreSQL: concurrency, freeze, CSV atomicity, append-only, twice on
fresh disposable databases.

## 14. Exact diffs (apply only after vote)

### DESIGN.md

```diff
--- a/docs/inventory-truth-v1/DESIGN.md
+++ b/docs/inventory-truth-v1/DESIGN.md
@@ QUANTITY_CHANGING list (unchanged types)
+Live staff/owner quantity changes MAY insert event_type=adjust with
+lot_id NULL. They MUST NOT insert event_type=loss (backfill loss stays
+lot-required). Adjustments MUST NOT write Sale, lot cost, PurchaseRecord
+cost, or weighted-average cost.
@@ canonical sources after outbound-side list
+  adjust-side (AMENDMENT-1.2.0):
+    admin_adjust   admin_adjust:{shop_id}:{idempotency_uuid}
+    csv_adjust     csv_adjust:{shop_id}:{upload_uuid}:{row_identity}
+    count_adjust   count_adjust:{shop_id}:{idempotency_uuid}
+    reverse of those uses reverse_{orig_source}:{shop_id}:{orig_pk}
+    with no :seq; at most one reverse per original adjustment event.
```

### MIGRATION.md

```diff
--- a/docs/inventory-truth-v1/MIGRATION.md
+++ b/docs/inventory-truth-v1/MIGRATION.md
@@ freeze sentence
 PATCH/CSV stock overwrite stay frozen until the adjust slice.
+While frozen, price-only PATCH remains allowed and MUST NOT write
+quantity or cost. Mixed price-plus-quantity PATCH fails atomically.
@@ additive envelope
+Slice-03 (AMENDMENT-1.2.0): inventory_adjustment joins TRUTH_TABLE_NAMES.
+Uniques: (shop_id, id); (shop_id, inventory_event_id);
+(shop_id, client_idempotency_key) WHERE client_idempotency_key IS NOT NULL;
+(shop_id, csv_upload_id, csv_row_identity) WHERE csv_upload_id IS NOT NULL;
+(shop_id, reverses_event_id) WHERE reverses_event_id IS NOT NULL.
+Checks: after=before+delta; after>=0; delta<>0; reason/source/input_mode
+enums; loss-class delta<0. Append-only + TRUNCATE deny. create_all MUST NOT
+create it. CSV new-item rows are a file-level validation failure.
+inventory_exception.kind also allows adjust_anomaly.
```

### TESTS.md

```diff
--- a/docs/inventory-truth-v1/TESTS.md
+++ b/docs/inventory-truth-v1/TESTS.md
@@
+## Slice-03 adjustment acceptance tests (AMENDMENT-1.2.0)
+
+The 31 tests listed in amendments/AMENDMENT-1.2.0.md §13. PostgreSQL
+concurrency/freeze/CSV/append-only twice on disposable databases.
```

### CONTRACT.md (pointer only; no self-hash)

Apply this closed §9 text after the DESIGN/MIGRATION/TESTS diffs, and
**before** hashing. Do not put a generated timestamp or CONTRACT’s own
SHA-256 in this file.

```diff
--- a/docs/inventory-truth-v1/CONTRACT.md
+++ b/docs/inventory-truth-v1/CONTRACT.md
@@ header version line
-**Version:** `1.0.0` → `1.1.0` (AMENDMENT-1.1.0 approved and applied 2026-08-23; §8 freeze record)
+**Version:** `1.0.0` → `1.1.0` → `1.2.0` (AMENDMENT-1.2.0 approved; hashes in freezes/FREEZE-1.2.0.json)
@@ §7 current gate state
-SLICE-02 PLAN FROZEN, AWAITING IMPLEMENTATION APPROVAL
+SLICE-02 COMPLETED (NOT MERGED, NOT DEPLOYED); AMENDMENT-1.2.0 APPROVED;
+SLICE-03 PLAN FROZEN, IMPLEMENTATION STILL BLOCKED
@@ after §8
+## 9. Amendment 1.2.0 freeze record
+Resulting contract version: **1.2.0**.
+Approved amendment: `AMENDMENT-1.2.0`.
+Freeze manifest: `docs/inventory-truth-v1/freezes/FREEZE-1.2.0.json`.
+Byte hashes, algorithm, freeze timestamp, and file list live only in
+that manifest. This file does not store its own SHA-256.
+The §2 v1.0.0 and §8 v1.1.0 records remain unchanged.
```

Then write `docs/inventory-truth-v1/freezes/FREEZE-1.2.0.json` with
SHA-256 of the five hashed files (CONTRACT, DESIGN, MIGRATION, TESTS,
AMENDMENT-1.2.0). The manifest must not include itself. Procedure:
`docs/inventory-truth-v1/freezes/MANIFEST-SPEC.md`. Validator:
`scripts/validate_inventory_truth_freeze.py`.

## 15. v1.2.0 freeze file set and hash procedure

After the vote, still not implementation:

1. Apply §14 DESIGN, MIGRATION, TESTS, and CONTRACT pointer diffs.
   CONTRACT §9 must not contain a timestamp or its own hash.
2. Hash exact repository bytes of:
   `docs/inventory-truth-v1/CONTRACT.md`
   `docs/inventory-truth-v1/DESIGN.md`
   `docs/inventory-truth-v1/MIGRATION.md`
   `docs/inventory-truth-v1/TESTS.md`
   `docs/inventory-truth-v1/amendments/AMENDMENT-1.2.0.md`
   Algorithm: SHA-256, lowercase hex, no transcoding, no line-ending
   rewrite (`git hash-object --no-filters` or raw `read_bytes()`).
3. Write `docs/inventory-truth-v1/freezes/FREEZE-1.2.0.json` with
   contract id/version, `freeze_timestamp`, approved amendments, previous freeze
   pointer to CONTRACT §8 / v1.1.0, algorithm, canonical-byte rule, and
   the file hashes. Do not hash the manifest.
4. Do not edit hashed files after step 2. Timestamp and status belong
   only in the unhashed manifest.
5. Keep CONTRACT §2 (v1.0.0) and §8 (v1.1.0) byte-for-byte as
   historical tables except for the additive §7/§9/header pointer
   edits in step 1.
6. Run `python scripts/validate_inventory_truth_freeze.py --manifest docs/inventory-truth-v1/freezes/FREEZE-1.2.0.json`.

## 16. Recommendation

Approve AMENDMENT-1.2.0. The freeze-evidence defect is corrected: hashes
are non-self-referential. Substantive adjustment decisions are unchanged.
Do not implement slice-03 in the same vote.
