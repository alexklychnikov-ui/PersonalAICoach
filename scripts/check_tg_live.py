"""Smoke: POST /api/v1/market/search source=telegram."""

from __future__ import annotations

import json
import sys

import httpx

base = sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:8000"
query = sys.argv[2] if len(sys.argv) > 2 else "t.me/Koteyka_Freelancer"
r = httpx.post(
    f"{base.rstrip('/')}/api/v1/market/search",
    json={"source": "telegram", "query": query, "limit": 5},
    timeout=60,
)
print("status", r.status_code)
data = r.json()
if isinstance(data, list):
    print("count", len(data))
    for item in data[:5]:
        print("-", item.get("title", "")[:80], "|", item.get("url"))
else:
    print(json.dumps(data, ensure_ascii=False)[:500])
