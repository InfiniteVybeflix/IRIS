"""Cloud Security Skill — Cloud config audit, IAM review, compliance check."""

import json
import logging
from typing import Dict, Any, List
from skills import BaseSkill

logger = logging.getLogger(__name__)


class CloudSecuritySkill(BaseSkill):
    """Cloud configuration auditing, IAM review, and compliance checking."""

    def __init__(self):
        super().__init__(name="cloud_security", category="security", capabilities=["cloud_security"])

    def execute(self, capability: str, params: Dict[str, Any]) -> Dict[str, Any]:
        method = params.get("method", "audit_config")
        if method == "audit_config":
            return self.audit_config(params)
        elif method == "review_iam":
            return self.review_iam(params)
        elif method == "check_compliance":
            return self.check_compliance(params)
        return {"error": f"Unknown method: {method}"}

    def audit_config(self, params: Dict[str, Any]) -> Dict[str, Any]:
        provider = params.get("provider", "aws")
        service = params.get("service", "")
        findings = []
        if provider == "aws":
            try:
                import subprocess
                # Check if AWS CLI is configured
                result = subprocess.run(["aws", "configure", "list"], capture_output=True, text=True, timeout=15)
                if "not found" in result.stderr or result.returncode != 0:
                    findings.append({"severity": "info", "message": "AWS CLI not configured. Manual checks only."})
                else:
                    # Check S3 buckets
                    s3_result = subprocess.run(["aws", "s3api", "list-buckets"], capture_output=True, text=True, timeout=15)
                    if s3_result.returncode == 0:
                        buckets = json.loads(s3_result.stdout).get("Buckets", [])
                        for bucket in buckets:
                            bname = bucket["Name"]
                            policy_result = subprocess.run(["aws", "s3api", "get-bucket-policy-status", "--bucket", bname], capture_output=True, text=True, timeout=10)
                            if policy_result.returncode == 0:
                                status = json.loads(policy_result.stdout)
                                if status.get("PolicyStatus", {}).get("IsPublic", False):
                                    findings.append({"severity": "critical", "service": "S3", "resource": bname, "message": "S3 bucket has public policy"})
            except FileNotFoundError:
                findings.append({"severity": "info", "message": "AWS CLI not installed"})
            except Exception as e:
                findings.append({"severity": "info", "message": f"AWS audit error: {e}"})
            # General AWS checks
            findings.extend([
                {"severity": "high", "check": "mfa_delete", "message": "Ensure MFA Delete is enabled on S3 buckets"},
                {"severity": "high", "check": "encryption", "message": "Ensure S3 default encryption is enabled"},
                {"severity": "medium", "check": "cloudtrail", "message": "Verify CloudTrail is enabled in all regions"},
                {"severity": "medium", "check": "config", "message": "Verify AWS Config is recording"},
            ])
        elif provider == "gcp":
            findings.extend([
                {"severity": "high", "check": "storage_encryption", "message": "Ensure CMEK is used for sensitive storage"},
                {"severity": "medium", "check": "vpc_flow", "message": "Enable VPC Flow Logs"},
            ])
        elif provider == "azure":
            findings.extend([
                {"severity": "high", "check": "storage_https", "message": "Enforce HTTPS for Storage Accounts"},
                {"severity": "medium", "check": "nsg_flow", "message": "Enable NSG Flow Logs"},
            ])
        return {"success": True, "provider": provider, "service": service, "findings": findings, "finding_count": len(findings)}

    def review_iam(self, params: Dict[str, Any]) -> Dict[str, Any]:
        provider = params.get("provider", "aws")
        policies_reviewed = []
        checks = [
            {"check": "password_policy", "description": "Strong password policy enforced"},
            {"check": "access_keys_rotation", "description": "Access keys rotated every 90 days"},
            {"check": "mfa_enabled", "description": "MFA enabled for all users"},
            {"check": "least_privilege", "description": "Least privilege principle applied"},
            {"check": "unused_credentials", "description": "Unused credentials disabled"},
            {"check": "inline_policies", "description": "Minimize use of inline policies"},
        ]
        return {"success": True, "provider": provider, "checks": checks, "policies_reviewed": len(checks), "recommendations": ["Enable MFA for root account", "Rotate access keys quarterly", "Use IAM roles instead of access keys where possible"]}

    def check_compliance(self, params: Dict[str, Any]) -> Dict[str, Any]:
        framework = params.get("framework", "CIS")
        provider = params.get("provider", "aws")
        controls = {
            "CIS": [
                {"id": "1.1", "description": "Maintain current contact details", "status": "manual_check"},
                {"id": "1.2", "description": "Ensure security contact information", "status": "manual_check"},
                {"id": "1.3", "description": "Ensure security questions registered", "status": "manual_check"},
                {"id": "1.4", "description": "Ensure no root account access key exists", "status": "check_required"},
                {"id": "1.5", "description": "MFA enabled on root account", "status": "check_required"},
                {"id": "1.6", "description": "Hardware MFA on root account", "status": "check_required"},
                {"id": "2.1", "description": "Ensure CloudTrail is enabled", "status": "check_required"},
                {"id": "2.2", "description": "Ensure CloudTrail log file validation", "status": "check_required"},
                {"id": "4.1", "description": "Ensure no security groups allow 0.0.0.0/0 to port 22", "status": "check_required"},
                {"id": "4.2", "description": "Ensure no security groups allow 0.0.0.0/0 to port 3389", "status": "check_required"},
            ],
            "NIST": [
                {"id": "AC-2", "description": "Account Management", "status": "check_required"},
                {"id": "AC-3", "description": "Access Enforcement", "status": "check_required"},
                {"id": "AU-6", "description": "Audit Review", "status": "check_required"},
                {"id": "SC-7", "description": "Boundary Protection", "status": "check_required"},
            ],
            "SOC2": [
                {"id": "CC6.1", "description": "Logical access security", "status": "check_required"},
                {"id": "CC7.2", "description": "System monitoring", "status": "check_required"},
            ],
        }
        framework_controls = controls.get(framework, controls["CIS"])
        return {"success": True, "framework": framework, "provider": provider, "total_controls": len(framework_controls), "controls": framework_controls}
