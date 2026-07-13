"""
IRIS v1.0 — File Watcher

Monitor file system changes, unauthorized access, permission changes,
and ransomware-like mass encryption patterns.

Dependencies: watchdog (optional)
"""

from __future__ import annotations

import logging
import os
import threading
from collections import defaultdict
from typing import Any, Dict, List, Optional, Set

from .base_sense import BaseSense

logger = logging.getLogger(__name__)


class FileWatcher(BaseSense):
    """File system monitoring and anomaly detection."""

    name: str = "file_watcher"
    interval: int = 10
    thresholds: Dict[str, Any] = {"max_changes_per_interval": 100, "max_permission_changes": 10, "ransware_entropy_threshold": 0.7}

    def __init__(self, iris_core: Optional[Any] = None) -> None:
        super().__init__(iris_core)
        self._watched_paths: Set[str] = set()
        self._recursive: Dict[str, bool] = {}
        self._snapshots: Dict[str, Dict[str, Any]] = {}
        self._changes_buffer: List[Dict[str, Any]] = []
        self._buffer_lock: threading.Lock = threading.Lock()

    def watch_path(self, path: str, recursive: bool = True) -> None:
        safe_path = os.path.abspath(os.path.expanduser(path))
        if not os.path.isdir(safe_path):
            logger.warning(f"Not a directory: {safe_path}")
            return
        self._watched_paths.add(safe_path)
        self._recursive[safe_path] = recursive
        logger.info(f"Watching: {safe_path} (recursive={recursive})")

    def _sense(self) -> Dict[str, Any]:
        findings: Dict[str, Any] = {"changes": [], "permission_changes": [], "ransware_indicators": [], "watched_paths": list(self._watched_paths)}
        if not self._watched_paths:
            return findings
        for path in self._watched_paths:
            current = self._snapshot_path(path, self._recursive.get(path, True))
            previous = self._snapshots.get(path, {})
            for filepath, meta in current.items():
                if filepath not in previous:
                    findings["changes"].append({"type": "created", "path": filepath, "size": meta["size"]})
                elif previous[filepath]["mtime"] != meta["mtime"]:
                    findings["changes"].append({"type": "modified", "path": filepath, "old_size": previous[filepath]["size"], "new_size": meta["size"]})
                if previous.get(filepath, {}).get("mode") != meta["mode"]:
                    findings["permission_changes"].append({"path": filepath, "old_mode": previous[filepath]["mode"], "new_mode": meta["mode"]})
            for filepath in previous:
                if filepath not in current:
                    findings["changes"].append({"type": "deleted", "path": filepath})
            modified = [c for c in findings["changes"] if c["type"] == "modified"]
            if len(modified) > self.thresholds.get("max_changes_per_interval", 100):
                entropy_changes = 0
                for change in modified[:50]:
                    try:
                        if self._calculate_entropy(change["path"]) > self.thresholds.get("ransware_entropy_threshold", 0.7):
                            entropy_changes += 1
                    except Exception:
                        pass
                if entropy_changes > 20:
                    findings["ransware_indicators"].append({"type": "mass_encryption_detected", "modified_count": len(modified),
                        "high_entropy_count": entropy_changes, "severity": "critical"})
            self._snapshots[path] = current
        return findings

    def _snapshot_path(self, path: str, recursive: bool) -> Dict[str, Dict[str, Any]]:
        snapshot: Dict[str, Dict[str, Any]] = {}
        try:
            for root, dirs, files in os.walk(path):
                if not recursive and root != path:
                    dirs[:] = []
                for filename in files:
                    filepath = os.path.join(root, filename)
                    try:
                        stat = os.stat(filepath)
                        snapshot[filepath] = {"size": stat.st_size, "mtime": stat.st_mtime, "mode": stat.st_mode, "inode": stat.st_ino}
                    except (OSError, PermissionError):
                        pass
        except Exception as exc:
            logger.error(f"Snapshot error: {exc}")
        return snapshot

    def _calculate_entropy(self, filepath: str) -> float:
        try:
            with open(filepath, "rb") as f:
                data = f.read(8192)
            if not data:
                return 0.0
            from collections import Counter
            import math
            counts = Counter(data)
            length = len(data)
            return -sum((c / length) * math.log2(c / length) for c in counts.values()) / 8.0
        except Exception:
            return 0.0

    def _should_alert(self, result: Dict[str, Any]) -> bool:
        if not result.get("success"):
            return True
        output = result.get("output", {})
        if output.get("ransware_indicators"):
            return True
        if len(output.get("permission_changes", [])) > self.thresholds.get("max_permission_changes", 10):
            return True
        if len(output.get("changes", [])) > self.thresholds.get("max_changes_per_interval", 100):
            return True
        return False

    def _emit_alert(self, result: Dict[str, Any]) -> None:
        output = result.get("output", {})
        severity = "critical" if output.get("ransware_indicators") else "warning"
        self.report({"type": "filesystem_alert", "sense": self.name, "severity": severity,
            "message": f"File system anomaly: {len(output.get('changes', []))} changes", "data": output})

    def check_permissions(self, path: Optional[str] = None) -> Dict[str, Any]:
        self._begin_check()
        try:
            targets = [path] if path else list(self._watched_paths)
            findings: List[Dict[str, Any]] = []
            for target in targets:
                safe_target = os.path.abspath(os.path.expanduser(target))
                for root, _, files in os.walk(safe_target):
                    for filename in files:
                        filepath = os.path.join(root, filename)
                        try:
                            stat = os.stat(filepath)
                            mode = stat.st_mode
                            if mode & 0o002:
                                findings.append({"path": filepath, "issue": "world_writable", "mode": oct(mode)})
                            if mode & 0o4000 or mode & 0o2000:
                                findings.append({"path": filepath, "issue": "setuid_setgid", "mode": oct(mode)})
                        except (OSError, PermissionError):
                            pass
            res = self._build_result(success=True, action="check_permissions", output=findings,
                parsed={"finding_count": len(findings), "findings": findings})
            self.last_result = res
            self._end_check(True)
            return res
        except Exception as exc:
            logger.exception("check_permissions failed")
            res = self._build_result(success=False, action="check_permissions", errors=[str(exc)])
            self.last_result = res
            self._end_check(False)
            return res

    def detect_ransomware_patterns(self, path: Optional[str] = None) -> Dict[str, Any]:
        self._begin_check()
        try:
            targets = [path] if path else list(self._watched_paths)
            indicators: List[Dict[str, Any]] = []
            for target in targets:
                safe_target = os.path.abspath(os.path.expanduser(target))
                high_entropy = total = 0
                for root, _, files in os.walk(safe_target):
                    for filename in files:
                        try:
                            ent = self._calculate_entropy(os.path.join(root, filename))
                            total += 1
                            if ent > self.thresholds.get("ransware_entropy_threshold", 0.7):
                                high_entropy += 1
                        except Exception:
                            pass
                        if total >= 100:
                            break
                    if total >= 100:
                        break
                if total > 0 and high_entropy / total > 0.3:
                    indicators.append({"path": safe_target, "high_entropy_ratio": high_entropy / total,
                        "high_entropy_count": high_entropy, "total_checked": total, "severity": "critical"})
            res = self._build_result(success=True, action="detect_ransomware_patterns", output=indicators,
                parsed={"indicator_count": len(indicators), "indicators": indicators})
            self.last_result = res
            self._end_check(True)
            return res
        except Exception as exc:
            logger.exception("detect_ransomware_patterns failed")
            res = self._build_result(success=False, action="detect_ransomware_patterns", errors=[str(exc)])
            self.last_result = res
            self._end_check(False)
            return res


__all__ = ["FileWatcher"]
