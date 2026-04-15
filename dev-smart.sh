#!/bin/bash

GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

CONTAINER_NAME="gemma-hub-app"
SERVICE_NAME="app"

echo -e "${YELLOW}🤖 Выберите режим:${NC}"
echo "1) ⚡ Быстрая пересборка (с кэшем)"
echo "2) 🔥 Полная пересборка (без кэша)"
echo "3) 🚀 Супер-быстрая (без остановки)"
echo "4) 📋 Просто посмотреть логи"
read -r choice

case $choice in
    1)
        echo -e "\n${YELLOW}⚡ Быстрая пересборка...${NC}"
        docker compose down
        docker compose build ${SERVICE_NAME}
        docker compose up -d
        ;;
    2)
        echo -e "\n${YELLOW}🔥 Полная пересборка...${NC}"
        docker compose down
        docker compose build --no-cache ${SERVICE_NAME}
        docker compose up -d
        ;;
    3)
        echo -e "\n${YELLOW}🚀 Супер-быстрая пересборка...${NC}"
        docker compose build ${SERVICE_NAME}
        docker compose up -d --no-deps --force-recreate ${SERVICE_NAME}
        ;;
    4)
        echo -e "\n${YELLOW}📋 Логи в реальном времени (Ctrl+C для выхода):${NC}"
        docker logs -f ${CONTAINER_NAME}
        exit 0
        ;;
    *)
        echo -e "${RED}❌ Неверный выбор${NC}"
        exit 1
        ;;
esac

echo -e "\n${GREEN}✅ Логи:${NC}"
docker logs --tail 20 ${CONTAINER_NAME}
echo -e "\n${GREEN}✨ Статус:${NC}"
docker ps --filter "name=${CONTAINER_NAME}"
