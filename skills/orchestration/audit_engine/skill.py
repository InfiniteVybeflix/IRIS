"""IRIS Audit Engine — Repository auditing and codebase analysis."""
import os
import re
import json
import ast
import subprocess
import logging
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
from datetime import datetime
from dataclasses import dataclass, field, asdict

from skills.base import BaseSkill, SkillCapability
from skills.contracts.skill_request import SkillRequest
from skills.contracts.skill_result import SkillResult
from skills.contracts.capability_tags import CapabilityTags

logger = logging.getLogger(__name__)


@dataclass
class AuditFinding:
    severity: str  # critical, high, medium, low, info
    category: str  # security, architecture, bug, style, performance, dead_code
    file_path: str
    line_number: int
    message: str
    suggestion: str = ""
    code_snippet: str = ""
    confidence: float = 1.0


@dataclass
class AuditReport:
    repo_path: str
    scanned_at: str
    total_files: int
    total_lines: int
    findings: List[AuditFinding] = field(default_factory=list)
    summary: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict:
        return {
            "repo_path": self.repo_path,
            "scanned_at": self.scanned_at,
            "total_files": self.total_files,
            "total_lines": self.total_lines,
            "findings": [asdict(f) for f in self.findings],
            "summary": self.summary,
        }


class AuditEngineSkill(BaseSkill):
    name = "audit_engine"
    display_name = "Audit Engine"
    description = "Repository auditing, codebase analysis, security scanning, and structured report generation."
    version = "2.0.0"
    category = "orchestration"
    icon = "🔍"
    uses_storage = True
    supports_background = False

    capabilities = [
        SkillCapability(
            name="audit_repo",
            description="Full audit of a repository — structure, security, bugs, architecture",
            input_schema={"repo_path": "str", "depth": "str: quick|standard|deep"},
            output_schema={"report": "dict", "findings_count": "int"},
            tags=[CapabilityTags.AUDIT_ENGINE],
        ),
        SkillCapability(
            name="security_scan",
            description="Scan for secrets, hardcoded keys, vulnerabilities",
            input_schema={"repo_path": "str"},
            output_schema={"issues": "list", "count": "int"},
            tags=[CapabilityTags.AUDIT_ENGINE, CapabilityTags.TRUST_SAFETY],
        ),
        SkillCapability(
            name="structure_analysis",
            description="Analyze project structure and dependencies",
            input_schema={"repo_path": "str"},
            output_schema={"structure": "dict"},
            tags=[CapabilityTags.AUDIT_ENGINE],
        ),
        SkillCapability(
            name="code_quality",
            description="Check code quality, complexity, dead code",
            input_schema={"repo_path": "str"},
            output_schema={"metrics": "dict", "issues": "list"},
            tags=[CapabilityTags.AUDIT_ENGINE],
        ),
        SkillCapability(
            name="generate_report",
            description="Generate a formatted audit report",
            input_schema={"findings": "list", "format": "str: json|markdown|html"},
            output_schema={"report": "str", "path": "str"},
            tags=[CapabilityTags.AUDIT_ENGINE],
        ),
        SkillCapability(
            name="clone_and_audit",
            description="Clone a repo from URL and audit it",
            input_schema={"repo_url": "str", "depth": "str"},
            output_schema={"report": "dict"},
            tags=[CapabilityTags.AUDIT_ENGINE],
        ),
    ]

    def __init__(self):
        super().__init__()
        self.storage_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "data", "audit_engine")
        os.makedirs(self.storage_dir, exist_ok=True)

    def execute(self, request: SkillRequest) -> SkillResult:
        intent = request.intent.lower()
        params = request.params

        if intent in ("audit_repo", "audit", "code_audit"):
            return self._audit_repo(params)
        elif intent in ("security_scan", "security_audit", "scan_secrets"):
            return self._security_scan(params)
        elif intent in ("structure_analysis", "analyze_structure", "repo_structure"):
            return self._structure_analysis(params)
        elif intent in ("code_quality", "quality_check", "dead_code"):
            return self._code_quality(params)
        elif intent in ("generate_report", "audit_report"):
            return self._generate_report(params)
        elif intent in ("clone_and_audit", "fetch_and_audit"):
            return self._clone_and_audit(params)
        else:
            return SkillResult.fail(error=f"Unknown audit intent: {intent}")

    def can_handle(self, request: SkillRequest) -> float:
        intent = request.intent.lower()
        keywords = ["audit", "scan", "analyze", "review", "inspect", "check", "security", "vulnerability", "code quality", "structure"]
        if any(k in intent for k in keywords):
            return 0.9
        return super().can_handle(request)

    # === Core Audit ===

    def _audit_repo(self, params: Dict) -> SkillResult:
        repo_path = params.get("repo_path", ".")
        depth = params.get("depth", "standard")

        if not os.path.exists(repo_path):
            return SkillResult.fail(error=f"Repository path not found: {repo_path}")

        report = AuditReport(
            repo_path=repo_path,
            scanned_at=datetime.now().isoformat(),
            total_files=0,
            total_lines=0,
        )

        # Phase 1: Structure
        structure = self._analyze_structure(repo_path)
        report.total_files = structure["file_count"]
        report.total_lines = structure["total_lines"]

        # Phase 2: Security
        security_findings = self._scan_security(repo_path)
        report.findings.extend(security_findings)

        # Phase 3: Code Quality
        quality_findings = self._scan_quality(repo_path, depth)
        report.findings.extend(quality_findings)

        # Phase 4: Architecture
        arch_findings = self._scan_architecture(repo_path, structure)
        report.findings.extend(arch_findings)

        # Summary
        severity_counts = {"critical": 0, "high": 0, "medium": 0, "low": 0, "info": 0}
        category_counts = {}
        for f in report.findings:
            severity_counts[f.severity] = severity_counts.get(f.severity, 0) + 1
            category_counts[f.category] = category_counts.get(f.category, 0) + 1

        report.summary = {
            "severity_breakdown": severity_counts,
            "category_breakdown": category_counts,
            "total_findings": len(report.findings),
            "files_scanned": report.total_files,
            "lines_scanned": report.total_lines,
            "health_score": max(0, 100 - severity_counts["critical"] * 20 - severity_counts["high"] * 10 - severity_counts["medium"] * 3),
        }

        # Save report
        report_path = os.path.join(self.storage_dir, f"audit_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json")
        with open(report_path, "w", encoding="utf-8") as f:
            json.dump(report.to_dict(), f, indent=2, default=str)

        return SkillResult.ok(
            message=f"Audit complete. {len(report.findings)} findings. Health score: {report.summary['health_score']}/100",
            data={"report": report.to_dict(), "findings_count": len(report.findings), "report_path": report_path}
        )

    def _security_scan(self, params: Dict) -> SkillResult:
        repo_path = params.get("repo_path", ".")
        findings = self._scan_security(repo_path)
        return SkillResult.ok(
            data={"issues": [asdict(f) for f in findings], "count": len(findings)},
            message=f"Security scan: {len(findings)} issue(s) found."
        )

    def _structure_analysis(self, params: Dict) -> SkillResult:
        repo_path = params.get("repo_path", ".")
        structure = self._analyze_structure(repo_path)
        return SkillResult.ok(data={"structure": structure})

    def _code_quality(self, params: Dict) -> SkillResult:
        repo_path = params.get("repo_path", ".")
        findings = self._scan_quality(repo_path, "standard")
        return SkillResult.ok(
            data={"metrics": {"findings": len(findings)}, "issues": [asdict(f) for f in findings]},
            message=f"Code quality: {len(findings)} issue(s) found."
        )

    def _generate_report(self, params: Dict) -> SkillResult:
        findings = params.get("findings", [])
        fmt = params.get("format", "markdown")

        if fmt == "markdown":
            lines = ["# Audit Report\n", f"Generated: {datetime.now().isoformat()}\n\n"]
            lines.append("## Findings Summary\n\n")
            for f in findings:
                lines.append(f"### [{f.get('severity', 'info').upper()}] {f.get('category', 'general')}\n")
                lines.append(f"- **File:** `{f.get('file_path', 'N/A')}` (line {f.get('line_number', 0)})\n")
                lines.append(f"- **Message:** {f.get('message', '')}\n")
                if f.get('suggestion'):
                    lines.append(f"- **Suggestion:** {f.get('suggestion')}\n")
                lines.append("\n")
            content = "\n".join(lines)
        elif fmt == "json":
            content = json.dumps(findings, indent=2, default=str)
        else:
            content = str(findings)

        report_path = os.path.join(self.storage_dir, f"report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.{fmt}")
        with open(report_path, "w", encoding="utf-8") as f:
            f.write(content)

        return SkillResult.ok(data={"report": content, "path": report_path, "format": fmt})

    def _clone_and_audit(self, params: Dict) -> SkillResult:
        repo_url = params.get("repo_url")
        if not repo_url:
            return SkillResult.fail(error="repo_url is required")

        target = os.path.join(self.storage_dir, "repos", repo_url.split("/")[-1].replace(".git", ""))
        os.makedirs(os.path.dirname(target), exist_ok=True)

        try:
            result = subprocess.run(
                ["git", "clone", "--depth", "1", repo_url, target],
                capture_output=True, text=True, timeout=120
            )
            if result.returncode != 0:
                return SkillResult.fail(error=f"Clone failed: {result.stderr}")
            return self._audit_repo({"repo_path": target, "depth": params.get("depth", "standard")})
        except Exception as e:
            return SkillResult.fail(error=str(e))

    # === Scanning Engines ===

    def _analyze_structure(self, repo_path: str) -> Dict:
        file_count = 0
        total_lines = 0
        languages = {}
        entry_points = []
        config_files = []
        test_files = []
        doc_files = []

        for root, dirs, files in os.walk(repo_path):
            # Skip common non-code dirs
            dirs[:] = [d for d in dirs if d not in {
                "node_modules", ".git", "__pycache__", "venv", ".venv",
                "dist", "build", ".next", ".vercel", ".idea", ".vscode"
            }]

            for file in files:
                file_path = os.path.join(root, file)
                rel_path = os.path.relpath(file_path, repo_path)
                file_count += 1

                ext = os.path.splitext(file)[1].lower()
                if ext in languages:
                    languages[ext] += 1
                else:
                    languages[ext] = 1

                if file in ["app.py", "main.py", "index.js", "server.js", "main.go", "main.rs"]:
                    entry_points.append(rel_path)
                if file in ["package.json", "requirements.txt", "Cargo.toml", "go.mod", "Dockerfile", "docker-compose.yml", ".env.example"]:
                    config_files.append(rel_path)
                if "test" in file.lower() or "spec" in file.lower():
                    test_files.append(rel_path)
                if file.endswith(".md") or file.endswith(".rst") or file.endswith(".txt"):
                    doc_files.append(rel_path)

                try:
                    with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
                        total_lines += len(f.readlines())
                except Exception:
                    pass

        return {
            "file_count": file_count,
            "total_lines": total_lines,
            "languages": languages,
            "entry_points": entry_points,
            "config_files": config_files,
            "test_files": test_files,
            "doc_files": doc_files,
            "has_tests": len(test_files) > 0,
            "has_docs": len(doc_files) > 0,
            "has_docker": any("docker" in f.lower() for f in config_files),
        }

    def _scan_security(self, repo_path: str) -> List[AuditFinding]:
        findings = []

        secret_patterns = [
            (r'(?i)(api[_-]?key|apikey)\s*=\s*["']\w{20,}["']', "Hardcoded API key", "critical"),
            (r'(?i)(password|passwd|pwd)\s*=\s*["'][^"']{8,}["']', "Hardcoded password", "critical"),
            (r'(?i)(token|access_token|auth_token)\s*=\s*["']\w{20,}["']', "Hardcoded token", "critical"),
            (r'(?i)(secret|client_secret)\s*=\s*["']\w{20,}["']', "Hardcoded secret", "critical"),
            (r'(?i)(private_key|rsa_key)\s*[:=]\s*["']?[\w+/=]{100,}', "Private key exposed", "critical"),
            (r'(?i)aws_access_key_id\s*=\s*["']\w{16,}["']', "AWS key exposed", "critical"),
            (r'(?i)github[_-]?token\s*=\s*["']gh[pousr]_[\w]{30,}["']', "GitHub token exposed", "critical"),
            (r'(?i)sk-[a-zA-Z0-9]{40,}', "OpenAI API key pattern", "critical"),
            (r'(?i)(eval|exec)\s*\(', "Dangerous eval/exec usage", "high"),
            (r'(?i)subprocess\.call\s*\([^)]*shell\s*=\s*True', "Shell=True subprocess", "high"),
            (r'(?i)pickle\.loads?\s*\(', "Unsafe pickle deserialization", "high"),
            (r'(?i)yaml\.load\s*\([^)]*Loader\s*=\s*yaml\.Loader', "Unsafe YAML loader", "high"),
            (r'(?i)\.format\s*\([^)]*\)', "Potential format string injection", "medium"),
        ]

        for root, dirs, files in os.walk(repo_path):
            dirs[:] = [d for d in dirs if d not in {"node_modules", ".git", "__pycache__", "venv"}]
            for file in files:
                if not any(file.endswith(ext) for ext in [".py", ".js", ".ts", ".jsx", ".tsx", ".json", ".env", ".yaml", ".yml", ".toml"]):
                    continue
                file_path = os.path.join(root, file)
                rel_path = os.path.relpath(file_path, repo_path)
                try:
                    with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
                        lines = f.readlines()
                    for line_num, line in enumerate(lines, 1):
                        for pattern, msg, severity in secret_patterns:
                            if re.search(pattern, line):
                                findings.append(AuditFinding(
                                    severity=severity,
                                    category="security",
                                    file_path=rel_path,
                                    line_number=line_num,
                                    message=msg,
                                    suggestion="Move to environment variables or a secrets manager.",
                                    code_snippet=line.strip()[:200],
                                    confidence=0.9,
                                ))
                except Exception:
                    pass

        return findings

    def _scan_quality(self, repo_path: str, depth: str) -> List[AuditFinding]:
        findings = []

        for root, dirs, files in os.walk(repo_path):
            dirs[:] = [d for d in dirs if d not in {"node_modules", ".git", "__pycache__", "venv"}]
            for file in files:
                if not file.endswith(".py"):
                    continue
                file_path = os.path.join(root, file)
                rel_path = os.path.relpath(file_path, repo_path)
                try:
                    with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
                        source = f.read()
                        lines = source.split("\n")

                    # Try AST analysis
                    try:
                        tree = ast.parse(source)
                        for node in ast.walk(tree):
                            if isinstance(node, ast.FunctionDef):
                                func_lines = node.end_lineno - node.lineno if hasattr(node, 'end_lineno') and node.end_lineno else 0
                                if func_lines > 50:
                                    findings.append(AuditFinding(
                                        severity="medium",
                                        category="architecture",
                                        file_path=rel_path,
                                        line_number=node.lineno,
                                        message=f"Function '{node.name}' is {func_lines} lines — consider refactoring",
                                        suggestion="Break into smaller functions (max ~30 lines each).",
                                    ))
                            if isinstance(node, ast.ExceptHandler):
                                if node.type is None or (isinstance(node.type, ast.Name) and node.type.id == "Exception"):
                                    findings.append(AuditFinding(
                                        severity="medium",
                                        category="bug",
                                        file_path=rel_path,
                                        line_number=node.lineno,
                                        message="Bare except: catches all exceptions including KeyboardInterrupt",
                                        suggestion="Use specific exception types.",
                                    ))
                    except SyntaxError:
                        findings.append(AuditFinding(
                            severity="high",
                            category="bug",
                            file_path=rel_path,
                            line_number=0,
                            message="Syntax error — file cannot be parsed",
                            suggestion="Fix syntax errors before deployment.",
                        ))

                    # Line-by-line checks
                    for line_num, line in enumerate(lines, 1):
                        stripped = line.strip()
                        if stripped.startswith("# TODO") or stripped.startswith("# FIXME"):
                            findings.append(AuditFinding(
                                severity="low",
                                category="dead_code",
                                file_path=rel_path,
                                line_number=line_num,
                                message=f"Unresolved TODO: {stripped[5:].strip()}",
                                suggestion="Resolve or remove TODO comments.",
                            ))
                        if "print(" in stripped and not stripped.startswith("#"):
                            findings.append(AuditFinding(
                                severity="low",
                                category="style",
                                file_path=rel_path,
                                line_number=line_num,
                                message="Debug print statement found",
                                suggestion="Use logging instead of print.",
                            ))
                        if len(line) > 120:
                            findings.append(AuditFinding(
                                severity="low",
                                category="style",
                                file_path=rel_path,
                                line_number=line_num,
                                message="Line exceeds 120 characters",
                                suggestion="Break into multiple lines.",
                            ))

                except Exception:
                    pass

        return findings

    def _scan_architecture(self, repo_path: str, structure: Dict) -> List[AuditFinding]:
        findings = []

        if not structure.get("has_tests"):
            findings.append(AuditFinding(
                severity="high",
                category="architecture",
                file_path=".",
                line_number=0,
                message="No test files detected",
                suggestion="Add unit tests (pytest recommended for Python).",
            ))

        if not structure.get("has_docs"):
            findings.append(AuditFinding(
                severity="medium",
                category="architecture",
                file_path=".",
                line_number=0,
                message="No documentation files detected",
                suggestion="Add README.md and inline documentation.",
            ))

        if not structure.get("has_docker"):
            findings.append(AuditFinding(
                severity="low",
                category="architecture",
                file_path=".",
                line_number=0,
                message="No Docker configuration found",
                suggestion="Consider adding Dockerfile for deployment consistency.",
            ))

        # Check for .env files committed
        env_files = []
        for root, dirs, files in os.walk(repo_path):
            dirs[:] = [d for d in dirs if d != ".git"]
            for f in files:
                if f == ".env" or f.endswith(".env"):
                    env_files.append(os.path.relpath(os.path.join(root, f), repo_path))
        if env_files:
            findings.append(AuditFinding(
                severity="critical",
                category="security",
                file_path=", ".join(env_files),
                line_number=0,
                message=".env file(s) committed to repository",
                suggestion="Remove .env files, add to .gitignore, use .env.example instead.",
            ))

        # Check requirements duplication
        req_files = [f for f in structure.get("config_files", []) if "requirements" in f]
        if len(req_files) > 1:
            findings.append(AuditFinding(
                severity="low",
                category="architecture",
                file_path=", ".join(req_files),
                line_number=0,
                message=f"Multiple requirements files: {len(req_files)}",
                suggestion="Consolidate into a single requirements.txt or use poetry/pipenv.",
            ))

        return findings
