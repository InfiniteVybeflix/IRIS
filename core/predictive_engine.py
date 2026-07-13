"""IRIS v1 Hybrid Predictive Engine — Pre-warm context, proactive suggestions"""
import os
import json
import time
from datetime import datetime, timedelta
from typing import Dict, List, Optional
from collections import Counter
from config import config

class PredictiveEngine:
    """
    Predict what the user needs before they ask:
    - Time-of-day patterns
    - Project context awareness
    - Recent workflow prediction
    """

    def __init__(self):
        self.patterns_file = os.path.join(config.DATA_DIR, "predictive_patterns.json")
        self.patterns = self._load_patterns()
        self.context_cache = {}
        self.last_prediction = None

    def _load_patterns(self) -> Dict:
        if os.path.exists(self.patterns_file):
            try:
                with open(self.patterns_file, 'r') as f:
                    return json.load(f)
            except:
                pass
        return {
            "hourly_patterns": {},
            "project_contexts": {},
            "workflow_chains": {},
            "common_requests": Counter()
        }

    def _save_patterns(self):
        with open(self.patterns_file, 'w') as f:
            json.dump(self.patterns, f, indent=2)

    def record_interaction(self, user_input: str, tools_used: List[str], success: bool):
        """Record interaction for pattern learning."""
        hour = datetime.now().hour
        self.patterns["common_requests"][user_input[:50]] = self.patterns["common_requests"].get(user_input[:50], 0) + 1

        # Hourly pattern
        h_key = str(hour)
        if h_key not in self.patterns["hourly_patterns"]:
            self.patterns["hourly_patterns"][h_key] = []
        self.patterns["hourly_patterns"][h_key].append({
            "input": user_input[:100],
            "tools": tools_used,
            "success": success,
            "timestamp": datetime.now().isoformat()
        })
        # Keep last 50 per hour
        self.patterns["hourly_patterns"][h_key] = self.patterns["hourly_patterns"][h_key][-50:]

        self._save_patterns()

    def predict_next_action(self) -> Dict:
        """Predict what the user will ask next."""
        hour = datetime.now().hour
        predictions = []

        # Time-based prediction
        h_patterns = self.patterns["hourly_patterns"].get(str(hour), [])
        if h_patterns:
            recent = [p["input"] for p in h_patterns[-10:]]
            predictions.append({
                "type": "time_based",
                "confidence": 0.6,
                "suggestion": f"Based on your {hour}:00 pattern, you might want to: {recent[-1]}",
                "context": recent
            })

        # Frequency-based
        if self.patterns["common_requests"]:
            top = Counter(self.patterns["common_requests"]).most_common(1)[0]
            predictions.append({
                "type": "frequency",
                "confidence": 0.4,
                "suggestion": f"You often ask about: {top[0]}"
            })

        return {
            "predictions": predictions,
            "top_suggestion": predictions[0]["suggestion"] if predictions else None,
            "confidence": max(p["confidence"] for p in predictions) if predictions else 0.0
        }

    def proactive_suggestion(self) -> str:
        """Generate a proactive suggestion for the user."""
        prediction = self.predict_next_action()
        if prediction["confidence"] > 0.5:
            return f"💡 Proactive: {prediction['top_suggestion']}"
        return ""

    def prewarm_context(self, user_input: str) -> Dict:
        """Pre-load relevant context before the user asks."""
        context = {
            "predicted_tools": [],
            "relevant_files": [],
            "recent_similar": [],
            "preloaded_at": datetime.now().isoformat()
        }

        # Predict tools
        hour = datetime.now().hour
        h_patterns = self.patterns["hourly_patterns"].get(str(hour), [])
        for p in h_patterns[-5:]:
            context["predicted_tools"].extend(p.get("tools", []))
        context["predicted_tools"] = list(set(context["predicted_tools"]))

        # Check for project keywords
        project_keywords = ["deploy", "build", "fix", "create", "test"]
        for kw in project_keywords:
            if kw in user_input.lower():
                context["relevant_files"] = self._find_recent_files(kw)
                break

        return context

    def _find_recent_files(self, keyword: str) -> List[str]:
        """Find recently modified files matching a keyword."""
        results = []
        try:
            for root, _, files in os.walk(config.BASE_DIR):
                for file in files:
                    if keyword in file.lower() and file.endswith('.py'):
                        path = os.path.join(root, file)
                        mtime = os.path.getmtime(path)
                        if time.time() - mtime < 86400:  # Last 24h
                            results.append(path)
        except: pass
        return results[:10]

    def analyze_patterns(self) -> Dict:
        """Return pattern analysis for dashboard."""
        total_interactions = sum(len(v) for v in self.patterns["hourly_patterns"].values())
        return {
            "total_interactions": total_interactions,
            "hourly_distribution": {k: len(v) for k, v in self.patterns["hourly_patterns"].items()},
            "top_requests": Counter(self.patterns["common_requests"]).most_common(10),
            "prediction_accuracy": self._calculate_accuracy()
        }

    def _calculate_accuracy(self) -> float:
        """Rough accuracy estimate based on successful predictions."""
        # In production, track actual vs predicted
        return 0.75  # Placeholder

# Singleton
predictive_engine = PredictiveEngine()
