"""Forensics Skill — Digital forensics, artifact analysis, timeline reconstruction."""

import os
import re
import hashlib
import logging
from typing import Dict, Any, List
from datetime import datetime
from skills import BaseSkill

logger = logging.getLogger(__name__)


class ForensicsSkill(BaseSkill):
    """Digital forensics, artifact extraction, and timeline reconstruction."""

    def __init__(self):
        super().__init__(name="forensics", category="security", capabilities=["forensics"])

    def execute(self, capability: str, params: Dict[str, Any]) -> Dict[str, Any]:
        method = params.get("method", "analyze_disk")
        if method == "analyze_disk":
            return self.analyze_disk(params)
        elif method == "reconstruct_timeline":
            return self.reconstruct_timeline(params)
        elif method == "extract_artifacts":
            return self.extract_artifacts(params)
        return {"error": f"Unknown method: {method}"}

    def analyze_disk(self, params: Dict[str, Any]) -> Dict[str, Any]:
        path = params.get("path", "")
        if not path or not os.path.exists(path):
            return {"success": False, "error": f"Path not found: {path}"}
        artifacts = []
        try:
            for root, dirs, files in os.walk(path):
                for f in files:
                    full_path = os.path.join(root, f)
                    try:
                        stat = os.stat(full_path)
                        file_hash = ""
                        if params.get("hash_files", False):
                            with open(full_path, 'rb') as fh:
                                file_hash = hashlib.sha256(fh.read()).hexdigest()
                        artifacts.append({"path": full_path, "size": stat.st_size, "modified": datetime.fromtimestamp(stat.st_mtime).isoformat(), "created": datetime.fromtimestamp(stat.st_ctime).isoformat(), "hash": file_hash})
                    except (OSError, PermissionError):
                        pass
                if len(artifacts) >= params.get("max_files", 1000):
                    break
        except Exception as e:
            return {"success": False, "error": str(e)}
        # Identify suspicious files
        suspicious = []
        for a in artifacts:
            lower_name = os.path.basename(a["path"]).lower()
            if any(lower_name.endswith(ext) for ext in ['.exe', '.dll', '.bat', '.ps1', '.vbs', '.js']):
                if any(kw in lower_name for kw in ['temp', 'tmp', 'cache', 'log']):
                    suspicious.append({"path": a["path"], "reason": "executable_in_temp", "hash": a["hash"]})
        return {"success": True, "path": path, "artifacts_found": len(artifacts), "artifacts": artifacts[:100], "suspicious_files": suspicious, "suspicious_count": len(suspicious)}

    def reconstruct_timeline(self, params: Dict[str, Any]) -> Dict[str, Any]:
        events = params.get("events", [])
        if not events:
            return {"success": False, "error": "No events provided"}
        sorted_events = sorted(events, key=lambda x: x.get("timestamp", ""))
        gaps = []
        for i in range(1, len(sorted_events)):
            prev = sorted_events[i - 1].get("timestamp", "")
            curr = sorted_events[i].get("timestamp", "")
            if prev and curr:
                try:
                    from datetime import datetime
                    prev_dt = datetime.fromisoformat(prev.replace('Z', '+00:00'))
                    curr_dt = datetime.fromisoformat(curr.replace('Z', '+00:00'))
                    gap_seconds = (curr_dt - prev_dt).total_seconds()
                    if gap_seconds > 3600:  # Gap > 1 hour
                        gaps.append({"between": [i - 1, i], "gap_seconds": int(gap_seconds), "start": prev, "end": curr})
                except ValueError:
                    pass
        return {"success": True, "events_processed": len(sorted_events), "timeline": sorted_events, "gaps": gaps, "gap_count": len(gaps)}

    def extract_artifacts(self, params: Dict[str, Any]) -> Dict[str, Any]:
        source = params.get("source", "")
        artifact_types = params.get("types", ["files", "registry", "logs"])
        if not source or not os.path.exists(source):
            return {"success": False, "error": f"Source not found: {source}"}
        extracted = []
        if "files" in artifact_types:
            for root, dirs, files in os.walk(source):
                for f in files:
                    full = os.path.join(root, f)
                    try:
                        stat = os.stat(full)
                        extracted.append({"type": "file", "path": full, "size": stat.st_size, "mtime": datetime.fromtimestamp(stat.st_mtime).isoformat()})
                    except OSError:
                        pass
                if len(extracted) >= 500:
                    break
        if "logs" in artifact_types:
            log_patterns = [r'\d{4}-\d{2}-\d{2}[T ]\d{2}:\d{2}:\d{2}', r'\w{3}\s+\d{1,2}\s+\d{2}:\d{2}:\d{2}']
            for art in extracted[:50]:
                if art["path"].endswith(('.log', '.txt')):
                    try:
                        with open(art["path"], 'r', errors='replace') as lf:
                            lines = lf.readlines()[:20]
                            timestamps = []
                            for line in lines:
                                for pat in log_patterns:
                                    m = re.search(pat, line)
                                    if m:
                                        timestamps.append(m.group(0))
                            if timestamps:
                                art["timestamps_found"] = timestamps
                    except Exception:
                        pass
        return {"success": True, "source": source, "artifacts": extracted[:200], "artifact_count": len(extracted), "types_searched": artifact_types}
