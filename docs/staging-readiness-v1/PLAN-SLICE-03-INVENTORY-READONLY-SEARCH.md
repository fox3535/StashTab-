# Proposed checkpoint — slice-03 inventory read-only search

**Slice:** `staging-readiness-v1 / slice-03-inventory-readonly-search`  
**Status:** `COMPLETED, STAGING ONLY (D-029)`  
**Depends on:** slice-02 schema applied to staging (`ACCEPTANCE-SLICE-02.md`)  
**Pinned commit:** `d49eca9fc31298847bd07abf42347ab691b4f974` (`main`)

Do not implement, deploy, seed, or enable writes until a named human unlock.

## Intent

Prove one authenticated, shop-isolated inventory **read** against the empty
staging tables. Do not enable writes, intake, POS checkout, adjustments,
CSV quantity, Shopify, worker, notifications, payments, or Watch.

## Existing route inventory (current FastAPI)

| Area | Routes | Staging note |
|---|---|---|
| Health | `GET /health`, `GET /ready` | Already used for identity |
| Shops | create/onboard/me/get/members | Identity kernel; leave as-is |
| Inventory reads | `GET /inventory/search`, `GET /inventory/{sku}` | Query `inventory_item` only; **candidate** |
| Inventory pulls | `GET /inventory/pulls`, `POST .../mark-pulled` | Touches `online_pull_queue` **not on staging**; keep unused |
| Admin inventory read | `GET /admin/inventory` | Queries `inventory_item`; adjacent to mutation routes |
| Admin dashboard | `GET /admin/dashboard` | Also queries `staging_item` and `sync_outbox` **not on staging**; would fail |
| Intake / staging writes | `POST /admin/intake/*`, staging commit/delete/refetch, apply-trades | Writes; remain `FEATURE_NOT_READY` or unused |
| Adjust / CSV | `PATCH /admin/inventory/{id}`, reverse-adjust, `POST /admin/import` | Writes; remain blocked |
| POS | `POST /sales/checkout` | Write; remain blocked |
| Sales history | `GET /sales/history` | Reads `sale`; not needed for this proof |
| Shopify / worker | `/sync/*`, Shopify credential routes | Off; no tokens; worker not provisioned |
| Notifications / Web Push | `/notifications/*` | Schema not on staging; stay off |
| Payments / Watch | none built | Stay out of scope |
| Inventory-truth ops | status / cutover / reconcile | Cutover must stay incomplete so writes stay 503 |

## Recommended first route

**Only** `GET {api_prefix}/inventory/search`.

This slice is a **named smoke**, not a new endpoint and not a schema change.

Reasons:

- It already exists. It is not behind `FEATURE_NOT_READY`.
- It filters inventory to the verified shop and `stock > 0`.
- It requires verified Clerk identity plus membership. Shop headers are hints.
- Empty staging returns an empty list. No seed is required.
- It does not join missing tables (`staging_item`, `sync_outbox`, `online_pull_queue`).

Do **not** use `GET /admin/dashboard` or `GET /inventory/pulls` first: they
touch tables that are not on staging.

`GET /inventory/{sku}` and `GET /admin/inventory` read the same table. They
are not the first proof. Admin list sits next to mutation routes.

Writes stay 503 `FEATURE_NOT_READY` in staging while cutover is not
`complete`. Schema apply did not enable writes.

## Authorization and failure behavior

- No bearer / invalid token → 401.
- Authenticated user without membership in the hinted shop → 403.
- Shop A token + Shop B hint → 403; empty or 200 list must never include the other shop.
- Own shop, empty tables → 200 with empty items.
- Writes (intake, checkout, PATCH quantity, CSV, cutover) stay 503
  `FEATURE_NOT_READY` while cutover is not `complete`.
- Missing extra tables (staging, outbox, pull queue) must not be exercised.

No inventory seed. Empty-table 200 is the success signal.

## Acceptance tests (if later unlocked)

1. Anonymous search → 401.
2. Spoofed headers without bearer → 401.
3. User A searches own shop → 200, `total=0`, `items=[]`.
4. User A searches User B shop → 403.
5. User B searches own shop → 200 empty.
6. PATCH/checkout/intake/import still 503 or unused.
7. `/ready` still 200 with notifications/worker/Shopify off.
8. No new tables; inventory tables still empty.

## Rollback

This slice does not change schema. Rollback is operational: stop using the
search smoke; do not enable other routes. Do not drop inventory tables.

If a later code change were approved and then rejected, revert that deploy
only. Schema stays.

## Partner mapping (read-only)

| Partner | Current | Preserve | Deviation |
|---|---|---|---|
| `vendor/mimir-partner/web_checkout_module.py` `api_search` | `GET /inventory/search` | SKU exact then name match, in-stock only | Clerk membership + `shop_id`; no desktop session; no checkout |
| `vendor/mimir-partner/core.py` SKU lookup on `InventoryItem` | same route | Shop-scoped SKU read | Partner is single-shop; StashTab must never omit `shop_id` |
| Partner intake/sale/adjust | existing write routes | Not used | Remain 503 until a later unlock |

Do not copy partner single-shop queries.

## Railway note

Staging API is still `0dd8f00`. This plan does **not** request a deploy.
Search likely already exists on that SHA. Schema apply may make a
previously failing SELECT return 200 empty. That is not accepted proof
until this slice is unlocked and the eight tests run. If the live API
cannot serve search, stop and ask for a named deploy unlock.

## Bounded review (one pass)

| Lens | Finding |
|---|---|
| Architecture | Smallest proof is an existing GET on `inventory_item` only. Do not add endpoints. |
| Partner/domain | Partner `api_search` is the analog; keep shop isolation; no checkout. |
| DB security | API already SELECT-only; search does not need INSERT. |
| Integrity | Empty-table 200; no seed; cutover stays incomplete. |
| Tenant isolation | Membership gate + `shop_id` filter is the proof. |
| Adversarial | Cross-shop 403; write probes only to confirm 503. |
| Operations | No schema, deploy, or Neon contact in this slice. |
| Liveness | Planning only; one correction below; then stop. |

## Correction (one pass)

1. Do not recommend `GET /admin/inventory` first. Dashboard and pull
   routes hit missing tables. Search is the minimum.
2. Do not treat this as new route code. It is an authorized smoke of an
   existing GET. Writes remain 503 because cutover is incomplete.
3. PLAN.md F0 now lists this proposed smoke before full inventory-truth
   proof. Schema apply (D-028) is not that proof.

## Terminal recommendation

Approve planning for `GET /inventory/search` smoke only. Keep every write
and extra-table read disabled. Implementation waits for a named unlock.

## Owner decisions required

1. Unlock slice-03 planning as the next named checkpoint, or reject.
2. Confirm `GET /inventory/search` is the only first route.
3. Confirm no Railway deploy is authorized unless search is proven missing
   on the current staging API.
