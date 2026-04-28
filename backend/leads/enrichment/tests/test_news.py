"""
Integration tests — hit the live SerpAPI Google News service.
Skipped in normal runs; opt in with: pytest -m integration
"""
import os
import sys

import django
import pytest

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")

_backend = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__)
))))
if _backend not in sys.path:
    sys.path.insert(0, _backend)

django.setup()

from django.conf import settings  # noqa: E402

from leads.enrichment.services.news import search_articles  # noqa: E402

_requires_key = pytest.mark.skipif(
    not getattr(settings, "SERPAPI_API_KEY", ""),
    reason="SERPAPI_API_KEY not configured",
)


@_requires_key
@pytest.mark.integration
@pytest.mark.asyncio
async def test_search_articles_returns_article_list():
    articles = await search_articles("Greystar")
    assert isinstance(articles, list)
    assert len(articles) > 0


@_requires_key
@pytest.mark.integration
@pytest.mark.asyncio
async def test_search_articles_result_has_expected_fields():
    articles = await search_articles("Bozzuto")
    assert articles, "expected at least one article"
    first = articles[0]
    for field in ("title", "source", "publishedAt", "snippet", "url"):
        assert field in first
