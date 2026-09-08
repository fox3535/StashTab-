-- Step 3 validation path: confirm the generation-1 'locking' row without
-- writing anything.
--
-- Runbook step: CHECKPOINT-F2-CUTOVER-OPERATIONS-PLAN section 3, step 3
--               ("inserting or validating"), and step 4 database evidence.
-- Session: the private, time-bounded direct migrator session.
--          Pass -v expected_role=<write_role>. read_role is asserted by name
--          against the catalog and is never the session role.
-- Writes: none.
--
-- Unlike 03-write-locking.sql this file is idempotent and safe to rerun at any
-- point, including after a stop, after a break-glass, and at the start of a
-- resumed attempt. It is the only supported way to establish the current
-- cutover state; it never mutates a row and never widens an expectation.
--
-- It is also the fail-closed alternative to "insert if missing": there is no
-- UPSERT anywhere in this packet, because an UPSERT would silently rewrite an
-- existing row's status and timestamps and destroy the audit trail.

\ir lib-guards.sql

\echo '--- V1 exactly one cutover row exists in total ---'
SELECT CASE
         WHEN (SELECT count(*) FROM inventory_truth_cutover) = 1
         THEN 'one-row-globally'
         ELSE current_setting('stashtab_f2.f2_verify_locking_v1_expected_exactly_one_cutover_row')
       END AS v1_total_row_count;

\echo '--- V2 that row belongs to the pinned shop at generation 1 ---'
SELECT CASE
         WHEN (SELECT count(*) FROM inventory_truth_cutover
                WHERE shop_id = :'cutover_shop_id'
                  AND generation = :cutover_generation) = 1
          AND (SELECT count(*) FROM inventory_truth_cutover
                WHERE shop_id <> :'cutover_shop_id') = 0
          AND (SELECT count(*) FROM inventory_truth_cutover
                WHERE generation <> :cutover_generation) = 0
         THEN 'pinned-shop-gen1-only'
         ELSE current_setting('stashtab_f2.f2_verify_locking_v2_row_belongs_to_a_different_tenant_or_generation')
       END AS v2_tenant_and_generation_scope;

\echo '--- V3 the row is still locking, with frozen_at and no opened_at ---'
SELECT CASE
         WHEN (SELECT count(*) FROM inventory_truth_cutover
                WHERE shop_id = :'cutover_shop_id'
                  AND generation = :cutover_generation
                  AND status = 'locking'
                  AND frozen_at IS NOT NULL
                  AND opened_at IS NULL) = 1
         THEN 'locking-with-frozen_at-and-no-opened_at'
         ELSE current_setting('stashtab_f2.f2_verify_locking_v3_row_is_not_in_the_expected_locking_shape')
       END AS v3_locking_shape;

\echo '--- V4 the value the application gate would read is not complete ---'
-- cutover_status() in services/api/app/inventory_truth/core.py takes the first
-- row for the shop with no generation filter and no ORDER BY. With exactly one
-- row, proven by V1 and V2, that read is deterministic and returns 'locking',
-- so ensure_inventory_mutations_ready() must raise FeatureNotReadyError and the
-- receive endpoint must answer 503. If V4 fails while the HTTP check in step 4
-- still returned 503, the gate is not driven by this row and the attempt stops
-- under S2.
SELECT CASE
         WHEN (SELECT status FROM inventory_truth_cutover
                WHERE shop_id = :'cutover_shop_id'
                LIMIT 1) = 'locking'
         THEN 'gate-reads-locking'
         ELSE current_setting('stashtab_f2.f2_verify_locking_v4_gate_would_not_read_locking')
       END AS v4_gate_visible_status;

\echo '--- V5 the row exactly as it stands (audit evidence) ---'
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

\echo '--- V6 no receive evidence exists for the pinned shop ---'
-- D-045 decision 4 defers the receive to a second named unlock, so at this
-- point the envelope must still be empty for the pinned tenant. This is the
-- database half of the step 4 proof that no successful receive was performed;
-- the HTTP half is in the runbook.
SELECT CASE
         WHEN (SELECT count(*) FROM purchase_record WHERE shop_id = :'cutover_shop_id') = 0
          AND (SELECT count(*) FROM acquisition_lot WHERE shop_id = :'cutover_shop_id') = 0
          AND (SELECT count(*) FROM inventory_event WHERE shop_id = :'cutover_shop_id') = 0
         THEN 'no-receive-evidence'
         ELSE current_setting('stashtab_f2.f2_verify_locking_v6_receive_rows_exist_before_the_receive_unlock')
       END AS v6_no_receive_rows;

\echo '--- V7 the reserved future key is unused ---'
-- F2-CUT-GEN1-0001 is reserved by D-045 decision 5 for the later receive
-- unlock. It must not appear in the database at cutover time, and neither of
-- the two earlier probe markers may appear either.
SELECT CASE
         WHEN (SELECT count(*) FROM purchase_record
                WHERE client_idempotency_key IN
                      ('F2-CUT-GEN1-0001', 'F2-PROBE-DO-NOT-USE', 'F2-TEST-0001')) = 0
         THEN 'reserved-and-probe-keys-unused'
         ELSE current_setting('stashtab_f2.f2_verify_locking_v7_a_reserved_or_probe_key_is_already_present')
       END AS v7_reserved_key_unused;

\echo '--- validation complete: row is locking, gate is closed, no receive evidence ---'
