# Proposed first implementation slice

**Slice:** `frontend-recovery-v1 / slice-01-authenticated-shell-and-readonly-inventory`  
**Status:** `PROPOSED — DO NOT IMPLEMENT until named owner unlock`  
**Depends on:** owner approval of slice-00 planning (this packet) and D-035

## Goal

One authenticated vendor shell plus read-only inventory search/list.
No writes. No Shopify. No POS checkout. No card-resolution UI yet.

## In scope

- Shared authenticated layout: nav, shop context from membership, explicit
  sign-out, session-expired handling.
- Inventory page: search, empty success, loading, 401, 403, 503
  `FEATURE_NOT_READY`.
- Locked/preview treatment for Intake, POS sell, Shopify, settings writes.
- Desktop and one phone viewport.
- Tests for the states above. No Convex.

## Out of scope

- Inventory PATCH, intake commit, staging commit, checkout, CSV, resticker.
- Notification settings, service worker, Web Push.
- Dashboard charts bound to live data.
- Onboarding shop create (unless already required to obtain a shop).
- Migrating card-resolution into the UI.

## Acceptance

1. Signed-out user hitting `/admin/inventory` is sent to sign-in.
2. Signed-in member sees empty inventory as success when search returns [].
3. Search uses FastAPI read contract with Bearer token.
4. Cross-shop or non-member access shows 403, not another shop’s rows.
5. Session expiry shows sign-in, not a raw stack trace.
6. Locked nav items do not look like live tools.
7. Flag-off card-resolution and write endpoints never appear “ready”.
8. No Neon access from the browser. No Convex.

## Owner decisions

1. Approve this as the first code slice.
2. Shop context: membership API vs remaining local shop hint for
   local-only demos.
3. Whether POS Find is in slice-01 (read-only) or waits.
Recommended: include POS Find as the same read search, sell locked.
