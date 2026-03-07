# 📰 AI News Assistant

<div align="center">

![Python](https://img.shields.io/badge/Python-3.9%2B-3776AB?style=for-the-badge&logo=python&logoColor=white)
![Streamlit](https://img.shields.io/badge/Streamlit-1.35%2B-FF4B4B?style=for-the-badge&logo=streamlit&logoColor=white)
![NewsAPI](https://img.shields.io/badge/NewsAPI-Live-22C55E?style=for-the-badge&logo=rss&logoColor=white)
![SQLite](https://img.shields.io/badge/SQLite-Persistent-003B57?style=for-the-badge&logo=sqlite&logoColor=white)
![License](https://img.shields.io/badge/License-MIT-F59E0B?style=for-the-badge)

**A production-grade, real-time news aggregator with AI-powered summaries,
sentiment analysis, source credibility scoring, and persistent bookmarks.**

[🚀 Live Demo](https://ai-news-assistant.streamlit.app) · [🐛 Report Bug](https://github.com/YuvarajOfl/ai-news-assistant/issues) · [💡 Request Feature](https://github.com/YuvarajOfl/ai-news-assistant/issues)

</div>

---

## 📸 Preview

> Clean, minimal ChatGPT-inspired UI with light/dark themes, real-time headlines, and AI-powered card summaries.

---

## ✨ Features

| Feature | Description |
|---|---|
| 🔍 **Live Search** | Search thousands of global sources in real time via NewsAPI |
| 🔥 **Trending Feed** | Top headlines across 9 categories: Tech, Business, Science, Health, Sports, Entertainment, Gaming, Movies, General |
| 🟢 **Sentiment Analysis** | Rule-based Positive / Neutral / Negative badge on every article |
| ✓ **Source Credibility** | Trusted / Known / Unverified labels based on publisher reputation |
| ⭐ **Persistent Bookmarks** | Save articles to SQLite — bookmarks survive page refreshes and restarts |
| ⎘ **Share Button** | One-click copy article URL to clipboard |
| 📄 **Pagination** | Navigate through pages of results — no 12-article cap |
| 🌍 **Multi-language** | 10 languages: English, Hindi, Tamil, German, Spanish, Portuguese, Italian, Japanese, Chinese, Arabic |
| 🎨 **3 Themes** | Default, Light, Dark — switch instantly without reloading |
| ⚡ **Quick Topics** | One-click pills: AI, Climate Change, Stock Market, Space, Cybersecurity, Startups |
| ⚙️ **Advanced Filters** | Sort by Latest / Relevant / Popular, date range, articles per page |
| 📊 **Stats Bar** | Article count, source count, active category and language |

---

## 🗂 Project Structure

```
ai-news-assistant/
├── app.py              ← Single-file Streamlit app (all logic + UI)
├── requirements.txt    ← Python dependencies
├── bookmarks.db        ← Auto-created SQLite database (gitignored)
└── README.md
```

---

## 🚀 Getting Started

### Prerequisites
- Python 3.9 or higher
- A free [NewsAPI key](https://newsapi.org/register)

### 1. Clone the repository
```bash
git clone https://github.com/YuvarajOfl/ai-news-assistant.git
cd ai-news-assistant
```

### 2. Install dependencies
```bash
pip install -r requirements.txt
```

### 3. Set your API key

**Option A — Environment variable (recommended for local dev)**
```bash
# macOS / Linux
export NEWS_API_KEY="your_api_key_here"

# Windows Command Prompt
set NEWS_API_KEY=your_api_key_here
```

**Option B — Streamlit secrets (for Streamlit Cloud)**

Create a file `.streamlit/secrets.toml`:
```toml
NEWS_API_KEY = "your_api_key_here"
```

### 4. Run the app
```bash
streamlit run app.py
```

Open [http://localhost:8501](http://localhost:8501) in your browser.

---

## ☁️ Deploying to Streamlit Cloud

1. Push your code to GitHub
2. Go to [share.streamlit.io](https://share.streamlit.io) → **New app**
3. Select your repo, branch (`main`), and set **Main file** to `app.py`
4. Under **Advanced settings → Secrets**, add:
   ```
   NEWS_API_KEY = "your_api_key_here"
   ```
5. Click **Deploy** — live in ~60 seconds

---

## 🛠 Tech Stack

| Layer | Technology |
|---|---|
| **UI Framework** | [Streamlit](https://streamlit.io/) |
| **News Data** | [NewsAPI](https://newsapi.org/) |
| **Storage** | SQLite (via Python `sqlite3`) |
| **Sentiment** | Rule-based keyword analysis (no external ML lib) |
| **Styling** | Custom CSS — Inter font, CSS variables, theme tokens |
| **Language** | Python 3.9+ |

---

## ⚙️ Configuration

All tuneable values are at the top of `app.py`:

| Constant | Default | Description |
|---|---|---|
| `CACHE_TTL` | `600` | API cache duration in seconds |
| `QUICK_TOPICS` | 6 topics | Pill buttons shown below search bar |
| `TRENDING_TABS` | 9 categories | Tabs in the Trending section |
| `HIGH_CRED` | ~18 sources | Publishers marked as "Trusted" |
| `POS_WORDS / NEG_WORDS` | ~25 each | Keyword sets for sentiment scoring |

---

## 🗺 Roadmap

- [ ] Transformer-based abstractive summarisation (BART / T5)
- [ ] User authentication (Google OAuth)
- [ ] Email digest — daily summary to inbox
- [ ] News bias / political lean meter
- [ ] Mobile-first responsive layout
- [ ] Export saved articles as PDF

---

## 🤝 Contributing

Contributions are welcome!

1. Fork the repository
2. Create a feature branch: `git checkout -b feature/your-feature`
3. Commit your changes: `git commit -m "Add your feature"`
4. Push to the branch: `git push origin feature/your-feature`
5. Open a Pull Request

---


## 👤 Author

**Yuvaraj T**
- GitHub: [@YuvarajOfl](https://github.com/YuvarajOfl)
- LinkedIn: [Yuvaraj T](www.linkedin.com/in/yuvaraj8)

---

<div align="center">
  <sub>Built with ❤️ using Python & Streamlit</sub>
</div>
