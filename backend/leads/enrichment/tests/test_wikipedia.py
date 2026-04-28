"""
Integration tests — hit live Wikipedia APIs.
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

from leads.enrichment.services.wikipedia import fetch_summary, search_pages  # noqa: E402


@pytest.mark.integration
@pytest.mark.asyncio
async def test_search_pages_returns_results():
    results = await search_pages("Bozzuto")
    assert isinstance(results, list)
    assert len(results) > 0
    first = results[0]
    assert "title" in first
    assert "snippet" in first


@pytest.mark.integration
@pytest.mark.asyncio
async def test_fetch_summary_returns_expected_fields():
    summary = await fetch_summary("New York City")
    assert summary is not None
    assert "extract" in summary
    assert "description" in summary
    assert "content_urls" in summary
