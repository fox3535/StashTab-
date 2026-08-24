# Notification freeze manifest (v1.1.1 procedure)

Hashes live in a non-self-referential JSON manifest. Amendment, directive,
and freeze-check files never store their own full-file SHA-256.

## After the human APPROVE vote

1. Record D-N5 (at-least-once transport) in AMENDMENT-1.1.1.
2. Leave `docs/card-resolution-workflow/AMENDMENT-1.1.0.md` byte-identical.
3. Compute SHA-256 of the **exact file bytes** of each listed file
   (`Path.read_bytes()` / `git hash-object --no-filters`). No transcoding.
4. Write `docs/backend-notification-integration-v1/freezes/FREEZE-1.1.1.json`.
   The manifest does **not** list or hash itself.
5. Do not edit any hashed file after step 4.

## Manifest fields (required)

- `contract_id`
- `contract_version` (`1.1.1`)
- `freeze_status` (`FROZEN`)
- `freeze_timestamp` (UTC ISO-8601, manifest-only)
- `approved_amendments` (must include `AMENDMENT-1.1.1`; records `AMENDMENT-1.1.0` as unchanged product-policy)
- `previous_freeze` (parent contract `1.0.0` + 1.1.0 policy record)
- `algorithm` (`SHA-256`)
- `canonical_bytes` (`exact-file-bytes-no-rewrite`)
- `files` (array of `{path, sha256}` lowercase hex, 64 chars)

Paths must be repository-relative, unique, POSIX slashes, no `..`,
not absolute. Allowed locations:

- under `docs/backend-notification-integration-v1/` except this JSON
- `docs/card-resolution-workflow/AMENDMENT-1.1.0.md`

Required hashed paths:

- `docs/backend-notification-integration-v1/AMENDMENT-1.1.1.md`
  (state machine, schema, and acceptance tests live here)
- `docs/backend-notification-integration-v1/DIRECTIVE.md`
- `docs/backend-notification-integration-v1/FREEZE-CHECK.md`
- `docs/card-resolution-workflow/AMENDMENT-1.1.0.md`

## Validator

`python scripts/validate_notification_freeze.py --manifest docs/backend-notification-integration-v1/freezes/FREEZE-1.1.1.json`

`--negative-check` mutates and restores each frozen file and rejects
version, amendment, missing, duplicate, absolute, and path-escaping
manifests.
