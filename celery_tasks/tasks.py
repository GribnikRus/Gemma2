"""
Celery задачи для фоновой обработки тяжелых операций.
Используется для анализа изображений, аудио и других ресурсоемких задач.
"""
from celery import Celery
from config import CELERY_BROKER_URL, CELERY_RESULT_BACKEND
from ollama_client import OllamaClient
import base64

# Инициализация Celery
celery_app = Celery(
    'gemma_hub',
    broker=CELERY_BROKER_URL,
    backend=CELERY_RESULT_BACKEND
)

# Конфигурация
celery_app.conf.update(
    task_serializer='json',
    accept_content=['json'],
    result_serializer='json',
    timezone='UTC',
    enable_utc=True,
    task_track_started=True,
    task_time_limit=300,  # 5 минут максимум
)


@celery_app.task(bind=True, max_retries=3)
def analyze_image_task(self, image_base64: str, prompt: str = "Опиши это изображение подробно.") -> dict:
    """
    Фоновая задача для анализа изображения.
    
    Args:
        image_base64: Изображение в base64
        prompt: Промт для анализа
    
    Returns:
        dict с результатом анализа
    """
    try:
        client = OllamaClient()
        result = client.analyze_image(image_base64, prompt)
        
        return {
            'status': 'success',
            'result': result,
            'task_id': self.request.id
        }
    except Exception as e:
        # Retry logic
        try:
            raise self.retry(exc=e, countdown=60)
        except self.MaxRetriesExceededError:
            return {
                'status': 'failed',
                'error': str(e),
                'task_id': self.request.id
            }


@celery_app.task(bind=True, max_retries=3)
def transcribe_audio_task(self, file_path: str, file_name: str) -> dict:
    """
    Фоновая задача для транскрибации аудио.
    Пока использует заглушку, в будущем будет Whisper.
    
    Args:
        file_path: Путь к аудиофайлу
        file_name: Имя файла
    
    Returns:
        dict с результатом транскрибации
    """
    try:
        # TODO: Интегрировать Whisper API или другую speech-to-text модель
        # Пока эмулируем задержку и возвращаем заглушку
        client = OllamaClient()
        result = client.transcribe_audio_stub(f"{file_name} ({file_path})")
        
        return {
            'status': 'success',
            'result': result,
            'task_id': self.request.id,
            'note': 'Это эмуляция. Подключите Whisper для реальной транскрибации.'
        }
    except Exception as e:
        try:
            raise self.retry(exc=e, countdown=60)
        except self.MaxRetriesExceededError:
            return {
                'status': 'failed',
                'error': str(e),
                'task_id': self.request.id
            }


@celery_app.task(bind=True, max_retries=2)
def analyze_chat_observer_task(self, messages: list, role_prompt: str, 
                                analysis_type: str = 'quick') -> dict:
    """
    Фоновая задача для анализа чата наблюдателем.
    
    Args:
        messages: Список сообщений чата
        role_prompt: Роль аналитика
        analysis_type: quick или full
    
    Returns:
        dict с результатом анализа
    """
    try:
        client = OllamaClient()
        result = client.analyze_chat_as_observer(messages, role_prompt, analysis_type)
        
        return {
            'status': 'success',
            'result': result,
            'messages_analyzed': len(messages),
            'task_id': self.request.id
        }
    except Exception as e:
        try:
            raise self.retry(exc=e, countdown=30)
        except self.MaxRetriesExceededError:
            return {
                'status': 'failed',
                'error': str(e),
                'task_id': self.request.id
            }
