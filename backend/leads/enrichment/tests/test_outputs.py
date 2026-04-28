import pytest

from leads.enrichment.llm import outputs
from leads.enrichment.llm.outputs import (
    _compose_email,
    _parse_component_output,
    _validate_email_quality,
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


def test_parse_component_output_returns_valid_payload():
    text = """EMAIL_SUBJECT: Tripalink + EliseAI
OPENER: Seattle still looks like a renter-heavy market.
FACT: Tripalink is operating at meaningful scale in student and multifamily housing.
PAIN: EliseAI could help Tripalink keep leasing follow-up and resident communication from turning into manual back-and-forth.
CTA: Open to 15 minutes next week to compare notes?
"""

    result = _parse_component_output(text)

    assert result["email_subject"] == "Tripalink + EliseAI"
    assert "Tripalink" in result["fact"]


def test_parse_component_output_accepts_loose_labels():
    text = """Subject: Tripalink and EliseAI
Opener: Seattle still looks renter-heavy.
Fact: Tripalink seems to be operating at real scale, especially around student housing.
Pain: EliseAI could help the team move faster on leasing follow-up without adding manual work.
Cta: Open to 15 minutes next week?
"""

    result = _parse_component_output(text)

    assert result["email_subject"] == "Tripalink and EliseAI"
    assert "Tripalink seems to be operating at real scale" in result["fact"]


def test_parse_component_output_salvages_full_body_format():
    text = """EMAIL_SUBJECT: Tripalink + EliseAI
EMAIL_BODY: Seattle still looks renter-heavy. Tripalink appears to be scaling its student housing footprint. EliseAI could help the team keep leasing follow-up and resident communication from turning into manual back-and-forth. Open to 15 minutes next week?
"""

    result = _parse_component_output(text)

    assert result["opener"] == "Seattle still looks renter-heavy."
    assert "Tripalink appears to be scaling" in result["fact"]
    assert result["cta"] == "Open to 15 minutes next week?"


def test_compose_email_joins_components():
    result = _compose_email(
        {
            "email_subject": "Tripalink and EliseAI",
            "opener": "Seattle still looks renter-heavy.",
            "fact": "Tripalink appears to be operating at real scale.",
            "pain": "EliseAI could help with leasing follow-up and resident communication.",
            "cta": "Open to 15 minutes next week?",
        }
    )

    assert result["email_subject"] == "Tripalink and EliseAI"
    assert "Seattle still looks renter-heavy." in result["email_body"]
    assert result["email_body"].endswith("Open to 15 minutes next week?")


def test_validate_email_quality_rejects_thin_email():
    with pytest.raises(ValueError):
        _validate_email_quality(
            {"company": "Tripalink"},
            {
                "email_subject": "Tripalink's growth",
                "email_body": "It's a mild overcast day in Seattle, Kris.",
            },
        )


@pytest.mark.asyncio
async def test_generate_email_and_insights_retries_on_parse_failure(monkeypatch):
    calls = []

    async def fake_call_claude(system, user, response_model=None, max_tokens=1024):
        calls.append(user)
        if len(calls) == 1:
            return "EMAIL_SUBJECT: bad\nOPENER: incomplete"
        return """EMAIL_SUBJECT: Better subject
OPENER: Seattle is still a tight renter market.
FACT: Tripalink is clearly expanding in student-oriented housing.
PAIN: EliseAI could help Tripalink handle leasing follow-up and resident communication without adding manual back-and-forth.
CTA: Open to 15 minutes next week?
"""

    monkeypatch.setattr(outputs, "call_claude", fake_call_claude)

    result = await generate_email_and_insights(
        {"company": "Tripalink", "city": "Seattle", "state": "Washington"},
        {},
        {"score_tier": "A"},
    )

    assert result["email_subject"] == "Better subject"
    assert len(result["insights"]) >= 4
    assert len(calls) == 2
