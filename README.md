# Gemma Hub - Веб-сервис с AI ассистентом

## Структура проекта

```
gemma-hub/
├── app.py                 # Flask приложение (основной сервер)
├── config.py              # Конфигурация
├── db.py                  # Модели БД и хелперы
├── ollama_client.py       # Клиент для Ollama API
├── celery_tasks/
│   └── tasks.py          # Celery задачи для фоновой обработки
├── templates/
│   ├── index.html        # Основной интерфейс
│   └── login.html        # Страница авторизации
├── static/
│   ├── css/
│   │   └── style.css     # Стили
│   └── js/
│       └── app.js        # Frontend логика
└── uploads/              # Папка для загруженных файлов
```

## Технический стек

- **Backend**: Python + Flask (порт 5002)
- **База данных**: PostgreSQL
- **Очередь задач**: Redis + Celery
- **AI Модель**: Ollama (gemma4:e4b)
- **Frontend**: HTML5, CSS3, Vanilla JS

## Установка зависимостей

```bash
pip install flask sqlalchemy psycopg2-binary redis celery requests
```

## Конфигурация

В `config.py` указаны следующие параметры:

```python
# Ollama
OLLAMA_URL = "http://192.168.0.166:11434/api/generate"
OLLAMA_MODEL_CHAT = "gemma4:e4b"
OLLAMA_MODEL_VISION = "gemma4:e4b"

# Redis
CELERY_BROKER_URL = "redis://localhost:6379/0"
CELERY_RESULT_BACKEND = "redis://localhost:6379/0"

# PostgreSQL
DATABASE_URL = "postgresql://bot_user:YesNo1977@192.168.0.34:5432/sleep_data_db"
```

## Запуск

### 1. Запуск Flask приложения

```bash
python app.py
```

Сервер запустится на `http://0.0.0.0:5002`

### 2. Запуск Celery worker (для фоновых задач)

```bash
celery -A celery_tasks.tasks worker --loglevel=info
```

### 3. Запуск Redis (если не запущен)

```bash
redis-server
```

## API Endpoints

### Авторизация
- `POST /api/auth/register` - Регистрация нового пользователя
- `POST /api/auth/login` - Вход в систему
- `POST /api/auth/logout` - Выход
- `GET /api/auth/me` - Информация о текущем пользователе

### Личный ассистент
- `POST /api/chat/personal/create` - Создать новый личный чат
- `GET /api/chat/personal/<chat_id>` - Получить чат с историей
- `POST /api/chat/send` - Отправить сообщение

### Анализ изображений
- `POST /api/upload/image` - Загрузить и анализировать изображение

### Транскрибация аудио
- `POST /api/upload/audio` - Загрузить аудио для транскрибации

### Групповые чаты
- `POST /api/group/create` - Создать группу
- `GET /api/client/groups` - Список групп пользователя
- `GET /api/group/<group_id>` - Информация о группе
- `POST /api/group/<group_id>/invite` - Пригласить пользователя
- `POST /api/group/<group_id>/accept` - Принять приглашение

### ИИ-Наблюдатель
- `POST /api/group/observe` - Запустить анализ чата

## Функциональные модули

### А. Личный Ассистент (Individual Mode)
- Чат с ИИ
- Анализ изображений (Vision)
- Транскрибация аудио (заглушка для Whisper)
- История действий сохраняется в `task_history`

### Б. Совместный Чат (Collaborative Group Chat)
- Создание групп
- Приглашение пользователей по логину
- Общий чат с ИИ
- Проверка прав доступа через `is_client_member_of_group`

### В. ИИ-Наблюдатель (Observer Mode)
- Выбор роли ИИ (Критик, Саммаризатор, и т.д.)
- Быстрый анализ (последние 10 сообщений)
- Полный отчет (все сообщения)
- ИИ не вмешивается автоматически, только по команде

## Важные замечания

1. **Таблица clients** используется для веб-авторизации
2. **Таблица users** зарезервирована для Telegram-бота и не используется в веб-логике
3. Для работы требуется предварительно создать таблицу `clients` в БД
4. Транскрибация аудио пока реализована как заглушка - требуется интеграция с Whisper

## Требования к БД

Необходимо создать таблицу `clients`:

```sql
CREATE TABLE IF NOT EXISTS clients (
    id SERIAL PRIMARY KEY,
    username VARCHAR(100) UNIQUE NOT NULL,
    password_hash VARCHAR(255) NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    is_active BOOLEAN DEFAULT TRUE
);
```

Остальные таблицы будут созданы автоматически при первом запуске через SQLAlchemy.