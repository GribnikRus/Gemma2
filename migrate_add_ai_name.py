"""
Миграция: Добавление колонки ai_name в таблицу chat_groups
Запускать после основного приложения или отдельно.
"""
import logging
from sqlalchemy import text
from db import engine, SessionLocal
from config import DATABASE_URL

logging.basicConfig(format="[%(levelname)s] %(asctime)s - %(name)s - %(message)s", level=logging.INFO)
logger = logging.getLogger("migration")


def add_ai_name_column():
    """Добавляет колонку ai_name в таблицу chat_groups если её нет"""
    db = SessionLocal()
    try:
        # Проверяем существует ли уже колонка
        result = db.execute(text("""
            SELECT column_name 
            FROM information_schema.columns 
            WHERE table_name = 'chat_groups' AND column_name = 'ai_name'
        """)).fetchone()
        
        if result:
            logger.info("Колонка ai_name уже существует в таблице chat_groups")
            return True
        
        logger.info("Добавление колонки ai_name в таблицу chat_groups...")
        
        # Добавляем колонку
        db.execute(text("""
            ALTER TABLE chat_groups 
            ADD COLUMN ai_name VARCHAR(100) DEFAULT 'Гемма'
        """))
        
        db.commit()
        logger.info("✅ Колонка ai_name успешно добавлена в таблицу chat_groups")
        return True
        
    except Exception as e:
        db.rollback()
        logger.error(f"❌ Ошибка при добавлении колонки ai_name: {e}")
        return False
    finally:
        db.close()


if __name__ == "__main__":
    print(f"Подключение к базе данных: {DATABASE_URL.split('@')[1]}...")
    success = add_ai_name_column()
    if success:
        print("✅ Миграция завершена успешно")
    else:
        print("❌ Миграция завершилась с ошибкой")
