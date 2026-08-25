"""Decide whether a named CI job should run for files changed on a pull request.

Exit 0 always when used as a GitHub step. Prints ``name=true|false`` lines
for GitHub Actions outputs. A missing path match is an honest skip, not a
fabricated test pass.
"""

from __future__ import annotations

import argparse
import fnmatch
import os
import subprocess
import sys
from pathlib import Path

BACKEND = (
    "services/api/**",
    ".github/workflows/backend-notification-gates.yml",
    ".github/workflows/inventory-truth-gates.yml",
    ".github/workflows/card-resolution-gates.yml",
    "scripts/ci_pr_gate.py",
)

NOTIFICATION_CONTRACT = (
    "services/api/**",
    "docs/backend-notification-integration-v1/**",
    "docs/inventory-truth-v1/**",
    "scripts/validate_notification_freeze.py",
    "scripts/validate_inventory_truth_freeze.py",
    "scripts/validate_agent_context.py",
    ".gitattributes",
    ".github/workflows/backend-notification-gates.yml",
    "scripts/ci_pr_gate.py",
)

INVENTORY_PG = (
    "services/api/**",
    "docs/inventory-truth-v1/**",
    "scripts/validate_inventory_truth_freeze.py",
    ".gitattributes",
    ".github/workflows/inventory-truth-gates.yml",
    "scripts/ci_pr_gate.py",
)

CARD_BACKEND = (
    "services/api/**",
    "app/admin/**",
    "components/notification-settings.tsx",
    "lib/**",
    "public/sw.js",
    "docs/card-resolution-workflow/**",
    "docs/agent-context/**",
    "PLAN.md",
    "AGENTS.md",
    ".cursor/rules/card-resolution.mdc",
    "scripts/**",
    ".env.example",
    "services/api/.env.example",
    ".github/workflows/card-resolution-gates.yml",
)

FRONTEND = (
    "app/**",
    "components/**",
    "lib/**",
    "public/**",
    "package.json",
    "package-lock.json",
    "tsconfig.json",
    "next.config.ts",
    "next.config.js",
    "next.config.mjs",
    ".github/workflows/card-resolution-gates.yml",
)

GATES = {
    "sqlite": BACKEND,
    "postgres": BACKEND,
    "contract": NOTIFICATION_CONTRACT,
    "contract-and-backend": CARD_BACKEND,
    "frontend-build": FRONTEND,
    "pg-acceptance": INVENTORY_PG,
}


def path_matches(changed: str, pattern: str) -> bool:
    changed = changed.replace("\\", "/").lstrip("./")
    pattern = pattern.replace("\\", "/")
    if pattern.endswith("/**"):
        root = pattern[:-3].rstrip("/")
        return changed == root or changed.startswith(root + "/")
    return fnmatch.fnmatch(changed, pattern) or fnmatch.fnmatch(Path(changed).name, pattern)


def should_run(gate: str, files: list[str]) -> bool:
    patterns = GATES[gate]
    return any(path_matches(path, pattern) for path in files for pattern in patterns)


def changed_files(base: str, head: str) -> list[str]:
    result = subprocess.run(
        ["git", "diff", "--name-only", f"{base}...{head}"],
        check=True,
        capture_output=True,
        text=True,
    )
    return [line.strip().replace("\\", "/") for line in result.stdout.splitlines() if line.strip()]


def self_test() -> None:
    assert should_run("sqlite", ["services/api/app/main.py"])
    assert should_run("postgres", ["services/api/tests/test_notification_pg.py"])
    assert should_run("pg-acceptance", ["services/api/app/inventory_truth/core.py"])
    assert should_run("contract", ["docs/backend-notification-integration-v1/GATES.md"])
    assert should_run("contract-and-backend", ["docs/card-resolution-workflow/CONTRACT.md"])
    assert should_run("frontend-build", ["app/admin/dashboard/page.tsx"])
    assert should_run("frontend-build", ["package.json"])
    assert not should_run("sqlite", ["README.md"])
    assert not should_run("postgres", ["docs/product-strategy/VENDOR-OS-USP-ROADMAP.md"])
    assert not should_run("frontend-build", ["README.md"])
    assert not should_run("pg-acceptance", ["README.md"])
    mixed = ["services/api/app/main.py", "app/admin/dashboard/page.tsx"]
    assert should_run("sqlite", mixed)
    assert should_run("frontend-build", mixed)
    print("ci_pr_gate self-test passed")


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("gates", nargs="*")
    parser.add_argument("--self-test", action="store_true")
    parser.add_argument("--files", nargs="*")
    args = parser.parse_args(argv)
    if args.self_test:
        self_test()
        return 0
    gates = args.gates or list(GATES)
    unknown = [name for name in gates if name not in GATES]
    if unknown:
        raise SystemExit(f"unknown gates: {unknown}")
    if args.files is not None:
        files = args.files
    else:
        base = os.environ.get("BASE_SHA", "")
        head = os.environ.get("HEAD_SHA", "")
        if not base or not head:
            raise SystemExit("BASE_SHA and HEAD_SHA are required")
        files = changed_files(base, head)
    for gate in gates:
        print(f"{gate}={'true' if should_run(gate, files) else 'false'}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
