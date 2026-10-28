"""IRIS v2 Chat Routes — sessions, streaming, edit/retry/delete.

Endpoints:
  POST /api/chat                  — send a message (non-streaming, returns full answer)
  POST /api/chat/stream           — send a message, SSE stream of orchestrator events
  GET  /api/chat/sessions         — list all chat sessions (history)
  POST /api/chat/sessions         — create a new session
  GET  /api/chat/sessions/<id>    — one session + its messages
  PATCH /api/chat/sessions/<id>   — rename a session
  DELETE /api/chat/sessions/<id>  — delete a session and all its messages
  PUT  /api/chat/sessions/<id>/messages/<mid>    — edit a message
  DELETE /api/chat/sessions/<id>/messages/<mid>  — delete a message
  POST /api/chat/sessions/<id>/retry/<mid>       — retry from a message:
                                       drops that assistant message and regenerates

All responses are honest: failures return success:false with the real error.
"""
import json
import re
import uuid
from flask import Blueprint, Response, jsonify, request, stream_with_context

from config import config
from core.db import db
from core.orchestrator import orchestrator

try:
    from api.utils.rate_limiter import rate_limit
except Exception:  # pragma: no cover — rate limiter is optional in tests
    def rate_limit(fn):
        return fn

chat_bp = Blueprint('chat', __name__, url_prefix='/api/chat')


# ─────────────────────────────────────────────────────────────────────────────
# Provider override (frontend localStorage bridge)
# ─────────────────────────────────────────────────────────────────────────────
def _extract_provider_override(data: dict) -> dict:
    """Build the per-request provider override sent by the frontend.

    Shape: {backend?, url?, key?, x_aevibron_key?, model?, host?, providers?}
    Only known fields pass through — never trust arbitrary keys.
    """
    pc = data.get("provider_config") or {}
    if not isinstance(pc, dict):
        return {}
    out = {}
    for k in ("url", "key", "x_aevibron_key", "model", "host"):
        v = pc.get(k)
        if v and isinstance(v, str):
            out[k] = v
    b = pc.get("backend") or pc.get("provider")
    if b and isinstance(b, str):
        out["backend"] = b.lower()
    return out


def _session_id(data: dict) -> str:
    sid = data.get('session_id')
    if sid and isinstance(sid, str) and re.fullmatch(r"[A-Za-z0-9_\-]{6,64}", sid):
        return sid
    return str(uuid.uuid4())


def _auto_title(text: str) -> str:
    """Derive a session title from the first user message."""
    t = re.sub(r"\s+", " ", (text or "")).strip()
    if not t:
        return "New chat"
    return (t[:48] + "…") if len(t) > 48 else t


def _history_for_llm(session_id: str) -> list:
    """Recent messages for context (excluding the current user message that
    was just saved — the orchestrator adds it itself)."""
    try:
        rows = db.get_conversation(session_id, limit=config.MAX_CONVERSATION_HISTORY)
    except Exception:
        rows = []
    return [{"role": r.get("role"), "content": r.get("content")}
            for r in rows if r.get("role") in ("user", "assistant") and r.get("content")]


def _drop_messages_from(session_id: str, message_id):
    """Delete message_id and everything after it in the session."""
    try:
        rows = db.get_messages_after(session_id, message_id)
        for r in rows:
            db.delete_message(r["id"])
        db.delete_message(message_id)
    except Exception:
        pass


# ─────────────────────────────────────────────────────────────────────────────
# Sessions
# ─────────────────────────────────────────────────────────────────────────────
@chat_bp.route('/sessions', methods=['GET'])
def list_sessions():
    try:
        rows = db.list_chat_sessions()
        return jsonify({"success": True, "sessions": rows, "count": len(rows)})
    except Exception as e:
        return jsonify({"success": False, "error": f"Could not list sessions: {e}"}), 500


@chat_bp.route('/sessions', methods=['POST'])
def create_session():
    data = request.get_json(silent=True) or {}
    sid = data.get("session_id") or str(uuid.uuid4())
    if not re.fullmatch(r"[A-Za-z0-9_\-]{6,64}", sid):
        return jsonify({"success": False, "error": "Invalid session id"}), 400
    title = (data.get("title") or "New chat").strip()[:80] or "New chat"
    try:
        db.create_chat_session(sid, title)
        return jsonify({"success": True, "session": {
            "session_id": sid, "title": title, "message_count": 0, "last_message": None}})
    except Exception as e:
        return jsonify({"success": False, "error": f"Could not create session: {e}"}), 500


@chat_bp.route('/sessions/<session_id>', methods=['GET'])
def get_session(session_id):
    try:
        meta = db.get_chat_session(session_id)
        if not meta:
            return jsonify({"success": False, "error": "Session not found"}), 404
        messages = db.get_conversation(session_id, limit=500)
        return jsonify({"success": True, "session": meta, "messages": messages})
    except Exception as e:
        return jsonify({"success": False, "error": f"Could not load session: {e}"}), 500


@chat_bp.route('/sessions/<session_id>', methods=['PATCH'])
def rename_session(session_id):
    data = request.get_json(silent=True) or {}
    title = (data.get("title") or "").strip()[:80]
    if not title:
        return jsonify({"success": False, "error": "title required"}), 400
    try:
        db.rename_chat_session(session_id, title)
        return jsonify({"success": True, "session_id": session_id, "title": title})
    except Exception as e:
        return jsonify({"success": False, "error": f"Could not rename session: {e}"}), 500


@chat_bp.route('/sessions/<session_id>', methods=['DELETE'])
def delete_session(session_id):
    try:
        db.delete_chat_session(session_id)
        return jsonify({"success": True, "deleted": session_id})
    except Exception as e:
        return jsonify({"success": False, "error": f"Could not delete session: {e}"}), 500


@chat_bp.route('/sessions/<session_id>/messages/<message_id>', methods=['PUT'])
def edit_message(session_id, message_id):
    data = request.get_json(silent=True) or {}
    content = data.get("content")
    if not content or not isinstance(content, str):
        return jsonify({"success": False, "error": "content required"}), 400
    try:
        db.update_message(message_id, content)
        db.touch_chat_session(session_id)
        return jsonify({"success": True, "message_id": message_id, "content": content})
    except Exception as e:
        return jsonify({"success": False, "error": f"Could not edit message: {e}"}), 500


@chat_bp.route('/sessions/<session_id>/messages/<message_id>', methods=['DELETE'])
def delete_message(session_id, message_id):
    try:
        db.delete_message(message_id)
        return jsonify({"success": True, "deleted": message_id})
    except Exception as e:
        return jsonify({"success": False, "error": f"Could not delete message: {e}"}), 500


# ─────────────────────────────────────────────────────────────────────────────
# Chat (non-streaming)
# ─────────────────────────────────────────────────────────────────────────────
@chat_bp.route('', methods=['POST'])
@rate_limit
def chat():
    data = request.get_json() or {}
    user_input = (data.get('message') or '').strip()
    session_id = _session_id(data)
    provider_override = _extract_provider_override(data)

    if not user_input:
        return jsonify({"success": False, "error": "No message provided"}), 400

    # Ensure the session exists (auto-title from the first message).
    try:
        existing = db.get_chat_session(session_id)
        if not existing:
            db.create_chat_session(session_id, _auto_title(user_input))
    except Exception:
        pass

    try:
        db.save_message(session_id, "user", user_input)
    except Exception:
        pass

    history = _history_for_llm(session_id)[:-1]  # drop the just-saved user msg

    answer = ""
    events = []
    try:
        for ev in orchestrator.process_stream(user_input, session_id=session_id,
                                              history=history, provider_override=provider_override):
            events.append(ev)
            if ev.get("type") == "answer":
                answer += ev.get("content", "")
            elif ev.get("type") == "answer_retract":
                answer = answer[:max(0, len(answer) - int(ev.get("length", 0)))]
            elif ev.get("type") == "error":
                return jsonify({"success": False, "error": ev.get("message"),
                                "session_id": session_id}), 502
    except Exception as e:
        return jsonify({"success": False, "error": f"Orchestrator failed: {e}",
                        "session_id": session_id}), 500

    tool_calls = []
    done_ev = next((e for e in events if e.get("type") == "done"), {})
    tool_calls = done_ev.get("tool_calls", [])

    try:
        db.save_message(session_id, "assistant", answer,
                        reasoning=None,
                        tool_calls=[{"name": t.get("name"), "arguments": t.get("arguments")}
                                    for t in tool_calls],
                        model_used=done_ev.get("provider", ""))
        db.touch_chat_session(session_id)
    except Exception:
        pass

    return jsonify({
        "success": True,
        "response": answer,
        "session_id": session_id,
        "provider": done_ev.get("provider", ""),
        "tool_calls": [{"name": t.get("name")} for t in tool_calls],
        "events": [e for e in events if e.get("type") in ("thinking", "terminal_start", "terminal_end")],
        "duration": done_ev.get("duration"),
    })


# ─────────────────────────────────────────────────────────────────────────────
# Chat (SSE streaming — the main chat path)
# ─────────────────────────────────────────────────────────────────────────────
@chat_bp.route('/stream', methods=['POST'])
@rate_limit
def chat_stream():
    data = request.get_json() or {}
    user_input = (data.get('message') or '').strip()
    session_id = _session_id(data)
    provider_override = _extract_provider_override(data)

    if not user_input:
        return jsonify({"success": False, "error": "No message provided"}), 400

    # Ensure the session exists (auto-title from the first message).
    try:
        existing = db.get_chat_session(session_id)
        if not existing:
            db.create_chat_session(session_id, _auto_title(user_input))
    except Exception:
        pass

    try:
        db.save_message(session_id, "user", user_input)
    except Exception:
        pass

    history = _history_for_llm(session_id)[:-1]  # drop the just-saved user msg

    def generate():
        answer = ""
        thinking = ""
        tool_calls_meta = []
        done_meta = {}
        try:
            for ev in orchestrator.process_stream(user_input, session_id=session_id,
                                                  history=history,
                                                  provider_override=provider_override):
                if ev.get("type") == "answer":
                    answer += ev.get("content", "")
                elif ev.get("type") == "answer_retract":
                    answer = answer[:max(0, len(answer) - int(ev.get("length", 0)))]
                elif ev.get("type") == "thinking":
                    thinking += ev.get("content", "")
                elif ev.get("type") == "terminal_start":
                    tool_calls_meta.append({"title": ev.get("title"), "command": ev.get("command")})
                elif ev.get("type") == "done":
                    done_meta = ev
                yield f"data: {json.dumps(ev, default=str, ensure_ascii=False)}\n\n"
        except Exception as e:
            yield f"data: {json.dumps({'type': 'error', 'message': f'Stream failed: {e}'})}\n\n"

        # Persist the assistant answer (best-effort, honest).
        try:
            if answer.strip():
                db.save_message(session_id, "assistant", answer, reasoning=thinking or None,
                                tool_calls=tool_calls_meta,
                                model_used=done_meta.get("provider", ""))
                db.touch_chat_session(session_id)
        except Exception as e:
            yield f"data: {json.dumps({'type': 'warning', 'message': f'Answer not saved: {e}'})}\n\n"

        # Session summary so the frontend can update its sidebar.
        try:
            meta = db.get_chat_session(session_id) or {}
            yield "data: " + json.dumps({
                "type": "session",
                "session_id": session_id,
                "title": meta.get("title", _auto_title(user_input)),
            }, default=str) + "\n\n"
        except Exception:
            pass

        yield "data: [DONE]\n\n"

    return Response(stream_with_context(generate()), mimetype='text/event-stream',
                    headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no",
                             "Connection": "keep-alive"})


# ─────────────────────────────────────────────────────────────────────────────
# Retry — regenerate an assistant reply
# ─────────────────────────────────────────────────────────────────────────────
@chat_bp.route('/sessions/<session_id>/retry/<message_id>', methods=['POST'])
@rate_limit
def retry_message(session_id, message_id):
    """Retry: delete the assistant message (and anything after it), then
    stream a new answer for the last user message in the session."""
    data = request.get_json(silent=True) or {}
    provider_override = _extract_provider_override(data)

    try:
        rows = db.get_conversation(session_id, limit=500)
    except Exception as e:
        return jsonify({"success": False, "error": f"Could not load session: {e}"}), 500

    target = next((r for r in rows if str(r.get("id")) == str(message_id)), None)
    if not target:
        return jsonify({"success": False, "error": "Message not found"}), 404

    # Drop the assistant message + everything after it.
    _drop_messages_from(session_id, message_id)

    # The last remaining user message is the prompt to regenerate from.
    remaining = [r for r in db.get_conversation(session_id, limit=500) if r.get("role") == "user"]
    if not remaining:
        return jsonify({"success": False, "error": "No user message to retry from"}), 400
    prompt = remaining[-1]["content"]
    history = _history_for_llm(session_id)[:-1]

    def generate():
        answer = ""
        done_meta = {}
        try:
            for ev in orchestrator.process_stream(prompt, session_id=session_id,
                                                  history=history,
                                                  provider_override=provider_override):
                if ev.get("type") == "answer":
                    answer += ev.get("content", "")
                elif ev.get("type") == "answer_retract":
                    answer = answer[:max(0, len(answer) - int(ev.get("length", 0)))]
                elif ev.get("type") == "done":
                    done_meta = ev
                yield f"data: {json.dumps(ev, default=str, ensure_ascii=False)}\n\n"
        except Exception as e:
            yield f"data: {json.dumps({'type': 'error', 'message': f'Retry failed: {e}'})}\n\n"
        try:
            if answer.strip():
                db.save_message(session_id, "assistant", answer, model_used=done_meta.get("provider", ""))
                db.touch_chat_session(session_id)
        except Exception:
            pass
        yield "data: [DONE]\n\n"

    return Response(stream_with_context(generate()), mimetype='text/event-stream',
                    headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})
