# Freeze-evidence correction — checkout conversion only

**Date:** 2026-08-25  
**Decision unchanged:** AMENDMENT-1.1.1, AMENDMENT-1.1.2, and inventory-truth 1.2.0 remain approved and frozen.

This record does **not** change contract text, table inventory, or approved
product decisions. It corrects how byte hashes are captured.

## What went wrong

Historical freeze JSON files hashed Windows working-tree bytes under
`core.autocrlf=true` (CRLF). Git stores those files as LF blobs. Linux CI
checks out LF, so historical hashes failed there even though the committed
text was unchanged.

`git ls-files --eol` on this correction showed `i/lf w/crlf` for the hashed
markdown files: index/blob LF, working tree CRLF.

## What is preserved

- `FREEZE-1.1.1.json`
- `FREEZE-1.1.2.json`
- `docs/inventory-truth-v1/freezes/FREEZE-1.2.0.json`

Those files remain historical Windows-checkout hash evidence. They are not
silently rewritten.

## What is added

Canonical Git-LF hash records:

- `FREEZE-1.1.1-git-canonical.json`
- `FREEZE-1.1.2-git-canonical.json`
- `docs/inventory-truth-v1/freezes/FREEZE-1.2.0-git-canonical.json`

`canonical_bytes` for these records is `git-lf-text-bytes`. Validators hash
file bytes after normalizing CR LF / CR to LF. That matches Git blobs and
Linux checkouts. A genuine content change still fails.

`.gitattributes` now pins LF for frozen contract/specification/manifest text.
