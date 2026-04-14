"""
WebSocket события: disconnect, join_group, join_personal, send_message.
Обработчик 'connect' вынесен в app.py для централизованной авторизации.
Все обработчики @socketio.on(...) вынесены в этот модуль.
"""
import logging
from flask import session, current_app
from flask_socketio import emit, join_room

from db import (
    SessionLocal, update_user_online_status, is_client_member_of_group,
    get_personal_chat as get_personal_chat_from_db, get_personal_chat_history,
    add_message, get_client_by_id, get_group_by_id, get_group_history, Client
)
from ollama_client import OllamaClient
from .utils import is_ai_triggered

logger = logging.getLogger("app")

ollama = OllamaClient()


def register_websocket_events(socketio):
    """Регистрирует все WebSocket обработчики событий (кроме connect)"""
    
    # ============================================================
    # ❌ ОБРАБОТЧИК 'connect' УДАЛЁН — он теперь в app.py
    # Это предотвращает конфликты и дублирование логики
    # ============================================================
    
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
                socketio.emit('user_left', {'client_id': client_id})
            except Exception as e:
                logger.error(f"Error updating offline status: {e}")
                db.rollback()
            finally:
                db.close()
        # SocketIO автоматически удаляет из комнат при disconnect

    @socketio.on('join_group')
    def handle_join_group(data):
        """Присоединение к комнате группы"""
        client_id = session.get('client_id')
        group_id = data.get('group_id')

        if not client_id or not group_id:
            emit('error', {'message': 'Неверные параметры для присоединения к группе'})
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
                emit('error', {'message': 'Нет доступа к этой группе'})
        except Exception as e:
            logger.error(f"Error in join_group: {str(e)}")
            emit('error', {'message': f'Ошибка: {str(e)}'})
        finally:
            db.close()

    @socketio.on('join_personal')
    def handle_join_personal(data):
        """Присоединение к личному чату (для получения уведомлений)"""
        client_id = session.get('client_id')
        personal_chat_id = data.get('personal_chat_id')

        if not client_id or not personal_chat_id:
            emit('error', {'message': 'Неверные параметры для присоединения к чату'})
            return

        db = SessionLocal()
        try:
            chat = get_personal_chat_from_db(db, personal_chat_id, client_id)
            if chat:
                room_name = f'personal_{personal_chat_id}'
                join_room(room_name)
                logger.info(f"Client {client_id} joined personal chat room {room_name}")
                emit('joined_personal', {'personal_chat_id': personal_chat_id})
            else:
                logger.warning(f"Client {client_id} tried to join non-existent personal chat {personal_chat_id}")
                emit('error', {'message': 'Чат не найден'})
        except Exception as e:
            logger.error(f"Error in join_personal: {str(e)}")
            emit('error', {'message': f'Ошибка: {str(e)}'})
        finally:
            db.close()

    @socketio.on('send_message')
    def handle_send_message(data):
        """Обработка отправки сообщения через WebSocket"""
        client_id = session.get('client_id')
        content = data.get('content', '').strip()
        personal_chat_id = data.get('personal_chat_id')
        group_id = data.get('group_id')

        logger.info(f"📨 WebSocket send_message: client_id={client_id}, personal_chat_id={personal_chat_id}, group_id={group_id}, content_length={len(content)}")
        logger.debug(f"   Message content preview: {content[:100]}...")

        if not content:
            logger.warning(f"❌ Empty message content from client_id={client_id}")
            emit('error', {'message': 'Сообщение не может быть пустым'})
            return

        if not client_id:
            logger.error(f"❌ Unauthenticated WebSocket message attempt")
            emit('error', {'message': 'Требуется авторизация'})
            return

        db = SessionLocal()
        try:
            logger.info(f"   Database session opened for message processing")
            
            # Определяем тип чата и сохраняем сообщение
            if personal_chat_id:
                logger.info(f"   Processing PERSONAL chat message (chat_id={personal_chat_id})")
                # Личный чат
                chat = get_personal_chat_from_db(db, personal_chat_id, client_id)
                if not chat:
                    logger.error(f"❌ Personal chat {personal_chat_id} not found for client {client_id}")
                    emit('error', {'message': 'Чат не найден'})
                    return
                logger.info(f"   ✅ Personal chat found: title='{chat.title}', ai_enabled={chat.ai_enabled}")

                # Добавляем сообщение пользователя
                logger.info(f"   Saving user message to database...")
                user_msg = add_message(
                    db, content, 'client', client_id,
                    personal_chat_id=personal_chat_id, message_type='text'
                )
                logger.info(f"   ✅ User message saved: id={user_msg.id}")

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
                logger.info(f"   Prepared message_data for WebSocket emit: sender_name='{message_data['sender_name']}'")

                # Отправляем сообщение всем в комнате личного чата
                room_name = f'personal_{personal_chat_id}'
                logger.info(f"   Emitting 'new_message' to room '{room_name}'...")
                try:
                    socketio.emit('new_message', message_data, room=room_name)
                    logger.info(f"   ✅ WebSocket message emitted successfully to room '{room_name}'")
                except Exception as ws_error:
                    logger.warning(f"⚠️ WebSocket send failed for user message (client may be disconnected): {ws_error}")

                # Проверяем флаг ai_enabled и триггер обращения к ИИ
                if chat.ai_enabled and is_ai_triggered(content, chat.ai_name or "Гемма"):
                    logger.info(f"   🤖 AI trigger detected! ai_name='{chat.ai_name}', generating response...")
                    # Показываем индикатор "печатает" (опционально, если клиент поддерживает)
                    # socketio.emit('ai_typing', {'chat_id': personal_chat_id}, room=f'personal_{personal_chat_id}')
                    
                    # Получаем историю для контекста
                    history = get_personal_chat_history(db, personal_chat_id, client_id, limit=20)
                    logger.info(f"   Retrieved {len(history)} messages for AI context")
                    context = "\n".join([f"{m.sender_type}: {m.content}" for m in history])

                    # Отправляем в Ollama
                    logger.info(f"   Calling Ollama API with model={ollama.model_chat}...")
                    ai_response = ollama.chat(
                        message=f"{context}\nUser: {content}",
                        system_prompt=f"Ты полезный ассистент. Тебя зовут {chat.ai_name or 'Гемма'}. Отвечай кратко и по делу."
                    )
                    logger.info(f"   ✅ Ollama response received: {len(ai_response)} chars")

                    # Добавляем ответ ИИ
                    logger.info(f"   Saving AI response to database...")
                    ai_msg = add_message(
                        db, ai_response, 'ai', None,
                        personal_chat_id=personal_chat_id, message_type='text'
                    )
                    logger.info(f"   ✅ AI message saved: id={ai_msg.id}")

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
                    logger.info(f"   Emitting AI response to room '{room_name}'...")
                    try:
                        socketio.emit('new_message', ai_message_data, room=room_name)
                        logger.info(f"   ✅ AI WebSocket message emitted successfully")
                    except Exception as ws_error:
                        logger.warning(f"⚠️ WebSocket send failed for AI message (client may be disconnected): {ws_error}")
                else:
                    logger.debug(f"   AI not triggered: ai_enabled={chat.ai_enabled}, is_ai_triggered={is_ai_triggered(content, chat.ai_name or 'Гемма')}")

            elif group_id:
                logger.info(f"   Processing GROUP chat message (group_id={group_id})")
                # Групповой чат
                if not is_client_member_of_group(db, client_id, group_id):
                    logger.error(f"❌ Client {client_id} is not a member of group {group_id}")
                    emit('error', {'message': 'Нет доступа к группе'})
                    return
                logger.info(f"   ✅ Client membership confirmed for group {group_id}")

                # Получаем группу
                group = get_group_by_id(db, group_id)
                logger.info(f"   Group found: name='{group.name}', ai_enabled={group.ai_enabled}")

                # Добавляем сообщение пользователя
                logger.info(f"   Saving user message to database...")
                user_msg = add_message(
                    db, content, 'client', client_id,
                    group_id=group_id, message_type='text'
                )
                logger.info(f"   ✅ User message saved: id={user_msg.id}")

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
                logger.info(f"   Prepared message_data for WebSocket emit: sender_name='{message_data['sender_name']}'")

                # ОТПРАВЛЯЕМ СООБЩЕНИЕ ВСЕМ В КОМНАТЕ ГРУППЫ
                room_name = f'group_{group_id}'
                logger.info(f"   Emitting 'new_message' to room '{room_name}'...")
                try:
                    socketio.emit('new_message', message_data, room=room_name)
                    logger.info(f"   ✅ WebSocket message emitted successfully to room '{room_name}'")
                except Exception as ws_error:
                    logger.warning(f"⚠️ WebSocket send failed for user message (client may be disconnected): {ws_error}")

                # Проверяем флаг ai_enabled и триггер обращения к ИИ
                if group and group.ai_enabled and is_ai_triggered(content, group.ai_name or "Гемма"):
                    logger.info(f"   🤖 AI trigger detected in group! ai_name='{group.ai_name}', generating response...")
                    # Получаем историю для контекста
                    history = get_group_history(db, group_id, client_id, limit=20)
                    logger.info(f"   Retrieved {len(history)} messages for AI context")
                    context = "\n".join([f"{m.sender_type}: {m.content}" for m in history])

                    # Отправляем в Ollama
                    logger.info(f"   Calling Ollama API with model={ollama.model_chat}...")
                    ai_response = ollama.chat(
                        message=f"{context}\nUser: {content}",
                        system_prompt=f"Ты полезный ассистент в групповом чате. Тебя зовут {group.ai_name or 'Гемма'}. Отвечай кратко и по делу."
                    )
                    logger.info(f"   ✅ Ollama response received: {len(ai_response)} chars")

                    # Добавляем ответ ИИ
                    logger.info(f"   Saving AI response to database...")
                    ai_msg = add_message(
                        db, ai_response, 'ai', None,
                        group_id=group_id, message_type='text'
                    )
                    logger.info(f"   ✅ AI message saved: id={ai_msg.id}")

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
                    logger.info(f"   Emitting AI response to room '{room_name}'...")
                    try:
                        socketio.emit('new_message', ai_message_data, room=room_name)
                        logger.info(f"   ✅ AI WebSocket message emitted successfully")
                    except Exception as ws_error:
                        logger.warning(f"⚠️ WebSocket send failed for AI message (client may be disconnected): {ws_error}")
                else:
                    logger.debug(f"   AI not triggered in group: ai_enabled={group.ai_enabled if group else 'N/A'}")

            else:
                logger.error(f"❌ No chat ID provided: personal_chat_id={personal_chat_id}, group_id={group_id}")
                emit('error', {'message': 'Необходимо указать personal_chat_id или group_id'})

        except Exception as e:
            logger.error(f"❌ Error in send_message WebSocket: {str(e)}", exc_info=True)
            emit('error', {'message': f'Ошибка отправки: {str(e)}'})
            db.rollback()
            raise
        finally:
            db.close()
            logger.debug(f"   Database session closed")