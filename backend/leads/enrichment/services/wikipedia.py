from __future__ import annotations

import html
import logging
import re
from urllib.parse import quote

import httpx

logger = logging.getLogger(__name__)

_SEARCH_URL = "https://en.wikipedia.org/w/api.php"
_SUMMARY_URL = "https://en.wikipedia.org/api/rest_v1/page/summary"
_TIMEOUT = 10.0
_TAG_RE = re.compile(r"<[^>]+>")


def _clean_snippet(snippet: str) -> str:
    return html.unescape(_TAG_RE.sub("", snippet or "")).strip()


async def search_pages(query: str) -> list[dict]:
    """Search Wikipedia and return up to 5 pages with title/snippet."""
    params = {
        "action": "query",
        "list": "search",
        "srsearch": query,
        "format": "json",
        "utf8": 1,
        "srlimit": 5,
    }

    try:
        async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
            response = await client.get(_SEARCH_URL, params=params)
            response.raise_for_status()
            data = response.json()
    except httpx.HTTPStatusError as exc:
        logger.warning(
            "wikipedia search failed: HTTP %s for query=%r",
            exc.response.status_code,
            query,
        )
        return []
    except httpx.RequestError as exc:
        logger.warning("wikipedia search network error for query=%r: %s", query, exc)
        return []
    except Exception as exc:
        logger.warning("wikipedia search unexpected error for query=%r: %s", query, exc)
        return []

    try:
        results = data.get("query", {}).get("search") or []
        return [
            {
                "title": result.get("title"),
                "snippet": _clean_snippet(result.get("snippet", "")),
            }
            for result in results
            if result.get("title")
        ]
    except Exception as exc:
        logger.warning("wikipedia search parse error for query=%r: %s", query, exc)
        return []


async def fetch_summary(title: str) -> dict | None:
    """Fetch Wikipedia REST summary payload for a page title."""
    encoded_title = quote(title, safe="")

    try:
        async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
            response = await client.get(f"{_SUMMARY_URL}/{encoded_title}")
            response.raise_for_status()
            data = response.json()
    except httpx.HTTPStatusError as exc:
        logger.warning(
            "wikipedia summary failed: HTTP %s for title=%r",
            exc.response.status_code,
            title,
        )
        return None
    except httpx.RequestError as exc:
        logger.warning("wikipedia summary network error for title=%r: %s", title, exc)
        return None
    except Exception as exc:
        logger.warning("wikipedia summary unexpected error for title=%r: %s", title, exc)
        return None

    try:
        return {
            "extract": data.get("extract", ""),
            "description": data.get("description"),
            "content_urls": data.get("content_urls") or {},
        }
    except Exception as exc:
        logger.warning("wikipedia summary parse error for title=%r: %s", title, exc)
        return None
