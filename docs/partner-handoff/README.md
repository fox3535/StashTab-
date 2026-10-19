# StashTab partner handoff — 2026-10-19

Read this, AI-WORKFLOW.md and GEMINI-STARTER.md, then AGENTS.md, PLAN.md,
docs/agent-context/INDEX.md and CURRENT.md, the matching role packet and only
task-relevant frozen contracts/amendments. Older context is stale; dated execution
evidence matters. This document authorizes no live operation.

## Critical current hold

Repository inspected and fetched October 19: main and origin/main are
e8fb3b2ae1bb5833a56d661b2cf0ae52fa96cbc8 (PR #42 landing/branding merge).
No live staging checks performed for this handoff.

The saved audit's last entry, October 1, records staging api FAILED, new deployment
d9f3dfe2-785e-4c7f-b175-933dbcb2b7c9, old deployment
44317623-c881-4e4a-9615-984290e7dbd8 REMOVED, readiness HTTP 404. Freshness
checks stopped before SSH and 05/05b reruns. Cause, actor, schema impact and
present status are unknown. Do not assume autodeploy caused it. Restoration
requires separate approval, not an old cutover command.

Evidence: ../inventory-truth-v1/AUDIT-F2-CUTOVER-GEN1-20260919T045427Z.md,
especially final section N entries. Historical optimistic headings do not
override the later failure. Audit is preserved unchanged, not independently
re-certified by this handoff.

Last DB check September 30: 04 G1–G9/V1–V7 passed, EXIT=0. Database
stashtab_staging; Smoke Shop B 798d40f4-0832-46c4-991b-050e1310f6c4;
generation 1, row id=1, locking, opened_at NULL; frozen_at and created_at
2026-09-21 00:58:16.503535+00. No receive evidence then. Not current proof.
Historical HTTP checks passed; 05/05b passed September 25. R1–R3 were trivial
zero-row results, not successful receive proof. Gate 2/06 has no recorded
execution; successful receive remains unauthorized. Never rerun 01 (expects
empty cutover) or 03 (inserts locking). No 06 or break-glass from this handoff.

Original baselines, not to be replaced to conceal drift:
- freeze_window_start: 2026-09-19 04:54:27.776376+00
- baseline_digest: 4a556fc25312fc7c9664f80f84c9f271
- baseline_excl_cutover: 058e9f26376fa7e7c95bfc6afdf452e8
- base_r5_inventory: 8669a4d11ff3bc75cb3b7b737236c9f7
- base_r5_notification: 75e7e3d7093ac362292ab59fe82b7321
- notification_baseline_state: absent

## Product, design and feature freedom

Vendor-only TCG operating system, not consumer marketplace/escrow. Next.js UI,
Python/FastAPI business logic, Neon PostgreSQL data, Clerk identity plus verified
shop membership. Headers alone grant nothing; no Convex reintroduction.
Preserve vendor/mimir-partner/ as read-only reference; extend existing systems.

F1 landing/branding merged: immediate static hero, no intro scroll video, one
signed-in Open Dashboard entry, public POS Find links removed, authenticated
POS Find retained, supplied SVG marks/wordmarks and enlarged header branding.
Merged does not mean deployed.

Design starting points: app/globals.css, existing components,
UI_DESIGN_SYSTEM.md and OPEN_DESIGN_HANDOFF.md. Compare docs with implementation.
Chris invites partner feature and design contributions. A requested local slice
may proceed with fixtures/local tests while staging is held. Keep unavailable
actions honest; preserve backend/security contracts. No unrelated rewrite.
Production, external delivery, payments, migrations and live feature enablement
are not granted by general design freedom.

## First session and local material

Get normal GitHub collaborator access. Fetch, inspect HEAD/branch/dirty files,
never reset/clean/overwrite. Until merged, read this handoff from its PR branch.
Read the source chain above; report the staging hold; choose a local slice OR
seek separate authority for read-only incident investigation. Establish local
dependencies from lockfiles/setup docs. Frontend used port 3001; verify config
before requests. Do not blindly start a service against staging.

Existing unrelated modified file preserved and NOT included:
docs/frontend-recovery-v1/PLAN-F2-SLICE-01-CONTROLLED-RECEIVE.md.
Untracked .qoder/, lib/use-api-auth.ts, barcode PNGs, mobile-header-screenshot.png,
and Python cache are not automatically committed. Inspect with Chris before
moving them. The audit is intentionally included as historical evidence.

Git carries no ignored .env, sessions, passwords or Docker containers. Arrange
authorized private access; prefer individual collaborator accounts. Shared Qoder
access is not blanket permission for connected services. Chris remains the
recorded F2 supervisor unless explicitly changed in an approved record.

If Path A is separately resumed: private human PowerShell holds PG variables,
credential-free f2c holds approved SQL, docker exec forwards variable NAMES only
including PGSSLMODE, never expanded passwords. Masked entry; psql -X -w; verify
full include variables and all SQL hashes. One command/result at a time; failure
stops, no automatic retry/repair. Tokens stay in-page, never printed/saved or
expanded into curl arguments. No cloud credential belongs in model chat.
