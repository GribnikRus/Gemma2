#!/bin/bash

GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

CONTAINER_NAME="gemma-hub-app"
SERVICE_NAME="app"

echo -e "${YELLOW}🚀 Супер-быстрая пересборка...${NC}\n"

echo -e "${YELLOW}🔨 Пересобираем...${NC}"
docker compose build ${SERVICE_NAME}

echo -e "${YELLOW}🔄 Перезапускаем сервис...${NC}"
docker compose up -d --no-deps --force-recreate ${SERVICE_NAME}

echo -e "\n${GREEN}✅ Логи:${NC}"
docker logs --tail 15 ${CONTAINER_NAME}

echo -e "\n${GREEN}✨ Статус:${NC}"
docker ps --filter "name=${CONTAINER_NAME}"
