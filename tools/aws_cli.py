"""
IRIS v7.0 — AWS CLI Wrapper

AWS API operations via boto3. Resource enumeration, security analysis,
IAM auditing, compliance checks, CloudTrail log retrieval.

Dependencies: boto3, botocore
"""

from __future__ import annotations

import logging
import os
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

from .base_tool import BaseTool

logger = logging.getLogger(__name__)


class AWSCLI(BaseTool):
    """AWS cloud operations and security auditing."""

    name: str = "aws_cli"
    category: str = "cloud"
    dependencies: List[str] = ["boto3", "botocore"]

    def __init__(self, region: Optional[str] = None, profile: Optional[str] = None, iris_core: Optional[Any] = None) -> None:
        super().__init__(iris_core)
        self.region = region or os.environ.get("AWS_DEFAULT_REGION", "us-east-1")
        self.profile = profile or os.environ.get("AWS_PROFILE", None)
        self._sessions: Dict[str, Any] = {}

    def _get_session(self, service: str) -> Any:
        if service not in self._sessions:
            try:
                import boto3
                kwargs = {"region_name": self.region}
                if self.profile:
                    kwargs["profile_name"] = self.profile
                self._sessions[service] = boto3.Session(**kwargs).client(service)
            except Exception as exc:
                raise RuntimeError(f"boto3 client creation failed for {service}: {exc}")
        return self._sessions[service]

    def _run(self, *args: Any, **kwargs: Any) -> Dict[str, Any]:
        return {}

    def list_resources(self, service: str) -> Dict[str, Any]:
        self._begin_execution()
        try:
            safe_service = self.sanitize_input(service).lower()
            client = self._get_session(safe_service)
            resources: List[Dict[str, Any]] = []
            if safe_service == "ec2":
                for page in client.get_paginator("describe_instances").paginate():
                    for r in page.get("Reservations", []):
                        for inst in r.get("Instances", []):
                            resources.append({"id": inst.get("InstanceId"), "type": inst.get("InstanceType"),
                                "state": inst.get("State", {}).get("Name"), "public_ip": inst.get("PublicIpAddress"),
                                "private_ip": inst.get("PrivateIpAddress"),
                                "launch_time": inst.get("LaunchTime").isoformat() if inst.get("LaunchTime") else None})
            elif safe_service == "s3":
                for bucket in client.list_buckets().get("Buckets", []):
                    resources.append({"name": bucket.get("Name"),
                        "created": bucket.get("CreationDate").isoformat() if bucket.get("CreationDate") else None})
            elif safe_service == "rds":
                for page in client.get_paginator("describe_db_instances").paginate():
                    for db in page.get("DBInstances", []):
                        resources.append({"id": db.get("DBInstanceIdentifier"), "engine": db.get("Engine"),
                            "status": db.get("DBInstanceStatus"), "publicly_accessible": db.get("PubliclyAccessible", False)})
            elif safe_service == "lambda":
                for page in client.get_paginator("list_functions").paginate():
                    for func in page.get("Functions", []):
                        resources.append({"name": func.get("FunctionName"), "runtime": func.get("Runtime"), "last_modified": func.get("LastModified")})
            elif safe_service == "iam":
                for page in client.get_paginator("list_users").paginate():
                    for user in page.get("Users", []):
                        resources.append({"name": user.get("UserName"), "arn": user.get("Arn"),
                            "created": user.get("CreateDate").isoformat() if user.get("CreateDate") else None})
            else:
                return self._build_result(success=False, action="list_resources", errors=[f"Service '{safe_service}' not supported."])
            res = self._build_result(success=True, action="list_resources", output=resources,
                parsed={"service": safe_service, "resource_count": len(resources), "resources": resources})
            self.last_result = res
            self._end_execution(True)
            return res
        except Exception as exc:
            logger.exception(f"list_resources failed for {service}")
            res = self._build_result(success=False, action="list_resources", errors=[str(exc)])
            self.last_result = res
            self._end_execution(False)
            return res

    def check_security(self, service: str) -> Dict[str, Any]:
        self._begin_execution()
        try:
            safe_service = self.sanitize_input(service).lower()
            findings: List[Dict[str, Any]] = []
            if safe_service == "ec2":
                ec2 = self._get_session("ec2")
                for page in ec2.get_paginator("describe_security_groups").paginate():
                    for sg in page.get("SecurityGroups", []):
                        for rule in sg.get("IpPermissions", []):
                            for ip_range in rule.get("IpRanges", []):
                                if ip_range.get("CidrIp") == "0.0.0.0/0":
                                    findings.append({"type": "open_security_group", "severity": "high", "resource": sg.get("GroupId"),
                                        "port": f"{rule.get('FromPort')}-{rule.get('ToPort')}", "protocol": rule.get("IpProtocol"),
                                        "description": "Security group allows traffic from 0.0.0.0/0"})
            elif safe_service == "s3":
                s3 = self._get_session("s3")
                for bucket in s3.list_buckets().get("Buckets", []):
                    name = bucket.get("Name")
                    try:
                        acl = s3.get_bucket_acl(Bucket=name)
                        for grant in acl.get("Grants", []):
                            if grant.get("Grantee", {}).get("URI") == "http://acs.amazonaws.com/groups/global/AllUsers":
                                findings.append({"type": "public_s3_bucket", "severity": "high", "resource": name,
                                    "permission": grant.get("Permission"), "description": "S3 bucket grants public access"})
                    except Exception as exc:
                        findings.append({"type": "s3_acl_error", "severity": "low", "resource": name, "description": str(exc)})
            elif safe_service == "rds":
                rds = self._get_session("rds")
                for page in rds.get_paginator("describe_db_instances").paginate():
                    for db in page.get("DBInstances", []):
                        if db.get("PubliclyAccessible", False):
                            findings.append({"type": "public_rds_instance", "severity": "high", "resource": db.get("DBInstanceIdentifier"),
                                "description": "RDS instance is publicly accessible"})
            severity_counts: Dict[str, int] = {}
            for f in findings:
                sev = f.get("severity", "unknown")
                severity_counts[sev] = severity_counts.get(sev, 0) + 1
            res = self._build_result(success=True, action="check_security", output=findings,
                parsed={"service": safe_service, "finding_count": len(findings), "severity_breakdown": severity_counts, "findings": findings})
            self.last_result = res
            self._end_execution(True)
            return res
        except Exception as exc:
            logger.exception(f"check_security failed for {service}")
            res = self._build_result(success=False, action="check_security", errors=[str(exc)])
            self.last_result = res
            self._end_execution(False)
            return res

    def audit_iam(self) -> Dict[str, Any]:
        self._begin_execution()
        try:
            iam = self._get_session("iam")
            findings: List[Dict[str, Any]] = []
            for page in iam.get_paginator("list_users").paginate():
                for user in page.get("Users", []):
                    username = user.get("UserName")
                    for key in iam.list_access_keys(UserName=username).get("AccessKeyMetadata", []):
                        if key.get("Status") == "Active":
                            last_used = iam.get_access_key_last_used(AccessKeyId=key.get("AccessKeyId"))
                            lud = last_used.get("AccessKeyLastUsed", {}).get("LastUsedDate")
                            if lud:
                                days = (datetime.now(timezone.utc) - lud).days
                                if days > 90:
                                    findings.append({"type": "unused_access_key", "severity": "medium", "user": username,
                                        "key_id": key.get("AccessKeyId"), "days_since_use": days,
                                        "description": f"Access key unused for {days} days"})
            for page in iam.get_paginator("list_users").paginate():
                for user in page.get("Users", []):
                    if not iam.list_mfa_devices(UserName=user.get("UserName")).get("MFADevices"):
                        findings.append({"type": "no_mfa", "severity": "medium", "user": user.get("UserName"),
                            "description": "User does not have MFA enabled"})
            res = self._build_result(success=True, action="audit_iam", output=findings,
                parsed={"finding_count": len(findings), "findings": findings})
            self.last_result = res
            self._end_execution(True)
            return res
        except Exception as exc:
            logger.exception("audit_iam failed")
            res = self._build_result(success=False, action="audit_iam", errors=[str(exc)])
            self.last_result = res
            self._end_execution(False)
            return res

    def check_compliance(self, standard: str = "soc2") -> Dict[str, Any]:
        self._begin_execution()
        try:
            safe_standard = self.sanitize_input(standard).lower()
            checks: List[Dict[str, Any]] = []
            if safe_standard in ("soc2", "iso27001", "pci-dss"):
                s3 = self._get_session("s3")
                for bucket in s3.list_buckets().get("Buckets", []):
                    name = bucket.get("Name")
                    try:
                        enc = s3.get_bucket_encryption(Bucket=name)
                        rules = enc.get("ServerSideEncryptionConfiguration", {}).get("Rules", [])
                        if not rules:
                            checks.append({"control": "encryption_at_rest", "status": "fail", "resource": name,
                                "standard": safe_standard, "description": "S3 bucket lacks default encryption"})
                        else:
                            checks.append({"control": "encryption_at_rest", "status": "pass", "resource": name,
                                "standard": safe_standard, "description": "S3 bucket has default encryption"})
                    except Exception:
                        checks.append({"control": "encryption_at_rest", "status": "fail", "resource": name,
                            "standard": safe_standard, "description": "Unable to verify S3 bucket encryption"})
            passed = sum(1 for c in checks if c["status"] == "pass")
            res = self._build_result(success=True, action="check_compliance", output=checks,
                parsed={"standard": safe_standard, "total_checks": len(checks), "passed": passed, "failed": len(checks) - passed, "checks": checks})
            self.last_result = res
            self._end_execution(True)
            return res
        except Exception as exc:
            logger.exception("check_compliance failed")
            res = self._build_result(success=False, action="check_compliance", errors=[str(exc)])
            self.last_result = res
            self._end_execution(False)
            return res

    def get_cloudtrail_events(self, hours: int = 24) -> Dict[str, Any]:
        self._begin_execution()
        try:
            ct = self._get_session("cloudtrail")
            end = datetime.now(timezone.utc)
            start = end - timedelta(hours=hours)
            events: List[Dict[str, Any]] = []
            for page in ct.get_paginator("lookup_events").paginate(StartTime=start, EndTime=end):
                for event in page.get("Events", []):
                    events.append({"event_id": event.get("EventId"), "event_name": event.get("EventName"),
                        "event_time": event.get("EventTime").isoformat() if event.get("EventTime") else None,
                        "username": event.get("Username"), "source_ip": event.get("SourceIPAddress")})
            res = self._build_result(success=True, action="get_cloudtrail_events", output=events,
                parsed={"hours": hours, "event_count": len(events), "events": events})
            self.last_result = res
            self._end_execution(True)
            return res
        except Exception as exc:
            logger.exception("get_cloudtrail_events failed")
            res = self._build_result(success=False, action="get_cloudtrail_events", errors=[str(exc)])
            self.last_result = res
            self._end_execution(False)
            return res


__all__ = ["AWSCLI"]
