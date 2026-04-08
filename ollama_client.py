"""
Клиент для взаимодействия с Ollama API.
Унифицированный класс для отправки запросов к модели.
"""
import requests
import base64
from typing import Optional, List
from config import OLLAMA_URL, OLLAMA_MODEL_CHAT, OLLAMA_MODEL_VISION


class OllamaClient:
    """Клиент для работы с Ollama API"""
    
    def __init__(self, url: str = OLLAMA_URL, model: str = OLLAMA_MODEL_CHAT):
        self.url = url
        self.model = model
        self.timeout = 120  # секунды
    
    def generate(self, prompt: str, system_prompt: Optional[str] = None, 
                 images: Optional[List[str]] = None, stream: bool = False) -> dict:
        """
        Генерация ответа от модели.
        
        Args:
            prompt: Основной промт
            system_prompt: Системный промт (роль ИИ)
            images: Список base64 кодированных изображений
            stream: Потоковый режим
        
        Returns:
            dict с ответом от API
        """
        payload = {
            "model": self.model,
            "prompt": prompt,
            "stream": stream
        }
        
        if system_prompt:
            payload["system"] = system_prompt
        
        if images:
            payload["images"] = images
        
        try:
            response = requests.post(
                self.url,
                json=payload,
                timeout=self.timeout
            )
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            return {"error": str(e), "response": None}
    
    def chat(self, message: str, system_prompt: Optional[str] = None) -> str:
        """
        Обычный чат с моделью.
        
        Args:
            message: Сообщение пользователя
            system_prompt: Системный промт (опционально)
        
        Returns:
            Текст ответа или сообщение об ошибке
        """
        result = self.generate(prompt=message, system_prompt=system_prompt)
        
        if "error" in result:
            return f"Ошибка Ollama: {result['error']}"
        
        return result.get("response", "Нет ответа от модели")
    
    def analyze_image(self, image_base64: str, prompt: str = "Опиши это изображение подробно.") -> str:
        """
        Анализ изображения через vision-модель.
        
        Args:
            image_base64: Изображение в base64
            prompt: Промт для анализа
        
        Returns:
            Текстовое описание изображения
        """
        # Используем vision модель если она отличается
        original_model = self.model
        self.model = OLLAMA_MODEL_VISION
        
        try:
            result = self.generate(
                prompt=prompt,
                images=[image_base64]
            )
            
            if "error" in result:
                return f"Ошибка анализа изображения: {result['error']}"
            
            return result.get("response", "Не удалось проанализировать изображение")
        finally:
            self.model = original_model
    
    def transcribe_audio_stub(self, audio_description: str) -> str:
        """
        Заглушка для транскрибации аудио.
        В будущем будет заменена на Whisper или мультимодальную модель.
        
        Args:
            audio_description: Описание аудиофайла
        
        Returns:
            Эмулированный текст транскрибации
        """
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
        
        ДИАЛОГ:
        {formatted_messages}
        
        Твой анализ:
        """
        
        return self.chat(prompt, system_prompt=role_prompt)


# Глобальный экземпляр клиента
ollama_client = OllamaClient()
