#!/bin/bash

# Цвета для вывода
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Название сервиса и контейнера
SERVICE_NAME="app"
CONTAINER_NAME="gemma-hub-app"

echo -e "${YELLOW}🚀 Запуск дев-скрипта для Docker...${NC}\n"

# 1. Останавливаем и удаляем старые контейнеры
echo -e "${YELLOW}📦 Останавливаем и удаляем старые контейнеры...${NC}"
docker compose down

# 2. Удаляем старые образы (опционально)
echo -e "${YELLOW}🗑️  Удаляем старый образ сервиса ${SERVICE_NAME}...${NC}"
docker rmi $(docker images -q $(docker compose config --images | grep ${SERVICE_NAME})) 2>/dev/null || true

# 3. Очищаем неиспользуемые ресурсы
echo -e "${YELLOW}🧹 Очищаем неиспользуемые ресурсы Docker...${NC}"
docker system prune -f

# 4. Собираем заново без кэша
echo -e "${YELLOW}🔨 Собираем образ ${SERVICE_NAME} заново (без кэша)...${NC}"
docker compose build --no-cache ${SERVICE_NAME}

# 5. Запускаем контейнеры
echo -e "${YELLOW}▶️  Запускаем контейнеры...${NC}"
docker compose up -d

# 6. Ждем немного для инициализации
echo -e "${YELLOW}⏳ Ждем 3 секунды для запуска сервисов...${NC}"
sleep 3

# 7. Проверяем статус контейнера
echo -e "${YELLOW}🔍 Статус контейнера:${NC}"
docker ps --filter "name=${CONTAINER_NAME}"

# 8. Показываем логи
echo -e "\n${YELLOW}📋 Последние логи контейнера ${CONTAINER_NAME}:${NC}"
docker logs --tail 50 ${CONTAINER_NAME}

# 9. Опция для просмотра логов в реальном времени
echo -e "\n${GREEN}✅ Готово!${NC}"
echo -e "${YELLOW}Хотите посмотреть логи в реальном времени? (y/n)${NC}"
read -r answer
if [ "$answer" = "y" ] || [ "$answer" = "Y" ]; then
    echo -e "${GREEN}📺 Показываем логи в реальном времени (Ctrl+C для выхода)...${NC}"
    docker logs -f ${CONTAINER_NAME}
fi