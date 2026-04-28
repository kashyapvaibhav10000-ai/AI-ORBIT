import urllib.request
import urllib.error
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
import logging
import json
import os

logger = logging.getLogger(__name__)

_HEALTH_FILE = os.path.join(os.path.dirname(os.path.dirname(__file__)), "logs", "feed_health.json")
_feed_health: dict = {}


def _load_health() -> None:
    global _feed_health
    os.makedirs(os.path.dirname(_HEALTH_FILE), exist_ok=True)
    if os.path.exists(_HEALTH_FILE):
        try:
            with open(_HEALTH_FILE, "r", encoding="utf-8") as f:
                _feed_health = json.load(f)
        except Exception:
            _feed_health = {}
    else:
        _feed_health = {}


def _save_health() -> None:
    os.makedirs(os.path.dirname(_HEALTH_FILE), exist_ok=True)
    with open(_HEALTH_FILE, "w", encoding="utf-8") as f:
        json.dump(_feed_health, f, indent=2)


def _get_feed_record(feed_url: str) -> dict:
    if feed_url not in _feed_health:
        _feed_health[feed_url] = {
            "feed_url": feed_url,
            "last_success": None,
            "last_failure": None,
            "consecutive_failures": 0,
            "total_failures": 0,
            "total_successes": 0,
            "status": "healthy",
        }
    return _feed_health[feed_url]


def _update_health_success(feed_url: str) -> None:
    rec = _get_feed_record(feed_url)
    rec["last_success"] = datetime.now(timezone.utc).isoformat()
    rec["consecutive_failures"] = 0
    rec["total_successes"] += 1
    rec["status"] = "healthy"


def _update_health_failure(feed_url: str) -> None:
    rec = _get_feed_record(feed_url)
    rec["last_failure"] = datetime.now(timezone.utc).isoformat()
    rec["consecutive_failures"] += 1
    rec["total_failures"] += 1
    cf = rec["consecutive_failures"]
    if cf >= 7:
        rec["status"] = "dead"
    elif cf >= 3:
        rec["status"] = "degraded"


def print_health_summary() -> None:
    healthy = [url for url, r in _feed_health.items() if r["status"] == "healthy"]
    degraded = [url for url, r in _feed_health.items() if r["status"] == "degraded"]
    dead = [url for url, r in _feed_health.items() if r["status"] == "dead"]
    print(f"{len(healthy)} feeds healthy, {len(degraded)} degraded, {len(dead)} dead")


def get_health_summary() -> dict:
    healthy = [url for url, r in _feed_health.items() if r["status"] == "healthy"]
    degraded = [url for url, r in _feed_health.items() if r["status"] == "degraded"]
    dead = [url for url, r in _feed_health.items() if r["status"] == "dead"]
    return {"healthy": healthy, "degraded": degraded, "dead": dead}

NAMESPACES = {
    "media": "http://search.yahoo.com/mrss/",
    "dc": "http://purl.org/dc/elements/1.1/",
    "content": "http://purl.org/rss/1.0/modules/content/",
    "atom": "http://www.w3.org/2005/Atom",
}

COMMUNITY_SOURCES = {"reddit.com", "hnrss.org", "news.ycombinator.com"}


def _parse_date(raw: str) -> str:
    """Parse RFC 822 or ISO 8601 date to YYYY-MM-DD. Return raw string on failure."""
    if not raw:
        return ""
    raw = raw.strip()
    formats = [
        "%a, %d %b %Y %H:%M:%S %z",
        "%a, %d %b %Y %H:%M:%S %Z",
        "%Y-%m-%dT%H:%M:%S%z",
        "%Y-%m-%dT%H:%M:%SZ",
        "%Y-%m-%d",
    ]
    for fmt in formats:
        try:
            return datetime.strptime(raw, fmt).strftime("%Y-%m-%d")
        except ValueError:
            continue
    return raw[:10] if len(raw) >= 10 else raw


def _source_from_url(feed_url: str) -> str:
    """Extract readable source name from feed URL."""
    from urllib.parse import urlparse
    host = urlparse(feed_url).netloc.lower()
    host = host.replace("www.", "").replace("blogs.", "")
    mapping = {
        "hnrss.org": "Hacker News",
        "reddit.com": "Reddit",
        "huggingface.co": "HuggingFace",
        "techcrunch.com": "TechCrunch",
        "venturebeat.com": "VentureBeat",
        "technologyreview.com": "MIT Tech Review",
        "openai.com": "OpenAI",
        "anthropic.com": "Anthropic",
        "deepmind.google": "DeepMind",
        "microsoft.com": "Microsoft AI",
        "arxiv.org": "arXiv",
    }
    for key, name in mapping.items():
        if key in host:
            return name
    return host


def _is_community(feed_url: str) -> bool:
    return any(s in feed_url for s in COMMUNITY_SOURCES)


def fetch_feed(feed_url: str, timeout: int = 10) -> list[dict]:
    """Fetch single RSS/Atom feed. Returns list of article dicts. Never raises."""
    articles = []
    source = _source_from_url(feed_url)
    is_community = _is_community(feed_url)

    rec = _get_feed_record(feed_url)
    if rec["status"] == "dead":
        logger.warning("Feed marked DEAD, attempting anyway: %s", feed_url)

    try:
        req = urllib.request.Request(
            feed_url,
            headers={"User-Agent": "AIRadar/1.0 (RSS Reader; +https://github.com/user/airadar)"},
        )
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            raw = resp.read()
    except urllib.error.URLError as e:
        logger.warning("Feed fetch failed [%s]: %s", feed_url, e)
        _update_health_failure(feed_url)
        _save_health()
        return []
    except Exception as e:
        logger.warning("Feed fetch error [%s]: %s", feed_url, e)
        _update_health_failure(feed_url)
        _save_health()
        return []

    try:
        root = ET.fromstring(raw)
    except ET.ParseError as e:
        logger.warning("Feed parse error [%s]: %s", feed_url, e)
        _update_health_failure(feed_url)
        _save_health()
        return []

    # Detect Atom vs RSS
    tag = root.tag.lower()
    if "feed" in tag:
        articles = _parse_atom(root, source, is_community)
    else:
        articles = _parse_rss(root, source, is_community)

    _update_health_success(feed_url)
    _save_health()
    return articles


def _parse_rss(root: ET.Element, source: str, is_community: bool) -> list[dict]:
    articles = []
    channel = root.find("channel")
    if channel is None:
        channel = root
    for item in channel.findall("item"):
        title = (item.findtext("title") or "").strip()
        link = (item.findtext("link") or "").strip()
        date_raw = item.findtext("pubDate") or item.findtext("dc:date", namespaces=NAMESPACES) or ""
        if not title or not link:
            continue
        articles.append({
            "title": title,
            "link": link,
            "date": _parse_date(date_raw),
            "source": source,
            "is_community": is_community,
        })
    return articles


def _parse_atom(root: ET.Element, source: str, is_community: bool) -> list[dict]:
    articles = []
    ns = ""
    if root.tag.startswith("{"):
        ns = root.tag.split("}")[0] + "}"
    for entry in root.findall(f"{ns}entry"):
        title_el = entry.find(f"{ns}title")
        title = (title_el.text or "").strip() if title_el is not None else ""
        link_el = entry.find(f"{ns}link")
        link = ""
        if link_el is not None:
            link = link_el.get("href", "") or (link_el.text or "")
        date_el = entry.find(f"{ns}updated") or entry.find(f"{ns}published")
        date_raw = (date_el.text or "") if date_el is not None else ""
        if not title or not link:
            continue
        articles.append({
            "title": title,
            "link": link.strip(),
            "date": _parse_date(date_raw),
            "source": source,
            "is_community": is_community,
        })
    return articles


def fetch_all_feeds(feeds: list[str], timeout: int = 10) -> list[dict]:
    """Fetch all feeds. Log failures, never crash."""
    _load_health()
    all_articles = []
    for feed_url in feeds:
        fetched = fetch_feed(feed_url, timeout=timeout)
        logger.info("Fetched %d articles from %s", len(fetched), feed_url)
        all_articles.extend(fetched)
    print_health_summary()
    return all_articles
