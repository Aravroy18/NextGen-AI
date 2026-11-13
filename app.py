
# ============================================================
# NEXTGEN AI — MAX ULTRA EDITION
# AI Chat | Voice | Stocks | Vision | PDF | Image | Web | Coding
# ============================================================

import os
import io
import re
import json
import time
import base64
import hashlib
import sqlite3
import secrets
import datetime
from pathlib import Path

import requests
import pandas as pd
import streamlit as st
import plotly.graph_objects as go

try:
    from dotenv import load_dotenv
    load_dotenv()
except Exception:
    pass

try:
    from groq import Groq
except Exception:
    Groq = None

try:
    from google import genai
    from google.genai import types
except Exception:
    genai = None
    types = None

try:
    from pypdf import PdfReader
except Exception:
    PdfReader = None

try:
    from gtts import gTTS
except Exception:
    gTTS = None


# ============================================================
# CONFIG
# ============================================================

st.set_page_config(
    page_title="NEXTGEN AI — MAX ULTRA",
    page_icon="🚀",
    layout="wide",
    initial_sidebar_state="expanded"
)

APP_NAME = "NEXTGEN AI"
DB_PATH = "nextgen_ai.db"

def get_secret(name, default=""):
    try:
        value = st.secrets.get(name, "")
        if value:
            return str(value)
    except Exception:
        pass
    return os.getenv(name, default)

GROQ_KEY = get_secret("GROQ_API_KEY")
GEMINI_KEY = get_secret("GEMINI_API_KEY")
FINNHUB_KEY = get_secret("FINNHUB_API_KEY")
TAVILY_KEY = get_secret("TAVILY_API_KEY")
CF_ACCOUNT = get_secret("CLOUDFLARE_ACCOUNT_ID")
CF_TOKEN = get_secret("CLOUDFLARE_API_TOKEN")

GROQ_MODEL = get_secret("GROQ_MODEL", "openai/gpt-oss-120b")
GEMINI_MODEL = get_secret("GEMINI_MODEL", "gemini-2.5-flash")

# ============================================================
# THEME
# ============================================================

st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&display=swap');

html, body, [class*="css"] {
    font-family: Inter, sans-serif;
}
.stApp {
    background:
    radial-gradient(circle at 10% 5%, rgba(55,50,150,.19), transparent 30%),
    radial-gradient(circle at 90% 20%, rgba(0,180,200,.10), transparent 25%),
    #080b14;
    color: #f4f6ff;
}
[data-testid="stSidebar"] {
    background: #0d1220;
    border-right: 1px solid #202a40;
}
.hero {
    padding: 30px;
    border-radius: 22px;
    background: linear-gradient(120deg,#161d38,#102a3d,#191c38);
    border: 1px solid #34415e;
    margin-bottom: 20px;
}
.hero h1 {
    font-size: 42px;
    font-weight: 800;
    margin: 0;
    background: linear-gradient(90deg,#8be9ff,#b6a2ff,#fff);
    -webkit-background-clip: text;
    color: transparent;
}
.hero p { color:#aab8d5; font-size:16px; }
.panel {
    padding:18px;
    background:rgba(20,27,45,.88);
    border:1px solid #293650;
    border-radius:16px;
    margin-bottom:12px;
}
.small-muted {color:#93a3c1;font-size:13px;}
div.stButton > button {
    border-radius: 10px;
    border: 1px solid #344566;
    background: linear-gradient(110deg,#25375d,#25304d);
    color: white;
    font-weight: 600;
}
div.stButton > button:hover {
    border-color:#68dfff;
    color:#8be9ff;
}
[data-testid="stChatMessage"] {
    background: rgba(22,29,48,.75);
    border: 1px solid #27334c;
    border-radius: 15px;
    padding: 12px;
}
hr {border-color:#28344c;}
</style>
""", unsafe_allow_html=True)


# ============================================================
# DATABASE — KEEP EXISTING DATABASE
# ============================================================

def db():
    return sqlite3.connect(DB_PATH, check_same_thread=False)

def init_db():
    con = db()
    cur = con.cursor()

    # Separate names prevent accidental destruction of older tables.
    cur.execute("""
    CREATE TABLE IF NOT EXISTS ng_users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT UNIQUE NOT NULL,
        password_hash TEXT NOT NULL,
        salt TEXT NOT NULL,
        created_at TEXT
    )
    """)

    cur.execute("""
    CREATE TABLE IF NOT EXISTS ng_chats (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL,
        title TEXT,
        created_at TEXT
    )
    """)

    cur.execute("""
    CREATE TABLE IF NOT EXISTS ng_messages (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        chat_id INTEGER NOT NULL,
        role TEXT NOT NULL,
        content TEXT NOT NULL,
        created_at TEXT
    )
    """)

    cur.execute("""
    CREATE TABLE IF NOT EXISTS ng_watchlist (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER,
        symbol TEXT,
        UNIQUE(user_id, symbol)
    )
    """)

    con.commit()
    con.close()

init_db()


# ============================================================
# AUTHENTICATION
# ============================================================

def password_hash(password, salt):
    return hashlib.pbkdf2_hmac(
        "sha256",
        password.encode(),
        salt.encode(),
        260000
    ).hex()

def register_user(username, password):
    username = username.strip()
    if len(username) < 3 or len(password) < 8:
        return False, "Username कम से कम 3 और password 8 characters का होना चाहिए।"

    salt = secrets.token_hex(16)
    hashed = password_hash(password, salt)

    try:
        con = db()
        con.execute(
            "INSERT INTO ng_users(username,password_hash,salt,created_at) VALUES(?,?,?,?)",
            (username, hashed, salt, str(datetime.datetime.now()))
        )
        con.commit()
        con.close()
        return True, "Account created successfully!"
    except sqlite3.IntegrityError:
        return False, "यह username पहले से मौजूद है।"
    except Exception as e:
        return False, str(e)

def login_user(username, password):
    con = db()
    row = con.execute(
        "SELECT id,password_hash,salt FROM ng_users WHERE username=?",
        (username.strip(),)
    ).fetchone()
    con.close()

    if not row:
        return None

    if secrets.compare_digest(password_hash(password, row[2]), row[1]):
        return row[0]
    return None


# ============================================================
# SESSION
# ============================================================

defaults = {
    "user_id": None,
    "username": None,
    "page": "Dashboard",
    "chat_id": None,
    "messages": [],
    "stock_symbol": "AAPL",
    "web_results": [],
    "last_response": "",
    "authenticated": False,
    "voice_text": ""
}

for key, value in defaults.items():
    if key not in st.session_state:
        st.session_state[key] = value


# ============================================================
# API HELPERS
# ============================================================

def api_status():
    return {
        "Groq": bool(GROQ_KEY),
        "Gemini": bool(GEMINI_KEY and genai),
        "Finnhub": bool(FINNHUB_KEY),
        "Tavily": bool(TAVILY_KEY),
        "Cloudflare": bool(CF_ACCOUNT and CF_TOKEN)
    }

def groq_client():
    if not GROQ_KEY or Groq is None:
        return None
    return Groq(api_key=GROQ_KEY)

def gemini_client():
    if not GEMINI_KEY or genai is None:
        return None
    return genai.Client(api_key=GEMINI_KEY)


# ============================================================
# AI ENGINE
# ============================================================

SYSTEM_PROMPT = """
You are NEXTGEN AI, an advanced multilingual AI assistant.
Be accurate, helpful, clear and structured.
You can explain technology, science, education, coding and finance.
Never invent live data, citations or tool results.
For financial topics, provide educational information, not personalized
investment instructions. Mention uncertainty when appropriate.
Answer in the language used by the user.
"""

def ask_groq(prompt, history=None):
    client = groq_client()
    if not client:
        raise RuntimeError("Groq API key missing.")

    msgs = [{"role": "system", "content": SYSTEM_PROMPT}]
    for item in (history or [])[-12:]:
        if item.get("role") in ("user", "assistant"):
            msgs.append({
                "role": item["role"],
                "content": item["content"][:12000]
            })

    msgs.append({"role": "user", "content": prompt})

    result = client.chat.completions.create(
        model=GROQ_MODEL,
        messages=msgs,
        temperature=0.65,
        max_tokens=3500
    )
    return result.choices[0].message.content

def ask_gemini(prompt, history=None):
    client = gemini_client()
    if not client:
        raise RuntimeError("Gemini API key missing.")

    conversation = SYSTEM_PROMPT + "\n\n"
    for item in (history or [])[-10:]:
        conversation += f"{item['role']}: {item['content'][:5000]}\n"

    conversation += "\nuser: " + prompt

    response = client.models.generate_content(
        model=GEMINI_MODEL,
        contents=conversation
    )
    return response.text or "No response received."

def ask_ai(prompt, history=None):
    errors = []

    if GROQ_KEY:
        try:
            return ask_groq(prompt, history), "Groq"
        except Exception as e:
            errors.append("Groq: " + str(e)[:250])

    if GEMINI_KEY:
        try:
            return ask_gemini(prompt, history), "Gemini"
        except Exception as e:
            errors.append("Gemini: " + str(e)[:250])

    raise RuntimeError(
        "AI service unavailable.\n" + "\n".join(errors)
        if errors else "No AI API key configured."
    )


# ============================================================
# MULTIMODAL VISION
# ============================================================

def analyze_image(image_bytes, mime_type, question):
    client = gemini_client()
    if not client:
        raise RuntimeError("Gemini API key required for image analysis.")

    response = client.models.generate_content(
        model=GEMINI_MODEL,
        contents=[
            question,
            types.Part.from_bytes(
                data=image_bytes,
                mime_type=mime_type
            )
        ]
    )
    return response.text or "Image analysis unavailable."


# ============================================================
# WEB SEARCH — TAVILY
# ============================================================

def web_search(query):
    if not TAVILY_KEY:
        raise RuntimeError("TAVILY_API_KEY missing.")

    response = requests.post(
        "https://api.tavily.com/search",
        json={
            "api_key": TAVILY_KEY,
            "query": query,
            "search_depth": "advanced",
            "max_results": 7,
            "include_answer": True
        },
        timeout=30
    )
    response.raise_for_status()
    data = response.json()

    results = []
    if data.get("answer"):
        results.append("SUMMARY:\n" + data["answer"])

    for item in data.get("results", []):
        results.append(
            f"TITLE: {item.get('title')}\n"
            f"URL: {item.get('url')}\n"
            f"CONTENT: {item.get('content')}"
        )
    return "\n\n".join(results)


# ============================================================
# FINNHUB STOCK ENGINE
# ============================================================

FINNHUB_BASE = "https://finnhub.io/api/v1"

def finnhub_get(endpoint, params=None):
    if not FINNHUB_KEY:
        raise RuntimeError("FINNHUB_API_KEY missing.")

    params = params or {}
    params["token"] = FINNHUB_KEY

    response = requests.get(
        FINNHUB_BASE + endpoint,
        params=params,
        timeout=20
    )
    response.raise_for_status()
    data = response.json()

    if isinstance(data, dict) and data.get("error"):
        raise RuntimeError(data["error"])

    return data

@st.cache_data(ttl=20, show_spinner=False)
def stock_quote(symbol):
    return finnhub_get("/quote", {"symbol": symbol})

@st.cache_data(ttl=3600, show_spinner=False)
def stock_profile(symbol):
    return finnhub_get("/stock/profile2", {"symbol": symbol})

@st.cache_data(ttl=60, show_spinner=False)
def stock_search(query):
    return finnhub_get("/search", {"q": query})

@st.cache_data(ttl=120, show_spinner=False)
def stock_news(symbol):
    today = datetime.date.today()
    start = today - datetime.timedelta(days=7)
    return finnhub_get("/company-news", {
        "symbol": symbol,
        "from": str(start),
        "to": str(today)
    })

@st.cache_data(ttl=60, show_spinner=False)
def stock_candles(symbol, resolution="D", days=90):
    end = int(time.time())
    start = end - days * 86400

    return finnhub_get("/stock/candle", {
        "symbol": symbol,
        "resolution": resolution,
        "from": start,
        "to": end
    })

def candle_dataframe(data):
    if data.get("s") != "ok":
        return pd.DataFrame()

    df = pd.DataFrame({
        "Time": pd.to_datetime(data["t"], unit="s"),
        "Open": data["o"],
        "High": data["h"],
        "Low": data["l"],
        "Close": data["c"],
        "Volume": data["v"]
    })
    return df


# ============================================================
# STOCK WATCHLIST
# ============================================================

DEFAULT_STOCKS = [
    "AAPL", "MSFT", "NVDA", "GOOGL",
    "AMZN", "TSLA", "RELIANCE.NS",
    "TCS.NS", "INFY.NS"
]

def get_watchlist(user_id):
    con = db()
    rows = con.execute(
        "SELECT symbol FROM ng_watchlist WHERE user_id=? ORDER BY symbol",
        (user_id,)
    ).fetchall()
    con.close()
    return [x[0] for x in rows]

def add_watchlist(user_id, symbol):
    con = db()
    con.execute(
        "INSERT OR IGNORE INTO ng_watchlist(user_id,symbol) VALUES(?,?)",
        (user_id, symbol.upper())
    )
    con.commit()
    con.close()

def remove_watchlist(user_id, symbol):
    con = db()
    con.execute(
        "DELETE FROM ng_watchlist WHERE user_id=? AND symbol=?",
        (user_id, symbol)
    )
    con.commit()
    con.close()


# ============================================================
# IMAGE GENERATION / EDITING — CLOUDFLARE
# ============================================================

def cloudflare_image(prompt, width=1024, height=1024, steps=4):
    if not CF_ACCOUNT or not CF_TOKEN:
        raise RuntimeError("Cloudflare API credentials missing.")

    model = "@cf/black-forest-labs/flux-1-schnell"
    url = (
        f"https://api.cloudflare.com/client/v4/accounts/"
        f"{CF_ACCOUNT}/ai/run/{model}"
    )

    payload = {
        "prompt": prompt,
        "width": int(width),
        "height": int(height),
        "num_steps": int(steps)
    }

    response = requests.post(
        url,
        headers={"Authorization": f"Bearer {CF_TOKEN}"},
        json=payload,
        timeout=180
    )
    response.raise_for_status()

    content_type = response.headers.get("content-type", "")

    if "image" in content_type:
        return response.content

    data = response.json()
    result = data.get("result", {})

    image_b64 = result.get("image")
    if image_b64:
        return base64.b64decode(image_b64)

    raise RuntimeError(str(data)[:1000])

def cloudflare_edit(prompt, image_bytes):
    if not CF_ACCOUNT or not CF_TOKEN:
        raise RuntimeError("Cloudflare API credentials missing.")

    model = "@cf/black-forest-labs/flux-1-kontext-pro"
    url = (
        f"https://api.cloudflare.com/client/v4/accounts/"
        f"{CF_ACCOUNT}/ai/run/{model}"
    )

    image_b64 = base64.b64encode(image_bytes).decode("utf-8")

    response = requests.post(
        url,
        headers={"Authorization": f"Bearer {CF_TOKEN}"},
        json={
            "prompt": prompt,
            "image": image_b64
        },
        timeout=180
    )
    response.raise_for_status()

    content_type = response.headers.get("content-type", "")
    if "image" in content_type:
        return response.content

    data = response.json()
    image_data = data.get("result", {}).get("image")

    if image_data:
        return base64.b64decode(image_data)

    raise RuntimeError(str(data)[:1000])


# ============================================================
# VOICE — RECORD / TRANSCRIBE / SPEAK
# ============================================================

def transcribe_audio(audio_bytes, filename="recording.wav"):
    if not GROQ_KEY or Groq is None:
        raise RuntimeError("Groq API key required for Whisper transcription.")

    client = groq_client()

    result = client.audio.transcriptions.create(
        file=(filename, audio_bytes),
        model="whisper-large-v3-turbo",
        response_format="text"
    )
    return str(result)

def text_to_speech(text, language="en"):
    if gTTS is None:
        raise RuntimeError("Install gTTS to enable text-to-speech.")

    audio = io.BytesIO()
    gTTS(text=text[:4000], lang=language).write_to_fp(audio)
    audio.seek(0)
    return audio.read()


# ============================================================
# CHAT HISTORY
# ============================================================

def create_chat(user_id, title="New Chat"):
    con = db()
    cur = con.cursor()
    cur.execute(
        "INSERT INTO ng_chats(user_id,title,created_at) VALUES(?,?,?)",
        (user_id, title, str(datetime.datetime.now()))
    )
    chat_id = cur.lastrowid
    con.commit()
    con.close()
    return chat_id

def save_message(chat_id, role, content):
    con = db()
    con.execute(
        "INSERT INTO ng_messages(chat_id,role,content,created_at) VALUES(?,?,?,?)",
        (chat_id, role, content, str(datetime.datetime.now()))
    )
    con.commit()
    con.close()

def load_messages(chat_id):
    con = db()
    rows = con.execute(
        "SELECT role,content FROM ng_messages WHERE chat_id=? ORDER BY id",
        (chat_id,)
    ).fetchall()
    con.close()
    return [{"role": r, "content": c} for r, c in rows]

def list_chats(user_id):
    con = db()
    rows = con.execute(
        "SELECT id,title,created_at FROM ng_chats WHERE user_id=? ORDER BY id DESC",
        (user_id,)
    ).fetchall()
    con.close()
    return rows

def rename_chat(chat_id, title):
    con = db()
    con.execute(
        "UPDATE ng_chats SET title=? WHERE id=?",
        (title[:80], chat_id)
    )
    con.commit()
    con.close()

def delete_chat(chat_id):
    con = db()
    con.execute("DELETE FROM ng_messages WHERE chat_id=?", (chat_id,))
    con.execute("DELETE FROM ng_chats WHERE id=?", (chat_id,))
    con.commit()
    con.close()


# ============================================================
# AUTH SCREEN
# ============================================================

def auth_screen():
    st.markdown("""
    <div class="hero">
      <h1>🚀 NEXTGEN AI</h1>
      <p>Your intelligent digital universe.</p>
    </div>
    """, unsafe_allow_html=True)

    login_tab, register_tab = st.tabs(["Login", "Create Account"])

    with login_tab:
        with st.form("login_form"):
            username = st.text_input("Username")
            password = st.text_input("Password", type="password")
            submit = st.form_submit_button("Login", use_container_width=True)

        if submit:
            user_id = login_user(username, password)
            if user_id:
                st.session_state.user_id = user_id
                st.session_state.username = username
                st.session_state.authenticated = True
                st.rerun()
            else:
                st.error("Invalid username or password.")

    with register_tab:
        with st.form("register_form"):
            new_user = st.text_input("Choose username")
            new_pass = st.text_input("Create password", type="password")
            confirm = st.text_input("Confirm password", type="password")
            submit_reg = st.form_submit_button(
                "Create Account",
                use_container_width=True
            )

        if submit_reg:
            if new_pass != confirm:
                st.error("Passwords do not match.")
            else:
                ok, message = register_user(new_user, new_pass)
                if ok:
                    st.success(message)
                else:
                    st.error(message)


# ============================================================
# DASHBOARD
# ============================================================

def dashboard():
    st.markdown("""
    <div class="hero">
      <h1>NEXTGEN AI</h1>
      <p>One intelligent platform. Endless possibilities.</p>
    </div>
    """, unsafe_allow_html=True)

    st.subheader("Welcome back, " + str(st.session_state.username))

    cols = st.columns(4)
    modules = [
        ("💬", "AI Chat", "Intelligent conversations"),
        ("📈", "Stock Market", "Market data and analysis"),
        ("🎨", "AI Image", "Generate and edit images"),
        ("🎙️", "Voice Studio", "Speak with AI")
    ]

    for col, item in zip(cols, modules):
        with col:
            st.markdown(
                f'<div class="panel"><h2>{item[0]}</h2>'
                f'<b>{item[1]}</b><p class="small-muted">{item[2]}</p></div>',
                unsafe_allow_html=True
            )

    st.subheader("API Connection Center")
    status = api_status()

    cols = st.columns(len(status))
    for col, (name, connected) in zip(cols, status.items()):
        with col:
            st.metric(name, "Connected" if connected else "Not configured")

    st.divider()
    st.subheader("Explore NEXTGEN AI")

    items = [
        ("AI Chat", "💬"),
        ("Stock Market", "📈"),
        ("AI Vision", "👁️"),
        ("PDF Assistant", "📄"),
        ("Image Studio", "🎨"),
        ("Web Search", "🌐"),
        ("Voice Studio", "🎙️"),
        ("Coding Lab", "💻"),
        ("Study Assistant", "📚"),
        ("Video Studio", "🎬"),
        ("AI Tools", "🧰")
    ]

    cols = st.columns(4)
    for i, (name, icon) in enumerate(items):
        with cols[i % 4]:
            if st.button(f"{icon} {name}", key=f"dash_{i}", use_container_width=True):
                st.session_state.page = name
                st.rerun()


# ============================================================
# CHAT PAGE
# ============================================================

def chat_page():
    st.title("💬 AI Chat")
    st.caption("Powered by Groq / Gemini")

    chats = list_chats(st.session_state.user_id)

    with st.sidebar:
        st.subheader("Chat History")

        if st.button("＋ New Chat", use_container_width=True):
            st.session_state.chat_id = create_chat(st.session_state.user_id)
            st.session_state.messages = []
            st.rerun()

        for cid, title, created in chats:
            c1, c2 = st.columns([5, 1])
            with c1:
                if st.button(title or "New Chat", key=f"open_{cid}"):
                    st.session_state.chat_id = cid
                    st.session_state.messages = load_messages(cid)
                    st.rerun()
            with c2:
                if st.button("⋯", key=f"menu_{cid}"):
                    st.session_state["manage_chat"] = cid

        if st.session_state.get("manage_chat"):
            selected = st.session_state.manage_chat
            st.caption("Manage selected conversation")
            new_title = st.text_input("Rename conversation", key="rename_input")
            if st.button("Save name"):
                rename_chat(selected, new_title)
                st.session_state.manage_chat = None
                st.rerun()
            if st.button("Delete conversation"):
                delete_chat(selected)
                st.session_state.chat_id = None
                st.session_state.messages = []
                st.session_state.manage_chat = None
                st.rerun()

    if not st.session_state.chat_id:
        st.session_state.chat_id = create_chat(st.session_state.user_id)
        st.session_state.messages = []

    if not st.session_state.messages:
        st.markdown("""
        <div class="panel">
        <h3>What can I help you with today?</h3>
        <p class="small-muted">
        Ask questions, learn, write code, analyze documents or explore ideas.
        </p>
        </div>
        """, unsafe_allow_html=True)

    for index, msg in enumerate(st.session_state.messages):
        with st.chat_message(msg["role"]):
            st.markdown(msg["content"])

            if msg["role"] == "assistant":
                with st.expander("Response actions"):
                    st.code(msg["content"])
                    if st.button("🔊 Read Aloud", key=f"read_{index}"):
                        try:
                            audio = text_to_speech(msg["content"])
                            st.audio(audio, format="audio/mp3")
                        except Exception as e:
                            st.warning(str(e))

    uploaded = st.file_uploader(
        "Attach files to your next message",
        type=["png", "jpg", "jpeg", "webp", "pdf", "txt"],
        accept_multiple_files=True,
        key="chat_files"
    )

    prompt = st.chat_input(
        "Message NEXTGEN AI...",
        accept_file=False
    )

    if prompt:
        if not prompt.strip():
            st.stop()

        attachments = []
        image_context = ""

        for file in uploaded or []:
            if file.type == "application/pdf" and PdfReader:
                try:
                    reader = PdfReader(io.BytesIO(file.getvalue()))
                    text = "\n".join(
                        page.extract_text() or "" for page in reader.pages
                    )
                    attachments.append(
                        f"PDF {file.name} CONTENT:\n{text[:12000]}"
                    )
                except Exception as e:
                    attachments.append(f"Could not read PDF: {e}")

            elif file.type.startswith("text/"):
                attachments.append(
                    f"FILE {file.name}:\n{file.getvalue().decode(errors='ignore')[:10000]}"
                )

            elif file.type.startswith("image/"):
                try:
                    image_context += "\nIMAGE ANALYSIS:\n"
                    image_context += analyze_image(
                        file.getvalue(), file.type,
                        "Describe this image and extract relevant information."
                    )
                except Exception as e:
                    image_context += f"\nImage analysis unavailable: {e}"

        full_prompt = prompt
        if attachments:
            full_prompt += "\n\nATTACHED DOCUMENTS:\n" + "\n".join(attachments)
        if image_context:
            full_prompt += "\n\n" + image_context

        st.session_state.messages.append({
            "role": "user",
            "content": prompt
        })
        save_message(st.session_state.chat_id, "user", prompt)

        with st.chat_message("user"):
            st.markdown(prompt)

        with st.chat_message("assistant"):
            with st.spinner("NEXTGEN AI is thinking..."):
                try:
                    response, provider = ask_ai(
                        full_prompt,
                        st.session_state.messages[:-1]
                    )
                    st.markdown(response)
                    st.caption("AI Engine: " + provider)

                    st.session_state.messages.append({
                        "role": "assistant",
                        "content": response
                    })
                    save_message(
                        st.session_state.chat_id,
                        "assistant",
                        response
                    )
                    st.session_state.last_response = response

                except Exception as e:
                    st.error(str(e))

        st.rerun()


# ============================================================
# STOCK MARKET PAGE
# ============================================================

def stock_page():
    st.title("📈 Global Stock Market")
    st.caption("Market information powered by Finnhub API")

    if not FINNHUB_KEY:
        st.error("FINNHUB_API_KEY configure करो।")
        return

    tabs = st.tabs([
        "Market Overview",
        "Stock Analysis",
        "Company Search",
        "Watchlist",
        "Market News"
    ])

    with tabs[0]:
        st.subheader("Market Watch")

        symbols = [
            "AAPL", "MSFT", "NVDA",
            "RELIANCE.NS", "TCS.NS", "INFY.NS",
            "^NSEI", "^BSESN", "^IXIC"
        ]

        for start in range(0, len(symbols), 3):
            cols = st.columns(3)
            for col, symbol in zip(cols, symbols[start:start+3]):
                with col:
                    try:
                        q = stock_quote(symbol)
                        price = q.get("c", 0)
                        change = q.get("dp", 0)
                        st.metric(
                            symbol,
                            f"{price:,.2f}" if price else "Unavailable",
                            f"{change:.2f}%" if change else None
                        )
                    except Exception:
                        st.metric(symbol, "Not supported / unavailable")

        st.info(
            "Finnhub exchange coverage और API plan के अनुसार कुछ Indian "
            "indices या symbols उपलब्ध न भी हों।"
        )

    with tabs[1]:
        st.subheader("Advanced Stock Analysis")

        symbol = st.text_input(
            "Enter ticker symbol",
            value=st.session_state.stock_symbol
        ).strip().upper()

        period = st.selectbox(
            "Chart period",
            ["1 Month", "3 Months", "6 Months", "1 Year", "2 Years"],
            index=2
        )

        days = {
            "1 Month": 30,
            "3 Months": 90,
            "6 Months": 180,
            "1 Year": 365,
            "2 Years": 730
        }[period]

        if st.button("Analyze Stock"):
            st.session_state.stock_symbol = symbol

        try:
            q = stock_quote(symbol)
            profile = stock_profile(symbol)

            c1, c2, c3, c4 = st.columns(4)
            c1.metric("Current Price", f"{q.get('c', 0):,.2f}")
            c2.metric("Change %", f"{q.get('dp', 0):.2f}%")
            c3.metric("Day High", f"{q.get('h', 0):,.2f}")
            c4.metric("Day Low", f"{q.get('l', 0):,.2f}")

            st.markdown("### Company Profile")
            st.write({
                "Name": profile.get("name", symbol),
                "Exchange": profile.get("exchange", "N/A"),
                "Industry": profile.get("finnhubIndustry", "N/A"),
                "Country": profile.get("country", "N/A"),
                "Currency": profile.get("currency", "N/A"),
                "Market Capitalization": profile.get("marketCapitalization", "N/A")
            })

            candles = stock_candles(symbol, "D", days)
            df = candle_dataframe(candles)

            if not df.empty:
                fig = go.Figure()
                fig.add_trace(go.Candlestick(
                    x=df["Time"],
                    open=df["Open"],
                    high=df["High"],
                    low=df["Low"],
                    close=df["Close"],
                    name=symbol
                ))
                fig.update_layout(
                    title=f"{symbol} — {period}",
                    template="plotly_dark",
                    height=500,
                    xaxis_rangeslider_visible=False
                )
                st.plotly_chart(fig, use_container_width=True)

                st.subheader("Historical Data")
                st.dataframe(df.tail(30), use_container_width=True)
                st.download_button(
                    "Download Historical CSV",
                    df.to_csv(index=False),
                    file_name=f"{symbol}_history.csv",
                    mime="text/csv"
                )
            else:
                st.warning("Historical candles unavailable for this symbol.")

        except Exception as e:
            st.error(f"Stock data error: {e}")

    with tabs[2]:
        st.subheader("Find Companies")
        query = st.text_input("Company name or ticker")

        if st.button("Search Companies"):
            try:
                results = stock_search(query)
                matches = results.get("result", [])
                if matches:
                    st.dataframe(
                        pd.DataFrame(matches),
                        use_container_width=True
                    )
                else:
                    st.info("No matching companies found.")
            except Exception as e:
                st.error(str(e))

    with tabs[3]:
        st.subheader("Your Watchlist")

        new_symbol = st.text_input("Add ticker to watchlist")
        if st.button("Add to Watchlist"):
            if new_symbol:
                add_watchlist(st.session_state.user_id, new_symbol)
                st.success("Added.")
                st.rerun()

        watchlist = get_watchlist(st.session_state.user_id)

        if not watchlist:
            watchlist = DEFAULT_STOCKS
            st.caption("Showing suggested symbols. Add your own to save them.")

        for symbol in watchlist:
            col1, col2, col3 = st.columns([3, 2, 1])
            with col1:
                st.write("**" + symbol + "**")
            with col2:
                try:
                    q = stock_quote(symbol)
                    st.write(f"{q.get('c', 0):,.2f} ({q.get('dp', 0):.2f}%)")
                except Exception:
                    st.write("Unavailable")
            with col3:
                if st.button("Remove", key="remove_" + symbol):
                    remove_watchlist(st.session_state.user_id, symbol)
                    st.rerun()

    with tabs[4]:
        st.subheader("Company News")
        news_symbol = st.text_input("News ticker", value="AAPL")

        if st.button("Load News"):
            try:
                news = stock_news(news_symbol)
                for item in news[:15]:
                    st.markdown(f"### {item.get('headline','News')}")
                    st.write(item.get("summary", ""))
                    if item.get("url"):
                        st.markdown(f"[Read Article]({item['url']})")
                    st.caption(
                        datetime.datetime.fromtimestamp(
                            item.get("datetime", 0)
                        ).strftime("%d %b %Y %H:%M")
                    )
                    st.divider()
            except Exception as e:
                st.error(str(e))

    st.caption(
        "Educational market-data tool. Data coverage, delays and available "
        "symbols depend on Finnhub plan and exchange support. Not investment advice."
    )


# ============================================================
# AI VISION
# ============================================================

def vision_page():
    st.title("👁️ AI Vision")
    st.write("Upload an image and ask NEXTGEN AI to understand it.")

    image = st.file_uploader(
        "Upload image",
        type=["png", "jpg", "jpeg", "webp"]
    )
    question = st.text_area(
        "What should I analyze?",
        "Describe this image in detail."
    )

    if image:
        st.image(image, use_container_width=True)

    if st.button("Analyze Image", type="primary"):
        if not image:
            st.warning("Upload an image first.")
        else:
            with st.spinner("Analyzing image..."):
                try:
                    result = analyze_image(
                        image.getvalue(),
                        image.type,
                        question
                    )
                    st.markdown("### Analysis")
                    st.write(result)
                except Exception as e:
                    st.error(str(e))


# ============================================================
# PDF ASSISTANT
# ============================================================

def pdf_page():
    st.title("📄 PDF Intelligence")

    if PdfReader is None:
        st.error("Install pypdf.")
        return

    pdf = st.file_uploader("Upload PDF", type=["pdf"])
    if not pdf:
        return

    try:
        reader = PdfReader(io.BytesIO(pdf.getvalue()))
        st.success(f"{len(reader.pages)} pages loaded.")

        page_text = []
        for i, page in enumerate(reader.pages):
            page_text.append(page.extract_text() or "")

        document = "\n\n".join(page_text)
        st.text_area(
            "Extracted text preview",
            document[:5000],
            height=200
        )

        question = st.text_area(
            "Ask a question about this PDF",
            "Summarize this document and explain its important points."
        )

        if st.button("Ask PDF Assistant"):
            with st.spinner("Reading document..."):
                try:
                    answer, provider = ask_ai(
                        "DOCUMENT:\n" + document[:25000] +
                        "\n\nQUESTION:\n" + question
                    )
                    st.markdown("### Answer")
                    st.write(answer)
                    st.caption("Powered by " + provider)
                except Exception as e:
                    st.error(str(e))

        st.download_button(
            "Download Extracted Text",
            document,
            file_name="extracted_document.txt"
        )

    except Exception as e:
        st.error(f"PDF error: {e}")


# ============================================================
# IMAGE STUDIO
# ============================================================

def image_page():
    st.title("🎨 AI Image Studio")

    generate_tab, edit_tab = st.tabs([
        "Generate Image",
        "Edit Image"
    ])

    with generate_tab:
        st.subheader("Text to Image")

        prompt = st.text_area(
            "Describe your image",
            placeholder="A futuristic city at night, cinematic lighting..."
        )

        col1, col2 = st.columns(2)
        with col1:
            width = st.selectbox(
                "Width",
                [512, 768, 1024],
                index=2
            )
        with col2:
            height = st.selectbox(
                "Height",
                [512, 768, 1024],
                index=2
            )

        steps = st.slider("Inference steps", 1, 8, 4)

        if st.button("Generate Image", type="primary"):
            if not prompt.strip():
                st.warning("Enter an image prompt.")
            else:
                with st.spinner("Creating image..."):
                    try:
                        image_data = cloudflare_image(
                            prompt, width, height, steps
                        )
                        st.image(image_data, use_container_width=True)
                        st.download_button(
                            "Download Image",
                            image_data,
                            file_name="nextgen_generated.png",
                            mime="image/png"
                        )
                    except Exception as e:
                        st.error(str(e))

    with edit_tab:
        st.subheader("AI Image Editing")

        source = st.file_uploader(
            "Upload image to edit",
            type=["png", "jpg", "jpeg", "webp"],
            key="edit_image"
        )

        edit_prompt = st.text_area(
            "Editing instructions",
            placeholder="Change the background to a futuristic city..."
        )

        if source:
            st.image(source, caption="Original image", use_container_width=True)

        if st.button("Edit Image"):
            if not source or not edit_prompt.strip():
                st.warning("Upload an image and enter editing instructions.")
            else:
                with st.spinner("Editing image..."):
                    try:
                        result = cloudflare_edit(
                            edit_prompt,
                            source.getvalue()
                        )
                        st.image(result, use_container_width=True)
                        st.download_button(
                            "Download Edited Image",
                            result,
                            file_name="nextgen_edited.png",
                            mime="image/png"
                        )
                    except Exception as e:
                        st.error(str(e))


# ============================================================
# WEB SEARCH
# ============================================================

def web_page():
    st.title("🌐 AI Web Search")

    query = st.text_input("Search the web")
    if st.button("Search"):
        if not query.strip():
            st.warning("Enter a search query.")
        else:
            with st.spinner("Searching..."):
                try:
                    results = web_search(query)
                    st.session_state.web_results = results
                    st.markdown(results)
                except Exception as e:
                    st.error(str(e))


# ============================================================
# VOICE STUDIO
# ============================================================

def voice_page():
    st.title("🎙️ Voice Studio")
    st.write("Record a voice message, transcribe it and send it to AI.")

    st.info(
        "यह push-to-talk voice workflow है। Continuous real-time phone-call "
        "जैसा WebRTC Live Call अलग integration मांगता है।"
    )

    audio = st.audio_input("Record your voice")

    if audio:
        audio_bytes = audio.getvalue()
        st.audio(audio_bytes)

        if st.button("Transcribe Recording"):
            with st.spinner("Converting speech to text..."):
                try:
                    transcript = transcribe_audio(audio_bytes)
                    st.session_state.voice_text = transcript
                    st.success("Transcription complete.")
                except Exception as e:
                    st.error(str(e))

    if st.session_state.voice_text:
        transcript = st.text_area(
            "Recognized speech",
            value=st.session_state.voice_text,
            height=120
        )

        if st.button("Ask NEXTGEN AI"):
            try:
                response, provider = ask_ai(transcript)
                st.markdown("### AI Response")
                st.write(response)
                st.caption(provider)

                if st.button("Speak Response"):
                    audio_output = text_to_speech(response)
                    st.audio(audio_output, format="audio/mp3")
            except Exception as e:
                st.error(str(e))


# ============================================================
# CODING LAB
# ============================================================

def coding_page():
    st.title("💻 NEXTGEN Coding Lab")

    mode = st.selectbox(
        "Choose coding task",
        [
            "Generate Code",
            "Debug Code",
            "Explain Code",
            "Build Project Plan",
            "Optimize Code"
        ]
    )

    language = st.selectbox(
        "Programming language",
        ["Python", "JavaScript", "HTML/CSS", "Java", "C++", "SQL", "Other"]
    )

    code = st.text_area(
        "Describe your task or paste your code",
        height=220
    )

    if st.button("Run AI Coding Assistant"):
        if not code.strip():
            st.warning("Enter your task or code.")
        else:
            prompt = f"""
            Task: {mode}
            Programming language: {language}
            User input:
            {code}

            Provide a correct, well-commented and structured solution.
            Explain how to use it.
            """
            try:
                answer, provider = ask_ai(prompt)
                st.markdown(answer)
                st.caption(provider)
            except Exception as e:
                st.error(str(e))


# ============================================================
# STUDY ASSISTANT
# ============================================================

def study_page():
    st.title("📚 AI Study Assistant")

    subject = st.selectbox(
        "Subject",
        [
            "Mathematics",
            "Science",
            "Physics",
            "Chemistry",
            "Biology",
            "English",
            "Hindi",
            "History",
            "Geography",
            "Computer Science",
            "General Knowledge"
        ]
    )

    grade = st.selectbox(
        "Learning level",
        ["Class 6", "Class 7", "Class 8", "Class 9",
         "Class 10", "Class 11", "Class 12", "Advanced"]
    )

    mode = st.selectbox(
        "Study mode",
        [
            "Explain Topic",
            "Make Short Notes",
            "Create MCQ Quiz",
            "Create Practice Questions",
            "Explain Difficult Questions",
            "Revision Plan"
        ]
    )

    topic = st.text_area("Enter topic or question")

    if st.button("Start Learning"):
        if not topic.strip():
            st.warning("Enter a topic.")
        else:
            prompt = f"""
            Subject: {subject}
            Level: {grade}
            Mode: {mode}
            Topic: {topic}

            Teach clearly with examples, key definitions and a useful structure.
            For quizzes, provide answers separately after questions.
            """
            try:
                answer, provider = ask_ai(prompt)
                st.markdown(answer)
                st.caption(provider)
            except Exception as e:
                st.error(str(e))


# ============================================================
# VIDEO STUDIO
# ============================================================

def video_page():
    st.title("🎬 AI Video Studio")

    platform = st.selectbox(
        "Platform",
        ["YouTube", "YouTube Shorts", "Instagram Reels", "TikTok", "Advertisement"]
    )

    duration = st.slider("Video duration (seconds)", 10, 180, 30)
    ratio = st.selectbox("Aspect ratio", ["9:16", "16:9", "1:1"])
    style = st.selectbox(
        "Video style",
        [
            "Cinematic",
            "Realistic",
            "3D Animation",
            "Documentary",
            "Funny",
            "Professional Advertisement",
            "Storytelling"
        ]
    )

    idea = st.text_area("Describe your video idea")

    if st.button("Create Video Production Plan"):
        if not idea.strip():
            st.warning("Enter an idea.")
        else:
            prompt = f"""
            Create a complete video production plan.
            Platform: {platform}
            Duration: {duration} seconds
            Ratio: {ratio}
            Style: {style}
            Idea: {idea}

            Include:
            1. Hook
            2. Scene-by-scene timeline
            3. Image prompts
            4. Video generation prompts
            5. Dialogue and voiceover
            6. Camera movements
            7. Sound effects
            8. Background music direction
            9. Editing instructions
            """
            try:
                answer, provider = ask_ai(prompt)
                st.markdown(answer)
                st.caption(provider)
            except Exception as e:
                st.error(str(e))


# ============================================================
# AI TOOLS
# ============================================================

def tools_page():
    st.title("🧰 AI Tool Center")

    tool = st.selectbox(
        "Select tool",
        [
            "Email Writer",
            "Content Writer",
            "Grammar Corrector",
            "Translator",
            "Summarizer",
            "Social Media Caption",
            "Business Idea Generator",
            "Presentation Outline",
            "Professional Bio",
            "Interview Practice",
            "Project Planner"
        ]
    )

    text_input = st.text_area("Enter your text or requirements", height=180)

    if st.button("Generate"):
        if not text_input.strip():
            st.warning("Enter some text.")
        else:
            try:
                answer, provider = ask_ai(
                    f"Tool: {tool}\nUser requirements:\n{text_input}"
                )
                st.markdown(answer)
                st.caption(provider)
            except Exception as e:
                st.error(str(e))


# ============================================================
# SETTINGS
# ============================================================

def settings_page():
    st.title("⚙️ Settings")

    st.subheader("API Status")
    for name, connected in api_status().items():
        st.write(
            ("🟢 " if connected else "🔴 ") +
            name + (" connected" if connected else " not configured")
        )

    st.divider()
    st.subheader("AI Configuration")
    st.write("Groq model:", GROQ_MODEL)
    st.write("Gemini model:", GEMINI_MODEL)

    st.divider()
    st.subheader("Account")
    st.write("Username:", st.session_state.username)

    if st.button("Logout"):
        for key in list(st.session_state.keys()):
            del st.session_state[key]
        st.rerun()


# ============================================================
# ABOUT
# ============================================================

def about_page():
    st.title("🚀 About NEXTGEN AI")

    st.markdown("""
    <div class="hero">
      <h1>NEXTGEN AI</h1>
      <p>One Platform. Multiple Intelligence Experiences.</p>
    </div>
    """, unsafe_allow_html=True)

    st.markdown("""
    NEXTGEN AI is a multi-module AI platform designed to bring together:

    - Intelligent conversations
    - Voice-based interaction
    - Stock market data and educational analysis
    - Image generation and editing
    - Computer vision
    - PDF intelligence
    - Web search
    - Coding assistance
    - Study assistance
    - Video production planning

    **Built with Python, Streamlit, SQLite and connected AI services.**

    This project is an educational and productivity platform.
    Financial information is not personalized investment advice.
    """)


# ============================================================
# MAIN ROUTER
# ============================================================

def main():
    if not st.session_state.authenticated:
        auth_screen()
        return

    pages = [
        "Dashboard",
        "AI Chat",
        "Stock Market",
        "AI Vision",
        "PDF Assistant",
        "Image Studio",
        "Web Search",
        "Voice Studio",
        "Coding Lab",
        "Study Assistant",
        "Video Studio",
        "AI Tools",
        "Settings",
        "About"
    ]

    with st.sidebar:
        st.markdown("## 🚀 NEXTGEN AI")
        st.caption("MAX ULTRA EDITION")
        st.divider()

        st.write("Signed in as")
        st.markdown("**" + str(st.session_state.username) + "**")

        selected = st.radio(
            "Navigation",
            pages,
            index=pages.index(st.session_state.page)
            if st.session_state.page in pages else 0
        )

        st.session_state.page = selected

        st.divider()
        st.caption("AI Services")
        for name, connected in api_status().items():
            st.write(
                ("🟢 " if connected else "⚪ ") + name
            )

        st.divider()
        if st.button("Logout", use_container_width=True):
            st.session_state.authenticated = False
            st.session_state.user_id = None
            st.session_state.username = None
            st.session_state.chat_id = None
            st.session_state.messages = []
            st.rerun()

        st.caption("NEXTGEN AI • 2026")

    page = st.session_state.page

    if page == "Dashboard":
        dashboard()
    elif page == "AI Chat":
        chat_page()
    elif page == "Stock Market":
        stock_page()
    elif page == "AI Vision":
        vision_page()
    elif page == "PDF Assistant":
        pdf_page()
    elif page == "Image Studio":
        image_page()
    elif page == "Web Search":
        web_page()
    elif page == "Voice Studio":
        voice_page()
    elif page == "Coding Lab":
        coding_page()
    elif page == "Study Assistant":
        study_page()
    elif page == "Video Studio":
        video_page()
    elif page == "AI Tools":
        tools_page()
    elif page == "Settings":
        settings_page()
    elif page == "About":
        about_page()


if __name__ == "__main__":
    main()
