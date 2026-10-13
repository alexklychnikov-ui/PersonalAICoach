import httpx

r = httpx.get("http://127.0.0.1:8000/health", timeout=10)
print("health", r.status_code, r.text)
r2 = httpx.get("http://127.0.0.1:8000/api/v1/interview/latest", timeout=10)
print("latest", r2.status_code)
d = r2.json()
answers = d.get("answers") or []
print("q", len(d.get("questions") or []), "answers", len(answers))
print("filled", sum(1 for a in answers if str(a).strip()))
print("preview", [str(a)[:40] for a in answers[:3]])
