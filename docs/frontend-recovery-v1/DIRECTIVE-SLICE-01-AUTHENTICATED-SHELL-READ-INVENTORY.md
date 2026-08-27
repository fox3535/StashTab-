# Prepared directive — slice-01 authenticated shell and read-only inventory

**Status:** `PREPARED — DO NOT EXECUTE`  
**Slice:** `frontend-recovery-v1 / slice-01-authenticated-shell-and-readonly-inventory`  
**Pinned `main`:** `6a266b10639df2931e1bd37d4040b49a0efd0bd2`  
**This document is not an implementation unlock.**

When a later named unlock is given, implement only:

1. Authenticated vendor shell (desktop + mobile): nav, shop chip,
   explicit sign-out, 401 session-expired handling.
2. Shop context from FastAPI membership. Stored shop ID is a preference
   checked against memberships. One shop auto-selects. Many shops show
   a selector. Stale preference is discarded. No caller user headers. No
   silent development shop fallback.
3. First live screen: `GET /api/v1/inventory/search` with loading,
   empty, populated, 403, 404, 409, and 503 FEATURE_NOT_READY states.
   Empty search is success. Do not create a shop for zero memberships.
4. Locked actions (Shopify, POS sell, intake commit, resticker, CSV,
   notifications, payments, Watch) explain “not ready”. They must not
   look successful or do nothing silently.
5. Shop selector uses `GET /api/v1/shops/me/memberships` (D-037, local
   only until merged). Do not invent a second list route.
6. Tests for the flows above. No Convex. No Neon from the browser.

Do not implement until that named unlock. Do not enable writes or deploy.
