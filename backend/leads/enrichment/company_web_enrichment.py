from __future__ import annotations

import asyncio
import json
import logging
import os
import re
from typing import Any
from urllib.parse import urlparse

from leads.enrichment._json import extract_json_object

logger = logging.getLogger(__name__)

_DEFAULT_MODEL = "gemini-2.5-flash"
_MAX_COMPANY_ENRICHMENT_ATTEMPTS = 2
_GENERIC_EMAIL_PROVIDERS = frozenset({
    "gmail.com",
    "yahoo.com",
    "hotmail.com",
    "outlook.com",
    "aol.com",
    "icloud.com",
    "proton.me",
    "protonmail.com",
})
_COMPANY_TYPE_VALUES = {
    "large_property_manager",
    "small_property_manager",
    "owner_operator",
    "property_specific_entity",
    "broker",
    "vendor",
    "unrelated",
    "unknown",
}
_RELEVANCE_VALUES = {"high", "medium", "low", "unknown"}
_SCALE_VALUES = {"large", "medium", "small", "unknown"}
_NEXT_STEP_VALUES = {"prioritize", "enrich_further", "manual_review", "discard"}
_SOURCE_TYPE_VALUES = {"official_website", "linkedin", "property_listing", "news", "directory", "unknown"}
_EMAIL_DOMAIN_TYPE_VALUES = {"corporate", "generic", "property_specific", "unknown"}

_COMPANY_TYPE_BASE = {
    "large_property_manager": 38,
    "small_property_manager": 27,
    "owner_operator": 30,
    "property_specific_entity": 18,
    "broker": 9,
    "vendor": 6,
    "unrelated": 0,
    "unknown": 6,
}
_PROPERTY_MGMT_BONUS = {"high": 8, "medium": 3, "low": 0, "unknown": 0}
_MULTIFAMILY_BONUS = {"high": 3, "medium": 2, "low": 0, "unknown": 0}
_SCALE_BONUS = {"large": 3, "medium": 2, "small": 1, "unknown": 0}

_PROMPT_TEMPLATE = """You are evaluating whether a company is a good property-management lead.

Company:
- Name: {company}
- Email domain: {email_domain}

Research what this company does using Google Search.

Do not score a specific building or property.
Only classify the company itself.

Return JSON only with this exact structure:

{{
  "company_name_normalized": string,
  "website": string | null,
  "description": string,
  "industry": string,
  "company_type": "large_property_manager" | "small_property_manager" | "owner_operator" | "property_specific_entity" | "broker" | "vendor" | "unrelated" | "unknown",
  "property_management_relevance": "high" | "medium" | "low" | "unknown",
  "multifamily_relevance": "high" | "medium" | "low" | "unknown",
  "scale_signal": "large" | "medium" | "small" | "unknown",
  "confidence": number,
  "reasons": string[],
  "evidence": [
    {{
      "claim": string,
      "url": string | null,
      "source_type": "official_website" | "linkedin" | "property_listing" | "news" | "directory" | "unknown"
    }}
  ],
  "recommended_next_step": "prioritize" | "enrich_further" | "manual_review" | "discard"
}}

Rules:
- Return JSON only.
- Do not use markdown.
- Do not include company_score. The code will compute it.
- Do not guess unsupported facts.
- If company identity is ambiguous, use "unknown".
- If the company is only a legal ownership LLC with no operator evidence, classify it as "property_specific_entity" or "unknown".
- Prefer official company websites over directories.
- Include URLs for claims whenever available.
- Confidence must be between 0.0 and 1.0.
- Use "large" scale only when there is evidence the company manages/owns a large portfolio or has broad regional/national operations.
- Use "small" scale when evidence suggests a local/single-property/small operator.
- Use "unknown" scale when there is no reliable evidence.
"""


def normalize_company_name(company: str) -> str:
    normalized = re.sub(r"[^\w\s]", " ", company.lower())
    normalized = re.sub(r"\b(the|inc|llc|ltd|corp|corporation|co|company|group|holdings|partners)\b", " ", normalized)
    normalized = re.sub(r"\s+", " ", normalized).strip()
    return normalized


def extract_email_domain(email_or_domain: str | None) -> str | None:
    if not email_or_domain:
        return None
    value = email_or_domain.strip().lower()
    if "@" in value:
        parts = value.split("@", 1)
        return parts[1] or None
    return value


def classify_email_domain(
    company_name_normalized: str,
    email_domain: str | None,
    website: str | None = None,
) -> str:
    domain = extract_email_domain(email_domain)
    if not domain:
        return "unknown"
    if domain in _GENERIC_EMAIL_PROVIDERS:
        return "generic"

    website_host = _hostname(website)
    domain_root = domain.split(".")[0]
    normalized_compact = company_name_normalized.replace(" ", "")

    if website_host and (domain in website_host or website_host in domain):
        return "corporate"
    if normalized_compact and (
        domain_root in normalized_compact
        or normalized_compact.startswith(domain_root)
        or domain_root.startswith(normalized_compact[: min(len(normalized_compact), len(domain_root))])
    ):
        return "corporate"

    if any(token in domain for token in ("apart", "homes", "living", "resid", "community", "property", "rent")):
        return "property_specific"
    return "unknown"


def build_company_research_prompt(company: str, email_domain: str | None) -> str:
    return _PROMPT_TEMPLATE.format(company=company, email_domain=email_domain or "unknown")


async def call_gemini_grounded_search(prompt: str) -> tuple[str, Any, list[str]]:
    def _call_sync() -> tuple[str, Any, list[str]]:
        from google import genai
        from google.genai import types

        api_key = os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY")
        if not api_key:
            raise RuntimeError("GEMINI_API_KEY or GOOGLE_API_KEY is not configured.")

        client = genai.Client(api_key=api_key)
        model_name = os.environ.get("GEMINI_MODEL", _DEFAULT_MODEL)
        structured_config = types.GenerateContentConfig(
            tools=[types.Tool(google_search=types.GoogleSearch())],
            response_mime_type="application/json",
            response_json_schema=_gemini_response_schema(),
        )
        plain_config = types.GenerateContentConfig(
            tools=[types.Tool(google_search=types.GoogleSearch())],
        )

        try:
            response = client.models.generate_content(
                model=model_name,
                contents=prompt,
                config=structured_config,
            )
        except Exception as exc:
            if not _is_unsupported_structured_grounding_error(exc):
                raise
            logger.warning(
                "Structured JSON with google_search is unsupported for model=%s; retrying with plain text grounded JSON.",
                model_name,
            )
            response = client.models.generate_content(
                model=model_name,
                contents=f"{prompt}\n\nReturn only a valid JSON object. Do not wrap it in markdown fences.",
                config=plain_config,
            )

        raw_text = response.text or ""
        candidate = response.candidates[0] if getattr(response, "candidates", None) else None
        grounding_metadata = getattr(candidate, "grounding_metadata", None)
        logger.info("company grounded raw Gemini response: %s", raw_text)
        logger.info("company grounded search queries: %s", _extract_grounding_queries(grounding_metadata))
        evidence_urls = _extract_model_evidence_urls(raw_text)
        return raw_text, grounding_metadata, evidence_urls

    return await asyncio.to_thread(_call_sync)


def parse_gemini_json(model_json: str) -> dict:
    cleaned = model_json.strip()
    if cleaned.startswith("```"):
        cleaned = re.sub(r"^```(?:json)?\s*", "", cleaned)
        cleaned = re.sub(r"\s*```$", "", cleaned)
    cleaned = cleaned.strip()
    try:
        return json.loads(cleaned)
    except json.JSONDecodeError:
        return json.loads(extract_json_object(cleaned))


def extract_grounding_sources(grounding_metadata: Any, evidence_urls: list[str]) -> list[dict]:
    seen: set[str] = set()
    sources: list[dict] = []

    def _add(url: str | None, title: str | None = None) -> None:
        if not url or url in seen:
            return
        seen.add(url)
        sources.append({"url": url, "title": title})

    for url in evidence_urls:
        _add(url, None)

    if grounding_metadata is None:
        return sources

    chunks = getattr(grounding_metadata, "grounding_chunks", None)
    if chunks is None and isinstance(grounding_metadata, dict):
        chunks = grounding_metadata.get("grounding_chunks")

    for chunk in chunks or []:
        web = getattr(chunk, "web", None)
        if web is None and isinstance(chunk, dict):
            web = chunk.get("web")
        if web is None:
            continue
        url = getattr(web, "uri", None)
        title = getattr(web, "title", None)
        if isinstance(web, dict):
            url = url or web.get("uri")
            title = title or web.get("title")
        _add(url, title)

    return sources


def _extract_grounding_queries(grounding_metadata: Any) -> list[str]:
    if grounding_metadata is None:
        return []
    queries = getattr(grounding_metadata, "web_search_queries", None)
    if queries is None and isinstance(grounding_metadata, dict):
        queries = grounding_metadata.get("web_search_queries") or grounding_metadata.get("webSearchQueries")
    result: list[str] = []
    for query in queries or []:
        text = str(query or "").strip()
        if text:
            result.append(text)
    return result


def _gemini_response_schema() -> dict[str, Any]:
    enum = sorted
    return {
        "type": "object",
        "properties": {
            "company_name_normalized": {"type": "string"},
            "website": {"type": ["string", "null"]},
            "description": {"type": "string"},
            "industry": {"type": "string"},
            "company_type": {"type": "string", "enum": enum(_COMPANY_TYPE_VALUES)},
            "property_management_relevance": {"type": "string", "enum": enum(_RELEVANCE_VALUES)},
            "multifamily_relevance": {"type": "string", "enum": enum(_RELEVANCE_VALUES)},
            "scale_signal": {"type": "string", "enum": enum(_SCALE_VALUES)},
            "confidence": {"type": "number"},
            "reasons": {"type": "array", "items": {"type": "string"}},
            "evidence": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "claim": {"type": "string"},
                        "url": {"type": ["string", "null"]},
                        "source_type": {"type": "string", "enum": enum(_SOURCE_TYPE_VALUES)},
                    },
                    "required": ["claim", "url", "source_type"],
                    "propertyOrdering": ["claim", "url", "source_type"],
                },
            },
            "recommended_next_step": {"type": "string", "enum": enum(_NEXT_STEP_VALUES)},
        },
        "required": [
            "company_name_normalized",
            "website",
            "description",
            "industry",
            "company_type",
            "property_management_relevance",
            "multifamily_relevance",
            "scale_signal",
            "confidence",
            "reasons",
            "evidence",
            "recommended_next_step",
        ],
        "propertyOrdering": [
            "company_name_normalized",
            "website",
            "description",
            "industry",
            "company_type",
            "property_management_relevance",
            "multifamily_relevance",
            "scale_signal",
            "confidence",
            "reasons",
            "evidence",
            "recommended_next_step",
        ],
    }


def _is_unsupported_structured_grounding_error(exc: Exception) -> bool:
    message = str(exc).lower()
    return "response mime type" in message and "unsupported" in message


def compute_company_score(classification: dict) -> dict:
    company_type = _coerce_enum(classification.get("company_type"), _COMPANY_TYPE_VALUES, "unknown")
    property_management_relevance = _coerce_enum(classification.get("property_management_relevance"), _RELEVANCE_VALUES, "unknown")
    multifamily_relevance = _coerce_enum(classification.get("multifamily_relevance"), _RELEVANCE_VALUES, "unknown")
    scale_signal = _coerce_enum(classification.get("scale_signal"), _SCALE_VALUES, "unknown")
    confidence = _normalize_confidence(classification.get("confidence"))

    raw_score = (
        _COMPANY_TYPE_BASE[company_type]
        + _PROPERTY_MGMT_BONUS[property_management_relevance]
        + _MULTIFAMILY_BONUS[multifamily_relevance]
        + _SCALE_BONUS[scale_signal]
    )
    raw_score = max(0, min(52, raw_score))
    final_score = int(raw_score * confidence)
    final_score = max(0, min(52, final_score))

    if final_score >= 42:
        tier = "strong"
    elif final_score >= 27:
        tier = "medium"
    elif final_score >= 12:
        tier = "weak"
    else:
        tier = "poor"

    return {
        "company_score": final_score,
        "tier": tier,
        "raw_score": raw_score,
        "score_components": [
            {"rule": f"company_type_{company_type}", "fired": True, "points": _COMPANY_TYPE_BASE[company_type]},
            {"rule": f"property_management_relevance_{property_management_relevance}", "fired": property_management_relevance != "low" and property_management_relevance != "unknown", "points": _PROPERTY_MGMT_BONUS[property_management_relevance]},
            {"rule": f"multifamily_relevance_{multifamily_relevance}", "fired": multifamily_relevance != "low" and multifamily_relevance != "unknown", "points": _MULTIFAMILY_BONUS[multifamily_relevance]},
            {"rule": f"scale_signal_{scale_signal}", "fired": scale_signal != "unknown", "points": _SCALE_BONUS[scale_signal]},
            {"rule": "confidence_multiplier", "fired": True, "points": final_score - raw_score, "confidence": confidence},
        ],
    }


async def enrich_company(company: str, email_domain: str | None = None) -> dict:
    normalized_name = normalize_company_name(company)
    domain = extract_email_domain(email_domain)
    prompt = build_company_research_prompt(company, domain)

    last_error: Exception | None = None
    for attempt in range(1, _MAX_COMPANY_ENRICHMENT_ATTEMPTS + 1):
        try:
            model_json, grounding_metadata, evidence_urls = await call_gemini_grounded_search(prompt)
            parsed = parse_gemini_json(model_json)
            return _finalize_company_enrichment(
                parsed,
                domain,
                grounding_metadata,
                evidence_urls,
                fallback=False,
            )
        except Exception as exc:
            last_error = exc
            logger.exception(
                "company enrichment failed for %r on attempt %s/%s",
                company,
                attempt,
                _MAX_COMPANY_ENRICHMENT_ATTEMPTS,
                exc_info=exc,
            )
            if attempt < _MAX_COMPANY_ENRICHMENT_ATTEMPTS:
                await asyncio.sleep(0.75 * attempt)

    fallback = {
        "company_name_normalized": normalized_name or company.strip(),
        "website": None,
        "description": "Grounded company research unavailable.",
        "industry": "unknown",
        "company_type": "unknown",
        "property_management_relevance": "unknown",
        "multifamily_relevance": "unknown",
        "scale_signal": "unknown",
        "confidence": 0.3,
        "reasons": _fallback_reasons(company, domain),
        "evidence": [],
        "grounding_sources": [],
        "recommended_next_step": "manual_review",
        "fallback_error": str(last_error) if last_error else "unknown company enrichment failure",
    }
    return _finalize_company_enrichment(
        fallback,
        domain,
        None,
        [],
        fallback=True,
    )


def _finalize_company_enrichment(
    payload: dict,
    email_domain: str | None,
    grounding_metadata: Any,
    evidence_urls: list[str],
    fallback: bool,
) -> dict:
    normalized_name = normalize_company_name(str(payload.get("company_name_normalized") or "")) or str(payload.get("company_name_normalized") or "")
    website = _coerce_nullable_str(payload.get("website"))
    email_domain_type = classify_email_domain(normalized_name, email_domain, website)

    evidence = _normalize_evidence(payload.get("evidence"))
    grounding_sources = extract_grounding_sources(grounding_metadata, evidence_urls)
    reasons = _normalize_reasons(payload.get("reasons"))
    if fallback and not reasons:
        reasons = ["Grounded company research failed; using conservative fallback heuristics."]

    classification = {
        "company_name_normalized": normalized_name,
        "website": website,
        "description": _coerce_nonempty_str(payload.get("description"), "Unknown company description."),
        "industry": _coerce_nonempty_str(payload.get("industry"), "unknown"),
        "company_type": _coerce_enum(payload.get("company_type"), _COMPANY_TYPE_VALUES, "unknown"),
        "property_management_relevance": _coerce_enum(payload.get("property_management_relevance"), _RELEVANCE_VALUES, "unknown"),
        "multifamily_relevance": _coerce_enum(payload.get("multifamily_relevance"), _RELEVANCE_VALUES, "unknown"),
        "scale_signal": _coerce_enum(payload.get("scale_signal"), _SCALE_VALUES, "unknown"),
        "email_domain_type": email_domain_type,
        "confidence": _normalize_confidence(payload.get("confidence")),
        "reasons": reasons,
        "evidence": evidence,
        "grounding_sources": grounding_sources,
        "recommended_next_step": _coerce_enum(payload.get("recommended_next_step"), _NEXT_STEP_VALUES, "manual_review"),
        "fallback_error": _coerce_nullable_str(payload.get("fallback_error")),
    }

    score = compute_company_score(classification)
    classification.update(
        {
            "company_score": score["company_score"],
            "tier": score["tier"],
            "score_components": score["score_components"],
        }
    )
    return classification


def _normalize_confidence(value: Any) -> float:
    try:
        confidence = float(value)
    except (TypeError, ValueError):
        confidence = 0.3
    return max(0.0, min(1.0, confidence))


def _coerce_enum(value: Any, allowed: set[str], default: str) -> str:
    normalized = str(value or "").strip().lower()
    return normalized if normalized in allowed else default


def _coerce_nonempty_str(value: Any, default: str) -> str:
    text = str(value or "").strip()
    return text or default


def _coerce_nullable_str(value: Any) -> str | None:
    text = str(value).strip() if value is not None else ""
    return text or None


def _normalize_reasons(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    reasons: list[str] = []
    for item in value:
        text = str(item or "").strip()
        if text:
            reasons.append(text)
    return reasons


def _normalize_evidence(value: Any) -> list[dict]:
    if not isinstance(value, list):
        return []

    evidence: list[dict] = []
    for item in value:
        if not isinstance(item, dict):
            continue
        evidence.append(
            {
                "claim": _coerce_nonempty_str(item.get("claim"), "Unknown claim"),
                "url": _coerce_nullable_str(item.get("url")),
                "source_type": _coerce_enum(item.get("source_type"), _SOURCE_TYPE_VALUES, "unknown"),
            }
        )
    return evidence


def _hostname(url: str | None) -> str | None:
    if not url:
        return None
    parsed = urlparse(url)
    return parsed.netloc.lower() or None


def _extract_model_evidence_urls(model_json: str) -> list[str]:
    try:
        payload = parse_gemini_json(model_json)
    except Exception:
        return []
    urls: list[str] = []
    for item in payload.get("evidence") or []:
        if isinstance(item, dict) and item.get("url"):
            urls.append(str(item["url"]))
    return urls


def _fallback_reasons(company: str, email_domain: str | None) -> list[str]:
    reasons = ["Grounded company research unavailable; using conservative fallback heuristics."]
    if email_domain in _GENERIC_EMAIL_PROVIDERS:
        reasons.append("Email domain is a generic provider, which weakens company identity confidence.")
    elif email_domain:
        reasons.append("Email domain is present but could not be verified against grounded company research.")
    if not normalize_company_name(company):
        reasons.append("Company name is ambiguous after normalization.")
    return reasons
