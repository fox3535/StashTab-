# Database controls (planning)

Implementation of these controls is blocked. Intended PostgreSQL bar for later
separately approved slices.

## 1. Verified tenant identity

**Current fact:** If `clerk_user_id` is set (from verified JWT **or** unverified
`X-Clerk-User-Id` even when issuer is configured), shop is `ShopMember.first()`
and `X-Shop-Id` is ignored. If no user id, `X-Shop-Id` is trusted with **no**
membership check, else env `DEV_SHOP_ID` / `NEXT_PUBLIC_DEV_SHOP_ID`.

**Required before any payment, ledger, inventory-event, lot, Portfolio Watch, or Market Watch slice (entry gate):**

- Production: verified JWT + `ShopMember` + **explicit authorized shop**
- Reject shop-id-only and header-user-id-only on mutating, financial,
  analytics-**read**, analytics-write, lot, and inventory-event routes
- Dev fallback behind an explicit local-only flag, not `debug=True`

Adjudicator: Control owner — Identity.

## 2. Centralized authorization

**Current fact:** Many routers use `get_shop_context`. Notification routes use
`get_notification_context` (Bearer required when issuer set). **Shop create,
onboard, get-by-id, list members, and invite do not use shop context** and are
effectively unauthenticated. `ShopMember.role` is not enforced.

**Required later:** deny-by-default on **all** mutating routes, including
membership writes, cash-session close, and analysis-run inserts.

Adjudicator: Control owner — Application.

## 3. Tenant-aware constraints

**Current fact:** `ShopScopedMixin.shop_id` is indexed, not an FK to `shops`.
Some tables have unique `(shop_id, …)` keys. Notification deliveries still
use id-only FKs.

**Required later:**

- FK from tenant tables to `shops.id` where feasible
- Unique and composite FKs that include `shop_id` on child rows
- No cross-shop parent pointers
- Unique `(shop_id, clerk_user_id)` on `shop_members`
- **No PAN/CVV columns.** No wallet, escrow, marketplace payout, or consumer
  listing tables.

Adjudicator: Control owner — Database.

## 4. Least-privilege roles

Proposed (not created): `stashtab_app` (DML, no superuser), `stashtab_migrator`
(approved DDL only), `stashtab_backup`, `stashtab_readonly_support`.

Compose today uses superuser `mimir`. Sequence: stop production runtime
`create_all`/`_ensure_columns`, approved migrations (contract §12.8), then
drop superuser from the API role.

## 5. Proposed PostgreSQL RLS (defense in depth)

RLS is **additional**. FastAPI `shop_id` filters remain mandatory (contract
§3.1).

Sketch (unsafe until identity is fail-closed):

- `SET LOCAL app.shop_id` as **text** inside the request transaction
- `FORCE ROW LEVEL SECURITY`; app must not be table owner/superuser
- Re-set shop GUC after every `COMMIT` (worker sync reuses one session)
- Never copy unverified `X-Shop-Id` into `app.shop_id`
- Analytics tables use the same shop policy. Cross-shop market *catalog*
  observations, if any, must be non-tenant or explicitly licensed shared
  reference data — never another shop’s lots.

Do not implement RLS from this packet.

## 6. Encryption

TLS to Postgres in staging/production (`sslmode=verify-full` or equivalent).
Disk encryption at rest. Do not persist PAN. Shopify token column is named
encrypted but stored plaintext today. Webhook secrets and provider keys: env
only.

## 7. Audit logging

Authz denials, membership, cash-session close, refund recording, inventory
promotion, analysis-run create, recommendation promote-to-eval. Never log
tokens, PAN, VAPID keys, raw provider secrets, or JustTCG keys.

## 8. PITR and restore testing

WAL archiving in production hosting. Restore into isolation. **Required
step:** scrub/null Shopify and any future payment tokens; synthetic fixtures.
Restored prod credentials must not be used (ROE).

## 9. Schema change control

`init_db()` runs `create_all` and `_ensure_columns` on API and worker
startup. Conflicts with contract §12.8 in production. This package does not
add Alembic by itself.

## 10. Future records (logical only — extend live tables; not created here)

Reuse-before-build (D-007). Keep `InventoryItem` as the query snapshot.
Do **not** add a second inventory manager, POS, or Watch product.

### Extend existing FastAPI models

- `InventoryItem` — derived/maintained stock, cost, availability from
  accepted **inventory events**. Weighted-average **cost remains the
  snapshot**; lots are not merged into it (D-008)
- `PurchaseRecord` — backfill source for immutable **acquisition lots**.
  Each receive is a new lot, including same-SKU different costs. Do not
  erase lot history. Do not double-count snapshot cost vs lots
- `Sale` — **lines** on a new parent receipt/transaction (D-008). One
  checkout, one receipt, one or more lines. Subledger and tenders attach
  to the receipt; lines keep SKU amounts
- `ShowSession` — cash-drawer open/count/variance/approval
- `ShowPriceCapture` — vendor sticker snapshot only; **not** licensed
  market history
- Staging, resticker, Shopify outbox, Collectr recon — extend; do not fork

Electronic checkout (later): `reserve` event at session start; `sell`
only after webhook-paid; `release` on fail/cancel/expiry. Cash/trade skip
reserve and sell immediately.

### New append-only / Watch records (still blocked)

`inventory_event`; acquisition lots; `provider_event` unique
`(shop_id, provider_name, provider_event_id)`; licensed price and
sale/listing observations; liquidity/trend features; market events;
`analysis_run`; recommendations/evidence; five separate confidence
components; vendor actions; outcomes; point-in-time evaluation datasets;
`model_rule_version`.

- Recs are **excluded by default** from market observations
- Shared licensed catalog must not contain another tenant’s lots, costs,
  sales, or listings
- Fail-closed identity on **reads and writes** of lots, events, recs, cash
  close, and ledgers
- Exact money on new financial columns; migrate floats with backfill
- Positions must not hide mixed condition/variant
