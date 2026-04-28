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
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from datetime import datetime, timezone, timedelta
from collections import defaultdict
from html import escape as html_escape

# ═══════════════════════════════════════════════════════════════
# ⚙️  CONFIGURATION — Fill in your credentials
# ═══════════════════════════════════════════════════════════════

GMAIL_ADDRESS = os.environ.get("GMAIL_ADDRESS", "")
GMAIL_APP_PASSWORD = os.environ.get("GMAIL_APP_PASSWORD", "")
RECIPIENT_EMAIL = os.environ.get("RECIPIENT_EMAIL", "")
MAX_ARTICLES_PER_SECTION = 5

# ═══════════════════════════════════════════════════════════════
# 📡 RSS FEED SOURCES
# ═══════════════════════════════════════════════════════════════

RSS_FEEDS = [
    {"url": "https://hnrss.org/newest?q=AI+LLM+GPT+machine+learning", "name": "Hacker News"},
    {"url": "https://huggingface.co/blog/feed.xml", "name": "Hugging Face"},
    {"url": "https://arxiv.org/rss/cs.AI", "name": "arXiv cs.AI"},
    {"url": "https://techcrunch.com/category/artificial-intelligence/feed/", "name": "TechCrunch"},
    {"url": "https://venturebeat.com/category/ai/feed/", "name": "VentureBeat"},
    {"url": "https://www.reddit.com/r/MachineLearning/.rss", "name": "r/MachineLearning"},
    {"url": "https://www.reddit.com/r/LocalLLaMA/.rss", "name": "r/LocalLLaMA"},
    {"url": "https://deepmind.google/blog/rss.xml", "name": "Google DeepMind"},
    {"url": "https://openai.com/blog/rss.xml", "name": "OpenAI"},
    {"url": "https://www.anthropic.com/rss.xml", "name": "Anthropic"},
    {"url": "https://www.technologyreview.com/feed/", "name": "MIT Tech Review"},
    {"url": "https://jack-clark.net/feed/", "name": "Import AI"},
    {"url": "https://read.deeplearning.ai/the-batch/rss/", "name": "The Batch"},
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

# Category keyword maps
CAT_LAUNCHES = ["launch", "release", "announce", "new", "debut"]
CAT_OPENSOURCE = ["free", "open source", "open-source", "weights", "huggingface", "hugging face"]
CAT_RESEARCH = ["paper", "arxiv", "research", "study", "benchmark"]
CAT_INDUSTRY = ["funding", "investment", "billion", "million", "startup", "acquire", "acquisition"]
CAT_COMMUNITY_SOURCES = ["hacker news", "r/machinelearning", "r/localllama"]

# ═══════════════════════════════════════════════════════════════
# 🔧 UTILITY FUNCTIONS
# ═══════════════════════════════════════════════════════════════


def log(msg):
    """Print a timestamped log message."""
    ts = datetime.now().strftime("%H:%M:%S")
    print(f"  [{ts}] {msg}")


def time_ago(dt_str):
    """Convert a datetime string to a human-readable 'time ago' format."""
    if not dt_str:
        return "recently"
    formats = [
        "%a, %d %b %Y %H:%M:%S %z",
        "%a, %d %b %Y %H:%M:%S %Z",
        "%Y-%m-%dT%H:%M:%S%z",
        "%Y-%m-%dT%H:%M:%SZ",
        "%Y-%m-%d %H:%M:%S",
        "%Y-%m-%dT%H:%M:%S.%f%z",
        "%Y-%m-%dT%H:%M:%S.%fZ",
        "%d %b %Y %H:%M:%S %z",
    ]
    parsed = None
    for fmt in formats:
        try:
            parsed = datetime.strptime(dt_str.strip(), fmt)
            break
        except (ValueError, TypeError):
            continue
    if not parsed:
        return "recently"
    now = datetime.now(timezone.utc)
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    diff = now - parsed
    seconds = int(diff.total_seconds())
    if seconds < 0:
        return "just now"
    if seconds < 60:
        return "just now"
    if seconds < 3600:
        m = seconds // 60
        return f"{m}m ago"
    if seconds < 86400:
        h = seconds // 3600
        return f"{h}h ago"
    d = seconds // 86400
    if d == 1:
        return "1 day ago"
    if d < 30:
        return f"{d} days ago"
    return f"{d // 30}mo ago"


def clean_text(text):
    """Strip HTML tags and extra whitespace from text."""
    if not text:
        return ""
    text = re.sub(r"<[^>]+>", "", text)
    text = re.sub(r"&[a-zA-Z]+;", " ", text)
    text = re.sub(r"&#\d+;", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def normalize_words(title):
    """Extract lowercase alphanumeric words from a title for dedup comparison."""
    return set(re.findall(r"[a-z0-9]+", title.lower()))


# ═══════════════════════════════════════════════════════════════
# 📡 RSS FETCHING
# ═══════════════════════════════════════════════════════════════


def fetch_feed(feed_info):
    """
    Fetch and parse a single RSS/Atom feed.
    Returns a list of article dicts. Skips silently on error.
    """
    url = feed_info["url"]
    source = feed_info["name"]
    articles = []

    try:
        req = urllib.request.Request(
            url,
            headers={
                "User-Agent": "AI-ORBIT/1.0 (Python; RSS Reader)",
                "Accept": "application/rss+xml, application/xml, text/xml, */*",
            },
        )
        with urllib.request.urlopen(req, timeout=10) as response:
            raw = response.read()

        # Try to decode
        for encoding in ("utf-8", "latin-1", "ascii"):
            try:
                xml_text = raw.decode(encoding)
                break
            except (UnicodeDecodeError, AttributeError):
                continue
        else:
            xml_text = raw.decode("utf-8", errors="replace")

        # Strip XML namespace prefixes for easier parsing
        xml_text = re.sub(r"xmlns\s*=\s*['\"][^'\"]*['\"]", "", xml_text, count=1)

        root = ET.fromstring(xml_text)

        # ── RSS 2.0 format ──
        for item in root.findall(".//item"):
            title = clean_text(
                (item.findtext("title") or "").strip()
            )
            link = (item.findtext("link") or "").strip()
            pub_date = (item.findtext("pubDate") or "").strip()
            description = clean_text(
                (item.findtext("description") or "")[:300]
            )
            if title and link:
                articles.append({
                    "title": title,
                    "link": link,
                    "source": source,
                    "pub_date": pub_date,
                    "description": description,
                    "score": 0,
                })

        # ── Atom format ──
        for entry in root.findall(".//entry"):
            title = clean_text(
                (entry.findtext("title") or "").strip()
            )
            link_el = entry.find("link")
            link = ""
            if link_el is not None:
                link = link_el.get("href", "") or link_el.text or ""
            link = link.strip()
            pub_date = (
                entry.findtext("published")
                or entry.findtext("updated")
                or ""
            ).strip()
            summary = clean_text(
                (entry.findtext("summary") or entry.findtext("content") or "")[:300]
            )
            if title and link:
                articles.append({
                    "title": title,
                    "link": link,
                    "source": source,
                    "pub_date": pub_date,
                    "description": summary,
                    "score": 0,
                })

        log(f"✅ {source}: {len(articles)} articles")

    except urllib.error.URLError as e:
        log(f"⚠️  {source}: Network error — {e.reason}")
    except ET.ParseError:
        log(f"⚠️  {source}: XML parse error")
    except Exception as e:
        log(f"⚠️  {source}: {type(e).__name__} — {e}")

    return articles


def fetch_all_feeds():
    """Fetch articles from all configured RSS feeds sequentially."""
    all_articles = []
    log(f"Fetching {len(RSS_FEEDS)} feeds...")
    print()
    for feed in RSS_FEEDS:
        articles = fetch_feed(feed)
        all_articles.extend(articles)
    print()
    log(f"Total raw articles: {len(all_articles)}")
    return all_articles


# ═══════════════════════════════════════════════════════════════
# 🎯 SCORING
# ═══════════════════════════════════════════════════════════════


def score_article(article):
    """Score an article 0–10 based on keyword hits in title + description."""
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
    """Score and sort all articles by score descending."""
    for a in articles:
        score_article(a)
    articles.sort(key=lambda x: x["score"], reverse=True)
    return articles


# ═══════════════════════════════════════════════════════════════
# 🧹 DEDUPLICATION
# ═══════════════════════════════════════════════════════════════


def deduplicate(articles, threshold=0.6):
    """
    Remove duplicate articles based on title word overlap.
    If two articles share ≥60% words in their titles, keep the higher-scored one.
    """
    keep = []
    for article in articles:
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
                break
        if not is_dup:
            keep.append(article)
    log(f"After dedup: {len(keep)} unique articles (removed {len(articles) - len(keep)} dupes)")
    return keep


# ═══════════════════════════════════════════════════════════════
# 📂 CATEGORIZATION
# ═══════════════════════════════════════════════════════════════


def categorize(articles):
    """
    Sort articles into themed sections.
    Returns an ordered dict of category → list of articles.
    """
    categories = {
        "🔥 TOP STORY": [],
        "🚀 NEW LAUNCHES": [],
        "🆓 FREE & OPEN SOURCE": [],
        "🔬 RESEARCH": [],
        "💰 INDUSTRY & FUNDING": [],
        "🌐 COMMUNITY BUZZ": [],
        "📌 QUICK HITS": [],
    }

    if not articles:
        return categories

    # Top story is always the highest scored article
    categories["🔥 TOP STORY"].append(articles[0])
    remaining = articles[1:]

    assigned = set()

    def matches_keywords(article, keywords):
        text = (article["title"] + " " + article.get("description", "")).lower()
        return any(kw in text for kw in keywords)

    # Pass 1: Categorize by keywords/source
    for i, article in enumerate(remaining):
        source_lower = article["source"].lower()

        if matches_keywords(article, CAT_LAUNCHES) and len(categories["🚀 NEW LAUNCHES"]) < MAX_ARTICLES_PER_SECTION:
            categories["🚀 NEW LAUNCHES"].append(article)
            assigned.add(i)
        elif matches_keywords(article, CAT_OPENSOURCE) and len(categories["🆓 FREE & OPEN SOURCE"]) < MAX_ARTICLES_PER_SECTION:
            categories["🆓 FREE & OPEN SOURCE"].append(article)
            assigned.add(i)
        elif matches_keywords(article, CAT_RESEARCH) and len(categories["🔬 RESEARCH"]) < MAX_ARTICLES_PER_SECTION:
            categories["🔬 RESEARCH"].append(article)
            assigned.add(i)
        elif matches_keywords(article, CAT_INDUSTRY) and len(categories["💰 INDUSTRY & FUNDING"]) < MAX_ARTICLES_PER_SECTION:
            categories["💰 INDUSTRY & FUNDING"].append(article)
            assigned.add(i)
        elif source_lower in CAT_COMMUNITY_SOURCES and len(categories["🌐 COMMUNITY BUZZ"]) < MAX_ARTICLES_PER_SECTION:
            categories["🌐 COMMUNITY BUZZ"].append(article)
            assigned.add(i)

    # Pass 2: Everything else → Quick Hits (max 10)
    for i, article in enumerate(remaining):
        if i not in assigned and len(categories["📌 QUICK HITS"]) < 10:
            categories["📌 QUICK HITS"].append(article)

    return categories


# ═══════════════════════════════════════════════════════════════
# 🎨 HTML EMAIL TEMPLATE
# ═══════════════════════════════════════════════════════════════


def score_dots(score):
    """Render score as colored dots (● per point, max 5)."""
    filled = min(score, 5)
    empty = 5 - filled
    dots = '<span style="color:#7c3aed;">●</span>' * filled
    dots += '<span style="color:#333;">●</span>' * empty
    return f'<span style="font-size:12px;letter-spacing:2px;">{dots}</span>'


def render_article_card(article, is_top=False):
    """Render a single article as an HTML card."""
    title = html_escape(article["title"])
    link = html_escape(article["link"])
    source = html_escape(article["source"])
    ago = time_ago(article.get("pub_date", ""))
    desc = html_escape(article.get("description", "")[:180])
    score = article.get("score", 0)

    border_color = "#7c3aed" if is_top else "#2a2a2a"
    bg = "#1e1030" if is_top else "#1a1a1a"
    title_size = "20px" if is_top else "15px"
    padding = "24px" if is_top else "18px"

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
            <span style="color:#666;font-size:11px;">{ago}</span>
            {score_dots(score)}
        </div>
    </div>
    """


def render_section(title, articles, is_top_section=False):
    """Render a full section with header and article cards."""
    if not articles:
        return ""

    cards = ""
    for a in articles:
        cards += render_article_card(a, is_top=is_top_section)

    return f"""
    <div style="margin-bottom:32px;">
        <h2 style="color:#e5e5e5;font-size:18px;font-weight:700;margin:0 0 16px;
                   padding-bottom:10px;border-bottom:1px solid #252525;">
            {title}
        </h2>
        {cards}
    </div>
    """


def build_html(categories):
    """Build the complete HTML email from categorized articles."""
    today = datetime.now().strftime("%A, %B %d, %Y")
    total = sum(len(v) for v in categories.values())

    sections_html = ""
    for cat_name, cat_articles in categories.items():
        is_top = (cat_name == "🔥 TOP STORY")
        sections_html += render_section(cat_name, cat_articles, is_top_section=is_top)

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
        <p style="color:#333;font-size:10px;margin:0;">
            🛸 AI-ORBIT &nbsp;·&nbsp; Powered by 13 RSS feeds &nbsp;·&nbsp; Curated by code
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
    """Send the HTML digest via Gmail SMTP with TLS."""
    if not GMAIL_ADDRESS or not GMAIL_APP_PASSWORD or not RECIPIENT_EMAIL:
        print("\n❌ ERROR: Email credentials not configured!")
        print("   Set GMAIL_ADDRESS, GMAIL_APP_PASSWORD, and RECIPIENT_EMAIL")
        print("   either in the script or as environment variables.")
        sys.exit(1)

    today = datetime.now().strftime("%b %d, %Y")
    msg = MIMEMultipart("alternative")
    msg["Subject"] = f"🛸 AI-ORBIT Digest — {today}"
    msg["From"] = f"AI-ORBIT <{GMAIL_ADDRESS}>"
    msg["To"] = RECIPIENT_EMAIL

    # Plain text fallback
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
# 🚀 MAIN ENTRY POINT
# ═══════════════════════════════════════════════════════════════


def main():
    print()
    print("  ╔══════════════════════════════════════════════╗")
    print("  ║  🛸 AI-ORBIT — AI News Digest                ║")
    print("  ║  Nothing escapes orbit.                      ║")
    print("  ╚══════════════════════════════════════════════╝")
    print()

    # 1. Fetch
    articles = fetch_all_feeds()
    if not articles:
        log("No articles fetched from any feed. Exiting.")
        sys.exit(1)

    # 2. Score
    articles = score_all(articles)
    log(f"Scored all articles (top score: {articles[0]['score']})")

    # 3. Deduplicate
    articles = deduplicate(articles)

    # 4. Categorize
    categories = categorize(articles)

    # Print summary
    print()
    for cat, items in categories.items():
        if items:
            log(f"{cat}: {len(items)} articles")
    print()

    # 5. Build HTML
    html = build_html(categories)
    log(f"HTML email built ({len(html):,} bytes)")

    # 6. Send
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
# Save the following as .github/workflows/daily.yml
#
# ---
# name: 🛸 AI-ORBIT Daily Digest
#
# on:
#   schedule:
#     # 8:00 AM IST = 2:30 AM UTC
#     - cron: "30 2 * * *"
#   workflow_dispatch:
#
# jobs:
#   send-digest:
#     runs-on: ubuntu-latest
#     steps:
#       - name: Checkout repository
#         uses: actions/checkout@v4
#
#       - name: Set up Python
#         uses: actions/setup-python@v5
#         with:
#           python-version: "3.12"
#
#       - name: Run AI-ORBIT
#         env:
#           GMAIL_ADDRESS: ${{ secrets.GMAIL_ADDRESS }}
#           GMAIL_APP_PASSWORD: ${{ secrets.GMAIL_APP_PASSWORD }}
#           RECIPIENT_EMAIL: ${{ secrets.RECIPIENT_EMAIL }}
#         run: python main.py
# ---
