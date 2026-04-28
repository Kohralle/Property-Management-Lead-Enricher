from __future__ import annotations

import json
import re
from textwrap import shorten

from pydantic import BaseModel, Field, ValidationError

from leads.enrichment.llm.client import call_claude

_SYSTEM_PROMPT = """You are a sales writing assistant for EliseAI lead enrichment.
EliseAI provides conversational AI for multifamily leasing, maintenance, and resident communications.
It helps operators respond faster, streamline follow-up, and cut lead-to-lease time.
Be concrete, concise, and grounded in the provided enrichment.
Write like a sharp account executive with a real point of view, not a generic SDR template.
The writing should sound natural, specific, and human.
Return only the requested plain-text sections. Do not use markdown fences."""

_USER_TEMPLATE = """You are writing outbound material for an EliseAI sales lead.

Lead profile:
{profile_json}

Scoring context:
{score_json}

Instructions for the email:
- Calibrate tone using the score and tier:
  - A-tier: high-effort, personalized, sharper relevance
  - B-tier: personalized but moderate effort
  - C-tier: lighter touch
  - D-tier: still professional, but minimal stretch
- Start with a brief weather or market opener in exactly 1 sentence.
- Reference one specific company-relevant fact from the enrichment, such as a news item, company background, or local operating context.
- Pitch EliseAI in 1-2 sentences tied to the lead's likely operating or leasing pain.
- Close with a low-friction CTA asking about 15 minutes next week.
- Keep the full email body under 120 words total.
- The email must include at least two concrete details from the profile across the opener, fact reference, or pain point.
- Use the company name naturally at least once.
- If relevant news exists, prefer that over generic company description.
- If no relevant news exists, use grounded company research or geo-demographic context instead of inventing a hook.
- Vary sentence length. One sentence can be short. Another can carry more detail.
- It is fine to sound slightly conversational as long as the note stays professional.
- Favor crisp specifics over polished marketing language.
- Use plainspoken phrasing a human AE would actually send.
- Avoid generic filler such as:
  - "I came across your company"
  - "wanted to reach out"
  - "thought I'd connect"
  - "hope you're doing well"
  - "just checking in"
  - "touching base"
- Avoid sounding overly polished, overly cheerful, or copy-pasted.
- Avoid stacked buzzwords, canned compliments, and empty personalization.
- Do not use vague claims like "could help streamline operations" unless you tie them to a specific likely pain from the profile.
- Do not mention data sources, enrichment, scoring, or that an AI generated the draft.
- If the available facts are thin, keep the note simple rather than making the personalization feel forced.
- The goal is a believable, specific outbound email that sounds like it was written by a thoughtful human in one pass.

Return exactly this format:
EMAIL_SUBJECT: <subject line>
EMAIL_BODY: <single-paragraph email body with no line breaks>

Do not return JSON.
Do not use markdown code fences.
"""

_FORMAT_RETRY_REMINDER = """

IMPORTANT:
- Follow the exact two-section format.
- Keep EMAIL_BODY on one line only.
- Do not return JSON.
- Do not add commentary before or after the sections.
"""


class GeneratedEmail(BaseModel):
    email_subject: str = Field(min_length=3)
    email_body: str = Field(min_length=40)


def _first_sentence(text: str) -> str:
    cleaned = " ".join((text or "").split())
    if not cleaned:
        return ""
    for marker in (". ", "! ", "? "):
        if marker in cleaned:
            return cleaned.split(marker, 1)[0].strip() + marker.strip()
    return cleaned


def _fallback_lines(parsed_lead: dict, enrichment: dict, score: dict) -> tuple[str, str, list[str]]:
    company = parsed_lead.get("company") or "your team"
    city = parsed_lead.get("city") or ""
    state = parsed_lead.get("state") or ""
    location = ", ".join(part for part in (city, state) if part)
    tier = (score or {}).get("score_tier") or "C"

    company_research = enrichment.get("company_research") or {}
    description = _first_sentence(company_research.get("description") or "")
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

    opener_bits = []
    if location:
        opener_bits.append(location)
    if renter_pct is not None:
        opener_bits.append(f"{round(renter_pct)}% renter occupied")
    elif median_rent is not None:
        opener_bits.append(f"median rent around ${int(median_rent):,}")

    opener = "The local market looks active."
    if opener_bits:
        opener = f"{' | '.join(opener_bits)} is an interesting operating backdrop."

    if news_hook:
        fact_line = f"I noticed {news_hook}"
    elif description:
        fact_line = description
    elif company_type != "unknown":
        fact_line = f"{company} appears to be a {company_type} business with {scale_signal} scale."
    else:
        fact_line = f"I took a look at {company}'s footprint and local context."

    pain_line = (
        "EliseAI tends to be most useful when leasing follow-up, resident communication, and maintenance volume start competing for the same team's time."
    )
    if tier == "A":
        pain_line = (
            "EliseAI helps multifamily teams handle leasing follow-up, maintenance intake, and resident communication without adding more manual back-and-forth."
        )

    body = " ".join(
        part
        for part in [
            opener,
            fact_line,
            pain_line,
            "Open to 15 minutes next week to compare notes?",
        ]
        if part
    ).strip()

    subject = f"{company} + EliseAI"
    insights = [
        f"Type: {company_type}",
        f"Scale: {scale_signal}",
        f"Email domain: {email_domain_type}",
        f"Local population: {int(population):,}" if population is not None else "Local population: unknown",
        f"Median rent: ${int(median_rent):,}" if median_rent is not None else "Median rent: unknown",
    ]
    return subject, shorten(body, width=120, placeholder="..."), insights[:5]


def build_fallback_email_and_insights(parsed_lead: dict, enrichment: dict, score: dict) -> dict:
    subject, body, insights = _fallback_lines(parsed_lead, enrichment, score)
    return {
        "email_subject": subject,
        "email_body": body,
        "insights": insights,
    }


def _fallback_insights(parsed_lead: dict, enrichment: dict, score: dict) -> list[str]:
    return build_fallback_email_and_insights(parsed_lead, enrichment, score)["insights"]


def _parse_tagged_output(text: str) -> dict:
    cleaned = (text or "").strip()
    cleaned = re.sub(r"^```(?:text)?\s*", "", cleaned)
    cleaned = re.sub(r"\s*```$", "", cleaned).strip()

    subject_match = re.search(r"^EMAIL_SUBJECT:\s*(.+)$", cleaned, re.MULTILINE)
    body_match = re.search(r"^EMAIL_BODY:\s*(.+)$", cleaned, re.MULTILINE)
    if not subject_match or not body_match:
        raise ValueError("Missing EMAIL_SUBJECT or EMAIL_BODY section.")

    payload = {
        "email_subject": subject_match.group(1).strip(),
        "email_body": body_match.group(1).strip(),
    }
    return GeneratedEmail.model_validate(payload).model_dump()


def _resolved_profile(parsed_lead: dict, enrichment: dict, score: dict) -> dict:
    return {
        "parsed_lead": parsed_lead,
        "company_research": enrichment.get("company_research"),
        "relevant_news_articles": _relevant_articles(enrichment),
        "news_analysis": enrichment.get("news_analysis"),
        "geo_demographics": enrichment.get("geo_demographics") or enrichment.get("market_data") or enrichment.get("census"),
        "weather": enrichment.get("weather") or enrichment.get("current_weather"),
        "score": score,
    }


def _relevant_articles(enrichment: dict) -> list[dict]:
    articles = enrichment.get("news_articles") or enrichment.get("articles") or []
    relevance_flags = enrichment.get("news_relevance") or []

    if relevance_flags and len(relevance_flags) == len(articles):
        return [article for article, is_relevant in zip(articles, relevance_flags) if is_relevant]

    return [article for article in articles if article.get("relevant") is True]


def _normalize_output(result: dict) -> dict:
    insights = [str(item).strip() for item in result.get("insights") or [] if str(item).strip()]
    return {
        "email_subject": str(result["email_subject"]).strip(),
        "email_body": str(result["email_body"]).strip(),
        "insights": insights,
    }


async def generate_email_and_insights(
    parsed_lead: dict,
    enrichment: dict,
    score: dict,
) -> dict:
    """Single LLM call returns email_subject, email_body, and 4-6 insight bullets."""
    profile = _resolved_profile(parsed_lead, enrichment, score)
    base_user = _USER_TEMPLATE.format(
        profile_json=json.dumps(profile, indent=2, sort_keys=True),
        score_json=json.dumps(score, indent=2, sort_keys=True),
    )

    attempts = [
        base_user,
        base_user + _FORMAT_RETRY_REMINDER,
    ]
    last_error: Exception | None = None

    for user_message in attempts:
        text = await call_claude(
            system=_SYSTEM_PROMPT,
            user=user_message,
            response_model=None,
            max_tokens=900,
        )
        try:
            parsed_output = _parse_tagged_output(str(text))
            parsed_output["insights"] = _fallback_insights(parsed_lead, enrichment, score)
            return _normalize_output(parsed_output)
        except (ValueError, ValidationError) as exc:
            last_error = exc

    assert last_error is not None
    raise last_error
