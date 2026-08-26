# Staging-readiness freeze manifest

Hashes live in `FREEZE-v1.json`. That JSON is **not** listed in `files` and does not hash itself.

## Canonical bytes

- `algorithm`: SHA-256
- `canonical_bytes`: `git-lf-text-bytes` (CRLF/CR normalized to LF, then SHA-256)
- Paths: repository-relative, POSIX slashes, under `docs/staging-readiness-v1/`
- The freeze JSON, `DIRECTIVE-SLICE-00.md`, and files under other directories are not hashed here

## After freeze

Do not edit hashed files. A new freeze is required if the packet changes.
