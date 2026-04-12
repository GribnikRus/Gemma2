# Gemma-Hub Architecture

## 🗂️ Структура проекта

```
Gemma2/
├── app.py                  # Точка входа: инициализация Flask, SocketIO, регистрация блюпринтов
├── config.py               # Конфигурация (URL БД, Ollama, секретные ключи)
├── db.py                   # Модели БД SQLAlchemy и helper-функции
├── ollama_client.py        # Клиент для взаимодействия с Ollama API
├── requirements.txt        # Зависимости Python
├── ARCHITECTURE.md         # Этот файл: документация архитектуры
│
├── blueprints/             # Flask Blueprints - функциональные модули
│   ├── __init__.py         # Инициализация пакета, экспорт всех blueprint
│   ├── utils.py            # Общие утилиты: hash_password, login_required, is_ai_triggered
│   ├── auth.py             # Регистрация, логин, логаут (/api/auth/*)
│   ├── chat_personal.py    # Личные чаты: создание, история, отправка сообщений (/api/chat/*)
│   ├── chat_group.py       # Групповые чаты: создание, участники, приглашения (/api/group/*, /api/client/*)
│   ├── chat_websocket.py   # WebSocket события: connect, join_*, send_message
│   ├── media_upload.py     # Загрузка и анализ изображений/аудио (/api/upload/*, /api/audio/*)
│   ├── observer.py         # ИИ-наблюдатель: анализ чатов (/api/group/observe)
│   ├── users.py            # Список пользователей, статус online/offline (/api/users/*)
│   └── tasks.py            # История задач, статусы выполнения (/api/task/*)
│
├── static/                 # Статические файлы (CSS, JS)
│   └── js/app.js           # Фронтенд JavaScript (модуляризирован)
│
├── templates/              # HTML шаблоны Jinja2
│   ├── index.html          # Основной интерфейс чата
│   └── login.html          # Страница входа/регистрации
│
└── uploads/                # Папка для загруженных файлов
```

## 🔗 Точки входа

| Объект | Модуль | Описание |
|--------|--------|----------|
| `app:app` | `app.py` | Flask приложение (основной экземпляр) |
| `app:socketio` | `app.py` | SocketIO экземпляр для WebSocket |
| `db:SessionLocal` | `db.py` | SQLAlchemy сессия (factory) |
| `db:engine` | `db.py` | Database engine для PostgreSQL |
| `ollama_client:OllamaClient` | `ollama_client.py` | Класс клиента Ollama API |

## 🌐 API Endpoints

### Авторизация (`/api/auth`)
| Метод | Путь | Модуль | Описание |
|-------|------|--------|----------|
| POST | `/api/auth/register` | `blueprints.auth` | Регистрация нового пользователя |
| POST | `/api/auth/login` | `blueprints.auth` | Вход в систему |
| POST | `/api/auth/logout` | `blueprints.auth` | Выход из системы |
| GET | `/api/auth/me` | `blueprints.auth` | Информация о текущем пользователе |

### Личные чаты (`/api/chat`)
| Метод | Путь | Модуль | Описание |
|-------|------|--------|----------|
| POST | `/api/chat/personal/create` | `blueprints.chat_personal` | Создать личный чат |
| GET | `/api/chat/personal/<id>` | `blueprints.chat_personal` | Получить личный чат с историей |
| POST | `/api/chat/send` | `blueprints.chat_personal` | Отправить сообщение (личный/групповой) |
| GET | `/api/chat/<id>/history` | `blueprints.chat_personal` | Получить обновления истории (polling) |
| POST | `/api/chat/toggle_ai` | `blueprints.chat_personal` | Переключить AI в чате |
| POST | `/api/chat/set_ai_name` | `blueprints.chat_personal` | Установить имя AI ассистента |
| POST | `/api/chat/observe` | `blueprints.chat_personal` | Анализ личного чата (Наблюдатель) |

### Групповые чаты (`/api/group`, `/api/client`)
| Метод | Путь | Модуль | Описание |
|-------|------|--------|----------|
| POST | `/api/group/create` | `blueprints.chat_group` | Создать группу |
| GET | `/api/client/groups` | `blueprints.chat_group` | Список групп пользователя |
| GET | `/api/group/<id>` | `blueprints.chat_group` | Информация о группе |
| POST | `/api/group/<id>/invite` | `blueprints.chat_group` | Пригласить в группу |
| POST | `/api/group/<id>/accept` | `blueprints.chat_group` | Принять приглашение |
| POST | `/api/group/invite` | `blueprints.chat_group` | API приглашения по login |
| GET | `/api/invitations` | `blueprints.chat_group` | Список приглашений |
| POST | `/api/invitations/accept` | `blueprints.chat_group` | Принять приглашение (API) |
| GET | `/api/client/chats` | `blueprints.chat_group` | Все чаты пользователя |

### Медиа (`/api/upload`, `/api/audio`, `/api/chat/vision`)
| Метод | Путь | Модуль | Описание |
|-------|------|--------|----------|
| POST | `/api/upload/image` | `blueprints.media_upload` | Загрузка и анализ изображения |
| POST | `/api/chat/vision` | `blueprints.media_upload` | Мультимодальный анализ нескольких изображений |
| POST | `/api/upload/audio` | `blueprints.media_upload` | Загрузка аудио (legacy) |
| POST | `/api/audio/transcribe-analyze` | `blueprints.media_upload` | Транскрибация + анализ аудио |

### Наблюдатель (`/api/group`)
| Метод | Путь | Модуль | Описание |
|-------|------|--------|----------|
| POST | `/api/group/observe` | `blueprints.observer` | Запуск AI-анализа группы |

### Пользователи (`/api/users`)
| Метод | Путь | Модуль | Описание |
|-------|------|--------|----------|
| GET | `/api/users/list` | `blueprints.users` | Список всех пользователей со статусом |

### Задачи (`/api/task`)
| Метод | Путь | Модуль | Описание |
|-------|------|--------|----------|
| GET | `/api/task/status/<id>` | `blueprints.tasks` | Статус задачи |

## ⚡ WebSocket Events

### Клиент → Сервер
| Событие | Данные | Модуль | Описание |
|---------|--------|--------|----------|
| `connect` | - | `chat_websocket` | Подключение к WebSocket |
| `disconnect` | - | `chat_websocket` | Отключение от WebSocket |
| `join_group` | `{group_id: number}` | `chat_websocket` | Присоединение к комнате группы |
| `join_personal` | `{personal_chat_id: number}` | `chat_websocket` | Присоединение к личному чату |
| `send_message` | `{content, group_id?, personal_chat_id?}` | `chat_websocket` | Отправка сообщения |

### Сервер → Клиент
| Событие | Данные | Описание |
|---------|--------|----------|
| `connected` | `{message}` | Подтверждение подключения |
| `new_message` | `{id, content, sender_type, sender_id, sender_name, created_at, group_id/personal_chat_id}` | Новое сообщение в чате |
| `joined_group` | `{group_id, message}` | Успешное присоединение к группе |
| `joined_personal` | `{personal_chat_id}` | Успешное присоединение к личному чату |
| `user_joined` | `{client_id}` | Пользователь онлайн |
| `user_left` | `{client_id}` | Пользователь офлайн |
| `ai_name_changed` | `{chat_type, chat_id, new_name}` | Изменено имя AI ассистента |
| `error` | `{message}` | Ошибка |

## 🗄️ Ключевые модели БД

### Client
| Поле | Тип | Описание |
|------|-----|----------|
| `id` | Integer | Primary key |
| `login` | String(100) | Уникальный логин |
| `password_hash` | String(255) | SHA-256 хеш пароля |
| `created_at` | DateTime | Дата создания |
| `last_seen` | DateTime | Последняя активность (для online статуса) |
| `client_uuid` | String(36) | UUID клиента |

### PersonalChat
| Поле | Тип | Описание |
|------|-----|----------|
| `id` | Integer | Primary key |
| `owner_id` | Integer | Foreign key → Client |
| `title` | String(255) | Название чата |
| `created_at` | DateTime | Дата создания |
| `updated_at` | DateTime | Последнее обновление |
| `ai_enabled` | Boolean | Флаг включения AI |
| `ai_name` | String(100) | Имя AI ассистента |

### ChatGroup
| Поле | Тип | Описание |
|------|-----|----------|
| `id` | Integer | Primary key |
| `name` | String(255) | Название группы |
| `owner_id` | Integer | Foreign key → Client |
| `description` | Text | Описание |
| `created_at` | DateTime | Дата создания |
| `ai_enabled` | Boolean | Флаг включения AI |
| `ai_name` | String(100) | Имя AI ассистента |

### GroupMember
| Поле | Тип | Описание |
|------|-----|----------|
| `id` | Integer | Primary key |
| `group_id` | Integer | Foreign key → ChatGroup |
| `client_id` | Integer | Foreign key → Client |
| `status` | String(20) | pending/accepted/rejected |
| `joined_at` | DateTime | Дата вступления |

### ChatMessage
| Поле | Тип | Описание |
|------|-----|----------|
| `id` | Integer | Primary key |
| `content` | Text | Текст сообщения |
| `sender_id` | Integer | Foreign key → Client (NULL если AI) |
| `sender_type` | String(20) | 'client' или 'ai' |
| `personal_chat_id` | Integer | Foreign key → PersonalChat |
| `group_id` | Integer | Foreign key → ChatGroup |
| `is_ai_response` | Boolean | Флаг ответа AI |
| `created_at` | DateTime | Дата создания |

### TaskHistory
| Поле | Тип | Описание |
|------|-----|----------|
| `id` | Integer | Primary key |
| `client_id` | Integer | Foreign key → Client |
| `task_type` | String(50) | 'chat', 'vision', 'audio' |
| `input_data` | Text | Входные данные |
| `result_data` | Text | Результат |
| `status` | String(20) | pending/processing/completed/failed |
| `created_at` | DateTime | Дата создания |

### ObserverSession / ObserverAnalysis
| Поле | Тип | Описание |
|------|-----|----------|
| `id` | Integer | Primary key |
| `group_id` | Integer | Foreign key → ChatGroup |
| `creator_id` | Integer | Foreign key → Client |
| `role_prompt` | Text | Роль аналитика |
| `analysis_type` | String(20) | quick/full |
| `analysis_text` | Text | Текст анализа |
| `messages_analyzed` | Integer | Количество проанализированных сообщений |

## ⚙️ Глобальные переменные и конфиги

| Переменная | Источник | Описание |
|------------|----------|----------|
| `SECRET_KEY` | `config.py` | Секретный ключ Flask для сессий |
| `DATABASE_URL` | `config.py` | PostgreSQL connection string |
| `OLLAMA_URL` | `config.py` | URL Ollama API сервера |
| `OLLAMA_MODEL_CHAT` | `config.py` | Модель для чата (gemma4:e4b) |
| `OLLAMA_MODEL_VISION` | `config.py` | Модель для vision (gemma4:e4b) |
| `REDIS_URL` | env / `config.py` | Redis URL для SocketIO message_queue |
| `UPLOAD_FOLDER` | `config.py` | Путь для загруженных файлов ("uploads") |
| `MAX_CONTENT_LENGTH` | `config.py` | Максимальный размер файла (16MB) |
| `LOG_LEVEL` | `config.py` | Уровень логирования (INFO/DEBUG) |
| `LOG_FORMAT` | `config.py` | Формат логов |

## 🔄 Порядок инициализации

1. **Загрузка config.py** — чтение конфигурационных переменных
2. **eventlet.monkey_patch()** — патчинг стандартных библиотек для async
3. **Инициализация Flask** — создание `app = Flask(__name__)`
4. **Настройка app.config** — SECRET_KEY, UPLOAD_FOLDER, MAX_CONTENT_LENGTH
5. **Инициализация SocketIO** — создание `socketio = SocketIO(app, ...)`
6. **Создание UPLOAD_FOLDER** — `os.makedirs(UPLOAD_FOLDER, exist_ok=True)`
7. **Инициализация БД** — вызов `init_db()` (создание таблиц)
8. **Регистрация Blueprint'ов** — `app.register_blueprint(...)`
9. **Регистрация WebSocket событий** — `register_websocket_events(socketio)`
10. **Запуск сервера** — `socketio.run(app, host='0.0.0.0', port=5000)`

## 📦 Зависимости между модулями

```
app.py
├── config.py
├── db.py
├── ollama_client.py
└── blueprints/
    ├── utils.py → db.py
    ├── auth.py → db.py, utils.py
    ├── chat_personal.py → db.py, ollama_client.py, utils.py
    ├── chat_group.py → db.py, utils.py
    ├── chat_websocket.py → db.py, ollama_client.py, utils.py
    ├── media_upload.py → db.py, ollama_client.py, utils.py
    ├── observer.py → db.py, ollama_client.py, utils.py
    ├── users.py → db.py, utils.py
    └── tasks.py → db.py, utils.py
```

## 🧪 Тестирование

### Проверка запуска:
```bash
python app.py
```

### Проверка endpoints:
```bash
# Регистрация
curl -X POST http://localhost:5000/api/auth/register \
  -H "Content-Type: application/json" \
  -d '{"login":"testuser","password":"password123"}'

# Логин
curl -X POST http://localhost:5000/api/auth/login \
  -H "Content-Type: application/json" \
  -d '{"login":"testuser","password":"password123"}'
```

### Проверка WebSocket:
Использовать клиентскую библиотеку socket.io-client в браузере или Node.js.

## 📝 Чеклист изменений

- [x] Создан пакет `blueprints/` с `__init__.py`
- [x] Вынесены утилиты в `blueprints/utils.py` (hash_password, login_required, is_ai_triggered)
- [x] Создан `blueprints/auth.py` — авторизация
- [x] Создан `blueprints/chat_personal.py` — личные чаты
- [x] Создан `blueprints/chat_group.py` — групповые чаты
- [x] Создан `blueprints/chat_websocket.py` — WebSocket события
- [x] Создан `blueprints/media_upload.py` — загрузка медиа
- [x] Создан `blueprints/observer.py` — ИИ-наблюдатель
- [x] Создан `blueprints/users.py` — пользователи
- [x] Создан `blueprints/tasks.py` — задачи
- [x] Обновлен `app.py` — точка входа с регистрацией blueprint'ов
- [x] Создан `ARCHITECTURE.md` — документация архитектуры
- [x] Сохранена 100% функциональность оригинала
- [x] Сохранены все комментарии и логирование
- [x] Сохранена обработка ошибок (try/except/finally с db.rollback())
- [x] `eventlet.monkey_patch()` вызывается до импорта Flask
