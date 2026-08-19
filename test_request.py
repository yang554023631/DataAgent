#!/usr/bin/env python3
import requests
import json
import sys

print("=== Creating session ===")
resp = requests.post("http://localhost:8000/api/sessions", json={})
session = resp.json()
session_id = session["session_id"]
print(f"Session created: {session_id}")
print()

print("=== Streaming response ===")
print("-" * 60)

url = f"http://localhost:8000/api/sessions/{session_id}/messages/stream"
data = {"content": "广告主6下未删除的广告计划4月份的消耗和点击"}

with requests.post(url, json=data, stream=True) as resp:
    for line in resp.iter_lines(decode_unicode=True):
        if line:
            print(line)

print("-" * 60)
