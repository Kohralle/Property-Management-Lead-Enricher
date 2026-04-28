from leads.enrichment.scoring.rules import (
    derive_tier,
    score_company_fit_activity,
    score_company_fit_hard,
    score_contact_quality,
    score_market_context,
)


def test_score_company_fit_hard_high_score_case():
    enrichment = {
        "company_research": {
            "company_score": 52,
            "score_components": [
                {"rule": "company_type_large_property_manager", "fired": True, "points": 38},
                {"rule": "property_management_relevance_high", "fired": True, "points": 5},
                {"rule": "multifamily_relevance_high", "fired": True, "points": 3},
                {"rule": "scale_signal_large", "fired": True, "points": 3},
                {"rule": "email_domain_type_corporate", "fired": True, "points": 3},
                {"rule": "confidence_multiplier", "fired": True, "points": 0},
            ],
        },
    }

    result = score_company_fit_hard(enrichment)

    assert result["points"] == 52
    assert all(item["fired"] for item in result["breakdown"])


def test_score_company_fit_hard_zero_score_case():
    result = score_company_fit_hard({})
    assert result["points"] == 0
    assert not any(item["fired"] for item in result["breakdown"])


def test_score_company_fit_activity_high_score_case():
    enrichment = {
        "news_articles": [
            {"title": f"Article {idx}", "snippet": "Coverage."}
            for idx in range(1, 11)
        ],
        "news_analysis": {
            "news_relevance": [True, True, True, False, False, False, False, False, False, False],
            "growth_flags": [False, False, True, False, False, False, False, False, False, False],
        },
    }

    result = score_company_fit_activity(enrichment)

    assert result["points"] == 18
    assert all(item["fired"] for item in result["breakdown"])


def test_score_company_fit_activity_zero_score_case():
    result = score_company_fit_activity({"news_articles": [], "news_analysis": {"news_relevance": [], "growth_flags": []}})
    assert result["points"] == 0
    assert not any(item["fired"] for item in result["breakdown"])


def test_score_company_fit_activity_uses_thirty_percent_threshold_when_under_ten_articles():
    enrichment = {
        "news_articles": [
            {"title": f"Article {idx}", "snippet": "Coverage."}
            for idx in range(1, 8)
        ],
        "news_analysis": {
            "news_relevance": [True, True, True, False, False, False, False],
            "growth_flags": [False, False, True, False, False, False, False],
        },
    }

    result = score_company_fit_activity(enrichment)

    assert result["points"] == 18
    assert all(item["fired"] for item in result["breakdown"])


def test_score_contact_quality_high_score_case():
    parsed = {
        "is_free_email_provider": False,
    }
    result = score_contact_quality(parsed)
    assert result["points"] == 12
    assert all(item["fired"] for item in result["breakdown"])


def test_score_contact_quality_zero_score_case():
    parsed = {
        "is_free_email_provider": True,
    }
    result = score_contact_quality(parsed)
    assert result["points"] == 0
    assert not any(item["fired"] for item in result["breakdown"])


def test_score_market_context_high_score_case():
    enrichment = {
        "geo_demographics": {
            "status": "success",
            "demographics": {"total_population": 5200},
            "housing": {
                "renter_occupied_pct": 52.4,
                "median_gross_rent": 2100,
            },
        },
    }
    result = score_market_context(enrichment)
    assert result["points"] == 18
    assert all(item["fired"] for item in result["breakdown"])


def test_score_market_context_zero_score_case():
    enrichment = {
        "geo_demographics": {
            "status": "success",
            "demographics": {"total_population": 2500},
            "housing": {
                "renter_occupied_pct": 20.0,
                "median_gross_rent": 1200,
            },
        },
    }
    result = score_market_context(enrichment)
    assert result["points"] == 0
    assert not any(item["fired"] for item in result["breakdown"])


def test_derive_tier_thresholds():
    assert derive_tier(85) == "A"
    assert derive_tier(65) == "B"
    assert derive_tier(40) == "C"
    assert derive_tier(20) == "D"
