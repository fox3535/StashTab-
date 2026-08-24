# Bounded consistency check — AMENDMENT-1.2.0

**Against:** frozen contract v1.1.0; `ACCEPTANCE-SLICE-01.md`;
`ACCEPTANCE-SLICE-02.md`
**Packet:** `amendments/AMENDMENT-1.2.0.md`
**Scope:** one pass; no new review loop

| Check | Evidence | Result |
| --- | --- | --- |
| Remaining equation | DESIGN remaining = SUM(quantity_delta); adjust/reverse are QUANTITY_CHANGING | PASS |
| Slice-01 receive/opening/shrinkage keys | Amendment §6 and §11 leave them untouched | PASS |
| Slice-01 `loss` creates no Sale | Live staff uses `adjust` + loss-class reason; backfill `loss` unchanged | PASS |
| Slice-02 sell/observation/refund/return keys | Unchanged | PASS |
| Shopify oversale | Still sell-path only; adjust cannot go negative | PASS |
| `create_all` exclusion | Table listed as migrator-only | PASS |
| Append-only / TRUNCATE deny | Same as slice-02 outbound tables | PASS |
| Cost/lot/PurchaseRecord/Sale immutability on this path | Explicit writer prohibition | PASS |
| CSV new-item | File-level fail; no lotless create | PASS |
| Double reverse | Unique (shop_id, reverses_event_id) | PASS |
| Alert after commit / no stack on retry | Separate transaction; exception_ref = idempotency key | PASS |
| Frozen bodies not edited | This check and the packet only add uncommitted proposal files | PASS |
| CONTRACT self-hash avoided | v1.2.0 hashes live in `freezes/FREEZE-1.2.0.json`; CONTRACT §9 is a pointer only | PASS |
| v1.0.0 / v1.1.0 history kept | Manifest previous_freeze → §8; validator requires §2 and §8 markers | PASS |

**Amendment blocker:** none.
**Implementation:** still blocked.
**Freeze-evidence correction:** validator self-test required green before the re-vote.
