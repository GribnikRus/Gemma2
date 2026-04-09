# Ollama
OLLAMA_URL = "http://192.168.0.166:11434"
OLLAMA_MODEL_CHAT = "gemma4:e4b"
OLLAMA_MODEL_VISION = "gemma4:e4b"

# Ollama Generation Parameters
OLLAMA_TEMPERATURE = 0.7
OLLAMA_TOP_K = 40
OLLAMA_TOP_P = 0.9

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

# Logging Configuration
LOG_LEVEL = "INFO"
LOG_FORMAT = "[%(levelname)s] %(asctime)s - %(name)s - %(message)s"
