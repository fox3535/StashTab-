# REVIEW — F2 cutover execution packet (bounded, multi-discipline)

**Reviewer role:** one bounded independent review across architecture,
data-integrity, database-security, concurrency, operations, and liveness. This is
the single review pass the lean execution protocol allows, followed by at most
one correction pass.
**Subject:** the F2 generation-1 cutover execution packet —
`RUNBOOK-F2-CUTOVER-GEN1.md`, `AUDIT-TEMPLATE-F2-CUTOVER-GEN1.md`, the twelve
files in `scripts/f2-cutover/sql/`, and `scripts/f2-cutover/harness_f2_cutover.py`.
**Required by:** the packet directive (one bounded multi-discipline review) and
`CHECKPOINT-F2-CUTOVER-OPERATIONS-PLAN.md` §5.
**Pinned to:** branch `docs/f2-cutover-execution-packet` from protected `main` at
`aafae79`.
**Verdict:** `PASS` — the packet is operator-safe, fails closed, preserves
append-only evidence, and is proven twice on fresh disposable PostgreSQL 16
databases. One forward-looking finding (**P1-1**) is recorded for the later
receive unlock; it is not a stop for this planning-only packet. **No correction
pass was required.**

No frozen file was edited and no application code was changed to reach this
verdict. Reviews require contract clauses, exact code, or test evidence; every
claim below cites one.

## 1. Method and evidence base

Read in full: the runbook, the audit template, all twelve SQL files, the harness,
and the operations plan §1–§10. Read for the R1 and privilege citations: frozen
`DESIGN.md` §1 and `MIGRATION.md`; `AMENDMENT-1.3.0`; `models_truth.py`,
`core.py`, `models/inventory.py`, `inventory_live_schema/migrator.py`,
`notifications_truth/migrator.py`, and `routers/admin.py`. Executed: the
disposable harness twice (§4). Verified by scan: the command-set write surface
(§3.3). This review did **not** re-derive R1 clause-by-clause — that is
`REVIEW-F2-CUTOVER-R1-SQL.md` — and did not execute anything against a cloud
provider.

## 2. Discipline findings

### 2.1 Architecture — PASS

The packet is documentation + SQL + a throwaway harness; it introduces no runtime
component and changes no application code, which is the correct shape for a
planning-and-local-proof slice. It reuses the accepted mechanism rather than
inventing a parallel one: the gate is driven by `cutover_status(db, shop_id)`
compared to `"complete"` in `feature_readiness.ensure_inventory_mutations_ready`
(operations-plan §1), and the packet only writes the row that function reads.

One deliberate deviation is recorded and justified. Operations-plan §3 labels
steps 2, 5, and 7 "pooled `stashtab_api`, read-only"; the runbook §0 uses the
single migrator session instead. The justification is sound and code-backed:
D-045 decision 1 authorises exactly one credential, and
`notifications_truth.migrator._grant_runtime_privileges` (L462–L479) grants the
runtime role `SELECT` on only six of the twelve notification relations
(`notification_occurrence`, `notification_audit`,
`notification_source_observation`, `notification_occurrence_transition`,
`notification_delivery_attempt`, `notification_recovery_park`), while R5b's
digest needs all twelve (`05b-r5-notification.sql` NB0 asserts the session can
read all twelve and fails closed otherwise). Read-only-ness is preserved by
`BEGIN; SET TRANSACTION READ ONLY` on every read step, so the property is
database-enforced rather than role-dependent. This is the right trade: it narrows
the credential surface to one session and keeps R5b complete.

### 2.2 Data integrity — PASS

Append-only evidence is preserved end to end. The command set's only writes are
one INSERT (`03:50`) and two single-row UPDATEs (`06:61`, `08:133`); there is no
live DELETE, TRUNCATE, DROP, ALTER, CREATE, GRANT, REVOKE, or SET ROLE (§3.3).
Break-glass changes `status` only and asserts through a `\gset` pre-image that
`id`, `created_at`, `frozen_at`, and `opened_at` are unchanged and that
`opened_at` is never nulled (`08` BG3), then recomputes a catalog-wide row-count
digest to prove nothing anywhere gained or lost a row (`08` BG4). The harness
cross-checks that digest with an independent per-relation count
(`Pg16.catalog_counts`) rather than reusing the packet's own `query_to_xml` walk,
so a shared bug cannot hide a deletion; it asserts the relation set is unchanged
and only `inventory_truth_cutover` moves `0 → 1`.

The digest design is honest: `02-baseline.sql` prints both an all-inclusive
`baseline_digest` and a `baseline_excl_cutover`, and F6 compares against the
latter because steps 3 and 6 are allowed to move exactly that one relation. The
harness asserts `baseline_all != baseline_excl`, so the cutover write cannot be
invisible to F6. R1 fidelity to frozen 1.3.0 is covered by the dedicated R1
review; its finding **R1-1** (the `ck_overlay_zero_delta` gap for
`reverse`-of-overlay) is compensated at the gate by R1c arms (c)/(d) and is
unreachable at step 5 (zero event rows), so it does not weaken this packet.

### 2.3 Database security — PASS

Least privilege is asserted against the catalog, not assumed. `lib-guards.sql`
G5 proves no role can assume the migrator (`pg_auth_members`), G6 proves neither
the write nor read role is a superuser, and G9 proves `current_user` and
`session_user` are the expected role so a leftover `SET ROLE` or a pooled
connection cannot write under the wrong identity. R7a–R7e
(`05-r1-r7.sql` L513–L588) assert the AMENDMENT-1.3.0 §7 envelope exactly:
SELECT+INSERT on the four envelope tables with DELETE/TRUNCATE/REFERENCES/TRIGGER
denied, `UPDATE` only on the `stock` and `cost` **columns** of `inventory_item`
and no table-wide UPDATE, USAGE on exactly the four F2 sequences, PUBLIC holding
nothing (via `aclexplode`), the secondary runtime roles holding nothing, and the
cutover table writable only by the migrator while the runtime role keeps
SELECT-only.

Credential handling matches D-045 decision 1. The runbook §2 uses libpq
environment variables and forbids a connection URL in any command, log, Git
object, Railway variable, or app config; §2.2 keeps `stashtab_truth_migrator_role`
out of the app environment (its presence flips `/api/v1/ready` to `503`, detector
S10); §2.3 destroys the temporary local credential and clears shell history while
**retaining** the Neon migrator role. The harness mirrors this: it drives psql
through `PG*` env vars, builds no URL except a single container-bootstrap
`_admin_url` that is created at call time, never written to a file, and carries
only fixed literals for a container destroyed at teardown. Tenant scoping is
double-entered (G1b compares `cutover_shop_id` to `pinned_shop_id`), so a
mistyped tenant stops before any statement touches data.

### 2.4 Concurrency — PASS

The design assumes one migrator session and one API process, and the P0
preconditions plus S8 enforce it (autodeploy off, no worker/cron, exactly one
process, no restart in the window). Steps 3 and 6 run their write and its
discipline assertions inside one explicit transaction, so a failed assertion
rolls back and cannot leave a half-written row. The gate runs inside one
`READ ONLY` transaction with `SET LOCAL statement_timeout` and `lock_timeout`, so
a concurrent lock cannot stall it silently.

The known determinism hazard is handled: `cutover_status` takes the **first**
matching row unordered (operations-plan §1), so a second generation would make the
gate non-deterministic. G2 forces generation 1, W2/T3/BG5 force total rowcount 1
with zero rows for other shops or generations, and `uq_cutover_shop_generation`
is the schema backstop. The harness proves the hazard cannot be reached: a
hand-written duplicate INSERT is refused by the unique constraint, and a rerun of
step 3 is refused earlier by W0's globally-empty precondition. The harness also
proves a genuine server-side `lock timeout` (holding `ACCESS EXCLUSIVE` on
`inventory_event` from a second connection) yields a non-zero exit with no
`R1-zero` in stdout.

### 2.5 Operations — PASS

Steps 1–8 map one-to-one to operations-plan §3, in the D-045 decision 3/4 order
(reconcile while `locking`, then `complete`, then stop without a receive). The
audit template is append-only, one copy per attempt, and records actor, wall
clocks, shop, generation, digests, every HTTP probe, all eleven stop conditions
(invoked or not), the break-glass block, the credential lifecycle, and the final
decision — including the explicit non-claims that `features.inventory_cutover`
stays `false`, the global readiness flag is not claimed true, no successful
receive was performed, and `F2-CUT-GEN1-0001` stays unused. Rerun behavior is
explicit and differentiated: step 1 has no resume path (P7), step 4 is idempotent,
step 3 refuses a rerun (W0), step 6 is intentionally not idempotent (T0b, so
`opened_at` is never re-stamped), and break-glass is not repeatable (BG0c). Each
is asserted by the harness. The step-6 attestation (`gate_attestation=
r1-r7-zero-variance`) is a typed human acknowledgement that the gate printed
zero, which the database cannot see; a wrong or missing value stops before the
transaction opens (T0).

### 2.6 Liveness — PASS

"Timeout is not green" is enforced structurally, not by instruction alone:
bounded `statement_timeout`/`lock_timeout` turn a hang into an error, and
`ON_ERROR_STOP` turns an error into a non-zero exit, so an unfinished
reconciliation can never report success (S3/S4). The gate parameters themselves
are range-checked (`g11`, `f2_gate_timeout_parameters_out_of_range`), so an
absurd timeout is refused before the gate opens. The exit path is finite: a
non-zero exit is never retried inside the same unlock, break-glass is never a way
past a failed reconciliation (S3 leaves the row `locking`), and step 8
terminates. There is no review/gate loop that can spin: the packet's own review
path is one bounded pass plus at most one correction, and the harness runs to a
deterministic pass/fail.

## 3. Evidence

### 3.1 Harness — two independent runs, each twice on fresh databases

`python -m pytest scripts/f2-cutover/harness_f2_cutover.py`:

| Run | Finished (UTC) | Result |
| --- | --- | --- |
| 1 | `2026-09-08T02:54:53Z` | `8 passed, 1 warning` in 56.83s |
| 2 | `2026-09-08T02:56:55Z` | `8 passed, 1 warning` in 56.20s |

8 tests = 4 methods × `{first-fresh-db, second-fresh-db}`; the function-scoped
`pg` fixture builds and destroys a fresh `postgres:16` container per test, so
each invocation proves the packet twice on fresh databases. The one warning is a
benign `StarletteDeprecationWarning` about `httpx`/`starlette.testclient`. No
container leaked (`docker ps -a --filter name=stashtab-f2cut-` empty after both).
Databases are provisioned by the reviewed migrators, not a mock. Results recorded
in `CHECKPOINT-F2-CUTOVER-EXECUTION-PACKET.md` §4.

### 3.2 HTTP checks over the real routers

Unauthenticated receive `401`; authenticated receive while `locking` `503` with
`error == FEATURE_NOT_READY`; control shop `503` after Smoke Shop B reaches
`complete`; `ready.features.inventory_cutover == false`; reserved key `422` and
missing key `422` (both before the gate). `ProbeLog` fails the harness on any
`2xx`, and envelope counts stay zero, so no successful receive is performed.

### 3.3 Command-set write surface (scan)

A regex scan of `scripts/f2-cutover/sql/*.sql` for live write/DDL/privilege
statements returns exactly `03:50 INSERT`, `06:61 UPDATE`, `08:133 UPDATE`, and
nothing else. Every other match for DELETE/TRUNCATE/DROP/ALTER/CREATE/GRANT/
REVOKE/SET ROLE/INSERT/UPDATE is a comment or a read-only
`has_table_privilege`/`has_column_privilege` check.

### 3.4 Citation verification

Frozen `DESIGN.md` L17–22/L29–31/L45–54/L56–58 and `MIGRATION.md`
L51–53/L120–122/L143–148; `models_truth.py` L82–86 (`ck_overlay_zero_delta`) and
L109–123 (`InventoryTruthCutover`, `uq_cutover_shop_generation`);
`core.py` L326–329 (`func_event_delta_sum`) and L419–445 (`reconcile_shop`);
`models/inventory.py` L11 and `inventory_live_schema/migrator.py` L103
(`uq_inventory_shop_sku`); `notifications_truth/migrator.py` L462–479 (six-of-twelve
SELECT); `routers/admin.py` L1203–1229 (`ControlledReceiveIn`,
`_validated_client_key`). All were read and match the packet's claims.

## 4. Findings register

| ID | Severity | Discipline | Finding | Disposition |
| --- | --- | --- | --- | --- |
| P1-1 | P1 for the **later receive unlock**; not a stop here | Operations / contract | D-045 decision 5 reserves `F2-CUT-GEN1-0001` as the first receive's idempotency key, but `_validated_client_key` (`admin.py` L1220–L1229) requires the `Idempotency-Key` header to be a 36-char UUIDv4 and that validated string becomes `purchase_record.client_idempotency_key`. The reserved 16-char, non-UUID key is therefore rejected `422` and cannot be used as written. | Record for an owner decision under the receive unlock (reserve a UUIDv4, or decide how the reserved string is used). This packet never receives and correctly leaves the key unused; the harness proves the `422`. No change to this packet. |
| R1-1 | P2 (recorded) | Data integrity / contract | `ck_overlay_zero_delta` does not enforce the frozen `reverse`-of-overlay `quantity_delta = 0` clause. | Already recorded in `REVIEW-F2-CUTOVER-R1-SQL.md`; compensated at the gate by R1c arms (c)/(d); unreachable at step 5. Schema reconciliation is a separate named slice. No change to this packet. |
| O-1 | Observation | Architecture | Runbook §0 says the notification migrator "issues REVOKEs for the other six" relations; precisely, `REVOKE TRUNCATE, DELETE` runs over all twelve (L469–470) and the other six simply receive no `SELECT` grant. | The operative claim — runtime role has SELECT on only six of twelve, so R5b needs the owning migrator session — is correct and verified at L462–L479. No correction required. |

No P0 finding. No finding requires editing a frozen file or application code.

## 5. Correction-pass decision

**None required.** The packet is internally consistent (runbook tokens ↔ SQL
markers ↔ harness assertions ↔ audit template all agree), the harness passes
twice on fresh databases, the write surface is minimal and fail-closed, and every
finding is a recording for a future owner decision rather than a defect in this
packet's behavior. The one allowed correction pass is therefore not used; using it
to churn a correct, proven document would add risk without adding safety.

## 6. What this review did not do

It did not execute anything against staging, Neon, Railway, or Clerk. It did not
edit frozen text, application code, schema, privileges, or flags. It did not
perform a receive, create a credential, or run a migrator against any database
other than a container destroyed at teardown. It did not approve execution: the
packet remains `PREPARED — PROVEN LOCALLY`, and a separate named cutover unlock
is still required.
