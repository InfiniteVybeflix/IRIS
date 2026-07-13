"""IRIS v1 Sports Routes"""
from flask import Blueprint, request, jsonify
from modules.sports_module import sports_module

sports_bp = Blueprint('sports', __name__, url_prefix='/api/sports')

@sports_bp.route('/live', methods=['GET'])
def sports_live():
    return jsonify(sports_module.get_live_matches(request.args.get('league_id', type=int)))

@sports_bp.route('/odds', methods=['GET'])
def sports_odds():
    return jsonify(sports_module.get_odds(request.args.get('sport', 'soccer'), request.args.get('region', 'us')))

@sports_bp.route('/team-stats', methods=['GET'])
def sports_team_stats():
    team_id = request.args.get('team_id', type=int)
    league_id = request.args.get('league_id', type=int)
    if not team_id or not league_id:
        return jsonify({"success": False, "error": "team_id and league_id required"}), 400
    return jsonify(sports_module.get_team_stats(team_id, league_id, request.args.get('season', 2024, type=int)))

@sports_bp.route('/summary', methods=['GET'])
def sports_summary():
    return jsonify({"success": True, "summary": sports_module.get_live_summary()})
