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

- Card resolution: `docs/card-resolution-workflow/CONTRACT.md`
- Inventory truth: `docs/inventory-truth-v1/CONTRACT.md`
  (`FROZEN, IMPLEMENTATION BLOCKED BY FAIL-CLOSED IDENTITY`)

