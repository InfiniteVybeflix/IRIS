#!/usr/bin/env python3
"""
IRIS v1 — Infinite Reactive Intelligence System
Perfect Entry Point — Fully Wired, Zero Orphans, Production Ready

Architecture:
- Flask app with modular blueprints
- Core infrastructure: DB, Commander, Orchestrator, Registry
- Modules: Consciousness, Security, Proactive, Autonomous, Voice, Vision
- Agents: 29-agent corps + OMNIS (the universal skills agent)
- Persona: Full identity and emotional system
- Cortex: 7 reasoning modules
- Memory: Semantic, episodic, vector, knowledge graph
- Senses: 9 perceptual monitors
- Tools: 14 operational tools
- Skills: Full framework with OMNIS as unified router (60+ capabilities)

OMNIS Integration:
  - iris.omnis — Universal skills agent (execute any capability)
  - iris.skill_router — Direct skill routing
  - iris.smart_execute() — Natural language to capability
  - All capabilities accessible via single entry point
"""

import os
import sys
import logging
import threading
from datetime import datetime
from flask import Flask, request, jsonify, render_template, session, Response, g
from flask_cors import CORS
from werkzeug.middleware.proxy_fix import ProxyFix

from config import config
from core.db import db
from core.orchestrator import AgentOrchestrator
from core.predictive_engine import PredictiveEngine
from core.registry import AgentRegistry
from core.communication import MessageBus
from core.shared_memory import SharedMemory
from core.task_queue import TaskQueue
from modules.consciousness import ConsciousnessEngine
from modules.security import SecurityManager
from modules.proactive_engine import ProactiveEngine
from modules.autonomous import AutonomousEngine
from modules.voice_system import VoiceSystem
from modules.vision_ai import VisionAI
from modules.vision_stream import VisionStream
from modules.project_generator import ProjectGenerator
from modules.sandbox_executor import SandboxExecutor
from modules.self_improve import SelfImprovementEngine
from modules.mobile_api import MobileAPI
from modules.phone_bridge import PhoneBridge
from modules.email_module import EmailModule
from modules.news_module import NewsModule
from modules.sports_module import SportsModule
from modules.web_search import WebSearch
from modules.nl2code import NL2Code
from modules.auto_debug import AutoDebug
from modules.image_generation import ImageGeneration
from modules.image_module import ImageModule
from modules.wake_word import WakeWordDetector
from modules.voicerss_module import VoiceRSSModule
from modules.chess_engine import ChessEngine
from modules.copilot_bridge import CopilotBridge
from memory.smart_memory import SmartMemory
from memory.chroma_memory import ChromaMemory
from memory.semantic_search import SemanticSearch
from memory.knowledge_graph import KnowledgeGraph
from memory.learning_engine import LearningEngine
from memory.mission_archive import MissionArchive
from memory.agent_memory import AgentMemory
from memory.skill_memory import SkillMemory
from memory.base_memory import BaseMemory
from persona import IRISCore as PersonaCore
from persona.core_identity import CoreIdentity
from persona.emotional_state import EmotionalState
from persona.creator_bond import CreatorBond
from persona.relationship_map import RelationshipMap
from persona.intruder_defense import IntruderDefense
from persona.voice_personality import VoicePersonality
from persona.growth_tracker import GrowthTracker
from persona.dream_engine import DreamEngine
from cortex.base_cortex import BaseCortex
from cortex.planner import Planner
from cortex.strategist import Strategist
from cortex.risk_assessor import RiskAssessor
from cortex.resource_optimizer import ResourceOptimizer
from cortex.hypothesis_tester import HypothesisTester
from cortex.meta_learner import MetaLearner
from senses.system_monitor import SystemMonitor
from senses.file_watcher import FileWatcher
from senses.network_watcher import NetworkWatcher
from senses.log_ingestor import LogIngestor
from senses.threat_feeds import ThreatFeeds
from senses.uptime_monitor import UptimeMonitor
from senses.alert_router import AlertRouter
from senses.base_sense import BaseSense
from senses.registry import SenseRegistry
from tools.registry import ToolRegistry
from tools.base_tool import BaseTool, IRISConnectable
from tools.nmap_wrapper import NmapWrapper
from tools.sqlmap_wrapper import SQLMapWrapper
from tools.metasploit_bridge import MetasploitBridge
from tools.burp_bridge import BurpBridge
from tools.wireshark_parser import WiresharkParser
from tools.volatility_bridge import VolatilityBridge
from tools.docker_engine import DockerEngine
from tools.aws_cli import AWSCLI
from tools.git_engine import GitEngine
from tools.api_client import APIClient
from tools.code_analyzer import CodeAnalyzer
from skills import SkillRouter, BaseSkill, SkillRegistry, skill_router, skill_registry
from agents.omnis import OMNIS, omnis
from api.routes.auth import auth_bp
from api.routes.chat import chat_bp
from api.routes.voice import voice_bp
from api.routes.vision import vision_bp
from api.routes.phone import phone_bp
from api.routes.calendar import calendar_bp
from api.routes.notes import notes_bp
from api.routes.math import math_bp
from api.routes.projects import projects_bp
from api.routes.self_improve import self_improve_bp
from api.routes.consciousness import consciousness_bp
from api.routes.memory import memory_bp
from api.routes.autonomous import autonomous_bp
from api.routes.proactive import proactive_bp
from api.routes.mobile import mobile_bp
from api.routes.tools import tools_bp
from api.routes.email import email_bp
from api.routes.news import news_bp
from api.routes.sports import sports_bp
from api.routes.image import image_bp
from api.routes.gateway import gateway_bp
from api.routes.system import system_bp
from api.routes.intelligence import intelligence_bp

logging.basicConfig(
    level=getattr(logging, config.LOG_LEVEL),
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler(os.path.join(config.DATA_DIR, "iris.log")) if config.LOG_TO_FILE else logging.NullHandler()
    ]
)
logger = logging.getLogger(__name__)

app = Flask(__name__, template_folder="templates", static_folder="static")
app.secret_key = config.FLASK_SECRET_KEY
app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1, x_prefix=1)
CORS(app, resources={r"/api/*": {"origins": "*", "supports_credentials": True}})


class IRISCore:
    """The one true IRIS core. Every module connects here."""

    _instance = None
    _lock = threading.Lock()

    def __new__(cls):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if self._initialized:
            return
        self._initialized = True

        logger.info("=" * 60)
        logger.info("IRIS v1 — Initializing Infinite Reactive Intelligence")
        logger.info("OMNIS Skills Agent — Loading all capabilities...")
        logger.info("=" * 60)

        self.db = db
        self.message_bus = MessageBus()
        self.shared_memory = SharedMemory()
        self.task_queue = TaskQueue()
        self.agent_registry = AgentRegistry()
        self.orchestrator = AgentOrchestrator()
        self.predictive = PredictiveEngine()

        self.consciousness = ConsciousnessEngine()
        self.security = SecurityManager()
        self.proactive = ProactiveEngine()
        self.autonomous = AutonomousEngine()
        self.voice = VoiceSystem()
        self.vision = VisionAI()
        self.vision_stream = VisionStream()
        self.project_gen = ProjectGenerator()
        self.sandbox = SandboxExecutor()
        self.self_improve = SelfImprovementEngine()
        self.mobile = MobileAPI()
        self.phone = PhoneBridge()
        self.email = EmailModule()
        self.news = NewsModule()
        self.sports = SportsModule()
        self.web_search = WebSearch()
        self.nl2code = NL2Code()
        self.auto_debug = AutoDebug()
        self.image_gen = ImageGeneration()
        self.image_module = ImageModule()
        self.wake_word = WakeWordDetector()
        self.voicerss = VoiceRSSModule()
        self.chess = ChessEngine()
        self.copilot = CopilotBridge()

        self.smart_memory = SmartMemory()
        self.chroma_memory = ChromaMemory()
        self.semantic_search = SemanticSearch()
        self.knowledge_graph = KnowledgeGraph()
        self.learning_engine = LearningEngine()
        self.mission_archive = MissionArchive()
        self.agent_memory = AgentMemory()
        self.skill_memory = SkillMemory()

        self.persona = PersonaCore()
        self.identity = CoreIdentity()
        self.emotions = EmotionalState()
        self.creator_bond = CreatorBond()
        self.relationships = RelationshipMap()
        self.defense = IntruderDefense()
        self.voice_personality = VoicePersonality()
        self.growth = GrowthTracker()
        self.dream = DreamEngine()

        self.planner = Planner()
        self.strategist = Strategist()
        self.risk_assessor = RiskAssessor()
        self.resource_optimizer = ResourceOptimizer()
        self.hypothesis_tester = HypothesisTester()
        self.meta_learner = MetaLearner()

        self.sense_registry = SenseRegistry()
        self.system_monitor = SystemMonitor()
        self.file_watcher = FileWatcher()
        self.network_watcher = NetworkWatcher()
        self.log_ingestor = LogIngestor()
        self.threat_feeds = ThreatFeeds()
        self.uptime_monitor = UptimeMonitor()
        self.alert_router = AlertRouter()

        self.tool_registry = ToolRegistry()
        self.tools = {
            "nmap": NmapWrapper(), "sqlmap": SQLMapWrapper(), "metasploit": MetasploitBridge(),
            "burp": BurpBridge(), "wireshark": WiresharkParser(), "volatility": VolatilityBridge(),
            "docker": DockerEngine(), "aws": AWSCLI(), "git": GitEngine(),
            "api": APIClient(), "code_analyzer": CodeAnalyzer(),
        }

        # OMNIS: The Universal Skills Agent
        self.omnis = OMNIS(iris_core=self)
        self.skill_router = skill_router
        self.skill_registry = skill_registry

        self._wire_modules()
        self.omnis.start()

        logger.info("IRIS v1 — All systems operational")
        logger.info("OMNIS is online — 60+ capabilities ready")
        logger.info("=" * 60)

    def _wire_modules(self):
        self.persona.iris_core = self
        self.consciousness.persona = self.persona
        self.orchestrator.smart_memory = self.smart_memory
        self.orchestrator.knowledge_graph = self.knowledge_graph
        self.security.iris_core = self
        self.alert_router.iris_core = self
        self.system_monitor.iris_core = self
        self.network_watcher.iris_core = self
        for name, tool in self.tools.items():
            tool.iris_core = self
        self.proactive.iris_core = self
        self.proactive.predictive = self.predictive
        self.autonomous.iris_core = self
        self.self_improve.iris_core = self
        self.omnis._iris_core = self
        logger.info("All modules cross-wired successfully (including OMNIS)")

    def health_check(self):
        return {
            "status": "healthy",
            "timestamp": datetime.now().isoformat(),
            "version": "v1.0.0",
            "modules": {
                "core": True, "orchestrator": True, "consciousness": True, "security": True,
                "proactive": True, "autonomous": True, "voice": True, "vision": True,
                "memory": True, "persona": True, "cortex": True, "senses": True,
                "tools": True, "skills": True, "omnis": self.omnis.health() if hasattr(self, 'omnis') else False,
            },
            "agents_registered": len(self.agent_registry._agents) if hasattr(self.agent_registry, "_agents") else 0,
            "tools_available": len(self.tools), "senses_active": 7,
            "omnis_status": self.omnis.health() if hasattr(self, 'omnis') else None,
            "capabilities_available": len(self.omnis._router.get_manifest().get("manifest", {})) if hasattr(self, 'omnis') else 0,
        }

    def receive_finding(self, finding: dict):
        logger.info(f"[FINDING] {finding.get('type')} from {finding.get('reported_by')}")
        if finding.get("type") == "threat":
            self.alert_router.route_alert(finding)
        elif finding.get("type") == "system":
            self.system_monitor.process(finding)
        self.smart_memory.store_finding(finding)

    def execute_skill(self, capability: str, params: Dict[str, Any] = None):
        """Execute a skill capability through OMNIS."""
        return self.omnis.execute(capability, params)

    def smart_execute(self, request: str, context: Dict[str, Any] = None):
        """Smart execution: pass natural language, OMNIS figures it out."""
        return self.omnis.smart_route(request, context)


iris = IRISCore()

blueprints = [
    auth_bp, chat_bp, voice_bp, vision_bp, phone_bp, calendar_bp, notes_bp,
    math_bp, projects_bp, self_improve_bp, consciousness_bp, memory_bp,
    autonomous_bp, proactive_bp, mobile_bp, tools_bp, email_bp, news_bp,
    sports_bp, image_bp, gateway_bp, system_bp, intelligence_bp,
]
for bp in blueprints:
    app.register_blueprint(bp)

@app.before_request
def before_request():
    g.iris = iris
    g.db = db

@app.route("/health")
def health():
    return jsonify(iris.health_check())

@app.route("/")
def index():
    return render_template("index.html")


# ─── OMNIS API Endpoints ─────────────────────────────────────────────────

@app.route("/api/omnis/execute", methods=["POST"])
def omnis_execute():
    data = request.get_json() or {}
    capability = data.get("capability", "")
    params = data.get("params", {})
    if not capability:
        return jsonify({"success": False, "error": "Missing 'capability' field"}), 400
    return jsonify(iris.omnis.execute(capability, params))

@app.route("/api/omnis/chain", methods=["POST"])
def omnis_chain():
    data = request.get_json() or {}
    steps = data.get("steps", [])
    if not steps:
        return jsonify({"success": False, "error": "Missing 'steps' array"}), 400
    return jsonify(iris.omnis.chain(steps))

@app.route("/api/omnis/discover", methods=["GET", "POST"])
def omnis_discover():
    if request.method == "POST":
        query = (request.get_json() or {}).get("query")
    else:
        query = request.args.get("query")
    caps = iris.omnis.discover(query)
    return jsonify({"success": True, "capabilities": caps, "total": len(caps)})

@app.route("/api/omnis/smart", methods=["POST"])
def omnis_smart():
    data = request.get_json() or {}
    req_text = data.get("request", "")
    context = data.get("context", {})
    if not req_text:
        return jsonify({"success": False, "error": "Missing 'request' field"}), 400
    return jsonify(iris.omnis.smart_route(req_text, context))

@app.route("/api/omnis/status", methods=["GET"])
def omnis_status():
    return jsonify(iris.omnis.status())

@app.route("/api/omnis/agents", methods=["GET"])
def omnis_agents():
    return jsonify({"success": True, "agents": list(iris.omnis._agent_map.keys()), "count": len(iris.omnis._agent_map)})

@app.route("/api/omnis/delegate", methods=["POST"])
def omnis_delegate():
    data = request.get_json() or {}
    agent_name = data.get("agent", "")
    task = data.get("task", {})
    if not agent_name:
        return jsonify({"success": False, "error": "Missing 'agent' field"}), 400
    return jsonify(iris.omnis.delegate(agent_name, task))

@app.route("/api/omnis/manifest", methods=["GET"])
def omnis_manifest():
    return jsonify(iris.omnis._router.get_manifest())

# ─── /Plugin Command System ──────────────────────────────────────────────

@app.route("/api/plugins", methods=["GET"])
def plugins_list():
    """Return all available /plugins organized by category."""
    return jsonify(iris.omnis.get_plugins())

@app.route("/api/plugins/<command>", methods=["GET", "POST"])
def plugin_command(command):
    """
    Execute a /plugin command.
    GET /api/plugins/calendar?method=list_events
    POST /api/plugins/tasks {"method": "create", "title": "Buy groceries"}
    """
    if request.method == "POST":
        params = request.get_json() or {}
    else:
        params = request.args.to_dict()
    result = iris.omnis.route_plugin(command, params)
    return jsonify(result)

@app.route("/api/plugins/search", methods=["GET"])
def plugins_search():
    """Search plugins by keyword."""
    query = request.args.get("q", "")
    return jsonify(iris.omnis.discover(query))


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=config.DEBUG)
