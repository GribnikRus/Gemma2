# Ollama
OLLAMA_URL = "http://192.168.0.166:11434/api/generate"
OLLAMA_MODEL_CHAT = "gemma4:e4b"
OLLAMA_MODEL_VISION = "gemma4:e4b"

# Redis
REDIS_BROKER_URL = "redis://localhost:6379/0"
CELERY_BROKER_URL = REDIS_BROKER_URL
CELERY_RESULT_BACKEND = REDIS_BROKER_URL

# PostgreSQL (твоя БД)
DATABASE_URL = "postgresql://bot_user:YesNo1977@192.168.0.34:5432/sleep_data_db"

# Flask
SECRET_KEY = "gemma-hub-secret-key-change-in-production"
UPLOAD_FOLDER = "uploads"
MAX_CONTENT_LENGTH = 16 * 1024 * 1024  # 16MB max file size
