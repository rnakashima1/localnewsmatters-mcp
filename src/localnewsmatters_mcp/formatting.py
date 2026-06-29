"""Markdown rendering for the normalized Local News Matters objects.

``wp_client`` returns compact, JSON-friendly dicts. These helpers turn those
dicts into readable Markdown so tools can offer a ``response_format="markdown"``
option in addition to the default JSON. Rendering is purely presentational and
operates on the already-normalized shapes — it never touches the network.
"""

from __future__ import annotations

from enum import Enum
from typing import Any, Callable


class ResponseFormat(str, Enum):
    """How a tool should serialize its result."""

    JSON = "json"
    MARKDOWN = "markdown"


def _day(value: Any) -> str:
    """Render the date portion (YYYY-MM-DD) of an ISO timestamp."""
    return str(value)[:10] if value else ""


def _lines(*parts: str | None) -> str:
    return "\n".join(p for p in parts if p)


# -- articles --------------------------------------------------------------


def _article_meta(a: dict[str, Any]) -> str:
    bits = [f"ID {a.get('id')}"]
    if _day(a.get("date")):
        bits.append(_day(a.get("date")))
    if a.get("author"):
        bits.append(f"by {a['author']}")
    return " · ".join(bits)


def _taxonomy_line(a: dict[str, Any]) -> str | None:
    parts = []
    if a.get("categories"):
        parts.append("Categories: " + ", ".join(a["categories"]))
    if a.get("tags"):
        parts.append("Tags: " + ", ".join(a["tags"]))
    return "  |  ".join(parts) or None


def _article_summary_md(a: dict[str, Any]) -> str:
    return _lines(
        f"### [{a.get('title') or 'Untitled'}]({a.get('url') or ''})",
        f"**{_article_meta(a)}**",
        a.get("excerpt"),
        _taxonomy_line(a),
    )


def _article_full_md(a: dict[str, Any]) -> str:
    return _lines(
        f"# {a.get('title') or 'Untitled'}",
        f"**{_article_meta(a)}**",
        f"**URL:** {a.get('url')}" if a.get("url") else None,
        _taxonomy_line(a),
        "",
        a.get("content") or a.get("excerpt") or "_(no body text)_",
    )


def _article_search_md(result: dict[str, Any]) -> str:
    items = result.get("results", [])
    header = (
        f"# Articles — {result.get('total', len(items))} match(es), "
        f"page {result.get('page', 1)} of {result.get('total_pages', 1)}"
    )
    if not items:
        return _lines(header, "", "_No articles found._")
    return _lines(header, "", "\n\n".join(_article_summary_md(a) for a in items))


# -- photos ----------------------------------------------------------------


def _photo_md(p: dict[str, Any]) -> str:
    dims = (
        f"{p['width']}×{p['height']}"
        if p.get("width") and p.get("height")
        else None
    )
    lines = [
        f"### {p.get('title') or 'Untitled photo'} (ID {p.get('id')})",
        p.get("caption"),
        f"**Alt text:** {p['alt_text']}" if p.get("alt_text") else None,
        f"**Source:** {p['source_url']}" if p.get("source_url") else None,
        f"**Dimensions:** {dims}" if dims else None,
    ]
    sizes = p.get("sizes")
    if sizes:
        lines.append("**Available sizes:** " + ", ".join(sorted(sizes)))
    return _lines(*lines)


def _photo_search_md(result: dict[str, Any]) -> str:
    items = result.get("results", [])
    header = (
        f"# Photos — {result.get('total', len(items))} match(es), "
        f"page {result.get('page', 1)} of {result.get('total_pages', 1)}"
    )
    if not items:
        return _lines(header, "", "_No photos found._")
    return _lines(header, "", "\n\n".join(_photo_md(p) for p in items))


def _article_photos_md(result: dict[str, Any]) -> str:
    photos = result.get("photos", [])
    header = f"# Photos for article {result.get('article_id')}"
    if not photos:
        return _lines(header, "", "_No photos attached._")
    return _lines(header, "", "\n\n".join(_photo_md(p) for p in photos))


# -- taxonomy / authors / pages -------------------------------------------


def _term_list_md(title: str) -> Callable[[list[dict[str, Any]]], str]:
    def render(terms: list[dict[str, Any]]) -> str:
        if not terms:
            return _lines(f"# {title}", "", "_None found._")
        rows = [
            f"- **{t.get('name')}** (ID {t.get('id')}, {t.get('count', 0)} article(s))"
            for t in terms
        ]
        return _lines(f"# {title}", "", *rows)

    return render


def _term_detail_md(label: str) -> Callable[[dict[str, Any]], str]:
    def render(t: dict[str, Any]) -> str:
        lines = [
            f"# {label}: {t.get('name')}",
            f"**ID** {t.get('id')} · **Slug** {t.get('slug')} · "
            f"**{t.get('count', 0)} article(s)**",
        ]
        if t.get("parent"):
            lines.append(f"**Parent ID:** {t['parent']}")
        if t.get("url"):
            lines.append(f"**URL:** {t['url']}")
        if t.get("description"):
            lines += ["", t["description"]]
        return _lines(*lines)

    return render


def _authors_md(authors: list[dict[str, Any]]) -> str:
    if not authors:
        return _lines("# Authors", "", "_None found._")
    rows = [f"- **{a.get('name')}** (ID {a.get('id')}) — {a.get('url')}" for a in authors]
    return _lines("# Authors", "", *rows)


def _pages_md(pages: list[dict[str, Any]]) -> str:
    if not pages:
        return _lines("# Site pages", "", "_None found._")
    rows = [f"- **[{p.get('title')}]({p.get('url')})** (ID {p.get('id')})" for p in pages]
    return _lines("# Site pages", "", *rows)


# -- dispatch --------------------------------------------------------------

_RENDERERS: dict[str, Callable[[Any], str]] = {
    "article_search": _article_search_md,
    "article": _article_full_md,
    "photo_search": _photo_search_md,
    "photo": _photo_md,
    "article_photos": _article_photos_md,
    "categories": _term_list_md("Categories"),
    "tags": _term_list_md("Tags"),
    "category": _term_detail_md("Category"),
    "tag": _term_detail_md("Tag"),
    "authors": _authors_md,
    "pages": _pages_md,
}


def to_markdown(data: Any, kind: str) -> str:
    """Render a normalized ``data`` object of the given ``kind`` as Markdown.

    Error payloads (``{"error": ...}``) are rendered uniformly; unknown kinds
    fall back to a plain string representation.
    """
    if isinstance(data, dict) and "error" in data:
        return f"**Error:** {data['error']}"
    renderer = _RENDERERS.get(kind)
    return renderer(data) if renderer else str(data)
