# Slice-02 partner mapping (SKU, purchase, sale, quantity)

Pinned to `d81e7c81aa03d72c1a236c481638808e9d05d759`. Runtime behavior is unchanged.

| Partner | StashTab | Preserve | Deviation | Proof |
|---|---|---|---|---|
| `vendor/mimir-partner/database.py` inventory / purchase / sale models | `InventoryItem`, `PurchaseRecord`, `Sale` | SKU snapshot, purchase row, sale line, quantity fields | `shop_id`; Clerk; no `create_all` on staging | live migrator column contract + rehearsal inserts |
| `vendor/mimir-partner/logic.py` intake commit writing vault rows | `app/logic/intake.py` | Persistent SKU onto `inventory_item` | Dual-write and `staging_item` not in this slice | FEATURE_NOT_READY remains |
| `vendor/mimir-partner/logic.py` trade writing purchase rows | `app/logic/trades.py` | Purchase as acquisition evidence | Dual-write gated | routes stay off |
| `vendor/mimir-partner/logic.py` checkout completing a sale | `app/logic/sales.py` | One sale line, snapshot decrement | Outbound truth gated | POS stays off |
| wipe helpers in `database.py` | none | Do not port | Destructive wipe forbidden | no route |

`staging_item`, Shopify, Collectr recon, and worker functions are out of this slice.
