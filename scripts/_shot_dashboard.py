"""Full-page Streamlit dashboard screenshots → Docs/Screenshots."""

from __future__ import annotations

import asyncio
from pathlib import Path

from playwright.async_api import Page, async_playwright

URL = "https://aicareercoach.alexklyvibe.ru/"
OUT = Path(__file__).resolve().parents[1] / "Docs" / "Screenshots"


async def unlock_streamlit_scroll(page: Page) -> None:
    await page.evaluate(
        """() => {
          const sel = [
            '[data-testid="stAppViewContainer"]',
            '[data-testid="stApp"]',
            '[data-testid="stMain"]',
            'section.main',
            '[data-testid="stSidebar"]',
            '.stApp',
          ];
          for (const s of sel) {
            for (const el of document.querySelectorAll(s)) {
              el.style.setProperty('overflow', 'visible', 'important');
              el.style.setProperty('height', 'auto', 'important');
              el.style.setProperty('max-height', 'none', 'important');
            }
          }
          document.documentElement.style.overflow = 'visible';
          document.body.style.overflow = 'visible';
          document.body.style.height = 'auto';
        }"""
    )


async def wait_ready(page: Page, *, settle_ms: int = 800) -> None:
    await page.wait_for_selector("text=Персональный ИИ-коуч", timeout=60000)
    for _ in range(80):
        running = await page.locator(
            '[data-testid="stStatusWidget"]'
        ).count()
        spinner = await page.locator("text=/Running|Please wait/i").count()
        if running == 0 and spinner == 0:
            break
        await page.wait_for_timeout(250)
    await page.wait_for_timeout(settle_ms)


async def select_section(page: Page, label: str) -> None:
    sidebar = page.locator('[data-testid="stSidebar"]')
    await sidebar.wait_for(state="visible", timeout=30000)
    await sidebar.get_by_text(label, exact=True).first.click()
    await wait_ready(page)


async def shot(page: Page, name: str) -> Path:
    await page.set_viewport_size({"width": 1440, "height": 1100})
    await page.wait_for_timeout(200)
    await unlock_streamlit_scroll(page)
    height = await page.evaluate(
        """() => {
          const nodes = [
            document.documentElement,
            document.body,
            document.querySelector('[data-testid="stAppViewContainer"]'),
            document.querySelector('[data-testid="stMain"]'),
            document.querySelector('section.main'),
            document.querySelector('[data-testid="stApp"]'),
          ].filter(Boolean);
          return Math.min(
            22000,
            Math.max(
              900,
              ...nodes.map((n) => n.scrollHeight || 0),
              ...nodes.map((n) => n.offsetHeight || 0)
            )
          );
        }"""
    )
    await page.set_viewport_size({"width": 1440, "height": int(height)})
    await unlock_streamlit_scroll(page)
    await page.wait_for_timeout(400)
    path = OUT / f"{name}.png"
    await page.screenshot(path=str(path), full_page=True, animations="disabled")
    print(f"  saved {path.name} ({path.stat().st_size} bytes, h={height})")
    return path


async def fill_market(page: Page) -> None:
    # Prefer Kwork — usually returns cards with test query
    src = page.locator('[data-testid="stSelectbox"]').filter(has_text="Источник")
    # Streamlit selectbox: click then option
    box = page.get_by_label("Источник")
    await box.click()
    await page.get_by_role("option", name="Kwork").click()
    await wait_ready(page, settle_ms=600)

    q = page.get_by_label(
        "Поиск (слова по отдельности + склонения; пусто = свежая лента)"
    )
    await q.fill("Telegram бот")
    await page.get_by_role("button", name="Искать").click()
    await wait_ready(page, settle_ms=1500)
    picks = page.locator('button:has-text("Выбрать:")')
    for _ in range(40):
        if await picks.count() > 0:
            break
        await page.wait_for_timeout(500)
    if await picks.count() > 0:
        await picks.first.click()
        await wait_ready(page, settle_ms=800)
        analyze = page.get_by_role("button", name="Разобрать совпадение с профилем")
        if await analyze.count():
            await analyze.click()
            for _ in range(90):
                if await page.locator("text=Разбор совпадения").count():
                    break
                await page.wait_for_timeout(1000)
            await wait_ready(page, settle_ms=1000)


async def fill_coaching(page: Page) -> None:
    chat = page.get_by_placeholder("Сообщение коучу")
    await chat.fill(
        "На этой неделе цели: 5 откликов на Kwork/Telegram и один кейс в портфолио. "
        "Что сделать в первую очередь?"
    )
    await chat.press("Enter")
    # wait assistant bubble
    for _ in range(60):
        msgs = await page.locator('[data-testid="stChatMessage"]').count()
        if msgs >= 2:
            break
        await page.wait_for_timeout(1000)
    await wait_ready(page, settle_ms=1000)

    # fill check-in form fields (not submit — keep visible filled)
    wins = page.get_by_label("Что получилось")
    blockers = page.get_by_label("Что мешает")
    if await wins.count():
        await wins.fill("Собрал MVP коуча, HH поиск заработал")
    if await blockers.count():
        await blockers.fill("Мало времени на отклики вечером")
    await page.wait_for_timeout(400)


async def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(
            viewport={"width": 1440, "height": 1100},
            device_scale_factor=1.25,
            locale="ru-RU",
        )
        page = await context.new_page()
        page.set_default_timeout(90000)
        await page.goto(URL, wait_until="domcontentloaded")
        await wait_ready(page)

        print("page: Онбординг")
        await select_section(page, "Онбординг")
        await shot(page, "01_onboarding")

        print("page: План")
        await select_section(page, "План")
        await shot(page, "02_plan")

        print("page: Рынок / Skill-gap")
        await select_section(page, "Рынок / Skill-gap")
        try:
            await fill_market(page)
        except Exception as exc:  # noqa: BLE001
            print(f"  market fill warn: {exc}")
        await shot(page, "03_market_skillgap")

        # Extra: Telegram channels list (saved config)
        try:
            box = page.get_by_label("Источник")
            await box.click()
            await page.get_by_role("option", name="Telegram канал").click()
            await wait_ready(page, settle_ms=800)
            await shot(page, "03b_market_telegram_channels")
        except Exception as exc:  # noqa: BLE001
            print(f"  telegram shot warn: {exc}")

        print("page: Коучинг")
        await select_section(page, "Коучинг")
        try:
            await fill_coaching(page)
        except Exception as exc:  # noqa: BLE001
            print(f"  coaching fill warn: {exc}")
        await shot(page, "04_coaching")

        print("page: Интервью")
        await select_section(page, "Интервью")
        await shot(page, "05_interview")

        print("page: Статус")
        await select_section(page, "Статус")
        await shot(page, "06_status")

        await browser.close()
    print("done", str(OUT))


if __name__ == "__main__":
    asyncio.run(main())
