"""IRIS v1 Project Generator Routes"""
from flask import Blueprint, request, jsonify
from api.utils.rate_limiter import rate_limit
from modules.project_generator import project_generator

projects_bp = Blueprint('projects', __name__, url_prefix='/api/projects')

@projects_bp.route('/generate', methods=['POST'])
@rate_limit
def projects_generate():
    data = request.get_json() or {}
    if not data.get('name'):
        return jsonify({"success": False, "error": "Project name required"}), 400
    return jsonify(project_generator.generate_project(data['name'], data.get('template', 'nextjs'), data.get('description', '')))

@projects_bp.route('/deploy', methods=['POST'])
@rate_limit
def projects_deploy():
    data = request.get_json() or {}
    if not data.get('name'):
        return jsonify({"success": False, "error": "Project name required"}), 400
    return jsonify(project_generator.deploy_project(data['name'], data.get('repo_name'), data.get('deploy_to_vercel', True)))

@projects_bp.route('', methods=['GET'])
def projects_list():
    return jsonify({"success": True, "projects": project_generator.get_projects()})

@projects_bp.route('/templates', methods=['GET'])
def projects_templates():
    return jsonify({"success": True, "templates": project_generator.get_available_templates()})
