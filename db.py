"""
База данных и модели для gemma-hub.
Используется таблица clients для веб-авторизации.
Таблица users зарезервирована для Telegram-бота.
"""
import logging
from sqlalchemy import create_engine, Column, Integer, String, Text, DateTime, ForeignKey, Boolean, Table
from sqlalchemy.orm import sessionmaker, declarative_base, relationship
from sqlalchemy.sql import func
import uuid
from config import DATABASE_URL, LOG_FORMAT, LOG_LEVEL

# Настройка логирования
logging.basicConfig(format=LOG_FORMAT, level=getattr(logging, LOG_LEVEL))
logger = logging.getLogger("db")

# Настройка движка и сессии
engine = create_engine(
    DATABASE_URL,
    pool_pre_ping=True,      # Проверка соединения перед использованием
    pool_recycle=3600,       # Пересоздание соединений через 1 час
    pool_size=10,            # Размер пула (для PostgreSQL)
    max_overflow=20          # Дополнительные соединения при пике
)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

# --- МОДЕЛИ ---

class Client(Base):
    __tablename__ = "clients"
    
    id = Column(Integer, primary_key=True, index=True)
    login = Column(String(100), unique=True, nullable=False, index=True)
    password_hash = Column(String(255), nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    last_seen = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    client_uuid = Column(String(36), unique=True, nullable=False, default=lambda: str(uuid.uuid4()))
    # Связи
    personal_chats = relationship("PersonalChat", back_populates="owner", cascade="all, delete-orphan")
    group_memberships = relationship("GroupMember", back_populates="client", cascade="all, delete-orphan")
    task_history = relationship("TaskHistory", back_populates="client", cascade="all, delete-orphan")

class PersonalChat(Base):
    __tablename__ = "personal_chats"
    
    id = Column(Integer, primary_key=True, index=True)
    owner_id = Column(Integer, ForeignKey("clients.id"), nullable=False)
    title = Column(String(255), default="Личный чат")
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    ai_enabled = Column(Boolean, default=True)
    ai_name = Column(String(100), default="Гемма")
    
    owner = relationship("Client", back_populates="personal_chats")
    messages = relationship("ChatMessage", back_populates="personal_chat", cascade="all, delete-orphan")

class ChatGroup(Base):
    __tablename__ = "chat_groups"
    
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(255), nullable=False)
    owner_id = Column(Integer, ForeignKey("clients.id"), nullable=False)
    description = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    ai_enabled = Column(Boolean, default=True)
    ai_name = Column(String(100), default="Гемма")
    
    owner = relationship("Client", foreign_keys=[owner_id])
    members = relationship("GroupMember", back_populates="group", cascade="all, delete-orphan")
    messages = relationship("ChatMessage", back_populates="group", cascade="all, delete-orphan")
    observer_sessions = relationship("ObserverSession", back_populates="group", cascade="all, delete-orphan")

class GroupMember(Base):
    __tablename__ = "group_members"
    
    id = Column(Integer, primary_key=True, index=True)
    group_id = Column(Integer, ForeignKey("chat_groups.id"), nullable=False)
    client_id = Column(Integer, ForeignKey("clients.id"), nullable=False)
    status = Column(String(20), default='pending')  # pending, accepted, rejected
    joined_at = Column(DateTime(timezone=True), server_default=func.now())
    
    group = relationship("ChatGroup", back_populates="members")
    client = relationship("Client", back_populates="group_memberships")

class ChatMessage(Base):
    __tablename__ = "chat_messages"
    
    id = Column(Integer, primary_key=True, index=True)
    content = Column(Text, nullable=False)
    sender_id = Column(Integer, ForeignKey("clients.id"), nullable=True) # NULL если сообщение от ИИ
    personal_chat_id = Column(Integer, ForeignKey("personal_chats.id"), nullable=True)
    group_id = Column(Integer, ForeignKey("chat_groups.id"), nullable=True)
    is_ai_response = Column(Boolean, default=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
        # ДОБАВЛЕНО/ПРОВЕРЕНО: поле sender_type
    sender_type = Column(String(20), nullable=False, default='client') # 'client' или 'ai'
    
    sender = relationship("Client")
    personal_chat = relationship("PersonalChat", back_populates="messages")
    group = relationship("ChatGroup", back_populates="messages")

class TaskHistory(Base):
    __tablename__ = "task_history"
    
    id = Column(Integer, primary_key=True, index=True)
    client_id = Column(Integer, ForeignKey("clients.id"), nullable=False)
    task_type = Column(String(50)) # 'chat', 'vision', 'audio'
    input_data = Column(Text, nullable=True) 
    result_data = Column(Text, nullable=True) 
    status = Column(String(20), default='pending')
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    
    client = relationship("Client", back_populates="task_history")

class ObserverSession(Base):
    __tablename__ = "observer_sessions"
    
    id = Column(Integer, primary_key=True, index=True)
    group_id = Column(Integer, ForeignKey("chat_groups.id"), nullable=False)
    creator_id = Column(Integer, ForeignKey("clients.id"), nullable=False)
    role_prompt = Column(Text, nullable=True)
    analysis_type = Column(String(20), default='quick') 
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    
    group = relationship("ChatGroup", back_populates="observer_sessions")
    analyses = relationship("ObserverAnalysis", back_populates="session", cascade="all, delete-orphan")

class ObserverAnalysis(Base):
    __tablename__ = "observer_analyses"
    
    id = Column(Integer, primary_key=True, index=True)
    session_id = Column(Integer, ForeignKey("observer_sessions.id"), nullable=False)
    analysis_text = Column(Text, nullable=False)
    messages_analyzed = Column(Integer, default=0)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    
    session = relationship("ObserverSession", back_populates="analyses")

# --- ХЕЛПЕРЫ ---

def init_db():
    """Инициализация таблиц БД"""
    logger.info("Initializing database tables")
    Base.metadata.create_all(bind=engine)
    logger.info("Database initialization completed")

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

def get_client_by_login(db, login: str):
    client = db.query(Client).filter(Client.login == login).first()
    if client:
        logger.debug(f"Client found by login: {login}")
    else:
        logger.debug(f"Client not found by login: {login}")
    return client

def get_client_by_id(db, client_id: int):
    client = db.query(Client).filter(Client.id == client_id).first()
    if client:
        logger.debug(f"Client found by id: {client_id}")
    else:
        logger.debug(f"Client not found by id: {client_id}")
    return client

def create_client(db, login: str, password_hash: str):
    logger.info(f"Creating new client: {login}")
    db_client = Client(login=login, password_hash=password_hash)
    db.add(db_client)
    db.commit()
    db.refresh(db_client)
    logger.info(f"Client created successfully: {login} (id={db_client.id})")
    return db_client

def is_client_member_of_group(db, client_id: int, group_id: int):
    member = db.query(GroupMember).filter(
        GroupMember.client_id == client_id,
        GroupMember.group_id == group_id,
        GroupMember.status == 'accepted'
    ).first()
    result = member is not None
    logger.debug(f"Client {client_id} membership in group {group_id}: {result}")
    return result

def get_group_members(db, group_id: int):
    members = db.query(GroupMember).join(Client).filter(
        GroupMember.group_id == group_id,
        GroupMember.status == 'accepted'
    ).all()
    logger.debug(f"Retrieved {len(members)} members for group {group_id}")
    return members

def invite_client_to_group(db, group_id: int, target_client_id: int):
    # Проверка на дубликат
    existing = db.query(GroupMember).filter(
        GroupMember.group_id == group_id,
        GroupMember.client_id == target_client_id
    ).first()
    
    if existing:
        logger.debug(f"Invite already exists for client {target_client_id} in group {group_id}")
        return existing
        
    new_member = GroupMember(group_id=group_id, client_id=target_client_id, status='pending')
    db.add(new_member)
    db.commit()
    db.refresh(new_member)
    logger.info(f"Client {target_client_id} invited to group {group_id}")
    return new_member

def accept_group_invite(db, group_id: int, client_id: int):
    member = db.query(GroupMember).filter(
        GroupMember.group_id == group_id,
        GroupMember.client_id == client_id,
        GroupMember.status == 'pending'
    ).first()
    
    if member:
        member.status = 'accepted'
        db.commit()
        db.refresh(member)
        logger.info(f"Client {client_id} accepted invite to group {group_id}")
    else:
        logger.warning(f"No pending invite found for client {client_id} in group {group_id}")
    return member

def create_group(db, name: str, owner_id: int, description: str = None):
    logger.info(f"Creating new group: {name} by owner {owner_id}")
    group = ChatGroup(name=name, owner_id=owner_id, description=description)
    db.add(group)
    db.flush()
    
    # Владелец автоматически становится участником со статусом accepted
    owner_member = GroupMember(group_id=group.id, client_id=owner_id, status='accepted')
    db.add(owner_member)
    db.commit()
    db.refresh(group)
    logger.info(f"Group created successfully: {name} (id={group.id})")
    return group

def create_personal_chat(db, client_id: int, title: str = "Новый чат"):
    logger.info(f"Creating personal chat for client {client_id}: {title}")
    chat = PersonalChat(owner_id=client_id, title=title)
    db.add(chat)
    db.commit()
    db.refresh(chat)
    logger.info(f"Personal chat created: id={chat.id}, title={title}")
    return chat

def get_personal_chat(db, chat_id: int, client_id: int):
    chat = db.query(PersonalChat).filter(
        PersonalChat.id == chat_id,
        PersonalChat.owner_id == client_id
    ).first()
    if chat:
        logger.debug(f"Personal chat {chat_id} retrieved for client {client_id}")
    else:
        logger.debug(f"Personal chat {chat_id} not found for client {client_id}")
    return chat

def get_client_personal_chats(db, client_id: int):
    chats = db.query(PersonalChat).filter(
        PersonalChat.owner_id == client_id
    ).order_by(PersonalChat.updated_at.desc()).all()
    logger.debug(f"Retrieved {len(chats)} personal chats for client {client_id}")
    return chats

def get_client_groups(db, client_id: int):
    memberships = db.query(GroupMember).filter(
        GroupMember.client_id == client_id,
        GroupMember.status == 'accepted'
    ).all()
    
    group_ids = [m.group_id for m in memberships]
    if not group_ids:
        return []
    groups = db.query(ChatGroup).filter(ChatGroup.id.in_(group_ids)).all()
    logger.debug(f"Retrieved {len(groups)} groups for client {client_id}")
    return groups

def get_group_history(db, group_id: int, client_id: int, limit: int = 50, last_message_id: int = None):
    if not is_client_member_of_group(db, client_id, group_id):
        logger.warning(f"Client {client_id} not member of group {group_id}, denying history access")
        return []
    
    query = db.query(ChatMessage).filter(ChatMessage.group_id == group_id)
    if last_message_id is not None:
        query = query.filter(ChatMessage.id > last_message_id)
    
    messages = query.order_by(ChatMessage.created_at.asc()).limit(limit).all()
    logger.debug(f"Retrieved {len(messages)} messages for group {group_id} (last_message_id={last_message_id})")
    return messages

def get_personal_chat_history(db, chat_id: int, client_id: int, limit: int = 50, last_message_id: int = None):
    chat = get_personal_chat(db, chat_id, client_id)
    if not chat:
        return []
    
    query = db.query(ChatMessage).filter(ChatMessage.personal_chat_id == chat_id)
    if last_message_id is not None:
        query = query.filter(ChatMessage.id > last_message_id)
    
    messages = query.order_by(ChatMessage.created_at.asc()).limit(limit).all()
    logger.debug(f"Retrieved {len(messages)} messages for personal chat {chat_id} (last_message_id={last_message_id})")
    return messages

def add_message(db, content: str, sender_type: str, sender_id: int = None, 
                personal_chat_id: int = None, group_id: int = None, 
                message_type: str = 'text'):
    chat_info = f"personal_chat_id={personal_chat_id}" if personal_chat_id else f"group_id={group_id}"
    logger.info(f"Adding message to chat ({chat_info}) by {sender_type} (sender_id={sender_id})")
    
    message = ChatMessage(
        content=content,
        sender_type=sender_type, # 'client' or 'ai'
        sender_id=sender_id,
        personal_chat_id=personal_chat_id,
        group_id=group_id,
        is_ai_response=(sender_type == 'ai')
    )
    db.add(message)
    
    # Обновляем updated_at у личного чата
    if personal_chat_id:
        chat = db.query(PersonalChat).get(personal_chat_id)
        if chat:
            chat.updated_at = func.now()
    
    db.commit()
    db.refresh(message)
    logger.info(f"Message added to chat_id={personal_chat_id or group_id} by client_id={sender_id or 'AI'}")
    return message

def create_task_history(db, client_id: int, task_type: str, input_data: str = None):
    logger.info(f"Creating task history for client {client_id}, type={task_type}")
    task = TaskHistory(
        client_id=client_id,
        task_type=task_type,
        input_data=input_data,
        status='processing'
    )
    db.add(task)
    db.commit()
    db.refresh(task)
    logger.info(f"Task history created: id={task.id}")
    return task

def update_task_history(db, task_id: int, result: str = None, status: str = 'completed'):
    task = db.query(TaskHistory).get(task_id)
    if task:
        task.result_data = result
        task.status = status
        db.commit()
        db.refresh(task)
        logger.info(f"Task {task_id} updated with status={status}")
    else:
        logger.error(f"Task {task_id} not found for update")
    return task

def create_observer_session(db, group_id: int, client_id: int, role_prompt: str, analysis_type: str = 'quick'):
    logger.info(f"Creating observer session for group {group_id} by client {client_id}")
    session = ObserverSession(
        group_id=group_id,
        creator_id=client_id,
        role_prompt=role_prompt,
        analysis_type=analysis_type
    )
    db.add(session)
    db.commit()
    db.refresh(session)
    logger.info(f"Observer session created: id={session.id}")
    return session

def add_observer_analysis(db, session_id: int, analysis_content: str, messages_analyzed: int = 0):
    logger.info(f"Adding observer analysis for session {session_id}")
    analysis = ObserverAnalysis(
        session_id=session_id,
        analysis_text=analysis_content,
        messages_analyzed=messages_analyzed
    )
    db.add(analysis)
    db.commit()
    db.refresh(analysis)
    logger.info(f"Observer analysis added: id={analysis.id}")
    return analysis


# ==================== НОВЫЕ HELPER ФУНКЦИИ ====================

def update_client_last_seen(db, client_id: int):
    """Обновляет last_seen для клиента"""
    client = db.query(Client).filter(Client.id == client_id).first()
    if client:
        client.last_seen = func.now()
        db.commit()
        logger.debug(f"Updated last_seen for client {client_id}")
    return client


def update_user_online_status(db, client_id: int, is_online: bool):
    """Обновляет last_seen для клиента при подключении/отключении WebSocket"""
    client = db.query(Client).filter(Client.id == client_id).first()
    if client:
        if is_online:
            client.last_seen = func.now()  # Устанавливаем текущее время при подключении
        else:
            # При отключении можно установить время в прошлое, чтобы считался offline
            from datetime import datetime, timedelta
            client.last_seen = datetime.utcnow() - timedelta(minutes=10)  # 10 минут назад
        db.commit()
        logger.debug(f"Updated online status for client {client_id}: {'online' if is_online else 'offline'}")
    return client


def get_all_users_with_status(db):
    """Возвращает список всех пользователей со статусом online/offline"""
    from datetime import datetime, timedelta
    clients = db.query(Client).all()
    users = []
    now = datetime.utcnow()
    for client in clients:
        is_online = False
        if client.last_seen:
            # Если last_seen меньше 5 минут назад - считаем онлайн
            is_online = (now - client.last_seen) < timedelta(minutes=5)
        users.append({
            'id': client.id,
            'login': client.login,
            'last_seen': client.last_seen.isoformat() if client.last_seen else None,
            'is_online': is_online
        })
    logger.debug(f"Retrieved {len(users)} users with status")
    return users


def get_pending_invitations(db, client_id: int):
    """Возвращает все pending-приглашения для клиента"""
    memberships = db.query(GroupMember).join(ChatGroup).filter(
        GroupMember.client_id == client_id,
        GroupMember.status == 'pending'
    ).all()
    
    invitations = []
    for m in memberships:
        invitations.append({
            'id': m.id,
            'group_id': m.group_id,
            'group_name': m.group.name,
            'status': m.status,
            'invited_at': m.joined_at.isoformat() if m.joined_at else None
        })
    logger.debug(f"Retrieved {len(invitations)} pending invitations for client {client_id}")
    return invitations


def accept_invitation(db, group_id: int, client_id: int):
    """Принимает приглашение в группу"""
    member = db.query(GroupMember).filter(
        GroupMember.group_id == group_id,
        GroupMember.client_id == client_id,
        GroupMember.status == 'pending'
    ).first()
    
    if member:
        member.status = 'accepted'
        db.commit()
        logger.info(f"Client {client_id} accepted invitation to group {group_id}")
        return True
    else:
        logger.warning(f"No pending invitation found for client {client_id} in group {group_id}")
        return False


def get_personal_chat_by_id(db, chat_id: int):
    """Получает личный чат по ID"""
    chat = db.query(PersonalChat).filter(PersonalChat.id == chat_id).first()
    return chat


def get_group_by_id(db, group_id: int):
    """Получает группу по ID"""
    group = db.query(ChatGroup).filter(ChatGroup.id == group_id).first()
    return group


def toggle_chat_ai_enabled(db, chat_type: str, chat_id: int, ai_enabled: bool):
    """Переключает флаг ai_enabled для чата"""
    if chat_type == 'personal':
        chat = get_personal_chat_by_id(db, chat_id)
        if chat:
            chat.ai_enabled = ai_enabled
            db.commit()
            logger.info(f"Set ai_enabled={ai_enabled} for personal chat {chat_id}")
            return True
    elif chat_type == 'group':
        group = get_group_by_id(db, chat_id)
        if group:
            group.ai_enabled = ai_enabled
            db.commit()
            logger.info(f"Set ai_enabled={ai_enabled} for group {chat_id}")
            return True
    return False


def set_chat_ai_name(db, chat_type: str, chat_id: int, new_name: str):
    """Устанавливает новое имя ИИ для чата"""
    # Валидация имени: минимум 2 символа, только буквы, цифры, пробелы и некоторые знаки препинания
    import re
    if len(new_name) < 2:
        logger.warning(f"AI name too short: {new_name}")
        return False
    if not re.match(r'^[\w\s\-_.,!?\']+$', new_name, re.UNICODE):
        logger.warning(f"Invalid AI name characters: {new_name}")
        return False
    
    if chat_type == 'personal':
        chat = get_personal_chat_by_id(db, chat_id)
        if chat:
            chat.ai_name = new_name
            db.commit()
            logger.info(f"Set ai_name={new_name} for personal chat {chat_id}")
            return True
    elif chat_type == 'group':
        group = get_group_by_id(db, chat_id)
        if group:
            group.ai_name = new_name
            db.commit()
            logger.info(f"Set ai_name={new_name} for group {chat_id}")
            return True
    return False