# Cross-platform review automation

The workflow `.github/workflows/cross-platform-review.yml` launches independent
Cursor and Codex reviewers against the same pull-request head commit, then asks a
separate read-only Codex run to synthesize their saved reports.

## Trigger

- Pull request opened
- Pull request reopened
- New commits pushed to a pull request
- Draft pull request marked ready for review
- Manual workflow dispatch

Fork pull requests are intentionally excluded because GitHub secrets are required.
Concurrent runs for the same pull request are cancelled when a newer commit arrives.

## Required GitHub secrets

- `CURSOR_API_KEY`: Cursor user or service-account key used by `@cursor/sdk`
- `OPENAI_API_KEY`: OpenAI API key used by `openai/codex-action`

## Safety boundaries

- Review agents receive read-only instructions and are pinned to one commit.
- Codex uses `sandbox: read-only` and the action's default sudo-removal strategy.
- The initial workflow never commits, pushes, deploys, migrates, or applies fixes.
- Only same-repository pull requests may use the secrets.
- Reviewer reports are retained as workflow artifacts before synthesis.
- The synthesis updates one marker-based PR comment instead of producing comment spam.
- Human approval remains required before implementing findings.
- A final read-only curator produces a compact proposed context handoff artifact.
- The handoff never edits `CURRENT.md`; a human must approve its promotion.

## Durable context and backlog

Fresh agents follow `docs/agent-context/INDEX.md` and receive only the current
summary plus their role packet. The contract gate validates that these packets
exist and remain within their context budgets.

The next build phase may be queued in `docs/agent-context/BACKLOG.md`. Planning and
review can happen while queued, but automation must not implement an item marked
`BUILD BLOCKED`.
