#!/usr/bin/env python3
import requests

try:
    resp = requests.post("http://localhost:8000/api/sessions", json={"user_id": "test_debug"}, timeout=5)
    print(f"Status: {resp.status_code}")
    if resp.status_code == 200:
        print(f"Response: {resp.json()}")
        print("\n✅ Server is responding OK")
    else:
        print(f"\n❌ Server returned status {resp.status_code}")
except Exception as e:
    print(f"❌ Error connecting to server: {e}")
