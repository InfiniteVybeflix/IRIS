"""
IRIS v1.0 — Git Engine

Git operations, repository analysis, commit inspection, secret detection,
vulnerability checking, and changelog generation.

Dependencies: git (system binary), gitpython
"""

from __future__ import annotations

import logging
import os
import shutil
import subprocess
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from .base_tool import BaseTool

logger = logging.getLogger(__name__)


class GitEngine(BaseTool):
    """Git repository analysis and operations tool."""

    name: str = "git_engine"
    category: str = "code"
    dependencies: List[str] = ["git", "gitpython"]

    def __init__(self, iris_core: Optional[Any] = None) -> None:
        super().__init__(iris_core)
        self._git_path: Optional[str] = None

    def _resolve_git(self) -> str:
        if self._git_path is None:
            path = shutil.which("git")
            if path is None:
                raise RuntimeError("git binary not found.")
            self._git_path = path
        return self._git_path

    def _run_git(self, args: List[str], cwd: Optional[str] = None, timeout: int = 120) -> subprocess.CompletedProcess:
        return self._run_subprocess([self._resolve_git()] + args, cwd=cwd, timeout=timeout)

    def _run(self, *args: Any, **kwargs: Any) -> Dict[str, Any]:
        return {}

    def clone_repo(self, url: str, path: str, branch: Optional[str] = None, depth: Optional[int] = None) -> Dict[str, Any]:
        self._begin_execution()
        try:
            safe_url = self.sanitize_input(url)
            safe_path = os.path.abspath(os.path.expanduser(path))
            os.makedirs(os.path.dirname(safe_path) or ".", exist_ok=True)
            args = ["clone", safe_url, safe_path]
            if branch:
                args.extend(["--branch", self.sanitize_input(branch)])
            if depth:
                args.extend(["--depth", str(depth)])
            result = self._run_git(args, timeout=300)
            res = self._build_result(success=result.returncode == 0, action="clone_repo", output=result.stdout,
                parsed={"url": safe_url, "path": safe_path, "branch": branch, "depth": depth},
                errors=[result.stderr] if result.stderr and result.returncode != 0 else [])
            self.last_result = res
            self._end_execution(result.returncode == 0)
            return res
        except Exception as exc:
            logger.exception("clone_repo failed")
            res = self._build_result(success=False, action="clone_repo", errors=[str(exc)])
            self.last_result = res
            self._end_execution(False)
            return res

    def analyze_history(self, repo_path: str) -> Dict[str, Any]:
        self._begin_execution()
        try:
            safe_path = os.path.abspath(os.path.expanduser(repo_path))
            if not os.path.exists(os.path.join(safe_path, ".git")):
                return self._build_result(success=False, action="analyze_history", errors=[f"Not a git repo: {safe_path}"])
            result = self._run_git(["rev-list", "--count", "HEAD"], cwd=safe_path)
            commit_count = int(result.stdout.strip()) if result.returncode == 0 else 0
            result = self._run_git(["shortlog", "-sn", "HEAD"], cwd=safe_path)
            contributors: List[Dict[str, Any]] = []
            if result.returncode == 0:
                for line in result.stdout.strip().splitlines():
                    parts = line.strip().split("\t", 1)
                    if len(parts) == 2:
                        contributors.append({"commits": int(parts[0].strip()), "name": parts[1].strip()})
            result = self._run_git(["log", "--pretty=format:%H|%ci|%s", "-n", "10"], cwd=safe_path)
            recent: List[Dict[str, Any]] = []
            if result.returncode == 0:
                for line in result.stdout.strip().splitlines():
                    parts = line.split("|", 2)
                    if len(parts) == 3:
                        recent.append({"hash": parts[0], "date": parts[1], "message": parts[2]})
            res = self._build_result(success=True, action="analyze_history", output={"commits": commit_count, "contributors": contributors},
                parsed={"repo_path": safe_path, "commit_count": commit_count, "contributor_count": len(contributors), "contributors": contributors, "recent_commits": recent})
            self.last_result = res
            self._end_execution(True)
            return res
        except Exception as exc:
            logger.exception("analyze_history failed")
            res = self._build_result(success=False, action="analyze_history", errors=[str(exc)])
            self.last_result = res
            self._end_execution(False)
            return res

    def find_secrets(self, repo_path: str) -> Dict[str, Any]:
        self._begin_execution()
        try:
            safe_path = os.path.abspath(os.path.expanduser(repo_path))
            findings: List[Dict[str, Any]] = []
            scanner_used = "none"
            if shutil.which("gitleaks"):
                scanner_used = "gitleaks"
                output_file = "/tmp/gitleaks_iris.json"
                result = self._run_subprocess(["gitleaks", "detect", "-s", safe_path, "-r", output_file, "--redact"], timeout=300)
                if os.path.exists(output_file):
                    import json
                    with open(output_file) as f:
                        data = json.load(f)
                    for finding in data:
                        findings.append({"file": finding.get("File"), "line": finding.get("StartLine"), "rule": finding.get("RuleID"),
                            "severity": finding.get("Severity", "high"), "type": finding.get("Description")})
            elif shutil.which("trufflehog"):
                scanner_used = "trufflehog"
                result = self._run_subprocess(["trufflehog", "filesystem", safe_path, "--json"], timeout=300)
                import json
                for line in result.stdout.strip().splitlines():
                    try:
                        data = json.loads(line)
                        findings.append({"file": data.get("SourceMetadata", {}).get("Data", {}).get("Filesystem", {}).get("file"),
                            "rule": data.get("DetectorName"), "severity": "high", "type": data.get("DetectorName")})
                    except Exception:
                        pass
            else:
                scanner_used = "regex_fallback"
                import re
                patterns = {"aws_access_key": re.compile(r"AKIA[0-9A-Z]{16}"), "aws_secret_key": re.compile(r"[0-9a-zA-Z/+]{40}"),
                    "private_key": re.compile(r"-----BEGIN (RSA |DSA |EC |OPENSSH )?PRIVATE KEY-----"),
                    "api_key_generic": re.compile(r"['\"]?api[_-]?key['\"]?\s*[:=]\s*['\"][a-zA-Z0-9_\-]{16,}['\"]")}
                for root, _, files in os.walk(safe_path):
                    if ".git" in root:
                        continue
                    for filename in files:
                        filepath = os.path.join(root, filename)
                        try:
                            with open(filepath, "r", encoding="utf-8", errors="ignore") as f:
                                content = f.read()
                            for name, pattern in patterns.items():
                                for match in pattern.finditer(content):
                                    line_num = content[:match.start()].count("\n") + 1
                                    findings.append({"file": filepath, "line": line_num, "pattern": name, "match": match.group(0)[:100]})
                        except Exception:
                            pass
            res = self._build_result(success=True, action="find_secrets", output=findings,
                parsed={"repo_path": safe_path, "scanner": scanner_used, "finding_count": len(findings), "findings": findings})
            self.last_result = res
            self._end_execution(True)
            return res
        except Exception as exc:
            logger.exception("find_secrets failed")
            res = self._build_result(success=False, action="find_secrets", errors=[str(exc)])
            self.last_result = res
            self._end_execution(False)
            return res

    def check_vulnerabilities(self, repo_path: str) -> Dict[str, Any]:
        self._begin_execution()
        try:
            safe_path = os.path.abspath(os.path.expanduser(repo_path))
            findings: List[Dict[str, Any]] = []
            scanner_used = "none"
            if os.path.exists(os.path.join(safe_path, "requirements.txt")) or os.path.exists(os.path.join(safe_path, "Pipfile")):
                if shutil.which("safety"):
                    scanner_used = "safety"
                    result = self._run_subprocess(["safety", "check", "--json", "--file", os.path.join(safe_path, "requirements.txt")], timeout=300)
                    try:
                        import json
                        data = json.loads(result.stdout)
                        for vuln in data.get("vulnerabilities", []):
                            findings.append({"package": vuln.get("package_name"), "affected": vuln.get("vulnerable_spec"),
                                "fixed": vuln.get("fixed_versions"), "severity": vuln.get("severity", "unknown"), "cve": vuln.get("cve")})
                    except Exception:
                        pass
            if os.path.exists(os.path.join(safe_path, "package.json")):
                if shutil.which("npm"):
                    scanner_used = "npm_audit"
                    result = self._run_subprocess(["npm", "audit", "--json"], cwd=safe_path, timeout=300)
                    try:
                        import json
                        data = json.loads(result.stdout)
                        for adv_id, adv in data.get("advisories", {}).items():
                            findings.append({"package": adv.get("module_name"), "severity": adv.get("severity"),
                                "title": adv.get("title"), "cve": adv.get("cves", [None])[0]})
                    except Exception:
                        pass
            res = self._build_result(success=True, action="check_vulnerabilities", output=findings,
                parsed={"repo_path": safe_path, "scanner": scanner_used, "vulnerability_count": len(findings), "findings": findings})
            self.last_result = res
            self._end_execution(True)
            return res
        except Exception as exc:
            logger.exception("check_vulnerabilities failed")
            res = self._build_result(success=False, action="check_vulnerabilities", errors=[str(exc)])
            self.last_result = res
            self._end_execution(False)
            return res

    def generate_changelog(self, repo_path: str, since: Optional[str] = None) -> Dict[str, Any]:
        self._begin_execution()
        try:
            safe_path = os.path.abspath(os.path.expanduser(repo_path))
            args = ["log", "--pretty=format:- %s (%h by %an on %ad)", "--date=short"]
            if since:
                args.append(f"{since}..HEAD")
            result = self._run_git(args, cwd=safe_path)
            changelog = result.stdout if result.returncode == 0 else ""
            categories: Dict[str, List[str]] = {"Features": [], "Fixes": [], "Documentation": [], "Other": []}
            for line in changelog.splitlines():
                lower = line.lower()
                if any(k in lower for k in ("feat", "feature", "add", "implement")):
                    categories["Features"].append(line)
                elif any(k in lower for k in ("fix", "bugfix", "patch", "resolve")):
                    categories["Fixes"].append(line)
                elif any(k in lower for k in ("doc", "readme", "comment")):
                    categories["Documentation"].append(line)
                else:
                    categories["Other"].append(line)
            formatted = "# Changelog\n\n"
            for cat, items in categories.items():
                if items:
                    formatted += f"## {cat}\n"
                    for item in items:
                        formatted += f"{item}\n"
                    formatted += "\n"
            res = self._build_result(success=result.returncode == 0, action="generate_changelog", output=formatted,
                parsed={"repo_path": safe_path, "since": since, "commit_count": len(changelog.splitlines()),
                    "categories": {k: len(v) for k, v in categories.items()}},
                errors=[result.stderr] if result.stderr and result.returncode != 0 else [])
            self.last_result = res
            self._end_execution(result.returncode == 0)
            return res
        except Exception as exc:
            logger.exception("generate_changelog failed")
            res = self._build_result(success=False, action="generate_changelog", errors=[str(exc)])
            self.last_result = res
            self._end_execution(False)
            return res


__all__ = ["GitEngine"]
