# Optional external AI reviews

The `Cross-platform contract review` workflow can call Cursor and OpenAI.
Those jobs are advisory. They are not a substitute for product, contract,
PostgreSQL, identity, inventory, or build/test gates.

No API keys are stored in this repository.

## If secrets are not configured

GitHub does not allow `secrets` in job-level `if` conditions. The workflow
copies the secret into a step `env` and checks whether it is empty. If
`CURSOR_API_KEY` or `OPENAI_API_KEY` is missing, it records that the external
review was not run. It does not invent a review. It does not run synthesis
or context handoff as if those reviews passed. Checked-in
human/independent review files under `docs/**/reviews/` remain the
inspectable review evidence.

## To enable the advisory automation later

Repository owners must add GitHub Actions secrets named:

- `CURSOR_API_KEY`
- `OPENAI_API_KEY`

Do not put those values in workflow YAML, source, or commits.
