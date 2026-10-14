"""Split market queries into terms and expand Russian word forms (cases)."""

from __future__ import annotations

import logging
import re
from functools import lru_cache

from app.domain.models import MarketItem

logger = logging.getLogger(__name__)

_TERM_RE = re.compile(r"[A-Za-zА-Яа-яЁё0-9_+#.-]{2,}")
_CYR_RE = re.compile(r"[А-Яа-яЁё]")


def split_query_terms(query: str) -> list[str]:
    """«RAG база знаний» → ['RAG', 'база', 'знаний']."""
    if not (query or "").strip():
        return []
    seen: set[str] = set()
    out: list[str] = []
    for m in _TERM_RE.finditer(query):
        term = m.group(0)
        key = term.lower()
        if key in seen:
            continue
        seen.add(key)
        out.append(term)
    return out


@lru_cache(maxsize=1)
def _morph():
    from pymorphy3 import MorphAnalyzer

    return MorphAnalyzer()


def _heuristic_ru_forms(word: str) -> set[str]:
    """Fallback endings when pymorphy is unavailable."""
    w = word.lower().replace("ё", "е")
    forms = {w, word.lower()}
    # peel common endings to guess a stem
    stem = w
    for suf in (
        "ями",
        "ами",
        "ого",
        "ему",
        "ому",
        "ыми",
        "ими",
        "иях",
        "иям",
        "ией",
        "ием",
        "ах",
        "ях",
        "ов",
        "ев",
        "ей",
        "ом",
        "ем",
        "ам",
        "ям",
        "ую",
        "юю",
        "ая",
        "яя",
        "ое",
        "ее",
        "ие",
        "ые",
        "ий",
        "ый",
        "ой",
        "ия",
        "ию",
        "ии",
        "ью",
        "ья",
        "ье",
        "а",
        "я",
        "у",
        "ю",
        "ы",
        "и",
        "е",
        "о",
    ):
        if len(w) > len(suf) + 2 and w.endswith(suf):
            stem = w[: -len(suf)]
            break
    if len(stem) < 3:
        stem = w
    for end in (
        "",
        "а",
        "я",
        "у",
        "ю",
        "ы",
        "и",
        "е",
        "о",
        "ой",
        "ей",
        "ом",
        "ем",
        "ам",
        "ям",
        "ами",
        "ями",
        "ах",
        "ях",
        "ов",
        "ев",
        "ия",
        "ии",
        "ию",
        "ий",
        "ие",
        "ью",
        "ье",
        "ья",
    ):
        forms.add(stem + end)
    return {f for f in forms if len(f) >= 2}


def lemma_of(word: str) -> str:
    raw = (word or "").strip()
    if not raw:
        return ""
    w = raw.lower().replace("ё", "е")
    if not _CYR_RE.search(w):
        return w
    try:
        return _morph().parse(w)[0].normal_form.replace("ё", "е")
    except Exception:  # noqa: BLE001
        return w


def remote_keywords_for_term(term: str) -> list[str]:
    """Keywords to hit remote search with: original + lemma."""
    t = (term or "").strip()
    if not t:
        return []
    out: list[str] = [t]
    lemma = lemma_of(t)
    if lemma and lemma.lower() != t.lower():
        out.append(lemma)
    return out


def expand_word_forms(word: str, *, max_forms: int = 48) -> list[str]:
    """программа → программа, программу, программы, …"""
    raw = (word or "").strip()
    if not raw:
        return []
    w = raw.lower().replace("ё", "е")
    if not _CYR_RE.search(w):
        return [w]

    forms: set[str] = {w, raw.lower()}
    try:
        morph = _morph()
        parses = morph.parse(w)
        if not parses:
            return sorted(_heuristic_ru_forms(w))
        for p in parses[:3]:
            forms.add(p.normal_form.replace("ё", "е"))
            for form in p.lexeme:
                forms.add(form.word.lower().replace("ё", "е"))
                if len(forms) >= max_forms:
                    break
            if len(forms) >= max_forms:
                break
    except Exception as exc:  # noqa: BLE001
        logger.debug("pymorphy expand failed for %r: %s", word, exc)
        forms |= _heuristic_ru_forms(w)

    # Prefer longer forms first so substring checks hit full words sooner
    return sorted(forms, key=lambda s: (-len(s), s))[:max_forms]


def text_matches_term(text: str, term: str) -> bool:
    blob = (text or "").lower().replace("ё", "е")
    if not blob or not term:
        return False
    for form in expand_word_forms(term):
        if form and form in blob:
            return True
    return False


def text_matches_query(text: str, query: str) -> bool:
    """OR across terms: hit if any term (any form) appears."""
    terms = split_query_terms(query)
    if not terms:
        return True
    return any(text_matches_term(text, t) for t in terms)


def item_matches_query(item: MarketItem, query: str) -> bool:
    blob = f"{item.title or ''} {item.description or ''}"
    return text_matches_query(blob, query)


def filter_items_by_query(items: list[MarketItem], query: str) -> list[MarketItem]:
    if not (query or "").strip():
        return items
    return [i for i in items if item_matches_query(i, query)]


def card_matches_query(card: dict, query: str) -> bool:
    blob = f"{card.get('title') or ''} {card.get('description') or ''}"
    return text_matches_query(blob, query)


def dedupe_items(items: list[MarketItem]) -> list[MarketItem]:
    seen: set[str] = set()
    out: list[MarketItem] = []
    for item in items:
        key = f"{item.source.value}:{item.external_id}"
        if key in seen:
            continue
        seen.add(key)
        out.append(item)
    return out


def dedupe_cards(cards: list[dict], *, id_key: str = "project_id") -> list[dict]:
    seen: set[str] = set()
    out: list[dict] = []
    for card in cards:
        pid = str(card.get(id_key) or "")
        if not pid or pid in seen:
            continue
        seen.add(pid)
        out.append(card)
    return out
