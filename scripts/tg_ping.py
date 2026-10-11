import os

import httpx

token = os.environ["TELEGRAM_BOT_TOKEN"]
owner = int(os.environ["TELEGRAM_OWNER_ID"])
r = httpx.get(f"https://api.telegram.org/bot{token}/getMe", timeout=30)
print("getMe", r.status_code, r.json().get("ok"), r.json().get("result", {}).get("username"))
r2 = httpx.post(
    f"https://api.telegram.org/bot{token}/sendMessage",
    json={"chat_id": owner, "text": "Smoke: бот на VPS OK. Напиши /start или /status"},
    timeout=30,
)
print("send", r2.status_code, r2.json().get("ok"), r2.json().get("description", ""))
