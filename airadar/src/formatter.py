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
SECTION_MAX = 9


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
    label, desc = SECTION_META[section_id]
    if not articles:
        placeholder = '<div class="article"><em style="color:#555">No articles in this category today.</em></div>'
        return f"""
    <div class="section">
      <h2>{label} (0)</h2>
      <p class="section-desc">{desc}</p>
      {placeholder}
    </div>"""
    capped = sorted(articles, key=lambda a: a.get("score", 0), reverse=True)[:SECTION_MAX]
    items = "\n".join(_article_html(a) for a in capped)
    return f"""
    <div class="section">
      <h2>{label} ({len(capped)})</h2>
      <p class="section-desc">{desc}</p>
      {items}
    </div>"""


def _feed_health_html(health: dict | None, raw_count: int, dedup_count: int, run_seconds: float) -> str:
    if health is None:
        health = {"healthy": [], "degraded": [], "dead": []}
    healthy = health.get("healthy", [])
    degraded = health.get("degraded", [])
    dead = health.get("dead", [])

    def _names(urls: list) -> str:
        from urllib.parse import urlparse
        names = []
        for u in urls:
            host = urlparse(u).netloc.replace("www.", "")
            names.append(host)
        return ", ".join(names) if names else "—"

    degraded_list = f" ({_names(degraded)})" if degraded else ""
    dead_list = f" ({_names(dead)})" if dead else ""

    return f"""
    <div class="section">
      <h2>📡 FEED HEALTH</h2>
      <div class="stats" style="font-size:12px;line-height:1.8">
        Healthy feeds: {len(healthy)}<br>
        Degraded feeds: {len(degraded)}{degraded_list}<br>
        Dead feeds: {len(dead)}{dead_list}<br>
        Total articles fetched: {raw_count}<br>
        After dedup: {dedup_count}<br>
        Run time: {run_seconds:.1f}s
      </div>
    </div>"""


def build_html(
    articles: list[dict],
    digest_date: str | None = None,
    health: dict | None = None,
    raw_count: int = 0,
    dedup_count: int = 0,
    run_seconds: float = 0.0,
) -> str:
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

    # Apply per-section cap and count
    for s_id in SECTION_ORDER:
        if len(buckets[s_id]) > SECTION_MAX:
            buckets[s_id] = sorted(buckets[s_id], key=lambda a: a.get("score", 0), reverse=True)[:SECTION_MAX]

    total = sum(len(v) for v in buckets.values())
    sections_html = "\n".join(
        _section_html(s_id, buckets[s_id]) for s_id in SECTION_ORDER
    )
    health_html = _feed_health_html(health, raw_count, dedup_count, run_seconds)

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>AI-ORBIT — Daily AI Digest | {digest_date}</title>
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
    <h1>🛸 AI-ORBIT</h1>
    <p class="subtitle">Daily AI Digest &bull; {digest_date}</p>
  </div>
  <div class="stats">
    {total} articles curated &bull; Ranked by relevance score
  </div>
  {sections_html}
  {health_html}
  <div class="footer">
    <p>AI-ORBIT — Your daily AI radar. Open source.<br>
    Fetched from public RSS feeds. No tracking.</p>
  </div>
</div>
</body>
</html>"""


def build_subject(digest_date: str | None = None, article_count: int = 0) -> str:
    if digest_date is None:
        digest_date = date.today().strftime("%B %d, %Y")
    count_str = f" | {article_count} articles" if article_count else ""
    return f"🛸 AI-ORBIT Daily Digest | {digest_date}{count_str}"
