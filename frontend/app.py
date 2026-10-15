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
        detail = resp.text
        try:
            payload = resp.json()
            if isinstance(payload, dict) and payload.get("detail"):
                detail = str(payload["detail"])
        except Exception:  # noqa: BLE001
            pass
        st.error(detail)
        return None
    return resp.json()


_GAP_IMPORTANCE_RU = {
    "critical": "критично",
    "important": "важно",
    "nice-to-have": "желательно",
    "nice_to_have": "желательно",
}

_TRACK_TYPE_RU = {
    "employment": "найм",
    "side_income": "доп. доход",
    "first_freelance_order": "первые заказы",
    "custom": "своя цель",
}

_TASK_STATUS_RU = {
    "todo": "к выполнению",
    "in_progress": "в работе",
    "done": "готово",
    "skipped": "пропущено",
}

_ENV_RU = {
    "production": "продакшен",
    "development": "разработка",
    "staging": "стейджинг",
    "test": "тест",
}


def _fmt_dt(value) -> str:
    if not value:
        return "не задано"
    text = str(value).replace("T", " ").replace("Z", "")
    if "." in text:
        text = text.split(".", 1)[0]
    return text[:19]


def _yes_no(flag: bool) -> str:
    return "да" if flag else "нет"


def render_health(data: dict | None) -> None:
    if not data:
        st.error("Не удалось получить статус API")
        return
    status = data.get("status") or "—"
    status_ru = {
        "ok": "всё в порядке",
        "degraded": "частично недоступно",
        "error": "ошибка",
    }.get(str(status), str(status))
    st.markdown(f"**Состояние:** {status_ru}")
    st.markdown(f"**Приложение:** {data.get('app') or '—'}")
    env = str(data.get("env") or "")
    st.markdown(f"**Окружение:** {_ENV_RU.get(env, env or '—')}")

    mongo = data.get("mongo") or {}
    if mongo.get("ok"):
        st.success("MongoDB: подключена")
    else:
        st.error(f"MongoDB: нет связи — {mongo.get('error') or 'неизвестно'}")

    kb = data.get("knowledge_base") or {}
    if kb.get("enabled"):
        if kb.get("ok"):
            st.success(f"База знаний: включена ({kb.get('detail') or 'ok'})")
        else:
            st.warning(f"База знаний: сбой — {kb.get('detail') or 'ошибка'}")
    else:
        st.info("База знаний: выключена")

    if data.get("llm_configured"):
        st.success("LLM: ключ настроен")
    else:
        st.warning("LLM: ключ не задан (работает StubLLM)")


def render_track(track: dict | None) -> None:
    if not track:
        st.info("Активного трека нет")
        return
    type_code = track.get("type") or ""
    type_ru = _TRACK_TYPE_RU.get(type_code, type_code or "—")
    status = track.get("status") or ""
    status_ru = {
        "active": "активен",
        "paused": "на паузе",
        "done": "завершён",
        "archived": "в архиве",
    }.get(str(status), str(status) or "—")
    mark = "🟢 активный" if track.get("is_active") else "⚪ неактивный"

    st.markdown(f"**{track.get('title') or 'Без названия'}** · {mark}")
    st.markdown(f"**Тип цели:** {type_ru}")
    st.markdown(f"**Статус:** {status_ru}")
    st.markdown(f"**Часов в неделю:** {track.get('weekly_hours_budget') or '—'}")
    deadline = track.get("deadline")
    st.markdown(f"**Дедлайн:** {_fmt_dt(deadline) if deadline else 'не задан'}")
    st.markdown(f"**Создан:** {_fmt_dt(track.get('created_at'))}")
    st.markdown(f"**Активирован:** {_fmt_dt(track.get('activated_at'))}")

    kpis = track.get("kpis") or []
    if kpis:
        st.markdown("**KPI:**")
        for kpi in kpis:
            st.markdown(f"- {kpi}")


def render_plan(plan: dict | None) -> None:
    if not plan:
        st.info("Плана пока нет")
        return
    summary = (plan.get("summary") or "").strip()
    if summary:
        st.markdown(summary)

    phases = plan.get("phases") or []
    if phases:
        st.subheader("Этапы")
        for i, phase in enumerate(phases, 1):
            name = phase.get("name") or f"Этап {i}"
            horizon = phase.get("horizon") or ""
            head = f"**{i}. {name}**"
            if horizon:
                head += f" · горизонт: {horizon}"
            st.markdown(head)
            goals = phase.get("goals") or []
            if goals:
                st.markdown("Цели:")
                for g in goals:
                    st.markdown(f"- {g}")
            skills = phase.get("skills") or []
            if skills:
                st.markdown("Навыки: " + ", ".join(skills))

    skills = plan.get("skills_to_develop") or []
    if skills:
        st.subheader("Навыки к развитию")
        for s in skills:
            st.markdown(f"- {s}")

    resources = plan.get("resources") or []
    if resources:
        st.subheader("Ресурсы")
        for r in resources:
            title = r.get("title") or "ресурс"
            kind = r.get("kind") or ""
            hours = r.get("estimated_hours")
            url = r.get("url")
            line = f"- **{title}**"
            extras = []
            if kind:
                extras.append(kind)
            if hours is not None:
                extras.append(f"~{hours} ч")
            if extras:
                line += f" ({', '.join(extras)})"
            if url:
                line += f" — {url}"
            st.markdown(line)

    checklist = plan.get("checklist") or []
    if checklist:
        st.subheader("Чек-лист")
        for item in checklist:
            st.markdown(f"- {item}")

    st.caption(f"Сгенерирован: {_fmt_dt(plan.get('generated_at'))}")


def render_interview_feedback(feedback: dict | None) -> None:
    if not feedback:
        st.info("Оценки пока нет")
        return
    score = feedback.get("score")
    if score is not None:
        st.metric("Оценка", f"{score} из 100")
    summary = (feedback.get("summary") or "").strip()
    if summary:
        st.subheader("Краткий вывод")
        st.write(summary)
    strengths = feedback.get("strengths") or []
    if strengths:
        st.subheader("Сильные стороны")
        for line in strengths:
            st.markdown(f"- {line}")
    improvements = feedback.get("improvements") or []
    if improvements:
        st.subheader("Что улучшить")
        for line in improvements:
            st.markdown(f"- {line}")


def render_skill_gap_report(report: dict) -> None:
    score = report.get("match_score")
    if score is not None:
        st.metric("Совпадение с заказом", f"{score} из 100")

    summary = (report.get("summary") or "").strip()
    if summary:
        st.subheader("Краткий вывод")
        st.write(summary)

    strengths = report.get("strengths") or []
    if strengths:
        st.subheader("Сильные стороны")
        for line in strengths:
            st.markdown(f"- {line}")

    gaps = report.get("gaps") or []
    if gaps:
        st.subheader("Чего не хватает")
        for gap in gaps:
            if isinstance(gap, dict):
                skill = gap.get("skill") or "—"
                importance = _GAP_IMPORTANCE_RU.get(
                    str(gap.get("importance") or "").lower(),
                    gap.get("importance") or "",
                )
                note = (gap.get("note") or "").strip()
                head = f"**{skill}**"
                if importance:
                    head += f" · {importance}"
                st.markdown(f"- {head}" + (f" — {note}" if note else ""))
            else:
                st.markdown(f"- {gap}")

    steps = report.get("roadmap_steps") or []
    if steps:
        st.subheader("Что сделать дальше")
        for i, step in enumerate(steps, 1):
            st.markdown(f"{i}. {step}")


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
    st.subheader("Состояние системы")
    render_health(api("GET", "/health"))

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
    render_track(active)

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
            render_plan(plans[0])
            tasks = api("GET", f"{PREFIX}/plans/tasks", params={"plan_id": plans[0]["id"]}) or []
            st.subheader("Задачи")
            for t in tasks:
                cols = st.columns([4, 1])
                status = t.get("status") or ""
                status_ru = _TASK_STATUS_RU.get(str(status), str(status))
                is_done = status == "done"
                cols[0].markdown(f"**{t['title']}** — {status_ru}")
                if cols[1].button(
                    "Готово",
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
    source_labels = {
        "hh": "hh.ru",
        "kwork": "Kwork",
        "flru": "FL.ru",
        "yandex_uslugi": "Яндекс.Услуги",
        "telegram": "Telegram канал",
        "manual": "Ручной импорт",
    }
    source = st.selectbox(
        "Источник",
        list(source_labels.keys()),
        format_func=lambda c: source_labels.get(c, c),
    )
    if source == "hh":
        st.caption(
            "hh.ru: поиск по API + локальный фильтр (слово/склонение должно "
            "быть в названии или сниппете). Нужен `HH_ACCESS_TOKEN`."
        )
    elif source == "yandex_uslugi":
        st.caption(
            "Яндекс.Услуги тянется через Playwright + `YANDEX_STORAGE_STATE`. "
            "Если пусто — обнови сессию: Freelance `deploy/yandex_login_interactive.py`."
        )
    elif source == "flru":
        st.caption(
            "FL.ru пока httpx+cookies (часто ломается SmartCaptcha с VPS). "
            "Нужен свежий `FLRU_STORAGE_STATE`."
        )
    elif source == "telegram":
        st.caption(
            "Поиск идёт по сохранённому списку каналов (публичное превью `t.me/s/…`; "
            "с Telethon — приватные + больше истории). "
            "Логин: `python scripts/telegram_login.py --list`."
        )
        saved = api("GET", f"{PREFIX}/market/telegram/channels") or {}
        saved_channels = saved.get("channels") or []
        # Sync editor BEFORE widget exists (Streamlit forbids mutating widget keys after).
        if "tg_channels_pending" in st.session_state:
            st.session_state["tg_channels_editor"] = st.session_state.pop(
                "tg_channels_pending"
            )
        elif "tg_channels_editor" not in st.session_state:
            st.session_state["tg_channels_editor"] = "\n".join(saved_channels)
        channels_text = st.text_area(
            "Список каналов (по одному в строке: @name, t.me/name или -100…)",
            height=120,
            key="tg_channels_editor",
        )
        if st.button("Сохранить список каналов"):
            lines = [ln.strip() for ln in channels_text.splitlines() if ln.strip()]
            out = api(
                "PUT",
                f"{PREFIX}/market/telegram/channels",
                json={"channels": lines},
            )
            if out is not None:
                st.session_state["tg_channels_pending"] = "\n".join(
                    out.get("channels") or []
                )
                st.session_state["tg_channels_flash"] = (
                    f"Сохранено каналов: {len(out.get('channels') or [])}"
                )
                st.rerun()
        flash = st.session_state.pop("tg_channels_flash", None)
        if flash:
            st.success(flash)
    if source == "manual":
        title = st.text_input("Заголовок")
        description = st.text_area("Текст вакансии/заказа")
        url = st.text_input("URL (опционально)", "")
        if st.button("Импорт") and title and description:
            item = api(
                "POST",
                f"{PREFIX}/market/import",
                json={"title": title, "description": description, "url": url or None},
            )
            st.session_state["market_item"] = item
    else:
        query_label = (
            "Фильтр по словам (пусто = свежие посты из всех каналов списка)"
            if source == "telegram"
            else "Поиск (слова по отдельности + склонения; пусто = свежая лента)"
        )
        query_placeholder = (
            "RAG база знаний"
            if source in ("telegram", "kwork", "yandex_uslugi", "flru", "hh")
            else "Telegram"
        )
        if source != "manual":
            st.caption(
                "Каждое слово ищется отдельно (OR), с учётом склонений "
                "(программа/программу/программы). Дубликаты схлопываются."
            )
        query = st.text_input(
            query_label,
            value="",
            placeholder=query_placeholder,
        )
        search_limit = 30 if source == "telegram" else 10
        if st.button("Искать", type="primary"):
            with st.spinner(f"Ищу на {source_labels.get(source, source)}…"):
                items = api(
                    "POST",
                    f"{PREFIX}/market/search",
                    json={
                        "source": source,
                        "query": query.strip(),
                        "limit": search_limit,
                    },
                )
            if items is None:
                st.session_state["market_items"] = []
            else:
                st.session_state["market_items"] = items
                st.session_state.pop("market_item", None)
                if items:
                    st.success(f"Найдено: {len(items)}")
                    errs = (items[0].get("raw") or {}).get("channel_errors") or []
                    for err in errs:
                        st.warning(err)
                else:
                    st.warning(
                        "Ничего не найдено. Очисти поиск или смени слова "
                        "(фильтр по словам в title/description)."
                    )
        items = st.session_state.get("market_items") or []
        if items:
            st.subheader(f"Результаты ({len(items)})")
        for item in items:
            ch = (item.get("raw") or {}).get("channel_label") or ""
            label = item.get("title") or item.get("id")
            btn = f"[{ch}] {label}" if ch and ch not in str(label) else str(label)
            if st.button(f"Выбрать: {btn}", key=f"pick_{item['id']}"):
                st.session_state["market_item"] = item
                st.rerun()
    item = st.session_state.get("market_item")
    if item:
        st.divider()
        st.write(f"**Выбрано:** {item.get('title')}")
        if item.get("url"):
            st.caption(item["url"])
        if item.get("description"):
            st.write(item["description"][:800])
        if st.button("Разобрать совпадение с профилем"):
            with st.spinner("Анализ…"):
                report = api("POST", f"{PREFIX}/market/skill-gap/{item['id']}")
            if report:
                st.session_state["skill_gap_report"] = report
                st.session_state["skill_gap_item_id"] = item["id"]
        report = st.session_state.get("skill_gap_report")
        if report and st.session_state.get("skill_gap_item_id") == item["id"]:
            st.divider()
            st.subheader("Разбор совпадения")
            render_skill_gap_report(report)

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
            wins = st.text_input("Что получилось")
            blockers = st.text_input("Что мешает")
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
                st.success("Check-in сохранён")

elif page == "Интервью":
    active = api("GET", f"{PREFIX}/profile/tracks/active")
    if not active:
        st.warning("Нужен активный трек")
    else:
        if "interview" not in st.session_state:
            restored = api(
                "GET",
                f"{PREFIX}/interview/latest",
                params={"track_id": active["id"]},
            )
            if restored:
                st.session_state["interview"] = restored
                st.session_state["_interview_saved_answers"] = list(
                    restored.get("answers") or []
                )

        session = st.session_state.get("interview")
        default_role = (
            (session or {}).get("role_title")
            or "Python / AI разработчик"
        )
        role = st.text_input("Роль", default_role)
        col_start, col_hint = st.columns([1, 2])
        with col_start:
            start_clicked = st.button("Старт mock interview")
        with col_hint:
            if session and not session.get("feedback"):
                st.caption("Черновик подтягивается с сервера после обновления страницы.")
        if start_clicked:
            new_session = api(
                "POST",
                f"{PREFIX}/interview/start",
                json={"track_id": active["id"], "role_title": role},
            )
            if new_session:
                sid = new_session["id"]
                for k in list(st.session_state.keys()):
                    if str(k).startswith("ans_"):
                        del st.session_state[k]
                st.session_state["interview"] = new_session
                st.session_state["_interview_saved_answers"] = list(
                    new_session.get("answers") or []
                )
                for i in range(len(new_session.get("questions") or [])):
                    saved = (new_session.get("answers") or [])
                    st.session_state[f"ans_{sid}_{i}"] = (
                        saved[i] if i < len(saved) else ""
                    )
                st.rerun()

        session = st.session_state.get("interview")
        if session:
            sid = session["id"]
            questions = session.get("questions") or []
            saved_answers = list(session.get("answers") or [])
            for i, q in enumerate(questions):
                key = f"ans_{sid}_{i}"
                if key not in st.session_state:
                    st.session_state[key] = (
                        saved_answers[i] if i < len(saved_answers) else ""
                    )
                st.write(f"**Q{i+1}.** {q['question']}")
                st.text_area(f"Ответ {i+1}", key=key, height=120)

            current = [
                st.session_state.get(f"ans_{sid}_{i}", "")
                for i in range(len(questions))
            ]
            prev = st.session_state.get("_interview_saved_answers")
            if not session.get("feedback") and prev != current:
                drafted = api(
                    "PATCH",
                    f"{PREFIX}/interview/{sid}/draft",
                    json={"answers": current},
                )
                if drafted:
                    st.session_state["interview"] = drafted
                    st.session_state["_interview_saved_answers"] = current
                    st.toast("Ответы сохранены", icon="💾")

            if session.get("feedback"):
                st.subheader("Оценка")
                render_interview_feedback(session["feedback"])
            elif st.button("Отправить на оценку"):
                result = api(
                    "POST",
                    f"{PREFIX}/interview/{sid}/answers",
                    json={"answers": current},
                )
                if result:
                    st.session_state["interview"] = result
                    st.session_state["_interview_saved_answers"] = list(
                        result.get("answers") or current
                    )
                    st.rerun()
