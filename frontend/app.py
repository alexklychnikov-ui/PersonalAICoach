import os

import httpx
import streamlit as st

API = os.getenv("API_BASE_URL", "http://127.0.0.1:8000").rstrip("/")
PREFIX = os.getenv("API_PREFIX", "/api/v1")


def api(method: str, path: str, **kwargs):
    url = f"{API}{path}"
    with httpx.Client(timeout=120) as client:
        resp = client.request(method, url, **kwargs)
    if resp.status_code >= 400:
        st.error(f"{method} {path}: {resp.status_code} {resp.text}")
        return None
    return resp.json()


st.set_page_config(page_title="Персональный ИИ-коуч", layout="wide")
st.title("Персональный ИИ-коуч")

page = st.sidebar.radio(
    "Раздел",
    [
        "Онбординг",
        "План",
        "Рынок / Skill-gap",
        "Коучинг",
        "Интервью",
        "Статус",
    ],
)

if page == "Статус":
    data = api("GET", "/health")
    st.json(data or {})

elif page == "Онбординг":
    defaults = api("GET", f"{PREFIX}/profile/defaults") or {}
    seed_profile = defaults.get("profile") or {}
    seed_track = defaults.get("track") or {}
    labels = defaults.get("track_type_labels") or {}
    type_codes = ["employment", "side_income", "first_freelance_order", "custom"]

    col_a, col_b = st.columns([1, 1])
    with col_a:
        if st.button("Заполнить из LightRAG-профиля", help="Профиль + трек «первые заказы»"):
            seeded = api("POST", f"{PREFIX}/profile/seed", params={"force_profile": True})
            if seeded:
                st.success("Профиль и трек засеяны (без дублей по type+title)")
                st.rerun()
    with col_b:
        st.caption("Несколько треков можно хранить; активен только один.")

    profile = api("GET", f"{PREFIX}/profile") or {}
    tracks = api("GET", f"{PREFIX}/profile/tracks") or []
    active = api("GET", f"{PREFIX}/profile/tracks/active") or {}

    st.subheader("Мои треки")
    if not tracks:
        st.info("Треков пока нет — сохрани форму ниже или нажми «Заполнить из LightRAG-профиля».")
    for t in tracks:
        mark = "🟢 активный" if t.get("is_active") else "⚪"
        c1, c2 = st.columns([4, 1])
        type_label = labels.get(t.get("type"), t.get("type"))
        c1.markdown(
            f"**{t.get('title')}** · {type_label} · {mark}\n\n"
            f"KPI: {'; '.join(t.get('kpis') or [])}"
        )
        if not t.get("is_active") and c2.button("Сделать активным", key=f"act_{t['id']}"):
            api("POST", f"{PREFIX}/profile/tracks/{t['id']}/activate")
            st.rerun()

    # Prefill empty profile fields from LightRAG seed
    def _val(key: str, fallback: str = "") -> str:
        cur = (profile.get(key) or "").strip()
        return cur if cur else str(seed_profile.get(key) or fallback)

    skills_default = ", ".join(profile.get("skills") or seed_profile.get("skills") or [])
    growth_src = profile.get("growth_areas") or seed_profile.get("growth_areas") or []
    growth_default = ", ".join(growth_src)
    weekly_default = float(
        profile.get("weekly_hours_available")
        or seed_profile.get("weekly_hours_available")
        or seed_track.get("weekly_hours_budget")
        or 15
    )
    default_type = (
        active.get("type")
        if active
        else seed_track.get("type") or "first_freelance_order"
    )
    type_index = type_codes.index(default_type) if default_type in type_codes else 2

    st.subheader("Профиль и цель")
    with st.form("profile_form"):
        current_position = st.text_input("Текущая должность", _val("current_position"))
        desired_role = st.text_input("Желаемая роль", _val("desired_role"))
        skills = st.text_area("Навыки (через запятую)", skills_default)
        growth = st.text_area("Зоны роста (через запятую)", growth_default)
        resume_summary = st.text_area("Кратко о себе", _val("resume_summary"))
        weekly = st.number_input(
            "Часов в неделю",
            min_value=1.0,
            max_value=80.0,
            value=weekly_default,
        )
        track_type = st.selectbox(
            "Тип цели",
            type_codes,
            index=type_index,
            format_func=lambda c: labels.get(c, c),
        )
        track_title = st.text_input(
            "Название цели",
            (active.get("title") if active else None)
            or seed_track.get("title")
            or "Первые заказы на фрилансе",
        )
        kpis_default = "; ".join(
            (active.get("kpis") if active else None) or seed_track.get("kpis") or []
        )
        kpis = st.text_input("KPI через ;", kpis_default)
        submitted = st.form_submit_button("Сохранить профиль и трек (без дублей)")
    if submitted:
        body = {
            "id": "singleton",
            "current_position": current_position,
            "desired_role": desired_role,
            "skills": [s.strip() for s in skills.split(",") if s.strip()],
            "growth_areas": [s.strip() for s in growth.split(",") if s.strip()],
            "resume_summary": resume_summary,
            "locale": "ru",
            "weekly_hours_available": weekly,
        }
        api("PUT", f"{PREFIX}/profile", json=body)
        track = api(
            "POST",
            f"{PREFIX}/profile/tracks/upsert",
            json={
                "type": track_type,
                "title": track_title,
                "weekly_hours_budget": weekly,
                "kpis": [k.strip() for k in kpis.split(";") if k.strip()],
                "activate": True,
            },
        )
        if track:
            st.success("Сохранено: профиль обновлён, трек upsert + активирован")
            st.rerun()

    st.subheader("Активный трек")
    st.json(active or {})

elif page == "План":
    active = api("GET", f"{PREFIX}/profile/tracks/active")
    if not active:
        st.warning("Сначала создай активный трек в онбординге")
    else:
        if st.button("Сгенерировать план"):
            plan = api("POST", f"{PREFIX}/plans/generate", json={"track_id": active["id"]})
            st.session_state["last_plan"] = plan
        plans = api("GET", f"{PREFIX}/plans", params={"track_id": active["id"]}) or []
        if plans:
            st.subheader("Последний план")
            st.write(plans[0].get("summary"))
            st.json(plans[0])
            tasks = api("GET", f"{PREFIX}/plans/tasks", params={"plan_id": plans[0]["id"]}) or []
            st.subheader("Задачи")
            for t in tasks:
                cols = st.columns([4, 1])
                is_done = t.get("status") == "done"
                cols[0].write(f"{t['title']} — `{t['status']}`")
                if cols[1].button(
                    "Done",
                    key=f"done_{t['id']}",
                    disabled=is_done,
                    help="Уже выполнено" if is_done else "Отметить выполненным",
                ):
                    api(
                        "PATCH",
                        f"{PREFIX}/plans/tasks/{t['id']}",
                        json={"status": "done"},
                    )
                    st.rerun()
            prog = api("GET", f"{PREFIX}/plans/progress/{active['id']}")
            st.metric("Прогресс %", (prog or {}).get("percent", 0))

elif page == "Рынок / Skill-gap":
    source = st.selectbox("Источник", ["hh", "kwork", "manual"])
    if source == "manual":
        title = st.text_input("Заголовок")
        description = st.text_area("Текст вакансии/заказа")
        if st.button("Импорт") and title and description:
            item = api(
                "POST",
                f"{PREFIX}/market/import",
                json={"title": title, "description": description},
            )
            st.session_state["market_item"] = item
    else:
        query = st.text_input("Поиск", "Python Telegram FastAPI")
        if st.button("Искать"):
            items = api(
                "POST",
                f"{PREFIX}/market/search",
                json={"source": source, "query": query, "limit": 5},
            )
            st.session_state["market_items"] = items or []
        for item in st.session_state.get("market_items") or []:
            if st.button(f"Выбрать: {item['title']}", key=item["id"]):
                st.session_state["market_item"] = item
    item = st.session_state.get("market_item")
    if item:
        st.write(item.get("title"))
        if st.button("Skill-gap анализ"):
            report = api("POST", f"{PREFIX}/market/skill-gap/{item['id']}")
            st.json(report or {})

elif page == "Коучинг":
    active = api("GET", f"{PREFIX}/profile/tracks/active")
    if not active:
        st.warning("Нужен активный трек")
    else:
        msg = st.chat_input("Сообщение коучу")
        if "chat" not in st.session_state:
            st.session_state.chat = []
        for m in st.session_state.chat:
            with st.chat_message(m["role"]):
                st.write(m["content"])
        if msg:
            history = [
                {"role": m["role"], "content": m["content"]} for m in st.session_state.chat[-8:]
            ]
            turn = api(
                "POST",
                f"{PREFIX}/coaching/turn",
                json={"track_id": active["id"], "message": msg, "history": history},
            )
            st.session_state.chat.append({"role": "user", "content": msg})
            if turn:
                note = " [KB]" if turn.get("knowledge_context_used") else ""
                st.session_state.chat.append(
                    {"role": "assistant", "content": turn.get("reply", "") + note}
                )
            st.rerun()
        st.subheader("Check-in")
        with st.form("checkin"):
            mood = st.slider("Настроение", 1, 5, 3)
            wins = st.text_input("Wins")
            blockers = st.text_input("Blockers")
            if st.form_submit_button("Сохранить"):
                api(
                    "POST",
                    f"{PREFIX}/coaching/checkins",
                    json={
                        "track_id": active["id"],
                        "mood": mood,
                        "wins": wins,
                        "blockers": blockers,
                    },
                )
                st.success("OK")

elif page == "Интервью":
    active = api("GET", f"{PREFIX}/profile/tracks/active")
    role = st.text_input("Роль", "Python / AI разработчик")
    if active and st.button("Старт mock interview"):
        session = api(
            "POST",
            f"{PREFIX}/interview/start",
            json={"track_id": active["id"], "role_title": role},
        )
        st.session_state["interview"] = session
    session = st.session_state.get("interview")
    if session:
        answers = []
        for i, q in enumerate(session.get("questions") or []):
            st.write(f"**Q{i+1}.** {q['question']}")
            answers.append(st.text_area(f"Ответ {i+1}", key=f"ans_{session['id']}_{i}"))
        if st.button("Отправить на оценку"):
            result = api(
                "POST",
                f"{PREFIX}/interview/{session['id']}/answers",
                json={"answers": answers},
            )
            st.json(result or {})
