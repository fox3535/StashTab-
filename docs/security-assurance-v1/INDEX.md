# security-assurance-v1

**Package ID:** `STASHTAB-SECURITY-ASSURANCE-001`  
**Version:** `0.3.2-draft`  
**Status:** `QUEUED — RESEARCH AND PLANNING ALLOWED, IMPLEMENTATION BLOCKED`  
**Created:** 2026-08-14  
**System of record:** this directory in the StashTab Git repository

Planning only. Does **not** authorize scanners, attack tools, migrations,
production access, scheduled jobs, payment integrations, Portfolio Watch,
Market Watch, prediction models, continual learning, blocking release gates,
or a frozen security contract. Does **not** authorize any security test by
existing.

## Product correction (2026-08-14)

StashTab is a **vendor-only SaaS operating system**, not a consumer
marketplace. Prior drafts that described consumer listings, meetup
fulfillment, multi-vendor carts, marketplace shipping, seller payouts,
escrow, or buyer protection are **withdrawn**.

## Non-blocking rule

Unfinished SOC 2, payments, Portfolio Watch, or Market Watch work **must not**
block card-resolution. `shop_id` tenant scoping is already a **frozen
contract** gate. Only a separately approved, named baseline control may become
an additional release blocker.

## Verified platform facts

- FastAPI owns business logic; Next.js is UI (`PLAN.md`).
- Tenant rows use `shop_id` (`ShopScopedMixin`).
- Shop context: JWT membership `.first()`, else `X-Shop-Id` with no membership
  check, else dev env. `X-Clerk-User-Id` works without Bearer even when issuer
  is set (`deps.py`, `clerk.py`). Shop invite/onboard routes skip shop context
  (`routers/shops.py`).
- `init_db()` uses `create_all` plus `_ensure_columns` ALTER on startup
  (`database.py`); worker also calls `init_db()`.
- Card-resolution: frozen contract v1.0.0; amendment 1.1.0 proposed; Web Push
  disabled.
- POS already records cash/trade and a card **settlement label**; that is not
  an approved CHD integration.
- Shopify sync already exists for a vendor’s own shop. That is not a StashTab
  consumer marketplace.

D-007 reuse-before-build and D-008 (receipt parent, immutable lots,
reserve-then-webhook) control product shape. Canonical order:
`docs/product-strategy/VENDOR-OS-USP-ROADMAP.md`.
This packet must not duplicate that roadmap or treat completed POS,
inventory, staging, sales, show, recon, resticker, reporting, or Shopify
foundations as unimplemented.

## Reading order

1. `docs/product-strategy/VENDOR-OS-USP-ROADMAP.md` (canonical; do not copy)
2. `ROADMAP-RECONCILIATION.md`
3. `SCOPE.md`
4. `TENANT-LIFECYCLE.md`
5. `PAYMENTS.md`
6. `ACCOUNTING.md`
7. `POS-STATES.md`
8. `PORTFOLIO-WATCH.md`
9. `MARKET-WATCH.md`
10. `AI-RISK.md`
11. `THREAT-MODEL.md`
12. `SOC2.md`
13. `FRAMEWORK-MAP.md`
14. `DATABASE-CONTROLS.md`
15. `TESTING-MODEL.md`
16. `RULES-OF-ENGAGEMENT.md`
17. `LEARNING-LOOP.md`
18. `WORKFLOW-LIVENESS.md`
19. `AUTOMATION-STATES.md`
20. `PHASED-IMPLEMENTATION.md`

## Precedence

1. Safety and law  
2. Frozen workflow contract (frozen amendments only)  
3. Explicit human approvals  
4. Current phase gate  
5. Assigned task  
6. Role-specific guidance  
7. General preferences  

Every **gate** has exactly one accountable adjudicator. Agent narrative cannot
complete a gate.

`reviews/PLANNING-REVIEW.md` is current after v0.3.2 (D-008). Older
marketplace conclusions and payments-first slice IDs are withdrawn.
