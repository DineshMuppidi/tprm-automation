"""Heuristic sentiment/story-type classification for real news articles
pulled by LiveNewsProvider (mock news signals are already pre-classified —
see mock_providers.py). Keyword-based, same spirit as the Phase 1 mock LLM
analyzer: deterministic and free, swappable for a real LLM classification
call later without changing the call site (Phase 2 spec §2, DAG
`daily_news_monitoring` task 2 calls this "LLM sentiment analysis" — a
keyword heuristic is today's implementation of that same interface)."""

_NEGATIVE_STRONG = ("breach", "ransomware", "hack", "lawsuit", "bankruptcy", "fraud", "indicted", "fined")
_NEGATIVE_SOFT = ("resign", "layoff", "layoffs", "downgrade", "investigation", "delay", "outage")
_POSITIVE = ("partnership", "funding", "acquire", "acquisition", "award", "launch", "expansion", "growth")

_STORY_TYPES = {
    "breach": ("breach", "hack", "ransomware", "data exposed", "cyberattack"),
    "lawsuit": ("lawsuit", "sues", "litigation", "indicted"),
    "bankruptcy": ("bankruptcy", "insolvent", "chapter 11"),
    "leadership_change": ("resign", "steps down", "departs", "ceo change", "names new ceo"),
}


def classify_news_article(headline: str, description: str) -> tuple[str, str]:
    """Returns (sentiment, story_type)."""
    text = f"{headline} {description}".lower()

    story_type = "other"
    for label, keywords in _STORY_TYPES.items():
        if any(k in text for k in keywords):
            story_type = label
            break

    if any(k in text for k in _NEGATIVE_STRONG):
        sentiment = "negative"
    elif any(k in text for k in _NEGATIVE_SOFT):
        sentiment = "negative"
    elif any(k in text for k in _POSITIVE):
        sentiment = "positive"
    else:
        sentiment = "neutral"

    return sentiment, story_type
