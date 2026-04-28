#!/usr/bin/env python3
"""
AIRadar — Daily AI digest via RSS + Gmail.
Pure stdlib. Zero dependencies.
"""

import json
import logging
import sys
from datetime import date
from pathlib import Path

# Allow running from project root
sys.path.insert(0, str(Path(__file__).parent))

from src.fetcher import fetch_all_feeds
from src.filter import filter_and_rank
from src.formatter import build_html, build_subject
from src.emailer import send_digest

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("airadar")


def load_config() -> dict:
    config_path = Path(__file__).parent / "config" / "config.json"
    with open(config_path, "r", encoding="utf-8") as f:
        return json.load(f)


def run() -> None:
    logger.info("AIRadar starting — %s", date.today().isoformat())

    config = load_config()
    feeds: list[str] = config.get("feeds", [])
    users: list[dict] = config.get("users", [])
    min_score: int = config.get("min_score", 1)
    max_articles: int = config.get("max_articles", 30)
    timeout: int = config.get("fetch_timeout", 10)

    if not feeds:
        logger.error("No feeds configured. Add feeds to config/config.json.")
        sys.exit(1)

    if not users:
        logger.error("No users configured. Add users to config/config.json.")
        sys.exit(1)

    logger.info("Fetching %d feeds...", len(feeds))
    raw_articles = fetch_all_feeds(feeds, timeout=timeout)
    logger.info("Total raw articles: %d", len(raw_articles))

    digest_date = date.today().strftime("%B %d, %Y")
    subject = build_subject(digest_date)

    results = {"sent": 0, "failed": 0}

    for user in users:
        name = user.get("name", "User")
        email = user.get("email", "")
        extra_keywords = user.get("keywords", [])

        if not email or email == "placeholder@gmail.com":
            logger.warning("User '%s' has placeholder email — skipping", name)
            continue

        logger.info("Building digest for %s <%s>", name, email)

        articles = filter_and_rank(
            raw_articles,
            min_score=min_score,
            max_articles=max_articles,
            extra_keywords=extra_keywords,
        )

        if not articles:
            logger.warning("No articles passed filter for %s — digest skipped", name)
            continue

        logger.info("Digest contains %d articles for %s", len(articles), name)
        html = build_html(articles, digest_date=digest_date)

        ok = send_digest(name, email, subject, html)
        if ok:
            results["sent"] += 1
        else:
            results["failed"] += 1

    logger.info(
        "Done. Sent: %d, Failed: %d",
        results["sent"],
        results["failed"],
    )

    if results["failed"] > 0 and results["sent"] == 0:
        sys.exit(1)


if __name__ == "__main__":
    run()
