#!/bin/bash

BASE_URL="http://localhost:8000"

echo "=== Creating session ==="
curl -X POST "$BASE_URL/api/sessions" \
  -H "Content-Type: application/json" \
  -d '{"user_id": "curl_test_19"}'

echo
echo

SESSION_ID=$(curl -s -X POST "$BASE_URL/api/sessions" -H "Content-Type: application/json" -d '{"user_id": "curl_test_19"}' | python3 -c "
import json
data = json.loads(input())
print(data['session_id'])
")

echo "Session ID: $SESSION_ID"
echo

echo "=== Sending query: 找出 广告主 digital_0 下名称含 mini 的创意，点击量大于50 ==="
echo "This may take several minutes..."
echo

curl -X POST "$BASE_URL/api/sessions/$SESSION_ID/messages" \
  -H "Content-Type: application/json" \
  -d '{"content": "找出 广告主 digital_0 下名称含 mini 的创意，点击量大于50"}' \
  -m 900

echo
echo "=== Done ==="
