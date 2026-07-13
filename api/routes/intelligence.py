"""IRIS v1 Intelligence Routes — Web Search, NL2Code, Vision AI, Auto-Debug"""
from flask import Blueprint, request, jsonify
from api.utils.rate_limiter import rate_limit
from modules.web_search import web_search
from modules.nl2code import nl2code
from modules.vision_ai import vision_ai
from modules.auto_debug import auto_debug

intelligence_bp = Blueprint('intelligence', __name__, url_prefix='/api/intelligence')

# ─── Web Search ───
@intelligence_bp.route('/search', methods=['POST'])
@rate_limit
def intelligence_search():
    data = request.get_json() or {}
    query = data.get('query', '')
    if not query:
        return jsonify({"success": False, "error": "query required"}), 400
    result = web_search.search(
        query=query,
        max_results=data.get('max_results', 5),
        fetch_content=data.get('fetch_content', True),
        source_filter=data.get('source_filter'),
        time_filter=data.get('time_filter')
    )
    return jsonify(result)

@intelligence_bp.route('/search/news', methods=['POST'])
@rate_limit
def intelligence_search_news():
    data = request.get_json() or {}
    if not data.get('query'):
        return jsonify({"success": False, "error": "query required"}), 400
    return jsonify(web_search.search_news(data['query'], data.get('max_results', 5)))

@intelligence_bp.route('/search/code', methods=['POST'])
@rate_limit
def intelligence_search_code():
    data = request.get_json() or {}
    if not data.get('query'):
        return jsonify({"success": False, "error": "query required"}), 400
    return jsonify(web_search.search_code(data['query'], data.get('language'), data.get('max_results', 5)))

@intelligence_bp.route('/search/summarize', methods=['POST'])
@rate_limit
def intelligence_search_summarize():
    data = request.get_json() or {}
    if not data.get('query'):
        return jsonify({"success": False, "error": "query required"}), 400
    search_result = web_search.search(data['query'], data.get('max_results', 5))
    summary = web_search.summarize_results(search_result, data.get('max_length', 500))
    return jsonify({"success": True, "summary": summary, "raw_results": search_result})

@intelligence_bp.route('/search/history', methods=['GET'])
def intelligence_search_history():
    return jsonify({"success": True, "history": web_search.get_search_history(request.args.get('limit', 10, type=int))})

# ─── NL2Code ───
@intelligence_bp.route('/nl2code/function', methods=['POST'])
@rate_limit
def intelligence_nl2code_function():
    data = request.get_json() or {}
    if not data.get('description'):
        return jsonify({"success": False, "error": "description required"}), 400
    return jsonify(nl2code.generate_function(
        description=data['description'],
        language=data.get('language', 'python'),
        inputs=data.get('inputs'),
        outputs=data.get('outputs'),
        constraints=data.get('constraints')
    ))

@intelligence_bp.route('/nl2code/project', methods=['POST'])
@rate_limit
def intelligence_nl2code_project():
    data = request.get_json() or {}
    if not data.get('requirements'):
        return jsonify({"success": False, "error": "requirements required"}), 400
    return jsonify(nl2code.generate_project(data['requirements'], data.get('tech_stack', 'nextjs')))

@intelligence_bp.route('/nl2code/api-client', methods=['POST'])
@rate_limit
def intelligence_nl2code_api_client():
    data = request.get_json() or {}
    if not data.get('api_spec'):
        return jsonify({"success": False, "error": "api_spec required"}), 400
    return jsonify(nl2code.generate_api_client(data['api_spec'], data.get('language', 'python')))

@intelligence_bp.route('/nl2code/fix', methods=['POST'])
@rate_limit
def intelligence_nl2code_fix():
    data = request.get_json() or {}
    if not data.get('bug_description') or not data.get('code'):
        return jsonify({"success": False, "error": "bug_description and code required"}), 400
    return jsonify(nl2code.fix_bug(data['bug_description'], data['code'], data.get('language', 'python')))

@intelligence_bp.route('/nl2code/explain', methods=['POST'])
@rate_limit
def intelligence_nl2code_explain():
    data = request.get_json() or {}
    if not data.get('code'):
        return jsonify({"success": False, "error": "code required"}), 400
    return jsonify(nl2code.explain_code(data['code'], data.get('language', 'python')))

# ─── Vision AI ───
@intelligence_bp.route('/vision/analyze', methods=['POST'])
@rate_limit
def intelligence_vision_analyze():
    data = request.get_json() or {}
    if not data.get('image_path') and not data.get('image_base64'):
        return jsonify({"success": False, "error": "image_path or image_base64 required"}), 400
    return jsonify(vision_ai.analyze_image(
        image_path=data.get('image_path'),
        image_base64=data.get('image_base64'),
        question=data.get('question', 'What do you see?'),
        detail=data.get('detail', 'high')
    ))

@intelligence_bp.route('/vision/screenshot', methods=['POST'])
@rate_limit
def intelligence_vision_screenshot():
    data = request.get_json() or {}
    if not data.get('image_path') and not data.get('image_base64'):
        return jsonify({"success": False, "error": "image_path or image_base64 required"}), 400
    return jsonify(vision_ai.describe_screenshot(data.get('image_path'), data.get('image_base64')))

@intelligence_bp.route('/vision/extract-code', methods=['POST'])
@rate_limit
def intelligence_vision_extract_code():
    data = request.get_json() or {}
    if not data.get('image_path') and not data.get('image_base64'):
        return jsonify({"success": False, "error": "image_path or image_base64 required"}), 400
    return jsonify(vision_ai.extract_code_from_image(data.get('image_path'), data.get('image_base64')))

@intelligence_bp.route('/vision/ui-issues', methods=['POST'])
@rate_limit
def intelligence_vision_ui_issues():
    data = request.get_json() or {}
    if not data.get('image_path') and not data.get('image_base64'):
        return jsonify({"success": False, "error": "image_path or image_base64 required"}), 400
    return jsonify(vision_ai.detect_ui_issues(data.get('image_path'), data.get('image_base64')))

@intelligence_bp.route('/vision/describe', methods=['POST'])
@rate_limit
def intelligence_vision_describe():
    data = request.get_json() or {}
    if not data.get('image_path') and not data.get('image_base64'):
        return jsonify({"success": False, "error": "image_path or image_base64 required"}), 400
    return jsonify(vision_ai.generate_image_description(
        data.get('image_path'), data.get('image_base64'), data.get('style', 'detailed')
    ))

# ─── Auto-Debug ───
@intelligence_bp.route('/debug/analyze', methods=['POST'])
@rate_limit
def intelligence_debug_analyze():
    data = request.get_json() or {}
    error_message = data.get('error_message', '')

    class ReconstructedError(Exception):
        pass

    try:
        exc = ReconstructedError(error_message)
        result = auto_debug.analyze_error(
            exc, 
            code=data.get('code'), 
            context=data.get('context', '')
        )
        return jsonify(result)
    except Exception as e:
        return jsonify({"success": False, "error": str(e)})

@intelligence_bp.route('/debug/stats', methods=['GET'])
def intelligence_debug_stats():
    return jsonify({"success": True, **auto_debug.get_error_stats()})
