"""Unit tests for the Markdown rendering helpers."""

from __future__ import annotations

from localnewsmatters_mcp.formatting import ResponseFormat, to_markdown


def _article(**overrides):
    article = {
        "id": 101,
        "title": "City Council Approves Budget",
        "url": "https://localnewsmatters.org/a/101",
        "date": "2024-01-02T08:00:00",
        "author": "Jane Reporter",
        "excerpt": "A short summary.",
        "categories": ["Government"],
        "tags": ["Budget"],
        "content": "First paragraph.\nSecond paragraph.",
    }
    article.update(overrides)
    return article


def test_response_format_enum_accepts_strings():
    assert ResponseFormat("markdown") is ResponseFormat.MARKDOWN
    assert ResponseFormat("json") is ResponseFormat.JSON


def test_full_article_markdown_includes_heading_and_body():
    md = to_markdown(_article(), "article")
    assert md.startswith("# City Council Approves Budget")
    assert "by Jane Reporter" in md
    assert "Second paragraph." in md
    assert "Categories: Government" in md


def test_article_search_markdown_lists_summaries_with_paging():
    result = {"results": [_article()], "total": 42, "total_pages": 5, "page": 2}
    md = to_markdown(result, "article_search")
    assert "42 match(es), page 2 of 5" in md
    assert "### [City Council Approves Budget](https://localnewsmatters.org/a/101)" in md


def test_empty_search_renders_friendly_message():
    md = to_markdown({"results": [], "total": 0, "total_pages": 0, "page": 1}, "article_search")
    assert "_No articles found._" in md


def test_photo_markdown_lists_sizes_and_dimensions():
    photo = {
        "id": 555,
        "title": "Hero shot",
        "caption": "The city hall.",
        "alt_text": "city hall",
        "source_url": "https://x/hero.jpg",
        "width": 1200,
        "height": 800,
        "sizes": {"thumbnail": {}, "large": {}},
    }
    md = to_markdown(photo, "photo")
    assert "1200×800" in md
    assert "large, thumbnail" in md  # sorted


def test_category_detail_markdown():
    md = to_markdown(
        {"id": 5, "name": "Government", "slug": "gov", "count": 12, "description": "City hall news."},
        "category",
    )
    assert md.startswith("# Category: Government")
    assert "12 article(s)" in md
    assert "City hall news." in md


def test_pages_markdown_links():
    md = to_markdown(
        [{"id": 2, "title": "About Us", "url": "https://x/about/"}],
        "pages",
    )
    assert "[About Us](https://x/about/)" in md


def test_error_payload_renders_uniformly():
    assert to_markdown({"error": "boom"}, "article") == "**Error:** boom"
