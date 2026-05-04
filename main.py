#!/usr/bin/env python3
"""
╔══════════════════════════════════════════════════════════════╗
║  🛸 AI-ORBIT — AI News Digest                               ║
║  Nothing escapes orbit.                                      ║
║                                                              ║
║  Zero dependencies. Pure Python stdlib.                      ║
║  Fetches 13 RSS feeds, scores, deduplicates, and emails      ║
║  a beautiful dark-themed HTML newsletter.                    ║
╚══════════════════════════════════════════════════════════════╝

Usage:
  python main.py              # normal run
  python main.py --verbose    # verbose logging
"""

import urllib.request
import urllib.error
import xml.etree.ElementTree as ET
import smtplib
import ssl
import json
import re
import os
import sys
import hashlib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from datetime import datetime, timezone, timedelta
from collections import defaultdict
from html import escape as html_escape

# ═══════════════════════════════════════════════════════════════
# ⚙️  CONFIGURATION
# ═══════════════════════════════════════════════════════════════

GMAIL_ADDRESS      = os.environ.get("GMAIL_ADDRESS", "")
GMAIL_APP_PASSWORD = os.environ.get("GMAIL_APP_PASSWORD", "")
RECIPIENT_EMAIL    = os.environ.get("RECIPIENT_EMAIL", "")

SCRIPT_DIR       = os.path.dirname(os.path.abspath(__file__))
SEEN_CACHE_FILE  = os.path.join(SCRIPT_DIR, "seen_articles.json")
ORBIT_STATE_FILE = os.path.join(SCRIPT_DIR, "orbit_state.json")

VERBOSE = "--verbose" in sys.argv

# ═══════════════════════════════════════════════════════════════
# 📡 RSS FEED SOURCES
# ═══════════════════════════════════════════════════════════════

RSS_FEEDS = [
    {"url": "https://hnrss.org/newest?q=AI+LLM+GPT+machine+learning", "name": "Hacker News"},
    {"url": "https://huggingface.co/blog/feed.xml",                    "name": "Hugging Face"},
    {"url": "https://arxiv.org/rss/cs.AI",                             "name": "arXiv cs.AI"},
    {"url": "https://techcrunch.com/category/artificial-intelligence/feed/", "name": "TechCrunch"},
    {"url": "https://venturebeat.com/category/ai/feed/",               "name": "VentureBeat"},
    {"url": "https://www.reddit.com/r/MachineLearning/.rss",           "name": "r/MachineLearning"},
    {"url": "https://www.reddit.com/r/LocalLLaMA/.rss",                "name": "r/LocalLLaMA"},
    {"url": "https://deepmind.google/blog/rss.xml",                    "name": "Google DeepMind"},
    {"url": "https://openai.com/blog/rss.xml",                         "name": "OpenAI"},
    {"url": "https://www.anthropic.com/rss.xml",                       "name": "Anthropic"},
    {"url": "https://www.technologyreview.com/feed/",                  "name": "MIT Tech Review"},
    {"url": "https://jack-clark.net/feed/",                            "name": "Import AI"},
    {"url": "https://read.deeplearning.ai/the-batch/rss/",             "name": "The Batch"},
]

# ═══════════════════════════════════════════════════════════════
# 🎯 KEYWORD SCORING WEIGHTS
# ═══════════════════════════════════════════════════════════════

KEYWORDS_HIGH = [
    "launch", "release", "free", "open source", "beats", "new model",
    "gpt", "claude", "gemini", "llama", "mistral", "open ai",
    "openai", "anthropic", "deepmind", "benchmark",
]
KEYWORDS_MEDIUM = [
    "ai", "llm", "model", "agent", "training", "research", "paper",
]
KEYWORDS_LOW = [
    "tech", "neural", "data", "compute", "chip", "gpu",
]

CAT_LAUNCHES         = ["launch", "release", "announce", "new", "debut"]
CAT_OPENSOURCE       = ["free", "open source", "open-source", "weights", "huggingface", "hugging face"]
CAT_RESEARCH         = ["paper", "arxiv", "research", "study", "benchmark"]
CAT_INDUSTRY         = ["funding", "investment", "billion", "million", "startup", "acquire", "acquisition"]
CAT_COMMUNITY_SOURCES = ["hacker news", "r/machinelearning", "r/localllama"]

# ═══════════════════════════════════════════════════════════════
# 🔧 LOGGING
# ═══════════════════════════════════════════════════════════════


def log(msg):
    ts = datetime.now().strftime("%H:%M:%S")
    print(f"  [{ts}] {msg}")


def vlog(msg):
    if VERBOSE:
        ts = datetime.now().strftime("%H:%M:%S")
        print(f"  [{ts}] [V] {msg}")


# ═══════════════════════════════════════════════════════════════
# ⏱️  TIMESTAMP UTILITIES
# ═══════════════════════════════════════════════════════════════

_DATE_FORMATS = [
    "%a, %d %b %Y %H:%M:%S %z",
    "%a, %d %b %Y %H:%M:%S %Z",
    "%Y-%m-%dT%H:%M:%S%z",
    "%Y-%m-%dT%H:%M:%SZ",
    "%Y-%m-%d %H:%M:%S",
    "%Y-%m-%dT%H:%M:%S.%f%z",
    "%Y-%m-%dT%H:%M:%S.%fZ",
    "%d %b %Y %H:%M:%S %z",
]


def parse_pub_date(dt_str):
    """Parse pub_date string → UTC-aware datetime, or None on failure."""
    if not dt_str:
        return None
    for fmt in _DATE_FORMATS:
        try:
            parsed = datetime.strptime(dt_str.strip(), fmt)
            if parsed.tzinfo is None:
                parsed = parsed.replace(tzinfo=timezone.utc)
            return parsed.astimezone(timezone.utc)
        except (ValueError, TypeError):
            continue
    return None


def format_timestamp(article):
    """Return 'May 04 · 3h ago' string. Uses cached _parsed_dt if present."""
    parsed = article.get("_parsed_dt") or parse_pub_date(article.get("pub_date", ""))
    if not parsed:
        return "unknown"
    now = datetime.now(timezone.utc)
    diff = now - parsed
    total_secs = int(diff.total_seconds())
    date_str = parsed.strftime("%b %d")
    if total_secs < 3600:
        mins = max(1, total_secs // 60)
        return f"{date_str} · {mins}m ago"
    hours = total_secs // 3600
    return f"{date_str} · {hours}h ago"


def is_within_hours(article, max_hours):
    """True if article._parsed_dt is within max_hours of now."""
    parsed = article.get("_parsed_dt")
    if not parsed:
        return False
    diff = datetime.now(timezone.utc) - parsed
    return diff.total_seconds() <= max_hours * 3600


# ═══════════════════════════════════════════════════════════════
# 💾 SEEN-ARTICLE CACHE  (cross-run deduplication)
# ═══════════════════════════════════════════════════════════════


def load_seen_cache():
    """Load seen_articles.json; auto-purge entries older than 7 days."""
    if not os.path.exists(SEEN_CACHE_FILE):
        return {}
    try:
        with open(SEEN_CACHE_FILE) as f:
            raw = json.load(f)
    except (json.JSONDecodeError, IOError):
        return {}
    cutoff = datetime.now(timezone.utc) - timedelta(days=7)
    purged = {}
    stale = 0
    for k, v in raw.items():
        try:
            ts = datetime.fromisoformat(v)
            if ts.tzinfo is None:
                ts = ts.replace(tzinfo=timezone.utc)
            if ts > cutoff:
                purged[k] = v
            else:
                stale += 1
        except (ValueError, TypeError):
            stale += 1
    if stale:
        vlog(f"Cache: purged {stale} stale entries (>7 days)")
    vlog(f"Cache: loaded {len(purged)} seen keys")
    return purged


def save_seen_cache(cache):
    try:
        with open(SEEN_CACHE_FILE, "w") as f:
            json.dump(cache, f, indent=2)
        vlog(f"Cache: saved {len(cache)} keys → {SEEN_CACHE_FILE}")
    except IOError as e:
        log(f"⚠️  Could not save seen cache: {e}")


def _article_cache_keys(article):
    """Return (url_key, title_key) strings for cache lookup."""
    url_key   = "url:"   + article["link"].strip()
    title_key = "title:" + hashlib.md5(
        article["title"].lower().strip().encode("utf-8", errors="replace")
    ).hexdigest()
    return url_key, title_key


# ═══════════════════════════════════════════════════════════════
# 📋 ORBIT STATE  (top-story rotation)
# ═══════════════════════════════════════════════════════════════


def load_orbit_state():
    if not os.path.exists(ORBIT_STATE_FILE):
        return {}
    try:
        with open(ORBIT_STATE_FILE) as f:
            return json.load(f)
    except (json.JSONDecodeError, IOError):
        return {}


def save_orbit_state(state):
    try:
        with open(ORBIT_STATE_FILE, "w") as f:
            json.dump(state, f, indent=2)
        vlog(f"State: saved → {ORBIT_STATE_FILE}")
    except IOError as e:
        log(f"⚠️  Could not save orbit state: {e}")


# ═══════════════════════════════════════════════════════════════
# 🧹 TEXT UTILITIES
# ═══════════════════════════════════════════════════════════════


def clean_text(text):
    if not text:
        return ""
    text = re.sub(r"<[^>]+>", "", text)
    text = re.sub(r"&[a-zA-Z]+;", " ", text)
    text = re.sub(r"&#\d+;", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def normalize_words(title):
    return set(re.findall(r"[a-z0-9]+", title.lower()))


# ═══════════════════════════════════════════════════════════════
# 📡 RSS FETCHING
# ═══════════════════════════════════════════════════════════════


def fetch_feed(feed_info):
    url    = feed_info["url"]
    source = feed_info["name"]
    articles = []

    try:
        req = urllib.request.Request(
            url,
            headers={
                "User-Agent": "AI-ORBIT/1.0 (Python; RSS Reader)",
                "Accept":     "application/rss+xml, application/xml, text/xml, */*",
            },
        )
        with urllib.request.urlopen(req, timeout=10) as response:
            raw = response.read()

        for encoding in ("utf-8", "latin-1", "ascii"):
            try:
                xml_text = raw.decode(encoding)
                break
            except (UnicodeDecodeError, AttributeError):
                continue
        else:
            xml_text = raw.decode("utf-8", errors="replace")

        xml_text = re.sub(r"xmlns\s*=\s*['\"][^'\"]*['\"]", "", xml_text, count=1)
        root = ET.fromstring(xml_text)

        # RSS 2.0
        for item in root.findall(".//item"):
            title   = clean_text((item.findtext("title")       or "").strip())
            link    = (item.findtext("link")                    or "").strip()
            pub_date = (item.findtext("pubDate")               or "").strip()
            description = clean_text((item.findtext("description") or "")[:300])
            if title and link:
                articles.append({
                    "title": title, "link": link, "source": source,
                    "pub_date": pub_date, "description": description, "score": 0,
                })

        # Atom
        for entry in root.findall(".//entry"):
            title = clean_text((entry.findtext("title") or "").strip())
            link_el = entry.find("link")
            link = ""
            if link_el is not None:
                link = link_el.get("href", "") or link_el.text or ""
            link = link.strip()
            pub_date = (
                entry.findtext("published") or entry.findtext("updated") or ""
            ).strip()
            summary = clean_text(
                (entry.findtext("summary") or entry.findtext("content") or "")[:300]
            )
            if title and link:
                articles.append({
                    "title": title, "link": link, "source": source,
                    "pub_date": pub_date, "description": summary, "score": 0,
                })

        log(f"✅ {source}: {len(articles)} articles fetched")

    except urllib.error.URLError as e:
        log(f"⚠️  {source}: Network error — {e.reason}")
    except ET.ParseError:
        log(f"⚠️  {source}: XML parse error")
    except Exception as e:
        log(f"⚠️  {source}: {type(e).__name__} — {e}")

    return articles


def fetch_all_feeds():
    all_articles = []
    log(f"Fetching {len(RSS_FEEDS)} feeds...")
    print()
    for feed in RSS_FEEDS:
        articles = fetch_feed(feed)
        all_articles.extend(articles)
    print()
    log(f"Total raw articles fetched: {len(all_articles)}")
    return all_articles


# ═══════════════════════════════════════════════════════════════
# 🕐 FRESHNESS FILTER  (strict 24-hour)
# ═══════════════════════════════════════════════════════════════


def filter_fresh(articles):
    """
    Keep only articles published within the last 24 hours.
    Attaches _parsed_dt to each kept article for reuse downstream.
    Returns (fresh_articles, filtered_count).
    """
    fresh = []
    filtered = 0
    no_date = 0
    for a in articles:
        parsed = parse_pub_date(a.get("pub_date", ""))
        if parsed is None:
            no_date += 1
            filtered += 1
            vlog(f"  [NO-DATE] {a['title'][:60]}")
            continue
        a["_parsed_dt"] = parsed
        diff = datetime.now(timezone.utc) - parsed
        if diff.total_seconds() <= 86400:
            fresh.append(a)
        else:
            filtered += 1
            vlog(f"  [STALE {int(diff.total_seconds()//3600)}h] {a['title'][:60]}")
    log(f"Freshness filter: {len(fresh)} fresh | {filtered} rejected ({no_date} no-date, {filtered-no_date} >24h)")
    return fresh, filtered


# ═══════════════════════════════════════════════════════════════
# 🎯 SCORING
# ═══════════════════════════════════════════════════════════════


def score_article(article):
    text = (article["title"] + " " + article.get("description", "")).lower()
    score = 0
    for kw in KEYWORDS_HIGH:
        if kw in text:
            score += 3
    for kw in KEYWORDS_MEDIUM:
        if kw in text:
            score += 2
    for kw in KEYWORDS_LOW:
        if kw in text:
            score += 1
    article["score"] = min(score, 10)
    return article


def score_all(articles):
    for a in articles:
        score_article(a)
    articles.sort(key=lambda x: x["score"], reverse=True)
    return articles


# ═══════════════════════════════════════════════════════════════
# 🧹 DEDUPLICATION  (cross-run + within-run)
# ═══════════════════════════════════════════════════════════════


def deduplicate(articles, seen_cache, threshold=0.6):
    """
    Two-stage dedup:
      1. Cross-run: skip articles whose URL or title hash is in seen_cache.
      2. Within-run: skip articles sharing ≥60% title words with a kept article.
    Returns (kept_articles, new_cache_key_pairs).
    """
    keep = []
    new_keys = []
    cross_skipped = 0
    within_skipped = 0

    for article in articles:
        url_key, title_key = _article_cache_keys(article)

        # Cross-run check
        if url_key in seen_cache or title_key in seen_cache:
            cross_skipped += 1
            vlog(f"  [SEEN] {article['title'][:60]}")
            continue

        # Within-run title-overlap check
        words_a = normalize_words(article["title"])
        is_dup = False
        for kept in keep:
            words_b = normalize_words(kept["title"])
            if not words_a or not words_b:
                continue
            overlap = len(words_a & words_b)
            smaller = min(len(words_a), len(words_b))
            if smaller > 0 and (overlap / smaller) >= threshold:
                is_dup = True
                within_skipped += 1
                vlog(f"  [DUP] {article['title'][:60]}")
                break

        if not is_dup:
            keep.append(article)
            new_keys.append((url_key, title_key))

    log(f"Dedup: kept={len(keep)} | cross-run skip={cross_skipped} | within-run skip={within_skipped}")
    return keep, new_keys


# ═══════════════════════════════════════════════════════════════
# 📂 CATEGORIZATION
# ═══════════════════════════════════════════════════════════════


def select_top_story(articles, orbit_state):
    """
    Pick freshest high-score article from last 24h.
    Avoids repeating last run's top story title.
    Updates orbit_state in-place.
    """
    last_title = orbit_state.get("last_top_story", "")

    # Sort: score desc, then newest first
    def sort_key(a):
        dt = a.get("_parsed_dt") or datetime.min.replace(tzinfo=timezone.utc)
        return (a["score"], dt)

    candidates = sorted(articles, key=sort_key, reverse=True)

    chosen = None
    for c in candidates:
        if c["title"] != last_title:
            chosen = c
            break

    if chosen is None and candidates:
        chosen = candidates[0]

    if chosen:
        orbit_state["last_top_story"] = chosen["title"]
        orbit_state["last_run"] = datetime.now(timezone.utc).isoformat()
        vlog(f"  Top story: {chosen['title'][:70]}")

    return chosen


def categorize(articles, orbit_state):
    categories = {
        "🔥 TOP STORY":          [],
        "🚀 NEW LAUNCHES":       [],
        "🆓 FREE & OPEN SOURCE": [],
        "🔬 RESEARCH":           [],
        "💰 INDUSTRY & FUNDING": [],
        "🌐 COMMUNITY BUZZ":     [],
        "📌 QUICK HITS":         [],
    }

    if not articles:
        return categories

    top = select_top_story(articles, orbit_state)
    if top:
        categories["🔥 TOP STORY"].append(top)

    remaining = [a for a in articles if a is not top]
    assigned = set()

    def matches(article, keywords):
        text = (article["title"] + " " + article.get("description", "")).lower()
        return any(kw in text for kw in keywords)

    for i, article in enumerate(remaining):
        source_lower = article["source"].lower()

        if matches(article, CAT_LAUNCHES):
            # NEW LAUNCHES: strict <24h (already guaranteed, but explicit)
            if is_within_hours(article, 24):
                categories["🚀 NEW LAUNCHES"].append(article)
                assigned.add(i)
        elif matches(article, CAT_OPENSOURCE):
            categories["🆓 FREE & OPEN SOURCE"].append(article)
            assigned.add(i)
        elif matches(article, CAT_RESEARCH):
            categories["🔬 RESEARCH"].append(article)
            assigned.add(i)
        elif matches(article, CAT_INDUSTRY):
            categories["💰 INDUSTRY & FUNDING"].append(article)
            assigned.add(i)
        elif source_lower in CAT_COMMUNITY_SOURCES:
            # COMMUNITY BUZZ: strict <12h
            if is_within_hours(article, 12):
                categories["🌐 COMMUNITY BUZZ"].append(article)
                assigned.add(i)

    for i, article in enumerate(remaining):
        if i not in assigned:
            categories["📌 QUICK HITS"].append(article)

    # Drop empty sections
    return {k: v for k, v in categories.items() if v}


# ═══════════════════════════════════════════════════════════════
# 🎨 HTML EMAIL TEMPLATE
# ═══════════════════════════════════════════════════════════════


def score_dots(score):
    filled = min(score, 5)
    empty  = 5 - filled
    dots  = '<span style="color:#7c3aed;">●</span>' * filled
    dots += '<span style="color:#333;">●</span>'    * empty
    return f'<span style="font-size:12px;letter-spacing:2px;">{dots}</span>'


def render_article_card(article, is_top=False):
    title  = html_escape(article["title"])
    link   = html_escape(article["link"])
    source = html_escape(article["source"])
    ts     = format_timestamp(article)
    desc   = html_escape(article.get("description", "")[:180])
    score  = article.get("score", 0)

    border_color = "#7c3aed" if is_top else "#2a2a2a"
    bg           = "#1e1030" if is_top else "#1a1a1a"
    title_size   = "20px"   if is_top else "15px"
    padding      = "24px"   if is_top else "18px"

    top_badge = ""
    if is_top:
        top_badge = """
        <div style="display:inline-block;background:linear-gradient(135deg,#7c3aed,#a855f7);
                     color:#fff;font-size:10px;font-weight:700;letter-spacing:1.5px;
                     padding:3px 10px;border-radius:4px;margin-bottom:12px;text-transform:uppercase;">
            TOP STORY
        </div><br>
        """

    return f"""
    <div style="background:{bg};border:1px solid {border_color};border-radius:12px;
                padding:{padding};margin-bottom:12px;transition:all 0.2s;">
        {top_badge}
        <a href="{link}" target="_blank"
           style="color:#e5e5e5;text-decoration:none;font-size:{title_size};
                  font-weight:600;line-height:1.4;display:block;margin-bottom:8px;">
            {title}
        </a>
        {"<p style='color:#999;font-size:13px;line-height:1.5;margin:0 0 10px;'>" + desc + "</p>" if desc and is_top else ""}
        <div style="display:flex;align-items:center;gap:12px;flex-wrap:wrap;">
            <span style="background:#252525;color:#a78bfa;font-size:11px;font-weight:600;
                         padding:3px 8px;border-radius:4px;">{source}</span>
            <span style="color:#666;font-size:11px;">{ts}</span>
            {score_dots(score)}
        </div>
    </div>
    """


def render_section(title, articles, is_top_section=False):
    if not articles:
        return ""
    cards = "".join(render_article_card(a, is_top=is_top_section) for a in articles)
    return f"""
    <div style="margin-bottom:32px;">
        <h2 style="color:#e5e5e5;font-size:18px;font-weight:700;margin:0 0 16px;
                   padding-bottom:10px;border-bottom:1px solid #252525;">
            {title}
        </h2>
        {cards}
    </div>
    """


def build_html(categories, stats):
    today = datetime.now().strftime("%A, %B %d, %Y")
    total = sum(len(v) for v in categories.values())

    sections_html = ""
    for cat_name, cat_articles in categories.items():
        is_top = (cat_name == "🔥 TOP STORY")
        sections_html += render_section(cat_name, cat_articles, is_top_section=is_top)

    stats_line = (
        f"fetched {stats['fetched']} · "
        f"{stats['fresh']} fresh · "
        f"{stats['filtered']} filtered · "
        f"{total} in digest"
    )

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>AI-ORBIT Digest</title>
</head>
<body style="margin:0;padding:0;background:#0d0d0d;font-family:'Segoe UI',Roboto,'Helvetica Neue',Arial,sans-serif;">
<div style="max-width:640px;margin:0 auto;padding:20px;">

    <!-- ═══ HEADER ═══ -->
    <div style="text-align:center;padding:40px 20px 32px;border-bottom:1px solid #1a1a1a;margin-bottom:32px;">
        <div style="font-size:48px;margin-bottom:4px;">🛸</div>
        <h1 style="margin:0;font-size:36px;font-weight:800;
                   background:linear-gradient(135deg,#7c3aed,#a855f7,#c084fc);
                   -webkit-background-clip:text;-webkit-text-fill-color:transparent;
                   background-clip:text;letter-spacing:-0.5px;">
            AI-ORBIT
        </h1>
        <p style="color:#666;font-size:13px;margin:8px 0 0;letter-spacing:3px;text-transform:uppercase;">
            Nothing escapes orbit.
        </p>
        <p style="color:#555;font-size:12px;margin:12px 0 0;">{today} &nbsp;·&nbsp; {total} articles curated</p>
    </div>

    <!-- ═══ CONTENT ═══ -->
    {sections_html}

    <!-- ═══ FOOTER ═══ -->
    <div style="text-align:center;padding:32px 20px;border-top:1px solid #1a1a1a;margin-top:16px;">
        <p style="color:#444;font-size:11px;margin:0 0 6px;letter-spacing:1px;">
            Built with pure Python. Zero dependencies. Open source.
        </p>
        <p style="color:#444;font-size:10px;margin:0 0 4px;">{stats_line}</p>
        <p style="color:#333;font-size:10px;margin:0;">
            🛸 AI-ORBIT &nbsp;·&nbsp; Powered by {len(RSS_FEEDS)} RSS feeds &nbsp;·&nbsp; Curated by code
        </p>
    </div>

</div>
</body>
</html>"""

    return html


# ═══════════════════════════════════════════════════════════════
# 📧 EMAIL SENDING
# ═══════════════════════════════════════════════════════════════


def send_email(html_content):
    if not GMAIL_ADDRESS or not GMAIL_APP_PASSWORD or not RECIPIENT_EMAIL:
        print("\n❌ ERROR: Email credentials not configured!")
        print("   Set GMAIL_ADDRESS, GMAIL_APP_PASSWORD, and RECIPIENT_EMAIL")
        print("   either in the script or as environment variables.")
        sys.exit(1)

    today = datetime.now().strftime("%b %d, %Y")
    msg = MIMEMultipart("alternative")
    msg["Subject"] = f"🛸 AI-ORBIT Digest — {today}"
    msg["From"]    = f"AI-ORBIT <{GMAIL_ADDRESS}>"
    msg["To"]      = RECIPIENT_EMAIL

    plain = "AI-ORBIT Digest\nView this email in an HTML-capable client for the full experience."
    msg.attach(MIMEText(plain, "plain", "utf-8"))
    msg.attach(MIMEText(html_content, "html", "utf-8"))

    try:
        context = ssl.create_default_context()
        with smtplib.SMTP("smtp.gmail.com", 587) as server:
            server.ehlo()
            server.starttls(context=context)
            server.ehlo()
            server.login(GMAIL_ADDRESS, GMAIL_APP_PASSWORD)
            server.sendmail(GMAIL_ADDRESS, RECIPIENT_EMAIL, msg.as_string())
        log(f"📧 Email sent to {RECIPIENT_EMAIL}")
        return True
    except smtplib.SMTPAuthenticationError:
        print("\n❌ SMTP Authentication Failed!")
        print("   Make sure you're using a Gmail App Password, not your regular password.")
        print("   Guide: https://support.google.com/accounts/answer/185833")
        return False
    except Exception as e:
        print(f"\n❌ Email sending failed: {type(e).__name__} — {e}")
        return False


# ═══════════════════════════════════════════════════════════════
# 🚀 MAIN
# ═══════════════════════════════════════════════════════════════


def main():
    print()
    print("  ╔══════════════════════════════════════════════╗")
    print("  ║  🛸 AI-ORBIT — AI News Digest                ║")
    print("  ║  Nothing escapes orbit.                      ║")
    if VERBOSE:
        print("  ║  [VERBOSE MODE ON]                           ║")
    print("  ╚══════════════════════════════════════════════╝")
    print()

    # Load persistent state
    seen_cache  = load_seen_cache()
    orbit_state = load_orbit_state()

    # 1. Fetch
    articles = fetch_all_feeds()
    total_fetched = len(articles)
    if not articles:
        log("No articles fetched from any feed. Exiting.")
        sys.exit(1)

    # 2. Freshness filter — strict 24h
    articles, filtered_count = filter_fresh(articles)
    total_fresh = len(articles)

    if total_fresh < 5:
        print()
        print(f"  ⚠️  WARNING: Only {total_fresh} fresh article(s) found in the last 24h (minimum: 5).")
        print("   Feeds may be slow or all recent items already seen.")
        print("   Exiting without sending.")
        sys.exit(0)

    # 3. Score
    articles = score_all(articles)
    log(f"Scored {len(articles)} articles (top score: {articles[0]['score']})")

    # 4. Dedup (cross-run + within-run)
    articles, new_keys = deduplicate(articles, seen_cache)

    if len(articles) < 5:
        print()
        print(f"  ⚠️  WARNING: Only {len(articles)} unique article(s) after dedup (minimum: 5).")
        print("   Exiting without sending.")
        # Still update cache so we don't retry the same articles next run
        now_iso = datetime.now(timezone.utc).isoformat()
        for url_key, title_key in new_keys:
            seen_cache[url_key]   = now_iso
            seen_cache[title_key] = now_iso
        save_seen_cache(seen_cache)
        sys.exit(0)

    # 5. Categorize (no section caps, top-story rotation, community buzz <12h)
    categories = categorize(articles, orbit_state)

    # 6. Persist state + cache
    now_iso = datetime.now(timezone.utc).isoformat()
    for url_key, title_key in new_keys:
        seen_cache[url_key]   = now_iso
        seen_cache[title_key] = now_iso
    save_seen_cache(seen_cache)
    save_orbit_state(orbit_state)

    # Summary
    total_shown = sum(len(v) for v in categories.values())
    print()
    log("─── Section breakdown ───────────────────────")
    for cat, items in categories.items():
        log(f"  {cat}: {len(items)} articles")
    log("─────────────────────────────────────────────")
    log(f"Fetched: {total_fetched}  |  Fresh (<24h): {total_fresh}  |  Filtered: {filtered_count}  |  In digest: {total_shown}")
    print()

    stats = {"fetched": total_fetched, "fresh": total_fresh, "filtered": filtered_count}

    # 7. Build HTML
    html = build_html(categories, stats)
    log(f"HTML built ({len(html):,} bytes)")

    # 8. Send
    success = send_email(html)

    if success:
        print()
        print("  ✅ AI-ORBIT digest sent successfully!")
        print()
    else:
        sys.exit(1)


if __name__ == "__main__":
    main()


# ═══════════════════════════════════════════════════════════════
# 📦 GITHUB ACTIONS WORKFLOW
# ═══════════════════════════════════════════════════════════════
#
# Save as .github/workflows/daily.yml
#
# ---
# name: 🛸 AI-ORBIT Daily Digest
#
# on:
#   schedule:
#     - cron: "30 2 * * *"   # 8:00 AM IST
#   workflow_dispatch:
#
# jobs:
#   send-digest:
#     runs-on: ubuntu-latest
#     steps:
#       - uses: actions/checkout@v4
#       - uses: actions/setup-python@v5
#         with:
#           python-version: "3.12"
#       - name: Run AI-ORBIT
#         env:
#           GMAIL_ADDRESS:      ${{ secrets.GMAIL_ADDRESS }}
#           GMAIL_APP_PASSWORD: ${{ secrets.GMAIL_APP_PASSWORD }}
#           RECIPIENT_EMAIL:    ${{ secrets.RECIPIENT_EMAIL }}
#         run: python main.py
# ---
