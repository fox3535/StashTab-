# Automation states

Specification only. No scheduler.

Every **working** state lists: entry, objective/owner, permitted, evidence,
success, timeout/heartbeat, retry, escalation, terminal failure, idempotency
key, exact next states.

**Run kind** (`planning` | `pr` | `weekly` | `prerelease` | `quarterly` |
`pentest` | `learning` | `unlock`) is part of every key.

## Names

| Name | Meaning |
|---|---|
| `completed` | Gate succeeded |
| `completed_with_warnings` | Succeeded with accepted P2/P3 gaps |
| `rejected` | Human rejected |
| `superseded` | Newer packet/run replaced this key |
| `cancelled` | Kill switch / abort |
| `failed_retryable` | **Not** terminal; next `retry_wait` if attempts remain |
| `failed_permanent` | Terminal. New human-issued key may open a wait; no auto-advance |
| `awaiting_named_human` | Human wait; `gate_id` required; not success |

`retry_wait` is not terminal. Key includes `attempt`.

---

## Planning run (`run_kind=planning`)

### `queued_research`

- Entry: backlog says planning allowed
- Owner: planner
- Permitted: docs under `docs/security-assurance-v1/` and context/backlog
- Evidence: INDEX + reading-order files
- Success: files present; no scanners/payment/Watch code added
- Timeout/heartbeat: 8h / 30m
- Retry: 1 via `retry_wait`
- Failure: prohibited impl → `failed_permanent`
- Key: `planning:queued:<docs-hash>:a<n>`
- Next success: `planning_draft`

### `planning_draft`

- Entry: queued success
- Owner: planner
- Permitted: planning docs only
- Success: checklist; no executable payments/models/scanners
- Timeout/heartbeat: 8h / 30m
- Retry: 1
- Key: `planning:draft:<docs-hash>:a<n>`
- Next success: `independent_review`

### `independent_review`

- Entry: draft hash stable
- Owner: six read-only reviews
- Success: six present
- Timeout/heartbeat: 4h / 20m
- Retry: 1 per missing role
- Failure: `awaiting_named_human` (`gate_id=independent_review`), **not**
  `planning_accept`
- Key: `planning:review:<docs-hash>:a<n>`
- Next success: `synthesis`

### `synthesis`

- Entry: six reviews
- Owner: planner writes `reviews/PLANNING-REVIEW.md`
- Success: file exists and does not assert freeze/unlock
- Timeout/heartbeat: 2h / 15m
- Retry: 1
- Failure: unlock claim → `failed_permanent`
- Key: `planning:synth:<docs-hash>:a<n>`
- Next success: `awaiting_named_human` (`gate_id=planning_accept`)

### `implementation_unlock`

- Entry: human asked to unlock a **named** PHASED slice
- Owner: sponsor
- Permitted: humans only
- Evidence: named slice; ROE if testing; payments/Watch extras as listed in
  PHASED-IMPLEMENTATION
- Success: explicit unlock text
- Timeout: 14d human wait
- Retry: 0
- Key: `unlock:<slice-id>:<sha>`
- Next: `completed` (that slice) | `rejected` | `cancelled`

Legal gates (`payments_config`, `pci_scope`, `tax_allocation`,
`accounting_review`, `market_data_license`, `watch_model_promote`,
`cross_tenant_aggregate`) record confirmation only. They do not unlock code.

---

## Future test runs (not enabled)

Retry keys include `:a<n>`. Timeout is not success.

- `pr_passive` key `pr:<sha>:a<n>` — timeout 30m; fail retryable then
  permanent; success `completed` run_kind=pr only
- `weekly_window` key `weekly:<date>:<allowlist-hash>:a<n>` — kill cancelled;
  timeout failed_permanent
- `pre_release` key `prerelease:<sha>:a<n>` — timeout → wait
  `gate_id=pre_release`
- `quarterly_exercise` key `quarterly:<yyyy-qn>:a<n>` — restore after token
  scrub
- `independent_pentest` key `pentest:<year-or-change>`
- `finding_intake` key `finding:<fingerprint>` run_kind=learning
- `learning_proposal` → wait `gate_id=learning:<fingerprint>` (does not
  replace `implementation_unlock`)
- `retry_wait` — attempt++; exhausted → `failed_permanent`
