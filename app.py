# ── Standard library imports ──────────────────────────────────────────────────
import os           # For reading environment variables (API key)
import re           # For regex-based text cleaning
import json         # For bookmark serialization to localStorage
import hashlib      # For generating unique widget keys
import requests     # For making HTTP requests to NewsAPI and RSS feeds
from datetime import datetime, timezone, timedelta
from collections import Counter   # For counting word frequencies (trending topics)
from concurrent.futures import ThreadPoolExecutor, as_completed  # Parallel image fetch
from typing import Optional

import streamlit as st  # The web framework

# ── Page config (must be first Streamlit call) ────────────────────────────────
st.set_page_config(
    page_title="News Analytics Dashboard",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="collapsed",
)

# ══════════════════════════════════════════════════════════════════════════════
# SECTION 1: CONFIGURATION & CONSTANTS
# All magic numbers and lookup tables live here — easy to modify
# ══════════════════════════════════════════════════════════════════════════════

# ── API key: first try Streamlit secrets (cloud), then env var (local) ────────
try:    NEWS_API_KEY = st.secrets["NEWS_API_KEY"]
except: NEWS_API_KEY = os.getenv("NEWS_API_KEY", "")

# ── API endpoints ─────────────────────────────────────────────────────────────
EVERYTHING_EP    = "https://newsapi.org/v2/everything"
TOP_HEADLINES_EP = "https://newsapi.org/v2/top-headlines"

# Cache for 10 minutes so we don't hammer the API on every rerun
CACHE_TTL = 600

# ── UI constants ──────────────────────────────────────────────────────────────
QUICK_TOPICS = [
    "Artificial Intelligence", "Climate Change", "Stock Market",
    "Space Exploration",        "Cybersecurity",  "Startups",
]

SORT_OPTIONS = {"Latest": "publishedAt", "Relevant": "relevancy", "Popular": "popularity"}

CATEGORIES = ["technology","business","science","health","sports","entertainment","general"]

LANGUAGES = {
    "English":"en","Hindi":"hi","French":"fr","German":"de","Spanish":"es",
    "Portuguese":"pt","Italian":"it","Japanese":"ja","Chinese":"zh","Arabic":"ar",
}

TRENDING_TABS = [
    ("🌐","General","general"),  ("💻","Tech","technology"),
    ("📈","Business","business"),("🔬","Science","science"),
    ("🏥","Health","health"),    ("⚽","Sports","sports"),
    ("🎬","Entertainment","entertainment"),
    ("🎮","Gaming","gaming"),    ("🎥","Movies","movies"),
]

CAT_EMOJI = {
    "technology":"💻","business":"📈","science":"🔬","health":"🏥",
    "sports":"⚽","entertainment":"🎬","general":"🌐","gaming":"🎮","movies":"🎥",
}

# ── Source credibility tiers ──────────────────────────────────────────────────
# Manually curated — transparent and explainable (no black-box scoring)
HIGH_CRED = {
    "reuters","associated press","ap","bbc news","bbc","the guardian","npr",
    "bloomberg","financial times","the economist","wall street journal",
    "new york times","washington post","the verge","wired","techcrunch","ars technica",
}
MED_CRED = {
    "cnn","fox news","msnbc","cnbc","forbes","time","newsweek","usa today",
    "the atlantic","politico","axios","the hill","vice",
}

# ── Sentiment word dictionaries ───────────────────────────────────────────────
# These are the ONLY things used for sentiment — no ML, fully explainable.
# Score: +1 per positive word found, -1 per negative word found in the text.
# Final: positive_score > negative_score → Positive, etc.
POSITIVE_WORDS = {
    "breakthrough","surge","win","record","growth","profit","success","launch",
    "innovative","hope","recover","rise","gain","soar","achieve","milestone",
    "positive","strong","boost","advance","improve","lead","thrive","discovery",
    "agreement","expansion","award","recovery","opportunity","increase","benefit",
}
NEGATIVE_WORDS = {
    "crash","crisis","war","death","fail","loss","decline","fear","risk","terror",
    "collapse","scandal","fraud","disaster","attack","threat","drop","controversy",
    "ban","arrest","killed","wounded","emergency","warning","breach","hack","conflict",
    "recession","layoff","shutdown","protest","violence","explosion","accused",
}

# ── English stopwords for keyword extraction ──────────────────────────────────
# These common words are ignored when finding trending topics.
# We want meaningful words like "Tesla", "election", "AI" — not "the", "is", "a".
STOPWORDS = {
    "the","a","an","and","or","but","in","on","at","to","for","of","with","by",
    "from","is","are","was","were","be","been","being","have","has","had","do",
    "does","did","will","would","could","should","may","might","that","this",
    "it","its","as","up","out","than","so","if","about","into","over","after",
    "new","says","said","say","one","two","us","uk","can","also","more","how",
    "what","who","when","where","why","not","no","he","she","they","we","i",
    "his","her","their","our","your","my","all","just","now","get","make","go",
}

# ══════════════════════════════════════════════════════════════════════════════
# SECTION 2: THEME SYSTEM
# CSS variables allow instant theme switching without page reload
# ══════════════════════════════════════════════════════════════════════════════
THEMES = {
    "Default": {
        "bg":"#F7F8FA","sf":"#FFFFFF","bd":"#E5E7EB","ac":"#2563EB",
        "al":"#EFF6FF","t1":"#111827","t2":"#6B7280","t3":"#9CA3AF","ibg":"#FFFFFF",
    },
    "Light": {
        "bg":"#FFFFFF","sf":"#F9FAFB","bd":"#E5E7EB","ac":"#2563EB",
        "al":"#DBEAFE","t1":"#111827","t2":"#4B5563","t3":"#9CA3AF","ibg":"#FFFFFF",
    },
    "Dark": {
        "bg":"#212121","sf":"#2F2F2F","bd":"#3F3F3F","ac":"#5B9BFF",
        "al":"#1E3A5F","t1":"#ECECEC","t2":"#ABABAB","t3":"#6B6B6B","ibg":"#3F3F3F",
    },
}

# ── Initialize session state with defaults ────────────────────────────────────
# session_state persists values across Streamlit reruns (like a global variable)
DEFAULTS = dict(
    theme        = "Default",
    active_query = "Artificial Intelligence",
    sort_by      = "publishedAt",
    days_back    = 7,
    page_size    = 6,
    language     = "en",
    feed_page    = 1,
    auto_refresh = False,
    bookmarks    = [],    # list of saved article dicts
    bm_loaded    = False, # flag: have we loaded bookmarks from localStorage yet?
)
for k, v in DEFAULTS.items():
    if k not in st.session_state:
        setattr(st.session_state, k, v)

T = THEMES[st.session_state.theme]  # shorthand for current theme colors

# ══════════════════════════════════════════════════════════════════════════════
# SECTION 3: CSS INJECTION
# All styling in one place. Uses CSS variables so themes work instantly.
# ══════════════════════════════════════════════════════════════════════════════
st.markdown(f"""
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600&display=swap');

/* CSS custom properties (variables) — changing T[] re-injects these */
:root {{
  --bg:  {T['bg']}; --sf:  {T['sf']}; --bd:  {T['bd']};
  --ac:  {T['ac']}; --al:  {T['al']};
  --t1:  {T['t1']}; --t2:  {T['t2']}; --t3:  {T['t3']};
  --ibg: {T['ibg']};
  --r: 10px;
  --f: 'Inter', system-ui, sans-serif;
}}

*, *::before, *::after {{ box-sizing: border-box; margin: 0; padding: 0; }}
html, body, .stApp,
[data-testid="stAppViewContainer"],
[data-testid="stAppViewBlockContainer"],
[data-testid="block-container"],
.stMainBlockContainer, section.main, .main > div {{
  background: var(--bg) !important;
  color: var(--t1) !important;
  font-family: var(--f) !important;
}}

/* Hide Streamlit's default chrome (menu, footer, header bar) */
#MainMenu, footer, header,
[data-testid="stToolbar"], [data-testid="stDecoration"],
[data-testid="stStatusWidget"], [data-testid="stHeader"], .stAppHeader {{
  display: none !important; height: 0 !important; visibility: hidden !important;
}}

[data-testid="stAppViewBlockContainer"] {{ padding-top: 1rem !important; }}
[data-testid="block-container"]         {{ padding-top: 0 !important; }}

/* Sidebar */
[data-testid="stSidebar"],
[data-testid="stSidebar"] > div,
[data-testid="stSidebarContent"] {{
  background: {T['sf']} !important;
  border-right: 1px solid {T['bd']} !important;
}}
[data-testid="stSidebar"] * {{ color: {T['t1']} !important; font-family: var(--f) !important; }}
[data-testid="stSidebar"] label {{
  font-size: .75rem !important; font-weight: 600 !important;
  color: {T['t3']} !important; text-transform: uppercase; letter-spacing: .05em;
}}

/* Text input */
div[data-testid="stTextInput"] input {{
  background: var(--ibg) !important; color: var(--t1) !important;
  border: 1px solid var(--bd) !important; border-radius: var(--r) !important;
  font-size: .9rem !important; font-family: var(--f) !important;
  padding: .6rem .9rem !important; outline: none !important;
  box-shadow: none !important; transition: border-color .15s !important;
}}
div[data-testid="stTextInput"] input:focus {{
  border-color: var(--ac) !important;
  box-shadow: 0 0 0 3px {T['al']} !important;
}}
div[data-testid="stTextInput"] input::placeholder {{ color: var(--t3) !important; }}

/* Selectbox — explicit colors fix the black-dropdown bug on dark theme */
div[data-baseweb="select"] > div {{
  background: var(--ibg) !important; border: 1px solid var(--bd) !important;
  border-radius: var(--r) !important; color: var(--t1) !important;
  font-family: var(--f) !important;
}}
div[data-baseweb="select"] * {{ color: var(--t1) !important; background: transparent !important; }}
div[data-baseweb="select"] svg {{ fill: {T['t2']} !important; }}
[data-baseweb="popover"], [data-baseweb="popover"] > div,
ul[data-baseweb="menu"], ul[data-baseweb="menu"] > li {{
  background: {T['sf']} !important; border: 1px solid {T['bd']} !important;
  border-radius: var(--r) !important; color: {T['t1']} !important;
  font-family: var(--f) !important;
}}
li[role="option"] {{ color: {T['t1']} !important; background: {T['sf']} !important; font-size: .84rem !important; }}
li[role="option"]:hover {{ background: {T['al']} !important; color: {T['ac']} !important; }}

/* Buttons */
div[data-testid="stButton"] > button {{
  background: var(--sf) !important; color: var(--t2) !important;
  border: 1px solid var(--bd) !important; border-radius: var(--r) !important;
  font-size: .82rem !important; font-weight: 500 !important;
  font-family: var(--f) !important; padding: .45rem .9rem !important;
  transition: all .15s !important; cursor: pointer !important;
}}
div[data-testid="stButton"] > button:hover {{
  border-color: var(--ac) !important; color: var(--ac) !important; background: var(--al) !important;
}}
div[data-testid="stButton"] > button[kind="primary"] {{
  background: var(--ac) !important; border-color: var(--ac) !important;
  color: #fff !important; font-weight: 600 !important;
}}
div[data-testid="stButton"] > button[kind="primary"]:hover {{ opacity:.88 !important; color:#fff !important; }}

/* Slider */
[data-testid="stSlider"] p {{ color: {T['t3']} !important; font-size:.78rem !important; }}
[data-testid="stSlider"] [role="slider"] {{ background: {T['ac']} !important; }}

/* Tabs */
[data-testid="stTabs"] [data-baseweb="tab-list"] {{
  background: transparent !important; border-bottom: 1px solid var(--bd) !important; gap: 0;
}}
[data-testid="stTabs"] [data-baseweb="tab"] {{
  font-family: var(--f) !important; font-size: .85rem !important; font-weight: 500 !important;
  color: var(--t2) !important; background: transparent !important; border: none !important;
  border-bottom: 2px solid transparent !important; margin-bottom: -1px !important;
  padding: .65rem 1.1rem !important;
}}
[data-testid="stTabs"] [aria-selected="true"] {{
  color: {T['ac']} !important; border-bottom-color: {T['ac']} !important;
}}

/* Streamlit native chart/dataframe theming */
[data-testid="stArrowVegaLiteChart"] canvas {{ background: transparent !important; }}
.stDataFrame {{ background: var(--sf) !important; }}

/* ── Custom app components ── */

.app-nav {{
  display:flex; align-items:center; justify-content:space-between;
  padding:.9rem 0; margin-bottom:1.25rem; border-bottom:1px solid var(--bd);
}}
.nav-brand {{
  font-size:1.75rem; font-weight:700; color:var(--t1);
  display:flex; align-items:center; gap:.5rem; letter-spacing:-.02em;
}}
.nav-right {{ display:flex; align-items:center; gap:.6rem; font-size:.78rem; color:var(--t3); }}
.live-dot  {{
  width:7px; height:7px; border-radius:50%; background:#22C55E;
  display:inline-block; animation:blink 2s ease-in-out infinite;
}}
@keyframes blink {{ 0%,100%{{opacity:1}} 50%{{opacity:.2}} }}
.sv-badge {{
  background:var(--al); color:var(--ac); font-size:.7rem;
  font-weight:600; padding:2px 8px; border-radius:999px; border:1px solid var(--ac);
}}

.sec     {{ font-size:.72rem; font-weight:600; color:var(--t3); text-transform:uppercase; letter-spacing:.06em; margin-bottom:.55rem; }}
.sec-ttl {{ font-size:1rem; font-weight:600; color:var(--t1); margin-bottom:.85rem; }}

/* Stat chips row */
.stat-row {{ display:flex; gap:.45rem; flex-wrap:wrap; margin-bottom:1rem; }}
.stat-chip {{ background:var(--sf); border:1px solid var(--bd); border-radius:8px; padding:.4rem .75rem; }}
.stat-chip strong {{ display:block; font-size:.88rem; font-weight:600; color:var(--t1); }}
.stat-chip span   {{ font-size:.65rem; color:var(--t3); }}

/* Analytics section */
.analytics-box {{
  background:var(--sf); border:1px solid var(--bd); border-radius:var(--r);
  padding:1rem 1.2rem; margin-bottom:1rem;
}}
.analytics-title {{
  font-size:.78rem; font-weight:700; color:var(--t2);
  text-transform:uppercase; letter-spacing:.05em; margin-bottom:.75rem;
}}
.kw-pill {{
  display:inline-block; background:var(--al); color:var(--ac); border:1px solid var(--ac);
  font-size:.72rem; font-weight:600; padding:.2rem .6rem; border-radius:999px;
  margin:.18rem; cursor:default;
}}
.kw-count {{ font-size:.62rem; color:var(--t3); margin-left:.2rem; }}

/* Article card */
.nc {{
  background:var(--sf); border:1px solid var(--bd); border-radius:var(--r);
  overflow:hidden; display:flex; flex-direction:column; height:100%;
  transition:box-shadow .15s, transform .15s;
}}
.nc:hover {{ box-shadow:0 4px 16px rgba(0,0,0,.08); transform:translateY(-1px); }}
.nc-img {{ width:100%; height:152px; object-fit:cover; display:block; }}
.nc-ph  {{
  width:100%; height:152px;
  background:linear-gradient(135deg, var(--al) 0%, var(--bd) 100%);
  display:flex; align-items:center; justify-content:center; font-size:2rem;
}}
.nc-body  {{ padding:.78rem .88rem; flex:1; display:flex; flex-direction:column; gap:.2rem; }}
.nc-meta  {{ display:flex; align-items:center; gap:.3rem; flex-wrap:wrap; }}
.nc-src   {{
  font-size:.6rem; font-weight:700; text-transform:uppercase; letter-spacing:.04em;
  padding:.1rem .38rem; border-radius:999px; background:var(--al); color:var(--ac);
  max-width:95px; overflow:hidden; text-overflow:ellipsis; white-space:nowrap;
}}
.nc-time  {{ font-size:.62rem; color:var(--t3); }}
.nc-ttl   {{ font-size:.88rem; font-weight:600; line-height:1.45; color:var(--t1); flex:1; }}
.nc-sum   {{
  font-size:.75rem; color:var(--t2); line-height:1.55;
  display:-webkit-box; -webkit-line-clamp:3; -webkit-box-orient:vertical; overflow:hidden;
}}
.nc-tags  {{ display:flex; gap:.28rem; flex-wrap:wrap; }}
.badge-pos{{ background:#DCFCE7;color:#15803D;font-size:.58rem;font-weight:700;padding:.1rem .38rem;border-radius:999px; }}
.badge-neg{{ background:#FEE2E2;color:#B91C1C;font-size:.58rem;font-weight:700;padding:.1rem .38rem;border-radius:999px; }}
.badge-neu{{ background:var(--al);color:var(--ac);font-size:.58rem;font-weight:700;padding:.1rem .38rem;border-radius:999px; }}
.cred-hi  {{ background:#DCFCE7;color:#15803D;font-size:.56rem;font-weight:700;padding:.1rem .35rem;border-radius:999px; }}
.cred-md  {{ background:#FEF9C3;color:#A16207;font-size:.56rem;font-weight:700;padding:.1rem .35rem;border-radius:999px; }}
.cred-lo  {{ background:var(--bd);color:var(--t3);font-size:.56rem;font-weight:700;padding:.1rem .35rem;border-radius:999px; }}
.nc-foot  {{
  display:flex; align-items:center; justify-content:space-between;
  border-top:1px solid var(--bd); padding-top:.52rem; margin-top:.32rem;
}}
.nc-link  {{ font-size:.72rem; font-weight:600; color:var(--ac); text-decoration:none; }}
.nc-link:hover {{ text-decoration:underline; }}
.nc-rt    {{ font-size:.62rem; color:var(--t3); }}
.share-btn{{
  font-size:.6rem; font-weight:500; color:var(--t3); cursor:pointer;
  padding:.1rem .32rem; border:1px solid var(--bd); border-radius:5px;
  background:transparent; transition:all .12s;
}}
.share-btn:hover{{ color:var(--ac); border-color:var(--ac); background:var(--al); }}

/* Trending list */
.tr-item{{
  background:var(--sf); border:1px solid var(--bd); border-radius:var(--r);
  padding:.6rem .82rem; margin-bottom:.38rem;
  display:flex; align-items:flex-start; gap:.5rem;
}}
.tr-rank{{ font-size:1rem; font-weight:700; color:var(--bd); min-width:1rem; padding-top:1px; }}
.tr-ttl {{ font-size:.8rem; font-weight:500; color:var(--t1); line-height:1.42; }}
.tr-src {{ font-size:.64rem; color:var(--t3); margin-top:.1rem; }}

/* Empty state */
.empty{{
  text-align:center; padding:2.5rem 1rem;
  background:var(--sf); border:1px dashed var(--bd); border-radius:var(--r);
}}
.empty .ico{{ font-size:2rem; margin-bottom:.35rem; }}
.empty p{{ font-size:.8rem; color:var(--t3); line-height:1.6; }}

/* Fallback banner */
.fallback-banner{{
  background:#FEF9C3; border:1px solid #FDE047; border-radius:8px;
  padding:.55rem 1rem; font-size:.78rem; color:#854D0E; margin-bottom:.85rem;
}}

::-webkit-scrollbar{{ width:4px; }}
::-webkit-scrollbar-track{{ background:transparent; }}
::-webkit-scrollbar-thumb{{ background:var(--bd); border-radius:2px; }}
</style>
""", unsafe_allow_html=True)

# ══════════════════════════════════════════════════════════════════════════════
# SECTION 4: BOOKMARK PERSISTENCE
# Uses browser localStorage so saves survive server restarts (Streamlit Cloud)
# Architecture: JS writes to a hidden input → Python reads it on load
# ══════════════════════════════════════════════════════════════════════════════

_LS_KEY = "ainews_bookmarks_v1"  # localStorage key — change to reset all saves

def _bm_js_init():
    """
    On page load, read bookmarks from localStorage and push them
    into the hidden text input so Python can access them.
    This is the bridge between the browser (JS) and the server (Python).
    """
    st.markdown(f"""
    <script>
    (function() {{
        const key  = "{_LS_KEY}";
        const raw  = localStorage.getItem(key) || "[]";
        const inp  = window.parent.document.querySelector(
            'input[data-testid="stTextInput"][aria-label="__bm_store__"]'
        );
        if (inp) {{
            // Use native setter to bypass React's value tracking
            const setter = Object.getOwnPropertyDescriptor(
                window.HTMLInputElement.prototype, 'value'
            ).set;
            setter.call(inp, raw);
            inp.dispatchEvent(new Event('input', {{ bubbles: true }}));
        }}
    }})();
    </script>
    """, unsafe_allow_html=True)

def _save_bookmarks_js():
    """
    Write the current bookmarks list to localStorage.
    Called every time a bookmark is added, removed, or cleared.
    """
    payload = json.dumps(st.session_state.bookmarks, ensure_ascii=False)
    # Escape backticks and $ signs so the JS template literal is safe
    safe = payload.replace("\\","\\\\").replace("`","\\`").replace("$","\\$")
    st.markdown(f"""
    <script>
    (function() {{
        try {{ localStorage.setItem("{_LS_KEY}", `{safe}`); }}
        catch(e) {{ console.warn("localStorage write failed:", e); }}
    }})();
    </script>
    """, unsafe_allow_html=True)

def bm_has(url: str) -> bool:
    """Return True if an article URL is already bookmarked."""
    return any(b.get("url") == url for b in st.session_state.bookmarks)

def bm_save(article: dict):
    """Add an article to bookmarks and persist to localStorage."""
    url = article.get("url", "")
    if not bm_has(url):
        st.session_state.bookmarks.append({
            "url":         url,
            "title":       article.get("title", ""),
            "description": article.get("description","") or article.get("content",""),
            "source":      {"name": (article.get("source") or {}).get("name","")},
            "publishedAt": article.get("publishedAt",""),
            "urlToImage":  article.get("urlToImage",""),
        })
    _save_bookmarks_js()

def bm_delete(url: str):
    """Remove a bookmarked article by URL."""
    st.session_state.bookmarks = [
        b for b in st.session_state.bookmarks if b.get("url") != url
    ]
    _save_bookmarks_js()

def bm_clear():
    """Remove all bookmarks."""
    st.session_state.bookmarks = []
    _save_bookmarks_js()

def bm_all() -> list:
    """Return all bookmarks, newest first."""
    return list(reversed(st.session_state.bookmarks))

def bm_count() -> int:
    """Return the number of saved bookmarks."""
    return len(st.session_state.bookmarks)

# ── Hidden input: bridge from localStorage (JS) → Python ─────────────────────
raw_bm = st.text_input("__bm_store__", value="", key="__bm_store__",
                        label_visibility="collapsed")
if not st.session_state.bm_loaded and raw_bm:
    try:
        data = json.loads(raw_bm)
        if isinstance(data, list):
            st.session_state.bookmarks = data
    except Exception:
        pass
    st.session_state.bm_loaded = True
_bm_js_init()

# ══════════════════════════════════════════════════════════════════════════════
# SECTION 5: TEXT UTILITIES
# Clean, decode, and process text from RSS/API responses
# ══════════════════════════════════════════════════════════════════════════════

def esc(s: str) -> str:
    """Escape special characters to prevent XSS in HTML strings."""
    return str(s).replace("&","&amp;").replace("<","&lt;").replace('"','&quot;')

def _decode_entities(text: str) -> str:
    """
    Decode HTML entities to readable characters.
    Examples:
      &#8216; → ' (left single quote)
      &#8220; → " (left double quote)
      &amp;   → &
    Why needed: RSS feeds often contain raw HTML entities in titles.
    """
    # Named entities
    text = (text
        .replace("&lt;","<").replace("&gt;",">").replace("&amp;","&")
        .replace("&quot;",'"').replace("&#39;","'").replace("&nbsp;"," ")
        .replace("&mdash;","—").replace("&ndash;","–").replace("&hellip;","…")
        .replace("&lsquo;","'").replace("&rsquo;","'")
        .replace("&ldquo;",'"').replace("&rdquo;",'"'))
    # Decimal numeric: &#8216; → chr(8216)
    text = re.sub(r"&#(\d+);",  lambda m: chr(int(m.group(1))),           text)
    # Hex numeric:     &#x2019; → chr(0x2019)
    text = re.sub(r"&#x([0-9a-fA-F]+);", lambda m: chr(int(m.group(1),16)), text)
    return text

def _clean_text(text: str) -> str:
    """
    Full text cleaner: decode entities, strip HTML tags, remove URLs.
    Used on article descriptions from RSS feeds.
    """
    if not text: return ""
    text = _decode_entities(text)
    text = re.sub(r"<[^>]+>", "", text)      # strip HTML tags like <a href=...>
    text = re.sub(r"https?://\S+", "", text) # remove raw URLs
    text = re.sub(r"\s+", " ", text).strip() # collapse whitespace
    return text

def fmt_date(iso: str) -> str:
    """
    Convert ISO timestamp to human-readable relative time.
    e.g. "2024-03-10T14:30:00Z" → "2h ago"
    """
    if not iso: return ""
    try:
        dt = datetime.fromisoformat(iso.replace("Z","+00:00"))
        d  = datetime.now(timezone.utc) - dt
        if d.days >= 1:       return f"{d.days}d ago"
        if d.seconds >= 3600: return f"{d.seconds//3600}h ago"
        return f"{d.seconds//60}m ago"
    except:
        return iso[:10]

def src_name(article: dict) -> str:
    """Extract publisher name from article dict."""
    return (article.get("source") or {}).get("name") or "Unknown"

def read_time(text: str) -> str:
    """
    Estimate reading time based on average reading speed of 200 WPM.
    e.g. 400 words → "2 min read"
    """
    if not text: return "< 1 min"
    return f"{max(1, round(len(text.split()) / 200))} min read"

def ce(cat: str) -> str:
    """Return emoji for a news category."""
    return CAT_EMOJI.get(cat.lower(), "📰")

def akey(article: dict, prefix: str) -> str:
    """
    Generate a unique Streamlit widget key for each article.
    Uses MD5 of the URL so it's deterministic and collision-free.
    This prevents Streamlit's DuplicateElementKey error.
    """
    url = article.get("url") or str(id(article))
    return f"{prefix}_{hashlib.md5(url.encode()).hexdigest()[:8]}"

# ══════════════════════════════════════════════════════════════════════════════
# SECTION 6: EXPLAINABLE NLP — THE CORE DATA SCIENCE LOGIC
# No transformers, no black boxes. Every decision is traceable.
# ══════════════════════════════════════════════════════════════════════════════

def analyze_sentiment(text: str) -> tuple:
    """
    Rule-based sentiment analysis using keyword dictionaries.

    Algorithm (explainable in an interview):
      1. Convert text to lowercase
      2. Count how many POSITIVE_WORDS appear in the text (+1 each)
      3. Count how many NEGATIVE_WORDS appear in the text (+1 each)
      4. Compare scores:
           positive > negative  → Positive
           negative > positive  → Negative
           equal                → Neutral

    Returns:
      (label: str, badge_html: str, pos_score: int, neg_score: int)

    Example:
      "Stock market surges to record growth" → pos=2, neg=0 → Positive
      "Economy crash leads to major loss"    → pos=0, neg=2 → Negative
    """
    if not text:
        return "Neutral", '<span class="badge-neu">· Neutral</span>', 0, 0

    words    = text.lower().split()  # tokenize by whitespace
    pos_score = sum(1 for w in words if w.strip(".,!?\"'") in POSITIVE_WORDS)
    neg_score = sum(1 for w in words if w.strip(".,!?\"'") in NEGATIVE_WORDS)

    if pos_score > neg_score:
        return "Positive", '<span class="badge-pos">▲ Positive</span>', pos_score, neg_score
    if neg_score > pos_score:
        return "Negative", '<span class="badge-neg">▼ Negative</span>', pos_score, neg_score
    return "Neutral", '<span class="badge-neu">· Neutral</span>', pos_score, neg_score

def get_sentiment_badge(text: str) -> str:
    """Return just the HTML badge for sentiment (used in article cards)."""
    _, badge, _, _ = analyze_sentiment(text)
    return badge

def credibility_badge(source: str) -> str:
    """
    Rule-based source credibility using manually curated lists.
    Transparent: you can see exactly which sources are in each tier.
    High → Trusted (major international outlets)
    Med  → Known   (popular but potentially partisan sources)
    Low  → Unverified (not in either list)
    """
    sl = source.lower()
    if sl in HIGH_CRED: return '<span class="cred-hi">✓ Trusted</span>'
    if sl in MED_CRED:  return '<span class="cred-md">◈ Known</span>'
    return '<span class="cred-lo">? Unverified</span>'

def extractive_summarize(text: str, n_sentences: int = 2) -> str:
    """
    Extractive summarization — picks the most informative sentences.

    Algorithm:
      1. Clean and split text into sentences
      2. Tokenize each sentence into words
      3. Build a word frequency table (ignoring stopwords)
      4. Score each sentence = sum of its word frequencies
      5. Pick the top N highest-scoring sentences (in original order)

    Why extractive (not abstractive)?
      - No ML model needed
      - Output is always grammatically correct (original sentences)
      - Fully explainable: scores are just word counts
      - Fast: O(n) where n = number of words

    Example:
      Input:  "Tesla reported record profits. The CEO said growth continues.
               Weather was nice today."
      Freq:   tesla=1, reported=1, record=1, profits=1, ceo=1, said=1,
              growth=1, continues=1, weather=1, nice=1, today=1
      Scores: S1=4(record+profits+reported+tesla), S2=3, S3=3
      Output: "Tesla reported record profits. The CEO said growth continues."
    """
    if not text:
        return "No description available."

    # Step 1: clean the text
    text = _clean_text(text)
    text = re.sub(r"\s*\[\+\d+ chars\]$", "", text).strip()

    # Step 2: split into sentences
    sentences = [s.strip() for s in re.split(r"(?<=[.!?])\s+", text)
                 if len(s.strip()) > 15]
    if not sentences:
        return text[:200] if text else "No description available."
    if len(sentences) <= n_sentences:
        return " ".join(sentences)

    # Step 3: word frequency table (excluding stopwords)
    all_words = re.findall(r"\b[a-z]{3,}\b", text.lower())
    freq = Counter(w for w in all_words if w not in STOPWORDS)

    if not freq:
        return " ".join(sentences[:n_sentences])

    # Step 4: score each sentence by sum of its word frequencies
    def score_sentence(sent: str) -> float:
        words = re.findall(r"\b[a-z]{3,}\b", sent.lower())
        return sum(freq.get(w, 0) for w in words if w not in STOPWORDS)

    scored = sorted(enumerate(sentences), key=lambda x: score_sentence(x[1]), reverse=True)

    # Step 5: pick top N, restore original order
    top_indices = sorted(i for i, _ in scored[:n_sentences])
    return " ".join(sentences[i] for i in top_indices)

def extract_trending_keywords(articles: list, top_n: int = 8) -> list:
    """
    Extract the most frequent meaningful keywords from article titles.

    Algorithm (Term Frequency approach):
      1. Collect all title words from every article
      2. Lowercase, tokenize, keep only alphabetic words ≥ 4 chars
      3. Remove stopwords (common English words like 'the', 'is', 'and')
      4. Count occurrences using Counter
      5. Return top N (word, count) pairs

    This is TF (Term Frequency) — the simplest part of TF-IDF.
    In an interview: "I implemented TF-based keyword extraction without
    any external NLP library."

    Returns: list of (keyword, count) tuples sorted by frequency
    """
    all_words = []

    for article in articles:
        title = article.get("title","") or ""
        title = _decode_entities(title).lower()
        # Extract alphabetic words, length ≥ 4 to skip noise like "pm", "vs"
        words = re.findall(r"\b[a-z]{4,}\b", title)
        # Filter stopwords
        all_words.extend(w for w in words if w not in STOPWORDS)

    if not all_words:
        return []

    # Counter.most_common returns [(word, count), ...] sorted by frequency
    return Counter(all_words).most_common(top_n)

def get_sentiment_distribution(articles: list) -> dict:
    """
    Count how many articles are Positive, Neutral, or Negative.
    Used for the analytics bar chart.

    Returns: {"Positive": 3, "Neutral": 2, "Negative": 1}
    """
    dist = {"Positive": 0, "Neutral": 0, "Negative": 0}
    for a in articles:
        text  = f"{a.get('title','')} {a.get('description','')}"
        label, _, _, _ = analyze_sentiment(text)
        dist[label] = dist.get(label, 0) + 1
    return dist

def get_source_counts(articles: list) -> dict:
    """
    Count articles per source publisher.
    Used for the analytics bar chart.

    Returns: {"BBC": 3, "Reuters": 2, ...}
    """
    counts = Counter(src_name(a) for a in articles)
    # Return top 8 sources (sorted by count)
    return dict(counts.most_common(8))

# ══════════════════════════════════════════════════════════════════════════════
# SECTION 7: RATE LIMIT TRACKER
# Detects when NewsAPI's 100-request limit is hit, switches to RSS fallback
# ══════════════════════════════════════════════════════════════════════════════

if "api_limited"     not in st.session_state: st.session_state.api_limited     = False
if "api_limit_until" not in st.session_state: st.session_state.api_limit_until = None

def _mark_limited():
    """Mark NewsAPI as rate-limited. Will auto-reset after 1 hour."""
    st.session_state.api_limited     = True
    st.session_state.api_limit_until = datetime.utcnow() + timedelta(hours=1)

def _is_limited() -> bool:
    """Check if we're currently rate-limited. Auto-resets after 1 hour."""
    if not st.session_state.api_limited: return False
    if st.session_state.api_limit_until and datetime.utcnow() > st.session_state.api_limit_until:
        st.session_state.api_limited     = False
        st.session_state.api_limit_until = None
        return False
    return True

def _show_fallback_banner():
    """Display a visible warning that we switched from NewsAPI to RSS."""
    st.markdown(
        '<div class="fallback-banner">⚠️ <b>NewsAPI limit reached</b> — '
        'showing results from free RSS feeds. Resets automatically in ~1 hour.</div>',
        unsafe_allow_html=True)

# ══════════════════════════════════════════════════════════════════════════════
# SECTION 8: RSS SCRAPING FALLBACK
# When NewsAPI hits its 100-request limit, we scrape free RSS feeds instead.
# No API key required. Curated list of reliable sources per category.
# ══════════════════════════════════════════════════════════════════════════════

RSS_FEEDS = {
    "general":       ["http://feeds.bbci.co.uk/news/rss.xml",
                      "https://rss.nytimes.com/services/xml/rss/nyt/HomePage.xml",
                      "https://feeds.npr.org/1001/rss.xml"],
    "technology":    ["http://feeds.bbci.co.uk/news/technology/rss.xml",
                      "https://feeds.feedburner.com/TechCrunch",
                      "https://www.wired.com/feed/rss",
                      "https://feeds.arstechnica.com/arstechnica/index"],
    "business":      ["http://feeds.bbci.co.uk/news/business/rss.xml",
                      "https://rss.nytimes.com/services/xml/rss/nyt/Business.xml"],
    "science":       ["http://feeds.bbci.co.uk/news/science_and_environment/rss.xml",
                      "https://rss.nytimes.com/services/xml/rss/nyt/Science.xml",
                      "https://www.sciencedaily.com/rss/top.xml"],
    "health":        ["http://feeds.bbci.co.uk/news/health/rss.xml",
                      "https://rss.nytimes.com/services/xml/rss/nyt/Health.xml"],
    "sports":        ["http://feeds.bbci.co.uk/sport/rss.xml",
                      "https://rss.nytimes.com/services/xml/rss/nyt/Sports.xml"],
    "entertainment": ["http://feeds.bbci.co.uk/news/entertainment_and_arts/rss.xml",
                      "https://rss.nytimes.com/services/xml/rss/nyt/Arts.xml"],
    "gaming":        ["https://www.ign.com/articles.rss",
                      "https://kotaku.com/rss"],
    "movies":        ["https://variety.com/v/film/feed/",
                      "https://deadline.com/feed/"],
}

def _google_news_rss(query: str, lang: str = "en") -> str:
    """Build a Google News RSS search URL. No API key needed."""
    q = requests.utils.quote(query)
    return f"https://news.google.com/rss/search?q={q}&hl={lang}&gl=US&ceid=US:{lang}"

def _extract_image_from_item(item_xml: str) -> str:
    """
    Try 3 methods to find an image URL in an RSS <item> block:
      1. <media:content url="...">  — used by BBC, TechCrunch, IGN
      2. <enclosure url="...">     — used by NPR, ScienceDaily
      3. <img src="..."> in desc   — fallback, used by some WordPress blogs
    Returns image URL or empty string.
    """
    # Method 1: media:content or media:thumbnail
    for pat in [
        r'<media:content[^>]+url=["\']([^"\']+)["\']',
        r'<media:thumbnail[^>]+url=["\']([^"\']+)["\']',
    ]:
        m = re.search(pat, item_xml, re.IGNORECASE)
        if m:
            url = m.group(1).strip()
            if url.startswith("http"): return url

    # Method 2: enclosure tag (only for images)
    m = re.search(r'<enclosure[^>]+url=["\']([^"\']+)["\']', item_xml, re.IGNORECASE)
    if m:
        url = m.group(1).strip()
        if url.startswith("http") and any(
            ext in url.lower() for ext in (".jpg",".jpeg",".png",".webp",".gif")
        ):
            return url

    # Method 3: img tag inside CDATA description
    m = re.search(r'<img[^>]+src=["\']([^"\']+)["\']', item_xml, re.IGNORECASE)
    if m:
        url = m.group(1).strip()
        if url.startswith("http"): return url

    return ""

def _parse_rss(url: str, limit: int = 10) -> list:
    """
    Fetch and parse an RSS XML feed into a list of article dicts.
    RSS is a standard XML format — no scraping library needed, just regex.
    Returns a list of article dicts matching NewsAPI's format for compatibility.
    """
    try:
        headers = {"User-Agent": "Mozilla/5.0 (compatible; NewsAssistant/1.0)"}
        r = requests.get(url, headers=headers, timeout=8)
        if r.status_code != 200: return []
        xml = r.text

        articles = []
        # Each news item is wrapped in <item>...</item> tags
        items = re.findall(r"<item>(.*?)</item>", xml, re.DOTALL)

        for item in items[:limit]:
            # Helper: extract content of a tag, handling CDATA sections
            def tag(t):
                m = re.search(rf"<{t}[^>]*><!\[CDATA\[(.*?)\]\]></{t}>", item, re.DOTALL)
                if m: return m.group(1).strip()
                m = re.search(rf"<{t}[^>]*>(.*?)</{t}>", item, re.DOTALL)
                return m.group(1).strip() if m else ""

            # Extract and clean each field
            title = _decode_entities(tag("title"))
            link  = tag("link") or tag("guid")
            desc  = _clean_text(tag("description"))
            pub   = tag("pubDate")

            # Source name: from <source> tag or extract domain from URL
            src_m = re.search(r"<source[^>]*>(.*?)</source>", item, re.DOTALL)
            src   = _decode_entities(src_m.group(1).strip()) if src_m else (
                    re.search(r"https?://(?:www\.)?([^/]+)", link or "").group(1)
                    if link else "RSS Feed")

            # Try to find an image inside the RSS item
            img = _extract_image_from_item(item)

            # Convert RSS date format to ISO 8601
            iso = ""
            for fmt in ("%a, %d %b %Y %H:%M:%S %z", "%a, %d %b %Y %H:%M:%S GMT"):
                try: iso = datetime.strptime(pub.strip(), fmt).isoformat(); break
                except: pass

            if title and link:
                # Return dict in NewsAPI-compatible format
                articles.append({
                    "title":       title,
                    "description": desc[:400] if desc else "",
                    "url":         link,
                    "urlToImage":  img,
                    "publishedAt": iso,
                    "source":      {"name": src},
                    "content":     desc,
                })
        return articles
    except Exception:
        return []

def _resolve_url(url: str) -> str:
    """
    Follow HTTP redirects to get the final URL.
    Needed because Google News wraps article links as:
    news.google.com/rss/articles/CBMi... → actual-publisher.com/article
    We need the real URL to fetch og:image from the publisher's page.
    Uses HEAD request (no body downloaded) for speed.
    """
    try:
        headers = {"User-Agent": "Mozilla/5.0 (compatible; NewsAssistant/1.0)"}
        r = requests.head(url, headers=headers, timeout=5, allow_redirects=True)
        return r.url if r.url else url
    except Exception:
        return url

def _fetch_og_image(url: str) -> str:
    """
    Fetch the og:image or twitter:image meta tag from an article page.
    These are the "social share thumbnails" every modern news site provides.

    Process:
      1. Resolve any redirects (Google News wraps links)
      2. Download the first 12KB of the page (enough to find <meta> tags)
      3. Search for og:image or twitter:image patterns with regex
    """
    try:
        headers = {"User-Agent": "Mozilla/5.0 (compatible; NewsAssistant/1.0)"}
        real_url = _resolve_url(url)  # follow Google News redirect
        r = requests.get(real_url, headers=headers, timeout=6, allow_redirects=True)
        if r.status_code != 200: return ""
        chunk = r.text[:12000]  # only first 12KB — meta tags are always in <head>
        for pattern in [
            r'<meta[^>]+property=["\']og:image["\'][^>]+content=["\']([^"\']+)["\']',
            r'<meta[^>]+content=["\']([^"\']+)["\'][^>]+property=["\']og:image["\']',
            r'<meta[^>]+name=["\']twitter:image(?::src)?["\'][^>]+content=["\']([^"\']+)["\']',
            r'<meta[^>]+content=["\']([^"\']+)["\'][^>]+name=["\']twitter:image["\']',
        ]:
            m = re.search(pattern, chunk, re.IGNORECASE)
            if m:
                img = m.group(1).strip()
                if img.startswith("http"): return img
    except Exception:
        pass
    return ""

def _enrich_with_images(articles: list) -> list:
    """
    Fetch og:image for articles that have no image (Google News RSS).
    Uses ThreadPoolExecutor for parallel fetching — 6 requests at once
    instead of 6 sequential requests, reducing wait time by ~5x.
    """
    needs_image = [i for i, a in enumerate(articles) if not a.get("urlToImage")]
    if not needs_image:
        return articles   # all articles already have images

    result = articles[:]  # shallow copy to avoid mutating the original list

    with ThreadPoolExecutor(max_workers=6) as executor:
        # Submit all image-fetch tasks at once
        future_to_idx = {
            executor.submit(_fetch_og_image, articles[i]["url"]): i
            for i in needs_image
        }
        # Collect results as they complete
        for future in as_completed(future_to_idx):
            idx = future_to_idx[future]
            try:
                img = future.result()
                if img:
                    result[idx] = {**result[idx], "urlToImage": img}
            except Exception:
                pass  # silently skip if image fetch fails

    return result

def _rss_for_query(query: str, lang: str, limit: int) -> list:
    """Search Google News RSS then enrich articles with og:images in parallel."""
    articles = _parse_rss(_google_news_rss(query, lang), limit=limit)
    return _enrich_with_images(articles)

def _rss_for_category(category: str, limit: int) -> list:
    """Pull from curated publisher RSS feeds for a given category."""
    feeds    = RSS_FEEDS.get(category, RSS_FEEDS["general"])
    articles, seen = [], set()
    for feed_url in feeds:
        for art in _parse_rss(feed_url, limit=limit):
            if art["url"] not in seen:
                seen.add(art["url"])
                articles.append(art)
        if len(articles) >= limit:
            break
    return articles[:limit]

# ══════════════════════════════════════════════════════════════════════════════
# SECTION 9: NEWS API  (primary source, with fallback to RSS)
# ══════════════════════════════════════════════════════════════════════════════

def _api_call(url: str, params: dict) -> tuple:
    """
    Make a NewsAPI request. Detects rate limit errors.
    Returns: (response_dict or None, is_rate_limited: bool)
    """
    try:
        r = requests.get(url, params={**params, "apiKey": NEWS_API_KEY}, timeout=10)
        # 429 = Too Many Requests, 426 = Upgrade Required (plan limit)
        if r.status_code in (429, 426):
            return None, True
        if r.status_code == 401:
            # NewsAPI sends 401 with specific codes when daily limit is reached
            body = r.json()
            code = body.get("code","")
            if "rateLimited" in code or "maximumResultsReached" in code:
                return None, True
            return None, False
        r.raise_for_status()
        return r.json(), False
    except Exception:
        return None, False

def _clean_articles(arts: list) -> list:
    """Remove removed/deleted articles from the list."""
    return [a for a in arts
            if a.get("title") and a["title"] != "[Removed]"
            and (a.get("source") or {}).get("name") != "[Removed]"
            and a.get("url")]

@st.cache_data(ttl=CACHE_TTL, show_spinner=False)
def fetch_everything(query: str, sort_by: str, page_size: int,
                     days_back: int, language: str = "en", page: int = 1) -> list:
    """
    Fetch articles matching a search query.
    Primary: NewsAPI /everything endpoint
    Fallback: Google News RSS (if rate limited)
    Results cached for 10 minutes to avoid redundant API calls.
    """
    if not _is_limited():
        from_date = (datetime.utcnow() - timedelta(days=days_back)).strftime("%Y-%m-%d")
        data, limited = _api_call(EVERYTHING_EP, {
            "q": query, "language": language, "sortBy": sort_by,
            "pageSize": page_size, "from": from_date, "page": page,
        })
        if limited:
            _mark_limited()  # switch to RSS mode for next hour
        elif data:
            arts = _clean_articles(data.get("articles", []))
            if arts: return arts

    # RSS fallback — no API key, no rate limits
    return _rss_for_query(query, language, page_size)

@st.cache_data(ttl=CACHE_TTL, show_spinner=False)
def fetch_headlines(category: str, page_size: int = 6) -> list:
    """
    Fetch top headlines for a category.
    Gaming/Movies use /everything (NewsAPI doesn't support them in /top-headlines).
    Fallback: curated RSS feeds per category.
    """
    if not _is_limited():
        if category in ("gaming", "movies"):
            q_map = {"gaming": "gaming video games", "movies": "movies film cinema"}
            fd    = (datetime.utcnow() - timedelta(days=3)).strftime("%Y-%m-%d")
            data, limited = _api_call(EVERYTHING_EP, {
                "q": q_map[category], "language": "en",
                "sortBy": "publishedAt", "pageSize": page_size, "from": fd,
            })
        else:
            data, limited = _api_call(TOP_HEADLINES_EP, {
                "country": "us", "category": category, "pageSize": page_size,
            })
        if limited:
            _mark_limited()
        elif data:
            arts = _clean_articles(data.get("articles", []))
            if arts: return arts

    return _rss_for_category(category, page_size)

# ══════════════════════════════════════════════════════════════════════════════
# SECTION 10: CARD & GRID RENDERING
# ══════════════════════════════════════════════════════════════════════════════

def card_html(article: dict, cat: str = "general") -> str:
    """
    Build the HTML string for a news article card.
    Uses extractive_summarize() for the description (our NLP function).
    Uses analyze_sentiment() for the badge.
    Uses credibility_badge() for the source rating.
    """
    title    = esc(article.get("title") or "Untitled")
    desc     = article.get("description") or article.get("content") or ""
    url      = esc(article.get("url") or "#")
    img      = article.get("urlToImage") or ""
    source   = src_name(article)
    pub      = fmt_date(article.get("publishedAt"))
    rt       = read_time(desc)
    summary  = esc(extractive_summarize(desc))
    emoji    = ce(cat)
    sent     = get_sentiment_badge(f"{article.get('title','')} {desc}")
    cred     = credibility_badge(source)
    src_esc  = esc(source)

    # JS: copy URL to clipboard on share button click
    share_js = (
        f"navigator.clipboard.writeText('{url}')"
        f".then(()=>{{this.textContent='✓ Copied!'; "
        f"setTimeout(()=>this.textContent='⎘',1500)}})"
    )

    # Image: show real image with emoji fallback
    img_url  = esc(img)
    if img:
        img_block = (
            f'<img class="nc-img" src="{img_url}" alt="" '
            f'onerror="this.style.display=\'none\';'
            f'this.nextElementSibling.style.display=\'flex\'">'
            f'<div class="nc-ph" style="display:none">{emoji}</div>'
        )
    else:
        img_block = f'<div class="nc-ph">{emoji}</div>'

    return (
        f'<div class="nc">{img_block}'
        f'<div class="nc-body">'
        f'  <div class="nc-meta">'
        f'    <span class="nc-src">{src_esc}</span>'
        f'    <span class="nc-time">{pub}</span>'
        f'  </div>'
        f'  <div class="nc-ttl">{title}</div>'
        f'  <div class="nc-sum">{summary}</div>'
        f'  <div class="nc-tags">{sent}&nbsp;{cred}</div>'
        f'  <div class="nc-foot">'
        f'    <a class="nc-link" href="{url}" target="_blank" rel="noopener">Read article →</a>'
        f'    <span style="display:flex;align-items:center;gap:.35rem">'
        f'      <span class="nc-rt">{rt}</span>'
        f'      <button class="share-btn" onclick="{share_js}">⎘</button>'
        f'    </span>'
        f'  </div>'
        f'</div></div>'
    )

def render_grid(articles: list, cat: str = "general", cols: int = 3, pfx: str = "g"):
    """Render a grid of article cards with Save/Unsave buttons."""
    if not articles:
        st.markdown(
            '<div class="empty"><div class="ico">📭</div>'
            '<p>No articles found.<br>Try a different search or adjust filters.</p></div>',
            unsafe_allow_html=True)
        return

    for i in range(0, len(articles), cols):
        for col, art in zip(st.columns(cols), articles[i:i+cols]):
            with col:
                st.markdown(card_html(art, cat), unsafe_allow_html=True)
                saved = bm_has(art.get("url",""))
                label = "⭐ Saved" if saved else "☆  Save"
                if st.button(label, key=akey(art, pfx), use_container_width=True):
                    bm_delete(art["url"]) if saved else bm_save(art)
                    st.rerun()

def render_trending_list(articles: list):
    """Render a numbered list of article titles (Quick Read sidebar)."""
    if not articles:
        st.markdown('<p style="font-size:.78rem;color:var(--t3)">No headlines available.</p>',
                    unsafe_allow_html=True)
        return
    for i, a in enumerate(articles, 1):
        title = esc(a.get("title") or "Untitled")
        url   = a.get("url") or "#"
        src   = esc(src_name(a))
        pub   = fmt_date(a.get("publishedAt"))
        st.markdown(
            f'<div class="tr-item">'
            f'<div class="tr-rank">{i}</div>'
            f'<div>'
            f'  <div class="tr-ttl">'
            f'    <a href="{url}" target="_blank" style="color:inherit;text-decoration:none">{title}</a>'
            f'  </div>'
            f'  <div class="tr-src">{src} · {pub}</div>'
            f'</div></div>',
            unsafe_allow_html=True)

def render_stats(articles: list, query: str, cat: str):
    """Show quick-glance statistics above the article grid."""
    srcs = len({src_name(a) for a in articles})
    lang = {v:k for k,v in LANGUAGES.items()}.get(st.session_state.language, "English")
    st.markdown(
        f'<div class="stat-row">'
        f'<div class="stat-chip"><strong>{len(articles)}</strong><span>Articles</span></div>'
        f'<div class="stat-chip"><strong>{srcs}</strong><span>Sources</span></div>'
        f'<div class="stat-chip"><strong>{cat.title()}</strong><span>Category</span></div>'
        f'<div class="stat-chip"><strong>&ldquo;{esc(query)}&rdquo;</strong><span>Topic</span></div>'
        f'<div class="stat-chip"><strong>{lang}</strong><span>Language</span></div>'
        f'</div>', unsafe_allow_html=True)

# ══════════════════════════════════════════════════════════════════════════════
# SECTION 11: ANALYTICS PANEL
# Data-driven charts generated from the live article set.
# Uses only Streamlit built-in charts — no matplotlib, no plotly needed.
# ══════════════════════════════════════════════════════════════════════════════

def render_analytics(articles: list):
    """
    Render the analytics panel below the article grid.
    Contains three data visualizations built from the fetched articles:
      A. Sentiment Distribution (bar chart)
      B. Top Sources (bar chart)
      C. Trending Keywords (pill badges)
    All data is computed with our explainable functions — no black boxes.
    """
    if not articles:
        return

    st.markdown("<br>", unsafe_allow_html=True)
    st.markdown(
        '<div class="sec-ttl">📊 Live Analytics — computed from current articles</div>',
        unsafe_allow_html=True)

    col1, col2, col3 = st.columns([1, 1, 1])

    # ── A. Sentiment Distribution ──────────────────────────────────────────
    # Shows how positive/neutral/negative the current news coverage is.
    # Computed using analyze_sentiment() — our keyword dictionary method.
    with col1:
        st.markdown('<div class="analytics-box">', unsafe_allow_html=True)
        st.markdown('<div class="analytics-title">😊 Sentiment Distribution</div>',
                    unsafe_allow_html=True)

        dist = get_sentiment_distribution(articles)

        # Build a simple data dict for Streamlit's bar chart
        # Colors map to sentiment labels
        chart_data = {
            "Sentiment": list(dist.keys()),
            "Count":     list(dist.values()),
        }
        # Use st.bar_chart for zero-dependency charting
        import pandas as pd
        df_sent = pd.DataFrame(chart_data).set_index("Sentiment")
        st.bar_chart(df_sent, use_container_width=True, height=180)

        # Show the raw numbers as text for clarity
        for label, count in dist.items():
            emoji = "🟢" if label == "Positive" else ("🔴" if label == "Negative" else "⚪")
            st.markdown(
                f'<div style="font-size:.75rem;color:var(--t2);margin:.1rem 0">'
                f'{emoji} {label}: <b>{count}</b> articles</div>',
                unsafe_allow_html=True)

        st.markdown('</div>', unsafe_allow_html=True)

    # ── B. Top Sources ──────────────────────────────────────────────────────
    # Shows which publishers contributed the most articles.
    # Simple Counter — fully explainable, no ML.
    with col2:
        st.markdown('<div class="analytics-box">', unsafe_allow_html=True)
        st.markdown('<div class="analytics-title">📰 Top Sources</div>',
                    unsafe_allow_html=True)

        src_counts = get_source_counts(articles)

        if src_counts:
            df_src = pd.DataFrame({
                "Source": list(src_counts.keys()),
                "Articles": list(src_counts.values()),
            }).set_index("Source")
            st.bar_chart(df_src, use_container_width=True, height=180)
        else:
            st.markdown('<p style="font-size:.78rem;color:var(--t3)">No data</p>',
                        unsafe_allow_html=True)

        st.markdown('</div>', unsafe_allow_html=True)

    # ── C. Trending Keywords ────────────────────────────────────────────────
    # Most frequent meaningful words in article titles.
    # TF-based extraction — term frequency without IDF for simplicity.
    with col3:
        st.markdown('<div class="analytics-box">', unsafe_allow_html=True)
        st.markdown('<div class="analytics-title">🔥 Trending Keywords</div>',
                    unsafe_allow_html=True)

        keywords = extract_trending_keywords(articles, top_n=10)

        if keywords:
            pills_html = ""
            for word, count in keywords:
                pills_html += (
                    f'<span class="kw-pill">{word.title()}'
                    f'<span class="kw-count">×{count}</span></span>'
                )
            st.markdown(
                f'<div style="line-height:2.2">{pills_html}</div>',
                unsafe_allow_html=True)

            # Also show as a small bar chart for visual impact
            df_kw = pd.DataFrame(keywords, columns=["Keyword","Count"]).set_index("Keyword")
            st.bar_chart(df_kw, use_container_width=True, height=160)
        else:
            st.markdown('<p style="font-size:.78rem;color:var(--t3)">No keywords extracted</p>',
                        unsafe_allow_html=True)

        st.markdown('</div>', unsafe_allow_html=True)

# ══════════════════════════════════════════════════════════════════════════════
# SECTION 12: SIDEBAR  (advanced filters)
# ══════════════════════════════════════════════════════════════════════════════

with st.sidebar:
    st.markdown("### ⚙️ Filters")
    st.markdown("---")

    st.markdown("**Category**")
    sidebar_cat = st.selectbox(
        "cat", CATEGORIES,
        format_func=lambda c: f"{ce(c)} {c.title()}",
        label_visibility="collapsed", key="sb_cat")

    st.markdown("**Sort by**")
    sort_lbl = st.selectbox(
        "sort", list(SORT_OPTIONS.keys()),
        label_visibility="collapsed", key="sb_sort")

    st.markdown("**Language**")
    lang_lbl = st.selectbox(
        "lang", list(LANGUAGES.keys()),
        index=list(LANGUAGES.values()).index(st.session_state.language)
              if st.session_state.language in LANGUAGES.values() else 0,
        label_visibility="collapsed", key="sb_lang")

    st.markdown("**Days back**")
    days_back = st.slider("days", 1, 30, st.session_state.days_back,
                          label_visibility="collapsed", key="sb_days")

    st.markdown("**Articles per page**")
    page_size = st.slider("n", 3, 12, st.session_state.page_size,
                          label_visibility="collapsed", key="sb_n")

    st.markdown("---")
    c1, c2 = st.columns(2)
    if c1.button("Apply", use_container_width=True, type="primary", key="apply"):
        st.session_state.days_back = days_back
        st.session_state.page_size = page_size
        st.session_state.sort_by   = SORT_OPTIONS[sort_lbl]
        st.session_state.language  = LANGUAGES[lang_lbl]
        st.session_state.feed_page = 1
        st.cache_data.clear()
        st.rerun()
    if c2.button("Reset", use_container_width=True, key="sb_reset"):
        for k, v in DEFAULTS.items():
            setattr(st.session_state, k, v)
        st.rerun()

    st.markdown("---")
    if st.button("🗑 Clear saved", use_container_width=True, key="sb_clear"):
        bm_clear()
        st.rerun()

# ══════════════════════════════════════════════════════════════════════════════
# SECTION 13: MAIN LAYOUT  (the actual rendered page)
# ══════════════════════════════════════════════════════════════════════════════

# ── Navbar ────────────────────────────────────────────────────────────────────
n_sv  = bm_count()
badge = f'<span class="sv-badge">⭐ {n_sv}</span>' if n_sv else ""
st.markdown(
    f'<div class="app-nav">'
    f'<div class="nav-brand">📊 News Analytics Dashboard</div>'
    f'<div class="nav-right">'
    f'  <span class="live-dot"></span><span>Live</span>'
    f'  <span style="color:var(--bd)">·</span>'
    f'  <span>Explainable NLP</span>'
    f'  <span style="color:var(--bd)">·</span>'
    f'  <span>Saved {badge}</span>'
    f'</div></div>',
    unsafe_allow_html=True)

# ── Search bar + Theme selector ───────────────────────────────────────────────
sc, bc, tc = st.columns([6, 1, 2])
with sc:
    st.markdown('<p class="sec">Search Topic</p>', unsafe_allow_html=True)
    query_input = st.text_input(
        "q", value=st.session_state.active_query,
        placeholder="e.g. Tesla, Climate, AI…",
        label_visibility="collapsed", key="search_input")
with bc:
    st.markdown('<p class="sec">&nbsp;</p>', unsafe_allow_html=True)
    if st.button("Search", type="primary", use_container_width=True, key="do_search"):
        q = query_input.strip() or "Artificial Intelligence"
        st.session_state.active_query = q
        st.session_state.feed_page    = 1
        st.cache_data.clear()
        st.rerun()
with tc:
    st.markdown('<p class="sec">Theme</p>', unsafe_allow_html=True)
    chosen = st.selectbox(
        "theme", list(THEMES.keys()),
        index=list(THEMES.keys()).index(st.session_state.theme),
        label_visibility="collapsed", key="theme_sel")
    if chosen != st.session_state.theme:
        st.session_state.theme = chosen
        st.rerun()

# ── Quick topic pills ─────────────────────────────────────────────────────────
st.markdown('<p class="sec" style="margin-bottom:.4rem">Quick Topics</p>',
            unsafe_allow_html=True)
qt_cols = st.columns(len(QUICK_TOPICS))
for col, topic in zip(qt_cols, QUICK_TOPICS):
    with col:
        if st.button(topic, key=f"qt_{topic.replace(' ','_')}", use_container_width=True):
            st.session_state.active_query = topic
            st.session_state.feed_page    = 1
            st.cache_data.clear()
            st.rerun()

st.markdown("<hr style='border-color:var(--bd);margin:1rem 0'>", unsafe_allow_html=True)

# ── Read session variables ────────────────────────────────────────────────────
query     = st.session_state.active_query
sort_by   = st.session_state.sort_by
days_back = st.session_state.days_back
page_size = st.session_state.page_size
language  = st.session_state.language
feed_page = st.session_state.feed_page

# ── Main tabs ─────────────────────────────────────────────────────────────────
tab_feed, tab_trend, tab_saved = st.tabs(["📰  Feed", "🔥  Trending", "⭐  Saved"])

# ── FEED TAB ──────────────────────────────────────────────────────────────────
with tab_feed:
    st.markdown(f'<div class="sec-ttl">Latest on &ldquo;{esc(query)}&rdquo;</div>',
                unsafe_allow_html=True)

    if _is_limited():
        _show_fallback_banner()

    with st.spinner("Fetching articles…"):
        articles = fetch_everything(
            query, sort_by=sort_by, page_size=page_size,
            days_back=days_back, language=language, page=feed_page)

    if articles:
        render_stats(articles, query, sidebar_cat)

    # Article grid
    render_grid(articles, cat=sidebar_cat, cols=3, pfx="feed")

    # Pagination controls
    p1, p2, p3 = st.columns([1, 2, 1])
    with p1:
        if feed_page > 1:
            if st.button("← Prev", use_container_width=True, key="pg_prev"):
                st.session_state.feed_page -= 1
                st.cache_data.clear()
                st.rerun()
    with p2:
        st.markdown(
            f'<p style="text-align:center;font-size:.75rem;color:var(--t3);padding:.5rem 0">'
            f'Page {feed_page}</p>', unsafe_allow_html=True)
    with p3:
        if len(articles) == page_size:
            if st.button("Next →", use_container_width=True, key="pg_next", type="primary"):
                st.session_state.feed_page += 1
                st.cache_data.clear()
                st.rerun()

    # ── Analytics Panel (only shown when we have articles) ────────────────
    if articles:
        render_analytics(articles)

# ── TRENDING TAB ──────────────────────────────────────────────────────────────
with tab_trend:
    st.markdown('<div class="sec-ttl">Top Headlines by Category</div>',
                unsafe_allow_html=True)

    if _is_limited():
        _show_fallback_banner()

    inner_tabs = st.tabs([f"{em} {name}" for em, name, _ in TRENDING_TABS])

    for (em, name, key), ctab in zip(TRENDING_TABS, inner_tabs):
        with ctab:
            with st.spinner(f"Loading {name}…"):
                t_arts = fetch_headlines(key, page_size=6)

            lc, rc = st.columns([2, 1])
            with lc:
                render_grid(t_arts, cat=key, cols=2, pfx=f"tr_{key}")
            with rc:
                st.markdown('<p class="sec" style="margin-bottom:.4rem">Quick Read</p>',
                            unsafe_allow_html=True)
                render_trending_list(t_arts[:5])

# ── SAVED TAB ─────────────────────────────────────────────────────────────────
with tab_saved:
    saved = bm_all()
    h1, h2 = st.columns([5, 1])
    with h1:
        st.markdown('<div class="sec-ttl">Your Saved Articles</div>', unsafe_allow_html=True)
    with h2:
        if saved and st.button("🗑 Clear", key="clr_saved", use_container_width=True):
            bm_clear()
            st.rerun()

    if not saved:
        st.markdown(
            '<div class="empty"><div class="ico">🔖</div>'
            '<p>No saved articles yet.<br>Hit ☆ Save on any card.<br>'
            '<small>Saves persist in your browser.</small></p></div>',
            unsafe_allow_html=True)
    else:
        n = len(saved)
        st.markdown(
            f'<div class="stat-row">'
            f'<div class="stat-chip"><strong>{n}</strong>'
            f'<span>Saved article{"s" if n!=1 else ""}</span></div>'
            f'<div class="stat-chip"><strong>Browser</strong><span>localStorage</span></div>'
            f'</div>', unsafe_allow_html=True)
        render_grid(saved, cols=3, pfx="sv")

        # Analytics for saved articles too
        if len(saved) >= 2:
            st.markdown("<br>", unsafe_allow_html=True)
            render_analytics(saved)
