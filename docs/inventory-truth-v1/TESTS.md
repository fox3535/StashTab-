# Tests and rollback evidence (locked wording)

No tests are added to the app in this packet. An implementation PR must
include these before unlock. Fixtures only; no live Stripe/PayPal.

## Tenant isolation

Header `X-Shop-Id` / `X-Clerk-User-Id` cannot read or write another
shop’s lots or events. Those tests belong to the **identity** slice;
this slice must not merge without that gate `completed`. Queries always
filter `shop_id`. Composite parents include `shop_id`.

## Preserve existing behavior

- Staging commit still updates `InventoryItem.stock` and WA `cost`.
- `finalize_sale` still inserts one `Sale` per line and decrements
  snapshot stock; returned ids still work.
- Trade receive still inserts `PurchaseRecord`.
- `ShowPriceCapture` untouched.
- Rollback drill: dual-write off; POS/intake/trade match pre-slice
  fixtures; snapshot and `Sale` rows unchanged.

## Lots and events

- Two receives of the same SKU, same or different cost → two lots.
- Remaining = `SUM(quantity_delta)` only; header `quantity_acquired` is
  not added to the sum.
- Overlay types (if inserted in a later slice) have `quantity_delta = 0`
  and do not change remaining. Receive-first PR **does not insert**
  `reserve` / `release`. Cash/trade/`card` label do not write overlay.
- Duplicate `(shop_id, idempotency_key)` does not insert a second lot
  or a second event. Same string on lot and event is required.
- Live dual-write and purchase backfill share
  `purchase_record:{shop_id}:{id}` with no `:receive` suffix.
- Inventory **loss** / shrinkage is event type `loss`. It MUST NOT
  create a `Sale` row. Sale count unchanged.
- Cross-shop lot/item pointer rejected by composite FK.
- Lot/event quantity UPDATE rejected.
- CSV/admin stock change during freeze rejected.
- `init_db` / application `create_all` does **not** create
  `acquisition_lot`, `inventory_event`, or `inventory_truth_cutover`
  (migrator-only acceptance check in `MIGRATION.md`).

## Backfill / recon

- PurchaseRecord → one lot + receive; rerun is no-op.
- SKU with stock and no purchases → one opening lot + receive; rerun
  no-op.
- SKU with extra purchase qty vs stock → `loss` (not sell, not Sale).
- Opening-gap vs a concurrent receive: cutover lock + freeze; after
  complete, `unaccounted_qty = 0`. Crash during `locking` retries the
  same gen:1 keys without a second opening lot.
- Cross-shop lot id in an event is rejected.

## Out of scope for this slice’s PR

PAN; Watch; webhook paid; receipt parent; reserve/release **writes**;
Shopify dual-write; removing `create_all` for existing models.

## Slice-02 outbound acceptance tests (AMENDMENT-1.1.0)

Twelve tests per `DIRECTIVE-SLICE-02.md` §8:

1. POS/show line dual-write with populated `sale_id`; Sale rows identical
   to pre-slice behaviour.
2. POS retry → no-op; observation-ledger unique violation → no second
   decrement.
3. Pull retry / overlapping schedulers on one order → exactly one
   decrement set; transactional arbitration.
4. Cross-channel same-real-sale (both observe) → NO merge; both
   observations recorded; duplicate-suspicion exception at reconcile;
   fail-visible, never fail-silent.
5. Two genuinely distinct same-SKU/same-price sales → both counted, no
   exception, no similarity-based linking.
6. Over-sale pull (Q>S) → −S event + open exception Q−S + vendor alert +
   auto-pause; retry after restock stays a no-op (stable key); batch
   continues past poisoned lines.
7. Contradictory retry → `failed_permanent` for that line only.
8. Insufficient-stock POS cart → `409 Conflict` with stable machine-
   readable code; zero partial Sale/snapshot/lot/event mutation.
9. Refund without return → `refund_record` only; DB-level append-only
   negative test (UPDATE/DELETE fails).
10. Confirmed whole-unit resalable return → single positive event in the
    same transaction as the record; repeat confirm no-op; actor/shop/
    timestamp/original-ref/qty/outcome recorded.
11. Freeze/rollback drill: cutover-row flip refreezes outbound; drain
    under legacy rules; reconcile-zero checkpoint before dual-write
    resumes.
12. PG harness extension in blocking CI: cross-channel race, scheduler
    overlap, over-sale retry-after-restock, create_all prevention for all
    four new tables; grep-gate proves no un-inventoried stock mutation
    outside the inventoried path list.

## Slice-03 adjustment acceptance tests (AMENDMENT-1.2.0)

The 31 tests listed in `amendments/AMENDMENT-1.2.0.md` §13. PostgreSQL
concurrency/freeze/CSV/append-only twice on disposable databases.

## F2 controlled-receive acceptance tests (AMENDMENT-1.3.0)

The 8 tests listed in `amendments/AMENDMENT-1.3.0.md` §13. PostgreSQL
permissions/concurrency/idempotency/atomic-failure/append-only twice on
disposable databases; API-level equivalents with synthetic membership.
