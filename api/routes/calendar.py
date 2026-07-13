"""IRIS v1 Calendar Routes"""
from flask import Blueprint, request, jsonify, Response
from skills.calendar_skill import calendar_skill

calendar_bp = Blueprint('calendar', __name__, url_prefix='/api/calendar')

@calendar_bp.route('/events', methods=['GET'])
def calendar_get_events():
    result = calendar_skill.get_events(
        request.args.get('start'),
        request.args.get('end'),
        request.args.get('category')
    )
    return jsonify(result)

@calendar_bp.route('/events', methods=['POST'])
def calendar_add_event():
    data = request.get_json() or {}
    if not data.get('title') or not data.get('start_time'):
        return jsonify({"success": False, "error": "Title and start_time required"}), 400
    result = calendar_skill.add_event(
        title=data['title'],
        start_time=data['start_time'],
        end_time=data.get('end_time'),
        description=data.get('description'),
        location=data.get('location'),
        category=data.get('category', 'general'),
        priority=data.get('priority', 5),
        recurring=data.get('recurring')
    )
    return jsonify(result)

@calendar_bp.route('/events/<event_id>', methods=['DELETE'])
def calendar_delete_event(event_id):
    return jsonify(calendar_skill.delete_event(event_id))

@calendar_bp.route('/today', methods=['GET'])
def calendar_today():
    return jsonify(calendar_skill.get_today())

@calendar_bp.route('/upcoming', methods=['GET'])
def calendar_upcoming():
    return jsonify(calendar_skill.get_upcoming(request.args.get('hours', 24, type=int)))

@calendar_bp.route('/parse', methods=['POST'])
def calendar_parse():
    return jsonify(calendar_skill.parse_natural_date(request.get_json().get('text', '')))

@calendar_bp.route('/export', methods=['GET'])
def calendar_export():
    ics = calendar_skill.export_to_ics()
    return Response(ics, mimetype='text/calendar', headers={'Content-Disposition': 'attachment; filename=iris_calendar.ics'})
