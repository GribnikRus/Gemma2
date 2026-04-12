"""
WebSocket события: connect, disconnect, join_group, join_personal, send_message.
Все обработчики @socketio.on(...) вынесены в этот модуль.
"""
import logging
from flask import session
from flask_socketio import emit, join_room

from db import (
    SessionLocal, update_user_online_status, is_client_member_of_group,
    get_personal_chat as get_personal_chat_from_db, get_personal_chat_history,
    add_message, get_client_by_id, get_group_by_id, get_group_history
)
from ollama_client import OllamaClient
from .utils import is_ai_triggered

logger = logging.getLogger("app")

ollama = OllamaClient()


def register_websocket_events(socketio):
    """Регистрирует все WebSocket обработчики событий"""
    
    @socketio.on('connect')
    def handle_connect():
        """Обработка подключения клиента"""
        client_id = session.get('client_id')
        if client_id:
            # Добавляем пользователя в личную комнату
            join_room(f'user_{client_id}')
            logger.info(f"Client {client_id} connected via WebSocket")

            # Обновляем статус пользователя на online в базе данных
            db = SessionLocal()
            try:
                update_user_online_status(db, client_id, True)
                # Уведомляем всех о том, что пользователь зашел
                socketio.emit('user_joined', {'client_id': client_id}, broadcast=True)
            finally:
                db.close()

            emit('connected', {'message': 'Connected to WebSocket'})
        else:
            logger.warning("WebSocket connection without authenticated session")
            return False  # Отклоняем подключение без авторизации

    @socketio.on('disconnect')
    def handle_disconnect():
        """Обработка отключения клиента"""
        client_id = session.get('client_id')
        if client_id:
            logger.info(f"Client {client_id} disconnected from WebSocket")

            # Обновляем статус пользователя на offline в базе данных
            db = SessionLocal()
            try:
                update_user_online_status(db, client_id, False)
                # Уведомляем всех о том, что пользователь вышел
                socketio.emit('user_left', {'client_id': client_id}, broadcast=True)
            finally:
                db.close()
        # SocketIO автоматически удаляет из комнат при disconnect

    @socketio.on('join_group')
    def handle_join_group(data):
        """Присоединение к комнате группы"""
        client_id = session.get('client_id')
        group_id = data.get('group_id')

        if not client_id or not group_id:
            return

        db = SessionLocal()
        try:
            # Проверяем, является ли клиент участником группы
            if is_client_member_of_group(db, client_id, group_id):
                room_name = f'group_{group_id}'
                join_room(room_name)
                logger.info(f"Client {client_id} joined group room {room_name}")
                emit('joined_group', {'group_id': group_id, 'message': f'Joined group {group_id}'})
            else:
                logger.warning(f"Client {client_id} tried to join group {group_id} but is not a member")
        finally:
            db.close()

    @socketio.on('join_personal')
    def handle_join_personal(data):
        """Присоединение к личному чату (для получения уведомлений)"""
        client_id = session.get('client_id')
        personal_chat_id = data.get('personal_chat_id')

        if not client_id or not personal_chat_id:
            return

        db = SessionLocal()
        try:
            chat = get_personal_chat_from_db(db, personal_chat_id, client_id)
            if chat:
                room_name = f'personal_{personal_chat_id}'
                join_room(room_name)
                logger.info(f"Client {client_id} joined personal chat room {room_name}")
                emit('joined_personal', {'personal_chat_id': personal_chat_id})
        finally:
            db.close()

    @socketio.on('send_message')
    def handle_send_message(data):
        """Обработка отправки сообщения через WebSocket"""
        client_id = session.get('client_id')
        content = data.get('content', '').strip()
        personal_chat_id = data.get('personal_chat_id')
        group_id = data.get('group_id')

        if not content:
            emit('error', {'message': 'Сообщение не может быть пустым'})
            return

        if not client_id:
            emit('error', {'message': 'Требуется авторизация'})
            return

        db = SessionLocal()
        try:
            # Определяем тип чата и сохраняем сообщение
            if personal_chat_id:
                # Личный чат
                chat = get_personal_chat_from_db(db, personal_chat_id, client_id)
                if not chat:
                    emit('error', {'message': 'Чат не найден'})
                    return

                # Добавляем сообщение пользователя
                user_msg = add_message(
                    db, content, 'client', client_id,
                    personal_chat_id=personal_chat_id, message_type='text'
                )

                # Получаем имя отправителя
                user_client = get_client_by_id(db, client_id)
                message_data = {
                    'id': user_msg.id,
                    'content': user_msg.content,
                    'sender_type': user_msg.sender_type,
                    'sender_id': client_id,
                    'sender_name': user_client.login if user_client else 'Unknown',
                    'created_at': user_msg.created_at.isoformat(),
                    'personal_chat_id': personal_chat_id
                }

                # Отправляем сообщение всем в комнате личного чата
                socketio.emit('new_message', message_data, room=f'personal_{personal_chat_id}')

                # Проверяем флаг ai_enabled и триггер обращения к ИИ
                if chat.ai_enabled and is_ai_triggered(content, chat.ai_name or "Гемма"):
                    # Получаем историю для контекста
                    history = get_personal_chat_history(db, personal_chat_id, client_id, limit=20)
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

                    ai_message_data = {
                        'id': ai_msg.id,
                        'content': ai_msg.content,
                        'sender_type': ai_msg.sender_type,
                        'sender_id': None,
                        'sender_name': chat.ai_name or 'Гемма',
                        'created_at': ai_msg.created_at.isoformat(),
                        'personal_chat_id': personal_chat_id
                    }

                    # Отправляем ответ ИИ
                    socketio.emit('new_message', ai_message_data, room=f'personal_{personal_chat_id}')

            elif group_id:
                # Групповой чат
                if not is_client_member_of_group(db, client_id, group_id):
                    emit('error', {'message': 'Нет доступа к группе'})
                    return

                # Получаем группу
                group = get_group_by_id(db, group_id)

                # Добавляем сообщение пользователя
                user_msg = add_message(
                    db, content, 'client', client_id,
                    group_id=group_id, message_type='text'
                )

                # Получаем имя отправителя
                user_client = get_client_by_id(db, client_id)
                message_data = {
                    'id': user_msg.id,
                    'content': user_msg.content,
                    'sender_type': user_msg.sender_type,
                    'sender_id': client_id,
                    'sender_name': user_client.login if user_client else 'Unknown',
                    'created_at': user_msg.created_at.isoformat(),
                    'group_id': group_id
                }

                # ОТПРАВЛЯЕМ СООБЩЕНИЕ ВСЕМ В КОМНАТЕ ГРУППЫ
                room_name = f'group_{group_id}'
                socketio.emit('new_message', message_data, room=room_name)

                # Проверяем флаг ai_enabled и триггер обращения к ИИ
                if group and group.ai_enabled and is_ai_triggered(content, group.ai_name or "Гемма"):
                    # Получаем историю для контекста
                    history = get_group_history(db, group_id, client_id, limit=20)
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

                    ai_message_data = {
                        'id': ai_msg.id,
                        'content': ai_msg.content,
                        'sender_type': ai_msg.sender_type,
                        'sender_id': None,
                        'sender_name': group.ai_name or 'Гемма',
                        'created_at': ai_msg.created_at.isoformat(),
                        'group_id': group_id
                    }

                    # Отправляем ответ ИИ всем в группе
                    socketio.emit('new_message', ai_message_data, room=room_name)

        except Exception as e:
            logger.error(f"Error in send_message WebSocket: {str(e)}")
            emit('error', {'message': f'Ошибка отправки: {str(e)}'})
        finally:
            db.close()
