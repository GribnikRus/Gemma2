"""
Flask приложение gemma-hub.
Точка входа: инициализация Flask, SocketIO, регистрация блюпринтов.
"""
import os
import eventlet
eventlet.monkey_patch()

import logging
from flask import Flask, render_template, session, jsonify
from flask_socketio import SocketIO, disconnect, join_room, emit

from config import SECRET_KEY, UPLOAD_FOLDER, MAX_CONTENT_LENGTH, LOG_FORMAT, LOG_LEVEL
from db import init_db, SessionLocal

# Настройка логирования
logging.basicConfig(format=LOG_FORMAT, level=getattr(logging, LOG_LEVEL))
logger = logging.getLogger("app")

# Инициализация Flask
app = Flask(__name__)
app.secret_key = SECRET_KEY
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['MAX_CONTENT_LENGTH'] = MAX_CONTENT_LENGTH

# Инициализация SocketIO БЕЗ Redis (упрощённый режим)
socketio = SocketIO(
    app, 
    cors_allowed_origins="*", 
    async_mode='eventlet',
    ping_timeout=60,
    ping_interval=25
)

# Создаем папку для загрузок
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

# Инициализируем БД
try:
    init_db()
    logger.info("Database initialized successfully")
except Exception as e:
    logger.error(f"Database initialization failed: {e}")
    raise

# Добавляем socketio в extensions для доступа из блупринтов
app.extensions['socketio'] = socketio

# Создаем ЕДИНЫЙ экземпляр OllamaClient для всего приложения
from ollama_client import OllamaClient
ollama_client = OllamaClient()
app.extensions['ollama_client'] = ollama_client


# ==================== ГЛАВНАЯ СТРАНИЦА ====================

@app.route('/')
def index():
    """Главная страница"""
    if 'client_id' in session:
        return render_template('index.html')
    return render_template('login.html')


# ==================== WEBSOCKET: ПОЛНЫЙ ОБРАБОТЧИК CONNECT ====================

# ==================== WEBSOCKET: ПОЛНЫЙ ОБРАБОТЧИК CONNECT ====================

@socketio.on('connect')
def ws_connect(auth=None):  # ✅ Принимаем опциональный аргумент auth
    """Полная обработка подключения: авторизация + комнаты + статусы"""
    from flask_socketio import emit, join_room
    
    # 1. Проверка авторизации
    if 'client_id' not in session:
        logger.warning("WebSocket connection rejected: not authenticated")
        disconnect()
        return False
    
    client_id = session['client_id']
    logger.info(f"Client {client_id} connected via WebSocket")
    
    # 2. Добавляем в личную комнату (для приватных уведомлений)
    join_room(f'user_{client_id}')
    
    # 3. Обновляем статус online в БД
    db = SessionLocal()
    try:
        from db import update_user_online_status
        update_user_online_status(db, client_id, True)
        
        # 4. Уведомляем других клиентов (ОПЦИЯ 1: без 'to' = всем)
        # ✅ Правильный способ: не указывать 'to' или 'broadcast'
        socketio.emit('user_joined', {'client_id': client_id})
        
        # Если хочешь отправить ТОЛЬКО в определённую комнату:
        # socketio.emit('user_joined', {'client_id': client_id}, room='all_users')
        
    except Exception as e:
        logger.error(f"Error in ws_connect: {e}", exc_info=True)
        db.rollback()
    finally:
        db.close()
    
    # 5. Подтверждаем подключение клиенту
    emit('connected', {'message': 'Connected to Gemma-Hub', 'client_id': client_id})
    return True


# ==================== РЕГИСТРАЦИЯ BLUEPRINTS ====================

from blueprints.auth import auth_bp
from blueprints.chat_personal import chat_personal_bp
from blueprints.chat_group import chat_group_bp
from blueprints.media_upload import media_upload_bp
from blueprints.observer import observer_bp
from blueprints.users import users_bp
from blueprints.tasks import tasks_bp
from blueprints.ai_status import ai_status_bp
from blueprints.ai_models import ai_models_bp  

app.register_blueprint(auth_bp)
app.register_blueprint(chat_personal_bp)
app.register_blueprint(chat_group_bp)
app.register_blueprint(media_upload_bp)
app.register_blueprint(observer_bp)
app.register_blueprint(users_bp)
app.register_blueprint(tasks_bp)
app.register_blueprint(ai_status_bp)
app.register_blueprint(ai_models_bp)


# ==================== WEBSOCKET EVENTS ====================
# register_websocket_events регистрирует ТОЛЬКО: disconnect, join_group, join_personal, send_message
# (обработчик connect уже определён выше и не должен дублироваться в блюпринте)
from blueprints.chat_websocket import register_websocket_events
register_websocket_events(socketio)


# ==================== ЗАПУСК ПРИЛОЖЕНИЯ ====================

@app.route('/api/health', methods=['GET'])
def healthcheck():
    """Проверка здоровья сервиса: БД + Ollama"""
    import requests
    from sqlalchemy import text
    from config import OLLAMA_URL
    
    status = {'database': 'unknown', 'ollama': 'unknown', 'status': 'unknown'}
    
    # Проверка БД
    db = SessionLocal()
    try:
        db.execute(text("SELECT 1"))
        status['database'] = 'ok'
    except Exception as e:
        status['database'] = f'error: {str(e)}'
    finally:
        db.close()
    
    # Проверка Ollama
    try:
        response = requests.get(f"{OLLAMA_URL}/api/tags", timeout=5)
        if response.ok:
            status['ollama'] = 'ok'
        else:
            status['ollama'] = f'error: HTTP {response.status_code}'
    except Exception as e:
        status['ollama'] = f'error: {str(e)}'
    
    # Общий статус
    if status['database'] == 'ok' and status['ollama'] == 'ok':
        status['status'] = 'healthy'
        return jsonify(status), 200
    else:
        status['status'] = 'unhealthy'
        return jsonify(status), 503


if __name__ == '__main__':
    logger.info("Starting Gemma-Hub Server on port 5002...")
    socketio.run(app, host='0.0.0.0', port=5002, debug=False, use_reloader=False)