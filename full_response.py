#!/usr/bin/env python3
import requests
import json

BASE_URL = "http://localhost:8000"
query = "广告主6转化率最高的创意"

# Create session
resp = requests.post(f"{BASE_URL}/api/sessions", json={"user_id": "test"})
session = resp.json()
session_id = session["session_id"]

# Send message
resp = requests.post(
    f"{BASE_URL}/api/sessions/{session_id}/messages",
    json={"content": query}
)

result = resp.json()
print(json.dumps(result, indent=2, ensure_ascii=False))
