"""
База данных и модели для gemma-hub.
Используется таблица clients для веб-авторизации.
Таблица users зарезервирована для Telegram-бота.
"""
from sqlalchemy import create_engine, Column, Integer, String, Text, DateTime, ForeignKey, Boolean, Table
from sqlalchemy.orm import sessionmaker, declarative_base, relationship
from datetime import datetime
from config import DATABASE_URL

engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


# Таблица связи многие-ко-многим для участников групп
group_members = Table(
    'group_members_assoc', Base.metadata,
    Column('group_id', Integer, ForeignKey('chat_groups.id'), primary_key=True),
    Column('client_id', Integer, ForeignKey('clients.id'), primary_key=True),
    Column('status', String(20), default='pending'),  # pending, accepted, rejected
    Column('joined_at', DateTime, default=datetime.utcnow),
    extend_existing=True
)


class Client(Base):
    """Веб-клиенты (не путать с users для Telegram)"""
    __tablename__ = 'clients'
    
    id = Column(Integer, primary_key=True)
    username = Column(String(100), unique=True, nullable=False)
    password_hash = Column(String(255), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    is_active = Column(Boolean, default=True)
    
    # Связи
    personal_chats = relationship("PersonalChat", back_populates="client", cascade="all, delete-orphan")
    group_memberships = relationship("GroupMember", back_populates="client", cascade="all, delete-orphan")
    task_history = relationship("TaskHistory", back_populates="client", cascade="all, delete-orphan")


class PersonalChat(Base):
    """Личные чаты клиента с ИИ"""
    __tablename__ = 'personal_chats'
    
    id = Column(Integer, primary_key=True)
    client_id = Column(Integer, ForeignKey('clients.id'), nullable=False)
    title = Column(String(200), default="Новый чат")
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    client = relationship("Client", back_populates="personal_chats")
    messages = relationship("ChatMessage", back_populates="personal_chat", cascade="all, delete-orphan", foreign_keys="ChatMessage.personal_chat_id")


class ChatGroup(Base):
    """Группы для совместного чата"""
    __tablename__ = 'chat_groups'
    
    id = Column(Integer, primary_key=True)
    name = Column(String(200), nullable=False)
    owner_id = Column(Integer, ForeignKey('clients.id'), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    description = Column(Text, nullable=True)
    
    owner = relationship("Client", foreign_keys=[owner_id])
    members = relationship("GroupMember", back_populates="group", cascade="all, delete-orphan")
    messages = relationship("ChatMessage", back_populates="group", cascade="all, delete-orphan", foreign_keys="ChatMessage.group_id")
    observer_sessions = relationship("ObserverSession", back_populates="group", cascade="all, delete-orphan")


class GroupMember(Base):
    """Участники группы"""
    __tablename__ = 'group_members'
    
    id = Column(Integer, primary_key=True)
    group_id = Column(Integer, ForeignKey('chat_groups.id'), nullable=False)
    client_id = Column(Integer, ForeignKey('clients.id'), nullable=False)
    status = Column(String(20), default='pending')  # pending, accepted, rejected
    invited_at = Column(DateTime, default=datetime.utcnow)
    
    group = relationship("ChatGroup", back_populates="members")
    client = relationship("Client", back_populates="group_memberships")


class ChatMessage(Base):
    """Сообщения в чатах (личных и групповых)"""
    __tablename__ = 'chat_messages'
    
    id = Column(Integer, primary_key=True)
    personal_chat_id = Column(Integer, ForeignKey('personal_chats.id'), nullable=True)
    group_id = Column(Integer, ForeignKey('chat_groups.id'), nullable=True)
    sender_id = Column(Integer, ForeignKey('clients.id'), nullable=True)  # None если от ИИ
    sender_type = Column(String(20), nullable=False)  # 'client', 'ai'
    content = Column(Text, nullable=False)
    message_type = Column(String(50), default='text')  # text, image_analysis, audio_transcript, observation
    created_at = Column(DateTime, default=datetime.utcnow)
    
    personal_chat = relationship("PersonalChat", back_populates="messages")
    group = relationship("ChatGroup", back_populates="messages")
    sender = relationship("Client")


class TaskHistory(Base):
    """История задач (анализ изображений, аудио и т.д.)"""
    __tablename__ = 'task_history'
    
    id = Column(Integer, primary_key=True)
    client_id = Column(Integer, ForeignKey('clients.id'), nullable=False)
    task_type = Column(String(50), nullable=False)  # image_analysis, audio_transcript, chat, observation
    input_data = Column(Text, nullable=True)  # путь к файлу или краткое описание
    result = Column(Text, nullable=True)
    status = Column(String(20), default='pending')  # pending, processing, completed, failed
    created_at = Column(DateTime, default=datetime.utcnow)
    completed_at = Column(DateTime, nullable=True)
    
    client = relationship("Client", back_populates="task_history")


class ObserverSession(Base):
    """Сессии наблюдателя для анализа чатов"""
    __tablename__ = 'observer_sessions'
    
    id = Column(Integer, primary_key=True)
    group_id = Column(Integer, ForeignKey('chat_groups.id'), nullable=False)
    client_id = Column(Integer, ForeignKey('clients.id'), nullable=False)
    role_prompt = Column(Text, nullable=False)  # системный промт для роли ИИ
    analysis_type = Column(String(50), default='quick')  # quick, full
    created_at = Column(DateTime, default=datetime.utcnow)
    
    group = relationship("ChatGroup", back_populates="observer_sessions")
    client = relationship("Client")
    analyses = relationship("ObserverAnalysis", back_populates="session", cascade="all, delete-orphan")


class ObserverAnalysis(Base):
    """Результаты анализа наблюдателя"""
    __tablename__ = 'observer_analyses'
    
    id = Column(Integer, primary_key=True)
    session_id = Column(Integer, ForeignKey('observer_sessions.id'), nullable=False)
    analysis_content = Column(Text, nullable=False)
    messages_analyzed = Column(Integer, default=0)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    session = relationship("ObserverSession", back_populates="analyses")


# Функции для работы с БД
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db():
    """Инициализация таблиц БД"""
    Base.metadata.create_all(bind=engine)


# Хелперы для работы с клиентами и группами
def get_client_by_username(db, username: str):
    return db.query(Client).filter(Client.username == username).first()


def get_client_by_id(db, client_id: int):
    return db.query(Client).filter(Client.id == client_id).first()


def create_personal_chat(db, client_id: int, title: str = "Новый чат"):
    chat = PersonalChat(client_id=client_id, title=title)
    db.add(chat)
    db.commit()
    db.refresh(chat)
    return chat


def get_personal_chat(db, chat_id: int, client_id: int):
    return db.query(PersonalChat).filter(
        PersonalChat.id == chat_id,
        PersonalChat.client_id == client_id
    ).first()


def get_client_personal_chats(db, client_id: int):
    return db.query(PersonalChat).filter(
        PersonalChat.client_id == client_id
    ).order_by(PersonalChat.updated_at.desc()).all()


def create_group(db, name: str, owner_id: int, description: str = None):
    group = ChatGroup(name=name, owner_id=owner_id, description=description)
    db.add(group)
    db.flush()
    
    # Добавляем владельца как участника со статусом accepted
    member = GroupMember(group_id=group.id, client_id=owner_id, status='accepted')
    db.add(member)
    
    db.commit()
    db.refresh(group)
    return group


def invite_client_to_group(db, group_id: int, client_id: int):
    """Пригласить клиента в группу"""
    existing = db.query(GroupMember).filter(
        GroupMember.group_id == group_id,
        GroupMember.client_id == client_id
    ).first()
    
    if existing:
        return existing
    
    member = GroupMember(group_id=group_id, client_id=client_id, status='pending')
    db.add(member)
    db.commit()
    db.refresh(member)
    return member


def accept_group_invite(db, group_id: int, client_id: int):
    """Принять приглашение в группу"""
    member = db.query(GroupMember).filter(
        GroupMember.group_id == group_id,
        GroupMember.client_id == client_id
    ).first()
    
    if member:
        member.status = 'accepted'
        db.commit()
        db.refresh(member)
    return member


def is_client_member_of_group(db, group_id: int, client_id: int):
    """Проверить является ли клиент участником группы"""
    member = db.query(GroupMember).filter(
        GroupMember.group_id == group_id,
        GroupMember.client_id == client_id,
        GroupMember.status == 'accepted'
    ).first()
    return member is not None


def get_client_groups(db, client_id: int):
    """Получить все группы, где клиент является участником"""
    memberships = db.query(GroupMember).filter(
        GroupMember.client_id == client_id,
        GroupMember.status == 'accepted'
    ).all()
    
    group_ids = [m.group_id for m in memberships]
    return db.query(ChatGroup).filter(ChatGroup.id.in_(group_ids)).all()


def get_group_history(db, group_id: int, client_id: int, limit: int = 50):
    """Получить историю сообщений группы (только для участников)"""
    if not is_client_member_of_group(db, group_id, client_id):
        return []
    
    messages = db.query(ChatMessage).filter(
        ChatMessage.group_id == group_id
    ).order_by(ChatMessage.created_at.asc()).limit(limit).all()
    
    return messages


def get_personal_chat_history(db, chat_id: int, client_id: int, limit: int = 50):
    """Получить историю личного чата"""
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
    """Добавить сообщение в чат"""
    message = ChatMessage(
        content=content,
        sender_type=sender_type,
        sender_id=sender_id,
        personal_chat_id=personal_chat_id,
        group_id=group_id,
        message_type=message_type
    )
    db.add(message)
    
    # Обновляем updated_at у личного чата
    if personal_chat_id:
        chat = db.query(PersonalChat).get(personal_chat_id)
        if chat:
            chat.updated_at = datetime.utcnow()
    
    db.commit()
    db.refresh(message)
    return message


def create_task_history(db, client_id: int, task_type: str, input_data: str = None):
    """Создать запись в истории задач"""
    task = TaskHistory(
        client_id=client_id,
        task_type=task_type,
        input_data=input_data,
        status='pending'
    )
    db.add(task)
    db.commit()
    db.refresh(task)
    return task


def update_task_history(db, task_id: int, result: str = None, status: str = 'completed'):
    """Обновить запись в истории задач"""
    task = db.query(TaskHistory).get(task_id)
    if task:
        task.result = result
        task.status = status
        task.completed_at = datetime.utcnow()
        db.commit()
        db.refresh(task)
    return task


def create_observer_session(db, group_id: int, client_id: int, role_prompt: str, analysis_type: str = 'quick'):
    """Создать сессию наблюдателя"""
    session = ObserverSession(
        group_id=group_id,
        client_id=client_id,
        role_prompt=role_prompt,
        analysis_type=analysis_type
    )
    db.add(session)
    db.commit()
    db.refresh(session)
    return session


def add_observer_analysis(db, session_id: int, analysis_content: str, messages_analyzed: int = 0):
    """Добавить результат анализа наблюдателя"""
    analysis = ObserverAnalysis(
        session_id=session_id,
        analysis_content=analysis_content,
        messages_analyzed=messages_analyzed
    )
    db.add(analysis)
    db.commit()
    db.refresh(analysis)
    return analysis
