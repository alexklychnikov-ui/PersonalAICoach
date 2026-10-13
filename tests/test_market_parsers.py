from app.adapters.flru_market import parse_flru_listing
from app.adapters.kwork_market import parse_kwork_listing
from app.adapters.market_urls import (
    extract_flru_project_id,
    extract_kwork_project_id,
    extract_yandex_order_id,
)
from app.adapters.telegram_market import (
    normalize_channel_list,
    parse_channel_query,
    parse_telegram_preview,
)
from app.adapters.yandex_uslugi_market import parse_yandex_listing


def test_kwork_listing_ids():
    html = """
    <div class="want-card">
      <a class="wants-card__header-title" href="/projects/123456/view">Bot for Telegram</a>
      <span>до 15 000 ₽</span>
    </div>
    """
    cards = parse_kwork_listing(html)
    assert cards[0]["project_id"] == "123456"
    assert "Bot" in cards[0]["title"]


def test_flru_listing_skips_vacancy():
    vac = "\u0432\u0430\u043a\u0430\u043d\u0441\u0438\u044f"  # вакансия
    cards = parse_flru_listing(
        '<a href="/projects/55555/x.html">Need parser script</a>'
        + ("x" * 50)
        + f'<a href="/projects/66666/y.html">{vac} Python</a>'
    )
    ids = {c["project_id"] for c in cards}
    assert "55555" in ids
    assert "66666" not in ids


def test_yandex_listing_uuid():
    oid = "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee"
    html = f'<a href="/order/{oid}">Сделать бота</a><span>до 5 000 ₽</span>'
    cards = parse_yandex_listing(html)
    assert cards[0]["project_id"] == oid
    assert "бота" in cards[0]["title"].lower()


def test_url_extractors():
    assert extract_kwork_project_id("https://kwork.ru/projects/42/view") == "42"
    assert extract_flru_project_id("https://www.fl.ru/projects/12345/foo.html") == "12345"
    assert (
        extract_yandex_order_id(
            "https://uslugi.yandex.ru/order/aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee"
        )
        == "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee"
    )


def test_telegram_preview_posts():
    html = """
    <div class="tgme_widget_message" data-post="Koteyka_Freelancer/7970">
      <div class="tgme_widget_message_text js-message_text">Нужен <b>бот</b> для Telegram&#33;</div>
    </div>
    <div class="tgme_widget_message" data-post="Koteyka_Freelancer/7971">
      <div class="tgme_widget_message_text js-message_text">Вакансия администратора</div>
    </div>
    """
    cards = parse_telegram_preview(html)
    assert cards[0]["external_id"] == "Koteyka_Freelancer/7970"
    assert "бот" in cards[0]["description"]
    assert cards[0]["url"].endswith("/7970")
    assert "!" in cards[0]["description"]


def test_telegram_channel_query():
    assert parse_channel_query("t.me/Koteyka_Freelancer") == (
        "Koteyka_Freelancer",
        "",
    )
    assert parse_channel_query("@Koteyka_Freelancer python bot") == (
        "Koteyka_Freelancer",
        "python bot",
    )
    assert parse_channel_query("https://t.me/s/Koteyka_Freelancer | бот")[0] == (
        "Koteyka_Freelancer"
    )
    assert parse_channel_query("-1001451211985 вакансия") == (
        "-1001451211985",
        "вакансия",
    )


def test_normalize_channel_list():
    assert normalize_channel_list(
        [
            "t.me/Koteyka_Freelancer",
            "@Koteyka_Freelancer",
            "https://t.me/s/OtherChannel",
            "-1001451211985",
            "trash!!!",
        ]
    ) == ["Koteyka_Freelancer", "OtherChannel", "-1001451211985"]
