"""
IRIS v7.0 — Unit Test Stubs
Comprehensive test coverage for all memory and cortex modules.

Run with: python -m pytest tests/ -v
Or individually: python -m unittest tests.test_iris

Author: IRIS Core Team
"""

import json
import os
import tempfile
import unittest
from unittest.mock import MagicMock, patch

from iris_v7.iris_core import IRISCore
from iris_v7.memory import (
    AgentMemory,
    KnowledgeGraph,
    LearningEngine,
    MissionArchive,
    SemanticSearch,
    SkillMemory,
)
from iris_v7.cortex import (
    HypothesisTester,
    MetaLearner,
    Planner,
    ResourceOptimizer,
    RiskAssessor,
    Strategist,
)


class TestBaseMemory(unittest.TestCase):
    """Tests for BaseMemory abstract class and common functionality."""

    def setUp(self) -> None:
        self.temp_dir = tempfile.mkdtemp()
        self.db_path = os.path.join(self.temp_dir, "test_memory.db")

    def tearDown(self) -> None:
        import shutil
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_result_envelope_structure(self) -> None:
        """Verify standard result envelope has all required keys."""
        from iris_v7.memory.base_memory import BaseMemory
        # BaseMemory is abstract, test via AgentMemory
        am = AgentMemory(db_path=self.db_path)
        result = am._result(True, "test", {"key": "value"}, confidence=0.9, duration_ms=100)
        self.assertIn("success", result)
        self.assertIn("module", result)
        self.assertIn("action", result)
        self.assertIn("data", result)
        self.assertIn("confidence", result)
        self.assertIn("errors", result)
        self.assertIn("duration_ms", result)
        self.assertIn("timestamp", result)
        am.close()

    def test_sqlite_fallback_to_json(self) -> None:
        """Verify JSON fallback works when SQLite is unavailable."""
        # Create with invalid path to trigger fallback
        am = AgentMemory(db_path="/invalid/path/test.db")
        result = am.record_mission("TestAgent", "m-001", [], {"success": True}, 1000)
        self.assertTrue(result["success"])
        am.close()


class TestAgentMemory(unittest.TestCase):
    """Tests for AgentMemory module."""

    def setUp(self) -> None:
        self.temp_dir = tempfile.mkdtemp()
        self.db_path = os.path.join(self.temp_dir, "test_agent.db")
        self.am = AgentMemory(db_path=self.db_path)

    def tearDown(self) -> None:
        self.am.close()
        import shutil
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_record_mission(self) -> None:
        """Test recording a mission."""
        result = self.am.record_mission(
            "Alpha", "m-001",
            [{"type": "recon", "description": "scan"}],
            {"success": True, "errors": []},
            5000,
        )
        self.assertTrue(result["success"])
        self.assertEqual(result["data"]["mission_id"], "m-001")

    def test_get_agent_history(self) -> None:
        """Test retrieving agent history."""
        self.am.record_mission("Alpha", "m-001", [], {"success": True}, 1000)
        self.am.record_mission("Alpha", "m-002", [], {"success": False}, 2000)
        result = self.am.get_agent_history("Alpha", limit=10)
        self.assertTrue(result["success"])
        self.assertEqual(len(result["data"]), 2)

    def test_get_agent_performance(self) -> None:
        """Test performance metrics calculation."""
        self.am.record_mission("Alpha", "m-001", [], {"success": True}, 1000)
        self.am.record_mission("Alpha", "m-002", [], {"success": True}, 2000)
        self.am.record_mission("Alpha", "m-003", [], {"success": False}, 3000)
        result = self.am.get_agent_performance("Alpha")
        self.assertTrue(result["success"])
        self.assertAlmostEqual(result["data"]["success_rate"], 0.6667, places=3)

    def test_compare_agents(self) -> None:
        """Test agent comparison for task type."""
        self.am.record_mission("Alpha", "m-001", [{"type": "recon"}], {"success": True}, 1000)
        self.am.record_mission("Beta", "m-002", [{"type": "recon"}], {"success": False}, 2000)
        result = self.am.compare_agents("recon")
        self.assertTrue(result["success"])
        self.assertEqual(result["data"][0]["agent_name"], "Alpha")

    def test_suggest_agent(self) -> None:
        """Test agent suggestion."""
        self.am.record_mission("Alpha", "m-001", [{"type": "recon"}], {"success": True}, 1000)
        result = self.am.suggest_agent("recon")
        self.assertTrue(result["success"])
        self.assertEqual(result["data"], "Alpha")


class TestKnowledgeGraph(unittest.TestCase):
    """Tests for KnowledgeGraph module."""

    def setUp(self) -> None:
        self.temp_dir = tempfile.mkdtemp()
        self.db_path = os.path.join(self.temp_dir, "test_kg.db")
        self.kg = KnowledgeGraph(db_path=self.db_path)

    def tearDown(self) -> None:
        self.kg.close()
        import shutil
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_add_fact(self) -> None:
        """Test adding a fact."""
        result = self.kg.add_fact("IRIS", "is_a", "AI", confidence=1.0, source="test")
        self.assertTrue(result["success"])
        self.assertIn("fact_id", result["data"])

    def test_query(self) -> None:
        """Test querying facts."""
        self.kg.add_fact("IRIS", "is_a", "AI")
        self.kg.add_fact("IRIS", "has", "memory")
        result = self.kg.query(subject="IRIS")
        self.assertTrue(result["success"])
        self.assertEqual(len(result["data"]), 2)

    def test_find_path(self) -> None:
        """Test path finding between entities."""
        self.kg.add_fact("A", "leads_to", "B")
        self.kg.add_fact("B", "leads_to", "C")
        result = self.kg.find_path("A", "C")
        self.assertTrue(result["success"])
        self.assertTrue(len(result["data"]) > 0)

    def test_infer(self) -> None:
        """Test transitive inference."""
        self.kg.add_fact("A", "connected", "B")
        self.kg.add_fact("B", "connected", "C")
        result = self.kg.infer("A", "connected")
        self.assertTrue(result["success"])
        # Should infer A -> C
        inferred = [f for f in result["data"] if f.get("object") == "C"]
        self.assertTrue(len(inferred) > 0)

    def test_visualize(self) -> None:
        """Test graph visualization export."""
        self.kg.add_fact("A", "link", "B")
        dot = self.kg.visualize(format="dot")
        self.assertIn("digraph", dot)
        mermaid = self.kg.visualize(format="mermaid")
        self.assertIn("graph TD", mermaid)

    def test_export_turtle(self) -> None:
        """Test RDF/Turtle export."""
        self.kg.add_fact("IRIS", "is_a", "AI")
        turtle = self.kg.export_turtle()
        self.assertIn("@prefix", turtle)


class TestSkillMemory(unittest.TestCase):
    """Tests for SkillMemory module."""

    def setUp(self) -> None:
        self.temp_dir = tempfile.mkdtemp()
        self.db_path = os.path.join(self.temp_dir, "test_skill.db")
        self.sm = SkillMemory(db_path=self.db_path)

    def tearDown(self) -> None:
        self.sm.close()
        import shutil
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_record_technique(self) -> None:
        """Test recording technique usage."""
        result = self.sm.record_technique("Alpha", "port_scan", "recon", True, 1000, {"target": "192.168.1.1"})
        self.assertTrue(result["success"])

    def test_get_best_technique(self) -> None:
        """Test finding best technique."""
        self.sm.record_technique("Alpha", "port_scan", "recon", True, 1000)
        self.sm.record_technique("Beta", "osint", "recon", True, 2000)
        self.sm.record_technique("Alpha", "port_scan", "recon", False, 500)
        result = self.sm.get_best_technique("recon")
        self.assertTrue(result["success"])
        self.assertIn("technique", result["data"])

    def test_get_emerging_techniques(self) -> None:
        """Test emerging technique detection."""
        self.sm.record_technique("Alpha", "new_tech", "recon", True, 1000)
        self.sm.record_technique("Alpha", "new_tech", "recon", True, 1000)
        self.sm.record_technique("Alpha", "new_tech", "recon", True, 1000)
        result = self.sm.get_emerging_techniques()
        self.assertTrue(result["success"])
        self.assertTrue(len(result["data"]) > 0)


class TestMissionArchive(unittest.TestCase):
    """Tests for MissionArchive module."""

    def setUp(self) -> None:
        self.temp_dir = tempfile.mkdtemp()
        self.db_path = os.path.join(self.temp_dir, "test_mission.db")
        self.ma = MissionArchive(db_path=self.db_path)

    def tearDown(self) -> None:
        self.ma.close()
        import shutil
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_archive_mission(self) -> None:
        """Test archiving a mission."""
        mission = {
            "id": "m-001",
            "agent_name": "Alpha",
            "tasks": [{"type": "scan"}],
            "outcomes": {"success": True},
        }
        result = self.ma.archive_mission(mission)
        self.assertTrue(result["success"])

    def test_search_missions(self) -> None:
        """Test mission search with filters."""
        self.ma.archive_mission({
            "id": "m-001", "agent_name": "Alpha",
            "mission_type": "recon", "description": "network scan",
            "tasks": [], "outcomes": {"success": True},
        })
        result = self.ma.search_missions("scan", filters={"mission_type": "recon"})
        self.assertTrue(result["success"])
        self.assertEqual(len(result["data"]), 1)

    def test_extract_lessons(self) -> None:
        """Test lesson extraction."""
        self.ma.archive_mission({
            "id": "m-001", "agent_name": "Alpha",
            "tasks": [{"type": "scan", "success": True}],
            "outcomes": {"success": True, "errors": [], "warnings": ["slow"]},
        })
        result = self.ma.extract_lessons("m-001")
        self.assertTrue(result["success"])
        self.assertTrue(len(result["data"]) > 0)


class TestSemanticSearch(unittest.TestCase):
    """Tests for SemanticSearch module."""

    def setUp(self) -> None:
        self.temp_dir = tempfile.mkdtemp()
        self.db_path = os.path.join(self.temp_dir, "test_semantic.db")
        self.ss = SemanticSearch(db_path=self.db_path)

    def tearDown(self) -> None:
        self.ss.close()
        import shutil
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_index_and_search(self) -> None:
        """Test document indexing and search."""
        self.ss.index_document("doc-1", "IRIS is an AI system", {"type": "desc"})
        self.ss.index_document("doc-2", "Machine learning processes data")
        result = self.ss.search("artificial intelligence", top_k=2)
        self.assertTrue(result["success"])
        self.assertTrue(len(result["data"]) > 0)

    def test_hybrid_search(self) -> None:
        """Test hybrid semantic + keyword search."""
        self.ss.index_document("doc-1", "IRIS reasoning engine")
        self.ss.index_document("doc-2", "Database storage system")
        result = self.ss.hybrid_search("reasoning AI", top_k=2)
        self.assertTrue(result["success"])
        self.assertTrue(len(result["data"]) > 0)
        self.assertIn("blended_score", result["data"][0])

    def test_get_similar(self) -> None:
        """Test finding similar documents."""
        self.ss.index_document("doc-1", "AI system with memory")
        self.ss.index_document("doc-2", "Machine learning model")
        self.ss.index_document("doc-3", "Neural network architecture")
        result = self.ss.get_similar("doc-1", top_k=2)
        self.assertTrue(result["success"])


class TestLearningEngine(unittest.TestCase):
    """Tests for LearningEngine module."""

    def setUp(self) -> None:
        self.temp_dir = tempfile.mkdtemp()
        self.db_path = os.path.join(self.temp_dir, "test_learning.db")
        self.le = LearningEngine(db_path=self.db_path)

    def tearDown(self) -> None:
        self.le.close()
        import shutil
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_update_beliefs(self) -> None:
        """Test Bayesian belief updating."""
        result = self.le.update_beliefs({"belief_A": 0.8, "belief_B": 0.3})
        self.assertTrue(result["success"])
        self.assertEqual(len(result["data"]), 2)

    def test_belief_persistence(self) -> None:
        """Test beliefs persist across updates."""
        self.le.update_beliefs({"test_belief": 0.7})
        self.le.update_beliefs({"test_belief": 0.9})
        result = self.le.retrieve("test_belief")
        self.assertTrue(result["success"])
        # After two updates: (0.5*0 + 0.7)/1 = 0.7, then (0.7*1 + 0.9)/2 = 0.8
        self.assertAlmostEqual(result["data"]["probability"], 0.8, places=2)


class TestPlanner(unittest.TestCase):
    """Tests for Planner module."""

    def setUp(self) -> None:
        self.temp_dir = tempfile.mkdtemp()
        self.db_path = os.path.join(self.temp_dir, "test_planner.db")
        self.planner = Planner(db_path=self.db_path)

    def tearDown(self) -> None:
        self.planner.close()
        import shutil
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_decompose(self) -> None:
        """Test goal decomposition."""
        result = self.planner.decompose("Secure website")
        self.assertTrue(result["success"])
        self.assertTrue(len(result["data"]) > 0)

    def test_create_plan(self) -> None:
        """Test complete plan creation."""
        result = self.planner.create_plan("Scan network", context={"target": "192.168.1.0/24"})
        self.assertTrue(result["success"])
        self.assertIn("plan_id", result["data"])
        self.assertIn("tasks", result["data"])

    def test_validate_plan(self) -> None:
        """Test plan validation."""
        plan = self.planner.create_plan("Test plan")["data"]
        result = self.planner.validate_plan(plan)
        self.assertTrue(result["success"])
        # Valid plans should have no critical issues
        critical = [i for i in result["data"] if i.get("severity") == "critical"]
        self.assertEqual(len(critical), 0)

    def test_optimize_plan(self) -> None:
        """Test plan optimization."""
        plan = self.planner.create_plan("Secure website")["data"]
        result = self.planner.optimize_plan(plan, metric="time")
        self.assertTrue(result["success"])
        self.assertEqual(result["data"]["optimized_for"], "time")


class TestStrategist(unittest.TestCase):
    """Tests for Strategist module."""

    def setUp(self) -> None:
        self.temp_dir = tempfile.mkdtemp()
        self.db_path = os.path.join(self.temp_dir, "test_strategist.db")
        self.strategist = Strategist(db_path=self.db_path)

    def tearDown(self) -> None:
        self.strategist.close()
        import shutil
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_select_approach(self) -> None:
        """Test approach selection."""
        task = {"type": "reconnaissance", "complexity": 5}
        result = self.strategist.select_approach(task, ["Alpha", "Beta-Recon"])
        self.assertTrue(result["success"])
        self.assertIn("recommended_agent", result["data"])

    def test_evaluate_speed_vs_thoroughness(self) -> None:
        """Test speed vs thoroughness trade-off."""
        task = {"complexity": 8, "time_sensitive": False, "criticality": 9}
        result = self.strategist.evaluate_speed_vs_thoroughness(task)
        self.assertTrue(result["success"])
        self.assertIn("recommendation", result["data"])

    def test_adapt_strategy(self) -> None:
        """Test mid-mission strategy adaptation."""
        mid = {"strategy": "balanced", "current_tasks": []}
        intel = {"detection_alert": True}
        result = self.strategist.adapt_strategy(mid, intel)
        self.assertTrue(result["success"])
        self.assertEqual(result["data"]["new_strategy"], "stealth")


class TestRiskAssessor(unittest.TestCase):
    """Tests for RiskAssessor module."""

    def setUp(self) -> None:
        self.temp_dir = tempfile.mkdtemp()
        self.db_path = os.path.join(self.temp_dir, "test_risk.db")
        self.ra = RiskAssessor(db_path=self.db_path)

    def tearDown(self) -> None:
        self.ra.close()
        import shutil
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_assess_action(self) -> None:
        """Test action risk assessment."""
        result = self.ra.assess_action("port_scan", "192.168.1.1", {"stealth": True})
        self.assertTrue(result["success"])
        self.assertIn("risk_score", result["data"])
        self.assertIn("mitigations", result["data"])

    def test_assess_legal_compliance(self) -> None:
        """Test legal risk assessment."""
        result = self.ra.assess_legal_compliance("port_scan", "US")
        self.assertTrue(result["success"])
        self.assertIn("legal_risk_score", result["data"])

    def test_require_approval(self) -> None:
        """Test approval threshold."""
        self.assertTrue(self.ra.require_approval(0.8))
        self.assertFalse(self.ra.require_approval(0.5))


class TestResourceOptimizer(unittest.TestCase):
    """Tests for ResourceOptimizer module."""

    def setUp(self) -> None:
        self.temp_dir = tempfile.mkdtemp()
        self.db_path = os.path.join(self.temp_dir, "test_resource.db")
        self.ro = ResourceOptimizer(db_path=self.db_path)

    def tearDown(self) -> None:
        self.ro.close()
        import shutil
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_estimate_cost(self) -> None:
        """Test cost estimation."""
        plan = {"tasks": [{"type": "recon", "estimated_ms": 300000}, {"type": "scan", "estimated_ms": 600000}]}
        result = self.ro.estimate_cost(plan)
        self.assertTrue(result["success"])
        self.assertIn("api_tokens", result["data"])

    def test_load_balance(self) -> None:
        """Test task distribution across agents."""
        tasks = [
            {"id": "t1", "estimated_ms": 300000},
            {"id": "t2", "estimated_ms": 600000},
            {"id": "t3", "estimated_ms": 200000},
        ]
        result = self.ro.load_balance(["Alpha", "Beta"], tasks)
        self.assertTrue(result["success"])
        self.assertIn("assignments", result["data"])


class TestHypothesisTester(unittest.TestCase):
    """Tests for HypothesisTester module."""

    def setUp(self) -> None:
        self.temp_dir = tempfile.mkdtemp()
        self.db_path = os.path.join(self.temp_dir, "test_hypothesis.db")
        self.ht = HypothesisTester(db_path=self.db_path)

    def tearDown(self) -> None:
        self.ht.close()
        import shutil
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_generate_hypotheses(self) -> None:
        """Test hypothesis generation."""
        obs = {"type": "anomaly", "value": "unusual_traffic"}
        result = self.ht.generate_hypotheses(obs)
        self.assertTrue(result["success"])
        self.assertTrue(len(result["data"]) >= 3)

    def test_simulate_outcome(self) -> None:
        """Test action outcome simulation."""
        result = self.ht.simulate_outcome("block_ip", {"status": "under_attack", "threat_level": 0.8})
        self.assertTrue(result["success"])
        self.assertIn("success_probability", result["data"])

    def test_falsify_hypothesis(self) -> None:
        """Test falsification conditions."""
        hyp = {"description": "System under attack"}
        result = self.ht.falsify_hypothesis(hyp)
        self.assertTrue(result["success"])
        self.assertTrue(len(result["data"]["falsification_conditions"]) > 0)


class TestMetaLearner(unittest.TestCase):
    """Tests for MetaLearner module."""

    def setUp(self) -> None:
        self.temp_dir = tempfile.mkdtemp()
        self.db_path = os.path.join(self.temp_dir, "test_meta.db")
        self.ml = MetaLearner(db_path=self.db_path)

    def tearDown(self) -> None:
        self.ml.close()
        import shutil
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_record_outcome(self) -> None:
        """Test outcome recording."""
        plan = {"plan_id": "p-001", "predicted_success": {"success_probability": 0.9}}
        actual = {"success": True, "duration_ms": 5000}
        result = self.ml.record_outcome(plan, actual)
        self.assertTrue(result["success"])

    def test_track_prediction_accuracy(self) -> None:
        """Test accuracy tracking with no data."""
        result = self.ml.track_prediction_accuracy()
        self.assertTrue(result["success"])
        self.assertEqual(result["data"]["total_predictions"], 0)

    def test_update_models_insufficient_data(self) -> None:
        """Test model update with insufficient data."""
        result = self.ml.update_models()
        self.assertTrue(result["success"])
        self.assertEqual(result["data"]["status"], "skipped")


class TestIRISCore(unittest.TestCase):
    """Integration tests for IRISCore."""

    def setUp(self) -> None:
        self.temp_dir = tempfile.mkdtemp()
        self.config = {
            "IRIS_MEMORY_DB": os.path.join(self.temp_dir, "iris_memory.db"),
            "IRIS_AGENT_MEMORY_DB": os.path.join(self.temp_dir, "iris_agent.db"),
            "IRIS_KG_DB": os.path.join(self.temp_dir, "iris_kg.db"),
            "IRIS_SKILL_MEMORY_DB": os.path.join(self.temp_dir, "iris_skill.db"),
            "IRIS_MISSION_ARCHIVE_DB": os.path.join(self.temp_dir, "iris_mission.db"),
            "IRIS_SEMANTIC_DB": os.path.join(self.temp_dir, "iris_semantic.db"),
            "IRIS_LEARNING_DB": os.path.join(self.temp_dir, "iris_learning.db"),
            "IRIS_CORTEX_DB": os.path.join(self.temp_dir, "iris_cortex.db"),
            "IRIS_PLANNER_DB": os.path.join(self.temp_dir, "iris_planner.db"),
            "IRIS_STRATEGIST_DB": os.path.join(self.temp_dir, "iris_strategist.db"),
            "IRIS_RISK_DB": os.path.join(self.temp_dir, "iris_risk.db"),
            "IRIS_RESOURCE_DB": os.path.join(self.temp_dir, "iris_resource.db"),
            "IRIS_HYPOTHESIS_DB": os.path.join(self.temp_dir, "iris_hypothesis.db"),
            "IRIS_META_LEARNER_DB": os.path.join(self.temp_dir, "iris_meta.db"),
        }
        for k, v in self.config.items():
            os.environ[k] = v
        self.iris = IRISCore()

    def tearDown(self) -> None:
        self.iris.shutdown()
        import shutil
        shutil.rmtree(self.temp_dir, ignore_errors=True)
        for k in self.config.keys():
            os.environ.pop(k, None)

    def test_boot(self) -> None:
        """Test IRIS boot sequence."""
        result = self.iris.boot()
        self.assertIn(result["status"], ["online", "degraded"])
        self.assertIn("modules", result)

    def test_health_check(self) -> None:
        """Test health check across all modules."""
        health = self.iris.health_check()
        self.assertIn("overall", health)
        self.assertIn("modules", health)

    def test_add_and_query_knowledge(self) -> None:
        """Test knowledge graph operations through core."""
        self.iris.add_knowledge("IRIS", "is_a", "AI_system", 1.0)
        result = self.iris.query_knowledge(subject="IRIS")
        self.assertTrue(result["success"])
        self.assertTrue(len(result["data"]) > 0)

    def test_execute_mission(self) -> None:
        """Test full mission execution."""
        result = self.iris.execute_mission("Scan network", agent_name="TestAgent")
        self.assertIn("mission_id", result)
        self.assertIn("status", result)

    def test_findings_system(self) -> None:
        """Test finding aggregation."""
        self.iris.receive_finding({"action": "test", "data": "value"})
        findings = self.iris.get_findings()
        self.assertEqual(len(findings), 1)
        self.iris.clear_findings()
        self.assertEqual(len(self.iris.get_findings()), 0)


if __name__ == "__main__":
    unittest.main()
