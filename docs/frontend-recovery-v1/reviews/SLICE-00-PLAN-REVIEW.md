# Bounded review — frontend recovery slice-00

**Packet:** `docs/frontend-recovery-v1/`  
**Pinned `main`:** `6a266b1`  
One round. Planning only.

## Architecture

Target (Clerk → Next.js → FastAPI → Neon) matches AGENTS.md and D-024.
Risk: two shells (dashboard vs admin) and `NEXT_PUBLIC_DEV_SHOP_ID` as
real shop context. Correction: one shell; membership is shop identity.

## Product UX

Vendor-only direction is kept. Risk: Shopify, Quick Create, and POS sell
look live. Correction: slice-01 locks those affordances.

## Accessibility / responsive

Shell uses a sidebar pattern that can work on phone if POS stays a first
viewport. Correction: require desktop and phone checks in slice-01;
do not ship dashboard-only density for Find.

## Security

Bearer tokens exist. Remaining issue: shop hint and onboarding body
`clerk_user_id`. Slice-01 must not treat the hint as identity. Onboarding
body field is out of slice-01.

## Workflow liveness

401/403/503 paths are specified. No worker required. Human can complete
sign-in → empty inventory → search with no background jobs.

## Verdict

Planning is sound after the corrections below. Do not implement until
owner unlock.
