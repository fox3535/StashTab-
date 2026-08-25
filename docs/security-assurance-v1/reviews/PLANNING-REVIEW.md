# security-assurance-v1 planning review synthesis

**Date:** 2026-08-14  
**Package:** `docs/security-assurance-v1/` **v0.3.2-draft**  
**Status:** planning only; implementation blocked; **not freeze-ready**  
**Pin:** uncommitted working tree on `feature/card-resolution-notifications`

**This file supersedes v0.2.x marketplace synthesis and v0.3.0
payments-first slice IDs.** Do not unlock `pos-accounting-foundation` or
treat that name as current.

Canonical product order is D-007 /
`docs/product-strategy/VENDOR-OS-USP-ROADMAP.md`.

Independent reviews of v0.3.1-draft:

| Role | Reviewer |
|---|---|
| Architecture | [Architecture review](50fccffe-a654-47c5-999b-41060ee5d634) |
| Database-security | [Database-security review](19c03dad-a498-4769-a7a8-d17b138695a2) |
| Application-security | [Application-security review](dd678163-6091-476e-83dc-2bfdddc54f9f) |
| Compliance | [Compliance review](1adc75b5-c623-472b-8ffd-8565c68da0ed) |
| Adversarial | [Adversarial review](acb47a07-df10-4262-9cba-641c3554a249) |
| Workflow-liveness | [Workflow-liveness review](26d91c8e-ba81-4c8a-8395-7b8d8726479a) |

Agreement is not acceptance. Clarifications after these reviews are
planning-text only.

---

## Capability classes (do not rewrite live features)

See `ROADMAP-RECONCILIATION.md`. Short form:

1. **Implemented:** inventory snapshot, staging, SKU reuse, weighted cost,
   purchase log, sales, POS cash/trade/card-label, trades, shows, sticker
   captures, resticker, Collectr, Shopify, labels, reporting, Clerk shell.
2. **Optimize in place:** event ledger under `InventoryItem`; lots from
   `PurchaseRecord`; locations/reservations; cash drawer on `ShowSession`;
   exact money migration; fail-closed identity.
3. **New and blocked:** inventory events, licensed market observations,
   Watch runs/recs, vendor-merchant card capture.
4. **Blocked by gates:** card-resolution-core-v1; identity; licenses; PCI;
   accountant letter; per-slice unlock.

---

## Shared conclusions

- Vendor-only OS. Marketplace / meetup / payouts / escrow stay withdrawn.
- Reuse-before-build is controlling. No parallel inventory, POS, or Watch.
- Live POS `card` is a label, not paid.
- Fail-open auth remains. Lots, Watch **reads**, cash close, and payments
  must not ship on it.
- D-004 and D-006 are still proposed. D-007 and **D-008** are approved
  product direction. D-008 does not unlock implementation.

### Human product resolutions (D-008) — no longer planning blockers

- One checkout = one receipt + existing `Sale` lines (parent identity).
- Immutable lots per acquisition; weighted-average snapshot retained; COGS
  method deferred.
- Electronic tender: reserve → webhook paid → deduct; cash/trade immediate.
- COGS, trade-credit booking, market-data license, PCI, provider production
  config, and production migration approval are **deferred professional
  gates**, not holes in this planning packet.

---

## Ranked findings

### P0 — Fail-closed identity must cover lots and Watch reads

Still true of **live code**. Must be closed before any unlocked B/C/D/E/F
slice. Not a reason to leave receipt/lot/reserve unspecified.

### P0 — Live `card` label still decrements stock today

Accepted current behavior for the **label** path. Future Stripe/PayPal
must not extend that path; it uses reserve-then-webhook (D-008).

### P1

- Exact-money migration mechanics (planner-owned at unlock).
- Watch E vs F still in one contract file (metrics first; signals are F).
- Tenant lifecycle overlay vs live shop create.
- Orthogonal security slices still lack IDs.
- Fail-open membership writes remain a slice entry gate.

---

## Verdict

**Do not implement, migrate, commit, push, or deploy.** Product shape for
receipts, lots, and electronic tender is decided. Professional gates are
deferred. `planning_accept` still does not start Roadmap B–F.
