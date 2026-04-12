"""
Модуль загрузки и анализа медиафайлов: изображения (vision), аудио (whisper).
Все endpoints с префиксом /api/upload и /api/chat/vision, /api/audio/*
"""
import os
import logging
import base64
from flask import Blueprint, request, jsonify
from werkzeug.utils import secure_filename
from datetime import datetime

from db import SessionLocal, create_task_history, update_task_history, add_message
from ollama_client import OllamaClient
from .utils import login_required

logger = logging.getLogger("app")

media_upload_bp = Blueprint('media_upload', __name__, url_prefix='/api')

ollama = OllamaClient()


@media_upload_bp.route('/upload/image', methods=['POST'])
@login_required
def upload_image():
    """Загрузка и анализ изображения (одиночное, legacy)"""
    from flask import session, current_app
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

    # Сохраняем файл
    filename = secure_filename(file.filename)
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    unique_filename = f"{timestamp}_{filename}"
    filepath = os.path.join(current_app.config['UPLOAD_FOLDER'], unique_filename)
    file.save(filepath)
    logger.debug(f"Image saved to {filepath}")

    # Кодируем в base64 для отправки в Ollama
    with open(filepath, 'rb') as f:
        image_base64 = base64.b64encode(f.read()).decode('utf-8')
    logger.debug(f"Image encoded to base64 ({len(image_base64)} chars)")

    db = SessionLocal()
    try:
        # Создаем запись в истории задач
        task = create_task_history(
            db, session['client_id'],
            'image_analysis',
            unique_filename
        )

        # Простой вызов ollama vision (если поддерживается)
        try:
            response = ollama.analyze_image(image_base64, "Опиши изображение")
            update_task_history(db, task.id, result=response, status='completed')
            logger.info(f"Image analysis completed for task {task.id}, status=200")
            return jsonify({
                'task_id': task.id,
                'status': 'completed',
                'result': response
            })
        except Exception as e:
            logger.error(f"Image analysis failed for task {task.id}: {str(e)}")
            update_task_history(db, task.id, result=str(e), status='failed')
            return jsonify({'error': f'Ошибка анализа: {str(e)}'}), 500

    except Exception as e:
        logger.error(f"Error in upload_image: {str(e)}")
        return jsonify({'error': str(e)}), 500
    finally:
        db.close()


@media_upload_bp.route('/chat/vision', methods=['POST'])
@login_required
def chat_vision():
    """
    Мультимодальный анализ нескольких изображений.
    Поддерживает загрузку нескольких файлов одновременно.
    Gemma 4 обрабатывает массив изображений в одном запросе.
    """
    from flask import session, current_app
    client_ip = request.remote_addr
    client_id = session.get('client_id')
    logger.info(f"POST /api/chat/vision from {client_ip} (client_id={client_id})")

    if 'files' not in request.files:
        logger.warning(f"No files in request from {client_ip}")
        return jsonify({'error': 'Файлы не найдены'}), 400

    files = request.files.getlist('files')
    if not files or all(f.filename == '' for f in files):
        logger.warning(f"Empty filenames from {client_ip}")
        return jsonify({'error': 'Файлы не выбраны'}), 400

    prompt = request.form.get('prompt', 'Опишите эти изображения подробно.')
    chat_type = request.form.get('chat_type', 'personal')
    chat_id = request.form.get('chat_id')

    images_base64 = []
    saved_filenames = []

    # Обрабатываем каждое изображение
    for file in files:
        if file.filename == '':
            continue

        filename = secure_filename(file.filename)
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        unique_filename = f"{timestamp}_{filename}"
        filepath = os.path.join(current_app.config['UPLOAD_FOLDER'], unique_filename)
        file.save(filepath)
        logger.debug(f"Image saved to {filepath}")

        with open(filepath, 'rb') as f:
            image_base64 = base64.b64encode(f.read()).decode('utf-8')

        images_base64.append(image_base64)
        saved_filenames.append(unique_filename)

    logger.info(f"Processing {len(images_base64)} images for vision analysis")

    db = SessionLocal()
    try:
        # Создаем запись в истории задач
        task = create_task_history(
            db, session['client_id'],
            'vision_analysis',
            f"Multiple images ({len(saved_filenames)})"
        )

        # Вызываем mulltimodal анализ через ollama_client
        try:
            analysis = ollama.analyze_image_batch(images_base64, prompt)

            # Сохраняем результат
            update_task_history(db, task.id, result=analysis, status='completed')

            # Если есть чат, сохраняем туда результат
            if chat_id and chat_type == 'personal':
                user_msg = add_message(
                    db, f"📷 Анализ {len(images_base64)} изображения(ий): {prompt}",
                    'client', session['client_id'],
                    personal_chat_id=int(chat_id), message_type='text'
                )
                ai_msg = add_message(
                    db, analysis, 'ai', None,
                    personal_chat_id=int(chat_id), message_type='text'
                )

            logger.info(f"Vision analysis completed for task {task.id}")
            return jsonify({
                'task_id': task.id,
                'status': 'completed',
                'analysis': analysis,
                'images_count': len(images_base64)
            })

        except Exception as e:
            logger.error(f"Vision analysis failed for task {task.id}: {str(e)}")
            update_task_history(db, task.id, result=str(e), status='failed')
            return jsonify({'error': f'Ошибка анализа: {str(e)}'}), 500

    except Exception as e:
        logger.error(f"Error in chat_vision: {str(e)}")
        return jsonify({'error': str(e)}), 500
    finally:
        db.close()


@media_upload_bp.route('/upload/audio', methods=['POST'])
@login_required
def upload_audio():
    """Загрузка аудио для транскрибации (legacy endpoint)"""
    from flask import session, current_app
    if 'file' not in request.files:
        return jsonify({'error': 'Файл не найден'}), 400

    file = request.files['file']
    if file.filename == '':
        return jsonify({'error': 'Файл не выбран'}), 400

    # Сохраняем файл
    filename = secure_filename(file.filename)
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    unique_filename = f"{timestamp}_{filename}"
    filepath = os.path.join(current_app.config['UPLOAD_FOLDER'], unique_filename)
    file.save(filepath)

    db = SessionLocal()
    try:
        # Создаем запись в истории задач
        task = create_task_history(
            db, session['client_id'],
            'audio_transcript',
            unique_filename
        )

        # ЗАГЛУШКА: Возвращаем текст сразу
        result_text = "Транскрибация пока в разработке. Файл сохранен: " + unique_filename

        update_task_history(db, task.id, result=result_text, status='completed')

        return jsonify({
            'task_id': task.id,
            'status': 'completed',
            'result': result_text
        })

    finally:
        db.close()


@media_upload_bp.route('/audio/transcribe-analyze', methods=['POST'])
@login_required
def audio_transcribe_analyze():
    """
    Транскрибация и анализ аудиофайла.
    Использует Whisper для транскрибации (или заглушку если Whisper не установлен).
    Затем отправляет текст в Gemma 4 для анализа содержания.
    """
    from flask import session, current_app
    client_ip = request.remote_addr
    client_id = session.get('client_id')
    logger.info(f"POST /api/audio/transcribe-analyze from {client_ip} (client_id={client_id})")

    if 'file' not in request.files:
        logger.warning(f"No file in request from {client_ip}")
        return jsonify({'error': 'Файл не найден'}), 400

    file = request.files['file']
    if file.filename == '':
        logger.warning(f"Empty filename from {client_ip}")
        return jsonify({'error': 'Файл не выбран'}), 400

    # Сохраняем файл
    filename = secure_filename(file.filename)
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    unique_filename = f"{timestamp}_{filename}"
    filepath = os.path.join(current_app.config['UPLOAD_FOLDER'], unique_filename)
    file.save(filepath)
    logger.info(f"Audio file saved to {filepath}")

    db = SessionLocal()
    try:
        # Создаем запись в истории задач
        task = create_task_history(
            db, session['client_id'],
            'audio_transcribe_analyze',
            unique_filename
        )

        # Попытка транскрибации через Whisper
        transcription = None
        try:
            # Проверяем наличие whisper
            import whisper

            logger.info(f"Loading Whisper model for transcription...")
            # Используем легкую модель для скорости (можно заменить на 'medium' или 'large')
            model = whisper.load_model("base")

            logger.info(f"Transcribing audio file: {filepath}")
            result = model.transcribe(filepath)
            transcription = result["text"]

            logger.info(f"Transcription completed ({len(transcription)} chars)")

        except ImportError:
            # Whisper не установлен - используем заглушку
            logger.warning("Whisper not installed, using stub transcription")
            transcription = (
                "[ЗАГЛУШКА] Whisper не установлен. "
                "Для реальной транскрибации установите: pip install openai-whisper\n\n"
                "Эмуляция транскрибации:\n"
                "Это пример текста который мог бы быть получен из аудиофайла. "
                "В реальном сценарии здесь будет распознанная речь из файла {}. "
                "Подключите Whisper API или локальную модель для настоящей транскрибации.".format(unique_filename)
            )
        except Exception as e:
            logger.error(f"Whisper transcription error: {str(e)}")
            transcription = f"Ошибка транскрибации: {str(e)}"

        # Анализируем текст через Gemma 4
        try:
            analysis_result = ollama.transcribe_and_analyze_audio(transcription)

            # Сохраняем результат
            full_result = {
                'transcription': analysis_result['transcription'],
                'analysis': analysis_result['analysis']
            }

            update_task_history(db, task.id, result=str(full_result), status='completed')

            logger.info(f"Audio transcribe-analyze completed for task {task.id}")

            return jsonify({
                'task_id': task.id,
                'status': 'completed',
                'transcription': analysis_result['transcription'],
                'analysis': analysis_result['analysis']
            })

        except Exception as e:
            logger.error(f"Analysis failed for task {task.id}: {str(e)}")
            update_task_history(db, task.id, result=str(e), status='failed')
            return jsonify({'error': f'Ошибка анализа: {str(e)}'}), 500

    except Exception as e:
        logger.error(f"Error in audio_transcribe_analyze: {str(e)}")
        return jsonify({'error': str(e)}), 500
    finally:
        db.close()
