# Inventory-truth freeze manifest (v1.2.0 procedure)

Hashes live in a non-self-referential JSON manifest. `CONTRACT.md` never
stores its own full-file SHA-256.

## After a human vote (not now)

1. Apply the approved AMENDMENT-1.2.0 diffs to DESIGN, MIGRATION, TESTS,
   and the amendment file.
2. Append CONTRACT §9 **only** as the closed text in the amendment packet:
   version `1.2.0`, pointer to this manifest path, statement that §2 and
   §8 remain, and that this file does not store its own hash. No generated
   timestamp and no mutable extra status after this point.
3. Compute SHA-256 of the **exact Git blob bytes** of each listed file
   (`git hash-object --no-filters -- <file>` or `Path.read_bytes()` of
   the committed file). No transcoding. No line-ending rewrite.
4. Write `docs/inventory-truth-v1/freezes/FREEZE-1.2.0.json` with those
   hashes, algorithm, previous-freeze pointer, and freeze timestamp.
   The manifest does **not** list or hash itself.
5. Do not edit any hashed file after step 3.

## Manifest fields (required)

- `contract_id` (string)
- `contract_version` (string, e.g. `1.2.0`)
- `freeze_status` (`FROZEN` after vote; `PROPOSED` is not a freeze)
- `freeze_timestamp` (UTC ISO-8601, manifest-only; not copied into hashed files)
- `approved_amendments` (array of ids, must include `AMENDMENT-1.2.0`)
- `previous_freeze` (`contract_version` `1.1.0`, `record` pointing at
  CONTRACT §8; history also requires CONTRACT still contains the v1.0.0
  §2 table)
- `algorithm` (`SHA-256`)
- `canonical_bytes` (`exact-file-bytes-no-rewrite`)
- `files` (array of `{path, sha256}` lowercase hex, 64 chars)

Paths must be repository-relative, unique, POSIX slashes, no `..`,
not absolute, and must stay under `docs/inventory-truth-v1/`.

Required hashed paths for 1.2.0:

- `docs/inventory-truth-v1/CONTRACT.md`
- `docs/inventory-truth-v1/DESIGN.md`
- `docs/inventory-truth-v1/MIGRATION.md`
- `docs/inventory-truth-v1/TESTS.md`
- `docs/inventory-truth-v1/amendments/AMENDMENT-1.2.0.md`

## Validator

`scripts/validate_inventory_truth_freeze.py --manifest <path>`

Loads the manifest, rejects bad paths, recomputes every listed hash,
checks contract version and amendment ids, and confirms §2 and §8
history strings remain in CONTRACT.md.
