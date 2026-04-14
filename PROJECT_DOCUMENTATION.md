# 📘 Gemma-Hub: Полное описание проекта

## 📋 Оглавление
1. [Обзор проекта](#обзор-проекта)
2. [Архитектура приложения](#архитектура-приложения)
3. [Модули и их ответственность](#модули-и-их-ответственность)
4. [Связи между модулями](#связи-между-модулями)
5. [База данных](#база-данных)
6. [API Endpoints](#api-endpoints)
7. [WebSocket события](#websocket-события)
8. [Frontend архитектура](#frontend-архитектура)
9. [Конфигурация](#конфигурация)
10. [Фоновые задачи](#фоновые-задачи)

---

## 🎯 Обзор проекта

**Gemma-Hub** — это веб-приложение для общения с ИИ-ассистентом (на базе Ollama/Gemma), поддерживающее:
- Личные чаты с ИИ
- Групповые чаты с участниками
- Анализ изображений (vision)
- Режим наблюдателя для анализа диалогов
- Управление моделями ИИ
- Real-time уведомления через WebSocket

**Технологический стек:**
- Backend: Flask + Flask-SocketIO (eventlet)
- Database: PostgreSQL / SQLite + SQLAlchemy ORM
- AI: Ollama API (Gemma и другие модели)
- Frontend: Vanilla JS + ES6 Modules
- Task Queue: Celery (опционально, через Redis)

---

## 🏗️ Архитектура приложения

```
┌─────────────────────────────────────────────────────────────┐
│                        Client Browser                        │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐      │
│  │  HTML/JS     │  │  WebSocket   │  │   REST API   │      │
│  │  (app.js)    │◄─┤   Socket.IO  ├─►│   Fetch      │      │
│  └──────────────┘  └──────────────┘  └──────────────┘      │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼ HTTP + WebSocket
┌─────────────────────────────────────────────────────────────┐
│                    Flask Application                         │
│  ┌──────────────────────────────────────────────────────┐   │
│  │                   app.py (main)                       │   │
│  │  • Инициализация Flask + SocketIO                     │   │
│  │  • Регистрация Blueprint'ов                           │   │
│  │  • Глобальный обработчик WebSocket connect            │   │
│  │  • Health check endpoint                              │   │
│  └──────────────────────────────────────────────────────┘   │
│                                                              │
│  ┌──────────────────────────────────────────────────────┐   │
│  │              Blueprints (модули)                      │   │
│  │  ┌─────────┐ ┌─────────┐ ┌─────────┐ ┌─────────┐    │   │
│  │  │  auth   │ │  chat   │ │  media  │ │ observer│    │   │
│  │  └─────────┘ └─────────┘ └─────────┘ └─────────┘    │   │
│  │  ┌─────────┐ ┌─────────┐ ┌─────────┐ ┌─────────┐    │   │
│  │  │  users  │ │  tasks  │ │ ai_*    │ │ utils   │    │   │
│  │  └─────────┘ └─────────┘ └─────────┘ └─────────┘    │   │
│  └──────────────────────────────────────────────────────┘   │
│                                                              │
│  ┌──────────────────────────────────────────────────────┐   │
│  │              Extensions & Clients                     │   │
│  │  • OllamaClient (единый экземпляр)                   │   │
│  │  • SocketIO instance                                  │   │
│  │  • SQLAlchemy SessionLocal                            │   │
│  └──────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────┘
         │                          │
         ▼ DB Protocol              ▼ HTTP
┌─────────────────────┐   ┌─────────────────────┐
│   PostgreSQL/SQLite │   │   Ollama Server     │
│   • clients         │   │   • /api/chat       │
│   • chats           │   │   • /api/tags       │
│   • messages        │   │   • vision API      │
│   • groups          │   └─────────────────────┘
│   • tasks           │
│   • observer        │   ┌─────────────────────┐
└─────────────────────┘   │   Celery Worker     │
                          │   (опционально)     │
                          └─────────────────────┘
```

---

## 📦 Модули и их ответственность

### 1. **app.py** — Точка входа
**Ответственность:**
- Инициализация Flask приложения
- Настройка SocketIO с eventlet
- Создание глобальных экземпляров: `OllamaClient`, `SessionLocal`
- Регистрация всех Blueprint'ов
- Обработка WebSocket подключения (`connect`)
- Health check endpoint `/api/health`

**Зависимости:**
- `config` — конфигурация
- `db` — база данных
- `ollama_client` — клиент Ollama
- Все blueprints из `blueprints/`

---

### 2. **config.py** — Конфигурация
**Ответственность:**
- Загрузка переменных окружения (.env)
- Настройки Ollama (URL, модели, таймауты, параметры генерации)
- Настройки базы данных
- Настройки Flask (SECRET_KEY, UPLOAD_FOLDER)
- Настройки логирования

**Параметры:**
```python
OLLAMA_URL, OLLAMA_MODEL_CHAT, OLLAMA_MODEL_VISION
OLLAMA_TIMEOUT, OLLAMA_TEMPERATURE, OLLAMA_TOP_K, OLLAMA_TOP_P
DATABASE_URL
SECRET_KEY, UPLOAD_FOLDER, MAX_CONTENT_LENGTH
LOG_LEVEL, LOG_FORMAT
```

---

### 3. **db.py** — База данных и ORM модели
**Ответственность:**
- Подключение к БД (PostgreSQL/SQLite)
- Определение SQLAlchemy моделей
- CRUD операции и хелперы для работы с данными

**Модели данных:**
| Модель | Описание |
|--------|----------|
| `Client` | Пользователи системы (логин, пароль, UUID) |
| `PersonalChat` | Личные чаты пользователей |
| `ChatGroup` | Групповые чаты |
| `GroupMember` | Участники групп (статусы: pending/accepted/rejected) |
| `ChatMessage` | Сообщения (личные и групповые, от клиентов и ИИ) |
| `TaskHistory` | История задач (анализ изображений, аудио) |
| `ObserverSession` | Сессии наблюдателя для анализа чатов |
| `ObserverAnalysis` | Результаты анализа наблюдателя |

**Хелпер функции:**
- `init_db()` — создание таблиц
- `get_client_by_login()`, `get_client_by_id()` — поиск клиентов
- `create_client()` — регистрация
- `create_personal_chat()`, `get_personal_chat_history()` — личные чаты
- `create_group()`, `get_client_groups()`, `invite_client_to_group()` — группы
- `add_message()` — добавление сообщения
- `update_user_online_status()` — статус online/offline
- И многие другие...

---

### 4. **ollama_client.py** — Клиент Ollama API
**Ответственность:**
- Взаимодействие с Ollama API
- Текстовый чат (`chat()`)
- Анализ изображений (`analyze_image()`, `analyze_image_batch()`)
- Анализ аудио транскрипций (`transcribe_and_analyze_audio()`)
- Получение списка моделей (`get_available_models()`)
- Режим наблюдателя (`analyze_chat_as_observer()`)
- Динамическая смена моделей (`set_model()`)

**Параметры генерации:**
- temperature, top_k, top_p, num_predict

---

### 5. **blueprints/auth.py** — Аутентификация
**URL префикс:** `/api/auth`

**Endpoints:**
| Метод | Endpoint | Описание |
|-------|----------|----------|
| POST | `/register` | Регистрация нового пользователя |
| POST | `/login` | Вход в систему |
| POST | `/logout` | Выход из системы |
| GET | `/me` | Получить текущего пользователя |

**Логика:**
- Хеширование паролей (SHA-256)
- Управление сессиями Flask (`session['client_id']`)
- Проверка существования пользователей

**Зависимости:**
- `db` — модели Client, хелперы
- `blueprints/utils` — `hash_password_sha256`, `verify_password_sha256`

---

### 6. **blueprints/chat_personal.py** — Личные чаты
**URL префикс:** `/api/chat`

**Endpoints:**
| Метод | Endpoint | Описание |
|-------|----------|----------|
| POST | `/personal/create` | Создать личный чат |
| GET | `/personal/<id>` | Получить чат с историей |
| GET | `/personal/list` | Список всех личных чатов |
| POST | `/personal/<id>/message` | Отправить сообщение |

**Логика:**
- Создание/получение личных чатов
- Отправка сообщений пользователем
- Триггеры для ИИ-ответов (через `utils.is_ai_triggered()`)
- Генерация ответов ИИ через `OllamaClient`

**Зависимости:**
- `db` — PersonalChat, ChatMessage, хелперы
- `blueprints/utils` — декоратор `login_required`, триггеры ИИ
- `current_app.extensions['ollama_client']` — AI клиент

---

### 7. **blueprints/chat_group.py** — Групповые чаты
**URL префикс:** `/api`

**Endpoints:**
| Метод | Endpoint | Описание |
|-------|----------|----------|
| POST | `/group/create` | Создать группу |
| GET | `/client/groups` | Список групп пользователя |
| GET | `/group/<id>` | Информация о группе |
| POST | `/group/<id>/invite` | Пригласить участника |
| POST | `/group/accept-invite` | Принять приглашение |
| GET | `/group/<id>/history` | История сообщений группы |

**Логика:**
- CRUD операции для групп
- Управление участниками (приглашения, принятие)
- Проверка прав доступа

**Зависимости:**
- `db` — ChatGroup, GroupMember, Client, хелперы
- `blueprints/utils` — `login_required`

---

### 8. **blueprints/chat_websocket.py** — WebSocket события
**Ответственность:**
- Регистрация обработчиков WebSocket событий
- Обработка disconnect, join_group, join_personal, send_message

**События:**
| Событие | Описание |
|---------|----------|
| `disconnect` | Обновление статуса offline, уведомление других |
| `join_group` | Подключение к комнате группы |
| `join_personal` | Подключение к личному чату |
| `send_message` | Отправка сообщения в реальном времени |

**Логика:**
- Rooms (комнаты) для изоляции чатов: `user_<id>`, `group_<id>`, `personal_<id>`
- Рассылка сообщений участникам
- Триггеры для ИИ-ответов в групповых чатах

**Зависимости:**
- `db` — обновление статусов, сохранение сообщений
- `blueprints/utils` — `is_ai_triggered()`
- `socketio.emit()` — отправка событий клиентам

---

### 9. **blueprints/media_upload.py** — Загрузка медиа
**URL префикс:** `/api`

**Endpoints:**
| Метод | Endpoint | Описание |
|-------|----------|----------|
| POST | `/upload/image` | Загрузить и проанализировать изображение |
| POST | `/chat/vision` | Анализ изображения с промптом |
| POST | `/audio/transcribe` | Транскрибация аудио (будущее) |
| POST | `/audio/analyze` | Анализ аудио (будущее) |

**Логика:**
- Валидация файлов (MIME-type, размер)
- Сохранение в `uploads/`
- Кодирование в base64
- Отправка в Ollama для vision-анализа
- Интеграция с Celery для фоновой обработки

**Зависимости:**
- `db` — TaskHistory для отслеживания задач
- `current_app.extensions['ollama_client']` — анализ изображений
- `celery_tasks.tasks` — фоновые задачи (опционально)

---

### 10. **blueprints/observer.py** — ИИ-наблюдатель
**URL префикс:** `/api`

**Endpoints:**
| Метод | Endpoint | Описание |
|-------|----------|----------|
| POST | `/group/observe` | Анализ чата наблюдателем |

**Логика:**
- Получение истории сообщений группы
- Форматирование контекста для ИИ
- Вызов `OllamaClient.analyze_chat_as_observer()`
- Сохранение результатов анализа

**Типы анализа:**
- `quick` — последние 10 сообщений
- `full` — последние 100 сообщений

**Зависимости:**
- `db` — ObserverSession, ObserverAnalysis
- `ollama_client` — специализированный метод анализа

---

### 11. **blueprints/users.py** — Управление пользователями
**URL префикс:** `/api`

**Endpoints:**
| Метод | Endpoint | Описание |
|-------|----------|----------|
| GET | `/users/list` | Список всех пользователей со статусами |

**Логика:**
- Определение online/offline по `last_seen` (< 5 минут = online)
- Возврат списка с логинами и статусами

**Зависимости:**
- `db` — модель Client

---

### 12. **blueprints/tasks.py** — История задач
**URL префикс:** `/api`

**Endpoints:**
| Метод | Endpoint | Описание |
|-------|----------|----------|
| GET | `/task/status/<id>` | Статус задачи |

**Логика:**
- Получение статуса и результата задачи

**Зависимости:**
- `db` — TaskHistory

---

### 13. **blueprints/ai_status.py** — Статус AI
**URL префикс:** `/api/ai`

**Endpoints:**
| Метод | Endpoint | Описание |
|-------|----------|----------|
| GET | `/status` | Проверка доступности Ollama и моделей |
| GET | `/health` | Простая проверка Ollama (без авторизации) |

**Логика:**
- Прямой запрос к Ollama API `/api/tags`
- Проверка наличия конкретных моделей

**Зависимости:**
- `config` — OLLAMA_URL, названия моделей
- `requests` — HTTP клиент

---

### 14. **blueprints/ai_models.py** — Управление моделями
**URL префикс:** `/api/ai`

**Endpoints:**
| Метод | Endpoint | Описание |
|-------|----------|----------|
| GET | `/models` | Список доступных моделей |
| POST | `/models/set` | Сменить активную модель |
| GET | `/status` | Статус Ollama (через клиент) |

**Логика:**
- Получение списка моделей от Ollama
- Динамическая смена модели для чата/vision
- Валидация доступности модели

**Зависимости:**
- `current_app.extensions['ollama_client']` — управление моделями

---

### 15. **blueprints/utils.py** — Общие утилиты
**Ответственность:**
- Хелпер функции для всех blueprints

**Функции:**
- `hash_password_sha256()` — хеширование паролей
- `verify_password_sha256()` — проверка паролей
- `is_ai_triggered()` — определение обращения к ИИ
- `login_required` — декоратор защиты endpoints
- `get_current_client()` — получение текущего клиента

**Триггеры ИИ:**
- `@<имя>` в начале сообщения
- `/gemma`, `/ai` команды
- `<имя>,` или `<имя> ` в начале

---

### 16. **celery_tasks/tasks.py** — Celery задачи
**Ответственность:**
- Фоновая обработка тяжелых операций

**Задачи:**
- `analyze_image_task` — анализ изображений в фоне

**Конфигурация:**
- Broker/Backend: Redis
- Таймаут: 300 секунд
- Максимум попыток: 3

**Зависимости:**
- `ollama_client` — выполнение анализа
- `config` — CELERY_BROKER_URL, CELERY_RESULT_BACKEND

---

## 🔗 Связи между модулями

### Граф зависимостей

```
app.py
├── config.py
├── db.py
├── ollama_client.py
└── blueprints/
    ├── __init__.py
    ├── auth.py ──────────────┬── utils.py
    ├── chat_personal.py ─────┼── utils.py
    ├── chat_group.py ────────┼── utils.py
    ├── chat_websocket.py ────┼── utils.py
    ├── media_upload.py ──────┼── utils.py ─── celery_tasks/
    ├── observer.py ──────────┴── ollama_client.py
    ├── users.py ─────────────┬── utils.py
    ├── tasks.py ─────────────┼── utils.py
    ├── ai_status.py ─────────┼── utils.py ─── config.py
    ├── ai_models.py ─────────┴── utils.py
    └── utils.py ─────────────┴── db.py
```

### Таблица взаимодействий

| Модуль | Зависит от | Использует |
|--------|-----------|------------|
| `app.py` | config, db, ollama_client, все blueprints | Flask, SocketIO |
| `auth.py` | db, utils | session, jsonify |
| `chat_personal.py` | db, utils, ollama_client | current_app |
| `chat_group.py` | db, utils | session |
| `chat_websocket.py` | db, utils, socketio | emit, join_room |
| `media_upload.py` | db, utils, ollama_client | base64, werkzeug |
| `observer.py` | db, ollama_client, utils | - |
| `users.py` | db, utils | datetime |
| `tasks.py` | db, utils | - |
| `ai_status.py` | config, utils, requests | - |
| `ai_models.py` | utils, ollama_client | current_app |
| `utils.py` | db | hashlib, re, functools |
| `celery_tasks/tasks.py` | config, ollama_client | Celery |

---

## 🗄️ База данных

### Схема данных

```
┌─────────────────┐       ┌──────────────────┐
│    clients      │       │ personal_chats   │
├─────────────────┤       ├──────────────────┤
│ id (PK)         │◄──────│ owner_id (FK)    │
│ login           │       │ id (PK)          │
│ password_hash   │       │ title            │
│ created_at      │       │ created_at       │
│ last_seen       │       │ updated_at       │
│ client_uuid     │       │ ai_enabled       │
└─────────────────┘       │ ai_name          │
       │                  └──────────────────┘
       │                         │
       │    ┌────────────────────┘
       │    │
       ▼    ▼
┌─────────────────┐       ┌──────────────────┐
│  group_members  │       │  chat_messages   │
├─────────────────┤       ├──────────────────┤
│ id (PK)         │       │ id (PK)          │
│ group_id (FK)   │       │ content          │
│ client_id (FK)  │       │ sender_id (FK)   │
│ status          │       │ sender_type      │
│ joined_at       │       │ personal_chat_id │
└─────────────────┘       │ group_id (FK)    │
       ▲                  │ is_ai_response   │
       │                  │ created_at       │
       │                  └──────────────────┘
       │
┌──────┴──────────┐
│   chat_groups   │
├─────────────────┤
│ id (PK)         │
│ name            │
│ owner_id (FK)   │
│ description     │
│ created_at      │
│ ai_enabled      │
│ ai_name         │
└─────────────────┘

┌─────────────────┐       ┌──────────────────┐
│  task_history   │       │observer_sessions │
├─────────────────┤       ├──────────────────┤
│ id (PK)         │       │ id (PK)          │
│ client_id (FK)  │       │ group_id (FK)    │
│ task_type       │       │ creator_id (FK)  │
│ input_data      │       │ role_prompt      │
│ result_data     │       │ analysis_type    │
│ status          │       │ created_at       │
│ created_at      │       └──────────────────┘
└─────────────────┘                │
                                   │
                          ┌────────┴──────────┐
                          │observer_analyses  │
                          ├───────────────────┤
                          │ id (PK)           │
                          │ session_id (FK)   │
                          │ analysis_text     │
                          │ messages_analyzed │
                          │ created_at        │
                          └───────────────────┘
```

---

## 🌐 API Endpoints

### Authentication (`/api/auth`)
```
POST /api/auth/register      — Регистрация
POST /api/auth/login         — Вход
POST /api/auth/logout        — Выход
GET  /api/auth/me            — Текущий пользователь
```

### Personal Chats (`/api/chat`)
```
POST /api/chat/personal/create           — Создать чат
GET  /api/chat/personal/<id>             — Получить чат
GET  /api/chat/personal/list             — Список чатов
POST /api/chat/personal/<id>/message     — Отправить сообщение
```

### Group Chats (`/api`)
```
POST /api/group/create                   — Создать группу
GET  /api/client/groups                  — Мои группы
GET  /api/group/<id>                     — Инфо о группе
POST /api/group/<id>/invite              — Пригласить
POST /api/group/accept-invite            — Принять приглашение
GET  /api/group/<id>/history             — История
POST /api/group/observe                  — Анализ наблюдателем
```

### Media (`/api`)
```
POST /api/upload/image                   — Загрузить изображение
POST /api/chat/vision                    — Анализ с промптом
```

### Users (`/api`)
```
GET /api/users/list                      — Список пользователей
```

### Tasks (`/api`)
```
GET /api/task/status/<id>                — Статус задачи
```

### AI Management (`/api/ai`)
```
GET  /api/ai/status                      — Статус Ollama
GET  /api/ai/health                      — Health check
GET  /api/ai/models                      — Список моделей
POST /api/ai/models/set                  — Сменить модель
```

### Health Check
```
GET /api/health                          — Полный health check (БД + Ollama)
```

---

## 🔌 WebSocket события

### Сервер → Клиент
| Событие | Данные | Описание |
|---------|--------|----------|
| `connected` | `{message, client_id}` | Подтверждение подключения |
| `user_joined` | `{client_id}` | Пользователь онлайн |
| `user_left` | `{client_id}` | Пользователь офлайн |
| `new_message` | `{id, content, sender_id, ...}` | Новое сообщение в чате |
| `ai_response` | `{content, chat_id}` | Ответ ИИ |
| `typing_indicator` | `{user_id}` | Пользователь печатает |

### Клиент → Сервер
| Событие | Данные | Описание |
|---------|--------|----------|
| `join_group` | `{group_id}` | Войти в комнату группы |
| `join_personal` | `{chat_id}` | Войти в личный чат |
| `send_message` | `{chat_id, content, ...}` | Отправить сообщение |

---

## 🖥️ Frontend архитектура

### Структура JavaScript
```
static/js/
├── app.js                 — Главное приложение, состояние, инициализация
└── modules/
    ├── images.js          — Загрузка и предпросмотр изображений
    ├── chat.js            — Логика чатов (отправка, получение)
    ├── groups.js          — Управление группами
    ├── users.js           — Список пользователей, статусы
    └── ai.js              — Управление моделями ИИ
```

### Состояние приложения (`state` в app.js)
```javascript
{
    currentUser: null,          // Текущий пользователь
    currentChat: null,          // Активный чат
    currentChatType: 'personal',// 'personal' или 'group'
    chats: [],                  // Список личных чатов
    groups: [],                 // Список групп
    usersStatus: [],            // Статусы пользователей
    lastMessageId: null,        // ID последнего сообщения
    originalTitle: '',          // Заголовок окна (для уведомлений)
    socket: null,               // Socket.IO соединение
    appInitialized: false       // Флаг инициализации
}
```

### Основные функции
- `initApp()` — инициализация приложения
- `connectSocket()` — подключение WebSocket
- `loadChats()`, `loadGroups()` — загрузка чатов/групп
- `renderMessages()` — отображение сообщений
- `sendMessage()` — отправка сообщения
- `handleAIResponse()` — обработка ответа ИИ

---

## ⚙️ Конфигурация

### Переменные окружения (.env)
```bash
# Ollama
OLLAMA_URL=http://192.168.0.166:11434
OLLAMA_MODEL_CHAT=gemma4:e4b
OLLAMA_MODEL_VISION=gemma4:e4b
OLLAMA_TIMEOUT=300
OLLAMA_TEMPERATURE=0.7
OLLAMA_TOP_K=40
OLLAMA_TOP_P=0.9

# Database
DATABASE_URL=postgresql://user:pass@host:5432/dbname

# Flask
SECRET_KEY=your-secret-key
UPLOAD_FOLDER=uploads
MAX_CONTENT_LENGTH=16777216

# Logging
LOG_LEVEL=INFO
LOG_FORMAT=[%(levelname)s] %(asctime)s - %(name)s - %(message)s

# Redis (для Celery)
REDIS_BROKER_URL=redis://localhost:6379/0
```

---

## 🔄 Фоновые задачи

### Celery интеграция
**Когда используется:**
- Анализ больших изображений
- Обработка аудио
- Длительные вычисления

**Архитектура:**
```
Flask App ──► Redis Broker ──► Celery Worker ──► Ollama
     │                              │
     └────── Result Backend ◄───────┘
```

**Настройка:**
- Broker: Redis
- Backend: Redis
- Time limit: 300s
- Max retries: 3

---

## 📝 Процесс обработки запроса

### Пример: Отправка сообщения в личном чате

1. **Клиент** отправляет POST `/api/chat/personal/<id>/message`
2. **chat_personal.py** проверяет авторизацию (`login_required`)
3. Сохраняет сообщение в БД через `add_message()`
4. Проверяет триггер ИИ через `is_ai_triggered()`
5. Если триггер — вызывает `ollama.chat()`
6. Получает ответ от Ollama
7. Сохраняет ответ ИИ в БД
8. Отправляет событие WebSocket `new_message` всем подключенным
9. **Клиент** получает событие и обновляет UI

### Пример: WebSocket подключение

1. **Клиент** устанавливает WebSocket соединение
2. **app.py** обрабатывает `connect`:
   - Проверяет `session['client_id']`
   - Добавляет в комнату `user_<client_id>`
   - Обновляет статус online в БД
   - Уведомляет других: `emit('user_joined')`
   - Отправляет подтверждение: `emit('connected')`
3. **Клиент** получает `connected` и начинает работу

---

## 🔒 Безопасность

- **Авторизация:** Декоратор `login_required` на всех API endpoints
- **Пароли:** Хеширование SHA-256
- **Сессии:** Flask sessions с SECRET_KEY
- **WebSocket:** Проверка авторизации при подключении
- **Валидация файлов:** MIME-type, размер, secure_filename
- **SQL Injection:** Защита через SQLAlchemy ORM

---

## 📊 Масштабируемость

### Горизонтальное масштабирование
- **Stateless API:** Все endpoints stateless, можно запускать несколько инстансов
- **Redis для сессий:** Требуется для общих сессий между инстансами
- **WebSocket:** Требует Redis Pub/Sub для синхронизации между серверами

### Оптимизация
- **Connection Pooling:** SQLAlchemy pool_size=10, max_overflow=20
- **Pool Pre-ping:** Проверка соединений перед использованием
- **Pool Recycle:** Пересоздание соединений через 1 час

---

## 🧪 Тестирование

### Health Check
```bash
curl http://localhost:5002/api/health
# Ответ: {"database": "ok", "ollama": "ok", "status": "healthy"}
```

### Проверка API
```bash
# Регистрация
curl -X POST http://localhost:5002/api/auth/register \
  -H "Content-Type: application/json" \
  -d '{"login": "test", "password": "password123"}'

# Логин
curl -X POST http://localhost:5002/api/auth/login \
  -H "Content-Type: application/json" \
  -d '{"login": "test", "password": "password123"}' \
  -c cookies.txt

# Список пользователей
curl http://localhost:5002/api/users/list -b cookies.txt
```

---

## 📁 Структура проекта

```
/workspace/
├── app.py                    # Точка входа Flask
├── config.py                 # Конфигурация
├── db.py                     # Модели БД и хелперы
├── ollama_client.py          # Клиент Ollama API
├── blueprints/
│   ├── __init__.py
│   ├── auth.py               # Аутентификация
│   ├── chat_personal.py      # Личные чаты
│   ├── chat_group.py         # Групповые чаты
│   ├── chat_websocket.py     # WebSocket события
│   ├── media_upload.py       # Загрузка медиа
│   ├── observer.py           # ИИ-наблюдатель
│   ├── users.py              # Пользователи
│   ├── tasks.py              # История задач
│   ├── ai_status.py          # Статус AI
│   ├── ai_models.py          # Управление моделями
│   └── utils.py              # Утилиты
├── celery_tasks/
│   ├── __init__.py
│   └── tasks.py              # Celery задачи
├── static/
│   ├── js/
│   │   ├── app.js            # Главное JS приложение
│   │   └── modules/
│   │       ├── images.js     # Модуль изображений
│   │       └── ...           # Другие модули
│   └── css/
├── templates/
│   ├── index.html            # Главный экран
│   └── login.html            # Страница входа
├── uploads/                  # Загруженные файлы
├── requirements.txt          # Зависимости Python
├── Dockerfile                # Docker образ
├── docker-compose.yml        # Docker Compose
└── .env                      # Переменные окружения
```

---

## 🚀 Развёртывание

### Локальный запуск
```bash
# Установка зависимостей
pip install -r requirements.txt

# Запуск
python app.py
# или через скрипт
./run.sh
```

### Docker
```bash
docker-compose up -d
```

### Systemd сервис
```bash
sudo systemctl start gemma-hub
sudo systemctl enable gemma-hub
```

---

## 📈 Будущие улучшения

1. **Telegram бот** — интеграция с Telegram (таблица `users` зарезервирована)
2. **Аудио транскрибация** — Whisper integration
3. **Redis сессии** — для горизонтального масштабирования
4. **Rate limiting** — ограничение запросов к API
5. **Многопользовательские роли** — расширенные права в группах
6. **Экспорт чатов** — выгрузка истории в файлы
7. **Темы оформления** — светлая/тёмная тема

---

*Документ создан автоматически на основе анализа кода проекта.*
