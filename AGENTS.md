# StashTab agent instructions

Before planning or changing card identification, OCR intake, catalog matching,
JustTCG fallback, pricing enrichment, review queues, notifications, staging, or
inventory promotion:

1. Read `PLAN.md`.
2. Read `docs/card-resolution-workflow/CONTRACT.md`.
3. Read every proposed or frozen amendment in `docs/card-resolution-workflow/`.
4. Read `docs/agent-context/INDEX.md` and only the role packet it assigns.
5. Preserve Python/FastAPI ownership of business logic and `shop_id` scoping.
6. Do not enable external delivery, perform production migrations, push, or deploy
   without explicit human approval.

Reviewers must cite contract clauses, exact code, or failing tests. Agreement
between agents is not acceptance evidence.

Agents must not treat chat transcripts as durable project memory. Record only
verified facts, approved decisions, evidence-backed lessons, and explicit open
questions through the context-handoff process.
