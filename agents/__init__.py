"""
IRIS Agent Corps — 30+ Specialized Agents + OMNIS

OMNIS (Omniscient Mastery & Navigation Intelligence System) is the
single entry point for ALL skills and capabilities in IRIS.

Usage:
    iris.omnis.execute("web_search", {"query": "..."})
    iris.omnis.smart_route("search for latest AI papers")
    iris.omnis.chain([...])  # Multi-step chaining up to 25 steps

Available agents: api_gateway, architect, automation_forge,
blockchain_ledger, blue_sentinel, chart_artisan, cloud_ranger,
code_sage, container_guard, data_alchemist, database_sage,
devops_maven, doc_scribe, email_herald, forensics_wraith,
ml_engineer, mobile_sentinel, net_weaver, purple_judge,
quantum_seer, recon_ghost, red_specter, research_scholar,
swarm_coordinator, sys_overlord, test_oracle, threat_prophet,
ui_visionary, voice_herald, vuln_hunter, OMNIS
"""
from agents.omnis import OMNIS, omnis
__all__ = ["OMNIS", "omnis"]
