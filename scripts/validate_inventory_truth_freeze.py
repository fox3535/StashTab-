"""Validate an inventory-truth freeze manifest (non-self-referential).

`git-lf-text-bytes` hashes LF-normalized repository text so Windows checkouts
and Linux CI agree. Historical `exact-file-bytes-no-rewrite` manifests are
kept as Windows working-tree evidence and are not rewritten.
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
    "frozen_at",
    "approved_amendments",
    "previous_freeze",
    "algorithm",
    "canonical_bytes",
    "files",
)

REQUIRED_PATHS_1_2_0 = (
    "docs/inventory-truth-v1/CONTRACT.md",
    "docs/inventory-truth-v1/DESIGN.md",
    "docs/inventory-truth-v1/MIGRATION.md",
    "docs/inventory-truth-v1/TESTS.md",
    "docs/inventory-truth-v1/amendments/AMENDMENT-1.2.0.md",
)

ALLOWED_PREFIX = "docs/inventory-truth-v1/"
HEX64 = 64
CANONICAL_GIT_LF = "git-lf-text-bytes"
LEGACY_EXACT = "exact-file-bytes-no-rewrite"


def repo_root() -> Path:
    return Path(__file__).resolve().parents[1]


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def canonicalize_bytes(data: bytes, mode: str) -> bytes:
    if mode == CANONICAL_GIT_LF:
        return data.replace(b"\r\n", b"\n").replace(b"\r", b"\n")
    if mode == LEGACY_EXACT:
        return data
    raise ValueError(f"unsupported canonical_bytes: {mode}")


def hash_file(path: Path, mode: str) -> str:
    return sha256_bytes(canonicalize_bytes(path.read_bytes(), mode))


def canonical_mode(manifest: dict) -> str:
    mode = manifest["canonical_bytes"]
    if mode not in (CANONICAL_GIT_LF, LEGACY_EXACT):
        raise ValueError(
            "canonical_bytes must be git-lf-text-bytes or exact-file-bytes-no-rewrite"
        )
    return mode


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
    if not path.startswith(ALLOWED_PREFIX):
        raise ValueError(f"path outside freeze tree: {path}")
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
    mode = canonical_mode(manifest)
    if manifest["contract_id"] != "STASHTAB-INVENTORY-TRUTH-001":
        raise ValueError("contract_id mismatch")
    if not isinstance(manifest["approved_amendments"], list):
        raise ValueError("approved_amendments must be a list")
    if "AMENDMENT-1.2.0" not in manifest["approved_amendments"]:
        raise ValueError("approved_amendments must include AMENDMENT-1.2.0")

    previous = manifest["previous_freeze"]
    if not isinstance(previous, dict):
        raise ValueError("previous_freeze must be an object")
    if previous.get("contract_version") not in ("1.1.0", "1.0.0"):
        raise ValueError("previous_freeze.contract_version must preserve 1.1.0 lineage")

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

    if manifest["contract_version"] == "1.2.0":
        missing_required = [path for path in REQUIRED_PATHS_1_2_0 if path not in listed]
        if missing_required:
            raise ValueError(f"1.2.0 manifest missing required files: {missing_required}")

    for rel, expected in listed.items():
        target = (root / rel).resolve()
        try:
            target.relative_to(root.resolve())
        except ValueError as exc:
            raise ValueError(f"path escapes repository: {rel}") from exc
        if not target.is_file():
            raise ValueError(f"missing file: {rel}")
        actual = hash_file(target, mode)
        if actual != expected:
            raise ValueError(f"hash mismatch: {rel}")

    contract = (root / "docs/inventory-truth-v1/CONTRACT.md").read_text(encoding="utf-8")
    if f"**Version:** `{manifest['contract_version']}`" not in contract and (
        f"resulting version: **{manifest['contract_version']}**" not in contract.lower()
        and f"Resulting contract version: **{manifest['contract_version']}**" not in contract
    ):
        # Accept either header version or §9 resulting-version line.
        header_ok = f"**{manifest['contract_version']}**" in contract
        if not header_ok:
            raise ValueError("CONTRACT.md does not agree with manifest contract_version")
    if "AMENDMENT-1.2.0" not in contract:
        raise ValueError("CONTRACT.md does not name AMENDMENT-1.2.0")
    if "docs/inventory-truth-v1/freezes/FREEZE-1.2.0.json" not in contract:
        raise ValueError("CONTRACT.md must point at FREEZE-1.2.0.json and not self-hash")
    if "1.0.0" not in contract or "## 2." not in contract:
        raise ValueError("v1.0.0 freeze history missing from CONTRACT.md")
    if "## 8." not in contract or "1.1.0" not in contract:
        raise ValueError("v1.1.0 freeze history missing from CONTRACT.md")


def _write(path: Path, data: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)


def _manifest_for(root: Path, version: str, files: list[Path], extra: dict | None = None) -> dict:
    entries = []
    for path in files:
        rel = path.relative_to(root).as_posix()
        entries.append({"path": rel, "sha256": sha256_bytes(path.read_bytes())})
    payload = {
        "contract_id": "STASHTAB-INVENTORY-TRUTH-001",
        "contract_version": version,
        "freeze_status": "FROZEN",
        "frozen_at": "2026-08-24T00:00:00Z",
        "approved_amendments": ["AMENDMENT-1.1.0", "AMENDMENT-1.2.0"],
        "previous_freeze": {
            "contract_version": "1.1.0",
            "record": "docs/inventory-truth-v1/CONTRACT.md §8",
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
        contract = root / "docs/inventory-truth-v1/CONTRACT.md"
        design = root / "docs/inventory-truth-v1/DESIGN.md"
        migration = root / "docs/inventory-truth-v1/MIGRATION.md"
        tests = root / "docs/inventory-truth-v1/TESTS.md"
        amendment = root / "docs/inventory-truth-v1/amendments/AMENDMENT-1.2.0.md"
        freeze_dir = root / "docs/inventory-truth-v1/freezes"
        manifest_path = freeze_dir / "FREEZE-1.2.0.json"

        _write(
            contract,
            (
                "# Contract\n\n"
                "**Version:** `1.2.0`\n\n"
                "## 2. Files included in the freeze\n"
                "v1.0.0 historical table remains.\n\n"
                "## 8. Amendment 1.1.0 freeze record\n"
                "Version 1.1.0 remains.\n\n"
                "## 9. Amendment 1.2.0 freeze record\n"
                "Resulting contract version: **1.2.0**.\n"
                "Approved amendment: `AMENDMENT-1.2.0`.\n"
                "Freeze manifest: `docs/inventory-truth-v1/freezes/FREEZE-1.2.0.json`.\n"
                "This file does not store its own SHA-256.\n"
            ).encode("utf-8"),
        )
        _write(design, b"DESIGN body\n")
        _write(migration, b"MIGRATION body\n")
        _write(tests, b"TESTS body\n")
        _write(amendment, b"AMENDMENT-1.2.0 body\n")

        listed = [contract, design, migration, tests, amendment]
        payload = _manifest_for(root, "1.2.0", listed)
        _write(manifest_path, json.dumps(payload, indent=2).encode("utf-8"))
        validate(root, manifest_path)

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
        payload["contract_version"] = "1.2.0"
        payload["approved_amendments"] = ["AMENDMENT-1.1.0"]
        _write(manifest_path, json.dumps(payload, indent=2).encode("utf-8"))
        try:
            validate(root, manifest_path)
            raise SystemExit("expected amendment-id failure")
        except ValueError:
            pass
        payload["approved_amendments"] = ["AMENDMENT-1.1.0", "AMENDMENT-1.2.0"]

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

        payload["files"] = payload["files"][:-1]
        payload["previous_freeze"] = {
            "contract_version": "9.9.9",
            "record": "wrong-lineage",
        }
        _write(manifest_path, json.dumps(payload, indent=2).encode("utf-8"))
        try:
            validate(root, manifest_path)
            raise SystemExit("expected wrong-lineage failure")
        except ValueError:
            pass

        payload = _manifest_for(root, "1.2.0", listed)
        _write(manifest_path, json.dumps(payload, indent=2).encode("utf-8"))
        validate(root, manifest_path)

        lf_payload = _manifest_for(root, "1.2.0", listed)
        lf_payload["canonical_bytes"] = CANONICAL_GIT_LF
        lf_payload["files"] = [
            {
                "path": entry["path"],
                "sha256": hash_file(root / entry["path"], CANONICAL_GIT_LF),
            }
            for entry in lf_payload["files"]
        ]
        _write(manifest_path, json.dumps(lf_payload, indent=2).encode("utf-8"))
        for path in listed:
            lf = canonicalize_bytes(originals[path], CANONICAL_GIT_LF)
            path.write_bytes(lf.replace(b"\n", b"\r\n"))
        validate(root, manifest_path)
        listed[0].write_bytes(
            canonicalize_bytes(originals[listed[0]], CANONICAL_GIT_LF).replace(b"\n", b"\r\n")
            + b"X"
        )
        try:
            validate(root, manifest_path)
            raise SystemExit("expected git-lf content failure")
        except ValueError:
            pass
        for path in listed:
            path.write_bytes(originals[path])
        validate(root, manifest_path)


def negative_check(root: Path, manifest_path: Path) -> None:
    validate(root, manifest_path)
    manifest = load_manifest(manifest_path)
    originals: dict[Path, bytes] = {}
    backup = manifest_path.read_bytes()
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

        if canonical_mode(manifest) == CANONICAL_GIT_LF:
            for path, data in originals.items():
                lf = canonicalize_bytes(data, CANONICAL_GIT_LF)
                path.write_bytes(lf.replace(b"\n", b"\r\n"))
            validate(root, manifest_path)
            first = next(iter(originals))
            lf = canonicalize_bytes(originals[first], CANONICAL_GIT_LF)
            first.write_bytes(lf.replace(b"\n", b"\r\n") + b"X")
            try:
                validate(root, manifest_path)
            except ValueError:
                pass
            else:
                raise SystemExit("expected live content failure after CRLF plus extra byte")
            for path, data in originals.items():
                path.write_bytes(data)
            validate(root, manifest_path)

        payload = json.loads(backup)
        payload["previous_freeze"] = {
            "contract_version": "9.9.9",
            "record": "wrong-lineage",
        }
        manifest_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        try:
            validate(root, manifest_path)
            raise SystemExit("expected live wrong-lineage failure")
        except ValueError:
            pass
        payload = json.loads(backup)
        payload["files"] = list(payload["files"]) + [
            {"path": "../secret.txt", "sha256": "0" * 64}
        ]
        manifest_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        try:
            validate(root, manifest_path)
            raise SystemExit("expected live path-escape failure")
        except ValueError:
            pass
        manifest_path.write_bytes(backup)
        validate(root, manifest_path)
    finally:
        for path, data in originals.items():
            path.write_bytes(data)
        manifest_path.write_bytes(backup)


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", type=Path)
    parser.add_argument("--root", type=Path)
    parser.add_argument("--self-test", action="store_true")
    parser.add_argument("--negative-check", action="store_true")
    args = parser.parse_args(argv)
    if args.self_test:
        self_test()
        print("freeze-manifest self-test passed")
        return 0
    if not args.manifest:
        raise SystemExit("--manifest is required unless --self-test")
    root = args.root or repo_root()
    validate(root, args.manifest)
    print(f"freeze manifest ok: {args.manifest}")
    if args.negative_check:
        negative_check(root, args.manifest)
        print("negative checks passed; packet restored")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
