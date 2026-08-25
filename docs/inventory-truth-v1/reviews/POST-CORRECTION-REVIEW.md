# inventory-truth-v1 post-correction review

**Date:** 2026-08-20  
**Packet:** `docs/inventory-truth-v1/` v0.1.0-draft (final text; not
superseded PLANNING-REVIEW wording)  
**Status:** `POST-CORRECTION REVIEW COMPLETE — AWAITING FREEZE DECISION`  
**Pin:** uncommitted working tree  
**This review is not freeze, unlock, or identity implementation.**

Independent reviewers (agreement is not acceptance):

| Role | Reviewer |
|---|---|
| Architecture | [Architecture](9c971201-54bf-4846-89c6-c881b02295e0) |
| Data-integrity | [Data-integrity](689c22c0-90b9-4d0f-8224-5939c0f459a6) |
| Database-security | [Database-security](35602a3f-e0cf-4c2a-ad45-c687fdda06b9) |
| Adversarial/concurrency | [Adversarial](dcb1ac03-bb1e-4fe1-acf7-9d492ed93d98) |
| Workflow-liveness | [Liveness](cf0f039c-2a2d-4ac1-afd9-a2b1a6f3c66f) |

---

## Freeze recommendation

**Do not freeze.** P0/P1 planning defects remain. Do not implement lots,
migrations, or fail-closed identity from this review.

---

## P0 / P1 — block plan freeze

**P0 — Remaining filter vs overlay events.** Remaining is “sum of event
deltas” and also “reserve/release do not change remaining.” Recon uses
the unfiltered sum. Lock remaining/recon to quantity-moving types only
(`receive`, `sell`, `loss`, `adjust`, `return`, `reverse` of those).

**P0 — Dual-write vs backfill keys still forked.** Design lists one key;
migration still allows `:receive` suffix or “identical prefix.” Skip-if-lot-
exists can strand a lot with no receive. Lock one string per source; skip
only when **both** lot and receive exist; repair otherwise. Same string
on the two tables is allowed.

**P0 — Cross-shop FKs not implementable as written.** Composite keys need
unique `(shop_id, id)` on live `inventory_item` / `purchase_record` /
`sale`. Migration says do not alter those tables. Purchase FK is still
“later.” Sale and reverse pointers are not composite.

**P0 — `create_all` footgun.** “Do not register models” is advice. Gates
leave startup `create_all` in place. New models on the shared Base would
auto-create on boot.

**P0 — Planning gates have no exit.** No named `independent_review` /
`planning_accept` owner, evidence, timeout, terminal, or escalation.
Review can loop. Unlock vs §12.8 apply can deadlock.

**P1 — TESTS.md still says “shrinkage sell.”** Design/migration say `loss`
and no new Sale row. Unlock is “TESTS.md passes.”

**P1 — Cutover races.** Dual-write on before backfill; freeze is only
PATCH/CSV. Staging/trade/POS/Shopify can move stock during opening-gap
math. Optional `lot_balance` can become a second remaining.

**P1 — Card-label vs reserve.** Design says not electronic tender. Tests
still require reserve/release math in this slice.

---

## Checks that hold

| Check | Result |
|---|---|
| Receive counted once (intent) | Header qty is evidence, not added again |
| Rollback | Snapshot, Sale, PurchaseRecord left intact |
| Receive-first vs Sale/Shopify/Watch/payments | First PR omits those writes |
| Identity is a separate entry gate | Stated; **not implemented here** |

---

## Implementation acceptance evidence (after freeze + identity + unlock)

- One receive per source; remaining = filtered event sum
- Dual-write then backfill is a no-op; crash repair completes the pair
- Cross-shop pointers rejected
- Startup does not create the new tables
- Rollback drill: POS/intake/trade match pre-slice fixtures
- Identity isolation tests live on the **identity** slice; this slice must
  not merge without them

## Specialist / go-live (not freeze blockers)

COGS method; trade-credit booking; licenses; PCI; provider production
config; production migration. Accountant letter must not gate storing lots.

## Non-blocking follow-ups

Sell/Shopify dual-write; receipt parent; payments reserve; Watch; RLS;
global `create_all` removal; exact-money on snapshot floats; POS search
must not leak lot unit cost.

---

**Human next step:** freeze **no**, or send the packet back for a **single**
locked-wording pass, then one freeze/no-freeze decision. Not another open
review loop.
