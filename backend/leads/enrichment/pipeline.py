from __future__ import annotations

import asyncio
import logging
from typing import Optional

from leads.enrichment.company_web_enrichment import enrich_company
from leads.enrichment.llm.outputs import (
    build_fallback_email_and_insights,
    generate_email_and_insights,
)
from leads.enrichment.scoring.news_judgment import llm_news_judgment
from leads.enrichment.scoring.rules import (
    derive_tier,
    score_company_fit_activity,
    score_company_fit_hard,
    score_contact_quality,
    score_market_context,
)
from leads.enrichment.services import census, news, weather
from leads.enrichment.services.parsing import parse_lead
from leads.models import EnrichmentResult, Person

logger = logging.getLogger(__name__)


def _lead_context(lead: Person) -> dict:
    building = lead.building
    return {
        "name": lead.name,
        "company": lead.company,
        "email": lead.email,
        "city": getattr(building, "city", ""),
        "state": getattr(building, "state", ""),
        "property_address": getattr(building, "property_address", ""),
        "country": getattr(building, "country", ""),
    }


def _error_bucket(raw_enrichment: dict) -> list[dict]:
    return raw_enrichment.setdefault("_errors", [])


def _record_error(raw_enrichment: dict, step: str, exc: Exception) -> None:
    logger.exception("enrichment step failed: %s", step, exc_info=exc)
    _error_bucket(raw_enrichment).append(
        {
            "step": step,
            "error": exc.__class__.__name__,
            "message": str(exc),
        }
    )


async def _run_step(raw_enrichment: dict, step: str, func, *args, default=None, **kwargs):
    try:
        return await func(*args, **kwargs)
    except Exception as exc:
        _record_error(raw_enrichment, step, exc)
        return default


def _breakdown_dict(*sections: tuple[str, dict]) -> dict:
    return {name: payload for name, payload in sections}


async def enrich_person(lead: Person) -> EnrichmentResult:
    raw_enrichment: dict = {}
    parsed_lead: dict = {}
    lead_context = _lead_context(lead)
    company_research: dict = {}
    news_articles: list[dict] = []
    weather_data: Optional[dict] = None
    geo_demographics: Optional[dict] = None
    news_analysis: dict = {
        "articles": [],
        "news_relevance": [],
        "growth_flags": [],
    }
    generated: dict = {
        "email_subject": "",
        "email_body": "",
        "insights": [],
    }

    try:
        parsed_lead = parse_lead(lead)
        parsed_lead.update(lead_context)
        raw_enrichment["parsed_lead"] = parsed_lead
    except Exception as exc:
        _record_error(raw_enrichment, "parse_lead", exc)
        parsed_lead = dict(lead_context)
        parsed_lead.setdefault("company_query_variants", [])
        raw_enrichment["parsed_lead"] = parsed_lead

    try:
        (
            company_research,
            news_articles,
            weather_data,
            geo_demographics,
        ) = await asyncio.gather(
            _run_step(
                raw_enrichment,
                "company_web_enrichment.enrich_company",
                enrich_company,
                parsed_lead.get("company", ""),
                parsed_lead.get("email_domain"),
                default={},
            ),
            _run_step(
                raw_enrichment,
                "news.search_articles",
                news.search_articles,
                parsed_lead.get("company", ""),
                default=[],
            ),
            _run_step(
                raw_enrichment,
                "weather.fetch_current",
                weather.fetch_current,
                parsed_lead.get("city", ""),
                parsed_lead.get("state", ""),
                default=None,
            ),
            _run_step(
                raw_enrichment,
                "census.enrich_geo_demographics",
                census.enrich_geo_demographics,
                {
                    **parsed_lead,
                    "property_address": parsed_lead.get("property_address"),
                    "city": parsed_lead.get("city"),
                    "state": parsed_lead.get("state"),
                    "country": parsed_lead.get("country"),
                },
                default=None,
            ),
        )
    except Exception as exc:
        _record_error(raw_enrichment, "candidate_gathering", exc)

    raw_enrichment["company_research"] = company_research
    raw_enrichment["company_enrichment"] = {
        "company_research": company_research,
        "geo_demographics": geo_demographics,
    }
    if company_research.get("fallback_error"):
        _error_bucket(raw_enrichment).append(
            {
                "step": "company_web_enrichment.enrich_company",
                "error": "CompanyResearchFallback",
                "message": str(company_research.get("fallback_error")),
            }
        )
    raw_enrichment["news_articles"] = news_articles
    raw_enrichment["weather"] = weather_data
    raw_enrichment["geo_demographics"] = geo_demographics
    raw_enrichment["market_data"] = geo_demographics

    try:
        news_analysis = await _run_step(
            raw_enrichment,
            "llm_news_judgment",
            llm_news_judgment,
            parsed_lead,
            news_articles[:10],
            default=news_analysis,
        )
    except Exception as exc:
        _record_error(raw_enrichment, "llm_news_judgment_wrapper", exc)

    raw_enrichment["news_analysis"] = news_analysis
    raw_enrichment["news_relevance"] = news_analysis.get("news_relevance") or []
    raw_enrichment["news_growth_flags"] = news_analysis.get("growth_flags") or []

    company_fit_hard = {"points": 0, "breakdown": []}
    company_fit_activity = {"points": 0, "breakdown": []}
    contact_quality = {"points": 0, "breakdown": []}
    market_context = {"points": 0, "breakdown": []}

    try:
        company_fit_hard = score_company_fit_hard(raw_enrichment)
    except Exception as exc:
        _record_error(raw_enrichment, "score_company_fit_hard", exc)
    try:
        company_fit_activity = score_company_fit_activity(raw_enrichment)
    except Exception as exc:
        _record_error(raw_enrichment, "score_company_fit_activity", exc)
    try:
        contact_quality = score_contact_quality(parsed_lead, company_research)
    except Exception as exc:
        _record_error(raw_enrichment, "score_contact_quality", exc)
    try:
        market_context = score_market_context(raw_enrichment)
    except Exception as exc:
        _record_error(raw_enrichment, "score_market_context", exc)

    rule_total = (
        company_fit_hard["points"]
        + company_fit_activity["points"]
        + contact_quality["points"]
        + market_context["points"]
    )
    grand_total = rule_total
    score_tier = derive_tier(grand_total)

    score = {
        "total_score": grand_total,
        "score_tier": score_tier,
        "score_breakdown": _breakdown_dict(
            ("company_fit_hard", company_fit_hard),
            ("company_fit_activity", company_fit_activity),
            ("contact_quality", contact_quality),
            ("market_context", market_context),
        ),
    }
    raw_enrichment["score"] = score

    try:
        generated = await _run_step(
            raw_enrichment,
            "generate_email_and_insights",
            generate_email_and_insights,
            parsed_lead,
            raw_enrichment,
            score,
            default=generated,
        )
    except Exception as exc:
        _record_error(raw_enrichment, "generate_email_and_insights_wrapper", exc)

    if not generated.get("email_subject") or not generated.get("email_body"):
        generated = build_fallback_email_and_insights(parsed_lead, raw_enrichment, score)
        raw_enrichment["generated_output_fallback"] = True

    raw_enrichment["generated_output"] = generated

    return await EnrichmentResult.objects.acreate(
        lead=lead,
        score_total=grand_total,
        score_tier=score_tier,
        score_breakdown=score["score_breakdown"],
        email_subject=generated.get("email_subject", ""),
        email_body=generated.get("email_body", ""),
        insights=generated.get("insights", []),
        raw_enrichment=raw_enrichment,
        disqualifier_flag=False,
        disqualifier_reason="",
        llm_reasoning="",
    )
