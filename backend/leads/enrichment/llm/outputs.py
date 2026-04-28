from __future__ import annotations

import json
from textwrap import shorten

from leads.enrichment.llm.client import call_gemini

_SYSTEM_PROMPT = """You are a sales assistant for EliseAI, which sells conversational AI to multifamily property management companies. EliseAI automates leasing follow-up, maintenance intake, and resident communication — helping operators respond faster and handle more volume without adding headcount.

Tailor the pitch to the company's profile:
- Large property manager: lead with handling leasing and maintenance volume at scale across a large portfolio
- Small property manager or owner-operator: lead with doing more with a lean team — AI covers after-hours inquiries and follow-up so nothing falls through the cracks
- Company with recent growth news: lead with scaling operations without proportional headcount growth
- High renter-occupied market (>60% renter share): lead with leasing speed and response time in a competitive rental environment

Write a short outbound sales email under 120 words. Return plain text only — no JSON, no markdown."""

_USER_TEMPLATE = """Lead profile:
{profile_json}

Write the email body only. Plain text, under 120 words."""


def _resolved_profile(parsed_lead: dict, enrichment: dict, score: dict) -> dict:
    return {
        "name": parsed_lead.get("name"),
        "company": parsed_lead.get("company"),
        "email": parsed_lead.get("email"),
        "city": parsed_lead.get("city"),
        "state": parsed_lead.get("state"),
        "score_tier": score.get("score_tier"),
        "company_research": enrichment.get("company_research"),
        "relevant_news": _relevant_articles(enrichment),
        "geo_demographics": enrichment.get("geo_demographics"),
        "weather": enrichment.get("weather"),
    }


def _relevant_articles(enrichment: dict) -> list[dict]:
    articles = enrichment.get("news_articles") or []
    relevance_flags = enrichment.get("news_relevance") or []
    if relevance_flags and len(relevance_flags) == len(articles):
        return [a for a, flag in zip(articles, relevance_flags) if flag]
    return [a for a in articles if a.get("relevant") is True]


def _first_sentence(text: str) -> str:
    cleaned = " ".join((text or "").split())
    for marker in (". ", "! ", "? "):
        if marker in cleaned:
            return cleaned.split(marker, 1)[0].strip() + marker.strip()
    return cleaned


def build_fallback_email_and_insights(parsed_lead: dict, enrichment: dict, score: dict) -> dict:
    company = parsed_lead.get("company") or "your team"
    city = parsed_lead.get("city") or ""
    state = parsed_lead.get("state") or ""
    tier = (score or {}).get("score_tier") or "C"

    company_research = enrichment.get("company_research") or {}
    company_type = str(company_research.get("company_type") or "unknown").replace("_", " ")
    scale_signal = str(company_research.get("scale_signal") or "unknown")
    email_domain_type = str(company_research.get("email_domain_type") or "unknown")

    geo = enrichment.get("geo_demographics") or {}
    housing = geo.get("housing") or {}
    demographics = geo.get("demographics") or {}
    median_rent = housing.get("median_gross_rent")
    renter_pct = housing.get("renter_occupied_pct")
    population = demographics.get("total_population")

    relevant_articles = _relevant_articles(enrichment)
    news_hook = ""
    if relevant_articles:
        news_hook = shorten((relevant_articles[0].get("title") or "").strip(), width=110, placeholder="...")

    location = ", ".join(p for p in (city, state) if p)
    opener_bits = []
    if location:
        opener_bits.append(location)
    if renter_pct is not None:
        opener_bits.append(f"{round(renter_pct)}% renter occupied")
    elif median_rent is not None:
        opener_bits.append(f"median rent around ${int(median_rent):,}")

    opener = f"{' | '.join(opener_bits)} is an interesting operating backdrop." if opener_bits else "The local market looks active."

    if news_hook:
        fact_line = f"I noticed {news_hook}"
    elif _first_sentence(company_research.get("description") or ""):
        fact_line = _first_sentence(company_research.get("description") or "")
    else:
        fact_line = f"I took a look at {company}'s footprint and local context."

    pain_line = (
        "EliseAI helps multifamily teams handle leasing follow-up, maintenance intake, and resident communication without adding more manual back-and-forth."
        if tier == "A" else
        "EliseAI tends to be most useful when leasing follow-up, resident communication, and maintenance volume start competing for the same team's time."
    )

    body = " ".join(p for p in [opener, fact_line, pain_line, "Open to 15 minutes next week to compare notes?"] if p)

    return {
        "email_subject": f"{company} + EliseAI",
        "email_body": body,
        "insights": [
            f"Type: {company_type}",
            f"Scale: {scale_signal}",
            f"Email domain: {email_domain_type}",
            f"Local population: {int(population):,}" if population is not None else "Local population: unknown",
            f"Median rent: ${int(median_rent):,}" if median_rent is not None else "Median rent: unknown",
        ],
    }


async def generate_email_and_insights(
    parsed_lead: dict,
    enrichment: dict,
    score: dict,
) -> dict:
    profile = _resolved_profile(parsed_lead, enrichment, score)
    company = parsed_lead.get("company") or "your company"

    body = await call_gemini(
        system=_SYSTEM_PROMPT,
        user=_USER_TEMPLATE.format(profile_json=json.dumps(profile, indent=2, sort_keys=True)),
        response_model=None,
        max_tokens=512,
    )

    return {
        "email_subject": f"EliseAI + {company}",
        "email_body": str(body).strip(),
        "insights": _fallback_insights(parsed_lead, enrichment, score),
    }
