"""Telegram market: Telethon user-session (private + deep history) with t.me/s fallback."""

from __future__ import annotations

import asyncio
import html as html_lib
import logging
import re
from pathlib import Path
from urllib.parse import urlparse

import httpx

from app.adapters.query_expand import text_matches_query
from app.config import Settings
from app.domain.models import MarketItem, MarketSource

logger = logging.getLogger(__name__)

_DATA_POST_RE = re.compile(r'data-post="([^"/]+)/(\d+)"')
_TEXT_RE = re.compile(
    r'class="tgme_widget_message_text[^"]*"[^>]*>(.*?)</div>',
    re.IGNORECASE | re.DOTALL,
)
_TAG_RE = re.compile(r"<[^>]+>")
_WS_RE = re.compile(r"\s+")
_CHANNEL_FROM_URL_RE = re.compile(
    r"(?:https?://)?(?:t\.me|telegram\.me)/(?:s/)?([A-Za-z0-9_]{4,})",
    re.IGNORECASE,
)
_PEER_ID_RE = re.compile(r"^-?\d{6,}$")
_CLIENT_LOCK = asyncio.Lock()


def html_to_text(fragment: str) -> str:
    text = fragment.replace("<br>", "\n").replace("<br/>", "\n").replace("<br />", "\n")
    text = re.sub(r"</p\s*>", "\n", text, flags=re.IGNORECASE)
    text = _TAG_RE.sub(" ", text)
    text = html_lib.unescape(text)
    return _WS_RE.sub(" ", text).strip()


def normalize_channel_ref(raw: str) -> str | None:
    """Normalize t.me/@/id ref → username or peer id string."""
    part = (raw or "").strip()
    if not part or part.startswith("#"):
        return None
    m = _CHANNEL_FROM_URL_RE.search(part)
    if m:
        return m.group(1)
    part = part.lstrip("@")
    if part.startswith("http"):
        parsed = urlparse(part)
        part = parsed.path.strip("/").removeprefix("s/")
    if _PEER_ID_RE.fullmatch(part) or re.fullmatch(r"[A-Za-z0-9_]{4,}", part):
        return part
    return None


def normalize_channel_list(items: list[str]) -> list[str]:
    out: list[str] = []
    seen: set[str] = set()
    for raw in items:
        for chunk in re.split(r"[,;\n]+", raw):
            ch = normalize_channel_ref(chunk)
            if not ch:
                continue
            key = ch.lower()
            if key in seen:
                continue
            seen.add(key)
            out.append(ch)
    return out


def channel_label(channel: str) -> str:
    if _PEER_ID_RE.fullmatch(channel):
        return channel
    return f"@{channel}"


def parse_channel_query(query: str) -> tuple[str | None, str]:
    """Return (channel_username|peer_id|None, keyword_filter)."""
    raw = (query or "").strip()
    if not raw:
        return None, ""

    m = _CHANNEL_FROM_URL_RE.search(raw)
    if m:
        channel = m.group(1)
        rest = (raw[: m.start()] + raw[m.end() :]).strip()
        rest = rest.lstrip("| ").strip()
        return channel, rest

    token = raw.split(None, 1)
    head = token[0].lstrip("@")
    if _PEER_ID_RE.fullmatch(head) or re.fullmatch(r"[A-Za-z0-9_]{4,}", head):
        return head, (token[1] if len(token) > 1 else "").strip()
    return None, raw


def parse_telegram_preview(html: str) -> list[dict[str, str]]:
    items: list[dict[str, str]] = []
    seen: set[str] = set()
    for m in _DATA_POST_RE.finditer(html):
        channel, msg_id = m.group(1), m.group(2)
        external_id = f"{channel}/{msg_id}"
        if external_id in seen:
            continue
        seen.add(external_id)
        window = html[m.end() : m.end() + 12_000]
        tm = _TEXT_RE.search(window)
        if not tm:
            continue
        text = html_to_text(tm.group(1))
        if not text:
            continue
        title = text[:140] + ("…" if len(text) > 140 else "")
        items.append(
            {
                "external_id": external_id,
                "channel": channel,
                "msg_id": msg_id,
                "title": title,
                "description": text,
                "url": f"https://t.me/{channel}/{msg_id}",
            }
        )
    return items


def _filter_keywords(cards: list[dict[str, str]], keywords: str) -> list[dict[str, str]]:
    if not keywords:
        return cards
    return [
        c
        for c in cards
        if text_matches_query(f"{c['title']} {c['description']}", keywords)
    ]


def _card_to_item(card: dict[str, str], *, via: str) -> MarketItem:
    ch = card.get("channel") or card.get("source_ref") or ""
    label = channel_label(ch)
    raw = {
        "channel": ch,
        "channel_label": label,
        "source_ref": card.get("source_ref") or ch,
        "msg_id": card["msg_id"],
        "via": via,
    }
    title = card["title"]
    if not title.startswith("["):
        title = f"[{label}] {title}"
    return MarketItem(
        source=MarketSource.TELEGRAM,
        external_id=card["external_id"],
        title=title,
        description=card["description"],
        url=card["url"],
        raw=raw,
    )


class TelegramMarketSource:
    name = "telegram"

    def __init__(self, settings: Settings) -> None:
        self._settings = settings

    def _telethon_ready(self) -> bool:
        if not (
            self._settings.telegram_api_id and self._settings.telegram_api_hash
        ):
            return False
        if self._settings.telegram_session.strip():
            return True
        path = self._settings.telegram_session_path.strip()
        return bool(path and Path(path).is_file())

    def _load_session_string(self) -> str:
        path = self._settings.telegram_session_path.strip()
        if path:
            p = Path(path)
            if not p.is_file():
                raise RuntimeError(
                    f"Telegram: TELEGRAM_SESSION_PATH не найден: {path}"
                )
            return p.read_text(encoding="utf-8").strip()
        return self._settings.telegram_session.strip()

    def _default_channels(self) -> list[str]:
        return normalize_channel_list(
            re.split(r"[,;\s]+", self._settings.telegram_channels.strip())
            if self._settings.telegram_channels.strip()
            else []
        )

    def _resolve_peer(self, channel: str):
        if _PEER_ID_RE.fullmatch(channel):
            return int(channel)
        return channel

    async def _fetch_preview(self, channel: str) -> list[dict[str, str]]:
        if _PEER_ID_RE.fullmatch(channel):
            raise RuntimeError(
                f"Telegram: peer id {channel} доступен только через Telethon "
                "(нужны TELEGRAM_API_ID/HASH + session)."
            )
        url = f"https://t.me/s/{channel}"
        async with httpx.AsyncClient(timeout=30, follow_redirects=True) as client:
            resp = await client.get(
                url,
                headers={
                    "User-Agent": (
                        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                        "AppleWebKit/537.36 (KHTML, like Gecko) "
                        "Chrome/124.0.0.0 Safari/537.36"
                    ),
                    "Accept-Language": "ru,en;q=0.8",
                },
            )
        if resp.status_code == 404:
            raise RuntimeError(
                f"Telegram: канал/группа @{channel} не найдена или приватная "
                f"(нужен публичный username, превью https://t.me/s/{channel})."
            )
        resp.raise_for_status()
        cards = parse_telegram_preview(resp.text)
        if not cards and "tgme_page_title" in resp.text:
            raise RuntimeError(
                f"Telegram: @{channel} недоступен для публичного превью "
                "(приват / нет username / invite-only). Подключи Telethon-сессию."
            )
        return cards

    async def _fetch_telethon(
        self, channel: str, *, limit: int
    ) -> list[dict[str, str]]:
        from telethon import TelegramClient
        from telethon.sessions import StringSession

        session = self._load_session_string()
        client = TelegramClient(
            StringSession(session),
            self._settings.telegram_api_id,
            self._settings.telegram_api_hash,
        )
        async with _CLIENT_LOCK:
            await client.connect()
            try:
                if not await client.is_user_authorized():
                    raise RuntimeError(
                        "Telegram: session не авторизована. "
                        "Перелогинься: python scripts/telegram_login.py"
                    )
                entity = await client.get_entity(self._resolve_peer(channel))
                uname = getattr(entity, "username", None)
                channel_key = uname or str(getattr(entity, "id", channel))
                cards: list[dict[str, str]] = []
                async for msg in client.iter_messages(entity, limit=limit):
                    text = (msg.message or "").strip()
                    if not text:
                        continue
                    msg_id = str(msg.id)
                    title = text[:140] + ("…" if len(text) > 140 else "")
                    if uname:
                        url = f"https://t.me/{uname}/{msg_id}"
                    else:
                        # private: t.me/c/<internal>/<id>
                        peer_id = getattr(entity, "id", None)
                        if peer_id is not None and int(peer_id) < 0:
                            internal = str(abs(int(peer_id)))
                            if internal.startswith("100"):
                                internal = internal[3:]
                            url = f"https://t.me/c/{internal}/{msg_id}"
                        else:
                            url = f"tg://openmessage?chat_id={channel_key}&message_id={msg_id}"
                    cards.append(
                        {
                            "external_id": f"{channel_key}/{msg_id}",
                            "channel": str(channel_key),
                            "msg_id": msg_id,
                            "title": title,
                            "description": text,
                            "url": url,
                        }
                    )
                return cards
            finally:
                await client.disconnect()

    async def _fetch_channel(
        self, channel: str, *, history_limit: int
    ) -> tuple[list[dict[str, str]], str]:
        if self._telethon_ready():
            try:
                cards = await self._fetch_telethon(channel, limit=history_limit)
                return cards, "telethon"
            except RuntimeError:
                raise
            except Exception as exc:  # noqa: BLE001
                logger.warning(
                    "telethon fetch failed for %s (%s); trying public preview",
                    channel,
                    exc,
                )
                if _PEER_ID_RE.fullmatch(channel):
                    raise RuntimeError(
                        f"Telegram Telethon не смог прочитать {channel}: {exc}"
                    ) from exc
        cards = await self._fetch_preview(channel)
        return cards, "preview"

    async def search(self, query: str, *, limit: int = 10) -> list[MarketItem]:
        channel, keywords = parse_channel_query(query)
        channels = [channel] if channel else self._default_channels()
        return await self.search_channels(channels, keywords, limit=limit)

    async def search_channels(
        self,
        channels: list[str],
        keywords: str = "",
        *,
        limit: int = 10,
    ) -> list[MarketItem]:
        if not self._settings.telegram_market_enabled:
            return []

        channels = normalize_channel_list(channels)
        if not channels:
            raise RuntimeError(
                "Telegram: список каналов пуст. Добавь каналы в UI "
                "(или TELEGRAM_CHANNELS в .env)."
            )

        history = max(limit, int(self._settings.telegram_history_limit or 80))
        batches: list[list[dict[str, str]]] = []
        errors: list[str] = []
        via_last = "preview"
        for ch in channels:
            try:
                batch, via_last = await self._fetch_channel(
                    ch, history_limit=history
                )
                if via_last == "preview":
                    batch = list(reversed(batch))
                for c in batch:
                    c["source_ref"] = ch
                batch = _filter_keywords(batch, keywords)
                if batch:
                    batches.append(batch)
            except Exception as exc:  # noqa: BLE001
                logger.warning("telegram channel %s failed: %s", ch, exc)
                errors.append(f"{channel_label(ch)}: {exc}")

        if not batches and errors:
            raise RuntimeError(
                "Telegram: ни один канал не отдался.\n" + "\n".join(errors)
            )

        # Round-robin across channels so one noisy feed doesn't own the limit.
        cards: list[dict[str, str]] = []
        indexes = [0] * len(batches)
        while len(cards) < limit and any(
            indexes[i] < len(batches[i]) for i in range(len(batches))
        ):
            for i, batch in enumerate(batches):
                if indexes[i] >= len(batch):
                    continue
                cards.append(batch[indexes[i]])
                indexes[i] += 1
                if len(cards) >= limit:
                    break

        items = [_card_to_item(c, via=via_last) for c in cards]
        if errors and items:
            items[0].raw["channel_errors"] = errors
        return items

    async def get_item(self, external_id: str) -> MarketItem | None:
        if not self._settings.telegram_market_enabled:
            return None
        if "/" not in external_id:
            return None
        channel, _, msg_id = external_id.partition("/")
        if not channel or not msg_id.isdigit():
            return None

        if self._telethon_ready():
            try:
                from telethon import TelegramClient
                from telethon.sessions import StringSession

                session = self._load_session_string()
                client = TelegramClient(
                    StringSession(session),
                    self._settings.telegram_api_id,
                    self._settings.telegram_api_hash,
                )
                async with _CLIENT_LOCK:
                    await client.connect()
                    try:
                        entity = await client.get_entity(self._resolve_peer(channel))
                        msg = await client.get_messages(entity, ids=int(msg_id))
                        if not msg or not (msg.message or "").strip():
                            return None
                        text = msg.message.strip()
                        username = getattr(entity, "username", None) or channel
                        url = (
                            f"https://t.me/{entity.username}/{msg_id}"
                            if getattr(entity, "username", None)
                            else f"https://t.me/{channel}/{msg_id}"
                        )
                        return _card_to_item(
                            {
                                "external_id": f"{username}/{msg_id}",
                                "channel": str(username),
                                "msg_id": msg_id,
                                "title": text[:140]
                                + ("…" if len(text) > 140 else ""),
                                "description": text,
                                "url": url,
                            },
                            via="telethon",
                        )
                    finally:
                        await client.disconnect()
            except Exception as exc:  # noqa: BLE001
                logger.warning("telegram get_item telethon failed: %s", exc)

        try:
            cards, via = await self._fetch_channel(channel, history_limit=40)
        except Exception as exc:  # noqa: BLE001
            logger.warning("telegram get_item failed: %s", exc)
            return None
        for c in cards:
            if c["external_id"] == external_id or c["msg_id"] == msg_id:
                return _card_to_item(c, via=via)
        return MarketItem(
            source=MarketSource.TELEGRAM,
            external_id=external_id,
            title=f"@{channel} #{msg_id}",
            description="",
            url=f"https://t.me/{channel}/{msg_id}",
            raw={"channel": channel, "msg_id": msg_id, "stale": True},
        )
