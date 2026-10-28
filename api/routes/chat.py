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


def _extract_provider_override(data: dict) -> dict:
    """Pull a per-request provider config from the chat request body.

    The frontend saves settings to localStorage as a fallback when the
    server has no persistent backend (Vercel + no Postgres). Those saved
    values are sent with each chat request as `provider_config` so the
    orchestrator can use them for THIS request even though they were
    never persisted server-side. Settings that ARE persisted server-side
    take precedence — the override only fills in gaps.
    """
    pc = data.get("provider_config") or {}
    if not isinstance(pc, dict):
        return {}
    # Only honor known Aevibron fields — never trust arbitrary keys.
    out = {}
    for k in ("url", "key", "x_aevibron_key"):
        v = pc.get(k)
        if v and isinstance(v, str):
            out[k] = v
    # Also allow the user to specify a model per-request
    if pc.get("model"):
        out["model"] = str(pc["model"])
    return out


@chat_bp.route('', methods=['POST'])
@rate_limit
def chat():
    data = request.get_json() or {}
    user_input = data.get('message', '')
    session_id = data.get('session_id') or str(uuid.uuid4())
    provider_override = _extract_provider_override(data)

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
    # NOTE: orchestrator.process() accepts (user_input, session_id, provider_override).
    # The override is filled from localStorage-saved settings on the client
    # when the server has no persistent backend — so saving settings in
    # the UI actually drives the model end-to-end, even on Vercel sans DB.
    for update in orchestrator.process(user_input, session_id, provider_override=provider_override):
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
    provider_override = _extract_provider_override(data)

    def generate():
        for update in orchestrator.process(user_input, session_id, provider_override=provider_override):
            yield f"data: {json.dumps(update)}\n\n"
        yield "data: [DONE]\n\n"

    return Response(stream_with_context(generate()), mimetype='text/event-stream')
