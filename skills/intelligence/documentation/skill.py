"""Documentation Skill — Auto-generate docs from code, APIs, or specs."""

import re
import os
import logging
from typing import Dict, Any, List
from skills import BaseSkill

logger = logging.getLogger(__name__)


class DocumentationSkill(BaseSkill):
    """Auto-generate documentation from code, APIs, or specifications."""

    def __init__(self):
        super().__init__(
            name="documentation",
            category="intelligence",
            capabilities=["documentation"]
        )

    def execute(self, capability: str, params: Dict[str, Any]) -> Dict[str, Any]:
        method = params.get("method", "generate_api_docs")
        if method == "generate_api_docs":
            return self.generate_api_docs(params)
        elif method == "generate_readme":
            return self.generate_readme(params)
        elif method == "generate_wiki":
            return self.generate_wiki(params)
        return {"error": f"Unknown method: {method}"}

    def generate_api_docs(self, params: Dict[str, Any]) -> Dict[str, Any]:
        code = params.get("code", "")
        language = params.get("language", "python")
        if not code:
            return {"success": False, "error": "No code provided"}
        docs = []
        if language == "python":
            # Extract classes with docstrings
            class_matches = re.finditer(r'^class\s+(\w+)(?:\([^)]*\))?:\s*(?:\n\s*"""([^"]*(?:\n[^"]*)*)""")?', code, re.MULTILINE)
            for m in class_matches:
                docs.append({"type": "class", "name": m.group(1), "docstring": (m.group(2) or "").strip(), "signature": f"class {m.group(1)}"})
            # Extract functions with docstrings
            func_matches = re.finditer(r'^(?:\s*)def\s+(\w+)\s*\(([^)]*)\)(?:\s*->\s*([^:]+))?\s*:\s*(?:\n\s*"""([^"]*(?:\n[^"]*)*)""")?', code, re.MULTILINE)
            for m in func_matches:
                docs.append({"type": "function", "name": m.group(1), "args": m.group(2), "returns": (m.group(3) or "").strip(), "docstring": (m.group(4) or "").strip(), "signature": f"def {m.group(1)}({m.group(2)})"})
            # Extract module-level constants
            const_matches = re.finditer(r'^([A-Z][A-Z_0-9]+)\s*=\s*(.+)$', code, re.MULTILINE)
            for m in const_matches:
                docs.append({"type": "constant", "name": m.group(1), "value": m.group(2).strip()})
        elif language in ("javascript", "typescript"):
            class_matches = re.finditer(r'(?:export\s+)?class\s+(\w+)(?:\s+extends\s+\w+)?\s*\{', code)
            for m in class_matches:
                docs.append({"type": "class", "name": m.group(1), "signature": f"class {m.group(1)}"})
            func_matches = re.finditer(r'(?:export\s+)?(?:async\s+)?function\s+(\w+)\s*\(([^)]*)\)', code)
            for m in func_matches:
                docs.append({"type": "function", "name": m.group(1), "args": m.group(2), "signature": f"function {m.group(1)}({m.group(2)})"})
            # JSDoc comments
            jsdoc_matches = re.finditer(r'/\*\*\s*(.*?)\*/', code, re.DOTALL)
            for m in jsdoc_matches:
                docs.append({"type": "jsdoc", "content": re.sub(r'\s*\n\s*\*\s?', ' ', m.group(1)).strip()})
        markdown = self._docs_to_markdown(docs, params.get("title", "API Documentation"))
        return {"success": True, "docs": docs, "count": len(docs), "markdown": markdown, "language": language}

    def _docs_to_markdown(self, docs: List[Dict[str, Any]], title: str) -> str:
        md = f"# {title}\n\n"
        classes = [d for d in docs if d["type"] == "class"]
        functions = [d for d in docs if d["type"] == "function"]
        constants = [d for d in docs if d["type"] == "constant"]
        if classes:
            md += "## Classes\n\n"
            for c in classes:
                md += f"### `{c['name']}`\n\n{c.get('docstring', '')}\n\n"
        if functions:
            md += "## Functions\n\n"
            for f in functions:
                md += f"### `{f['name']}`\n\n**Signature:** `{f.get('signature', '')}`\n\n{f.get('docstring', '')}\n\n"
        if constants:
            md += "## Constants\n\n"
            for c in constants:
                md += f"- `{c['name']}` = `{c['value']}`\n"
        return md

    def generate_readme(self, params: Dict[str, Any]) -> Dict[str, Any]:
        project_name = params.get("project_name", "My Project")
        description = params.get("description", "")
        badges = params.get("badges", [])
        install_steps = params.get("install_steps", ["pip install -r requirements.txt"])
        usage_example = params.get("usage_example", "")
        features = params.get("features", [])
        readme = f"# {project_name}\n\n"
        if badges:
            readme += " ".join(badges) + "\n\n"
        readme += f"{description}\n\n"
        if features:
            readme += "## Features\n\n"
            for f in features:
                readme += f"- {f}\n"
            readme += "\n"
        readme += "## Installation\n\n```bash\n" + "\n".join(install_steps) + "\n```\n\n"
        if usage_example:
            readme += "## Usage\n\n```python\n" + usage_example + "\n```\n\n"
        readme += "## License\n\nMIT\n"
        return {"success": True, "readme": readme, "project_name": project_name}

    def generate_wiki(self, params: Dict[str, Any]) -> Dict[str, Any]:
        topic = params.get("topic", "")
        sections = params.get("sections", [])
        wiki = f"# {topic}\n\n"
        if sections:
            wiki += "## Table of Contents\n\n"
            for i, s in enumerate(sections):
                wiki += f"{i+1}. [{s.get('title', '')}](#{s.get('title', '').lower().replace(' ', '-')})\n"
            wiki += "\n"
            for s in sections:
                wiki += f"## {s.get('title', '')}\n\n{s.get('content', '')}\n\n"
        else:
            wiki += params.get("content", "")
        return {"success": True, "wiki": wiki, "topic": topic}
