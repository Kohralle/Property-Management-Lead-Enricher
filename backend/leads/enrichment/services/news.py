from __future__ import annotations

import html
import logging
import re

import httpx
from django.conf import settings

logger = logging.getLogger(__name__)

_BASE_URL = "https://serpapi.com/search.json"
_TIMEOUT = 10.0
_MAX_ARTICLES = 10
_ARTICLE_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36"
    ),
}


def _api_key() -> str:
    return getattr(settings, "SERPAPI_API_KEY", "")


def _query_variants(company: str) -> list[str]:
    return [
        f'"{company}" real estate',
        f'"{company}" property management',
        company,
    ]


async def search_articles(company: str, days_back: int = 90) -> list[dict]:
    """Fetch top Google News results for a company via SerpAPI."""
    api_key = _api_key()
    if not api_key:
        logger.warning("news search skipped: SERPAPI_API_KEY not configured for company=%r", company)
        return []

    for query in _query_variants(company):
        params = {
            "engine": "google_news",
            "q": query,
            "api_key": api_key,
            "num": _MAX_ARTICLES,
        }
        data = await _fetch_news(company, query, params)
        if not isinstance(data, dict):
            continue

        try:
            articles = [
                {
                    "title": article.get("title"),
                    "source": (article.get("source") or {}).get("name"),
                    "publishedAt": article.get("date"),
                    "snippet": article.get("snippet") or "",
                    "url": article.get("link"),
                }
                for article in (data.get("news_results") or [])[:_MAX_ARTICLES]
                if article.get("title") and article.get("link")
            ]
        except Exception as exc:
            logger.warning("news search parse error for company=%r query=%r: %s", company, query, exc)
            continue

        if articles:
            return articles

    return []


async def _fetch_news(company: str, query: str, params: dict) -> dict | None:
    try:
        async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
            response = await client.get(_BASE_URL, params=params)
            response.raise_for_status()
            data = response.json()
    except httpx.HTTPStatusError as exc:
        logger.warning(
            "news search failed: HTTP %s for company=%r query=%r",
            exc.response.status_code,
            company,
            query,
        )
        return None
    except httpx.RequestError as exc:
        logger.warning("news search network error for company=%r query=%r: %s", company, query, exc)
        return None
    except Exception as exc:
        logger.warning("news search unexpected error for company=%r query=%r: %s", company, query, exc)
        return None

    if data.get("error"):
        logger.warning("news search provider error for company=%r query=%r: %s", company, query, data["error"])
        return None
    return data


def _normalize_text(text: str) -> str:
    text = html.unescape(text or "").lower()
    text = re.sub(r"(?<=\w)\.(?=\w)", "", text)
    text = re.sub(r"[^\w\s]", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def _extract_readable_text(document: str) -> str:
    text = document or ""
    text = re.sub(r"(?is)<(script|style|noscript|svg|iframe|template).*?>.*?</\1>", " ", text)
    text = re.sub(r"(?is)<br\s*/?>", " ", text)
    text = re.sub(r"(?is)</p>|</div>|</section>|</article>|</li>|</h\d>", " ", text)
    text = re.sub(r"(?is)<[^>]+>", " ", text)
    text = html.unescape(text)
    return re.sub(r"\s+", " ", text).strip()


def extract_excerpt_from_text(
    document_text: str,
    company_variants: list[str],
    *,
    window_chars: int = 400,
) -> str | None:
    plain_text = _extract_readable_text(document_text)
    normalized_text = _normalize_text(plain_text)
    if not normalized_text:
        return None

    normalized_variants = sorted(
        {
            _normalize_text(variant)
            for variant in company_variants
            if _normalize_text(variant)
        },
        key=len,
        reverse=True,
    )
    for variant in normalized_variants:
        match = re.search(rf"\b{re.escape(variant)}\b", normalized_text)
        if not match:
            continue
        start = max(0, match.start() - window_chars)
        end = min(len(normalized_text), match.end() + window_chars)
        excerpt = normalized_text[start:end].strip()
        return excerpt or None
    return None


async def fetch_article_excerpt(url: str, company_variants: list[str]) -> str | None:
    if not url or not company_variants:
        return None

    try:
        async with httpx.AsyncClient(timeout=_TIMEOUT, headers=_ARTICLE_HEADERS, follow_redirects=True) as client:
            response = await client.get(url)
            response.raise_for_status()
    except httpx.HTTPStatusError as exc:
        logger.warning("article fetch failed: HTTP %s for url=%r", exc.response.status_code, url)
        return None
    except httpx.RequestError as exc:
        logger.warning("article fetch network error for url=%r: %s", url, exc)
        return None
    except Exception as exc:
        logger.warning("article fetch unexpected error for url=%r: %s", url, exc)
        return None

    return extract_excerpt_from_text(response.text, company_variants)
