"""Tests for the server's tool-input validation layer.

These exercise the FastMCP/pydantic bounds attached to tool parameters; they go
through ``mcp.call_tool`` (not the bare function) because that is where the
validation runs. No network access is needed — bad input is rejected first.
"""

from __future__ import annotations

import pytest
from mcp.server.fastmcp.exceptions import ToolError

from localnewsmatters_mcp import server


@pytest.mark.parametrize(
    "tool, args",
    [
        ("search_articles", {"per_page": 999}),  # above the 1-100 cap
        ("search_articles", {"page": 0}),  # page is 1-based
        ("search_articles", {"author_id": 0}),  # ids must be >= 1
        ("get_article", {"article_id": 0}),
        ("get_photo", {"photo_id": -5}),
        ("get_category", {"category_id": 0}),
        ("get_article_by_slug", {"slug": ""}),  # slug must be non-empty
    ],
)
async def test_invalid_arguments_are_rejected(tool, args):
    with pytest.raises(ToolError):
        await server.mcp.call_tool(tool, args)


async def test_all_expected_tools_are_registered():
    names = {t.name for t in await server.mcp.list_tools()}
    assert {
        "search_articles",
        "list_recent_articles",
        "get_article",
        "get_article_by_slug",
        "search_photos",
        "get_photo",
        "get_article_photos",
        "list_categories",
        "get_category",
        "list_tags",
        "get_tag",
        "list_authors",
        "list_pages",
    } <= names
