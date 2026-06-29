"""MCP server exposing Local News Matters articles and photos.

Run with stdio transport (the default for MCP clients like Claude Desktop / Claude
Code) via the ``localnewsmatters-mcp`` console script or ``python -m
localnewsmatters_mcp.server``.

Interface
---------
Tools (actions over the live catalog):
    * search_articles / get_article / get_article_by_slug
    * list_recent_articles
    * search_photos / get_photo / get_article_photos
    * list_categories / get_category / list_tags / get_tag / list_authors
    * list_pages

Most read tools accept ``response_format="json"`` (default) or ``"markdown"``.

Resources (read-only data addressable by URI template):
    * lnm://article/{id}        -- a single article as JSON
    * lnm://article/{id}/photos -- photos attached to an article
    * lnm://photo/{id}          -- a single photo's metadata + available sizes
    * lnm://recent/articles     -- the latest published articles
    * lnm://categories          -- the site's sections
"""

from __future__ import annotations

import json
from typing import Annotated, Any

from mcp.server.fastmcp import FastMCP
from pydantic import Field

from .formatting import ResponseFormat, to_markdown
from .wp_client import LocalNewsMattersClient, WordPressError

mcp = FastMCP(
    "localnewsmatters",
    instructions=(
        "Tools and resources for Local News Matters (localnewsmatters.org), a Bay "
        "Area nonprofit local-news publication. Use the tools to search and read "
        "the site's articles and photos. IDs returned by search tools can be fed "
        "into get_article / get_photo or used as resource URIs (lnm://article/{id}, "
        "lnm://photo/{id})."
    ),
)

# A single shared client for the life of the process.
_client = LocalNewsMattersClient()


# Validated parameter aliases. Bounds are enforced by the MCP/pydantic layer
# before the tool body runs, so callers get a clear error instead of a bad request.
Query = Annotated[str, Field(max_length=200)]
Page = Annotated[int, Field(ge=1)]
PerPage = Annotated[int, Field(ge=1, le=100)]
ItemId = Annotated[int, Field(ge=1)]
OptionalId = Annotated[int | None, Field(ge=1)]
Slug = Annotated[str, Field(min_length=1, max_length=200)]


def _dumps(data: Any) -> str:
    return json.dumps(data, indent=2, ensure_ascii=False)


async def _safe(coro) -> Any:
    """Await a client coroutine, converting API errors into a structured result."""
    try:
        return await coro
    except WordPressError as exc:
        return {"error": str(exc)}


def _render(data: Any, kind: str, response_format: ResponseFormat) -> str:
    """Serialize ``data`` as JSON (default) or Markdown per ``response_format``."""
    if response_format == ResponseFormat.MARKDOWN:
        return to_markdown(data, kind)
    return _dumps(data)


# ---------------------------------------------------------------------------
# Tools
# ---------------------------------------------------------------------------


@mcp.tool()
async def search_articles(
    query: Query = "",
    page: Page = 1,
    per_page: PerPage = 10,
    category_ids: list[int] | None = None,
    tag_ids: list[int] | None = None,
    author_id: OptionalId = None,
    after: str | None = None,
    before: str | None = None,
    response_format: ResponseFormat = ResponseFormat.JSON,
) -> str:
    """Search Local News Matters articles.

    Args:
        query: Full-text search terms. Leave empty to browse the most recent articles.
        page: 1-based page number for paging through results.
        per_page: Results per page (1-100).
        category_ids: Restrict to these category IDs (see list_categories).
        tag_ids: Restrict to these tag IDs (see list_tags).
        author_id: Restrict to a single author (see list_authors).
        after: ISO-8601 date; only articles published on/after it (e.g. "2024-01-01T00:00:00").
        before: ISO-8601 date; only articles published on/before it.
        response_format: "json" (default) for raw data, or "markdown" for readable text.

    Returns `results` (article summaries) plus `total`, `total_pages`, `page`.
    """
    result = await _safe(
        _client.search_articles(
            query=query or None,
            page=page,
            per_page=per_page,
            categories=category_ids,
            tags=tag_ids,
            author=author_id,
            after=after,
            before=before,
        )
    )
    return _render(result, "article_search", response_format)


@mcp.tool()
async def list_recent_articles(
    per_page: PerPage = 10, response_format: ResponseFormat = ResponseFormat.JSON
) -> str:
    """List the most recently published Local News Matters articles."""
    result = await _safe(_client.search_articles(per_page=per_page))
    return _render(result, "article_search", response_format)


@mcp.tool()
async def get_article(
    article_id: ItemId, response_format: ResponseFormat = ResponseFormat.JSON
) -> str:
    """Fetch a single article by numeric ID, including full body text."""
    result = await _safe(_client.get_article(article_id))
    return _render(result, "article", response_format)


@mcp.tool()
async def get_article_by_slug(
    slug: Slug, response_format: ResponseFormat = ResponseFormat.JSON
) -> str:
    """Fetch a single article by its URL slug (the last path segment of its URL)."""
    result = await _safe(_client.get_article_by_slug(slug))
    if result is None:
        result = {"error": f"No article found with slug '{slug}'."}
    return _render(result, "article", response_format)


@mcp.tool()
async def search_photos(
    query: Query = "",
    page: Page = 1,
    per_page: PerPage = 10,
    article_id: OptionalId = None,
    response_format: ResponseFormat = ResponseFormat.JSON,
) -> str:
    """Search photos/images in the Local News Matters media library.

    Args:
        query: Search terms matched against title, caption and alt text.
        page: 1-based page number.
        per_page: Results per page (1-100).
        article_id: Restrict to photos attached to a specific article.
        response_format: "json" (default) for raw data, or "markdown" for readable text.

    Returns `results` (photo summaries incl. `source_url`) plus `total`, `total_pages`.
    """
    result = await _safe(
        _client.search_photos(
            query=query or None,
            page=page,
            per_page=per_page,
            parent_article=article_id,
        )
    )
    return _render(result, "photo_search", response_format)


@mcp.tool()
async def get_photo(
    photo_id: ItemId, response_format: ResponseFormat = ResponseFormat.JSON
) -> str:
    """Fetch a single photo by numeric ID, including caption, alt text and available sizes."""
    result = await _safe(_client.get_photo(photo_id))
    return _render(result, "photo", response_format)


@mcp.tool()
async def get_article_photos(
    article_id: ItemId, response_format: ResponseFormat = ResponseFormat.JSON
) -> str:
    """List every photo attached to a given article."""
    result = await _safe(_client.get_article_photos(article_id))
    return _render(result, "article_photos", response_format)


@mcp.tool()
async def list_categories(
    response_format: ResponseFormat = ResponseFormat.JSON,
) -> str:
    """List the site's categories (sections), ordered by article count."""
    result = await _safe(_client.list_categories())
    return _render(result, "categories", response_format)


@mcp.tool()
async def get_category(
    category_id: ItemId, response_format: ResponseFormat = ResponseFormat.JSON
) -> str:
    """Fetch a single category by ID, including its description and article count."""
    result = await _safe(_client.get_category(category_id))
    return _render(result, "category", response_format)


@mcp.tool()
async def list_tags(
    search: Query = "", response_format: ResponseFormat = ResponseFormat.JSON
) -> str:
    """List topic tags, optionally filtered by a search term, ordered by usage."""
    result = await _safe(_client.list_tags(search=search or None))
    return _render(result, "tags", response_format)


@mcp.tool()
async def get_tag(
    tag_id: ItemId, response_format: ResponseFormat = ResponseFormat.JSON
) -> str:
    """Fetch a single tag by ID, including its description and article count."""
    result = await _safe(_client.get_tag(tag_id))
    return _render(result, "tag", response_format)


@mcp.tool()
async def list_authors(
    response_format: ResponseFormat = ResponseFormat.JSON,
) -> str:
    """List the site's authors/contributors."""
    result = await _safe(_client.list_authors())
    return _render(result, "authors", response_format)


@mcp.tool()
async def list_pages(
    response_format: ResponseFormat = ResponseFormat.JSON,
) -> str:
    """List the site's static pages (About, Contact, Donate, etc.), sorted by title."""
    result = await _safe(_client.list_pages())
    return _render(result, "pages", response_format)


# ---------------------------------------------------------------------------
# Resources
# ---------------------------------------------------------------------------


@mcp.resource(
    "lnm://article/{article_id}",
    name="Article",
    description="A single Local News Matters article (full text) as JSON.",
    mime_type="application/json",
)
async def article_resource(article_id: str) -> str:
    return _dumps(await _safe(_client.get_article(int(article_id))))


@mcp.resource(
    "lnm://article/{article_id}/photos",
    name="Article photos",
    description="Photos attached to a Local News Matters article, as JSON.",
    mime_type="application/json",
)
async def article_photos_resource(article_id: str) -> str:
    return _dumps(await _safe(_client.get_article_photos(int(article_id))))


@mcp.resource(
    "lnm://photo/{photo_id}",
    name="Photo",
    description="A single Local News Matters photo's metadata and available sizes, as JSON.",
    mime_type="application/json",
)
async def photo_resource(photo_id: str) -> str:
    return _dumps(await _safe(_client.get_photo(int(photo_id))))


@mcp.resource(
    "lnm://recent/articles",
    name="Recent articles",
    description="The most recently published Local News Matters articles, as JSON.",
    mime_type="application/json",
)
async def recent_articles_resource() -> str:
    return _dumps(await _safe(_client.search_articles(per_page=20)))


@mcp.resource(
    "lnm://categories",
    name="Categories",
    description="Local News Matters categories (sections), as JSON.",
    mime_type="application/json",
)
async def categories_resource() -> str:
    return _dumps(await _safe(_client.list_categories()))


def main() -> None:
    """Console-script entry point: run the server over stdio."""
    mcp.run()


if __name__ == "__main__":
    main()
