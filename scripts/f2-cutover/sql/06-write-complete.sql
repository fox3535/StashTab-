-- Step 6: transition the same generation-1 row from 'locking' to 'complete'.
--
-- Runbook step: CHECKPOINT-F2-CUTOVER-OPERATIONS-PLAN section 3, step 6.
-- Session: the private, time-bounded direct migrator session only.
--          Pass -v expected_role=<write_role>.
-- Writes: exactly one UPDATE of one existing row. No INSERT, no DELETE, no
--         second generation, no schema change, no privilege change.
--
-- Permission to run this file comes from 05-r1-r7.sql printing zero for every
-- invariant. The database cannot see that transcript, so the operator must
-- attest to it explicitly on the command line:
--
--   -v gate_attestation=r1-r7-zero-variance
--
-- Without that exact value the file refuses to run. The attestation is a
-- typed human acknowledgement, not a substitute for the gate: if any invariant
-- was non-zero, errored, or timed out, do not pass it. Stop under S3 or S4.
-- A timeout is never green, and "fix forward" is never available here.
--
-- Rerun behaviour: the UPDATE is guarded by status = 'locking'. A second run
-- matches zero rows and fails closed, so the transition can never be replayed
-- into a different state and can never silently re-stamp opened_at.

\ir lib-guards.sql

\echo '--- T0 attestation that the R1 to R7 gate returned zero variance ---'
SELECT CASE
         WHEN :'gate_attestation' = 'r1-r7-zero-variance'
         THEN 'operator-attested-zero-variance'
         ELSE current_setting('stashtab_f2.f2_complete_t0_gate_attestation_missing_or_wrong')
       END AS t0_gate_attestation;

\echo '--- T0b precondition: the row is currently locking, not already complete ---'
SELECT CASE
         WHEN (SELECT count(*) FROM inventory_truth_cutover
                WHERE shop_id = :'cutover_shop_id'
                  AND generation = :cutover_generation
                  AND status = 'locking'
                  AND frozen_at IS NOT NULL
                  AND opened_at IS NULL) = 1
          AND (SELECT count(*) FROM inventory_truth_cutover) = 1
         THEN 'locking-and-ready-to-transition'
         ELSE current_setting('stashtab_f2.f2_complete_t0b_row_is_not_in_the_locking_state')
       END AS t0b_current_state;

\echo '--- T0c precondition: this session may update the row ---'
SELECT CASE
         WHEN has_table_privilege(current_user, 'public.inventory_truth_cutover', 'UPDATE')
         THEN current_user || '-may-update'
         ELSE current_setting('stashtab_f2.f2_complete_t0c_session_cannot_update_cutover_row')
       END AS t0c_update_privilege;

BEGIN;

\echo '--- T1 transition exactly one row to complete with opened_at ---'
-- One statement, so the row-count discipline check and the UPDATE commit or
-- roll back together. frozen_at and created_at are deliberately not in the SET
-- list: the freeze instant is audit evidence and must survive the transition.
-- opened_at uses now(), the transaction timestamp.
WITH transitioned AS (
  UPDATE inventory_truth_cutover
     SET status = 'complete',
         opened_at = now()
   WHERE shop_id = :'cutover_shop_id'
     AND generation = :cutover_generation
     AND status = 'locking'
  RETURNING id
)
SELECT CASE
         WHEN (SELECT count(*) FROM transitioned) = 1
         THEN 'one-row-transitioned'
         ELSE current_setting('stashtab_f2.f2_complete_t1_transition_did_not_affect_exactly_one_row')
       END AS t1_rows_transitioned;

\echo '--- T2 the same row is now complete, with both timestamps set ---'
SELECT CASE
         WHEN (SELECT count(*) FROM inventory_truth_cutover
                WHERE shop_id = :'cutover_shop_id'
                  AND generation = :cutover_generation
                  AND status = 'complete'
                  AND frozen_at IS NOT NULL
                  AND opened_at IS NOT NULL
                  AND opened_at >= frozen_at) = 1
         THEN 'complete-with-opened_at-after-frozen_at'
         ELSE current_setting('stashtab_f2.f2_complete_t2_row_shape_wrong_after_transition')
       END AS t2_row_shape;

\echo '--- T3 no other tenant and no second generation were touched ---'
-- Stop under S1 if this fails.
SELECT CASE
         WHEN (SELECT count(*) FROM inventory_truth_cutover) = 1
          AND (SELECT count(*) FROM inventory_truth_cutover
                WHERE shop_id <> :'cutover_shop_id') = 0
          AND (SELECT count(*) FROM inventory_truth_cutover
                WHERE generation <> :cutover_generation) = 0
          AND (SELECT count(*) FROM inventory_truth_cutover
                WHERE status <> 'complete') = 0
         THEN 'pinned-shop-gen1-only'
         ELSE current_setting('stashtab_f2.f2_complete_t3_row_discipline_violated')
       END AS t3_row_discipline;

\echo '--- T4 the cutover write touched nothing else ---'
-- The transition must not create receive evidence. If any of these is non-zero
-- the attempt stops under S6: something outside the cutover row was written.
SELECT CASE
         WHEN (SELECT count(*) FROM purchase_record WHERE shop_id = :'cutover_shop_id') = 0
          AND (SELECT count(*) FROM acquisition_lot WHERE shop_id = :'cutover_shop_id') = 0
          AND (SELECT count(*) FROM inventory_event WHERE shop_id = :'cutover_shop_id') = 0
          AND (SELECT count(*) FROM inventory_item   WHERE shop_id = :'cutover_shop_id') = 0
         THEN 'no-envelope-rows-written'
         ELSE current_setting('stashtab_f2.f2_complete_t4_envelope_rows_appeared_during_the_transition')
       END AS t4_no_envelope_writes;

COMMIT;

\echo '--- T5 the row exactly as it now stands (audit evidence) ---'
SELECT id,
       shop_id,
       generation,
       status,
       frozen_at,
       opened_at,
       created_at
FROM inventory_truth_cutover
WHERE shop_id = :'cutover_shop_id'
ORDER BY generation, id;

\echo '--- step 6 complete: same row is now complete, gate open for this shop only ---'
\echo '--- next: 07-final-verification.sql, then step 8 STOP without receiving ---'
