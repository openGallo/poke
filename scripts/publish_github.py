"""Publish reviewed Ember source using the user's already authenticated GitHub CLI.
No tokens are requested, read, printed, or embedded by this script. No deployment.
Run without --publish for read-only preflight. Requires git, gh, and gh auth setup-git.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import shutil
import subprocess
import sys

from audit_tree import audit

ROOT = Path(__file__).resolve().parents[1]
OWNER = "openGallo"
REPO = "openGallo/poke"
REMOTE = "https://github.com/openGallo/poke.git"
ALLOWED_REMOTES = {REMOTE, REMOTE.removesuffix(".git"), "git@github.com:openGallo/poke.git"}


def command(*args: str, optional: bool = False) -> subprocess.CompletedProcess:
    result = subprocess.run(args, cwd=ROOT, text=True, capture_output=True, check=False)
    if result.returncode and not optional:
        # Git/CLI errors can contain URLs or environment-derived details. Fail without dumping them.
        raise RuntimeError(f"{args[0]} {args[1]} failed (exit {result.returncode}). Check your local account/permissions; no force push was attempted.")
    return result


def inspect_repo() -> dict | None:
    result = command("gh", "api", "--include", "repos/" + REPO, optional=True)
    if result.returncode:
        if any(line.startswith("HTTP/") and " 404 " in line for line in result.stdout.splitlines()):
            return None
        raise RuntimeError("Cannot verify repository visibility. Check GitHub access; refusing to publish.")
    # --include emits response headers followed by the JSON body.
    body = result.stdout[result.stdout.find("{"):]
    value = json.loads(body)
    if value.get("full_name", "").lower() != REPO.lower() or not isinstance(value.get("private"), bool):
        raise RuntimeError("Destination must be the exact owner-selected repository with verified visibility. Refusing to publish elsewhere or change visibility.")
    if not value.get("permissions", {}).get("push"):
        raise RuntimeError("The authenticated CLI lacks push permission to the selected Ember repository.")
    return value


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--publish", action="store_true", help="Create private repository if absent and push clean main")
    parser.add_argument("--initialize", action="store_true", help="Initialize an extracted source ZIP as a new local Git repository")
    args = parser.parse_args()
    try:
        if not shutil.which("git") or not shutil.which("gh"):
            raise RuntimeError("Install Git and the official GitHub CLI first; then sign in with gh auth login outside this script.")
        account = json.loads(command("gh", "api", "user").stdout)
        if account.get("login") != OWNER:
            raise RuntimeError("The GitHub CLI must be authenticated as openGallo. No changes made.")
        result = audit()
        if not result["passed"]:
            print(json.dumps(result, indent=2))
            raise RuntimeError("Source hygiene check failed. Resolve findings before publishing.")
        top = command("git", "rev-parse", "--show-toplevel", optional=True)
        if top.returncode:
            if not (args.initialize and args.publish):
                raise RuntimeError("Source ZIP has no Git history. Use --initialize --publish to initialize and publish this directory only.")
            command("git", "init", "--initial-branch=main")
            bundle=ROOT/"ember-history.bundle"
            if bundle.is_file():
                command("git", "fetch", str(bundle), "main")
                command("git", "reset", "--mixed", "FETCH_HEAD")
            else:
                command("git", "add", "--all")
                author = account.get("name") or OWNER
                email = f"{account['id']}+{OWNER}@users.noreply.github.com"
                command("git", "-c", "user.name=" + author, "-c", "user.email=" + email,
                        "commit", "-m", "Import reviewed Ember reconstruction")
        elif Path(top.stdout.strip()).resolve() != ROOT:
            raise RuntimeError("Directory belongs to another Git repository. Refusing to modify unrelated work.")
        if command("git", "status", "--porcelain").stdout.strip():
            raise RuntimeError("Working tree is dirty. Review and commit intended changes before publishing.")
        if command("git", "branch", "--show-current").stdout.strip() != "main":
            raise RuntimeError("Initial publishing helper expects main. Use the documented branch/PR workflow for subsequent changes.")
        history = audit(history=True)
        if not history["passed"]:
            print(json.dumps(history, indent=2))
            raise RuntimeError("Git history hygiene check failed.")
        repo = inspect_repo()
        if not args.publish:
            print("Preflight passed. Existing repository visibility is preserved; an absent repository is created private. No push or deployment occurred.")
            return 0
        if repo is None:
            command("gh", "repo", "create", REPO, "--private", "--description",
                    "Ember: private, evidence-led Charmander PSA 10 collection binder")
            repo = inspect_repo()
            if repo is None:
                raise RuntimeError("Repository creation was not verified. No push attempted.")
        configured = command("git", "remote", "get-url", "origin", optional=True)
        if configured.returncode:
            command("git", "remote", "add", "origin", REMOTE)
        elif configured.stdout.strip() not in ALLOWED_REMOTES:
            raise RuntimeError("Origin is not the exact Ember destination. Refusing to overwrite it.")
        remote_refs = command("git", "ls-remote", "--heads", "origin").stdout.strip()
        if remote_refs:
            main = next((line.split()[0] for line in remote_refs.splitlines() if line.endswith("refs/heads/main")), None)
            if main is None:
                raise RuntimeError("Remote already contains another branch/history. Review it manually; nothing overwritten.")
            command("git", "fetch", "origin", "main")
            if command("git", "merge-base", "--is-ancestor", "origin/main", "HEAD", optional=True).returncode:
                raise RuntimeError("Remote main has unrelated or diverging history. Refusing to force-push.")
        command("git", "push", "--set-upstream", "origin", "main")
        repo = inspect_repo()
        local_sha = command("git", "rev-parse", "HEAD").stdout.strip()
        remote_sha = json.loads(command("gh", "api", "repos/" + REPO + "/commits/main").stdout)["sha"]
        if local_sha != remote_sha:
            raise RuntimeError("Push returned but GitHub commit readback differs. Publication not verified.")
        print(json.dumps({"repository": repo["html_url"], "private": repo["private"], "branch": "main",
                          "commit": remote_sha, "deployment": "not performed by this script"}, indent=2))
        return 0
    except (RuntimeError, ValueError, OSError, KeyError) as error:
        print("STOP: " + str(error), file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
