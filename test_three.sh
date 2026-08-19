#!/bin/bash
tests=(
  "id为6的广告主 4月份的消耗趋势"
  "广告主6 下未删除的广告计划 4月份的消耗和点击"
  "id为6的广告主 4月份消耗大于10的广告计划有哪些"
)

for i in "${!tests[@]}"; do
  query="${tests[$i]}"
  test_num=$((i+1))
  echo "======================================"
  echo "测试 $test_num: $query"
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
    -d "{\"content\": \"$query\"}"

  echo -e "\n\n"
done
