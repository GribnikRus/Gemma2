"""
Модуль личных чатов: создание, история, отправка сообщений.
Все endpoints с префиксом /api/chat/personal
"""
import logging
from flask import Blueprint, request, jsonify

from db import (
    SessionLocal, create_personal_chat, get_personal_chat as get_personal_chat_from_db,
    get_personal_chat_history, add_message, get_client_by_id, get_personal_chat_by_id,
    PersonalChat
)
from ollama_client import OllamaClient
from .utils import hash_password_sha256, verify_password_sha256, login_required, get_current_client, is_ai_triggered

logger = logging.getLogger("app")

chat_personal_bp = Blueprint('chat_personal', __name__, url_prefix='/api/chat')

ollama = OllamaClient()


@chat_personal_bp.route('/personal/create', methods=['POST'])
@login_required
def create_personal_chat_route():
    """Создать новый личный чат"""
    from flask import session
    data = request.get_json()
    title = data.get('title', 'Новый чат')
    
    db = SessionLocal()
    try:
        chat = create_personal_chat(db, session['client_id'], title)
        return jsonify({
            'id': chat.id,
            'title': chat.title,
            'created_at': chat.created_at.isoformat()
        }), 201
    finally:
        db.close()


@chat_personal_bp.route('/personal/<int:chat_id>', methods=['GET'])
@login_required
def get_personal_chat(chat_id: int):
    """Получить личный чат с историей"""
    from flask import session
    db = SessionLocal()
    try:
        chat = get_personal_chat_from_db(db, chat_id, session['client_id'])
        if not chat:
            return jsonify({'error': 'Чат не найден'}), 404
        
        messages = get_personal_chat_history(db, chat_id, session['client_id'], limit=100)
        
        return jsonify({
            'chat': {
                'id': chat.id,
                'title': chat.title,
                'created_at': chat.created_at.isoformat(),
                'ai_enabled': chat.ai_enabled
            },
            'messages': [{
                'id': m.id,
                'content': m.content,
                'sender_type': m.sender_type,
                'sender_name': m.sender.login if m.sender else 'Gemma AI',
                'created_at': m.created_at.isoformat()
            } for m in messages]
        })
    finally:
        db.close()


@chat_personal_bp.route('/send', methods=['POST'])
@login_required
def send_message():
    """Отправить сообщение в личный или групповой чат"""
    from flask import session
    client_ip = request.remote_addr
    client_id = session.get('client_id')
    logger.info(f"POST /api/chat/send from {client_ip} (client_id={client_id})")
    
    data = request.get_json()
    content = data.get('content', '').strip()
    personal_chat_id = data.get('personal_chat_id')
    group_id = data.get('group_id')
    
    if not content:
        logger.warning(f"Empty message content from {client_ip}")
        return jsonify({'error': 'Сообщение не может быть пустым'}), 400
    
    db = SessionLocal()
    try:
        # Определяем тип чата
        if personal_chat_id:
            # Личный чат
            chat = get_personal_chat_from_db(db, personal_chat_id, session['client_id'])
            if not chat:
                logger.warning(f"Personal chat {personal_chat_id} not found for client {client_id}")
                return jsonify({'error': 'Чат не найден'}), 404
            
            # Добавляем сообщение пользователя
            user_msg = add_message(
                db, content, 'client', session['client_id'],
                personal_chat_id=personal_chat_id, message_type='text'
            )
            
            # Проверяем флаг ai_enabled и триггер обращения к ИИ
            ai_message = None
            if chat.ai_enabled and is_ai_triggered(content, chat.ai_name or "Гемма"):
                # Получаем историю для контекста
                history = get_personal_chat_history(db, personal_chat_id, session['client_id'], limit=20)
                context = "\n".join([f"{m.sender_type}: {m.content}" for m in history])
                
                # Отправляем в Ollama
                ai_response = ollama.chat(
                    message=f"{context}\nUser: {content}",
                    system_prompt=f"Ты полезный ассистент. Тебя зовут {chat.ai_name or 'Гемма'}. Отвечай кратко и по делу."
                )
                
                # Добавляем ответ ИИ
                ai_msg = add_message(
                    db, ai_response, 'ai', None,
                    personal_chat_id=personal_chat_id, message_type='text'
                )
                ai_message = {
                    'id': ai_msg.id,
                    'content': ai_msg.content,
                    'sender_type': ai_msg.sender_type,
                    'sender_name': chat.ai_name or 'Гемма',
                    'created_at': ai_msg.created_at.isoformat()
                }
            
            logger.info(f"Message sent to personal chat {personal_chat_id}, status=200")
            
            # Получаем имя отправителя для user_message
            user_client = get_client_by_id(db, session['client_id'])
            result = {
                'user_message': {
                    'id': user_msg.id,
                    'content': user_msg.content,
                    'sender_type': user_msg.sender_type,
                    'sender_name': user_client.login if user_client else 'Unknown',
                    'created_at': user_msg.created_at.isoformat()
                }
            }
            if ai_message:
                result['ai_message'] = ai_message
            return jsonify(result)
        
        elif group_id:
            # Групповой чат - обрабатывается в chat_group модуле
            # Этот код остается здесь для обратной совместимости
            from db import is_client_member_of_group, get_group_by_id, get_group_history
            
            if not is_client_member_of_group(db, session['client_id'], group_id):
                logger.warning(f"Client {client_id} not member of group {group_id}")
                return jsonify({'error': 'Нет доступа к группе'}), 403

            # Получаем группу для проверки ai_enabled
            group = get_group_by_id(db, group_id)

            # Добавляем сообщение пользователя
            user_msg = add_message(
                db, content, 'client', session['client_id'],
                group_id=group_id, message_type='text'
            )

            # Проверяем флаг ai_enabled и триггер обращения к ИИ
            ai_message = None
            if group and group.ai_enabled and is_ai_triggered(content, group.ai_name or "Гемма"):
                # Получаем историю для контекста
                history = get_group_history(db, group_id, session['client_id'], limit=20)
                context = "\n".join([f"{m.sender_type}: {m.content}" for m in history])

                # Отправляем в Ollama
                ai_response = ollama.chat(
                    message=f"{context}\nUser: {content}",
                    system_prompt=f"Ты полезный ассистент в групповом чате. Тебя зовут {group.ai_name or 'Гемма'}. Отвечай кратко и по делу."
                )

                # Добавляем ответ ИИ
                ai_msg = add_message(
                    db, ai_response, 'ai', None,
                    group_id=group_id, message_type='text'
                )
                ai_message = {
                    'id': ai_msg.id,
                    'content': ai_msg.content,
                    'sender_type': ai_msg.sender_type,
                    'sender_name': group.ai_name or 'Гемма',
                    'created_at': ai_msg.created_at.isoformat()
                }

            logger.info(f"Message sent to group {group_id}, status=200")
            
            # Получаем имя отправителя для user_message
            user_client = get_client_by_id(db, session['client_id'])
            result = {
                'user_message': {
                    'id': user_msg.id,
                    'content': user_msg.content,
                    'sender_type': user_msg.sender_type,
                    'sender_name': user_client.login if user_client else 'Unknown',
                    'created_at': user_msg.created_at.isoformat()
                }
            }
            if ai_message:
                result['ai_message'] = ai_message
            return jsonify(result)
        
        else:
            return jsonify({'error': 'Необходимо указать personal_chat_id или group_id'}), 400
            
    except Exception as e:
        db.rollback()
        logger.error(f"Error sending message: {str(e)}")
        return jsonify({'error': str(e)}), 500
    finally:
        db.close()


@chat_personal_bp.route('/<int:chat_id>/history', methods=['GET'])
@login_required
def get_chat_history_updates(chat_id: int):
    """Получить новые сообщения для чата (для polling)"""
    from flask import session
    from db import is_client_member_of_group
    chat_type = request.args.get('type', 'personal')
    last_message_id = request.args.get('last_message_id', type=int)
    limit = request.args.get('limit', default=50, type=int)

    db = SessionLocal()
    try:
        if chat_type == 'personal':
            chat = get_personal_chat_from_db(db, chat_id, session['client_id'])
            if not chat:
                return jsonify({'error': 'Чат не найден'}), 404

            messages = get_personal_chat_history(db, chat_id, session['client_id'], limit=limit, last_message_id=last_message_id)
        else:  # group
            if not is_client_member_of_group(db, session['client_id'], chat_id):
                return jsonify({'error': 'Нет доступа к группе'}), 403

            messages = get_group_history(db, chat_id, session['client_id'], limit=limit, last_message_id=last_message_id)

        return jsonify({
            'messages': [{
                'id': m.id,
                'content': m.content,
                'sender_type': m.sender_type,
                'sender_name': m.sender.login if m.sender else 'Gemma AI',
                'created_at': m.created_at.isoformat()
            } for m in messages]
        })
    finally:
        db.close()


@chat_personal_bp.route('/toggle_ai', methods=['POST'])
@login_required
def toggle_ai():
    """Переключить флаг ai_enabled для чата"""
    from flask import session
    data = request.get_json()
    chat_type = data.get('chat_type')  # 'personal' или 'group'
    chat_id = data.get('chat_id')

    if not chat_type or not chat_id:
        return jsonify({'error': 'Необходимо указать chat_type и chat_id'}), 400

    db = SessionLocal()
    try:
        chat = None

        # Ищем чат в зависимости от типа
        if chat_type == 'personal':
            chat = db.query(PersonalChat).filter(
                PersonalChat.id == chat_id,
                PersonalChat.owner_id == session['client_id']
            ).first()
        elif chat_type == 'group':
            from db import is_client_member_of_group, ChatGroup
            # Проверяем членство в группе
            if not is_client_member_of_group(db, session['client_id'], chat_id):
                return jsonify({'error': 'Нет доступа к группе'}), 403
            chat = db.query(ChatGroup).filter(
                ChatGroup.id == chat_id
            ).first()

        if not chat:
            return jsonify({'error': 'Чат не найден или нет прав'}), 404

        # Переключаем значение
        chat.ai_enabled = not chat.ai_enabled
        db.commit()

        logger.info(f"AI toggled to {chat.ai_enabled} for {chat_type} #{chat_id}")
        return jsonify({'ai_enabled': chat.ai_enabled})

    except Exception as e:
        db.rollback()
        logger.error(f"Error toggling AI: {e}")
        return jsonify({'error': str(e)}), 500
    finally:
        db.close()


@chat_personal_bp.route('/set_ai_name', methods=['POST'])
@login_required
def set_ai_name_route():
    """Установить новое имя ИИ для чата"""
    from flask import session, current_app
    data = request.get_json()
    chat_type = data.get('chat_type')  # 'personal' или 'group'
    chat_id = data.get('chat_id')
    new_name = data.get('new_name', '').strip()

    if not chat_type or not chat_id:
        return jsonify({'error': 'Необходимо указать chat_type и chat_id'}), 400

    if not new_name or len(new_name) < 2:
        return jsonify({'error': 'Имя должно содержать минимум 2 символа'}), 400

    db = SessionLocal()
    try:
        chat = None

        # Проверяем права доступа
        if chat_type == 'personal':
            chat = db.query(PersonalChat).filter(
                PersonalChat.id == chat_id,
                PersonalChat.owner_id == session['client_id']
            ).first()
            if not chat:
                return jsonify({'error': 'Чат не найден или нет прав'}), 404
        elif chat_type == 'group':
            from db import is_client_member_of_group, ChatGroup
            # Проверяем членство в группе
            if not is_client_member_of_group(db, session['client_id'], chat_id):
                return jsonify({'error': 'Нет доступа к группе'}), 403
            chat = db.query(ChatGroup).filter(
                ChatGroup.id == chat_id
            ).first()
            if not chat:
                return jsonify({'error': 'Группа не найдена'}), 404
        else:
            return jsonify({'error': 'Неверный тип чата'}), 400

        # Устанавливаем новое имя через helper функцию
        from db import set_chat_ai_name
        success = set_chat_ai_name(db, chat_type, chat_id, new_name)

        if not success:
            return jsonify({'error': 'Не удалось установить имя. Проверьте корректность.'}), 500

        logger.info(f"AI name set to '{new_name}' for {chat_type} #{chat_id}")

        # Отправляем событие всем участникам чата через WebSocket
        socketio = current_app.extensions['socketio']
        room_name = f'{chat_type}_{chat_id}'
        socketio.emit('ai_name_changed', {
            'chat_type': chat_type,
            'chat_id': chat_id,
            'new_name': new_name
        }, room=room_name)

        return jsonify({
            'message': f'Имя ассистента изменено на {new_name}',
            'ai_name': new_name
        })

    except Exception as e:
        db.rollback()
        logger.error(f"Error setting AI name: {e}")
        return jsonify({'error': str(e)}), 500
    finally:
        db.close()


@chat_personal_bp.route('/observe', methods=['POST'])
@login_required
def observe_personal_chat():
    """ИИ-анализатор для личных чатов (режим Наблюдатель)"""
    from flask import session
    data = request.get_json()
    personal_chat_id = data.get('personal_chat_id')
    role_prompt = data.get('role_prompt', 'Ты полезный аналитик. Проанализируй диалог.')
    analysis_type = data.get('analysis_type', 'quick')

    if not personal_chat_id:
        return jsonify({'error': 'Необходимо указать personal_chat_id'}), 400

    db = SessionLocal()
    try:
        chat = get_personal_chat_by_id(db, personal_chat_id)
        if not chat or chat.owner_id != session['client_id']:
            return jsonify({'error': 'Чат не найден'}), 404

        # Получаем историю сообщений
        limit = 10 if analysis_type == 'quick' else 100
        history = get_personal_chat_history(db, personal_chat_id, session['client_id'], limit=limit)

        if not history:
            return jsonify({'result': 'Нет сообщений для анализа'})

        # Формируем контекст
        context = "\n".join([f"{m.sender_type}: {m.content}" for m in history])

        # Отправляем в Ollama
        system_prompt = f"{role_prompt} Анализируй последние {len(history)} сообщений."
        ai_response = ollama.chat(
            message=f"{context}\n\nАнализ:",
            system_prompt=system_prompt
        )

        logger.info(f"Observer analysis completed for personal chat {personal_chat_id}")
        return jsonify({'result': ai_response, 'messages_analyzed': len(history)})
    finally:
        db.close()
