from pathlib import Path

root = Path(__file__).resolve().parents[1]
context = root / "docs/agent-context"
required = [
    "INDEX.md", "CURRENT.md", "DECISIONS.md", "LESSONS.md", "BACKLOG.md",
    "roles/implementer.md", "roles/architecture.md", "roles/security.md",
    "roles/data-integrity.md", "roles/adversarial.md",
]

for relative in required:
    path = context / relative
    if not path.exists():
        raise SystemExit(f"Missing agent context file: {path.relative_to(root)}")

limits = {"CURRENT.md": 150}
for relative, maximum in limits.items():
    count = len((context / relative).read_text(encoding="utf-8").splitlines())
    if count > maximum:
        raise SystemExit(f"{relative} exceeds its {maximum}-line context budget")

for path in (context / "roles").glob("*.md"):
    if len(path.read_text(encoding="utf-8").splitlines()) > 200:
        raise SystemExit(f"{path.name} exceeds its 200-line context budget")

current = (context / "CURRENT.md").read_text(encoding="utf-8")
if "**Contract:**" not in current or "## Active gates" not in current:
    raise SystemExit("CURRENT.md must identify the contract and active gates")

print("Agent context packet is complete and within budget.")
