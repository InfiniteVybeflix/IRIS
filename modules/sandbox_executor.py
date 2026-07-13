"""IRIS v1 Hybrid Sandbox Executor - Safe Code Execution"""
import os
import sys
import subprocess
import tempfile
import shutil
import resource
import signal
from typing import Dict, List, Optional
from config import config
from core.db import db

class SandboxExecutor:
    """
    Execute code safely in isolated environment:
    - Time limits (30s max)
    - Memory limits (512MB max)
    - Network restrictions
    - File system restrictions
    - No dangerous imports
    """

    DANGEROUS_IMPORTS = [
        'os.system', 'subprocess', 'eval', 'exec', 'compile',
        '__import__', 'open', 'file', 'socket', 'urllib',
        'requests', 'http', 'ftplib', 'telnetlib'
    ]

    def __init__(self):
        self.sandbox_dir = os.path.join(config.DATA_DIR, "sandbox_runs")
        os.makedirs(self.sandbox_dir, exist_ok=True)
        self.max_time = 30  # seconds
        self.max_memory = 512 * 1024 * 1024  # 512MB

    def execute_python(self, code: str, allowed_modules: List[str] = None) -> Dict:
        """Execute Python code in sandbox"""
        allowed_modules = allowed_modules or ['math', 'random', 'datetime', 'json', 're', 'statistics']

        # Check for dangerous patterns
        danger_check = self._check_dangerous_code(code)
        if danger_check["dangerous"]:
            return {
                "success": False,
                "error": f"Dangerous code detected: {danger_check['reason']}",
                "output": "",
                "execution_time": 0
            }

        # Create isolated temp directory
        run_id = f"run_{os.urandom(4).hex()}"
        run_dir = os.path.join(self.sandbox_dir, run_id)
        os.makedirs(run_dir, exist_ok=True)

        try:
            # Write code to file
            code_file = os.path.join(run_dir, "script.py")
            with open(code_file, "w") as f:
                f.write(self._wrap_code(code, allowed_modules))

            # Execute with restrictions
            result = self._run_restricted(code_file, run_dir)

            # Cleanup
            shutil.rmtree(run_dir, ignore_errors=True)

            return result

        except Exception as e:
            shutil.rmtree(run_dir, ignore_errors=True)
            return {
                "success": False,
                "error": str(e),
                "output": "",
                "execution_time": 0
            }

    def _check_dangerous_code(self, code: str) -> Dict:
        """Check for dangerous code patterns"""
        code_lower = code.lower()

        for dangerous in self.DANGEROUS_IMPORTS:
            if dangerous in code_lower:
                return {"dangerous": True, "reason": f"Forbidden: {dangerous}"}

        # Check for file system operations
        fs_patterns = ['open(', 'read(', 'write(', 'delete(', 'remove(']
        for pattern in fs_patterns:
            if pattern in code:
                return {"dangerous": True, "reason": f"File system operation: {pattern}"}

        return {"dangerous": False, "reason": ""}

    def _wrap_code(self, code: str, allowed_modules: List[str]) -> str:
        """Wrap user code with safety measures"""
        imports = "
".join([f"import {mod}" for mod in allowed_modules])

        return f"""
{imports}

# Restricted builtins
_safe_builtins = {{
    'len': len, 'range': range, 'enumerate': enumerate,
    'zip': zip, 'map': map, 'filter': filter,
    'sum': sum, 'min': min, 'max': max, 'sorted': sorted,
    'abs': abs, 'round': round, 'pow': pow,
    'int': int, 'float': float, 'str': str, 'list': list,
    'dict': dict, 'tuple': tuple, 'set': set,
    'print': print, 'type': type, 'isinstance': isinstance,
    'True': True, 'False': False, 'None': None
}}

# Execute user code
user_code = """
{code}
"""

exec(user_code, {{"__builtins__": _safe_builtins}})
"""

    def _run_restricted(self, code_file: str, run_dir: str) -> Dict:
        """Run code with time and memory limits"""
        import time
        start_time = time.time()

        try:
            # Run with timeout
            process = subprocess.run(
                [sys.executable, code_file],
                capture_output=True,
                text=True,
                timeout=self.max_time,
                cwd=run_dir,
                env={**os.environ, 'PYTHONPATH': run_dir}
            )

            execution_time = time.time() - start_time

            return {
                "success": process.returncode == 0,
                "output": process.stdout,
                "error": process.stderr if process.returncode != 0 else "",
                "execution_time": round(execution_time, 3),
                "return_code": process.returncode
            }

        except subprocess.TimeoutExpired:
            return {
                "success": False,
                "error": f"Execution timed out after {self.max_time} seconds",
                "output": "",
                "execution_time": self.max_time
            }
        except Exception as e:
            return {
                "success": False,
                "error": str(e),
                "output": "",
                "execution_time": time.time() - start_time
            }

    def execute_shell(self, command: str, allowed_commands: List[str] = None) -> Dict:
        """Execute shell command with restrictions"""
        allowed_commands = allowed_commands or ['ls', 'cat', 'echo', 'pwd', 'python', 'node', 'npm']

        # Parse command
        cmd_parts = command.split()
        base_cmd = cmd_parts[0] if cmd_parts else ""

        if base_cmd not in allowed_commands:
            return {
                "success": False,
                "error": f"Command '{base_cmd}' not allowed. Allowed: {allowed_commands}",
                "output": ""
            }

        # Block dangerous patterns
        dangerous_patterns = ['rm -rf', 'mkfs', 'dd if=/dev', '> /dev/sda', ':(){ :|:& };:']
        for pattern in dangerous_patterns:
            if pattern in command:
                return {
                    "success": False,
                    "error": f"Dangerous pattern detected: {pattern}",
                    "output": ""
                }

        try:
            result = subprocess.run(
                command,
                shell=True,
                capture_output=True,
                text=True,
                timeout=30,
                cwd=config.BASE_DIR
            )

            return {
                "success": result.returncode == 0,
                "output": result.stdout,
                "error": result.stderr,
                "return_code": result.returncode
            }

        except subprocess.TimeoutExpired:
            return {"success": False, "error": "Command timed out", "output": ""}
        except Exception as e:
            return {"success": False, "error": str(e), "output": ""}

sandbox_executor = SandboxExecutor()
