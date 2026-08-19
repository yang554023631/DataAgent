#!/bin/bash
curl -X POST http://localhost:8000/api/chat \
  -H "Content-Type: application/json" \
  -d '{
    "message": "id为6的广告主 4月份消耗大于10的广告计划有哪些",
    "session_id": "test-fix-001"
  }' | python -m json.tool
