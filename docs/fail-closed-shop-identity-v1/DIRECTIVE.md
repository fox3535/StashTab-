# fail-closed-shop-identity-v1 — implementation directive

**Slice id:** `fail-closed-shop-identity-v1`  
**Gate id:** `identity-fail-closed`  
**Status:** `COMPLETED — ACCEPTED 2026-08-23`  
**Prepared:** 2026-08-20  
**Unlock:** D-010 (identity slice only).

Prerequisite for `inventory-truth-foundation` implementation unlock.
Does **not** start lots, events, dual-write, backfill, payments, or Watch.

## Goal

Production API identity is fail-closed:

- User comes from a verified Clerk Bearer JWT.
- Shop comes from an explicit `ShopMember` row for that user.
- Caller-supplied `X-Shop-Id` and `X-Clerk-User-Id` are never enough in
  production.

Keep a **named** local/test bypass that cannot turn on in production.

## Current paths (verified)

### API request context

`get_shop_context` accepts a Clerk user, else trusts `X-Shop-Id` with no
membership check, else `DEV_SHOP_ID` / `NEXT_PUBLIC_DEV_SHOP_ID`. Shop
membership uses the first `ShopMember` row for that user, not a chosen
shop. Used by inventory, sales, admin, reports, shows, and Shopify sync
routers.

### Clerk membership

`resolve_clerk_user_id` verifies JWT when an issuer is set **if** a
Bearer token is present. If no Bearer token, `X-Clerk-User-Id` is still
accepted even when the issuer is configured. That is fail-open.

### Invitations and shop routes

Shop create, onboard, get-by-id, list members, and invite **do not** use
shop context. Onboard trusts `clerk_user_id` in the JSON body. Invite
trusts the path `shop_id` and body user id. `/shops/me` trusts
`X-Clerk-User-Id` only.

### Background workers / Shopify jobs

The sync worker loads every `Shop` and runs Shopify sync and pending
notifications **per shop id from the database**, not from request
headers. That path is in scope: keep shop id from persisted rows, never
from a caller header.

### Notification settings

Notification routes use `get_notification_context`, which requires a
user when Clerk is configured, but still depend on `get_shop_context`
first. Tests often override the dependency. Production must not keep
header-only shop identity under those routes.

### Tests

Notification tests mix dependency overrides with raw `X-Shop-Id`
headers. Other API tests likely assume header shop identity. This slice
must update tests to JWT fixtures, explicit membership rows, or the
named dev/test bypass — not production header trust.

### Local development and UI

Next.js admin/POS/onboarding send `X-Shop-Id` and sometimes
`X-Clerk-User-Id`. Several pages hard-code `NEXT_PUBLIC_DEV_SHOP_ID`.
Clerk middleware protects UI routes; it does not protect FastAPI.
`settings.debug` defaults to true.

## Proposed boundaries (this slice)

**In**

- Fail-closed `get_shop_context` / Clerk resolver.
- Membership must match the authenticated user **and** the requested
  shop (JWT plus optional shop hint that is authorized, never sole
  identity).
- Shop create / onboard / invite / member list / get shop: authenticated
  owner/member rules; no anonymous membership writes.
- Named dev/test bypass (see below).
- Tests for the acceptance list.
- UI clients send Bearer tokens; shop hint only as an authorized
  selector.

**Out**

- Inventory lots/events, dual-write, backfill, migrator tables.
- Payments, Watch, Web Push enablement, RLS, removing `create_all` for
  existing models.
- Changing Clerk billing or Convex webhooks except if they forge shop
  membership (they must not).

## Dev/test mechanism (proposed; needs human confirm)

Allowed **only** when all are true:

- Process is not production (`ENVIRONMENT` / `APP_ENV` is not
  `production`).
- `debug` is true.
- `STASHTAB_ALLOW_DEV_IDENTITY=1` is set.

Then a documented header or env shop id may resolve a fixture shop.
If any production signal is set, headers are ignored and requests
without a verified JWT + membership fail closed.

Pytest should prefer dependency overrides or signed test helpers over
production header trust.

## Acceptance tests (must exist before identity `completed`)

1. Production-like settings (`debug` false or env `production`):
   `X-Shop-Id` alone → 401/403 on inventory mutation and membership
   write.
2. Same settings: `X-Clerk-User-Id` alone, including with issuer
   configured → 401/403.
3. Valid JWT, no membership → 403.
4. Valid JWT, membership in shop A, hint/body for shop B → 403.
5. Valid JWT + matching membership → allowed; `shop_id` is the member
   shop, not an unverified header.
6. Shop invite/onboard/create without JWT → rejected.
7. Worker/Shopify job still scopes by persisted `shop.id`, not headers.
8. Notification preference/subscription routes cannot bind another
   shop via headers.
9. With production signals on, `STASHTAB_ALLOW_DEV_IDENTITY` does not
   re-enable header trust.
10. With the named local bypass on (non-production), a documented
    fixture shop still works.

## Rollback

Feature flag or settings default: restore previous resolver only in
non-production. Production stays fail-closed once enabled. No inventory
schema in this slice, so rollback is code/settings only. Snapshot,
`Sale`, and `PurchaseRecord` unchanged.

## Genuine human decision blockers

1. **Exact production detector** — which env flags mean production
   (recommend: `APP_ENV=production` **or** `debug=false` both fail-closed).
2. **Multi-shop users** — today the API picks the first membership.
   Confirm: require an authorized shop selector checked against
   membership (not a trusted header identity).
3. **Public shop create/onboard** — confirm these require a verified
   Clerk user and that the body cannot name a different `clerk_user_id`.
4. **Implementation unlock** for this slice — still required before any
   code. This file is not that unlock.
