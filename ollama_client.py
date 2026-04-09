"""
Клиент для взаимодействия с Ollama API.
Унифицированный класс для отправки запросов к модели.
"""
import logging
import requests
import base64
from typing import Optional, List
from config import (
    OLLAMA_URL, 
    OLLAMA_MODEL_CHAT, 
    OLLAMA_MODEL_VISION,
    OLLAMA_TEMPERATURE,
    OLLAMA_TOP_K,
    OLLAMA_TOP_P,
    LOG_FORMAT,
    LOG_LEVEL
)

# Настройка логирования
logging.basicConfig(format=LOG_FORMAT, level=getattr(logging, LOG_LEVEL))
logger = logging.getLogger("ollama")


class OllamaClient:
    """Клиент для работы с Ollama API"""
    
    def __init__(self, url: str = OLLAMA_URL, model: str = OLLAMA_MODEL_CHAT):
        self.url = url
        self.model = model
        self.timeout = 120  # секунды
        # Параметры генерации для Gemma 4
        self.temperature = OLLAMA_TEMPERATURE
        self.top_k = OLLAMA_TOP_K
        self.top_p = OLLAMA_TOP_P
    
    def generate(self, prompt: str, system_prompt: Optional[str] = None, 
                 images: Optional[List[str]] = None, stream: bool = False,
                 temperature: Optional[float] = None,
                 top_k: Optional[int] = None,
                 top_p: Optional[float] = None) -> dict:
        """
        Генерация ответа от модели через /api/generate endpoint.
        
        Args:
            prompt: Основной промт
            system_prompt: Системный промт (роль ИИ)
            images: Список base64 кодированных изображений
            stream: Потоковый режим
            temperature: Температура генерации (0.0-2.0)
            top_k: Top-K sampling
            top_p: Top-P (nucleus) sampling
        
        Returns:
            dict с ответом от API
        """
        logger.debug(f"Sending request to {self.model} (prompt length: {len(prompt)} chars)")
        
        payload = {
            "model": self.model,
            "prompt": prompt,
            "stream": stream,
            "options": {
                "temperature": temperature if temperature is not None else self.temperature,
                "top_k": top_k if top_k is not None else self.top_k,
                "top_p": top_p if top_p is not None else self.top_p,
            }
        }
        
        if system_prompt:
            payload["system"] = system_prompt
            logger.debug(f"System prompt set: {len(system_prompt)} chars")
        
        if images:
            payload["images"] = images
            logger.debug(f"Attached {len(images)} image(s) for vision analysis")
        
        try:
            response = requests.post(
                f"{self.url}/api/generate",
                json=payload,
                timeout=self.timeout
            )
            response.raise_for_status()
            result = response.json()
            logger.info(f"Received response from {self.model} ({len(result.get('response', ''))} chars)")
            return result
        except requests.exceptions.RequestException as e:
            logger.error(f"Request failed: {str(e)}")
            return {"error": str(e), "response": None}
    
    def chat(self, message: str, system_prompt: Optional[str] = None,
             images: Optional[List[str]] = None,
             temperature: Optional[float] = None,
             top_k: Optional[int] = None,
             top_p: Optional[float] = None) -> str:
        """
        Чат с моделью через /api/chat endpoint (предпочтительно для диалогов).
        Поддерживает мультимодальность (изображения в поле images).
        
        Args:
            message: Сообщение пользователя
            system_prompt: Системный промт (роль ИИ)
            images: Список base64 кодированных изображений (для мультимодальных моделей)
            temperature: Температура генерации
            top_k: Top-K sampling
            top_p: Top-P sampling
        
        Returns:
            Текст ответа или сообщение об ошибке
        """
        logger.info(f"Chat request to {self.model} (message length: {len(message)} chars)")
        
        # Формируем сообщения в формате Ollama Chat API
        messages = []
        
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        
        # Базовое сообщение пользователя
        user_message = {"role": "user", "content": message}
        if images:
            user_message["images"] = images
            logger.debug(f"Attaching {len(images)} image(s) to chat message")
        
        messages.append(user_message)
        
        payload = {
            "model": self.model,
            "messages": messages,
            "stream": False,
            "options": {
                "temperature": temperature if temperature is not None else self.temperature,
                "top_k": top_k if top_k is not None else self.top_k,
                "top_p": top_p if top_p is not None else self.top_p,
            }
        }
        
        try:
            response = requests.post(
                f"{self.url}/api/chat",
                json=payload,
                timeout=self.timeout
            )
            response.raise_for_status()
            result = response.json()
            
            # Извлекаем ответ из формата chat API
            content = result.get("message", {}).get("content", "")
            if content:
                logger.info(f"Chat response received ({len(content)} chars)")
                return content
            else:
                logger.warning("Empty response from chat API")
                return "Нет ответа от модели"
                
        except requests.exceptions.RequestException as e:
            logger.error(f"Chat request failed: {str(e)}")
            return f"Ошибка Ollama: {str(e)}"
    
    def analyze_image(self, image_base64: str, prompt: str = "Опиши это изображение подробно.") -> str:
        """
        Анализ изображения через vision-модель (Gemma 4 с поддержкой мультимодальности).
        Использует /api/chat endpoint с полем images для корректной передачи изображений.
        
        Args:
            image_base64: Изображение в base64
            prompt: Промт для анализа
        
        Returns:
            Текстовое описание изображения
        """
        logger.info(f"Analyzing image with {OLLAMA_MODEL_VISION} (prompt: {prompt[:50]}...)")
        
        # Используем chat endpoint с images для мультимодального запроса
        try:
            response = self.chat(
                message=prompt,
                images=[image_base64],
                system_prompt="Ты эксперт по анализу изображений. Описывай детально что видишь на картинке."
            )
            
            if response.startswith("Ошибка Ollama:"):
                logger.error(f"Image analysis failed: {response}")
            else:
                logger.info(f"Image analysis completed ({len(response)} chars)")
            
            return response
            
        except Exception as e:
            logger.error(f"Unexpected error during image analysis: {str(e)}")
            return f"Ошибка анализа изображения: {str(e)}"
    
    def transcribe_audio_stub(self, audio_description: str) -> str:
        """
        Заглушка для транскрибации аудио.
        В будущем будет заменена на Whisper или мультимодальную модель.
        
        Args:
            audio_description: Описание аудиофайла
        
        Returns:
            Эмулированный текст транскрибации
        """
        logger.debug(f"Audio transcription stub called for: {audio_description}")
        # Пока эмулируем ответ - в реальности здесь будет вызов Whisper
        prompt = f"""
        Это заглушка для транскрибации аудио. 
        Файл: {audio_description}
        
        Поскольку текущая модель Gemma не поддерживает прямой ввод аудио,
        пожалуйста, опишите что должно быть в транскрибации или подключите Whisper API.
        
        ЭМУЛИРОВАННАЯ ТРАНСКРИБАЦИЯ:
        [Здесь будет текст расшифровки аудио после подключения Whisper или другой speech-to-text модели]
        """
        return self.chat(prompt)
    
    def analyze_chat_as_observer(self, messages: List[dict], role_prompt: str, 
                                  analysis_type: str = 'quick') -> str:
        """
        Анализ чата в режиме наблюдателя.
        
        Args:
            messages: Список сообщений чата [{'sender': 'user', 'content': '...'}, ...]
            role_prompt: Роль аналитика (Критик, Саммаризатор, и т.д.)
            analysis_type: quick (последние 10) или full (все)
        
        Returns:
            Анализ чата
        """
        logger.info(f"Observer analysis started (type: {analysis_type}, messages: {len(messages)})")
        
        # Ограничиваем количество сообщений для quick анализа
        if analysis_type == 'quick':
            messages_to_analyze = messages[-10:]
        else:
            messages_to_analyze = messages
        
        # Форматируем сообщения для промта
        formatted_messages = "\n".join([
            f"{msg['sender']}: {msg['content']}" for msg in messages_to_analyze
        ])
        
        prompt = f"""
        Ты выступаешь в роли: {role_prompt}
        
        Проанализируй следующий диалог и предоставь свой анализ согласно выбранной роли.
        Будь конкретен, структурирован и полезен в своем анализе.
        
        ДИАЛОГ:
        {formatted_messages}
        
        Твой анализ:
        """
        
        result = self.chat(prompt, system_prompt=role_prompt)
        logger.info(f"Observer analysis completed ({len(result)} chars)")
        return result
    
    def analyze_image_batch(self, images_base64: List[str], prompt: str = "Опишите эти изображения подробно.") -> str:
        """
        Анализ нескольких изображений одновременно (мультимодальность Gemma 4).
        Использует /api/chat endpoint с массивом изображений.
        
        Args:
            images_base64: Список изображений в base64
            prompt: Промт для анализа
        
        Returns:
            Текстовое описание изображений
        """
        logger.info(f"Analyzing {len(images_base64)} images with {OLLAMA_MODEL_VISION} (prompt: {prompt[:50]}...)")
        
        try:
            response = self.chat(
                message=prompt,
                images=images_base64,  # Передаем массив изображений
                system_prompt="Ты эксперт по анализу изображений. Сравнивай, находи сходства и различия между изображениями. Описывай детально что видишь на каждой картинке и как они соотносятся друг с другом."
            )
            
            if response.startswith("Ошибка Ollama:"):
                logger.error(f"Batch image analysis failed: {response}")
            else:
                logger.info(f"Batch image analysis completed ({len(response)} chars)")
            
            return response
            
        except Exception as e:
            logger.error(f"Unexpected error during batch image analysis: {str(e)}")
            return f"Ошибка анализа изображений: {str(e)}"
    
    def transcribe_and_analyze_audio(self, text_from_whisper: str) -> dict:
        """
        Анализ транскрибированного текста аудио через Gemma 4.
        
        Args:
            text_from_whisper: Текст полученный от Whisper (или другой speech-to-text системы)
        
        Returns:
            dict с транскрибацией и анализом
        """
        logger.info(f"Analyzing audio transcription ({len(text_from_whisper)} chars)")
        
        analysis_prompt = """
        Проанализируй следующую транскрибацию аудио. Выполни следующие задачи:
        1. Выдели главные мысли и ключевые тезисы
        2. Составь краткое резюме содержания
        3. Отметь важные детали или выводы
        
        Транскрибация:
        """
        
        analysis = self.chat(
            message=f"{analysis_prompt}\n\n{text_from_whisper}",
            system_prompt="Ты эксперт по анализу текстов и аудио-контента. Твоя задача — выделять суть и структурировать информацию."
        )
        
        logger.info(f"Audio content analysis completed ({len(analysis)} chars)")
        
        return {
            'transcription': text_from_whisper,
            'analysis': analysis
        }


# Глобальный экземпляр клиента
ollama_client = OllamaClient()
