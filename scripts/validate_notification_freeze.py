"""Validate the backend-notification AMENDMENT-1.1.1 freeze manifest.

Hashes exact file bytes. The manifest must not list or hash itself.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import posixpath
import sys
import tempfile
from pathlib import Path

REQUIRED_FIELDS = (
    "contract_id",
    "contract_version",
    "freeze_status",
    "freeze_timestamp",
    "approved_amendments",
    "previous_freeze",
    "algorithm",
    "canonical_bytes",
    "files",
)

REQUIRED_PATHS = (
    "docs/backend-notification-integration-v1/AMENDMENT-1.1.1.md",
    "docs/backend-notification-integration-v1/DIRECTIVE.md",
    "docs/backend-notification-integration-v1/FREEZE-CHECK.md",
    "docs/card-resolution-workflow/AMENDMENT-1.1.0.md",
)

ALLOWED_PREFIXES = (
    "docs/backend-notification-integration-v1/",
    "docs/card-resolution-workflow/",
)

MANIFEST_NAME = "FREEZE-1.1.1.json"
HEX64 = 64


def repo_root() -> Path:
    return Path(__file__).resolve().parents[1]


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def normalize_relpath(raw: str) -> str:
    if not isinstance(raw, str) or not raw.strip():
        raise ValueError("empty path")
    path = raw.replace("\\", "/").strip()
    if path.startswith("/") or (len(path) >= 2 and path[1] == ":"):
        raise ValueError(f"absolute path rejected: {raw}")
    if path.startswith("./"):
        path = path[2:]
    parts = posixpath.normpath(path).split("/")
    if ".." in parts or parts[:1] == ["."]:
        raise ValueError(f"path escapes repository: {raw}")
    if not any(path.startswith(prefix) for prefix in ALLOWED_PREFIXES):
        raise ValueError(f"path outside freeze tree: {path}")
    if path.endswith(MANIFEST_NAME) or path.endswith("freezes/" + MANIFEST_NAME):
        raise ValueError("manifest must not hash itself")
    return path


def load_manifest(path: Path) -> dict:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("manifest must be a JSON object")
    missing = [key for key in REQUIRED_FIELDS if key not in payload]
    if missing:
        raise ValueError(f"manifest missing fields: {missing}")
    return payload


def validate(root: Path, manifest_path: Path) -> None:
    manifest = load_manifest(manifest_path)
    manifest_rel = manifest_path.resolve().relative_to(root.resolve()).as_posix()

    if manifest["algorithm"] != "SHA-256":
        raise ValueError("algorithm must be SHA-256")
    if manifest["canonical_bytes"] != "exact-file-bytes-no-rewrite":
        raise ValueError("canonical_bytes must be exact-file-bytes-no-rewrite")
    if manifest["contract_id"] != "STASHTAB-CARD-RESOLUTION-001":
        raise ValueError("contract_id mismatch")
    if manifest["contract_version"] != "1.1.1":
        raise ValueError("contract_version mismatch")
    if manifest["freeze_status"] != "FROZEN":
        raise ValueError("freeze_status must be FROZEN")
    if not isinstance(manifest["approved_amendments"], list):
        raise ValueError("approved_amendments must be a list")
    if "AMENDMENT-1.1.1" not in manifest["approved_amendments"]:
        raise ValueError("approved_amendments must include AMENDMENT-1.1.1")
    if "AMENDMENT-1.1.0" not in manifest["approved_amendments"]:
        raise ValueError("approved_amendments must record unchanged AMENDMENT-1.1.0")

    previous = manifest["previous_freeze"]
    if not isinstance(previous, dict):
        raise ValueError("previous_freeze must be an object")
    if previous.get("contract_version") != "1.0.0":
        raise ValueError("previous_freeze.contract_version must remain parent 1.0.0")

    files = manifest["files"]
    if not isinstance(files, list) or not files:
        raise ValueError("files must be a non-empty list")

    seen: set[str] = set()
    listed: dict[str, str] = {}
    for entry in files:
        if not isinstance(entry, dict) or "path" not in entry or "sha256" not in entry:
            raise ValueError("each files[] entry needs path and sha256")
        rel = normalize_relpath(entry["path"])
        if rel == manifest_rel:
            raise ValueError("manifest must not hash itself")
        if rel in seen:
            raise ValueError(f"duplicate path: {rel}")
        digest = str(entry["sha256"]).lower()
        if len(digest) != HEX64 or any(ch not in "0123456789abcdef" for ch in digest):
            raise ValueError(f"invalid sha256 for {rel}")
        seen.add(rel)
        listed[rel] = digest

    missing_required = [path for path in REQUIRED_PATHS if path not in listed]
    if missing_required:
        raise ValueError(f"manifest missing required files: {missing_required}")

    for rel, expected in listed.items():
        target = (root / rel).resolve()
        try:
            target.relative_to(root.resolve())
        except ValueError as exc:
            raise ValueError(f"path escapes repository: {rel}") from exc
        if not target.is_file():
            raise ValueError(f"missing file: {rel}")
        actual = sha256_bytes(target.read_bytes())
        if actual != expected:
            raise ValueError(f"hash mismatch: {rel}")

    amendment = (root / "docs/backend-notification-integration-v1/AMENDMENT-1.1.1.md").read_text(
        encoding="utf-8"
    )
    if "AMENDMENT-1.1.1" not in amendment:
        raise ValueError("AMENDMENT-1.1.1.md does not name AMENDMENT-1.1.1")
    if "APPROVED AND FROZEN" not in amendment:
        raise ValueError("AMENDMENT-1.1.1.md is not marked APPROVED AND FROZEN")
    if "docs/backend-notification-integration-v1/freezes/FREEZE-1.1.1.json" not in amendment:
        raise ValueError("AMENDMENT-1.1.1.md must point at FREEZE-1.1.1.json and not self-hash")
    own_hash = listed["docs/backend-notification-integration-v1/AMENDMENT-1.1.1.md"]
    if own_hash in amendment:
        raise ValueError("AMENDMENT-1.1.1.md must not contain its own SHA-256")

    policy = (root / "docs/card-resolution-workflow/AMENDMENT-1.1.0.md").read_text(
        encoding="utf-8"
    )
    if "Proposed Contract Amendment 1.1.0" not in policy:
        raise ValueError("AMENDMENT-1.1.0.md was unexpectedly rewritten")

    parent = (root / "docs/card-resolution-workflow/CONTRACT.md").read_text(encoding="utf-8")
    if "**Version:** `1.0.0`" not in parent:
        raise ValueError("parent CONTRACT.md version must remain 1.0.0")


def compatibility(root: Path) -> None:
    amendment = (root / "docs/backend-notification-integration-v1/AMENDMENT-1.1.1.md").read_text(
        encoding="utf-8"
    )
    identity = (root / "docs/fail-closed-shop-identity-v1/DIRECTIVE.md").read_text(
        encoding="utf-8"
    )
    inventory = (root / "docs/inventory-truth-v1/CONTRACT.md").read_text(encoding="utf-8")
    if "JWT" not in amendment or "shop membership" not in amendment.lower() and "membership" not in amendment:
        raise ValueError("notification amendment missing JWT/membership identity rule")
    if "X-Shop-Id" not in identity or "never enough" not in identity:
        raise ValueError("identity directive no longer states headers are untrusted")
    if "1.2.0" not in inventory:
        raise ValueError("inventory-truth contract is not 1.2.0")
    if "create_all" not in amendment or "inventory_exception" not in amendment:
        raise ValueError("notification amendment missing inventory-truth isolation language")


def _write(path: Path, data: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)


def _manifest_for(root: Path, files: list[Path], extra: dict | None = None) -> dict:
    entries = []
    for path in files:
        rel = path.relative_to(root).as_posix()
        entries.append({"path": rel, "sha256": sha256_bytes(path.read_bytes())})
    payload = {
        "contract_id": "STASHTAB-CARD-RESOLUTION-001",
        "contract_version": "1.1.1",
        "freeze_status": "FROZEN",
        "freeze_timestamp": "2026-08-24T15:30:00Z",
        "approved_amendments": ["AMENDMENT-1.1.0", "AMENDMENT-1.1.1"],
        "previous_freeze": {
            "contract_version": "1.0.0",
            "record": "docs/card-resolution-workflow/CONTRACT.md and AMENDMENT-1.1.0.md",
        },
        "algorithm": "SHA-256",
        "canonical_bytes": "exact-file-bytes-no-rewrite",
        "files": entries,
    }
    if extra:
        payload.update(extra)
    return payload


def self_test() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        amendment = root / "docs/backend-notification-integration-v1/AMENDMENT-1.1.1.md"
        directive = root / "docs/backend-notification-integration-v1/DIRECTIVE.md"
        freeze_check = root / "docs/backend-notification-integration-v1/FREEZE-CHECK.md"
        policy = root / "docs/card-resolution-workflow/AMENDMENT-1.1.0.md"
        contract = root / "docs/card-resolution-workflow/CONTRACT.md"
        identity = root / "docs/fail-closed-shop-identity-v1/DIRECTIVE.md"
        inventory = root / "docs/inventory-truth-v1/CONTRACT.md"
        manifest_path = root / "docs/backend-notification-integration-v1/freezes/FREEZE-1.1.1.json"

        _write(
            amendment,
            (
                "# AMENDMENT-1.1.1\n"
                "Status: APPROVED AND FROZEN\n"
                "JWT + shop membership\n"
                "create_all must not own tables\n"
                "inventory_exception is source of truth\n"
                "Freeze: docs/backend-notification-integration-v1/freezes/FREEZE-1.1.1.json\n"
            ).encode("utf-8"),
        )
        _write(directive, b"DIRECTIVE\n")
        _write(freeze_check, b"FREEZE-CHECK\n")
        _write(policy, b"# Proposed Contract Amendment 1.1.0 - Human-Intervention Notifications\n")
        _write(contract, b"**Version:** `1.0.0`\n")
        _write(
            identity,
            b"Caller-supplied `X-Shop-Id` and `X-Clerk-User-Id` are never enough in production.\n",
        )
        _write(inventory, b"**Version:** `1.0.0` -> `1.1.0` -> `1.2.0`\n")

        listed = [amendment, directive, freeze_check, policy]
        payload = _manifest_for(root, listed)
        _write(manifest_path, json.dumps(payload, indent=2).encode("utf-8") + b"\n")
        validate(root, manifest_path)
        compatibility(root)

        originals = {path: path.read_bytes() for path in listed}
        for path in listed:
            path.write_bytes(originals[path] + b"X")
            try:
                validate(root, manifest_path)
            except ValueError:
                pass
            else:
                raise SystemExit(f"expected hash failure for {path.name}")
            path.write_bytes(originals[path])
        validate(root, manifest_path)

        payload["contract_version"] = "9.9.9"
        _write(manifest_path, json.dumps(payload, indent=2).encode("utf-8"))
        try:
            validate(root, manifest_path)
            raise SystemExit("expected version mismatch failure")
        except ValueError:
            pass
        payload["contract_version"] = "1.1.1"
        payload["approved_amendments"] = ["AMENDMENT-1.1.0"]
        _write(manifest_path, json.dumps(payload, indent=2).encode("utf-8"))
        try:
            validate(root, manifest_path)
            raise SystemExit("expected amendment-id failure")
        except ValueError:
            pass
        payload["approved_amendments"] = ["AMENDMENT-1.1.0", "AMENDMENT-1.1.1"]

        payload["files"] = list(payload["files"]) + [
            {"path": "../secret.txt", "sha256": "0" * 64}
        ]
        _write(manifest_path, json.dumps(payload, indent=2).encode("utf-8"))
        try:
            validate(root, manifest_path)
            raise SystemExit("expected path-escape failure")
        except ValueError:
            pass
        payload["files"] = payload["files"][:-1]
        payload["files"] = list(payload["files"]) + [
            {"path": "C:/Windows/system32/cmd.exe", "sha256": "0" * 64}
        ]
        _write(manifest_path, json.dumps(payload, indent=2).encode("utf-8"))
        try:
            validate(root, manifest_path)
            raise SystemExit("expected absolute-path failure")
        except ValueError:
            pass
        payload = _manifest_for(root, listed)
        payload["files"] = list(payload["files"]) + [payload["files"][0]]
        _write(manifest_path, json.dumps(payload, indent=2).encode("utf-8"))
        try:
            validate(root, manifest_path)
            raise SystemExit("expected duplicate-path failure")
        except ValueError:
            pass
        payload = _manifest_for(root, listed)
        payload["files"] = [entry for entry in payload["files"] if "AMENDMENT-1.1.1" not in entry["path"]]
        _write(manifest_path, json.dumps(payload, indent=2).encode("utf-8"))
        try:
            validate(root, manifest_path)
            raise SystemExit("expected missing-required failure")
        except ValueError:
            pass

        payload = _manifest_for(root, listed)
        _write(manifest_path, json.dumps(payload, indent=2).encode("utf-8") + b"\n")
        validate(root, manifest_path)


def negative_check(root: Path, manifest_path: Path) -> None:
    validate(root, manifest_path)
    compatibility(root)
    manifest = load_manifest(manifest_path)
    originals: dict[Path, bytes] = {}
    try:
        for entry in manifest["files"]:
            path = root / entry["path"]
            originals[path] = path.read_bytes()
            path.write_bytes(originals[path] + b"X")
            try:
                validate(root, manifest_path)
            except ValueError:
                pass
            else:
                raise SystemExit(f"expected live hash failure for {entry['path']}")
            path.write_bytes(originals[path])
        validate(root, manifest_path)

        backup = manifest_path.read_bytes()
        payload = json.loads(backup)
        payload["contract_version"] = "0.0.0"
        manifest_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        try:
            validate(root, manifest_path)
            raise SystemExit("expected live version mismatch failure")
        except ValueError:
            pass
        payload["contract_version"] = "1.1.1"
        payload["approved_amendments"] = ["AMENDMENT-1.1.0"]
        manifest_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        try:
            validate(root, manifest_path)
            raise SystemExit("expected live amendment mismatch failure")
        except ValueError:
            pass
        payload["approved_amendments"] = ["AMENDMENT-1.1.0", "AMENDMENT-1.1.1"]
        payload["files"] = list(payload["files"]) + [
            {"path": "../etc/passwd", "sha256": "0" * 64}
        ]
        manifest_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        try:
            validate(root, manifest_path)
            raise SystemExit("expected live path-escape failure")
        except ValueError:
            pass
        payload["files"] = payload["files"][:-1] + [
            {"path": "C:/Windows/system32/cmd.exe", "sha256": "0" * 64}
        ]
        manifest_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        try:
            validate(root, manifest_path)
            raise SystemExit("expected live absolute-path failure")
        except ValueError:
            pass
        payload = json.loads(backup)
        payload["files"] = list(payload["files"]) + [payload["files"][0]]
        manifest_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        try:
            validate(root, manifest_path)
            raise SystemExit("expected live duplicate failure")
        except ValueError:
            pass
        payload = json.loads(backup)
        payload["files"] = payload["files"][1:]
        manifest_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        try:
            validate(root, manifest_path)
            raise SystemExit("expected live missing-entry failure")
        except ValueError:
            pass
        manifest_path.write_bytes(backup)
        validate(root, manifest_path)
        compatibility(root)
    finally:
        for path, data in originals.items():
            path.write_bytes(data)
        # restore manifest if tests left it mutated
        if "backup" in locals():
            manifest_path.write_bytes(backup)


def write_manifest(root: Path, manifest_path: Path) -> None:
    files = [root / path for path in REQUIRED_PATHS]
    payload = _manifest_for(root, files)
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    manifest_path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", type=Path)
    parser.add_argument("--root", type=Path)
    parser.add_argument("--self-test", action="store_true")
    parser.add_argument("--negative-check", action="store_true")
    parser.add_argument("--write-manifest", action="store_true")
    args = parser.parse_args(argv)
    root = args.root or repo_root()
    if args.self_test:
        self_test()
        print("notification freeze-manifest self-test passed")
        return 0
    manifest_path = args.manifest or (
        root / "docs/backend-notification-integration-v1/freezes/FREEZE-1.1.1.json"
    )
    if args.write_manifest:
        write_manifest(root, manifest_path)
        print(f"wrote {manifest_path}")
    validate(root, manifest_path)
    compatibility(root)
    print(f"freeze manifest ok: {manifest_path}")
    print("identity and inventory-truth 1.2.0 compatibility: GREEN")
    if args.negative_check:
        negative_check(root, manifest_path)
        print("negative checks passed; packet restored")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
