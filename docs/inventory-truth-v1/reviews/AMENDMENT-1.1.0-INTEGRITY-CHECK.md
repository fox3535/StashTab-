# AMENDMENT-1.1.0 — bounded integrity check

**Date:** 2026-08-23 · **Scope:** one bounded check, per owner instruction
· **Result:** 5/5 PASS → slice-02 plan frozen against contract v1.1.0.

| # | Proof | Method | Result |
|---|---|---|---|
| 1 | Slice-01 receive/backfill keys and evidence unchanged | Diff review of applied changes: DESIGN §2 additions are purely additive (receive-side block reproduced verbatim from v1.0.0); MIGRATION backfill section untouched; no `inventory_truth` code, migrator, or test file modified (working-tree verification). Slice-01 PG evidence hashes predate the amendment and remain the accepted record. | PASS |
| 2 | Same-key oversale retries cannot stack exceptions | Binding interpretation §17.1 + directive §6: exception lookup is by canonical order-line key before insert; unique arbitration `(shop_id, channel, channel_ref)` makes retry and replay hit the committed observation row; insert path is insert-or-get-existing within one transaction (idempotent + concurrency-safe). Stacking occurs only for genuinely distinct order-line keys. | PASS |
| 3 | No similarity signal can automatically link or compensate | Amendment §14 hard prohibition is contract text; directive v3 removed all similarity match bases and merchant self-declaration from the write path; compensating events require verified provider link / trusted system-minted link / explicit authorized human resolution with audit record. No code path in scope can do otherwise. | PASS |
| 4 | Three pre-implementation decisions closed | Owner vote §17 closes: ledger-vs-index (keep ledger), alert routing (always exception; conditional Web Push; SMS out), POS 409 with stable code. All three were classified "required before implementation" or "amendment-vote" in the decision list; all now binding text. | PASS |
| 5 | Production-cutover decisions recorded as gates, not loop blockers | GATES.md carries: manual-resolution workflow required before production outbound cutover; resalable definition owned by vendor at return time; adjust-slice completion before production cutover; retention policy as named follow-up with no-auto-delete default. None blocks planning/implementation loops. | PASS |

No new findings. Check complete; no further review cycle opened.
