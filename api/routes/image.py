"""IRIS v1 Image Routes — Processing + Generation (Aevibron Imagine)"""
from flask import Blueprint, request, jsonify
from modules.image_module import image_module
from modules.image_generation import image_generation

image_bp = Blueprint('image', __name__, url_prefix='/api/image')

# ─── Processing ───
@image_bp.route('/remove-bg', methods=['POST'])
def image_remove_bg():
    data = request.get_json() or {}
    if not data.get('image_path'):
        return jsonify({"success": False, "error": "image_path required"}), 400
    return jsonify(image_module.remove_background(data['image_path'], data.get('output_path')))

@image_bp.route('/remove-bg-base64', methods=['POST'])
def image_remove_bg_base64():
    data = request.get_json() or {}
    if not data.get('image_base64'):
        return jsonify({"success": False, "error": "image_base64 required"}), 400
    return jsonify(image_module.remove_background_base64(data['image_base64']))

@image_bp.route('/resize', methods=['POST'])
def image_resize():
    data = request.get_json() or {}
    if not data.get('image_path') or not data.get('width') or not data.get('height'):
        return jsonify({"success": False, "error": "image_path, width, and height required"}), 400
    return jsonify(image_module.resize_image(data['image_path'], data['width'], data['height']))

@image_bp.route('/convert', methods=['POST'])
def image_convert():
    data = request.get_json() or {}
    if not data.get('image_path'):
        return jsonify({"success": False, "error": "image_path required"}), 400
    return jsonify(image_module.convert_format(data['image_path'], data.get('format', 'png')))

# ─── Aevibron Imagine Generation ───
@image_bp.route('/generate', methods=['POST'])
def image_generate():
    """Generate images using Aevibron Imagine V1 or Flash."""
    data = request.get_json() or {}
    prompt = data.get('prompt', '')
    if not prompt:
        return jsonify({"success": False, "error": "prompt required"}), 400
    result = image_generation.generate(
        prompt=prompt,
        model=data.get('model', 'imagine_v1'),
        size=data.get('size', '1024x1024'),
        quality=data.get('quality', 'standard'),
        style=data.get('style', 'vivid'),
        n=data.get('n', 1),
        response_format=data.get('response_format', 'url')
    )
    return jsonify(result)

@image_bp.route('/generate/quick', methods=['POST'])
def image_generate_quick():
    """Quick generate with sensible defaults."""
    data = request.get_json() or {}
    if not data.get('prompt'):
        return jsonify({"success": False, "error": "prompt required"}), 400
    return jsonify(image_generation.quick_generate(data['prompt'], fast=data.get('fast', False)))

@image_bp.route('/generate/variation', methods=['POST'])
def image_generate_variation():
    """Generate variations of an existing image."""
    data = request.get_json() or {}
    if not data.get('image_path'):
        return jsonify({"success": False, "error": "image_path required"}), 400
    return jsonify(image_generation.generate_variation(
        data['image_path'], data.get('n', 1), data.get('size', '1024x1024')
    ))

@image_bp.route('/generate/edit', methods=['POST'])
def image_generate_edit():
    """Edit an image with mask and prompt."""
    data = request.get_json() or {}
    if not data.get('image_path') or not data.get('mask_path') or not data.get('prompt'):
        return jsonify({"success": False, "error": "image_path, mask_path, and prompt required"}), 400
    return jsonify(image_generation.edit_image(
        data['image_path'], data['mask_path'], data['prompt'],
        data.get('n', 1), data.get('size', '1024x1024')
    ))
