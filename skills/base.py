"""Base skill — every skill inherits from this."""
import os
import json
import time
import logging
from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional, Callable
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

from skills.contracts.skill_result import SkillResult
from skills.contracts.skill_request import SkillRequest
from skills.contracts.permissions import SkillPermissions, PermissionLevel
from skills.contracts.capability_tags import CapabilityTags

logger = logging.getLogger(__name__)


@dataclass
class SkillCapability:
    """One thing a skill can do."""
    name: str
    description: str
    input_schema: Dict[str, Any] = field(default_factory=dict)
    output_schema: Dict[str, Any] = field(default_factory=dict)
    examples: List[Dict[str, Any]] = field(default_factory=list)
    requires_confirmation: bool = False
    supports_background: bool = False
    is_async: bool = False
    tags: List[CapabilityTags] = field(default_factory=list)


class BaseSkill(ABC):
    """
    Every skill in IRIS must inherit from BaseSkill.
    Auto-discovery works because of this contract.
    """

    # === Metadata (override in subclass) ===
    name: str = "base"
    display_name: str = "Base Skill"
    description: str = "Base skill — do not use directly."
    version: str = "1.0.0"
    author: str = "IRIS"
    category: str = "orchestration"
    icon: str = "🔧"

    # === Capabilities (override in subclass) ===
    capabilities: List[SkillCapability] = []

    # === Permissions (override in subclass) ===
    permissions: SkillPermissions = field(default_factory=SkillPermissions)

    # === Persistence ===
    uses_storage: bool = False
    storage_dir: Optional[str] = None
    storage_file: Optional[str] = None

    # === Background ===
    supports_background: bool = False
    background_interval_seconds: int = 60

    # === Dependencies ===
    required_packages: List[str] = field(default_factory=list)
    required_env_vars: List[str] = field(default_factory=list)
    optional_integrations: List[str] = field(default_factory=list)

    # === State ===
    _initialized: bool = False
    _storage_cache: Dict[str, Any] = field(default_factory=dict)

    def __init__(self):
        self._initialized = False
        self._storage_cache = {}
        self._ensure_storage()
        self._initialized = True
        logger.info(f"Skill '{self.name}' initialized")

    def _ensure_storage(self):
        """Create storage directory/file if needed."""
        if self.uses_storage and self.storage_dir:
            os.makedirs(self.storage_dir, exist_ok=True)
        if self.uses_storage and self.storage_file:
            os.makedirs(os.path.dirname(self.storage_file), exist_ok=True)
            if not os.path.exists(self.storage_file):
                self._write_storage({})

    # === Core contract ===
    @abstractmethod
    def execute(self, request: SkillRequest) -> SkillResult:
        """Main entry point. Every skill implements this."""
        raise NotImplementedError

    def can_handle(self, request: SkillRequest) -> float:
        """
        Return confidence 0.0-1.0 that this skill should handle the request.
        Override for smarter routing.
        """
        intent_lower = request.intent.lower()
        for cap in self.capabilities:
            if cap.name.lower() in intent_lower or cap.name.lower().replace("_", " ") in intent_lower:
                return 0.8
        if self.name.lower() in intent_lower:
            return 0.7
        return 0.0

    def get_metadata(self) -> Dict[str, Any]:
        """Full skill metadata for discovery."""
        return {
            "name": self.name,
            "display_name": self.display_name,
            "description": self.description,
            "version": self.version,
            "author": self.author,
            "category": self.category,
            "icon": self.icon,
            "capabilities": [
                {
                    "name": c.name,
                    "description": c.description,
                    "requires_confirmation": c.requires_confirmation,
                    "supports_background": c.supports_background,
                    "is_async": c.is_async,
                    "tags": [t.value for t in c.tags],
                }
                for c in self.capabilities
            ],
            "permissions": {
                "level": self.permissions.level.value,
                "requires_auth": self.permissions.requires_auth,
                "rate_limit_per_minute": self.permissions.rate_limit_per_minute,
            },
            "uses_storage": self.uses_storage,
            "supports_background": self.supports_background,
            "background_interval_seconds": self.background_interval_seconds,
            "required_packages": self.required_packages,
            "required_env_vars": self.required_env_vars,
            "initialized": self._initialized,
        }

    # === Storage helpers ===
    def _read_storage(self) -> Dict[str, Any]:
        if not self.storage_file or not os.path.exists(self.storage_file):
            return {}
        try:
            with open(self.storage_file, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            logger.error(f"[{self.name}] Storage read error: {e}")
            return {}

    def _write_storage(self, data: Dict[str, Any]):
        if not self.storage_file:
            return
        try:
            with open(self.storage_file, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2, default=str)
        except Exception as e:
            logger.error(f"[{self.name}] Storage write error: {e}")

    def _get_storage(self, key: str, default: Any = None) -> Any:
        data = self._read_storage()
        return data.get(key, default)

    def _set_storage(self, key: str, value: Any):
        data = self._read_storage()
        data[key] = value
        self._write_storage(data)

    def _delete_storage(self, key: str):
        data = self._read_storage()
        if key in data:
            del data[key]
            self._write_storage(data)

    # === Background task hook ===
    def background_tick(self) -> List[SkillResult]:
        """
        Called periodically if supports_background=True.
        Return any notifications/actions to take.
        """
        return []

    # === Utility ===
    def _timed_execute(self, fn: Callable, *args, **kwargs) -> SkillResult:
        start = time.time()
        try:
            result = fn(*args, **kwargs)
            if isinstance(result, SkillResult):
                result.duration_ms = (time.time() - start) * 1000
                result.skill_name = self.name
                return result
            return SkillResult.ok(data=result, duration_ms=(time.time() - start) * 1000, skill_name=self.name)
        except Exception as e:
            logger.exception(f"[{self.name}] Execution error")
            return SkillResult.fail(str(e), duration_ms=(time.time() - start) * 1000, skill_name=self.name)

    def __repr__(self):
        return f"<{self.__class__.__name__} name={self.name} caps={len(self.capabilities)}>"
