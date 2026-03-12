#!/usr/bin/env python3
import time
import httpx

URL = "http://127.0.0.1:8000/api/hyperliquid/run-scan"
SLEEP_SECONDS = 30

while True:
    try:
        with httpx.Client(timeout=10) as c:
            c.post(URL)
    except Exception:
        pass
    time.sleep(SLEEP_SECONDS)
