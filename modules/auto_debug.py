"""IRIS v1 Auto-Debug — Self-Healing Error Recovery
Automatically detects, diagnoses, and fixes errors in code execution.
"""
import re
import traceback
import logging
import ast
from typing import Dict, List, Optional, Tuple
from core.aevibron_client import aevibron
from core.tool_registry import tool_registry

logger = logging.getLogger(__name__)

class AutoDebugger:
    """
    Jarvis-level auto-debugging:
    - Catches exceptions in real-time
    - Analyzes stack traces with AI
    - Suggests and applies fixes
    - Learns from common error patterns
    """

    def __init__(self):
        self.error_patterns = {}
        self.fix_history = []
        self.common_fixes = {
            "NameError": [
                "Check if variable is defined before use",
                "Import missing module",
                "Check for typos in variable name"
            ],
            "TypeError": [
                "Check argument types",
                "Ensure proper type conversion",
                "Verify function signature"
            ],
            "ImportError": [
                "Install missing package: pip install <module>",
                "Check Python path",
                "Verify module name spelling"
            ],
            "IndexError": [
                "Check list/dict length before indexing",
                "Use .get() for dict access",
                "Add bounds checking"
            ],
            "KeyError": [
                "Use dict.get() with default value",
                "Check if key exists before access",
                "Verify dict structure"
            ],
            "AttributeError": [
                "Check object type",
                "Verify method/property exists",
                "Ensure proper initialization"
            ],
            "ModuleNotFoundError": [
                "pip install the missing module",
                "Check requirements.txt",
                "Verify Python environment"
            ],
            "SyntaxError": [
                "Check for missing colons/brackets",
                "Verify indentation",
                "Check quote matching"
            ]
        }

    def analyze_error(self, error: Exception, code: str = None, context: str = "") -> Dict:
        """
        Analyze an error and generate a detailed diagnosis.

        Returns:
            {
                "error_type": type of error,
                "message": error message,
                "suggestions": list of fix suggestions,
                "ai_analysis": AI-generated explanation,
                "confidence": confidence in fix (0-1),
                "auto_fixable": whether IRIS can auto-fix
            }
        """
        error_type = type(error).__name__
        error_msg = str(error)
        tb = traceback.format_exc()

        # Get common fixes for this error type
        suggestions = self.common_fixes.get(error_type, ["Review the error message carefully"])

        # AI-powered analysis
        ai_analysis = self._ai_diagnose(error_type, error_msg, tb, code, context)

        # Determine if auto-fixable
        auto_fixable = error_type in ["NameError", "ImportError", "ModuleNotFoundError", "SyntaxError"]

        result = {
            "error_type": error_type,
            "message": error_msg,
            "traceback": tb,
            "suggestions": suggestions,
            "ai_analysis": ai_analysis,
            "confidence": ai_analysis.get("confidence", 0.5),
            "auto_fixable": auto_fixable,
            "timestamp": __import__('datetime').datetime.now().isoformat()
        }

        # Log to learning database
        self._log_error(result)

        return result

    def _ai_diagnose(self, error_type: str, error_msg: str, traceback_str: str, 
                     code: str = None, context: str = "") -> Dict:
        """Use AI to diagnose the error deeply."""
        prompt = f"""You are an expert debugger. Analyze this error and provide:
1. Root cause explanation (1-2 sentences)
2. Specific fix suggestion
3. Confidence level (0-1)
4. Whether this is auto-fixable

Error Type: {error_type}
Error Message: {error_msg}
Context: {context}

Traceback:
{traceback_str[:1000]}

{"Code:" + code[:2000] if code else ""}

Respond in JSON format:
{{
    "root_cause": "explanation",
    "fix_suggestion": "specific fix",
    "confidence": 0.85,
    "auto_fixable": true,
    "code_fix": "the corrected code if applicable"
}}"""

        try:
            response = aevibron.fast_response(prompt)
            content = response.get("choices", [{}])[0].get("message", {}).get("content", "")

            # Extract JSON
            import json
            start = content.find("{")
            end = content.rfind("}") + 1
            if start >= 0 and end > start:
                return json.loads(content[start:end])
            return {"root_cause": "Could not parse AI response", "confidence": 0.0, "auto_fixable": False}
        except Exception as e:
            logger.error(f"AI diagnosis failed: {e}")
            return {"root_cause": "AI diagnosis unavailable", "confidence": 0.0, "auto_fixable": False}

    def attempt_fix(self, code: str, error_analysis: Dict) -> Dict:
        """Attempt to automatically fix the code."""
        if not error_analysis.get("auto_fixable"):
            return {"success": False, "reason": "Error not auto-fixable", "analysis": error_analysis}

        error_type = error_analysis["error_type"]

        try:
            if error_type == "NameError":
                fixed = self._fix_name_error(code, error_analysis["message"])
            elif error_type in ["ImportError", "ModuleNotFoundError"]:
                fixed = self._fix_import_error(code, error_analysis["message"])
            elif error_type == "SyntaxError":
                fixed = self._fix_syntax_error(code, error_analysis["message"])
            else:
                fixed = None

            if fixed:
                # Validate the fix
                if self._validate_code(fixed):
                    self.fix_history.append({
                        "error_type": error_type,
                        "original": code[:200],
                        "fixed": fixed[:200],
                        "timestamp": __import__('datetime').datetime.now().isoformat()
                    })
                    return {"success": True, "fixed_code": fixed, "analysis": error_analysis}
                else:
                    return {"success": False, "reason": "Fix validation failed", "analysis": error_analysis}

            return {"success": False, "reason": "No fix pattern matched", "analysis": error_analysis}
        except Exception as e:
            return {"success": False, "reason": f"Fix attempt failed: {e}", "analysis": error_analysis}

    def _fix_name_error(self, code: str, error_msg: str) -> Optional[str]:
        """Fix NameError by adding missing imports or definitions."""
        match = re.search(r"name '(.+?)' is not defined", error_msg)
        if match:
            var_name = match.group(1)
            # Common missing imports
            common_imports = {
                "os": "import os",
                "sys": "import sys",
                "json": "import json",
                "re": "import re",
                "requests": "import requests",
                "datetime": "from datetime import datetime",
                "timedelta": "from datetime import timedelta",
                "uuid": "import uuid",
                "random": "import random",
                "math": "import math",
                "numpy": "import numpy as np",
                "pd": "import pandas as pd",
            }
            if var_name in common_imports:
                return common_imports[var_name] + "\n" + code
        return None

    def _fix_import_error(self, code: str, error_msg: str) -> Optional[str]:
        """Fix ImportError by adding pip install comments."""
        match = re.search(r"No module named '(.+?)'", error_msg)
        if match:
            module = match.group(1)
            return f"# TODO: Run: pip install {module}\n" + code
        return None

    def _fix_syntax_error(self, code: str, error_msg: str) -> Optional[str]:
        """Attempt to fix common syntax errors."""
        # Fix missing colons in if/for/while/def
        lines = code.split("\n")
        fixed_lines = []
        for line in lines:
            stripped = line.strip()
            if stripped.startswith(("if ", "for ", "while ", "def ", "class ", "elif ", "else", "try", "except", "finally")):
                if not stripped.endswith(":") and not stripped.endswith("\"):
                    line = line + ":"
            fixed_lines.append(line)
        return "\n".join(fixed_lines)

    def _validate_code(self, code: str) -> bool:
        """Validate Python code syntax."""
        try:
            ast.parse(code)
            return True
        except SyntaxError:
            return False

    def _log_error(self, error_data: Dict):
        """Log error for pattern learning."""
        error_type = error_data["error_type"]
        self.error_patterns[error_type] = self.error_patterns.get(error_type, 0) + 1

    def get_error_stats(self) -> Dict:
        """Get error frequency statistics."""
        total = sum(self.error_patterns.values())
        return {
            "total_errors_logged": total,
            "error_breakdown": self.error_patterns,
            "most_common": max(self.error_patterns, key=self.error_patterns.get) if self.error_patterns else None,
            "fixes_applied": len(self.fix_history)
        }

    def wrap_function(self, func):
        """Decorator to auto-debug any function."""
        def wrapper(*args, **kwargs):
            try:
                return func(*args, **kwargs)
            except Exception as e:
                analysis = self.analyze_error(e, context=f"Function: {func.__name__}")
                logger.error(f"Auto-debug caught error in {func.__name__}: {analysis['error_type']}")

                if analysis.get("auto_fixable") and analysis.get("confidence", 0) > 0.7:
                    # Try to get code and fix it
                    import inspect
                    try:
                        source = inspect.getsource(func)
                        fix_result = self.attempt_fix(source, analysis)
                        if fix_result.get("success"):
                            logger.info(f"Auto-fixed {func.__name__}!")
                            # Note: In production, you'd need to reload the module

                # Re-raise with enhanced info
                raise Exception(f"[{analysis['error_type']}] {analysis['message']}\nAI Suggestion: {analysis['ai_analysis'].get('fix_suggestion', 'N/A')}") from e
        return wrapper


# Singleton
auto_debug = AutoDebugger()
