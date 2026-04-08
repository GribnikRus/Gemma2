"""
Flask приложение gemma-hub.
Основной сервер с API endpoints для всех режимов работы.
"""
import os
import base64
from flask import Flask, render_template, request, jsonify, session, redirect, url_for
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
from functools import wraps
from datetime import datetime

from config import SECRET_KEY, UPLOAD_FOLDER, MAX_CONTENT_LENGTH
from db import (
    init_db, get_db, SessionLocal,
    get_client_by_username, get_client_by_id,
    create_personal_chat, get_personal_chat, get_client_personal_chats,
    create_group, invite_client_to_group, accept_group_invite,
    is_client_member_of_group, get_client_groups, get_group_history,
    get_personal_chat_history, add_message,
    create_task_history, update_task_history,
    create_observer_session, add_observer_analysis,
    Client, ChatGroup, GroupMember
)
from ollama_client import OllamaClient
from celery_tasks.tasks import analyze_image_task, transcribe_audio_task, analyze_chat_observer_task

# Инициализация Flask
app = Flask(__name__)
app.secret_key = SECRET_KEY
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['MAX_CONTENT_LENGTH'] = MAX_CONTENT_LENGTH

# Создаем папку для загрузок если не существует
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

# Инициализируем БД
init_db()

# Клиент Ollama
ollama = OllamaClient()


# ==================== УТИЛИТЫ ====================

def login_required(f):
    """Декоратор для защиты маршрутов требующих авторизации"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'client_id' not in session:
            return jsonify({'error': 'Требуется авторизация'}), 401
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
    data = request.get_json()
    username = data.get('username', '').strip()
    password = data.get('password', '')
    
    if not username or not password:
        return jsonify({'error': 'Логин и пароль обязательны'}), 400
    
    if len(username) < 3:
        return jsonify({'error': 'Логин должен быть не менее 3 символов'}), 400
    
    if len(password) < 6:
        return jsonify({'error': 'Пароль должен быть не менее 6 символов'}), 400
    
    db = SessionLocal()
    try:
        # Проверяем существование
        existing = get_client_by_username(db, username)
        if existing:
            return jsonify({'error': 'Пользователь уже существует'}), 409
        
        # Создаем клиента
        new_client = Client(
            username=username,
            password_hash=generate_password_hash(password)
        )
        db.add(new_client)
        db.commit()
        db.refresh(new_client)
        
        return jsonify({
            'message': 'Регистрация успешна',
            'client_id': new_client.id,
            'username': new_client.username
        }), 201
    finally:
        db.close()


@app.route('/api/auth/login', methods=['POST'])
def login():
    """Вход в систему"""
    data = request.get_json()
    username = data.get('username', '').strip()
    password = data.get('password', '')
    
    db = SessionLocal()
    try:
        client = get_client_by_username(db, username)
        
        if not client or not check_password_hash(client.password_hash, password):
            return jsonify({'error': 'Неверный логин или пароль'}), 401
        
        if not client.is_active:
            return jsonify({'error': 'Аккаунт деактивирован'}), 403
        
        # Создаем сессию
        session['client_id'] = client.id
        session['username'] = client.username
        
        return jsonify({
            'message': 'Вход успешен',
            'client_id': client.id,
            'username': client.username
        })
    finally:
        db.close()


@app.route('/api/auth/logout', methods=['POST'])
def logout():
    """Выход из системы"""
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
        'username': client.username,
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
        chat = get_personal_chat(db, chat_id, session['client_id'])
        if not chat:
            return jsonify({'error': 'Чат не найден'}), 404
        
        messages = get_personal_chat_history(db, chat_id, session['client_id'], limit=100)
        
        return jsonify({
            'chat': {
                'id': chat.id,
                'title': chat.title,
                'created_at': chat.created_at.isoformat()
            },
            'messages': [{
                'id': m.id,
                'content': m.content,
                'sender_type': m.sender_type,
                'message_type': m.message_type,
                'created_at': m.created_at.isoformat()
            } for m in messages]
        })
    finally:
        db.close()


@app.route('/api/chat/send', methods=['POST'])
@login_required
def send_message():
    """Отправить сообщение в личный или групповой чат"""
    data = request.get_json()
    content = data.get('content', '').strip()
    personal_chat_id = data.get('personal_chat_id')
    group_id = data.get('group_id')
    
    if not content:
        return jsonify({'error': 'Сообщение не может быть пустым'}), 400
    
    db = SessionLocal()
    try:
        # Определяем тип чата
        if personal_chat_id:
            # Личный чат
            chat = get_personal_chat(db, personal_chat_id, session['client_id'])
            if not chat:
                return jsonify({'error': 'Чат не найден'}), 404
            
            # Добавляем сообщение пользователя
            user_msg = add_message(
                db, content, 'client', session['client_id'],
                personal_chat_id=personal_chat_id, message_type='text'
            )
            
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
            
            return jsonify({
                'user_message': {
                    'id': user_msg.id,
                    'content': user_msg.content,
                    'sender_type': user_msg.sender_type,
                    'created_at': user_msg.created_at.isoformat()
                },
                'ai_message': {
                    'id': ai_msg.id,
                    'content': ai_msg.content,
                    'sender_type': ai_msg.sender_type,
                    'created_at': ai_msg.created_at.isoformat()
                }
            })
        
        elif group_id:
            # Групповой чат
            if not is_client_member_of_group(db, group_id, session['client_id']):
                return jsonify({'error': 'Нет доступа к группе'}), 403
            
            # Добавляем сообщение пользователя
            user_msg = add_message(
                db, content, 'client', session['client_id'],
                group_id=group_id, message_type='text'
            )
            
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
            
            return jsonify({
                'user_message': {
                    'id': user_msg.id,
                    'content': user_msg.content,
                    'sender_type': user_msg.sender_type,
                    'created_at': user_msg.created_at.isoformat()
                },
                'ai_message': {
                    'id': ai_msg.id,
                    'content': ai_msg.content,
                    'sender_type': ai_msg.sender_type,
                    'created_at': ai_msg.created_at.isoformat()
                }
            })
        else:
            return jsonify({'error': 'Не указан чат'}), 400
    
    finally:
        db.close()


# ==================== АНАЛИЗ ИЗОБРАЖЕНИЙ ====================

@app.route('/api/upload/image', methods=['POST'])
@login_required
def upload_image():
    """Загрузка и анализ изображения"""
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
    
    # Кодируем в base64 для отправки в Ollama
    with open(filepath, 'rb') as f:
        image_base64 = base64.b64encode(f.read()).decode('utf-8')
    
    db = SessionLocal()
    try:
        # Создаем запись в истории задач
        task = create_task_history(
            db, session['client_id'], 
            'image_analysis', 
            unique_filename
        )
        
        # Запускаем фоновую задачу Celery
        celery_task = analyze_image_task.delay(image_base64, "Опиши это изображение подробно на русском языке.")
        
        return jsonify({
            'task_id': task.id,
            'celery_task_id': celery_task.id,
            'status': 'processing',
            'message': 'Анализ изображения запущен'
        }), 202
    
    finally:
        db.close()


@app.route('/api/task/status/<int:task_id>', methods=['GET'])
@login_required
def get_task_status(task_id: int):
    """Получить статус задачи"""
    db = SessionLocal()
    try:
        # В реальном приложении здесь была бы проверка статуса Celery задачи
        # Пока просто возвращаем заглушку
        return jsonify({
            'task_id': task_id,
            'status': 'completed',
            'result': 'Это заглушка. Реальный статус будет после интеграции с Celery.'
        })
    finally:
        db.close()


# ==================== ТРАНСКРИБАЦИЯ АУДИО ====================

@app.route('/api/upload/audio', methods=['POST'])
@login_required
def upload_audio():
    """Загрузка аудио для транскрибации"""
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
        
        # Запускаем фоновую задачу Celery
        celery_task = transcribe_audio_task.delay(filepath, unique_filename)
        
        return jsonify({
            'task_id': task.id,
            'celery_task_id': celery_task.id,
            'status': 'processing',
            'message': 'Транскрибация запущена'
        }), 202
    
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
        
        if not is_client_member_of_group(db, group_id, session['client_id']):
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
                'owner_id': group.owner_id
            },
            'members': [{
                'client_id': m.client_id,
                'username': m.client.username,
                'status': m.status
            } for m in members],
            'messages': [{
                'id': m.id,
                'content': m.content,
                'sender_type': m.sender_type,
                'sender_id': m.sender_id,
                'sender_name': m.sender.username if m.sender else 'AI',
                'message_type': m.message_type,
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
    username = data.get('username', '').strip()
    
    if not username:
        return jsonify({'error': 'Логин пользователя обязателен'}), 400
    
    db = SessionLocal()
    try:
        # Проверяем что текущий пользователь владелец
        group = db.query(ChatGroup).get(group_id)
        if not group or group.owner_id != session['client_id']:
            return jsonify({'error': 'Только владелец может приглашать'}), 403
        
        # Находим приглашаемого
        invitee = get_client_by_username(db, username)
        if not invitee:
            return jsonify({'error': 'Пользователь не найден'}), 404
        
        if invitee.id == session['client_id']:
            return jsonify({'error': 'Нельзя пригласить самого себя'}), 400
        
        # Приглашаем
        member = invite_client_to_group(db, group_id, invitee.id)
        
        return jsonify({
            'message': f'Приглашение отправлено пользователю {username}',
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
        if not is_client_member_of_group(db, group_id, session['client_id']):
            return jsonify({'error': 'Нет доступа к группе'}), 403
        
        # Получаем сообщения
        messages = get_group_history(db, group_id, session['client_id'], limit=100 if analysis_type == 'full' else 10)
        
        if not messages:
            return jsonify({'error': 'Нет сообщений для анализа'}), 400
        
        # Форматируем для анализа
        formatted_messages = [
            {'sender': m.sender.username if m.sender else 'AI', 'content': m.content}
            for m in messages
        ]
        
        # Создаем сессию наблюдателя
        observer_session = create_observer_session(
            db, group_id, session['client_id'], role_prompt, analysis_type
        )
        
        # Запускаем фоновую задачу
        celery_task = analyze_chat_observer_task.delay(
            formatted_messages, role_prompt, analysis_type
        )
        
        # Для демонстрации сразу делаем синхронный запрос
        ai_analysis = ollama.analyze_chat_as_observer(
            formatted_messages, role_prompt, analysis_type
        )
        
        # Сохраняем результат
        analysis = add_observer_analysis(
            db, observer_session.id, ai_analysis, len(messages)
        )
        
        return jsonify({
            'session_id': observer_session.id,
            'analysis': ai_analysis,
            'messages_analyzed': len(messages),
            'analysis_type': analysis_type
        })
    
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
                'updated_at': c.updated_at.isoformat() if c.updated_at else None
            } for c in personal_chats],
            'groups': [{
                'id': g.id,
                'name': g.name,
                'type': 'group',
                'created_at': g.created_at.isoformat()
            } for g in groups]
        })
    finally:
        db.close()


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5002, debug=True)
