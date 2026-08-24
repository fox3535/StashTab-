# inventory-truth-v1

**Package ID:** `STASHTAB-INVENTORY-TRUTH-001`
**Version:** `1.2.0`
**Slice id:** `slice-01-receive-foundation`
**Status:** `CONTRACT v1.2.0 FROZEN — SLICE-03 ACCEPTED — NOT MERGED — NOT DEPLOYED`
**Frozen on:** `2026-08-20`
**System of record:** `CONTRACT.md`

Planning contract frozen; contract bodies unchanged. Slice
`slice-01-receive-foundation` implemented 2026-08-23 under a named human
unlock after identity acceptance, then **accepted by the human owner the
same day**: see `ACCEPTANCE-SLICE-01.md`. `slice-02-outbound-events` was
implemented in an isolated worktree from checkpoint `132f0f5` and
**accepted by the human owner 2026-08-24**: see `ACCEPTANCE-SLICE-02.md`.
It is **not merged and not deployed**. AMENDMENT-1.2.0 is approved;
contract v1.2.0 and the slice-03 adjustment plan are frozen. Implementation
of slice-03 is accepted and not merged. See `ACCEPTANCE-SLICE-03.md`.

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
10. `DIRECTIVE-SLICE-02.md` (v3 outbound plan — frozen against v1.1.0)
11. `reviews/SLICE-02-PLANNING-REVIEWS.md` (5 review verdicts + corrections)
12. `ACCEPTANCE-SLICE-02.md` (human acceptance record, 2026-08-24)
13. `amendments/AMENDMENT-1.2.0.md` and `freezes/FREEZE-1.2.0.json`
14. `DIRECTIVE-SLICE-03.md` (adjustment plan frozen against v1.2.0)
15. `ACCEPTANCE-SLICE-03.md` (human acceptance record, 2026-08-24)
