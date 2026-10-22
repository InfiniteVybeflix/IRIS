"""GitHub Integration Skill — issues, PRs, releases, repo listing.

Uses PyGithub (already in IRIS requirements.txt). All operations
require GITHUB_TOKEN env var.
"""

from __future__ import annotations

import logging
import os
import sys
from typing import Any, Dict

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "..", ".."))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from skills import BaseSkill

logger = logging.getLogger(__name__)


class GithubIntegrationSkill(BaseSkill):
    """GitHub operations: issues, PRs, releases, repo listing."""

    def __init__(self):
        super().__init__(
            name="github_integration",
            category="productivity",
            capabilities=[
                "github_create_issue", "github_list_issues",
                "github_create_pr", "github_create_release",
                "github_list_repos",
            ],
        )

    def init(self) -> bool:
        return True

    def shutdown(self) -> bool:
        return True

    def _get_client(self):
        token = os.environ.get("GITHUB_TOKEN")
        if not token:
            raise RuntimeError("GITHUB_TOKEN env var not set")
        try:
            from github import Github
            return Github(token)
        except ImportError:
            raise RuntimeError("PyGithub not installed (pip install PyGithub)")

    def execute(self, capability: str, params: Dict[str, Any]) -> Dict[str, Any]:
        try:
            client = self._get_client()
            if capability == "github_create_issue":
                return self._create_issue(client, params)
            elif capability == "github_list_issues":
                return self._list_issues(client, params)
            elif capability == "github_create_pr":
                return self._create_pr(client, params)
            elif capability == "github_create_release":
                return self._create_release(client, params)
            elif capability == "github_list_repos":
                return self._list_repos(client, params)
            return {"success": False, "error": f"unknown capability: {capability}"}
        except Exception as e:
            logger.exception("GithubIntegration.execute failed for %s", capability)
            return {"success": False, "error": str(e), "capability": capability}

    def _create_issue(self, client, params: Dict[str, Any]) -> Dict[str, Any]:
        repo_full = params.get("repo")  # "owner/name"
        title = params.get("title")
        body = params.get("body", "")
        labels = params.get("labels", [])
        if not repo_full or not title:
            return {"success": False, "error": "repo and title required"}
        repo = client.get_repo(repo_full)
        issue = repo.create_issue(title=title, body=body, labels=labels)
        return {"success": True, "number": issue.number, "url": issue.html_url, "title": issue.title}

    def _list_issues(self, client, params: Dict[str, Any]) -> Dict[str, Any]:
        repo_full = params.get("repo")
        state = params.get("state", "open")
        limit = int(params.get("limit", 30))
        if not repo_full:
            return {"success": False, "error": "repo required (owner/name)"}
        repo = client.get_repo(repo_full)
        issues = list(repo.get_issues(state=state))[:limit]
        return {
            "success": True,
            "count": len(issues),
            "issues": [
                {"number": i.number, "title": i.title, "state": i.state,
                 "url": i.html_url, "user": i.user.login if i.user else None,
                 "labels": [l.name for l in i.labels]}
                for i in issues
            ],
        }

    def _create_pr(self, client, params: Dict[str, Any]) -> Dict[str, Any]:
        repo_full = params.get("repo")
        title = params.get("title")
        body = params.get("body", "")
        head = params.get("head")  # source branch
        base = params.get("base", "main")
        if not repo_full or not title or not head:
            return {"success": False, "error": "repo, title, head required"}
        repo = client.get_repo(repo_full)
        pr = repo.create_pull(title=title, body=body, head=head, base=base)
        return {"success": True, "number": pr.number, "url": pr.html_url, "title": pr.title}

    def _create_release(self, client, params: Dict[str, Any]) -> Dict[str, Any]:
        repo_full = params.get("repo")
        tag = params.get("tag")
        name = params.get("name", tag)
        body = params.get("body", "")
        draft = params.get("draft", False)
        prerelease = params.get("prerelease", False)
        if not repo_full or not tag:
            return {"success": False, "error": "repo and tag required"}
        repo = client.get_repo(repo_full)
        release = repo.create_git_release(tag=tag, name=name, message=body,
                                            draft=draft, prerelease=prerelease)
        return {"success": True, "tag": release.tag_name, "url": release.html_url, "id": release.id}

    def _list_repos(self, client, params: Dict[str, Any]) -> Dict[str, Any]:
        limit = int(params.get("limit", 50))
        sort = params.get("sort", "updated")
        user = client.get_user()
        repos = list(user.get_repos(sort=sort))[:limit]
        return {
            "success": True,
            "count": len(repos),
            "repos": [
                {"name": r.full_name, "url": r.html_url, "private": r.private,
                 "stars": r.stargazers_count, "language": r.language,
                 "description": r.description}
                for r in repos
            ],
        }
