"""
Flask приложение gemma-hub.
Точка входа: инициализация Flask, SocketIO, регистрация блюпринтов.
"""
import os
import eventlet
eventlet.monkey_patch()

import logging
from flask import Flask, render_template, session
from flask_socketio import SocketIO

from config import SECRET_KEY, UPLOAD_FOLDER, MAX_CONTENT_LENGTH, LOG_FORMAT, LOG_LEVEL, REDIS_BROKER_URL
from db import init_db, SessionLocal

# Настройка логирования
logging.basicConfig(format=LOG_FORMAT, level=getattr(logging, LOG_LEVEL))
logger = logging.getLogger("app")

# Инициализация Flask
app = Flask(__name__)
app.secret_key = SECRET_KEY
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['MAX_CONTENT_LENGTH'] = MAX_CONTENT_LENGTH

# Redis URL для SocketIO (из переменной окружения или по умолчанию)
REDIS_URL = os.environ.get('REDIS_URL', REDIS_BROKER_URL)

# Инициализация SocketIO с поддержкой Redis для production
socketio = SocketIO(app, cors_allowed_origins="*", async_mode='eventlet', message_queue=REDIS_URL)

# Создаем папку для загрузок если существует
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

# Инициализируем БД
init_db()


# ==================== ГЛАВНАЯ СТРАНИЦА ====================

@app.route('/')
def index():
    """Главная страница - редирект на логин или интерфейс"""
    if 'client_id' in session:
        return render_template('index.html')
    return render_template('login.html')


# ==================== РЕГИСТРАЦИЯ BLUEPRINTS ====================

from blueprints.auth import auth_bp
from blueprints.chat_personal import chat_personal_bp
from blueprints.chat_group import chat_group_bp
from blueprints.media_upload import media_upload_bp
from blueprints.observer import observer_bp
from blueprints.users import users_bp
from blueprints.tasks import tasks_bp

app.register_blueprint(auth_bp)
app.register_blueprint(chat_personal_bp)
app.register_blueprint(chat_group_bp)
app.register_blueprint(media_upload_bp)
app.register_blueprint(observer_bp)
app.register_blueprint(users_bp)
app.register_blueprint(tasks_bp)


# ==================== WEBSOCKET EVENTS ====================

from blueprints.chat_websocket import register_websocket_events
register_websocket_events(socketio)


# ==================== ЗАПУСК ПРИЛОЖЕНИЯ ====================

if __name__ == '__main__':
    logger.info("Starting Gemma-Hub Server...")
    # Запускаем через socketio.run для поддержки WebSocket
    socketio.run(app, host='0.0.0.0', port=5000, debug=False)
