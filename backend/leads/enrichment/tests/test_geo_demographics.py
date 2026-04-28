import httpx
import pytest

from leads.enrichment.services.census import (
    _CACHE,
    _InvalidCensusApiKeyError,
    GeoDemographicEnricher,
    normalize_location_input,
)


GEOCODER_PAYLOAD = {
    "result": {
        "addressMatches": [
            {
                "matchedAddress": "100 Main St, Seattle, WA 98101",
                "coordinates": {"x": -122.3351, "y": 47.608},
                "geographies": {
                    "Census Tracts": [
                        {
                            "STATE": "53",
                            "COUNTY": "033",
                            "TRACT": "008700",
                            "BLKGRP": "1",
                            "NAME": "Census Tract 87, King County, Washington",
                        }
                    ],
                    "Counties": [{"NAME": "King County"}],
                    "States": [{"NAME": "Washington"}],
                },
            }
        ]
    }
}

ACS_HEADERS = [
    "NAME",
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
    "state",
    "county",
    "tract",
]
ACS_ROW = [
    "Census Tract 87, King County, Washington",
    "1000",
    "90000",
    "120",
    "150",
    "60",
    "25",
    "15",
    "800000",
    "2400",
    "40",
    "500",
    "400",
    "150",
    "250",
    "600",
    "500",
    "200",
    "100",
    "300",
    "1000",
    "53",
    "033",
    "008700",
]


def make_enricher(**overrides):
    return GeoDemographicEnricher(
        geocoder_url="https://geo.test/geocode",
        acs_base_url="https://acs.test/data",
        timeout=1.0,
        retries=2,
        cache_ttl=60,
        api_key=overrides.pop("api_key", "test-key"),
        configured_acs_year=overrides.pop("configured_acs_year", 2023),
        **overrides,
    )


@pytest.fixture(autouse=True)
def clear_geo_cache():
    _CACHE.clear()
    yield
    _CACHE.clear()


@pytest.mark.asyncio
async def test_valid_full_us_address(monkeypatch):
    enricher = make_enricher()

    async def fake_request(url, params):
        if "geocode" in url:
            return GEOCODER_PAYLOAD
        return [ACS_HEADERS, ACS_ROW]

    monkeypatch.setattr(enricher, "_request_json", fake_request)
    result = await enricher.enrich(
        {
            "full_address": "100 Main St, Seattle, WA 98101",
            "country": "US",
        }
    )

    assert result["status"] == "success"
    assert result["location"]["state_fips"] == "53"
    assert result["demographics"]["total_population"] == 1000
    assert result["economics"]["poverty_rate_pct"] == 12.0
    assert result["economics"]["unemployment_rate_pct"] == 8.0
    assert result["housing"]["renter_occupied_pct"] == 62.5
    assert result["demographics"]["education"]["bachelors_or_higher_count"] == 250
    assert result["demographics"]["education"]["bachelors_or_higher_pct"] == 41.67


def test_city_state_only_input():
    normalized = normalize_location_input({"city": "Seattle", "state": "WA", "country": "US"})
    assert normalized["status"] == "ready"
    assert normalized["query"] == "Seattle, WA, US"


@pytest.mark.asyncio
async def test_missing_address():
    result = await make_enricher().enrich({})
    assert result["status"] == "error"
    assert result["reason"] == "missing_address"


@pytest.mark.asyncio
async def test_non_us_address():
    result = await make_enricher().enrich({"city": "Toronto", "country": "Canada"})
    assert result == {"status": "skipped", "reason": "non_us_location"}


@pytest.mark.asyncio
async def test_geocoder_returns_no_matches(monkeypatch):
    enricher = make_enricher()

    async def fake_request(url, params):
        return {"result": {"addressMatches": []}}

    monkeypatch.setattr(enricher, "_request_json", fake_request)
    result = await enricher.enrich({"full_address": "Unknown", "country": "US"})
    assert result["status"] == "not_found"
    assert result["reason"] == "not_found"


@pytest.mark.asyncio
async def test_acs_returns_valid_data(monkeypatch):
    enricher = make_enricher()

    async def fake_request(url, params):
        if "geocode" in url:
            return GEOCODER_PAYLOAD
        assert params["key"] == "test-key"
        return [ACS_HEADERS, ACS_ROW]

    monkeypatch.setattr(enricher, "_request_json", fake_request)
    result = await enricher.enrich({"full_address": "100 Main St", "country": "US"})
    assert result["economics"]["median_household_income"] == 90000
    assert result["housing"]["median_gross_rent"] == 2400


@pytest.mark.asyncio
async def test_acs_returns_missing_values(monkeypatch):
    enricher = make_enricher()

    missing_row = list(ACS_ROW)
    missing_row[1] = "-666666666"
    missing_row[8] = "-999999999"
    missing_row[12] = "0"
    missing_row[13] = ""
    missing_row[14] = ""

    async def fake_request(url, params):
        if "geocode" in url:
            return GEOCODER_PAYLOAD
        return [ACS_HEADERS, missing_row]

    monkeypatch.setattr(enricher, "_request_json", fake_request)
    result = await enricher.enrich({"full_address": "100 Main St", "country": "US"})
    assert result["demographics"]["total_population"] is None
    assert result["housing"]["median_home_value"] is None
    assert result["housing"]["owner_occupied_pct"] is None
    assert result["housing"]["renter_occupied_pct"] is None


@pytest.mark.asyncio
async def test_timeout_and_500_response(monkeypatch):
    enricher = make_enricher()

    async def timeout_request(url, params):
        raise httpx.TimeoutException("timed out")

    monkeypatch.setattr(enricher, "_request_json", timeout_request)
    timeout_result = await enricher.enrich({"full_address": "100 Main St", "country": "US"})
    assert timeout_result["status"] == "error"
    assert timeout_result["reason"] == "timeout"
    _CACHE.clear()

    async def geocode_then_500(url, params):
        if "geocode" in url:
            return GEOCODER_PAYLOAD
        request = httpx.Request("GET", url)
        response = httpx.Response(500, request=request)
        raise httpx.HTTPStatusError("boom", request=request, response=response)

    monkeypatch.setattr(enricher, "_request_json", geocode_then_500)
    server_result = await enricher.enrich({"full_address": "101 Main St", "country": "US"})
    assert server_result["status"] == "error"
    assert server_result["reason"] == "service_unavailable"


@pytest.mark.asyncio
async def test_division_by_zero_in_derived_metrics(monkeypatch):
    enricher = make_enricher()
    zero_row = list(ACS_ROW)
    zero_row[11] = "0"
    zero_row[12] = "0"
    zero_row[15] = "0"

    async def fake_request(url, params):
        if "geocode" in url:
            return GEOCODER_PAYLOAD
        return [ACS_HEADERS, zero_row]

    monkeypatch.setattr(enricher, "_request_json", fake_request)
    result = await enricher.enrich({"full_address": "100 Main St", "country": "US"})
    assert result["economics"]["unemployment_rate_pct"] is None
    assert result["housing"]["owner_occupied_pct"] is None
    assert result["demographics"]["education"]["bachelors_or_higher_pct"] is None


@pytest.mark.asyncio
async def test_no_census_api_key_configured(monkeypatch):
    enricher = make_enricher(api_key="")

    async def fake_request(url, params):
        if "geocode" in url:
            return GEOCODER_PAYLOAD
        assert "key" not in params
        return [ACS_HEADERS, ACS_ROW]

    monkeypatch.setattr(enricher, "_request_json", fake_request)
    result = await enricher.enrich({"full_address": "100 Main St", "country": "US"})
    assert result["status"] == "success"


@pytest.mark.asyncio
async def test_invalid_census_api_key_falls_back_to_anonymous(monkeypatch):
    enricher = make_enricher(api_key="bad-key")
    calls = []

    async def fake_request(url, params):
        calls.append(dict(params))
        if "geocode" in url:
            return GEOCODER_PAYLOAD
        if "key" in params:
            raise _InvalidCensusApiKeyError("bad key")
        return [ACS_HEADERS, ACS_ROW]

    monkeypatch.setattr(enricher, "_request_json", fake_request)
    result = await enricher.enrich({"full_address": "100 Main St", "country": "US"})
    assert result["status"] == "success"
    assert any("key rejected" in warning.lower() for warning in result["quality"]["warnings"])
    assert any("key" in call for call in calls)
