from leads.enrichment.services.news import extract_excerpt_from_text
from leads.enrichment.services import news


def test_extract_excerpt_from_text_returns_none_without_company_mention():
    excerpt = extract_excerpt_from_text(
        "<html><body><p>Apartment demand remains stable in Seattle.</p></body></html>",
        ["bozzuto"],
    )
    assert excerpt is None


def test_extract_excerpt_from_text_returns_match_centered_excerpt():
    excerpt = extract_excerpt_from_text(
        """
        <html><body>
        <article>
          <p>Market context before the mention.</p>
          <p>The Bozzuto Group announced a new development and portfolio growth in Arlington.</p>
          <p>Additional details after the mention.</p>
        </article>
        </body></html>
        """,
        ["bozzuto", "the bozzuto group"],
    )
    assert excerpt is not None
    assert "the bozzuto group announced a new development and portfolio growth in arlington" in excerpt


def test_search_articles_returns_up_to_ten_results(monkeypatch):
    async def fake_fetch_news(company, query, params):
        return {
            "news_results": [
                {
                    "title": f"Article {idx}",
                    "source": {"name": "Example"},
                    "date": "1 day ago",
                    "snippet": "Coverage",
                    "link": f"https://example.com/{idx}",
                }
                for idx in range(1, 13)
            ]
        }

    monkeypatch.setattr(news, "_fetch_news", fake_fetch_news)
    monkeypatch.setattr(news, "_api_key", lambda: "test-key")

    articles = __import__("asyncio").run(news.search_articles("Bozzuto"))

    assert len(articles) == 10
