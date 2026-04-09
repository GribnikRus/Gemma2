# migrate_new_schema.py
"""
Скрипт миграции базы данных.
Создает новые таблицы, необходимые для архитектуры gemma-hub,
не удаляя и не изменяя существующие данные (кроме создания таблиц).
"""

import sys
from db import engine, Base
from config import DATABASE_URL

def run_migration():
    print(f"Подключение к базе данных: {DATABASE_URL.split('@')[1]}...")
    
    try:
        # Создаем все таблицы, которых нет в базе.
        # Существующие таблицы (например, clients) останутся без изменений.
        # Примечание: Если в таблице clients нет колонки 'login' (а есть 'username'),
        # этот скрипт её НЕ изменит. Это нужно сделать вручную или отдельным ALTER TABLE.
        # Но так как мы обновили модель в db.py, SQLAlchemy будет ожидать правильную структуру при работе.
        
        print("Проверка схемы и создание отсутствующих таблиц...")
        Base.metadata.create_all(bind=engine)
        
        print("✅ Успешно! Все необходимые таблицы созданы.")
        print("Список созданных таблиц (если их не было):")
        tables = [
            "personal_chats", "chat_groups", "group_members", 
            "chat_messages", "task_history", "observer_sessions", "observer_analyses"
        ]
        for t in tables:
            print(f"  - {t}")
            
    except Exception as e:
        print(f"❌ Ошибка при миграции: {e}")
        sys.exit(1)

if __name__ == "__main__":
    run_migration()