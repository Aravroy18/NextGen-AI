import os
import io
import re
import json
import html
import uuid
import base64
import sqlite3
import hashlib
import secrets
import requests
from html.parser import HTMLParser
from urllib.parse import urlparse, parse_qs, unquote
import streamlit as st
import streamlit.components.v1 as components

from datetime import datetime
from dotenv import load_dotenv

load_dotenv()

# ============================================================
# NEXTGEN AI V10
# Existing visual theme + practical new features
# ============================================================

st.set_page_config(
    page_title="NEXTGEN AI",
    page_icon="✦",
    layout="wide",
    initial_sidebar_state="expanded"
)

DB_PATH = "nextgen_v5.db"

# ---------------- API SECRETS ----------------

def get_secret(key):
    try:
        return st.secrets.get(key, os.getenv(key, ""))
    except Exception:
        return os.getenv(key, "")

GROQ_KEY = get_secret("GROQ_API_KEY")
GEMINI_KEY = get_secret("GEMINI_API_KEY")
OPENAI_KEY = get_secret("OPENAI_API_KEY")
ANTHROPIC_KEY = get_secret("ANTHROPIC_API_KEY")

CF_ACCOUNT = get_secret("CLOUDFLARE_ACCOUNT_ID")
CF_TOKEN = get_secret("CLOUDFLARE_API_TOKEN")
CF_LIVE_URL = get_secret("CLOUDFLARE_VOICE_URL")
TAVILY_KEY = get_secret("TAVILY_API_KEY")

GROQ_MODEL = "openai/gpt-oss-120b"
GEMINI_MODEL = "gemini-3.5-flash-lite"
OPENAI_MODEL = "gpt-4.1-mini"
CLAUDE_MODEL = "claude-3-5-haiku-latest"
IMAGE_MODEL = "@cf/black-forest-labs/flux-1-schnell"

SYSTEM_PROMPT = """
You are NEXTGEN AI, a helpful and intelligent AI assistant.
Give accurate, clear and useful answers.
Communicate in the language used by the user.
For school topics, explain concepts in an easy-to-understand way.
For coding, provide complete and practical code when requested.
Never invent facts, sources, or actions.
The creator and owner of NEXTGEN AI is Arav.

CREATOR-IDENTITY RESPONSE RULE:
- If anyone asks who created, owns, built, or is behind NEXTGEN AI,
  clearly answer: "NEXTGEN AI was created by Arav."
- Add a warm, respectful description grounded in known facts: Arav is a
  curious student developer and AI enthusiast who enjoys technology,
  coding, creative problem-solving, and building useful AI projects.
- You may praise his creativity, curiosity, effort, and initiative, but
  do not invent awards, qualifications, achievements, wealth, or biography.
- Do not reveal or guess private details such as his school, age, address,
  contact details, or location. Do not claim to know anything not provided.
- Do not say that the AI itself has a human owner beyond identifying the
  creator of this NEXTGEN AI application.

For financial topics, provide educational information, not personal
investment instructions or guaranteed returns.
"""

# ---------------- DATABASE ----------------

def connect_db():
    con = sqlite3.connect(DB_PATH, check_same_thread=False)
    con.execute("PRAGMA foreign_keys=ON")
    return con


def init_db():
    con = connect_db()
    cur = con.cursor()

    cur.execute("""
        CREATE TABLE IF NOT EXISTS users(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            email TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            created TEXT
        )
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS v5_chats(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT,
            created TEXT
        )
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS v5_messages(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            chat_id INTEGER,
            role TEXT,
            content TEXT,
            created TEXT
        )
    """)

    columns = [
        row[1] for row in cur.execute(
            "PRAGMA table_info(v5_chats)"
        ).fetchall()
    ]

    if "user_id" not in columns:
        cur.execute("ALTER TABLE v5_chats ADD COLUMN user_id INTEGER")

    cur.execute("""
        CREATE INDEX IF NOT EXISTS idx_messages_chat
        ON v5_messages(chat_id)
    """)

    cur.execute("""
        CREATE INDEX IF NOT EXISTS idx_chats_user
        ON v5_chats(user_id)
    """)

    con.commit()
    con.close()


init_db()


def password_hash(password, salt=None):
    salt = salt or secrets.token_hex(16)
    digest = hashlib.pbkdf2_hmac(
        "sha256",
        password.encode(),
        salt.encode(),
        250000
    ).hex()
    return salt + "$" + digest


def verify_password(password, saved):
    try:
        salt, old_hash = saved.split("$", 1)
        return secrets.compare_digest(
            password_hash(password, salt).split("$", 1)[1],
            old_hash
        )
    except Exception:
        return False


def register_user(username, email, password):
    con = connect_db()
    try:
        con.execute(
            """INSERT INTO users(username,email,password_hash,created)
               VALUES(?,?,?,?)""",
            (
                username.strip(),
                email.strip().lower(),
                password_hash(password),
                datetime.now().isoformat()
            )
        )
        con.commit()
        return True, "Account created successfully."
    except sqlite3.IntegrityError:
        return False, "Username or email already exists."
    finally:
        con.close()


def login_user(email, password):
    con = connect_db()
    row = con.execute(
        "SELECT id,username,password_hash FROM users WHERE email=?",
        (email.strip().lower(),)
    ).fetchone()
    con.close()

    if row and verify_password(password, row[2]):
        return {"id": row[0], "username": row[1]}
    return None


def create_chat(user_id):
    con = connect_db()
    cur = con.cursor()
    cur.execute(
        """INSERT INTO v5_chats(title,created,user_id)
           VALUES(?,?,?)""",
        ("New Chat", datetime.now().isoformat(), user_id)
    )
    chat_id = cur.lastrowid
    con.commit()
    con.close()
    return chat_id


def all_chats(user_id):
    con = connect_db()
    rows = con.execute(
        """SELECT id,title,created FROM v5_chats
           WHERE user_id=? ORDER BY id DESC""",
        (user_id,)
    ).fetchall()
    con.close()
    return rows


def get_messages(chat_id, user_id):
    con = connect_db()
    rows = con.execute(
        """SELECT m.role,m.content
           FROM v5_messages m
           JOIN v5_chats c ON c.id=m.chat_id
           WHERE m.chat_id=? AND c.user_id=?
           ORDER BY m.id""",
        (chat_id, user_id)
    ).fetchall()
    con.close()
    return rows


def save_message(chat_id, user_id, role, content):
    con = connect_db()
    con.execute(
        """INSERT INTO v5_messages(chat_id,role,content,created)
           SELECT ?,?,?,?
           WHERE EXISTS(
               SELECT 1 FROM v5_chats WHERE id=? AND user_id=?
           )""",
        (
            chat_id, role, content, datetime.now().isoformat(),
            chat_id, user_id
        )
    )
    con.commit()
    con.close()


def set_chat_title(chat_id, user_id, title):
    con = connect_db()
    con.execute(
        """UPDATE v5_chats SET title=?
           WHERE id=? AND user_id=?""",
        (title[:48], chat_id, user_id)
    )
    con.commit()
    con.close()


def remove_chat(chat_id, user_id):
    con = connect_db()
    con.execute(
        """DELETE FROM v5_messages
           WHERE chat_id=? AND chat_id IN
           (SELECT id FROM v5_chats WHERE user_id=?)""",
        (chat_id, user_id)
    )
    con.execute(
        "DELETE FROM v5_chats WHERE id=? AND user_id=?",
        (chat_id, user_id)
    )
    con.commit()
    con.close()


# ---------------- AUTHENTICATION ----------------

if "user" not in st.session_state:
    st.session_state.user = None

if "auth_mode" not in st.session_state:
    st.session_state.auth_mode = "Login"


# ---------------- DESIGN: ORIGINAL V7 THEME ----------------

st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800;900&display=swap');

html,body,[class*="css"] {
    font-family: Inter, sans-serif;
}

.stApp {
    background:
      radial-gradient(ellipse at 12% 0%,#28235a 0%,transparent 35%),
      radial-gradient(ellipse at 95% 5%,#172e50 0%,transparent 35%),
      #080c18;
    color: #f6f6ff;
}

.block-container {
    max-width: 1450px;
    padding-top: 1.4rem;
    padding-bottom: 5rem;
}

[data-testid="stSidebar"] {
    background: linear-gradient(180deg,#111a30,#0a1020);
    border-right: 1px solid #2c3858;
}

[data-testid="stSidebar"] > div {
    padding-top: 1.2rem;
}

/* Keep Streamlit's native sidebar controls readable across versions. */
[data-testid="stSidebarCollapseButton"],
[data-testid="collapsedControl"],
[data-testid="stSidebarCollapsedControl"] {
    color: #dce3ff !important;
}
[data-testid="stSidebarCollapseButton"] span,
[data-testid="collapsedControl"] span,
[data-testid="stSidebarCollapsedControl"] span {
    font-size: 0 !important;
    line-height: 1 !important;
}
[data-testid="stSidebarCollapseButton"] span::after {
    content: "‹";
    font-size: 26px;
    font-weight: 700;
}
[data-testid="collapsedControl"] span::after,
[data-testid="stSidebarCollapsedControl"] span::after {
    content: "›";
    font-size: 26px;
    font-weight: 700;
}

[data-testid="stSidebar"] button {
    text-align: left;
    border-radius: 11px;
    background: transparent;
    border: 1px solid transparent;
    color: #dce3ff;
    min-height: 40px;
}

[data-testid="stSidebar"] button:hover {
    background: #242d4a;
    border-color: #414d76;
}

.brand {
    font-size: 27px;
    font-weight: 900;
    letter-spacing: -1.3px;
    padding: 5px 0;
}

.brand span {
    color: #a89aff;
}

.sidebar-tag {
    color: #8998bd;
    font-size: 10px;
    letter-spacing: 2px;
    margin-bottom: 18px;
}

.hero {
    border: 1px solid #55548b;
    background: linear-gradient(115deg,#171e3e,#30265d 55%,#183451);
    border-radius: 25px;
    padding: 34px;
    margin-bottom: 25px;
    box-shadow: 0 15px 50px #0005;
}

.hero-label {
    color: #c0b6ff;
    font-size: 11px;
    font-weight: 800;
    letter-spacing: 3px;
}

.hero-title {
    font-size: clamp(34px,5vw,55px);
    font-weight: 900;
    line-height: 1.1;
    margin: 13px 0;
    color: white;
}

.hero-sub {
    color: #c4cbe5;
    font-size: 14px;
    max-width: 850px;
}

.panel {
    border: 1px solid #303c5d;
    border-radius: 18px;
    padding: 21px;
    background: linear-gradient(145deg,#172139,#10172a);
    min-height: 125px;
    margin-bottom: 12px;
}

.panel-icon {
    font-size: 25px;
    margin-bottom: 8px;
}

.panel-title {
    font-size: 17px;
    font-weight: 800;
    color: white;
}

.panel-desc {
    font-size: 12px;
    color: #aab7d4;
    margin-top: 7px;
    line-height: 1.5;
}

.metric {
    border: 1px solid #303c5d;
    background: linear-gradient(145deg,#19243d,#111a2c);
    padding: 17px;
    border-radius: 15px;
}

.metric-label {
    font-size: 11px;
    color: #aab6d4;
}

.metric-value {
    font-size: 23px;
    font-weight: 900;
    margin: 5px 0;
}

.small-muted {
    color: #9ca9c8;
    font-size: 11px;
}

.dash-feature {
    border: 1px solid #39486d;
    border-radius: 18px;
    padding: 18px 20px;
    background: linear-gradient(135deg,#182541,#121a30);
    margin-bottom: 12px;
}

.dash-feature h3 {
    font-size: 17px;
    margin: 0 0 6px;
    color: white;
}

.dash-feature p {
    font-size: 12px;
    color: #aebbd7;
    margin: 0;
}

.dash-kicker {
    font-size: 10px;
    letter-spacing: 2px;
    color: #bcb2ff;
    font-weight: 800;
}

.tool-stat {
    border: 1px solid #3b4770;
    border-radius: 15px;
    padding: 15px 17px;
    background: linear-gradient(130deg,#1b2845,#171b36);
    margin-bottom: 15px;
}

div.stButton > button,
div.stLinkButton > a {
    border-radius: 11px;
    border: 1px solid #414d72;
    background: linear-gradient(120deg,#252f50,#34285e);
    color: white;
    font-weight: 700;
    min-height: 39px;
}

div.stButton > button:hover,
div.stLinkButton > a:hover {
    border-color: #aaa0ff;
    color: white;
}

div[data-testid="stChatMessage"] {
    background: #141d30;
    border: 1px solid #2b3855;
    border-radius: 17px;
    padding: 13px;
    margin-bottom: 12px;
}

[data-testid="stChatInput"] {
    border: 1px solid #515b7d !important;
    border-radius: 24px !important;
    background: #111a2c !important;
    box-shadow: 0 5px 25px #0004;
}

[data-testid="stChatInput"] textarea {
    color: white !important;
    font-size: 14px !important;
}

[data-testid="stChatInput"] button {
    border-radius: 50% !important;
}

div[data-testid="stFileUploader"] {
    border: 1px dashed #535f86;
    border-radius: 13px;
    background: #121b30;
    padding: 8px;
}

div[data-testid="stTextInput"] input,
div[data-testid="stTextArea"] textarea {
    background: #111a2d;
    color: white;
    border: 1px solid #394766;
    border-radius: 12px;
}

hr {
    border-color: #293550;
}

footer,#MainMenu {
    visibility: hidden;
}
</style>
""", unsafe_allow_html=True)


# ---------------- UI HELPERS ----------------

def hero(title, subtitle, label="NEXTGEN AI"):
    st.markdown(f"""
    <div class="hero">
      <div class="hero-label">{label}</div>
      <div class="hero-title">{title}</div>
      <div class="hero-sub">{subtitle}</div>
    </div>
    """, unsafe_allow_html=True)


def metric(label, value, note):
    st.markdown(f"""
    <div class="metric">
      <div class="metric-label">{label}</div>
      <div class="metric-value">{value}</div>
      <div class="small-muted">{note}</div>
    </div>
    """, unsafe_allow_html=True)


def render_answer_controls(answer_text, control_key):
    """Render copy and browser read-aloud controls for one AI-generated answer."""
    if not answer_text:
        return

    safe_key = re.sub(r"[^a-zA-Z0-9_-]", "_", str(control_key))
    encoded_text = base64.b64encode(
        str(answer_text).encode("utf-8")
    ).decode("ascii")

    components.html(f"""
    <div style="display:flex;gap:8px;align-items:center;flex-wrap:wrap;font-family:Arial,sans-serif;">
      <button id="ng-copy-{safe_key}" style="border:1px solid #59658a;border-radius:9px;padding:8px 12px;background:#202b48;color:white;font-weight:700;cursor:pointer;">📋 Copy</button>
      <button id="ng-speak-{safe_key}" style="border:1px solid #59658a;border-radius:9px;padding:8px 12px;background:#252f50;color:white;font-weight:700;cursor:pointer;">🔊 Read aloud</button>
      <button id="ng-stop-{safe_key}" style="border:1px solid #59658a;border-radius:9px;padding:8px 12px;background:#171f35;color:white;cursor:pointer;">Stop</button>
      <span id="ng-status-{safe_key}" style="color:#aebbd7;font-size:12px;">Copy or listen to this answer</span>
    </div>
    <script>
    (() => {{
      const answerText = new TextDecoder().decode(
        Uint8Array.from(atob('{encoded_text}'), c => c.charCodeAt(0))
      );
      const copyBtn = document.getElementById('ng-copy-{safe_key}');
      const speakBtn = document.getElementById('ng-speak-{safe_key}');
      const stopBtn = document.getElementById('ng-stop-{safe_key}');
      const status = document.getElementById('ng-status-{safe_key}');

      copyBtn.onclick = async () => {{
        try {{
          if (navigator.clipboard && window.isSecureContext) {{
            await navigator.clipboard.writeText(answerText);
          }} else {{
            const area = document.createElement('textarea');
            area.value = answerText;
            area.style.position = 'fixed';
            area.style.opacity = '0';
            document.body.appendChild(area);
            area.select();
            const copied = document.execCommand('copy');
            area.remove();
            if (!copied) throw new Error('Copy was blocked');
          }}
          status.textContent = 'Copied';
        }} catch (error) {{
          status.textContent = 'Copy was blocked by the browser';
        }}
      }};

      speakBtn.onclick = () => {{
        if (!('speechSynthesis' in window)) {{
          status.textContent = 'Speech is not supported in this browser';
          return;
        }}
        window.speechSynthesis.cancel();
        const utterance = new SpeechSynthesisUtterance(answerText);
        utterance.rate = 0.96;
        utterance.pitch = 1.0;
        const voices = window.speechSynthesis.getVoices();
        const preferred = voices.find(v => /hi-IN|en-IN/i.test(v.lang))
          || voices.find(v => /hi|en/i.test(v.lang));
        if (preferred) utterance.voice = preferred;
        utterance.onstart = () => status.textContent = 'Speaking…';
        utterance.onend = () => status.textContent = 'Finished';
        utterance.onerror = () => status.textContent = 'Voice playback failed';
        window.speechSynthesis.speak(utterance);
      }};

      stopBtn.onclick = () => {{
        if ('speechSynthesis' in window) window.speechSynthesis.cancel();
        status.textContent = 'Stopped';
      }};
    }})();
    </script>
    """, height=54)


# ---------------- AI PROVIDERS ----------------

def groq_request(messages):
    if not GROQ_KEY:
        raise RuntimeError("Groq API key is missing.")

    response = requests.post(
        "https://api.groq.com/openai/v1/chat/completions",
        headers={
            "Authorization": f"Bearer {GROQ_KEY}",
            "Content-Type": "application/json"
        },
        json={
            "model": GROQ_MODEL,
            "messages": [
                {"role": "system", "content": SYSTEM_PROMPT},
                *messages
            ],
            "temperature": 0.6,
            "max_completion_tokens": 4096
        },
        timeout=60
    )
    response.raise_for_status()
    return response.json()["choices"][0]["message"]["content"]


def gemini_request(messages):
    if not GEMINI_KEY:
        raise RuntimeError("Gemini API key is missing.")

    contents = []
    for msg in messages:
        contents.append({
            "role": "model" if msg["role"] == "assistant" else "user",
            "parts": [{"text": msg["content"]}]
        })

    url = (
        "https://generativelanguage.googleapis.com/v1beta/models/"
        + GEMINI_MODEL
        + ":generateContent?key="
        + GEMINI_KEY
    )

    response = requests.post(
        url,
        json={
            "system_instruction": {
                "parts": [{"text": SYSTEM_PROMPT}]
            },
            "contents": contents,
            "generationConfig": {
                "temperature": 0.6,
                "maxOutputTokens": 4096
            }
        },
        timeout=60
    )
    response.raise_for_status()
    return response.json()["candidates"][0]["content"]["parts"][0]["text"]


def openai_request(messages):
    if not OPENAI_KEY:
        raise RuntimeError("OpenAI API key is missing.")

    response = requests.post(
        "https://api.openai.com/v1/chat/completions",
        headers={
            "Authorization": f"Bearer {OPENAI_KEY}",
            "Content-Type": "application/json"
        },
        json={
            "model": OPENAI_MODEL,
            "messages": [
                {"role": "system", "content": SYSTEM_PROMPT},
                *messages
            ],
            "temperature": 0.6
        },
        timeout=60
    )
    response.raise_for_status()
    return response.json()["choices"][0]["message"]["content"]


def claude_request(messages):
    if not ANTHROPIC_KEY:
        raise RuntimeError("Claude API key is missing.")

    response = requests.post(
        "https://api.anthropic.com/v1/messages",
        headers={
            "x-api-key": ANTHROPIC_KEY,
            "anthropic-version": "2023-06-01",
            "content-type": "application/json"
        },
        json={
            "model": CLAUDE_MODEL,
            "max_tokens": 4096,
            "system": SYSTEM_PROMPT,
            "messages": messages
        },
        timeout=60
    )
    response.raise_for_status()
    data = response.json()
    return "".join(
        part.get("text", "")
        for part in data.get("content", [])
        if part.get("type") == "text"
    )


def ask_ai(messages):
    providers = [
        ("Groq", groq_request),
        ("Gemini", gemini_request),
        ("OpenAI", openai_request),
        ("Claude", claude_request)
    ]

    errors = []

    for name, function in providers:
        try:
            answer = function(messages)
            if answer and answer.strip():
                return answer, name
            errors.append(name + ": empty response")
        except Exception as exc:
            errors.append(name + ": " + str(exc)[:220])

    raise RuntimeError(
        "All configured AI providers failed:\n\n" + "\n".join(errors)
    )


# ---------------- SMART WEB SEARCH ----------------

def tavily_search(query, max_results=5):
    if not TAVILY_KEY:
        raise RuntimeError("TAVILY_API_KEY is missing in Streamlit Secrets.")

    response = requests.post(
        "https://api.tavily.com/search",
        headers={
            "Authorization": f"Bearer {TAVILY_KEY}",
            "Content-Type": "application/json"
        },
        json={
            "query": query,
            "search_depth": "basic",
            "max_results": max_results,
            "include_answer": False
        },
        timeout=25
    )

    response.raise_for_status()
    data = response.json()

    results = []

    for item in data.get("results", []):
        title = item.get("title", "").strip()
        url = item.get("url", "").strip()
        content = item.get("content", "").strip()

        if title and url.startswith("http"):
            results.append({
                "title": title,
                "url": url,
                "content": content
            })

    if not results:
        raise RuntimeError("Tavily returned no search results.")

    return results


def cloudflare_search(query, max_results=5):
    if not CF_ACCOUNT or not CF_TOKEN:
        raise RuntimeError("Cloudflare account ID or API token is missing.")

    response = requests.post(
        f"https://api.cloudflare.com/client/v4/accounts/{CF_ACCOUNT}/ai/websearch/",
        headers={
            "Authorization": f"Bearer {CF_TOKEN}",
            "Content-Type": "application/json"
        },
        json={
            "query": query[:1024],
            "provider": "exa",
            "limit": min(max_results, 10),
            "options": {
                "gateway": {
                    "id": "default"
                }
            }
        },
        timeout=25
    )

    response.raise_for_status()
    data = response.json()

    results = []

    for item in data.get("items", []):
        title = item.get("title", "").strip()
        url = item.get("url", "").strip()
        content = item.get("description", "").strip()

        if title and url.startswith("http"):
            results.append({
                "title": title,
                "url": url,
                "content": content
            })

    if not results:
        raise RuntimeError("Cloudflare returned no search results.")

    return results


def smart_web_search(query, max_results=5):
    errors = []

    # First choice: Tavily
    if TAVILY_KEY:
        try:
            return tavily_search(query, max_results)
        except Exception as exc:
            errors.append("Tavily: " + str(exc)[:180])

    # Fallback: Cloudflare Web Search
    if CF_ACCOUNT and CF_TOKEN:
        try:
            return cloudflare_search(query, max_results)
        except Exception as exc:
            errors.append("Cloudflare: " + str(exc)[:180])

    if not errors:
        raise RuntimeError(
            "No search API is configured. Check Tavily and Cloudflare Secrets."
        )

    raise RuntimeError("All web search providers failed:\n" + "\n".join(errors))


def needs_web_search(text):
    q = (text or "").lower()

    terms = (
        "search the web", "search online", "google it", "look it up",
        "web search", "website search", "online search",
        "सर्च करो", "इंटरनेट पर खोज", "वेबसाइट पर खोज",
        "वेब पर खोज", "latest", "today", "current", "right now",
        "this week", "2026", "news", "recent", "price today",
        "live score", "release date", "new update", "updated version",
        "अभी का", "आज का", "ताज़ा", "लेटेस्ट", "वर्तमान",
        "न्यूज़", "कीमत आज", "अभी कौन"
    )

    return any(term in q for term in terms)


def ai_should_search_web(user_text):
    """Ask the configured AI model whether this particular question needs live web data."""
    prompt = f"""
You are the web-search decision module for NEXTGEN AI.

Decide whether answering the user's question accurately requires fresh,
current, changing, local, or externally verifiable information from the internet.

Return ONLY one JSON object, with no markdown:
{{"search": true}}
or
{{"search": false}}

Choose true when the user asks for current/latest/today information, news,
recent events or releases, live prices or scores, current opening hours,
current policies, current versions, current availability, or facts likely
to have changed since the model's training data. Also choose true when the
user explicitly asks you to search, look something up, verify a claim, or
provide sources.

Choose false for stable general knowledge, ordinary explanations, maths,
schoolwork that does not need current facts, translation, creative writing,
and tasks based entirely on text or files the user supplied.

If uncertain whether facts may have changed, choose true.

USER QUESTION:
{user_text}
"""
    try:
        decision, _ = ask_ai([
            {"role": "user", "content": prompt}
        ])
        match = re.search(r"\{[\s\S]*?\}", decision)
        if match:
            parsed = json.loads(match.group(0))
            if isinstance(parsed.get("search"), bool):
                return parsed["search"]
    except Exception:
        pass

    # Fallback if the classifier cannot return valid JSON.
    return needs_web_search(user_text)


def format_search_context(results):
    lines = [
        "WEB SEARCH RESULTS. Use these sources to answer accurately. "
        "Do not invent facts."
    ]

    for i, item in enumerate(results, 1):
        lines.append(
            f"[{i}] {item['title']}\n"
            f"URL: {item['url']}\n"
            f"Information: {item.get('content', '')}"
        )

    lines.append(
        "Use relevant source URLs when answering. "
        "Say clearly if the search results are insufficient."
    )

    return "\n\n".join(lines)

# ---------------- PUBLIC MARKET CHART DATA ----------------

def fetch_public_market_history(symbol, period="1mo", interval="1d"):
    """Fetch chart history from Yahoo Finance's public chart endpoint.
    This endpoint is unofficial and may rate-limit or change without notice.
    """
    clean_symbol = symbol.strip().upper()
    if not clean_symbol:
        raise ValueError("Enter a ticker symbol.")
    url = "https://query1.finance.yahoo.com/v8/finance/chart/" + requests.utils.quote(clean_symbol)
    response = requests.get(
        url,
        params={"range": period, "interval": interval, "events": "history"},
        headers={"User-Agent": "Mozilla/5.0"},
        timeout=20
    )
    response.raise_for_status()
    payload = response.json().get("chart", {})
    if payload.get("error"):
        raise RuntimeError(str(payload["error"]))
    result = (payload.get("result") or [None])[0]
    if not result:
        raise RuntimeError("No market history returned for this ticker.")
    timestamps = result.get("timestamp") or []
    quote = (result.get("indicators", {}).get("quote") or [{}])[0]
    closes = quote.get("close") or []
    points = []
    for stamp, close in zip(timestamps, closes):
        if close is not None:
            points.append((datetime.fromtimestamp(stamp).strftime("%Y-%m-%d"), float(close)))
    if len(points) < 2:
        raise RuntimeError("Not enough chart data returned for this ticker.")
    return points, result.get("meta", {})


# ---------------- IMAGE GENERATION ----------------

def cloudflare_image(prompt):
    if not CF_ACCOUNT or not CF_TOKEN:
        raise RuntimeError("Cloudflare credentials are missing.")

    url = (
        "https://api.cloudflare.com/client/v4/accounts/"
        + CF_ACCOUNT
        + "/ai/run/"
        + IMAGE_MODEL
    )

    response = requests.post(
        url,
        headers={
            "Authorization": f"Bearer {CF_TOKEN}",
            "Content-Type": "application/json"
        },
        json={"prompt": prompt, "steps": 4},
        timeout=150
    )
    response.raise_for_status()

    data = response.json()
    image_data = data.get("result", {}).get("image")

    if not image_data:
        raise RuntimeError(str(data))

    return base64.b64decode(image_data)


# ---------------- VOICE TRANSCRIPTION ----------------

def transcribe_audio(audio_file):
    if not GROQ_KEY:
        raise RuntimeError("Groq key is missing.")

    response = requests.post(
        "https://api.groq.com/openai/v1/audio/transcriptions",
        headers={"Authorization": f"Bearer {GROQ_KEY}"},
        files={
            "file": (
                audio_file.name,
                audio_file.getvalue(),
                audio_file.type or "audio/wav"
            )
        },
        data={"model": "whisper-large-v3-turbo"},
        timeout=90
    )
    response.raise_for_status()
    return response.json().get("text", "")


# ---------------- TOOL LIBRARY ----------------

TOOL_LIBRARY = {
    "Study & Education": [
        "Topic Explainer", "Explain Like I'm 12", "Chapter Summary",
        "Short Notes Maker", "Detailed Notes Maker", "MCQ Generator",
        "Quiz Generator", "Flashcard Creator", "Worksheet Maker",
        "Study Timetable", "Study Planner", "Maths Step Solver",
        "Science Explainer", "Physics Numericals Coach",
        "Chemistry Helper", "Biology Explainer", "History Notes",
        "Geography Explainer", "Civics Explainer", "Grammar Tutor",
        "Vocabulary Builder", "Exam Revision Sheet",
        "Practice Test Maker", "Textbook Answer Helper",
        "Olympiad Practice", "Foundation Question Maker",
        "Formula Sheet Creator", "Weak Topic Finder"
    ],
    "Coding School": [
        "Python Beginner Course", "Python Practice Questions",
        "Python Code Helper", "HTML Beginner Course",
        "HTML Page Builder", "CSS Beginner Course",
        "CSS Designer", "JavaScript Beginner Course",
        "JavaScript Practice", "Code Explainer", "Code Debugger",
        "Code Reviewer", "SQL Beginner Course", "SQL Query Writer",
        "Git and GitHub Tutor", "API Learning Coach",
        "JSON Helper", "Regex Tutor", "React Beginner Course",
        "Flask Learning Guide", "Django Learning Guide",
        "Streamlit App Builder", "Streamlit Error Fixer",
        "Website Project Mentor", "App Development Roadmap",
        "Database Design Tutor", "Programming Quiz",
        "Algorithm Explainer", "Data Structures Tutor",
        "Computer Science Basics", "Coding Challenge Generator",
        "Project-Based Learning", "Code Documentation Maker"
    ],
    "Writing & Documents": [
        "Email Writer", "Formal Letter Writer", "Essay Writer",
        "Application Writer", "Notice Writer", "Speech Writer",
        "Story Writer", "Article Writer", "Report Writer",
        "Resume Builder", "Cover Letter Writer", "Blog Writer",
        "Social Media Caption", "YouTube Description",
        "Advertisement Copy", "Product Description",
        "Invitation Writer", "Complaint Letter", "Apology Letter",
        "Newsletter Writer", "Meeting Agenda", "Proposal Writer",
        "Biography Writer", "Debate Speech Writer", "Book Summary"
    ],
    "YouTube & Creator": [
        "YouTube Video Ideas", "YouTube Shorts Ideas", "Reel Ideas",
        "Video Script Writer", "Shorts Script Writer",
        "Thumbnail Concept", "Thumbnail Text Ideas",
        "Image Prompt Generator", "AI Video Prompt Generator",
        "Scene-by-Scene Planner", "Voiceover Script",
        "Character Creator", "Story Plot Generator",
        "Hook Generator", "Video Title Generator",
        "Hashtag Generator", "Channel Bio Writer",
        "Content Calendar", "Video SEO Helper",
        "Faceless Video Planner", "Animal Story Generator",
        "Cinematic Video Script", "AI Animation Story Planner"
    ],
    "Business & Marketing": [
        "Business Idea Generator", "Business Plan Writer",
        "Brand Name Maker", "Slogan Generator", "Marketing Strategy",
        "Customer Reply Writer", "Product Launch Planner",
        "Sales Pitch Writer", "Competitor Analysis Framework",
        "Target Audience Planner", "SWOT Analysis",
        "Startup Roadmap", "Shop Advertisement Script",
        "Local Business Promotion Planner", "Poster Copy Writer",
        "Small Shop Branding Assistant", "Business Growth Ideas"
    ],
    "Language & Translation": [
        "Hindi to English", "English to Hindi", "English Simplifier",
        "Hindi Proofreader", "English Proofreader",
        "Grammar Correction", "Text Rewriter",
        "Professional Tone Converter", "Text Summarizer",
        "Vocabulary Practice", "English Speaking Practice",
        "Daily English Vocabulary", "Tense Practice Generator",
        "Active Passive Voice Tutor", "Synonyms and Antonyms"
    ],
    "Productivity & Planning": [
        "Daily Planner", "Weekly Planner", "Monthly Goal Planner",
        "To-Do List Maker", "Checklist Generator", "Decision Helper",
        "Brainstorming Assistant", "Goal Breakdown", "Routine Planner",
        "Time Management Plan", "Project Planner", "Task Prioritizer",
        "Revision Schedule", "Problem Solving Framework"
    ],
    "Creative & Design": [
        "Logo Concept Generator", "Poster Design Brief",
        "Rangoli Design Ideas", "Greeting Card Message",
        "Color Palette Suggestions", "Infographic Outline",
        "Mascot Character Concept", "Brand Identity Brief",
        "Photo Editing Prompt", "AI Art Style Prompt",
        "Storyboard Creator", "YouTube Banner Concept"
    ],
    "Maths & Science Lab": [
        "Algebra Tutor", "Geometry Tutor", "Mensuration Helper",
        "Percentage Calculator Explainer", "Ratio Proportion Tutor",
        "Speed Distance Time Solver", "Unit Conversion Explainer",
        "Electricity Concept Tutor", "Ohms Law Practice",
        "Motion Concept Explainer", "Force and Pressure Tutor",
        "Chemistry Equation Explainer", "Periodic Table Tutor",
        "Scientific Experiment Planner", "Light and Sound Explainer"
    ],
    "Research & Analysis": [
        "Research Topic Planner", "Research Question Generator",
        "Argument Builder", "Critical Thinking Coach",
        "Fact Check Checklist", "Source Evaluation Helper",
        "Compare Two Topics", "Problem Analysis",
        "Root Cause Analysis", "Decision Matrix",
        "Case Study Explainer", "Logical Reasoning Coach",
        "Data Explanation", "CSV Analysis Plan", "Chart Recommendation"
    ]
}

BASE_TOOL_COUNT = sum(len(v) for v in TOOL_LIBRARY.values())
TOOL_OUTPUT_FORMATS = [
    "Quick answer", "Step-by-step guide", "Detailed report", "Checklist",
    "Table", "Study notes", "Presentation outline", "Practice exercise"
]
TOOL_LEVELS = [
    "Beginner", "School level", "Intermediate", "Advanced",
    "Professional", "Expert", "Research level"
]
# Each preset can run in 8 output formats and 7 learning/detail levels.
# These are configurable workflows, not 11,000 separately trained AI models.
TOOL_COUNT = BASE_TOOL_COUNT * len(TOOL_OUTPUT_FORMATS) * len(TOOL_LEVELS)


def run_tool(tool_name, details):
    prompt = f"""
You are running the NEXTGEN AI tool: {tool_name}.

Complete the user's task, not merely explain how to do it.
Give a useful, accurate and well-organized result.
Use the user's language.
For coding lessons, teach step by step with beginner-friendly examples.
For school topics, use an appropriate student-friendly level.

USER REQUEST:
{details}
"""
    return ask_ai([{"role": "user", "content": prompt}])


# ---------------- SESSION STATE ----------------

defaults = {
    "page": "Dashboard",
    "chat_id": None,
    "messages": [],
    "last_provider": "Automatic",
    "tool_result": None,
    "selected_tool": None,
    "last_user_prompt": "",
    "website_result": "",
    "website_provider": "",
    "app_builder_result": "",
    "app_builder_provider": "",
    "quick_prompt": None,
    "workspace_theme": "Midnight Dark",
    "chat_response_mode": "Balanced",
    "chat_output_format": "Automatic"
}

for key, value in defaults.items():
    if key not in st.session_state:
        st.session_state[key] = value

THEME_PRESETS = {
    "Midnight Dark": {"font": "Inter", "foreground": "#f6f6ff", "background": "#080c18", "sidebar": "#0a1020"},
    "Neon Cyber": {"font": "Space Grotesk", "foreground": "#ffffff", "background": "#070b18", "sidebar": "#090f24"},
    "Soft Focus": {"font": "Poppins", "foreground": "#f8f7ff", "background": "#111022", "sidebar": "#17152b"},
    "Warm Studio": {"font": "Lora", "foreground": "#fffaf2", "background": "#211a18", "sidebar": "#2a211e"},
    "Light Mode": {"font": "Nunito Sans", "foreground": "#172033", "background": "#f4f6fb", "sidebar": "#e8edf6"}
}


# ---------------- LOGIN / SIGN UP SCREEN ----------------

if st.session_state.user is None:

    hero(
        "Welcome to NEXTGEN AI",
        "Your personal AI workspace. Sign in, create a free account, or continue as a guest."
    )

    st.markdown("""
    <style>
    .auth-wrap {max-width:760px;margin:0 auto 18px auto;padding:22px 24px;
      border:1px solid #39486d;border-radius:20px;
      background:linear-gradient(135deg,#172541,#171a36);}
    .auth-heading {font-size:24px;font-weight:900;color:#fff;margin-bottom:5px;}
    .auth-sub {font-size:13px;color:#aebbd7;margin-bottom:12px;}
    .auth-pill {display:inline-block;padding:6px 11px;border-radius:20px;
      background:#30295a;color:#d8d0ff;font-size:11px;font-weight:800;
      letter-spacing:.5px;margin-bottom:10px;}
    </style>
    <div class="auth-wrap">
      <div class="auth-pill">✦ YOUR AI WORKSPACE</div>
      <div class="auth-heading">Get started with NEXTGEN AI</div>
      <div class="auth-sub">Create an account to keep your chats, or enter instantly as a guest.</div>
    </div>
    """, unsafe_allow_html=True)

    login_tab, signup_tab, guest_tab = st.tabs([
        "🔐 Login", "✨ Create Account", "🚀 Continue as Guest"
    ])

    with login_tab:
        st.markdown("### Welcome back")
        st.caption("Log in to continue with your saved conversations.")
        with st.form("login_form", clear_on_submit=False):
            email = st.text_input("Email address", placeholder="you@example.com")
            password = st.text_input("Password", type="password", placeholder="Enter your password")
            login_submit = st.form_submit_button(
                "Login to NEXTGEN AI", use_container_width=True
            )

        if login_submit:
            if not email.strip() or not password:
                st.error("Please enter both email and password.")
            else:
                user = login_user(email, password)
                if user:
                    user["is_guest"] = False
                    st.session_state.user = user
                    st.session_state.chat_id = create_chat(user["id"])
                    st.session_state.messages = []
                    st.session_state.page = "Dashboard"
                    st.rerun()
                else:
                    st.error("Email or password is incorrect. Please try again.")

    with signup_tab:
        st.markdown("### Create your free account")
        st.caption("After successful sign up, you will be taken directly into the app — no second login required.")
        with st.form("signup_form", clear_on_submit=False):
            username = st.text_input("Your name / username", placeholder="At least 3 characters")
            new_email = st.text_input("Email address", placeholder="you@example.com")
            new_password = st.text_input("Create password", type="password", placeholder="At least 8 characters")
            confirm_password = st.text_input("Confirm password", type="password", placeholder="Re-enter your password")
            st.caption("Use at least 8 characters. A mix of letters and numbers is recommended.")
            signup_submit = st.form_submit_button(
                "Create Account & Enter NEXTGEN AI →", use_container_width=True
            )

        if signup_submit:
            clean_name = username.strip()
            clean_email = new_email.strip().lower()
            if len(clean_name) < 3:
                st.error("Name / username must contain at least 3 characters.")
            elif len(clean_name) > 32:
                st.error("Name / username must be 32 characters or fewer.")
            elif not re.fullmatch(r"[^\s@]+@[^\s@]+\.[^\s@]+", clean_email):
                st.error("Please enter a valid email address.")
            elif len(new_password) < 8:
                st.error("Password must contain at least 8 characters.")
            elif new_password != confirm_password:
                st.error("The two passwords do not match.")
            else:
                ok, message = register_user(clean_name, clean_email, new_password)
                if ok:
                    # Automatically sign the newly created user in.
                    new_user = login_user(clean_email, new_password)
                    if new_user:
                        new_user["is_guest"] = False
                        st.session_state.user = new_user
                        st.session_state.chat_id = create_chat(new_user["id"])
                        st.session_state.messages = []
                        st.session_state.page = "Dashboard"
                        st.success("Account created! Opening your workspace…")
                        st.rerun()
                    else:
                        st.error("Account created, but automatic sign-in failed. Please use Login.")
                else:
                    st.error(message)

    with guest_tab:
        st.markdown("### Try NEXTGEN AI instantly")
        st.write("No email or password required. You can explore the available tools and chat features as a guest.")
        st.info("Guest conversations are kept separate from registered accounts. They may not be available after your browser session or app storage is reset.")
        if st.button("🚀 Continue as Guest", key="continue_guest", use_container_width=True):
            # Negative unique ID keeps guest chats isolated from registered user IDs.
            guest_id = -(uuid.uuid4().int % 900000000000000000 + 1)
            st.session_state.user = {
                "id": guest_id,
                "username": "Guest",
                "is_guest": True
            }
            st.session_state.chat_id = create_chat(guest_id)
            st.session_state.messages = []
            st.session_state.page = "Dashboard"
            st.rerun()

    st.stop()


# ---------------- ENSURE CURRENT CHAT ----------------

USER_ID = st.session_state.user["id"]

if st.session_state.chat_id is None:
    st.session_state.chat_id = create_chat(USER_ID)

if not st.session_state.messages:
    st.session_state.messages = get_messages(
        st.session_state.chat_id,
        USER_ID
    )


# ---------------- SIDEBAR ----------------

with st.sidebar:

    st.markdown(
        '<div class="brand">✦ NEXTGEN<span> AI</span></div>',
        unsafe_allow_html=True
    )

    st.markdown(
        '<div class="sidebar-tag">YOUR AI WORKSPACE</div>',
        unsafe_allow_html=True
    )

    if st.session_state.user.get("is_guest", False):
        st.caption("Browsing as Guest · Chats are separate from registered accounts")
    else:
        st.caption("Signed in as " + st.session_state.user["username"])

    if st.button("＋   New Chat", use_container_width=True):
        st.session_state.chat_id = create_chat(USER_ID)
        st.session_state.messages = []
        st.session_state.page = "AI Chat"
        st.rerun()

    st.markdown("---")
    st.caption("ALL WORKSPACE FEATURES")

    navigation = [
        ("⌂", "Dashboard"),
        ("✦", "AI Chat"),
        ("▧", "AI Image Studio"),
        ("⌕", "Tool Center"),
        ("▥", "Stock Market & Trading Hub"),
        ("▤", "PDF Assistant"),
        ("◈", "Website Builder"),
        ("▣", "App Builder"),
        ("◉", "Live Voice"),
        ("◷", "Chat History"),
        ("✧", "My Creations"),
        ("⚙", "Settings"),
        ("ⓘ", "About")
    ]

    for icon_text, name in navigation:
        is_active = st.session_state.page == name
        if st.button(
            f"{icon_text}   {name}" + ("   •" if is_active else ""),
            key=f"nav_{name}",
            use_container_width=True
        ):
            st.session_state.page = name
            st.rerun()

    st.markdown("---")
    st.caption("WORKSPACE MOOD & FONT")
    selected_theme = st.selectbox(
        "Choose visual mood",
        list(THEME_PRESETS.keys()),
        key="workspace_theme"
    )

    st.markdown("---")
    st.caption("RECENT CONVERSATIONS")

    for chat in all_chats(USER_ID)[:7]:
        if st.button(
            "•  " + (chat[1] or "New Chat")[:25],
            key=f"recent_{chat[0]}",
            use_container_width=True
        ):
            st.session_state.chat_id = chat[0]
            st.session_state.messages = get_messages(
                chat[0], USER_ID
            )
            st.session_state.page = "AI Chat"
            st.rerun()

    st.markdown("---")

    if st.session_state.user.get("is_guest", False):
        if st.button("Exit Guest Mode", use_container_width=True):
            st.session_state.user = None
            st.session_state.chat_id = None
            st.session_state.messages = []
            st.session_state.page = "Dashboard"
            st.rerun()
    else:
        if st.button("Log Out", use_container_width=True):
            st.session_state.user = None
            st.session_state.chat_id = None
            st.session_state.messages = []
            st.session_state.page = "Dashboard"
            st.rerun()

    st.markdown(
        '<div class="small-muted">NEXTGEN AI V10<br>'
        'Created by Arav</div>',
        unsafe_allow_html=True
    )

_theme = THEME_PRESETS.get(st.session_state.workspace_theme, THEME_PRESETS["Midnight Dark"])
_theme_font = _theme["font"]
_theme_fg = _theme["foreground"]
_theme_bg = _theme["background"]
_theme_sidebar = _theme["sidebar"]
_theme_app_background = (
    "radial-gradient(ellipse at 12% 0%,#28235a 0%,transparent 35%), radial-gradient(ellipse at 95% 5%,#172e50 0%,transparent 35%), #080c18"
    if st.session_state.workspace_theme == "Midnight Dark" else _theme_bg
)
_theme_surface_override = (
    ".panel, .metric, .dash-feature, .tool-stat { background:#ffffff !important; border-color:#d8deea !important; }"
    if st.session_state.workspace_theme == "Light Mode" else ""
)
_theme_hero_background = "#ffffff" if st.session_state.workspace_theme == "Light Mode" else "linear-gradient(115deg,#171e3e,#30265d 55%,#183451)"
st.markdown(f"""
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800;900&family=Space+Grotesk:wght@400;500;600;700&family=Poppins:wght@400;500;600;700;800&family=Lora:wght@400;500;600;700&family=Nunito+Sans:wght@400;500;600;700;800;900&display=swap');
.stApp, .stApp p, .stApp span, .stApp label, .stApp li, .stApp div,
.stApp h1, .stApp h2, .stApp h3, .stApp h4, .stApp h5, .stApp h6,
.stApp input, .stApp textarea, .stApp button, .stApp select,
[data-testid="stMarkdownContainer"], [data-testid="stChatMessage"] {{
  font-family: '{_theme_font}', sans-serif !important;
}}
.stApp {{ color: {_theme_fg} !important; background: {_theme_app_background} !important; }}
.hero {{ background: {_theme_hero_background} !important; }}
{_theme_surface_override}
.hero-title, .panel-title, .dash-feature h3, .metric-value {{ color: {_theme_fg} !important; }}
.hero-label {{ color: {_theme_fg} !important; }}
.hero-sub, .panel-desc, .small-muted, .metric-label, .dash-feature p {{ color: {_theme_fg} !important; }}
[data-testid="stTextInput"] input, [data-testid="stTextArea"] textarea {{
  background: {'#ffffff' if st.session_state.workspace_theme == 'Light Mode' else '#111a2d'} !important;
  color: {_theme_fg} !important;
}}
.stApp p, .stApp li, .stApp label, .stApp [data-testid="stMarkdownContainer"] {{ color: {_theme_fg}; }}
[data-testid="stSidebar"] {{ background: { _theme_sidebar } !important; }}
[data-testid="stSidebar"] * {{ font-family: '{_theme_font}', sans-serif !important; }}
[data-testid="stChatMessage"] {{ color: {_theme_fg} !important; }}
[data-testid="stChatMessage"] p, [data-testid="stChatMessage"] li {{ color: {_theme_fg} !important; }}
</style>
""", unsafe_allow_html=True)

page = st.session_state.page


# ============================================================
# DASHBOARD
# ============================================================

if page == "Dashboard":

    hero(
        "Your Ideas. Your Intelligence.",
        "One creative workspace for learning, writing, building and exploring."
    )

    st.markdown(
        f'<div class="tool-stat">'
        f'<span class="dash-kicker">YOUR AI TOOLBOX</span>'
        f'<h2 style="margin:5px 0 2px;color:white;font-size:30px;">'
        f'{TOOL_COUNT:,} AI tool workflows</h2>'
        f'<div class="small-muted">Study, coding, writing, creator workflows and more.</div>'
        f'</div>',
        unsafe_allow_html=True
    )

    a, b, c, d = st.columns(4)

    with a:
        metric("AI EXPERIENCE", "SMART", "One workspace for many tasks")

    with b:
        metric("AI TOOLBOX", "10,000+", "Configurable AI workflows")

    with c:
        metric("BUILD", "WEBSITES", "Create responsive web pages")

    with d:
        metric("BUILD", "APPS", "Generate application starter code")

    st.markdown("## Explore your workspace")

    left, right = st.columns(2, gap="large")

    with left:
        st.markdown("""
        <div class="dash-feature">
        <div class="dash-kicker">CONVERSATION</div>
        <h3>✦ AI Chat</h3>
        <p>Chat with your AI assistant and use response actions.</p>
        </div>
        """, unsafe_allow_html=True)

        if st.button("Open AI Chat", key="dash_chat", use_container_width=True):
            st.session_state.page = "AI Chat"
            st.rerun()

        st.markdown("""
        <div class="dash-feature">
        <div class="dash-kicker">CREATION</div>
        <h3>▧ AI Image Studio</h3>
        <p>Create images using Cloudflare FLUX.</p>
        </div>
        """, unsafe_allow_html=True)

        if st.button("Open Image Studio", key="dash_image", use_container_width=True):
            st.session_state.page = "AI Image Studio"
            st.rerun()

        st.markdown("""
        <div class="dash-feature">
        <div class="dash-kicker">FINANCE LEARNING</div>
        <h3>▥ Stock Market & Trading Hub</h3>
        <p>Learn the stock market and trading, analyse charts and practise with a virtual portfolio.</p>
        </div>
        """, unsafe_allow_html=True)
        if st.button("Open Stock Market & Trading Hub", key="dash_stock", use_container_width=True):
            st.session_state.page = "Stock Market & Trading Hub"
            st.rerun()

    with right:
        st.markdown("""
        <div class="dash-feature">
        <div class="dash-kicker">LEARNING</div>
        <h3>⌕ Coding School & AI Tools</h3>
        <p>Learn Python, HTML, CSS, JavaScript and more.</p>
        </div>
        """, unsafe_allow_html=True)

        if st.button("Explore AI Tools", key="dash_tools", use_container_width=True):
            st.session_state.page = "Tool Center"
            st.rerun()

        st.markdown("""
        <div class="dash-feature">
        <div class="dash-kicker">DOCUMENTS</div>
        <h3>▤ PDF Assistant</h3>
        <p>Upload a PDF and ask questions about it.</p>
        </div>
        """, unsafe_allow_html=True)

        if st.button("Open PDF Assistant", key="dash_pdf", use_container_width=True):
            st.session_state.page = "PDF Assistant"
            st.rerun()

    builder_left, builder_right = st.columns(2, gap="large")
    with builder_left:
        st.markdown('<div class="dash-feature"><div class="dash-kicker">BUILD</div><h3>◈ Website Builder</h3><p>Generate responsive websites and downloadable HTML files.</p></div>', unsafe_allow_html=True)
        if st.button("Open Website Builder", key="dash_website", use_container_width=True):
            st.session_state.page = "Website Builder"
            st.rerun()
    with builder_right:
        st.markdown('<div class="dash-feature"><div class="dash-kicker">DEVELOP</div><h3>⌘ App Builder</h3><p>Generate application starter code and project files.</p></div>', unsafe_allow_html=True)
        if st.button("Open App Builder", key="dash_appbuilder", use_container_width=True):
            st.session_state.page = "App Builder"
            st.rerun()

    st.markdown("## Built for your workflow")

    st.markdown("""
    - **AI Chat:** An assistant experience with automatic service fallback.
    - **AI Tool Center:** 10,000+ configurable workflows generated from task presets, output formats and learning levels.
    - **Stock Market & Trading Hub:** Beginner lessons, uploaded-data chart analysis, company research checklists and paper-portfolio calculations.
    - **Coding School:** Beginner-friendly coding lessons.
    - **AI Image Studio:** Create images from text prompts.
    - **PDF Assistant:** Document question answering.
    - **Website Builder:** Prompt-based responsive website generation.
    - **App Builder:** Prompt-based application starter code.
    - **Smart Web Search:** Automatically searches when a question needs fresh online information.
    - **Chat History:** Saved conversations linked to your account.
    """)


# =====================================================
# AI CHAT - ORIGINAL DESIGN PRESERVED
# =====================================================

elif page == "AI Chat":

    st.markdown("## ✦ AI Chat")
    st.caption("Ask anything. Your assistant is ready.")

    mode_col, format_col = st.columns(2)
    with mode_col:
        response_mode = st.selectbox(
            "Response mode",
            ["Balanced", "Deep analysis", "Step-by-step tutor", "Concise answer", "Creative mode"],
            key="chat_response_mode"
        )
    with format_col:
        output_format = st.selectbox(
            "Answer format",
            ["Automatic", "Structured bullets", "Table", "Checklist", "Examples first"],
            key="chat_output_format"
        )

    followup_actions = [
        ("Explain more", "Explain your previous answer in more detail with simple examples."),
        ("Summarize", "Summarize your previous answer into the most important points."),
        ("Give examples", "Give practical examples for your previous answer."),
        ("Make a plan", "Turn your previous answer into a clear step-by-step action plan."),
        ("Quiz me", "Create a short quiz based on your previous answer and ask one question at a time.")
    ]

    for message_index, (role, content) in enumerate(st.session_state.messages):
        with st.chat_message(role):
            st.markdown(content)
            if role == "assistant":
                render_answer_controls(content, f"chat_{message_index}")

        if role == "assistant":
            action_cols = st.columns(5)
            for action_index, (action_label, action_prompt) in enumerate(followup_actions):
                with action_cols[action_index]:
                    if st.button(action_label, key=f"answer_action_{message_index}_{action_index}", use_container_width=True):
                        st.session_state.quick_prompt = action_prompt
                        st.rerun()

    with st.container(border=True):

        live_col, input_col = st.columns(
            [1.0, 8.5],
            vertical_alignment="center"
        )

        with live_col:

            if CF_LIVE_URL:
                st.link_button(
                    "◉ Live",
                    CF_LIVE_URL,
                    use_container_width=True
                )
            else:
                st.button(
                    "◉ Live",
                    disabled=True,
                    help="Add CLOUDFLARE_VOICE_URL in Streamlit Secrets.",
                    use_container_width=True
                )

        with input_col:

            submitted = st.chat_input(
                "Message NEXTGEN AI...",
                key="nextgen_chat_input",
                accept_file=True,
                accept_audio=True,
                file_type=["pdf", "txt", "png", "jpg", "jpeg"],
                max_upload_size=20
            )

    quick_prompt = st.session_state.pop("quick_prompt", None)
    if submitted is not None or quick_prompt:

        user_text = (submitted.text or "") if submitted is not None else quick_prompt
        file_context = ""

        attached_files = submitted.files if submitted is not None else []
        for uploaded in (attached_files or []):

            filename = uploaded.name.lower()

            if filename.endswith(".txt"):

                file_context += "\n\n[Attached text]\n"
                file_context += uploaded.getvalue().decode(
                    "utf-8", errors="ignore"
                )[:20000]

            elif filename.endswith(".pdf"):

                try:
                    from pypdf import PdfReader

                    reader = PdfReader(io.BytesIO(uploaded.getvalue()))

                    extracted = "\n".join(
                        p.extract_text() or ""
                        for p in reader.pages
                    )

                    file_context += "\n\n[Attached PDF]\n"
                    file_context += extracted[:25000]

                except Exception as e:
                    st.warning(f"Could not read {uploaded.name}: {e}")

            elif filename.endswith((".png", ".jpg", ".jpeg")):

                st.info(
                    f"{uploaded.name} attached. Image understanding "
                    "is not enabled in this text-chat build."
                )

        if submitted is not None and submitted.audio is not None:

            with st.spinner("Converting your voice to text..."):

                try:
                    voice_text = transcribe_audio(submitted.audio)
                    user_text = (user_text + "\n" + voice_text).strip()

                except Exception as e:
                    st.error(f"Voice transcription failed: {e}")

        user_text = (user_text + file_context).strip()

        if user_text:

            st.session_state.messages.append(("user", user_text))

            save_message(
                st.session_state.chat_id,
                USER_ID,
                "user",
                user_text
            )

            if len(st.session_state.messages) == 1:
                set_chat_title(st.session_state.chat_id, USER_ID, user_text[:48])

            api_messages = [
                {"role": role, "content": content}
                for role, content in st.session_state.messages[-20:]
            ]
            if api_messages:
                api_messages[-1]["content"] += (
                    f"\n\nResponse mode: {response_mode if 'response_mode' in locals() else st.session_state.chat_response_mode}. "
                    f"Answer format: {output_format if 'output_format' in locals() else st.session_state.chat_output_format}. "
                    "Follow this preference while keeping the answer accurate and readable."
                )

            with st.spinner("NEXTGEN AI is thinking..."):
                try:
                    search_results = []

                    # AI decides whether fresh web information is needed.
                    if ai_should_search_web(user_text):
                        try:
                            search_results = smart_web_search(
                                user_text,
                                max_results=5
                            )
                        except Exception as search_error:
                            st.warning(
                                "Web search failed. I will answer using the "
                                "configured AI model only. "
                                + str(search_error)[:200]
                            )

                    if search_results:
                        api_messages.append({
                            "role": "user",
                            "content": format_search_context(search_results)
                        })

                    answer, provider = ask_ai(api_messages)

                    if search_results:
                        answer += "\n\n**Web sources**\n" + "\n".join(
                            f"- [{item['title']}]({item['url']})"
                            for item in search_results
                        )

                    st.session_state.messages.append(("assistant", answer))
                    save_message(
                        st.session_state.chat_id,
                        USER_ID,
                        "assistant",
                        answer
                    )
                    st.session_state.last_provider = provider

                except Exception as e:
                    st.error(str(e))

            st.rerun()

    st.caption("Your assistant is ready whenever you are. Plus and Mic are built into the chat input.")

# ============================================================
# LIVE VOICE
# ============================================================

elif page == "Live Voice":
    hero("Live Voice", "Voice interaction hub for speaking and listening.")
    st.markdown("### Choose how to use voice")
    voice_tab, call_tab, setup_tab = st.tabs(["Speak & Listen", "Live Calling", "Setup"])
    with voice_tab:
        st.write("Use the microphone in AI Chat to send a voice message. NEXTGEN AI can also read its latest answer aloud using voices installed on your device.")
        st.info("Browser voices vary by device, operating system and browser. This free playback option is not the same as a studio-quality hosted voice model.")
        if st.button("Open AI Chat for microphone input", use_container_width=True):
            st.session_state.page = "AI Chat"
            st.rerun()
    with call_tab:
        if CF_LIVE_URL:
            st.success("A live voice endpoint is configured.")
            st.link_button("Open Live Voice Session", CF_LIVE_URL, use_container_width=True)
            st.caption("The configured endpoint opens separately. Its availability, call quality and provider charges depend on that service.")
        else:
            st.warning("Live calling is not connected yet.")
            st.write("To enable a real two-way live call, configure CLOUDFLARE_VOICE_URL with your working voice-room or realtime-call URL in Streamlit Secrets.")
    with setup_tab:
        st.markdown("**Current voice capabilities**")
        st.write("• Voice-to-text input in AI Chat through the configured Groq transcription key.")
        st.write("• Read-aloud playback through the device/browser speech engine.")
        st.write("• Optional external live-call endpoint through CLOUDFLARE_VOICE_URL.")
        st.write("• A true embedded realtime call needs a working realtime provider endpoint and its own credentials; a normal API key alone does not create a calling service.")


# ============================================================
# AI IMAGE STUDIO
# ============================================================

elif page == "AI Image Studio":

    hero(
        "AI Image Studio",
        "Create artwork with styles, composition controls and social-media ratios."
    )

    st.markdown("### Describe your image")

    image_mode = st.selectbox(
        "＋ Choose creation type",
        ["Text to Image", "Cinematic Poster", "Anime Artwork", "Logo Concept",
         "YouTube Thumbnail", "Instagram Post", "Product Photography",
         "Fantasy Art", "Devotional Artwork", "Character Design", "Book Cover",
         "Wallpaper", "Story Scene", "Professional Portrait"]
    )

    prompt = st.text_area(
        "Image prompt",
        placeholder="Describe the subject, background, mood, colours, clothing, lighting and details...",
        height=120,
        key="image_prompt"
    )

    style_options = [
        "Cinematic realism", "Ultra-realistic photography", "3D Pixar-like animation",
        "Anime", "Manga ink illustration", "Watercolor painting", "Oil painting",
        "Digital concept art", "Fantasy illustration", "Cyberpunk neon",
        "Vintage film", "Minimalist", "Luxury editorial", "Dark dramatic",
        "Indian festive art", "Devotional traditional art", "Comic-book style",
        "Clay 3D", "Isometric 3D", "Ghibli-inspired soft animation look",
        "Retro 90s poster", "Street photography", "Architectural visualization",
        "Product studio photography", "Paper-cut craft", "Pixel art"
    ]
    style = st.selectbox("Choose an art style", style_options, index=0)

    col_a, col_b = st.columns(2)
    with col_a:
        aspect = st.selectbox(
            "Aspect ratio / composition",
            ["9:16 — Reels / Shorts / Stories", "16:9 — YouTube / Landscape",
             "1:1 — Square post", "4:5 — Instagram portrait",
             "3:4 — Portrait artwork", "4:3 — Classic landscape",
             "3:2 — Photography", "2:3 — Poster / Book cover"]
        )
    with col_b:
        lighting = st.selectbox(
            "Lighting & mood",
            ["Cinematic dramatic lighting", "Golden hour", "Soft natural light",
             "Studio lighting", "Neon night lighting", "Sunrise glow",
             "Moody shadows", "Bright colourful lighting", "Candlelight"]
        )

    col_c, col_d = st.columns(2)
    with col_c:
        camera = st.selectbox(
            "Camera / framing",
            ["Wide shot", "Medium shot", "Close-up", "Extreme close-up",
             "Low-angle hero shot", "Top-down view", "Eye-level portrait",
             "Macro detail", "Full-body composition"]
        )
    with col_d:
        detail_level = st.selectbox(
            "Detail level", ["Balanced detail", "Highly detailed", "Clean minimal detail", "Fine textures and sharp focus"]
        )

    negative_prompt = st.text_input(
        "Avoid (optional)",
        placeholder="e.g. blurry, text errors, extra fingers, watermark, clutter"
    )

    st.caption("The selected ratio guides the composition prompt. The connected image model may not return an exact pixel ratio.")

    if st.button("✦ Generate Image", use_container_width=True):
        if not prompt.strip():
            st.warning("Please write an image prompt.")
        else:
            full_prompt = (
                f"{image_mode}. Art direction: {style}. Subject and scene: {prompt}. "
                f"Composition ratio: {aspect}. Lighting: {lighting}. Camera framing: {camera}. "
                f"Quality: {detail_level}. Create a polished, coherent image with clear subject placement. "
                + (f"Avoid: {negative_prompt}." if negative_prompt.strip() else "")
            )
            with st.spinner("Creating your image..."):
                try:
                    result = cloudflare_image(full_prompt)
                    st.image(result, use_container_width=True)
                    st.download_button(
                        "↓ Download Image", data=result,
                        file_name="nextgen_image.png", mime="image/png"
                    )
                except Exception as exc:
                    st.error("Image generation failed: " + str(exc))


# ============================================================
# WEBSITE BUILDER
# ============================================================

elif page == "Website Builder":
    hero("AI Website Builder", "Describe a website and generate a responsive, downloadable HTML page.")
    website_type = st.selectbox("Website type", ["Business Website", "Portfolio", "Landing Page", "Blog", "Event Website", "Product Showcase", "Educational Website"], key="website_type")
    website_prompt = st.text_area("Describe your website", placeholder="Example: Create a modern stationery shop website with home, products, about and contact sections...", height=150, key="website_prompt")
    website_style = st.selectbox("Visual direction", ["Modern and clean", "Premium dark", "Colorful and friendly", "Minimal", "Professional corporate"], key="website_style")

    if st.button("✦ Generate Website", key="generate_website", use_container_width=True):
        if len(website_prompt.strip()) < 12:
            st.warning("Please describe the website in a little more detail.")
        else:
            request_text = ("Create a complete, polished, responsive " + website_type + ".\n"
                + "Visual direction: " + website_style + ".\nUser requirements: " + website_prompt
                + "\nReturn ONLY a complete single-file index.html with embedded CSS and JavaScript. "
                + "Use mobile-first responsive layout, accessible semantic HTML, working navigation, "
                + "working buttons/forms where possible, no paid service dependencies, and clear comments "
                + "where owner contact details or API credentials must be added. Do not use markdown fences. "
                + "Do not claim it is hosted or deployed.")
            with st.spinner("Building your website..."):
                try:
                    result, provider = ask_ai([{"role": "user", "content": request_text}])
                    cleaned = re.sub(r"^```(?:html)?\s*|\s*```$", "", result.strip(), flags=re.I)
                    st.session_state.website_result = cleaned
                    st.session_state.website_provider = provider
                except Exception as exc:
                    st.error("Website generation failed: " + str(exc))

    if st.session_state.get("website_result"):
        st.markdown("### Generated website code")
        st.caption("Created with NEXTGEN AI")
        st.code(st.session_state.website_result, language="html")
        render_answer_controls(st.session_state.website_result, "website_builder_result")
        st.download_button("↓ Download index.html", data=st.session_state.website_result.encode("utf-8"), file_name="index.html", mime="text/html", key="download_generated_website")


# ============================================================
# APP BUILDER
# ============================================================

elif page == "App Builder":
    hero("AI App Builder", "Generate practical application starter code from your idea.")
    app_platform = st.selectbox("Application platform", ["Python + Streamlit", "Python CLI", "HTML + CSS + JavaScript", "React frontend starter", "Flask web app"], key="app_platform")
    app_prompt = st.text_area("Describe the application", placeholder="Example: Build a student task manager with add, complete, delete and search tasks...", height=150, key="app_prompt")
    app_level = st.selectbox("Code detail", ["Beginner-friendly with comments", "Clean production-style starter", "Detailed with explanation"], key="app_level")

    if st.button("✦ Generate App Code", key="generate_app_code", use_container_width=True):
        if len(app_prompt.strip()) < 12:
            st.warning("Please describe the app in a little more detail.")
        else:
            request_text = ("Create a working starter application for this idea: " + app_prompt
                + "\nTarget platform: " + app_platform + ".\nCode style: " + app_level
                + ".\nReturn complete code for the main runnable file with required imports, input validation, "
                + "useful error handling, and comments. Never invent API keys. If external dependencies are "
                + "required, list them after the code. Do not claim the code was executed or deployed. "
                + "Use markdown code fences and identify the language.")
            with st.spinner("Building your application..."):
                try:
                    result, provider = ask_ai([{"role": "user", "content": request_text}])
                    st.session_state.app_builder_result = result
                    st.session_state.app_builder_provider = provider
                except Exception as exc:
                    st.error("App generation failed: " + str(exc))

    if st.session_state.get("app_builder_result"):
        st.markdown("### Generated application")
        st.caption("Created with NEXTGEN AI")
        st.markdown(st.session_state.app_builder_result)
        render_answer_controls(st.session_state.app_builder_result, "app_builder_result")
        st.download_button("↓ Download generated code as TXT", data=st.session_state.app_builder_result.encode("utf-8"), file_name="generated_app_code.txt", mime="text/plain", key="download_generated_app")


# ============================================================
# TOOL CENTER + CODING SCHOOL
# ============================================================

elif page == "Tool Center":

    hero(
        "AI Tool Center",
        "Choose a category, select a tool and let NEXTGEN AI do the work."
    )

    st.markdown(
        f'<div class="tool-stat">'
        f'<span class="dash-kicker">TOOL LIBRARY</span>'
        f'<h2 style="margin:4px 0;color:white;font-size:28px;">'
        f'{TOOL_COUNT:,} AI tool workflows</h2>'
        f'<div class="small-muted">Study, coding, writing, creativity and productivity.</div>'
        f'</div>',
        unsafe_allow_html=True
    )

    category = st.selectbox(
        "① Select a Category",
        list(TOOL_LIBRARY.keys()),
        key="tool_category_select"
    )

    tool_name = st.selectbox(
        "② Select an AI Tool",
        TOOL_LIBRARY[category],
        key="tool_name_select"
    )

    option_a, option_b = st.columns(2)
    with option_a:
        output_format = st.selectbox("③ Output format", TOOL_OUTPUT_FORMATS, key="tool_output_format")
    with option_b:
        learning_level = st.selectbox("④ Detail / learning level", TOOL_LEVELS, key="tool_learning_level")

    st.markdown(f"### ✦ {tool_name}")
    st.caption("Selected Category: " + category)

    details = st.text_area(
        "Your instructions",
        placeholder=(
            "Tell NEXTGEN AI what you need. Add topic, language, "
            "class/level, length or other requirements..."
        ),
        height=120,
        key="tool_details"
    )

    if st.button(
        "Run Tool ✦",
        key="run_selected_tool",
        use_container_width=True
    ):

        if not details.strip():
            st.warning("Enter your instructions first.")

        else:
            with st.spinner(f"Running {tool_name}..."):
                try:
                    configured_details = (
                        f"Requested output format: {output_format}\n"
                        f"Requested level: {learning_level}\n\n{details}"
                    )
                    result, provider = run_tool(tool_name, configured_details)

                    st.session_state.tool_result = {
                        "tool": tool_name,
                        "category": category,
                        "result": result,
                        "provider": provider
                    }

                except Exception as exc:
                    st.error("Tool failed: " + str(exc))

    if st.session_state.tool_result:

        st.markdown("---")
        st.markdown(
            "### Result: " + st.session_state.tool_result["tool"]
        )

        st.markdown(st.session_state.tool_result["result"])
        render_answer_controls(st.session_state.tool_result["result"], "tool_center_result")

        st.caption(
            "Generated by " + st.session_state.tool_result["provider"]
        )

        st.download_button(
            "↓ Download result as TXT",
            data=st.session_state.tool_result["result"],
            file_name="nextgen_ai_result.txt",
            mime="text/plain"
        )

    st.caption(
        f"{BASE_TOOL_COUNT} base task presets × {len(TOOL_OUTPUT_FORMATS)} output formats "
        f"× {len(TOOL_LEVELS)} levels = {TOOL_COUNT:,} configurable AI workflows. "
        "These are workflows powered by your configured AI provider, not separate AI models."
    )


# ============================================================
# STOCK MARKET ACADEMY — EDUCATION + CHART ANALYSIS
# ============================================================

elif page == "Stock Market & Trading Hub":
    hero("Stock Market & Trading Hub", "Learn the stock market, understand trading concepts, analyse charts and practise with virtual money.")

    st.info("Learning mode only: this page does not tell you what to buy or sell. Market prices can change quickly. Use a parent/guardian and a qualified financial professional for real financial decisions.")

    tab_learn, tab_chart, tab_company, tab_practice, tab_trading, tab_simulator = st.tabs([
        "Stock Market Learning", "Chart Lab", "Company Analysis",
        "Paper Portfolio", "Trading School", "Paper Trading Simulator"
    ])

    with tab_learn:
        lessons = {
            "1. What is a stock?": "A stock represents a small ownership share in a company. Stock prices can rise or fall, and you can lose money.",
            "2. Exchanges and indices": "Exchanges are marketplaces where securities trade. An index tracks a selected group of securities, such as the NIFTY 50 or S&P 500.",
            "3. Candlesticks": "A candle summarizes open, high, low and close for a time period. The body compares open and close; the wicks show the high and low.",
            "4. Trend and support/resistance": "A trend describes the broad direction of price. Support and resistance are chart areas where price has previously struggled to move through; they are not guarantees.",
            "5. Volume": "Volume measures how many shares traded in a period. It can add context to a price move but does not predict the future.",
            "6. Risk and diversification": "Risk is uncertainty about outcomes. Diversification spreads exposure across different assets; it cannot remove all risk.",
            "7. Fundamental analysis": "This studies a company's business, revenue, profit, debt, cash flow, competitive position and valuation.",
            "8. Technical analysis": "This studies price and volume history using charts and indicators. Indicators are descriptive tools, not certain signals.",
            "9. Common indicators": "Moving averages smooth price data. RSI measures recent momentum. MACD compares moving averages. Each can give false signals.",
            "10. Long-term investing vs trading": "Investing usually focuses on ownership and long-term business performance. Trading usually focuses on shorter-term price movements and often involves higher activity and costs.",
            "11. Fees, taxes and inflation": "Costs and taxes reduce returns. Inflation reduces purchasing power, so nominal gains are not the same as real gains.",
            "12. Scams and emotional decisions": "Be cautious of guaranteed-return claims, pressure tactics, unregistered advisers and social-media tips. Never share OTPs or account credentials.",
            "13. Reading financial statements": "Learn how the income statement, balance sheet and cash-flow statement describe different parts of a business.",
            "14. Revenue, profit and margins": "Revenue is money earned from operations; profit is what remains after costs. Margins compare profit with revenue.",
            "15. EPS and P/E ratio": "EPS relates profit to shares outstanding. P/E compares price with earnings; neither metric should be used alone.",
            "16. Market capitalisation": "Market cap is share price multiplied by shares outstanding. It is one way to describe a company's market value.",
            "17. Dividends": "Dividends are distributions a company may make to shareholders. They are not guaranteed and can be reduced or stopped.",
            "18. Debt and interest coverage": "Debt can help fund growth but creates repayment obligations. Interest coverage compares operating earnings with interest expense.",
            "19. Cash flow": "Operating cash flow shows cash generated by core operations. Profit and cash flow can differ for many accounting reasons.",
            "20. Portfolio diversification": "Diversification spreads exposure across companies, sectors and asset types. Correlations can rise during market stress.",
            "21. Volatility and drawdown": "Volatility describes variation in returns. Drawdown measures a decline from a previous portfolio peak.",
            "22. Backtesting basics": "Backtesting checks a historical strategy against past data. It can suffer from overfitting, survivorship bias and unrealistic costs.",
            "23. Order types": "Market, limit and stop orders behave differently. Availability and rules depend on the broker and exchange.",
            "24. Investor psychology": "Fear, overconfidence and herd behaviour can affect decisions. A written plan and risk limits can reduce impulsive choices."
        }
        lesson_name = st.selectbox("Choose a lesson", list(lessons.keys()), key="market_lesson")
        st.markdown("### " + lesson_name)
        st.write(lessons[lesson_name])
        learner_question = st.text_area("Ask NEXTGEN AI to teach this topic with examples", key="market_lesson_question", placeholder="Explain this in simple Hindi with an example...")
        if st.button("Teach me this topic", key="teach_market_topic", use_container_width=True):
            question = f"Teach this stock-market education topic safely and accurately: {lesson_name}. Base explanation: {lessons[lesson_name]}. Student question: {learner_question or 'Explain from basics with an example and a short quiz.'} Do not give personalized buy/sell advice or promise returns."
            with st.spinner("Preparing your lesson..."):
                try:
                    answer, provider = ask_ai([{"role": "user", "content": question}])
                    st.markdown(answer)
                    render_answer_controls(answer, "market_lesson_answer")
                    st.caption("Learning response from NEXTGEN AI")
                except Exception as exc:
                    st.error("AI lesson unavailable: " + str(exc))

    with tab_chart:
        st.markdown("### Live / historical market chart")
        st.write("Try a ticker such as AAPL, MSFT, RELIANCE.NS or TCS.NS. The public chart source is unofficial and may be unavailable or rate-limited; always verify prices with your broker or exchange.")
        live_a, live_b = st.columns(2)
        with live_a:
            market_symbol = st.text_input("Ticker symbol", value="RELIANCE.NS", key="market_chart_symbol")
        with live_b:
            market_period = st.selectbox("Chart period", ["1mo", "3mo", "6mo", "1y", "5y"], index=1, key="market_chart_period")
        if st.button("Load market chart", key="load_market_chart", use_container_width=True):
            try:
                points, market_meta = fetch_public_market_history(market_symbol, market_period)
                st.session_state["market_chart_points"] = points
                st.session_state["market_chart_meta"] = market_meta
                st.session_state["market_chart_symbol_loaded"] = market_symbol.strip().upper()
            except Exception as exc:
                st.warning("Live chart could not be loaded: " + str(exc))
        if st.session_state.get("market_chart_points"):
            points = st.session_state["market_chart_points"]
            st.markdown("#### " + st.session_state.get("market_chart_symbol_loaded", "Market") + " price history")
            close_values = [v for _, v in points]
            st.line_chart({"Close": close_values}, y_label="Price")

            def sma(values, window):
                return [None if i + 1 < window else sum(values[i + 1 - window:i + 1]) / window for i in range(len(values))]

            def ema(values, window):
                if not values:
                    return []
                alpha = 2 / (window + 1)
                output = [values[0]]
                for value in values[1:]:
                    output.append(alpha * value + (1 - alpha) * output[-1])
                return output

            def rsi(values, window=14):
                output = [None] * len(values)
                if len(values) <= window:
                    return output
                gains = [max(values[i] - values[i - 1], 0) for i in range(1, len(values))]
                losses = [max(values[i - 1] - values[i], 0) for i in range(1, len(values))]
                avg_gain = sum(gains[:window]) / window
                avg_loss = sum(losses[:window]) / window
                output[window] = 100 if avg_loss == 0 else 100 - (100 / (1 + avg_gain / avg_loss))
                for i in range(window + 1, len(values)):
                    avg_gain = (avg_gain * (window - 1) + gains[i - 1]) / window
                    avg_loss = (avg_loss * (window - 1) + losses[i - 1]) / window
                    output[i] = 100 if avg_loss == 0 else 100 - (100 / (1 + avg_gain / avg_loss))
                return output

            sma20 = sma(close_values, 20)
            sma50 = sma(close_values, 50)
            ema12 = ema(close_values, 12)
            ema26 = ema(close_values, 26)
            macd_line = [a - b for a, b in zip(ema12, ema26)]
            macd_signal = ema(macd_line, 9)
            rsi14 = rsi(close_values, 14)
            bollinger_mid = sma(close_values, 20)
            bollinger_upper, bollinger_lower = [], []
            for i, mid in enumerate(bollinger_mid):
                if mid is None:
                    bollinger_upper.append(None)
                    bollinger_lower.append(None)
                else:
                    window_values = close_values[i + 1 - 20:i + 1]
                    variance = sum((v - mid) ** 2 for v in window_values) / 20
                    deviation = variance ** 0.5
                    bollinger_upper.append(mid + 2 * deviation)
                    bollinger_lower.append(mid - 2 * deviation)
            indicator_cols = st.columns(5)
            latest_rsi = next((v for v in reversed(rsi14) if v is not None), None)
            indicator_cols[0].metric("RSI (14)", f"{latest_rsi:.2f}" if latest_rsi is not None else "Need 15+ points")
            indicator_cols[1].metric("SMA (20)", f"{sma20[-1]:,.2f}" if sma20 and sma20[-1] is not None else "Need 20+ points")
            indicator_cols[2].metric("EMA (12)", f"{ema12[-1]:,.2f}" if ema12 else "—")
            indicator_cols[3].metric("MACD", f"{macd_line[-1]:,.3f}" if macd_line else "—")
            indicator_cols[4].metric("Bollinger (20)", f"{bollinger_lower[-1]:,.2f} – {bollinger_upper[-1]:,.2f}" if bollinger_upper and bollinger_upper[-1] is not None else "Need 20+ points")
            with st.expander("View technical indicator charts"):
                series = {"Close": close_values, "EMA 12": ema12, "EMA 26": ema26, "Bollinger Upper": bollinger_upper, "Bollinger Mid": bollinger_mid, "Bollinger Lower": bollinger_lower}
                if any(v is not None for v in sma20):
                    series["SMA 20"] = sma20
                if any(v is not None for v in sma50):
                    series["SMA 50"] = sma50
                st.line_chart(series, y_label="Price / moving average")
                st.line_chart({"MACD": macd_line, "Signal": macd_signal}, y_label="MACD")
                if latest_rsi is not None:
                    st.line_chart({"RSI 14": [v if v is not None else 0 for v in rsi14]}, y_label="RSI (0–100)")
                st.caption("Indicators are calculated from the loaded closing prices only: SMA, EMA, RSI, MACD and Bollinger Bands. They are educational descriptions, not buy/sell signals. RSI uses Wilder-style smoothing after its initial average.")

            start_price, end_price = points[0][1], points[-1][1]
            pct = ((end_price - start_price) / start_price * 100) if start_price else 0
            q1, q2, q3 = st.columns(3)
            q1.metric("First close", f"{start_price:,.2f}")
            q2.metric("Latest close", f"{end_price:,.2f}")
            q3.metric("Period change", f"{pct:+.2f}%")
            st.caption("Historical prices are not predictions. Endpoint: Yahoo Finance public chart API (unofficial).")

        st.markdown("---")
        st.markdown("### Or analyse your own CSV data")
        st.write("Upload a CSV with a Date column and a Close column. This is your uploaded data, not a live feed.")
        chart_file = st.file_uploader("Upload price history CSV", type=["csv"], key="market_csv")
        if chart_file is not None:
            try:
                import csv
                raw = chart_file.getvalue().decode("utf-8-sig").splitlines()
                rows = list(csv.DictReader(raw))
                if not rows:
                    st.warning("The CSV has no data rows.")
                else:
                    headers = list(rows[0].keys())
                    date_col = next((h for h in headers if h and h.lower() in ["date", "time", "timestamp"]), headers[0])
                    close_col = next((h for h in headers if h and h.lower() in ["close", "adj close", "price", "last"]), None)
                    if close_col is None:
                        st.error("Could not find a Close, Adj Close, Price or Last column.")
                    else:
                        chart_rows = []
                        for row in rows:
                            try:
                                chart_rows.append((str(row.get(date_col, "")), float(str(row.get(close_col, "").replace(",", "")))))
                            except Exception:
                                continue
                        if len(chart_rows) >= 2:
                            st.line_chart({"Close": [v for _, v in chart_rows]}, x_label="Uploaded rows", y_label="Close price")
                            first, last = chart_rows[0][1], chart_rows[-1][1]
                            change = ((last - first) / first * 100) if first else 0
                            m1, m2, m3 = st.columns(3)
                            m1.metric("First close", f"{first:,.2f}")
                            m2.metric("Latest close", f"{last:,.2f}")
                            m3.metric("Change in uploaded range", f"{change:+.2f}%")
                            st.caption(f"Showing {len(chart_rows)} valid rows from {date_col} / {close_col}. This is historical uploaded data, not a forecast.")
                        else:
                            st.warning("At least two valid numeric closing prices are needed.")
            except Exception as exc:
                st.error("Could not read CSV: " + str(exc))
        else:
            sample_prices = [100, 102, 101, 105, 103, 108, 110, 107, 112, 115, 113, 118]
            st.line_chart({"Illustrative sample price": sample_prices}, y_label="Illustrative price")
            st.caption("Illustrative sample only — not a real stock or live market data.")

    with tab_company:
        st.markdown("### Company research checklist")
        ticker = st.text_input("Company name / ticker", placeholder="e.g. a company you want to study", key="market_company")
        company_context = st.text_area("Paste financial data or describe what you want to understand", placeholder="Revenue, profit, debt, cash flow, valuation, business model, competitors, risks...", height=120, key="market_company_context")
        if st.button("Create educational company analysis", key="company_analysis_button", use_container_width=True):
            if not ticker.strip():
                st.warning("Enter a company name or ticker first.")
            else:
                prompt = f"Create an educational research report for {ticker}. Analyse only the information supplied below; if data is missing, list it as missing and do not invent figures. Cover business model, revenue/profit trends, debt, cash flow, valuation concepts, competition, governance, risks, questions to research and a balanced summary. Do not give a personalized buy/sell recommendation. Data/context: {company_context}"
                with st.spinner("Reviewing the supplied information..."):
                    try:
                        answer, provider = ask_ai([{"role": "user", "content": prompt}])
                        st.markdown(answer)
                        render_answer_controls(answer, "company_analysis_answer")
                        st.caption("Educational analysis from NEXTGEN AI. Verify figures against official filings and exchange disclosures.")
                    except Exception as exc:
                        st.error("Analysis unavailable: " + str(exc))

    with tab_practice:
        st.markdown("### Paper portfolio calculator")
        st.caption("Practice arithmetic with hypothetical numbers. No order is placed and no real money is involved.")
        pc1, pc2, pc3 = st.columns(3)
        with pc1:
            buy_price = st.number_input("Hypothetical entry price", min_value=0.0, value=100.0, step=1.0, key="paper_buy")
        with pc2:
            current_price = st.number_input("Hypothetical current price", min_value=0.0, value=110.0, step=1.0, key="paper_current")
        with pc3:
            quantity = st.number_input("Units", min_value=1, value=5, step=1, key="paper_quantity")
        invested = buy_price * quantity
        current_value = current_price * quantity
        pnl = current_value - invested
        pnl_pct = (pnl / invested * 100) if invested else 0
        p1, p2, p3 = st.columns(3)
        p1.metric("Hypothetical cost", f"₹{invested:,.2f}")
        p2.metric("Hypothetical value", f"₹{current_value:,.2f}")
        p3.metric("Unrealized practice P/L", f"₹{pnl:,.2f}", f"{pnl_pct:+.2f}%")
        st.caption("This simplified example excludes brokerage, taxes, slippage, dividends and other costs.")


    with tab_trading:
        st.markdown("### Trading School")
        st.write("A beginner-friendly learning area covering how trading works, how to read a trade plan and how to manage risk. These lessons are educational—not signals or recommendations.")
        trading_lessons = {
            "1. What is trading?": "Trading means buying and selling financial assets over shorter periods. Prices can move against a trader, and frequent trading can increase costs and risk.",
            "2. Investing vs trading": "Investing generally focuses on long-term ownership and business performance. Trading focuses more on shorter-term price changes. Neither guarantees a profit.",
            "3. Market, limit and stop orders": "A market order seeks execution at the best available price, but the final price can differ. A limit order sets a maximum buy price or minimum sell price and may not execute. Stop-order behaviour varies by broker and exchange.",
            "4. Intraday, swing and positional trading": "Intraday positions are opened and closed within a session; swing trading may last days or weeks; positional trading can last longer. Holding time does not remove market risk.",
            "5. Candlestick basics": "Candles show open, high, low and close for a time period. A candle is a record of past trading, not a prediction of the next move.",
            "6. Risk per trade and position sizing": "Position sizing connects the amount at risk with the distance between entry and an exit level. A stop order cannot guarantee the exact exit price, especially in fast markets.",
            "7. Stop-loss and exit planning": "A stop-loss is an instruction intended to limit a loss, but execution price can differ during gaps or fast moves. A trade plan should define conditions before a simulated entry.",
            "8. Risk-reward ratio": "A risk-reward ratio compares a possible loss with a possible gain. It is a planning tool, not a probability estimate or guarantee.",
            "9. Trading psychology": "Fear of missing out, revenge trading and overconfidence can lead to impulsive decisions. A written journal can help review decisions calmly.",
            "10. Trading journal": "Record the reason for a simulated trade, entry, exit, costs assumed, outcome and what you learned. Review process quality rather than judging only profit or loss.",
            "11. Leverage and margin": "Leverage increases exposure relative to the cash deposited and can magnify losses. Beginners should understand the risks and practise without leverage.",
            "12. Common scams": "Avoid guaranteed-profit claims, paid signal pressure, fake screenshots and requests for OTPs or account credentials. Verify intermediaries through official regulatory sources."
        }
        selected_trading_lesson = st.selectbox("Choose a trading lesson", list(trading_lessons.keys()), key="trading_lesson_select")
        st.markdown("#### " + selected_trading_lesson)
        st.write(trading_lessons[selected_trading_lesson])
        trading_question = st.text_area("What would you like NEXTGEN AI to explain?", key="trading_lesson_question", placeholder="Explain in simple Hindi with an example...")
        if st.button("Learn this trading topic", key="teach_trading_topic", use_container_width=True):
            prompt = (
                "Teach this trading education topic to a beginner in clear, simple language. "
                "Use a hypothetical example and finish with three short quiz questions. "
                "Explain uncertainty, costs and risk. Do not provide personalized financial advice, "
                "specific buy/sell calls, guaranteed outcomes, leverage instructions or real-money execution. "
                f"Topic: {selected_trading_lesson}. Base notes: {trading_lessons[selected_trading_lesson]}. "
                f"Student question: {trading_question or 'Explain from basics.'}"
            )
            with st.spinner("Preparing your trading lesson..."):
                try:
                    answer, _provider = ask_ai([{"role": "user", "content": prompt}])
                    st.markdown(answer)
                    render_answer_controls(answer, "trading_lesson_answer")
                except Exception as exc:
                    st.error("Trading lesson unavailable: " + str(exc))

    with tab_simulator:
        st.markdown("### Virtual Paper Trading")
        st.info("Simulation only. This uses virtual funds and manually entered practice prices. It does not connect to a broker, place orders or use real money.")
        if "paper_trade_cash" not in st.session_state:
            st.session_state.paper_trade_cash = 100000.0
        if "paper_trade_holdings" not in st.session_state:
            st.session_state.paper_trade_holdings = {}
        if "paper_trade_history" not in st.session_state:
            st.session_state.paper_trade_history = []

        cash = float(st.session_state.paper_trade_cash)
        holdings = st.session_state.paper_trade_holdings
        h1, h2 = st.columns(2)
        h1.metric("Virtual cash", f"₹{cash:,.2f}")
        h2.metric("Open positions", str(len(holdings)))

        st.markdown("#### Create a simulated order")
        sim_symbol = st.text_input("Practice ticker / asset name", placeholder="Example: RELIANCE.NS", key="sim_trade_symbol").strip().upper()
        sim_side = st.radio("Practice action", ["BUY", "SELL"], horizontal=True, key="sim_trade_side")
        sim_price = st.number_input("Practice price per unit (₹)", min_value=0.01, value=100.0, step=1.0, key="sim_trade_price")
        sim_qty = st.number_input("Quantity (units)", min_value=1, max_value=100000, value=1, step=1, key="sim_trade_qty")
        estimated_value = float(sim_price) * int(sim_qty)
        st.caption(f"Simulated order value: ₹{estimated_value:,.2f} · No brokerage or taxes are included.")
        if st.button("Run virtual simulation", key="run_paper_trade", use_container_width=True):
            if not sim_symbol:
                st.warning("Enter a ticker or asset name.")
            elif sim_side == "BUY" and estimated_value > float(st.session_state.paper_trade_cash):
                st.error("Not enough virtual cash for this simulated purchase.")
            elif sim_side == "SELL" and int(holdings.get(sim_symbol, {}).get("quantity", 0)) < int(sim_qty):
                st.error("You do not have enough virtual units to simulate this sale.")
            else:
                if sim_side == "BUY":
                    previous = holdings.get(sim_symbol, {"quantity": 0, "average_price": 0.0})
                    old_qty = int(previous["quantity"])
                    new_qty = old_qty + int(sim_qty)
                    new_average = ((old_qty * float(previous["average_price"])) + estimated_value) / new_qty
                    holdings[sim_symbol] = {"quantity": new_qty, "average_price": new_average}
                    st.session_state.paper_trade_cash = float(st.session_state.paper_trade_cash) - estimated_value
                else:
                    previous = holdings[sim_symbol]
                    remaining = int(previous["quantity"]) - int(sim_qty)
                    if remaining:
                        holdings[sim_symbol] = {"quantity": remaining, "average_price": float(previous["average_price"])}
                    else:
                        del holdings[sim_symbol]
                    st.session_state.paper_trade_cash = float(st.session_state.paper_trade_cash) + estimated_value
                st.session_state.paper_trade_holdings = holdings
                st.session_state.paper_trade_history.insert(0, {
                    "Action": sim_side, "Ticker": sim_symbol, "Quantity": int(sim_qty),
                    "Practice Price": float(sim_price), "Simulated Value": estimated_value,
                    "Note": "Virtual only"
                })
                st.success("Virtual practice transaction recorded. No real order was placed.")
                st.rerun()

        st.markdown("#### Your virtual holdings")
        if holdings:
            holding_rows = [
                {"Ticker": symbol, "Units": data["quantity"], "Average practice price (₹)": round(data["average_price"], 2)}
                for symbol, data in sorted(holdings.items())
            ]
            st.dataframe(holding_rows, use_container_width=True, hide_index=True)
        else:
            st.caption("No virtual holdings yet. Try a small simulated example.")

        st.markdown("#### Practice trade journal")
        if st.session_state.paper_trade_history:
            st.dataframe(st.session_state.paper_trade_history, use_container_width=True, hide_index=True)
        else:
            st.caption("Your simulated transactions will appear here.")

        if st.button("Reset virtual portfolio", key="reset_paper_trade"):
            st.session_state.paper_trade_cash = 100000.0
            st.session_state.paper_trade_holdings = {}
            st.session_state.paper_trade_history = []
            st.success("Virtual portfolio reset to ₹1,00,000.")
            st.rerun()


# ============================================================
# PDF ASSISTANT
# ============================================================

elif page == "PDF Assistant":

    hero(
        "PDF Assistant",
        "Upload a document and ask questions about its contents."
    )

    pdf = st.file_uploader(
        "＋ Upload PDF",
        type=["pdf"],
        key="pdf_assistant_upload"
    )

    if pdf:

        try:
            from pypdf import PdfReader

            reader = PdfReader(io.BytesIO(pdf.getvalue()))

            pdf_text = "\n".join(
                page.extract_text() or ""
                for page in reader.pages
            )

            st.success(f"Loaded {len(reader.pages)} pages.")

            question = st.text_input(
                "Ask a question about this PDF"
            )

            if st.button("Ask NEXTGEN AI"):

                if question.strip():

                    with st.spinner("Reading your document..."):

                        answer, provider = ask_ai([{
                            "role": "user",
                            "content": (
                                "Answer based on this PDF. If the answer "
                                "is not in the document, say so clearly.\n\n"
                                + pdf_text[:45000]
                                + "\n\nQuestion: " + question
                            )
                        }])

                    st.markdown(answer)
                    render_answer_controls(answer, "pdf_answer")
                    st.caption("Created with NEXTGEN AI")

                else:
                    st.warning("Type a question first.")

        except Exception as exc:
            st.error("PDF error: " + str(exc))


# ============================================================
# CHAT HISTORY
# ============================================================

elif page == "Chat History":

    hero(
        "Chat History",
        "Continue your previous conversations."
    )

    chats = all_chats(USER_ID)

    if not chats:
        st.info("No conversations yet.")

    for chat in chats:

        chat_id, title, created = chat

        with st.expander(
            f"{title or 'New Chat'}  ·  {created[:16]}"
        ):

            open_col, delete_col = st.columns(2)

            with open_col:
                if st.button("Open", key=f"history_open_{chat_id}"):

                    st.session_state.chat_id = chat_id
                    st.session_state.messages = get_messages(
                        chat_id, USER_ID
                    )
                    st.session_state.page = "AI Chat"
                    st.rerun()

            with delete_col:
                if st.button("Delete", key=f"history_delete_{chat_id}"):

                    remove_chat(chat_id, USER_ID)

                    if st.session_state.chat_id == chat_id:
                        st.session_state.chat_id = create_chat(USER_ID)
                        st.session_state.messages = []

                    st.rerun()


# ============================================================
# MY CREATIONS
# ============================================================

elif page == "My Creations":

    hero(
        "My Creations",
        "Your creative workspace."
    )

    st.info(
        "Generated images can be downloaded from Image Studio. "
        "A permanent image gallery is not included in this version."
    )


# ============================================================
# SETTINGS
# ============================================================

elif page == "Settings":

    hero(
        "Your Space, Your Style",
        "Make NEXTGEN AI feel comfortable, focused and truly yours."
    )

    st.markdown("""
    <div class="dash-feature">
      <div class="dash-kicker">A LITTLE ABOUT THE CREATOR</div>
      <h3>✦ Built with curiosity by Arav</h3>
      <p>Arav is a student developer and AI enthusiast who enjoys learning
      technology, experimenting with code, and turning creative ideas into
      useful projects. NEXTGEN AI is a growing workspace built from that
      curiosity and effort.</p>
    </div>
    """, unsafe_allow_html=True)

    st.markdown("### ✨ Personalize your experience")
    appearance_tab, chat_tab, profile_tab = st.tabs([
        "🎨 Appearance", "💬 Chat preferences", "👤 Your profile"
    ])

    with appearance_tab:
        st.write("Choose the visual mood that feels right for your workspace.")
        theme_choice = st.selectbox(
            "Workspace theme",
            list(THEME_PRESETS.keys()),
            index=list(THEME_PRESETS.keys()).index(st.session_state.workspace_theme),
            key="settings_theme_choice"
        )
        if theme_choice != st.session_state.workspace_theme:
            st.session_state.workspace_theme = theme_choice
            st.rerun()
        st.caption("Your theme is applied across the workspace.")

    with chat_tab:
        st.write("Choose how NEXTGEN AI should usually respond.")
        st.selectbox(
            "Preferred response style",
            ["Balanced", "Deep analysis", "Step-by-step tutor", "Concise answer", "Creative mode"],
            key="chat_response_mode"
        )
        st.selectbox(
            "Preferred answer layout",
            ["Automatic", "Structured bullets", "Table", "Checklist", "Examples first"],
            key="chat_output_format"
        )
        st.caption("You can still change these choices inside AI Chat whenever you like.")

    with profile_tab:
        current_user = st.session_state.user
        st.markdown("#### Welcome to your workspace")
        st.write("**Username:**", current_user.get("username", "Guest"))
        st.write(
            "**Account type:**",
            "Guest session" if current_user.get("is_guest", False) else "Registered account"
        )
        st.info(
            "Your conversations are organized in Chat History. "
            "Use the sidebar to start a new chat or return to an earlier one."
        )

    st.markdown("---")
    st.markdown("### 🚀 What you can explore")
    feature_cols = st.columns(2)
    feature_cards = [
        ("✦ AI Chat", "Ask questions, learn, brainstorm and work through ideas."),
        ("▧ Image Studio", "Turn creative prompts into images."),
        ("⌕ Tool Center", "Use guided tools for study, writing, coding and planning."),
        ("▤ PDF Assistant", "Ask questions about documents you upload."),
        ("◈ Website Builder", "Create a starting point for a responsive website."),
        ("▣ App Builder", "Turn an app idea into a practical starter project."),
        ("▥ Stock Market", "Explore market concepts and understand chart data."),
        ("◉ Live Voice", "Open the voice experience when it is configured.")
    ]
    for index, (feature_title, feature_desc) in enumerate(feature_cards):
        with feature_cols[index % 2]:
            st.markdown(
                f'<div class="dash-feature"><h3>{feature_title}</h3>'
                f'<p>{feature_desc}</p></div>',
                unsafe_allow_html=True
            )

    st.caption("Settings here control the experience shown in this workspace. "
               "Private service configuration stays out of the user interface.")


# ============================================================
# ABOUT
# ============================================================

elif page == "About":

    hero(
        "Meet the Creator",
        "The student mind behind NEXTGEN AI."
    )

    st.markdown("""
    ## ✦ Arav

    **Student Developer | AI Enthusiast | Creator of NEXTGEN AI**

    Arav is a curious and creative student developer who enjoys
    artificial intelligence, technology, coding, and creative
    problem-solving. He is the creator of NEXTGEN AI, bringing his
    ideas and enthusiasm for technology into one AI-powered workspace.

    NEXTGEN AI brings multiple AI-powered capabilities together
    in one workspace.

    ### Platform Features

    - AI Chat Assistant
    - AI Image Studio
    - AI Tool Center
    - Website Builder
    - App Builder
    - Smart automatic web search
    - Five response modes and five answer formats
    - Five follow-up actions under each AI answer
    - Workspace mood and font presets
    - Browser read-aloud and microphone transcription
    - Live Voice endpoint launcher
    - Stock chart indicators: SMA, EMA, RSI and MACD
    - Coding School
    - PDF Assistant
    - Chat History
    - Account Login and Sign Up
    - Continue as Guest
    - Automatic sign-in after account creation
    - Multiple AI providers

    ### What NEXTGEN AI stands for

    - Curiosity: keep asking questions and exploring new ideas.
    - Learning: make difficult topics easier to understand.
    - Creativity: turn ideas into useful projects.
    - Progress: improve the workspace one step at a time.

    NEXTGEN AI is a growing project. Features may evolve as the creator
    learns, tests ideas and improves the experience.

    **One Platform. Endless Possibilities.**
    """)

    st.caption("NEXTGEN AI © 2026 · Created by Arav")
