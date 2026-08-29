# Migration and reconciliation (locked wording)

No migration is run from this document.

## Compatibility

1. Additive unique indexes `(shop_id, id)` on live `inventory_item`,
   `purchase_record`, `sale` — **indexes only**, not column rewrites.
   Exception authorized only by AMENDMENT-1.3.0: one additive nullable
   column `purchase_record.client_idempotency_key VARCHAR(36)` plus the
   partial unique `uq_purchase_record_shop_client_key`; no type change,
   no rewrite, no drop.
2. Add `acquisition_lot`, `inventory_event`, and
   `inventory_truth_cutover` with `UNIQUE (shop_id, id)` on the first two
   and `UNIQUE (shop_id, generation)` on cutover. Composite FKs: `DESIGN.md`.
3. Do not drop `purchase_record`. Do not change snapshot float types.
4. Lot money: `Numeric(12,2)`.

## 4. `create_all` must not create the new tables

Verified fact: `init_db()` in `app/database.py` calls
`Base.metadata.create_all`. API, worker, seed, and image backfill call
`init_db()`.

**Locked path:**

- `AcquisitionLot`, `InventoryEvent`, and `InventoryTruthCutover` MUST
  live in a module that is **not** imported by `app.models`,
  `app.models.__init__`, `app.database`, `app.main`, or `worker`.
- The approved migrator is the **only** process that imports that module
  and applies DDL.
- Tests that call `create_all` on application `Base` MUST NOT create
  these tables.

**Acceptance check (must fail the PR if red):** start the API `init_db`
path against an empty schema fixture. Assert tables `acquisition_lot`,
`inventory_event`, and `inventory_truth_cutover` **do not exist**. Run
the migrator. Assert they **do exist**.

Existing models may still use `create_all`. This packet does not remove
that for live tables.

## Order (cutover — no opening-gap vs live-receive race)

1. Fail-closed identity on inventory mutation routes (separate slice).
2. Unlock + approved schema apply (indexes, then new tables, then FKs).
3. **Freeze first** for that shop: reject staging commit, trade receive,
   POS finalize, Shopify stock pull/push, admin PATCH stock, and CSV
   stock overwrite. Dual-write code may be deployed but **must not**
   accept live receives until freeze lifts.
4. **Per-shop cutover transaction** (watermark + lock):
   - Insert `inventory_truth_cutover (shop_id, generation=1, status=
     locking, frozen_at=now())` or fail if a completed gen:1 exists.
   - `SELECT … FOR UPDATE` on that shop’s `inventory_item` and
     `purchase_record` rows used in this generation.
   - Inside the same transaction: backfill A then B. Gap is computed
     from this locked snapshot. No live receive can commit during freeze.
   - Set cutover `status=complete`, `opened_at=now()`.
   - Commit.
5. Enable receive dual-write (staging commit + trade) **and** lift freeze
   for intake/trade/POS/Shopify in the same release step. PATCH/CSV stock
   overwrite stay frozen until a later `adjust` slice.
   While frozen, price-only PATCH remains allowed and MUST NOT write
   quantity or cost. Mixed price-plus-quantity PATCH fails atomically.
6. Recon must be 0. Timeout is **not** green.
7. Sell/Shopify dual-write is a later PR gated on AMENDMENT-1.1.0;
   shipping order: outbound slice → adjust slice → production cutover.

## Slice-02 additive envelope (AMENDMENT-1.1.0)

Same locked discipline as above, extended:

- `inventory_channel_observation`, `refund_record`, `return_record`,
  `inventory_exception` join `TRUTH_TABLE_NAMES`; startup `create_all`
  can never create them.
- Unique arbitration:
  `uq_obs_shop_channel_ref (shop_id, channel, channel_ref)` on
  `inventory_channel_observation`.
- All parent references are composite `(shop_id, id)` FKs
  `ON DELETE RESTRICT`.

## Slice-03 additive envelope (AMENDMENT-1.2.0)

Same locked discipline. `inventory_adjustment` joins `TRUTH_TABLE_NAMES`.
Uniques: `(shop_id, id)`; `(shop_id, inventory_event_id)`;
`(shop_id, client_idempotency_key)` WHERE `client_idempotency_key IS NOT NULL`;
`(shop_id, csv_upload_id, csv_row_identity)` WHERE `csv_upload_id IS NOT NULL`;
`(shop_id, reverses_event_id)` WHERE `reverses_event_id IS NOT NULL`.
Checks: after=before+delta; after>=0; delta<>0; reason/source/input_mode
enums; loss-class delta<0. Append-only + TRUNCATE deny. `create_all` MUST NOT
create it. CSV new-item rows are a file-level validation failure.
`inventory_exception.kind` also allows `adjust_anomaly`.

## F2 controlled-receive envelope (AMENDMENT-1.3.0)

Same locked discipline. Staging only. Live migrator adds the nullable
client key column and partial unique on `purchase_record` before any
truth step; rerun no-op; injected failure leaves nothing partial.
Runtime grant envelope for `stashtab_api` replaces SELECT-only on
exactly `inventory_item` (SELECT, INSERT, UPDATE (stock, cost)),
`purchase_record` (SELECT, INSERT), `acquisition_lot` (SELECT, INSERT),
`inventory_event` (SELECT, INSERT), plus USAGE on their four identity
sequences. No DELETE, TRUNCATE, DDL, ownership, or migrator assumption.
Truth keys unchanged: `purchase_record:{shop_id}:{purchase_record.id}`.
Live receive still requires a completed gen:1 cutover for that shop;
unrelated writes after cutover fail with controlled 503
FEATURE_NOT_READY, never raw privilege errors. Rollback disables the
route and revokes grants; evidence rows remain.

## Backfill (same keys as live dual-write)

### A — Purchase records

One transaction: lot + `receive`, key
`purchase_record:{shop_id}:{purchase_record.id}` on **both** rows.
Collision/retry: `DESIGN.md` §2.

### B — Opening gap (inside the cutover lock)

```text
gap = inventory_item.stock - SUM(quantity_delta for that shop+sku)
```

If `gap > 0`: one `opening_balance` lot + `receive` `+gap`, key
`opening:{shop_id}:{inventory_item.id}:gen:1`. Cost = snapshot WA.
Label **synthetic / provisional**.

If `gap < 0`: one shrinkage lot with `quantity_acquired = abs(gap)` and
one `loss` event `quantity_delta = -abs(gap)`. Reason
`backfill_shrinkage_provisional`. **Not a Sale. Do not insert a `Sale`
row.** Key `shrinkage:{shop_id}:{inventory_item.id}:gen:1` on both rows.

If `gap = 0`: write nothing.

### Safe retry

Same gen:1 keys. Follow `DESIGN.md` §2. Do **not** mint `:gen:2` unless
the executive sponsor authorizes a new generation after `REJECTED`.
If cutover `status=complete`, retry is no-op. If `locking` after crash:
re-enter the same transaction procedure; do not lift freeze until
complete or `failed_permanent`.

## Reconciliation

```text
event_remaining(sku) = SUM(quantity_delta) for shop+sku
unaccounted if event_remaining != inventory_item.stock
```

## Rollback

Dual-write off. Snapshot, `Sale`, `PurchaseRecord` unchanged. New tables
unused or dropped. Cutover row may remain as evidence. No WA recompute
from lots.
