from __future__ import annotations

import asyncio
import logging
import time
from dataclasses import dataclass
from typing import Any

import httpx
from django.conf import settings

logger = logging.getLogger(__name__)

_DEFAULT_GEOCODER_URL = "https://geocoding.geo.census.gov/geocoder/geographies/onelineaddress"
_DEFAULT_ACS_BASE_URL = "https://api.census.gov/data"
_DEFAULT_TIMEOUT = 10.0
_DEFAULT_RETRIES = 3
_DEFAULT_CACHE_TTL = 30 * 24 * 60 * 60
_DEFAULT_ACS_YEAR = 2023
_MISSING_VALUES = {"", "null", "-666666666", "-999999999", None}
_ACS_VARIABLES = (
    "B01003_001E",
    "B19013_001E",
    "B17001_002E",
    "B15003_022E",
    "B15003_023E",
    "B15003_024E",
    "B15003_025E",
    "B25077_001E",
    "B25064_001E",
    "B23025_005E",
    "B23025_003E",
    "B25003_001E",
    "B25003_002E",
    "B25003_003E",
    "B15003_001E",
    "B02001_002E",
    "B02001_003E",
    "B02001_005E",
    "B03003_003E",
    "B03003_001E",
)
_CACHE: dict[str, tuple[float, dict]] = {}


class _InvalidCensusApiKeyError(RuntimeError):
    pass


@dataclass
class GeoDemographicEnricher:
    geocoder_url: str
    acs_base_url: str
    timeout: float
    retries: int
    cache_ttl: int
    api_key: str
    configured_acs_year: int

    @classmethod
    def from_settings(cls) -> "GeoDemographicEnricher":
        return cls(
            geocoder_url=getattr(settings, "CENSUS_GEOCODER_URL", _DEFAULT_GEOCODER_URL),
            acs_base_url=getattr(settings, "CENSUS_ACS_BASE_URL", _DEFAULT_ACS_BASE_URL),
            timeout=float(getattr(settings, "CENSUS_TIMEOUT_SECONDS", _DEFAULT_TIMEOUT)),
            retries=int(getattr(settings, "CENSUS_RETRIES", _DEFAULT_RETRIES)),
            cache_ttl=int(getattr(settings, "CENSUS_CACHE_TTL_SECONDS", _DEFAULT_CACHE_TTL)),
            api_key=getattr(settings, "CENSUS_API_KEY", ""),
            configured_acs_year=int(getattr(settings, "CENSUS_ACS_YEAR", _DEFAULT_ACS_YEAR)),
        )

    async def enrich(self, company_record: dict[str, Any]) -> dict:
        normalized = normalize_location_input(company_record)
        query = normalized["query"]
        if normalized["status"] == "skipped":
            return {
                "status": "skipped",
                "reason": normalized["reason"],
            }
        if not query:
            return {
                "status": "error",
                "reason": "missing_address",
                "details": "No usable address or location fields were provided.",
            }

        cache_key = query.lower()
        cached = _cache_get(cache_key, self.cache_ttl)
        if cached is not None:
            return cached

        logger.info("geo demographics normalized address=%r", query)
        geocode_result = await self._geocode(query)
        if geocode_result["status"] != "success":
            result = {
                "status": geocode_result["status"],
                "reason": geocode_result["reason"],
                "details": geocode_result.get("details"),
            }
            _cache_set(cache_key, result, self.cache_ttl)
            return result

        location = geocode_result["location"]
        logger.info(
            "geo demographics matched state=%s county=%s tract=%s",
            location["state_fips"],
            location["county_fips"],
            location["tract"],
        )

        acs_result = await self._fetch_acs(location)
        if acs_result["status"] != "success":
            result = {
                "status": "error",
                "reason": acs_result["reason"],
                "details": acs_result.get("details"),
                "location": location,
                "quality": {
                    "geocode_confidence": "matched",
                    "warnings": acs_result.get("warnings", []),
                },
            }
            _cache_set(cache_key, result, self.cache_ttl)
            return result

        result = {
            "status": "success",
            "source": "us_census_acs_5yr",
            "acs_year": acs_result["acs_year"],
            "location": location,
            "demographics": acs_result["demographics"],
            "economics": acs_result["economics"],
            "housing": acs_result["housing"],
            "quality": {
                "geocode_confidence": "matched",
                "warnings": acs_result.get("warnings", []),
            },
        }
        _cache_set(cache_key, result, self.cache_ttl)
        return result

    async def _geocode(self, query: str) -> dict:
        params = {
            "address": query,
            "benchmark": "Public_AR_Current",
            "vintage": "Current_Current",
            "format": "json",
        }
        try:
            data = await self._request_json(self.geocoder_url, params=params)
        except httpx.TimeoutException as exc:
            return {"status": "error", "reason": "timeout", "details": str(exc)}
        except httpx.HTTPStatusError as exc:
            return {
                "status": "error",
                "reason": _status_reason(exc.response.status_code),
                "details": f"Geocoder HTTP {exc.response.status_code}",
            }
        except Exception as exc:
            return {"status": "error", "reason": "geocoder_error", "details": str(exc)}

        matches = (data.get("result") or {}).get("addressMatches") or []
        if not matches:
            logger.info("geo demographics geocoder matched=false")
            return {
                "status": "not_found",
                "reason": "not_found",
                "details": "No Census geocoder address match was found.",
            }

        match = matches[0]
        geographies = match.get("geographies") or {}
        tracts = geographies.get("Census Tracts") or []
        if not tracts:
            return {
                "status": "error",
                "reason": "malformed_response",
                "details": "Census geocoder response did not include tract geography.",
            }

        tract_row = tracts[0]
        county_row = (geographies.get("Counties") or [{}])[0]
        state_row = (geographies.get("States") or [{}])[0]
        location = {
            "input_address": query,
            "matched_address": match.get("matchedAddress"),
            "latitude": _to_float((match.get("coordinates") or {}).get("y")),
            "longitude": _to_float((match.get("coordinates") or {}).get("x")),
            "state_fips": str(tract_row.get("STATE", "")).zfill(2),
            "county_fips": str(tract_row.get("COUNTY", "")).zfill(3),
            "tract": str(tract_row.get("TRACT", "")).zfill(6),
            "block_group": str(tract_row.get("BLKGRP", "")).strip() or None,
            "geo_name": tract_row.get("NAME") or county_row.get("NAME") or state_row.get("NAME"),
            "county_name": county_row.get("NAME"),
            "state_name": state_row.get("NAME"),
        }
        return {"status": "success", "location": location}

    async def _fetch_acs(self, location: dict) -> dict:
        warnings: list[str] = []
        for year in candidate_acs_years(self.configured_acs_year):
            url = f"{self.acs_base_url}/{year}/acs/acs5"
            for use_key in (bool(self.api_key), False):
                params = {
                    "get": ",".join(("NAME",) + _ACS_VARIABLES),
                    "for": f"tract:{location['tract']}",
                    "in": f"state:{location['state_fips']} county:{location['county_fips']}",
                }
                if use_key and self.api_key:
                    params["key"] = self.api_key

                try:
                    data = await self._request_json(url, params=params)
                except _InvalidCensusApiKeyError:
                    warnings.append("ACS API key rejected; retrying without key.")
                    if use_key:
                        continue
                    return {
                        "status": "error",
                        "reason": "invalid_key",
                        "details": "Census ACS rejected the configured API key and anonymous retry also failed.",
                        "warnings": warnings,
                    }
                except httpx.TimeoutException as exc:
                    return {"status": "error", "reason": "timeout", "details": str(exc), "warnings": warnings}
                except httpx.HTTPStatusError as exc:
                    if exc.response.status_code in (400, 404) and year != candidate_acs_years(self.configured_acs_year)[-1]:
                        warnings.append(f"ACS year {year} unavailable; falling back.")
                        break
                    return {
                        "status": "error",
                        "reason": _status_reason(exc.response.status_code),
                        "details": f"ACS HTTP {exc.response.status_code}",
                        "warnings": warnings,
                    }
                except Exception as exc:
                    return {"status": "error", "reason": "acs_error", "details": str(exc), "warnings": warnings}

                try:
                    headers, row = data
                    payload = dict(zip(headers, row))
                    return {
                        "status": "success",
                        "acs_year": year,
                        "warnings": warnings,
                        **_transform_acs_payload(payload),
                    }
                except Exception as exc:
                    return {
                        "status": "error",
                        "reason": "malformed_response",
                        "details": str(exc),
                        "warnings": warnings,
                    }

        return {
            "status": "error",
            "reason": "acs_unavailable",
            "details": "No configured ACS year returned usable data.",
            "warnings": warnings,
        }

    async def _request_json(self, url: str, params: dict[str, Any]) -> Any:
        delay = 0.5
        last_exc: Exception | None = None
        for attempt in range(1, self.retries + 1):
            try:
                async with httpx.AsyncClient(timeout=self.timeout, follow_redirects=True) as client:
                    response = await client.get(url, params=params)
                    response.raise_for_status()
                    try:
                        return response.json()
                    except ValueError as exc:
                        if _looks_like_invalid_key_response(response):
                            raise _InvalidCensusApiKeyError("Census API key rejected") from exc
                        raise
            except httpx.TimeoutException as exc:
                last_exc = exc
                if attempt == self.retries:
                    raise
            except httpx.HTTPStatusError as exc:
                last_exc = exc
                if not _should_retry_status(exc.response.status_code) or attempt == self.retries:
                    raise
            except httpx.RequestError as exc:
                last_exc = exc
                if attempt == self.retries:
                    raise
            await asyncio.sleep(delay)
            delay *= 2
        assert last_exc is not None
        raise last_exc


async def enrich_geo_demographics(company_record: dict[str, Any]) -> dict:
    """
    Enrich a U.S. location into tract-level Census demographics/economics.

    Example output:
    {
      "status": "success",
      "source": "us_census_acs_5yr",
      "acs_year": 2023,
      "location": {...},
      "demographics": {...},
      "economics": {...},
      "housing": {...},
      "quality": {...}
    }
    """
    enricher = GeoDemographicEnricher.from_settings()
    return await enricher.enrich(company_record)


def normalize_location_input(company_record: dict[str, Any]) -> dict[str, Any]:
    country = _clean(company_record.get("country"))
    if country and country.upper() not in {"US", "USA", "UNITED STATES", "UNITED STATES OF AMERICA"}:
        return {"status": "skipped", "reason": "non_us_location", "query": None}

    address_line1 = company_record.get("address_line1") or company_record.get("property_address")
    candidates = [
        company_record.get("full_address"),
        _join_parts(
            address_line1,
            company_record.get("address_line2"),
            company_record.get("city"),
            company_record.get("state"),
            company_record.get("postal_code") or company_record.get("zip"),
        ) if address_line1 else None,
        company_record.get("headquarters_address"),
        _join_parts(company_record.get("city"), company_record.get("state"), company_record.get("country")),
        company_record.get("location") or company_record.get("raw_location") or company_record.get("headquarters"),
    ]
    for candidate in candidates:
        cleaned = _clean(candidate)
        if cleaned:
            return {"status": "ready", "reason": None, "query": cleaned}
    return {"status": "error", "reason": "missing_address", "query": None}


def candidate_acs_years(configured_year: int) -> list[int]:
    years: list[int] = []
    for year in (configured_year, 2023, 2022):
        if year not in years:
            years.append(year)
    return years


def _transform_acs_payload(payload: dict[str, Any]) -> dict:
    total_population = _to_int(payload.get("B01003_001E"))
    ethnicity_total = _to_int(payload.get("B03003_001E"))
    education_population = _to_int(payload.get("B15003_001E"))
    bachelors_degree = _to_int(payload.get("B15003_022E"))
    masters_degree = _to_int(payload.get("B15003_023E"))
    professional_degree = _to_int(payload.get("B15003_024E"))
    doctorate_degree = _to_int(payload.get("B15003_025E"))
    bachelors_or_higher_count = _sum_values(
        bachelors_degree,
        masters_degree,
        professional_degree,
        doctorate_degree,
    )
    occupied_housing_units = _to_int(payload.get("B25003_001E"))
    owner_occupied_units = _to_int(payload.get("B25003_002E"))
    renter_occupied_units = _to_int(payload.get("B25003_003E"))
    poverty_count = _to_int(payload.get("B17001_002E"))
    unemployed_population = _to_int(payload.get("B23025_005E"))
    civilian_labor_force = _to_int(payload.get("B23025_003E"))

    return {
        "demographics": {
            "total_population": total_population,
            "race_ethnicity": {
                "white_alone_pct": _pct(_to_int(payload.get("B02001_002E")), total_population),
                "black_alone_pct": _pct(_to_int(payload.get("B02001_003E")), total_population),
                "asian_alone_pct": _pct(_to_int(payload.get("B02001_005E")), total_population),
                "hispanic_or_latino_pct": _pct(_to_int(payload.get("B03003_003E")), ethnicity_total),
            },
            "education": {
                "bachelors_or_higher_count": bachelors_or_higher_count,
                "bachelors_or_higher_pct": _pct(bachelors_or_higher_count, education_population),
            },
        },
        "economics": {
            "median_household_income": _to_int(payload.get("B19013_001E")),
            "poverty_count": poverty_count,
            "poverty_rate_pct": _pct(poverty_count, total_population),
            "unemployment_rate_pct": _pct(unemployed_population, civilian_labor_force),
        },
        "housing": {
            "median_home_value": _to_int(payload.get("B25077_001E")),
            "median_gross_rent": _to_int(payload.get("B25064_001E")),
            "owner_occupied_pct": _pct(owner_occupied_units, occupied_housing_units),
            "renter_occupied_pct": _pct(renter_occupied_units, occupied_housing_units),
        },
    }


def _to_int(value: Any) -> int | None:
    if value in _MISSING_VALUES:
        return None
    try:
        return int(str(value))
    except (TypeError, ValueError):
        return None


def _to_float(value: Any) -> float | None:
    if value in _MISSING_VALUES:
        return None
    try:
        return float(str(value))
    except (TypeError, ValueError):
        return None


def _pct(numerator: int | None, denominator: int | None) -> float | None:
    if numerator is None or denominator in (None, 0):
        return None
    return round((numerator / denominator) * 100, 2)


def _sum_values(*values: int | None) -> int | None:
    present = [value for value in values if value is not None]
    if not present:
        return None
    return sum(present)


def _join_parts(*parts: Any) -> str | None:
    cleaned = [_clean(part) for part in parts]
    joined = ", ".join(part for part in cleaned if part)
    return joined or None


def _clean(value: Any) -> str | None:
    text = str(value or "").strip()
    return text or None


def _status_reason(status_code: int) -> str:
    if status_code == 429:
        return "rate_limited"
    if 500 <= status_code < 600:
        return "service_unavailable"
    if status_code == 400:
        return "invalid_request"
    return "upstream_error"


def _looks_like_invalid_key_response(response: httpx.Response) -> bool:
    content_type = (response.headers.get("content-type") or "").lower()
    body = (response.text or "").lower()
    return "text/html" in content_type and "invalid key" in body


def _should_retry_status(status_code: int) -> bool:
    return status_code == 429 or 500 <= status_code < 600


def _cache_get(key: str, ttl: int) -> dict | None:
    cached = _CACHE.get(key)
    if not cached:
        return None
    expires_at, value = cached
    if expires_at < time.time():
        _CACHE.pop(key, None)
        return None
    return value


def _cache_set(key: str, value: dict, ttl: int) -> None:
    _CACHE[key] = (time.time() + ttl, value)


async def fetch_city_data(city: str, state_abbr: str, property_address: str = "") -> dict | None:
    """
    Backward-compatible shim for older callers.
    Prefer enrich_geo_demographics().
    """
    result = await enrich_geo_demographics(
        {
            "property_address": property_address,
            "city": city,
            "state": state_abbr,
            "country": "US",
        }
    )
    if result.get("status") != "success":
        return None
    return {
        "name": result["location"].get("geo_name"),
        "city": city,
        "state_abbr": state_abbr.upper(),
        "state_fips": result["location"].get("state_fips"),
        "county_fips": result["location"].get("county_fips"),
        "tract": result["location"].get("tract"),
        "population": result["demographics"].get("total_population"),
        "median_rent": result["housing"].get("median_gross_rent"),
        "renter_percentage": result["housing"].get("renter_occupied_pct"),
    }
