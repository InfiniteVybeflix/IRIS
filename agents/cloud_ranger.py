"""
cloud_ranger.py — NEBULA
Cloud security agent. AWS/Azure/GCP security posture assessment, IAM policy
analysis, S3 bucket security, container registry scanning, compliance mapping
(SOC 2, ISO 27001, PCI-DSS).
"""

import logging
import os
import re
import json
import hashlib
import subprocess
import threading
import time
from typing import Any, Dict, List, Optional, Tuple, Set
from datetime import datetime, timedelta
from dataclasses import dataclass, field, asdict
from collections import defaultdict

try:
    import boto3
except ImportError:
    boto3 = None

try:
    from azure.identity import DefaultAzureCredential
    from azure.mgmt.resource import ResourceManagementClient
    from azure.mgmt.storage import StorageManagementClient
except ImportError:
    DefaultAzureCredential = None
    ResourceManagementClient = None
    StorageManagementClient = None

try:
    from google.cloud import storage as gcp_storage
    from google.cloud import resource_manager as gcp_resource
except ImportError:
    gcp_storage = None
    gcp_resource = None

logger = logging.getLogger("NEBULA")


@dataclass
class ComplianceFinding:
    finding_id: str
    control_id: str
    framework: str
    requirement: str
    status: str
    resource: str
    severity: str
    remediation: str
    evidence: Dict[str, Any] = field(default_factory=dict)


@dataclass
class IAMPolicy:
    policy_id: str
    principal: str
    actions: List[str]
    resources: List[str]
    conditions: Dict[str, Any]
    risk_level: str
    issues: List[str]


class CloudRanger:
    CODENAME = "NEBULA"

    COMPLIANCE_CONTROLS = {
        "SOC2": {
            "CC6.1": "Logical and physical access controls",
            "CC6.2": "Access removal",
            "CC6.3": "Access restrictions",
            "CC6.6": "Encryption of data at rest",
            "CC6.7": "Encryption of data in transit",
            "CC7.1": "Detection of security events",
            "CC7.2": "Incident response",
        },
        "ISO27001": {
            "A.9.1.1": "Access control policy",
            "A.9.2.1": "User registration",
            "A.9.2.3": "Access rights review",
            "A.10.1.1": "Cryptographic controls policy",
            "A.12.3.1": "Information backup",
            "A.12.4.1": "Event logging",
        },
        "PCI-DSS": {
            "1.1": "Firewall configuration standards",
            "2.1": "Default passwords changed",
            "3.4": "PAN storage encryption",
            "4.1": "Transmission encryption",
            "7.1": "Need-to-know access",
            "10.1": "Audit trails",
        },
    }

    def __init__(self, commander_bus=None, shared_memory=None):
        self._lock = threading.RLock()
        self._running = False
        self._commander_bus = commander_bus
        self._shared_memory = shared_memory
        self._findings: List[ComplianceFinding] = []
        self._iam_policies: List[IAMPolicy] = []
        self._session_id = hashlib.sha256(
            f"nebula_{time.time()}_{os.urandom(8).hex()}".encode()
        ).hexdigest()[:16]
        logger.info(f"[{self.CODENAME}] Initialized session {self._session_id}")

    def start(self) -> bool:
        with self._lock:
            self._running = True
        logger.info(f"[{self.CODENAME}] Agent started")
        return True

    def stop(self) -> bool:
        with self._lock:
            self._running = False
        logger.info(f"[{self.CODENAME}] Agent stopped")
        return True

    def health(self) -> Dict[str, Any]:
        with self._lock:
            return {
                "codename": self.CODENAME,
                "session_id": self._session_id,
                "running": self._running,
                "findings_count": len(self._findings),
                "policies_analyzed": len(self._iam_policies),
            }

    def _report_to_commander(self, message: str, level: str = "info", data: Optional[Dict] = None) -> None:
        payload = {
            "agent": self.CODENAME,
            "session_id": self._session_id,
            "timestamp": datetime.utcnow().isoformat(),
            "level": level,
            "message": message,
            "data": data or {},
        }
        logger.info(f"[{self.CODENAME}] REPORT: {message}")
        if self._commander_bus:
            try:
                self._commander_bus.publish(f"agent.{self.CODENAME}", payload)
            except Exception as e:
                logger.error(f"[{self.CODENAME}] Bus report failed: {e}")

    def _store_memory(self, key: str, value: Any) -> None:
        if self._shared_memory:
            try:
                self._shared_memory.set(f"{self.CODENAME}.{key}", value, ttl=86400)
            except Exception as e:
                logger.error(f"[{self.CODENAME}] Memory store failed: {e}")

    def _execute_shell(self, command: str, timeout: int = 60) -> Tuple[int, str, str]:
        try:
            result = subprocess.run(command, shell=True, capture_output=True, text=True, timeout=timeout, cwd=os.getcwd())
            return result.returncode, result.stdout, result.stderr
        except subprocess.TimeoutExpired:
            return -1, "", f"Command timed out after {timeout}s"
        except Exception as e:
            return -1, "", str(e)

    # AWS Security Posture
    def assess_aws_security(self, regions: Optional[List[str]] = None) -> Dict[str, Any]:
        results = {
            "provider": "AWS",
            "timestamp": datetime.utcnow().isoformat(),
            "findings": [],
            "services": {},
        }
        if not boto3:
            results["error"] = "boto3 not installed. Run: pip install boto3"
            self._report_to_commander("AWS assessment failed: boto3 not installed", level="warning")
            return results
        try:
            iam_findings = self._analyze_aws_iam()
            results["services"]["iam"] = iam_findings
            results["findings"].extend(iam_findings.get("findings", []))
            s3_findings = self._analyze_aws_s3()
            results["services"]["s3"] = s3_findings
            results["findings"].extend(s3_findings.get("findings", []))
            ec2_findings = self._analyze_aws_ec2(regions)
            results["services"]["ec2"] = ec2_findings
            results["findings"].extend(ec2_findings.get("findings", []))
            trail_findings = self._analyze_aws_cloudtrail()
            results["services"]["cloudtrail"] = trail_findings
            results["findings"].extend(trail_findings.get("findings", []))
        except Exception as e:
            results["error"] = str(e)
            logger.error(f"[{self.CODENAME}] AWS assessment error: {e}")
        self._store_memory("aws.assessment", results)
        self._report_to_commander(f"AWS security assessment complete: {len(results['findings'])} findings")
        return results

    def _analyze_aws_iam(self) -> Dict[str, Any]:
        findings = {"findings": [], "users": 0, "roles": 0, "policies": 0}
        try:
            iam = boto3.client("iam")
            users = iam.list_users()["Users"]
            findings["users"] = len(users)
            for user in users:
                mfa_devices = iam.list_mfa_devices(UserName=user["UserName"])["MFADevices"]
                if not mfa_devices:
                    finding = ComplianceFinding(
                        finding_id=f"nebula_aws_{hashlib.md5(user['Arn'].encode()).hexdigest()[:12]}",
                        control_id="CC6.1", framework="SOC2",
                        requirement="Logical and physical access controls",
                        status="fail", resource=user["Arn"], severity="high",
                        remediation="Enable MFA for IAM user",
                        evidence={"user": user["UserName"], "mfa_enabled": False},
                    )
                    findings["findings"].append(asdict(finding))
            policies = iam.list_policies(Scope="Local")["Policies"]
            findings["policies"] = len(policies)
            for policy in policies:
                if policy["PolicyName"] in ["AdministratorAccess", "PowerUserAccess"]:
                    finding = ComplianceFinding(
                        finding_id=f"nebula_aws_{hashlib.md5(policy['Arn'].encode()).hexdigest()[:12]}",
                        control_id="A.9.1.1", framework="ISO27001",
                        requirement="Access control policy",
                        status="warning", resource=policy["Arn"], severity="medium",
                        remediation="Review and restrict overly permissive IAM policy",
                        evidence={"policy": policy["PolicyName"]},
                    )
                    findings["findings"].append(asdict(finding))
            try:
                password_policy = iam.get_account_password_policy()["PasswordPolicy"]
                if password_policy.get("MinimumPasswordLength", 0) < 12:
                    finding = ComplianceFinding(
                        finding_id="nebula_aws_password_policy",
                        control_id="2.1", framework="PCI-DSS",
                        requirement="Default passwords changed",
                        status="fail", resource="account_password_policy", severity="medium",
                        remediation="Increase minimum password length to 12+ characters",
                        evidence={"min_length": password_policy.get("MinimumPasswordLength")},
                    )
                    findings["findings"].append(asdict(finding))
            except iam.exceptions.NoSuchEntityException:
                finding = ComplianceFinding(
                    finding_id="nebula_aws_no_password_policy",
                    control_id="2.1", framework="PCI-DSS",
                    requirement="Default passwords changed",
                    status="fail", resource="account_password_policy", severity="high",
                    remediation="Set an account password policy",
                    evidence={},
                )
                findings["findings"].append(asdict(finding))
        except Exception as e:
            findings["error"] = str(e)
            logger.error(f"[{self.CODENAME}] AWS IAM analysis error: {e}")
        return findings

    def _analyze_aws_s3(self) -> Dict[str, Any]:
        findings = {"findings": [], "buckets": 0}
        try:
            s3 = boto3.client("s3")
            buckets = s3.list_buckets()["Buckets"]
            findings["buckets"] = len(buckets)
            for bucket in buckets:
                bucket_name = bucket["Name"]
                try:
                    public_access = s3.get_public_access_block(Bucket=bucket_name)["PublicAccessBlockConfiguration"]
                    if not all(public_access.values()):
                        finding = ComplianceFinding(
                            finding_id=f"nebula_s3_{bucket_name}_public",
                            control_id="CC6.3", framework="SOC2",
                            requirement="Access restrictions",
                            status="fail", resource=f"arn:aws:s3:::{bucket_name}", severity="critical",
                            remediation="Enable all public access blocks on S3 bucket",
                            evidence={"public_access": public_access},
                        )
                        findings["findings"].append(asdict(finding))
                except s3.exceptions.ClientError:
                    finding = ComplianceFinding(
                        finding_id=f"nebula_s3_{bucket_name}_no_block",
                        control_id="CC6.3", framework="SOC2",
                        requirement="Access restrictions",
                        status="fail", resource=f"arn:aws:s3:::{bucket_name}", severity="critical",
                        remediation="Configure public access block on S3 bucket",
                        evidence={},
                    )
                    findings["findings"].append(asdict(finding))
                try:
                    encryption = s3.get_bucket_encryption(Bucket=bucket_name)["ServerSideEncryptionConfiguration"]["Rules"][0]
                except s3.exceptions.ClientError:
                    finding = ComplianceFinding(
                        finding_id=f"nebula_s3_{bucket_name}_no_encryption",
                        control_id="CC6.6", framework="SOC2",
                        requirement="Encryption of data at rest",
                        status="fail", resource=f"arn:aws:s3:::{bucket_name}", severity="high",
                        remediation="Enable default server-side encryption on S3 bucket",
                        evidence={},
                    )
                    findings["findings"].append(asdict(finding))
                try:
                    versioning = s3.get_bucket_versioning(Bucket=bucket_name)
                    if versioning.get("Status") != "Enabled":
                        finding = ComplianceFinding(
                            finding_id=f"nebula_s3_{bucket_name}_no_versioning",
                            control_id="A.12.3.1", framework="ISO27001",
                            requirement="Information backup",
                            status="warning", resource=f"arn:aws:s3:::{bucket_name}", severity="medium",
                            remediation="Enable versioning on S3 bucket",
                            evidence={"versioning": versioning.get("Status")},
                        )
                        findings["findings"].append(asdict(finding))
                except Exception:
                    pass
        except Exception as e:
            findings["error"] = str(e)
            logger.error(f"[{self.CODENAME}] AWS S3 analysis error: {e}")
        return findings

    def _analyze_aws_ec2(self, regions: Optional[List[str]] = None) -> Dict[str, Any]:
        findings = {"findings": [], "instances": 0, "security_groups": 0}
        try:
            ec2_global = boto3.client("ec2", region_name="us-east-1")
            all_regions = [r["RegionName"] for r in ec2_global.describe_regions()["Regions"]]
            target_regions = regions or all_regions
            for region in target_regions:
                try:
                    ec2 = boto3.client("ec2", region_name=region)
                    sgs = ec2.describe_security_groups()["SecurityGroups"]
                    findings["security_groups"] += len(sgs)
                    for sg in sgs:
                        for rule in sg.get("IpPermissions", []):
                            for ip_range in rule.get("IpRanges", []):
                                if ip_range.get("CidrIp") == "0.0.0.0/0":
                                    finding = ComplianceFinding(
                                        finding_id=f"nebula_sg_{sg['GroupId']}_open",
                                        control_id="1.1", framework="PCI-DSS",
                                        requirement="Firewall configuration standards",
                                        status="fail", resource=sg["GroupId"], severity="high",
                                        remediation="Restrict security group to specific IP ranges",
                                        evidence={"rule": rule, "region": region},
                                    )
                                    findings["findings"].append(asdict(finding))
                    instances = ec2.describe_instances()["Reservations"]
                    for reservation in instances:
                        findings["instances"] += len(reservation.get("Instances", []))
                except Exception as e:
                    logger.warning(f"[{self.CODENAME}] EC2 analysis failed for region {region}: {e}")
        except Exception as e:
            findings["error"] = str(e)
            logger.error(f"[{self.CODENAME}] AWS EC2 analysis error: {e}")
        return findings

    def _analyze_aws_cloudtrail(self) -> Dict[str, Any]:
        findings = {"findings": [], "trails": 0}
        try:
            cloudtrail = boto3.client("cloudtrail")
            trails = cloudtrail.describe_trails()["trailList"]
            findings["trails"] = len(trails)
            if not trails:
                finding = ComplianceFinding(
                    finding_id="nebula_aws_no_cloudtrail",
                    control_id="A.12.4.1", framework="ISO27001",
                    requirement="Event logging",
                    status="fail", resource="aws_account", severity="critical",
                    remediation="Enable CloudTrail for all regions",
                    evidence={},
                )
                findings["findings"].append(asdict(finding))
            else:
                for trail in trails:
                    if not trail.get("IsMultiRegionTrail"):
                        finding = ComplianceFinding(
                            finding_id=f"nebula_trail_{trail['Name']}_single_region",
                            control_id="A.12.4.1", framework="ISO27001",
                            requirement="Event logging",
                            status="warning", resource=trail["TrailARN"], severity="medium",
                            remediation="Enable multi-region logging for CloudTrail",
                            evidence={"multi_region": trail.get("IsMultiRegionTrail")},
                        )
                        findings["findings"].append(asdict(finding))
        except Exception as e:
            findings["error"] = str(e)
            logger.error(f"[{self.CODENAME}] AWS CloudTrail analysis error: {e}")
        return findings

    # Azure Security Posture
    def assess_azure_security(self, subscription_ids: Optional[List[str]] = None) -> Dict[str, Any]:
        results = {
            "provider": "Azure",
            "timestamp": datetime.utcnow().isoformat(),
            "findings": [],
            "services": {},
        }
        if not DefaultAzureCredential:
            results["error"] = "Azure SDK not installed. Run: pip install azure-identity azure-mgmt-resource azure-mgmt-storage"
            self._report_to_commander("Azure assessment failed: SDK not installed", level="warning")
            return results
        try:
            credential = DefaultAzureCredential()
            if not subscription_ids:
                sub_client = ResourceManagementClient(credential, "")
                subscription_ids = [sub.subscription_id for sub in sub_client.subscriptions.list()]
            for sub_id in subscription_ids:
                storage_client = StorageManagementClient(credential, sub_id)
                for account in storage_client.storage_accounts.list():
                    account_name = account.name
                    if not account.enable_https_traffic_only:
                        finding = ComplianceFinding(
                            finding_id=f"nebula_az_{account_name}_no_https",
                            control_id="CC6.7", framework="SOC2",
                            requirement="Encryption of data in transit",
                            status="fail", resource=account.id, severity="high",
                            remediation="Enable HTTPS-only traffic on storage account",
                            evidence={"https_only": account.enable_https_traffic_only},
                        )
                        results["findings"].append(asdict(finding))
                    if account.encryption and account.encryption.services:
                        if not account.encryption.services.blob.enabled:
                            finding = ComplianceFinding(
                                finding_id=f"nebula_az_{account_name}_blob_no_encrypt",
                                control_id="CC6.6", framework="SOC2",
                                requirement="Encryption of data at rest",
                                status="fail", resource=account.id, severity="high",
                                remediation="Enable blob encryption on storage account",
                                evidence={},
                            )
                            results["findings"].append(asdict(finding))
        except Exception as e:
            results["error"] = str(e)
            logger.error(f"[{self.CODENAME}] Azure assessment error: {e}")
        self._store_memory("azure.assessment", results)
        self._report_to_commander(f"Azure security assessment complete: {len(results['findings'])} findings")
        return results

    # GCP Security Posture
    def assess_gcp_security(self, project_ids: Optional[List[str]] = None) -> Dict[str, Any]:
        results = {
            "provider": "GCP",
            "timestamp": datetime.utcnow().isoformat(),
            "findings": [],
            "services": {},
        }
        if not gcp_storage:
            results["error"] = "Google Cloud SDK not installed. Run: pip install google-cloud-storage google-cloud-resource-manager"
            self._report_to_commander("GCP assessment failed: SDK not installed", level="warning")
            return results
        try:
            rc, out, err = self._execute_shell("gcloud projects list --format=json 2>/dev/null || echo '[]'", timeout=30)
            if rc == 0 and out:
                projects = json.loads(out)
                target_projects = project_ids or [p["projectId"] for p in projects]
                for project in target_projects:
                    rc2, out2, err2 = self._execute_shell(
                        f"gcloud projects get-iam-policy {project} --format=json 2>/dev/null",
                        timeout=30
                    )
                    if rc2 == 0 and out2:
                        policy = json.loads(out2)
                        for binding in policy.get("bindings", []):
                            role = binding.get("role", "")
                            if role == "roles/owner" and len(binding.get("members", [])) > 3:
                                finding = ComplianceFinding(
                                    finding_id=f"nebula_gcp_{project}_too_many_owners",
                                    control_id="A.9.1.1", framework="ISO27001",
                                    requirement="Access control policy",
                                    status="warning", resource=f"projects/{project}", severity="medium",
                                    remediation="Reduce number of project owners",
                                    evidence={"owners": binding.get("members", [])},
                                )
                                results["findings"].append(asdict(finding))
                    rc3, out3, err3 = self._execute_shell(
                        f"gsutil ls -L -b gs://* 2>/dev/null | head -100 || echo 'No buckets or gsutil not available'",
                        timeout=30
                    )
                    if out3 and "not available" not in out3:
                        results["services"]["storage"] = {"buckets_checked": out3.count("gs://")}
        except Exception as e:
            results["error"] = str(e)
            logger.error(f"[{self.CODENAME}] GCP assessment error: {e}")
        self._store_memory("gcp.assessment", results)
        self._report_to_commander(f"GCP security assessment complete: {len(results['findings'])} findings")
        return results

    # Container Registry Scanning
    def scan_container_registry(self, registry_type: str = "ecr", registry_name: Optional[str] = None) -> Dict[str, Any]:
        results = {
            "registry_type": registry_type,
            "registry_name": registry_name,
            "timestamp": datetime.utcnow().isoformat(),
            "images": [],
            "vulnerabilities": [],
        }
        try:
            if registry_type == "ecr" and boto3:
                ecr = boto3.client("ecr")
                repositories = ecr.describe_repositories()["repositories"]
                for repo in repositories:
                    repo_name = repo["repositoryName"]
                    images = ecr.describe_images(repositoryName=repo_name)["imageDetails"]
                    for image in images:
                        results["images"].append({
                            "repository": repo_name,
                            "digest": image.get("imageDigest", ""),
                            "tags": image.get("imageTags", []),
                            "pushed_at": str(image.get("imagePushedAt", "")),
                        })
                        try:
                            scan = ecr.describe_image_scan_findings(
                                repositoryName=repo_name,
                                imageId={"imageDigest": image["imageDigest"]}
                            )
                            findings = scan.get("imageScanFindings", {}).get("findings", [])
                            for finding in findings:
                                results["vulnerabilities"].append({
                                    "repository": repo_name,
                                    "severity": finding.get("severity", "UNKNOWN"),
                                    "name": finding.get("name", ""),
                                    "description": finding.get("description", ""),
                                    "uri": finding.get("uri", ""),
                                })
                        except Exception:
                            pass
            elif registry_type in ["acr", "gcr"]:
                if registry_type == "acr":
                    rc, out, err = self._execute_shell(
                        f"az acr repository list --name {registry_name} 2>/dev/null || echo 'ACR scan simulated'",
                        timeout=30
                    )
                else:
                    rc, out, err = self._execute_shell(
                        f"gcloud container images list --repository={registry_name} 2>/dev/null || echo 'GCR scan simulated'",
                        timeout=30
                    )
                results["cli_output"] = out or err
        except Exception as e:
            results["error"] = str(e)
            logger.error(f"[{self.CODENAME}] Registry scan error: {e}")
        self._store_memory(f"registry.{registry_type}", results)
        self._report_to_commander(f"Registry scan complete: {len(results['vulnerabilities'])} vulnerabilities found")
        return results

    # Compliance Mapping
    def generate_compliance_report(self, framework: str = "SOC2") -> Dict[str, Any]:
        controls = self.COMPLIANCE_CONTROLS.get(framework, {})
        with self._lock:
            findings = list(self._findings)
        report = {
            "framework": framework,
            "generated_at": datetime.utcnow().isoformat(),
            "controls": {},
            "summary": {"pass": 0, "fail": 0, "warning": 0, "total": 0},
        }
        for control_id, requirement in controls.items():
            control_findings = [f for f in findings if f.control_id == control_id]
            passed = len([f for f in control_findings if f.status == "pass"])
            failed = len([f for f in control_findings if f.status == "fail"])
            warnings = len([f for f in control_findings if f.status == "warning"])
            report["controls"][control_id] = {
                "requirement": requirement,
                "findings": [asdict(f) for f in control_findings],
                "pass": passed,
                "fail": failed,
                "warning": warnings,
                "compliance_rate": round(passed / max(passed + failed, 1) * 100, 2),
            }
            report["summary"]["pass"] += passed
            report["summary"]["fail"] += failed
            report["summary"]["warning"] += warnings
            report["summary"]["total"] += len(control_findings)
        report["summary"]["overall_compliance"] = round(
            report["summary"]["pass"] / max(report["summary"]["total"], 1) * 100, 2
        )
        self._store_memory(f"compliance.{framework}", report)
        self._report_to_commander(f"Compliance report generated for {framework}")
        return report

    # Unit Tests
    def test_compliance_finding(self) -> bool:
        finding = ComplianceFinding(
            finding_id="test_finding", control_id="CC6.1", framework="SOC2",
            requirement="Test", status="fail", resource="test", severity="high",
            remediation="Test remediation",
        )
        assert finding.finding_id == "test_finding"
        return True

    def test_iam_policy(self) -> bool:
        policy = IAMPolicy(
            policy_id="test_policy", principal="test_user",
            actions=["s3:GetObject"], resources=["arn:aws:s3:::test-bucket/*"],
            conditions={}, risk_level="low", issues=[],
        )
        assert policy.policy_id == "test_policy"
        return True

    def test_compliance_report(self) -> bool:
        report = self.generate_compliance_report("SOC2")
        assert "controls" in report
        return True
