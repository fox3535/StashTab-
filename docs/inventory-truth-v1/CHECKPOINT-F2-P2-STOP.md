# CHECKPOINT — F2 preflight P2 stop (notification relations missing)

Status: STOPPED. Cutover remains STOPPED. Mutable context; not frozen.
Distinct from and additional to the earlier G5 stop recorded in
CHECKPOINT-F2-G5-OWNER-EXCEPTION.md. The two stops are separate attempts and
are preserved separately.

## Attempt identity

- Authorization: one fresh read-only preflight at main
  `6c9cfa09752515171d5ddefc5644dc9ce894a3e1`, target Neon `stashtab_staging`,
  Smoke Shop B `798d40f4-0832-46c4-991b-050e1310f6c4`, generation 1, session
  role `stashtab_migrator`, Path A name-only env forwarding via `f2c`.
- File: `scripts/f2-cutover/sql/01-preflight.sql`, command 1 of 3.

## Observed result (verbatim key lines)

- Guards G1, G1b, G2, G3, G4, G5, G6, G7, G8, G9 all passed. G5 returned
  `no-unapproved-role-can-assume-stashtab_migrator` against the live staging
  catalog, confirming the merged narrowed guard.
- P1 passed: `all-13-present`.
- Halt: `psql:/sql/01-preflight.sql:49: ERROR: unrecognized configuration
  parameter "stashtab_f2.f2_preflight_p2_notification_relation_missing"`,
  `$LASTEXITCODE=3`.
- P3 through P8 never ran. No retry performed inside this unlock.

## Interpretation and mapping

- P2 requires all twelve canonical notification relations
  (`notification_event`, `notification_occurrence`, `notification_delivery`,
  `notification_source`, `push_subscription`, `notification_preference`,
  `shop_notification_policy`, `notification_audit`,
  `notification_source_observation`, `notification_occurrence_transition`,
  `notification_delivery_attempt`, `notification_recovery_park`). Fewer than
  twelve exist on staging; the exact present/absent split is pending a
  bounded catalog-only diagnostic.
- Mapped to stop condition S11 (a P0 precondition cannot be evidenced; stop
  before writing anything). No S1-S10 trigger: the file is read-only, halted
  early, wrote nothing, changed no grant or role, performed no receive and no
  deployment. Gate 1 was not reached.
- Catalog diagnostic (bounded, read-only, owner-run): `0` of the twelve
  relations present, `0` stray `notification*`/`push_subscription` relations,
  `EXIT=0`. The relations are **currently absent** from `stashtab_staging`.
  That is a catalog observation about now; on its own it does not prove they
  were never applied and later removed, and no such historical claim is made
  here.
- Approved staging provisioning (CHECKPOINT-F2-SLICE-01-STAGING-PROVISIONING.md,
  "Explicitly not this checkpoint") excluded notifications, so P2's expectation
  of twelve present relations exceeded the approved staging scope. The
  notification schema apply in
  CHECKPOINT-F2-CUTOVER-EXECUTION-PACKET.md §4.2 belongs to disposable
  `Pg16.provision()` test setup and confers no staging authority.
- Frozen boundary: AMENDMENT-1.3.0 §5 exclusions ("Exclusions (never written by
  this endpoint): ... notifications ...") and §16 explicit exclusions list
  notifications outside the cutover write scope. No frozen clause requires the
  notification relations to exist before an inventory-only cutover, so this is
  not a contract amendment and creates no provisioning dependency.

## State preserved

- Nothing written on staging by this attempt.
- No schema apply, grant, role change, notification enablement, guard edit,
  preflight retry, cutover, or receive performed.
- Correction path pending owner decision after the catalog diagnostic: either
  a mutable preflight/baseline correction that preserves the
  no-notification-write guarantee, or a named provisioning dependency with its
  exact authority.

## Correction implemented (owner-authorized, mutable files only)

The owner authorized the bounded mutable notification-presence correction. The
dependency question resolved to **no provisioning dependency**: the absent
state is the approved staging shape, so the packet was corrected rather than
staging being provisioned.

Three-state handling, identical in every notification-aware file:

| File | Check | absent | present | partial (1-11) |
| --- | --- | --- | --- | --- |
| `01-preflight.sql` | P2 | `all-12-absent` | `all-12-present` | `f2_preflight_p2_notification_relation_partial_presence` |
| `02b-baseline-notification.sql` | N0p, N0/N1 | baseline = `md5('notification-relations-absent')` marker | unchanged N0 grant + N1 row digest | `f2_notification_baseline_n0p_notification_relation_partial_presence` |
| `05b-r5-notification.sql` | NB0p, NB0, R5b | still absent + marker unchanged | unchanged digest and pinned-shop zero | `f2_gate_r5b_nb0p_notification_relation_partial_presence` |
| `07b-verify-notification.sql` | NB0pv, NB0v, F10-F12 | still absent + marker unchanged | unchanged digest, pinned-shop zero, detail | `f2_verify_nb0pv_notification_relation_partial_presence` |

A state change during the attempt fails closed in `02b`, `05b` and `07b` even
when the new state would pass a fresh preflight, because each compares the
catalog against the operator-supplied `-v notification_baseline_state` recorded
at P2/02b: `..._n0p_notification_presence_changed_during_attempt`,
`..._nb0p_notification_presence_changed_during_attempt`,
`..._nb0pv_notification_presence_changed_during_attempt`.

Inspected and unchanged **by this correction**: `02-baseline.sql`,
`03-write-locking.sql`, `04-verify-locking.sql`, `05-r1-r7.sql` (R5b is a
pointer to `05b` only), `06-write-complete.sql`,
`07-final-verification.sql` (pointer comment only),
`08-break-glass-locking.sql` (no notification reference at all), and
`lib-guards.sql` (whose separate G5 correction is already merged on `main` at
`6c9cfa0` and is not part of this change). The correction therefore does not
move the failure to a later step.

No frozen file, schema provisioning, grant, role, application code, or staging
contact was involved. Staging was not retried. Disposable PostgreSQL 16 tests
in `harness_f2_cutover.py` (`TestNotificationPresenceStates`) prove the absent
chain end to end with no receive, the present chain unchanged, partial presence
failing at preflight and baseline, and both absent-to-present and
present-to-absent transitions failing mid-attempt.

## Review correction pass (pre-merge, same authorization)

The final bounded review of draft PR #41 at head `db8ca04` found one blocking
defect outside the SQL packet and four harness coverage gaps. Both were
corrected before merge; nothing above was reverted.

Blocking defect — the mandatory audit record still required present-state-only
evidence. `AUDIT-TEMPLATE-F2-CUTOVER-GEN1.md` is required before step 1 by the
runbook §1 checklist ("Audit template copied and open") and by its own §C row
P0-10, and it is **not** in the freeze manifest, so it is mutable and belongs in
this correction. Before the fix its §D step-5 row, §H R5b row and step-7 F10/F11
rows demanded `R5b-unchanged`, `R5b-zero-rows-for-pinned-shop` and
`R5b-unchanged-at-step-7`, and §E demanded per-relation N1 rows that absent-mode
`02b` does not print. Combined with "a missing token is a failure", an operator
on the real 0-of-12 staging shape could not record the absent state at all, and
the absent tokens are string supersets of the present ones, so a substring
reading would have mis-recorded an absence proof as a presence proof.

Audit template now, per state:

| Section | `absent` | `present` |
| --- | --- | --- |
| §A | `notification_baseline_state = absent`, recorded once from P2 and reused unchanged at steps 2, 5, 7 | same, `present` |
| §D | step rows name `p2_notification_relations`, `n0p_`/`nb0p_`/`nb0pv_notification_presence_state` and "the §H pair for the state recorded in §A" | same |
| §E | `base_r5_notification` = the absence marker; N1 block annotated `N1-not-applicable-relations-absent` with the two absent columns pasted | full N1 per-relation rows |
| §H | `R5b-notification-relations-still-absent` + `R5b-zero-rows-for-pinned-shop-absent-relations` | `R5b-unchanged` + `R5b-zero-rows-for-pinned-shop` |
| §H step 7 | `R5b-unchanged-at-step-7-absent-relations` + `R5b-zero-rows-for-pinned-shop-absent-relations` | `R5b-unchanged-at-step-7` + `R5b-zero-rows-for-pinned-shop` |

§H also states the matching rule explicitly: exact string equality against the
printed column value, never substring containment; a mixed present/absent set or
any `*_partial_presence` / `*_presence_changed_during_attempt` parameter is a
failure; partial presence is never recorded as a pass and never repaired by the
operator. Runbook §6 carries the same rule and points at the template rows.

Harness gaps closed in `TestNotificationPresenceStates`:

- Missing `-v notification_baseline_state` now fails closed at `02b`, `05b` and
  `07b` (syntax error, non-zero exit, no `baseline-state-` token printed).
- Invalid values `foo`, `PRESENT`, empty and `none` reach
  `..._presence_changed_during_attempt` at all three files, proving the pass
  `ELSE` branch is unreachable for any out-of-domain state.
- Partial presence is now asserted at `05b` and `07b` as well as `01` and `02b`,
  under both supplied states, with the relation count re-checked afterwards so
  nothing was provisioned or dropped.
- Both mid-attempt transitions are now also refused at `07b`
  (`f2_verify_nb0pv_notification_presence_changed_during_attempt`), so the
  failure is not deferred past step 6.
- The transition proof runs **P2's own text**, extracted verbatim from
  `01-preflight.sql` between its count query and `END AS
  p2_notification_relations;`, copied into the disposable container and run as a
  packet file, instead of a hand-copied reimplementation that could diverge.
  Extraction asserts its own content, so drift fails the test loudly.

Still unchanged by this pass: every frozen file, all application code, staging
schema, grants, roles and both D-047 confirmation gates. No staging contact, no
preflight retry, no receive.

### Second bounded review of this correction pass

One review of the correction itself returned no P0/P1 and four concrete findings,
all corrected before merge:

1. The new audit-template step-7 row was labelled `F12`, but `07b` already owns
   `F12` for its present-state per-relation detail block; the presence-state
   value is printed by NB0pv. Relabelled to `NB0pv notification presence state
   at step 7`, and a separate `F12 per-relation detail` row was added with
   `F12-not-applicable-relations-absent` for the absent state, so no row points
   an operator at a block that cannot print it.
2. No test asserted the three `*_notification_presence_state` tokens this pass
   made mandatory. `_chain` now asserts
   `n0p_`/`nb0p_`/`nb0pv_notification_presence_state == baseline-state-<state>`
   by exact equality in both states, so a drifted column name or string fails
   the harness instead of surfacing as a missing-token stop on staging.
3. The packet-P2 extraction proof ran in only one transition test.
   `test_present_to_absent_transition_fails_mid_attempt` now also runs P2's own
   text and asserts `all-12-absent`, so neither direction rests on the
   harness's reimplementation of the count query.
4. Runbook §6 listed the step-5 presence-state token for the `absent` state
   only, disagreeing with the state-agnostic audit-template row. `present` now
   lists `nb0p_notification_presence_state = baseline-state-present` too, and
   §7 spells out the 07b token set per state with F12 as present-only.

After the fixes: disposable PostgreSQL 16 harness `19 passed`, no skips;
`validate_inventory_truth_freeze.py` ok, `validate_agent_context.py` ok,
`git diff --check` clean, no secret-pattern line in the added diff.
