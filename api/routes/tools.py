"""IRIS v1 Tools Routes"""
from flask import Blueprint, request, jsonify
from api.utils.rate_limiter import rate_limit
from core.tool_registry import tool_registry

tools_bp = Blueprint('tools', __name__, url_prefix='/api/tools')

@tools_bp.route('', methods=['GET'])
def tools_list():
    return jsonify({"success": True, "tools": tool_registry.schemas})

@tools_bp.route('/execute', methods=['POST'])
@rate_limit
def tools_execute():
    data = request.get_json() or {}
    tool_name = data.get('tool', '')
    if tool_name not in tool_registry.tools:
        return jsonify({"success": False, "error": f"Unknown tool: {tool_name}"}), 400
    result = tool_registry.tools[tool_name](**data.get('params', {}))
    return jsonify(result.dict())
