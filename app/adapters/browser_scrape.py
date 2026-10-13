"""Headless Chromium scrape with Playwright storage_state (Yandex/FL SPAs)."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

# Prefer IPv4 on VPS (same trick as Freelance Auto-Responder).
_YANDEX_HOSTS = (
    "uslugi.yandex.ru",
    "passport.yandex.ru",
    "passport.yandex.com",
    "yandex.ru",
    "yastatic.net",
    "mc.yandex.ru",
)

YANDEX_LISTING_JS = """
() => {
  const UUID = /[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}/i;
  const seen = new Set();
  const cards = [];
  const links = [...document.querySelectorAll('a[href*="/order/"]')];
  for (const link of links) {
    const href = link.getAttribute('href') || '';
    const m = href.match(UUID);
    if (!m) continue;
    const id = m[0].toLowerCase();
    if (seen.has(id)) continue;
    seen.add(id);
    const card =
      link.closest('[data-id], [class*="order"], [class*="Order"], article, li, section')
      || link.parentElement;
    const titleEl =
      card?.querySelector('h1, h2, h3, [class*="title"], [class*="Title"]') || link;
    let title = (titleEl?.textContent || '').replace(/\\s+/g, ' ').trim();
    if (!title || title.length < 3) {
      title = (link.textContent || '').replace(/\\s+/g, ' ').trim();
    }
    const budgetEl = card?.querySelector(
      '[class*="price"], [class*="Price"], [class*="budget"], [class*="Budget"]'
    );
    const budget_text = budgetEl
      ? (budgetEl.textContent || '').replace(/\\s+/g, ' ').trim()
      : null;
    const descEl = card?.querySelector('[class*="description"], [class*="Description"], p');
    const description = descEl
      ? (descEl.textContent || '').replace(/\\s+/g, ' ').trim().slice(0, 2000)
      : '';
    const url = href.startsWith('http')
      ? href.split('?')[0]
      : 'https://uslugi.yandex.ru' + href.split('?')[0];
    cards.push({
      project_id: id,
      url,
      title: title.slice(0, 300),
      budget_text: budget_text || null,
      description,
    });
  }
  return cards;
}
"""


def _ipv4_resolver_rules() -> str:
    import socket

    parts: list[str] = []
    for host in _YANDEX_HOSTS:
        try:
            infos = socket.getaddrinfo(host, 443, socket.AF_INET, socket.SOCK_STREAM)
        except OSError:
            continue
        if infos:
            parts.append(f"MAP {host} {infos[0][4][0]}")
    return ",".join(parts)


def scrape_with_playwright(
    *,
    url: str,
    storage_state_path: str,
    evaluate_js: str,
    wait_ms: int = 4000,
    timeout_ms: int = 45000,
) -> list[dict[str, Any]]:
    """Sync Playwright: open URL with storage_state, evaluate JS, return cards."""
    try:
        from playwright.sync_api import sync_playwright
    except ImportError as exc:
        raise RuntimeError("playwright not installed") from exc

    path = Path(storage_state_path).expanduser()
    if not path.is_file():
        raise RuntimeError(f"storage_state missing: {path}")

    rules = _ipv4_resolver_rules()
    args = ["--disable-blink-features=AutomationControlled"]
    if rules:
        args.append(f"--host-resolver-rules={rules}")

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True, args=args)
        try:
            context = browser.new_context(
                storage_state=str(path),
                locale="ru-RU",
                user_agent=(
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/131.0.0.0 Safari/537.36"
                ),
            )
            page = context.new_page()
            page.goto(url, wait_until="domcontentloaded", timeout=timeout_ms)
            page.wait_for_timeout(wait_ms)
            final = page.url or ""
            if "passport.yandex" in final.lower():
                raise RuntimeError("yandex session expired — refresh YANDEX_STORAGE_STATE")
            raw = page.evaluate(evaluate_js)
            if not isinstance(raw, list) or not raw:
                # one more wait for late SPA cards
                page.wait_for_timeout(2500)
                raw = page.evaluate(evaluate_js)
            context.close()
        finally:
            browser.close()

    if not isinstance(raw, list):
        return []
    return [x for x in raw if isinstance(x, dict)]
