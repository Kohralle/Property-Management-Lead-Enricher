import pytest

from leads.enrichment.llm import outputs
from leads.enrichment.llm.outputs import (
    _parse_tagged_output,
    build_fallback_email_and_insights,
    generate_email_and_insights,
)


def test_build_fallback_email_and_insights_returns_usable_payload():
    parsed_lead = {
        "company": "Bozzuto",
        "city": "Arlington",
        "state": "VA",
    }
    enrichment = {
        "company_research": {
            "description": "Bozzuto is a multifamily owner, developer, and operator.",
            "company_type": "owner_operator",
            "scale_signal": "large",
            "email_domain_type": "corporate",
        },
        "geo_demographics": {
            "demographics": {"total_population": 5100},
            "housing": {
                "median_gross_rent": 2450,
                "renter_occupied_pct": 61.8,
            },
        },
        "news_articles": [],
        "news_relevance": [],
    }
    score = {"score_tier": "A"}

    result = build_fallback_email_and_insights(parsed_lead, enrichment, score)

    assert result["email_subject"]
    assert result["email_body"]
    assert "Bozzuto" in result["email_subject"] or "Bozzuto" in result["email_body"]
    assert len(result["insights"]) >= 4


def test_parse_tagged_output_returns_valid_payload():
    text = """EMAIL_SUBJECT: Tripalink + EliseAI
EMAIL_BODY: Seattle looks tight on renter inventory, and Tripalink is clearly operating at meaningful scale. Curious if a 15 minute compare-notes chat next week is worth it.
"""

    result = _parse_tagged_output(text)

    assert result["email_subject"] == "Tripalink + EliseAI"
    assert "Tripalink" in result["email_body"]


@pytest.mark.asyncio
async def test_generate_email_and_insights_retries_on_parse_failure(monkeypatch):
    calls = []

    async def fake_call_claude(system, user, response_model=None, max_tokens=1024):
        calls.append(user)
        if len(calls) == 1:
            return "EMAIL_SUBJECT: bad\nEMAIL_BODY: incomplete"
        return "EMAIL_SUBJECT: Better subject\nEMAIL_BODY: Seattle is still a tight renter market, and Tripalink is clearly expanding. Open to 15 minutes next week?"

    monkeypatch.setattr(outputs, "call_claude", fake_call_claude)

    result = await generate_email_and_insights(
        {"company": "Tripalink", "city": "Seattle", "state": "Washington"},
        {},
        {"score_tier": "A"},
    )

    assert result["email_subject"] == "Better subject"
    assert len(result["insights"]) >= 4
    assert len(calls) == 2
