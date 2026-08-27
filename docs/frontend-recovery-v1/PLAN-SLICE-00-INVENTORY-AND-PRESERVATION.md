# Frontend recovery — slice-00 inventory and preservation

**Slice:** `frontend-recovery-v1 / slice-00-inventory-and-preservation`  
**Status:** `PLANNING COMPLETE — SLICE-01 APPROVED, IMPLEMENTATION AWAITING NAMED UNLOCK`  
**Pinned `main`:** `6a266b10639df2931e1bd37d4040b49a0efd0bd2`  
**Depends on:** D-035 F0 exit passed for frontend recovery  
**This packet is planning only.** Do not implement frontend code from this file
until a named owner unlock.

## Purpose

Inventory current, owner, partner, and preserved UI. Choose what to keep
before any rewrite. First later implementation slice should be a shared
authenticated shell plus read-only inventory.

## Boundaries

- Clerk for identity. FastAPI for business logic. Neon only through FastAPI.
- Never restore Convex.
- Do not copy dirty legacy trees over `main`.
- Do not move Python rules into React.
- Writes, Shopify, notifications, payments, Watch, and Web Push stay
  disabled or preview-only until later unlocks.
- Vendor-only product. No marketplace, escrow, or seller payouts.

## Deliverables of this planning slice

1. Screen inventory (`SCREEN-INVENTORY.md`).
2. Target frontend architecture (`ARCHITECTURE.md`).
3. Smallest first implementation proposal (`SLICE-01-PROPOSAL.md`).
4. Bounded review and one correction pass.

## Owner decisions

Recorded in `OWNER-DECISIONS.md`. Slice-01 is approved as the first code
slice. Implementation still requires a named unlock. Do not start code
from this packet.

## Explicit exclusions

No frontend code in this slice. No API changes. No schema. No flag enablement.
No legacy bulk copy.
