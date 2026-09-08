-- Step 5b: invariant R5b, the notification half of the out-of-scope write check.
--
-- Runbook step: CHECKPOINT-F2-CUTOVER-OPERATIONS-PLAN section 3, step 5.
-- Invariant: same document, section 5, R5 ("0 rows in notification tables").
-- Session: the private, time-bounded direct migrator session, which owns the
--          notification relations and therefore holds SELECT on all twelve.
--          Pass -v expected_role=<write_role>.
-- Writes: none, and enforced by an explicit READ ONLY transaction.
--
-- Required extra variables:
--
--   base_r5_notification   r5_notification_digest printed by
--                          02b-baseline-notification.sql
--   recon_timeout_ms       statement timeout for the gate, e.g. 15000
--
-- This file completes step 5. 05-r1-r7.sql covers R1 to R4, R5a, R5c, R6 and
-- R7; R5b is here. 06-write-complete.sql must not run until both files have
-- printed zero, because a partial reconciliation is a failure under D-045
-- decision 6, not a pass.
--
-- The zero condition is deliberately two-sided: the digest must equal the
-- step-2b baseline, AND the pinned tenant must hold zero notification rows. The
-- first half catches a write anywhere; the second catches the specific case
-- that matters for this cutover, which is a notification row appearing for the
-- shop being cut over.

\ir lib-guards.sql

SELECT CASE
         WHEN :'base_r5_notification' ~ '^[0-9a-f]{32}$'
         THEN 'notification-baseline-present'
         ELSE current_setting('stashtab_f2.f2_gate_r5b_missing_or_invalid_notification_baseline_digest')
       END AS g15_notification_baseline_digest;

SELECT CASE
         WHEN :recon_timeout_ms BETWEEN 1000 AND 600000
         THEN :recon_timeout_ms::text
         ELSE current_setting('stashtab_f2.f2_gate_timeout_parameters_out_of_range')
       END AS g16_timeout_parameter;

BEGIN;

SET TRANSACTION READ ONLY;
SET LOCAL statement_timeout = :recon_timeout_ms;

\echo '--- NB0 the session can read all twelve notification relations ---'
SELECT CASE
         WHEN (SELECT count(*)
                 FROM (VALUES ('notification_event'), ('notification_occurrence'),
                              ('notification_delivery'), ('notification_source'),
                              ('push_subscription'), ('notification_preference'),
                              ('shop_notification_policy'), ('notification_audit'),
                              ('notification_source_observation'),
                              ('notification_occurrence_transition'),
                              ('notification_delivery_attempt'),
                              ('notification_recovery_park')) AS required(rel)
                WHERE has_table_privilege(current_user, 'public.' || required.rel,
                                          'SELECT')) = 12
         THEN current_user || '-can-read-all-12'
         ELSE current_setting('stashtab_f2.f2_gate_r5b_nb0_session_lacks_select_on_a_notification_relation')
       END AS nb0_notification_select_privileges;

\echo '--- NB1 the gate is still being evaluated at the locking point ---'
SELECT CASE
         WHEN (SELECT status FROM inventory_truth_cutover
                WHERE shop_id = :'cutover_shop_id'
                  AND generation = :cutover_generation) = 'locking'
         THEN 'evaluating-at-locking'
         ELSE current_setting('stashtab_f2.f2_gate_r5b_nb1_row_is_not_locking')
       END AS nb1_evaluation_point;

\echo '--- R5b assertion: notification baseline unchanged ---'
WITH notification(rel, total_rows, cutover_shop_rows) AS (
  VALUES
    ('notification_audit',
     (SELECT count(*) FROM notification_audit),
     (SELECT count(*) FROM notification_audit WHERE shop_id = :'cutover_shop_id')),
    ('notification_delivery',
     (SELECT count(*) FROM notification_delivery),
     (SELECT count(*) FROM notification_delivery WHERE shop_id = :'cutover_shop_id')),
    ('notification_delivery_attempt',
     (SELECT count(*) FROM notification_delivery_attempt),
     (SELECT count(*) FROM notification_delivery_attempt WHERE shop_id = :'cutover_shop_id')),
    ('notification_event',
     (SELECT count(*) FROM notification_event),
     (SELECT count(*) FROM notification_event WHERE shop_id = :'cutover_shop_id')),
    ('notification_occurrence',
     (SELECT count(*) FROM notification_occurrence),
     (SELECT count(*) FROM notification_occurrence WHERE shop_id = :'cutover_shop_id')),
    ('notification_occurrence_transition',
     (SELECT count(*) FROM notification_occurrence_transition),
     (SELECT count(*) FROM notification_occurrence_transition WHERE shop_id = :'cutover_shop_id')),
    ('notification_preference',
     (SELECT count(*) FROM notification_preference),
     (SELECT count(*) FROM notification_preference WHERE shop_id = :'cutover_shop_id')),
    ('notification_recovery_park',
     (SELECT count(*) FROM notification_recovery_park),
     (SELECT count(*) FROM notification_recovery_park WHERE shop_id = :'cutover_shop_id')),
    ('notification_source',
     (SELECT count(*) FROM notification_source),
     (SELECT count(*) FROM notification_source WHERE shop_id = :'cutover_shop_id')),
    ('notification_source_observation',
     (SELECT count(*) FROM notification_source_observation),
     (SELECT count(*) FROM notification_source_observation WHERE shop_id = :'cutover_shop_id')),
    ('push_subscription',
     (SELECT count(*) FROM push_subscription),
     (SELECT count(*) FROM push_subscription WHERE shop_id = :'cutover_shop_id')),
    ('shop_notification_policy',
     (SELECT count(*) FROM shop_notification_policy),
     (SELECT count(*) FROM shop_notification_policy WHERE shop_id = :'cutover_shop_id'))
)
SELECT CASE
         WHEN md5(string_agg(rel || '=' || total_rows || '/' || cutover_shop_rows,
                             '|' ORDER BY rel)) = :'base_r5_notification'
         THEN 'R5b-unchanged'
         ELSE current_setting('stashtab_f2.f2_gate_r5b_notification_rows_changed')
       END AS r5b_result
FROM notification;

\echo '--- R5b detail: zero notification rows for the pinned tenant ---'
WITH notification(rel, cutover_shop_rows) AS (
  VALUES
    ('notification_audit',
     (SELECT count(*) FROM notification_audit WHERE shop_id = :'cutover_shop_id')),
    ('notification_delivery',
     (SELECT count(*) FROM notification_delivery WHERE shop_id = :'cutover_shop_id')),
    ('notification_delivery_attempt',
     (SELECT count(*) FROM notification_delivery_attempt WHERE shop_id = :'cutover_shop_id')),
    ('notification_event',
     (SELECT count(*) FROM notification_event WHERE shop_id = :'cutover_shop_id')),
    ('notification_occurrence',
     (SELECT count(*) FROM notification_occurrence WHERE shop_id = :'cutover_shop_id')),
    ('notification_occurrence_transition',
     (SELECT count(*) FROM notification_occurrence_transition WHERE shop_id = :'cutover_shop_id')),
    ('notification_preference',
     (SELECT count(*) FROM notification_preference WHERE shop_id = :'cutover_shop_id')),
    ('notification_recovery_park',
     (SELECT count(*) FROM notification_recovery_park WHERE shop_id = :'cutover_shop_id')),
    ('notification_source',
     (SELECT count(*) FROM notification_source WHERE shop_id = :'cutover_shop_id')),
    ('notification_source_observation',
     (SELECT count(*) FROM notification_source_observation WHERE shop_id = :'cutover_shop_id')),
    ('push_subscription',
     (SELECT count(*) FROM push_subscription WHERE shop_id = :'cutover_shop_id')),
    ('shop_notification_policy',
     (SELECT count(*) FROM shop_notification_policy WHERE shop_id = :'cutover_shop_id'))
)
SELECT CASE
         WHEN (SELECT COALESCE(SUM(cutover_shop_rows), 0) FROM notification) = 0
         THEN 'R5b-zero-rows-for-pinned-shop'
         ELSE current_setting('stashtab_f2.f2_gate_r5b_notification_rows_exist_for_the_pinned_shop')
       END AS r5b_pinned_shop_rows;

COMMIT;

\echo '--- step 5b complete: R5b evaluated at the locking point ---'
