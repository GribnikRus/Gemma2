"""
Модуль пользователей: список пользователей, статус online/offline, приглашения.
Все endpoints с префиксом /api/users
"""
import logging
from flask import Blueprint, request, jsonify
from datetime import datetime, timezone

from db import SessionLocal, Client
from .utils import login_required

logger = logging.getLogger("app")

users_bp = Blueprint('users', __name__, url_prefix='/api')


@users_bp.route('/users/list', methods=['GET'])
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

                if diff < 300:  # 5 минут
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
