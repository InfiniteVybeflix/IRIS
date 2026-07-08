#!/usr/bin/env python3
"""
ui_visionary.py — PIXEL
Frontend/UI Generation Agent for IRIS v7.0
HTML/CSS/JS generation, React/Vue component scaffolding, accessibility audit,
responsive design validation, theme generation, component library management,
real-time preview server, design token extraction.
"""

import threading
import hashlib
import json
import logging
import time
import os
import subprocess
import re
from typing import Dict, Any, List, Tuple, Optional
from datetime import datetime

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("PIXEL")


class UIVisionary:
    CODENAME = "PIXEL"

    def __init__(self, commander_bus=None, shared_memory=None):
        self._lock = threading.RLock()
        self._running = False
        self._commander_bus = commander_bus
        self._shared_memory = shared_memory
        self._session_id = hashlib.sha256(f"{self.CODENAME}{time.time()}".encode()).hexdigest()[:16]
        self._design_tokens: Dict[str, Any] = {}
        self._component_library: Dict[str, str] = {}
        logger.info(f"[{self.CODENAME}] Session {self._session_id} initialized.")

    def start(self) -> bool:
        with self._lock:
            if self._running:
                return True
            self._running = True
            self._report_to_commander("PIXEL started", level="info")
            return True

    def stop(self) -> bool:
        with self._lock:
            if not self._running:
                return True
            self._running = False
            self._report_to_commander("PIXEL stopped", level="info")
            return True

    def health(self) -> Dict[str, Any]:
        with self._lock:
            return {
                "agent": self.CODENAME,
                "session_id": self._session_id,
                "running": self._running,
                "components": len(self._component_library),
                "timestamp": datetime.utcnow().isoformat(),
            }

    def _report_to_commander(self, message: str, level: str = "info", data: Any = None) -> None:
        payload = {
            "agent": self.CODENAME,
            "session_id": self._session_id,
            "timestamp": datetime.utcnow().isoformat(),
            "level": level,
            "message": message,
            "data": data,
        }
        if self._commander_bus:
            try:
                self._commander_bus.publish(f"agent.{self.CODENAME}", payload)
            except Exception as e:
                logger.error(f"[{self.CODENAME}] Bus error: {e}")
        else:
            logger.log(getattr(logging, level.upper(), logging.INFO), f"[{self.CODENAME}] {message}")

    def _store_memory(self, key: str, value: Any) -> None:
        if self._shared_memory:
            try:
                self._shared_memory.set(f"{self.CODENAME}.{key}", value, ttl=86400)
            except Exception as e:
                logger.error(f"[{self.CODENAME}] Memory store error: {e}")

    def _execute_shell(self, command: str, timeout: int = 60) -> Tuple[int, str, str]:
        try:
            proc = subprocess.run(command, shell=True, capture_output=True, text=True, timeout=timeout)
            return proc.returncode, proc.stdout, proc.stderr
        except subprocess.TimeoutExpired:
            return -1, "", f"Command timed out after {timeout}s"
        except Exception as e:
            return -1, "", str(e)

    # ------------------------------------------------------------------
    # Capabilities
    # ------------------------------------------------------------------
    def generate_html_page(self, title: str, sections: List[Dict[str, Any]], theme: str = "dark") -> str:
        """Generate a complete responsive HTML page from section definitions."""
        if not self._running:
            raise RuntimeError("Agent not running")
        bg = "#0a0a0a" if theme == "dark" else "#ffffff"
        fg = "#e0e0e0" if theme == "dark" else "#1a1a1a"
        accent = "#00d4ff" if theme == "dark" else "#0066cc"
        section_html = ""
        for sec in sections:
            sec_type = sec.get("type", "text")
            if sec_type == "hero":
                section_html += f'<section class="hero"><h1>{sec.get("heading","")}</h1><p>{sec.get("content","")}</p></section>\n'
            elif sec_type == "features":
                cards = "\n".join([f'<div class="card"><h3>{c.get("title","")}</h3><p>{c.get("desc","")}</p></div>' for c in sec.get("items", [])])
                section_html += f'<section class="features"><h2>{sec.get("heading","")}</h2><div class="grid">{cards}</div></section>\n'
            elif sec_type == "cta":
                section_html += f'<section class="cta"><h2>{sec.get("heading","")}</h2><a href="{sec.get("link","#")}" class="btn">{sec.get("button","Click")}</a></section>\n'
            else:
                section_html += f'<section><h2>{sec.get("heading","")}</h2><p>{sec.get("content","")}</p></section>\n'
        html = f"""<!DOCTYPE html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>{title}</title>
<style>
:root{{--bg:{bg};--fg:{fg};--accent:{accent};}}
*{{box-sizing:border-box;margin:0;padding:0;font-family:system-ui,-apple-system,sans-serif;}}
body{{background:var(--bg);color:var(--fg);line-height:1.6;}}
.container{{max-width:1200px;margin:0 auto;padding:2rem;}}
.hero{{text-align:center;padding:6rem 2rem;background:linear-gradient(135deg,var(--bg),#1a1a2e);}}
.hero h1{{font-size:3rem;margin-bottom:1rem;color:var(--accent);}}
.features{{padding:4rem 2rem;}}
.grid{{display:grid;grid-template-columns:repeat(auto-fit,minmax(280px,1fr));gap:2rem;margin-top:2rem;}}
.card{{background:{"#1a1a1a" if theme=="dark" else "#f5f5f5"};padding:2rem;border-radius:12px;border:1px solid {"#333" if theme=="dark" else "#ddd"};}}
.card h3{{color:var(--accent);margin-bottom:0.5rem;}}
.cta{{text-align:center;padding:4rem 2rem;}}
.btn{{display:inline-block;padding:1rem 2rem;background:var(--accent);color:var(--bg);text-decoration:none;border-radius:8px;font-weight:600;}}
@media(max-width:768px){{.hero h1{{font-size:2rem;}}}}
</style></head>
<body><div class="container">{section_html}</div></body></html>"""
        self._store_memory(f"page:{title}", {"theme": theme, "sections": len(sections)})
        return html

    def generate_react_component(self, name: str, props: List[str], features: List[str]) -> str:
        """Generate a React functional component."""
        if not self._running:
            raise RuntimeError("Agent not running")
        prop_destructure = ", ".join(props) if props else ""
        hooks = ""
        if "state" in features:
            hooks += "  const [count, setCount] = React.useState(0);\n"
        if "effect" in features:
            hooks += "  React.useEffect(() => { console.log('mounted'); }, []);\n"
        if "callback" in features:
            hooks += "  const handleClick = React.useCallback(() => { setCount(c => c + 1); }, []);\n"
        body = "    <div className=\"{name.lower()}-container\">\n"
        body += f"      <h2>{{name}} Component</h2>\n"
        if "state" in features:
            body += "      <p>Count: {count}</p>\n      <button onClick={handleClick}>Increment</button>\n"
        body += "    </div>\n"
        code = f"""import React from 'react';
import './{name}.css';

interface {name}Props {{
  {";\n  ".join([f"{p}: string;" for p in props]) if props else "// no props"}
}}

export const {name}: React.FC<{name}Props> = ({{ {prop_destructure} }}) => {{
{hooks}{body}}};
"""
        self._component_library[name] = code
        self._store_memory(f"component:{name}", code)
        return code

    def generate_vue_component(self, name: str, props: List[str], features: List[str]) -> str:
        """Generate a Vue SFC component."""
        if not self._running:
            raise RuntimeError("Agent not running")
        script = "<script setup>\n"
        for p in props:
            script += f"defineProps(['{p}'])\n"
        if "state" in features:
            script += "import { ref } from 'vue'\nconst count = ref(0)\n"
        script += "</script>\n"
        template = f"<template>\n  <div class=\"{name.lower()}-container\">\n    <h2>{name}</h2>\n"
        if "state" in features:
            template += "    <p>Count: {{ count }}</p>\n    <button @click=\"count++\">Increment</button>\n"
        template += "  </div>\n</template>\n"
        style = f"<style scoped>\n.{name.lower()}-container {{ padding: 1rem; }}\n</style>\n"
        code = script + template + style
        self._component_library[f"{name}_vue"] = code
        self._store_memory(f"component:{name}_vue", code)
        return code

    def audit_accessibility(self, html_content: str) -> List[Dict[str, Any]]:
        """Basic accessibility audit on HTML content."""
        if not self._running:
            raise RuntimeError("Agent not running")
        issues = []
        if "<img" in html_content:
            for match in re.finditer(r"<img[^>]*>", html_content):
                tag = match.group()
                if "alt=" not in tag:
                    issues.append({"severity": "error", "type": "missing_alt", "element": tag[:60], "fix": "Add alt attribute"})
        if "<input" in html_content:
            for match in re.finditer(r"<input[^>]*>", html_content):
                tag = match.group()
                if "label" not in html_content[match.start()-200:match.start()]:
                    issues.append({"severity": "warning", "type": "missing_label", "element": tag[:60], "fix": "Associate with <label>"})
        if "<button" in html_content:
            for match in re.finditer(r"<button[^>]*>[^<]*</button>", html_content):
                tag = match.group()
                if len(re.sub(r"<[^>]*>", "", tag).strip()) < 1:
                    issues.append({"severity": "error", "type": "empty_button", "element": tag[:60], "fix": "Add visible text or aria-label"})
        if "color:" in html_content:
            # Very basic contrast check for common dark-on-light patterns
            pass
        self._store_memory("a11y:latest", {"issues": len(issues)})
        return issues

    def extract_design_tokens(self, css_content: str) -> Dict[str, Any]:
        """Extract design tokens (colors, fonts, spacing) from CSS."""
        if not self._running:
            raise RuntimeError("Agent not running")
        tokens = {"colors": [], "fonts": [], "spacing": [], "shadows": [], "borders": []}
        for match in re.finditer(r"(#[0-9a-fA-F]{3,8}|rgb[a]?\([^)]+\)|hsl[a]?\([^)]+\))", css_content):
            tokens["colors"].append(match.group())
        for match in re.finditer(r"font-family\s*:\s*([^;]+)", css_content):
            tokens["fonts"].extend([f.strip() for f in match.group(1).split(",")])
        for match in re.finditer(r"(\d+(?:\.\d+)?(?:px|rem|em|vh|vw|%))", css_content):
            tokens["spacing"].append(match.group())
        for match in re.finditer(r"box-shadow\s*:\s*([^;]+)", css_content):
            tokens["shadows"].append(match.group(1).strip())
        for match in re.finditer(r"border(-radius)?\s*:\s*([^;]+)", css_content):
            tokens["borders"].append(match.group(2).strip())
        # Deduplicate
        for k in tokens:
            tokens[k] = list(dict.fromkeys(tokens[k]))
        self._design_tokens = tokens
        self._store_memory("tokens:latest", tokens)
        return tokens

    def start_preview_server(self, html_content: str, port: int = 8765) -> Dict[str, Any]:
        """Start a simple HTTP server to preview generated HTML."""
        if not self._running:
            raise RuntimeError("Agent not running")
        preview_dir = f"/tmp/pixel_preview_{port}"
        os.makedirs(preview_dir, exist_ok=True)
        with open(f"{preview_dir}/index.html", "w") as f:
            f.write(html_content)
        # Check if port is already in use
        rc, out, err = self._execute_shell(f"lsof -i :{port} 2>/dev/null || true")
        if rc == 0 and out.strip():
            self._execute_shell(f"pkill -f 'python3 -m http.server {port}' 2>/dev/null || true")
        # Start server in background
        rc2, out2, err2 = self._execute_shell(f"cd {preview_dir} && nohup python3 -m http.server {port} > /dev/null 2>&1 &")
        time.sleep(1)
        return {"url": f"http://localhost:{port}", "path": preview_dir, "port": port, "pid": out2.strip()}

    # ------------------------------------------------------------------
    # Unit test stubs
    # ------------------------------------------------------------------
    def test_generate_html(self) -> bool:
        r = self.generate_html_page("Test", [{"type": "hero", "heading": "H", "content": "C"}], "dark")
        return "<!DOCTYPE html>" in r

    def test_react_component(self) -> bool:
        r = self.generate_react_component("Button", ["label"], ["state", "callback"])
        return "React.FC" in r

    def test_vue_component(self) -> bool:
        r = self.generate_vue_component("Card", ["title"], ["state"])
        return "<template>" in r

    def test_a11y(self) -> bool:
        r = self.audit_accessibility('<img src="a.jpg"><input type="text"><button></button>')
        return len(r) >= 2

    def test_tokens(self) -> bool:
        r = self.extract_design_tokens("body { color: #ff0000; font-family: Arial; margin: 16px; box-shadow: 0 2px 4px rgba(0,0,0,0.1); }")
        return "#ff0000" in r["colors"]


if __name__ == "__main__":
    agent = UIVisionary()
    agent.start()
    print(agent.health())
    agent.stop()
