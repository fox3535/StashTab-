# CHECKPOINT — F2 G5 owner exception and failed staging preflight evidence

Status: recorded. Cutover remains STOPPED. This document is mutable context,
not part of the frozen contract envelope.

## 1. Purpose

Record the outcome of the bounded read-only diagnostic of the G5 preflight
failure on Neon `stashtab_staging`, state the frozen-contract boundary that
makes the guard correction a mutable change rather than a contract amendment,
and preserve the failed staging attempt as historical evidence.

## 2. Observed staging catalog evidence (2026-09-17)

A single read-only catalog query was run as `stashtab_migrator` against
`stashtab_staging` through the private `f2c` session. No write, grant, revoke,
role change, retry, cutover, or receive occurred. Results:

- Members of `stashtab_migrator` (`pg_auth_members`, `roleid` = migrator):
  - `member = neondb_owner`, `grantor = cloud_admin`,
    `admin_option = t`, `inherit_option = f`, `set_option = f`.
  - `member = neondb_owner`, `grantor = neondb_owner`,
    `admin_option = f`, `inherit_option = t`, `set_option = t`.
- Runtime roles `stashtab_api`, `stashtab_worker`, `stashtab_readonly`:
  no direct membership in the migrator (`NO-MEMBERSHIP`).
- Transitive reachability from those runtime roles to the migrator: zero paths.
- psql exit code 0 for the diagnostic itself.

## 3. Interpretation

- This is not a runtime privilege violation. No application runtime role holds
  the migrator, directly or through any membership chain.
- Guard G5 as previously written matched ANY membership row regardless of
  options, so it fired on the administrative owner membership.
- The matched role is `neondb_owner`, the Neon administrative database-owner
  role. Its second membership row carries `set_option = t` and
  `inherit_option = t`, i.e. it CAN assume the migrator. This capability is
  acknowledged here as a platform-inherent administrative exception. It is not
  claimed that the owner cannot assume the migrator, and administrators are not
  broadly exempted: only this single named role is excluded, and only from the
  membership-denial predicate.

## 4. Frozen boundary finding

- The 1.3.0 freeze manifests (`freezes/FREEZE-1.3.0.json` and
  `freezes/FREEZE-1.3.0-git-canonical.json`) hash exactly: `CONTRACT.md`,
  `DESIGN.md`, `MIGRATION.md`, `TESTS.md`, `amendments/AMENDMENT-1.3.0.md`.
  `scripts/f2-cutover/sql/lib-guards.sql` and the runbook are not in the frozen
  set, so G5 is a mutable execution guard.
- The only frozen privilege clause bearing on assumption is
  `AMENDMENT-1.3.0` §1 decision 3: "Only the plan's exact least-privilege
  grants: column-scoped `UPDATE (stock, cost)`, the named INSERT/SELECT grants,
  and exact sequence USAGE. No DELETE, TRUNCATE, DDL, ownership, role
  administration, or migrator-role assumption." That clause constrains what the
  runtime envelope receives; it forbids runtime migrator-role assumption. No
  frozen clause requires that the migrator role have zero members.
- Therefore narrowing G5 to deny runtime/unapproved membership while recording
  the administrative owner exception is consistent with the frozen contract and
  is a mutable-guard correction, not a contract amendment. No frozen file is
  modified by this change.

## 5. Guard correction

`lib-guards.sql` G5 now computes the transitive membership closure of the write
role and fails closed (`f2_guard_prohibited_role_membership`, S5) when any
reaching role other than the write role and the single documented exception
`neondb_owner` exists. Direct and indirect runtime access by `stashtab_api`,
`stashtab_worker`, `stashtab_readonly`, and any unexpected member remain
denied. The pass label changed to `no-unapproved-role-can-assume-<write_role>`;
the failure parameter and the S5 stop mapping are unchanged.

## 6. Preserved historical evidence

The failed staging preflight (G5 raising
`stashtab_f2.f2_guard_prohibited_role_membership`, `lib-guards.sql`, psql exit
3, mapped to runbook stop condition S5) is retained as history. Nothing was
deleted or rewritten to make it look current. No retry was performed under this
correction; any future preflight or cutover step requires its own fresh,
explicit unlock. The cutover remains stopped.

## 7. Limitations

Membership-catalog evidence proves no runtime role holds the migrator through
`pg_auth_members`. It does not prove the absence of every escalation path:
superuser sessions, role ownership, platform administration outside the
membership catalog, and grants created after this observation are not covered.
The preflight guards re-verify membership at each run; this exception does not
weaken that re-verification for unapproved roles.

## 8. Tests

`scripts/f2-cutover/harness_f2_cutover.py::TestG5OwnerException` proves on
disposable PostgreSQL 16: the documented owner membership passes G5 despite
`set_option`/`inherit_option` being true; direct runtime membership fails
closed; transitive runtime membership (runtime role granted the owner role)
fails closed; and an unexpected member fails closed.
