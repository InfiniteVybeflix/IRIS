"""IRIS v1 Chat Routes — Streaming, Proactive Context, Tool Calling"""
import json
import uuid
from flask import Blueprint, request, jsonify, Response, stream_with_context
from api.utils.rate_limiter import rate_limit
from config import config
from core.db import db
from core.orchestrator import orchestrator
from core.memory_engine import memory_engine
from core.predictive_engine import predictive_engine
from modules.consciousness import consciousness
from modules.proactive_engine import proactive_engine

chat_bp = Blueprint('chat', __name__, url_prefix='/api/chat')

@chat_bp.route('', methods=['POST'])
@rate_limit
def chat():
    data = request.get_json() or {}
    user_input = data.get('message', '')
    session_id = data.get('session_id') or str(uuid.uuid4())

    if not user_input:
        return jsonify({"success": False, "error": "No message provided"}), 400

    proactive_engine.record_interaction(user_input, "chat", True)
    db.save_message(session_id, "user", user_input)

    matching_skill = memory_engine.find_matching_skill(user_input)
    plan = memory_engine.apply_skill(matching_skill, user_input) if matching_skill else None
    predictive_engine.record_interaction(user_input, [], True)
    context = predictive_engine.prewarm_context(user_input)
    proactive_context = proactive_engine.get_context_summary()

    results = []
    final = None
    # NOTE: orchestrator.process() accepts (user_input, session_id) only.
    # The proactive context summary is recorded above via
    # proactive_engine.record_interaction/get_context_summary and is
    # gathered internally by the orchestrator's OBSERVE phase.
    for update in orchestrator.process(user_input, session_id):
        if update.get("final"):
            final = update
        else:
            results.append(update)

    response_text = final.get("message", "Processing...") if final else "Processing..."
    db.save_message(
        session_id, "assistant", response_text,
        reasoning=json.dumps(final.get("data", {}).get("plan", {})) if final else None,
        tool_calls=final.get("data", {}).get("tools_used", []) if final else [],
        model_used=final.get("data", {}).get("model_used") if final else None
    )
    consciousness.on_event("user_message", {"input": user_input})

    return jsonify({
        "success": True,
        "response": response_text,
        "session_id": session_id,
        "status_updates": results,
        "verification": final.get("data", {}).get("verification") if final else None,
        "emotion": consciousness.get_dominant_emotion(),
        "proactive_suggestion": proactive_engine.suggest_action()
    })

@chat_bp.route('/stream', methods=['POST'])
@rate_limit
def chat_stream():
    data = request.get_json() or {}
    user_input = data.get('message', '')
    session_id = data.get('session_id') or str(uuid.uuid4())

    def generate():
        for update in orchestrator.process(user_input, session_id):
            yield f"data: {json.dumps(update)}\n\n"
        yield "data: [DONE]\n\n"

    return Response(stream_with_context(generate()), mimetype='text/event-stream')
