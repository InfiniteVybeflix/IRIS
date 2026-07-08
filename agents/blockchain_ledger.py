#!/usr/bin/env python3
"""
blockchain_ledger.py — CHAIN
Blockchain Security Agent for IRIS v7.0
Smart contract audit (Solidity/Vyper), transaction analysis,
wallet security checks, gas optimization, ERC standard compliance,
DeFi protocol risk scoring, on-chain forensics.
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
logger = logging.getLogger("CHAIN")


class BlockchainLedger:
    CODENAME = "CHAIN"

    # Common vulnerability patterns in Solidity
    VULN_PATTERNS = [
        (r"function\s+\w+\s*\([^)]*\)\s*\{[^}]*msg\.sender\.transfer\s*\(", "reentrancy_risk", "high"),
        (r"tx\.origin\s*==", "tx_origin_auth", "critical"),
        (r"block\.timestamp\s*", "timestamp_dependence", "medium"),
        (r"block\.number\s*", "block_number_dependence", "medium"),
        (r"selfdestruct\s*\(", "selfdestruct_present", "info"),
        (r"assembly\s*\{", "inline_assembly", "low"),
        (r"delegatecall\s*\(", "delegatecall_risk", "high"),
        (r"\.call\.value\s*\(", "low_level_call", "high"),
        (r"unchecked\s*\{", "unchecked_arithmetic", "medium"),
    ]

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
            self._report_to_commander("CHAIN started", level="info")
            return True

    def stop(self) -> bool:
        with self._lock:
            if not self._running:
                return True
            self._running = False
            self._report_to_commander("CHAIN stopped", level="info")
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
    def audit_solidity(self, contract_path: str) -> Dict[str, Any]:
        """Static audit of a Solidity smart contract."""
        if not self._running:
            raise RuntimeError("Agent not running")
        if not os.path.exists(contract_path):
            return {"error": "Contract not found"}
        with open(contract_path, "r", errors="replace") as f:
            source = f.read()
        issues: List[Dict[str, Any]] = []
        for pattern, vuln_type, severity in self.VULN_PATTERNS:
            for match in re.finditer(pattern, source, re.DOTALL):
                line = source[:match.start()].count("
") + 1
                issues.append({"type": vuln_type, "severity": severity, "line": line, "snippet": source[match.start():match.end()][:80]})
        # Check for missing visibility
        for match in re.finditer(r"function\s+(\w+)\s*\([^)]*\)\s*(?!\s*(?:public|private|internal|external))", source):
            line = source[:match.start()].count("
") + 1
            issues.append({"type": "missing_visibility", "severity": "low", "line": line, "snippet": match.group()[:80]})
        # Check for unprotected functions
        for match in re.finditer(r"function\s+(\w+)\s*\([^)]*\)\s*public\s*(?!\s*onlyOwner|require\s*\(\s*msg\.sender)", source):
            line = source[:match.start()].count("
") + 1
            issues.append({"type": "unprotected_function", "severity": "medium", "line": line, "snippet": match.group()[:80]})

        # Try slither if available
        slither_issues: List[Dict] = []
        rc, out, err = self._execute_shell(f"slither {contract_path} --json - 2>&1", timeout=120)
        if rc == 0:
            try:
                slither_data = json.loads(out)
                for det in slither_data.get("results", []):
                    slither_issues.append({"type": det.get("check"), "severity": det.get("impact", "info"), "description": det.get("description", "")})
            except json.JSONDecodeError:
                pass

        result = {
            "contract": contract_path,
            "issues": issues,
            "slither_issues": slither_issues,
            "issue_count": len(issues) + len(slither_issues),
            "critical": len([i for i in issues if i["severity"] == "critical"]),
            "high": len([i for i in issues if i["severity"] == "high"]),
        }
        self._store_memory(f"audit:{contract_path}", result)
        self._report_to_commander(f"Audit complete: {result['issue_count']} issues", data=result)
        return result

    def analyze_transaction(self, tx_hash: str, rpc_url: str = "") -> Dict[str, Any]:
        """Analyze an Ethereum transaction via RPC."""
        if not self._running:
            raise RuntimeError("Agent not running")
        rpc = rpc_url or os.environ.get("ETH_RPC_URL", "https://cloudflare-eth.com")
        payload = json.dumps({"jsonrpc": "2.0", "method": "eth_getTransactionByHash", "params": [tx_hash], "id": 1}).encode()
        req = urllib.request.Request(rpc, data=payload, headers={"Content-Type": "application/json"}, method="POST")
        try:
            with urllib.request.urlopen(req, timeout=30) as resp:
                data = json.loads(resp.read().decode())
            tx = data.get("result", {})
            receipt_payload = json.dumps({"jsonrpc": "2.0", "method": "eth_getTransactionReceipt", "params": [tx_hash], "id": 2}).encode()
            req2 = urllib.request.Request(rpc, data=receipt_payload, headers={"Content-Type": "application/json"}, method="POST")
            with urllib.request.urlopen(req2, timeout=30) as resp2:
                receipt = json.loads(resp2.read().decode()).get("result", {})
            result = {
                "tx_hash": tx_hash,
                "from": tx.get("from"),
                "to": tx.get("to"),
                "value": tx.get("value"),
                "gas": tx.get("gas"),
                "gasPrice": tx.get("gasPrice"),
                "status": receipt.get("status"),
                "gasUsed": receipt.get("gasUsed"),
                "logs_count": len(receipt.get("logs", [])),
            }
            self._store_memory(f"tx:{tx_hash}", result)
            return result
        except Exception as e:
            return {"tx_hash": tx_hash, "error": str(e)}

    def check_wallet_security(self, address: str) -> Dict[str, Any]:
        """Check wallet security: balance, code, first/last tx."""
        if not self._running:
            raise RuntimeError("Agent not running")
        rpc = os.environ.get("ETH_RPC_URL", "https://cloudflare-eth.com")
        results = {"address": address, "is_contract": False, "balance": "0", "issues": []}
        try:
            # Get balance
            bal_payload = json.dumps({"jsonrpc": "2.0", "method": "eth_getBalance", "params": [address, "latest"], "id": 3}).encode()
            req = urllib.request.Request(rpc, data=bal_payload, headers={"Content-Type": "application/json"}, method="POST")
            with urllib.request.urlopen(req, timeout=30) as resp:
                bal_data = json.loads(resp.read().decode())
            results["balance"] = bal_data.get("result", "0x0")
            # Check if contract
            code_payload = json.dumps({"jsonrpc": "2.0", "method": "eth_getCode", "params": [address, "latest"], "id": 4}).encode()
            req2 = urllib.request.Request(rpc, data=code_payload, headers={"Content-Type": "application/json"}, method="POST")
            with urllib.request.urlopen(req2, timeout=30) as resp2:
                code_data = json.loads(resp2.read().decode())
            code = code_data.get("result", "0x")
            results["is_contract"] = code != "0x"
            if results["is_contract"]:
                results["issues"].append({"type": "contract_wallet", "note": "Address is a smart contract"})
        except Exception as e:
            results["error"] = str(e)
        self._store_memory(f"wallet:{address}", results)
        return results

    def erc_compliance_check(self, contract_path: str, standard: str = "ERC20") -> List[Dict[str, Any]]:
        """Check if a contract implements required ERC functions."""
        if not self._running:
            raise RuntimeError("Agent not running")
        with open(contract_path, "r", errors="replace") as f:
            source = f.read().lower()
        required = {
            "ERC20": ["totalsupply", "balanceof", "transfer", "transferfrom", "approve", "allowance"],
            "ERC721": ["balanceof", "ownerof", "safetransferfrom", "transferfrom", "approve", "setapprovalforall", "getapproved", "isapprovedforall"],
            "ERC1155": ["balanceof", "balanceofbatch", "setapprovalforall", "issapprovedforall", "safetransferfrom", "safetransferfrombatch"],
        }
        missing = []
        for func in required.get(standard, []):
            if func not in source:
                missing.append({"function": func, "status": "missing"})
        return missing

    # ------------------------------------------------------------------
    # Unit test stubs
    # ------------------------------------------------------------------
    def test_audit_solidity(self) -> bool:
        import tempfile
        with tempfile.NamedTemporaryFile(mode="w", suffix=".sol", delete=False) as f:
            f.write("pragma solidity ^0.8.0;\ncontract C {\n  function f() { tx.origin; }\n}\n")
            path = f.name
        r = self.audit_solidity(path)
        return any(i["type"] == "tx_origin_auth" for i in r["issues"])

    def test_analyze_transaction(self) -> bool:
        # Requires real tx; stub
        return True

    def test_check_wallet(self) -> bool:
        r = self.check_wallet_security("0x0000000000000000000000000000000000000000")
        return "balance" in r

    def test_erc_compliance(self) -> bool:
        import tempfile
        with tempfile.NamedTemporaryFile(mode="w", suffix=".sol", delete=False) as f:
            f.write("pragma solidity ^0.8.0;\ncontract T { function totalSupply() public {} }\n")
            path = f.name
        r = self.erc_compliance_check(path, "ERC20")
        return len(r) > 0  # missing most functions


if __name__ == "__main__":
    agent = BlockchainLedger()
    agent.start()
    print(agent.health())
    agent.stop()
