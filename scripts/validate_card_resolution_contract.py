from pathlib import Path
import re

root = Path(__file__).resolve().parents[1]
contract = root / "docs/card-resolution-workflow/CONTRACT.md"
amendment = root / "docs/card-resolution-workflow/AMENDMENT-1.1.0.md"
root_env = root / ".env.example"

required_contract = [
    "Local matching -> JustTCG validation -> Human review -> Verified database write",
    "Every tenant-owned record and query is scoped by `shop_id`.",
    "AI agreement is not proof of correctness.",
]
required_amendment = [
    "PROPOSED — IMPLEMENTATION DISABLED BY DEFAULT",
    "Web Push is disabled unless a complete server-side VAPID configuration exists.",
    "Required acceptance evidence",
]

for path, phrases in ((contract, required_contract), (amendment, required_amendment)):
    if not path.exists():
        raise SystemExit(f"Missing required workflow document: {path.relative_to(root)}")
    text = path.read_text(encoding="utf-8")
    missing = [phrase for phrase in phrases if phrase not in text]
    if missing:
        raise SystemExit(f"{path.name} is missing required clauses: {missing}")

if "VAPID_PRIVATE_KEY" in root_env.read_text(encoding="utf-8"):
    raise SystemExit("Root .env.example must not name VAPID_PRIVATE_KEY")

secret_pattern = re.compile(r"NEXT_PUBLIC_[A-Z0-9_]*VAPID[A-Z0-9_]*PRIVATE", re.IGNORECASE)
for path in [root / ".env.example", root / "services" / "api" / ".env.example", *root.rglob("*.ts"), *root.rglob("*.tsx"), *root.rglob("*.js")]:
    if not path.exists() or any(part in {".git", "node_modules", ".venv", "dist"} for part in path.parts):
        continue
    try:
        text = path.read_text(encoding="utf-8")
    except (UnicodeDecodeError, OSError):
        continue
    if secret_pattern.search(text):
        raise SystemExit(f"Forbidden public VAPID private-key name in {path.relative_to(root)}")

print("Card-resolution contract gates are present.")
