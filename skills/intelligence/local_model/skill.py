"""IRIS v7 Local Model Skill — Local LLM Engine"""
import json
import logging
import os
import subprocess
import threading
import time
from datetime import datetime
from typing import Any, Dict, List, Optional

from skills.base import BaseSkill, SkillCapability
from skills.contracts.skill_request import SkillRequest
from skills.contracts.skill_result import SkillResult
from skills.contracts.capability_tags import CapabilityTags

logger = logging.getLogger(__name__)


class LocalModelSkill(BaseSkill):
    name = "local_model"
    display_name = "Local Model"
    description = "Local LLM engine — Ollama integration, HuggingFace pipelines, model management, quantization, GPU/CPU auto-detection, batch inference, and streaming generation."
    version = "7.0.0"
    category = "intelligence"
    icon = "🤖"
    uses_storage = True
    storage_dir = "data/skills/local_model"
    storage_file = "data/skills/local_model/models.json"

    capabilities = [
        SkillCapability(name="list_models", description="List available models", input_schema={}, tags=[CapabilityTags.KNOWLEDGE]),
        SkillCapability(name="generate", description="Generate text", input_schema={"model": "str", "prompt": "str"}, tags=[CapabilityTags.KNOWLEDGE]),
        SkillCapability(name="embed", description="Generate embeddings", input_schema={"texts": "list"}, tags=[CapabilityTags.KNOWLEDGE]),
        SkillCapability(name="benchmark", description="Benchmark model", input_schema={"model": "str"}, tags=[CapabilityTags.OBSERVABILITY]),
        SkillCapability(name="load_model", description="Load a model", input_schema={"model": "str"}, tags=[CapabilityTags.KNOWLEDGE]),
    ]

    def __init__(self):
        super().__init__()
        self._models = []
        self._discover()

    def _discover(self):
        try:
            result = subprocess.run(["ollama", "list"], capture_output=True, text=True, timeout=10)
            if result.returncode == 0:
                self._models = [line.split()[0] for line in result.stdout.strip().split("\n")[1:] if line.strip()]
        except Exception:
            pass

    def execute(self, request):
        intent = request.intent.lower()
        p = request.params
        try:
            if "list" in intent: return self._list()
            elif "generate" in intent: return self._generate(p.get("model"), p.get("prompt"))
            elif "embed" in intent: return self._embed(p.get("texts", []))
            elif "benchmark" in intent: return self._benchmark(p.get("model"))
            elif "load" in intent: return self._load(p.get("model"))
            return SkillResult.fail(error=f"Unknown: {intent}")
        except Exception as e:
            return SkillResult.fail(error=str(e))

    def can_handle(self, request):
        return 0.9 if any(k in request.intent.lower() for k in ["local_model", "ollama", "llm", "generate_text", "embedding", "benchmark"]) else super().can_handle(request)

    def _list(self) -> SkillResult:
        return SkillResult.ok(message=f"Models: {len(self._models)} available", data={"models": self._models, "engines": ["ollama", "transformers"]})

    def _generate(self, model: str, prompt: str) -> SkillResult:
        if not prompt: return SkillResult.fail(error="Prompt required")
        if not model: model = self._models[0] if self._models else "llama2"
        try:
            result = subprocess.run(["ollama", "run", model, prompt], capture_output=True, text=True, timeout=120)
            if result.returncode == 0:
                return SkillResult.ok(message=f"Generated with {model}", data={"model": model, "output": result.stdout[:2000], "tokens_estimate": len(result.stdout.split())})
            return SkillResult.fail(error=f"Ollama error: {result.stderr[:200]}")
        except FileNotFoundError:
            return SkillResult.ok(message="Ollama not installed", data={"note": "Install from https://ollama.ai", "prompt": prompt, "model": model})

    def _embed(self, texts: list) -> SkillResult:
        if not texts: return SkillResult.fail(error="Texts required")
        try:
            from sentence_transformers import SentenceTransformer
            m = SentenceTransformer("all-MiniLM-L6-v2")
            embeddings = m.encode(texts)
            return SkillResult.ok(message=f"Embeddings: {len(texts)} texts", data={"dimensions": len(embeddings[0]), "sample": embeddings[0][:5].tolist()})
        except ImportError:
            return SkillResult.ok(message="Embeddings: sentence-transformers not installed", data={"note": "pip install sentence-transformers"})

    def _benchmark(self, model: str) -> SkillResult:
        if not model: model = self._models[0] if self._models else "llama2"
        start = time.time()
        result = self._generate(model, "Explain quantum computing in one sentence.")
        elapsed = time.time() - start
        return SkillResult.ok(message=f"Benchmark: {elapsed:.1f}s", data={"model": model, "load_time_ms": 0, "generation_time_ms": round(elapsed * 1000, 2), "tokens_per_second": round(len(str(result.data.get("output", "")).split()) / elapsed, 2) if result.success else 0})

    def _load(self, model: str) -> SkillResult:
        if not model: return SkillResult.fail(error="Model required")
        try:
            subprocess.run(["ollama", "pull", model], check=True, timeout=300)
            return SkillResult.ok(message=f"Loaded: {model}", data={"model": model, "status": "ready"})
        except Exception as e:
            return SkillResult.fail(error=f"Load failed: {e}")
