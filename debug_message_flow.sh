#!/bin/bash
# LiveTranslator Message Flow Debug Script
# This captures the entire flow: Browser -> API -> Redis -> STT -> Redis -> API -> Browser

set -e

BLUE='\033[0;34m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

echo -e "${GREEN}================================================${NC}"
echo -e "${GREEN}LiveTranslator Message Flow Debugger${NC}"
echo -e "${GREEN}================================================${NC}"
echo ""

# Create output directory
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
OUTPUT_DIR="/tmp/lt_debug_${TIMESTAMP}"
mkdir -p "$OUTPUT_DIR"

echo -e "${BLUE}Output directory: $OUTPUT_DIR${NC}"
echo ""

# Get JWT token
echo -e "${BLUE}[1/7] Getting authentication token...${NC}"
TOKEN=$(curl -sS -X POST http://localhost:9003/auth/login \
  -H 'content-type: application/x-www-form-urlencoded' \
  --data-urlencode 'username=YOU@example.com' \
  --data-urlencode 'password=STRONGPASS' | jq -r '.access_token')

if [ -z "$TOKEN" ] || [ "$TOKEN" == "null" ]; then
    echo "❌ Failed to get token"
    exit 1
fi
echo "✓ Token obtained: ${TOKEN:0:20}..."
echo "$TOKEN" > "$OUTPUT_DIR/token.txt"
echo ""

# Start Redis monitor in background
echo -e "${BLUE}[2/7] Starting Redis monitor...${NC}"
docker compose exec -T redis redis-cli -n 5 MONITOR > "$OUTPUT_DIR/redis_monitor.log" 2>&1 &
REDIS_PID=$!
echo "✓ Redis monitor started (PID: $REDIS_PID)"
sleep 1
echo ""

# Start API logs in background
echo -e "${BLUE}[3/7] Starting API logs capture...${NC}"
docker compose logs -f api > "$OUTPUT_DIR/api_logs.log" 2>&1 &
API_PID=$!
echo "✓ API logs started (PID: $API_PID)"
sleep 1
echo ""

# Start STT worker logs in background
echo -e "${BLUE}[4/7] Starting STT worker logs capture...${NC}"
docker compose logs -f stt_worker > "$OUTPUT_DIR/stt_worker_logs.log" 2>&1 &
STT_PID=$!
echo "✓ STT worker logs started (PID: $STT_PID)"
sleep 1
echo ""

# Start WebSocket client in background
echo -e "${BLUE}[5/7] Starting WebSocket client...${NC}"
websocat "ws://localhost:9003/ws/rooms/demo?token=$TOKEN" > "$OUTPUT_DIR/websocket_messages.log" 2>&1 &
WS_PID=$!
echo "✓ WebSocket client started (PID: $WS_PID)"
sleep 2
echo ""

# Instructions for user
echo -e "${GREEN}================================================${NC}"
echo -e "${YELLOW}READY TO TEST!${NC}"
echo -e "${GREEN}================================================${NC}"
echo ""
echo "All monitoring is now active. Please:"
echo ""
echo "  1. Open your browser to: https://livetranslator.pawelgawliczek.cloud"
echo "  2. Login with your credentials"
echo "  3. Join room: demo"
echo "  4. Click 'Start mic' button"
echo "  5. Speak clearly for 5-10 seconds"
echo "  6. Click 'Stop mic' button"
echo ""
echo -e "${YELLOW}When done, press ENTER here to stop monitoring...${NC}"
read -r

# Stop all monitoring processes
echo ""
echo -e "${BLUE}[6/7] Stopping monitors...${NC}"
kill $REDIS_PID 2>/dev/null || true
kill $API_PID 2>/dev/null || true
kill $STT_PID 2>/dev/null || true
kill $WS_PID 2>/dev/null || true
sleep 2
echo "✓ All monitors stopped"
echo ""

# Analyze the logs
echo -e "${BLUE}[7/7] Analyzing captured data...${NC}"
echo ""

# Create analysis report
REPORT="$OUTPUT_DIR/ANALYSIS_REPORT.txt"

cat > "$REPORT" << 'EOF'
================================================================================
LiveTranslator Message Flow Analysis Report
================================================================================

EOF

echo "Generated: $(date)" >> "$REPORT"
echo "" >> "$REPORT"

# Check 1: WebSocket Connection
echo "=== 1. WebSocket Connection ===" >> "$REPORT"
WS_JOIN=$(grep -c "ws_join.*demo" "$OUTPUT_DIR/api_logs.log" 2>/dev/null || echo "0")
if [ "$WS_JOIN" -gt 0 ]; then
    echo "✓ WebSocket connected to room 'demo' ($WS_JOIN times)" >> "$REPORT"
    grep "ws_join.*demo" "$OUTPUT_DIR/api_logs.log" | tail -3 >> "$REPORT"
else
    echo "✗ No WebSocket connection detected" >> "$REPORT"
fi
echo "" >> "$REPORT"

# Check 2: Audio chunks sent from browser
echo "=== 2. Audio Chunks (Browser -> API) ===" >> "$REPORT"
AUDIO_CHUNKS=$(grep -c "\[STT\] push_chunk" "$OUTPUT_DIR/api_logs.log" 2>/dev/null || echo "0")
if [ "$AUDIO_CHUNKS" -gt 0 ]; then
    echo "✓ $AUDIO_CHUNKS audio chunks received by API" >> "$REPORT"
    grep "\[STT\] push_chunk" "$OUTPUT_DIR/api_logs.log" | head -5 >> "$REPORT"
    echo "..." >> "$REPORT"
    grep "\[STT\] push_chunk" "$OUTPUT_DIR/api_logs.log" | tail -2 >> "$REPORT"
else
    echo "✗ No audio chunks detected" >> "$REPORT"
fi
echo "" >> "$REPORT"

# Check 3: Audio chunks published to Redis
echo "=== 3. Redis Publish to stt_input ===" >> "$REPORT"
STT_INPUT=$(grep -c 'PUBLISH.*stt_input.*audio_chunk' "$OUTPUT_DIR/redis_monitor.log" 2>/dev/null || echo "0")
if [ "$STT_INPUT" -gt 0 ]; then
    echo "✓ $STT_INPUT audio chunks published to Redis stt_input channel" >> "$REPORT"
    grep 'PUBLISH.*stt_input' "$OUTPUT_DIR/redis_monitor.log" | head -3 | sed 's/pcm16_base64":"[^"]*"/pcm16_base64":"<TRUNCATED>"/' >> "$REPORT"
else
    echo "✗ No messages published to stt_input" >> "$REPORT"
fi
echo "" >> "$REPORT"

# Check 4: STT worker processing
echo "=== 4. STT Worker Processing ===" >> "$REPORT"
STT_LISTENING=$(grep -c "STT.*listening.*stt_input" "$OUTPUT_DIR/stt_worker_logs.log" 2>/dev/null || echo "0")
if [ "$STT_LISTENING" -gt 0 ]; then
    echo "✓ STT worker is listening on stt_input" >> "$REPORT"
else
    echo "✗ STT worker not listening on correct channel" >> "$REPORT"
    grep "listening" "$OUTPUT_DIR/stt_worker_logs.log" >> "$REPORT" 2>/dev/null || echo "No listening messages found" >> "$REPORT"
fi
echo "" >> "$REPORT"

# Check 5: STT results published
echo "=== 5. STT Results Published to stt_events ===" >> "$REPORT"
STT_EVENTS=$(grep -c 'PUBLISH.*stt_events' "$OUTPUT_DIR/redis_monitor.log" 2>/dev/null || echo "0")
if [ "$STT_EVENTS" -gt 0 ]; then
    echo "✓ $STT_EVENTS STT results published to stt_events" >> "$REPORT"
    grep 'PUBLISH.*stt_events' "$OUTPUT_DIR/redis_monitor.log" | head -5 >> "$REPORT"
else
    echo "✗ No STT results published" >> "$REPORT"
fi
echo "" >> "$REPORT"

# Check 6: API received STT events
echo "=== 6. API Received STT Events ===" >> "$REPORT"
API_STT=$(grep -c 'stt_event.*kind=' "$OUTPUT_DIR/api_logs.log" 2>/dev/null || echo "0")
if [ "$API_STT" -gt 0 ]; then
    echo "✓ API received $API_STT STT events" >> "$REPORT"
    grep 'stt_event' "$OUTPUT_DIR/api_logs.log" | head -5 >> "$REPORT"
else
    echo "✗ API did not receive STT events" >> "$REPORT"
fi
echo "" >> "$REPORT"

# Check 7: Messages sent to WebSocket
echo "=== 7. Messages in WebSocket Client ===" >> "$REPORT"
WS_MESSAGES=$(grep -c 'type.*stt_' "$OUTPUT_DIR/websocket_messages.log" 2>/dev/null || echo "0")
if [ "$WS_MESSAGES" -gt 0 ]; then
    echo "✓ $WS_MESSAGES messages received by WebSocket client" >> "$REPORT"
    grep 'type.*stt_' "$OUTPUT_DIR/websocket_messages.log" | head -5 >> "$REPORT"
else
    echo "✗ No messages in WebSocket" >> "$REPORT"
fi
echo "" >> "$REPORT"

# Check 8: Message format analysis
echo "=== 8. Message Format Analysis ===" >> "$REPORT"
echo "Sample STT event from Redis:" >> "$REPORT"
grep 'PUBLISH.*stt_events' "$OUTPUT_DIR/redis_monitor.log" | head -1 | grep -o '{.*}' | python3 -m json.tool 2>/dev/null >> "$REPORT" || echo "Could not parse JSON" >> "$REPORT"
echo "" >> "$REPORT"

# Summary
echo "=== SUMMARY ===" >> "$REPORT"
echo "" >> "$REPORT"

ISSUES=0

if [ "$WS_JOIN" -eq 0 ]; then
    echo "❌ ISSUE: WebSocket not connecting" >> "$REPORT"
    ((ISSUES++))
fi

if [ "$AUDIO_CHUNKS" -eq 0 ]; then
    echo "❌ ISSUE: No audio chunks from browser" >> "$REPORT"
    ((ISSUES++))
fi

if [ "$STT_INPUT" -eq 0 ]; then
    echo "❌ ISSUE: API not publishing to Redis stt_input" >> "$REPORT"
    ((ISSUES++))
fi

if [ "$STT_LISTENING" -eq 0 ]; then
    echo "❌ ISSUE: STT worker not listening on correct channel" >> "$REPORT"
    ((ISSUES++))
fi

if [ "$STT_EVENTS" -eq 0 ]; then
    echo "❌ ISSUE: STT worker not producing results" >> "$REPORT"
    ((ISSUES++))
fi

if [ "$API_STT" -eq 0 ]; then
    echo "❌ ISSUE: API not receiving STT events from Redis" >> "$REPORT"
    ((ISSUES++))
fi

if [ "$WS_MESSAGES" -eq 0 ]; then
    echo "❌ ISSUE: Messages not reaching WebSocket client" >> "$REPORT"
    ((ISSUES++))
fi

if [ $ISSUES -eq 0 ]; then
    echo "✓ All checks passed! Backend is working correctly." >> "$REPORT"
    echo "" >> "$REPORT"
    echo "If transcripts still not showing in browser, the issue is:" >> "$REPORT"
    echo "  - Frontend JavaScript not handling messages correctly" >> "$REPORT"
    echo "  - Browser cache (try Cmd+Shift+R or incognito mode)" >> "$REPORT"
    echo "  - Console errors (check browser DevTools console)" >> "$REPORT"
else
    echo "❌ Found $ISSUES issue(s) in the message flow" >> "$REPORT"
fi

echo "" >> "$REPORT"
echo "Full logs available in: $OUTPUT_DIR" >> "$REPORT"
echo "================================================================================" >> "$REPORT"

# Display report
cat "$REPORT"

echo ""
echo -e "${GREEN}================================================${NC}"
echo -e "${GREEN}Debug Complete!${NC}"
echo -e "${GREEN}================================================${NC}"
echo ""
echo "All logs saved to: $OUTPUT_DIR"
echo ""
echo "Files created:"
echo "  - ANALYSIS_REPORT.txt    (Summary)"
echo "  - api_logs.log           (API container logs)"
echo "  - stt_worker_logs.log    (STT worker logs)"
echo "  - redis_monitor.log      (All Redis activity)"
echo "  - websocket_messages.log (WebSocket client messages)"
echo "  - token.txt              (JWT token used)"
echo ""
