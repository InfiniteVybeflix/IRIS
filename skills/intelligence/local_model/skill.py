"""Local Model Skill — Local LLM inference, embeddings, classification."""

import os
import logging
import subprocess
from typing import Dict, Any
from skills import BaseSkill

logger = logging.getLogger(__name__)


class LocalModelSkill(BaseSkill):
    """Local LLM inference via llama.cpp, ollama, or similar local backends."""

    def __init__(self):
        super().__init__(
            name="local_model",
            category="intelligence",
            capabilities=["local_model"]
        )
        self._ollama_host = os.environ.get("OLLAMA_HOST", "http://localhost:11434")

    def execute(self, capability: str, params: Dict[str, Any]) -> Dict[str, Any]:
        method = params.get("method", "generate")
        if method == "generate":
            return self.generate(params)
        elif method == "embed":
            return self.embed(params)
        elif method == "classify":
            return self.classify(params)
        return {"error": f"Unknown method: {method}"}

    def generate(self, params: Dict[str, Any]) -> Dict[str, Any]:
        prompt = params.get("prompt", "")
        model = params.get("model", "llama3.2")
        max_tokens = params.get("max_tokens", 512)
        temperature = params.get("temperature", 0.7)
        if not prompt:
            return {"success": False, "error": "No prompt provided"}
        # Try Ollama first
        try:
            import urllib.request
            import json
            req_data = json.dumps({"model": model, "prompt": prompt, "stream": False, "options": {"num_predict": max_tokens, "temperature": temperature}}).encode()
            req = urllib.request.Request(f"{self._ollama_host}/api/generate", data=req_data, headers={"Content-Type": "application/json"}, method="POST")
            with urllib.request.urlopen(req, timeout=120) as resp:
                data = json.loads(resp.read().decode())
            return {"success": True, "output": data.get("response", ""), "model": model, "done": data.get("done", False), "backend": "ollama"}
        except Exception as e:
            logger.warning(f"Ollama failed: {e}")
        # Fallback: llama.cpp server
        try:
            import urllib.request
            import json
            req_data = json.dumps({"prompt": prompt, "n_predict": max_tokens, "temperature": temperature}).encode()
            req = urllib.request.Request("http://localhost:8080/completion", data=req_data, headers={"Content-Type": "application/json"}, method="POST")
            with urllib.request.urlopen(req, timeout=120) as resp:
                data = json.loads(resp.read().decode())
            return {"success": True, "output": data.get("content", ""), "model": model, "backend": "llama.cpp"}
        except Exception as e2:
            logger.warning(f"llama.cpp failed: {e2}")
        return {"success": False, "error": f"No local LLM backend available. Tried Ollama ({self._ollama_host}) and llama.cpp (localhost:8080). Install ollama or start llama.cpp server.", "prompt": prompt[:100], "model": model}

    def embed(self, params: Dict[str, Any]) -> Dict[str, Any]:
        text = params.get("text", "")
        model = params.get("model", "nomic-embed-text")
        if not text:
            return {"success": False, "error": "No text provided"}
        try:
            import urllib.request
            import json
            req_data = json.dumps({"model": model, "prompt": text}).encode()
            req = urllib.request.Request(f"{self._ollama_host}/api/embeddings", data=req_data, headers={"Content-Type": "application/json"}, method="POST")
            with urllib.request.urlopen(req, timeout=60) as resp:
                data = json.loads(resp.read().decode())
            return {"success": True, "embedding": data.get("embedding", []), "dimensions": len(data.get("embedding", [])), "model": model, "backend": "ollama"}
        except Exception as e:
            logger.error(f"Embedding failed: {e}")
            return {"success": False, "error": str(e), "model": model}

    def classify(self, params: Dict[str, Any]) -> Dict[str, Any]:
        text = params.get("text", "")
        labels = params.get("labels", [])
        if not text or not labels:
            return {"success": False, "error": "Provide text and labels"}
        # Use local LLM for zero-shot classification
        prompt = f"Classify the following text into exactly one of these categories: {', '.join(labels)}.\n\nText: {text}\n\nCategory:"
        result = self.generate({"prompt": prompt, "model": params.get("model", "llama3.2"), "max_tokens": 32, "temperature": 0.1})
        if result.get("success"):
            predicted = result["output"].strip().split("\n")[0].strip()
            # Match to closest label
            best_label = labels[0]
            best_score = 0
            for label in labels:
                if label.lower() in predicted.lower():
                    if len(label) > best_score:
                        best_score = len(label)
                        best_label = label
            return {"success": True, "text": text, "predicted": best_label, "raw_output": predicted, "labels": labels}
        return {"success": False, "error": result.get("error", "Classification failed")}
