from datetime import date

SECTIONS = [
    ("top",        "🔥 TOP STORIES",         "Top-scored AI stories of the day."),
    ("launches",   "🚀 NEW LAUNCHES",         "New model releases and product announcements."),
    ("opensource", "🆓 FREE & OPEN SOURCE",   "Open weights, free models, and OSS releases."),
    ("research",   "🔬 RESEARCH",             "Papers, benchmarks, and academic findings."),
    ("industry",   "💰 INDUSTRY",             "Funding rounds, acquisitions, and business moves."),
    ("community",  "🌐 COMMUNITY BUZZ",       "Top discussions from Reddit and Hacker News."),
    ("quickhits",  "📌 QUICK HITS",           "More AI news worth a glance."),
]

SECTION_ORDER = [s[0] for s in SECTIONS]
SECTION_META = {s[0]: (s[1], s[2]) for s in SECTIONS}

TOP_SCORE_THRESHOLD = 3


def _article_html(article: dict) -> str:
    title = article.get("title", "Untitled")
    link = article.get("link", "#")
    source = article.get("source", "Unknown")
    date_str = article.get("date", "")
    score = article.get("score", 0)

    meta = f"{source}"
    if date_str:
        meta += f" &bull; {date_str}"

    return f"""
      <div class="article">
        <a href="{link}" class="article-title">{title}</a>
        <div class="article-meta">{meta} <span class="score">&#9733; {score}</span></div>
      </div>"""


def _section_html(section_id: str, articles: list[dict]) -> str:
    if not articles:
        return ""
    label, desc = SECTION_META[section_id]
    items = "\n".join(_article_html(a) for a in articles)
    return f"""
    <div class="section">
      <h2>{label}</h2>
      <p class="section-desc">{desc}</p>
      {items}
    </div>"""


def build_html(articles: list[dict], digest_date: str | None = None) -> str:
    if digest_date is None:
        digest_date = date.today().strftime("%B %d, %Y")

    # Bucket articles
    buckets: dict[str, list[dict]] = {s: [] for s in SECTION_ORDER}
    top_ids: set[int] = set()

    # Top stories: score >= threshold, not already community
    for art in articles:
        if art.get("score", 0) >= TOP_SCORE_THRESHOLD and art.get("section") != "community":
            buckets["top"].append(art)
            top_ids.add(id(art))

    for art in articles:
        if id(art) in top_ids:
            continue
        section = art.get("section", "quickhits")
        if section in buckets:
            buckets[section].append(art)
        else:
            buckets["quickhits"].append(art)

    total = sum(len(v) for v in buckets.values())
    sections_html = "\n".join(
        _section_html(s_id, buckets[s_id]) for s_id in SECTION_ORDER
    )

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>AIRadar — Daily AI Digest | {digest_date}</title>
<style>
  body {{
    font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
    background: #0f0f0f;
    color: #e0e0e0;
    margin: 0;
    padding: 0;
  }}
  .wrapper {{
    max-width: 680px;
    margin: 0 auto;
    padding: 24px 16px;
  }}
  .header {{
    border-bottom: 2px solid #333;
    padding-bottom: 16px;
    margin-bottom: 24px;
  }}
  .header h1 {{
    margin: 0 0 4px;
    font-size: 24px;
    color: #fff;
  }}
  .header .subtitle {{
    color: #888;
    font-size: 13px;
    margin: 0;
  }}
  .section {{
    margin-bottom: 32px;
  }}
  .section h2 {{
    font-size: 17px;
    color: #fff;
    margin: 0 0 4px;
    border-left: 3px solid #4a9eff;
    padding-left: 10px;
  }}
  .section-desc {{
    color: #666;
    font-size: 12px;
    margin: 0 0 12px 13px;
  }}
  .article {{
    padding: 10px 0;
    border-bottom: 1px solid #222;
  }}
  .article:last-child {{
    border-bottom: none;
  }}
  .article-title {{
    display: block;
    color: #a8d8ff;
    text-decoration: none;
    font-size: 14px;
    font-weight: 600;
    line-height: 1.4;
    margin-bottom: 3px;
  }}
  .article-title:hover {{
    color: #fff;
    text-decoration: underline;
  }}
  .article-meta {{
    color: #666;
    font-size: 12px;
  }}
  .score {{
    color: #f4c542;
    font-size: 11px;
  }}
  .footer {{
    margin-top: 32px;
    padding-top: 16px;
    border-top: 1px solid #333;
    color: #555;
    font-size: 12px;
    text-align: center;
  }}
  .stats {{
    background: #1a1a1a;
    border-radius: 6px;
    padding: 10px 14px;
    margin-bottom: 24px;
    font-size: 12px;
    color: #888;
  }}
</style>
</head>
<body>
<div class="wrapper">
  <div class="header">
    <h1>🤖 AIRadar</h1>
    <p class="subtitle">Daily AI Digest &bull; {digest_date}</p>
  </div>
  <div class="stats">
    {total} articles curated from 13 sources &bull; Ranked by relevance score
  </div>
  {sections_html}
  <div class="footer">
    <p>AIRadar — Your daily AI radar. Open source.<br>
    Fetched from public RSS feeds. No tracking.</p>
  </div>
</div>
</body>
</html>"""


def build_subject(digest_date: str | None = None) -> str:
    if digest_date is None:
        digest_date = date.today().strftime("%B %d, %Y")
    return f"🤖 AIRadar — Daily AI Digest | {digest_date}"
