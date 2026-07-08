# IRIS v7.0 — Tools & Senses Combined Wiring, README, and Requirements

> This file combines all wiring, documentation, and requirements for the IRIS v7.0 `tools/` and `senses/` layers.
> Generated from: WIRING_GUIDE.md, senses_readme.md, senses_wiring.py, senses_requirements.txt, tools_README.md, tools_wiring.py, tools_requirements.txt

---

# TABLE OF CONTENTS

1. [Wiring Guide](#1-wiring-guide)
2. [Tools README](#2-tools-readme)
3. [Tools Wiring (Python)](#3-tools-wiring-python)
4. [Tools Requirements](#4-tools-requirements)
5. [Senses README](#5-senses-readme)
6. [Senses Wiring (Python)](#6-senses-wiring-python)
7. [Senses Requirements](#7-senses-requirements)

---

# 1. WIRING GUIDE

# IRIS v7.0 — Wiring Guide

This document shows exactly how to connect the `tools/` and `senses/` directories into your main IRIS project.

## Directory Structure

```
iris_v7/
├── tools/                    # Operational layer (actuators)
│   ├── __init__.py
│   ├── tools_wiring.py       # <-- Import this
│   ├── tools_readme.md
│   ├── tools_requirements.txt
│   ├── base_tool.py
│   ├── registry.py
│   ├── nmap_wrapper.py
│   ├── sqlmap_wrapper.py
│   ├── metasploit_bridge.py
│   ├── burp_bridge.py
│   ├── wireshark_parser.py
│   ├── volatility_bridge.py
│   ├── docker_engine.py
│   ├── aws_cli.py
│   ├── git_engine.py
│   ├── api_client.py
│   └── code_analyzer.py
├── senses/                   # Perceptual layer (monitors)
│   ├── __init__.py
│   ├── senses_wiring.py      # <-- Import this
│   ├── senses_readme.md
│   ├── senses_requirements.txt
│   ├── base_sense.py
│   ├── registry.py
│   ├── system_monitor.py
│   ├── file_watcher.py
│   ├── network_watcher.py
│   ├── log_ingestor.py
│   ├── threat_feeds.py
│   ├── uptime_monitor.py
│   └── alert_router.py
└── WIRING_GUIDE.md           # <-- You are here
```

## Installation

```bash
# From your main project root (where tools/ and senses/ live)
pip install -r tools/tools_requirements.txt
pip install -r senses/senses_requirements.txt
```

## Wiring into Your Main Entry Point

### Option A: Full Auto-Wiring (Recommended)

```python
# main.py — your IRIS core entry point

from tools.tools_wiring import get_tools_registry, run_tool
from senses.senses_wiring import get_senses_registry, start_monitoring, stop_monitoring

class IRISCore:
    def __init__(self):
        self.tools = get_tools_registry(iris_core=self)
        self.senses = get_senses_registry(iris_core=self)
        self.findings = []

    def receive_finding(self, finding: dict):
        '''Every tool and sense reports here.'''
        self.findings.append(finding)
        print(f"[IRIS] Finding: {finding.get('type')} from {finding.get('reported_by')}")

    def start(self):
        start_monitoring(self.senses)
        print("[IRIS] All systems operational.")

    def stop(self):
        stop_monitoring(self.senses)
        print("[IRIS] All systems halted.")

    def execute_tool(self, name: str, **kwargs):
        return self.tools.execute(name, **kwargs)

    def get_status(self):
        return {
            "tools": self.tools.health_check_all(),
            "senses": self.senses.get_status(),
        }

# Run
if __name__ == "__main__":
    iris = IRISCore()
    iris.start()

    # Example: Run a tool
    result = iris.execute_tool("nmap_wrapper", target="127.0.0.1", ports="22")
    print(result)

    # Example: Check senses status
    print(iris.get_status())

    iris.stop()
```

### Option B: Direct Tool Access

```python
from tools.tools_wiring import NmapWrapper, SQLMapWrapper, APIClient

nmap = NmapWrapper(iris_core=iris)
result = nmap.scan_ports("192.168.1.1", ports="80,443")
```

### Option C: Direct Sense Access

```python
from senses.senses_wiring import SystemMonitor, UptimeMonitor

monitor = SystemMonitor(iris_core=iris)
monitor.start()
# Auto-runs every 5 seconds, reports findings to iris.receive_finding()
```

## Connection Contract

Every tool and sense connects via `IRISConnectable`:

```python
class IRISConnectable:
    def __init__(self, iris_core=None):
        self.iris_core = iris_core
        self.status = "idle"       # idle | active | error | disabled
        self.last_result = None

    def health_check(self) -> dict:
        # Return: {"status": "available|missing_deps|error", "message": "...", "details": {}}
        pass

    def report(self, finding: dict) -> None:
        # Sends to iris_core.receive_finding() or logs locally
        pass
```

## Standard Result Format (Both Layers)

```python
{
    "success": bool,
    "tool" | "sense": str,      # Component name
    "action": str,              # What was attempted
    "output": Any,              # Raw results
    "parsed": dict,             # Structured extracted data
    "errors": list,             # Error messages
    "warnings": list,           # Non-critical issues
    "duration_ms": int,         # Execution time
    "timestamp": str            # ISO timestamp
}
```

## Environment Variables

Copy `.env.example` content from `tools/tools_readme.md` and `senses/senses_readme.md` into your main `.env` file.

## Key Files for Your Agent

| File | Purpose |
|------|---------|
| `tools/tools_wiring.py` | One import for all tools |
| `senses/senses_wiring.py` | One import for all senses |
| `tools/tools_readme.md` | Tool layer docs |
| `senses/senses_readme.md` | Sense layer docs |
| `WIRING_GUIDE.md` | This file — integration guide |

## Safety Reminders

- `IRIS_SAFE_ENV=true` required for Metasploit exploit execution
- `IRIS_SQLMAP_AUTHORIZED` comma-separated hosts for SQLMap data extraction
- All API keys from environment variables only
- No hardcoded secrets anywhere


---

# 2. TOOLS README

# IRIS v7.0 — Tools Layer

The operational actuator layer. Every tool executes REAL commands against REAL systems. No simulations. No stubs.

## Quick Start

```python
from tools import ToolRegistry

registry = ToolRegistry()
registry.discover()

# Run any tool by name
result = registry.execute("nmap_wrapper", target="192.168.1.1", ports="22,80,443")
print(result)
```

## Available Tools

| Tool | Category | Description |
|------|----------|-------------|
| `nmap_wrapper` | network | Port scanning, service detection, OS fingerprinting |
| `sqlmap_wrapper` | network | SQL injection detection & exploitation |
| `metasploit_bridge` | network | Metasploit RPC integration |
| `burp_bridge` | network | Burp Suite Enterprise API |
| `wireshark_parser` | forensics | PCAP analysis with scapy |
| `volatility_bridge` | forensics | Memory forensics via Volatility3 |
| `docker_engine` | container | Container control, vulnerability scanning |
| `aws_cli` | cloud | AWS resource enumeration & security auditing |
| `git_engine` | code | Git ops, secret detection, changelog generation |
| `api_client` | web | Universal REST/GraphQL/WebSocket client |
| `code_analyzer` | code | Semgrep, Bandit, custom regex, SARIF output |

## Environment Variables

```bash
# SQLMap
IRIS_SQLMAP_AUTHORIZED=localhost,127.0.0.1

# Metasploit
IRIS_SAFE_ENV=false
IRIS_MSFRPCD_PASS=your_password

# Burp Suite
IRIS_BURP_URL=https://burp:8080
IRIS_BURP_API_KEY=your_key

# AWS
AWS_DEFAULT_REGION=us-east-1
AWS_ACCESS_KEY_ID=your_key
AWS_SECRET_ACCESS_KEY=your_secret
```

## Standard Result Format

Every tool returns:
```python
{
    "success": bool,
    "tool": str,
    "action": str,
    "output": Any,
    "parsed": dict,
    "errors": list,
    "warnings": list,
    "duration_ms": int,
    "timestamp": str
}
```

## Safety

- Input sanitization prevents command injection
- Authorization checks on destructive operations
- Safe-environment enforcement for exploits
- No hardcoded secrets


---

# 3. TOOLS WIRING (PYTHON)

```python
"""
IRIS v7.0 — Tools Wiring Module

Single import point for the entire tools layer.
Use this in your main entry point to get a fully configured ToolRegistry.

Usage:
    from tools.tools_wiring import get_tools_registry, run_tool

    registry = get_tools_registry()
    result = run_tool("nmap_wrapper", target="10.0.0.1")
"""

from .registry import ToolRegistry
from .base_tool import BaseTool, IRISConnectable

# Re-export all tools for direct access
from .nmap_wrapper import NmapWrapper
from .sqlmap_wrapper import SQLMapWrapper
from .metasploit_bridge import MetasploitBridge
from .burp_bridge import BurpBridge
from .wireshark_parser import WiresharkParser
from .volatility_bridge import VolatilityBridge
from .docker_engine import DockerEngine
from .aws_cli import AWSCLI
from .git_engine import GitEngine
from .api_client import APIClient
from .code_analyzer import CodeAnalyzer

__all__ = [
    "ToolRegistry",
    "BaseTool",
    "IRISConnectable",
    "NmapWrapper",
    "SQLMapWrapper",
    "MetasploitBridge",
    "BurpBridge",
    "WiresharkParser",
    "VolatilityBridge",
    "DockerEngine",
    "AWSCLI",
    "GitEngine",
    "APIClient",
    "CodeAnalyzer",
    "get_tools_registry",
    "run_tool",
    "health_check_all_tools",
]


def get_tools_registry(iris_core=None) -> ToolRegistry:
    """
    Create, discover, and return a fully configured ToolRegistry.

    Args:
        iris_core: Optional reference to the central IRIS core.

    Returns:
        Configured ToolRegistry with all tools registered.
    """
    registry = ToolRegistry()
    registry.discover()
    # Set iris_core reference on all tools
    for tool in registry._tools.values():
        tool.iris_core = iris_core
    return registry


def run_tool(name: str, iris_core=None, **kwargs):
    """
    One-shot tool execution. Creates registry, discovers, runs, returns result.

    Args:
        name: Tool codename.
        iris_core: Optional IRIS core reference.
        **kwargs: Arguments passed to the tool.

    Returns:
        Standard result dict.
    """
    registry = get_tools_registry(iris_core)
    return registry.execute(name, **kwargs)


def health_check_all_tools(iris_core=None) -> dict:
    """
    Run health checks on all available tools.

    Args:
        iris_core: Optional IRIS core reference.

    Returns:
        Dictionary mapping tool name -> health status.
    """
    registry = get_tools_registry(iris_core)
    return registry.health_check_all()

```

---

# 4. TOOLS REQUIREMENTS

```
# IRIS v7.0 — Tools Requirements
# Install: pip install -r tools_requirements.txt

# Core
python-dotenv>=1.0.0
pydantic>=2.0.0

# Network & Security
python-nmap>=0.7.1
scapy>=2.5.0
requests>=2.31.0
urllib3>=2.0.0
websocket-client>=1.6.0

# Cloud & AWS
boto3>=1.28.0
botocore>=1.31.0

# Docker
docker>=6.1.0

# Data & Parsing
dpkt>=1.9.8
pyshark>=0.6
lxml>=4.9.0

# System Monitoring
psutil>=5.9.0

# File Watching
watchdog>=3.0.0

# Static Analysis
bandit>=1.7.0
semgrep>=1.35.0

# Git
gitpython>=3.1.0

# Cryptography & Hashing
cryptography>=41.0.0

# Testing
pytest>=7.4.0
pytest-asyncio>=0.21.0

# Logging
structlog>=23.0.0

```

---

# 5. SENSES README

# IRIS v7.0 — Senses Layer

The perceptual layer. Every sense monitors REAL systems, streams REAL data, detects REAL anomalies. No simulations. No stubs.

## Quick Start

```python
from senses import SenseRegistry

registry = SenseRegistry()
registry.discover()
registry.start_all()

# Check status
status = registry.get_status()
alerts = registry.get_alerts()
```

## Available Senses

| Sense | Domain | Description |
|-------|--------|-------------|
| `system_monitor` | system | CPU, RAM, disk, network, temperature |
| `file_watcher` | filesystem | File changes, permissions, ransomware detection |
| `network_watcher` | network | Packet capture, port scans, bandwidth, DNS tunneling |
| `log_ingestor` | logs | Syslog/Apache-Nginx parsing, brute force, privilege escalation |
| `threat_feeds` | threat | CVE feeds, abuse.ch, OTX, VirusTotal, IOC matching |
| `uptime_monitor` | uptime | HTTP/TCP/DNS/SSL certificate monitoring |
| `alert_router` | alert | Routing, deduplication, escalation, notifications |

## Environment Variables

```bash
# Threat Intelligence APIs
IRIS_OTX_API_KEY=your_otx_key
IRIS_VT_API_KEY=your_virustotal_key
IRIS_ABUSEIPDB_KEY=your_abuseipdb_key

# Notifications
IRIS_SMTP_HOST=smtp.gmail.com
IRIS_SMTP_PORT=587
IRIS_SMTP_USER=your_email@gmail.com
IRIS_SMTP_PASS=your_app_password
IRIS_ALERT_EMAIL=alerts@example.com
IRIS_WEBHOOK_URL=https://hooks.slack.com/services/xxx/yyy/zzz
IRIS_TWILIO_SID=your_twilio_sid
IRIS_TWILIO_TOKEN=your_twilio_token
IRIS_TWILIO_FROM=+1234567890
IRIS_SMS_NUMBER=+1234567890
IRIS_PUSH_TOKEN=your_push_token
```

## Standard Result Format

Every sense returns:
```python
{
    "success": bool,
    "sense": str,
    "action": str,
    "output": Any,
    "parsed": dict,
    "errors": list,
    "warnings": list,
    "duration_ms": int,
    "timestamp": str
}
```

## Alert Format

```python
{
    "type": "system_alert|filesystem_alert|network_alert|log_alert|threat_alert|uptime_alert",
    "sense": str,
    "severity": "low|medium|high|critical",
    "message": str,
    "data": dict
}
```

## Safety

- Read-only monitoring by default
- No system modifications
- Thread-safe with locks
- Graceful degradation when deps missing


---

# 6. SENSES WIRING (PYTHON)

```python
"""
IRIS v7.0 — Senses Wiring Module

Single import point for the entire senses layer.
Use this in your main entry point to get a fully configured SenseRegistry.

Usage:
    from senses.senses_wiring import get_senses_registry, start_monitoring, get_alerts

    registry = get_senses_registry()
    start_monitoring(registry)

    # Later...
    alerts = get_alerts(registry)
"""

from .registry import SenseRegistry
from .base_sense import BaseSense, IRISConnectable

# Re-export all senses for direct access
from .system_monitor import SystemMonitor
from .file_watcher import FileWatcher
from .network_watcher import NetworkWatcher
from .log_ingestor import LogIngestor
from .threat_feeds import ThreatFeeds
from .uptime_monitor import UptimeMonitor
from .alert_router import AlertRouter

__all__ = [
    "SenseRegistry",
    "BaseSense",
    "IRISConnectable",
    "SystemMonitor",
    "FileWatcher",
    "NetworkWatcher",
    "LogIngestor",
    "ThreatFeeds",
    "UptimeMonitor",
    "AlertRouter",
    "get_senses_registry",
    "start_monitoring",
    "stop_monitoring",
    "get_alerts",
    "route_alert",
]


def get_senses_registry(iris_core=None) -> SenseRegistry:
    """
    Create, discover, and return a fully configured SenseRegistry.

    Args:
        iris_core: Optional reference to the central IRIS core.

    Returns:
        Configured SenseRegistry with all senses registered.
    """
    registry = SenseRegistry()
    registry.discover()
    # Set iris_core reference on all senses
    for sense in registry._senses.values():
        sense.iris_core = iris_core
    return registry


def start_monitoring(registry: SenseRegistry) -> None:
    """
    Start all sense monitoring.

    Args:
        registry: SenseRegistry instance.
    """
    registry.start_all()


def stop_monitoring(registry: SenseRegistry) -> None:
    """
    Stop all sense monitoring.

    Args:
        registry: SenseRegistry instance.
    """
    registry.stop_all()


def get_alerts(registry: SenseRegistry, limit: int = 100) -> list:
    """
    Retrieve recent alerts from all senses.

    Args:
        registry: SenseRegistry instance.
        limit: Maximum number of alerts.

    Returns:
        List of alert dictionaries.
    """
    return registry.get_alerts(limit)


def route_alert(registry: SenseRegistry, alert: dict) -> dict:
    """
    Route an alert through the AlertRouter sense if available.

    Args:
        registry: SenseRegistry instance.
        alert: Alert dictionary.

    Returns:
        Routing result dict.
    """
    router = registry.get("alert_router")
    if router:
        return router.route_alert(alert)
    return {"success": False, "error": "AlertRouter not registered"}

```

---

# 7. SENSES REQUIREMENTS

```
# IRIS v7.0 — Senses Requirements
# Install: pip install -r senses_requirements.txt
# 
# Core dependencies for the IRIS v7.0 perceptual layer.
# All senses monitor real systems, stream real data, detect real anomalies.
# No simulations. No stubs.
#
# Required for:
#   - system_monitor: CPU, RAM, disk, network, temperature monitoring
#   - file_watcher: File system change detection, ransomware patterns
#   - network_watcher: Packet capture, port scan detection, bandwidth
#   - log_ingestor: Syslog/Apache-Nginx parsing, brute force detection
#   - threat_feeds: CVE feeds, abuse.ch, OTX, VirusTotal lookups
#   - uptime_monitor: HTTP/TCP/DNS/SSL certificate health checks
#   - alert_router: Alert routing, deduplication, escalation, notifications

# Core
python-dotenv>=1.0.0
pydantic>=2.0.0

# System Monitoring (system_monitor)
psutil>=5.9.0

# File Watching (file_watcher)
watchdog>=3.0.0

# Network (network_watcher, packet capture)
scapy>=2.5.0

# HTTP / API (uptime_monitor, threat_feeds, alert_router webhooks)
requests>=2.31.0

# Testing
pytest>=7.4.0
pytest-asyncio>=0.21.0

# Logging
structlog>=23.0.0

```

---

# END OF COMBINED DOCUMENT

> All sections above are self-contained. Copy any section into its respective file as needed.
> For the original separate files, refer to the IRIS v7.0 project structure.
