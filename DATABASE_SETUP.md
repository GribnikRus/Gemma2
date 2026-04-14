# 🔧 Настройка подключения к базе данных

## 📋 Проблема
При запуске в Docker приложение пыталось подключиться к удалённому PostgreSQL (`192.168.0.34`), но:
1. Сервер недоступен из контейнера (firewall, сеть)
2. Таймаут соединения блокирует запуск приложения

## ✅ Решение (выбрано по умолчанию)
**SQLite для быстрой проверки работоспособности**

По умолчанию теперь используется SQLite:
```bash
DATABASE_URL=sqlite:///./data/gemma_hub.db
```

Это позволяет:
- Быстро запустить приложение без настройки PostgreSQL
- Протестировать весь функционал (кроме многопользовательской синхронизации)
- Избежать проблем с сетью и таймаутами

## 🔄 Как переключиться на PostgreSQL

### Вариант 1: Удалённый PostgreSQL (ваш сервер)
1. Откройте `.env`
2. Закомментируйте строку с SQLite
3. Раскомментируйте строку с вашим PostgreSQL:
```bash
# DATABASE_URL=sqlite:///./data/gemma_hub.db
DATABASE_URL=postgresql://bot_user:YesNo1977@192.168.0.34:5432/sleep_data_db
```
4. Проверьте доступность сервера:
```bash
ping 192.168.0.34
psql -h 192.168.0.34 -U bot_user -d sleep_data_db
```

### Вариант 2: PostgreSQL на хосте (Docker на Windows/Mac)
1. В `.env` используйте `host.docker.internal`:
```bash
DATABASE_URL=postgresql://bot_user:YesNo1977@host.docker.internal:5432/sleep_data_db
```

### Вариант 3: PostgreSQL на хосте (Docker на Linux)
1. Узнайте IP хоста:
```bash
ip addr show docker0 | grep "inet " | awk '{print $2}' | cut -d/ -f1
# Обычно это 172.17.0.1
```
2. В `.env`:
```bash
DATABASE_URL=postgresql://bot_user:YesNo1977@172.17.0.1:5432/sleep_data_db
```

### Вариант 4: PostgreSQL в Docker Compose
1. Добавьте сервис PostgreSQL в `docker-compose.yml`:
```yaml
services:
  postgres:
    image: postgres:15-alpine
    environment:
      POSTGRES_USER: bot_user
      POSTGRES_PASSWORD: YesNo1977
      POSTGRES_DB: sleep_data_db
    volumes:
      - pg_data:/var/lib/postgresql/data
    ports:
      - "5432:5432"
  
  app:
    # ... остальная конфигурация
    environment:
      - DATABASE_URL=postgresql://bot_user:YesNo1977@postgres:5432/sleep_data_db
    depends_on:
      - postgres

volumes:
  pg_data:
```

## 🧪 Проверка подключения

### Для SQLite:
```bash
python -c "from db import init_db; init_db(); print('OK')"
```
Ожидаемый вывод:
```
[INFO] 🔧 SQLite detected: using default pool settings
[INFO] ✅ Successfully connected to SQLite database
[INFO] Database file: ./data/gemma_hub.db
```

### Для PostgreSQL:
```bash
python -c "from db import init_db; init_db(); print('OK')"
```
Ожидаемый вывод:
```
[INFO] 🔧 PostgreSQL detected: pool_size=10, max_overflow=20
[INFO] ✅ Successfully connected to PostgreSQL database 'sleep_data_db' as user 'bot_user'
[INFO] Connection pool settings: pool_size=10, max_overflow=20, pool_recycle=3600
```

## ⚠️ Частые ошибки

### 1. `Connection timed out`
**Причина**: Сервер PostgreSQL недоступен по сети  
**Решение**: 
- Проверьте firewall: `sudo ufw allow 5432/tcp`
- Проверьте, что PostgreSQL слушает внешний интерфейс: `listen_addresses = '*'` в `postgresql.conf`
- Проверьте `pg_hba.conf`: разрешите подключение с вашего IP

### 2. `no such function: current_database()`
**Причина**: Приложение пытается выполнить PostgreSQL-специфичный запрос на SQLite  
**Решение**: Исправлено в `db.py` — теперь проверка типа БД делается до запроса

### 3. `'QueuePool' object has no attribute 'maxoverflow'`
**Причина**: Разные имена атрибутов у пулов SQLite и PostgreSQL  
**Решение**: Исправлено в `db.py` — используется правильное имя атрибута

## 📊 Сравнение режимов

| Параметр | SQLite | PostgreSQL |
|----------|--------|------------|
| **Скорость запуска** | ⚡ Мгновенно | 🐌 Требует настройки сети |
| **Производительность** | Хорошая для тестов | Отличная для production |
| **Многопользовательский режим** | ❌ Ограничен | ✅ Полная поддержка |
| **WebSocket чаты** | ✅ Работает | ✅ Работает |
| **ИИ (Ollama)** | ✅ Работает | ✅ Работает |
| **Рекомендация** | Для разработки | Для production |

## 🚀 Быстрый старт

```bash
# 1. Убедитесь, что используется SQLite (по умолчанию)
grep "^DATABASE_URL" .env
# Должно быть: DATABASE_URL=sqlite:///./data/gemma_hub.db

# 2. Инициализируйте базу
python -c "from db import init_db; init_db()"

# 3. Запустите приложение
python app.py

# 4. Откройте браузер
# http://localhost:5002
```

## 📝 Примечание
После успешного запуска на SQLite вы можете переключиться на PostgreSQL, изменив `.env` и перезапустив приложение. Все данные можно перенести через `pg_dump` и `psql`.
