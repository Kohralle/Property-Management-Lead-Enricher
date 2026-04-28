"""
Integration tests — hit live Census geocoder and ACS APIs.
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

from leads.enrichment.services.census import enrich_geo_demographics  # noqa: E402


@pytest.mark.integration
@pytest.mark.asyncio
async def test_enrich_geo_demographics_returns_structured_payload():
    data = await enrich_geo_demographics(
        {
            "full_address": "701 5th Ave, Seattle, WA 98104",
            "country": "US",
        }
    )
    assert data["status"] == "success"
    assert data["source"] == "us_census_acs_5yr"
    assert "location" in data
    assert "demographics" in data
    assert "economics" in data
    assert "housing" in data


@pytest.mark.integration
@pytest.mark.asyncio
async def test_enrich_geo_demographics_returns_numeric_fields():
    data = await enrich_geo_demographics(
        {
            "city": "Austin",
            "state": "TX",
            "country": "US",
        }
    )
    assert data["status"] in {"success", "not_found"}
    if data["status"] == "success":
        assert isinstance(data["demographics"]["total_population"], int) or data["demographics"]["total_population"] is None
        assert isinstance(data["housing"]["median_gross_rent"], int) or data["housing"]["median_gross_rent"] is None
