"""
Модуль авторизации: регистрация, логин, логаут.
Все endpoints с префиксом /api/auth
"""
import logging
from flask import Blueprint, render_template, request, jsonify, session

from db import SessionLocal, get_client_by_login, Client
from .utils import hash_password_sha256, verify_password_sha256, login_required, get_current_client

logger = logging.getLogger("app")

auth_bp = Blueprint('auth', __name__, url_prefix='/api/auth')


@auth_bp.route('/register', methods=['POST'])
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


@auth_bp.route('/login', methods=['POST'])
def login():
    """Вход в систему"""
    client_ip = request.remote_addr
    logger.info(f"=== LOGIN ATTEMPT ===")
    logger.info(f"POST /api/auth/login from {client_ip}")
    
    data = request.get_json()
    login = data.get('login', '').strip()
    password = data.get('password', '')
    
    logger.info(f"Login attempt for user: {login}")
    
    if not login or not password:
        logger.warning(f"Login failed: missing credentials from {client_ip}")
        return jsonify({'error': 'Логин и пароль обязательны'}), 400
    
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
        
        logger.info(f"✅ Login successful: {login} (id={client.id}) from {client_ip}")
        logger.info(f"Session after login: client_id={session.get('client_id')}, login={session.get('login')}")
        
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


@auth_bp.route('/logout', methods=['POST'])
def logout():
    """Выход из системы"""
    client_ip = request.remote_addr
    client_id = session.get('client_id')
    logger.info(f"POST /api/auth/logout from {client_ip} (client_id={client_id})")
    
    session.clear()
    return jsonify({'message': 'Выход успешен'})


@auth_bp.route('/me', methods=['GET'])
@login_required
def get_current_user():
    """Информация о текущем пользователе"""
    client = get_current_client()
    if not client:
        return jsonify({'error': 'Пользователь не найден'}), 404
    
    logger.info(f"GET /api/auth/me: returning user {client.login} (id={client.id})")
    
    return jsonify({
        'client_id': client.id,
        'login': client.login,
        'created_at': client.created_at.isoformat() if client.created_at else None
    })