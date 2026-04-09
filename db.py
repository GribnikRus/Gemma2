"""
База данных и модели для gemma-hub.
Используется таблица clients для веб-авторизации.
Таблица users зарезервирована для Telegram-бота.
"""
from sqlalchemy import create_engine, Column, Integer, String, Text, DateTime, ForeignKey, Boolean, Table
from sqlalchemy.orm import sessionmaker, declarative_base, relationship
from sqlalchemy.sql import func
import uuid
from config import DATABASE_URL

# Настройка движка и сессии
engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

# --- МОДЕЛИ ---

class Client(Base):
    __tablename__ = "clients"
    
    id = Column(Integer, primary_key=True, index=True)
    login = Column(String(100), unique=True, nullable=False, index=True)
    password_hash = Column(String(255), nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
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
    
    owner = relationship("Client", back_populates="personal_chats")
    messages = relationship("ChatMessage", back_populates="personal_chat", cascade="all, delete-orphan")

class ChatGroup(Base):
    __tablename__ = "chat_groups"
    
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(255), nullable=False)
    owner_id = Column(Integer, ForeignKey("clients.id"), nullable=False)
    description = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    
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
    Base.metadata.create_all(bind=engine)

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

def get_client_by_login(db, login: str):
    return db.query(Client).filter(Client.login == login).first()

def get_client_by_id(db, client_id: int):
    return db.query(Client).filter(Client.id == client_id).first()

def create_client(db, login: str, password_hash: str):
    db_client = Client(login=login, password_hash=password_hash)
    db.add(db_client)
    db.commit()
    db.refresh(db_client)
    return db_client

def is_client_member_of_group(db, client_id: int, group_id: int):
    member = db.query(GroupMember).filter(
        GroupMember.client_id == client_id,
        GroupMember.group_id == group_id,
        GroupMember.status == 'accepted'
    ).first()
    return member is not None

def get_group_members(db, group_id: int):
    return db.query(GroupMember).join(Client).filter(
        GroupMember.group_id == group_id,
        GroupMember.status == 'accepted'
    ).all()

def invite_client_to_group(db, group_id: int, target_client_id: int):
    # Проверка на дубликат
    existing = db.query(GroupMember).filter(
        GroupMember.group_id == group_id,
        GroupMember.client_id == target_client_id
    ).first()
    
    if existing:
        return existing
        
    new_member = GroupMember(group_id=group_id, client_id=target_client_id, status='pending')
    db.add(new_member)
    db.commit()
    db.refresh(new_member)
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
    return member

def create_group(db, name: str, owner_id: int, description: str = None):
    group = ChatGroup(name=name, owner_id=owner_id, description=description)
    db.add(group)
    db.flush()
    
    # Владелец автоматически становится участником со статусом accepted
    owner_member = GroupMember(group_id=group.id, client_id=owner_id, status='accepted')
    db.add(owner_member)
    db.commit()
    db.refresh(group)
    return group

def create_personal_chat(db, client_id: int, title: str = "Новый чат"):
    chat = PersonalChat(owner_id=client_id, title=title)
    db.add(chat)
    db.commit()
    db.refresh(chat)
    return chat

def get_personal_chat(db, chat_id: int, client_id: int):
    return db.query(PersonalChat).filter(
        PersonalChat.id == chat_id,
        PersonalChat.owner_id == client_id
    ).first()

def get_client_personal_chats(db, client_id: int):
    return db.query(PersonalChat).filter(
        PersonalChat.owner_id == client_id
    ).order_by(PersonalChat.updated_at.desc()).all()

def get_client_groups(db, client_id: int):
    memberships = db.query(GroupMember).filter(
        GroupMember.client_id == client_id,
        GroupMember.status == 'accepted'
    ).all()
    
    group_ids = [m.group_id for m in memberships]
    if not group_ids:
        return []
    return db.query(ChatGroup).filter(ChatGroup.id.in_(group_ids)).all()

def get_group_history(db, group_id: int, client_id: int, limit: int = 50):
    if not is_client_member_of_group(db, client_id, group_id):
        return []
    
    messages = db.query(ChatMessage).filter(
        ChatMessage.group_id == group_id
    ).order_by(ChatMessage.created_at.asc()).limit(limit).all()
    
    return messages

def get_personal_chat_history(db, chat_id: int, client_id: int, limit: int = 50):
    chat = get_personal_chat(db, chat_id, client_id)
    if not chat:
        return []
    
    messages = db.query(ChatMessage).filter(
        ChatMessage.personal_chat_id == chat_id
    ).order_by(ChatMessage.created_at.asc()).limit(limit).all()
    
    return messages

def add_message(db, content: str, sender_type: str, sender_id: int = None, 
                personal_chat_id: int = None, group_id: int = None, 
                message_type: str = 'text'):
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
    return message

def create_task_history(db, client_id: int, task_type: str, input_data: str = None):
    task = TaskHistory(
        client_id=client_id,
        task_type=task_type,
        input_data=input_data,
        status='processing'
    )
    db.add(task)
    db.commit()
    db.refresh(task)
    return task

def update_task_history(db, task_id: int, result: str = None, status: str = 'completed'):
    task = db.query(TaskHistory).get(task_id)
    if task:
        task.result_data = result
        task.status = status
        db.commit()
        db.refresh(task)
    return task

def create_observer_session(db, group_id: int, client_id: int, role_prompt: str, analysis_type: str = 'quick'):
    session = ObserverSession(
        group_id=group_id,
        creator_id=client_id,
        role_prompt=role_prompt,
        analysis_type=analysis_type
    )
    db.add(session)
    db.commit()
    db.refresh(session)
    return session

def add_observer_analysis(db, session_id: int, analysis_content: str, messages_analyzed: int = 0):
    analysis = ObserverAnalysis(
        session_id=session_id,
        analysis_text=analysis_content,
        messages_analyzed=messages_analyzed
    )
    db.add(analysis)
    db.commit()
    db.refresh(analysis)
    return analysis