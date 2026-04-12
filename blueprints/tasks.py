"""
Модуль задач: история задач, статусы выполнения.
Все endpoints с префиксом /api/task
"""
import logging
from flask import Blueprint, jsonify

from db import SessionLocal, TaskHistory
from .utils import login_required

logger = logging.getLogger("app")

tasks_bp = Blueprint('tasks', __name__, url_prefix='/api')


@tasks_bp.route('/task/status/<int:task_id>', methods=['GET'])
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
