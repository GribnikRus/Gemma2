"""
Модуль загрузки и анализа медиафайлов: изображения (vision), аудио (whisper).
Все endpoints с префиксом /api/upload и /api/chat/vision, /api/audio/*
"""
import os
import logging
import base64
from flask import Blueprint, request, jsonify, current_app
from werkzeug.utils import secure_filename
from datetime import datetime

from db import SessionLocal, create_task_history, update_task_history, add_message, Client
from ollama_client import OllamaClient
from .utils import login_required

logger = logging.getLogger("app")

media_upload_bp = Blueprint('media_upload', __name__, url_prefix='/api')
ollama = OllamaClient()


@media_upload_bp.route('/upload/image', methods=['POST'])
@login_required
def upload_image():
    """Загрузка и анализ изображения (одиночное, legacy)"""
    from flask import session
    
    client_ip = request.remote_addr
    client_id = session.get('client_id')
    logger.info(f"POST /api/upload/image from {client_ip} (client_id={client_id})")

    if 'file' not in request.files:
        logger.warning(f"No file in request from {client_ip}")
        return jsonify({'error': 'Файл не найден'}), 400

    file = request.files['file']
    if file.filename == '':
        logger.warning(f"Empty filename from {client_ip}")
        return jsonify({'error': 'Файл не выбран'}), 400

    filename = secure_filename(file.filename)
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    unique_filename = f"{timestamp}_{filename}"
    filepath = os.path.join(current_app.config['UPLOAD_FOLDER'], unique_filename)
    file.save(filepath)
    logger.debug(f"Image saved to {filepath}")

    with open(filepath, 'rb') as f:
        image_base64 = base64.b64encode(f.read()).decode('utf-8')

    db = SessionLocal()
    try:
        task = create_task_history(db, session['client_id'], 'image_analysis', unique_filename)
        
        try:
            response = ollama.analyze_image(image_base64, "Опиши изображение")
            update_task_history(db, task.id, result=response, status='completed')
            db.commit()
            return jsonify({'task_id': task.id, 'status': 'completed', 'result': response})
        except Exception as e:
            logger.error(f"Image analysis failed: {str(e)}")
            update_task_history(db, task.id, result=str(e), status='failed')
            db.rollback()
            return jsonify({'error': f'Ошибка анализа: {str(e)}'}), 500
    except Exception as e:
        logger.error(f"Error in upload_image: {str(e)}")
        return jsonify({'error': str(e)}), 500
    finally:
        db.close()


@media_upload_bp.route('/chat/vision', methods=['POST'])
@login_required
def chat_vision():
    """Мультимодальный анализ нескольких изображений. Возвращает 202, результат — через WebSocket."""
    from flask import session
    
    client_ip = request.remote_addr
    client_id = session.get('client_id')
    logger.info(f"POST /api/chat/vision from {client_ip} (client_id={client_id})")

    if 'files' not in request.files:
        return jsonify({'error': 'Файлы не найдены'}), 400

    files = request.files.getlist('files')
    if not files or all(f.filename == '' for f in files):
        return jsonify({'error': 'Файлы не выбраны'}), 400

    prompt = request.form.get('prompt', 'Опишите эти изображения подробно.')
    chat_type = request.form.get('chat_type', 'personal')
    chat_id = request.form.get('chat_id')
    
    logger.info(f"DEBUG: chat_type={chat_type}, chat_id={chat_id}, prompt={prompt[:50]}")

    images_base64 = []
    saved_filenames = []
    for file in files:
        if file.filename == '': continue
        filename = secure_filename(file.filename)
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        unique_filename = f"{timestamp}_{filename}"
        filepath = os.path.join(current_app.config['UPLOAD_FOLDER'], unique_filename)
        file.save(filepath)
        with open(filepath, 'rb') as f:
            image_base64 = base64.b64encode(f.read()).decode('utf-8')
        images_base64.append(image_base64)
        saved_filenames.append(unique_filename)

    logger.info(f"Processing {len(images_base64)} images for vision analysis")

    # === Создаём задачу в БД ===
    db = SessionLocal()
    try:
        task = create_task_history(db, session['client_id'], 'vision_analysis', f"Multiple images ({len(saved_filenames)})")
        db.commit()
        task_id = task.id
    except Exception as e:
        logger.error(f"Failed to create task: {e}")
        db.rollback()
        return jsonify({'error': 'Не удалось создать задачу'}), 500
    finally:
        db.close()

    # === ЗАПУСКАЕМ ФОНОВУЮ ЗАДАЧУ ===
    # ⚠️ ВАЖНО: Копируем все нужные данные ДО старта потока (session недоступен в фоне!)
    bg_client_id = session['client_id']
    bg_chat_type = chat_type
    bg_chat_id = chat_id
    bg_task_id = task_id
    bg_prompt = prompt
    bg_images_base64 = images_base64[:]

    def process_vision_analysis():
        """Фоновая задача: анализ + БД + WebSocket"""
        db = SessionLocal()  # НОВАЯ сессия для фонового потока
        try:
            # 1. Анализ изображений
            analysis = ollama.analyze_image_batch(bg_images_base64, bg_prompt)
            
            # 2. Сохраняем результат
            update_task_history(db, bg_task_id, result=analysis, status='completed')
            db.commit()

            # 3. Если есть чат — сохраняем и отправляем через WebSocket
            if bg_chat_id:
                user_message_text = f"📷 Анализ {len(bg_images_base64)} изображения(ий): {bg_prompt}"
                user_msg = None
                ai_msg = None
                
                if bg_chat_type == 'personal':
                    user_msg = add_message(db, user_message_text, 'client', bg_client_id, personal_chat_id=int(bg_chat_id), message_type='text')
                    ai_msg = add_message(db, analysis, 'ai', None, personal_chat_id=int(bg_chat_id), message_type='text')
                elif bg_chat_type == 'group':
                    user_msg = add_message(db, user_message_text, 'client', bg_client_id, group_id=int(bg_chat_id), message_type='text')
                    ai_msg = add_message(db, analysis, 'ai', None, group_id=int(bg_chat_id), message_type='text')
                
                if user_msg and ai_msg:
                    db.commit()
                    
                    # 4. WebSocket отправка
                    try:
                        socketio = current_app.extensions.get('socketio')
                        if socketio:
                            room_name = f"{bg_chat_type}_{bg_chat_id}"
                            client = db.query(Client).filter(Client.id == bg_client_id).first()
                            sender_name = client.login if client else "Пользователь"
                            
                            socketio.emit('new_message', {
                                'id': user_msg.id, 'content': user_msg.content, 'sender_type': 'client',
                                'sender_id': bg_client_id, 'sender_name': sender_name,
                                'created_at': user_msg.created_at.isoformat(),
                                f'{bg_chat_type}_chat_id': int(bg_chat_id)
                            }, room=room_name)
                            
                            socketio.emit('new_message', {
                                'id': ai_msg.id, 'content': ai_msg.content, 'sender_type': 'ai',
                                'sender_id': None, 'sender_name': 'Gemma AI',
                                'created_at': ai_msg.created_at.isoformat(),
                                f'{bg_chat_type}_chat_id': int(bg_chat_id)
                            }, room=room_name)
                            
                            logger.info(f"✅ WebSocket messages sent to room: {room_name}")
                    except Exception as ws_error:
                        logger.error(f"WebSocket send error: {ws_error}", exc_info=True)

            logger.info(f"✅ Vision analysis completed for task {bg_task_id}")
            
        except Exception as e:
            logger.error(f"❌ Vision analysis failed for task {bg_task_id}: {str(e)}")
            update_task_history(db, bg_task_id, result=str(e), status='failed')
            db.rollback()
        finally:
            db.close()

    # Запуск фоновой задачи
    socketio = current_app.extensions.get('socketio')
    if socketio:
        socketio.start_background_task(process_vision_analysis)
    else:
        logger.warning("⚠️ SocketIO not available, running synchronously")
        process_vision_analysis()

    # === НЕМЕДЛЕННЫЙ ОТВЕТ КЛИЕНТУ ===
    return jsonify({
        'task_id': task_id,
        'status': 'processing',
        'message': 'Анализ запущен. Результат придёт через WebSocket.',
        'images_count': len(images_base64),
        'model_used': ollama.model_vision
    }), 202


@media_upload_bp.route('/upload/audio', methods=['POST'])
@login_required
def upload_audio():
    """Загрузка аудио (legacy)"""
    from flask import session, current_app
    if 'file' not in request.files:
        return jsonify({'error': 'Файл не найден'}), 400
    file = request.files['file']
    if file.filename == '':
        return jsonify({'error': 'Файл не выбран'}), 400

    filename = secure_filename(file.filename)
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    unique_filename = f"{timestamp}_{filename}"
    filepath = os.path.join(current_app.config['UPLOAD_FOLDER'], unique_filename)
    file.save(filepath)

    db = SessionLocal()
    try:
        task = create_task_history(db, session['client_id'], 'audio_transcript', unique_filename)
        result_text = "Транскрибация пока в разработке. Файл сохранен: " + unique_filename
        update_task_history(db, task.id, result=result_text, status='completed')
        db.commit()
        return jsonify({'task_id': task.id, 'status': 'completed', 'result': result_text})
    except Exception as e:
        logger.error(f"Error in upload_audio: {str(e)}")
        db.rollback()
        return jsonify({'error': str(e)}), 500
    finally:
        db.close()


@media_upload_bp.route('/audio/transcribe-analyze', methods=['POST'])
@login_required
def audio_transcribe_analyze():
    """Транскрибация и анализ аудио"""
    from flask import session, current_app
    client_ip = request.remote_addr
    client_id = session.get('client_id')
    logger.info(f"POST /api/audio/transcribe-analyze from {client_ip} (client_id={client_id})")

    if 'file' not in request.files:
        return jsonify({'error': 'Файл не найден'}), 400
    file = request.files['file']
    if file.filename == '':
        return jsonify({'error': 'Файл не выбран'}), 400

    filename = secure_filename(file.filename)
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    unique_filename = f"{timestamp}_{filename}"
    filepath = os.path.join(current_app.config['UPLOAD_FOLDER'], unique_filename)
    file.save(filepath)

    db = SessionLocal()
    try:
        task = create_task_history(db, session['client_id'], 'audio_transcribe_analyze', unique_filename)
        
        # Заглушка транскрибации (если Whisper не установлен)
        transcription = "[ЗАГЛУШКА] Установите openai-whisper для реальной транскрибации."
        
        try:
            analysis_result = ollama.transcribe_and_analyze_audio(transcription)
            full_result = {'transcription': analysis_result['transcription'], 'analysis': analysis_result['analysis']}
            update_task_history(db, task.id, result=str(full_result), status='completed')
            db.commit()
            return jsonify({'task_id': task.id, 'status': 'completed', **analysis_result})
        except Exception as e:
            logger.error(f"Analysis failed: {str(e)}")
            update_task_history(db, task.id, result=str(e), status='failed')
            db.rollback()
            return jsonify({'error': f'Ошибка анализа: {str(e)}'}), 500
    except Exception as e:
        logger.error(f"Error in audio_transcribe_analyze: {str(e)}")
        db.rollback()
        return jsonify({'error': str(e)}), 500
    finally:
        db.close()