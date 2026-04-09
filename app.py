"""
Flask приложение gemma-hub.
Основной сервер с API endpoints для всех режимов работы.
"""
import os
import logging
import base64
import hashlib
from flask import Flask, render_template, request, jsonify, session, redirect, url_for
from werkzeug.utils import secure_filename
from functools import wraps
from datetime import datetime, timezone

from config import SECRET_KEY, UPLOAD_FOLDER, MAX_CONTENT_LENGTH, LOG_FORMAT, LOG_LEVEL
# ИСПРАВЛЕНО: Добавлены PersonalChat и ChatGroup в импорт
from db import (
    init_db, get_db, SessionLocal,
    get_client_by_login, get_client_by_id,
    create_personal_chat, get_personal_chat as get_personal_chat_from_db, get_client_personal_chats,
    create_group, invite_client_to_group, accept_group_invite,
    is_client_member_of_group, get_client_groups, get_group_history,
    get_personal_chat_history, add_message,
    create_task_history, update_task_history,
    create_observer_session, add_observer_analysis,
    update_client_last_seen, get_all_users_with_status, get_pending_invitations,
    accept_invitation, toggle_chat_ai_enabled, get_personal_chat_by_id, get_group_by_id,
    Client, ChatGroup, GroupMember, TaskHistory, PersonalChat  # <--- ДОБАВЛЕНО PersonalChat
)
from ollama_client import OllamaClient

# Настройка логирования
logging.basicConfig(format=LOG_FORMAT, level=getattr(logging, LOG_LEVEL))
logger = logging.getLogger("app")

# Инициализация Flask
app = Flask(__name__)
app.secret_key = SECRET_KEY
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['MAX_CONTENT_LENGTH'] = MAX_CONTENT_LENGTH

# Создаем папку для загрузок если существует
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

# Инициализируем БД
init_db()

# Клиент Ollama
ollama = OllamaClient()

# ==================== УТИЛИТЫ ПАРОЛЕЙ (SHA-256) ====================

def hash_password_sha256(password: str) -> str:
    """Хеширует пароль через SHA-256 (совместимо с VARCHAR(64) в БД)"""
    return hashlib.sha256(password.encode('utf-8')).hexdigest()

def verify_password_sha256(password: str, hashed: str) -> bool:
    """Проверяет пароль"""
    return hash_password_sha256(password) == hashed

# ==================== УТИЛИТЫ ====================

def login_required(f):
    """Декоратор для защиты маршрутов требующих авторизации"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'client_id' not in session:
            return jsonify({'error': 'Требуется авторизация'}), 401
        # Обновляем last_seen при каждом запросе авторизованного пользователя
        db = SessionLocal()
        try:
            update_client_last_seen(db, session['client_id'])
        finally:
            db.close()
        return f(*args, **kwargs)
    return decorated_function


def get_current_client():
    """Получить текущего клиента из сессии"""
    if 'client_id' not in session:
        return None
    db = SessionLocal()
    try:
        return get_client_by_id(db, session['client_id'])
    finally:
        db.close()


# ==================== АВТОРИЗАЦИЯ ====================

@app.route('/')
def index():
    """Главная страница - редирект на логин или интерфейс"""
    if 'client_id' in session:
        return render_template('index.html')
    return render_template('login.html')


@app.route('/api/auth/register', methods=['POST'])
def register():
    """Регистрация нового клиента"""
    client_ip = request.remote_addr
    logger.info(f"POST /api/auth/register from {client_ip}")
    
    data = request.get_json()
    login = data.get('login', '').strip()
    password = data.get('password', '')
    
    if not login or not password:
        logger.warning(f"Registration failed: missing login or password from {client_ip}")
        return jsonify({'error': 'Логин и пароль обязательны'}), 400
    
    if len(login) < 3:
        logger.warning(f"Registration failed: login too short from {client_ip}")
        return jsonify({'error': 'Логин должен быть не менее 3 символов'}), 400
    
    if len(password) < 6:
        logger.warning(f"Registration failed: password too short from {client_ip}")
        return jsonify({'error': 'Пароль должен быть не менее 6 символов'}), 400
    
    db = SessionLocal()
    try:
        # Проверяем существование
        existing = get_client_by_login(db, login)
        if existing:
            logger.warning(f"Registration failed: user {login} already exists from {client_ip}")
            return jsonify({'error': 'Пользователь уже существует'}), 409
        
        # Хешируем пароль через SHA-256
        pwd_hash = hash_password_sha256(password)

        # Создаем клиента
        new_client = Client(
            login=login,
            password_hash=pwd_hash
        )
        db.add(new_client)
        db.commit()
        db.refresh(new_client)
        
        logger.info(f"User registered successfully: {login} (id={new_client.id}) from {client_ip}")
        return jsonify({
            'message': 'Регистрация успешна',
            'client_id': new_client.id,
            'login': new_client.login
        }), 201
    except Exception as e:
        db.rollback()
        logger.error(f"Registration error for {login}: {str(e)}")
        if "unique constraint" in str(e).lower():
            return jsonify({'error': 'Пользователь уже существует'}), 409
        return jsonify({'error': str(e)}), 500
    finally:
        db.close()


@app.route('/api/auth/login', methods=['POST'])
def login():
    """Вход в систему"""
    client_ip = request.remote_addr
    logger.info(f"POST /api/auth/login from {client_ip}")
    
    data = request.get_json()
    login = data.get('login', '').strip()
    password = data.get('password', '')
    
    db = SessionLocal()
    try:
        client = get_client_by_login(db, login)
        
        # Используем нашу SHA-256 проверку
        if not client or not verify_password_sha256(password, client.password_hash):
            logger.warning(f"Login failed for {login} from {client_ip}")
            return jsonify({'error': 'Неверный логин или пароль'}), 401
        
        # Создаем сессию
        session['client_id'] = client.id
        session['login'] = client.login
        
        logger.info(f"Login successful: {login} (id={client.id}) from {client_ip}")
        return jsonify({
            'message': 'Вход успешен',
            'client_id': client.id,
            'login': client.login
        })
    except Exception as e:
        logger.error(f"Login error for {login}: {str(e)}")
        raise
    finally:
        db.close()


@app.route('/api/auth/logout', methods=['POST'])
def logout():
    """Выход из системы"""
    client_ip = request.remote_addr
    client_id = session.get('client_id')
    logger.info(f"POST /api/auth/logout from {client_ip} (client_id={client_id})")
    
    session.clear()
    return jsonify({'message': 'Выход успешен'})


@app.route('/api/auth/me', methods=['GET'])
@login_required
def get_current_user():
    """Информация о текущем пользователе"""
    client = get_current_client()
    if not client:
        return jsonify({'error': 'Пользователь не найден'}), 404
    
    return jsonify({
        'client_id': client.id,
        'login': client.login,
        'created_at': client.created_at.isoformat() if client.created_at else None
    })


# ==================== ЛИЧНЫЙ АССИСТЕНТ ====================

@app.route('/api/chat/personal/create', methods=['POST'])
@login_required
def create_personal_chat_route():
    """Создать новый личный чат"""
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


@app.route('/api/chat/personal/<int:chat_id>', methods=['GET'])
@login_required
def get_personal_chat(chat_id: int):
    """Получить личный чат с историей"""
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
                'created_at': m.created_at.isoformat()
            } for m in messages]
        })
    finally:
        db.close()


@app.route('/api/chat/send', methods=['POST'])
@login_required
def send_message():
    """Отправить сообщение в личный или групповой чат"""
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
            
            # Проверяем флаг ai_enabled
            ai_message = None
            if chat.ai_enabled:
                # Получаем историю для контекста
                history = get_personal_chat_history(db, personal_chat_id, session['client_id'], limit=20)
                context = "\n".join([f"{m.sender_type}: {m.content}" for m in history])
                
                # Отправляем в Ollama
                ai_response = ollama.chat(
                    message=f"{context}\nUser: {content}",
                    system_prompt="Ты полезный ассистент. Отвечай кратко и по делу."
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
                    'created_at': ai_msg.created_at.isoformat()
                }
            
            logger.info(f"Message sent to personal chat {personal_chat_id}, status=200")
            result = {
                'user_message': {
                    'id': user_msg.id,
                    'content': user_msg.content,
                    'sender_type': user_msg.sender_type,
                    'created_at': user_msg.created_at.isoformat()
                }
            }
            if ai_message:
                result['ai_message'] = ai_message
            return jsonify(result)
        
        elif group_id:
            # Групповой чат
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

            # Проверяем флаг ai_enabled
            ai_message = None
            if group and group.ai_enabled:
                # Получаем историю для контекста
                history = get_group_history(db, group_id, session['client_id'], limit=20)
                context = "\n".join([f"{m.sender_type}: {m.content}" for m in history])

                # Отправляем в Ollama
                ai_response = ollama.chat(
                    message=f"{context}\nUser: {content}",
                    system_prompt="Ты полезный ассистент в групповом чате. Отвечай кратко и по делу."
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
                    'created_at': ai_msg.created_at.isoformat()
                }

            logger.info(f"Message sent to group {group_id}, status=200")
            result = {
                'user_message': {
                    'id': user_msg.id,
                    'content': user_msg.content,
                    'sender_type': user_msg.sender_type,
                    'created_at': user_msg.created_at.isoformat()
                }
            }
            if ai_message:
                result['ai_message'] = ai_message
            return jsonify(result)
    
    finally:
        db.close()


# ==================== АНАЛИЗ ИЗОБРАЖЕНИЙ ====================

@app.route('/api/upload/image', methods=['POST'])
@login_required
def upload_image():
    """Загрузка и анализ изображения (одиночное, legacy)"""
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
    filepath = os.path.join(app.config['UPLOAD_FOLDER'], unique_filename)
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


@app.route('/api/chat/vision', methods=['POST'])
@login_required
def chat_vision():
    """
    Мультимодальный анализ нескольких изображений.
    Поддерживает загрузку нескольких файлов одновременно.
    Gemma 4 обрабатывает массив изображений в одном запросе.
    """
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
        filepath = os.path.join(app.config['UPLOAD_FOLDER'], unique_filename)
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


@app.route('/api/task/status/<int:task_id>', methods=['GET'])
@login_required
def get_task_status(task_id: int):
    """Получить статус задачи"""
    db = SessionLocal()
    try:
        task = db.query(TaskHistory).get(task_id)
        if not task:
            return jsonify({'error': 'Задача не найдена'}), 404
            
        return jsonify({
            'task_id': task.id,
            'status': task.status,
            'result': task.result_data
        })
    finally:
        db.close()


# ==================== ТРАНСКРИБАЦИЯ АУДИО ====================

@app.route('/api/upload/audio', methods=['POST'])
@login_required
def upload_audio():
    """Загрузка аудио для транскрибации (legacy endpoint)"""
    if 'file' not in request.files:
        return jsonify({'error': 'Файл не найден'}), 400
    
    file = request.files['file']
    if file.filename == '':
        return jsonify({'error': 'Файл не выбран'}), 400
    
    # Сохраняем файл
    filename = secure_filename(file.filename)
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    unique_filename = f"{timestamp}_{filename}"
    filepath = os.path.join(app.config['UPLOAD_FOLDER'], unique_filename)
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


@app.route('/api/audio/transcribe-analyze', methods=['POST'])
@login_required
def audio_transcribe_analyze():
    """
    Транскрибация и анализ аудиофайла.
    Использует Whisper для транскрибации (или заглушку если Whisper не установлен).
    Затем отправляет текст в Gemma 4 для анализа содержания.
    """
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
    filepath = os.path.join(app.config['UPLOAD_FOLDER'], unique_filename)
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


# ==================== СОВМЕСТНЫЙ ЧАТ (ГРУППЫ) ====================

@app.route('/api/group/create', methods=['POST'])
@login_required
def create_group_route():
    """Создать новую группу"""
    data = request.get_json()
    name = data.get('name', '').strip()
    description = data.get('description', '')
    
    if not name:
        return jsonify({'error': 'Название группы обязательно'}), 400
    
    db = SessionLocal()
    try:
        group = create_group(db, name, session['client_id'], description)
        
        return jsonify({
            'id': group.id,
            'name': group.name,
            'description': group.description,
            'owner_id': group.owner_id,
            'created_at': group.created_at.isoformat()
        }), 201
    finally:
        db.close()


@app.route('/api/client/groups', methods=['GET'])
@login_required
def get_client_groups_route():
    """Получить список групп клиента"""
    db = SessionLocal()
    try:
        groups = get_client_groups(db, session['client_id'])
        
        return jsonify([{
            'id': g.id,
            'name': g.name,
            'description': g.description,
            'owner_id': g.owner_id,
            'created_at': g.created_at.isoformat()
        } for g in groups])
    finally:
        db.close()


@app.route('/api/group/<int:group_id>', methods=['GET'])
@login_required
def get_group(group_id: int):
    """Получить информацию о группе"""
    db = SessionLocal()
    try:
        group = db.query(ChatGroup).get(group_id)
        if not group:
            return jsonify({'error': 'Группа не найдена'}), 404
        
        if not is_client_member_of_group(db, session['client_id'], group_id):
            return jsonify({'error': 'Нет доступа к группе'}), 403
        
        members = db.query(GroupMember).filter(
            GroupMember.group_id == group_id,
            GroupMember.status == 'accepted'
        ).all()
        
        messages = get_group_history(db, group_id, session['client_id'], limit=100)
        
        return jsonify({
            'group': {
                'id': group.id,
                'name': group.name,
                'description': group.description,
                'owner_id': group.owner_id,
                'ai_enabled': group.ai_enabled
            },
            'members': [{
                'client_id': m.client_id,
                'login': m.client.login,
                'status': m.status
            } for m in members],
            'messages': [{
                'id': m.id,
                'content': m.content,
                'sender_type': m.sender_type,
                'sender_id': m.sender_id,
                'sender_name': m.sender.login if m.sender else 'AI',
                'created_at': m.created_at.isoformat()
            } for m in messages]
        })
    finally:
        db.close()


@app.route('/api/group/<int:group_id>/invite', methods=['POST'])
@login_required
def invite_to_group(group_id: int):
    """Пригласить пользователя в группу"""
    data = request.get_json()
    target_login = data.get('login', '').strip()
    
    if not target_login:
        return jsonify({'error': 'Логин пользователя обязателен'}), 400
    
    db = SessionLocal()
    try:
        # Проверяем что текущий пользователь владелец
        group = db.query(ChatGroup).get(group_id)
        if not group or group.owner_id != session['client_id']:
            return jsonify({'error': 'Только владелец может приглашать'}), 403
        
        # Находим приглашаемого
        invitee = get_client_by_login(db, target_login)
        if not invitee:
            return jsonify({'error': 'Пользователь не найден'}), 404
        
        if invitee.id == session['client_id']:
            return jsonify({'error': 'Нельзя пригласить самого себя'}), 400
        
        # Приглашаем
        member = invite_client_to_group(db, group_id, invitee.id)
        
        return jsonify({
            'message': f'Приглашение отправлено пользователю {target_login}',
            'status': member.status
        })
    finally:
        db.close()


@app.route('/api/group/<int:group_id>/accept', methods=['POST'])
@login_required
def accept_invite(group_id: int):
    """Принять приглашение в группу"""
    db = SessionLocal()
    try:
        member = accept_group_invite(db, group_id, session['client_id'])
        
        if not member:
            return jsonify({'error': 'Приглашение не найдено'}), 404
        
        return jsonify({
            'message': 'Приглашение принято',
            'status': member.status
        })
    finally:
        db.close()


# ==================== ИИ-НАБЛЮДАТЕЛЬ ====================

@app.route('/api/group/observe', methods=['POST'])
@login_required
def start_observer():
    """Запустить анализ чата наблюдателем"""
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
            {'sender': m.sender.login if m.sender else 'AI', 'content': m.content}
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


@app.route('/api/client/chats', methods=['GET'])
@login_required
def get_client_chats():
    """Получить все чаты клиента (личные + группы)"""
    db = SessionLocal()
    try:
        # Личные чаты
        personal_chats = get_client_personal_chats(db, session['client_id'])
        
        # Группы
        groups = get_client_groups(db, session['client_id'])
        
        return jsonify({
            'personal_chats': [{
                'id': c.id,
                'title': c.title,
                'type': 'personal',
                'ai_enabled': c.ai_enabled,
                'updated_at': c.updated_at.isoformat() if c.updated_at else None
            } for c in personal_chats],
            'groups': [{
                'id': g.id,
                'name': g.name,
                'type': 'group',
                'ai_enabled': g.ai_enabled,
                'created_at': g.created_at.isoformat()
            } for g in groups]
        })
    finally:
        db.close()


# ==================== СТАТУС ПОЛЬЗОВАТЕЛЕЙ ====================


@app.route('/api/users/list', methods=['GET'])
@login_required
def get_users_list():
    """Возвращает список всех пользователей со статусом online/offline"""
    db = SessionLocal()
    try:
        clients = db.query(Client).all()
        users_data = []
        # Получаем текущее время UTC (с часовым поясом)
        now = datetime.now(timezone.utc)
        
        for c in clients:
            is_online = False
            if c.last_seen:
                last = c.last_seen
                
                # ХИТРОСТЬ: Если время из БД "без пояса" (naive), считаем что оно UTC
                if last.tzinfo is None:
                    last = last.replace(tzinfo=timezone.utc)
                
                # Если время из БД "с поясом" (aware), то вычитаем напрямую
                # Теперь оба времени совместимы
                diff = (now - last).total_seconds()
                
                if diff < 300: # 5 минут
                    is_online = True
            
            users_data.append({
                'id': c.id,
                'login': c.login,
                'is_online': is_online
            })
            
        return jsonify({'users': users_data})
    except Exception as e:
        logger.error(f"Error getting users list: {e}")
        return jsonify({'error': str(e)}), 500
    finally:
        db.close()


# ==================== ПРИГЛАШЕНИЯ В ГРУППЫ ====================

@app.route('/api/group/invite', methods=['POST'])
@login_required
def invite_to_group_api():
    """Пригласить пользователя в группу по логину"""
    data = request.get_json()
    group_id = data.get('group_id')
    login = data.get('login', '').strip()
    
    if not group_id or not login:
        return jsonify({'error': 'Необходимо указать group_id и login'}), 400
    
    db = SessionLocal()
    try:
        # Проверяем существование группы
        group = get_group_by_id(db, group_id)
        if not group:
            return jsonify({'error': 'Группа не найдена'}), 404
        
        # Проверяем что текущий пользователь - владелец группы
        if group.owner_id != session['client_id']:
            return jsonify({'error': 'Только владелец может приглашать'}), 403
        
        # Находим пользователя по логину
        target_client = get_client_by_login(db, login)
        if not target_client:
            return jsonify({'error': 'Пользователь не найден'}), 404
        
        # Приглашаем
        member = invite_client_to_group(db, group_id, target_client.id)
        logger.info(f"Client {target_client.id} invited to group {group_id} by {session['client_id']}")
        return jsonify({'message': 'Приглашение отправлено', 'member_id': member.id})
    finally:
        db.close()


@app.route('/api/invitations', methods=['GET'])
@login_required
def get_invitations():
    """Возвращает все pending-приглашения для текущего пользователя"""
    db = SessionLocal()
    try:
        invitations = get_pending_invitations(db, session['client_id'])
        return jsonify({'invitations': invitations})
    finally:
        db.close()


@app.route('/api/invitations/accept', methods=['POST'])
@login_required
def accept_invitation_api():
    """Принять приглашение в группу"""
    data = request.get_json()
    group_id = data.get('group_id')
    
    if not group_id:
        return jsonify({'error': 'Необходимо указать group_id'}), 400
    
    db = SessionLocal()
    try:
        success = accept_invitation(db, group_id, session['client_id'])
        if success:
            return jsonify({'message': 'Приглашение принято'})
        else:
            return jsonify({'error': 'Приглашение не найдено или уже обработано'}), 404
    finally:
        db.close()


# ==================== TOGGLE AI ====================

@app.route('/api/chat/toggle_ai', methods=['POST'])
@login_required
def toggle_ai():
    """Переключить флаг ai_enabled для чата"""
    data = request.get_json()
    chat_type = data.get('chat_type')  # 'personal' или 'group'
    chat_id = data.get('chat_id')
    
    if not chat_type or not chat_id:
        return jsonify({'error': 'Необходимо указать chat_type и chat_id'}), 400
    
    db = SessionLocal()
    try:
        chat = None
        
        # Ищем чат в зависимости от типа
        # Для личных чатов - проверяем owner_id
        # Для групп - проверяем членство (любой участник может переключать ИИ)
        if chat_type == 'personal':
            chat = db.query(PersonalChat).filter(
                PersonalChat.id == chat_id,
                PersonalChat.owner_id == session['client_id']
            ).first()
        elif chat_type == 'group':
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


# ==================== НАБЛЮДАТЕЛЬ ДЛЯ ЛИЧНЫХ ЧАТОВ ====================

@app.route('/api/chat/observe', methods=['POST'])
@login_required
def observe_personal_chat():
    """ИИ-анализатор для личных чатов (режим Наблюдатель)"""
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

if __name__ == '__main__':
    # Обновляем last_seen при старте (опционально)
    logger.info("Starting Gemma-Hub Server...")
    app.run(host='0.0.0.0', port=5002, debug=True)