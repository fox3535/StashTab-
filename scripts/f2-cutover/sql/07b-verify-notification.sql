-- Step 7b: final verification of the notification relations.
--
-- Runbook step: CHECKPOINT-F2-CUTOVER-OPERATIONS-PLAN section 3, step 7.
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
--   verify_timeout_ms      statement timeout for verification, e.g. 15000
--
-- This file completes step 7. 07-final-verification.sql verifies the cutover
-- row, the open gate, R1, R6, the inventory and identity baseline and the
-- out-of-envelope inventory digest; the notification half of R5 is here, for
-- the same grant reason given in 02b and 05b. Step 8 must not be reached until
-- both files have printed their expected values.
--
-- The zero condition is two-sided, exactly as in 05b: the digest must still
-- equal the step-2b baseline, AND the pinned tenant must hold zero
-- notification rows. Steps 3 and 6 write only the cutover row, so any
-- difference here means something outside this packet touched the database and
-- the attempt stops under S6.

\ir lib-guards.sql

SELECT CASE
         WHEN :'base_r5_notification' ~ '^[0-9a-f]{32}$'
         THEN 'notification-baseline-present'
         ELSE current_setting('stashtab_f2.f2_verify_missing_or_invalid_notification_baseline_digest')
       END AS g17_notification_baseline_digest;

SELECT CASE
         WHEN :verify_timeout_ms BETWEEN 1000 AND 600000
         THEN :verify_timeout_ms::text
         ELSE current_setting('stashtab_f2.f2_verify_timeout_parameter_out_of_range')
       END AS g18_timeout_parameter;

BEGIN;

SET TRANSACTION READ ONLY;
SET LOCAL statement_timeout = :verify_timeout_ms;

\echo '--- NB0v the session can read all twelve notification relations ---'
-- Set taken verbatim from NOTIFICATION_TABLE_NAMES in
-- services/api/app/notifications_truth/models.py. Fails closed and names what
-- is missing rather than verifying over a partial set.
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
         ELSE current_setting('stashtab_f2.f2_verify_nb0v_session_lacks_select_on_a_notification_relation')
       END AS nb0v_notification_select_privileges;

\echo '--- NB1v the gate is being verified at the complete point ---'
-- R5b at step 7 is only meaningful against the same single row that step 6
-- transitioned. If this fails the packet is being run out of order.
SELECT CASE
         WHEN (SELECT status FROM inventory_truth_cutover
                WHERE shop_id = :'cutover_shop_id'
                  AND generation = :cutover_generation) = 'complete'
          AND (SELECT count(*) FROM inventory_truth_cutover) = 1
         THEN 'verifying-at-complete'
         ELSE current_setting('stashtab_f2.f2_verify_nb1v_row_is_not_the_single_complete_row')
       END AS nb1v_evaluation_point;

\echo '--- F10 R5b re-evaluated: notification baseline unchanged ---'
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
         THEN 'R5b-unchanged-at-step-7'
         ELSE current_setting('stashtab_f2.f2_verify_f10_notification_rows_changed_during_the_cutover')
       END AS f10_r5b_stability
FROM notification;

\echo '--- F11 zero notification rows for the pinned tenant ---'
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
         ELSE current_setting('stashtab_f2.f2_verify_f11_notification_rows_exist_for_the_pinned_shop')
       END AS f11_pinned_shop_rows;

\echo '--- F12 per-relation detail for the audit record ---'
SELECT rel, cutover_shop_rows
FROM (VALUES
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
) AS detail(rel, cutover_shop_rows)
ORDER BY rel;

COMMIT;

\echo '--- step 7 complete: cutover verified, R1/R4/R5/R6 zero, one tenant open, ---'
\echo '--- no receive performed. Next is step 8: STOP. Do not POST to the ---'
\echo '--- receive endpoint. Destroy the temporary local credential now. ---'
\echo '--- Retain the Neon stashtab_migrator role. ---'
