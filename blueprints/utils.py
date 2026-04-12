"""
Общие утилиты для blueprint модулей.
"""
import hashlib
import re
from functools import wraps
from flask import session, jsonify
from db import SessionLocal, update_client_last_seen, get_client_by_id


def hash_password_sha256(password: str) -> str:
    """Хеширует пароль через SHA-256 (совместимо с VARCHAR(64) в БД)"""
    return hashlib.sha256(password.encode('utf-8')).hexdigest()


def verify_password_sha256(password: str, hashed: str) -> bool:
    """Проверяет пароль"""
    return hash_password_sha256(password) == hashed


def is_ai_triggered(content: str, ai_name: str) -> bool:
    """
    Проверяет, обращается ли пользователь к ИИ.
    Триггеры:
    1. @<имя_ии> в начале сообщения
    2. /gemma или /ai в начале
    3. <имя_ии>, или <имя_ии> с последующим пробелом/запятой
    """
    if not content:
        return False
    
    # Нормализуем имя для сравнения (убираем пробелы по краям)
    ai_name_clean = ai_name.strip()
    
    # 1. Проверка @<имя> в начале
    if content.startswith('@'):
        # Извлекаем имя после @
        match = re.match(r'^@(\S+)[,\s]?', content, re.IGNORECASE)
        if match:
            mentioned_name = match.group(1).rstrip(',').rstrip('!').rstrip('.')
            if mentioned_name.lower() == ai_name_clean.lower():
                return True
    
    # 2. Проверка команд /gemma или /ai
    if content.startswith('/gemma') or content.startswith('/ai'):
        return True
    
    # 3. Проверка имени в начале без @, но с запятой или пробелом
    # Например: "Гемма, привет" или "Гемма объясни"
    # Паттерн: имя в начале строки, за которым следует запятая, пробел или конец строки
    pattern = rf'^{re.escape(ai_name_clean)}[,\s]|^{re.escape(ai_name_clean)}$'
    if re.match(pattern, content, re.IGNORECASE):
        return True
    
    return False


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
