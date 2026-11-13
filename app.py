
# ============================================================
# NEXTGEN AI — MAX ULTRA PRO
# ============================================================

import os
import io
import re
import time
import json
import base64
import hashlib
import sqlite3
import secrets
import datetime

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

try:
    import extra_streamlit_components as stx
except Exception:
    stx = None

# ============================================================
# CONFIGURATION
# ============================================================

st.set_page_config(
    page_title="NEXTGEN AI",
    page_icon="🚀",
    layout="wide",
    initial_sidebar_state="expanded"
)

APP_NAME = "NEXTGEN AI"
DB_PATH = "nextgen_ai.db"

def env(key, default=""):
    try:
        value = st.secrets.get(key, "")
        if value:
            return str(value)
    except Exception:
        pass
    return os.getenv(key, default)

GROQ_KEY = env("GROQ_API_KEY")
GEMINI_KEY = env("GEMINI_API_KEY")
FINNHUB_KEY = env("FINNHUB_API_KEY")
TAVILY_KEY = env("TAVILY_API_KEY")
CF_ACCOUNT = env("CLOUDFLARE_ACCOUNT_ID")
CF_TOKEN = env("CLOUDFLARE_API_TOKEN")

GROQ_MODEL = env("GROQ_MODEL", "openai/gpt-oss-120b")
GEMINI_MODEL = env("GEMINI_MODEL", "gemini-2.5-flash")

# ============================================================
# UI THEME
# ============================================================

st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&display=swap');

html,body,[class*="css"] {
    font-family: Inter,sans-serif;
}
.stApp {
    background:
    radial-gradient(circle at 10% 5%,rgba(55,50,150,.19),transparent 30%),
    radial-gradient(circle at 90% 20%,rgba(0,180,200,.10),transparent 25%),
    #080b14;
    color:#f4f6ff;
}
[data-testid="stSidebar"] {
    background:#0d1220;
    border-right:1px solid #202a40;
}
.hero {
    padding:30px;
    border-radius:22px;
    background:linear-gradient(120deg,#161d38,#102a3d,#191c38);
    border:1px solid #34415e;
    margin-bottom:20px;
}
.hero h1 {
    font-size:42px;
    font-weight:800;
    margin:0;
    background:linear-gradient(90deg,#8be9ff,#b6a2ff,#fff);
    -webkit-background-clip:text;
    color:transparent;
}
.hero p {color:#aab8d5;font-size:16px;}
.panel {
    padding:18px;
    background:rgba(20,27,45,.88);
    border:1px solid #293650;
    border-radius:16px;
    margin-bottom:12px;
}
.small-muted {color:#93a3c1;font-size:13px;}
div.stButton>button {
    border-radius:10px;
    border:1px solid #344566;
    background:linear-gradient(110deg,#25375d,#25304d);
    color:white;
    font-weight:600;
}
div.stButton>button:hover {
    border-color:#68dfff;
    color:#8be9ff;
}
[data-testid="stChatMessage"] {
    background:rgba(22,29,48,.75);
    border:1px solid #27334c;
    border-radius:15px;
    padding:12px;
}
hr {border-color:#28344c;}
</style>
""", unsafe_allow_html=True)

# ============================================================
# DATABASE
# ============================================================

def db():
    con = sqlite3.connect(DB_PATH, check_same_thread=False)
    con.execute("PRAGMA foreign_keys=ON")
    return con

def init_db():
    con = db()
    cur = con.cursor()

    cur.execute("""
    CREATE TABLE IF NOT EXISTS ng_users(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT UNIQUE NOT NULL,
        password_hash TEXT NOT NULL,
        salt TEXT NOT NULL,
        created_at TEXT
    )
    """)

    cur.execute("""
    CREATE TABLE IF NOT EXISTS ng_chats(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL,
        title TEXT,
        created_at TEXT
    )
    """)

    cur.execute("""
    CREATE TABLE IF NOT EXISTS ng_messages(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        chat_id INTEGER NOT NULL,
        role TEXT NOT NULL,
        content TEXT NOT NULL,
        created_at TEXT
    )
    """)

    cur.execute("""
    CREATE TABLE IF NOT EXISTS ng_watchlist(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER,
        symbol TEXT,
        UNIQUE(user_id,symbol)
    )
    """)

    cur.execute("""
    CREATE TABLE IF NOT EXISTS ng_sessions(
        token_hash TEXT PRIMARY KEY,
        user_id INTEGER NOT NULL,
        expires_at TEXT NOT NULL,
        created_at TEXT
    )
    """)

    con.commit()
    con.close()

init_db()

# ============================================================
# AUTHENTICATION
# ============================================================

def hash_password(password, salt):
    return hashlib.pbkdf2_hmac(
        "sha256",
        password.encode(),
        salt.encode(),
        260000
    ).hex()

def register_user(username, password):
    username = username.strip()

    if not re.fullmatch(r"[A-Za-z0-9_.-]{3,30}", username):
        return False, "Username must be 3–30 characters."

    if len(password) < 8:
        return False, "Password must have at least 8 characters."

    salt = secrets.token_hex(16)
    hashed = hash_password(password, salt)

    try:
        con = db()
        con.execute("""
        INSERT INTO ng_users(username,password_hash,salt,created_at)
        VALUES(?,?,?,?)
        """, (
            username,
            hashed,
            salt,
            str(datetime.datetime.now())
        ))
        con.commit()
        con.close()
        return True, "Account created successfully."
    except sqlite3.IntegrityError:
        return False, "Username already exists."

def login_user(username, password):
    con = db()
    row = con.execute("""
        SELECT id,password_hash,salt
        FROM ng_users WHERE username=?
    """, (username.strip(),)).fetchone()
    con.close()

    if not row:
        return None

    if secrets.compare_digest(
        hash_password(password, row[2]),
        row[1]
    ):
        return row[0]

    return None

def create_guest():
    username = "guest_" + secrets.token_hex(8)
    password = secrets.token_urlsafe(32)
    salt = secrets.token_hex(16)

    con = db()
    cur = con.cursor()
    cur.execute("""
    INSERT INTO ng_users(username,password_hash,salt,created_at)
    VALUES(?,?,?,?)
    """, (
        username,
        hash_password(password, salt),
        salt,
        str(datetime.datetime.now())
    ))
    user_id = cur.lastrowid
    con.commit()
    con.close()

    return user_id

def transfer_guest_data(guest_id, account_id):
    if not guest_id or guest_id == account_id:
        return

    con = db()
    con.execute(
        "UPDATE ng_chats SET user_id=? WHERE user_id=?",
        (account_id, guest_id)
    )
    con.execute("""
        INSERT OR IGNORE INTO ng_watchlist(user_id,symbol)
        SELECT ?,symbol FROM ng_watchlist WHERE user_id=?
    """, (account_id, guest_id))
    con.execute(
        "DELETE FROM ng_watchlist WHERE user_id=?",
        (guest_id,)
    )
    con.commit()
    con.close()

# ============================================================
# REMEMBER LOGIN
# ============================================================

cookie_manager = None

if stx:
    try:
        cookie_manager = stx.CookieManager(key="nextgen_cookie_manager")
    except Exception:
        pass

def token_hash(token):
    return hashlib.sha256(token.encode()).hexdigest()

def create_session(user_id):
    token = secrets.token_urlsafe(40)
    expiry = datetime.datetime.now(
        datetime.timezone.utc
    ) + datetime.timedelta(days=30)

    con = db()
    con.execute("""
    INSERT INTO ng_sessions(token_hash,user_id,expires_at,created_at)
    VALUES(?,?,?,?)
    """, (
        token_hash(token),
        user_id,
        expiry.isoformat(),
        datetime.datetime.now().isoformat()
    ))
    con.commit()
    con.close()

    st.session_state.session_token = token

    if cookie_manager:
        try:
            cookie_manager.set(
                "nextgen_session",
                token,
                expires_at=expiry,
                key="save_session"
            )
        except Exception:
            pass

def restore_session():
    if st.session_state.get("authenticated"):
        return

    if not cookie_manager:
        return

    try:
        token = cookie_manager.get("nextgen_session")
    except Exception:
        token = None

    if not token:
        return

    con = db()
    row = con.execute("""
        SELECT user_id,expires_at
        FROM ng_sessions WHERE token_hash=?
    """, (token_hash(token),)).fetchone()

    if not row:
        con.close()
        return

    try:
        expiry = datetime.datetime.fromisoformat(row[1])
        if expiry < datetime.datetime.now(datetime.timezone.utc):
            con.execute(
                "DELETE FROM ng_sessions WHERE token_hash=?",
                (token_hash(token),)
            )
            con.commit()
            con.close()
            return
    except Exception:
        con.close()
        return

    user = con.execute(
        "SELECT username FROM ng_users WHERE id=?",
        (row[0],)
    ).fetchone()
    con.close()

    if user:
        st.session_state.user_id = row[0]
        st.session_state.username = user[0]
        st.session_state.authenticated = True
        st.session_state.is_guest = user[0].startswith("guest_")

def logout():
    token = st.session_state.get("session_token")

    if token:
        con = db()
        con.execute(
            "DELETE FROM ng_sessions WHERE token_hash=?",
            (token_hash(token),)
        )
        con.commit()
        con.close()

    if cookie_manager:
        try:
            cookie_manager.delete("nextgen_session")
        except Exception:
            pass

    for key in list(st.session_state.keys()):
        del st.session_state[key]

    st.rerun()

# ============================================================
# SESSION STATE
# ============================================================

defaults = {
    "user_id": None,
    "username": None,
    "page": "Dashboard",
    "chat_id": None,
    "messages": [],
    "authenticated": False,
    "is_guest": False,
    "last_response": "",
    "last_prompt": "",
    "web_results": "",
    "voice_text": "",
    "session_token": None
}

for key, value in defaults.items():
    if key not in st.session_state:
        st.session_state[key] = value

restore_session()

# ============================================================
# API CLIENTS
# ============================================================

def api_status():
    return {
        "Groq": bool(GROQ_KEY and Groq),
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
You are NEXTGEN AI, an intelligent multilingual assistant.
Answer clearly and accurately.
Use the user's language.
Explain difficult concepts step by step.
Do not invent facts or live data.
For finance, provide educational information, not personalized investment advice.
"""

def ask_groq(prompt, history=None):
    client = groq_client()
    if not client:
        raise RuntimeError("Groq API key missing.")

    messages = [{"role": "system", "content": SYSTEM_PROMPT}]

    for item in (history or [])[-12:]:
        if item.get("role") in ("user", "assistant"):
            messages.append({
                "role": item["role"],
                "content": item["content"][:12000]
            })

    messages.append({"role": "user", "content": prompt})

    result = client.chat.completions.create(
        model=GROQ_MODEL,
        messages=messages,
        temperature=0.65,
        max_tokens=3500
    )

    return result.choices[0].message.content

def ask_gemini(prompt, history=None):
    client = gemini_client()
    if not client:
        raise RuntimeError("Gemini API key missing.")

    content = SYSTEM_PROMPT + "\n"

    for item in (history or [])[-10:]:
        content += (
            f"{item['role']}: {item['content'][:5000]}\n"
        )

    content += "\nuser: " + prompt

    response = client.models.generate_content(
        model=GEMINI_MODEL,
        contents=content
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
        "\n".join(errors) if errors
        else "No AI API key configured."
    )

# ============================================================
# VISION
# ============================================================

def analyze_image(image_bytes, mime_type, question):
    client = gemini_client()

    if not client or types is None:
        raise RuntimeError("Gemini API required for vision.")

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

    return response.text or "No image analysis received."

# ============================================================
# WEB SEARCH
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

    output = []

    if data.get("answer"):
        output.append("SUMMARY:\n" + data["answer"])

    for item in data.get("results", []):
        output.append(
            f"TITLE: {item.get('title')}\n"
            f"URL: {item.get('url')}\n"
            f"CONTENT: {item.get('content')}"
        )

    return "\n\n".join(output)

# ============================================================
# FINNHUB
# ============================================================

FINNHUB_BASE = "https://finnhub.io/api/v1"

def finnhub_get(endpoint, params=None):
    if not FINNHUB_KEY:
        raise RuntimeError("FINNHUB_API_KEY missing.")

    params = dict(params or {})
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

    return pd.DataFrame({
        "Time": pd.to_datetime(data["t"], unit="s"),
        "Open": data["o"],
        "High": data["h"],
        "Low": data["l"],
        "Close": data["c"],
        "Volume": data["v"]
    })

# ============================================================
# WATCHLIST
# ============================================================

def get_watchlist(user_id):
    con = db()
    rows = con.execute(
        "SELECT symbol FROM ng_watchlist WHERE user_id=?",
        (user_id,)
    ).fetchall()
    con.close()
    return [x[0] for x in rows]

def add_watchlist(user_id, symbol):
    con = db()
    con.execute(
        "INSERT OR IGNORE INTO ng_watchlist(user_id,symbol) VALUES(?,?)",
        (user_id, symbol.upper().strip())
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
# CLOUDFLARE IMAGE GENERATION
# ============================================================

def cloudflare_image(prompt, width=1024, height=1024, steps=4):
    if not CF_ACCOUNT or not CF_TOKEN:
        raise RuntimeError("Cloudflare credentials missing.")

    model = "@cf/black-forest-labs/flux-1-schnell"

    url = (
        f"https://api.cloudflare.com/client/v4/accounts/"
        f"{CF_ACCOUNT}/ai/run/{model}"
    )

    response = requests.post(
        url,
        headers={"Authorization": f"Bearer {CF_TOKEN}"},
        json={
            "prompt": prompt,
            "width": int(width),
            "height": int(height),
            "num_steps": int(steps)
        },
        timeout=180
    )
    response.raise_for_status()

    if "image" in response.headers.get("content-type", ""):
        return response.content

    image_data = response.json().get("result", {}).get("image")

    if image_data:
        return base64.b64decode(image_data)

    raise RuntimeError(response.text[:1000])

def cloudflare_edit(prompt, image_bytes):
    if not CF_ACCOUNT or not CF_TOKEN:
        raise RuntimeError("Cloudflare credentials missing.")

    model = "@cf/black-forest-labs/flux-1-kontext-pro"

    url = (
        f"https://api.cloudflare.com/client/v4/accounts/"
        f"{CF_ACCOUNT}/ai/run/{model}"
    )

    image_b64 = base64.b64encode(image_bytes).decode()

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

    if "image" in response.headers.get("content-type", ""):
        return response.content

    image_data = response.json().get("result", {}).get("image")

    if image_data:
        return base64.b64decode(image_data)

    raise RuntimeError(response.text[:1000])

# ============================================================
# VOICE
# ============================================================

def transcribe_audio(audio_bytes, filename="recording.wav"):
    if not GROQ_KEY or Groq is None:
        raise RuntimeError("Groq API key required.")

    client = groq_client()

    result = client.audio.transcriptions.create(
        file=(filename, audio_bytes),
        model="whisper-large-v3-turbo",
        response_format="text"
    )

    return str(result)

def text_to_speech(text, language="en"):
    if gTTS is None:
        raise RuntimeError("Install gTTS.")

    audio = io.BytesIO()
    gTTS(text=text[:4000], lang=language).write_to_fp(audio)
    audio.seek(0)
    return audio.read()

# ============================================================
# CHAT DATABASE FUNCTIONS
# ============================================================

def create_chat(user_id, title="New Chat"):
    con = db()
    cur = con.cursor()

    cur.execute("""
    INSERT INTO ng_chats(user_id,title,created_at)
    VALUES(?,?,?)
    """, (user_id, title, str(datetime.datetime.now())))

    chat_id = cur.lastrowid
    con.commit()
    con.close()

    return chat_id

def save_message(chat_id, role, content):
    con = db()
    con.execute("""
    INSERT INTO ng_messages(chat_id,role,content,created_at)
    VALUES(?,?,?,?)
    """, (
        chat_id,
        role,
        content,
        str(datetime.datetime.now())
    ))
    con.commit()
    con.close()

def load_messages(chat_id, user_id):
    con = db()
    rows = con.execute("""
    SELECT m.role,m.content
    FROM ng_messages m
    JOIN ng_chats c ON c.id=m.chat_id
    WHERE c.id=? AND c.user_id=?
    ORDER BY m.id
    """, (chat_id, user_id)).fetchall()

    con.close()

    return [
        {"role": role, "content": content}
        for role, content in rows
    ]

def list_chats(user_id):
    con = db()
    rows = con.execute("""
    SELECT id,title,created_at
    FROM ng_chats
    WHERE user_id=?
    ORDER BY id DESC
    """, (user_id,)).fetchall()

    con.close()
    return rows

def rename_chat(chat_id, user_id, title):
    con = db()
    con.execute(
        "UPDATE ng_chats SET title=? WHERE id=? AND user_id=?",
        (title[:80], chat_id, user_id)
    )
    con.commit()
    con.close()

def delete_chat(chat_id, user_id):
    con = db()
    con.execute("""
    DELETE FROM ng_messages
    WHERE chat_id=?
    AND EXISTS(
        SELECT 1 FROM ng_chats
        WHERE id=? AND user_id=?
    )
    """, (chat_id, chat_id, user_id))

    con.execute(
        "DELETE FROM ng_chats WHERE id=? AND user_id=?",
        (chat_id, user_id)
    )

    con.commit()
    con.close()

# ============================================================
# LOGIN / REGISTER SCREEN
# ============================================================

def auth_screen():
    st.markdown("""
    <div class="hero">
        <h1>🚀 NEXTGEN AI</h1>
        <p>Your intelligent digital universe.</p>
    </div>
    """, unsafe_allow_html=True)

    login_tab, register_tab = st.tabs([
        "Login",
        "Create Account"
    ])

    with login_tab:
        with st.form("login_form"):
            username = st.text_input("Username")
            password = st.text_input("Password", type="password")
            submit = st.form_submit_button(
                "Login",
                use_container_width=True
            )

        if submit:
            user_id = login_user(username, password)

            if user_id:
                guest_id = st.session_state.get("user_id")

                if st.session_state.get("is_guest"):
                    transfer_guest_data(guest_id, user_id)

                st.session_state.user_id = user_id
                st.session_state.username = username.strip()
                st.session_state.authenticated = True
                st.session_state.is_guest = False

                create_session(user_id)
                st.rerun()
            else:
                st.error("Invalid username or password.")

    with register_tab:
        with st.form("register_form"):
            new_user = st.text_input("Choose username")
            new_pass = st.text_input("Create password", type="password")
            confirm = st.text_input("Confirm password", type="password")

            submit = st.form_submit_button(
                "Create Account",
                use_container_width=True
            )

        if submit:
            if new_pass != confirm:
                st.error("Passwords do not match.")
            else:
                ok, message = register_user(new_user, new_pass)

                if ok:
                    user_id = login_user(new_user, new_pass)

                    if user_id:
                        if st.session_state.get("is_guest"):
                            transfer_guest_data(
                                st.session_state.user_id,
                                user_id
                            )

                        st.session_state.user_id = user_id
                        st.session_state.username = new_user.strip()
                        st.session_state.authenticated = True
                        st.session_state.is_guest = False

                        create_session(user_id)
                        st.success(message)
                        st.rerun()
                else:
                    st.error(message)

    st.divider()

    if st.button("Continue as Guest", use_container_width=True):
        user_id = create_guest()

        st.session_state.user_id = user_id
        st.session_state.username = "Guest"
        st.session_state.authenticated = True
        st.session_state.is_guest = True

        create_session(user_id)
        st.rerun()

    st.caption(
        "Guest chats are saved separately. Log in or register to transfer them."
    )

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
        ("🎨", "Image Studio", "Generate and edit images"),
        ("🎙️", "Voice Studio", "Speech and AI")
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
            st.metric(
                name,
                "Connected" if connected else "Not configured"
            )

    st.divider()
    st.subheader("Explore NEXTGEN AI")

    items = [
        ("AI Chat", "💬"),
        ("Stock Market", "📈"),
        ("Stock Market Academy", "📊"),
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
            if st.button(
                f"{icon} {name}",
                key=f"dashboard_{i}",
                use_container_width=True
            ):
                st.session_state.page = name
                st.rerun()

# ============================================================
# CHAT ATTACHMENTS
# ============================================================

def process_attachments(files):
    documents = []
    image_context = ""

    for file in files or []:
        data = file.getvalue()
        mime = file.type or ""

        if mime == "application/pdf":
            if PdfReader is None:
                documents.append("PDF reader unavailable.")
                continue

            try:
                reader = PdfReader(io.BytesIO(data))
                extracted = "\n".join(
                    page.extract_text() or ""
                    for page in reader.pages
                )
                documents.append(
                    f"PDF {file.name}:\n{extracted[:12000]}"
                )
            except Exception as e:
                documents.append(f"PDF error: {e}")

        elif mime.startswith("text/") or file.name.endswith(
            (".txt", ".md", ".csv", ".py", ".json")
        ):
            documents.append(
                f"FILE {file.name}:\n"
                + data.decode(errors="ignore")[:10000]
            )

        elif mime.startswith("image/"):
            try:
                image_context += "\n"
                image_context += analyze_image(
                    data,
                    mime,
                    "Describe this image and extract useful information."
                )
            except Exception as e:
                image_context += f"\nImage analysis error: {e}"

    return documents, image_context

# ============================================================
# AI CHAT
# ============================================================

def chat_page():
    st.title("💬 AI Chat")
    st.caption("Your intelligent AI assistant")

    user_id = st.session_state.user_id
    chats = list_chats(user_id)

    with st.sidebar:
        st.subheader("Chat History")

        if st.button("＋ New Chat", use_container_width=True):
            st.session_state.chat_id = create_chat(user_id)
            st.session_state.messages = []
            st.rerun()

        for chat_id, title, created in chats:
            col1, col2 = st.columns([5, 1])

            with col1:
                if st.button(
                    title or "New Chat",
                    key=f"open_{chat_id}",
                    use_container_width=True
                ):
                    st.session_state.chat_id = chat_id
                    st.session_state.messages = load_messages(
                        chat_id, user_id
                    )
                    st.rerun()

            with col2:
                if st.button("⋯", key=f"manage_{chat_id}"):
                    st.session_state.manage_chat = chat_id

        if st.session_state.get("manage_chat"):
            selected = st.session_state.manage_chat
            title = st.text_input("New chat title")

            if st.button("Rename"):
                rename_chat(selected, user_id, title)
                st.session_state.manage_chat = None
                st.rerun()

            if st.button("Delete chat"):
                delete_chat(selected, user_id)

                if st.session_state.chat_id == selected:
                    st.session_state.chat_id = None
                    st.session_state.messages = []

                st.session_state.manage_chat = None
                st.rerun()

    if not st.session_state.chat_id:
        st.session_state.chat_id = create_chat(user_id)
        st.session_state.messages = []

    if not st.session_state.messages:
        st.markdown("""
        <div class="panel">
        <h3>What can I help you with today?</h3>
        <p class="small-muted">
        Ask questions, learn, write code, analyze documents and explore ideas.
        </p>
        </div>
        """, unsafe_allow_html=True)

    for index, message in enumerate(st.session_state.messages):
        with st.chat_message(message["role"]):
            st.markdown(message["content"])

            if message["role"] == "assistant":
                with st.expander("Response tools"):
                    st.code(message["content"])

                    if st.button("🔊 Read Aloud", key=f"read_{index}"):
                        try:
                            audio = text_to_speech(message["content"])
                            st.audio(audio, format="audio/mp3")
                        except Exception as e:
                            st.warning(str(e))

                    if st.button("👍 Helpful", key=f"like_{index}"):
                        st.toast("Thanks for your feedback!")

                    if st.button("👎 Not helpful", key=f"dislike_{index}"):
                        st.toast("Feedback noted.")

    try:
        chat_input = st.chat_input(
            "Message NEXTGEN AI...",
            accept_file="multiple",
            file_type=[
                "png", "jpg", "jpeg", "webp",
                "pdf", "txt", "md", "csv", "py", "json"
            ]
        )
    except TypeError:
        chat_input = st.chat_input("Message NEXTGEN AI...")

    if chat_input:
        if isinstance(chat_input, str):
            prompt = chat_input.strip()
            files = []
        else:
            prompt = (chat_input.text or "").strip()
            files = chat_input.files or []

        if prompt or files:
            attachment_text, image_context = process_attachments(files)

            full_prompt = prompt or "Analyze the attached files."

            if attachment_text:
                full_prompt += (
                    "\n\nATTACHED DOCUMENTS:\n"
                    + "\n".join(attachment_text)
                )

            if image_context:
                full_prompt += "\n\nIMAGE ANALYSIS:\n" + image_context

            display_prompt = prompt or "Please analyze my attachment."

            st.session_state.messages.append({
                "role": "user",
                "content": display_prompt
            })

            save_message(
                st.session_state.chat_id,
                "user",
                display_prompt
            )

            with st.chat_message("user"):
                st.markdown(display_prompt)
                for file in files:
                    st.caption("Attached: " + file.name)

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
                        st.session_state.last_prompt = full_prompt

                    except Exception as e:
                        st.error(str(e))

            st.rerun()

    if st.session_state.get("last_prompt"):
        if st.button("🔄 Regenerate last answer"):
            history = st.session_state.messages[:-1]

            try:
                answer, provider = ask_ai(
                    st.session_state.last_prompt,
                    history
                )

                st.session_state.messages.append({
                    "role": "assistant",
                    "content": answer
                })

                save_message(
                    st.session_state.chat_id,
                    "assistant",
                    answer
                )
                st.rerun()

            except Exception as e:
                st.error(str(e))

# ============================================================
# STOCK MARKET
# ============================================================

def stock_page():
    st.title("📈 Global Stock Market")
    st.caption("Live market data through Finnhub")

    if not FINNHUB_KEY:
        st.error("FINNHUB_API_KEY is missing.")
        return

    tabs = st.tabs([
        "Market Overview",
        "Stock Analysis",
        "Company Search",
        "Watchlist",
        "Market News"
    ])

    with tabs[0]:
        symbols = [
            "AAPL", "MSFT", "NVDA",
            "RELIANCE.NS", "TCS.NS", "INFY.NS"
        ]

        for start in range(0, len(symbols), 3):
            cols = st.columns(3)

            for col, symbol in zip(cols, symbols[start:start + 3]):
                with col:
                    try:
                        quote = stock_quote(symbol)
                        st.metric(
                            symbol,
                            f"{quote.get('c', 0):,.2f}",
                            f"{quote.get('dp', 0):.2f}%"
                        )
                    except Exception:
                        st.metric(symbol, "Unavailable")

    with tabs[1]:
        symbol = st.text_input(
            "Ticker symbol",
            value="AAPL"
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
            try:
                quote = stock_quote(symbol)
                profile = stock_profile(symbol)

                cols = st.columns(4)
                cols[0].metric(
                    "Current Price",
                    f"{quote.get('c', 0):,.2f}"
                )
                cols[1].metric(
                    "Change %",
                    f"{quote.get('dp', 0):.2f}%"
                )
                cols[2].metric(
                    "Day High",
                    f"{quote.get('h', 0):,.2f}"
                )
                cols[3].metric(
                    "Day Low",
                    f"{quote.get('l', 0):,.2f}"
                )

                st.subheader("Company Profile")
                st.write({
                    "Name": profile.get("name", symbol),
                    "Exchange": profile.get("exchange", "N/A"),
                    "Industry": profile.get("finnhubIndustry", "N/A"),
                    "Country": profile.get("country", "N/A"),
                    "Currency": profile.get("currency", "N/A"),
                    "Market Cap": profile.get("marketCapitalization", "N/A")
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
                    st.dataframe(df.tail(30), use_container_width=True)

                    st.download_button(
                        "Download CSV",
                        df.to_csv(index=False),
                        file_name=f"{symbol}_history.csv",
                        mime="text/csv"
                    )

                else:
                    st.warning("Historical data unavailable.")

            except Exception as e:
                st.error(str(e))

    with tabs[2]:
        query = st.text_input("Search company or ticker")

        if st.button("Search Companies"):
            try:
                results = stock_search(query).get("result", [])
                if results:
                    st.dataframe(
                        pd.DataFrame(results),
                        use_container_width=True
                    )
                else:
                    st.info("No companies found.")
            except Exception as e:
                st.error(str(e))

    with tabs[3]:
        new_symbol = st.text_input("Add symbol to watchlist")

        if st.button("Add Symbol"):
            if new_symbol.strip():
                add_watchlist(st.session_state.user_id, new_symbol)
                st.rerun()

        watchlist = get_watchlist(st.session_state.user_id)

        for symbol in watchlist:
            cols = st.columns([3, 2, 1])

            cols[0].write("**" + symbol + "**")

            try:
                quote = stock_quote(symbol)
                cols[1].write(
                    f"{quote.get('c', 0):,.2f} ({quote.get('dp', 0):.2f}%)"
                )
            except Exception:
                cols[1].write("Unavailable")

            if cols[2].button("Remove", key="remove_" + symbol):
                remove_watchlist(st.session_state.user_id, symbol)
                st.rerun()

    with tabs[4]:
        news_symbol = st.text_input("News ticker", value="AAPL")

        if st.button("Load News"):
            try:
                news = stock_news(news_symbol)

                for item in news[:15]:
                    st.markdown("### " + item.get("headline", "News"))
                    st.write(item.get("summary", ""))

                    if item.get("url"):
                        st.markdown(
                            f"[Read Article]({item['url']})"
                        )

                    st.divider()

            except Exception as e:
                st.error(str(e))

    st.caption(
        "Market data coverage depends on your Finnhub plan. "
        "Educational use only; not investment advice."
    )

# ============================================================
# STOCK MARKET ACADEMY
# ============================================================

def market_academy_page():
    st.title("📊 Stock Market Academy")

    level = st.selectbox(
        "Learning level",
        ["Beginner", "Intermediate", "Advanced"]
    )

    topic = st.selectbox(
        "Choose topic",
        [
            "What is the Stock Market?",
            "How Shares Work",
            "NSE and BSE",
            "NIFTY and SENSEX",
            "IPO Explained",
            "Mutual Funds",
            "Index Funds",
            "Fundamental Analysis",
            "Technical Analysis",
            "Candlestick Charts",
            "Support and Resistance",
            "Risk Management",
            "Diversification",
            "Market Psychology",
            "Financial Statements"
        ]
    )

    if st.button("Start Learning"):
        try:
            answer, provider = ask_ai(
                f"Teach {topic} at {level} level. "
                "Include definitions, examples, recap and quiz. "
                "Keep it educational, not personalized financial advice."
            )
            st.markdown(answer)
            st.caption(provider)
        except Exception as e:
            st.error(str(e))

# ============================================================
# AI VISION
# ============================================================

def vision_page():
    st.title("👁️ AI Vision")

    image_file = st.file_uploader(
        "Upload image",
        type=["png", "jpg", "jpeg", "webp"]
    )

    question = st.text_area(
        "What should I analyze?",
        "Describe this image in detail."
    )

    if image_file:
        st.image(image_file, use_container_width=True)

    if st.button("Analyze Image"):
        if not image_file:
            st.warning("Upload an image first.")
        else:
            try:
                result = analyze_image(
                    image_file.getvalue(),
                    image_file.type,
                    question
                )
                st.markdown(result)
            except Exception as e:
                st.error(str(e))

# ============================================================
# PDF ASSISTANT
# ============================================================

def pdf_page():
    st.title("📄 PDF Assistant")

    if PdfReader is None:
        st.error("Install pypdf.")
        return

    pdf = st.file_uploader("Upload PDF", type=["pdf"])

    if not pdf:
        return

    try:
        reader = PdfReader(io.BytesIO(pdf.getvalue()))
        document = "\n\n".join(
            page.extract_text() or ""
            for page in reader.pages
        )

        st.success(f"{len(reader.pages)} pages loaded.")

        st.text_area(
            "Extracted text",
            document[:5000],
            height=200
        )

        question = st.text_area(
            "Ask about this PDF",
            "Summarize the document."
        )

        if st.button("Ask PDF AI"):
            answer, provider = ask_ai(
                "DOCUMENT:\n" + document[:25000]
                + "\nQUESTION:\n" + question
            )
            st.markdown(answer)
            st.caption(provider)

        st.download_button(
            "Download extracted text",
            document,
            file_name="extracted_document.txt"
        )

    except Exception as e:
        st.error(str(e))

# ============================================================
# IMAGE STUDIO
# ============================================================

def image_page():
    st.title("🎨 AI Image Studio")

    tab1, tab2 = st.tabs(["Generate", "Edit"])

    with tab1:
        prompt = st.text_area("Describe your image")

        col1, col2 = st.columns(2)

        width = col1.selectbox(
            "Width", [512, 768, 1024], index=2
        )
        height = col2.selectbox(
            "Height", [512, 768, 1024], index=2
        )

        steps = st.slider("Steps", 1, 8, 4)

        if st.button("Generate Image"):
            if not prompt.strip():
                st.warning("Enter a prompt.")
            else:
                try:
                    with st.spinner("Generating image..."):
                        result = cloudflare_image(
                            prompt, width, height, steps
                        )

                    st.image(result, use_container_width=True)

                    st.download_button(
                        "Download Image",
                        result,
                        file_name="nextgen_image.png",
                        mime="image/png"
                    )
                except Exception as e:
                    st.error(str(e))

    with tab2:
        source = st.file_uploader(
            "Upload image",
            type=["png", "jpg", "jpeg", "webp"],
            key="edit_upload"
        )

        instruction = st.text_area("How should I edit it?")

        if source:
            st.image(source, use_container_width=True)

        if st.button("Edit Image"):
            if not source or not instruction.strip():
                st.warning("Upload an image and describe the edit.")
            else:
                try:
                    result = cloudflare_edit(
                        instruction,
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
    st.title("🌐 Web Search")

    query = st.text_input("Search the web")

    if st.button("Search"):
        if query.strip():
            try:
                st.session_state.web_results = web_search(query)
            except Exception as e:
                st.error(str(e))
        else:
            st.warning("Enter a query.")

    if st.session_state.web_results:
        st.markdown(st.session_state.web_results)

# ============================================================
# VOICE STUDIO
# ============================================================

def voice_page():
    st.title("🎙️ Voice Studio")

    st.info(
        "This version supports recording and transcription. "
        "Continuous real-time voice calls require a separate WebRTC "
        "and realtime-audio integration."
    )

    audio = st.audio_input("Record your voice")

    if audio:
        st.audio(audio.getvalue())

        if st.button("Transcribe"):
            try:
                st.session_state.voice_text = transcribe_audio(
                    audio.getvalue()
                )
                st.success("Transcription complete.")
            except Exception as e:
                st.error(str(e))

    if st.session_state.voice_text:
        text = st.text_area(
            "Recognized speech",
            value=st.session_state.voice_text
        )

        if st.button("Ask AI"):
            try:
                answer, provider = ask_ai(text)
                st.markdown(answer)
                st.caption(provider)

                audio_output = text_to_speech(answer)
                st.audio(audio_output, format="audio/mp3")

            except Exception as e:
                st.error(str(e))

# ============================================================
# CODING ACADEMY
# ============================================================

def coding_page():
    st.title("💻 Coding Academy")

    tab1, tab2 = st.tabs(["AI Coding Lab", "Learn Programming"])

    with tab1:
        mode = st.selectbox(
            "Task",
            [
                "Generate Code",
                "Debug Code",
                "Explain Code",
                "Build Project Plan",
                "Optimize Code"
            ]
        )

        language = st.selectbox(
            "Language",
            ["Python", "JavaScript", "HTML/CSS", "Java", "C++", "SQL"]
        )

        code = st.text_area(
            "Describe your task or paste code",
            height=220
        )

        if st.button("Generate Solution"):
            if code.strip():
                answer, provider = ask_ai(
                    f"Task: {mode}\nLanguage: {language}\n"
                    f"Input:\n{code}\n"
                    "Give a complete solution and explain how to run it."
                )
                st.markdown(answer)
                st.caption(provider)

    with tab2:
        level = st.selectbox(
            "Your level",
            ["Beginner", "Intermediate", "Advanced"]
        )

        topic = st.selectbox(
            "Lesson",
            [
                "What is Programming?",
                "Python Basics",
                "Variables and Data Types",
                "Conditions and Loops",
                "Functions",
                "Lists and Dictionaries",
                "Object-Oriented Programming",
                "File Handling",
                "APIs and Web Development",
                "Build a Project"
            ]
        )

        if st.button("Start Lesson"):
            try:
                answer, provider = ask_ai(
                    f"Teach {topic} at {level} level. "
                    "Include examples, exercises and solutions."
                )
                st.markdown(answer)
                st.caption(provider)
            except Exception as e:
                st.error(str(e))

# ============================================================
# STUDY ACADEMY
# ============================================================

def study_page():
    st.title("📚 Study Academy")

    subject = st.selectbox(
        "Subject",
        [
            "Mathematics", "Science", "Physics",
            "Chemistry", "Biology", "English",
            "Hindi", "History", "Geography",
            "Computer Science", "General Knowledge"
        ]
    )

    grade = st.selectbox(
        "Class / Level",
        [
            "Class 6", "Class 7", "Class 8",
            "Class 9", "Class 10", "Class 11",
            "Class 12", "Advanced"
        ]
    )

    mode = st.selectbox(
        "Study mode",
        [
            "Explain Topic",
            "Short Notes",
            "MCQ Quiz",
            "Practice Questions",
            "Explain Difficult Questions",
            "Revision Plan",
            "Chapter Summary",
            "Exam Preparation"
        ]
    )

    topic = st.text_area("Topic or question")

    if st.button("Start Learning"):
        if topic.strip():
            try:
                answer, provider = ask_ai(
                    f"Subject: {subject}\nLevel: {grade}\n"
                    f"Mode: {mode}\nTopic: {topic}\n"
                    "Explain clearly with examples and structured notes."
                )
                st.markdown(answer)
                st.caption(provider)
            except Exception as e:
                st.error(str(e))

# ============================================================
# VIDEO STUDIO
# ============================================================

def video_page():
    st.title("🎬 Video Studio")

    platform = st.selectbox(
        "Platform",
        [
            "YouTube",
            "YouTube Shorts",
            "Instagram Reels",
            "Advertisement"
        ]
    )

    duration = st.slider("Duration (seconds)", 10, 180, 30)
    ratio = st.selectbox("Aspect ratio", ["9:16", "16:9", "1:1"])

    style = st.selectbox(
        "Style",
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

    idea = st.text_area("Video idea")

    if st.button("Create Production Plan"):
        if idea.strip():
            try:
                answer, provider = ask_ai(
                    f"""
Create a complete video production plan.
Platform: {platform}
Duration: {duration} seconds
Ratio: {ratio}
Style: {style}
Idea: {idea}

Include hook, scene-by-scene timeline, image prompts,
video prompts, dialogues, voiceover, camera movements,
sound effects, music direction and editing instructions.
"""
                )
                st.markdown(answer)
                st.caption(provider)
            except Exception as e:
                st.error(str(e))

# ============================================================
# AI TOOLS
# ============================================================

def tools_page():
    st.title("🧰 AI Tools")

    tool = st.selectbox(
        "Choose tool",
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

    text_input = st.text_area(
        "Your requirements",
        height=180
    )

    if st.button("Generate"):
        if text_input.strip():
            try:
                answer, provider = ask_ai(
                    f"Tool: {tool}\nRequirements:\n{text_input}"
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
            ("🟢 " if connected else "🔴 ")
            + name
            + (" connected" if connected else " not configured")
        )

    st.divider()

    st.write("Groq model:", GROQ_MODEL)
    st.write("Gemini model:", GEMINI_MODEL)
    st.write("Username:", st.session_state.username)

    if st.session_state.is_guest:
        st.info(
            "Guest mode is active. Register or log in to transfer chats."
        )

    if st.button("Logout"):
        logout()

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
### Features

- AI Chat
- Guest Mode and chat history
- Stock Market Dashboard
- Stock Market Academy
- AI Vision
- PDF Assistant
- AI Image Generation and Editing
- Web Search
- Voice Studio
- Coding Academy
- Study Academy
- Video Production Planner
- AI Tools

Built with Python, Streamlit, SQLite and connected AI services.

Financial information is educational, not personalized investment advice.
""")

# ============================================================
# MAIN APP
# ============================================================

def main():
    if not st.session_state.authenticated:
        auth_screen()
        return

    pages = [
        "Dashboard",
        "AI Chat",
        "Stock Market",
        "Stock Market Academy",
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
        st.caption("MAX ULTRA PRO EDITION")
        st.divider()

        st.write("Signed in as")
        st.markdown("**" + str(st.session_state.username) + "**")

        if st.session_state.is_guest:
            st.caption("Guest Mode")

        selected = st.radio(
            "Navigation",
            pages,
            index=pages.index(st.session_state.page)
            if st.session_state.page in pages else 0
        )

        st.session_state.page = selected

        st.divider()
        st.caption("API Connections")

        for name, connected in api_status().items():
            st.write(("🟢 " if connected else "⚪ ") + name)

        st.divider()

        if st.button("Logout", use_container_width=True):
            logout()

        st.caption("NEXTGEN AI • 2026")

    page = st.session_state.page

    routes = {
        "Dashboard": dashboard,
        "AI Chat": chat_page,
        "Stock Market": stock_page,
        "Stock Market Academy": market_academy_page,
        "AI Vision": vision_page,
        "PDF Assistant": pdf_page,
        "Image Studio": image_page,
        "Web Search": web_page,
        "Voice Studio": voice_page,
        "Coding Lab": coding_page,
        "Study Assistant": study_page,
        "Video Studio": video_page,
        "AI Tools": tools_page,
        "Settings": settings_page,
        "About": about_page
    }

    routes.get(page, dashboard)()

if __name__ == "__main__":
    main()
