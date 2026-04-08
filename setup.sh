#!/bin/bash

# ==========================================
# Скрипт настройки окружения для gemma-hub
# ==========================================

set -e  # Остановить скрипт при ошибке

echo "🚀 Настройка окружения для gemma-hub..."

# 1. Проверка наличия Python 3
if ! command -v python3 &> /dev/null; then
    echo "❌ Ошибка: Python 3 не найден. Установите Python 3.8+"
    exit 1
fi

echo "✅ Python 3 найден: $(python3 --version)"

# 2. Создание виртуального окружения (если еще не создано)
if [ ! -d "venv" ]; then
    echo "📦 Создание виртуального окружения..."
    python3 -m venv venv
    echo "✅ Виртуальное окружение создано"
else
    echo "ℹ️  Виртуальное окружение уже существует"
fi

# 3. Активация виртуального окружения
echo "🔌 Активация виртуального окружения..."
source venv/bin/activate

# 4. Обновление pip
echo "⬆️  Обновление pip..."
pip install --upgrade pip

# 5. Установка зависимостей
echo "📥 Установка зависимостей из requirements.txt..."
pip install -r requirements.txt

echo "✅ Все зависимости установлены!"

# 6. Проверка конфигурации
echo ""
echo "🔍 Проверка доступности сервисов..."

# Проверка PostgreSQL
if command -v psql &> /dev/null; then
    echo "   ℹ️  PostgreSQL клиент найден"
else
    echo "   ⚠️  PostgreSQL клиент не найден (не критично, если БД доступна по сети)"
fi

# Проверка Redis
if command -v redis-cli &> /dev/null; then
    if redis-cli ping &> /dev/null; then
        echo "   ✅ Redis доступен"
    else
        echo "   ⚠️  Redis CLI найден, но сервер не отвечает на ping"
    fi
else
    echo "   ⚠️  Redis CLI не найден (проверьте подключение вручную)"
fi

echo ""
echo "============================================"
echo "✅ Настройка завершена успешно!"
echo ""
echo "Для запуска приложения выполните:"
echo "  source venv/bin/activate"
echo "  ./run.sh"
echo ""
echo "Или используйте:"
echo "  ./run.sh"
echo "============================================"
