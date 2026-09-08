-- Shared fail-closed guards for the F2 generation-1 cutover command set.
--
-- Included with \ir from every step file. This file performs no DML and no
-- DDL. It only proves that the psql invocation supplied the required
-- parameters and that the target roles and database are the expected ones.
--
-- Packet: docs/inventory-truth-v1/RUNBOOK-F2-CUTOVER-GEN1.md
-- Authority: D-045 decisions 1, 2 and 3; CHECKPOINT-F2-CUTOVER-OPERATIONS-PLAN
--            sections 3, 5 and 7.
--
-- Conventions used by the whole command set
--
--   1. Every step file sets ON_ERROR_STOP itself, so the command set fails
--      closed even when the operator forgets the -v flag.
--   2. Assertions are plain SELECT CASE expressions whose failure branch reads
--      a deliberately unset, namespaced configuration parameter:
--
--          ELSE current_setting('stashtab_f2.<invariant_name>')
--
--      When the WHEN branch holds, the ELSE branch is never evaluated and the
--      statement returns its evidence. When it does not hold, PostgreSQL raises
--      `unrecognized configuration parameter "stashtab_f2.<invariant_name>"`,
--      which names the exact invariant that failed, cannot be swallowed by any
--      error handler, and gives psql a non-zero exit under ON_ERROR_STOP.
--
--      The three obvious alternatives were each tested against postgres:16 and
--      each is unsound, which is why this form is used everywhere:
--
--        a. A call to a function that does not exist, e.g. `ELSE f2_fail()`.
--           PostgreSQL resolves function names during parse analysis, before
--           any evaluation, so the statement fails even when WHEN is true. This
--           makes every assertion fail unconditionally.
--        b. A cast of a constant, e.g. `ELSE 'f2_fail'::int`. Constants are
--           folded during parse analysis for the same reason, so this also
--           fails unconditionally.
--        c. A DO block with RAISE EXCEPTION. psql does not interpolate
--           variables inside a dollar-quoted body: `:'cutover_shop_id'` reaches
--           the server verbatim and is a syntax error. Every guard in this
--           packet depends on interpolated variables, so DO blocks cannot be
--           used. That was verified directly, not assumed.
--
--      current_setting() is STABLE rather than IMMUTABLE, so it is never
--      constant-folded, and it returns text, so it type-matches the text
--      evidence in every WHEN branch. It needs no DDL and creates nothing: the
--      packet runs as the migrator role but must still leave the catalog free
--      of helper objects.
--
--      The `stashtab_f2.` prefix is a custom parameter class that nothing in
--      this repository ever sets, so the failure branch cannot be silenced by
--      an unrelated configuration value.
--   3. An unset psql variable is emitted as literal text, which is itself a
--      syntax error under ON_ERROR_STOP. A missing parameter fails closed
--      rather than defaulting to something convenient.
--   4. Nothing in this command set ever interpolates a connection string, a
--      password, or a token. Connection parameters are supplied through libpq
--      environment variables by the caller and never appear in these files.
--
-- Required variables (all of them, for every step file):
--
--   cutover_shop_id      pinned gen-1 shop, D-045 decision 2
--   pinned_shop_id       the same value, supplied independently as a
--                        double-entry control; the two must agree
--   cutover_generation   must be 1; the command set refuses any other value
--   write_role           the migrator role that owns the cutover write path.
--                        This is the role the whole packet runs as, under
--                        D-045 decision 1: one direct session, one credential.
--   read_role            the pooled runtime role whose privileges are asserted
--                        BY NAME against the catalog in P5 and R7. It is never
--                        the session role; the packet never opens a second
--                        credential and never runs SET ROLE.
--   expected_database    the database the session must be connected to
--   expected_role        the role this session must be running as; the runbook
--                        passes write_role here for every step file
--   expected_shops       identity baseline, 2 under D-045 decision 2
--   expected_shop_members identity baseline, 2 under D-045 decision 2

\set ON_ERROR_STOP on

-- G1. The pinned shop id must be a lowercase UUID literal. This is the guard
--     that stops a mistyped or substituted tenant from being cut over.
SELECT CASE
         WHEN :'cutover_shop_id' ~
              '^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$'
         THEN :'cutover_shop_id'
         ELSE current_setting('stashtab_f2.f2_guard_missing_or_invalid_cutover_shop_id')
       END AS g1_cutover_shop_id;

-- G1b. Double-entry control on the tenant. cutover_shop_id is what the command
--      set operates on; pinned_shop_id is what the operator believes D-045
--      decision 2 named. They are supplied as two separate -v arguments so that
--      a transcription error in either one fails closed instead of cutting over
--      the wrong tenant. Both must be the Smoke Shop B literal.
SELECT CASE
         WHEN :'cutover_shop_id' = :'pinned_shop_id'
         THEN 'shop-id-double-entry-agrees'
         ELSE current_setting('stashtab_f2.f2_guard_cutover_shop_id_does_not_match_the_pinned_shop_id')
       END AS g1b_shop_id_double_entry;

-- G2. Generation 1 only. A second generation would make cutover_status()
--     non-deterministic, because it takes the first matching row unordered.
SELECT CASE
         WHEN :cutover_generation = 1 THEN :cutover_generation::text
         ELSE current_setting('stashtab_f2.f2_guard_generation_must_be_exactly_one')
       END AS g2_cutover_generation;

-- G3. The session must be attached to the database the operator named. This is
--     the guard that stops the command set running against the wrong database.
SELECT CASE
         WHEN current_database() = :'expected_database' THEN current_database()
         ELSE current_setting('stashtab_f2.f2_guard_unexpected_database')
       END AS g3_database;

-- G4. Role names must be valid SQL identifiers before they are compared
--     against the catalog. Both roles must already exist; this command set
--     never creates, alters, or drops a role.
SELECT CASE
         WHEN :'write_role' ~ '^[a-z][a-z0-9_]*$'
          AND :'read_role' ~ '^[a-z][a-z0-9_]*$'
          AND (SELECT count(*) FROM pg_roles
                WHERE rolname IN (:'write_role', :'read_role')) = 2
         THEN :'write_role' || ',' || :'read_role'
         ELSE current_setting('stashtab_f2.f2_guard_required_roles_missing')
       END AS g4_roles_present;

-- G5. No runtime role may be able to assume the migrator role. If this fails,
--     stop under S5: the least-privilege envelope is already broken and the
--     cutover write is not distinguishable from application traffic.
SELECT CASE
         WHEN NOT EXISTS (
                SELECT 1
                  FROM pg_auth_members m
                  JOIN pg_roles r ON r.oid = m.roleid
                  JOIN pg_roles u ON u.oid = m.member
                 WHERE r.rolname = :'write_role'
                   AND u.rolname <> :'write_role'
              )
         THEN 'no-role-can-assume-' || :'write_role'
         ELSE current_setting('stashtab_f2.f2_guard_prohibited_role_membership')
       END AS g5_no_migrator_assumption;

-- G6. The write role must never be a superuser, and the read role must never
--     be a superuser. A superuser session would defeat every privilege
--     assertion in R7 and every fail-closed property proved by the harness.
SELECT CASE
         WHEN (SELECT count(*) FROM pg_roles
                WHERE rolname IN (:'write_role', :'read_role')
                  AND rolsuper) = 0
         THEN 'no-superuser'
         ELSE current_setting('stashtab_f2.f2_guard_superuser_session_not_permitted')
       END AS g6_no_superuser;

-- G7. Identity baseline. D-045 decision 2 makes shops = 2 and shop_members = 2
--     both a precondition and a postcondition of the cutover.
SELECT CASE
         WHEN (SELECT count(*) FROM shops) = :expected_shops
          AND (SELECT count(*) FROM shop_members) = :expected_shop_members
         THEN (SELECT count(*) FROM shops) || '/' ||
              (SELECT count(*) FROM shop_members)
         ELSE current_setting('stashtab_f2.f2_guard_identity_baseline_mismatch')
       END AS g7_identity_baseline;

-- G8. The pinned shop must exist and must have exactly one membership. The
--     cutover row is shop-scoped, so a missing or ambiguous tenant here is a
--     stop under S11, not something to create on the fly: creating a shop or a
--     membership is an identity write and needs its own authorization.
SELECT CASE
         WHEN (SELECT count(*) FROM shops WHERE id = :'cutover_shop_id') = 1
          AND (SELECT count(*) FROM shop_members
                WHERE shop_id = :'cutover_shop_id') = 1
         THEN 'shop-present-with-one-membership'
         ELSE current_setting('stashtab_f2.f2_guard_pinned_shop_absent_or_ambiguous')
       END AS g8_pinned_shop_present;

-- G9. The session must actually be the role the operator named, for both
--     current_user and session_user. A SET ROLE left over from an earlier
--     step, or a pooled connection that silently assumed another role, must
--     fail here rather than write under the wrong identity. Every step file in
--     this packet passes expected_role=write_role, because D-045 decision 1
--     allows exactly one credential: the direct migrator session. The
--     read-only steps still cannot write, because they wrap their work in an
--     explicit SET TRANSACTION READ ONLY and assert that no row moved.
SELECT CASE
         WHEN current_user = :'expected_role'
          AND session_user = :'expected_role'
         THEN current_user
         ELSE current_setting('stashtab_f2.f2_guard_session_is_not_the_expected_role')
       END AS g9_session_role;
