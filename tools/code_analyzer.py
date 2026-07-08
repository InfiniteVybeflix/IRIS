"""
IRIS v7.0 — Code Analyzer

Static analysis engine supporting Semgrep, Bandit, and custom regex.
Generates SARIF output for CI/CD integration.

Dependencies: semgrep (optional), bandit (optional)
"""

from __future__ import annotations

import json
import logging
import os
import re
import shutil
from typing import Any, Dict, List, Optional

from .base_tool import BaseTool

logger = logging.getLogger(__name__)


class CodeAnalyzer(BaseTool):
    """Static code analysis tool. Read-only."""

    name: str = "code_analyzer"
    category: str = "code"
    dependencies: List[str] = ["semgrep", "bandit"]

    def __init__(self, iris_core: Optional[Any] = None) -> None:
        super().__init__(iris_core)
        self._sarif_runs: List[Dict[str, Any]] = []

    def _run(self, *args: Any, **kwargs: Any) -> Dict[str, Any]:
        return {}

    def run_semgrep(self, targets: List[str], rules: Optional[str] = None, config: Optional[str] = None) -> Dict[str, Any]:
        self._begin_execution()
        try:
            if not shutil.which("semgrep"):
                return self._build_result(success=False, action="run_semgrep", errors=["semgrep not installed."])
            safe_targets = [self.sanitize_input(t) for t in targets]
            output_file = "/tmp/semgrep_iris.json"
            cmd = ["semgrep", "--json", "-o", output_file]
            if rules:
                cmd.extend(["--config", self.sanitize_input(rules)])
            elif config:
                cmd.extend(["--config", self.sanitize_input(config)])
            else:
                cmd.extend(["--config", "p/security-audit"])
            cmd.extend(safe_targets)
            result = self._run_subprocess(cmd, timeout=600)
            findings: List[Dict[str, Any]] = []
            if os.path.exists(output_file):
                with open(output_file) as f:
                    data = json.load(f)
                for r in data.get("results", []):
                    findings.append({"file": r.get("path"), "line": r.get("start", {}).get("line"),
                        "column": r.get("start", {}).get("col"), "rule": r.get("check_id"),
                        "message": r.get("extra", {}).get("message"),
                        "severity": r.get("extra", {}).get("metadata", {}).get("severity", "unknown"), "language": r.get("extra", {}).get("language")})
            res = self._build_result(success=result.returncode in (0, 1), action="run_semgrep",
                output=data if os.path.exists(output_file) else {},
                parsed={"target_count": len(safe_targets), "finding_count": len(findings), "findings": findings},
                errors=[result.stderr] if result.stderr and result.returncode not in (0, 1) else [])
            self.last_result = res
            self._end_execution(res["success"])
            return res
        except Exception as exc:
            logger.exception("run_semgrep failed")
            res = self._build_result(success=False, action="run_semgrep", errors=[str(exc)])
            self.last_result = res
            self._end_execution(False)
            return res

    def run_bandit(self, files: List[str]) -> Dict[str, Any]:
        self._begin_execution()
        try:
            if not shutil.which("bandit"):
                return self._build_result(success=False, action="run_bandit", errors=["bandit not installed."])
            safe_files = [self.sanitize_input(f) for f in files]
            output_file = "/tmp/bandit_iris.json"
            cmd = ["bandit", "-f", "json", "-o", output_file, "-r"]
            cmd.extend(safe_files)
            result = self._run_subprocess(cmd, timeout=300)
            findings: List[Dict[str, Any]] = []
            if os.path.exists(output_file):
                with open(output_file) as f:
                    data = json.load(f)
                for r in data.get("results", []):
                    findings.append({"file": r.get("filename"), "line": r.get("line_number"), "issue": r.get("issue_text"),
                        "severity": r.get("issue_severity"), "confidence": r.get("issue_confidence"),
                        "cwe": r.get("issue_cwe", {}).get("id"), "test_id": r.get("test_id")})
            res = self._build_result(success=result.returncode in (0, 1), action="run_bandit",
                output=data if os.path.exists(output_file) else {},
                parsed={"file_count": len(safe_files), "finding_count": len(findings), "findings": findings},
                errors=[result.stderr] if result.stderr and result.returncode not in (0, 1) else [])
            self.last_result = res
            self._end_execution(res["success"])
            return res
        except Exception as exc:
            logger.exception("run_bandit failed")
            res = self._build_result(success=False, action="run_bandit", errors=[str(exc)])
            self.last_result = res
            self._end_execution(False)
            return res

    def custom_regex_scan(self, patterns: Dict[str, str], targets: List[str]) -> Dict[str, Any]:
        self._begin_execution()
        try:
            compiled = {name: re.compile(pattern) for name, pattern in patterns.items()}
            findings: List[Dict[str, Any]] = []
            for target in targets:
                safe_target = os.path.abspath(os.path.expanduser(target))
                if os.path.isdir(safe_target):
                    for root, _, files in os.walk(safe_target):
                        if ".git" in root:
                            continue
                        for filename in files:
                            self._scan_file(os.path.join(root, filename), compiled, findings)
                elif os.path.isfile(safe_target):
                    self._scan_file(safe_target, compiled, findings)
            res = self._build_result(success=True, action="custom_regex_scan", output=findings,
                parsed={"pattern_count": len(patterns), "target_count": len(targets), "finding_count": len(findings), "findings": findings})
            self.last_result = res
            self._end_execution(True)
            return res
        except Exception as exc:
            logger.exception("custom_regex_scan failed")
            res = self._build_result(success=False, action="custom_regex_scan", errors=[str(exc)])
            self.last_result = res
            self._end_execution(False)
            return res

    def _scan_file(self, filepath: str, patterns: Dict[str, re.Pattern], findings: List[Dict[str, Any]]) -> None:
        try:
            with open(filepath, "r", encoding="utf-8", errors="ignore") as f:
                content = f.read()
            for name, pattern in patterns.items():
                for match in pattern.finditer(content):
                    line_num = content[:match.start()].count("\n") + 1
                    findings.append({"file": filepath, "line": line_num, "pattern": name, "match": match.group(0)[:100]})
        except Exception:
            pass

    def generate_sarif(self, findings: List[Dict[str, Any]]) -> Dict[str, Any]:
        self._begin_execution()
        try:
            sarif = {
                "$schema": "https://raw.githubusercontent.com/oasis-tcs/sarif-spec/master/Schemata/sarif-schema-2.1.0.json",
                "version": "2.1.0",
                "runs": [{"tool": {"driver": {"name": "IRIS Code Analyzer", "version": "7.0.0"}}, "results": []}]
            }
            for finding in findings:
                sarif["runs"][0]["results"].append({
                    "ruleId": finding.get("rule", finding.get("pattern", "unknown")),
                    "message": {"text": finding.get("message", finding.get("issue", "Finding detected"))},
                    "locations": [{"physicalLocation": {"artifactLocation": {"uri": finding.get("file", "")},
                        "region": {"startLine": finding.get("line", 1), "startColumn": finding.get("column", 1)}}}],
                    "level": finding.get("severity", "warning").lower(),
                })
            res = self._build_result(success=True, action="generate_sarif", output=sarif,
                parsed={"result_count": len(findings), "sarif_version": "2.1.0"})
            self.last_result = res
            self._end_execution(True)
            return res
        except Exception as exc:
            logger.exception("generate_sarif failed")
            res = self._build_result(success=False, action="generate_sarif", errors=[str(exc)])
            self.last_result = res
            self._end_execution(False)
            return res


__all__ = ["CodeAnalyzer"]
