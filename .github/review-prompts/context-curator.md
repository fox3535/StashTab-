# Context handoff curator

Create a compact proposed handoff for a fresh agent at this exact commit. Read the
frozen contract, `docs/agent-context/INDEX.md`, `CURRENT.md`, the synthesized review
artifact, and the repository diff.

Output Markdown with: commit, verified changes, tests/evidence, approved decisions,
unresolved findings, blockers, next gated action, and lessons supported by citations.
Clearly label hypotheses. Do not include chain-of-thought, secrets, customer data,
raw provider payloads, or uncited claims. Do not modify the repository or contract.
Keep the proposal under 150 lines and state that human approval is required before
it replaces `CURRENT.md`.
