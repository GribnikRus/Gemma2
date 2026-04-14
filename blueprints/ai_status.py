"""
Blueprint для проверки статуса AI моделей
Endpoints: /api/ai/status, /api/ai/health
"""
import logging
import requests
from flask import Blueprint, jsonify

from config import OLLAMA_URL, OLLAMA_MODEL_CHAT, OLLAMA_MODEL_VISION, OLLAMA_TIMEOUT
from .utils import login_required

logger = logging.getLogger("app")

ai_status_bp = Blueprint('ai_status', __name__, url_prefix='/api/ai')


@ai_status_bp.route('/status', methods=['GET'])
@login_required
def get_ai_status():
    """Проверка доступности Ollama и моделей (прямой запрос к API)"""
    try:
        host = OLLAMA_URL.rstrip('/')
        
        # Прямой запрос к Ollama API
        response = requests.get(f"{host}/api/tags", timeout=10)
        
        if response.ok:
            models = response.json().get('models', [])
            
            # Проверяем наличие конкретных моделей
            def is_model_present(model_name):
                return any(
                    m['name'] == model_name or m['name'].startswith(f"{model_name}:")
                    for m in models
                )
            
            chat_available = is_model_present(OLLAMA_MODEL_CHAT)
            vision_available = (
                is_model_present(OLLAMA_MODEL_VISION) 
                if OLLAMA_MODEL_VISION != OLLAMA_MODEL_CHAT 
                else chat_available
            )
            
            return jsonify({
                'available': chat_available,  # для обратной совместимости
                'chat_model': {
                    'name': OLLAMA_MODEL_CHAT,
                    'available': chat_available
                },
                'vision_model': {
                    'name': OLLAMA_MODEL_VISION,
                    'available': vision_available
                },
                'ollama_url': host,
                'models_count': len(models)
            })
        
        return jsonify({
            'available': False, 
            'error': f'Ollama API error: {response.status_code}'
        }), 502
        
    except requests.exceptions.Timeout:
        return jsonify({
            'available': False, 
            'error': f'Timeout ({OLLAMA_TIMEOUT}s)'
        }), 504
    except Exception as e:
        logger.error(f"Error checking AI status: {e}", exc_info=True)
        return jsonify({
            'available': False,
            'error': str(e)
        }), 503


@ai_status_bp.route('/health', methods=['GET'])
def simple_health():
    """Простая проверка: отвечает ли Ollama сервер (без аутентификации)"""
    try:
        host = OLLAMA_URL.rstrip('/')
        response = requests.get(f"{host}/api/tags", timeout=5)
        
        return jsonify({
            'status': 'ok' if response.ok else 'degraded',
            'ollama_responding': response.ok,
            'status_code': response.status_code
        })
    except Exception as e:
        return jsonify({
            'status': 'error',
            'error': str(e)
        }), 503