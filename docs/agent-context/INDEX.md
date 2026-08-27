# Agent context index

This directory is the compact, durable memory for fresh agents. Do not load raw
chat history or every archived handoff.

## Required reading

All roles read, in order:

1. `PLAN.md`
2. `docs/card-resolution-workflow/CONTRACT.md`
3. Relevant amendments in `docs/card-resolution-workflow/`
4. `docs/agent-context/CURRENT.md`
5. One matching file in `docs/agent-context/roles/`

Read `DECISIONS.md`, `LESSONS.md`, or an archived handoff only when the assigned
task points to it.

## Context rules

- Pin work and reviews to an exact Git commit.
- Facts require a repository, test, PR, or contract citation.
- Label unverified claims as hypotheses.
- Never store secrets, raw provider responses, customer data, or chain-of-thought.
- The frozen contract cannot be changed by a context update.
- `CURRENT.md` is limited to 150 lines; each role packet to 200 lines.
- Context updates are proposals until a human approves them.

## Frozen planning contracts

- Card resolution: `docs/card-resolution-workflow/CONTRACT.md` v1.0.0;
  AMENDMENT-1.1.0 (product policy, file unchanged);
  AMENDMENT-1.1.1 frozen (`docs/backend-notification-integration-v1/freezes/FREEZE-1.1.1.json`);
  AMENDMENT-1.1.2 frozen (`docs/backend-notification-integration-v1/freezes/FREEZE-1.1.2.json`);
  local 1.1.2 backend accepted 2026-08-25; PR #1 merged as
  `c3647a4eda37d355ed47f9e77ad667e4fda7930c`; not deployed
- Inventory truth: `docs/inventory-truth-v1/CONTRACT.md` v1.2.0
  (`FROZEN; slices accepted, on main via c3647a4, not deployed`)
- Staging readiness: `docs/staging-readiness-v1/` frozen at
  `freezes/FREEZE-v1.json`; slice-00 isolated API code accepted 2026-08-25;
  slice-01 identity smoke **COMPLETED, DEPLOYED TO STAGING ONLY** (D-025,
  `ACCEPTANCE-SLICE-01.md`). Frozen `GATES.md` is unchanged; live status is
  `GATES-POINTER-SLICE-01.md`.
- Convex is not in the target architecture (D-024 in `DECISIONS.md`). Frozen
  staging text that said “Convex deferred” is historical and superseded.

