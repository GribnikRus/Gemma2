# Blueprints package initialization
from .auth import auth_bp
from .chat_personal import chat_personal_bp
from .chat_group import chat_group_bp
from .media_upload import media_upload_bp
from .observer import observer_bp
from .users import users_bp
from .tasks import tasks_bp

__all__ = [
    'auth_bp',
    'chat_personal_bp',
    'chat_group_bp',
    'media_upload_bp',
    'observer_bp',
    'users_bp',
    'tasks_bp'
]
