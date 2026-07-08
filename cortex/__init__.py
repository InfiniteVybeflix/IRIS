"""
IRIS v7.0 Cortex Package
Reasoning, planning, strategy, and self-improvement engines.

All cortex modules inherit from BaseCortex and implement:
- Structured reasoning chains
- Risk-aware decision making
- Resource optimization
- Meta-learning from outcomes
- Thread-safe operations

Modules:
    base_cortex:        Abstract base for all reasoning modules
    planner:            Goal decomposition and mission planning
    strategist:         Approach selection and adaptation
    risk_assessor:      Pre-execution risk analysis
    resource_optimizer: Efficient resource allocation
    hypothesis_tester:  "What-if" simulation and falsification
    meta_learner:       Self-improvement and bias detection

Usage:
    from iris_v7.cortex import BaseCortex, Planner, Strategist
    from iris_v7.cortex import RiskAssessor, ResourceOptimizer, HypothesisTester, MetaLearner
"""

from .base_cortex import BaseCortex
from .planner import Planner
from .strategist import Strategist
from .risk_assessor import RiskAssessor
from .resource_optimizer import ResourceOptimizer
from .hypothesis_tester import HypothesisTester
from .meta_learner import MetaLearner

__all__ = [
    "BaseCortex",
    "Planner",
    "Strategist",
    "RiskAssessor",
    "ResourceOptimizer",
    "HypothesisTester",
    "MetaLearner",
]
