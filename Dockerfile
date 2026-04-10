FROM python:3.12-slim

WORKDIR /app

# Устанавливаем системные зависимости
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# Копируем requirements и устанавливаем Python зависимости
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Копируем код приложения
COPY . .

# Создаем папку uploads если не существует
RUN mkdir -p /app/uploads

# Открываем порт
EXPOSE 5002

# Запускаем приложение через eventlet для WebSocket поддержки
CMD ["python", "app.py"]
