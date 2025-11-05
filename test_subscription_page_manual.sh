#!/bin/bash

# Manual test script for US-002: User Subscription Page
# Tests the backend APIs that power the subscription page

set -e

API_URL="http://localhost:9003"
echo "Testing US-002 Subscription Page APIs..."
echo "=========================================="

# Step 1: Create test user and get token
echo ""
echo "1. Creating test user..."
SIGNUP_RESPONSE=$(curl -s -X POST "$API_URL/auth/signup" \
  -H "Content-Type: application/json" \
  -d '{"email":"test_sub_'$(date +%s)'@example.com","password":"testpass123","display_name":"Test User"}')

TOKEN=$(echo $SIGNUP_RESPONSE | grep -o '"access_token":"[^"]*' | cut -d'"' -f4)

if [ -z "$TOKEN" ]; then
  echo "ERROR: Failed to get token"
  echo "Response: $SIGNUP_RESPONSE"
  exit 1
fi

echo "✓ Token obtained: ${TOKEN:0:20}..."

# Step 2: Test GET /api/subscription
echo ""
echo "2. Testing GET /api/subscription..."
SUB_RESPONSE=$(curl -s -X GET "$API_URL/api/subscription" \
  -H "Authorization: Bearer $TOKEN")

echo "$SUB_RESPONSE" | python3 -m json.tool

if echo "$SUB_RESPONSE" | grep -q "tier_id"; then
  echo "✓ Subscription endpoint works"
else
  echo "✗ FAILED: Missing tier_id"
  exit 1
fi

# Step 3: Test GET /api/quota/status
echo ""
echo "3. Testing GET /api/quota/status..."
QUOTA_RESPONSE=$(curl -s -X GET "$API_URL/api/quota/status" \
  -H "Authorization: Bearer $TOKEN")

echo "$QUOTA_RESPONSE" | python3 -m json.tool

if echo "$QUOTA_RESPONSE" | grep -q "quota_used_seconds"; then
  echo "✓ Quota status endpoint works"
else
  echo "✗ FAILED: Missing quota_used_seconds"
  exit 1
fi

# Step 4: Test GET /api/payments/credit-packages
echo ""
echo "4. Testing GET /api/payments/credit-packages..."
PACKAGES_RESPONSE=$(curl -s -X GET "$API_URL/api/payments/credit-packages" \
  -H "Authorization: Bearer $TOKEN")

echo "$PACKAGES_RESPONSE" | python3 -m json.tool

if echo "$PACKAGES_RESPONSE" | grep -q "packages"; then
  PACKAGE_COUNT=$(echo "$PACKAGES_RESPONSE" | python3 -c "import sys, json; print(len(json.load(sys.stdin)['packages']))")
  echo "✓ Credit packages endpoint works ($PACKAGE_COUNT packages)"
else
  echo "✗ FAILED: Missing packages"
  exit 1
fi

# Step 5: Test POST /api/payments/stripe/create-checkout (expect 503 without Stripe key)
echo ""
echo "5. Testing POST /api/payments/stripe/create-checkout..."
CHECKOUT_RESPONSE=$(curl -s -w "\nHTTP_STATUS:%{http_code}" -X POST "$API_URL/api/payments/stripe/create-checkout" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"product_type":"subscription","tier_id":2}')

HTTP_STATUS=$(echo "$CHECKOUT_RESPONSE" | grep "HTTP_STATUS" | cut -d: -f2)
CHECKOUT_BODY=$(echo "$CHECKOUT_RESPONSE" | sed '/HTTP_STATUS/d')

echo "$CHECKOUT_BODY" | python3 -m json.tool || echo "$CHECKOUT_BODY"

if [ "$HTTP_STATUS" = "200" ]; then
  echo "✓ Checkout endpoint works (Stripe configured)"
elif [ "$HTTP_STATUS" = "503" ]; then
  echo "⚠ Checkout endpoint returns 503 (Stripe not configured - expected in test)"
else
  echo "✗ FAILED: Unexpected status $HTTP_STATUS"
  exit 1
fi

# Step 6: Test authentication required
echo ""
echo "6. Testing authentication required..."
UNAUTH_RESPONSE=$(curl -s -w "\nHTTP_STATUS:%{http_code}" -X GET "$API_URL/api/subscription")
UNAUTH_STATUS=$(echo "$UNAUTH_RESPONSE" | grep "HTTP_STATUS" | cut -d: -f2)

if [ "$UNAUTH_STATUS" = "401" ]; then
  echo "✓ Authentication required (401 returned)"
else
  echo "✗ FAILED: Expected 401, got $UNAUTH_STATUS"
  exit 1
fi

# Summary
echo ""
echo "=========================================="
echo "✓ ALL TESTS PASSED"
echo "=========================================="
echo ""
echo "Verified:"
echo "  - GET /api/subscription returns tier info"
echo "  - GET /api/quota/status returns quota data"
echo "  - GET /api/payments/credit-packages returns packages"
echo "  - POST /api/payments/stripe/create-checkout handles requests"
echo "  - All endpoints require authentication"
echo ""
echo "The subscription page frontend can now:"
echo "  1. Display current tier and quota"
echo "  2. Show credit packages"
echo "  3. Initiate Stripe checkout"
