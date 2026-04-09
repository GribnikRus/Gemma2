#!/bin/bash

# ==========================================
# Скрипт запуска gemma-hub
# ==========================================

set -e  # Остановить скрипт при критической ошибке

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# Цвета для вывода
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo -e "${GREEN}============================================${NC}"
echo -e "${GREEN}🚀 Запуск gemma-hub...${NC}"
echo -e "${GREEN}============================================${NC}"

# 1. Проверка виртуального окружения
if [ ! -d "venv" ]; then
    echo -e "${RED}❌ Виртуальное окружение 'venv' не найдено!${NC}"
    echo "Сначала создайте его: python3 -m venv venv && source venv/bin/activate && pip install -r requirements.txt"
    exit 1
fi

# 2. Активация окружения
echo "🔌 Активация виртуального окружения..."
source venv/bin/activate

# 3. Загрузка переменных из .env (если есть)
if [ -f ".env" ]; then
    echo "📄 Загрузка переменных из .env..."
    set -a
    source .env
    set +a
fi

# 4. Очистка старых процессов и файлов
echo "🧹 Очистка старых процессов..."

# Убиваем всё, что висит на порту 5002
if lsof -Pi :5002 -sTCP:LISTEN -t >/dev/null ; then
    echo -e "${YELLOW}⚠️ Порт 5002 занят. Освобождение...${NC}"
    fuser -k 5002/tcp 2>/dev/null || true
    sleep 1
fi

# Удаляем старые PID файлы
rm -f celery.pid flask.pid

# Убиваем возможные зависшие процессы celery и python, принадлежащие этому проекту
pkill -f "celery.*gemma" 2>/dev/null || true
# pkill -f "python.*app.py" 2>/dev/null || true # Лучше не убивать все python, а полагаться на порт

# 5. Функция корректной остановки
cleanup() {
    echo ""
    echo -e "${YELLOW}⏹️  Получен сигнал остановки. Завершение работы...${NC}"
    
    if [ -n "$FLASK_PID" ]; then
        echo "   Остановка Flask (PID: $FLASK_PID)..."
        kill $FLASK_PID 2>/dev/null || true
    fi
    
    if [ -n "$CELERY_PID" ]; then
        echo "   Остановка Celery (PID: $CELERY_PID)..."
        kill $CELERY_PID 2>/dev/null || true
        # Ждем немного и убиваем жестко, если не закрылся
        sleep 2
        kill -9 $CELERY_PID 2>/dev/null || true
    fi
    
    # Чистим дочерние процессы
    pkill -P $$ 2>/dev/null || true
    
    rm -f celery.pid flask.pid
    echo -e "${GREEN}✅ Все сервисы остановлены.${NC}"
    exit 0
}

# Перехват сигналов Ctrl+C и TERM
trap cleanup SIGINT SIGTERM

# 6. Запуск Celery Worker
echo "📦 Запуск Celery worker..."
# --detach запускает в фоне, --pidfile сохраняет ID процесса
celery -A celery_tasks.tasks worker --loglevel=info --detach --pidfile=celery.pid

if [ -f celery.pid ]; then
    CELERY_PID=$(cat celery.pid)
    echo -e "   ${GREEN}✅ Celery запущен (PID: $CELERY_PID)${NC}"
else
    echo -e "   ${RED}❌ Не удалось запустить Celery${NC}"
    cleanup
fi

# Даем Celery пару секунд на инициализацию подключения к Redis/DB
sleep 2

# 7. Запуск Flask
echo "🌐 Запуск Flask приложения (Port 5002)..."
python app.py > flask.log 2>&1 &
FLASK_PID=$!
echo $FLASK_PID > flask.pid
echo -e "   ${GREEN}✅ Flask запущен (PID: $FLASK_PID)${NC}"

echo ""
echo -e "${GREEN}============================================${NC}"
echo -e "${GREEN}✅ Сервис успешно запущен!${NC}"
echo -e "${GREEN}============================================${NC}"
echo ""
echo "🌐 Web Interface: http://localhost:5002"
echo "📝 Flask Logs:     tail -f flask.log"
echo "🔄 Celery Status:  celery -A celery_tasks.tasks inspect ping"
echo ""
echo -e "${YELLOW}Нажмите Ctrl+C для остановки всех сервисов${NC}"
echo ""

# Ждем завершения Flask процесса
wait $FLASK_PID