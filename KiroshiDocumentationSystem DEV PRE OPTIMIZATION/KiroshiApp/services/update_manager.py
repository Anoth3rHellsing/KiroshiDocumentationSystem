# -*- coding: utf-8 -*-
import os
import re
import logging
import requests
from typing import Iterator
from datetime import datetime

from KiroshiApp.constants import (
    DEFAULT_UPDATE_REPO, DEFAULT_UPDATE_BRANCH, VERSION,
    GITHUB_TOKEN_ENV_VAR, UPDATE_CHECK_TIMEOUT
)
from KiroshiApp.models import UpdateCheckResult

def _get_github_headers() -> dict[str, str]:
    token = os.environ.get(GITHUB_TOKEN_ENV_VAR)
    if token:
        return {
            "Authorization": f"Bearer {token}",
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
        }
    return {
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
    }

def _discover_default_branch(repo: str) -> str | None:
    url = f"https://api.github.com/repos/{repo}"
    try:
        response = requests.get(url, headers=_get_github_headers(), timeout=UPDATE_CHECK_TIMEOUT)
        if response.status_code == 200:
            data = response.json()
            branch = data.get("default_branch")
            if branch:
                return str(branch).strip()
    except Exception as exc:
        logging.debug("Failed to discover default branch for %s: %s", repo, exc)
    return None

def _discover_remote_app_paths(repo: str, branch: str) -> Iterator[str]:
    url = f"https://api.github.com/repos/{repo}/git/trees/{branch}?recursive=1"
    try:
        response = requests.get(url, headers=_get_github_headers(), timeout=UPDATE_CHECK_TIMEOUT)
        if response.status_code == 200:
            data = response.json()
            tree = data.get("tree")
            if isinstance(tree, list):
                for item in tree:
                    if not isinstance(item, dict):
                        continue
                    path = item.get("path")
                    if path and str(path).endswith("case_documentation_app.py"):
                        yield str(path)
    except Exception as exc:
        logging.debug("Failed to discover remote app paths: %s", exc)

def _iter_remote_app_paths(repo: str, branch: str) -> Iterator[str]:
    env_paths = os.environ.get("KIROSHI_UPDATE_APP_PATHS")
    if env_paths:
        for path in env_paths.split(","):
            cleaned = path.strip().lstrip("/")
            if cleaned:
                yield cleaned

    yield from _discover_remote_app_paths(repo, branch)
    # Fallback default paths if discovery fails or is empty, though discovery covers them usually
    yield "case_documentation_app.py"

def check_for_updates() -> UpdateCheckResult:
    repo = os.environ.get("KIROSHI_UPDATE_REPO", DEFAULT_UPDATE_REPO)
    branch = os.environ.get("KIROSHI_UPDATE_BRANCH")

    if not branch:
        branch = _discover_default_branch(repo)

    if not branch:
        return UpdateCheckResult(
            repo=repo,
            branch="unknown",
            current_version=VERSION,
            error=f"Could not resolve branch for repository {repo}",
        )

    latest_version = None
    download_url = None
    latest_commit = None
    latest_published = None

    # Check commits for metadata
    try:
        commits_url = f"https://api.github.com/repos/{repo}/commits/{branch}"
        commit_resp = requests.get(commits_url, headers=_get_github_headers(), timeout=UPDATE_CHECK_TIMEOUT)
        if commit_resp.status_code == 200:
            commit_data = commit_resp.json()
            latest_commit = commit_data.get("sha")
            committer = commit_data.get("commit", {}).get("committer", {})
            date_str = committer.get("date")
            if date_str:
                try:
                    # Parse ISO format
                    dt = datetime.fromisoformat(date_str.replace("Z", "+00:00"))
                    latest_published = dt.strftime("%Y-%m-%d %H:%M %Z")
                except ValueError:
                    latest_published = date_str
    except Exception:
        pass

    # Check file content for version
    for path in _iter_remote_app_paths(repo, branch):
        raw_url = f"https://raw.githubusercontent.com/{repo}/{branch}/{path}"
        try:
            response = requests.get(raw_url, headers=_get_github_headers(), timeout=UPDATE_CHECK_TIMEOUT)
            if response.status_code == 200:
                content = response.text
                match = re.search(r'VERSION\s*=\s*["\']([^"\']+)["\']', content)
                if match:
                    latest_version = match.group(1)
                    break
        except Exception:
            continue

    if not latest_version:
        return UpdateCheckResult(
            repo=repo,
            branch=branch,
            current_version=VERSION,
            error=f"Could not find version info in repository {repo} (branch: {branch})",
        )

    has_update = latest_version != VERSION
    download_url = f"https://codeload.github.com/{repo}/zip/refs/heads/{branch}"

    return UpdateCheckResult(
        repo=repo,
        branch=branch,
        current_version=VERSION,
        latest_version=latest_version,
        latest_commit=latest_commit,
        latest_published=latest_published,
        has_update=has_update,
        download_url=download_url,
    )
