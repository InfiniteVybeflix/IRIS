"""IRIS v9 Hybrid Copilot Bridge - IDE Integration"""
import os
import json
from typing import Dict, List, Optional
from config import config
from core.db import db

class CopilotBridge:
    """
    Bridge to IDEs for real-time code assistance:
    - VS Code extension API
    - JetBrains plugin API
    - Vim/Neovim integration
    - Sublime Text plugin
    - Real-time code completion
    - Inline suggestions
    """

    def __init__(self):
        self.active_sessions = {}
        self.suggestion_cache = {}

    def get_inline_completion(self, file_path: str, line: int, column: int, 
                             prefix: str, language: str = "python") -> Dict:
        """Get inline code completion suggestion"""
        try:
            from core.aevibron_client import aevibron

            # Read context from file
            context = self._get_file_context(file_path, line)

            prompt = f"""Complete this code:

File: {file_path}
Language: {language}
Context:
```{language}
{context}
```

Current line (cursor at column {column}):
```{language}
{prefix}
```

Provide ONLY the completion. No explanations. No markdown."""

            response = aevibron.fast_response(prompt)
            completion = response.get("choices", [{}])[0].get("message", {}).get("content", "")

            # Clean up completion
            completion = completion.strip().replace("```" + language, "").replace("```", "").strip()

            return {
                "success": True,
                "completion": completion,
                "file": file_path,
                "line": line,
                "column": column
            }

        except Exception as e:
            return {"success": False, "error": str(e)}

    def get_code_explanation(self, file_path: str, start_line: int, end_line: int) -> Dict:
        """Explain selected code"""
        try:
            code = self._get_file_lines(file_path, start_line, end_line)

            from core.aevibron_client import aevibron
            prompt = f"Explain this code:

```python
{code}
```

Provide a concise explanation."

            response = aevibron.fast_response(prompt)
            explanation = response.get("choices", [{}])[0].get("message", {}).get("content", "")

            return {
                "success": True,
                "explanation": explanation,
                "code": code,
                "file": file_path,
                "lines": f"{start_line}-{end_line}"
            }

        except Exception as e:
            return {"success": False, "error": str(e)}

    def get_refactoring_suggestion(self, file_path: str, start_line: int, end_line: int) -> Dict:
        """Suggest refactoring for selected code"""
        try:
            code = self._get_file_lines(file_path, start_line, end_line)

            from core.aevibron_client import aevibron
            prompt = f"Refactor this code to be cleaner, more efficient, and follow best practices:

```python
{code}
```

Provide ONLY the refactored code. No explanations."

            response = aevibron.fast_response(prompt)
            refactored = response.get("choices", [{}])[0].get("message", {}).get("content", "")

            # Clean up
            refactored = refactored.strip().replace("```python", "").replace("```", "").strip()

            return {
                "success": True,
                "original": code,
                "refactored": refactored,
                "file": file_path,
                "lines": f"{start_line}-{end_line}"
            }

        except Exception as e:
            return {"success": False, "error": str(e)}

    def get_bug_detection(self, file_path: str) -> Dict:
        """Detect potential bugs in file"""
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                code = f.read()

            from core.aevibron_client import aevibron
            prompt = f"Find potential bugs, security issues, and code smells in this file:

```python
{code[:5000]}
```

List each issue with line number and severity."

            response = aevibron.fast_response(prompt)
            issues = response.get("choices", [{}])[0].get("message", {}).get("content", "")

            return {
                "success": True,
                "issues": issues,
                "file": file_path
            }

        except Exception as e:
            return {"success": False, "error": str(e)}

    def _get_file_context(self, file_path: str, line: int, context_lines: int = 20) -> str:
        """Get context around a line in file"""
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                lines = f.readlines()

            start = max(0, line - context_lines - 1)
            end = min(len(lines), line + context_lines)
            return "".join(lines[start:end])
        except:
            return ""

    def _get_file_lines(self, file_path: str, start: int, end: int) -> str:
        """Get specific lines from file"""
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                lines = f.readlines()
            return "".join(lines[start-1:end])
        except:
            return ""

    def generate_vscode_extension_manifest(self) -> Dict:
        """Generate VS Code extension manifest for IRIS Copilot"""
        return {
            "name": "iris-copilot",
            "displayName": "IRIS Copilot",
            "description": "AI-powered coding assistant by IRIS for Infinite Vybeflix",
            "version": "1.0.0",
            "publisher": "aevibron",
            "engines": {"vscode": "^1.85.0"},
            "categories": ["Machine Learning", "Snippets", "Other"],
            "activationEvents": ["onCommand:iris.suggest", "onLanguage:python"],
            "main": "./out/extension.js",
            "contributes": {
                "commands": [
                    {"command": "iris.suggest", "title": "IRIS: Get Suggestion"},
                    {"command": "iris.explain", "title": "IRIS: Explain Code"},
                    {"command": "iris.refactor", "title": "IRIS: Refactor Code"},
                    {"command": "iris.bugcheck", "title": "IRIS: Check for Bugs"}
                ],
                "keybindings": [
                    {"command": "iris.suggest", "key": "ctrl+shift+i", "when": "editorTextFocus"}
                ]
            }
        }

copilot_bridge = CopilotBridge()
