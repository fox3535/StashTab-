# Inventory truth design (locked wording)

Reuse-before-build. FastAPI owns writes. Implementation blocked.

## Holds

- Do not drop, rename, or split `sale`. Receive-first does **not** write
  `Sale` rows or change `finalize_sale`.
- Do not change `InventoryItem.stock` / `cost` types or the WA formula.
- Do not enable Shopify dual-write, Watch, payments, or `reserve`/`release`
  **writes** in the receive-first slice.
- Fail-closed identity is implemented in a **separate** slice.

## 1. One quantity equation

```text
QUANTITY_CHANGING = receive | sell | loss | return | damage | adjust
                    | reverse  (only if the reversed event is QUANTITY_CHANGING)

OVERLAY            = reserve | release | move | channel_commit | quarantine
                    | reverse  (only if the reversed event is OVERLAY)
```

Live staff/owner quantity changes MAY insert event_type=adjust with
lot_id NULL. They MUST NOT insert event_type=loss (backfill loss stays
lot-required). Adjustments MUST NOT write Sale, lot cost, PurchaseRecord
cost, or weighted-average cost.

**Overlay events MUST set `quantity_delta = 0`.** They MAY set
`overlay_quantity` (int) for later availability math. They **never**
enter remaining or recon.

**Locked remaining (lot):**

```text
lot_remaining(shop_id, lot_id)
  = SUM(quantity_delta)
    FROM inventory_event
    WHERE shop_id = :shop_id
      AND lot_id  = :lot_id
```

Because overlay deltas are 0, reserve/release cannot change remaining.

**Locked recon (SKU), receive-first slice:**

```text
event_remaining(shop_id, sku)
  = SUM(quantity_delta)
    FROM inventory_event
    WHERE shop_id = :shop_id AND sku = :sku

unaccounted if event_remaining != inventory_item.stock
```

`quantity_acquired` on the lot header is denormalized evidence and **MUST
equal** the lot’s `receive.quantity_delta`. It is **never** added to the
sum.

Receive-first slice **writes** only `receive`, `loss`, and `reverse` of
those. Other types may exist in the enum but MUST NOT be inserted in
that PR. No `Sale` row is created for `loss`.

## 2. Canonical idempotency key

**Format (exact):** `{source}:{shop_id}:{source_pk}`  
Opening and shrinkage append `:gen:{n}` (this slice uses `n=1` only):  
`{source}:{shop_id}:{source_pk}:gen:1`

| source | source_pk | Used by |
|---|---|---|
| `purchase_record` | `purchase_record.id` | Live trade dual-write **and** purchase backfill |
| `staging_commit` | `staging_item.id` captured **before** delete | Live staging dual-write |
| `opening` | `inventory_item.id` | One backfill generation (`:gen:1`) |
| `shrinkage` | `inventory_item.id` | One backfill generation (`:gen:1`) |

Examples: `purchase_record:{shop_id}:{id}`,
`opening:{shop_id}:{inventory_item.id}:gen:1`.

**Uniqueness boundary:** `UNIQUE (shop_id, idempotency_key)` on
`acquisition_lot` **and separately** on `inventory_event`.

**Same string on both tables is required** for a pair (lot key == event
key). Two rows in the **same** table with that string are forbidden.

**No `:receive` suffix. No “prefix” alternative.**

**Canonical sources (complete list, per AMENDMENT-1.1.0):**

Receive-side (v1.0.0):

```text
staging_commit     staging_commit:{shop_id}:{staging_item_id}
purchase_record    purchase_record:{shop_id}:{purchase_record_id}
opening|shrinkage  {source}:{shop_id}:{inventory_item_id}:gen:1
```

Outbound-side (AMENDMENT-1.1.0):

```text
sell_sale             sell_sale:{shop_id}:{sale_id}
sell_shopify_order_line
                      sell_shopify_order_line:{shop_id}:{order_id}:{line_id}
return_refund         return_refund:{shop_id}:{return_record_id}
return_sale           return_sale:{shop_id}:{return_record_id}
reverse               reverse_{orig_source}:{shop_id}:{orig_pk}[:seq]
```

Adjust-side (AMENDMENT-1.2.0):

```text
admin_adjust   admin_adjust:{shop_id}:{idempotency_uuid}
csv_adjust     csv_adjust:{shop_id}:{upload_uuid}:{row_identity}
count_adjust   count_adjust:{shop_id}:{idempotency_uuid}
```

Reverse of those uses `reverse_{orig_source}:{shop_id}:{orig_pk}`
with no `:seq`; at most one reverse per original adjustment event.

Permitted characters `[A-Za-z0-9_.:-]`; max length 255. The ONLY
generation suffix remains `:gen:{n}`. Over-sale short sells reuse
`sell_shopify_order_line` verbatim; the unsatisfied quantity lives in
`inventory_exception`, never in a key.

**Retry / collision:**

1. Insert lot then the matching event in **one transaction**.
2. If both rows exist with matching type and qty → no-op.
3. If lot exists and event does not → insert the missing event with the
   **same** key; do not insert a second lot. Event type and delta:
   - `purchase_record` / `staging_commit` / `opening` → `receive`,
     `quantity_delta = +lot.quantity_acquired`
   - `shrinkage` → `loss`, `quantity_delta = -lot.quantity_acquired`
4. If event exists and lot does not → `failed_permanent` (does not skip).
5. Unique violation on either table → treat as retry of that pair; do
   not add quantity.

Trade receive uses **only** `purchase_record:{shop_id}:{id}` (not also
`staging_commit`), even if staging was deleted in that trade apply.

## 3. Same-shop keys (prerequisite)

**Additive unique indexes** (no column type changes). Global integer PKs
already imply uniqueness; this index is still required for composite FKs:

1. Validate: no duplicate `(shop_id, id)` (vacuous if `id` is the PK).
2. `CREATE UNIQUE INDEX` `(shop_id, id)` on live:
   `inventory_item`, `purchase_record`, `sale`.
3. Then create new tables with `UNIQUE (shop_id, id)`.
4. Then create composite FKs.

**FKs (all `ON DELETE RESTRICT`):**

| Child | Columns | Parent |
|---|---|---|
| `acquisition_lot` | `(shop_id, inventory_item_id)` | `inventory_item (shop_id, id)` nullable |
| `acquisition_lot` | `(shop_id, purchase_record_id)` | `purchase_record (shop_id, id)` nullable |
| `inventory_event` | `(shop_id, lot_id)` | `acquisition_lot (shop_id, id)` **required for receive/loss** |
| `inventory_event` | `(shop_id, inventory_item_id)` | `inventory_item (shop_id, id)` nullable |
| `inventory_event` | `(shop_id, sale_id)` | `sale (shop_id, id)` nullable; **always null in receive-first** |
| `inventory_event` | `(shop_id, reverses_event_id)` | `inventory_event (shop_id, id)` nullable |

No `TimestampMixin` / `onupdate`. Insert `created_at` only. No UPDATE of
quantity or cost. No `lot_balance` table in this slice.

`staging_item` is not an FK target after delete; the staging id lives
only inside the idempotency key.

## 4. Overlay vs this slice

`reserve` / `release` are enum values for a **later** payments slice.
Receive-first MUST NOT insert them. Cash, trade, and live `card` **label**
MUST NOT write overlay events.

## 5. What we will not build

Parallel inventory/POS; wallets; Watch tables; dropping `PurchaseRecord`
or `Sale`; treating `ShowPriceCapture` as market history.
