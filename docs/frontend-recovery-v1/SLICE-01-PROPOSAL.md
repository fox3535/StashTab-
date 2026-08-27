# Slice-01 — authenticated shell and read-only inventory

**Slice:** `frontend-recovery-v1 / slice-01-authenticated-shell-and-readonly-inventory`  
**Status:** `OWNER-APPROVED FOR PLANNING — IMPLEMENTATION AWAITING NAMED UNLOCK`  
**Pinned `main`:** `6a266b10639df2931e1bd37d4040b49a0efd0bd2`  
**Decisions:** `OWNER-DECISIONS.md`  
**Directive (prepared, not authorized):**
`DIRECTIVE-SLICE-01-AUTHENTICATED-SHELL-READ-INVENTORY.md`

## Goal

One authenticated vendor shell plus the first real backend-backed screen:
read-only inventory search. Writes stay locked and explained.

## Shell layout and navigation

**Desktop**
- Left nav: Inventory (live), POS Find (read-only). Locked: Intake, POS
  Sell, Shopify, Resticker, Import, Notifications, Payments, Watch.
- Header: shop name/chip, explicit Sign out.
- Locked items stay visible, look disabled, and on activate show
  “This feature is not ready” (503 language), not a spinner that
  succeeds.

**Tablet**
- Collapsible sidebar or top bar + sheet nav. Same items and rules.

**Mobile**
- Bottom or sheet nav with Inventory, Find, More. Sign out in More /
  account sheet. Sell and Shopify in More as disabled with explanation.

Landing and marketing stay public and outside this shell.

## Membership loading and shop selection

Authority is FastAPI membership, not Clerk org metadata and not an env
shop.

Flow after sign-in:

1. Load memberships with Bearer token. Do not send `X-Clerk-User-Id`.
2. One membership → select it and continue.
3. Multiple → show only authorized shops. A stored preference is used
   only if it is in that list.
4. Stale/unauthorized stored ID is discarded. User must pick a valid
   shop. Do not silently pick another shop.
5. Zero memberships → empty “no shop access” state, not a fake shop.

`GET /api/v1/shops/me` today returns one shop: auto-selects a single
membership; with several memberships it returns 409 unless `X-Shop-Id`
matches a membership; unauthorized hint is 403. Slice-01 may add a
**read-only** `GET /api/v1/shops/memberships` (or equivalent) listing the
caller’s shops if the selector cannot be built from existing reads.
That is the only allowed API addition. No silent `NEXT_PUBLIC_DEV_SHOP_ID`
fallback.

## Session-expired handling

- 401 or missing token: clear local shop preference if the session is
  invalid, send the user to sign-in, copy “Session expired. Sign in
  again.”
- Do not keep showing inventory from a previous session.
- Sign-out is explicit on desktop header and mobile nav; it must end
  the Clerk session and return to public landing.

## Inventory states

Use accepted read contract `GET /api/v1/inventory/search` (D-029).
Admin `/admin/inventory` list may be adapted later; it is not the first
contract because PATCH lives on that surface.

| State | UI |
|---|---|
| Loading memberships or inventory | Skeleton, not an empty-error |
| Empty | Success empty: no in-stock rows. Not a write failure. |
| Populated | Search results for the selected shop only |
| Forbidden 403 | No access. Discard stale preference. |
| No membership 404 | No shop access. Do not invent a shop. |
| Unavailable 503 FEATURE_NOT_READY | Locked/gated features only. Empty search is not 503. |
| Conflict 409 | Shop selection required. Show the selector. Discard stale preference. |
| General error | Retry; no fake rows |

Search uses Bearer + membership-validated shop hint only. The accepted
search contract returns in-stock items only.

## HTTP mapping

- 401 → session expired / sign-in
- 403 → forbidden shop; discard unauthorized preference
- 404 on memberships/`GET /api/v1/shops/me` → no shop access
- 409 → shop selection required (multi-shop, no valid preference)
- 503 FEATURE_NOT_READY → not-ready banner, never a success toast

## Accessibility

- Sign-out and shop selector are keyboard reachable and named.
- Disabled nav uses `aria-disabled` and visible reason text, not
  colour-only.
- Empty, error, and not-ready messages are in the accessibility tree.
- Focus is not trapped in the mobile or tablet sheet after close.
- Contrast meets existing dark theme; do not rely on toast alone.
- Tablet: shop selector and sign-out remain reachable without a
  hover-only control.

## Preservation mapping

Keep: product shell, inventory list/search layout, POS find density,
Bearer helper (`lib/protected-api-headers.ts`), owner visual system.
Adapt: inventory page to search-only; remove live-looking edit/save.
Retire: Quick Create, Inbox, env shop as authority.
Defer: intake commit, resticker, CSV, Shopify, notification UI (do not
copy Convex from the notification branch).
Partner: floor find speed and barcode intent; not desktop Python UI.

## API contract mapping

| Need | Contract | Class |
|---|---|---|
| Current shop | `GET /api/v1/shops/me` | read-ready |
| Membership list | `GET /api/v1/shops/me/memberships` | local read-ready (D-037); not merged |
| Inventory search | `GET /api/v1/inventory/search` | read-ready |
| Inventory PATCH / CSV / checkout / intake commit / resticker / Shopify | existing write routes | write-disabled |
| Card-resolution | merged, flag off | 503 / locked |
| Notifications / payments / Watch | not for this slice | deferred |

## Acceptance tests

1. Public landing remains reachable signed-out.
2. `/admin/inventory` signed-out → sign-in.
3. One membership → no selector, inventory loads.
4. Several memberships → selector; stored unauthorized ID discarded.
5. Empty search `[]` is success empty, not error.
6. Results are only the selected shop.
7. 401 → expired copy + sign-in.
8. 403 → forbidden copy, no rows; preference discarded.
9. 404 no membership → no-shop-access copy, no invented shop.
10. 409 → selector shown; no silent shop pick.
11. 503 / locked action → not-ready copy; never a success toast.
12. Disabled Sell/Shopify/Intake commit do not call write APIs.
13. Sign-out works on desktop, tablet, and mobile, then public landing.
14. No `X-Clerk-User-Id`; no silent dev shop fallback.
15. No Convex. No Neon from the browser.
16. Desktop, tablet, and phone layouts keep Inventory, Find, shop
    chip, and sign-out reachable.

## Rollback

Slice-01 is UI plus optional memberships GET. Rollback is revert of that
branch. No staging schema. No flag changes. Inventory truth tables
untouched.

## Exclusions

No inventory writes, POS sell, intake commit, resticker, CSV quantity,
Shopify, notification worker/service worker, payments, Watch,
card-resolution UI, shop onboarding/create, production, or Convex.
Slice-01 does not create shops for users with zero memberships.

## Owner decisions (closed)

See `OWNER-DECISIONS.md`. Remaining before code: named implementation
unlock for this slice only.
