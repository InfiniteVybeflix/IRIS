"""IRIS v1 Email Routes"""
from flask import Blueprint, request, jsonify
from api.utils.rate_limiter import rate_limit
from modules.email_module import email_module

email_bp = Blueprint('email', __name__, url_prefix='/api/email')

@email_bp.route('/send', methods=['POST'])
@rate_limit
def email_send():
    data = request.get_json() or {}
    if not data.get('to') or not data.get('subject') or not data.get('body'):
        return jsonify({"success": False, "error": "to, subject, and body required"}), 400
    if data.get('provider') == 'resend':
        return jsonify(email_module.send_resend(data['to'], data['subject'], data['body'], data.get('html', False)))
    return jsonify(email_module.send_gmail(data['to'], data['subject'], data['body'], data.get('html', False)))

@email_bp.route('/log-report', methods=['POST'])
def email_log_report():
    data = request.get_json() or {}
    return jsonify(email_module.send_log_report(data.get('content', ''), data.get('title', 'IRIS Log Report')))

@email_bp.route('/alert', methods=['POST'])
def email_alert():
    data = request.get_json() or {}
    return jsonify(email_module.send_alert(data.get('type', ''), data.get('message', ''), data.get('priority', 'normal')))
