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

Generate components, not the full final email.

Instructions:
- Calibrate tone using the score and tier:
  - A-tier: high-effort, personalized, sharper relevance
  - B-tier: personalized but moderate effort
  - C-tier: lighter touch
  - D-tier: still professional, but minimal stretch
- OPENER must be exactly 1 sentence and use weather or market context.
- FACT must be exactly 1 sentence and reference one specific company-relevant fact from the enrichment.
- PAIN must be exactly 1 sentence and tie EliseAI to a likely operating, leasing, maintenance, or resident-communication pain.
- CTA must be exactly 1 sentence and ask about 15 minutes next week.
- Across OPENER, FACT, and PAIN, include at least two concrete details from the profile.
- Use the company name naturally at least once somewhere in FACT or PAIN.
- If relevant news exists, prefer that over generic company description.
- If no relevant news exists, use grounded company research or geo-demographic context instead of inventing a hook.
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
- Do not mention data sources, enrichment, scoring, or that an AI generated the draft.
- If the available facts are thin, keep the lines simple rather than forcing personalization.

Return exactly this format:
EMAIL_SUBJECT: <subject line>
OPENER: <one sentence>
FACT: <one sentence>
PAIN: <one sentence>
CTA: <one sentence>

Do not return JSON.
Do not use markdown code fences.
"""

_FORMAT_RETRY_REMINDER = """

IMPORTANT:
- Follow the exact five-section format.
- Every section must be present exactly once.
- OPENER, FACT, PAIN, and CTA must each be one sentence.
- Do not return JSON.
- Do not add commentary before or after the sections.
"""


class GeneratedEmail(BaseModel):
    email_subject: str = Field(min_length=3)
    email_body: str = Field(min_length=40)


class GeneratedComponents(BaseModel):
    email_subject: str = Field(min_length=3)
    opener: str = Field(min_length=8)
    fact: str = Field(min_length=12)
    pain: str = Field(min_length=12)
    cta: str = Field(min_length=12)


def _validate_email_quality(parsed_lead: dict, payload: dict) -> dict:
    subject = str(payload.get("email_subject") or "").strip()
    body = str(payload.get("email_body") or "").strip()
    company = str(parsed_lead.get("company") or "").strip()
    word_count = len(body.split())

    sentence_markers = body.count(".") + body.count("!") + body.count("?")
    has_cta = any(
        phrase in body.lower()
        for phrase in (
            "15 minutes",
            "15 minute",
            "next week",
            "open to",
            "worth a conversation",
            "compare notes",
            "chat next week",
        )
    )
    mentions_company = not company or company.lower() in body.lower() or company.lower() in subject.lower()

    if len(body) < 80:
        raise ValueError("Generated email body is too short.")
    if sentence_markers < 2:
        raise ValueError("Generated email body is too thin.")
    if word_count > 120:
        raise ValueError("Generated email body is too long.")
    if not has_cta:
        raise ValueError("Generated email body is missing a CTA.")
    if not mentions_company:
        raise ValueError("Generated email does not mention the company.")

    return {
        "email_subject": subject,
        "email_body": body,
    }


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


def _parse_component_output(text: str) -> dict:
    cleaned = (text or "").strip()
    cleaned = re.sub(r"^```(?:text)?\s*", "", cleaned)
    cleaned = re.sub(r"\s*```$", "", cleaned).strip()
    normalized = cleaned.replace("\r\n", "\n")

    def match_field(*names: str) -> str:
        pattern = rf"(?:^|\n)\s*(?:{'|'.join(names)})\s*:\s*(.+?)(?=\n\s*(?:EMAIL_SUBJECT|SUBJECT|OPENER|FACT|PAIN|CTA)\s*:|\Z)"
        match = re.search(pattern, normalized, re.IGNORECASE | re.DOTALL)
        return " ".join(match.group(1).split()).strip() if match else ""

    payload = {
        "email_subject": match_field("EMAIL_SUBJECT", "SUBJECT"),
        "opener": match_field("OPENER"),
        "fact": match_field("FACT"),
        "pain": match_field("PAIN"),
        "cta": match_field("CTA"),
    }

    if not all(payload.values()):
        body_match = re.search(
            r"(?:^|\n)\s*(?:EMAIL_BODY|BODY)\s*:\s*(.+?)\s*\Z",
            normalized,
            re.IGNORECASE | re.DOTALL,
        )
        if payload["email_subject"] and body_match:
            body_text = " ".join(body_match.group(1).split()).strip()
            sentences = re.findall(r"[^.!?]+[.!?]", body_text)
            sentences = [" ".join(sentence.split()).strip() for sentence in sentences if sentence.strip()]
            if len(sentences) >= 3:
                cta_sentence = sentences[-1]
                body_middle = sentences[2:-1]
                payload = {
                    "email_subject": payload["email_subject"],
                    "opener": sentences[0],
                    "fact": sentences[1],
                    "pain": " ".join(body_middle).strip() or sentences[2],
                    "cta": cta_sentence,
                }

    if not all(payload.values()):
        raise ValueError("Missing one or more email component sections.")

    return GeneratedComponents.model_validate(payload).model_dump()


def _compose_email(components: dict) -> dict:
    body = " ".join(
        part.strip()
        for part in (
            components.get("opener") or "",
            components.get("fact") or "",
            components.get("pain") or "",
            components.get("cta") or "",
        )
        if part and part.strip()
    ).strip()
    return {
        "email_subject": str(components.get("email_subject") or "").strip(),
        "email_body": body,
    }


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
    """Generate email components with the LLM, then compose the final draft deterministically."""
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
            parsed_components = _parse_component_output(str(text))
            parsed_output = _compose_email(parsed_components)
            parsed_output = _validate_email_quality(parsed_lead, parsed_output)
            parsed_output["insights"] = _fallback_insights(parsed_lead, enrichment, score)
            return _normalize_output(parsed_output)
        except (ValueError, ValidationError) as exc:
            last_error = exc

    assert last_error is not None
    raise last_error
