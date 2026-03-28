"""
AI News Assistant  ·  v6  ·  Clean & Minimal
Run:  streamlit run app.py
"""

import os, re, hashlib, sqlite3, requests
from datetime import datetime, timezone, timedelta
from typing import Optional
import streamlit as st

# ── Page config ───────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="AI News Assistant",
    page_icon="📰",
    layout="wide",
    initial_sidebar_state="collapsed",
)

# ── API Key ───────────────────────────────────────────────────────────────────
try:    NEWS_API_KEY = st.secrets["NEWS_API_KEY"]
except: NEWS_API_KEY = os.getenv("NEWS_API_KEY", "")

# ── Constants ─────────────────────────────────────────────────────────────────
EVERYTHING_EP    = "https://newsapi.org/v2/everything"
TOP_HEADLINES_EP = "https://newsapi.org/v2/top-headlines"
CACHE_TTL        = 600
DB_PATH          = "bookmarks.db"

QUICK_TOPICS = ["Artificial Intelligence","Climate Change","Stock Market",
                "Space Exploration","Cybersecurity","Startups"]

SORT_OPTIONS = {"Latest":"publishedAt","Relevant":"relevancy","Popular":"popularity"}
CATEGORIES   = ["technology","business","science","health","sports","entertainment","general"]
LANGUAGES    = {"English":"en","Hindi":"hi","French":"fr","German":"de","Spanish":"es",
                "Portuguese":"pt","Italian":"it","Japanese":"ja","Chinese":"zh","Arabic":"ar"}

TRENDING_TABS = [
    ("🌐","General","general"),("💻","Tech","technology"),("📈","Business","business"),
    ("🔬","Science","science"),("🏥","Health","health"),("⚽","Sports","sports"),
    ("🎬","Entertainment","entertainment"),("🎮","Gaming","gaming"),("🎥","Movies","movies"),
]
CAT_EMOJI = {"technology":"💻","business":"📈","science":"🔬","health":"🏥",
             "sports":"⚽","entertainment":"🎬","general":"🌐","gaming":"🎮","movies":"🎥"}

HIGH_CRED = {"reuters","associated press","ap","bbc news","bbc","the guardian","npr",
             "bloomberg","financial times","the economist","wall street journal",
             "new york times","washington post","the verge","wired","techcrunch","ars technica"}
MED_CRED  = {"cnn","fox news","msnbc","cnbc","forbes","time","newsweek","usa today",
             "the atlantic","politico","axios","the hill","vice"}
POS_WORDS = {"breakthrough","surge","win","record","growth","profit","success","launch",
             "innovative","hope","recover","rise","gain","soar","achieve","milestone",
             "positive","strong","boost","advance","improve","lead","thrive","discovery"}
NEG_WORDS = {"crash","crisis","war","death","fail","loss","decline","fear","risk","terror",
             "collapse","scandal","fraud","disaster","attack","threat","drop","controversy",
             "ban","arrest","killed","wounded","emergency","warning","breach","hack","conflict"}

# ── Theme ─────────────────────────────────────────────────────────────────────
THEMES = {
    "Default": {"bg":"#F7F8FA","sf":"#FFFFFF","bd":"#E5E7EB","ac":"#2563EB",
                "al":"#EFF6FF","t1":"#111827","t2":"#6B7280","t3":"#9CA3AF","ibg":"#FFFFFF"},
    "Light":   {"bg":"#FFFFFF","sf":"#F9FAFB","bd":"#E5E7EB","ac":"#2563EB",
                "al":"#DBEAFE","t1":"#111827","t2":"#4B5563","t3":"#9CA3AF","ibg":"#FFFFFF"},
    "Dark":    {"bg":"#212121","sf":"#2F2F2F","bd":"#3F3F3F","ac":"#5B9BFF",
                "al":"#1E3A5F","t1":"#ECECEC","t2":"#ABABAB","t3":"#6B6B6B","ibg":"#3F3F3F"},
}

DEFAULTS = dict(theme="Default", active_query="Artificial Intelligence",
                sort_by="publishedAt", days_back=7, page_size=6,
                language="en", feed_page=1, auto_refresh=False)
for k, v in DEFAULTS.items():
    if k not in st.session_state: setattr(st.session_state, k, v)

T = THEMES[st.session_state.theme]

# ── CSS — clean, minimal, ChatGPT-inspired ────────────────────────────────────
st.markdown(f"""
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600&display=swap');

/* ── Tokens ── */
:root {{
  --bg:  {T['bg']}; --sf:  {T['sf']}; --bd:  {T['bd']};
  --ac:  {T['ac']}; --al:  {T['al']};
  --t1:  {T['t1']}; --t2:  {T['t2']}; --t3:  {T['t3']};
  --ibg: {T['ibg']};
  --r: 10px;
  --f: 'Inter', system-ui, sans-serif;
}}

/* ── Base ── */
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

/* Kill all Streamlit chrome — including that empty top bar */
#MainMenu, footer, header,
[data-testid="stToolbar"],
[data-testid="stDecoration"],
[data-testid="stStatusWidget"],
[data-testid="stHeader"],
.stAppHeader {{
  display: none !important;
  height: 0 !important;
  visibility: hidden !important;
}}

/* Remove top padding Streamlit adds */
[data-testid="stAppViewBlockContainer"] {{
  padding-top: 1rem !important;
}}
[data-testid="block-container"] {{
  padding-top: 0 !important;
}}

/* ── Sidebar ── */
[data-testid="stSidebar"],
[data-testid="stSidebar"] > div,
[data-testid="stSidebarContent"] {{
  background: {T['sf']} !important;
  border-right: 1px solid {T['bd']} !important;
}}
[data-testid="stSidebar"] * {{ color: {T['t1']} !important; font-family: var(--f) !important; }}
[data-testid="stSidebar"] label {{ font-size: .75rem !important; font-weight: 600 !important; color: {T['t3']} !important; text-transform: uppercase; letter-spacing: .05em; }}

/* ── Input ── */
div[data-testid="stTextInput"] input {{
  background: var(--ibg) !important; color: var(--t1) !important;
  border: 1px solid var(--bd) !important; border-radius: var(--r) !important;
  font-size: .9rem !important; font-family: var(--f) !important;
  padding: .6rem .9rem !important; outline: none !important; box-shadow: none !important;
  transition: border-color .15s !important;
}}
div[data-testid="stTextInput"] input:focus {{
  border-color: var(--ac) !important;
  box-shadow: 0 0 0 3px {T['al']} !important;
}}
div[data-testid="stTextInput"] input::placeholder {{ color: var(--t3) !important; }}

/* ── Selectbox — FIX BLACK DROPDOWN ── */
div[data-baseweb="select"] > div {{
  background: var(--ibg) !important; border: 1px solid var(--bd) !important;
  border-radius: var(--r) !important; color: var(--t1) !important; font-family: var(--f) !important;
}}
div[data-baseweb="select"] * {{ color: var(--t1) !important; background: transparent !important; }}
div[data-baseweb="select"] svg {{ fill: {T['t2']} !important; }}

/* Dropdown list — this is what was black */
[data-baseweb="popover"],
[data-baseweb="popover"] > div,
ul[data-baseweb="menu"],
ul[data-baseweb="menu"] > li {{
  background: {T['sf']} !important;
  border: 1px solid {T['bd']} !important;
  border-radius: var(--r) !important;
  color: {T['t1']} !important;
  font-family: var(--f) !important;
}}
li[role="option"] {{
  color: {T['t1']} !important;
  background: {T['sf']} !important;
  font-size: .84rem !important;
}}
li[role="option"]:hover {{
  background: {T['al']} !important;
  color: {T['ac']} !important;
}}

/* ── Buttons ── */
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
div[data-testid="stButton"] > button[kind="primary"]:hover {{
  opacity: .88 !important; color: #fff !important;
}}

/* ── Slider ── */
[data-testid="stSlider"] p {{ color: {T['t3']} !important; font-size:.78rem !important; }}
[data-testid="stSlider"] [role="slider"] {{ background: {T['ac']} !important; }}

/* ── Checkbox ── */
[data-testid="stCheckbox"] label span {{ color: {T['t2']} !important; font-size:.82rem !important; }}

/* ── Tabs ── */
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

/* ── Spinner ── */
[data-testid="stSpinner"] > div > div {{ color: var(--t3) !important; }}

/* ─── App components ─── */

.app-nav {{
  display: flex; align-items: center; justify-content: space-between;
  padding: .9rem 0; margin-bottom: 1.25rem;
  border-bottom: 1px solid var(--bd);
}}
.nav-brand {{ font-size: 1.75rem; font-weight: 700; color: var(--t1); display: flex; align-items: center; gap: .5rem; letter-spacing: -.02em; }}
.nav-right  {{ display: flex; align-items: center; gap: .6rem; font-size: .78rem; color: var(--t3); }}
.live-dot   {{
  width: 7px; height: 7px; border-radius: 50%; background: #22C55E;
  display: inline-block; animation: blink 2s ease-in-out infinite;
}}
@keyframes blink {{ 0%,100%{{opacity:1}} 50%{{opacity:.2}} }}
.sv-badge {{
  background: var(--al); color: var(--ac); font-size: .7rem;
  font-weight: 600; padding: 2px 8px; border-radius: 999px;
  border: 1px solid var(--ac);
}}

/* Search row */
.search-row {{ display: flex; align-items: flex-end; gap: .6rem; margin-bottom: 1rem; }}

/* Topic pills */
.pills {{ display: flex; flex-wrap: wrap; gap: .35rem; margin-bottom: 1.25rem; }}

/* Section label */
.sec {{ font-size: .72rem; font-weight: 600; color: var(--t3); text-transform: uppercase;
       letter-spacing: .06em; margin-bottom: .55rem; }}

/* Section title */
.sec-ttl {{ font-size: 1rem; font-weight: 600; color: var(--t1); margin-bottom: .85rem; }}

/* Stat row */
.stat-row {{ display: flex; gap: .45rem; flex-wrap: wrap; margin-bottom: 1rem; }}
.stat-chip {{
  background: var(--sf); border: 1px solid var(--bd); border-radius: 8px;
  padding: .4rem .75rem;
}}
.stat-chip strong {{ display: block; font-size: .88rem; font-weight: 600; color: var(--t1); }}
.stat-chip span   {{ font-size: .65rem; color: var(--t3); }}

/* ── Article card ── */
.nc {{
  background: var(--sf); border: 1px solid var(--bd); border-radius: var(--r);
  overflow: hidden; display: flex; flex-direction: column; height: 100%;
  transition: box-shadow .15s, transform .15s;
}}
.nc:hover {{ box-shadow: 0 4px 16px rgba(0,0,0,.08); transform: translateY(-1px); }}
.nc-img {{ width:100%; height:152px; object-fit:cover; display:block; }}
.nc-ph  {{
  width:100%; height:152px;
  background: linear-gradient(135deg, var(--al) 0%, var(--bd) 100%);
  display:flex; align-items:center; justify-content:center; font-size:2rem;
}}
.nc-body  {{ padding:.78rem .88rem; flex:1; display:flex; flex-direction:column; gap:.2rem; }}
.nc-meta  {{ display:flex; align-items:center; gap:.3rem; flex-wrap:wrap; }}
.nc-src   {{
  font-size:.6rem; font-weight:700; text-transform:uppercase; letter-spacing:.04em;
  padding:.1rem .38rem; border-radius:999px;
  background:var(--al); color:var(--ac);
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
  font-size:.6rem;font-weight:500;color:var(--t3);cursor:pointer;
  padding:.1rem .32rem;border:1px solid var(--bd);border-radius:5px;
  background:transparent;transition:all .12s;
}}
.share-btn:hover{{ color:var(--ac);border-color:var(--ac);background:var(--al); }}

/* ── Trending ── */
.tr-item{{
  background:var(--sf);border:1px solid var(--bd);border-radius:var(--r);
  padding:.6rem .82rem;margin-bottom:.38rem;display:flex;align-items:flex-start;gap:.5rem;
}}
.tr-rank{{ font-size:1rem;font-weight:700;color:var(--bd);min-width:1rem;padding-top:1px; }}
.tr-ttl {{ font-size:.8rem;font-weight:500;color:var(--t1);line-height:1.42; }}
.tr-src {{ font-size:.64rem;color:var(--t3);margin-top:.1rem; }}

/* ── Empty ── */
.empty{{
  text-align:center;padding:2.5rem 1rem;
  background:var(--sf);border:1px dashed var(--bd);border-radius:var(--r);
}}
.empty .ico{{ font-size:2rem;margin-bottom:.35rem; }}
.empty p{{ font-size:.8rem;color:var(--t3);line-height:1.6; }}

/* ── Pagination ── */
.pg-bar{{ display:flex;align-items:center;justify-content:center;gap:1rem;margin-top:.75rem; }}

/* ── Scrollbar ── */
::-webkit-scrollbar{{ width:4px; }}
::-webkit-scrollbar-track{{ background:transparent; }}
::-webkit-scrollbar-thumb{{ background:var(--bd);border-radius:2px; }}
</style>
""", unsafe_allow_html=True)

# ─────────────────────────────────────────────────────────────────────────────
# SQLITE BOOKMARKS
# ─────────────────────────────────────────────────────────────────────────────
def _db():
    con = sqlite3.connect(DB_PATH)
    con.execute("""CREATE TABLE IF NOT EXISTS bookmarks(
        url TEXT PRIMARY KEY, title TEXT, description TEXT,
        source TEXT, published_at TEXT, url_to_image TEXT, saved_at TEXT)""")
    con.commit(); return con

def db_save(a):
    with _db() as c:
        c.execute("INSERT OR REPLACE INTO bookmarks VALUES(?,?,?,?,?,?,?)",(
            a.get("url",""), a.get("title",""),
            a.get("description","") or a.get("content",""),
            (a.get("source") or {}).get("name",""),
            a.get("publishedAt",""), a.get("urlToImage",""),
            datetime.utcnow().isoformat()))

def db_delete(url):
    with _db() as c: c.execute("DELETE FROM bookmarks WHERE url=?", (url,))

def db_has(url) -> bool:
    with _db() as c: return c.execute("SELECT 1 FROM bookmarks WHERE url=?", (url,)).fetchone() is not None

def db_all():
    with _db() as c:
        rows = c.execute("SELECT url,title,description,source,published_at,url_to_image FROM bookmarks ORDER BY saved_at DESC").fetchall()
    return [{"url":r[0],"title":r[1],"description":r[2],"source":{"name":r[3]},"publishedAt":r[4],"urlToImage":r[5]} for r in rows]

def db_clear():
    with _db() as c: c.execute("DELETE FROM bookmarks")

def db_count():
    with _db() as c: return c.execute("SELECT COUNT(*) FROM bookmarks").fetchone()[0]

# ─────────────────────────────────────────────────────────────────────────────
# HELPERS
# ─────────────────────────────────────────────────────────────────────────────
def esc(s): return str(s).replace("&","&amp;").replace("<","&lt;").replace('"','&quot;')

def summarize(text):
    if not text: return "No description available."
    text = re.sub(r"\s*\[\+\d+ chars\]$","",text).strip()
    s = [x.strip() for x in re.split(r"(?<=[.!?])\s+",text) if x.strip()]
    return " ".join(s[:2]) or "No description available."

def fmt_date(iso):
    if not iso: return ""
    try:
        dt = datetime.fromisoformat(iso.replace("Z","+00:00"))
        d  = datetime.now(timezone.utc) - dt
        if d.days>=1:       return f"{d.days}d ago"
        if d.seconds>=3600: return f"{d.seconds//3600}h ago"
        return f"{d.seconds//60}m ago"
    except: return iso[:10]

def src_name(a): return (a.get("source") or {}).get("name") or "Unknown"
def read_time(t): return "< 1 min" if not t else f"{max(1,round(len(t.split())/200))} min read"
def ce(cat): return CAT_EMOJI.get(cat.lower(),"📰")
def akey(a, pfx): return f"{pfx}_{hashlib.md5((a.get('url') or str(id(a))).encode()).hexdigest()[:8]}"

def sentiment(text):
    if not text: return '<span class="badge-neu">· Neutral</span>'
    t = text.lower()
    p = sum(1 for w in POS_WORDS if w in t)
    n = sum(1 for w in NEG_WORDS if w in t)
    if p > n: return '<span class="badge-pos">▲ Positive</span>'
    if n > p: return '<span class="badge-neg">▼ Negative</span>'
    return '<span class="badge-neu">· Neutral</span>'

def cred(source):
    sl = source.lower()
    if sl in HIGH_CRED: return '<span class="cred-hi">✓ Trusted</span>'
    if sl in MED_CRED:  return '<span class="cred-md">◈ Known</span>'
    return '<span class="cred-lo">? Unverified</span>'

# ─────────────────────────────────────────────────────────────────────────────
# RATE LIMIT TRACKER  (persisted in session_state)
# ─────────────────────────────────────────────────────────────────────────────
if "api_limited"     not in st.session_state: st.session_state.api_limited     = False
if "api_limit_until" not in st.session_state: st.session_state.api_limit_until = None

def _mark_limited():
    """Call when NewsAPI returns 429 or 401 exhausted — switches to RSS mode."""
    st.session_state.api_limited     = True
    st.session_state.api_limit_until = datetime.utcnow() + timedelta(hours=1)

def _is_limited() -> bool:
    if not st.session_state.api_limited: return False
    if st.session_state.api_limit_until and datetime.utcnow() > st.session_state.api_limit_until:
        st.session_state.api_limited     = False   # auto-reset after 1 hour
        st.session_state.api_limit_until = None
        return False
    return True

def _show_fallback_banner():
    st.markdown(
        '<div style="background:#FEF9C3;border:1px solid #FDE047;border-radius:8px;'
        'padding:.55rem 1rem;font-size:.78rem;color:#854D0E;margin-bottom:.85rem">'
        '⚠️ <b>NewsAPI limit reached</b> — showing results from free RSS feeds. '
        'Resets automatically in ~1 hour.</div>',
        unsafe_allow_html=True)

# ─────────────────────────────────────────────────────────────────────────────
# RSS FEED SOURCES  (free, no key needed)
# ─────────────────────────────────────────────────────────────────────────────
RSS_FEEDS = {
    "general":       ["http://feeds.bbci.co.uk/news/rss.xml",
                      "https://rss.nytimes.com/services/xml/rss/nyt/HomePage.xml",
                      "https://feeds.npr.org/1001/rss.xml"],
    "technology":    ["http://feeds.bbci.co.uk/news/technology/rss.xml",
                      "https://feeds.feedburner.com/TechCrunch",
                      "https://www.wired.com/feed/rss",
                      "https://feeds.arstechnica.com/arstechnica/index"],
    "business":      ["http://feeds.bbci.co.uk/news/business/rss.xml",
                      "https://feeds.bloomberg.com/markets/news.rss",
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

# Topic → RSS search via Google News RSS (no key)
def _google_news_rss(query: str, lang: str = "en") -> str:
    q = requests.utils.quote(query)
    return f"https://news.google.com/rss/search?q={q}&hl={lang}&gl=US&ceid=US:{lang}"

def _extract_image(item_xml: str, article_url: str) -> str:
    """
    Try 3 methods to find an image for an RSS item:
      1. media:content or media:thumbnail (most feeds)
      2. enclosure tag
      3. <img> inside description HTML
    Returns image URL string or "".
    """
    # 1. media:content / media:thumbnail
    for pattern in [
        r'<media:content[^>]+url=["\']([^"\']+)["\']',
        r'<media:thumbnail[^>]+url=["\']([^"\']+)["\']',
        r'<media:content[^>]+url=([^\s>]+)',
    ]:
        m = re.search(pattern, item_xml, re.IGNORECASE)
        if m:
            url = m.group(1).strip().strip('"\'')
            if url.startswith("http"): return url

    # 2. enclosure tag (url attribute)
    m = re.search(r'<enclosure[^>]+url=["\']([^"\']+)["\']', item_xml, re.IGNORECASE)
    if m:
        url = m.group(1).strip()
        if url.startswith("http") and any(ext in url.lower() for ext in (".jpg",".jpeg",".png",".webp",".gif")):
            return url

    # 3. <img src="..."> inside description CDATA
    m = re.search(r'<img[^>]+src=["\']([^"\']+)["\']', item_xml, re.IGNORECASE)
    if m:
        url = m.group(1).strip()
        if url.startswith("http"): return url

    return ""

def _parse_rss(url: str, limit: int = 10) -> list:
    """Fetch and parse an RSS feed. Returns list of article dicts."""
    try:
        headers = {"User-Agent": "Mozilla/5.0 (compatible; NewsAssistant/1.0)"}
        r = requests.get(url, headers=headers, timeout=8)
        if r.status_code != 200: return []
        xml = r.text

        articles = []
        items = re.findall(r"<item>(.*?)</item>", xml, re.DOTALL)
        for item in items[:limit]:
            def tag(t):
                m = re.search(rf"<{t}[^>]*><!\[CDATA\[(.*?)\]\]></{t}>", item, re.DOTALL)
                if m: return m.group(1).strip()
                m = re.search(rf"<{t}[^>]*>(.*?)</{t}>", item, re.DOTALL)
                return m.group(1).strip() if m else ""

            title = tag("title")
            link  = tag("link") or tag("guid")
            desc  = re.sub(r"<[^>]+>", "", tag("description"))
            pub   = tag("pubDate")
            src_m = re.search(r"<source[^>]*>(.*?)</source>", item, re.DOTALL)
            src   = src_m.group(1).strip() if src_m else (
                    re.search(r"https?://(?:www\.)?([^/]+)", link or "").group(1)
                    if link else "RSS Feed")

            # ── Image extraction (3 methods) ──
            img = _extract_image(item, link or "")

            # Parse pubDate → ISO
            iso = ""
            for fmt in ("%a, %d %b %Y %H:%M:%S %z", "%a, %d %b %Y %H:%M:%S GMT"):
                try: iso = datetime.strptime(pub.strip(), fmt).isoformat(); break
                except: pass

            if title and link:
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

def _rss_for_query(query: str, lang: str, limit: int) -> list:
    """Use Google News RSS to search by query — unlimited, no key."""
    return _parse_rss(_google_news_rss(query, lang), limit=limit)

def _rss_for_category(category: str, limit: int) -> list:
    """Pull from curated RSS feeds for a category."""
    feeds = RSS_FEEDS.get(category, RSS_FEEDS["general"])
    articles, seen = [], set()
    for feed_url in feeds:
        for art in _parse_rss(feed_url, limit=limit):
            if art["url"] not in seen:
                seen.add(art["url"])
                articles.append(art)
        if len(articles) >= limit: break
    return articles[:limit]

# ─────────────────────────────────────────────────────────────────────────────
# NEWS API  (with rate-limit detection + RSS fallback)
# ─────────────────────────────────────────────────────────────────────────────
def _api(url, params) -> tuple:
    """Returns (data_or_None, hit_limit: bool)."""
    try:
        r = requests.get(url, params={**params, "apiKey": NEWS_API_KEY}, timeout=10)
        if r.status_code in (429, 426):          # rate limited
            return None, True
        if r.status_code == 401:
            body = r.json()
            if "rateLimited" in body.get("code","") or "maximumResultsReached" in body.get("code",""):
                return None, True
            return None, False
        r.raise_for_status()
        return r.json(), False
    except requests.HTTPError:
        return None, False
    except requests.ConnectionError:
        return None, False
    except requests.Timeout:
        return None, False
    except Exception:
        return None, False

def _clean(arts):
    return [a for a in arts
            if a.get("title") and a["title"] != "[Removed]"
            and (a.get("source") or {}).get("name") != "[Removed]"
            and a.get("url")]

@st.cache_data(ttl=CACHE_TTL, show_spinner=False)
def fetch_everything(query, sort_by, page_size, days_back, language="en", page=1):
    # Try NewsAPI first (unless already known-limited)
    if not _is_limited():
        fd = (datetime.utcnow() - timedelta(days=days_back)).strftime("%Y-%m-%d")
        data, limited = _api(EVERYTHING_EP, {
            "q": query, "language": language, "sortBy": sort_by,
            "pageSize": page_size, "from": fd, "page": page,
        })
        if limited:
            _mark_limited()
        elif data:
            arts = _clean(data.get("articles", []))
            if arts: return arts

    # RSS fallback
    return _rss_for_query(query, language, page_size)

@st.cache_data(ttl=CACHE_TTL, show_spinner=False)
def fetch_headlines(category, page_size=6):
    if not _is_limited():
        if category in ("gaming", "movies"):
            q  = {"gaming": "gaming video games", "movies": "movies film cinema"}[category]
            fd = (datetime.utcnow() - timedelta(days=3)).strftime("%Y-%m-%d")
            data, limited = _api(EVERYTHING_EP, {"q": q, "language": "en",
                                  "sortBy": "publishedAt", "pageSize": page_size, "from": fd})
        else:
            data, limited = _api(TOP_HEADLINES_EP,
                                  {"country": "us", "category": category, "pageSize": page_size})
        if limited:
            _mark_limited()
        elif data:
            arts = _clean(data.get("articles", []))
            if arts: return arts

    # RSS fallback
    return _rss_for_category(category, page_size)

# ─────────────────────────────────────────────────────────────────────────────
# CARD
# ─────────────────────────────────────────────────────────────────────────────
def card_html(a, cat="general"):
    title = esc(a.get("title") or "Untitled")
    desc  = a.get("description") or a.get("content") or ""
    url   = esc(a.get("url") or "#")
    img   = a.get("urlToImage") or ""
    s     = src_name(a); se = esc(s)
    pub   = fmt_date(a.get("publishedAt"))
    rt    = read_time(desc)
    summ  = esc(summarize(desc))
    em    = ce(cat)
    sent  = sentiment(f"{a.get('title','')} {desc}")
    cr    = cred(s)
    share = f"navigator.clipboard.writeText('{url}').then(()=>{{this.textContent='✓ Copied!';setTimeout(()=>this.textContent='⎘',1500)}})"

    img_url = esc(img)
    if img:
        img_b = (f'<img class="nc-img" src="{img_url}" alt="" '
                 f'onerror="this.style.display=\'none\';this.nextElementSibling.style.display=\'flex\'">'
                 f'<div class="nc-ph" style="display:none">{em}</div>')
    else:
        img_b = f'<div class="nc-ph">{em}</div>'

    return (f'<div class="nc">{img_b}'
            f'<div class="nc-body">'
            f'<div class="nc-meta"><span class="nc-src">{se}</span><span class="nc-time">{pub}</span></div>'
            f'<div class="nc-ttl">{title}</div>'
            f'<div class="nc-sum">{summ}</div>'
            f'<div class="nc-tags">{sent}&nbsp;{cr}</div>'
            f'<div class="nc-foot">'
            f'<a class="nc-link" href="{url}" target="_blank" rel="noopener">Read article →</a>'
            f'<span style="display:flex;align-items:center;gap:.35rem">'
            f'<span class="nc-rt">{rt}</span>'
            f'<button class="share-btn" onclick="{share}">⎘</button>'
            f'</span></div></div></div>')

def render_grid(articles, cat="general", cols=3, pfx="g"):
    if not articles:
        st.markdown('<div class="empty"><div class="ico">📭</div>'
                    '<p>No articles found.<br>Try a different search or adjust filters.</p></div>',
                    unsafe_allow_html=True); return
    for i in range(0, len(articles), cols):
        for col, art in zip(st.columns(cols), articles[i:i+cols]):
            with col:
                st.markdown(card_html(art, cat), unsafe_allow_html=True)
                saved = db_has(art.get("url",""))
                if st.button("⭐ Saved" if saved else "☆  Save",
                             key=akey(art,pfx), use_container_width=True):
                    db_delete(art["url"]) if saved else db_save(art)
                    st.rerun()

def render_trending(articles):
    if not articles:
        st.markdown('<p style="font-size:.78rem;color:var(--t3)">No headlines available.</p>',
                    unsafe_allow_html=True); return
    for i,a in enumerate(articles,1):
        title = esc(a.get("title") or "Untitled")
        url   = a.get("url") or "#"
        s,pub = esc(src_name(a)), fmt_date(a.get("publishedAt"))
        st.markdown(f'<div class="tr-item"><div class="tr-rank">{i}</div>'
                    f'<div><div class="tr-ttl"><a href="{url}" target="_blank" '
                    f'style="color:inherit;text-decoration:none">{title}</a></div>'
                    f'<div class="tr-src">{s} · {pub}</div></div></div>',
                    unsafe_allow_html=True)

def render_stats(articles, query, cat):
    srcs = len({src_name(a) for a in articles})
    lang = {v:k for k,v in LANGUAGES.items()}.get(st.session_state.language,"English")
    st.markdown(
        f'<div class="stat-row">'
        f'<div class="stat-chip"><strong>{len(articles)}</strong><span>Articles</span></div>'
        f'<div class="stat-chip"><strong>{srcs}</strong><span>Sources</span></div>'
        f'<div class="stat-chip"><strong>{cat.title()}</strong><span>Category</span></div>'
        f'<div class="stat-chip"><strong>&ldquo;{esc(query)}&rdquo;</strong><span>Topic</span></div>'
        f'<div class="stat-chip"><strong>{lang}</strong><span>Language</span></div>'
        f'</div>', unsafe_allow_html=True)

# ─────────────────────────────────────────────────────────────────────────────
# SIDEBAR
# ─────────────────────────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown("### ⚙️ Filters")
    st.markdown("---")

    st.markdown("**Category**")
    sidebar_cat = st.selectbox("cat", CATEGORIES,
                               format_func=lambda c: f"{ce(c)} {c.title()}",
                               label_visibility="collapsed", key="sb_cat")
    st.markdown("**Sort by**")
    sort_lbl = st.selectbox("sort", list(SORT_OPTIONS.keys()),
                            label_visibility="collapsed", key="sb_sort")
    st.markdown("**Language**")
    lang_lbl = st.selectbox("lang", list(LANGUAGES.keys()),
                            index=list(LANGUAGES.values()).index(st.session_state.language)
                                  if st.session_state.language in LANGUAGES.values() else 0,
                            label_visibility="collapsed", key="sb_lang")
    st.markdown("**Days back**")
    days_back = st.slider("days",1,30,st.session_state.days_back,
                          label_visibility="collapsed", key="sb_days")
    st.markdown("**Articles per page**")
    page_size = st.slider("n",3,12,st.session_state.page_size,
                          label_visibility="collapsed", key="sb_n")
    st.markdown("---")
    c1, c2 = st.columns(2)
    if c1.button("Apply",use_container_width=True,type="primary",key="apply"):
        st.session_state.days_back = days_back
        st.session_state.page_size = page_size
        st.session_state.sort_by   = SORT_OPTIONS[sort_lbl]
        st.session_state.language  = LANGUAGES[lang_lbl]
        st.session_state.feed_page = 1
        st.cache_data.clear(); st.rerun()
    if c2.button("Reset",use_container_width=True,key="sb_reset"):
        for k,v in DEFAULTS.items(): setattr(st.session_state,k,v)
        st.rerun()
    st.markdown("---")
    if st.button("🗑 Clear saved",use_container_width=True,key="sb_clear"):
        db_clear(); st.rerun()

# ─────────────────────────────────────────────────────────────────────────────
# MAIN LAYOUT
# ─────────────────────────────────────────────────────────────────────────────

# ① Navbar
n_sv  = db_count()
badge = f'<span class="sv-badge">⭐ {n_sv}</span>' if n_sv else ""
st.markdown(
    f'<div class="app-nav">'
    f'<div class="nav-brand">📰 AI News Assistant</div>'
    f'<div class="nav-right">'
    f'<span class="live-dot"></span><span>Live</span>'
    f'<span style="color:var(--bd)">·</span>'
    f'<span>AI Summaries</span>'
    f'<span style="color:var(--bd)">·</span>'
    f'<span>Saved {badge}</span>'
    f'</div></div>', unsafe_allow_html=True)

# ② Search bar + Theme toggle (single clean row, no empty space)
sc, bc, tc = st.columns([6, 1, 2])
with sc:
    st.markdown('<p class="sec">Search Topic</p>', unsafe_allow_html=True)
    query_input = st.text_input("q", value=st.session_state.active_query,
                                placeholder="e.g. Tesla, Climate, AI…",
                                label_visibility="collapsed", key="search_input")
with bc:
    st.markdown('<p class="sec">&nbsp;</p>', unsafe_allow_html=True)
    if st.button("Search", type="primary", use_container_width=True, key="do_search"):
        q = query_input.strip() or "Artificial Intelligence"
        st.session_state.active_query = q
        st.session_state.feed_page    = 1
        st.cache_data.clear(); st.rerun()
with tc:
    st.markdown('<p class="sec">Theme</p>', unsafe_allow_html=True)
    chosen = st.selectbox("theme", list(THEMES.keys()),
                          index=list(THEMES.keys()).index(st.session_state.theme),
                          label_visibility="collapsed", key="theme_sel")
    if chosen != st.session_state.theme:
        st.session_state.theme = chosen; st.rerun()

# ③ Quick topic pills
st.markdown('<p class="sec" style="margin-bottom:.4rem">Quick Topics</p>', unsafe_allow_html=True)
qt = st.columns(len(QUICK_TOPICS))
for col, topic in zip(qt, QUICK_TOPICS):
    with col:
        if st.button(topic, key=f"qt_{topic.replace(' ','_')}", use_container_width=True):
            st.session_state.active_query = topic
            st.session_state.feed_page    = 1
            st.cache_data.clear(); st.rerun()

st.markdown("<hr style='border-color:var(--bd);margin:1rem 0'>", unsafe_allow_html=True)

# ④ Tabs
query     = st.session_state.active_query
sort_by   = st.session_state.sort_by
days_back = st.session_state.days_back
page_size = st.session_state.page_size
language  = st.session_state.language
feed_page = st.session_state.feed_page

tab_feed, tab_trend, tab_saved = st.tabs(["📰  Feed", "🔥  Trending", "⭐  Saved"])

# ── Feed ──────────────────────────────────────────────────────────────────────
with tab_feed:
    st.markdown(f'<div class="sec-ttl">Latest on &ldquo;{esc(query)}&rdquo;</div>',
                unsafe_allow_html=True)
    if _is_limited():
        _show_fallback_banner()
    with st.spinner("Fetching articles…"):
        articles = fetch_everything(query, sort_by=sort_by, page_size=page_size,
                                    days_back=days_back, language=language, page=feed_page)
    if articles:
        render_stats(articles, query, sidebar_cat)
    render_grid(articles, cat=sidebar_cat, cols=3, pfx="feed")

    # Pagination
    p1, p2, p3 = st.columns([1,2,1])
    with p1:
        if feed_page > 1:
            if st.button("← Prev", use_container_width=True, key="pg_prev"):
                st.session_state.feed_page -= 1; st.cache_data.clear(); st.rerun()
    with p2:
        st.markdown(f'<p style="text-align:center;font-size:.75rem;color:var(--t3);padding:.5rem 0">Page {feed_page}</p>',
                    unsafe_allow_html=True)
    with p3:
        if len(articles) == page_size:
            if st.button("Next →", use_container_width=True, key="pg_next", type="primary"):
                st.session_state.feed_page += 1; st.cache_data.clear(); st.rerun()

# ── Trending ──────────────────────────────────────────────────────────────────
with tab_trend:
    st.markdown('<div class="sec-ttl">Top Headlines by Category</div>', unsafe_allow_html=True)
    if _is_limited():
        _show_fallback_banner()
    inner = st.tabs([f"{em} {name}" for em,name,_ in TRENDING_TABS])
    for (em,name,key), ctab in zip(TRENDING_TABS, inner):
        with ctab:
            with st.spinner(f"Loading {name}…"):
                t_arts = fetch_headlines(key, page_size=6)
            lc, rc = st.columns([2, 1])
            with lc:
                render_grid(t_arts, cat=key, cols=2, pfx=f"tr_{key}")
            with rc:
                st.markdown('<p class="sec" style="margin-bottom:.4rem">Quick Read</p>', unsafe_allow_html=True)
                render_trending(t_arts[:5])

# ── Saved ─────────────────────────────────────────────────────────────────────
with tab_saved:
    saved = db_all()
    h1, h2 = st.columns([5,1])
    with h1:
        st.markdown('<div class="sec-ttl">Your Saved Articles</div>', unsafe_allow_html=True)
    with h2:
        if saved and st.button("🗑 Clear", key="clr_saved", use_container_width=True):
            db_clear(); st.rerun()

    if not saved:
        st.markdown('<div class="empty"><div class="ico">🔖</div>'
                    '<p>No saved articles yet.<br>Hit ☆ Save on any card.<br>'
                    '<small>Saves persist across sessions.</small></p></div>',
                    unsafe_allow_html=True)
    else:
        n = len(saved)
        st.markdown(f'<div class="stat-row">'
                    f'<div class="stat-chip"><strong>{n}</strong>'
                    f'<span>Saved article{"s" if n!=1 else ""}</span></div>'
                    f'<div class="stat-chip"><strong>Persistent</strong><span>SQLite</span></div>'
                    f'</div>', unsafe_allow_html=True)
        render_grid(saved, cols=3, pfx="sv")

