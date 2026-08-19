#!/bin/bash
# Test smoke test 3: 广告主6 4月份消耗大于10的广告计划有哪些

# Create session and get ID
echo "Creating session..."
RESPONSE=$(curl -s -X POST http://localhost:8000/api/sessions \
  -H "Content-Type: application/json" \
  -d '{}')

echo "Response: $RESPONSE"
SESSION_ID=$(echo "$RESPONSE" | python3 -c "import sys; import json; data = json.load(sys.stdin); print(data['session_id'])")

echo "Session ID: $SESSION_ID"
echo -e "\nStarting stream for query: 广告主6 4月份消耗大于10的广告计划有哪些\n---"

curl -N -X POST http://localhost:8000/api/sessions/$SESSION_ID/messages/stream \
  -H "Content-Type: application/json" \
  -d '{"content": "广告主6 4月份消耗大于10的广告计划有哪些"}'
