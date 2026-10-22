"""Autonomous Tools Skill — Hermes-style code/shell/file/git operations + self-healing loop.

Capabilities:
  git_clone, git_read_file, git_edit_file, git_push, git_create_repo,
  execute_shell, execute_python, edit_own_code, vercel_deploy,
  read_file, write_file, list_directory, browse_url, autonomous_build
"""
from __future__ import annotations
import logging, os, sys, subprocess, tempfile, shutil
from typing import Any, Dict

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "..", ".."))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from skills import BaseSkill

logger = logging.getLogger(__name__)


class AutonomousToolsSkill(BaseSkill):
    """Hermes-style autonomous operations: git, shell, file, deploy, self-healing loop."""

    def __init__(self):
        super().__init__(
            name="autonomous_tools",
            category="productivity",
            capabilities=[
                "git_clone", "git_read_file", "git_edit_file", "git_push",
                "git_create_repo", "execute_shell", "execute_python",
                "edit_own_code", "vercel_deploy", "read_file", "write_file",
                "list_directory", "browse_url", "autonomous_build",
            ],
        )

    def init(self) -> bool:
        return True

    def shutdown(self) -> bool:
        return True

    def execute(self, capability: str, params: Dict[str, Any]) -> Dict[str, Any]:
        try:
            if capability == "git_clone":
                return self._git_clone(params)
            elif capability == "git_read_file":
                return self._git_read_file(params)
            elif capability == "git_edit_file":
                return self._git_edit_file(params)
            elif capability == "git_push":
                return self._git_push(params)
            elif capability == "git_create_repo":
                return self._git_create_repo(params)
            elif capability == "execute_shell":
                return self._execute_shell(params)
            elif capability == "execute_python":
                return self._execute_python(params)
            elif capability == "edit_own_code":
                return self._edit_own_code(params)
            elif capability == "vercel_deploy":
                return self._vercel_deploy(params)
            elif capability == "read_file":
                return self._read_file(params)
            elif capability == "write_file":
                return self._write_file(params)
            elif capability == "list_directory":
                return self._list_directory(params)
            elif capability == "browse_url":
                return self._browse_url(params)
            elif capability == "autonomous_build":
                from modules.autonomous_loop import execute_autonomous_build
                return execute_autonomous_build(params)
            return {"success": False, "error": f"Unknown capability: {capability}"}
        except Exception as e:
            logger.exception("AutonomousToolsSkill.execute failed for %s", capability)
            return {"success": False, "error": str(e), "capability": capability}

    def _git_clone(self, params):
        repo_url = params.get("repo_url") or params.get("url")
        target_path = params.get("target_path") or params.get("path")
        if not repo_url or not target_path:
            return {"success": False, "error": "repo_url and target_path required"}
        if os.path.exists(target_path):
            return {"success": False, "error": f"target_path already exists: {target_path}"}
        try:
            result = subprocess.run(
                ["git", "clone", "--depth", "1", repo_url, target_path],
                capture_output=True, text=True, timeout=120)
            return {"success": result.returncode == 0, "repo_url": repo_url,
                    "target_path": target_path,
                    "stdout": result.stdout[-2000:] if result.stdout else "",
                    "stderr": result.stderr[-2000:] if result.stderr else ""}
        except subprocess.TimeoutExpired:
            return {"success": False, "error": "git clone timed out (120s)"}
        except FileNotFoundError:
            return {"success": False, "error": "git binary not found"}

    def _git_read_file(self, params):
        repo_path = params.get("repo_path") or params.get("target_path")
        file_path = params.get("file_path") or params.get("path")
        if not repo_path or not file_path:
            return {"success": False, "error": "repo_path and file_path required"}
        full_path = os.path.join(repo_path, file_path.lstrip("/"))
        if ".." in file_path or not os.path.realpath(full_path).startswith(os.path.realpath(repo_path)):
            return {"success": False, "error": "path traversal detected"}
        try:
            with open(full_path, "r", errors="replace") as f:
                content = f.read()
            return {"success": True, "path": file_path, "content": content, "size": len(content)}
        except FileNotFoundError:
            return {"success": False, "error": f"file not found: {file_path}"}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def _git_edit_file(self, params):
        repo_path = params.get("repo_path") or params.get("target_path")
        file_path = params.get("file_path") or params.get("path")
        old_text = params.get("old_text")
        new_text = params.get("new_text")
        new_content = params.get("new_content")
        if not repo_path or not file_path:
            return {"success": False, "error": "repo_path and file_path required"}
        full_path = os.path.join(repo_path, file_path.lstrip("/"))
        if ".." in file_path or not os.path.realpath(full_path).startswith(os.path.realpath(repo_path)):
            return {"success": False, "error": "path traversal detected"}
        try:
            with open(full_path, "r", errors="replace") as f:
                content = f.read()
            if new_content is not None:
                updated = new_content
            elif old_text is not None and new_text is not None:
                if old_text not in content:
                    return {"success": False, "error": "old_text not found in file"}
                updated = content.replace(old_text, new_text, 1)
            else:
                return {"success": False, "error": "either new_content OR (old_text + new_text) required"}
            with open(full_path, "w") as f:
                f.write(updated)
            return {"success": True, "path": file_path, "size": len(updated)}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def _git_push(self, params):
        repo_path = params.get("repo_path") or params.get("path")
        message = params.get("message", "IRIS autonomous commit")
        if not repo_path:
            return {"success": False, "error": "repo_path required"}
        try:
            subprocess.run(["git", "add", "-A"], cwd=repo_path, capture_output=True, timeout=30)
            r1 = subprocess.run(["git", "commit", "-m", message], cwd=repo_path, capture_output=True, text=True, timeout=30)
            r2 = subprocess.run(["git", "push"], cwd=repo_path, capture_output=True, text=True, timeout=60)
            return {"success": r2.returncode == 0,
                    "commit_stdout": r1.stdout[-500:], "push_stdout": r2.stdout[-500:],
                    "push_stderr": r2.stderr[-500:]}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def _git_create_repo(self, params):
        name = params.get("name")
        description = params.get("description", "")
        private = params.get("private", False)
        if not name:
            return {"success": False, "error": "name required"}
        try:
            from github import Github
            token = os.environ.get("GITHUB_TOKEN")
            if not token:
                return {"success": False, "error": "GITHUB_TOKEN env var not set"}
            g = Github(token)
            user = g.get_user()
            repo = user.create_repo(name, description=description, private=private, auto_init=True)
            return {"success": True, "repo": repo.full_name, "url": repo.html_url}
        except ImportError:
            return {"success": False, "error": "PyGithub not installed (pip install PyGithub)"}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def _execute_shell(self, params):
        command = params.get("command")
        if not command:
            return {"success": False, "error": "command required"}
        blocked = ["rm -rf /", "mkfs", "dd if=/dev/zero", ">/dev/sd", ":(){:|:&};:"]
        for bad in blocked:
            if bad in command:
                return {"success": False, "error": f"refused: blocked pattern '{bad}'"}
        timeout = int(params.get("timeout", 30))
        cwd = params.get("cwd")
        try:
            result = subprocess.run(command, shell=True, capture_output=True, text=True, timeout=timeout, cwd=cwd)
            return {"success": result.returncode == 0, "exit_code": result.returncode,
                    "stdout": result.stdout[-5000:] if result.stdout else "",
                    "stderr": result.stderr[-5000:] if result.stderr else ""}
        except subprocess.TimeoutExpired:
            return {"success": False, "error": f"command timed out ({timeout}s)"}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def _execute_python(self, params):
        code = params.get("code")
        if not code:
            return {"success": False, "error": "code required"}
        timeout = int(params.get("timeout", 30))
        with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as f:
            f.write(code); temp_path = f.name
        try:
            result = subprocess.run([sys.executable, temp_path], capture_output=True, text=True, timeout=timeout)
            return {"success": result.returncode == 0, "exit_code": result.returncode,
                    "stdout": result.stdout[-5000:] if result.stdout else "",
                    "stderr": result.stderr[-5000:] if result.stderr else ""}
        except subprocess.TimeoutExpired:
            return {"success": False, "error": f"execution timed out ({timeout}s)"}
        finally:
            os.unlink(temp_path)

    def _edit_own_code(self, params):
        file_path = params.get("file_path")
        old_text = params.get("old_text")
        new_text = params.get("new_text")
        if not file_path or not old_text or not new_text:
            return {"success": False, "error": "file_path, old_text, new_text required"}
        full_path = os.path.join(PROJECT_ROOT, file_path.lstrip("/"))
        if ".." in file_path:
            return {"success": False, "error": "path traversal detected"}
        try:
            import py_compile
            backup_path = full_path + ".iris-backup"
            shutil.copy2(full_path, backup_path)
            with open(full_path, "r") as f:
                content = f.read()
            if old_text not in content:
                return {"success": False, "error": "old_text not found", "file": file_path}
            updated = content.replace(old_text, new_text, 1)
            with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as tf:
                tf.write(updated); temp_py = tf.name
            try:
                py_compile.compile(temp_py, doraise=True)
            except py_compile.PyCompileError as e:
                os.unlink(temp_py)
                shutil.move(backup_path, full_path)
                return {"success": False, "error": f"would break syntax: {e}", "rolled_back": True}
            os.unlink(temp_py)
            with open(full_path, "w") as f:
                f.write(updated)
            return {"success": True, "file": file_path, "backup": backup_path}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def _vercel_deploy(self, params):
        project_path = params.get("project_path", os.getcwd())
        token = os.environ.get("VERCEL_TOKEN")
        if not token:
            return {"success": False, "error": "VERCEL_TOKEN env var not set"}
        try:
            result = subprocess.run(["npx", "vercel", "--token", token, "--yes", "--prod"],
                                     cwd=project_path, capture_output=True, text=True, timeout=180)
            return {"success": result.returncode == 0,
                    "url": result.stdout.strip() if result.returncode == 0 else None,
                    "stdout": result.stdout[-2000:], "stderr": result.stderr[-2000:]}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def _read_file(self, params):
        path = params.get("path")
        if not path:
            return {"success": False, "error": "path required"}
        try:
            with open(path, "r", errors="replace") as f:
                content = f.read()
            return {"success": True, "path": path, "content": content, "size": len(content)}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def _write_file(self, params):
        path = params.get("path")
        content = params.get("content", "")
        append = params.get("append", False)
        if not path:
            return {"success": False, "error": "path required"}
        try:
            mode = "a" if append else "w"
            with open(path, mode) as f:
                f.write(content)
            return {"success": True, "path": path, "size": len(content), "appended": append}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def _list_directory(self, params):
        path = params.get("path", ".")
        try:
            entries = []
            for entry in sorted(os.listdir(path)):
                full = os.path.join(path, entry)
                entries.append({"name": entry,
                                "type": "dir" if os.path.isdir(full) else "file",
                                "size": os.path.getsize(full) if os.path.isfile(full) else None})
            return {"success": True, "path": path, "entries": entries, "count": len(entries)}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def _browse_url(self, params):
        import urllib.request, re
        url = params.get("url")
        if not url:
            return {"success": False, "error": "url required"}
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "IRIS/1.0"})
            with urllib.request.urlopen(req, timeout=15) as resp:
                html = resp.read().decode("utf-8", errors="replace")
            text = re.sub(r"<script[^>]*>[\s\S]*?</script>", " ", html, flags=re.IGNORECASE)
            text = re.sub(r"<style[^>]*>[\s\S]*?</style>", " ", text, flags=re.IGNORECASE)
            text = re.sub(r"<[^>]+>", " ", text)
            text = re.sub(r"\s+", " ", text).strip()
            title = re.search(r"<title>([^<]*)</title>", html, re.IGNORECASE)
            return {"success": True, "url": url,
                    "title": title.group(1) if title else "",
                    "text": text[:5000], "size": len(html)}
        except Exception as e:
            return {"success": False, "error": str(e)}
