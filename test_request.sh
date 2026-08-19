#!/bin/bash
# Test the API with the problematic query

# Create session
echo "=== Creating session ==="
curl -s -X POST http://localhost:8000/api/sessions \
  -H "Content-Type: application/json" \
  -d '{}' | python -m json.tool

echo -e "\n\n=== Send streaming message ==="
SESSION_ID=$(curl -s -X POST http://localhost:8000/api/sessions -H "Content-Type: application/json" -d '{}' | python -c "import json; data = json.loads(sys.stdin.read()); print(data['session_id'])")

echo "Session ID: $SESSION_ID"
echo -e "\nStarting stream:\n---"

# Stream the response
curl -N -X POST http://localhost:8000/api/sessions/$SESSION_ID/messages/stream \
  -H "Content-Type: application/json" \
  -d '{"content": "广告主6下未删除的广告计划4月份的消耗和点击"}'
