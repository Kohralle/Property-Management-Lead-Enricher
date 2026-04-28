import pytest

from leads.enrichment.company_web_enrichment import (
    compute_company_score,
    enrich_company,
    parse_gemini_json,
)


def test_scoring_large_property_manager():
    result = compute_company_score({
        "company_type": "large_property_manager",
        "property_management_relevance": "high",
        "multifamily_relevance": "high",
        "scale_signal": "large",
        "email_domain_type": "corporate",
        "confidence": 1.0,
    })
    assert result["company_score"] == 52
    assert result["tier"] == "strong"


def test_scoring_unrelated_company():
    result = compute_company_score({
        "company_type": "unrelated",
        "property_management_relevance": "low",
        "multifamily_relevance": "low",
        "scale_signal": "unknown",
        "email_domain_type": "unknown",
        "confidence": 1.0,
    })
    assert result["company_score"] == 0
    assert result["tier"] == "poor"


def test_generic_email_penalty():
    result = compute_company_score({
        "company_type": "small_property_manager",
        "property_management_relevance": "medium",
        "multifamily_relevance": "medium",
        "scale_signal": "small",
        "email_domain_type": "generic",
        "confidence": 1.0,
    })
    assert result["company_score"] == 28


@pytest.mark.asyncio
async def test_invalid_json_fallback(monkeypatch):
    calls = []

    async def fake_call(prompt: str):
        calls.append(prompt)
        return "not json", None, []

    monkeypatch.setattr(
        "leads.enrichment.company_web_enrichment.call_gemini_grounded_search",
        fake_call,
    )

    result = await enrich_company("Acme Properties", "contact@acme.com")
    assert result["company_type"] == "unknown"
    assert result["recommended_next_step"] == "manual_review"
    assert result["company_score"] == 2
    assert result["fallback_error"]
    assert len(calls) == 2


def test_confidence_multiplier():
    result = compute_company_score({
        "company_type": "owner_operator",
        "property_management_relevance": "high",
        "multifamily_relevance": "high",
        "scale_signal": "medium",
        "email_domain_type": "corporate",
        "confidence": 0.5,
    })
    assert result["company_score"] == 21
    assert result["tier"] == "weak"


def test_score_clamping_at_45():
    result = compute_company_score({
        "company_type": "large_property_manager",
        "property_management_relevance": "high",
        "multifamily_relevance": "high",
        "scale_signal": "large",
        "email_domain_type": "corporate",
        "confidence": 1.0,
    })
    assert result["company_score"] == 52


def test_parse_gemini_json_extracts_object_from_wrapped_text():
    payload = parse_gemini_json('Here is the result:\n```json\n{"company_type":"owner_operator","confidence":0.9}\n```')
    assert payload == {"company_type": "owner_operator", "confidence": 0.9}
