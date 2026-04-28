"""
Integration tests — hit the live OpenWeather APIs.
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

from leads.enrichment.services.weather import fetch_current  # noqa: E402

_requires_key = pytest.mark.skipif(
    not getattr(settings, "OPENWEATHER_API_KEY", ""),
    reason="OPENWEATHER_API_KEY not configured",
)


@_requires_key
@pytest.mark.integration
@pytest.mark.asyncio
async def test_fetch_current_returns_expected_fields():
    weather = await fetch_current("Seattle", "WA")
    assert weather is not None
    for field in ("description", "temp_f", "conditions_label"):
        assert field in weather


@_requires_key
@pytest.mark.integration
@pytest.mark.asyncio
async def test_fetch_current_returns_temperature_number():
    weather = await fetch_current("Austin", "TX")
    assert weather is not None
    assert isinstance(weather["temp_f"], float)
