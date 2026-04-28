import re
import logging

logger = logging.getLogger(__name__)

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


def score_article(article: dict, extra_keywords: list[str] | None = None) -> int:
    """Score article by keyword hits in title. Higher = more relevant."""
    title_lower = _normalize(article.get("title", ""))
    keywords = SCORE_KEYWORDS + (extra_keywords or [])
    score = 0
    for kw in keywords:
        if kw in title_lower:
            score += 1
    return score


def _title_key(title: str) -> str:
    """Normalize title for dedup comparison."""
    t = re.sub(r"[^a-z0-9 ]", "", title.lower())
    t = re.sub(r"\s+", " ", t).strip()
    return t


def deduplicate(articles: list[dict]) -> list[dict]:
    """Remove near-duplicate titles. Keep highest-scored."""
    seen: dict[str, dict] = {}
    for art in articles:
        key = _title_key(art["title"])
        words = set(key.split())
        # Check overlap with existing keys
        merged = False
        for existing_key in list(seen.keys()):
            existing_words = set(existing_key.split())
            if not existing_words or not words:
                continue
            overlap = len(words & existing_words) / max(len(words), len(existing_words))
            if overlap > 0.7:
                # Keep higher score
                if art.get("score", 0) > seen[existing_key].get("score", 0):
                    seen[existing_key] = art
                merged = True
                break
        if not merged:
            seen[key] = art
    return list(seen.values())


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
    return deduped[:max_articles]
