"""
IRIS v7.0 — Senses Package

The perceptual layer. Every sense in this package monitors real systems,
streams real data, and detects real anomalies. No simulations. No stubs.

Senses are organized by domain:
    - system:     system_monitor
    - filesystem: file_watcher
    - network:    network_watcher
    - logs:       log_ingestor
    - threat:     threat_feeds
    - uptime:     uptime_monitor
    - alert:      alert_router

Usage:
    from iris_v7.senses import SenseRegistry
    registry = SenseRegistry()
    registry.discover()
    registry.start_all()
    status = registry.get_status()
"""

from .registry import SenseRegistry
from .base_sense import BaseSense, IRISConnectable

__all__ = ["SenseRegistry", "BaseSense", "IRISConnectable"]
