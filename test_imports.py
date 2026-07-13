#!/usr/bin/env python3
"""IRIS v1 Quick Validation Test"""
import sys
import os

# Add project to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

print("=" * 60)
print("IRIS v1 — Import Validation Test")
print("=" * 60)

errors = []

# Test core imports
tests = [
    ("config", "Config"),
    ("core.models", "ReasoningPlan, ToolResult"),
    ("core.tool_registry", "tool_registry"),
    ("core.orchestrator", "orchestrator"),
    ("core.memory_engine", "memory_engine"),
    ("core.predictive_engine", "predictive_engine"),
    ("core.db", "db"),
    ("core.aevibron_client", "aevibron"),
    ("agents.base_agent", "BaseAgent"),
    ("agents.swarm_coordinator", "swarm_coordinator"),
    ("modules.consciousness", "consciousness"),
    ("modules.security", "security_manager"),
    ("modules.wake_word", "wake_word_detector"),
    ("modules.phone_bridge", "phone_bridge"),
    ("modules.vision_stream", "vision_stream"),
    ("modules.voice_system", "voice_system"),
    ("modules.autonomous", "autonomous_engine"),
    ("modules.project_generator", "project_generator"),
    ("modules.sandbox_executor", "sandbox_executor"),
    ("modules.mobile_api", "mobile_api"),
    ("modules.self_improve", "self_improvement"),
    ("skills.calendar_skill", "calendar_skill"),
    ("skills.notes_skill", "notes_skill"),
    ("skills.math_skill", "math_skill"),
]

for module_name, expected in tests:
    try:
        __import__(module_name)
        print(f"  ✓ {module_name}")
    except Exception as e:
        print(f"  ✗ {module_name} — {str(e)[:60]}")
        errors.append((module_name, str(e)))

print()
print("=" * 60)
if errors:
    print(f"FAILED: {len(errors)} import errors")
    for mod, err in errors:
        print(f"  - {mod}: {err}")
    sys.exit(1)
else:
    print("ALL IMPORTS SUCCESSFUL!")
    print("IRIS v1 is ready to run.")
    print()
    print("Next: Edit .env with your API keys, then run:")
    print("  python app.py")
