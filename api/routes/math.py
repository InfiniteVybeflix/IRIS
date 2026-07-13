"""IRIS v1 Math Routes"""
from flask import Blueprint, request, jsonify
from skills.math_skill import math_skill

math_bp = Blueprint('math', __name__, url_prefix='/api/math')

@math_bp.route('/solve', methods=['POST'])
def math_solve():
    data = request.get_json() or {}
    return jsonify(math_skill.solve(data.get('expression', ''), data.get('variable', 'x')))

@math_bp.route('/simplify', methods=['POST'])
def math_simplify():
    return jsonify(math_skill.simplify(request.get_json().get('expression', '')))

@math_bp.route('/differentiate', methods=['POST'])
def math_differentiate():
    data = request.get_json() or {}
    return jsonify(math_skill.differentiate(data.get('expression', ''), data.get('variable', 'x'), data.get('order', 1)))

@math_bp.route('/integrate', methods=['POST'])
def math_integrate():
    data = request.get_json() or {}
    return jsonify(math_skill.integrate(data.get('expression', ''), data.get('variable', 'x'), data.get('limits')))

@math_bp.route('/evaluate', methods=['POST'])
def math_evaluate():
    return jsonify(math_skill.evaluate(request.get_json().get('expression', '')))

@math_bp.route('/statistics', methods=['POST'])
def math_statistics():
    data = request.get_json() or {}
    return jsonify(math_skill.statistics(data.get('values', []), data.get('operation', 'all')))

@math_bp.route('/convert', methods=['POST'])
def math_convert():
    data = request.get_json() or {}
    return jsonify(math_skill.convert_units(data.get('value', 0), data.get('from', ''), data.get('to', '')))
