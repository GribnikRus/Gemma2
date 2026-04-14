# config.py
import os
from dotenv import load_dotenv

load_dotenv()

# Ollama
OLLAMA_URL = os.environ.get('OLLAMA_URL', "http://192.168.0.166:11434")
OLLAMA_MODEL_CHAT = os.environ.get('OLLAMA_MODEL_CHAT', "gemma4:e4b")
OLLAMA_MODEL_VISION = os.environ.get('OLLAMA_MODEL_VISION', "gemma4:e4b")
OLLAMA_TIMEOUT = int(os.environ.get('OLLAMA_TIMEOUT', '300'))  # ← НОВОЕ: 300 секунд вместо 120

# Ollama Generation Parameters
OLLAMA_TEMPERATURE = float(os.environ.get('OLLAMA_TEMPERATURE', '0.7'))
OLLAMA_TOP_K = int(os.environ.get('OLLAMA_TOP_K', '40'))
OLLAMA_TOP_P = float(os.environ.get('OLLAMA_TOP_P', '0.9'))

# Redis (пока не используется, но оставим для будущего)
REDIS_BROKER_URL = os.environ.get('REDIS_BROKER_URL', "redis://localhost:6379/0")
CELERY_BROKER_URL = REDIS_BROKER_URL
CELERY_RESULT_BACKEND = REDIS_BROKER_URL

# PostgreSQL
DATABASE_URL = os.environ.get('DATABASE_URL', "postgresql://bot_user:YesNo1977@192.168.0.34:5432/sleep_data_db")

# Flask
SECRET_KEY = os.environ.get('SECRET_KEY', "gemma-hub-secret-key-change-in-production")
UPLOAD_FOLDER = os.environ.get('UPLOAD_FOLDER', "uploads")
MAX_CONTENT_LENGTH = int(os.environ.get('MAX_CONTENT_LENGTH', 16 * 1024 * 1024))  # 16MB

# Logging
LOG_LEVEL = os.environ.get('LOG_LEVEL', 'INFO')
LOG_FORMAT = os.environ.get('LOG_FORMAT', "[%(levelname)s] %(asctime)s - %(name)s - %(message)s")