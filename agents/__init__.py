"""
IRIS v7.0 Agents Package
Aevibron Agent Corps — 29 Specialized Agents
"""

# V1 Agents
from .architect import Architect
from .code_sage import CodeSage
from .test_oracle import TestOracle
from .devops_maven import DevOpsMaven
from .recon_ghost import ReconGhost
from .vuln_hunter import VulnHunter

# V2 Agents
from .red_specter import RedSpecter
from .blue_sentinel import BlueSentinel
from .purple_judge import PurpleJudge
from .forensics_wraith import ForensicsWraith
from .threat_prophet import ThreatProphet
from .cloud_ranger import CloudRanger
from .container_guard import ContainerGuard
from .net_weaver import NetWeaver
from .sys_overlord import SysOverlord

# V3 Agents
from .data_alchemist import DataAlchemist
from .research_scholar import ResearchScholar
from .doc_scribe import DocScribe
from .email_herald import EmailHerald
from .chart_artisan import ChartArtisan
from .voice_herald import VoiceHerald
from .automation_forge import AutomationForge
from .api_gateway import APIGateway
from .database_sage import DatabaseSage

# Additional Agents
from .mobile_sentinel import MobileSentinel
from .blockchain_ledger import BlockchainLedger
from .quantum_seer import QuantumSeer
from .ml_engineer import MLEngineer
from .ui_visionary import UIVisionary

__all__ = [
    # V1
    "Architect", "CodeSage", "TestOracle", "DevOpsMaven",
    "ReconGhost", "VulnHunter",
    # V2
    "RedSpecter", "BlueSentinel", "PurpleJudge",
    "ForensicsWraith", "ThreatProphet", "CloudRanger",
    "ContainerGuard", "NetWeaver", "SysOverlord",
    # V3
    "DataAlchemist", "ResearchScholar", "DocScribe",
    "EmailHerald", "ChartArtisan", "VoiceHerald",
    "AutomationForge", "APIGateway", "DatabaseSage",
    # Additional
    "MobileSentinel", "BlockchainLedger", "QuantumSeer",
    "MLEngineer", "UIVisionary",
]
