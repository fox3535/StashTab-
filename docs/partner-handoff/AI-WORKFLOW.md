# Gemini + Antigravity + Qoder workflow

Human partner chooses feature/design goals. Gemini frames bounded directives
and evaluates evidence; it must not claim file/test/cloud access it lacks.
Antigravity OR Qoder is the one active builder for a slice. Do not have both edit
the same checkout concurrently. Git and durable docs, not chat memory, carry state.

Loop: inspect existing implementation -> short plan -> implement scoped changes
-> relevant tests/visual checks -> one bounded review -> fix concrete findings
-> feature-branch commit -> authorized push/draft PR. Unresolved P0/P1 means
blocked, not done. Avoid endless reviews and approvals for routine local details.
Transfers between builders record full SHA, branch, dirty files, test results,
remaining questions and next step.

Separate explicit approval remains necessary for merge, deploy, migrations,
grants, live writes, external delivery, paid providers, production, destructive
operations and frozen-contract changes. Never push main, force-push or bypass
protections. F2 Gate 2 and successful receive are separate approvals.
Use local fixtures for UI work during staging hold; label them, never report
mock evidence as live proof. Preserve tenant isolation and Python business logic.

## Directive template Gemini should generate

Title: <slice> — <concrete outcome>

Objective: one user-visible outcome.
Evidence: inspected commit/files; known facts separated from unknowns.
Scope: allowed changes, exclusions and work to preserve.
Acceptance: observable results plus relevant tests/visual checks.
Authority: allowed local/branch/PR actions; separately gated operations.
Execution: inspect/reuse, implement, test, review once, correct, finalize.
Stop: genuine missing authority, contract conflict, failed invariant or P0/P1.
Reporting: maximum four bullets (outcome/files, tests and limitations,
branch/full SHA/PR, blocker or one next action); detailed evidence in docs.
End exactly: <SLICE> — <VERIFIED STATUS>, <REMAINING GATE>.

## Communication and evidence

Outcome first; plain language; title every directive. Give only the next manual
step when the human must act. Supply complete copyable commands, not references
to old messages. Never ask for credentials in chat. Distinguish provided,
executed, verified, committed, merged and deployed. Old output is not fresh proof;
identical row values alone do not prove two outputs came from the same run.
Use execution/timestamp evidence, exact tokens and exit codes where required.

Do not invent product scope from a backlog. Do not block routine frontend work
on unrelated production gates. Stop for a real consequential choice, not facts
discoverable from the repository. Preserve evidence even when it is inconvenient.

## Final builder report

- Outcome: changed files/behavior and preserved scope.
- Checks: actual commands/results; skipped checks and limitations.
- Git: branch, full SHA, PR link and draft/merge status; deploy status separate.
- Next: one next action or precise blocker.

<SLICE> — <STATUS>, <LIVE-OPERATION GATES>

For UI: mobile/desktop, keyboard/focus/contrast, loading/empty/error/offline,
no misleading enabled controls; reuse design tokens/components; explain
intentional system changes. Inspect package.json for current tests; affected
tests/typecheck/build as appropriate. Backend changes need relevant tenant,
auth, idempotency and regression tests. Never build a second backend for a mock.
