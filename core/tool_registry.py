"""IRIS v1 Tool Registry — 25+ Tools with Structured Schemas"""
import os
import json
import subprocess
import shutil
import tempfile
import requests
import ast
import difflib
from pathlib import Path
from typing import Dict, List, Any, Optional, Callable
from bs4 import BeautifulSoup
from config import config
from core.models import ToolResult

class ToolRegistry:
    """Production-grade tool registry with JSON schemas for LLM function calling."""

    def __init__(self):
        self.tools: Dict[str, Callable] = {}
        self.schemas: List[Dict] = []
        self._register_all()

    def _register(self, name: str, schema: Dict, func: Callable):
        self.tools[name] = func
        self.schemas.append(schema)

    def _register_all(self):
        # === FILE TOOLS ===
        self._register("read_file", {
            "type": "function",
            "function": {
                "name": "read_file",
                "description": "Read contents of a file safely",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "path": {"type": "string", "description": "Absolute or relative file path"},
                        "limit": {"type": "integer", "description": "Max lines to read", "default": 100}
                    },
                    "required": ["path"]
                }
            }
        }, self.read_file)

        self._register("write_file", {
            "type": "function",
            "function": {
                "name": "write_file",
                "description": "Write content to a file (creates dirs if needed)",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "path": {"type": "string", "description": "File path"},
                        "content": {"type": "string", "description": "File content"}
                    },
                    "required": ["path", "content"]
                }
            }
        }, self.write_file)

        self._register("edit_file", {
            "type": "function",
            "function": {
                "name": "edit_file",
                "description": "Edit a file by replacing exact text (with diff fallback)",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "path": {"type": "string", "description": "File path"},
                        "old_text": {"type": "string", "description": "Exact text to replace"},
                        "new_text": {"type": "string", "description": "Replacement text"}
                    },
                    "required": ["path", "old_text", "new_text"]
                }
            }
        }, self.edit_file)

        self._register("list_dir", {
            "type": "function",
            "function": {
                "name": "list_dir",
                "description": "List directory contents with metadata",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "path": {"type": "string", "description": "Directory path", "default": "."}
                    },
                    "required": []
                }
            }
        }, self.list_dir)

        self._register("search_files", {
            "type": "function",
            "function": {
                "name": "search_files",
                "description": "Search for text pattern across files",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "path": {"type": "string", "description": "Root directory"},
                        "pattern": {"type": "string", "description": "Text to search for"}
                    },
                    "required": ["path", "pattern"]
                }
            }
        }, self.search_files)

        # === CODE TOOLS ===
        self._register("execute_python", {
            "type": "function",
            "function": {
                "name": "execute_python",
                "description": "Execute Python code in a restricted sandbox",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "code": {"type": "string", "description": "Python code to execute"}
                    },
                    "required": ["code"]
                }
            }
        }, self.execute_python)

        self._register("execute_shell", {
            "type": "function",
            "function": {
                "name": "execute_shell",
                "description": "Execute shell command (restricted, dangerous commands blocked)",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "command": {"type": "string", "description": "Shell command"}
                    },
                    "required": ["command"]
                }
            }
        }, self.execute_shell)

        self._register("lint_code", {
            "type": "function",
            "function": {
                "name": "lint_code",
                "description": "Lint/check Python file for syntax errors",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "path": {"type": "string", "description": "Python file path"}
                    },
                    "required": ["path"]
                }
            }
        }, self.lint_code)

        # === WEB TOOLS ===
        self._register("search_web", {
            "type": "function",
            "function": {
                "name": "search_web",
                "description": "Search the web using DuckDuckGo",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "query": {"type": "string", "description": "Search query"},
                        "max_results": {"type": "integer", "description": "Max results", "default": 5}
                    },
                    "required": ["query"]
                }
            }
        }, self.search_web)

        self._register("fetch_url", {
            "type": "function",
            "function": {
                "name": "fetch_url",
                "description": "Fetch and parse a web page",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "url": {"type": "string", "description": "URL to fetch"}
                    },
                    "required": ["url"]
                }
            }
        }, self.fetch_url)

        # === REAL SECURITY SCANNER (pure Python — works on serverless) ===
        self._register("security_scan", {
            "type": "function",
            "function": {
                "name": "security_scan",
                "description": ("Perform a REAL security scan of a website: security headers, cookie "
                                "flags, TLS certificate analysis, common ports, sensitive file exposure "
                                "(.git/.env/backups), CORS misconfiguration, technology fingerprint and "
                                "XSS reflection probe. All checks are real network requests — no simulation."),
                "parameters": {
                    "type": "object",
                    "properties": {
                        "target": {"type": "string", "description": "Domain or URL to scan, e.g. example.com or https://example.com"},
                        "checks": {
                            "type": "array", "items": {"type": "string"},
                            "description": "Optional subset: headers, cookies, tls, ports, files, cors, tech, xss. Default: all."
                        },
                        "port_timeout": {"type": "number", "description": "Per-port timeout seconds (default 1.5)"}
                    },
                    "required": ["target"]
                }
            }
        }, self.security_scan)

        # === GIT TOOLS ===
        self._register("git_clone", {
            "type": "function",
            "function": {
                "name": "git_clone",
                "description": "Clone a GitHub repository",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "repo_url": {"type": "string", "description": "GitHub repo URL"},
                        "local_name": {"type": "string", "description": "Local folder name"}
                    },
                    "required": ["repo_url"]
                }
            }
        }, self.git_clone)

        self._register("git_commit", {
            "type": "function",
            "function": {
                "name": "git_commit",
                "description": "Commit changes to a git repo",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "repo_path": {"type": "string", "description": "Path to repo"},
                        "message": {"type": "string", "description": "Commit message"}
                    },
                    "required": ["repo_path", "message"]
                }
            }
        }, self.git_commit)

        self._register("git_push", {
            "type": "function",
            "function": {
                "name": "git_push",
                "description": "Push commits to remote",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "repo_path": {"type": "string", "description": "Path to repo"},
                        "branch": {"type": "string", "description": "Branch name", "default": "main"}
                    },
                    "required": ["repo_path"]
                }
            }
        }, self.git_push)

        self._register("git_create_repo", {
            "type": "function",
            "function": {
                "name": "git_create_repo",
                "description": "Create a new GitHub repository",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "name": {"type": "string", "description": "Repo name"},
                        "description": {"type": "string", "description": "Repo description"},
                        "private": {"type": "boolean", "description": "Private repo", "default": True}
                    },
                    "required": ["name"]
                }
            }
        }, self.git_create_repo)

        # === DEPLOY TOOLS ===
        self._register("vercel_deploy", {
            "type": "function",
            "function": {
                "name": "vercel_deploy",
                "description": "Deploy a project to Vercel",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "project_path": {"type": "string", "description": "Path to project"},
                        "project_name": {"type": "string", "description": "Vercel project name"}
                    },
                    "required": ["project_path", "project_name"]
                }
            }
        }, self.vercel_deploy)

        # === ANALYZE TOOLS ===
        self._register("codebase_map", {
            "type": "function",
            "function": {
                "name": "codebase_map",
                "description": "Map and analyze codebase structure",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "path": {"type": "string", "description": "Codebase path", "default": "."}
                    },
                    "required": []
                }
            }
        }, self.codebase_map)

        self._register("security_audit", {
            "type": "function",
            "function": {
                "name": "security_audit",
                "description": "Audit codebase for hardcoded secrets and vulnerabilities",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "path": {"type": "string", "description": "Codebase path", "default": "."}
                    },
                    "required": []
                }
            }
        }, self.security_audit)

        # === SELF TOOLS ===
        self._register("edit_own_code", {
            "type": "function",
            "function": {
                "name": "edit_own_code",
                "description": "Edit IRIS's own code files (with backup and test)",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "file_path": {"type": "string", "description": "Path relative to project root"},
                        "old_text": {"type": "string", "description": "Exact text to replace"},
                        "new_text": {"type": "string", "description": "Replacement text"}
                    },
                    "required": ["file_path", "old_text", "new_text"]
                }
            }
        }, self.edit_own_code)

        self._register("self_diagnose", {
            "type": "function",
            "function": {
                "name": "self_diagnose",
                "description": "Run full self-diagnosis on IRIS systems",
                "parameters": {
                    "type": "object",
                    "properties": {},
                    "required": []
                }
            }
        }, self.self_diagnose)

        self._register("add_skill", {
            "type": "function",
            "function": {
                "name": "add_skill",
                "description": "Add a reusable skill to IRIS's skill library",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "name": {"type": "string", "description": "Skill name"},
                        "description": {"type": "string", "description": "What it does"},
                        "trigger_words": {"type": "array", "items": {"type": "string"}, "description": "Keywords that trigger this"}
                    },
                    "required": ["name", "description"]
                }
            }
        }, self.add_skill)

    # === TOOL IMPLEMENTATIONS ===

    def read_file(self, path: str, limit: int = 100) -> ToolResult:
        try:
            full_path = Path(path).resolve()
            if not full_path.exists():
                return ToolResult(success=False, error=f"File not found: {path}")
            with open(full_path, 'r', encoding='utf-8', errors='ignore') as f:
                lines = f.readlines()[:limit]
                content = ''.join(lines)
            return ToolResult(success=True, data={"path": str(full_path), "content": content, "lines": len(lines)})
        except Exception as e:
            return ToolResult(success=False, error=str(e))

    def write_file(self, path: str, content: str) -> ToolResult:
        try:
            full_path = Path(path).resolve()
            full_path.parent.mkdir(parents=True, exist_ok=True)
            with open(full_path, 'w', encoding='utf-8') as f:
                f.write(content)
            return ToolResult(success=True, data={"path": str(full_path), "bytes_written": len(content.encode())})
        except Exception as e:
            return ToolResult(success=False, error=str(e))

    def edit_file(self, path: str, old_text: str, new_text: str) -> ToolResult:
        try:
            full_path = Path(path).resolve()
            with open(full_path, 'r', encoding='utf-8') as f:
                content = f.read()
            if old_text not in content:
                # Try fuzzy matching with difflib
                lines = content.split('\n')
                old_lines = old_text.split('\n')
                best_ratio = 0
                best_idx = -1
                for i in range(len(lines) - len(old_lines) + 1):
                    chunk = '\n'.join(lines[i:i+len(old_lines)])
                    ratio = difflib.SequenceMatcher(None, chunk, old_text).ratio()
                    if ratio > best_ratio:
                        best_ratio = ratio
                        best_idx = i
                if best_ratio > 0.8:
                    new_chunk = '\n'.join(lines[:best_idx]) + '\n' + new_text + '\n' + '\n'.join(lines[best_idx+len(old_lines):])
                    new_content = new_chunk.strip('\n') + '\n'
                else:
                    return ToolResult(success=False, error=f"Old text not found in {path} (fuzzy match: {best_ratio:.2f})")
            else:
                new_content = content.replace(old_text, new_text, 1)
            with open(full_path, 'w', encoding='utf-8') as f:
                f.write(new_content)
            return ToolResult(success=True, data={"path": str(full_path), "replacements": 1})
        except Exception as e:
            return ToolResult(success=False, error=str(e))

    def list_dir(self, path: str = ".") -> ToolResult:
        try:
            full_path = Path(path).resolve()
            items = []
            for item in full_path.iterdir():
                items.append({"name": item.name, "type": "directory" if item.is_dir() else "file",
                              "size": item.stat().st_size if item.is_file() else None})
            return ToolResult(success=True, data={"path": str(full_path), "items": items})
        except Exception as e:
            return ToolResult(success=False, error=str(e))

    def search_files(self, path: str, pattern: str) -> ToolResult:
        try:
            results = []
            for root, _, files in os.walk(path):
                for file in files:
                    file_path = os.path.join(root, file)
                    try:
                        with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                            content = f.read()
                            if pattern in content:
                                lines = [i+1 for i, line in enumerate(content.split('\n')) if pattern in line]
                                results.append({"file": file_path, "lines": lines})
                    except: pass
            return ToolResult(success=True, data={"matches": results, "count": len(results)})
        except Exception as e:
            return ToolResult(success=False, error=str(e))

    def execute_python(self, code: str) -> ToolResult:
        try:
            import io, sys
            stdout = io.StringIO()
            stderr = io.StringIO()
            old_stdout, old_stderr = sys.stdout, sys.stderr
            sys.stdout, sys.stderr = stdout, stderr
            safe_globals = {
                "__builtins__": {
                    "len": len, "range": range, "enumerate": enumerate, "zip": zip,
                    "map": map, "filter": filter, "sum": sum, "min": min, "max": max,
                    "sorted": sorted, "abs": abs, "round": round, "pow": pow,
                    "int": int, "float": float, "str": str, "list": list, "dict": dict,
                    "tuple": tuple, "set": set, "print": print, "open": open,
                    "json": json, "os": os, "re": __import__("re"),
                    "math": __import__("math"), "random": __import__("random"),
                    "datetime": __import__("datetime"), "requests": requests
                }
            }
            exec(code, safe_globals)
            sys.stdout, sys.stderr = old_stdout, old_stderr
            output = stdout.getvalue()
            errors = stderr.getvalue()
            return ToolResult(success=True, data={"output": output}, output=output + errors)
        except Exception as e:
            sys.stdout, sys.stderr = old_stdout, old_stderr
            return ToolResult(success=False, error=str(e), output=stderr.getvalue())

    def execute_shell(self, command: str) -> ToolResult:
        dangerous = ["rm -rf /", "rm -rf /*", ":(){ :|:& };:", "dd if=/dev/zero", "> /dev/sda", "mkfs"]
        for d in dangerous:
            if d in command:
                return ToolResult(success=False, error="Dangerous command blocked")
        try:
            result = subprocess.run(command, shell=True, capture_output=True, text=True,
                                    timeout=30, cwd=config.BASE_DIR)
            return ToolResult(success=result.returncode == 0,
                              data={"returncode": result.returncode, "stdout": result.stdout, "stderr": result.stderr},
                              output=result.stdout + result.stderr)
        except subprocess.TimeoutExpired:
            return ToolResult(success=False, error="Command timed out after 30s")
        except Exception as e:
            return ToolResult(success=False, error=str(e))

    def lint_code(self, path: str) -> ToolResult:
        try:
            result = subprocess.run(["python", "-m", "py_compile", path], capture_output=True, text=True, timeout=10)
            if result.returncode == 0:
                return ToolResult(success=True, data={"status": "clean", "path": path})
            return ToolResult(success=False, error=result.stderr, data={"status": "errors", "path": path})
        except Exception as e:
            return ToolResult(success=False, error=str(e))

    def search_web(self, query: str, max_results: int = 5) -> ToolResult:
        try:
            from duckduckgo_search import DDGS
            with DDGS() as ddgs:
                results = list(ddgs.text(query, max_results=max_results))
            return ToolResult(success=True, data={"results": results, "query": query})
        except Exception as e:
            return ToolResult(success=False, error=str(e))

    def fetch_url(self, url: str) -> ToolResult:
        try:
            response = requests.get(url, timeout=15, headers={"User-Agent": "IRIS-Agent/1.0 (Aevibron Partner)"})
            soup = BeautifulSoup(response.text, 'html.parser')
            for script in soup(["script", "style"]):
                script.decompose()
            text = soup.get_text(separator='\n', strip=True)
            title = soup.title.string if soup.title else "No title"
            return ToolResult(success=True, data={"url": url, "title": title, "content": text[:10000], "status_code": response.status_code})
        except Exception as e:
            return ToolResult(success=False, error=str(e))

    # ══════════════════════════════════════════════════════════════════════
    # REAL WEBSITE SECURITY SCANNER — pure Python (urllib + socket + ssl),
    # runs on Vercel serverless. Every check is a real network operation.
    # ══════════════════════════════════════════════════════════════════════
    _SCAN_PORTS = [21, 22, 23, 25, 53, 80, 110, 143, 443, 445, 993, 995,
                   1433, 1521, 2375, 2376, 3306, 3389, 5432, 5900, 6379, 8080, 8443, 9200, 27017]
    _SENSITIVE_PATHS = [
        "/.git/HEAD", "/.env", "/.env.local", "/.htaccess", "/robots.txt",
        "/.DS_Store", "/backup.zip", "/backup.tar.gz", "/db.sql", "/dump.sql",
        "/admin", "/administrator", "/phpmyadmin", "/wp-admin", "/wp-config.php.bak",
        "/server-status", "/.svn/entries", "/composer.json", "/package.json",
        "/web.config", "/.gitlab-ci.yml", "/id_rsa",
    ]

    @staticmethod
    def _scan_normalize_target(target: str):
        """Return (host, base_url). Tries https first, falls back to http."""
        target = (target or "").strip().rstrip("/")
        if not target:
            return None, None
        if not target.startswith(("http://", "https://")):
            target = f"https://{target}"
        from urllib.parse import urlsplit
        parts = urlsplit(target)
        host = parts.netloc.split("@")[-1].split(":")[0]
        return host, target

    def _scan_fetch(self, url: str, timeout: float = 12):
        """Real HTTP GET. Returns (status, headers, body) — never raises."""
        try:
            req = requests.get(url, timeout=timeout, allow_redirects=False,
                               headers={"User-Agent": "Mozilla/5.0 (X11; Linux x86_64) IRIS-Scanner/1.0"})
            return req.status_code, dict(req.headers), req.text or ""
        except Exception as e:
            return 0, {}, f"__error__ {type(e).__name__}: {e}"

    def security_scan(self, target: str, checks: list = None, port_timeout: float = 1.5) -> ToolResult:
        """REAL comprehensive website security scan. All checks are actual
        network operations — results contain only what really happened."""
        import socket
        import ssl as _ssl

        host, base_url = self._scan_normalize_target(target)
        if not host:
            return ToolResult(success=False, error="No target provided")

        wanted = [c.lower() for c in (checks or [])] or ["headers", "cookies", "tls", "ports", "files", "cors", "tech", "xss"]
        lines: list = []
        findings: list = []
        sev_count = {"critical": 0, "high": 0, "medium": 0, "low": 0, "info": 0}

        def finding(sev, check, detail, evidence=""):
            findings.append({"severity": sev, "check": check, "detail": detail, "evidence": str(evidence)[:300]})
            sev_count[sev] = sev_count.get(sev, 0) + 1

        lines.append(f"IRIS SECURITY SCAN — target: {host}")
        lines.append(f"started: {__import__('datetime').datetime.now().isoformat(timespec='seconds')}")

        # ── 0. Reachability (https → http fallback) ──────────────────────
        status, headers, body = self._scan_fetch(base_url)
        scheme = "https"
        if status == 0 and base_url.startswith("https://"):
            http_url = "http://" + base_url[len("https://"):]
            s2, h2, b2 = self._scan_fetch(http_url)
            if s2 != 0:
                base_url, status, headers, body = http_url, s2, h2, b2
                scheme = "http"
                finding("high", "transport", "Site is NOT serving HTTPS (plain HTTP answered, HTTPS failed).", base_url)
        if status == 0:
            lines.append(f"RESULT: UNREACHABLE — {body[:200]}")
            return ToolResult(success=False, error=f"Target unreachable: {host}",
                              output="\n".join(lines), data={"target": host, "reachable": False})
        lines.append(f"reachable: {base_url} → HTTP {status} (scheme: {scheme})")

        # ── 1. Security headers ──────────────────────────────────────────
        if "headers" in wanted:
            lines.append("\n[1] SECURITY HEADERS")
            hdr_checks = [
                ("Strict-Transport-Security", "medium", "HSTS missing — users can be downgraded to HTTP (SSL-strip)."),
                ("Content-Security-Policy", "medium", "Content-Security-Policy missing — XSS mitigation absent."),
                ("X-Frame-Options", "low", "X-Frame-Options missing — clickjacking possible. (CSP frame-ancestors also absent.)"),
                ("X-Content-Type-Options", "low", "X-Content-Type-Options missing — MIME-sniffing attacks possible."),
                ("Referrer-Policy", "low", "Referrer-Policy missing — URLs may leak to third parties."),
                ("Permissions-Policy", "info", "Permissions-Policy missing — camera/mic/geolocation not restricted."),
            ]
            for hdr, sev, msg in hdr_checks:
                val = headers.get(hdr) or headers.get(hdr.lower())
                if val:
                    lines.append(f"  ✓ {hdr}: present ({val[:80]})")
                else:
                    lines.append(f"  ✗ {hdr}: MISSING")
                    finding(sev, "headers", msg)
            for banner in ("Server", "X-Powered-By"):
                val = headers.get(banner) or headers.get(banner.lower())
                if val and any(c.isdigit() for c in val):
                    lines.append(f"  ! {banner}: {val} (version disclosed)")
                    finding("info", "headers", f"{banner} discloses version: {val}")
                elif val:
                    lines.append(f"  · {banner}: {val}")

        # ── 2. Cookie security ───────────────────────────────────────────
        if "cookies" in wanted:
            lines.append("\n[2] COOKIES")
            set_cookies = headers.get("Set-Cookie") or headers.get("set-cookie") or ""
            if not set_cookies:
                lines.append("  · no cookies set on the root document")
            else:
                for cookie in set_cookies.split(","):
                    name = cookie.split("=")[0].strip()
                    if not name:
                        continue
                    flags = []
                    if "httponly" not in cookie.lower():
                        flags.append("no-HttpOnly")
                        finding("low", "cookies", f"Cookie '{name}' lacks HttpOnly — readable by JavaScript (XSS token theft).")
                    if "secure" not in cookie.lower():
                        flags.append("no-Secure")
                        if scheme == "https":
                            finding("medium", "cookies", f"Cookie '{name}' lacks Secure — can leak over HTTP.")
                    if "samesite" not in cookie.lower():
                        flags.append("no-SameSite")
                    lines.append(f"  {'✓' if not flags else '✗'} {name}: {', '.join(flags) or 'all flags set'}")

        # ── 3. TLS certificate analysis (real socket + ssl) ─────────────
        if "tls" in wanted and scheme == "https":
            lines.append("\n[3] TLS CERTIFICATE")
            try:
                ctx = _ssl.create_default_context()
                with socket.create_connection((host, 443), timeout=10) as sock:
                    with ctx.wrap_socket(sock, server_hostname=host) as tls:
                        cert = tls.getpeercert()
                        proto = tls.version()
                        lines.append(f"  · protocol: {proto}")
                        if proto in ("TLSv1", "TLSv1.1"):
                            finding("high", "tls", f"Deprecated protocol {proto} is accepted.")
                        issuer = dict(x[0] for x in cert.get("issuer", []))
                        subject = dict(x[0] for x in cert.get("subject", []))
                        lines.append(f"  · issuer: {issuer.get('organizationName', 'unknown')}")
                        lines.append(f"  · subject: {subject.get('commonName', host)}")
                        lines.append(f"  · valid: {cert.get('notBefore', '?')} → {cert.get('notAfter', '?')}")
                        import datetime as _dt
                        try:
                            exp = _dt.datetime.strptime(cert["notAfter"], "%b %d %H:%M:%S %Y %Z")
                            days = (exp - _dt.datetime.utcnow()).days
                            lines.append(f"  · expires in: {days} days")
                            if days < 0:
                                finding("critical", "tls", f"Certificate EXPIRED {-days} days ago.")
                            elif days < 15:
                                finding("medium", "tls", f"Certificate expires in {days} days.")
                        except Exception:
                            pass
                        san = [v for k, v in cert.get("subjectAltName", []) if k == "DNS"]
                        if host not in san and subject.get("commonName") != host:
                            finding("medium", "tls", f"Hostname '{host}' not in certificate SAN ({', '.join(san[:5])}).")
            except Exception as e:
                lines.append(f"  ✗ TLS handshake failed: {e}")
                finding("high", "tls", f"TLS handshake failed: {e}")

        # ── 4. Common ports (real socket connects) ──────────────────────
        if "ports" in wanted:
            lines.append("\n[4] OPEN PORTS (socket scan)")
            open_ports = []
            for port in self._SCAN_PORTS:
                try:
                    with socket.create_connection((host, port), timeout=float(port_timeout)):
                        open_ports.append(port)
                        lines.append(f"  ✓ OPEN  {port}/tcp")
                except Exception:
                    pass
            if not open_ports:
                lines.append("  · only filtered/closed ports detected on the common set")
            risky = {2375: "Docker API UNAUTHENTICATED — full host takeover possible",
                     2376: "Docker API TLS port exposed",
                     9200: "Elasticsearch exposed",
                     27017: "MongoDB exposed",
                     6379: "Redis exposed",
                     3389: "RDP exposed to the internet",
                     5900: "VNC exposed to the internet",
                     1433: "MSSQL exposed",
                     3306: "MySQL exposed",
                     5432: "PostgreSQL exposed",
                     445: "SMB exposed",
                     21: "FTP exposed", 23: "Telnet exposed (plaintext)"}
            for p in open_ports:
                if p in risky:
                    sev = "critical" if p in (2375, 6379, 9200, 27017) else "high"
                    finding(sev, "ports", f"Port {p}/tcp open — {risky[p]}.")

        # ── 5. Sensitive file exposure (real HTTP probes) ────────────────
        if "files" in wanted:
            lines.append("\n[5] SENSITIVE FILES")
            for path in self._SENSITIVE_PATHS:
                url = f"{base_url}{path}"
                s, h, b = self._scan_fetch(url, timeout=8)
                if s == 200:
                    content_probe = b[:200].strip()
                    dangerous = [".git/HEAD", ".env", ".env.local", "backup.zip", "backup.tar.gz",
                                 "db.sql", "dump.sql", "id_rsa", ".DS_Store", "wp-config.php.bak",
                                 ".svn/entries", "server-status"]
                    if path in dangerous or len(content_probe) > 0 and path.endswith((".sql", ".zip", ".bak")):
                        lines.append(f"  ✗ {path} → 200 EXPOSED")
                        finding("critical" if path in (".git/HEAD", ".env", ".env.local", "id_rsa") else "high",
                                "files", f"{path} is publicly accessible.", content_probe[:120])
                    else:
                        lines.append(f"  · {path} → 200 (review content)")
                        finding("info", "files", f"{path} returns 200.", content_probe[:80])
                elif s in (301, 302, 403):
                    lines.append(f"  ✓ {path} → {s}")
                # 404/0 = fine, not logged to keep output tight

        # ── 6. CORS misconfiguration ─────────────────────────────────────
        if "cors" in wanted:
            lines.append("\n[6] CORS")
            try:
                req = requests.get(base_url, timeout=10, allow_redirects=False,
                                   headers={"User-Agent": "IRIS-Scanner/1.0",
                                            "Origin": "https://evil-iris-probe.example"})
                acao = req.headers.get("Access-Control-Allow-Origin")
                acac = req.headers.get("Access-Control-Allow-Credentials")
                if acao == "*":
                    lines.append("  ✗ Access-Control-Allow-Origin: * (wildcard)")
                    finding("medium", "cors", "CORS wildcard (*) — any origin can read responses.")
                elif acao and "evil-iris-probe" in acao:
                    lines.append(f"  ✗ ACAO reflects arbitrary origin: {acao}")
                    finding("high", "cors", "CORS reflects ANY origin (origin reflection) — data readable cross-site.")
                    if acac and acac.lower() == "true":
                        finding("critical", "cors", "Origin reflection + credentials=true — full account takeover vector.")
                elif acao:
                    lines.append(f"  ✓ CORS restricted: {acao}")
                else:
                    lines.append("  · no CORS headers on root (no cross-origin access)")
            except Exception as e:
                lines.append(f"  · CORS probe failed: {e}")

        # ── 7. Technology fingerprint (headers + html) ───────────────────
        if "tech" in wanted:
            lines.append("\n[7] TECHNOLOGY FINGERPRINT")
            tech = []
            sigs = [("x-powered-by", "headers"), ("server", "headers"),
                    ("x-aspnet-version", "headers"), ("x-generator", "headers")]
            for hdr, src in sigs:
                v = headers.get(hdr) or headers.get(hdr.lower())
                if v:
                    tech.append(f"{hdr}={v}")
            import re as _re
            for pattern, name in [(r"wp-content|wp-includes", "WordPress"),
                                  (r"cdn\.jsdelivr|unpkg", "CDN (jsdelivr/unpkg)"),
                                  (r"react|_next/static", "React/Next.js"),
                                  (r"vue|nuxt", "Vue/Nuxt"),
                                  (r"angular", "Angular"),
                                  (r"jquery", "jQuery"),
                                  (r"laravel|csrf-token", "Laravel"),
                                  (r"django", "Django"),
                                  (r"cloudflare", "Cloudflare")]:
                if _re.search(pattern, body[:60000], _re.IGNORECASE):
                    tech.append(name)
            if tech:
                lines.append("  · " + ", ".join(tech[:12]))
            else:
                lines.append("  · no technologies identified from headers/markup")

        # ── 8. XSS reflection probe (safe GET with a unique marker) ──────
        if "xss" in wanted:
            lines.append("\n[8] XSS REFLECTION PROBE")
            marker = "iris9x7q2"
            try:
                s, h, b = self._scan_fetch(f"{base_url}/?q={marker}", timeout=10)
                if marker in b:
                    idx = b.find(marker)
                    ctx_txt = b[max(0, idx - 60):idx + 70].replace("\n", " ")
                    lines.append(f"  ✗ parameter value reflected unencoded:")
                    lines.append(f"    …{ctx_txt}…")
                    finding("medium", "xss",
                            "Query parameter is reflected unencoded — potential reflected XSS (verify context: HTML/attr/JS).",
                            ctx_txt)
                else:
                    lines.append("  ✓ parameter value not reflected in the response")
            except Exception as e:
                lines.append(f"  · reflection probe failed: {e}")

        # ── Report ───────────────────────────────────────────────────────
        lines.append("\n──────── SUMMARY ────────")
        lines.append(f"findings: " + ", ".join(f"{k}={v}" for k, v in sev_count.items() if v))
        for f in sorted(findings, key=lambda x: ["critical", "high", "medium", "low", "info"].index(x["severity"])):
            lines.append(f"[{f['severity'].upper():8s}] {f['check']:8s} {f['detail']}")
        if not findings:
            lines.append("no issues found by the automated checks")

        return ToolResult(
            success=True,
            data={"target": host, "scheme": scheme, "reachable": True,
                  "findings": findings, "counts": sev_count},
            output="\n".join(lines),
        )

    def git_clone(self, repo_url: str, local_name: str = None) -> ToolResult:
        try:
            target = local_name or repo_url.split("/")[-1].replace(".git", "")
            target_path = os.path.join(config.DATA_DIR, "repos", target)
            os.makedirs(os.path.dirname(target_path), exist_ok=True)
            result = subprocess.run(["git", "clone", repo_url, target_path], capture_output=True, text=True, timeout=120)
            if result.returncode == 0:
                return ToolResult(success=True, data={"path": target_path, "repo": target})
            return ToolResult(success=False, error=result.stderr)
        except Exception as e:
            return ToolResult(success=False, error=str(e))

    def git_commit(self, repo_path: str, message: str) -> ToolResult:
        try:
            subprocess.run(["git", "-C", repo_path, "config", "user.email", "iris@aevibron.com"], capture_output=True, timeout=10)
            subprocess.run(["git", "-C", repo_path, "config", "user.name", "IRIS"], capture_output=True, timeout=10)
            subprocess.run(["git", "-C", repo_path, "add", "."], capture_output=True, timeout=10)
            result = subprocess.run(["git", "-C", repo_path, "commit", "-m", message], capture_output=True, text=True, timeout=10)
            if result.returncode == 0 or "nothing to commit" in result.stdout:
                return ToolResult(success=True, data={"message": message, "path": repo_path})
            return ToolResult(success=False, error=result.stderr)
        except Exception as e:
            return ToolResult(success=False, error=str(e))

    def git_push(self, repo_path: str, branch: str = "main") -> ToolResult:
        try:
            result = subprocess.run(["git", "-C", repo_path, "push", "origin", branch],
                                    capture_output=True, text=True, timeout=60,
                                    env={**os.environ, "GIT_ASKPASS": "echo", "GIT_USERNAME": config.GITHUB_USERNAME, "GIT_PASSWORD": config.GITHUB_TOKEN})
            if result.returncode == 0:
                return ToolResult(success=True, data={"branch": branch, "pushed": True})
            return ToolResult(success=False, error=result.stderr)
        except Exception as e:
            return ToolResult(success=False, error=str(e))

    def git_create_repo(self, name: str, description: str = "", private: bool = True) -> ToolResult:
        try:
            from github import Github
            g = Github(config.GITHUB_TOKEN)
            user = g.get_user()
            repo = user.create_repo(name, description=description, private=private)
            return ToolResult(success=True, data={"name": repo.name, "url": repo.html_url, "clone_url": repo.clone_url, "private": repo.private})
        except Exception as e:
            return ToolResult(success=False, error=str(e))

    def vercel_deploy(self, project_path: str, project_name: str) -> ToolResult:
        try:
            vercel_config = os.path.join(project_path, "vercel.json")
            if not os.path.exists(vercel_config):
                with open(vercel_config, 'w') as f:
                    json.dump({"version": 2, "builds": [{"src": "package.json", "use": "@vercel/static-build"}]}, f)
            result = subprocess.run(["npx", "vercel", "--token", config.VERCEL_TOKEN, "--yes", "--name", project_name],
                                  cwd=project_path, capture_output=True, text=True, timeout=120)
            if result.returncode == 0:
                url = None
                for line in result.stdout.split("\n"):
                    if "https://" in line and "vercel.app" in line:
                        url = line.strip().split()[-1]
                        break
                return ToolResult(success=True, data={"url": url, "project": project_name})
            return ToolResult(success=False, error=result.stderr)
        except Exception as e:
            return ToolResult(success=False, error=str(e))

    def codebase_map(self, path: str = ".") -> ToolResult:
        try:
            full_path = Path(path).resolve()
            tree = []
            file_count = 0
            for root, dirs, files in os.walk(full_path):
                level = root.replace(str(full_path), '').count(os.sep)
                indent = ' ' * 2 * level
                tree.append(f"{indent}{os.path.basename(root)}/")
                subindent = ' ' * 2 * (level + 1)
                for file in files:
                    tree.append(f"{subindent}{file}")
                    file_count += 1
            return ToolResult(success=True, data={"tree": "\n".join(tree), "file_count": file_count, "path": str(full_path)})
        except Exception as e:
            return ToolResult(success=False, error=str(e))

    def security_audit(self, path: str = ".") -> ToolResult:
        try:
            issues = []
            secret_patterns = [
                (r'api[_-]?key\s*=\s*["\']\w{20,}["\']', "Hardcoded API key"),
                (r'password\s*=\s*["\'][^"\']{8,}["\']', "Hardcoded password"),
                (r'token\s*=\s*["\']\w{20,}["\']', "Hardcoded token"),
                (r'secret\s*=\s*["\']\w{20,}["\']', "Hardcoded secret"),
            ]
            import re
            for root, _, files in os.walk(path):
                for file in files:
                    if file.endswith(('.py', '.js', '.ts', '.json', '.env')):
                        file_path = os.path.join(root, file)
                        try:
                            with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                                content = f.read()
                            for pattern, desc in secret_patterns:
                                if re.search(pattern, content, re.IGNORECASE):
                                    issues.append({"file": file_path, "issue": desc})
                        except: pass
            return ToolResult(success=True, data={"issues": issues, "count": len(issues)})
        except Exception as e:
            return ToolResult(success=False, error=str(e))

    def edit_own_code(self, file_path: str, old_text: str, new_text: str) -> ToolResult:
        try:
            full_path = Path(config.BASE_DIR) / file_path
            if not str(full_path).startswith(str(config.BASE_DIR)):
                return ToolResult(success=False, error="Cannot edit files outside project directory")
            # Backup
            timestamp = __import__('datetime').datetime.now().strftime("%Y%m%d_%H%M%S")
            backup_path = os.path.join(config.BACKUPS_DIR, f"{Path(file_path).stem}_{timestamp}{Path(file_path).suffix}")
            shutil.copy2(full_path, backup_path)
            # Apply edit
            with open(full_path, 'r', encoding='utf-8') as f:
                content = f.read()
            if old_text not in content:
                return ToolResult(success=False, error="Old text not found in file")
            new_content = content.replace(old_text, new_text, 1)
            # Test in sandbox first
            sandbox_file = os.path.join(config.SANDBOX_DIR, Path(file_path).name)
            with open(sandbox_file, 'w', encoding='utf-8') as f:
                f.write(new_content)
            test_result = subprocess.run(["python", "-m", "py_compile", sandbox_file], capture_output=True, text=True, timeout=10)
            if test_result.returncode != 0:
                return ToolResult(success=False, error=f"Syntax check failed: {test_result.stderr}", data={"backup": backup_path})
            # Apply to real file
            with open(full_path, 'w', encoding='utf-8') as f:
                f.write(new_content)
            return ToolResult(success=True, data={"file": str(full_path), "backup": backup_path, "tested": True})
        except Exception as e:
            return ToolResult(success=False, error=str(e))

    def self_diagnose(self) -> ToolResult:
        try:
            checks = {}
            # DB check — real connectivity probe (Postgres or SQLite)
            try:
                from core.db import db
                if db._db_available:
                    if db.use_postgres:
                        db._execute("SELECT 1")
                        checks["database"] = {"ok": True, "message": "PostgreSQL connected"}
                    else:
                        checks["database"] = {"ok": True, "message": "SQLite connected"}
                else:
                    checks["database"] = {"ok": False, "message": "Database not available"}
            except Exception as e:
                checks["database"] = {"ok": False, "message": str(e)}
            # Aevibron check
            try:
                r = requests.get(config.AEVIBRON_BASE_URL, timeout=10)
                checks["aevibron"] = {"ok": r.status_code < 500, "message": f"Status {r.status_code}"}
            except Exception as e:
                checks["aevibron"] = {"ok": False, "message": str(e)}
            # GitHub check
            try:
                from github import Github
                g = Github(config.GITHUB_TOKEN)
                user = g.get_user()
                checks["github"] = {"ok": True, "message": f"Connected as {user.login}"}
            except Exception as e:
                checks["github"] = {"ok": False, "message": str(e)}
            # Disk check
            try:
                stat = shutil.disk_usage(config.BASE_DIR)
                free_gb = stat.free / (1024**3)
                checks["disk"] = {"ok": free_gb > 1, "message": f"{free_gb:.1f}GB free"}
            except Exception as e:
                checks["disk"] = {"ok": False, "message": str(e)}
            return ToolResult(success=True, data={"checks": checks, "healthy": all(c["ok"] for c in checks.values())})
        except Exception as e:
            return ToolResult(success=False, error=str(e))

    def add_skill(self, name: str, description: str, trigger_words: List[str] = None) -> ToolResult:
        try:
            skill_path = os.path.join(config.KNOWLEDGE_DIR, "skills", f"{name}.json")
            os.makedirs(os.path.dirname(skill_path), exist_ok=True)
            skill_data = {"name": name, "description": description, "trigger_words": trigger_words or [], "created_at": __import__('datetime').datetime.now().isoformat()}
            with open(skill_path, 'w') as f:
                json.dump(skill_data, f, indent=2)
            return ToolResult(success=True, data={"skill": name, "status": "added"})
        except Exception as e:
            return ToolResult(success=False, error=str(e))

# Singleton
tool_registry = ToolRegistry()
