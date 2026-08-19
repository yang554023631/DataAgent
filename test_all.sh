#!/bin/bash

echo "======================================"
echo "测试 1: id为6的广告主 4月份的消耗趋势"
echo "======================================"

# Create session
RESPONSE=$(curl -s -X POST http://localhost:8000/api/sessions \
  -H "Content-Type: application/json" \
  -d '{}')
SESSION_ID=$(echo "$RESPONSE" | python3 -c "import sys; import json; data = json.load(sys.stdin); print(data['session_id'])")
echo "Session ID: $SESSION_ID"
echo

curl -N -X POST http://localhost:8000/api/sessions/$SESSION_ID/messages/stream \
  -H "Content-Type: application/json" \
  -d '{"content": "id为6的广告主 4月份的消耗趋势"}'

echo -e "\n\n======================================"
echo "测试 2: 广告主6 下未删除的广告计划 4月份的消耗和点击"
echo "======================================"

RESPONSE=$(curl -s -X POST http://localhost:8000/api/sessions \
  -H "Content-Type: application/json" \
  -d '{}')
SESSION_ID2=$(echo "$RESPONSE" | python3 -c "import sys; import json; data = json.load(sys.stdin); print(data['session_id'])")
echo "Session ID: $SESSION_ID2"
echo

curl -N -X POST http://localhost:8000/api/sessions/$SESSION_ID2/messages/stream \
  -H "Content-Type: application/json" \
  -d '{"content": "广告主6 下未删除的广告计划 4月份的消耗和点击"}'

echo -e "\n\n======================================"
echo "测试 3: id为6的广告主 4月份消耗大于10的广告计划有哪些"
echo "======================================"

RESPONSE=$(curl -s -X POST http://localhost:8000/api/sessions \
  -H "Content-Type: application/json" \
  -d '{}')
SESSION_ID3=$(echo "$RESPONSE" | python3 -c "import sys; import json; data = json.load(sys.stdin); print(data['session_id'])")
echo "Session ID: $SESSION_ID3"
echo

curl -N -X POST http://localhost:8000/api/sessions/$SESSION_ID3/messages/stream \
  -H "Content-Type: application/json" \
  -d '{"content": "id为6的广告主 4月份消耗大于10的广告计划有哪些"}'
