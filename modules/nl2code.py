"""IRIS v1 NL2Code — Natural Language to Working Code
Converts plain English requirements into production-ready code.
"""
import re
import json
import logging
from typing import Dict, List, Optional
from core.aevibron_client import aevibron
from core.tool_registry import tool_registry
from modules.auto_debug import auto_debug

logger = logging.getLogger(__name__)

class NL2CodeEngine:
    """
    Transform natural language into code:
    - Requirements → Project structure
    - Feature description → Function implementation
    - Bug report → Fix suggestion
    - API spec → Client/server code
    """

    def __init__(self):
        self.language_templates = {
            "python": {
                "extension": ".py",
                "shebang": "#!/usr/bin/env python3\n",
                "comment": "#",
                "docstring": '"""{content}"""'
            },
            "javascript": {
                "extension": ".js",
                "shebang": "",
                "comment": "//",
                "docstring": "/**\n * {content}\n */"
            },
            "typescript": {
                "extension": ".ts",
                "shebang": "",
                "comment": "//",
                "docstring": "/**\n * {content}\n */"
            },
            "html": {
                "extension": ".html",
                "shebang": "",
                "comment": "<!--",
                "docstring": "<!-- {content} -->"
            },
            "css": {
                "extension": ".css",
                "shebang": "",
                "comment": "/*",
                "docstring": "/* {content} */"
            },
            "sql": {
                "extension": ".sql",
                "shebang": "",
                "comment": "--",
                "docstring": "/* {content} */"
            }
        }

    def generate_function(self, description: str, language: str = "python", 
                         inputs: List[str] = None, outputs: List[str] = None,
                         constraints: List[str] = None) -> Dict:
        """
        Generate a function from natural language description.

        Args:
            description: What the function should do
            language: Target programming language
            inputs: Expected input parameters
            outputs: Expected return values
            constraints: Performance/style constraints
        """
        template = self.language_templates.get(language, self.language_templates["python"])

        prompt = f"""You are an expert {language} developer. Generate a complete, production-ready function based on this description.

DESCRIPTION: {description}

{"INPUTS: " + ", ".join(inputs) if inputs else ""}
{"OUTPUTS: " + ", ".join(outputs) if outputs else ""}
{"CONSTRAINTS: " + "; ".join(constraints) if constraints else ""}

Requirements:
1. Include proper docstring/comments
2. Add input validation
3. Handle edge cases
4. Include type hints if applicable
5. Add error handling
6. Make it efficient and clean

Respond ONLY with the code, no explanations."""

        try:
            response = aevibron.chat(
                messages=[{"role": "user", "content": prompt}],
                model=config.DEEP_MODEL,
                temperature=0.3,
                max_tokens=2000
            )

            code = response.get("choices", [{}])[0].get("message", {}).get("content", "")
            # Clean up markdown code blocks
            code = re.sub(r"^```\w*\n?", "", code)
            code = re.sub(r"```$", "", code).strip()

            # Validate
            validation = self._validate_generated_code(code, language)

            return {
                "success": True,
                "code": code,
                "language": language,
                "description": description,
                "validation": validation,
                "filename": f"generated_function{template['extension']}"
            }
        except Exception as e:
            logger.error(f"NL2Code generation failed: {e}")
            return {"success": False, "error": str(e)}

    def generate_project(self, requirements: str, tech_stack: str = "nextjs") -> Dict:
        """
        Generate a complete project structure from requirements.

        Args:
            requirements: Plain English project description
            tech_stack: "nextjs", "fastapi", "flask", "react", "vue"
        """
        prompt = f"""You are a senior architect. Design a complete {tech_stack} project based on these requirements.

REQUIREMENTS:
{requirements}

Provide:
1. Project structure (file tree)
2. Key files with complete code
3. README with setup instructions
4. package.json / requirements.txt / etc.
5. Environment variables needed

Respond in JSON format:
{{
    "project_name": "name",
    "structure": ["file1", "file2"],
    "files": {{
        "path/to/file": "complete code content"
    }},
    "readme": "markdown content",
    "dependencies": ["dep1", "dep2"],
    "env_vars": ["VAR1", "VAR2"]
}}"""

        try:
            response = aevibron.chat(
                messages=[{"role": "user", "content": prompt}],
                model=config.DEEP_MODEL,
                temperature=0.4,
                max_tokens=4000
            )

            content = response.get("choices", [{}])[0].get("message", {}).get("content", "")

            # Extract JSON
            start = content.find("{")
            end = content.rfind("}") + 1
            if start >= 0 and end > start:
                project_data = json.loads(content[start:end])
                return {"success": True, **project_data, "tech_stack": tech_stack}

            return {"success": False, "error": "Could not parse project structure", "raw": content[:500]}
        except Exception as e:
            logger.error(f"Project generation failed: {e}")
            return {"success": False, "error": str(e)}

    def generate_api_client(self, api_spec: str, language: str = "python") -> Dict:
        """Generate API client code from OpenAPI/Swagger spec or description."""
        prompt = f"""Generate a complete {language} API client for this specification:

{api_spec}

Include:
1. Client class with authentication
2. All endpoint methods
3. Error handling
4. Type hints / interfaces
5. Usage examples

Respond with complete code only."""

        try:
            response = aevibron.chat(
                messages=[{"role": "user", "content": prompt}],
                model=config.DEEP_MODEL,
                temperature=0.3,
                max_tokens=3000
            )

            code = response.get("choices", [{}])[0].get("message", {}).get("content", "")
            code = re.sub(r"^```\w*\n?", "", code)
            code = re.sub(r"```$", "", code).strip()

            return {
                "success": True,
                "code": code,
                "language": language,
                "client_name": f"APIClient{self.language_templates[language]['extension']}"
            }
        except Exception as e:
            return {"success": False, "error": str(e)}

    def fix_bug(self, bug_description: str, code: str, language: str = "python") -> Dict:
        """Generate a bug fix from description and code."""
        prompt = f"""Fix this bug in the following {language} code.

BUG DESCRIPTION:
{bug_description}

CODE:
```{language}
{code}
```

Provide:
1. Root cause analysis (1 sentence)
2. Fixed code
3. Explanation of changes

Respond in JSON:
{{
    "root_cause": "explanation",
    "fixed_code": "complete fixed code",
    "changes_made": ["change1", "change2"]
}}"""

        try:
            response = aevibron.chat(
                messages=[{"role": "user", "content": prompt}],
                model=config.DEEP_MODEL,
                temperature=0.3,
                max_tokens=3000
            )

            content = response.get("choices", [{}])[0].get("message", {}).get("content", "")
            start = content.find("{")
            end = content.rfind("}") + 1
            if start >= 0 and end > start:
                fix_data = json.loads(content[start:end])
                return {"success": True, **fix_data, "language": language}

            return {"success": False, "error": "Could not parse fix"}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def _validate_generated_code(self, code: str, language: str) -> Dict:
        """Validate generated code."""
        issues = []

        if language == "python":
            try:
                import ast
                ast.parse(code)
            except SyntaxError as e:
                issues.append(f"Syntax error: {e}")

            # Check for common anti-patterns
            if "eval(" in code and "ast.literal_eval" not in code:
                issues.append("Uses eval() - security risk")
            if "exec(" in code:
                issues.append("Uses exec() - security risk")
            if "input(" in code:
                issues.append("Uses input() - may block in production")

        return {
            "valid": len(issues) == 0,
            "issues": issues,
            "lines": len(code.splitlines()),
            "characters": len(code)
        }

    def explain_code(self, code: str, language: str = "python") -> Dict:
        """Generate human-readable explanation of code."""
        prompt = f"""Explain this {language} code in plain English:

```{language}
{code}
```

Provide:
1. What the code does (1-2 sentences)
2. Key functions/components
3. Input/output
4. Any potential issues

Keep it concise but complete."""

        try:
            response = aevibron.fast_response(prompt)
            explanation = response.get("choices", [{}])[0].get("message", {}).get("content", "")
            return {"success": True, "explanation": explanation, "language": language}
        except Exception as e:
            return {"success": False, "error": str(e)}


# Singleton
nl2code = NL2CodeEngine()
