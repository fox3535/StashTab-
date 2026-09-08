-- Step 8 / section 6 break-glass: least-destructive return of the pinned
-- generation-1 row to 'locking'.
--
-- Runbook step: CHECKPOINT-F2-CUTOVER-OPERATIONS-PLAN section 6 step 2, and
--               section 7 rollback order item 1.
-- Session: the private, time-bounded direct migrator session only.
--          Pass -v expected_role=<write_role>.
-- Writes: exactly one UPDATE of one existing row, changing status only.
--
-- This is the least destructive action available and it is deliberately narrow:
--
--   * No DELETE and no TRUNCATE anywhere in this file. The row survives.
--   * status is the ONLY column changed. id, shop_id, generation, created_at,
--     frozen_at and opened_at are all preserved. opened_at in particular is
--     evidence of how long the gate was open and must not be nulled: nulling it
--     would erase the exposure window that the incident record needs.
--   * No other tenant's row can be reached; the WHERE clause pins shop_id and
--     generation, and BG2 plus BG5 prove exactly one row moved.
--   * No schema change, no privilege change, no role change, no seed.
--   * No redeploy and no restart. The gate fail-closes on the status value
--     alone, because ensure_inventory_mutations_ready() compares it to
--     'complete' and raises FeatureNotReadyError otherwise.
--
-- Break-glass is permitted only to stop active harm. It is never a way past a
-- failed reconciliation: if R1 to R7 were non-zero, stop under S3 and leave the
-- row exactly as it is. Do not run this file to make a red gate disappear.
--
-- Required extra variables:
--
--   break_glass_attestation   must be owner-authorized-break-glass
--   break_glass_timeout_ms    statement timeout, e.g. 30000
--
-- Rerun behaviour: the UPDATE matches only status = 'complete'. If the row is
-- already 'locking', BG0c stops the file with an explicit message rather than
-- reporting a withdrawal that did not happen.

\ir lib-guards.sql

SELECT CASE
         WHEN :'break_glass_attestation' = 'owner-authorized-break-glass'
         THEN 'owner-authorized'
         ELSE current_setting('stashtab_f2.f2_break_glass_attestation_missing_or_wrong')
       END AS bg0a_attestation;

SELECT CASE
         WHEN :break_glass_timeout_ms BETWEEN 1000 AND 600000
         THEN :break_glass_timeout_ms::text
         ELSE current_setting('stashtab_f2.f2_break_glass_timeout_parameter_out_of_range')
       END AS bg0b_timeout_parameter;

\echo '--- BG0 current state of the pinned row ---'
SELECT id, shop_id, generation, status, frozen_at, opened_at, created_at
FROM inventory_truth_cutover
WHERE shop_id = :'cutover_shop_id'
ORDER BY generation, id;

\echo '--- BG0c precondition: there is a complete row to withdraw ---'
-- If this stops, nothing was withdrawn. Record the real state from BG0 in the
-- audit template and continue with section 6 steps 3 to 6; do not retry this
-- file and do not delete the row.
SELECT CASE
         WHEN (SELECT count(*) FROM inventory_truth_cutover
                WHERE shop_id = :'cutover_shop_id'
                  AND generation = :cutover_generation
                  AND status = 'complete') = 1
         THEN 'complete-row-present'
         ELSE current_setting('stashtab_f2.f2_break_glass_bg0c_no_complete_row_to_withdraw')
       END AS bg0c_withdrawable;

BEGIN;

SET LOCAL statement_timeout = :break_glass_timeout_ms;

\echo '--- BG1 pre-image: row identity plus a digest of every public relation ---'
-- The digest is computed over row COUNTS for every ordinary relation in the
-- public schema, derived from the catalog rather than from a hand-written list,
-- so it cannot drift as the schema evolves and it proves that break-glass
-- deleted nothing anywhere in the database, not merely nothing in the envelope.
-- Captured inside the same transaction as the UPDATE, so nothing else can move
-- between the two measurements.
SELECT id AS bg_row_id,
       created_at AS bg_created_at,
       frozen_at AS bg_frozen_at,
       opened_at AS bg_opened_at
FROM inventory_truth_cutover
WHERE shop_id = :'cutover_shop_id'
  AND generation = :cutover_generation
\gset

SELECT md5(string_agg(counted.rel || '=' || counted.cnt, '|' ORDER BY counted.rel))
         AS bg_pre_digest,
       count(*) AS bg_pre_relations,
       count(*) FILTER (WHERE counted.cnt > 0) AS bg_pre_nonempty_relations,
       max(counted.cnt) FILTER (WHERE counted.rel = 'inventory_truth_cutover')
         AS bg_pre_cutover_rows
FROM (
  SELECT c.relname AS rel,
         (xpath('/table/row/c/text()',
                query_to_xml(
                  format('SELECT count(*) AS c FROM %I.%I', n.nspname, c.relname),
                  true, false, '')))[1]::text::bigint AS cnt
  FROM pg_class c
  JOIN pg_namespace n ON n.oid = c.relnamespace
  WHERE n.nspname = 'public'
    AND c.relkind = 'r'
) counted
\gset

\echo '--- BG1b self-test: the counting mechanism returned real numbers ---'
-- Positive control, and the reason the xpath root is /table and not /row.
-- query_to_xml is called with tableforest = false, so it emits a <table> root
-- wrapping the <row>. An xpath of '/row/c/text()' against that document matches
-- nothing, every count comes back NULL, string_agg skips NULLs, and BG4 would
-- then compare md5('') with md5('') and report success while proving nothing.
-- BG0c has already established that exactly one complete row exists for the
-- pinned tenant, so the walk must have seen exactly one row there.
SELECT CASE
         WHEN :bg_pre_relations > 0
          AND :bg_pre_cutover_rows = 1
          AND :bg_pre_nonempty_relations > 0
          AND :'bg_pre_digest' ~ '^[0-9a-f]{32}$'
          AND :'bg_pre_digest' <> 'd41d8cd98f00b204e9800998ecf8427e'
         THEN :bg_pre_relations || '-relations-counted'
         ELSE current_setting('stashtab_f2.f2_break_glass_bg1b_relation_counting_returned_nothing')
       END AS bg1b_counting_self_test;

SELECT :'bg_pre_digest' AS bg_pre_digest_captured,
       :bg_row_id AS bg_row_id_captured,
       :bg_pre_relations AS bg_pre_relations_captured;

\echo '--- BG2 withdraw: status back to locking, one row only ---'
WITH withdrawn AS (
  UPDATE inventory_truth_cutover
     SET status = 'locking'
   WHERE shop_id = :'cutover_shop_id'
     AND generation = :cutover_generation
     AND status = 'complete'
  RETURNING id
)
SELECT CASE
         WHEN (SELECT count(*) FROM withdrawn) = 1
          AND (SELECT count(*) FROM withdrawn WHERE id = :bg_row_id) = 1
         THEN 'one-row-withdrawn'
         ELSE current_setting('stashtab_f2.f2_break_glass_bg2_withdrawal_did_not_affect_exactly_the_pinned_row')
       END AS bg2_rows_withdrawn;

\echo '--- BG3 audit evidence preserved: identity and timestamps unchanged ---'
SELECT CASE
         WHEN (SELECT count(*) FROM inventory_truth_cutover
                WHERE id = :bg_row_id
                  AND shop_id = :'cutover_shop_id'
                  AND generation = :cutover_generation
                  AND status = 'locking'
                  AND created_at = :'bg_created_at'::timestamptz
                  AND frozen_at = :'bg_frozen_at'::timestamptz
                  AND opened_at = :'bg_opened_at'::timestamptz) = 1
         THEN 'evidence-preserved-status-only-changed'
         ELSE current_setting('stashtab_f2.f2_break_glass_bg3_audit_evidence_was_modified')
       END AS bg3_evidence_preserved;

\echo '--- BG4 nothing was deleted or inserted anywhere in the public schema ---'
WITH counted AS (
  SELECT c.relname AS rel,
         (xpath('/table/row/c/text()',
                query_to_xml(
                  format('SELECT count(*) AS c FROM %I.%I', n.nspname, c.relname),
                  true, false, '')))[1]::text::bigint AS cnt
  FROM pg_class c
  JOIN pg_namespace n ON n.oid = c.relnamespace
  WHERE n.nspname = 'public'
    AND c.relkind = 'r'
)
SELECT CASE
         WHEN md5(string_agg(counted.rel || '=' || counted.cnt, '|' ORDER BY counted.rel))
              = :'bg_pre_digest'
          AND (SELECT count(*) FROM counted) = :bg_pre_relations
          AND (SELECT count(*) FROM counted WHERE cnt IS NULL) = 0
         THEN 'all-row-counts-unchanged'
         ELSE current_setting('stashtab_f2.f2_break_glass_bg4_row_counts_changed_during_withdrawal')
       END AS bg4_no_rows_deleted
FROM counted;

\echo '--- BG5 still exactly one row, still only the pinned tenant ---'
SELECT CASE
         WHEN (SELECT count(*) FROM inventory_truth_cutover) = 1
          AND (SELECT count(*) FROM inventory_truth_cutover
                WHERE shop_id <> :'cutover_shop_id') = 0
          AND (SELECT count(*) FROM inventory_truth_cutover
                WHERE generation <> :cutover_generation) = 0
         THEN 'pinned-shop-gen1-only'
         ELSE current_setting('stashtab_f2.f2_break_glass_bg5_row_discipline_violated')
       END AS bg5_row_discipline;

\echo '--- BG6 the gate reads locking again, so receive fail-closes ---'
SELECT CASE
         WHEN (SELECT status FROM inventory_truth_cutover
                WHERE shop_id = :'cutover_shop_id'
                LIMIT 1) = 'locking'
         THEN 'gate-reads-locking'
         ELSE current_setting('stashtab_f2.f2_break_glass_bg6_gate_does_not_read_locking')
       END AS bg6_gate_fail_closed;

COMMIT;

\echo '--- BG7 post-withdrawal state (audit evidence) ---'
SELECT id, shop_id, generation, status, frozen_at, opened_at, created_at
FROM inventory_truth_cutover
WHERE shop_id = :'cutover_shop_id'
ORDER BY generation, id;

\echo '--- break-glass complete: gate fail-closed, no row deleted, evidence intact ---'
\echo '--- next: section 6 steps 3 to 6. Prove receive returns 503, re-snapshot, ---'
\echo '--- open an incident record, and do not retry inside the same unlock. ---'
