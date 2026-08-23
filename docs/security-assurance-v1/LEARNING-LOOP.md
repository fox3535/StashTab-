# Controlled learning loop

Findings and Watch evaluations may improve StashTab only through
human-approved change. Uncontrolled continual learning is forbidden.

## Allowed for agents (draft only)

- Draft a regression test or control text in a proposal
- Draft a backlog note under a **queued** item
- Draft a `LESSONS.md` sentence with a citation
- Draft an **offline** model/rule change proposal with evaluation evidence

## Forbidden without named human approval (merge/enable)

- Merging tests that fail CI
- Creating or enabling a blocking gate
- Expanding targets, cadence, or ROE
- Enabling scanners, jobs, production access, Stripe/PayPal, Watch models
- Starting `card-resolution-core-v1` or freezing amendment 1.1.0
- Implementing RLS, wallets, payment tables, or Watch schemas
- Silently changing production prompts, weights, thresholds, source
  priority, training sets, or models
- Storing exploit payloads

Fail-closed auth tests that already belong to an **unlocked product slice’s
acceptance list** may be implemented in that slice after that slice’s human
gate.

## Security-finding loop

```text
finding (citation)
  -> learning_proposal (draft)
  -> awaiting_named_human (gate_id=learning:<fingerprint>)
  -> approved: owning **unlocked** slice may implement
  -> rejected | superseded | cancelled
```

## Watch outcome loop

Follow `AI-RISK.md` steps 1–8. Promotion uses `gate_id=watch_model_promote`
and still requires `implementation_unlock` for this package if schemas/jobs
are new.

Agent discomfort is not evidence (frozen contract §1, §6). Duplicate
fingerprint + unchanged evidence is deadlock.
