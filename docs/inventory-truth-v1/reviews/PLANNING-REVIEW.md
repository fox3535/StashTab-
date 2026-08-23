# inventory-truth-v1 planning review synthesis

**Date:** 2026-08-20  
**Package:** `docs/inventory-truth-v1/` v0.1.0-draft  
**Status:** `QUEUED — PLANNING REVIEW REQUIRED, IMPLEMENTATION BLOCKED`  
**Pin:** uncommitted working tree

Independent reviews:

| Role | Reviewer |
|---|---|
| Architecture | [Architecture](1e32723b-e922-4686-8b48-560f8ce85c56) |
| Data-integrity | [Data-integrity](e9171789-b69c-4570-90ac-1bb91c9c4564) |
| Application-security | [Security](3b8cb57e-dd59-469b-8803-87b83f00cbb1) |
| Adversarial | [Adversarial](bb6e9309-d24e-4ec3-a2f1-0aea663e7582) |
| Compliance | [Compliance](bd3b1137-488f-41d7-bd1b-59b8b4aa177b) |
| Migration-liveness | [Liveness](5ab094c2-9e21-41b0-a0e3-66560ec01aed) |

Agreement is not acceptance. Planner corrections after reviews (remaining
math, key scheme, cutover order, `loss` vs `sell`, no `merge`, freeze CSV)
are planning-text only and **not a second review cycle**.

---

## Implementation blockers (true)

1. **Fail-closed shop identity** on inventory mutations, membership
   writes, and later lot/event reads/writes. Live header shop-id and
   header user-id still work. Do not implement lots on that model.
2. Named `implementation_unlock` for `inventory-truth-foundation`.
3. Remaining quantity must be **event-delta sum only** (receive counted
   once). Corrected in DESIGN/MIGRATION after review; must be true in
   code.
4. Dual-write and backfill **same idempotency keys**.
5. Composite same-shop FKs before unlock (not “FK later”).
6. First real schema apply via approved migrator, not silent `create_all`.

## Specialist / go-live gates (deferred, not planning blockers)

COGS method; trade-credit booking; market-data license; PCI; Stripe/PayPal
production config; production migration approval. Accountant letter must
**not** gate storing lots.

## Lower-priority follow-ups

- Full location tree, cycle counts, exact-money on snapshot floats
- Receipt parent (Roadmap C)
- Sell/Shopify dual-write (second PR)
- Reserve/release when payments unlock
- Restrict lot unit cost on POS search
- Unique `(shop_id, clerk_user_id)` on members (identity slice)
- Nightly recon job enablement after unlock; timeout ≠ green

---

## Smallest implementation slice (after identity)

Tables `acquisition_lot` + `inventory_event`; receive dual-write on
staging commit and trade; one-generation historical backfill; quantity
recon vs snapshot = 0. Freeze admin stock PATCH and CSV stock overwrite
during backfill. No sell events, no payments, no Watch, no Sale rewrite.
