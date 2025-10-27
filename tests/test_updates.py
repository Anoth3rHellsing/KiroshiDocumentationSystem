from datetime import datetime, timezone
from pathlib import Path
import sys

import pytest
import responses

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from case_documentation_app import (
    UpdateCheckResult,
    _discover_default_branch,
    _discover_remote_app_paths,
    _iter_remote_app_paths,
    check_for_updates,
)


@pytest.fixture(autouse=True)
def _clear_env(monkeypatch):
    monkeypatch.delenv("KIROSHI_UPDATE_REPO", raising=False)
    monkeypatch.delenv("KIROSHI_UPDATE_BRANCH", raising=False)
    monkeypatch.delenv("KIROSHI_UPDATE_APP_PATHS", raising=False)
    monkeypatch.delenv("KIROSHI_GITHUB_TOKEN", raising=False)


@responses.activate
def test_discover_default_branch_trims_whitespace():
    repo = "example/repo"
    url = f"https://api.github.com/repos/{repo}"
    responses.add(responses.GET, url, json={"default_branch": " main "}, status=200)

    branch = _discover_default_branch(repo)

    assert branch == "main"


@responses.activate
def test_discover_default_branch_handles_missing_metadata():
    repo = "example/repo"
    url = f"https://api.github.com/repos/{repo}"
    responses.add(responses.GET, url, json={"message": "Not Found"}, status=404)

    branch = _discover_default_branch(repo)

    assert branch is None


@responses.activate
def test_discover_remote_app_paths_yields_nested_entries():
    repo = "example/repo"
    branch = "main"
    url = f"https://api.github.com/repos/{repo}/git/trees/{branch}?recursive=1"
    responses.add(
        responses.GET,
        url,
        json={
            "tree": [
                {"path": "README.md", "type": "blob"},
                {"path": "nested/case_documentation_app.py", "type": "blob"},
                {"path": "tools/streamlit/case_documentation_app.py", "type": "blob"},
                {"path": "dir", "type": "tree"},
                "unexpected",
            ]
        },
        status=200,
    )

    paths = list(_discover_remote_app_paths(repo, branch))

    assert paths == [
        "nested/case_documentation_app.py",
        "tools/streamlit/case_documentation_app.py",
    ]


@responses.activate
def test_discover_remote_app_paths_handles_malformed_tree():
    repo = "example/repo"
    branch = "main"
    url = f"https://api.github.com/repos/{repo}/git/trees/{branch}?recursive=1"
    responses.add(responses.GET, url, json={"tree": {"not": "a list"}}, status=200)

    paths = list(_discover_remote_app_paths(repo, branch))

    assert paths == []


def test_iter_remote_app_paths_prefers_env_over_discovered(monkeypatch):
    monkeypatch.setenv(
        "KIROSHI_UPDATE_APP_PATHS",
        " custom/path , /leading/path ,,",
    )

    def fake_discover(repo: str, branch: str):
        yield "discovered/path"

    monkeypatch.setattr(
        "case_documentation_app._discover_remote_app_paths", fake_discover
    )

    paths = list(_iter_remote_app_paths("example/repo", "main"))

    assert paths[:3] == [
        "custom/path",
        "leading/path",
        "discovered/path",
    ]
    assert "case_documentation_app.py" in paths


@responses.activate
def test_check_for_updates_returns_commit_metadata(monkeypatch):
    repo = "example/repo"
    metadata_url = f"https://api.github.com/repos/{repo}"
    tree_url = f"https://api.github.com/repos/{repo}/git/trees/main?recursive=1"
    raw_url = f"https://raw.githubusercontent.com/{repo}/main/case_documentation_app.py"
    commits_url = f"https://api.github.com/repos/{repo}/commits/main"

    responses.add(
        responses.GET,
        metadata_url,
        json={"default_branch": " main "},
        status=200,
    )
    responses.add(
        responses.GET,
        tree_url,
        json={
            "tree": [
                {"path": "case_documentation_app.py", "type": "blob"},
            ]
        },
        status=200,
    )
    responses.add(
        responses.GET,
        raw_url,
        body="VERSION = \"RC 141026\"\n",
        status=200,
    )
    commit_date = datetime(2024, 1, 1, 12, 0, tzinfo=timezone.utc)
    responses.add(
        responses.GET,
        commits_url,
        json={
            "sha": "abc123",
            "commit": {
                "committer": {"date": commit_date.isoformat().replace("+00:00", "Z")}
            },
        },
        status=200,
    )

    monkeypatch.setenv("KIROSHI_UPDATE_REPO", repo)

    result = check_for_updates()

    assert isinstance(result, UpdateCheckResult)
    assert result.repo == repo
    assert result.branch == "main"
    assert result.latest_version == "RC 141026"
    assert result.has_update is True
    assert result.latest_commit == "abc123"
    assert result.latest_published == commit_date.astimezone().strftime(
        "%Y-%m-%d %H:%M %Z"
    )
    expected_url = f"https://codeload.github.com/{repo}/zip/refs/heads/main"
    assert result.download_url == expected_url


@responses.activate
def test_check_for_updates_reports_inaccessible_repository(monkeypatch):
    repo = "missing/repo"
    metadata_url = f"https://api.github.com/repos/{repo}"
    tree_url = f"https://api.github.com/repos/{repo}/git/trees/main?recursive=1"
    branch_url = f"https://api.github.com/repos/{repo}/branches/main"

    responses.add(responses.GET, metadata_url, json={"message": "Not Found"}, status=404)
    responses.add(responses.GET, tree_url, json={"message": "Not Found"}, status=404)
    for candidate in [
        "case_documentation_app.py",
        "KiroshiDocumentationSystem/case_documentation_app.py",
        "src/case_documentation_app.py",
        "app/case_documentation_app.py",
    ]:
        responses.add(
            responses.GET,
            f"https://raw.githubusercontent.com/{repo}/main/{candidate}",
            status=404,
        )
    responses.add(responses.GET, branch_url, json={"message": "Not Found"}, status=404)

    monkeypatch.setenv("KIROSHI_UPDATE_REPO", repo)

    result = check_for_updates()

    assert isinstance(result, UpdateCheckResult)
    assert result.error
    assert "repository" in result.error
    assert repo in result.error


@responses.activate
def test_check_for_updates_reports_missing_branch(monkeypatch):
    repo = "example/repo"
    branch = "staging"
    tree_url = f"https://api.github.com/repos/{repo}/git/trees/{branch}?recursive=1"
    branch_url = f"https://api.github.com/repos/{repo}/branches/{branch}"

    responses.add(responses.GET, tree_url, json={"message": "Not Found"}, status=404)
    for candidate in [
        "case_documentation_app.py",
        "KiroshiDocumentationSystem/case_documentation_app.py",
        "src/case_documentation_app.py",
        "app/case_documentation_app.py",
    ]:
        responses.add(
            responses.GET,
            f"https://raw.githubusercontent.com/{repo}/{branch}/{candidate}",
            status=404,
        )
    responses.add(
        responses.GET,
        branch_url,
        json={"message": "Branch not found"},
        status=404,
    )

    monkeypatch.setenv("KIROSHI_UPDATE_REPO", repo)
    monkeypatch.setenv("KIROSHI_UPDATE_BRANCH", branch)

    result = check_for_updates()

    assert isinstance(result, UpdateCheckResult)
    assert result.error
    assert branch in result.error

