"""
Модуль ИИ-наблюдателя: анализ чатов, роли.
Все endpoints с префиксом /api/group/observe
"""
import logging
from flask import Blueprint, request, jsonify

from db import (
    SessionLocal, is_client_member_of_group, get_group_history,
    create_observer_session, add_observer_analysis
)
from ollama_client import OllamaClient
from .utils import login_required

logger = logging.getLogger("app")

observer_bp = Blueprint('observer', __name__, url_prefix='/api')

ollama = OllamaClient()


@observer_bp.route('/group/observe', methods=['POST'])
@login_required
def start_observer():
    """Запустить анализ чата наблюдателем"""
    from flask import session
    data = request.get_json()
    group_id = data.get('group_id')
    role_prompt = data.get('role_prompt', 'Ты аналитик. Проанализируй диалог.')
    analysis_type = data.get('analysis_type', 'quick')  # quick или full

    if not group_id:
        return jsonify({'error': 'ID группы обязателен'}), 400

    db = SessionLocal()
    try:
        if not is_client_member_of_group(db, session['client_id'], group_id):
            return jsonify({'error': 'Нет доступа к группе'}), 403

        # Получаем сообщения
        limit = 100 if analysis_type == 'full' else 10
        messages = get_group_history(db, group_id, session['client_id'], limit=limit)

        if not messages:
            return jsonify({'error': 'Нет сообщений для анализа'}), 400

        # Форматируем для анализа
        formatted_messages = [
            {'sender': m.sender.login if m.sender else 'Gemma AI', 'content': m.content}
            for m in messages
        ]

        # Создаем сессию наблюдателя
        observer_session = create_observer_session(
            db, group_id, session['client_id'], role_prompt, analysis_type
        )

        # Вызываем Ollama для анализа через специализированный метод
        ai_analysis = ollama.analyze_chat_as_observer(formatted_messages, role_prompt, analysis_type)

        # Сохраняем результат
        analysis = add_observer_analysis(
            db, observer_session.id, ai_analysis, len(messages)
        )

        logger.info(f"Observer analysis completed for group {group_id}, type={analysis_type}")

        return jsonify({
            'session_id': observer_session.id,
            'analysis': ai_analysis,
            'messages_analyzed': len(messages),
            'analysis_type': analysis_type
        })

    except Exception as e:
        logger.error(f"Observer analysis failed: {str(e)}")
        return jsonify({'error': str(e)}), 500
    finally:
        db.close()
