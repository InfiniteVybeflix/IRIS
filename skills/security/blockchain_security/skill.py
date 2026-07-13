"""Blockchain Security Skill — Smart contract audit, transaction analysis."""

import re
import logging
from typing import Dict, Any, List
from skills import BaseSkill

logger = logging.getLogger(__name__)


class BlockchainSecuritySkill(BaseSkill):
    """Smart contract auditing and blockchain transaction analysis."""

    def __init__(self):
        super().__init__(name="blockchain_security", category="security", capabilities=["blockchain_security"])

    def execute(self, capability: str, params: Dict[str, Any]) -> Dict[str, Any]:
        method = params.get("method", "audit_contract")
        if method == "audit_contract":
            return self.audit_contract(params)
        elif method == "analyze_transactions":
            return self.analyze_transactions(params)
        return {"error": f"Unknown method: {method}"}

    def audit_contract(self, params: Dict[str, Any]) -> Dict[str, Any]:
        contract_code = params.get("contract_code", "")
        contract_path = params.get("contract_path", "")
        if contract_path and not contract_code:
            try:
                with open(contract_path, 'r') as f:
                    contract_code = f.read()
            except Exception as e:
                return {"success": False, "error": str(e)}
        if not contract_code:
            return {"success": False, "error": "No contract code provided"}
        issues = []
        lines = contract_code.split("\n")
        # Reentrancy detection
        if re.search(r'call\.value\s*\([^)]*\)\s*\{', contract_code) or re.search(r'\.call\s*\{[^}]*value:', contract_code):
            issues.append({"severity": "CRITICAL", "type": "reentrancy", "message": "Potential reentrancy vulnerability: external call before state update", "mitigation": "Use Checks-Effects-Interactions pattern. Update state before external calls."})
        # tx.origin
        if "tx.origin" in contract_code:
            issues.append({"severity": "HIGH", "type": "access_control", "message": "Use of tx.origin for authorization. Use msg.sender instead.", "mitigation": "Replace tx.origin with msg.sender for access control."})
        # block.timestamp manipulation
        if "block.timestamp" in contract_code or "block.number" in contract_code:
            issues.append({"severity": "LOW", "type": "time_manipulation", "message": "Use of block.timestamp/block.number for time-sensitive logic", "mitigation": "Accept time manipulation risk or use oracle for critical time dependencies."})
        # unchecked math (pre Solidity 0.8)
        if "unchecked" in contract_code:
            issues.append({"severity": "MEDIUM", "type": "unchecked_math", "message": "Use of unchecked block bypasses overflow/underflow protection", "mitigation": "Ensure unchecked blocks have manual bounds checking."})
        # delegatecall
        if "delegatecall" in contract_code:
            issues.append({"severity": "HIGH", "type": "delegatecall", "message": "Use of delegatecall can lead to proxy pattern vulnerabilities", "mitigation": "Ensure delegatecall target is trusted and validated."})
        # selfdestruct
        if "selfdestruct" in contract_code:
            issues.append({"severity": "MEDIUM", "type": "selfdestruct", "message": "Contract can be destroyed", "mitigation": "Ensure only authorized accounts can trigger selfdestruct."})
        # assembly usage
        if "assembly" in contract_code:
            issues.append({"severity": "INFO", "type": "assembly", "message": "Inline assembly used - manual review required", "mitigation": "Verify assembly blocks are correct and necessary."})
        # Visibility checks
        func_defs = re.findall(r'function\s+\w+\s*\([^)]*\)\s*(\w+)?', contract_code)
        for vis in func_defs:
            if not vis:
                issues.append({"severity": "MEDIUM", "type": "missing_visibility", "message": "Function without explicit visibility modifier defaults to public", "mitigation": "Add explicit visibility (public, external, internal, private)."})
        severity_counts = {"CRITICAL": 0, "HIGH": 0, "MEDIUM": 0, "LOW": 0, "INFO": 0}
        for i in issues:
            severity_counts[i["severity"]] = severity_counts.get(i["severity"], 0) + 1
        return {"success": True, "issues": issues, "issue_count": len(issues), "severity_counts": severity_counts, "lines_audited": len(lines), "recommendations": ["Use OpenZeppelin contracts where possible", "Run Slither static analysis", "Run Mythril symbolic execution", "Conduct formal audit for production"]}

    def analyze_transactions(self, params: Dict[str, Any]) -> Dict[str, Any]:
        tx_hash = params.get("tx_hash", "")
        blockchain = params.get("blockchain", "ethereum")
        if not tx_hash:
            return {"success": False, "error": "No transaction hash provided"}
        try:
            import urllib.request
            import json
            if blockchain == "ethereum":
                api_key = params.get("api_key", "")
                etherscan_url = f"https://api.etherscan.io/api?module=proxy&action=eth_getTransactionByHash&txhash={tx_hash}&apikey={api_key}"
                req = urllib.request.Request(etherscan_url)
                with urllib.request.urlopen(req, timeout=15) as resp:
                    data = json.loads(resp.read().decode())
                tx = data.get("result", {})
                return {"success": True, "tx_hash": tx_hash, "blockchain": blockchain, "from": tx.get("from", ""), "to": tx.get("to", ""), "value": int(tx.get("value", "0"), 16) if tx.get("value", "0x0").startswith("0x") else 0, "gas": int(tx.get("gas", "0"), 16) if tx.get("gas", "0x0").startswith("0x") else 0, "gas_price": int(tx.get("gasPrice", "0"), 16) if tx.get("gasPrice", "0x0").startswith("0x") else 0, "input_data": tx.get("input", "")[:200]}
        except Exception as e:
            return {"success": False, "error": str(e), "tx_hash": tx_hash}
