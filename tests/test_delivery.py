"""Publishing is simulated here. These tests never contact GitHub or push code."""
import json
from pathlib import Path
import subprocess
import sys

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import audit_tree
import publish_github as publish


def test_hygiene_flags_tokens_without_printing_them():
    token = "ghp_" + "x" * 36
    findings = audit_tree.problems("example.py", token.encode())
    assert findings and token not in json.dumps(findings)


@pytest.mark.parametrize("name", ["runtime/config.json", ".env", "backups/collection.sqlite3", "private.key"])
def test_hygiene_blocks_runtime_files(name):
    assert audit_tree.problems(name, b"{}")


def test_hygiene_allows_explicit_synthetic_url_fixture_only():
    fixture = ("https://" + "name:" + "password@" + "example.com/").encode()
    assert not audit_tree.problems("tests/test_models_matching.py", fixture)
    assert audit_tree.problems("ember/main.py", fixture)


def cp(stdout="", returncode=0):
    return subprocess.CompletedProcess([], returncode, stdout=stdout, stderr="")


@pytest.mark.parametrize("data", [
    {"full_name": publish.REPO, "private": None, "permissions": {"push": True}},
    {"full_name": "openGallo/lemien", "private": True, "permissions": {"push": True}},
    {"full_name": publish.REPO, "private": True, "permissions": {"push": False}},
])
def test_publisher_refuses_wrong_or_unverified_destination(monkeypatch, data):
    monkeypatch.setattr(publish, "command", lambda *a, **k: cp("HTTP/2.0 200 OK\n\n" + json.dumps(data)))
    with pytest.raises(RuntimeError):
        publish.inspect_repo()


@pytest.mark.parametrize("private", [True, False])
def test_publisher_preserves_owner_selected_repository_visibility(monkeypatch, private):
    data={"full_name":publish.REPO,"private":private,"permissions":{"push":True}}
    monkeypatch.setattr(publish,"command",lambda *a,**k:cp("HTTP/2.0 200 OK\n\n"+json.dumps(data)))
    assert publish.inspect_repo()["private"] is private


def test_publisher_targets_the_owner_named_poke_repository():
    assert publish.REPO=="openGallo/poke"
    assert all("openGallo/poke" in value for value in publish.ALLOWED_REMOTES)


@pytest.mark.parametrize("status", [403, 429, 500])
def test_publisher_does_not_create_after_an_access_or_server_error(monkeypatch, status):
    monkeypatch.setattr(publish, "command", lambda *a, **k: cp(f"HTTP/2.0 {status} Error\n", 1))
    with pytest.raises(RuntimeError):
        publish.inspect_repo()


def test_publisher_404_is_not_a_public_repository(monkeypatch):
    monkeypatch.setattr(publish, "command", lambda *a, **k: cp("HTTP/2.0 404 Not Found\n", 1))
    assert publish.inspect_repo() is None


def test_publisher_requires_exact_authenticated_owner(monkeypatch, capsys):
    calls = []
    monkeypatch.setattr(sys, "argv", ["publish_github.py", "--publish"])
    monkeypatch.setattr(publish.shutil, "which", lambda _: "/synthetic/executable")
    def command(*args, **kwargs):
        calls.append(args)
        return cp(json.dumps({"login": "someone-else"}))
    monkeypatch.setattr(publish, "command", command)
    assert publish.main() == 1
    assert calls == [("gh", "api", "user")]


def test_private_creation_push_and_commit_readback_mock(monkeypatch):
    calls = []
    lookups = 0
    sha = "a" * 40
    metadata = {"full_name": publish.REPO, "private": True, "permissions": {"push": True},
                "html_url": "https://github.com/" + publish.REPO}
    monkeypatch.setattr(sys, "argv", ["publish_github.py", "--publish"])
    monkeypatch.setattr(publish.shutil, "which", lambda _: "/synthetic/executable")
    monkeypatch.setattr(publish, "audit", lambda **kwargs: {"passed": True})
    def command(*args, **kwargs):
        nonlocal lookups
        calls.append(args)
        if args == ("gh", "api", "user"):
            return cp(json.dumps({"login": "openGallo"}))
        if args[:3] == ("gh", "api", "--include"):
            lookups += 1
            return cp("HTTP/2.0 404 Not Found\n", 1) if lookups == 1 else cp("HTTP/2.0 200 OK\n\n" + json.dumps(metadata))
        if args == ("git", "rev-parse", "--show-toplevel"):
            return cp(str(publish.ROOT))
        if args == ("git", "branch", "--show-current"):
            return cp("main\n")
        if args == ("git", "remote", "get-url", "origin"):
            return cp("", 1)
        if args == ("git", "rev-parse", "HEAD"):
            return cp(sha)
        if args == ("gh", "api", "repos/" + publish.REPO + "/commits/main"):
            return cp(json.dumps({"sha": sha}))
        return cp()
    monkeypatch.setattr(publish, "command", command)
    assert publish.main() == 0
    creates = [x for x in calls if x[:3] == ("gh", "repo", "create")]
    assert len(creates) == 1 and "--private" in creates[0]
    assert ("git", "push", "--set-upstream", "origin", "main") in calls
    assert all("--force" not in x and "--public" not in x for x in calls)
