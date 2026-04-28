from __future__ import annotations

import math

_LOCAL_POPULATION_THRESHOLD = 4000


def _rule(rule: str, fired: bool, points: int) -> dict:
    return {
        "rule": rule,
        "fired": fired,
        "points": points if fired else 0,
    }


def _sum_points(breakdown: list[dict]) -> int:
    return sum(item["points"] for item in breakdown)


def _relevant_articles(enrichment: dict) -> list[dict]:
    articles = enrichment.get("news_articles") or enrichment.get("articles") or []
    news_analysis = enrichment.get("news_analysis") or {}
    relevance_flags = news_analysis.get("news_relevance") or enrichment.get("news_relevance") or []

    if relevance_flags and len(relevance_flags) == len(articles):
        return [article for article, is_relevant in zip(articles, relevance_flags) if is_relevant]

    return [article for article in articles if article.get("relevant") is True]


def score_company_fit_hard(enrichment: dict) -> dict:
    """Returns {points: int, breakdown: list[{rule, fired, points}]}. Total max 52."""
    company_research = enrichment.get("company_research") or {}
    score = int(company_research.get("company_score") or 0)
    breakdown = list(company_research.get("score_components") or [])
    return {"points": score, "breakdown": breakdown}


def score_company_fit_activity(enrichment: dict) -> dict:
    """Max 18. Only counts LLM-filtered relevant articles."""
    news_analysis = enrichment.get("news_analysis") or {}
    articles = list(enrichment.get("news_articles") or enrichment.get("articles") or [])
    relevance_flags = list(news_analysis.get("news_relevance") or enrichment.get("news_relevance") or [])
    growth_flags = list(news_analysis.get("growth_flags") or enrichment.get("news_growth_flags") or [])

    relevant_count = sum(1 for flag in relevance_flags if flag)
    article_count = max(len(articles), len(relevance_flags))
    if article_count >= 10:
        relevant_threshold = 3
    elif article_count > 0:
        relevant_threshold = max(1, math.ceil(article_count * 0.3))
    else:
        relevant_threshold = 3

    recent_relevant = article_count > 0 and relevant_count >= relevant_threshold
    growth_signal = recent_relevant and any(flag for flag in growth_flags)

    breakdown = [
        _rule("recent_relevant_news", recent_relevant, 8),
        _rule("growth_signal_news", growth_signal, 10),
    ]
    return {"points": _sum_points(breakdown), "breakdown": breakdown}


def score_contact_quality(parsed: dict, company_research: dict | None = None) -> dict:
    """Max 12."""
    # Prefer email_domain_type from company research if available
    email_is_corporate = False
    if company_research and company_research.get("email_domain_type") == "corporate":
        email_is_corporate = True
    else:
        # Fallback: check if it's not a free email provider
        email_is_corporate = not bool(parsed.get("is_free_email_provider"))

    breakdown = [
        _rule("email_domain_type_corporate", email_is_corporate, 12),
    ]
    return {"points": _sum_points(breakdown), "breakdown": breakdown}


def score_market_context(enrichment: dict) -> dict:
    """Max 18."""
    market = enrichment.get("geo_demographics") or enrichment.get("market_data") or enrichment.get("census") or {}
    if market.get("status") == "success":
        renter_percentage = ((market.get("housing") or {}).get("renter_occupied_pct"))
        population = ((market.get("demographics") or {}).get("total_population"))
        median_rent = ((market.get("housing") or {}).get("median_gross_rent"))
    else:
        renter_percentage = market.get("renter_percentage")
        population = market.get("population")
        median_rent = market.get("median_rent")

    breakdown = [
        _rule("renter_pct_over_40", renter_percentage is not None and renter_percentage > 40, 6),
        # This is now tract-level Census data, so a city-scale 100k threshold would almost never fire.
        _rule("local_population_over_4k", population is not None and population > _LOCAL_POPULATION_THRESHOLD, 6),
        _rule("median_rent_over_1500", median_rent is not None and median_rent > 1500, 6),
    ]
    return {"points": _sum_points(breakdown), "breakdown": breakdown}


def derive_tier(total_score: int) -> str:
    """Tier thresholds on the deterministic 100-point scale."""
    if total_score >= 85:
        return "A"
    if total_score >= 65:
        return "B"
    if total_score >= 40:
        return "C"
    return "D"
