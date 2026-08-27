# Bounded review — F1 slice-01 plan

**Packet:** `docs/frontend-recovery-v1/` plus `PLAN.md` F1 and D-036  
**Pinned `main`:** `6a266b10639df2931e1bd37d4040b49a0efd0bd2`  
One architecture / UX / accessibility / security / liveness round.
Docs only. No frontend implementation.

## Architecture

Target remains Clerk → Next.js → FastAPI → Neon. Shop authority is
membership, not env shop ID. First live screen is D-029 search, not
admin PATCH. Optional read-only memberships GET is the only allowed
API add, because `GET /api/v1/shops/me` returns one shop or 409, not a list.

## Product UX

Shell, public landing, explicit sign-out, and locked not-ready writes
match owner decisions. Empty search is success. Disabled actions must
explain not-ready.

## Accessibility / responsive

Sign-out, shop selector, and locked-nav reasons must be named and
keyboard reachable on desktop, tablet, and phone. Do not rely on
toast-only copy.

## Security

No `X-Clerk-User-Id`. No silent development shop fallback. Stored shop
ID is a preference checked against memberships. 401/403/409/503 are
mapped. Slice-01 must not onboard or create shops.

## Workflow liveness

Human path: public landing → sign-in → memberships → (auto-select or
selector) → inventory search empty or populated. No worker. Locked
nav does not call writes.

## Verdict

Planning is sound after the one correction pass. Implementation is not
unlocked.
