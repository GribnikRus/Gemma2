# 🚀 Инструкция по запуску gemma-hub

## Предварительные требования

Перед запуском убедитесь, что следующие сервисы доступны:

- **PostgreSQL**: `192.168.0.34:5432` (база данных `sleep_data_db`)
- **Redis**: `localhost:6379`
- **Ollama**: `192.168.0.166:11434` (модель `gemma4:e4b`)

---

## 🔧 Быстрый старт (Разработка)

### 1. Настройка окружения

```bash
# Перейдите в директорию проекта
cd /workspace

# Запустите скрипт настройки (создаст venv и установит зависимости)
./setup.sh
```

### 2. Запуск приложения

```bash
# Запустите Flask + Celery одним скриптом
./run.sh
```

После запуска приложение будет доступно по адресу: **http://localhost:5002**

### 3. Остановка приложения

Нажмите `Ctrl+C` в терминале — скрипт корректно остановит все процессы.

---

## 📋 Пошаговая ручная установка

Если вы предпочитаете контролировать каждый шаг:

### Шаг 1: Создание виртуального окружения

```bash
python3 -m venv venv
source venv/bin/activate
```

### Шаг 2: Установка зависимостей

```bash
pip install --upgrade pip
pip install -r requirements.txt
```

### Шаг 3: Настройка переменных окружения (опционально)

```bash
# Скопируйте пример файла .env
cp .env.example .env

# Отредактируйте .env при необходимости
nano .env
```

### Шаг 4: Запуск Celery worker (в отдельном терминале)

```bash
source venv/bin/activate
celery -A celery_tasks.tasks worker --loglevel=info
```

### Шаг 5: Запуск Flask приложения (в другом терминале)

```bash
source venv/bin/activate
python app.py
```

---

## 🖥️ Запуск как системный сервис (systemd)

Для автоматического запуска при старте системы Linux:

### 1. Установка сервиса

```bash
# Скопируйте файл сервиса в systemd
sudo cp gemma-hub.service /etc/systemd/system/

# Отредактируйте путь к проекту в файле сервиса (если нужно)
sudo nano /etc/systemd/system/gemma-hub.service
```

### 2. Активация и запуск

```bash
# Перезагрузить конфигурацию systemd
sudo systemctl daemon-reload

# Включить автозапуск при старте
sudo systemctl enable gemma-hub

# Запустить сервис
sudo systemctl start gemma-hub

# Проверить статус
sudo systemctl status gemma-hub
```

### 3. Управление сервисом

```bash
# Остановить
sudo systemctl stop gemma-hub

# Перезапустить
sudo systemctl restart gemma-hub

# Просмотр логов
sudo journalctl -u gemma-hub -f
```

---

## 🐛 Диагностика проблем

### Проверка доступности сервисов

```bash
# PostgreSQL
psql -h 192.168.0.34 -U bot_user -d sleep_data_db

# Redis
redis-cli -h localhost -p 6379 ping
# Должен вернуть: PONG

# Ollama
curl http://192.168.0.166:11434/api/tags
```

### Логи приложения

```bash
# При запуске через run.sh логи выводятся в терминал

# При запуске через systemd
sudo journalctl -u gemma-hub --since "1 hour ago"
```

### Проверка процессов

```bash
# Проверить работающие процессы Python
ps aux | grep python

# Проверить процессы Celery
ps aux | grep celery

# Проверить порт 5002
netstat -tlnp | grep 5002
# или
ss -tlnp | grep 5002
```

---

## 📁 Структура файлов

```
/workspace/
├── app.py                 # Flask приложение
├── config.py              # Конфигурация
├── db.py                  # Модели БД
├── ollama_client.py       # Клиент Ollama
├── requirements.txt       # Зависимости Python
├── setup.sh               # Скрипт настройки
├── run.sh                 # Скрипт запуска
├── gemma-hub.service      # Systemd сервис
├── .env.example           # Пример переменных окружения
├── celery_tasks/
│   ├── __init__.py
│   └── tasks.py           # Фоновые задачи Celery
├── templates/
│   ├── index.html         # Основной интерфейс
│   └── login.html         # Страница входа
└── static/
    ├── css/
    │   └── style.css      # Стили
    └── js/
        └── app.js         # Frontend логика
```

---

## ⚙️ Конфигурация

Все настройки находятся в `config.py`:

| Параметр | Значение по умолчанию | Описание |
|----------|----------------------|----------|
| `DATABASE_URL` | `postgresql://bot_user:YesNo1977@192.168.0.34:5432/sleep_data_db` | Подключение к PostgreSQL |
| `REDIS_BROKER_URL` | `redis://localhost:6379/0` | Redis для Celery |
| `OLLAMA_URL` | `http://192.168.0.166:11434/api/generate` | API Ollama |
| `OLLAMA_MODEL_CHAT` | `gemma4:e4b` | Модель для чата |
| `OLLAMA_MODEL_VISION` | `gemma4:e4b` | Модель для анализа изображений |
| `PORT` | `5002` | Порт Flask приложения |

---

## 🔐 Безопасность

⚠️ **Важно:** Перед запуском в production:

1. Измените `SECRET_KEY` в `.env` на случайную строку
2. Установите `FLASK_DEBUG=False`
3. Настройте брандмауэр для ограничения доступа к портам
4. Используйте HTTPS (настройте reverse proxy через Nginx/Apache)
5. Регулярно обновляйте зависимости: `pip list --outdated`

---

## 📞 Поддержка

При возникновении проблем:

1. Проверьте логи: `journalctl -u gemma-hub -f`
2. Убедитесь, что все внешние сервисы доступны
3. Проверьте права доступа к файлам проекта
4. Убедитесь, что виртуальное окружение активировано
