#!/bin/bash

# Test script for Language Configuration Admin API
# Tests all new endpoints added for Migration 007

echo "========================================="
echo "Testing Language Configuration Admin API"
echo "========================================="
echo ""

API_URL="http://localhost:8000"

# Test 1: Get all language configurations
echo "1. Testing GET /api/admin/languages"
echo "-----------------------------------"
curl -s "${API_URL}/api/admin/languages" \
  --cookie "session=test" \
  | python3 -m json.tool 2>/dev/null || echo "Response:"
echo ""
echo ""

# Test 2: Get provider health
echo "2. Testing GET /api/admin/providers/health"
echo "-------------------------------------------"
curl -s "${API_URL}/api/admin/providers/health" \
  --cookie "session=test" \
  | python3 -m json.tool 2>/dev/null || echo "Response:"
echo ""
echo ""

# Test 3: Get system stats
echo "3. Testing GET /api/admin/stats"
echo "-------------------------------"
curl -s "${API_URL}/api/admin/stats" \
  --cookie "session=test" \
  | python3 -m json.tool 2>/dev/null || echo "Response:"
echo ""
echo ""

# Test 4: Get specific language config (Spanish)
echo "4. Testing GET /api/admin/languages/es-ES/config"
echo "-------------------------------------------------"
curl -s "${API_URL}/api/admin/languages/es-ES/config" \
  --cookie "session=test" \
  | python3 -m json.tool 2>/dev/null || echo "Response:"
echo ""
echo ""

# Test 5: Database verification
echo "5. Database Verification"
echo "------------------------"
echo "Languages configured:"
docker compose exec -T postgres psql -U lt_user -d livetranslator -c \
  "SELECT COUNT(DISTINCT language) as languages FROM stt_routing_config WHERE language != '*';" \
  2>/dev/null | grep -v "^$" | head -n 5

echo ""
echo "Provider health status:"
docker compose exec -T postgres psql -U lt_user -d livetranslator -c \
  "SELECT provider, service_type, status FROM provider_health ORDER BY service_type, provider;" \
  2>/dev/null | grep -v "^$" | head -n 15

echo ""
echo "========================================="
echo "Test Complete!"
echo "========================================="
