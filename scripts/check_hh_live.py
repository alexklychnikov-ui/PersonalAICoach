import os

import httpx

from app.config import get_settings

s = get_settings()
print("hh_enabled", s.hh_enabled)
print("token_set", bool(s.hh_access_token))
print("client_id_set", bool(s.hh_client_id))
print("ua", s.hh_user_agent)

headers = {
    "User-Agent": s.hh_user_agent,
    "Accept": "application/json",
}
if s.hh_access_token:
    headers["Authorization"] = f"Bearer {s.hh_access_token}"

with httpx.Client(timeout=30) as client:
    r = client.get(
        "https://api.hh.ru/vacancies",
        params={"text": "telegram", "per_page": 5, "page": 0},
        headers=headers,
    )
    print("direct", r.status_code, r.text[:400].replace("\n", " "))

    r2 = client.post(
        "http://127.0.0.1:8000/api/v1/market/search",
        json={"source": "hh", "query": "telegram", "limit": 5},
        timeout=60,
    )
    print("api", r2.status_code)
    data = r2.json()
    if isinstance(data, list):
        print("count", len(data))
        for x in data[:5]:
            print("-", x.get("title", "")[:80])
    else:
        print(data)
