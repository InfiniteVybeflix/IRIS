#!/usr/bin/env python3
"""
quantum_seer.py — QBIT
Quantum Security Agent for IRIS v1.0
Quantum-safe cryptography assessment, PQC algorithm recommendations,
QKD planning, cryptographic inventory, RSA/ECC key size analysis,
hybrid scheme design, post-quantum migration roadmap.
"""

import threading
import hashlib
import json
import logging
import time
import os
import subprocess
import re
from typing import Dict, Any, List, Tuple, Optional
from datetime import datetime

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("QBIT")


class QuantumSeer:
    CODENAME = "QBIT"

    # NIST PQC algorithms (Round 3/4 winners)
    PQC_ALGORITHMS = {
        "KEM": [
            {"name": "ML-KEM-512", "standard": "FIPS 203", "security_level": 1, "notes": "Formerly Kyber"},
            {"name": "ML-KEM-768", "standard": "FIPS 203", "security_level": 3, "notes": "Recommended default"},
            {"name": "ML-KEM-1024", "standard": "FIPS 203", "security_level": 5, "notes": "Maximum security"},
        ],
        "Signature": [
            {"name": "ML-DSA-44", "standard": "FIPS 204", "security_level": 2, "notes": "Formerly Dilithium"},
            {"name": "ML-DSA-65", "standard": "FIPS 204", "security_level": 3, "notes": "Recommended default"},
            {"name": "ML-DSA-87", "standard": "FIPS 204", "security_level": 5, "notes": "Maximum security"},
            {"name": "SLH-DSA-SHA2-128s", "standard": "FIPS 205", "security_level": 1, "notes": "Stateless hash-based"},
            {"name": "FN-DSA", "standard": "FIPS 206", "security_level": 3, "notes": "Formerly Falcon"},
        ],
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
            self._report_to_commander("QBIT started", level="info")
            return True

    def stop(self) -> bool:
        with self._lock:
            if not self._running:
                return True
            self._running = False
            self._report_to_commander("QBIT stopped", level="info")
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
    def inventory_crypto(self, source_dir: str) -> Dict[str, Any]:
        """Scan source code for cryptographic usage and quantum vulnerability."""
        if not self._running:
            raise RuntimeError("Agent not running")
        findings: List[Dict[str, Any]] = []
        for root, dirs, files in os.walk(source_dir):
            for f in files:
                if f.endswith((".py", ".js", ".ts", ".java", ".go", ".rs", ".cpp", ".c", ".h", ".sol")):
                    filepath = os.path.join(root, f)
                    try:
                        with open(filepath, "r", errors="replace") as file:
                            content = file.read()
                    except Exception:
                        continue
                    # Detect RSA
                    for match in re.finditer(r"RSA[_-]?(?:generate|private|public|key|encrypt|decrypt|sign|verify)", content, re.IGNORECASE):
                        line = content[:match.start()].count("
") + 1
                        findings.append({"file": filepath, "line": line, "algorithm": "RSA", "risk": "quantum-vulnerable", "action": "Migrate to ML-DSA"})
                    # Detect ECC
                    for match in re.finditer(r"(?:EC|Elliptic|secp|curve25519|ed25519|ECDSA|ECDH)", content, re.IGNORECASE):
                        line = content[:match.start()].count("
") + 1
                        findings.append({"file": filepath, "line": line, "algorithm": "ECC", "risk": "quantum-vulnerable", "action": "Migrate to ML-DSA or hybrid"})
                    # Detect AES (symmetric, not quantum-vulnerable at same scale)
                    for match in re.finditer(r"AES[_-]?(?:encrypt|decrypt|GCM|CBC|CTR)", content, re.IGNORECASE):
                        line = content[:match.start()].count("
") + 1
                        findings.append({"file": filepath, "line": line, "algorithm": "AES", "risk": "needs-256-bit", "action": "Ensure AES-256 for quantum margin"})
                    # Detect DH
                    for match in re.finditer(r"DiffieHellman|DH[_-]?generate|createDH", content, re.IGNORECASE):
                        line = content[:match.start()].count("
") + 1
                        findings.append({"file": filepath, "line": line, "algorithm": "DH/ECDH", "risk": "quantum-vulnerable", "action": "Replace with ML-KEM"})
                    # Detect DSA
                    for match in re.finditer(r"DSA|createSign.*dsa", content, re.IGNORECASE):
                        line = content[:match.start()].count("
") + 1
                        findings.append({"file": filepath, "line": line, "algorithm": "DSA", "risk": "quantum-vulnerable", "action": "Replace with ML-DSA"})
                    # Detect SHA-1/MD5
                    for match in re.finditer(r"sha1|md5", content, re.IGNORECASE):
                        line = content[:match.start()].count("
") + 1
                        findings.append({"file": filepath, "line": line, "algorithm": "Weak Hash", "risk": "broken-classical", "action": "Use SHA-3 or SHA-256+"})
        summary = {
            "source_dir": source_dir,
            "files_scanned": sum(len(files) for _, _, files in os.walk(source_dir)),
            "findings": findings,
            "quantum_vulnerable": len([f for f in findings if f["risk"] == "quantum-vulnerable"]),
            "weak_classical": len([f for f in findings if f["risk"] == "broken-classical"]),
        }
        self._store_memory(f"inventory:{source_dir}", summary)
        self._report_to_commander(f"Crypto inventory: {summary['quantum_vulnerable']} quantum-vulnerable findings", data=summary)
        return summary

    def recommend_pqc(self, use_case: str, security_level: int = 3) -> List[Dict[str, Any]]:
        """Recommend PQC algorithms for a given use case and security level."""
        if not self._running:
            raise RuntimeError("Agent not running")
        recommendations: List[Dict[str, Any]] = []
        if use_case in ("key_encapsulation", "kem", "tls", "vpn"):
            for alg in self.PQC_ALGORITHMS["KEM"]:
                if alg["security_level"] >= security_level:
                    recommendations.append({"use_case": use_case, **alg})
        elif use_case in ("signature", "code_signing", "tls_auth", "document_signing"):
            for alg in self.PQC_ALGORITHMS["Signature"]:
                if alg["security_level"] >= security_level:
                    recommendations.append({"use_case": use_case, **alg})
        elif use_case == "hybrid":
            recommendations.append({"use_case": "hybrid_kem", "classical": "X25519", "pqc": "ML-KEM-768", "standard": "IETF draft", "notes": "Combine classical + PQC"})
            recommendations.append({"use_case": "hybrid_sig", "classical": "ECDSA P-256", "pqc": "ML-DSA-65", "standard": "IETF draft", "notes": "Combine classical + PQC"})
        self._store_memory(f"recommend:{use_case}", recommendations)
        return recommendations

    def design_qkd_network(self, nodes: List[str], distances_km: List[float], key_rate: int = 1000) -> Dict[str, Any]:
        """Design a QKD network topology with trusted-node relay planning."""
        if not self._running:
            raise RuntimeError("Agent not running")
        if len(nodes) != len(distances_km) + 1:
            return {"error": "distances_km must have length nodes-1"}
        links = []
        for i in range(len(nodes) - 1):
            dist = distances_km[i]
            # Simplified model: BB84 effective ~100km with decoy states
            max_single_span = 100.0
            hops = int(__import__("math").ceil(dist / max_single_span))
            links.append({
                "from": nodes[i],
                "to": nodes[i + 1],
                "distance_km": dist,
                "hops_required": hops,
                "trusted_relays": hops - 1,
                "estimated_key_rate": max(1, int(key_rate / hops)),
                "technology": "BB84 with decoy states" if dist <= 100 else "Twin-field QKD" if dist <= 500 else "Trusted-node relay",
            })
        design = {
            "nodes": nodes,
            "links": links,
            "total_hops": sum(l["hops_required"] for l in links),
            "total_trusted_relays": sum(l["trusted_relays"] for l in links),
            "aggregate_key_rate": min(l["estimated_key_rate"] for l in links),
        }
        self._store_memory(f"qkd:{','.join(nodes)}", design)
        return design

    def generate_migration_roadmap(self, current_algorithms: List[str], timeline_years: int = 3) -> List[Dict[str, Any]]:
        """Generate a phased migration roadmap from classical to PQC."""
        if not self._running:
            raise RuntimeError("Agent not running")
        phases = []
        phases.append({
            "phase": 1, "duration": "0-6 months", "name": "Inventory & Assessment",
            "tasks": ["Audit all crypto usage", "Identify quantum-vulnerable algorithms", "Map data sensitivity to crypto lifetime"],
            "algorithms_to_address": current_algorithms,
        })
        phases.append({
            "phase": 2, "duration": "6-18 months", "name": "Hybrid Deployment",
            "tasks": ["Deploy hybrid schemes (classical + PQC)", "Update TLS/SSL configs", "Test PQC libraries (liboqs, Bouncy Castle)"],
            "algorithms_to_deploy": ["ML-KEM-768 hybrid", "ML-DSA-65 hybrid"],
        })
        phases.append({
            "phase": 3, "duration": "18-30 months", "name": "PQC-First Transition",
            "tasks": ["Switch default to PQC", "Deprecate pure RSA/ECC for long-term data", "Update certificate chains"],
            "algorithms_to_deploy": ["ML-KEM-768", "ML-DSA-65"],
        })
        phases.append({
            "phase": 4, "duration": "30-36 months", "name": "Full PQC",
            "tasks": ["Remove classical fallback for sensitive data", "Complete QKD integration for highest sensitivity", "Validate with third-party audit"],
            "algorithms_to_deploy": ["ML-KEM-1024", "ML-DSA-87", "SLH-DSA"],
        })
        self._store_memory(f"roadmap:{hashlib.md5(json.dumps(current_algorithms).encode()).hexdigest()}", phases)
        return phases

    def analyze_key_strength(self, key_bits: int, algorithm: str) -> Dict[str, Any]:
        """Analyze classical vs quantum security strength of a key."""
        if not self._running:
            raise RuntimeError("Agent not running")
        classical = key_bits
        if algorithm.lower() in ("rsa", "dsa", "dh"):
            # Shor's algorithm: roughly polynomial in key bits
            quantum = "broken"
            equivalent_pqc = "ML-DSA-65" if key_bits >= 2048 else "ML-DSA-44"
        elif algorithm.lower() in ("ecdsa", "ecdh", "ed25519", "curve25519"):
            quantum = "broken"
            equivalent_pqc = "ML-DSA-65" if key_bits >= 256 else "ML-DSA-44"
        elif algorithm.lower().startswith("aes"):
            # Grover's: sqrt(2^n) -> effectively halves key bits
            quantum = key_bits // 2
            equivalent_pqc = "AES-256 required for 128-bit quantum security"
        else:
            quantum = "unknown"
            equivalent_pqc = "unknown"
        return {
            "algorithm": algorithm,
            "key_bits": key_bits,
            "classical_security_bits": classical,
            "quantum_security": quantum,
            "recommended_pqc": equivalent_pqc,
            "action": "Migrate immediately" if quantum == "broken" else "Ensure 256-bit keys" if algorithm.lower().startswith("aes") else "Review",
        }

    # ------------------------------------------------------------------
    # Unit test stubs
    # ------------------------------------------------------------------
    def test_inventory_crypto(self) -> bool:
        import tempfile
        with tempfile.TemporaryDirectory() as td:
            with open(os.path.join(td, "test.py"), "w") as f:
                f.write("from Crypto.PublicKey import RSA\nkey = RSA.generate(2048)\n")
            r = self.inventory_crypto(td)
            return any(f["algorithm"] == "RSA" for f in r["findings"])

    def test_recommend_pqc(self) -> bool:
        r = self.recommend_pqc("signature", 3)
        return any(a["name"].startswith("ML-DSA") for a in r)

    def test_design_qkd(self) -> bool:
        r = self.design_qkd_network(["HQ", "Branch1", "Branch2"], [50.0, 120.0])
        return r["total_hops"] >= 2

    def test_migration_roadmap(self) -> bool:
        r = self.generate_migration_roadmap(["RSA-2048", "ECDSA P-256"])
        return len(r) == 4

    def test_key_strength(self) -> bool:
        r = self.analyze_key_strength(2048, "RSA")
        return r["quantum_security"] == "broken"


if __name__ == "__main__":
    agent = QuantumSeer()
    agent.start()
    print(agent.health())
    agent.stop()
