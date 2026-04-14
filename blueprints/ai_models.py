"""
Модуль управления моделями Ollama: список, выбор, статус.
Endpoints: /api/ai/models, /api/ai/models/set, /api/ai/status
"""
import logging
from flask import Blueprint, request, jsonify

from ollama_client import OllamaClient
from .utils import login_required

logger = logging.getLogger("app")

ai_models_bp = Blueprint('ai_models', __name__, url_prefix='/api/ai')
ollama = OllamaClient()


@ai_models_bp.route('/models', methods=['GET'])
@login_required
def list_models():
    """Список доступных моделей"""
    try:
        models = ollama.get_available_models()
        return jsonify({
            'available': True,
            'current_chat_model': ollama.model_chat,
            'current_vision_model': ollama.model_vision,
            'models': models
        })
    except Exception as e:
        logger.error(f"Failed to list models: {e}")
        return jsonify({'available': False, 'error': str(e)}), 500


@ai_models_bp.route('/models/set', methods=['POST'])
@login_required
def set_model():
    """Смена активной модели"""
    data = request.get_json()
    model_name = data.get('model')
    for_vision = data.get('for_vision', False)
    
    if not model_name:
        return jsonify({'error': 'Укажите название модели'}), 400
    
    try:
        success = ollama.set_model(model_name, for_vision=for_vision)
        if success:
            logger.info(f"Model changed: {model_name} (vision={for_vision})")
            return jsonify({
                'success': True,
                'message': f'Модель: {model_name}',
                'chat_model': ollama.model_chat,
                'vision_model': ollama.model_vision
            })
        return jsonify({'error': f'Модель {model_name} не найдена'}), 404
    except Exception as e:
        logger.error(f"Error setting model: {e}")
        return jsonify({'error': str(e)}), 500


@ai_models_bp.route('/status', methods=['GET'])
@login_required
def get_status():
    """Статус Ollama"""
    try:
        return jsonify({
            'available': ollama.is_model_available(ollama.model_chat),
            'host': ollama.host,
            'chat_model': ollama.model_chat,
            'vision_model': ollama.model_vision,
            'timeout': ollama.timeout
        })
    except Exception as e:
        return jsonify({'available': False, 'error': str(e)}), 500