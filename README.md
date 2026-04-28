# 🛸 AI-ORBIT

**Nothing escapes orbit.**

A zero-dependency Python tool that fetches AI news from 13 RSS feeds, scores and deduplicates articles, and sends a beautifully designed dark-themed HTML email digest.

![Python](https://img.shields.io/badge/Python-3.8+-blue?logo=python)
![Dependencies](https://img.shields.io/badge/Dependencies-Zero-green)
![License](https://img.shields.io/badge/License-MIT-purple)

---

## ✨ Features

- **13 RSS Sources** — Hacker News, arXiv, TechCrunch, Reddit, OpenAI, Anthropic, DeepMind, and more
- **Smart Scoring** — Articles scored 0–10 based on keyword relevance (HIGH/MEDIUM/LOW tiers)
- **Deduplication** — Removes duplicate articles using title word overlap (60% threshold)
- **7 Categories** — Top Story, Launches, Open Source, Research, Industry, Community, Quick Hits
- **Dark Theme Email** — Clean, modern HTML newsletter with purple accents
- **Zero Dependencies** — Pure Python stdlib. No `pip install`. No virtual env.
- **GitHub Actions** — Automated daily digest at 8:00 AM IST

---

## 🚀 Quick Start

### 1. Clone the repo

```bash
git clone https://github.com/YOUR_USERNAME/AI-ORBIT.git
cd AI-ORBIT
```

### 2. Get a Gmail App Password

> ⚠️ You need a **Gmail App Password**, not your regular Gmail password.

1. Go to [Google Account Security](https://myaccount.google.com/security)
2. Enable **2-Step Verification** if not already enabled
3. Go to [App Passwords](https://myaccount.google.com/apppasswords)
4. Select **Mail** → **Other (Custom name)** → Enter `AI-ORBIT`
5. Click **Generate** — copy the 16-character password

### 3. Run locally

**Option A: Environment variables (recommended)**

```bash
export GMAIL_ADDRESS="you@gmail.com"
export GMAIL_APP_PASSWORD="xxxx xxxx xxxx xxxx"
export RECIPIENT_EMAIL="you@gmail.com"

python main.py
```

**Option B: Edit the config in `main.py`**

Open `main.py` and fill in the top config section:

```python
GMAIL_ADDRESS = "you@gmail.com"
GMAIL_APP_PASSWORD = "xxxx xxxx xxxx xxxx"
RECIPIENT_EMAIL = "you@gmail.com"
```

Then run:

```bash
python main.py
```

---

## ⚙️ GitHub Actions Setup (Automated Daily Digest)

### 1. Push to GitHub

```bash
git init
git add .
git commit -m "🛸 Initial AI-ORBIT setup"
git remote add origin https://github.com/YOUR_USERNAME/AI-ORBIT.git
git push -u origin main
```

### 2. Add GitHub Secrets

Go to your repo → **Settings** → **Secrets and variables** → **Actions** → **New repository secret**

Add these three secrets:

| Secret Name          | Value                          |
|----------------------|--------------------------------|
| `GMAIL_ADDRESS`      | Your Gmail address             |
| `GMAIL_APP_PASSWORD` | Your 16-char App Password      |
| `RECIPIENT_EMAIL`    | Where to send the digest       |

### 3. Done!

The workflow runs automatically at **8:00 AM IST** (2:30 AM UTC) every day.

You can also trigger it manually:
- Go to **Actions** → **🛸 AI-ORBIT Daily Digest** → **Run workflow**

---

## 📡 RSS Sources

| # | Source | Feed |
|---|--------|------|
| 1 | Hacker News | AI/LLM/GPT stories |
| 2 | Hugging Face Blog | Official blog |
| 3 | arXiv cs.AI | Latest AI papers |
| 4 | TechCrunch | AI category |
| 5 | VentureBeat | AI category |
| 6 | r/MachineLearning | Reddit |
| 7 | r/LocalLLaMA | Reddit |
| 8 | Google DeepMind | Official blog |
| 9 | OpenAI | Official blog |
| 10 | Anthropic | Official blog |
| 11 | MIT Tech Review | All articles |
| 12 | Import AI | Jack Clark's newsletter |
| 13 | The Batch | DeepLearning.AI |

---

## 🎯 Scoring System

Articles are scored 0–10 based on keyword matches:

| Tier | Points | Keywords |
|------|--------|----------|
| 🔴 HIGH | 3 pts | launch, release, free, open source, beats, new model, gpt, claude, gemini, llama, mistral, openai, anthropic, deepmind, benchmark |
| 🟡 MEDIUM | 2 pts | ai, llm, model, agent, training, research, paper |
| 🟢 LOW | 1 pt | tech, neural, data, compute, chip, gpu |

---

## 📂 Categories

| Category | Criteria |
|----------|----------|
| 🔥 Top Story | Highest scored article |
| 🚀 New Launches | launch, release, announce, new, debut |
| 🆓 Free & Open Source | free, open source, weights, huggingface |
| 🔬 Research | paper, arxiv, research, study, benchmark |
| 💰 Industry & Funding | funding, investment, billion, startup, acquire |
| 🌐 Community Buzz | Reddit or Hacker News source |
| 📌 Quick Hits | Everything else (max 10) |

---

## 🛠️ Configuration

Edit these at the top of `main.py`:

```python
GMAIL_ADDRESS = ""           # Your Gmail
GMAIL_APP_PASSWORD = ""      # 16-char App Password
RECIPIENT_EMAIL = ""         # Recipient email
MAX_ARTICLES_PER_SECTION = 5 # Max articles per category
```

---

## 📦 Project Structure

```
AI-ORBIT/
├── main.py                        # Single-file tool (everything)
├── README.md                      # This file
└── .github/
    └── workflows/
        └── daily.yml              # GitHub Actions cron job
```

---

## 📜 License

MIT — do whatever you want with it.

---

<div align="center">

**Built with pure Python. Zero dependencies. Open source.**

🛸 *Nothing escapes orbit.*

</div>
