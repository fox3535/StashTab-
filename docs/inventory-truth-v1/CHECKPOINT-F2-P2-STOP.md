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
