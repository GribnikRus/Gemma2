#!/bin/bash
# healthcheck.sh - Проверка здоровья Gemma-Hub

set -e

HOST="${GEMMA_HUB_HOST:-localhost}"
PORT="${GEMMA_HUB_PORT:-5002}"
BASE_URL="http://${HOST}:${PORT}"

echo "🔍 Gemma-Hub Health Check"
echo "========================="
echo "Target: ${BASE_URL}"
echo ""

# 1. Проверка HTTP доступности
echo "1. Checking HTTP availability..."
if curl -s -o /dev/null -w "%{http_code}" "${BASE_URL}/" | grep -q "200\|302"; then
    echo "   ✅ HTTP server is running"
else
    echo "   ❌ HTTP server is NOT responding"
    exit 1
fi

# 2. Проверка health endpoint
echo "2. Checking /api/health endpoint..."
HEALTH_RESPONSE=$(curl -s "${BASE_URL}/api/health")
echo "   Response: ${HEALTH_RESPONSE}"

if echo "${HEALTH_RESPONSE}" | grep -q '"status":"healthy"'; then
    echo "   ✅ Service is healthy"
else
    echo "   ❌ Service is unhealthy"
    exit 1
fi

# 3. Проверка БД
if echo "${HEALTH_RESPONSE}" | grep -q '"database":"ok"'; then
    echo "   ✅ Database connection OK"
else
    echo "   ❌ Database connection FAILED"
    exit 1
fi

# 4. Проверка Ollama
if echo "${HEALTH_RESPONSE}" | grep -q '"ollama":"ok"'; then
    echo "   ✅ Ollama API connection OK"
else
    echo "   ❌ Ollama API connection FAILED"
    exit 1
fi

echo ""
echo "✅ All checks passed!"
exit 0
