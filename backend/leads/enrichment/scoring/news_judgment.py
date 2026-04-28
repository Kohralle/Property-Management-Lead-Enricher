from __future__ import annotations

import json
import re

from pydantic import BaseModel, Field

from leads.enrichment.llm.client import call_claude
from leads.enrichment.services import news as news_service

_SYSTEM_PROMPT = """You are evaluating Google News results for sales lead enrichment.
Determine whether each article is genuinely about the target company and whether it contains a growth or expansion signal.
Be conservative. Return valid JSON only."""

_USER_TEMPLATE = """Target company:
- Name: {company}
- Email domain: {email_domain}
- Known aliases / query variants:
{company_variants_json}

Article metadata:
{article_json}

Matched excerpt from article body:
{excerpt}

- The excerpt already contains a direct textual mention of the target company or alias from the article body.
- Treat the article as relevant to the company because the mention was found in the article body.
- Decide only whether this excerpt contains a real growth or momentum signal for the company.
- mentions_growth is true only if the excerpt clearly mentions expansion, acquisition, fundraising, development growth, new openings, portfolio growth, new capital, hiring for growth, or similar business momentum.
- Do not infer growth from geography, source name, URL, or general housing/real-estate themes alone.

Return JSON only:
{{
  "mentions_growth": <bool>,
  "reasoning": "<short phrase>"
}}
"""


class NewsJudgmentResponse(BaseModel):
    mentions_growth: bool
    reasoning: str = Field(min_length=1)


def _normalize_text(text: str) -> str:
    text = (text or "").lower()
    text = re.sub(r"(?<=\w)\.(?=\w)", "", text)
    text = re.sub(r"[^\w\s]", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def _company_variants(parsed_lead: dict) -> list[str]:
    variants = list(parsed_lead.get("company_query_variants") or [])
    company = parsed_lead.get("company") or ""
    if company:
        variants.append(company)
    seen: set[str] = set()
    normalized: list[str] = []
    for variant in variants:
        token = _normalize_text(variant)
        if token and token not in seen:
            seen.add(token)
            normalized.append(token)
    return normalized


def _article_prompt(parsed_lead: dict, article: dict, excerpt: str) -> str:
    return _USER_TEMPLATE.format(
        company=parsed_lead.get("company", ""),
        email_domain=parsed_lead.get("email_domain") or "unknown",
        company_variants_json=json.dumps(_company_variants(parsed_lead), indent=2, sort_keys=True),
        article_json=json.dumps(
            {
                "title": article.get("title"),
                "source": article.get("source"),
                "publishedAt": article.get("publishedAt"),
                "url": article.get("url"),
            },
            indent=2,
            sort_keys=True,
        ),
        excerpt=excerpt,
    )


async def _judge_article(parsed_lead: dict, article: dict, excerpt: str) -> dict:
    result = await call_claude(
        system=_SYSTEM_PROMPT,
        user=_article_prompt(parsed_lead, article, excerpt),
        response_model=NewsJudgmentResponse,
        max_tokens=256,
    )
    return {
        "relevant_to_company": True,
        "mentions_growth": bool(result.get("mentions_growth")),
        "reasoning": str(result.get("reasoning") or "").strip(),
        "matched_excerpt": excerpt,
    }


async def llm_news_judgment(parsed_lead: dict, articles: list[dict]) -> dict:
    if not articles:
        return {"articles": [], "news_relevance": [], "growth_flags": []}

    rows = []
    company_variants = _company_variants(parsed_lead)
    for article in articles[:10]:
        excerpt = await news_service.fetch_article_excerpt(article.get("url") or "", company_variants)
        if not excerpt:
            rows.append(
                {
                    "relevant_to_company": False,
                    "mentions_growth": False,
                    "reasoning": "company not found in article body",
                }
            )
            continue
        try:
            rows.append(await _judge_article(parsed_lead, article, excerpt))
        except Exception:
            rows.append(
                {
                    "relevant_to_company": False,
                    "mentions_growth": False,
                    "reasoning": "",
                    "matched_excerpt": excerpt,
                }
            )
    return {
        "articles": rows,
        "news_relevance": [row["relevant_to_company"] for row in rows],
        "growth_flags": [row["mentions_growth"] for row in rows],
    }
