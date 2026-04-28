import re
import logging
from urllib.parse import urlparse, parse_qs, urlencode, urlunparse

logger = logging.getLogger(__name__)

_UTM_PARAMS = {"utm_source", "utm_medium", "utm_campaign", "utm_term", "utm_content"}

SCORE_KEYWORDS = [
    "llm", "gpt", "claude", "gemini", "mistral", "llama",
    "open source", "release", "launch", "model", "ai",
    "artificial intelligence", "neural", "benchmark", "fine-tune",
    "finetune", "agent", "multimodal", "free", "beats", "sota",
    "transformer", "diffusion", "generative", "foundation model",
    "reasoning", "alignment", "rlhf", "rag", "inference",
]

SECTION_RULES = {
    "launches": ["launch", "release", "announce", "announced", "launches", "releases", "introducing", "unveil"],
    "opensource": ["free", "open source", "open-source", "weights", "open weight", "huggingface", "github"],
    "research": ["paper", "arxiv", "research", "study", "findings", "dataset", "evaluation", "survey"],
    "industry": ["funding", "raises", "raised", "acquires", "acquisition", "valuation", "million", "billion", "invest"],
}


def _normalize(text: str) -> str:
    return text.lower()


_BOOST_RULES: list[tuple[int, list[str]]] = [
    (2, ["free", "open source", "open-source"]),
    (2, ["release", "released", "launches", "launched"]),
    (2, ["beats", "outperforms", "sota", "state of the art"]),
    (1, ["new", "announce", "announced"]),
    (1, ["model", "weights", "fine-tune", "finetune"]),
]


def _keyword_boost(text: str) -> int:
    t = text.lower()
    boost = 0
    for points, terms in _BOOST_RULES:
        if any(term in t for term in terms):
            boost += points
    return boost


def score_article(article: dict, extra_keywords: list[str] | None = None) -> int:
    """Score article by keyword hits in title. Higher = more relevant."""
    title_lower = _normalize(article.get("title", ""))
    desc_lower = _normalize(article.get("description", ""))
    combined = title_lower + " " + desc_lower
    keywords = SCORE_KEYWORDS + (extra_keywords or [])
    score = 0
    for kw in keywords:
        if kw in title_lower:
            score += 1
    score += _keyword_boost(combined)
    return score


def _normalize_url(url: str) -> str:
    """Strip UTM params and trailing slash for URL-based dedup."""
    try:
        parsed = urlparse(url)
        qs = parse_qs(parsed.query, keep_blank_values=False)
        clean_qs = {k: v for k, v in qs.items() if k not in _UTM_PARAMS}
        clean_query = urlencode(clean_qs, doseq=True)
        normalized = urlunparse((
            parsed.scheme,
            parsed.netloc.lower(),
            parsed.path.rstrip("/"),
            parsed.params,
            clean_query,
            "",
        ))
        return normalized
    except Exception:
        return url


def _title_tokens(title: str) -> set[str]:
    t = re.sub(r"[^a-z0-9 ]", "", title.lower())
    return set(t.split())


def _title_similarity(t1: str, t2: str) -> float:
    a = _title_tokens(t1)
    b = _title_tokens(t2)
    if not a or not b:
        return 0.0
    return len(a & b) / len(a | b)


def deduplicate(articles: list[dict]) -> list[dict]:
    """Dedup by URL normalization first, then title Jaccard similarity > 0.6."""
    seen_urls: dict[str, int] = {}   # normalized_url -> index in `kept`
    kept: list[dict] = []
    dupes = 0

    for art in articles:
        norm_url = _normalize_url(art.get("link", ""))

        # URL exact match
        if norm_url and norm_url in seen_urls:
            idx = seen_urls[norm_url]
            if art.get("score", 0) > kept[idx].get("score", 0):
                kept[idx] = art
            dupes += 1
            continue

        # Title similarity match
        title = art.get("title", "")
        matched_idx = -1
        for i, existing in enumerate(kept):
            if _title_similarity(title, existing.get("title", "")) > 0.6:
                matched_idx = i
                break

        if matched_idx >= 0:
            if art.get("score", 0) > kept[matched_idx].get("score", 0):
                kept[matched_idx] = art
            # Map this URL to the canonical slot regardless of which won
            if norm_url:
                seen_urls[norm_url] = matched_idx
            dupes += 1
        else:
            if norm_url:
                seen_urls[norm_url] = len(kept)
            kept.append(art)

    logger.info("Dedup removed %d duplicates, %d unique remain", dupes, len(kept))
    return kept


def assign_section(article: dict) -> str:
    """Assign article to digest section based on title keywords."""
    title_lower = _normalize(article.get("title", ""))
    source = article.get("source", "").lower()
    is_community = article.get("is_community", False)

    # Community first — reddit/HN
    if is_community or any(s in source for s in ["reddit", "hacker news"]):
        return "community"

    for section, keywords in SECTION_RULES.items():
        for kw in keywords:
            if kw in title_lower:
                return section

    return "quickhits"


def filter_and_rank(
    articles: list[dict],
    min_score: int = 1,
    max_articles: int = 30,
    extra_keywords: list[str] | None = None,
) -> list[dict]:
    """Score, filter, deduplicate, assign sections, return top N."""
    scored = []
    for art in articles:
        s = score_article(art, extra_keywords)
        if s >= min_score:
            art = dict(art)
            art["score"] = s
            art["section"] = assign_section(art)
            scored.append(art)

    deduped = deduplicate(scored)
    deduped.sort(key=lambda a: a["score"], reverse=True)

    logger.info("After filter+dedup: %d articles (from %d raw)", len(deduped), len(articles))
    for i, a in enumerate(deduped[:5]):
        logger.info("Top-%d [score=%d]: %s", i + 1, a["score"], a.get("title", ""))
    return deduped[:max_articles]
