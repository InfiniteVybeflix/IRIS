"""Skill Registry — auto-discovers and catalogs all skills."""
import os
import sys
import importlib
import inspect
import logging
from pathlib import Path
from typing import Dict, List, Optional, Type, Any

from skills.base import BaseSkill
from skills.contracts.skill_request import SkillRequest
from skills.contracts.skill_result import SkillResult

logger = logging.getLogger(__name__)


class SkillRegistry:
    """
    Auto-discovers every skill in the skills/ directory.
    No manual registration needed.
    """

    def __init__(self, skills_root: str = None):
        self.skills_root = skills_root or os.path.dirname(os.path.abspath(__file__))
        self._skills: Dict[str, BaseSkill] = {}
        self._skill_classes: Dict[str, Type[BaseSkill]] = {}
        self._capability_index: Dict[str, List[str]] = {}
        self._discover()

    def _discover(self):
        """Scan all subdirectories for skill.py files and load them."""
        skills_dir = Path(self.skills_root)
        count = 0

        for skill_file in skills_dir.rglob("skill.py"):
            rel_path = skill_file.relative_to(skills_dir)
            # Skip _utils, contracts, and __pycache__
            if any(part.startswith("_") or part == "contracts" for part in rel_path.parts):
                continue

            # Build module path: skills.productivity.calendar.skill
            parts = list(rel_path.parts)[:-1]  # remove skill.py
            module_path = "skills." + ".".join(parts) + ".skill"

            try:
                # Ensure parent packages are importable
                self._ensure_packages_importable(skill_file.parent)

                module = importlib.import_module(module_path)
                for name, obj in inspect.getmembers(module):
                    if (inspect.isclass(obj) and
                        issubclass(obj, BaseSkill) and
                        obj is not BaseSkill and
                        hasattr(obj, "name") and
                        obj.name != "base"):

                        skill_instance = obj()
                        self._register(skill_instance)
                        count += 1
                        break  # One skill class per file
            except Exception as e:
                logger.warning(f"Failed to load skill from {rel_path}: {e}")

        logger.info(f"SkillRegistry: discovered {count} skills")

    def _ensure_packages_importable(self, directory: Path):
        """Add __init__.py files if missing so Python can import."""
        for parent in [directory] + list(directory.parents):
            if parent == Path(self.skills_root).parent:
                break
            init_file = parent / "__init__.py"
            if not init_file.exists():
                init_file.touch()

    def _register(self, skill: BaseSkill):
        self._skills[skill.name] = skill
        self._skill_classes[skill.name] = skill.__class__
        for cap in skill.capabilities:
            if cap.name not in self._capability_index:
                self._capability_index[cap.name] = []
            self._capability_index[cap.name].append(skill.name)
        logger.debug(f"Registered skill: {skill.name}")

    # === Public API ===
    def get(self, name: str) -> Optional[BaseSkill]:
        return self._skills.get(name)

    def list_skills(self) -> List[Dict[str, Any]]:
        return [s.get_metadata() for s in self._skills.values()]

    def list_names(self) -> List[str]:
        return list(self._skills.keys())

    def find_by_capability(self, capability_name: str) -> List[str]:
        return self._capability_index.get(capability_name, [])

    def route(self, request: SkillRequest) -> Optional[BaseSkill]:
        """Find the best skill for a request."""
        best_skill = None
        best_score = 0.0

        for skill in self._skills.values():
            score = skill.can_handle(request)
            if score > best_score:
                best_score = score
                best_skill = skill

        if best_score < 0.3:
            return None
        return best_skill

    def execute(self, request: SkillRequest) -> SkillResult:
        """Route and execute in one call."""
        skill = self.route(request)
        if not skill:
            return SkillResult.fail(
                error="No skill found for this request",
                message=f"Could not route intent: {request.intent}",
                suggestions=["Check available skills", "Rephrase your request"]
            )
        return skill.execute(request)

    def get_catalog(self) -> Dict[str, Any]:
        """Full catalog for AI introspection."""
        return {
            "total_skills": len(self._skills),
            "skills": self.list_skills(),
            "capability_index": self._capability_index,
        }

    def background_tick_all(self) -> List[SkillResult]:
        """Run background checks on all skills that support it."""
        results = []
        for skill in self._skills.values():
            if skill.supports_background:
                try:
                    tick_results = skill.background_tick()
                    results.extend(tick_results)
                except Exception as e:
                    logger.error(f"[{skill.name}] Background tick error: {e}")
        return results

    def reload_skill(self, name: str) -> bool:
        """Hot-reload a skill at runtime."""
        if name not in self._skill_classes:
            return False
        try:
            cls = self._skill_classes[name]
            module = sys.modules[cls.__module__]
            importlib.reload(module)
            for n, obj in inspect.getmembers(module):
                if inspect.isclass(obj) and issubclass(obj, BaseSkill) and obj is not BaseSkill:
                    if obj.name == name:
                        new_instance = obj()
                        del self._skills[name]
                        self._register(new_instance)
                        return True
            return False
        except Exception as e:
            logger.error(f"Failed to reload skill {name}: {e}")
            return False
