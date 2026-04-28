# 🤖 AIRadar

**Daily AI news digest, delivered to your inbox. Pure Python stdlib. Zero dependencies.**

Fetches 13 AI RSS feeds, scores articles by relevance, organizes into smart sections, sends clean HTML email via Gmail — automatically every day at 8am IST via GitHub Actions.

---

## How It Works

1. GitHub Actions triggers at **8:00 AM IST (02:30 UTC)** daily
2. Fetches 13 RSS feeds (HN, Reddit, HuggingFace, arXiv, TechCrunch, etc.)
3. Scores each article by AI keyword relevance
4. Deduplicates near-identical titles
5. Organizes into sections: Top Stories / Launches / Open Source / Research / Industry / Community / Quick Hits
6. Sends clean HTML digest to configured email(s)

---

## Setup Guide

### 1. Fork This Repo

Click **Fork** on GitHub. You need your own copy to set secrets and run Actions.

### 2. Configure Recipients

Edit `config/config.json`:

```json
{
  "users": [
    {
      "name": "Your Name",
      "email": "your@email.com",
      "keywords": ["llm", "gpt", "release", "open source"]
    }
  ],
  ...
}
```

- `name` — used in logs
- `email` — where digest is sent
- `keywords` — extra keywords boosting relevance score for this user

### 3. Create a Gmail App Password

> **Important:** Gmail requires an App Password when 2FA is enabled (which is required for App Passwords to work). Do NOT use your regular Gmail password.

**Step-by-step:**

1. Go to your Google Account: [myaccount.google.com](https://myaccount.google.com)
2. Click **Security** in the left sidebar
3. Under "How you sign in to Google", click **2-Step Verification** → enable it if not already on
4. Go back to Security → scroll down → click **App passwords** (or search "App passwords")
5. Click **Select app** → choose **Mail**
6. Click **Select device** → choose **Other (Custom name)** → type `AIRadar`
7. Click **Generate**
8. Copy the 16-character password shown (no spaces needed)

### 4. Set GitHub Secrets

In your forked repo on GitHub:

1. Go to **Settings** → **Secrets and variables** → **Actions**
2. Click **New repository secret**
3. Add two secrets:

| Secret Name | Value |
|---|---|
| `GMAIL_USER` | Your Gmail address (e.g. `yourname@gmail.com`) |
| `GMAIL_APP_PASSWORD` | The 16-character App Password from step 3 |

### 5. Enable GitHub Actions

Go to the **Actions** tab in your fork → click **"I understand my workflows, go ahead and enable them"** if prompted.

### 6. Test It Manually

Actions tab → **AIRadar Daily Digest** → **Run workflow** → **Run workflow**.

Check your inbox within ~60 seconds.

---

## Customization

### Add or Remove RSS Feeds

Edit the `"feeds"` array in `config/config.json`:

```json
"feeds": [
  "https://hnrss.org/newest?q=AI+LLM",
  "https://your-new-feed.com/rss.xml"
]
```

Any standard RSS or Atom feed works. Each feed gets a 10-second timeout — dead feeds are silently skipped.

### Change Scoring Threshold

`"min_score": 1` — raise to `2` or `3` for stricter filtering (fewer, higher-quality articles).

### Change Max Articles

`"max_articles": 30` — lower to `15` for a shorter digest.

### Add More Users (Multi-User)

Each user in the `"users"` array gets their own digest email:

```json
"users": [
  {
    "name": "Alice",
    "email": "alice@gmail.com",
    "keywords": ["llm", "research", "arxiv"]
  },
  {
    "name": "Bob",
    "email": "bob@company.com",
    "keywords": ["funding", "product", "launch"]
  }
]
```

Each user can have different keyword boosts — Alice gets research-heavy digest, Bob gets industry news.

> **Note:** All users receive email from the same `GMAIL_USER` account. Gmail free tier allows ~500 emails/day, so multi-user is fine for personal use.

### Change Digest Time

Edit `.github/workflows/daily.yml`:

```yaml
- cron: "30 2 * * *"   # 02:30 UTC = 08:00 IST
```

[Cron time converter](https://crontab.guru/) — UTC only in GitHub Actions.

---

## File Structure

```
airadar/
├── .github/
│   └── workflows/
│       └── daily.yml        # GitHub Actions cron
├── src/
│   ├── fetcher.py           # RSS fetch + XML parse
│   ├── filter.py            # Scoring, dedup, section assignment
│   ├── formatter.py         # HTML email builder
│   └── emailer.py           # Gmail SMTP sender
├── config/
│   └── config.json          # Feeds, users, thresholds
├── main.py                  # Entry point
└── README.md
```

---

## Sections Explained

| Section | What Goes Here |
|---|---|
| 🔥 Top Stories | Score ≥ 3, any non-community source |
| 🚀 New Launches | Keywords: launch, release, announce, unveil |
| 🆓 Free & Open Source | Keywords: free, open source, weights, HuggingFace |
| 🔬 Research | Keywords: paper, arxiv, research, study |
| 💰 Industry | Keywords: funding, raises, acquires, valuation |
| 🌐 Community Buzz | Reddit and Hacker News posts |
| 📌 Quick Hits | Everything else that passed the score threshold |

---

## Running Locally

```bash
# Set env vars
export GMAIL_USER="you@gmail.com"
export GMAIL_APP_PASSWORD="abcdabcdabcdabcd"

# Run
python main.py
```

No pip install needed. Requires Python 3.10+.

---

## Troubleshooting

**No email received:**
- Check Actions tab → see if job ran → check logs
- Verify `GMAIL_USER` and `GMAIL_APP_PASSWORD` secrets are set correctly
- Confirm Gmail App Password is 16 chars, no spaces
- Make sure 2FA is enabled on the Gmail account

**"SMTPAuthenticationError":**
- App Password is wrong or expired — regenerate one
- Make sure you're using App Password, not your Gmail account password

**Too many or too few articles:**
- Raise `min_score` to filter more aggressively
- Lower `min_score` to 1 for maximum coverage
- Adjust `max_articles` cap

**Feed consistently failing:**
- Some feeds (e.g. OpenAI, Anthropic blogs) may have rate limits or bot blocks
- Remove dead feeds from `config.json` — others provide redundancy

---

## License

MIT — fork, modify, share freely.
