#!/bin/bash

# ==========================================
# Скрипт запуска gemma-hub
# ==========================================

set -e  # Остановить скрипт при ошибке

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# Проверка наличия виртуального окружения
if [ ! -d "venv" ]; then
    echo "❌ Виртуальное окружение не найдено!"
    echo "Сначала выполните: ./setup.sh"
    exit 1
fi

# Активация виртуального окружения
echo "🔌 Активация виртуального окружения..."
source venv/bin/activate

# Проверка переменных окружения (опционально)
if [ -f ".env" ]; then
    echo "📄 Загрузка переменных из .env..."
    export $(cat .env | grep -v '^#' | xargs)
fi

echo ""
echo "============================================"
echo "🚀 Запуск gemma-hub..."
echo "============================================"
echo ""
echo "📍 Рабочая директория: $SCRIPT_DIR"
echo "🌐 Flask будет доступен на: http://localhost:5002"
echo ""

# Функция для остановки процессов при прерывании
cleanup() {
    echo ""
    echo "⏹️  Остановка сервисов..."
    if [ -n "$FLASK_PID" ] && kill -0 $FLASK_PID 2>/dev/null; then
        kill $FLASK_PID
    fi
    if [ -n "$CELERY_PID" ] && kill -0 $CELERY_PID 2>/dev/null; then
        kill $CELERY_PID
    fi
    # Остановка всех процессов celery дочерних процессов
    pkill -P $$ 2>/dev/null || true
    echo "✅ Все сервисы остановлены"
    exit 0
}

# Перехват сигналов для корректной остановки
trap cleanup SIGINT SIGTERM

# Запуск Celery worker в фоне
echo "📦 Запуск Celery worker..."
celery -A celery_tasks.tasks worker --loglevel=info --detach --pidfile=celery.pid
CELERY_PID=$!
echo "   ✅ Celery запущен (PID: $CELERY_PID)"

# Небольшая пауза для инициализации Celery
sleep 2

# Запуск Flask приложения
echo "🌐 Запуск Flask приложения..."
python app.py &
FLASK_PID=$!
echo "   ✅ Flask запущен (PID: $FLASK_PID)"

echo ""
echo "============================================"
echo "✅ Сервис запущен!"
echo ""
echo "Flask:  http://localhost:5002"
echo "Celery: активен (фоновый процесс)"
echo ""
echo "Нажмите Ctrl+C для остановки всех сервисов"
echo "============================================"
echo ""

# Ожидание завершения работы Flask
wait $FLASK_PID
