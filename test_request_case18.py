#!/usr/bin/env python3
import requests
import json

url = "http://localhost:8000/api/v1/query"
payload = {
    "query": "digital_0 投放中的广告计划，名称含有 best，列出消耗和点击",
    "advertiser_id": "6"
}

response = requests.post(url, json=payload, stream=True)
print(f"Status: {response.status_code}")
print()

for line in response.iter_lines(decode_unicode=True):
    if line:
        print(line)
