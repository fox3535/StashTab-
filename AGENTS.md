# StashTab agent instructions

## Canonical workspace and product boundary

- Work from `C:\Users\Chris\Desktop\Cursor Projects\StashTab` unless a named
  clean worktree is explicitly approved.
- StashTab is a vendor-only trading-card operating system. A consumer
  marketplace, escrow, and seller-payout platform are out of scope.
- Never delete, overwrite, or silently absorb preserved legacy worktrees or the
  partner Python snapshot.

## Required reading and source precedence

Before planning or changing code:

1. Read `PLAN.md`.
2. Read `docs/agent-context/INDEX.md` and `CURRENT.md`, then only the role packet
   assigned for the task.
3. Read the relevant frozen contract and amendments for the subsystem being
   changed. Do not load unrelated contract packets.
4. Inspect the current implementation and tests before proposing replacement
   code.

When sources disagree, frozen contracts and approved amendments win, followed
by recorded decisions/current context, then this plan. Report stale text rather
than guessing. Chat transcripts are not durable project memory.

## Preserve and use the partner Python brain

- `vendor/mimir-partner/` is a read-only reference snapshot of the partner's
  Python application. Preserve its behavior and provenance.
- Python/FastAPI owns business rules, tenant authorization, inventory, sales,
  reconciliation, pricing, and worker logic. Do not rewrite that logic in
  TypeScript.
- Do not blindly copy the snapshot. For each port or optimization, cite the
  partner source file/function, current StashTab target, preserved behavior,
  intentional deviations, and parity/regression tests.
- Extend the existing FastAPI modules when they are the stronger foundation.
  Do not create parallel inventory, sales, pricing, Shopify, reporting, or
  reconciliation systems.

## Preserve and later recover frontend work

- Existing frontend work and dirty legacy worktrees belong to the owners. Do
  not discard, bulk-copy, or overwrite them.
- Until the backend-foundation exit gate in `PLAN.md` closes, frontend changes
  are limited to safety, authentication, deployment compatibility, and required
  smoke-test fixes.
- Immediately after that gate closes, begin the planned frontend recovery and
  redesign phase: inventory current and legacy UI, preserve valuable work,
  improve the UX/design system, and reconnect it to accepted FastAPI contracts.
- A redesign is not permission to replace working backend behavior or revive
  starter-kit architecture such as Convex.

## Non-negotiable engineering rules

- Every tenant-owned operation is scoped by verified Clerk identity plus shop
  membership and `shop_id`; caller headers are hints, never identity.
- Neon PostgreSQL is the application database. Convex is not part of the target
  architecture.
- Use reviewed migrators for staging/production schema changes; never startup
  `create_all` or ad-hoc schema mutation.
- Preserve append-only inventory/notification evidence, idempotency,
  reconciliation, rollback, and least-privilege database roles.
- Do not commit secrets or local env files. Do not push, merge, migrate, deploy,
  enable external delivery, use paid provider credits, or use production
  credentials without the matching explicit human approval.
- Reviews require contract clauses, exact code, or test evidence. Agent
  agreement is not acceptance evidence.
- Use bounded review/correction/finalization paths. A timeout or repeated review
  is not success and must not create an endless gate loop.

## Lean execution protocol

- Use one builder agent for a slice. Other agents may perform one bounded
  specialist review, but must not repeat the full implementation workflow.
- Read only `PLAN.md`, `docs/agent-context/INDEX.md` and `CURRENT.md`, the active
  slice directive, and contracts directly relevant to the changed subsystem.
  Do not reload historical reviews or chat transcripts without a concrete need.
- Routine frontend and documentation work may run as one continuous sequence:
  inspect, implement, test, review once, correct once, commit, push, and open a
  draft PR. A named slice unlock authorizes these reversible local steps.
- Normal backend work uses one short plan, one implementation pass, relevant
  tests, one bounded review, and one correction pass.
- Reserve freeze/amendment packets and separate approval gates for high-risk
  changes: authentication/authorization, tenant isolation, database schema,
  payments, production, secrets, external delivery, paid providers, and frozen
  contract behavior.
- Always require separate human approval for merge, deploy, migration, enabling
  external or paid features, production credentials, and destructive actions.
- Stop only for a genuine owner decision, conflicting contract, unsafe or
  destructive action, missing authority/credential, P0/P1 finding, or failed
  acceptance criterion that cannot be corrected within the named slice.
- Do not stop for facts discoverable from the repository, reversible local
  edits inside scope, routine tests, or already-approved implementation details.
- Keep status reports concise: outcome, changed files, tests/evidence, genuine
  blockers, next action, and one terminal status line. Store detailed evidence
  in repository files instead of repeating it in chat.
- Keep the exit path finite. Deferred production, provider, compliance, and
  product work must not silently become blockers for an accepted local slice.

## Planning and context hygiene

- Pin implementation and review work to an exact Git commit.
- Backlog approval permits planning only unless a named gate explicitly unlocks
  implementation.
- Record only verified facts, approved decisions, evidence-backed lessons, and
  explicit open questions through the context-handoff process.
- Keep `PLAN.md`, mutable agent context, and acceptance records aligned after
  each completed slice; never rewrite frozen history to make it look current.
