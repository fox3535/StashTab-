# inventory-truth-v1

**Package ID:** `STASHTAB-INVENTORY-TRUTH-001`  
**Version:** `1.0.0`  
**Slice id:** `slice-01-receive-foundation`  
**Status:** `SLICE-01 COMPLETED (ACCEPTED) — SLICE-02 AWAITING PLANNING APPROVAL`  
**Frozen on:** `2026-08-20`  
**System of record:** `CONTRACT.md`

Planning contract frozen; contract bodies unchanged. Slice
`slice-01-receive-foundation` implemented 2026-08-23 under a named human
unlock after identity acceptance, then **accepted by the human owner the
same day**: see `ACCEPTANCE-SLICE-01.md`, with PostgreSQL acceptance
evidence in `reviews/SLICE-01-PG-ACCEPTANCE.md` (14/14 criteria pass;
blocking CI job added). The proposed directive for
`slice-02-outbound-events` is prepared but not implemented:
`DIRECTIVE-SLICE-02.md`.

## Holds (must stay true)

- Rollback leaves `InventoryItem` snapshot and `Sale` rows unchanged.
- Receive-first slice does not rewrite Sale, Shopify, Watch, payments, or
  reservations.
- Fail-closed shop identity is a **separate** implementation entry gate.
  This packet does not implement it.

## Closed planning path (complete)

```text
CORRECTION_IN_PROGRESS
  → READY_FOR_FREEZE_CHECK
  → FROZEN
```

Amendments require a separately versioned proposal. See `CONTRACT.md` §6.

## Reading order

1. `CONTRACT.md`
2. `GATES.md`
3. `DESIGN.md`
4. `MIGRATION.md`
5. `TESTS.md`
6. `reviews/FREEZE-CHECK.md` (freeze evidence)
7. `reviews/SLICE-01-IMPLEMENTATION.md` (implementation record)
8. `reviews/SLICE-01-PG-ACCEPTANCE.md` (PostgreSQL acceptance evidence)
9. `ACCEPTANCE-SLICE-01.md` (human acceptance record, 2026-08-23)
10. `DIRECTIVE-SLICE-02.md` (v3 outbound plan — ready for freeze decision)
11. `reviews/SLICE-02-PLANNING-REVIEWS.md` (5 review verdicts + corrections)
