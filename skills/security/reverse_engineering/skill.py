"""Reverse Engineering Skill — Binary analysis, disassembly, decompilation."""

import os
import re
import struct
import logging
from typing import Dict, Any
from skills import BaseSkill

logger = logging.getLogger(__name__)


class ReverseEngineeringSkill(BaseSkill):
    """Binary analysis, disassembly, and decompilation."""

    def __init__(self):
        super().__init__(name="reverse_engineering", category="security", capabilities=["reverse_engineering"])

    def execute(self, capability: str, params: Dict[str, Any]) -> Dict[str, Any]:
        method = params.get("method", "analyze_binary")
        if method == "disassemble":
            return self.disassemble(params)
        elif method == "decompile":
            return self.decompile(params)
        elif method == "analyze_binary":
            return self.analyze_binary(params)
        return {"error": f"Unknown method: {method}"}

    def analyze_binary(self, params: Dict[str, Any]) -> Dict[str, Any]:
        binary_path = params.get("binary_path", "")
        if not binary_path or not os.path.exists(binary_path):
            return {"success": False, "error": f"Binary not found: {binary_path}"}
        try:
            with open(binary_path, 'rb') as f:
                header = f.read(64)
            analysis = {"path": binary_path, "size": os.path.getsize(binary_path)}
            # Identify file type
            magic = header[:4]
            if magic == b'\x7fELF':
                analysis["format"] = "ELF"
                analysis["arch"] = {0x03: "i386", 0x3e: "x86-64", 0x28: "ARM", 0xb7: "AArch64"}.get(struct.unpack_from('<H', header, 18)[0], "unknown")
                analysis["endian"] = "little" if header[5] == 1 else "big"
                analysis["type"] = {1: "relocatable", 2: "executable", 3: "shared_object", 4: "core"}.get(header[16], "unknown")
            elif magic == b'MZ\x90\x00' or header[:2] == b'MZ':
                analysis["format"] = "PE/COFF"
                # Parse PE header offset
                pe_offset = struct.unpack_from('<I', header, 0x3c)[0] if len(header) > 0x3c else 0
                analysis["pe_header_offset"] = pe_offset
            elif magic[:4] == b'\xca\xfe\xba\xbe':
                analysis["format"] = "Mach-O (fat)"
            elif magic[:4] == b'\xcf\xfa\xed\xfe':
                analysis["format"] = "Mach-O 64"
            elif b'<?xml' in header[:20] or b'PK\x03\x04' in header[:20]:
                analysis["format"] = "Archive/Package"
            else:
                analysis["format"] = "Unknown"
                analysis["magic_hex"] = magic.hex()
            # Check for interesting strings
            try:
                with open(binary_path, 'rb') as f:
                    content = f.read()
                strings = re.findall(b'[\x20-\x7e]{8,}', content)
                interesting = [s.decode('ascii', errors='replace') for s in strings[:100] if any(kw in s.lower() for kw in [b'http', b'password', b'key', b'token', b'admin', b'root', b'backdoor', b'shell', b'cmd', b'eval'])]
                analysis["interesting_strings"] = interesting[:20]
                analysis["total_strings"] = len(strings)
            except Exception:
                pass
            return {"success": True, **analysis}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def disassemble(self, params: Dict[str, Any]) -> Dict[str, Any]:
        binary_path = params.get("binary_path", "")
        if not binary_path or not os.path.exists(binary_path):
            return {"success": False, "error": f"Binary not found: {binary_path}"}
        try:
            import subprocess
            result = subprocess.run(["objdump", "-d", binary_path], capture_output=True, text=True, timeout=60)
            if result.returncode == 0:
                lines = result.stdout.split("\n")
                functions = []
                current_func = None
                for line in lines:
                    if '<' in line and '>' in line:
                        func_name = re.search(r'<([^>]+)>', line)
                        if func_name:
                            current_func = {"name": func_name.group(1), "instructions": []}
                            functions.append(current_func)
                    elif current_func and re.match(r'\s+[0-9a-f]+:', line):
                        current_func["instructions"].append(line.strip())
                return {"success": True, "binary": binary_path, "disassembler": "objdump", "functions_found": len(functions), "functions": functions[:20], "total_lines": len(lines)}
            return {"success": False, "error": f"objdump failed: {result.stderr}", "binary": binary_path}
        except FileNotFoundError:
            return {"success": False, "error": "objdump not found. Install binutils.", "binary": binary_path}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def decompile(self, params: Dict[str, Any]) -> Dict[str, Any]:
        binary_path = params.get("binary_path", "")
        if not binary_path or not os.path.exists(binary_path):
            return {"success": False, "error": f"Binary not found: {binary_path}"}
        # Try ghidra, retdec, or radare2
        for tool, cmd in [("radare2", ["r2", "-qc", "pdg", binary_path]), ("retdec", ["retdec-decompiler", binary_path])]:
            try:
                import subprocess
                result = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
                if result.returncode == 0 and result.stdout:
                    return {"success": True, "binary": binary_path, "decompiler": tool, "output": result.stdout[:10000]}
            except FileNotFoundError:
                continue
            except Exception:
                continue
        return {"success": False, "error": "No decompiler available. Install radare2 or retdec.", "binary": binary_path, "suggested_tools": ["radare2", "ghidra", "retdec"]}
