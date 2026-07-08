"""
IRIS v7.0 — Volatility Bridge

Memory forensics using Volatility 3. Process analysis, malware detection,
network artifact extraction, process memory dumping.

Dependencies: volatility3
"""

from __future__ import annotations

import logging
import os
from typing import Any, Dict, List, Optional

from .base_tool import BaseTool

logger = logging.getLogger(__name__)


class VolatilityBridge(BaseTool):
    """Volatility 3 memory forensics bridge. Read-only."""

    name: str = "volatility_bridge"
    category: str = "forensics"
    dependencies: List[str] = ["volatility3"]

    def __init__(self, iris_core: Optional[Any] = None) -> None:
        super().__init__(iris_core)
        self._image_path: Optional[str] = None

    def _load_volatility(self) -> Any:
        try:
            import volatility3.framework
            return volatility3.framework
        except ImportError:
            return None

    def _run_plugin(self, image_path: str, plugin_name: str) -> str:
        cmd = ["python3", "-m", "volatility3", "-f", image_path, plugin_name]
        result = self._run_subprocess(cmd, timeout=600)
        return result.stdout

    def _run(self, *args: Any, **kwargs: Any) -> Dict[str, Any]:
        return {}

    def analyze_image(self, filepath: str) -> Dict[str, Any]:
        self._begin_execution()
        try:
            safe_path = os.path.abspath(os.path.expanduser(filepath))
            if not os.path.exists(safe_path):
                res = self._build_result(success=False, action="analyze_image", errors=[f"File not found: {safe_path}"])
                self.last_result = res
                self._end_execution(False)
                return res
            self._image_path = safe_path
            vol = self._load_volatility()
            if vol is None:
                res = self._build_result(success=False, action="analyze_image", errors=["volatility3 not installed."])
                self.last_result = res
                self._end_execution(False)
                return res
            plugins = ["windows.info.Info", "windows.pslist.PsList", "windows.pstree.PsTree", "windows.netscan.NetScan"]
            plugin_results: Dict[str, Any] = {}
            errors: List[str] = []
            for plugin in plugins:
                try:
                    plugin_results[plugin] = self._parse_table_output(self._run_plugin(safe_path, plugin))
                except Exception as exc:
                    errors.append(f"{plugin}: {exc}")
            res = self._build_result(success=True, action="analyze_image", output=plugin_results,
                parsed={"image_path": safe_path, "plugins_run": list(plugin_results.keys()), "results": plugin_results}, errors=errors)
            self.last_result = res
            self._end_execution(True)
            return res
        except Exception as exc:
            logger.exception("analyze_image failed")
            res = self._build_result(success=False, action="analyze_image", errors=[str(exc)])
            self.last_result = res
            self._end_execution(False)
            return res

    def list_processes(self, filepath: Optional[str] = None) -> Dict[str, Any]:
        image = filepath or self._image_path
        if not image:
            return self._build_result(success=False, action="list_processes", errors=["No memory image specified."])
        self._begin_execution()
        try:
            output = self._run_plugin(image, "windows.pslist.PsList")
            processes = self._parse_table_output(output)
            res = self._build_result(success=True, action="list_processes", output=output,
                parsed={"processes": processes, "count": len(processes)})
            self.last_result = res
            self._end_execution(True)
            return res
        except Exception as exc:
            logger.exception("list_processes failed")
            res = self._build_result(success=False, action="list_processes", errors=[str(exc)])
            self.last_result = res
            self._end_execution(False)
            return res

    def find_malware(self, filepath: Optional[str] = None) -> Dict[str, Any]:
        image = filepath or self._image_path
        if not image:
            return self._build_result(success=False, action="find_malware", errors=["No memory image specified."])
        self._begin_execution()
        try:
            try:
                output = self._run_plugin(image, "windows.vadyarascan.VadYaraScan")
                matches = self._parse_table_output(output)
            except Exception:
                procs = self.list_processes(image)
                suspicious = []
                for proc in procs.get("parsed", {}).get("processes", []):
                    name = str(proc.get("ImageFileName", "")).lower()
                    if any(s in name for s in ("mimikatz", "mimilib", "pwdump", "gsecdump", "wce")):
                        suspicious.append(proc)
                matches = suspicious
            res = self._build_result(success=True, action="find_malware", output=matches,
                parsed={"matches": matches, "match_count": len(matches)})
            self.last_result = res
            self._end_execution(True)
            return res
        except Exception as exc:
            logger.exception("find_malware failed")
            res = self._build_result(success=False, action="find_malware", errors=[str(exc)])
            self.last_result = res
            self._end_execution(False)
            return res

    def extract_network(self, filepath: Optional[str] = None) -> Dict[str, Any]:
        image = filepath or self._image_path
        if not image:
            return self._build_result(success=False, action="extract_network", errors=["No memory image specified."])
        self._begin_execution()
        try:
            output = self._run_plugin(image, "windows.netscan.NetScan")
            connections = self._parse_table_output(output)
            res = self._build_result(success=True, action="extract_network", output=output,
                parsed={"connections": connections, "count": len(connections)})
            self.last_result = res
            self._end_execution(True)
            return res
        except Exception as exc:
            logger.exception("extract_network failed")
            res = self._build_result(success=False, action="extract_network", errors=[str(exc)])
            self.last_result = res
            self._end_execution(False)
            return res

    def dump_process(self, pid: int, filepath: Optional[str] = None) -> Dict[str, Any]:
        image = filepath or self._image_path
        if not image:
            return self._build_result(success=False, action="dump_process", errors=["No memory image specified."])
        self._begin_execution()
        try:
            output_dir = "/tmp/iris_volatility_dumps"
            os.makedirs(output_dir, exist_ok=True)
            cmd = ["python3", "-m", "volatility3", "-f", image, "-o", output_dir, "windows.memmap.Memmap", "--pid", str(pid), "--dump"]
            result = self._run_subprocess(cmd, timeout=300)
            res = self._build_result(success=result.returncode == 0, action="dump_process", output=result.stdout,
                parsed={"pid": pid, "output_dir": output_dir, "dumped": result.returncode == 0},
                errors=[result.stderr] if result.stderr and result.returncode != 0 else [])
            self.last_result = res
            self._end_execution(result.returncode == 0)
            return res
        except Exception as exc:
            logger.exception("dump_process failed")
            res = self._build_result(success=False, action="dump_process", errors=[str(exc)])
            self.last_result = res
            self._end_execution(False)
            return res

    def _parse_table_output(self, output: str) -> List[Dict[str, Any]]:
        lines = output.strip().splitlines()
        if not lines:
            return []
        header_idx = -1
        for i, line in enumerate(lines):
            if line.strip().startswith("PID") or line.strip().startswith("Offset") or "Volatility" in line:
                header_idx = i
                break
        if header_idx == -1 or header_idx + 1 >= len(lines):
            return []
        headers = [h.strip() for h in lines[header_idx].split("|") if h.strip()]
        rows = []
        for line in lines[header_idx + 2:]:
            if not line.strip() or line.strip().startswith("*"):
                continue
            cells = [c.strip() for c in line.split("|")]
            if len(cells) >= len(headers):
                rows.append(dict(zip(headers, cells[:len(headers)])))
        return rows


__all__ = ["VolatilityBridge"]
