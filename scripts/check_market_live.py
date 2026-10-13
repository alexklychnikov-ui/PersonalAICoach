import httpx

base = "http://127.0.0.1:8000/api/v1"
for source in ("kwork", "flru", "yandex_uslugi"):
    r = httpx.post(
        f"{base}/market/search",
        json={"source": source, "query": "", "limit": 5},
        timeout=90,
    )
    data = r.json() if r.status_code < 400 else r.text
    n = len(data) if isinstance(data, list) else 0
    titles = [x.get("title", "")[:60] for x in data[:3]] if isinstance(data, list) else []
    print(source, r.status_code, "count=", n, "sample=", titles)
