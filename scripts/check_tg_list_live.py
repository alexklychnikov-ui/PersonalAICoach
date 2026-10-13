"""Smoke telegram channel-list search on API."""

from __future__ import annotations

import json
import sys

import httpx

base = (sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:8000").rstrip("/")
r = httpx.post(
    f"{base}/api/v1/market/search",
    json={"source": "telegram", "query": "", "limit": 8},
    timeout=90,
)
print("status", r.status_code)
d = r.json()
if not isinstance(d, list):
    print(json.dumps(d, ensure_ascii=False)[:500])
    raise SystemExit(1)
print("n", len(d))
for x in d:
    raw = x.get("raw") or {}
    print("-", raw.get("channel_label"), "|", (x.get("title") or "")[:80])
if d:
    print("errs", (d[0].get("raw") or {}).get("channel_errors"))
