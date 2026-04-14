"""
Клиент для взаимодействия с Ollama API.
Использует настройки из config.py: OLLAMA_URL, OLLAMA_MODEL_CHAT, OLLAMA_MODEL_VISION, OLLAMA_TIMEOUT
"""
import os
import logging
import requests
from typing import Optional, List

from config import (
    OLLAMA_URL, OLLAMA_MODEL_CHAT, OLLAMA_MODEL_VISION,
    OLLAMA_TIMEOUT, OLLAMA_TEMPERATURE, OLLAMA_TOP_K, OLLAMA_TOP_P
)

logger = logging.getLogger("app")


class OllamaClient:
    """Клиент для Ollama API с поддержкой чата и vision"""
    
    def __init__(self, model_chat: Optional[str] = None, model_vision: Optional[str] = None):
        self.host = OLLAMA_URL.rstrip('/')
        self.model_chat = model_chat or OLLAMA_MODEL_CHAT
        self.model_vision = model_vision or OLLAMA_MODEL_VISION or self.model_chat
        self.timeout = OLLAMA_TIMEOUT
        
        logger.info(f"OllamaClient: host={self.host}, chat={self.model_chat}, vision={self.model_vision}, timeout={self.timeout}s")
    
    def _get_options(self) -> dict:
        """Параметры генерации"""
        return {
            "temperature": OLLAMA_TEMPERATURE,
            "top_k": OLLAMA_TOP_K,
            "top_p": OLLAMA_TOP_P,
            "num_predict": 2048
        }
    
    def is_model_available(self, model_name: str) -> bool:
        """Проверяет наличие модели в Ollama"""
        try:
            response = requests.get(f"{self.host}/api/tags", timeout=10)
            if response.ok:
                models = response.json().get('models', [])
                return any(m['name'] == model_name or m['name'].startswith(f"{model_name}:") for m in models)
            return False
        except Exception as e:
            logger.error(f"Error checking model {model_name}: {e}")
            return False
    
    def chat(self, message: str, system_prompt: str = "Ты полезный ассистент.", model: Optional[str] = None) -> str:
        """Текстовый чат"""
        model = model or self.model_chat
        
        logger.info(f"Chat request to {model} (message length: {len(message)} chars)")
        
        try:
            payload = {
                "model": model,
                "messages": [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": message}
                ],
                "options": self._get_options(),
                "stream": False
            }
            
            response = requests.post(
                f"{self.host}/api/chat",
                json=payload,
                timeout=self.timeout  # ✅ Увеличенный таймаут
            )
            response.raise_for_status()
            
            result = response.json()
            content = result.get('message', {}).get('content', '')
            logger.info(f"Chat response from {model}: {len(content)} chars")
            return content
            
        except requests.exceptions.Timeout:
            logger.error(f"Chat timeout ({self.timeout}s) for {model}")
            return f"⚠️ Таймаут ответа от {model}. Увеличьте OLLAMA_TIMEOUT или упростите запрос."
        except Exception as e:
            logger.error(f"Chat request failed: {e}")
            return f"❌ Ошибка Ollama: {str(e)}"
    
    def analyze_image_batch(self, images_base64: List[str], prompt: str, model: Optional[str] = None) -> str:
        """Анализ изображений (мультимодальный запрос)"""
        model = model or self.model_vision
        
        logger.info(f"Analyzing {len(images_base64)} images with {model} (prompt: {prompt[:50]}...)")
        
        try:
            # Формируем сообщения с изображениями для Ollama API
            messages = [
                {"role": "system", "content": "Ты анализируешь изображения. Отвечай подробно, но по делу."}
            ]
            
            # Ollama API ожидает изображения в особом формате
            user_content = [{"type": "text", "text": prompt}]
            for img_b64 in images_base64:
                # Ollama принимает base64 без префикса в некоторых версиях, пробуем универсальный формат
                user_content.append({
                    "type": "image_url", 
                    "image_url": {"url": f"data:image/jpeg;base64,{img_b64}"}
                })
            
            messages.append({"role": "user", "content": user_content})
            
            payload = {
                "model": model,
                "messages": messages,
                "options": self._get_options(),
                "stream": False
            }
            
            response = requests.post(
                f"{self.host}/api/chat",
                json=payload,
                timeout=self.timeout  # ✅ Увеличенный таймаут для vision
            )
            response.raise_for_status()
            
            result = response.json()
            content = result.get('message', {}).get('content', '')
            logger.info(f"Vision response from {model}: {len(content)} chars")
            return content
            
        except requests.exceptions.Timeout:
            logger.error(f"Vision timeout ({self.timeout}s) for {model}")
            return f"⚠️ Таймаут анализа изображений. Модель {model} работает долго. Попробуйте уменьшить количество картинок или увеличить OLLAMA_TIMEOUT."
        except Exception as e:
            logger.error(f"Vision analysis failed: {e}")
            return f"❌ Ошибка Ollama: {str(e)}"
    
    def analyze_image(self, image_base64: str, prompt: str, model: Optional[str] = None) -> str:
        """Legacy: анализ одного изображения"""
        return self.analyze_image_batch([image_base64], prompt, model)
    
    def transcribe_and_analyze_audio(self, transcription: str, model: Optional[str] = None) -> dict:
        """Анализ транскрибированного аудио"""
        model = model or self.model_chat
        try:
            analysis_prompt = f"Проанализируй этот текст (транскрибация аудио):\n\n{transcription}\n\nВыдели ключевые моменты, действия и выводы."
            analysis = self.chat(analysis_prompt, model=model)
            return {"transcription": transcription, "analysis": analysis}
        except Exception as e:
            logger.error(f"Audio analysis failed: {e}")
            return {"transcription": transcription, "analysis": f"Ошибка анализа: {str(e)}"}
    
    def get_available_models(self) -> List[dict]:
        """Список доступных моделей"""
        try:
            response = requests.get(f"{self.host}/api/tags", timeout=10)
            if response.ok:
                models = response.json().get('models', [])
                return [
                    {
                        "name": m['name'],
                        "size_gb": round(m['size'] / (1024**3), 2),
                        "family": m.get('details', {}).get('family', 'unknown'),
                        "params": m.get('details', {}).get('parameter_size', 'unknown')
                    }
                    for m in models
                ]
            return []
        except Exception as e:
            logger.error(f"Failed to fetch models: {e}")
            return []
    
    def set_model(self, model_name: str, for_vision: bool = False) -> bool:
        """Динамическая смена модели"""
        if self.is_model_available(model_name):
            if for_vision:
                self.model_vision = model_name
                logger.info(f"Vision model changed to: {model_name}")
            else:
                self.model_chat = model_name
                # Если модель vision-совместимая, обновляем и её
                if any(kw in model_name.lower() for kw in ['vision', 'llava', 'moondream', 'bakllava', 'gemma4']):
                    self.model_vision = model_name
                logger.info(f"Chat model changed to: {model_name}")
            return True
        logger.warning(f"Model {model_name} not available in Ollama")
        return False