-- Step 3: write the generation-1 'locking' row for the pinned shop.
--
-- Runbook step: CHECKPOINT-F2-CUTOVER-OPERATIONS-PLAN section 3, step 3.
-- Session: the private, time-bounded direct migrator session only.
--          Pass -v expected_role=<write_role>.
-- Writes: exactly one INSERT into inventory_truth_cutover. Nothing else.
--
-- This step does NOT write 'complete'. Under D-045 decision 3 the row stays
-- 'locking' while R1 to R7 are run and recorded, and only 06-write-complete.sql
-- transitions it, in a separate transaction, and only at zero variance.
--
-- Rerun behaviour is deliberately strict and has two independent layers. The
-- first is W0 below, which requires the cutover relation to be globally empty
-- and so refuses a second run of this file before it can write anything. The
-- second is the accepted unique constraint uq_cutover_shop_generation, which
-- refuses a duplicate (shop_id, generation) even when the INSERT is issued by
-- hand outside this command set. Together they answer "what happens if the
-- operator runs this twice": the attempt stops, and neither a second generation
-- nor an overwrite of the first is possible. Recovery is
-- 04-verify-locking.sql, never an edited assertion and never a DELETE.
--
-- Atomicity: the INSERT and its discipline assertions run inside one explicit
-- transaction. If any assertion fails, psql stops under ON_ERROR_STOP and the
-- open transaction is rolled back when the session ends, so a failed step 3
-- cannot leave a half-written or unverified cutover row behind.

\ir lib-guards.sql

\echo '--- W0 precondition: no cutover row exists anywhere yet ---'
SELECT CASE
         WHEN (SELECT count(*) FROM inventory_truth_cutover) = 0
         THEN 'zero-rows-before-write'
         ELSE current_setting('stashtab_f2.f2_write_locking_w0_a_cutover_row_already_exists')
       END AS w0_cutover_table_empty;

\echo '--- W0b precondition: this session may insert ---'
SELECT CASE
         WHEN has_table_privilege(current_user, 'public.inventory_truth_cutover', 'INSERT')
         THEN current_user || '-may-insert'
         ELSE current_setting('stashtab_f2.f2_write_locking_w0b_session_cannot_insert_cutover_row')
       END AS w0b_insert_privilege;

BEGIN;

\echo '--- W1 insert generation 1, status locking, frozen_at set ---'
-- created_at has no server default in the accepted schema, so it is supplied
-- explicitly. opened_at is supplied as NULL on purpose: it is written only by
-- 06-write-complete.sql. frozen_at uses now(), the transaction timestamp, so
-- repeated statements in this transaction agree on one freeze instant.
INSERT INTO inventory_truth_cutover
    (shop_id, generation, status, frozen_at, opened_at, created_at)
VALUES
    (:'cutover_shop_id', :cutover_generation, 'locking', now(), NULL, now());

\echo '--- W2 row discipline: exactly one row, pinned shop only ---'
-- Stop under S1 if this fails. The transaction rolls back, so a failure here
-- leaves the database exactly as it was before step 3.
SELECT CASE
         WHEN (SELECT count(*) FROM inventory_truth_cutover) = 1
          AND (SELECT count(*) FROM inventory_truth_cutover
                WHERE shop_id = :'cutover_shop_id'
                  AND generation = :cutover_generation) = 1
          AND (SELECT count(*) FROM inventory_truth_cutover
                WHERE shop_id <> :'cutover_shop_id') = 0
          AND (SELECT count(*) FROM inventory_truth_cutover
                WHERE generation <> :cutover_generation) = 0
         THEN 'exactly-one-row-pinned-shop-gen1'
         ELSE current_setting('stashtab_f2.f2_write_locking_w2_row_discipline_violated')
       END AS w2_row_discipline;

\echo '--- W3 row shape: locking with frozen_at and no opened_at ---'
SELECT CASE
         WHEN (SELECT count(*) FROM inventory_truth_cutover
                WHERE shop_id = :'cutover_shop_id'
                  AND generation = :cutover_generation
                  AND status = 'locking'
                  AND frozen_at IS NOT NULL
                  AND opened_at IS NULL) = 1
         THEN 'locking-with-frozen_at'
         ELSE current_setting('stashtab_f2.f2_write_locking_w3_row_shape_wrong')
       END AS w3_row_shape;

COMMIT;

\echo '--- W4 the row exactly as written (audit evidence) ---'
SELECT id,
       shop_id,
       generation,
       status,
       frozen_at,
       opened_at,
       created_at
FROM inventory_truth_cutover
WHERE shop_id = :'cutover_shop_id'
  AND generation = :cutover_generation
ORDER BY id;

\echo '--- step 3 complete: generation-1 locking row written, gate still closed ---'
\echo '--- next: step 4 HTTP checks, then 05-r1-r7.sql while status is locking ---'
