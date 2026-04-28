from __future__ import annotations

import logging

import httpx
from django.conf import settings

logger = logging.getLogger(__name__)

_GEOCODE_URL = "https://api.openweathermap.org/geo/1.0/direct"
_CURRENT_URL = "https://api.openweathermap.org/data/2.5/weather"
_TIMEOUT = 10.0


def _api_key() -> str:
    return getattr(settings, "OPENWEATHER_API_KEY", "")


def _conditions_label(temp_f: float, description: str, main: str) -> str:
    condition = (main or description or "").lower()
    if "thunder" in condition:
        return "a stormy day"
    if "rain" in condition or "drizzle" in condition:
        return "a rainy day"
    if "snow" in condition:
        return "a snowy day"
    if "mist" in condition or "fog" in condition or "haze" in condition:
        return "a gray hazy day"
    if "clear" in condition:
        if temp_f < 45:
            return "a crisp clear day"
        if temp_f < 80:
            return "a pleasant sunny day"
        return "a hot sunny day"
    if "cloud" in condition:
        if temp_f < 45:
            return "a chilly cloudy day"
        if temp_f < 80:
            return "a mild overcast day"
        return "a warm muggy day"
    if temp_f < 45:
        return "a brisk day"
    if temp_f < 80:
        return "a mild day"
    return "a hot day"


async def fetch_current(city: str, state_abbr: str) -> dict | None:
    """Fetch current weather for a US city via OpenWeather geocoding + weather APIs."""
    api_key = _api_key()
    if not api_key:
        logger.warning(
            "weather fetch skipped: OPENWEATHER_API_KEY not configured for city=%r state=%r",
            city,
            state_abbr,
        )
        return None

    geocode_params = {
        "q": f"{city},{state_abbr},US",
        "limit": 1,
        "appid": api_key,
    }

    try:
        async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
            geocode_response = await client.get(_GEOCODE_URL, params=geocode_params)
            geocode_response.raise_for_status()
            locations = geocode_response.json()
    except httpx.HTTPStatusError as exc:
        logger.warning(
            "weather geocode failed: HTTP %s for city=%r state=%r",
            exc.response.status_code,
            city,
            state_abbr,
        )
        return None
    except httpx.RequestError as exc:
        logger.warning(
            "weather geocode network error for city=%r state=%r: %s",
            city,
            state_abbr,
            exc,
        )
        return None
    except Exception as exc:
        logger.warning(
            "weather geocode unexpected error for city=%r state=%r: %s",
            city,
            state_abbr,
            exc,
        )
        return None

    try:
        location = locations[0]
        lat = location["lat"]
        lon = location["lon"]
    except Exception as exc:
        logger.warning("weather geocode parse error for city=%r state=%r: %s", city, state_abbr, exc)
        return None

    weather_params = {
        "lat": lat,
        "lon": lon,
        "appid": api_key,
        "units": "imperial",
    }

    try:
        async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
            weather_response = await client.get(_CURRENT_URL, params=weather_params)
            weather_response.raise_for_status()
            data = weather_response.json()
    except httpx.HTTPStatusError as exc:
        logger.warning(
            "weather current failed: HTTP %s for city=%r state=%r",
            exc.response.status_code,
            city,
            state_abbr,
        )
        return None
    except httpx.RequestError as exc:
        logger.warning(
            "weather current network error for city=%r state=%r: %s",
            city,
            state_abbr,
            exc,
        )
        return None
    except Exception as exc:
        logger.warning(
            "weather current unexpected error for city=%r state=%r: %s",
            city,
            state_abbr,
            exc,
        )
        return None

    try:
        weather = (data.get("weather") or [{}])[0]
        description = weather.get("description", "")
        main = weather.get("main", "")
        temp_f = float((data.get("main") or {}).get("temp"))
        return {
            "description": description,
            "temp_f": round(temp_f, 1),
            "conditions_label": _conditions_label(temp_f, description, main),
        }
    except Exception as exc:
        logger.warning("weather current parse error for city=%r state=%r: %s", city, state_abbr, exc)
        return None
