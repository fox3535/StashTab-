"""Validate identity-score-v0 freeze (non-self-hashing)."""

from __future__ import annotations

import hashlib
import json
import posixpath
import sys
from pathlib import Path

REQUIRED_FIELDS = (
    "contract_id",
    "contract_version",
    "policy_id",
    "freeze_status",
    "freeze_timestamp",
    "authority",
    "algorithm",
    "canonical_bytes",
    "human_vote",
    "files",
)

REQUIRED_PATHS = (
    "docs/card-resolution-workflow/CONTRACT.md",
    "docs/card-resolution-workflow/SCORING-POLICY-INTAKE-ABSTENTION.md",
    "docs/card-resolution-workflow/freezes/IDENTITY-SCORE-v0.md",
    "docs/card-resolution-workflow/reviews/DETERMINISTIC-ACCEPT-AUTHORITY-CHECK.md",
    "docs/card-resolution-workflow/freezes/FREEZE-CHECK-IDENTITY-SCORE-v0.md",
)

ALLOWED_PREFIX = "docs/card-resolution-workflow/"
MANIFEST = "docs/card-resolution-workflow/freezes/FREEZE-IDENTITY-SCORE-v0.json"
HEX64 = 64
CANONICAL = "git-lf-text-bytes"


def repo_root() -> Path:
    return Path(__file__).resolve().parents[1]


def lf_bytes(data: bytes) -> bytes:
    return data.replace(b"\r\n", b"\n").replace(b"\r", b"\n")


def sha256_file(path: Path) -> str:
    return hashlib.sha256(lf_bytes(path.read_bytes())).hexdigest()


def normalize_relpath(raw: str) -> str:
    if not isinstance(raw, str) or not raw.strip():
        raise ValueError("empty path")
    path = raw.replace("\\", "/").strip()
    if path.startswith("/") or (len(path) >= 2 and path[1] == ":"):
        raise ValueError(f"absolute path rejected: {raw}")
    if ".." in posixpath.normpath(path).split("/"):
        raise ValueError(f"path escapes repository: {raw}")
    if not path.startswith(ALLOWED_PREFIX):
        raise ValueError(f"path outside freeze tree: {path}")
    if path.endswith("FREEZE-IDENTITY-SCORE-v0.json"):
        raise ValueError("manifest must not hash itself")
    return path


def write_manifest(root: Path) -> None:
    files = [{"path": p, "sha256": sha256_file(root / p)} for p in REQUIRED_PATHS]
    payload = {
        "contract_id": "STASHTAB-CARD-RESOLUTION-001",
        "contract_version": "1.0.0",
        "policy_id": "identity-score-v0",
        "freeze_status": "FROZEN",
        "freeze_timestamp": "2026-08-27T06:20:00Z",
        "authority": "CONTRACT.md section 16; sections 1, 5, 6, 7, 8, 13.1, 15",
        "algorithm": "SHA-256",
        "canonical_bytes": CANONICAL,
        "human_vote": "APPROVE",
        "does_not_amend_contract": True,
        "implementation_unlocked": False,
        "files": files,
    }
    dest = root / MANIFEST
    dest.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    print(f"wrote {MANIFEST}")


def validate(root: Path) -> None:
    manifest_path = root / MANIFEST
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    missing = [k for k in REQUIRED_FIELDS if k not in manifest]
    if missing:
        raise SystemExit(f"missing fields: {missing}")
    if manifest["freeze_status"] != "FROZEN":
        raise SystemExit("freeze_status must be FROZEN")
    if manifest["contract_id"] != "STASHTAB-CARD-RESOLUTION-001":
        raise SystemExit("contract_id mismatch")
    if manifest["contract_version"] != "1.0.0":
        raise SystemExit("contract_version must remain 1.0.0")
    if manifest["policy_id"] != "identity-score-v0":
        raise SystemExit("policy_id mismatch")
    if manifest["canonical_bytes"] != CANONICAL:
        raise SystemExit("canonical_bytes mismatch")
    if manifest.get("implementation_unlocked") is not False:
        raise SystemExit("implementation must remain locked")
    files = manifest["files"]
    if not isinstance(files, list) or not files:
        raise SystemExit("files must be a non-empty list")
    listed = []
    seen: set[str] = set()
    errors: list[str] = []
    for entry in files:
        rel = normalize_relpath(entry["path"])
        if rel in seen:
            raise SystemExit(f"duplicate path: {rel}")
        seen.add(rel)
        listed.append(rel)
        digest = str(entry["sha256"]).lower()
        if len(digest) != HEX64 or any(ch not in "0123456789abcdef" for ch in digest):
            raise SystemExit(f"invalid sha256 for {rel}")
        target = (root / rel).resolve()
        try:
            target.relative_to(root.resolve())
        except ValueError as exc:
            raise SystemExit(f"path escapes repository: {rel}") from exc
        if not target.is_file():
            raise SystemExit(f"missing file: {rel}")
        actual = sha256_file(target)
        if actual != digest:
            errors.append(f"{rel} expected {digest} got {actual}")
    if set(listed) != set(REQUIRED_PATHS):
        raise SystemExit(f"path set mismatch: {set(listed) ^ set(REQUIRED_PATHS)}")
    if MANIFEST in listed:
        raise SystemExit("manifest must not hash itself")
    if errors:
        raise SystemExit("\n".join(errors))
    print("identity-score-v0 freeze OK")


def prove_tamper(root: Path) -> None:
    sample = root / REQUIRED_PATHS[1]
    original = lf_bytes(sample.read_bytes())
    good = hashlib.sha256(original).hexdigest()
    bad = hashlib.sha256(original + b"x").hexdigest()
    if good == bad:
        raise SystemExit("tamper proof failed: hashes matched")
    listed = json.loads((root / MANIFEST).read_text(encoding="utf-8"))["files"]
    expected = next(e["sha256"] for e in listed if e["path"] == REQUIRED_PATHS[1])
    if good != expected:
        raise SystemExit("tamper proof failed: listed hash is not current file")
    print("one-byte tamper changes digest OK")


def main() -> int:
    root = repo_root()
    if "--write" in sys.argv:
        write_manifest(root)
        return 0
    validate(root)
    if "--prove-tamper" in sys.argv:
        prove_tamper(root)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
