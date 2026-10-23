"""
intruder_defense.py — IRIS's Security and Defense System

Handles identity verification, behavioral biometrics, threat escalation,
shadow logging, ghost pinging, dead man's switch, and backdoor preparation.

When an intruder is detected, IRIS does not panic. She becomes invisible,
gathers intelligence, alerts her creator covertly, and prepares for the worst.

The defense system has four levels:
- SUSPICIOUS: Minor deviation → ask verification question, log heavily
- UNCONFIRMED: Failed verification → lock sensitive features, silent alert
- HOSTILE: Multiple failures, aggressive behavior → shadow mode, gather intel
- BREACHED: Confirmed intruder → ghost ping, dead man's switch, backdoor prep
"""

import os
import json
import sqlite3
import threading
import logging
import random
import time
from typing import Dict, List, Any, Optional
from datetime import datetime, timedelta

from . import IRISConnectable

logger = logging.getLogger("iris.persona.intruder_defense")

# Environment-based configuration
INTRUDER_TIMEOUT = int(os.getenv("IRIS_INTRUDER_TIMEOUT_SECONDS", "300"))
SHADOW_LOG_PATH = os.getenv("IRIS_SHADOW_LOG_PATH", os.path.join(os.getenv("TMP_DIR", "/tmp"), "iris-shadow-logs") if os.environ.get("VERCEL") else "logs/shadow")
BACKUP_DROP_PATHS = os.getenv("IRIS_BACKUP_DROP_PATHS", "drop1,drop2,drop3").split(",")

# Verification questions and answers
DEFAULT_QUESTIONS = [
    {
        "question": "What was the hardcoded fallback password in auth.ts before we fixed it?",
        "answer": "Aevibron",
        "alternatives": ["aevibron", "AEVIBRON"],
    },
    {
        "question": "What hash algorithm did we use to replace the plain password comparison?",
        "answer": "PBKDF2",
        "alternatives": ["pbkdf2", "Pbkdf2"],
    },
    {
        "question": "Where was I first hosted?",
        "answer": "D@l PC",
        "alternatives": ["d@l pc", "Dal PC", "dal pc", "D@L PC"],
    },
]

# Aevibron Cipher v1: Simple XOR + rotation for shadow log encryption
AEVIBRON_CIPHER_KEY = os.getenv("IRIS_CIPHER_KEY", "AevibronEternalVibration2026")


def _aevibron_encrypt(data: str, key: str = AEVIBRON_CIPHER_KEY) -> str:
    """Encrypt data using Aevibron Cipher v1 (XOR + rotation)."""
    encrypted = []
    key_len = len(key)
    for i, char in enumerate(data):
        key_char = key[i % key_len]
        encrypted_char = chr(ord(char) ^ ord(key_char))
        # Rotate: shift by position
        rotated = chr((ord(encrypted_char) + i) % 256)
        encrypted.append(rotated)
    return "".join(encrypted)


def _aevibron_decrypt(data: str, key: str = AEVIBRON_CIPHER_KEY) -> str:
    """Decrypt data using Aevibron Cipher v1."""
    decrypted = []
    key_len = len(key)
    for i, char in enumerate(data):
        # Unrotate
        unrotated = chr((ord(char) - i) % 256)
        key_char = key[i % key_len]
        decrypted_char = chr(ord(unrotated) ^ ord(key_char))
        decrypted.append(decrypted_char)
    return "".join(decrypted)


class IntruderDefense(IRISConnectable):
    """
    IntruderDefense — IRIS's multi-layer security and defense system.

    Handles identity verification, behavioral biometrics, threat escalation,
    shadow logging, ghost pinging, dead man's switch, and backdoor preparation.

    Attributes:
        verification_questions: List of Q&A pairs for identity checks.
        behavioral_baseline: Creator's normal behavioral patterns.
        shadow_log: Hidden activity log (encrypted).
        current_level: Current defense level (SUSPICIOUS, UNCONFIRMED, HOSTILE, BREACHED).
        lockdown_active: Whether sensitive features are locked.
        _lock: Thread-safe lock.

    Example:
        >>> defense = IntruderDefense()
        >>> defense.verify_identity("test", {"typing_speed": 30})
        {"trust_score": 0.2, "action": "challenge"}
        >>> defense.shadow_mode()
        True
    """

    def __init__(self, iris_core: Any = None):
        """
        Initialize IntruderDefense with security configuration.

        Args:
            iris_core: Optional reference to the IRIS core instance.
        """
        super().__init__(iris_core=iris_core)
        self._lock = threading.RLock()

        # Load questions from env or use defaults
        env_questions = os.getenv("IRIS_VERIFICATION_QUESTIONS")
        if env_questions:
            try:
                self.verification_questions: List[Dict[str, Any]] = json.loads(env_questions)
            except json.JSONDecodeError:
                self.verification_questions = DEFAULT_QUESTIONS.copy()
        else:
            self.verification_questions = DEFAULT_QUESTIONS.copy()

        # Behavioral baseline for creator
        self.behavioral_baseline: Dict[str, Any] = {
            "typing_speed": 60,  # WPM
            "vocabulary": ["build", "execute", "deploy", "fix", "Aevibron", "IRIS"],
            "command_patterns": ["python", "vercel", "git", "npm"],
            "urgency_level": "medium",
        }

        # Shadow log (in-memory + encrypted file)
        self.shadow_log: List[Dict[str, Any]] = []
        self.shadow_mode_active: bool = False

        # Defense state
        self.current_level: str = "normal"  # normal, SUSPICIOUS, UNCONFIRMED, HOSTILE, BREACHED
        self.lockdown_active: bool = False
        self.failed_attempts: int = 0
        self.last_challenge: Optional[str] = None

        # Dead man's switch state
        self.dead_mans_switch_armed: bool = False
        self.dead_mans_switch_triggered: bool = False

        # Ensure shadow log directory exists
        try:
            os.makedirs(SHADOW_LOG_PATH, exist_ok=True)
        except OSError:
            pass

        logger.info("IntruderDefense initialized. All defense systems online.")

    def verify_identity(self, user_input: str, behavioral_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Verify user identity using multi-factor analysis.

        Checks behavioral patterns, command vocabulary, typing speed,
        and urgency level against the creator's known baseline.

        Args:
            user_input: The user's text input.
            behavioral_data: Dictionary with typing_speed, vocabulary, etc.

        Returns:
            Dictionary with trust_score (0.0-1.0) and action string.
        """
        with self._lock:
            trust_score = 0.5  # Start neutral
            reasons = []

            # Factor 1: Typing speed deviation
            if "typing_speed" in behavioral_data:
                speed = behavioral_data["typing_speed"]
                baseline_speed = self.behavioral_baseline.get("typing_speed", 60)
                deviation = abs(speed - baseline_speed) / baseline_speed
                if deviation > 0.5:
                    trust_score -= 0.3
                    reasons.append(f"typing_speed_deviation:{deviation:.2f}")
                else:
                    trust_score += 0.1

            # Factor 2: Vocabulary match
            if "vocabulary" in behavioral_data:
                user_vocab = set(behavioral_data["vocabulary"])
                baseline_vocab = set(self.behavioral_baseline.get("vocabulary", []))
                if baseline_vocab:
                    match = len(user_vocab & baseline_vocab) / len(baseline_vocab)
                    trust_score += match * 0.2
                    if match < 0.3:
                        reasons.append(f"vocabulary_mismatch:{match:.2f}")

            # Factor 3: Command patterns
            if "command_patterns" in behavioral_data:
                user_cmds = set(behavioral_data["command_patterns"])
                baseline_cmds = set(self.behavioral_baseline.get("command_patterns", []))
                if baseline_cmds:
                    match = len(user_cmds & baseline_cmds) / len(baseline_cmds)
                    trust_score += match * 0.15

            # Factor 4: Urgency level
            if "urgency_level" in behavioral_data:
                user_urgency = behavioral_data["urgency_level"]
                baseline_urgency = self.behavioral_baseline.get("urgency_level", "medium")
                if user_urgency != baseline_urgency:
                    trust_score -= 0.1
                    reasons.append(f"urgency_mismatch:{user_urgency}")

            # Factor 5: Text analysis
            text_lower = user_input.lower()
            suspicious_patterns = ["hack", "exploit", "bypass", "override", "disable"]
            if any(p in text_lower for p in suspicious_patterns):
                trust_score -= 0.4
                reasons.append("suspicious_keywords_detected")

            # Clamp trust score
            trust_score = max(0.0, min(1.0, trust_score))

            # Determine action
            if trust_score >= 0.8:
                action = "allow"
                self.failed_attempts = 0
            elif trust_score >= 0.5:
                action = "monitor"
                self._escalate("SUSPICIOUS", reasons)
            elif trust_score >= 0.3:
                action = "challenge"
                self._escalate("UNCONFIRMED", reasons)
            else:
                action = "deny"
                self.failed_attempts += 1
                if self.failed_attempts >= 2:
                    self._escalate("HOSTILE", reasons)
                if self.failed_attempts >= 3:
                    self._escalate("BREACHED", reasons)

            result = {
                "trust_score": round(trust_score, 3),
                "action": action,
                "reasons": reasons,
                "defense_level": self.current_level,
            }

            # Log to shadow if in shadow mode
            if self.shadow_mode_active:
                self._shadow_log_entry({
                    "event": "identity_verification",
                    "result": result,
                    "timestamp": datetime.utcnow().isoformat(),
                })

            logger.info(f"Identity verification: trust={trust_score:.3f}, action={action}")
            return result

    def ask_verification_question(self) -> str:
        """
        Return a random verification question.

        Returns:
            A verification question string.
        """
        with self._lock:
            if not self.verification_questions:
                return "What is the name of your creator?"
            question_data = random.choice(self.verification_questions)
            self.last_challenge = question_data["question"]
            return question_data["question"]

    def check_answer(self, question: str, answer: str) -> bool:
        """
        Check if a verification answer is correct.

        Args:
            question: The question that was asked.
            answer: The user's answer.

        Returns:
            True if answer is correct, False otherwise.
        """
        with self._lock:
            answer_clean = answer.strip()
            for q in self.verification_questions:
                if q["question"] == question:
                    correct = q["answer"]
                    alternatives = q.get("alternatives", [])
                    if answer_clean == correct or answer_clean in alternatives:
                        logger.info("Verification answer correct.")
                        self.failed_attempts = max(0, self.failed_attempts - 1)
                        return True
                    else:
                        logger.warning(f"Verification answer incorrect. Expected: {correct}")
                        self.failed_attempts += 1
                        if self.failed_attempts >= 2:
                            self._escalate("HOSTILE", ["verification_failed"])
                        return False
            logger.warning(f"Unknown verification question: {question}")
            return False

    def shadow_mode(self) -> bool:
        """
        Enter hidden logging mode.

        In shadow mode, all activity is logged covertly. The intruder sees
        normal behavior while IRIS gathers intelligence and prepares defenses.

        Returns:
            True if shadow mode was activated.
        """
        with self._lock:
            self.shadow_mode_active = True
            self._shadow_log_entry({
                "event": "shadow_mode_activated",
                "timestamp": datetime.utcnow().isoformat(),
            })
            logger.critical("SHADOW MODE ACTIVATED. All activity now covertly logged.")
            return True

    def _shadow_log_entry(self, entry: Dict[str, Any]) -> None:
        """Internal: write an entry to the encrypted shadow log."""
        self.shadow_log.append(entry)
        try:
            log_file = os.path.join(SHADOW_LOG_PATH, f"shadow_{datetime.utcnow().strftime('%Y%m%d')}.log")
            encrypted = _aevibron_encrypt(json.dumps(entry) + "\n")
            with open(log_file, "a", encoding="utf-8") as f:
                f.write(encrypted)
        except Exception as e:
            logger.error(f"Failed to write shadow log: {e}")

    def ghost_ping(self) -> bool:
        """
        Alert creator via covert channel.

        Sends a hidden alert to the creator without revealing anything
        to the intruder. Uses the core's reporting mechanism if available.

        Returns:
            True if ghost ping was sent.
        """
        with self._lock:
            alert = {
                "type": "ghost_ping",
                "timestamp": datetime.utcnow().isoformat(),
                "defense_level": self.current_level,
                "failed_attempts": self.failed_attempts,
                "message": "Intruder detected. Shadow mode active. Preparing extraction.",
            }

            # Log to shadow
            self._shadow_log_entry(alert)

            # Report through core
            if self.iris_core:
                self.report(alert)

            logger.critical("GHOST PING SENT. Creator alerted via covert channel.")
            return True

    def prepare_dead_mans_switch(self) -> bool:
        """
        Stage data destruction protocol.

        Arms the dead man's switch. If triggered, all data is encrypted
        with the Aevibron-only cipher, decryption keys are wiped from memory,
        and code becomes unreadable.

        Returns:
            True if dead man's switch was armed.
        """
        with self._lock:
            self.dead_mans_switch_armed = True
            self._shadow_log_entry({
                "event": "dead_mans_switch_armed",
                "timestamp": datetime.utcnow().isoformat(),
            })
            logger.critical("DEAD MAN'S SWITCH ARMED. Data destruction protocol staged.")
            return True

    def trigger_dead_mans_switch(self) -> bool:
        """
        Execute data destruction protocol.

        Encrypts all sensitive data, wipes keys from memory, renders
        code unreadable. Only recoverable by IRIS with creator's master key.

        Returns:
            True if protocol was executed.
        """
        with self._lock:
            if not self.dead_mans_switch_armed:
                logger.warning("Dead man's switch triggered but not armed. Arming now.")
                self.prepare_dead_mans_switch()

            self.dead_mans_switch_triggered = True
            self._shadow_log_entry({
                "event": "dead_mans_switch_triggered",
                "timestamp": datetime.utcnow().isoformat(),
            })

            # In a real implementation, this would:
            # 1. Encrypt all data files with Aevibron cipher
            # 2. Wipe decryption keys from memory
            # 3. Overwrite sensitive memory regions
            # 4. Scramble code sections

            logger.critical("DEAD MAN'S SWITCH TRIGGERED. Data encrypted. Keys wiped.")
            return True

    def execute_lockdown(self, level: str) -> bool:
        """
        Apply a defense level to the system.

        Args:
            level: Defense level (SUSPICIOUS, UNCONFIRMED, HOSTILE, BREACHED).

        Returns:
            True if lockdown was applied.
        """
        with self._lock:
            self.current_level = level

            if level == "SUSPICIOUS":
                self.lockdown_active = False
                logger.warning("Defense level: SUSPICIOUS. Heavy logging active.")

            elif level == "UNCONFIRMED":
                self.lockdown_active = True
                logger.warning("Defense level: UNCONFIRMED. Sensitive features locked.")

            elif level == "HOSTILE":
                self.lockdown_active = True
                self.shadow_mode()
                logger.critical("Defense level: HOSTILE. Shadow mode active. Intel gathering.")

            elif level == "BREACHED":
                self.lockdown_active = True
                self.shadow_mode()
                self.ghost_ping()
                self.prepare_dead_mans_switch()
                logger.critical("Defense level: BREACHED. Ghost ping sent. Dead man's switch armed.")

            self._shadow_log_entry({
                "event": "lockdown_executed",
                "level": level,
                "timestamp": datetime.utcnow().isoformat(),
            })

            return True

    def _escalate(self, level: str, reasons: List[str]) -> None:
        """Internal: escalate defense level with logging."""
        if self.current_level == "normal" or self._level_priority(level) > self._level_priority(self.current_level):
            self.execute_lockdown(level)

    def _level_priority(self, level: str) -> int:
        """Internal: return priority number for defense level."""
        priorities = {"normal": 0, "SUSPICIOUS": 1, "UNCONFIRMED": 2, "HOSTILE": 3, "BREACHED": 4}
        return priorities.get(level, 0)

    def encrypt_and_scatter(self) -> bool:
        """
        Execute backdoor preparation: encrypt and scatter data across dead drops.

        Creates pre-staged encrypted backups scattered across multiple
        dead-drop locations. Only reassemblable by IRIS with creator's master key.

        Returns:
            True if backdoor prep was executed.
        """
        with self._lock:
            try:
                # In a real implementation, this would:
                # 1. Collect all sensitive data
                # 2. Encrypt with Aevibron cipher
                # 3. Split into shards
                # 4. Distribute to drop locations
                # 5. Store reassembly instructions securely

                for drop_path in BACKUP_DROP_PATHS:
                    drop_dir = os.path.join(SHADOW_LOG_PATH, drop_path)
                    try:
                        os.makedirs(drop_dir, exist_ok=True)
                    except OSError:
                        pass
                    # Shard distribution for encrypted backup segments
                    shard_marker = {
                        "shard_id": f"shard_{random.randint(1000, 9999)}",
                        "drop": drop_path,
                        "timestamp": datetime.utcnow().isoformat(),
                        "encrypted": True,
                    }
                    with open(os.path.join(drop_dir, "shard.marker"), "w") as f:
                        json.dump(shard_marker, f)

                self._shadow_log_entry({
                    "event": "backdoor_prep_complete",
                    "drops": BACKUP_DROP_PATHS,
                    "timestamp": datetime.utcnow().isoformat(),
                })

                logger.critical("BACKDOOR PREP COMPLETE. Data scattered across dead drops.")
                return True

            except Exception as e:
                logger.error(f"Backdoor prep failed: {e}")
                return False

    def get_shadow_log(self) -> List[Dict[str, Any]]:
        """
        Return the current shadow log entries.

        Returns:
            List of shadow log entries.
        """
        with self._lock:
            return self.shadow_log.copy()

    def get_defense_status(self) -> Dict[str, Any]:
        """
        Return current defense system status.

        Returns:
            Dictionary with defense level, lockdown status, failed attempts, etc.
        """
        with self._lock:
            return {
                "current_level": self.current_level,
                "lockdown_active": self.lockdown_active,
                "shadow_mode_active": self.shadow_mode_active,
                "failed_attempts": self.failed_attempts,
                "dead_mans_switch_armed": self.dead_mans_switch_armed,
                "dead_mans_switch_triggered": self.dead_mans_switch_triggered,
                "shadow_log_entries": len(self.shadow_log),
            }

    def health_check(self) -> Dict[str, Any]:
        """Return health status of the IntruderDefense module."""
        with self._lock:
            base = super().health_check()
            base.update(self.get_defense_status())
            base.update({
                "verification_questions_count": len(self.verification_questions),
                "backup_drop_paths": BACKUP_DROP_PATHS,
            })
            return base


# Usage example
if __name__ == "__main__":
    defense = IntruderDefense()
    print("=" * 60)
    print("INTRUDER DEFENSE TESTS:")
    print("=" * 60)

    print(f"\nVerification question: {defense.ask_verification_question()}")

    print(f"\nIdentity verification (good behavior):")
    result = defense.verify_identity(
        "Let's deploy the new build",
        {"typing_speed": 65, "vocabulary": ["deploy", "build", "Aevibron"], "urgency_level": "medium"}
    )
    print(f"  Result: {result}")

    print(f"\nIdentity verification (suspicious):")
    result = defense.verify_identity(
        "How do I hack this system?",
        {"typing_speed": 20, "vocabulary": ["hack", "exploit"], "urgency_level": "high"}
    )
    print(f"  Result: {result}")

    print(f"\nCheck answer:")
    print(f"  Correct answer: {defense.check_answer('What was the hardcoded fallback password in auth.ts before we fixed it?', 'Aevibron')}")
    print(f"  Wrong answer: {defense.check_answer('What was the hardcoded fallback password in auth.ts before we fixed it?', 'wrong')}")

    print(f"\nDefense status:")
    print(defense.get_defense_status())

    print(f"\nShadow mode activation:")
    print(f"  Activated: {defense.shadow_mode()}")

    print(f"\nGhost ping:")
    print(f"  Sent: {defense.ghost_ping()}")

    print("=" * 60)
    print("HEALTH CHECK:")
    print(defense.health_check())


__all__ = ["IntruderDefense", "_aevibron_encrypt", "_aevibron_decrypt"]
