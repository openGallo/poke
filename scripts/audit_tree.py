"""Inspect the outgoing source and optional Git history; never print matched secrets.
This is a bounded hygiene check, not a penetration test or an advisory database.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import re
import subprocess
import sys
import json

ROOT = Path(__file__).resolve().parents[1]
ASSET_MANIFEST_PATH=ROOT/"ember/data/reference-assets.json"
ASSET_MANIFEST=json.loads(ASSET_MANIFEST_PATH.read_text()) if ASSET_MANIFEST_PATH.exists() else {}
SKIP_DIRS = {".git", ".venv", "venv", "runtime", "__pycache__", ".pytest_cache", ".mypy_cache",
             ".ruff_cache", "node_modules", "htmlcov", "dist", "build", "test-results", "playwright-report"}
SKIP_NAMES = {".coverage", ".DS_Store"}
PATTERNS = {
    "GitHub credential": re.compile(r"\b(?:gh[pousr]_[A-Za-z0-9]{30,}|github_pat_[A-Za-z0-9_]{40,})"),
    "OpenAI-style credential": re.compile(r"\bsk-(?:proj-|svcacct-)?[A-Za-z0-9_-]{35,}"),
    "AWS access identifier": re.compile(r"\b(?:AKIA|ASIA)[A-Z0-9]{16}\b"),
    "Private key": re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH |DSA )?PRIVATE KEY-----"),
    "Password hash": re.compile(r"\$argon2(?:id|i|d)\$v=\d+\$[^\s\"']{30,}"),
    "Embedded URL credential": re.compile(r"https?://[^\s/:@]+:[^\s/@]{6,}@"),
}
FORBIDDEN = {".db", ".sqlite", ".sqlite3", ".pem", ".key", ".p12", ".pfx"}


def source_files() -> list[Path]:
    return sorted(p for p in ROOT.rglob("*") if p.is_file()
                  and not any(part in SKIP_DIRS or part.endswith(".egg-info") for part in p.relative_to(ROOT).parts)
                  and p.name not in SKIP_NAMES and p.suffix not in {".pyc", ".log", ".zip", ".bundle"})


def problems(name: str, data: bytes) -> list[dict]:
    path = Path(name)
    found = []
    if "runtime" in path.parts or path.suffix in FORBIDDEN or (path.name.startswith(".env") and path.name != ".env.example"):
        found.append({"file": name, "problem": "Runtime/credential file must not be published"})
    try:
        text = data.decode("utf-8")
    except UnicodeDecodeError:
        reference=ASSET_MANIFEST.get(path.name) if name.startswith("ember/static/cards/") else None
        approved_reference=bool(reference and reference.get("reference_only") and reference.get("source","").startswith("https://") and reference.get("sha256")==hashlib.sha256(data).hexdigest())
        if not approved_reference and not (name.startswith("docs/verification/") and path.suffix == ".png"):
            found.append({"file": name, "problem": "Unexpected binary file: review before publication"})
        return found
    # One explicit, deliberately invalid example-host URL is a negative validation fixture.
    # Do not exempt all tests: real credentials in test files still fail this scan.
    if name in {"tests/test_models_matching.py", "docs/verification/v2.2/pytest.xml"}:
        fixture = "https://" + "name:" + "password@" + "example.com/"
        text = text.replace(fixture, "https://example.com/")
    for label, pattern in PATTERNS.items():
        if pattern.search(text):
            found.append({"file": name, "problem": label + " pattern found"})
    return found


def git(*args: str) -> subprocess.CompletedProcess:
    return subprocess.run(["git", *args], cwd=ROOT, capture_output=True, check=False)


def audit(history: bool = False) -> dict:
    paths = source_files()
    findings = [finding for p in paths for finding in problems(str(p.relative_to(ROOT)), p.read_bytes())]
    objects = 0
    if history:
        listed = git("rev-list", "--objects", "--all")
        if listed.returncode:
            findings.append({"file": ".git", "problem": "Requested history scan could not be performed"})
        else:
            for line in listed.stdout.decode().splitlines():
                parts = line.split(" ", 1)
                if len(parts) < 2:
                    continue
                sha, name = parts
                if git("cat-file", "-t", sha).stdout.strip() != b"blob":
                    continue
                objects += 1
                findings.extend({**x, "object": sha} for x in problems(name, git("cat-file", "blob", sha).stdout))
    return {"scope": "Outgoing source and known credential patterns; not a complete security audit",
            "files_checked": len(paths), "history_objects_checked": objects,
            "passed": not findings, "findings": findings}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--history", action="store_true")
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    result = audit(args.history)
    if args.output:
        args.output.write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps(result, indent=2))
    return 0 if result["passed"] else 1


if __name__ == "__main__":
    sys.exit(main())
