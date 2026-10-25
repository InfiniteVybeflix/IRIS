"""IRIS v1 Phone Bridge Routes"""
from flask import Blueprint, request, jsonify
from modules.phone_bridge import phone_bridge

phone_bp = Blueprint('phone', __name__, url_prefix='/api/phone')

@phone_bp.route('/contacts', methods=['GET'])
def phone_contacts():
    return jsonify(phone_bridge.get_contacts())

@phone_bp.route('/contacts/search', methods=['GET'])
def phone_search_contacts():
    return jsonify(phone_bridge.search_contacts(request.args.get('q', '')))

@phone_bp.route('/call', methods=['POST'])
def phone_call():
    return jsonify(phone_bridge.call_contact(request.get_json().get('number', '')))

@phone_bp.route('/messages', methods=['GET'])
def phone_messages():
    return jsonify(phone_bridge.get_messages(request.args.get('limit', 20, type=int)))

@phone_bp.route('/send-message', methods=['POST'])
def phone_send_message():
    data = request.get_json() or {}
    return jsonify(phone_bridge.send_message(data.get('number', ''), data.get('text', '')))

@phone_bp.route('/torch', methods=['POST'])
def phone_torch():
    return jsonify(phone_bridge.torch(request.get_json().get('state', 'toggle')))

@phone_bp.route('/wifi', methods=['POST'])
def phone_wifi():
    return jsonify(phone_bridge.toggle_wifi(request.get_json().get('state', 'toggle')))

@phone_bp.route('/bluetooth', methods=['POST'])
def phone_bluetooth():
    return jsonify(phone_bridge.toggle_bluetooth(request.get_json().get('state', 'toggle')))

@phone_bp.route('/battery', methods=['GET'])
def phone_battery():
    return jsonify(phone_bridge.get_battery())

@phone_bp.route('/notifications', methods=['GET'])
def phone_notifications():
    return jsonify(phone_bridge.get_notifications())

@phone_bp.route('/camera', methods=['POST'])
def phone_camera():
    action = request.get_json().get('action', 'open')
    if action == 'open':
        return jsonify(phone_bridge.open_camera())
    elif action == 'take_photo':
        return jsonify(phone_bridge.take_photo())
    return jsonify({"success": False, "error": "Unknown action"})

@phone_bp.route('/screenshot', methods=['GET'])
def phone_screenshot():
    return jsonify(phone_bridge.screenshot())

@phone_bp.route('/device-info', methods=['GET'])
def phone_device_info():
    return jsonify(phone_bridge.get_device_info())


# ─── Connect guide / command console ─────────────────────────────────────

@phone_bp.route('/devices', methods=['GET'])
def phone_devices():
    """List devices visible to adb (`adb devices -l`) — used by the connect
    guide's “Scan for devices” button."""
    return jsonify(phone_bridge.list_devices())


@phone_bp.route('/connect', methods=['POST'])
def phone_connect():
    """Connect to a device over the network: `adb connect <ip>:<port>`.

    Body: {"address": "192.168.1.20:5555"}
    """
    data = request.get_json() or {}
    return jsonify(phone_bridge.connect(data.get('address', '')))


@phone_bp.route('/exec', methods=['POST'])
def phone_exec():
    """Run a user-supplied ADB command from the Phone command console.

    Body: {"command": "shell dumpsys battery"}   (leading `adb ` is optional)

    The command runs for real on the host; stdout/stderr are returned
    verbatim. Destructive patterns are refused explicitly, never silently.
    """
    data = request.get_json() or {}
    return jsonify(phone_bridge.run_command(data.get('command', '')))
