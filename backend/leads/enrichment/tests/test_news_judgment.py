import pytest

from leads.enrichment.scoring import news_judgment


@pytest.mark.asyncio
async def test_llm_news_judgment_skips_articles_without_company_mention(monkeypatch):
    calls = []

    async def fake_call_claude(system, user, response_model=None, max_tokens=1024):
        calls.append(user)
        return {"mentions_growth": True, "reasoning": "should not be used"}

    monkeypatch.setattr(news_judgment, "call_claude", fake_call_claude)
    async def fake_fetch_article_excerpt(url, company_variants):
        return None

    monkeypatch.setattr(news_judgment.news_service, "fetch_article_excerpt", fake_fetch_article_excerpt)

    result = await news_judgment.llm_news_judgment(
        {"company": "Bozzuto", "email_domain": "bozzuto.com", "company_query_variants": ["bozzuto"]},
        [{"title": "Multifamily market trends accelerate", "snippet": "Seattle housing coverage."}],
    )

    assert result["news_relevance"] == [False]
    assert result["growth_flags"] == [False]
    assert result["articles"][0]["reasoning"] == "company not found in article body"
    assert calls == []


@pytest.mark.asyncio
async def test_llm_news_judgment_prompt_uses_matched_excerpt(monkeypatch):
    captured = {}
    calls = []

    async def fake_call_claude(system, user, response_model=None, max_tokens=1024):
        captured["system"] = system
        captured["user"] = user
        captured["max_tokens"] = max_tokens
        calls.append(user)
        return {"mentions_growth": True, "reasoning": "explicit mention with growth"}

    monkeypatch.setattr(news_judgment, "call_claude", fake_call_claude)
    async def fake_fetch_article_excerpt(url, company_variants):
        assert "bozzuto" in company_variants
        return "the bozzuto group announced a new expansion and portfolio growth in washington"

    monkeypatch.setattr(news_judgment.news_service, "fetch_article_excerpt", fake_fetch_article_excerpt)

    result = await news_judgment.llm_news_judgment(
        {"company": "Bozzuto", "email_domain": "bozzuto.com"},
        [{"title": "Bozzuto announces expansion", "source": "Bilt", "url": "https://example.com"}],
    )

    assert result["news_relevance"] == [True]
    assert result["growth_flags"] == [True]
    assert "Matched excerpt from article body" in captured["user"]
    assert "Treat the article as relevant to the company because the mention was found in the article body" in captured["user"]
    assert "portfolio growth in washington" in captured["user"]
    assert captured["max_tokens"] == 256
    assert len(calls) == 1
