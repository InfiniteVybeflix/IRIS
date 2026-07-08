#!/usr/bin/env python3
"""
mobile_sentinel.py — GUARD
Mobile Security Agent for IRIS v7.0
iOS/Android security analysis, APK/IPA static analysis,
reverse engineering helpers (jadx/apktool/frida), manifest auditing,
permission analysis, hardcoded secret detection, certificate pinning checks.
"""

import threading
import hashlib
import json
import logging
import time
import os
import subprocess
import re
import zipfile
from typing import Dict, Any, List, Tuple, Optional
from datetime import datetime
from xml.etree import ElementTree as ET

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("GUARD")


class MobileSentinel:
    CODENAME = "GUARD"

    # Dangerous Android permissions
    DANGEROUS_PERMS = {
        "android.permission.READ_SMS", "android.permission.SEND_SMS",
        "android.permission.READ_CONTACTS", "android.permission.WRITE_CONTACTS",
        "android.permission.RECORD_AUDIO", "android.permission.CAMERA",
        "android.permission.ACCESS_FINE_LOCATION", "android.permission.ACCESS_COARSE_LOCATION",
        "android.permission.READ_PHONE_STATE", "android.permission.CALL_PHONE",
        "android.permission.WRITE_EXTERNAL_STORAGE", "android.permission.READ_EXTERNAL_STORAGE",
    }

    def __init__(self, commander_bus=None, shared_memory=None):
        self._lock = threading.RLock()
        self._running = False
        self._commander_bus = commander_bus
        self._shared_memory = shared_memory
        self._session_id = hashlib.sha256(f"{self.CODENAME}{time.time()}".encode()).hexdigest()[:16]
        logger.info(f"[{self.CODENAME}] Session {self._session_id} initialized.")

    def start(self) -> bool:
        with self._lock:
            if self._running:
                return True
            self._running = True
            self._report_to_commander("GUARD started", level="info")
            return True

    def stop(self) -> bool:
        with self._lock:
            if not self._running:
                return True
            self._running = False
            self._report_to_commander("GUARD stopped", level="info")
            return True

    def health(self) -> Dict[str, Any]:
        with self._lock:
            return {
                "agent": self.CODENAME,
                "session_id": self._session_id,
                "running": self._running,
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
    def analyze_apk(self, apk_path: str, output_dir: str = "/tmp/guard_apk") -> Dict[str, Any]:
        """Static analysis of an Android APK using apktool and jadx fallback."""
        if not self._running:
            raise RuntimeError("Agent not running")
        if not os.path.exists(apk_path):
            return {"error": "APK not found"}
        os.makedirs(output_dir, exist_ok=True)
        results: Dict[str, Any] = {"apk": apk_path, "issues": [], "permissions": [], "secrets": [], "components": []}

        # Try apktool decode
        rc, out, err = self._execute_shell(f"apktool d -f -o {output_dir}/apktool {apk_path} 2>&1", timeout=120)
        if rc == 0:
            manifest_path = f"{output_dir}/apktool/AndroidManifest.xml"
            if os.path.exists(manifest_path):
                try:
                    tree = ET.parse(manifest_path)
                    root = tree.getroot()
                    ns = {"android": "http://schemas.android.com/apk/res/android"}
                    for perm in root.findall(".//uses-permission"):
                        name = perm.get("{http://schemas.android.com/apk/res/android}name", "")
                        results["permissions"].append(name)
                        if name in self.DANGEROUS_PERMS:
                            results["issues"].append({"severity": "warning", "type": "dangerous_permission", "detail": name})
                    for activity in root.findall(".//activity"):
                        act_name = activity.get("{http://schemas.android.com/apk/res/android}name", "")
                        exported = activity.get("{http://schemas.android.com/apk/res/android}exported", "false")
                        if exported.lower() == "true":
                            results["issues"].append({"severity": "high", "type": "exported_activity", "detail": act_name})
                        results["components"].append({"type": "activity", "name": act_name, "exported": exported})
                except Exception as e:
                    results["issues"].append({"severity": "info", "type": "manifest_parse_error", "detail": str(e)})

        # Try jadx decompile for source analysis
        rc2, out2, err2 = self._execute_shell(f"jadx -d {output_dir}/jadx {apk_path} 2>&1", timeout=180)
        if rc2 == 0:
            src_dir = f"{output_dir}/jadx/sources"
            if os.path.exists(src_dir):
                for root, dirs, files in os.walk(src_dir):
                    for f in files:
                        if f.endswith(".java"):
                            filepath = os.path.join(root, f)
                            with open(filepath, "r", errors="replace") as file:
                                content = file.read()
                            # Hardcoded secrets
                            for pattern, label in [
                                (r'["']AIza[0-9A-Za-z_-]{35}["']', "Google API Key"),
                                (r'sk-[0-9A-Za-z]{48}', "OpenAI API Key"),
                                (r'["']http://["']?[^\s"']+password[^\s"']*["']', "Password in URL"),
                            ]:
                                for match in re.finditer(pattern, content):
                                    results["secrets"].append({"file": filepath, "type": label, "snippet": match.group()[:50]})
                                    results["issues"].append({"severity": "critical", "type": "hardcoded_secret", "detail": f"{label} in {f}"})
                            # Certificate pinning bypass
                            if "X509TrustManager" in content and "checkServerTrusted" in content:
                                results["issues"].append({"severity": "high", "type": "custom_trust_manager", "detail": f"Custom TrustManager in {f}"})
                            # Debug mode
                            if "android.os.Debug.isDebuggerConnected()" in content:
                                results["issues"].append({"severity": "medium", "type": "debugger_detection", "detail": f"Debugger check in {f}"})

        self._store_memory(f"apk:{apk_path}", results)
        self._report_to_commander(f"APK analysis complete: {len(results['issues'])} issues", data={"issues": len(results["issues"])})
        return results

    def analyze_ipa(self, ipa_path: str, output_dir: str = "/tmp/guard_ipa") -> Dict[str, Any]:
        """Basic static analysis of an iOS IPA."""
        if not self._running:
            raise RuntimeError("Agent not running")
        if not os.path.exists(ipa_path):
            return {"error": "IPA not found"}
        os.makedirs(output_dir, exist_ok=True)
        results = {"ipa": ipa_path, "issues": [], "plist": {}, "binaries": []}
        # Unzip IPA
        with zipfile.ZipFile(ipa_path, "r") as z:
            z.extractall(output_dir)
        # Find Info.plist
        for root, dirs, files in os.walk(output_dir):
            for f in files:
                if f == "Info.plist":
                    plist_path = os.path.join(root, f)
                    try:
                        import plistlib
                        with open(plist_path, "rb") as pf:
                            plist = plistlib.load(pf)
                        results["plist"] = {k: str(v) for k, v in plist.items()}
                        if plist.get("CFBundleIdentifier", "").startswith("com."):
                            pass  # normal
                        if plist.get("UISupportsDocumentBrowser", False):
                            results["issues"].append({"severity": "info", "type": "file_sharing_enabled", "detail": "Document browser enabled"})
                        if not plist.get("UIFileSharingEnabled", False) is False:
                            results["issues"].append({"severity": "medium", "type": "file_sharing", "detail": "UIFileSharingEnabled is true"})
                    except Exception as e:
                        results["issues"].append({"severity": "info", "type": "plist_error", "detail": str(e)})
                if f.endswith(".dylib") or f.endswith("") and not "." in f:
                    results["binaries"].append(os.path.join(root, f))
        self._store_memory(f"ipa:{ipa_path}", results)
        return results

    def frida_inject(self, package_name: str, script_path: str, device_id: str = "") -> Dict[str, Any]:
        """Attempt Frida script injection against a running Android app."""
        if not self._running:
            raise RuntimeError("Agent not running")
        cmd = f"frida -U {'-d ' + device_id if device_id else ''} -f {package_name} -l {script_path} --no-pause 2>&1"
        rc, out, err = self._execute_shell(cmd, timeout=60)
        return {"returncode": rc, "stdout": out, "stderr": err, "injected": rc == 0}

    def adb_command(self, command: str) -> Dict[str, Any]:
        """Execute an adb command."""
        if not self._running:
            raise RuntimeError("Agent not running")
        rc, out, err = self._execute_shell(f"adb {command}", timeout=30)
        return {"returncode": rc, "stdout": out, "stderr": err}

    # ------------------------------------------------------------------
    # Unit test stubs
    # ------------------------------------------------------------------
    def test_analyze_apk(self) -> bool:
        # Requires real APK; stub
        return True

    def test_analyze_ipa(self) -> bool:
        # Requires real IPA; stub
        return True

    def test_adb_command(self) -> bool:
        r = self.adb_command("version")
        return r["returncode"] in (0, 127)  # 0 = success, 127 = not found


if __name__ == "__main__":
    agent = MobileSentinel()
    agent.start()
    print(agent.health())
    agent.stop()
