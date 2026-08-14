"""
Study Coach card metadata: difficulty + content locators.

A question can tag multiple lesson materials (book page, video, PDF, document).
Locators use stable ids (BookPage UUID or LessonMaterial UUID), not "page=3".
"""

from __future__ import annotations

from typing import Any

from django.utils.html import strip_tags

MAX_CATALOG = 80
MAX_PAGES = 60
MAX_EXCERPT = 180

CARD_DIFFICULTIES = ("easy", "intermediate", "hard")
SOURCE_KINDS = ("page", "video", "pdf", "document")
DIFFICULTY_ALIASES = {
    "medium": "intermediate",
    "med": "intermediate",
    "normal": "intermediate",
    "mid": "intermediate",
}

FALLBACK_EXPLANATION = "Review this idea in the lesson, then try a similar problem."


def normalize_difficulty(value: Any, *, default: str = "easy") -> str:
    text = str(value or "").strip().lower()
    text = DIFFICULTY_ALIASES.get(text, text)
    if text in CARD_DIFFICULTIES:
        return text
    return default if default in CARD_DIFFICULTIES else "easy"


def _page_excerpt(content: str) -> str:
    text = (content or "").strip()
    if not text:
        return ""
    if text.startswith("[") or text.startswith("{"):
        return ""
    return strip_tags(text).replace("\xa0", " ").strip()[:MAX_EXCERPT]


def _unique(ids: list[str]) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for raw in ids:
        key = str(raw or "").strip()
        if not key or key in seen:
            continue
        seen.add(key)
        out.append(key)
    return out


def stored_source(item: dict[str, Any]) -> dict[str, Any]:
    """Public locator stamped onto a card (never an invented URL)."""
    kind = str(item.get("kind") or "page")
    if kind not in SOURCE_KINDS:
        kind = "page"
    out: dict[str, Any] = {
        "kind": kind,
        "id": str(item["id"]),
        "material_id": str(item["material_id"]),
        "title": str(item.get("title") or ""),
    }
    if kind == "page" and item.get("page") is not None:
        out["page"] = int(item["page"])
    return out


def legacy_page_source(sources: list[dict[str, Any]]) -> dict[str, Any] | None:
    """First book page, for older clients that still read `source`."""
    for item in sources:
        if item.get("kind") == "page" and item.get("material_id") is not None:
            payload: dict[str, Any] = {
                "material_id": str(item["material_id"]),
                "title": str(item.get("title") or ""),
            }
            if item.get("page") is not None:
                payload["page"] = int(item["page"])
            return payload
    return None


def cited_source_ids(card: dict[str, Any]) -> list[str]:
    ids: list[str] = []
    raw_list = card.get("source_ids")
    if isinstance(raw_list, str) and raw_list.strip():
        ids.append(raw_list.strip())
    elif isinstance(raw_list, list):
        ids.extend(str(v).strip() for v in raw_list if str(v).strip())
    legacy = str(card.get("source_page_id") or "").strip()
    if legacy:
        ids.append(legacy)
    return _unique(ids)


def build_content_catalog(lesson) -> list[dict[str, Any]]:
    """Pages, videos, PDFs, and documents for this lesson — ids the model may cite."""
    from courses.models import BookPage, LessonMaterial

    catalog: list[dict[str, Any]] = []

    pages = (
        BookPage.objects.filter(book_material__lessons=lesson)
        .select_related("book_material")
        .order_by("book_material__order", "page_number")[:MAX_PAGES]
    )
    for page in pages:
        catalog.append(
            {
                "id": str(page.id),
                "kind": "page",
                "material_id": str(page.book_material_id),
                "page": int(page.page_number),
                "title": (page.title or "").strip() or f"Page {page.page_number}",
                "excerpt": _page_excerpt(page.content),
            }
        )
        if len(catalog) >= MAX_CATALOG:
            return catalog

    materials = (
        LessonMaterial.objects.filter(lessons=lesson)
        .order_by("order", "created_at")
    )
    for material in materials:
        if len(catalog) >= MAX_CATALOG:
            break
        mtype = (material.material_type or "").strip().lower()
        ext = (material.file_extension or "").strip().lower().lstrip(".")
        kind = None
        if mtype == "video":
            kind = "video"
        elif mtype == "pdf" or ext == "pdf":
            kind = "pdf"
        elif mtype == "document":
            kind = "document"
        if not kind:
            continue
        catalog.append(
            {
                "id": str(material.id),
                "kind": kind,
                "material_id": str(material.id),
                "title": (material.title or "").strip() or kind.title(),
                "excerpt": "",
            }
        )
    return catalog


def format_content_catalog_for_prompt(catalog: list[dict[str, Any]]) -> str:
    if not catalog:
        return ""
    lines = []
    for item in catalog:
        kind = item.get("kind") or "page"
        title = item.get("title") or kind
        line = f"- id={item['id']} | kind={kind} | title={title}"
        if kind == "page" and item.get("page") is not None:
            line += f" | page={item['page']}"
        excerpt = (item.get("excerpt") or "").strip()
        if excerpt:
            line += f" | excerpt={excerpt}"
        lines.append(line)
    return "\n".join(lines)


def resolve_catalog_item(
    raw_id: str, catalog: list[dict[str, Any]]
) -> dict[str, Any] | None:
    if not catalog:
        return None
    raw = str(raw_id or "").strip()
    if not raw:
        return None
    by_id = {str(item["id"]): item for item in catalog}
    matched = by_id.get(raw)
    if matched:
        return matched
    if raw.isdigit():
        hits = [
            item
            for item in catalog
            if (item.get("kind") or "page") == "page"
            and int(item.get("page") or 0) == int(raw)
        ]
        if len(hits) == 1:
            return hits[0]
    return None


def resolve_card_sources(
    card: dict[str, Any], catalog: list[dict[str, Any]]
) -> list[dict[str, Any]]:
    """Map model-cited catalog ids to stored locators. Drops invented ids."""
    if not catalog:
        return []
    cited = cited_source_ids(card)
    matched: list[dict[str, Any]] = []
    seen: set[str] = set()
    for raw in cited:
        item = resolve_catalog_item(raw, catalog)
        if not item:
            continue
        key = str(item["id"])
        if key in seen:
            continue
        seen.add(key)
        matched.append(stored_source(item))
    if matched:
        return matched
    if len(catalog) == 1 and not cited:
        return [stored_source(catalog[0])]
    return []


def attach_card_metadata(
    cards: list[dict[str, Any]],
    catalog: list[dict[str, Any]],
    *,
    default_difficulty: str = "easy",
) -> list[dict[str, Any]]:
    """Stamp difficulty + sources; drop model-only source id fields."""
    attached: list[dict[str, Any]] = []
    for card in cards:
        item = dict(card)
        explanation = str(item.get("explanation") or "").strip()
        item["explanation"] = explanation or FALLBACK_EXPLANATION
        item["difficulty"] = normalize_difficulty(
            item.get("difficulty"), default=default_difficulty
        )
        sources = resolve_card_sources(item, catalog)
        item.pop("source_page_id", None)
        item.pop("source_ids", None)
        item["sources"] = sources
        legacy = legacy_page_source(sources)
        if legacy:
            item["source"] = legacy
        else:
            item.pop("source", None)
        attached.append(item)
    return attached


def normalize_stored_card(card: dict[str, Any]) -> dict[str, Any]:
    """Shape older saved cards to the current metadata contract."""
    if not isinstance(card, dict):
        return card
    item = dict(card)
    item["difficulty"] = normalize_difficulty(item.get("difficulty"))
    sources = item.get("sources")
    if not isinstance(sources, list):
        sources = []
    cleaned: list[dict[str, Any]] = []
    for raw in sources:
        if isinstance(raw, dict) and raw.get("id") and raw.get("material_id"):
            cleaned.append(stored_source(raw))
    if not cleaned and isinstance(item.get("source"), dict):
        legacy = item["source"]
        material_id = str(legacy.get("material_id") or "").strip()
        if material_id:
            page = legacy.get("page")
            cleaned.append(
                stored_source(
                    {
                        "kind": "page" if page is not None else "document",
                        "id": str(legacy.get("id") or material_id),
                        "material_id": material_id,
                        "page": page,
                        "title": legacy.get("title") or "",
                    }
                )
            )
    item["sources"] = cleaned
    legacy = legacy_page_source(cleaned)
    if legacy:
        item["source"] = legacy
    elif "source" in item and not cleaned:
        item.pop("source", None)
    return item


def normalize_stored_cards(cards: Any) -> list[dict[str, Any]]:
    if not isinstance(cards, list):
        return []
    return [normalize_stored_card(card) for card in cards]


# Names used by older tests / imports.
def build_page_catalog(lesson) -> list[dict[str, Any]]:
    return [item for item in build_content_catalog(lesson) if item.get("kind") == "page"]


def format_page_catalog_for_prompt(catalog: list[dict[str, Any]]) -> str:
    return format_content_catalog_for_prompt(catalog)


def resolve_card_source(
    card: dict[str, Any], catalog: list[dict[str, Any]]
) -> dict[str, Any] | None:
    sources = resolve_card_sources(card, catalog)
    return legacy_page_source(sources) or (sources[0] if sources else None)


def attach_card_sources(
    cards: list[dict[str, Any]], catalog: list[dict[str, Any]]
) -> list[dict[str, Any]]:
    return attach_card_metadata(cards, catalog)
