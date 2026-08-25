# slice-02-outbound-events — planning reviews and correction record

**Date:** 2026-08-23
**Reviewed:** `DIRECTIVE-SLICE-02.md` v2
**Correction pass:** ONE bounded pass → v3 (current document)
**Final verification:** one re-read of v3 against every finding below

## Review verdicts (independent, planning-only)

| Review | P0 | P1 | P2 | Verdict on v2 |
|---|---|---|---|---|
| Architecture | 1 | 3 | 3 | Not ready — race mechanism inert cross-channel |
| Data-integrity | 3 | 2 | 3 | Not ready — sibling-line loss, loser semantics, key instability |
| Database-security | 0 | 4 | 3 | Directionally sound; governance gaps |
| Adversarial/concurrency | 2 | 2 | — | Not ready — arbitration inert; false-declaration merge |
| Workflow-liveness | 3×P1 | — | 2 | Stall risks in exception/adjust/amendment paths |

## Findings → corrections mapping (v3)

| Finding | Correction in v3 |
|---|---|
| Arch F1 / Adv F1 P0 / DI P0-2: disjoint txn_refs never contend; double decrement survives; loser semantics contradict quantity equation | Replaced correlation-string arbitration with per-line observation ledger (`inventory_channel_observation`, unique `(shop_id, channel, channel_ref)`); same-channel races arbitrate transactionally with loser rolling back BEFORE any stock write; cross-channel duplicates are fail-visible via duplicate-suspicion exceptions, never auto-arbitrated |
| DI P0-1: per-order registry uniqueness drops sibling lines | Ledger is per-line (`order_id:line_id`); multi-line orders each get their own row/event |
| DI P0-3: `:short` key chosen from live stock enables double-count after restock | `:short` suffix removed entirely; single stable line key; short marker lives in stored delta + reason field; contradictory retries become failed_permanent |
| Adv F2 P0: false merchant declaration silently suppresses a genuine sale | All merchant-declaration match bases removed from write path; nothing can take a linked/no-op branch across channels; duplicates surface as exceptions for human resolution |
| Arch F3 / DI note: `:short` violates frozen key grammar | Removed; canonical grammar untouched. Remaining additions (two new outbound source keys, migration envelope) packaged as a required CONTRACT §6 amendment vote — promoted from open question to blocking decision Q1 |
| Arch F2 P1: txn_ref column on Sale exceeds frozen indexes-only migration envelope | Sale-side column dropped; lineage joins through events' populated `sale_id` FK |
| Arch F4 P1: lotless sell events lack collision-rule counterpart | Outbound counterpart trio defined (event ↔ observation ↔ Sale) with full five-step analogue incl. event-without-Sale → failed_permanent |
| Adv F3b: poison-batch abort on PermanentPairError | Pull loop catches per-line failed_permanent, records, continues batch |
| Adv F4 / WL: freeze backlog burst; rollback wording contradicted shipped freeze behaviour; OnlinePullQueue check-then-insert race | Rollback section rewritten (drain-under-legacy-rules + reconciliation checkpoint before dual-write resumes); ledger uniqueness makes scheduler overlap transactionally safe |
| DBsec F1: create_all-prevention unstated for new tables | All four structures extend TruthBase + TRUTH_TABLE_NAMES; gate test added (§8 item 12) |
| DBsec F2: parent refs lack composite FKs | refund/return references are composite `(shop_id, id)` FKs ON DELETE RESTRICT |
| DBsec F3 / DI P2-1: append-only unenforced | DB-level REVOKE or trigger committed; negative PG test added |
| DBsec F4/F5: externally-influenced txn_ref validation | Moot in v3: no externally supplied correlation strings exist; only native channel identities are stored |
| DBsec F7: exception access roles | Read = verified membership; resolution = explicit authorized role + audit (follow-up flow) |
| DI P1-1: post-hoc linkage undefined | Resolution flow may only emit compensating reverse events; no rewrite/delete ever |
| DI P2-2/P2-3: return-event atomicity; lineage vs 60-char reason | Same-transaction pair pattern; sell events populate sale_id FK |
| WL P1s: exception-resolution owner/gate missing; adjust-before-cutover absent from GATES.md; unresolved amendment question stalls unlock | Exception resolution named follow-up flow with role+audit; ordering now recorded in GATES.md; amendment question became blocking decision Q1 |
| WL P2s / Arch F5/F6/F7: linkage UX ownership, alert ack, D-008 note, registry duplication, refund ref ambiguity | Captured as bounded decisions Q2/Q3/Q8; D-008 forward-compat noted; refund references pinned to the outbound event |

## Final verification

One re-read of v3 confirmed: no silent-merge or guessed-no-op path remains;
every legacy invariant has a test; all new DDL stays migrator-only; the
quantity equation holds under race, retry, over-sale, and freeze-drain
scenarios; remaining decisions are enumerated, named, and bounded.

## Recommendation to owner

Proceed to freeze decision. Blocking prerequisite: the §10 Q1 contract
amendment vote.
