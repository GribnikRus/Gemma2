"""
Модуль групповых чатов: создание, участники, приглашения, история.
Все endpoints с префиксом /api/group и /api/client/groups
"""
import logging
from flask import Blueprint, request, jsonify

from db import (
    SessionLocal, create_group, invite_client_to_group, accept_group_invite,
    is_client_member_of_group, get_client_groups, get_group_history,
    get_group_by_id, ChatGroup, GroupMember, Client
)
from .utils import login_required

logger = logging.getLogger("app")

chat_group_bp = Blueprint('chat_group', __name__, url_prefix='/api')


@chat_group_bp.route('/group/create', methods=['POST'])
@login_required
def create_group_route():
    """Создать новую группу"""
    from flask import session
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
            'ai_enabled': group.ai_enabled,
            'ai_name': group.ai_name,
            'created_at': group.created_at.isoformat()
        }), 201
    finally:
        db.close()


@chat_group_bp.route('/client/groups', methods=['GET'])
@login_required
def get_client_groups_route():
    """Получить список групп клиента"""
    from flask import session
    db = SessionLocal()
    try:
        groups = get_client_groups(db, session['client_id'])

        return jsonify([{
            'id': g.id,
            'name': g.name,
            'description': g.description,
            'owner_id': g.owner_id,
            'ai_enabled': g.ai_enabled,
            'ai_name': g.ai_name,
            'created_at': g.created_at.isoformat()
        } for g in groups])
    finally:
        db.close()


@chat_group_bp.route('/group/<int:group_id>', methods=['GET'])
@login_required
def get_group(group_id: int):
    """Получить информацию о группе"""
    from flask import session
    db = SessionLocal()
    try:
        group = db.query(ChatGroup).get(group_id)
        if not group:
            return jsonify({'error': 'Группа не найдена'}), 404

        if not is_client_member_of_group(db, session['client_id'], group_id):
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
                'owner_id': group.owner_id,
                'ai_enabled': group.ai_enabled,
                'ai_name': group.ai_name
            },
            'members': [{
                'client_id': m.client_id,
                'login': m.client.login,
                'status': m.status
            } for m in members],
            'messages': [{
                'id': m.id,
                'content': m.content,
                'sender_type': m.sender_type,
                'sender_id': m.sender_id,
                'sender_name': m.sender.login if m.sender else 'Gemma AI',
                'created_at': m.created_at.isoformat()
            } for m in messages]
        })
    finally:
        db.close()


@chat_group_bp.route('/group/<int:group_id>/invite', methods=['POST'])
@login_required
def invite_to_group(group_id: int):
    """Пригласить пользователя в группу"""
    from flask import session
    data = request.get_json()
    target_login = data.get('login', '').strip()

    if not target_login:
        return jsonify({'error': 'Логин пользователя обязателен'}), 400

    db = SessionLocal()
    try:
        # Проверяем что текущий пользователь владелец
        group = db.query(ChatGroup).get(group_id)
        if not group or group.owner_id != session['client_id']:
            return jsonify({'error': 'Только владелец может приглашать'}), 403

        # Находим приглашаемого
        from db import get_client_by_login
        invitee = get_client_by_login(db, target_login)
        if not invitee:
            return jsonify({'error': 'Пользователь не найден'}), 404

        if invitee.id == session['client_id']:
            return jsonify({'error': 'Нельзя пригласить самого себя'}), 400

        # Приглашаем
        member = invite_client_to_group(db, group_id, invitee.id)

        return jsonify({
            'message': f'Приглашение отправлено пользователю {target_login}',
            'status': member.status
        })
    finally:
        db.close()


@chat_group_bp.route('/group/<int:group_id>/accept', methods=['POST'])
@login_required
def accept_invite(group_id: int):
    """Принять приглашение в группу"""
    from flask import session
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


@chat_group_bp.route('/group/invite', methods=['POST'])
@login_required
def invite_to_group_api():
    """Пригласить пользователя в группу по логину"""
    from flask import session
    data = request.get_json()
    group_id = data.get('group_id')
    login = data.get('login', '').strip()

    if not group_id or not login:
        return jsonify({'error': 'Необходимо указать group_id и login'}), 400

    db = SessionLocal()
    try:
        # Проверяем существование группы
        group = get_group_by_id(db, group_id)
        if not group:
            return jsonify({'error': 'Группа не найдена'}), 404

        # Проверяем что текущий пользователь - владелец группы
        if group.owner_id != session['client_id']:
            return jsonify({'error': 'Только владелец может приглашать'}), 403

        # Находим пользователя по логину
        from db import get_client_by_login
        target_client = get_client_by_login(db, login)
        if not target_client:
            return jsonify({'error': 'Пользователь не найден'}), 404

        # Приглашаем
        member = invite_client_to_group(db, group_id, target_client.id)
        logger.info(f"Client {target_client.id} invited to group {group_id} by {session['client_id']}")
        return jsonify({'message': 'Приглашение отправлено', 'member_id': member.id})
    finally:
        db.close()


@chat_group_bp.route('/invitations', methods=['GET'])
@login_required
def get_invitations():
    """Возвращает все pending-приглашения для текущего пользователя"""
    from flask import session
    from db import get_pending_invitations
    db = SessionLocal()
    try:
        invitations = get_pending_invitations(db, session['client_id'])
        return jsonify({'invitations': invitations})
    finally:
        db.close()


@chat_group_bp.route('/invitations/accept', methods=['POST'])
@login_required
def accept_invitation_api():
    """Принять приглашение в группу"""
    from flask import session
    from db import accept_invitation
    data = request.get_json()
    group_id = data.get('group_id')

    if not group_id:
        return jsonify({'error': 'Необходимо указать group_id'}), 400

    db = SessionLocal()
    try:
        success = accept_invitation(db, group_id, session['client_id'])
        if success:
            return jsonify({'message': 'Приглашение принято'})
        else:
            return jsonify({'error': 'Приглашение не найдено или уже обработано'}), 404
    finally:
        db.close()


@chat_group_bp.route('/client/chats', methods=['GET'])
@login_required
def get_client_chats():
    """Получить все чаты клиента (личные + группы)"""
    from flask import session
    from db import get_client_personal_chats
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
                'ai_enabled': c.ai_enabled,
                'updated_at': c.updated_at.isoformat() if c.updated_at else None
            } for c in personal_chats],
            'groups': [{
                'id': g.id,
                'name': g.name,
                'type': 'group',
                'ai_enabled': g.ai_enabled,
                'ai_name': g.ai_name,
                'created_at': g.created_at.isoformat()
            } for g in groups]
        })
    finally:
        db.close()
