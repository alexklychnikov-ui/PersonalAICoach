"""Record a demo walkthrough of the Streamlit dashboard → Docs/Videos."""

from __future__ import annotations

import asyncio
import shutil
import subprocess
from pathlib import Path

from playwright.async_api import Page, async_playwright

URL = "https://aicareercoach.alexklyvibe.ru/"
OUT_DIR = Path(__file__).resolve().parents[1] / "Docs" / "Videos"
VIEWPORT = {"width": 1440, "height": 900}


async def wait_ready(page: Page, *, settle_ms: int = 700) -> None:
    await page.wait_for_selector("text=Персональный ИИ-коуч", timeout=60000)
    for _ in range(100):
        if await page.locator('[data-testid="stStatusWidget"]').count() == 0:
            break
        await page.wait_for_timeout(200)
    await page.wait_for_timeout(settle_ms)


async def select_section(page: Page, label: str) -> None:
    sidebar = page.locator('[data-testid="stSidebar"]')
    await sidebar.get_by_text(label, exact=True).first.click()
    await wait_ready(page)


async def scroll_main(page: Page, *, steps: int = 8, pause_ms: int = 350) -> None:
    """Smooth-ish scroll of Streamlit main pane to the bottom, then back up a bit."""
    for i in range(steps):
        await page.evaluate(
            """(frac) => {
              const main =
                document.querySelector('[data-testid="stMain"]') ||
                document.querySelector('section.main') ||
                document.scrollingElement;
              if (!main) return;
              const max = Math.max(0, (main.scrollHeight || 0) - (main.clientHeight || 0));
              // also scroll window for unlocked pages
              const wmax = Math.max(
                0,
                document.documentElement.scrollHeight - window.innerHeight
              );
              const target = Math.floor(Math.max(max, wmax) * frac);
              if (main.scrollTo) main.scrollTo({ top: target, behavior: 'instant' });
              window.scrollTo({ top: target, behavior: 'instant' });
            }""",
            (i + 1) / steps,
        )
        await page.wait_for_timeout(pause_ms)
    await page.wait_for_timeout(500)


async def scroll_to_top(page: Page) -> None:
    await page.evaluate(
        """() => {
          const main =
            document.querySelector('[data-testid="stMain"]') ||
            document.querySelector('section.main');
          if (main && main.scrollTo) main.scrollTo({ top: 0 });
          window.scrollTo({ top: 0 });
        }"""
    )
    await page.wait_for_timeout(400)


async def click_button(page: Page, name: str, *, exact: bool = False) -> bool:
    btn = page.get_by_role("button", name=name, exact=exact)
    if await btn.count() == 0:
        print(f"  skip button: {name}")
        return False
    await btn.first.scroll_into_view_if_needed()
    await page.wait_for_timeout(250)
    await btn.first.click()
    return True


async def demo(page: Page) -> None:
    await page.goto(URL, wait_until="domcontentloaded")
    await wait_ready(page, settle_ms=1200)

    # 1) Онбординг — профиль с данными + скролл
    print("1 onboarding")
    await select_section(page, "Онбординг")
    await page.wait_for_timeout(800)
    await scroll_main(page, steps=10, pause_ms=400)
    await scroll_to_top(page)
    # Показать кнопку seed без применения (hover)
    seed = page.get_by_role("button", name="Заполнить из LightRAG-профиля")
    if await seed.count():
        await seed.first.hover()
        await page.wait_for_timeout(700)
    await scroll_main(page, steps=6, pause_ms=300)

    # 2) План
    print("2 plan")
    await select_section(page, "План")
    await page.wait_for_timeout(600)
    await scroll_main(page, steps=12, pause_ms=350)
    # опционально «Готово» на первой незаблокированной задаче
    done_btns = page.get_by_role("button", name="Готово")
    if await done_btns.count() > 0:
        first = done_btns.first
        if await first.is_enabled():
            await first.scroll_into_view_if_needed()
            await page.wait_for_timeout(300)
            # не кликаем — меняет state; просто покажем скроллом
    await scroll_to_top(page)

    # 3) Рынок Kwork + skill-gap
    print("3 market kwork")
    await select_section(page, "Рынок / Skill-gap")
    await page.get_by_label("Источник").click()
    await page.get_by_role("option", name="Kwork").click()
    await wait_ready(page)
    q = page.get_by_label(
        "Поиск (слова по отдельности + склонения; пусто = свежая лента)"
    )
    await q.click()
    await q.fill("Telegram бот")
    await page.wait_for_timeout(400)
    await click_button(page, "Искать")
    await wait_ready(page, settle_ms=2000)
    picks = page.locator('button:has-text("Выбрать:")')
    for _ in range(40):
        if await picks.count() > 0:
            break
        await page.wait_for_timeout(400)
    if await picks.count() > 0:
        await picks.first.scroll_into_view_if_needed()
        await page.wait_for_timeout(400)
        await picks.first.click()
        await wait_ready(page, settle_ms=1000)
        await scroll_main(page, steps=6, pause_ms=300)
        if await click_button(page, "Разобрать совпадение с профилем"):
            for _ in range(90):
                if await page.locator("text=Разбор совпадения").count():
                    break
                await page.wait_for_timeout(800)
            await wait_ready(page, settle_ms=800)
            await scroll_main(page, steps=10, pause_ms=350)

    # 4) Telegram каналы
    print("4 telegram")
    await scroll_to_top(page)
    await page.get_by_label("Источник").click()
    await page.get_by_role("option", name="Telegram канал").click()
    await wait_ready(page, settle_ms=800)
    await scroll_main(page, steps=4, pause_ms=300)
    await click_button(page, "Искать")
    await wait_ready(page, settle_ms=2500)
    await scroll_main(page, steps=10, pause_ms=300)

    # 5) hh.ru
    print("5 hh")
    await scroll_to_top(page)
    await page.get_by_label("Источник").click()
    await page.get_by_role("option", name="hh.ru").click()
    await wait_ready(page)
    q = page.get_by_label(
        "Поиск (слова по отдельности + склонения; пусто = свежая лента)"
    )
    await q.fill("python")
    await page.wait_for_timeout(300)
    await click_button(page, "Искать")
    await wait_ready(page, settle_ms=2000)
    await scroll_main(page, steps=8, pause_ms=300)

    # 6) Коучинг
    print("6 coaching")
    await select_section(page, "Коучинг")
    await page.wait_for_timeout(600)
    chat = page.get_by_placeholder("Сообщение коучу")
    await chat.click()
    await chat.fill(
        "Сфокусируй меня: 5 откликов и один кейс на этой неделе. С чего начать?"
    )
    await page.wait_for_timeout(500)
    await chat.press("Enter")
    for _ in range(60):
        if await page.locator('[data-testid="stChatMessage"]').count() >= 2:
            break
        await page.wait_for_timeout(800)
    await wait_ready(page, settle_ms=800)
    wins = page.get_by_label("Что получилось")
    blockers = page.get_by_label("Что мешает")
    if await wins.count():
        await wins.fill("Задеплоил коуча, HH+Kwork работают")
    if await blockers.count():
        await blockers.fill("Мало вечернего времени на отклики")
    await page.wait_for_timeout(400)
    if await click_button(page, "Сохранить"):
        await wait_ready(page, settle_ms=1000)
    await scroll_main(page, steps=4, pause_ms=300)

    # 7) Интервью — скролл вопросов (оценка уже может быть)
    print("7 interview")
    await select_section(page, "Интервью")
    await page.wait_for_timeout(600)
    await scroll_main(page, steps=14, pause_ms=300)
    await scroll_to_top(page)
    await page.wait_for_timeout(500)

    # 8) Статус
    print("8 status")
    await select_section(page, "Статус")
    await page.wait_for_timeout(1200)
    await scroll_main(page, steps=3, pause_ms=400)
    await page.wait_for_timeout(1500)


def maybe_to_mp4(webm: Path) -> Path | None:
    ffmpeg = shutil.which("ffmpeg")
    if not ffmpeg:
        return None
    mp4 = webm.with_suffix(".mp4")
    cmd = [
        ffmpeg,
        "-y",
        "-i",
        str(webm),
        "-c:v",
        "libx264",
        "-pix_fmt",
        "yuv420p",
        "-movflags",
        "+faststart",
        str(mp4),
    ]
    try:
        subprocess.run(cmd, check=True, capture_output=True)
        return mp4
    except subprocess.CalledProcessError as exc:
        print("ffmpeg failed:", exc.stderr[-400:] if exc.stderr else exc)
        return None


async def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    # clean old temp videos in staging
    staging = OUT_DIR / "_pw_record"
    if staging.exists():
        shutil.rmtree(staging, ignore_errors=True)
    staging.mkdir(parents=True, exist_ok=True)

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(
            viewport=VIEWPORT,
            device_scale_factor=1.0,
            locale="ru-RU",
            record_video_dir=str(staging),
            record_video_size=VIEWPORT,
        )
        page = await context.new_page()
        page.set_default_timeout(90000)
        try:
            await demo(page)
        finally:
            await context.close()
            await browser.close()

    videos = sorted(staging.glob("*.webm"), key=lambda x: x.stat().st_mtime)
    if not videos:
        raise SystemExit("no video recorded")
    dest_webm = OUT_DIR / "dashboard_demo.webm"
    shutil.move(str(videos[0]), str(dest_webm))
    shutil.rmtree(staging, ignore_errors=True)
    print("webm:", dest_webm, dest_webm.stat().st_size, "bytes")

    mp4 = maybe_to_mp4(dest_webm)
    if mp4:
        print("mp4:", mp4, mp4.stat().st_size, "bytes")
    else:
        print("mp4: skipped (ffmpeg not found)")


if __name__ == "__main__":
    asyncio.run(main())
