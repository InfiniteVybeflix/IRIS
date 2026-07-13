"""IRIS v1 Notes Routes"""
from flask import Blueprint, request, jsonify
from skills.notes_skill import notes_skill

notes_bp = Blueprint('notes', __name__, url_prefix='/api/notes')

@notes_bp.route('', methods=['GET'])
def notes_get():
    return jsonify(notes_skill.get_notes(request.args.get('category'), request.args.get('search')))

@notes_bp.route('', methods=['POST'])
def notes_create():
    data = request.get_json() or {}
    if not data.get('title'):
        return jsonify({"success": False, "error": "Title required"}), 400
    return jsonify(notes_skill.create_note(
        title=data['title'],
        content=data.get('content', ''),
        category=data.get('category', 'general'),
        tags=data.get('tags', [])
    ))

@notes_bp.route('/<note_id>', methods=['GET'])
def notes_get_one(note_id):
    return jsonify(notes_skill.get_note(note_id))

@notes_bp.route('/<note_id>', methods=['PUT'])
def notes_update(note_id):
    data = request.get_json() or {}
    return jsonify(notes_skill.update_note(
        note_id=note_id,
        title=data.get('title'),
        content=data.get('content'),
        category=data.get('category'),
        tags=data.get('tags')
    ))

@notes_bp.route('/<note_id>', methods=['DELETE'])
def notes_delete(note_id):
    return jsonify(notes_skill.delete_note(note_id))

@notes_bp.route('/<note_id>/pin', methods=['POST'])
def notes_pin(note_id):
    return jsonify(notes_skill.pin_note(note_id, request.get_json().get('pinned', True)))

@notes_bp.route('/quick', methods=['POST'])
def notes_quick():
    return jsonify(notes_skill.quick_note(request.get_json().get('text', '')))
