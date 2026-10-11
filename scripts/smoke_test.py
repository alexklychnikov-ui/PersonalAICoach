"""Smoke-test Personal AI Coach API (without hh.ru)."""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

import httpx
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[1]
load_dotenv(ROOT / ".env")

BASE = os.getenv("SMOKE_BASE_URL", "https://aicareercoach.alexklyvibe.ru").rstrip("/")
PREFIX = os.getenv("API_PREFIX", "/api/v1")


def ok(name: str, cond: bool, detail: str = "") -> None:
    status = "PASS" if cond else "FAIL"
    print(f"[{status}] {name}" + (f" — {detail}" if detail else ""))
    if not cond:
        raise SystemExit(1)


def main() -> None:
    client = httpx.Client(base_url=BASE, timeout=120)
    print(f"BASE={BASE}")

    r = client.get("/health")
    ok("health", r.status_code == 200 and r.json().get("status") == "ok", r.text[:200])

    r = client.get(f"{PREFIX}/profile")
    profile = r.json()
    ok("profile", r.status_code == 200 and bool(profile.get("skills")), f"skills={len(profile.get('skills') or [])}")

    r = client.get(f"{PREFIX}/profile/tracks/active")
    active = r.json()
    ok("active_track", r.status_code == 200 and active and active.get("id"), active.get("title", "")[:80])
    track_id = active["id"]

    r = client.post(f"{PREFIX}/plans/generate", json={"track_id": track_id})
    plan = r.json()
    ok("plan_generate", r.status_code == 200 and plan.get("id") and plan.get("checklist"), f"id={plan.get('id')}")

    r = client.get(f"{PREFIX}/plans/tasks", params={"plan_id": plan["id"]})
    ok("tasks_http", r.status_code == 200, f"status={r.status_code} body={r.text[:120]!r}")
    tasks = r.json()
    ok("tasks_list", isinstance(tasks, list) and len(tasks) > 0, f"n={len(tasks)}")

    if tasks:
        tid = tasks[0]["id"]
        r = client.patch(f"{PREFIX}/plans/tasks/{tid}", json={"status": "done"})
        ok("task_done", r.status_code == 200 and r.json().get("status") == "done")

    r = client.get(f"{PREFIX}/plans/progress/{track_id}")
    ok("progress", r.status_code == 200 and "percent" in r.json(), str(r.json()))

    vacancy_text = (
        "Ищем Python-разработчика для Telegram-ботов и FastAPI. "
        "Нужны: Python, aiogram, PostgreSQL, Docker, опыт с OpenAI/RAG будет плюсом. "
        "Удалёнка, проектная занятость."
    )
    r = client.post(
        f"{PREFIX}/market/import",
        json={
            "title": "Python Telegram / FastAPI (smoke)",
            "description": vacancy_text,
            "url": None,
        },
    )
    item = r.json()
    ok("market_manual", r.status_code == 200 and item.get("id"), item.get("title", ""))

    r = client.post(f"{PREFIX}/market/skill-gap/{item['id']}")
    gap = r.json()
    ok(
        "skill_gap",
        r.status_code == 200 and "match_score" in gap and gap.get("summary"),
        f"score={gap.get('match_score')}",
    )

    r = client.post(
        f"{PREFIX}/market/search",
        json={"source": "hh", "query": "Python", "limit": 2},
    )
    # hh may be empty until token — not a hard fail
    hh_items = r.json() if r.status_code == 200 else []
    print(f"[INFO] hh_search status={r.status_code} count={len(hh_items)} (ожидаемо 0 без токена)")

    r = client.post(
        f"{PREFIX}/coaching/checkins",
        json={
            "track_id": track_id,
            "mood": 4,
            "wins": "smoke test check-in",
            "blockers": "ждём hh moderation",
        },
    )
    ok("checkin", r.status_code == 200 and r.json().get("id"))

    r = client.post(
        f"{PREFIX}/coaching/turn",
        json={
            "track_id": track_id,
            "message": "Что сделать на этой неделе для первых заказов на Kwork?",
            "history": [],
        },
    )
    turn = r.json()
    ok("coaching", r.status_code == 200 and bool(turn.get("reply")), (turn.get("reply") or "")[:120])

    r = client.post(
        f"{PREFIX}/interview/start",
        json={"track_id": track_id, "role_title": "Python / AI разработчик"},
    )
    session = r.json()
    ok(
        "interview_start",
        r.status_code == 200 and session.get("id") and session.get("questions"),
        f"q={len(session.get('questions') or [])}",
    )
    answers = ["Stub answer with metrics: cut ERP report time 300→96 hours." for _ in session.get("questions") or []]
    r = client.post(f"{PREFIX}/interview/{session['id']}/answers", json={"answers": answers})
    fb = r.json()
    ok("interview_feedback", r.status_code == 200 and fb.get("feedback"), json.dumps(fb.get("feedback") or {}, ensure_ascii=False)[:120])

    print("\nALL SMOKE CHECKS PASSED (hh optional)")


if __name__ == "__main__":
    main()
