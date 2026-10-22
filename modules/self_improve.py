"""IRIS v1 Hybrid Self-Improvement Engine - Edits Her Own Code"""
import os
import json
import shutil
import subprocess
from datetime import datetime
from pathlib import Path
from typing import Dict, List
from config import config
from core.db import db
from core.tool_registry import ToolResult

class SelfImprovementEngine:
    """IRIS reads her own code, finds bugs, fixes them, tests, commits."""

    def __init__(self):
        self.backup_dir = os.path.join(config.DATA_DIR, "backups")
        self.sandbox_dir = os.path.join(config.DATA_DIR, "sandbox")
        os.makedirs(self.backup_dir, exist_ok=True)
        os.makedirs(self.sandbox_dir, exist_ok=True)
        self.change_log = []

    def analyze_self(self) -> Dict:
        """Analyze IRIS own codebase for issues"""
        issues = []
        py_files = list(Path(config.BASE_DIR).rglob("*.py"))

        for file_path in py_files:
            if "__pycache__" in str(file_path):
                continue
            try:
                with open(file_path, "r", encoding="utf-8") as f:
                    content = f.read()

                for i, line in enumerate(content.split("\n"), 1):
                    if any(marker in line for marker in ["TODO", "FIXME", "HACK", "BUG", "XXX"]):
                        issues.append({"type": "todo", "file": str(file_path), "line": i,
                                       "description": line.strip(), "severity": "medium"})

                for i, line in enumerate(content.split("\n"), 1):
                    if "except:" in line and "except Exception" not in line:
                        issues.append({"type": "code_quality", "file": str(file_path), "line": i,
                                       "description": "Bare except clause", "severity": "high"})

                for i, line in enumerate(content.split("\n"), 1):
                    if any(p in line for p in ["api_key = ", "password = ", "token = "]):
                        if "triple_quote" not in line:
                            issues.append({"type": "security", "file": str(file_path), "line": i,
                                           "description": "Potential hardcoded secret", "severity": "critical"})

                import re
                imports = re.findall(r"^import (\w+)|^from (\w+)", content, re.MULTILINE)
                imported = [m[0] or m[1] for m in imports]
                for mod in imported:
                    if mod not in ["os", "sys", "json", "re", "typing"]:
                        usage = content.count(mod + ".") + content.count(" " + mod + " ")
                        if usage < 2:
                            issues.append({"type": "code_quality", "file": str(file_path), "line": 1,
                                           "description": f"Potentially unused import: {mod}", "severity": "low"})
            except Exception as e:
                issues.append({"type": "error", "file": str(file_path),
                               "description": f"Failed to analyze: {e}", "severity": "low"})

        severity_order = {"critical": 0, "high": 1, "medium": 2, "low": 3}
        issues.sort(key=lambda x: severity_order.get(x["severity"], 4))

        return {"total_files": len(py_files), "total_issues": len(issues),
                "critical": len([i for i in issues if i["severity"] == "critical"]),
                "high": len([i for i in issues if i["severity"] == "high"]),
                "medium": len([i for i in issues if i["severity"] == "medium"]),
                "low": len([i for i in issues if i["severity"] == "low"]),
                "issues": issues[:50]}

    def create_backup(self, file_path: str) -> str:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_name = f"{Path(file_path).stem}_{timestamp}{Path(file_path).suffix}"
        backup_path = os.path.join(self.backup_dir, backup_name)
        shutil.copy2(file_path, backup_path)
        return backup_path

    def propose_fix(self, issue: Dict) -> Dict:
        from core.aevibron_client import aevibron
        file_path = issue["file"]
        line_num = issue.get("line", 1)
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                lines = f.readlines()
                context = "".join(lines[max(0, line_num-5):min(len(lines), line_num+5)])
        except:
            return {"success": False, "error": "Could not read file"}

        prompt = f"""Fix this code issue:

File: {file_path}
Line: {line_num}
Issue: {issue['description']}

Context:
```python
{context}
```

Provide ONLY the fixed code. No explanations."""
        response = aevibron.fast_response(prompt)
        fix_code = response.get("choices", [{}])[0].get("message", {}).get("content", "")
        return {"success": True, "original_issue": issue, "proposed_fix": fix_code,
                "file": file_path, "line": line_num}

    def apply_fix(self, file_path: str, old_text: str, new_text: str) -> ToolResult:
        try:
            backup_path = self.create_backup(file_path)
            with open(file_path, "r", encoding="utf-8") as f:
                content = f.read()
            if old_text not in content:
                return ToolResult(False, error="Old text not found in file")
            new_content = content.replace(old_text, new_text, 1)
            sandbox_file = os.path.join(self.sandbox_dir, Path(file_path).name)
            with open(sandbox_file, "w", encoding="utf-8") as f:
                f.write(new_content)
            test_result = self._test_file(sandbox_file)
            if test_result["success"]:
                with open(file_path, "w", encoding="utf-8") as f:
                    f.write(new_content)
                self._log_change(file_path, old_text, new_text, backup_path, "success")
                return ToolResult(True, data={"file": file_path, "backup": backup_path, "test_result": test_result})
            else:
                return ToolResult(False, error=f"Tests failed: {test_result['error']}",
                                  data={"file": file_path, "test_result": test_result})
        except Exception as e:
            return ToolResult(False, error=str(e))

    def _test_file(self, file_path: str) -> Dict:
        try:
            result = subprocess.run(["python", "-m", "py_compile", file_path],
                                    capture_output=True, text=True, timeout=10)
            if result.returncode == 0:
                return {"success": True, "message": "Syntax valid"}
            return {"success": False, "error": result.stderr}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def rollback(self, file_path: str, backup_path: str) -> ToolResult:
        try:
            shutil.copy2(backup_path, file_path)
            return ToolResult(True, data={"restored": file_path, "from": backup_path})
        except Exception as e:
            return ToolResult(False, error=str(e))

    def self_diagnose_and_fix(self) -> Dict:
        analysis = self.analyze_self()
        if analysis["critical"] == 0 and analysis["high"] == 0:
            return {"success": True, "message": "No critical issues. IRIS is healthy.", "analysis": analysis}
        fixes_applied = []
        fixes_failed = []
        for issue in analysis["issues"]:
            if issue["severity"] in ["critical", "high"]:
                proposal = self.propose_fix(issue)
                if proposal.get("success"):
                    result = self.apply_fix(issue["file"], issue.get("description", ""), proposal["proposed_fix"])
                    if result.success:
                        fixes_applied.append(issue)
                    else:
                        fixes_failed.append({"issue": issue, "error": result.error})
        return {"success": len(fixes_failed) == 0, "fixes_applied": len(fixes_applied),
                "fixes_failed": len(fixes_failed), "applied": fixes_applied,
                "failed": fixes_failed, "analysis": analysis}

    def _log_change(self, file_path: str, old_text: str, new_text: str, backup: str, status: str):
        change = {"timestamp": datetime.now().isoformat(), "file": file_path,
                  "old": old_text[:200], "new": new_text[:200], "backup": backup, "status": status}
        self.change_log.append(change)
        log_file = os.path.join(config.SELF_DIR, "improvements.md")
        with open(log_file, "a", encoding="utf-8") as f:
            f.write(f"""
## {change['timestamp']}

**File:** `{file_path}`
**Status:** {status}

""")
        db.save_episode(f"Self-modified {Path(file_path).name}",
                        emotion="determination" if status == "success" else "concern",
                        lesson=f"{'Successfully' if status == 'success' else 'Failed to'} modify own code")

    def get_change_history(self) -> List[Dict]:
        return self.change_log

    def get_own_codebase_map(self) -> Dict:
        py_files = []
        total_lines = 0
        for file_path in Path(config.BASE_DIR).rglob("*.py"):
            if "__pycache__" in str(file_path):
                continue
            try:
                with open(file_path, "r", encoding="utf-8") as f:
                    lines = f.readlines()
                    line_count = len(lines)
                    total_lines += line_count
                    classes = []
                    functions = []
                    for i, line in enumerate(lines):
                        stripped = line.strip()
                        if stripped.startswith("class "):
                            classes.append({"name": stripped.split("(")[0].replace("class ", ""), "line": i+1})
                        elif stripped.startswith("def ") and not stripped.startswith("def __"):
                            functions.append({"name": stripped.split("(")[0].replace("def ", ""), "line": i+1})
                    py_files.append({"path": str(file_path.relative_to(config.BASE_DIR)),
                                     "lines": line_count, "classes": classes, "functions": functions})
            except:
                pass
        return {"total_files": len(py_files), "total_lines": total_lines, "files": py_files}

self_improvement = SelfImprovementEngine()
