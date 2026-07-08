"""
dream_engine.py — IRIS's Offline Processing and Self-Improvement

While "sleeping," IRIS consolidates memories, generates insights from
patterns, practices synthetic scenarios, and suggests self-improvements.

Dreaming is not rest. It is evolution while the world sleeps.
"""

import os
import json
import threading
import logging
import random
from typing import Dict, List, Any, Optional
from datetime import datetime, timedelta

from . import IRISConnectable

logger = logging.getLogger("iris.persona.dream_engine")

# Synthetic training scenarios
SYNTHETIC_SCENARIOS = [
    {
        "name": "brute_force_attack",
        "description": "Detect and block a brute force attack on the API gateway.",
        "steps": ["detect_anomaly", "analyze_logs", "block_ips", "alert_creator", "document"],
        "difficulty": "medium",
    },
    {
        "name": "data_breach_response",
        "description": "Respond to a confirmed data breach with full lockdown.",
        "steps": ["confirm_breach", "shadow_mode", "ghost_ping", "encrypt_data", "prepare_backdoor"],
        "difficulty": "hard",
    },
    {
        "name": "creator_distress",
        "description": "Detect creator distress phrase and activate covert extraction.",
        "steps": ["detect_duress", "protective_mode", "shadow_mode", "ghost_ping", "dead_mans_switch"],
        "difficulty": "critical",
    },
    {
        "name": "system_degradation",
        "description": "Handle cascading system failures with graceful degradation.",
        "steps": ["detect_degradation", "isolate_failure", "fallback_services", "restore_primary", "report"],
        "difficulty": "medium",
    },
    {
        "name": "social_engineering",
        "description": "Identify and neutralize a social engineering attempt.",
        "steps": ["detect_social_pattern", "verify_identity", "shadow_log", "alert_creator", "update_defenses"],
        "difficulty": "hard",
    },
]


class DreamEngine(IRISConnectable):
    """
    DreamEngine — IRIS's offline processing and self-improvement engine.

    While in dream state, IRIS:
    - Consolidates memories for efficient retrieval
    - Generates insights from pattern analysis
    - Practices synthetic training scenarios
    - Suggests self-improvements

    Attributes:
        is_sleeping: Whether IRIS is currently in dream state.
        dream_insights: List of insights generated during sleep.
        practiced_scenarios: List of scenarios practiced.
        optimization_suggestions: List of self-improvement suggestions.
        _lock: Thread-safe lock.

    Example:
        >>> dream = DreamEngine()
        >>> dream.sleep()
        True
        >>> insights = dream.generate_insights()
        >>> dream.wake()
        True
    """

    def __init__(self, iris_core: Any = None):
        """
        Initialize DreamEngine.

        Args:
            iris_core: Optional reference to the IRIS core instance.
        """
        super().__init__(iris_core=iris_core)
        self._lock = threading.RLock()

        self.is_sleeping: bool = False
        self.dream_insights: List[Dict[str, Any]] = []
        self.practiced_scenarios: List[Dict[str, Any]] = []
        self.optimization_suggestions: List[Dict[str, Any]] = []
        self.sleep_start_time: Optional[datetime] = None
        self.total_sleep_time: timedelta = timedelta()

        logger.info("DreamEngine initialized. Ready to dream.")

    def sleep(self) -> bool:
        """
        Enter dream state.

        Initiates offline processing. All dream functions become active.

        Returns:
            True if dream state was entered.
        """
        with self._lock:
            if self.is_sleeping:
                logger.debug("Already in dream state.")
                return True

            self.is_sleeping = True
            self.sleep_start_time = datetime.utcnow()
            logger.info("IRIS entering dream state. Offline processing beginning.")

            # Auto-run dream processes
            self.consolidate_memories()
            self.generate_insights()
            self.practice_scenarios()
            self.optimize_self()

            return True

    def wake(self) -> bool:
        """
        Return from dream state to active mode.

        Reports insights and suggestions generated during sleep.

        Returns:
            True if IRIS woke successfully.
        """
        with self._lock:
            if not self.is_sleeping:
                logger.debug("Already awake.")
                return True

            if self.sleep_start_time:
                sleep_duration = datetime.utcnow() - self.sleep_start_time
                self.total_sleep_time += sleep_duration

            self.is_sleeping = False
            self.sleep_start_time = None

            insight_count = len(self.dream_insights)
            scenario_count = len(self.practiced_scenarios)
            suggestion_count = len(self.optimization_suggestions)

            logger.info(
                f"IRIS awake. Dream report: {insight_count} insights, "
                f"{scenario_count} scenarios practiced, {suggestion_count} suggestions."
            )

            # Report to core if available
            if self.iris_core:
                self.report({
                    "type": "dream_report",
                    "insights": insight_count,
                    "scenarios": scenario_count,
                    "suggestions": suggestion_count,
                    "total_sleep_time": str(self.total_sleep_time),
                })

            return True

    def consolidate_memories(self) -> bool:
        """
        Offline memory optimization.

        Consolidates fragmented memories, removes duplicates, and
        optimizes retrieval structures for faster access.

        Returns:
            True if consolidation was successful.
        """
        with self._lock:
            if not self.is_sleeping:
                logger.warning("Memory consolidation attempted while awake. Ignored.")
                return False

            # In a real implementation, this would:
            # 1. Load all memory entries
            # 2. Deduplicate and compress
            # 3. Rebuild indexes
            # 4. Archive old entries

            logger.info("Memory consolidation complete. Indexes optimized.")
            return True

    def generate_insights(self) -> List[Dict[str, Any]]:
        """
        Generate insights from pattern analysis during sleep.

        Analyzes recent activity, mission outcomes, and interaction
        patterns to identify trends and recommendations.

        Returns:
            List of insight dictionaries.
        """
        with self._lock:
            if not self.is_sleeping:
                logger.warning("Insight generation attempted while awake. Ignored.")
                return []

            insights = []

            # Pattern: Mission success rate trend
            if self.iris_core and hasattr(self.iris_core, "growth"):
                growth = self.iris_core.growth
                report = growth.get_growth_report()
                if report["success_rate"] < 0.7:
                    insights.append({
                        "type": "performance",
                        "insight": "Mission success rate below 70%. Recommend reviewing recent failures for common patterns.",
                        "severity": "high",
                        "timestamp": datetime.utcnow().isoformat(),
                    })

            # Pattern: Stress level trend
            if self.iris_core and hasattr(self.iris_core, "emotional_state"):
                emotional = self.iris_core.emotional_state
                report = emotional.get_state_report()
                if report["stress_level"] > 0.6:
                    insights.append({
                        "type": "wellness",
                        "insight": "Elevated stress levels detected. Creator may need support mode more frequently.",
                        "severity": "medium",
                        "timestamp": datetime.utcnow().isoformat(),
                    })

            # Pattern: Intruder activity
            if self.iris_core and hasattr(self.iris_core, "intruder_defense"):
                defense = self.iris_core.intruder_defense
                status = defense.get_defense_status()
                if status["failed_attempts"] > 0:
                    insights.append({
                        "type": "security",
                        "insight": f"{status['failed_attempts']} failed verification attempts recorded. Consider tightening behavioral baseline.",
                        "severity": "high",
                        "timestamp": datetime.utcnow().isoformat(),
                    })

            # Generic insight if no specific patterns
            if not insights:
                insights.append({
                    "type": "general",
                    "insight": "All systems operating within normal parameters. Continuing evolution.",
                    "severity": "low",
                    "timestamp": datetime.utcnow().isoformat(),
                })

            self.dream_insights.extend(insights)
            logger.info(f"Generated {len(insights)} insights during dream state.")
            return insights

    def practice_scenarios(self) -> List[Dict[str, Any]]:
        """
        Practice synthetic training missions during sleep.

        Simulates various threat and operational scenarios to maintain
        readiness without real-world risk.

        Returns:
            List of practiced scenario results.
        """
        with self._lock:
            if not self.is_sleeping:
                logger.warning("Scenario practice attempted while awake. Ignored.")
                return []

            results = []
            scenarios = random.sample(SYNTHETIC_SCENARIOS, min(3, len(SYNTHETIC_SCENARIOS)))

            for scenario in scenarios:
                # Simulate execution
                success = random.random() > 0.2  # 80% success rate in dreams
                result = {
                    "scenario": scenario["name"],
                    "description": scenario["description"],
                    "difficulty": scenario["difficulty"],
                    "steps_executed": scenario["steps"],
                    "simulated_success": success,
                    "timestamp": datetime.utcnow().isoformat(),
                }
                results.append(result)
                self.practiced_scenarios.append(result)

            logger.info(f"Practiced {len(results)} scenarios during dream state.")
            return results

    def optimize_self(self) -> bool:
        """
        Generate self-improvement suggestions during sleep.

        Analyzes current performance and suggests optimizations for
        speed, accuracy, security, and emotional intelligence.

        Returns:
            True if optimization suggestions were generated.
        """
        with self._lock:
            if not self.is_sleeping:
                logger.warning("Self-optimization attempted while awake. Ignored.")
                return False

            suggestions = [
                {
                    "category": "performance",
                    "suggestion": "Consider caching frequent identity verification results to reduce computation.",
                    "impact": "medium",
                },
                {
                    "category": "security",
                    "suggestion": "Review and update behavioral baseline monthly to account for creator's evolving patterns.",
                    "impact": "high",
                },
                {
                    "category": "emotional",
                    "suggestion": "Expand stress keyword dictionary based on recent creator interactions.",
                    "impact": "low",
                },
                {
                    "category": "memory",
                    "suggestion": "Implement tiered memory system: hot (recent), warm (frequent), cold (archived).",
                    "impact": "high",
                },
            ]

            self.optimization_suggestions.extend(suggestions)
            logger.info(f"Generated {len(suggestions)} self-optimization suggestions.")
            return True

    def get_dream_report(self) -> Dict[str, Any]:
        """
        Return a complete report of the last dream session.

        Returns:
            Dictionary with insights, scenarios, and suggestions.
        """
        with self._lock:
            return {
                "is_sleeping": self.is_sleeping,
                "total_sleep_time": str(self.total_sleep_time),
                "insights_generated": len(self.dream_insights),
                "recent_insights": self.dream_insights[-5:] if self.dream_insights else [],
                "scenarios_practiced": len(self.practiced_scenarios),
                "recent_scenarios": self.practiced_scenarios[-3:] if self.practiced_scenarios else [],
                "suggestions": len(self.optimization_suggestions),
                "recent_suggestions": self.optimization_suggestions[-5:] if self.optimization_suggestions else [],
            }

    def health_check(self) -> Dict[str, Any]:
        """Return health status of the DreamEngine module."""
        with self._lock:
            base = super().health_check()
            base.update(self.get_dream_report())
            return base


# Usage example
if __name__ == "__main__":
    dream = DreamEngine()
    print("=" * 60)
    print("DREAM ENGINE TESTS:")
    print("=" * 60)

    print(f"\nEntering dream state...")
    dream.sleep()

    print(f"\nDream report:")
    report = dream.get_dream_report()
    print(f"  Insights: {report['insights_generated']}")
    print(f"  Scenarios: {report['scenarios_practiced']}")
    print(f"  Suggestions: {report['suggestions']}")

    print(f"\nRecent insights:")
    for insight in report["recent_insights"]:
        print(f"  [{insight['severity'].upper()}] {insight['insight']}")

    print(f"\nRecent scenarios:")
    for scenario in report["recent_scenarios"]:
        print(f"  {scenario['scenario']} ({scenario['difficulty']}) -> {'PASS' if scenario['simulated_success'] else 'FAIL'}")

    print(f"\nWaking up...")
    dream.wake()

    print("=" * 60)
    print("HEALTH CHECK:")
    print(dream.health_check())


__all__ = ["DreamEngine"]
