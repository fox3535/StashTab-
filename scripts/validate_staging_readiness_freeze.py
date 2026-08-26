"""Validate staging-readiness freeze manifest (non-self-hashing)."""

from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

REQUIRED_FIELDS = (
    "packet_id",
    "packet_version",
    "freeze_status",
    "freeze_timestamp",
    "baseline_commit",
    "algorithm",
    "canonical_bytes",
    "files",
)
REQUIRED_PATHS = (
    "docs/staging-readiness-v1/INDEX.md",
    "docs/staging-readiness-v1/TOPOLOGY.md",
    "docs/staging-readiness-v1/ENVIRONMENT.md",
    "docs/staging-readiness-v1/ROLES.md",
    "docs/staging-readiness-v1/SCHEMA.md",
    "docs/staging-readiness-v1/SAFEGUARDS.md",
    "docs/staging-readiness-v1/REHEARSAL.md",
    "docs/staging-readiness-v1/CUTOVER.md",
    "docs/staging-readiness-v1/FLAGS.md",
    "docs/staging-readiness-v1/SMOKE.md",
    "docs/staging-readiness-v1/OPERATIONS.md",
    "docs/staging-readiness-v1/RUNBOOK.md",
    "docs/staging-readiness-v1/GATES.md",
    "docs/staging-readiness-v1/REVIEWS.md",
    "docs/staging-readiness-v1/OWNER-DECISIONS.md",
    "docs/staging-readiness-v1/sql/provision-staging-roles.sql",
    "docs/staging-readiness-v1/freezes/MANIFEST-SPEC.md",
)
PREFIX = "docs/staging-readiness-v1/"
MANIFEST = "docs/staging-readiness-v1/freezes/FREEZE-v1.json"


def repo_root() -> Path:
    return Path(__file__).resolve().parents[1]


def lf_bytes(data: bytes) -> bytes:
    return data.replace(b"\r\n", b"\n").replace(b"\r", b"\n")


def sha256_file(path: Path) -> str:
    return hashlib.sha256(lf_bytes(path.read_bytes())).hexdigest()


def main() -> int:
    root = repo_root()
    write = "--write" in sys.argv
    manifest_path = root / MANIFEST
    if write:
        files = [{"path": p, "sha256": sha256_file(root / p)} for p in REQUIRED_PATHS]
        payload = {
            "packet_id": "STASHTAB-STAGING-READINESS-001",
            "packet_version": "1.0.0",
            "freeze_status": "FROZEN",
            "freeze_timestamp": "2026-08-26T00:05:00Z",
            "baseline_commit": "c3647a4eda37d355ed47f9e77ad667e4fda7930c",
            "algorithm": "SHA-256",
            "canonical_bytes": "git-lf-text-bytes",
            "human_vote": "APPROVE",
            "owner_decisions": "docs/staging-readiness-v1/OWNER-DECISIONS.md",
            "files": files,
        }
        manifest_path.parent.mkdir(parents=True, exist_ok=True)
        manifest_path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
        print(f"wrote {MANIFEST}")
        return 0

    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    missing = [k for k in REQUIRED_FIELDS if k not in manifest]
    if missing:
        raise SystemExit(f"missing fields: {missing}")
    if manifest["freeze_status"] != "FROZEN":
        raise SystemExit("freeze_status must be FROZEN")
    if manifest["canonical_bytes"] != "git-lf-text-bytes":
        raise SystemExit("canonical_bytes must be git-lf-text-bytes")
    listed = [e["path"] for e in manifest["files"]]
    if MANIFEST in listed:
        raise SystemExit("manifest must not hash itself")
    if set(listed) != set(REQUIRED_PATHS):
        raise SystemExit(f"path set mismatch: {set(listed) ^ set(REQUIRED_PATHS)}")
    errors = []
    for entry in manifest["files"]:
        path = entry["path"]
        if not path.startswith(PREFIX) or ".." in path:
            errors.append(f"bad path {path}")
            continue
        actual = sha256_file(root / path)
        if actual != entry["sha256"]:
            errors.append(f"{path} expected {entry['sha256']} got {actual}")
    if errors:
        raise SystemExit("\n".join(errors))
    print("staging-readiness freeze OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
