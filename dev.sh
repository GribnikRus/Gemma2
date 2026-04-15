#!/bin/bash

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

SERVICE_NAME="app"
CONTAINER_NAME="gemma-hub-app"

echo -e "${YELLOW}🚀 Полная пересборка Docker...${NC}\n"

echo -e "${YELLOW}📦 Останавливаем контейнеры...${NC}"
docker compose down

echo -e "${YELLOW}🗑️  Удаляем старый образ...${NC}"
docker rmi $(docker images -q ${CONTAINER_NAME}) 2>/dev/null || true

echo -e "${YELLOW}🧹 Очищаем Docker...${NC}"
docker system prune -f

echo -e "${YELLOW}🔨 Собираем без кэша...${NC}"
docker compose build --no-cache ${SERVICE_NAME}

echo -e "${YELLOW}▶️  Запускаем...${NC}"
docker compose up -d

sleep 3

echo -e "${GREEN}✅ Статус:${NC}"
docker ps --filter "name=${CONTAINER_NAME}"

echo -e "\n${GREEN}📋 Логи:${NC}"
docker logs --tail 30 ${CONTAINER_NAME}

echo -e "\n${GREEN}✨ Готово!${NC}"
