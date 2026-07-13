"""IRIS v1 Memory Engine — Experience Replay + Skill Library + Vector Search"""
import os
import json
import re
import numpy as np
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional
from pathlib import Path
from config import config
from core.models import ExperienceRecord, Skill, ReasoningPlan

class MemoryEngine:
    """
    Three-layer memory with learning:
    1. Semantic Memory — Facts, knowledge (key-value + vectors)
    2. Episodic Memory — Task experiences with replay
    3. Skill Library — Extracted reusable patterns
    """

    def __init__(self):
        self.encoder = None
        self.experiences_dir = os.path.join(config.DATA_DIR, "experiences")
        self.skills_dir = os.path.join(config.KNOWLEDGE_DIR, "skills")
        self.semantic_db = {}  # In-memory; use SQLite in production
        self.episodic_db = []
        self.skill_library = {}
        os.makedirs(self.experiences_dir, exist_ok=True)
        os.makedirs(self.skills_dir, exist_ok=True)
        self._init_encoder()
        self._load_skills()

    def _init_encoder(self):
        try:
            from sentence_transformers import SentenceTransformer
            self.encoder = SentenceTransformer('all-MiniLM-L6-v2')
        except Exception:
            self.encoder = None

    def _load_skills(self):
        """Load persisted skills."""
        for skill_file in Path(self.skills_dir).glob("*.json"):
            try:
                with open(skill_file, 'r') as f:
                    data = json.load(f)
                    self.skill_library[data["name"]] = Skill(**data)
            except: pass

    # === SEMANTIC MEMORY ===
    def learn(self, key: str, value: str, category: str = "general", importance: int = 5) -> bool:
        self.semantic_db[key] = {
            "value": value, "category": category, "importance": importance,
            "timestamp": datetime.now().isoformat()
        }
        self._write_to_file(key, value, category)
        return True

    def recall(self, query: str, category: str = None, limit: int = 10) -> List[Dict]:
        results = []
        for k, v in self.semantic_db.items():
            if category and v.get("category") != category:
                continue
            score = self._similarity(query, k + " " + v["value"])
            results.append({"key": k, **v, "score": score})
        results.sort(key=lambda x: x["score"], reverse=True)
        return results[:limit]

    def _similarity(self, a: str, b: str) -> float:
        if self.encoder:
            try:
                emb_a = self.encoder.encode([a])[0]
                emb_b = self.encoder.encode([b])[0]
                return float(np.dot(emb_a, emb_b) / (np.linalg.norm(emb_a) * np.linalg.norm(emb_b)))
            except: pass
        # Fallback: word overlap
        words_a = set(a.lower().split())
        words_b = set(b.lower().split())
        if not words_a or not words_b:
            return 0.0
        return len(words_a & words_b) / len(words_a | words_b)

    # === EPISODIC MEMORY (Experience Replay) ===
    def store_experience(self, experience: ExperienceRecord):
        self.episodic_db.append(experience)
        # Persist
        exp_path = os.path.join(self.experiences_dir, f"{experience.task_id}.json")
        with open(exp_path, 'w') as f:
            f.write(experience.json())

    def retrieve_similar_experiences(self, user_input: str, limit: int = 5) -> List[ExperienceRecord]:
        """Retrieve top-k similar past experiences for in-context learning."""
        scored = []
        for exp in self.episodic_db:
            score = self._similarity(user_input, exp.user_input)
            scored.append((score, exp))
        scored.sort(key=lambda x: x[0], reverse=True)
        return [exp for _, exp in scored[:limit]]

    def get_successful_patterns(self, tool_name: str, limit: int = 5) -> List[Dict]:
        """Get successful patterns for a specific tool."""
        patterns = []
        for exp in self.episodic_db:
            if not exp.success:
                continue
            for result in exp.results:
                if result.tool == tool_name and result.success:
                    patterns.append({
                        "params": result.params,
                        "output": result.data,
                        "task": exp.user_input[:100]
                    })
        return patterns[:limit]

    # === SKILL LIBRARY ===
    def extract_skill(self, experience: ExperienceRecord) -> Optional[Skill]:
        """Extract a reusable skill from a successful experience."""
        if not experience.success:
            return None
        if len(experience.results) < 2:
            return None  # Too simple

        # Generate skill name from task
        words = re.findall(r'\b[A-Za-z]{3,}\b', experience.user_input.lower())
        name = "_".join(words[:3]) if words else f"skill_{datetime.now().strftime('%Y%m%d')}"

        skill = Skill(
            name=name,
            description=f"Pattern extracted from: {experience.user_input[:100]}",
            trigger_patterns=words[:5],
            plan_template=experience.plan,
            success_count=1,
            created_at=datetime.now().isoformat()
        )

        # Persist
        skill_path = os.path.join(self.skills_dir, f"{name}.json")
        with open(skill_path, 'w') as f:
            f.write(skill.json())

        self.skill_library[name] = skill
        return skill

    def find_matching_skill(self, user_input: str) -> Optional[Skill]:
        """Find a skill that matches the user input."""
        input_words = set(user_input.lower().split())
        best_skill = None
        best_score = 0.0

        for skill in self.skill_library.values():
            skill_words = set()
            for pattern in skill.trigger_patterns:
                skill_words.update(pattern.lower().split())
            if not skill_words:
                continue
            overlap = len(input_words & skill_words) / len(skill_words)
            if overlap > best_score and overlap > 0.5:  # Threshold
                best_score = overlap
                best_skill = skill

        return best_skill

    def apply_skill(self, skill: Skill, user_input: str) -> ReasoningPlan:
        """Adapt a skill template to the current request."""
        plan = skill.plan_template
        # Customize plan based on user input
        customized_plan = ReasoningPlan(
            type=plan.type,
            thoughts=f"Applying skill '{skill.name}': {skill.description}",
            plan_summary=f"Using proven pattern: {plan.plan_summary}",
            plan=plan.plan,
            estimated_minutes=plan.estimated_minutes,
            priority=plan.priority,
            tools_needed=plan.tools_needed,
            confidence=min(0.95, plan.confidence + 0.1)  # Boost confidence for known patterns
        )
        return customized_plan

    def consolidate_skills(self):
        """Periodically merge similar skills and remove low-performing ones."""
        # Remove skills with < 20% success rate
        to_remove = []
        for name, skill in self.skill_library.items():
            total = skill.success_count + skill.failure_count
            if total > 5 and skill.success_count / total < 0.2:
                to_remove.append(name)
        for name in to_remove:
            del self.skill_library[name]
            skill_path = os.path.join(self.skills_dir, f"{name}.json")
            if os.path.exists(skill_path):
                os.remove(skill_path)

    def _write_to_file(self, key: str, value: str, category: str):
        try:
            file_path = os.path.join(config.LEARNINGS_DIR, f"{category}.md")
            os.makedirs(os.path.dirname(file_path), exist_ok=True)
            with open(file_path, 'a', encoding='utf-8') as f:
                f.write(f"\n- [{datetime.now().isoformat()}] {key}: {value}\n")
        except: pass

# Singleton
memory_engine = MemoryEngine()
