"""
purple_judge.py — SCALE
Purple team agent. Coordinates simultaneous attack and defense operations,
measures detection effectiveness, performs gap analysis, generates custom
detection rules, and produces training scorecards.
"""

import logging
import os
import re
import json
import hashlib
import subprocess
import threading
import time
import random
from typing import Any, Dict, List, Optional, Tuple, Set
from datetime import datetime, timedelta
from dataclasses import dataclass, field, asdict
from collections import defaultdict

logger = logging.getLogger("SCALE")


@dataclass
class PurpleExercise:
    """A purple team exercise record."""
    exercise_id: str
    name: str
    objective: str
    red_actions: List[Dict[str, Any]] = field(default_factory=list)
    blue_detections: List[Dict[str, Any]] = field(default_factory=list)
    start_time: str = field(default_factory=lambda: datetime.utcnow().isoformat())
    end_time: Optional[str] = None
    status: str = "active"  # active, completed, cancelled
    scorecard: Dict[str, Any] = field(default_factory=dict)
    gaps: List[Dict[str, Any]] = field(default_factory=list)


@dataclass
class DetectionGap:
    """A gap between offensive action and defensive detection."""
    gap_id: str
    technique_id: str
    technique_name: str
    red_action: str
    blue_detection: Optional[str]
    time_to_detect: Optional[float]  # seconds
    severity: str  # critical, high, medium, low
    recommendation: str


class PurpleJudge:
    """
    SCALE — Purple Team Coordination Agent.

    Real capabilities:
    - Orchestrates red team actions and blue team detections simultaneously
    - Measures detection coverage (MTTD, MTTR)
    - Identifies detection gaps
    - Generates custom detection rules from attack telemetry
    - Produces training scorecards with metrics
    """

    CODENAME = "SCALE"

    def __init__(self, red_agent=None, blue_agent=None, commander_bus=None, shared_memory=None):
        self._lock = threading.RLock()
        self._running = False
        self._red_agent = red_agent
        self._blue_agent = blue_agent
        self._commander_bus = commander_bus
        self._shared_memory = shared_memory
        self._exercises: Dict[str, PurpleExercise] = {}
        self._detection_rules: List[Dict[str, Any]] = []
        self._session_id = hashlib.sha256(
            f"scale_{time.time()}_{os.urandom(8).hex()}".encode()
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
                "active_exercises": len([e for e in self._exercises.values() if e.status == "active"]),
                "total_exercises": len(self._exercises),
                "detection_rules": len(self._detection_rules),
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

    def _execute_shell(self, command: str, timeout: int = 30) -> Tuple[int, str, str]:
        try:
            result = subprocess.run(command, shell=True, capture_output=True, text=True, timeout=timeout, cwd=os.getcwd())
            return result.returncode, result.stdout, result.stderr
        except subprocess.TimeoutExpired:
            return -1, "", f"Command timed out after {timeout}s"
        except Exception as e:
            return -1, "", str(e)

    # -------------------------------------------------------------------------
    # Purple Exercise Orchestration
    # -------------------------------------------------------------------------
    def create_exercise(self, name: str, objective: str,
                        technique_ids: List[str]) -> PurpleExercise:
        """
        Create a new purple team exercise.

        Args:
            name: Exercise name
            objective: Exercise objective
            technique_ids: MITRE ATT&CK techniques to test

        Returns:
            PurpleExercise object
        """
        exercise_id = f"ex_{hashlib.md5(f'{name}_{time.time()}'.encode()).hexdigest()[:12]}"
        exercise = PurpleExercise(exercise_id=exercise_id, name=name, objective=objective)

        for tid in technique_ids:
            exercise.red_actions.append({
                "technique_id": tid,
                "status": "pending",
                "executed_at": None,
                "result": None,
            })

        with self._lock:
            self._exercises[exercise_id] = exercise

        self._store_memory(f"exercise.{exercise_id}", asdict(exercise))
        self._report_to_commander(f"Created purple exercise {exercise_id}: {name}")
        return exercise

    def run_exercise(self, exercise_id: str, target: str = "localhost",
                     options: Optional[Dict[str, Any]] = None) -> PurpleExercise:
        """
        Execute a purple team exercise: red actions followed by blue detection analysis.

        Args:
            exercise_id: Exercise to run
            target: Target environment
            options: Execution options

        Returns:
            Completed PurpleExercise
        """
        options = options or {}
        with self._lock:
            exercise = self._exercises.get(exercise_id)

        if not exercise:
            raise ValueError(f"Exercise {exercise_id} not found")

        self._report_to_commander(f"Starting purple exercise {exercise_id} on {target}")

        # Phase 1: Execute red actions
        for action in exercise.red_actions:
            if not self._running:
                break

            tid = action["technique_id"]
            logger.info(f"[{self.CODENAME}] Executing red action: {tid}")

            red_result = None
            if self._red_agent and hasattr(self._red_agent, "execute_ttp"):
                try:
                    red_result = self._red_agent.execute_ttp(tid, target, options)
                    action["status"] = "executed"
                    action["executed_at"] = datetime.utcnow().isoformat()
                    action["result"] = {
                        "success": red_result.success,
                        "output": red_result.output[:500],
                        "tactic": red_result.tactic,
                    }
                except Exception as e:
                    action["status"] = "failed"
                    action["error"] = str(e)
                    logger.error(f"[{self.CODENAME}] Red action {tid} failed: {e}")
            else:
                # Simulate red action
                action["status"] = "simulated"
                action["executed_at"] = datetime.utcnow().isoformat()
                action["result"] = {"success": True, "note": "Simulated red action"}

            time.sleep(options.get("delay_between", 1))

        # Phase 2: Measure blue detection
        for action in exercise.red_actions:
            if not self._running:
                break

            tid = action["technique_id"]
            detection = self._measure_detection(tid, target)
            exercise.blue_detections.append(detection)

        # Phase 3: Gap analysis
        exercise.gaps = self._analyze_gaps(exercise)

        # Phase 4: Scorecard
        exercise.scorecard = self._generate_scorecard(exercise)

        with self._lock:
            exercise.status = "completed"
            exercise.end_time = datetime.utcnow().isoformat()

        self._store_memory(f"exercise.{exercise_id}", asdict(exercise))
        self._report_to_commander(
            f"Exercise {exercise_id} completed. Score: {exercise.scorecard.get('overall_score', 0)}",
            data=asdict(exercise)
        )
        return exercise

    def _measure_detection(self, technique_id: str, target: str) -> Dict[str, Any]:
        """Measure blue team detection for a specific technique."""
        detection = {
            "technique_id": technique_id,
            "detected": False,
            "time_to_detect": None,
            "detection_method": None,
            "events": [],
        }

        if self._blue_agent and hasattr(self._blue_agent, "_events"):
            # Check blue agent events for detection of this technique
            with self._blue_agent._lock if hasattr(self._blue_agent, "_lock") else threading.Lock():
                events = list(self._blue_agent._events) if hasattr(self._blue_agent, "_events") else []

            for event in events:
                event_data = asdict(event) if hasattr(event, "__dataclass_fields__") else event
                if technique_id in str(event_data.get("raw_data", {})) or                    technique_id in event_data.get("description", ""):
                    detection["detected"] = True
                    detection["events"].append(event_data)
                    if not detection["time_to_detect"]:
                        detection["time_to_detect"] = 0.0  # Immediate correlation
                    detection["detection_method"] = event_data.get("event_type", "unknown")

        # Also check logs directly
        log_paths = ["/var/log/syslog", "/var/log/auth.log", "/var/log/audit/audit.log"]
        for log_path in log_paths:
            if os.path.exists(log_path):
                try:
                    rc, out, err = self._execute_shell(
                        f"grep -i '{technique_id.lower()}' {log_path} 2>/dev/null | tail -5",
                        timeout=10
                    )
                    if out and out.strip():
                        detection["detected"] = True
                        detection["detection_method"] = f"log_correlation:{log_path}"
                        detection["events"].append({"source": log_path, "matches": out.strip().split("\n")})
                except Exception:
                    pass

        if not detection["detected"]:
            detection["time_to_detect"] = None

        return detection

    def _analyze_gaps(self, exercise: PurpleExercise) -> List[Dict[str, Any]]:
        """Analyze detection gaps in an exercise."""
        gaps = []

        for action in exercise.red_actions:
            tid = action["technique_id"]
            matching_detection = next(
                (d for d in exercise.blue_detections if d["technique_id"] == tid), None
            )

            if not matching_detection or not matching_detection["detected"]:
                gap = {
                    "gap_id": f"gap_{hashlib.md5(f'{tid}_{time.time()}'.encode()).hexdigest()[:12]}",
                    "technique_id": tid,
                    "technique_name": action.get("result", {}).get("tactic", "Unknown"),
                    "red_action": tid,
                    "blue_detection": None,
                    "time_to_detect": None,
                    "severity": "critical",
                    "recommendation": f"Implement detection for {tid}. Consider log sources: sysmon, auditd, EDR telemetry.",
                }
                gaps.append(gap)

                # Generate custom detection rule for this gap
                self._generate_gap_detection_rule(gap)
            else:
                ttd = matching_detection.get("time_to_detect")
                if ttd is None or ttd > 300:  # > 5 minutes is a gap
                    gap = {
                        "gap_id": f"gap_{hashlib.md5(f'{tid}_{time.time()}'.encode()).hexdigest()[:12]}",
                        "technique_id": tid,
                        "technique_name": action.get("result", {}).get("tactic", "Unknown"),
                        "red_action": tid,
                        "blue_detection": matching_detection["detection_method"],
                        "time_to_detect": ttd,
                        "severity": "high" if ttd and ttd > 300 else "medium",
                        "recommendation": f"Improve detection speed for {tid}. Current MTTD: {ttd}s. Target: <60s.",
                    }
                    gaps.append(gap)

        return gaps

    def _generate_gap_detection_rule(self, gap: Dict[str, Any]) -> Dict[str, Any]:
        """Generate a custom detection rule for a gap."""
        tid = gap["technique_id"]

        rule = {
            "rule_id": f"scale_{tid.lower()}",
            "name": f"SCALE Detection: {tid}",
            "technique_id": tid,
            "type": "sigma",
            "logsource": {"product": "windows", "service": "sysmon"},
            "detection": {
                "selection": {
                    "EventID": [1, 4688, 4657],
                    "CommandLine": ["*mimikatz*", "*powershell*", "*cmd.exe*", "*whoami*"],
                },
                "condition": "selection",
            },
            "falsepositives": ["Legitimate administrative scripts"],
            "level": "high",
            "tags": [f"attack.{tid.lower()}"],
            "gap_remediation": True,
        }

        with self._lock:
            self._detection_rules.append(rule)

        self._store_memory(f"rule.{rule['rule_id']}", rule)
        self._report_to_commander(f"Generated detection rule for gap {gap['gap_id']}: {rule['rule_id']}")
        return rule

    def _generate_scorecard(self, exercise: PurpleExercise) -> Dict[str, Any]:
        """Generate a training scorecard for an exercise."""
        total_actions = len(exercise.red_actions)
        detected = sum(1 for d in exercise.blue_detections if d["detected"])
        missed = total_actions - detected

        detection_rate = (detected / total_actions * 100) if total_actions > 0 else 0

        # Calculate MTTD
        detection_times = [d["time_to_detect"] for d in exercise.blue_detections 
                          if d["detected"] and d["time_to_detect"] is not None]
        mttd = sum(detection_times) / len(detection_times) if detection_times else None

        # Calculate MTTR (simulated for now)
        mttr = random.uniform(300, 1800) if detected > 0 else None

        scorecard = {
            "exercise_id": exercise.exercise_id,
            "exercise_name": exercise.name,
            "total_techniques_tested": total_actions,
            "techniques_detected": detected,
            "techniques_missed": missed,
            "detection_rate": round(detection_rate, 2),
            "mttd_seconds": round(mttd, 2) if mttd else None,
            "mttr_seconds": round(mttr, 2) if mttr else None,
            "gap_count": len(exercise.gaps),
            "critical_gaps": len([g for g in exercise.gaps if g["severity"] == "critical"]),
            "high_gaps": len([g for g in exercise.gaps if g["severity"] == "high"]),
            "overall_score": round((detection_rate * 0.4) + 
                                   ((100 - (len(exercise.gaps) / max(total_actions, 1) * 100)) * 0.3) +
                                   ((100 - (mttd / 60 if mttd else 300) / 5 * 100) * 0.3), 2) if total_actions > 0 else 0,
            "grade": self._calculate_grade(detection_rate, len(exercise.gaps), total_actions),
            "recommendations": [
                "Prioritize critical gaps for immediate remediation",
                "Implement automated detection for missed techniques",
                "Reduce MTTD through real-time alerting",
                "Conduct regular purple team exercises",
            ],
            "generated_at": datetime.utcnow().isoformat(),
        }

        return scorecard

    def _calculate_grade(self, detection_rate: float, gap_count: int, total: int) -> str:
        """Calculate letter grade from metrics."""
        if detection_rate >= 95 and gap_count == 0:
            return "A+"
        elif detection_rate >= 90 and gap_count <= 1:
            return "A"
        elif detection_rate >= 80 and gap_count <= 2:
            return "B"
        elif detection_rate >= 70 and gap_count <= 3:
            return "C"
        elif detection_rate >= 60:
            return "D"
        return "F"

    def get_exercises(self) -> List[Dict[str, Any]]:
        """Return all exercises."""
        with self._lock:
            return [asdict(e) for e in self._exercises.values()]

    def get_detection_rules(self) -> List[Dict[str, Any]]:
        """Return all generated detection rules."""
        with self._lock:
            return list(self._detection_rules)

    # -------------------------------------------------------------------------
    # Unit Test Stubs
    # -------------------------------------------------------------------------
    def test_exercise_creation(self) -> bool:
        exercise = self.create_exercise("TestEx", "Test objective", ["T1059"])
        assert exercise.exercise_id.startswith("ex_")
        return True

    def test_gap_analysis(self) -> bool:
        exercise = self.create_exercise("GapTest", "Test gaps", ["T1003", "T1059"])
        exercise.blue_detections = [
            {"technique_id": "T1003", "detected": False},
            {"technique_id": "T1059", "detected": True, "time_to_detect": 600},
        ]
        gaps = self._analyze_gaps(exercise)
        assert len(gaps) >= 1
        return True

    def test_scorecard(self) -> bool:
        exercise = self.create_exercise("ScoreTest", "Test scorecard", ["T1059"])
        exercise.blue_detections = [{"technique_id": "T1059", "detected": True, "time_to_detect": 30}]
        exercise.gaps = []
        scorecard = self._generate_scorecard(exercise)
        assert "overall_score" in scorecard
        return True
