#!/usr/bin/env python3
"""Test SSE streaming directly - observe when each event is received"""
import json
import time
import requests

BACKEND_URL = "http://localhost:8000"

def create_session():
    resp = requests.post(f"{BACKEND_URL}/api/sessions", json={})
    resp.raise_for_status()
    return resp.json()["session_id"]

def parse_sse_line(line):
    """Parse a single SSE line"""
    line = line.rstrip('\n')
    if not line:
        return None
    if line.startswith('data: '):
        return line[6:]
    return None

def stream_message(session_id: str, query: str):
    url = f"{BACKEND_URL}/api/sessions/{session_id}/messages/stream"
    payload = {"content": query}
    headers = {"Content-Type": "application/json"}

    print(f">>> Request: {query}")
    print(f">>> Connecting to {url}...")
    print()

    start_time = time.time()
    event_count = 0

    with requests.post(url, json=payload, headers=headers, stream=True) as resp:
        resp.raise_for_status()
        buffer = ''
        for line in resp.iter_lines(decode_unicode=True):
            if line is None:
                continue
            if not line:
                # Empty line means end of event
                if buffer:
                    try:
                        data = json.loads(buffer)
                        event_time = time.time() - start_time
                        event_count += 1
                        evt_type = data.get('type')
                        step = data.get('step')
                        status = data.get('status')
                        print(f"[+{event_time:.2f}s] #{event_count}: type={evt_type:<15} step={step:<20} status={status}")
                    except json.JSONDecodeError as e:
                        print(f"JSON decode error: {e}, buffer={repr(buffer)}")
                    finally:
                        buffer = ''
            else:
                parsed = parse_sse_line(line)
                if parsed is not None:
                    buffer += parsed

    print()
    print(f"<<< Complete. Total events: {event_count}, total time: {time.time() - start_time:.2f}s")

if __name__ == "__main__":
    session_id = create_session()
    print(f"Created session: {session_id}")
    print()
    # Test case 1
    stream_message(session_id, "id为6的广告主4月份的消耗趋势")
