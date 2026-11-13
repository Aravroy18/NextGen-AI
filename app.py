
# ============================================================
# NEXTGEN AI — YOUR CREATIVE UNIVERSE
# Premium Streamlit AI Workspace
# ============================================================
# Existing SQLite tables preserved:
# users, conversations, messages
#
# Streamlit Secrets:
# GROQ_API_KEY
# GEMINI_API_KEY
# TAVILY_API_KEY
# FINNHUB_API_KEY
# CLOUDFLARE_ACCOUNT_ID
# CLOUDFLARE_API_TOKEN
# CLOUDFLARE_IMAGE_MODEL (optional)
# CLOUDFLARE_EDIT_MODEL (optional)
# LIVE_VOICE_URL (optional)
# ============================================================

import os
import io
import re
import json
import time
import base64
import hashlib
import secrets
import sqlite3
from datetime import datetime, date
from urllib.parse import quote

import requests
import pandas as pd
import streamlit as st
import plotly.graph_objects as go

from PIL import Image
from pypdf import PdfReader
from groq import Groq
from google import genai
from google.genai import types
from gtts import gTTS


# ============================================================
# 1. APP CONFIGURATION
# ============================================================

st.set_page_config(
    page_title="NEXTGEN AI",
    page_icon="🚀",
    layout="wide",
    initial_sidebar_state="expanded"
)

APP_NAME = "NEXTGEN AI"
TAGLINE = "YOUR CREATIVE UNIVERSE"
DB_PATH = "nextgen_ai.db"

SYSTEM_PROMPT = """
You are NEXTGEN AI, an intelligent, helpful and capable AI assistant.
Give accurate, clear and useful answers.
Use the language used by the user.
For educational questions, explain concepts step by step.
For coding questions, provide complete and practical code.
Never pretend that an unavailable feature has worked.
If you are unsure, say so honestly.
"""


# ============================================================
# 2. STREAMLIT SECRETS
# ============================================================

def get_secret(name, default=""):
    try:
        value = st.secrets.get(name, default)
        if value:
            return str(value)
    except Exception:
        pass

    return os.getenv(name, default)


GROQ_API_KEY = get_secret("GROQ_API_KEY")
GEMINI_API_KEY = get_secret("GEMINI_API_KEY")
TAVILY_API_KEY = get_secret("TAVILY_API_KEY")
FINNHUB_API_KEY = get_secret("FINNHUB_API_KEY")

CLOUDFLARE_ACCOUNT_ID = get_secret("CLOUDFLARE_ACCOUNT_ID")
CLOUDFLARE_API_TOKEN = get_secret("CLOUDFLARE_API_TOKEN")

CLOUDFLARE_IMAGE_MODEL = get_secret(
    "CLOUDFLARE_IMAGE_MODEL",
    "@cf/black-forest-labs/flux-1-schnell"
)

CLOUDFLARE_EDIT_MODEL = get_secret(
    "CLOUDFLARE_EDIT_MODEL",
    "@cf/black-forest-labs/flux-kontext-pro"
)

LIVE_VOICE_URL = get_secret("LIVE_VOICE_URL")


# ============================================================
# 3. PREMIUM UI DESIGN
# ============================================================

st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800;900&display=swap');

:root {
    --bg: #080b14;
    --panel: #101626;
    --panel2: #151e31;
    --line: rgba(150,170,220,.14);
    --text: #f4f6ff;
    --muted: #929db5;
    --accent: #8b5cf6;
    --cyan: #22d3ee;
}

html, body, [class*="css"] {
    font-family: 'Inter', sans-serif;
}

.stApp {
    background:
      radial-gradient(ellipse at 15% 0%, rgba(89,65,180,.18), transparent 36%),
      radial-gradient(ellipse at 95% 20%, rgba(0,180,220,.10), transparent 30%),
      var(--bg);
    color: var(--text);
}

[data-testid="stHeader"] {
    background: rgba(8,11,20,.72);
}

[data-testid="stSidebar"] {
    background: linear-gradient(180deg,#0c1221,#080b14);
    border-right: 1px solid var(--line);
}

[data-testid="stSidebar"] > div:first-child {
    padding-top: 1rem;
}

.block-container {
    padding-top: 1.5rem;
    padding-bottom: 3rem;
    max-width: 1500px;
}

h1,h2,h3,h4 {
    color: #f7f8ff !important;
    letter-spacing: -.6px;
}

p, label, li {
    color: #d7def0;
}

div[data-testid="stMetric"] {
    background: linear-gradient(145deg,#151f34,#0e1525);
    border: 1px solid var(--line);
    padding: 19px;
    border-radius: 18px;
}

div[data-testid="stMetricLabel"] {
    color: #9ba8c2;
}

div[data-testid="stMetricValue"] {
    color: #ffffff;
    font-weight: 800;
}

.stButton > button {
    border-radius: 12px;
    border: 1px solid rgba(139,92,246,.35);
    background: linear-gradient(110deg,#6541c8,#4264d9);
    color: white;
    font-weight: 700;
    min-height: 42px;
    transition: .2s ease;
}

.stButton > button:hover {
    border-color: #22d3ee;
    transform: translateY(-1px);
    box-shadow: 0 5px 22px rgba(85,100,240,.2);
}

.stTextInput input,
.stTextArea textarea,
.stSelectbox div[data-baseweb="select"] {
    background: #10192b !important;
    border-color: var(--line) !important;
    border-radius: 12px !important;
    color: white !important;
}

[data-testid="stChatMessage"] {
    background: rgba(17,25,43,.82);
    border: 1px solid var(--line);
    border-radius: 17px;
    padding: 12px 15px;
    margin-bottom: 12px;
}

[data-testid="stChatInput"] {
    border: 1px solid rgba(139,92,246,.5);
    border-radius: 18px;
    background: #11192a;
}

[data-testid="stFileUploader"] {
    background: rgba(20,29,48,.65);
    border: 1px dashed rgba(139,92,246,.4);
    border-radius: 15px;
    padding: 10px;
}

hr {
    border-color: var(--line);
}

.ng-hero {
    position: relative;
    overflow: hidden;
    padding: 35px;
    border-radius: 25px;
    border: 1px solid rgba(139,92,246,.30);
    background:
      radial-gradient(circle at 85% 10%,rgba(34,211,238,.20),transparent 32%),
      linear-gradient(120deg,#171a37,#101b32 60%,#101b29);
    margin-bottom: 22px;
}

.ng-hero h1 {
    font-size: clamp(34px,5vw,58px);
    font-weight: 900;
    line-height: 1.05;
    margin: 8px 0;
}

.ng-hero p {
    color: #bac5df;
    font-size: 15px;
}

.ng-kicker {
    color: #a78bfa;
    font-weight: 800;
    letter-spacing: 3px;
    font-size: 11px;
}

.ng-card {
    height: 100%;
    background: linear-gradient(145deg,rgba(23,33,55,.96),rgba(13,20,35,.96));
    border: 1px solid var(--line);
    border-radius: 18px;
    padding: 19px;
    transition: .2s ease;
}

.ng-card:hover {
    border-color: rgba(34,211,238,.45);
    transform: translateY(-2px);
}

.ng-card-icon {
    font-size: 27px;
    margin-bottom: 9px;
}

.ng-card-title {
    font-size: 16px;
    font-weight: 800;
    color: white;
}

.ng-card-desc {
    font-size: 12px;
    color: #9eabc5;
    line-height: 1.6;
}

.ng-pill {
    display: inline-block;
    border: 1px solid rgba(34,211,238,.25);
    color: #67e8f9;
    background: rgba(34,211,238,.08);
    border-radius: 30px;
    padding: 5px 11px;
    font-size: 11px;
    font-weight: 700;
}

.ng-logo {
    font-size: 23px;
    font-weight: 900;
    letter-spacing: -1px;
    background: linear-gradient(90deg,#c4b5fd,#67e8f9);
    -webkit-background-clip: text;
    color: transparent;
}

.ng-muted {
    color: #929db5;
    font-size: 12px;
}

.ng-section {
    margin-top: 25px;
    margin-bottom: 12px;
    font-size: 20px;
    font-weight: 800;
}

.ng-feature {
    background: #10192a;
    border: 1px solid var(--line);
    border-radius: 15px;
    padding: 16px;
    margin-bottom: 10px;
}

footer {
    visibility: hidden;
}
</style>
""", unsafe_allow_html=True)


# ============================================================
# 4. DATABASE — PRESERVE EXISTING DATA
# ============================================================

def db_connection():
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    conn = db_connection()
    cur = conn.cursor()

    cur.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            password TEXT NOT NULL
        )
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS conversations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            title TEXT DEFAULT 'New Chat',
            created_at TEXT,
            updated_at TEXT
        )
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS messages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            conversation_id INTEGER NOT NULL,
            role TEXT NOT NULL,
            content TEXT NOT NULL,
            created_at TEXT
        )
    """)

    conn.commit()
    conn.close()


init_db()


# ============================================================
# 5. PASSWORD SECURITY AND AUTHENTICATION
# ============================================================

def hash_password(password, salt=None):
    salt = salt or secrets.token_hex(16)
    hashed = hashlib.pbkdf2_hmac(
        "sha256",
        password.encode("utf-8"),
        salt.encode("utf-8"),
        200000
    ).hex()
    return salt + "$" + hashed


def verify_password(password, stored):
    try:
        salt, old_hash = stored.split("$", 1)
        new_hash = hashlib.pbkdf2_hmac(
            "sha256",
            password.encode("utf-8"),
            salt.encode("utf-8"),
            200000
        ).hex()
        return secrets.compare_digest(new_hash, old_hash)
    except Exception:
        return False


def register_user(username, password):
    username = username.strip()
    if len(username) < 3 or len(password) < 6:
        return False, "Username must be 3+ characters and password 6+ characters."

    conn = db_connection()
    try:
        conn.execute(
            "INSERT INTO users(username,password) VALUES(?,?)",
            (username, hash_password(password))
        )
        conn.commit()
        return True, "Account created. Please sign in."
    except sqlite3.IntegrityError:
        return False, "This username already exists."
    finally:
        conn.close()


def login_user(username, password):
    conn = db_connection()
    user = conn.execute(
        "SELECT * FROM users WHERE username=?",
        (username.strip(),)
    ).fetchone()
    conn.close()

    if user and verify_password(password, user["password"]):
        return dict(user)
    return None


# ============================================================
# 6. SESSION STATE
# ============================================================

DEFAULT_STATE = {
    "authenticated": False,
    "user": None,
    "guest": False,
    "page": "Dashboard",
    "conversation_id": None,
    "messages": [],
    "pending_prompt": "",
    "last_answer": "",
    "voice_text": ""
}

for key, value in DEFAULT_STATE.items():
    if key not in st.session_state:
        st.session_state[key] = value


# ============================================================
# 7. CONVERSATION DATABASE FUNCTIONS
# ============================================================

def create_conversation(user_id, title="New Chat"):
    now = datetime.now().isoformat(timespec="seconds")
    conn = db_connection()
    cur = conn.cursor()
    cur.execute(
        """INSERT INTO conversations(user_id,title,created_at,updated_at)
           VALUES(?,?,?,?)""",
        (user_id, title, now, now)
    )
    conversation_id = cur.lastrowid
    conn.commit()
    conn.close()
    return conversation_id


def get_conversations(user_id):
    conn = db_connection()
    rows = conn.execute(
        """SELECT * FROM conversations
           WHERE user_id=?
           ORDER BY updated_at DESC""",
        (user_id,)
    ).fetchall()
    conn.close()
    return [dict(row) for row in rows]


def get_messages(conversation_id):
    conn = db_connection()
    rows = conn.execute(
        """SELECT role,content,created_at FROM messages
           WHERE conversation_id=?
           ORDER BY id ASC""",
        (conversation_id,)
    ).fetchall()
    conn.close()
    return [dict(row) for row in rows]


def save_message(conversation_id, role, content):
    now = datetime.now().isoformat(timespec="seconds")
    conn = db_connection()
    conn.execute(
        """INSERT INTO messages(conversation_id,role,content,created_at)
           VALUES(?,?,?,?)""",
        (conversation_id, role, content, now)
    )
    conn.execute(
        "UPDATE conversations SET updated_at=? WHERE id=?",
        (now, conversation_id)
    )
    conn.commit()
    conn.close()


def rename_conversation(conversation_id, title):
    conn = db_connection()
    conn.execute(
        "UPDATE conversations SET title=? WHERE id=?",
        (title[:80], conversation_id)
    )
    conn.commit()
    conn.close()


def delete_conversation(conversation_id):
    conn = db_connection()
    conn.execute(
        "DELETE FROM messages WHERE conversation_id=?",
        (conversation_id,)
    )
    conn.execute(
        "DELETE FROM conversations WHERE id=?",
        (conversation_id,)
    )
    conn.commit()
    conn.close()


def ensure_conversation():
    if st.session_state.guest:
        return None

    if not st.session_state.user:
        return None

    if not st.session_state.conversation_id:
        st.session_state.conversation_id = create_conversation(
            st.session_state.user["id"]
        )
    return st.session_state.conversation_id


# ============================================================
# 8. AI PROVIDERS — GROQ + GEMINI
# ============================================================

def ask_ai(prompt, history=None):
    history = history or []
    errors = []

    # Provider 1: Groq
    if GROQ_API_KEY:
        try:
            client = Groq(api_key=GROQ_API_KEY)

            messages = [{"role": "system", "content": SYSTEM_PROMPT}]

            for item in history[-12:]:
                if item.get("role") in ("user", "assistant"):
                    messages.append({
                        "role": item["role"],
                        "content": str(item["content"])
                    })

            messages.append({"role": "user", "content": prompt})

            response = client.chat.completions.create(
                model="openai/gpt-oss-120b",
                messages=messages,
                max_completion_tokens=2500
            )

            answer = response.choices[0].message.content
            if answer:
                return answer, "Groq GPT-OSS 120B"

            errors.append("Groq returned an empty response.")

        except Exception as exc:
            errors.append("Groq: " + str(exc))

    # Provider 2: Gemini
    if GEMINI_API_KEY:
        try:
            client = genai.Client(api_key=GEMINI_API_KEY)

            conversation = SYSTEM_PROMPT + "\n\n"
            for item in history[-12:]:
                role = "User" if item.get("role") == "user" else "Assistant"
                conversation += f"{role}: {item.get('content', '')}\n\n"

            conversation += f"User: {prompt}\nAssistant:"

            response = client.models.generate_content(
                model="gemini-3.8-flash",
                contents=conversation
            )

            if response.text:
                return response.text, "Gemini 3.8 Flash"

            errors.append("Gemini returned an empty response.")

        except Exception as exc:
            errors.append("Gemini: " + str(exc))

    if not GROQ_API_KEY and not GEMINI_API_KEY:
        return "AI keys are missing. Add GROQ_API_KEY or GEMINI_API_KEY in Streamlit Secrets.", "Configuration"

    return "Both AI providers failed:\n\n" + "\n\n".join(errors), "Provider Error"


# ============================================================
# 9. PDF TEXT EXTRACTION
# ============================================================

def extract_pdf_text(uploaded_file):
    try:
        reader = PdfReader(uploaded_file)
        pages = []
        for page in reader.pages:
            pages.append(page.extract_text() or "")
        return "\n\n".join(pages)
    except Exception as exc:
        return "PDF reading error: " + str(exc)


# ============================================================
# 10. IMAGE VISION
# ============================================================

def analyze_image(image_file, prompt):
    if not GEMINI_API_KEY:
        return "Gemini API key is missing."

    try:
        image = Image.open(image_file).convert("RGB")
        client = genai.Client(api_key=GEMINI_API_KEY)

        response = client.models.generate_content(
            model="gemini-3.8-flash",
            contents=[prompt, image]
        )
        return response.text or "No response received."
    except Exception as exc:
        return "Image analysis error: " + str(exc)


# ============================================================
# 11. IMAGE GENERATION — CLOUDFLARE FLUX
# ============================================================

def cloudflare_endpoint(model):
    return (
        "https://api.cloudflare.com/client/v4/accounts/"
        + CLOUDFLARE_ACCOUNT_ID
        + "/ai/run/"
        + quote(model, safe="@/-")
    )


def generate_image(prompt):
    if not CLOUDFLARE_ACCOUNT_ID or not CLOUDFLARE_API_TOKEN:
        return None, "Cloudflare Account ID or API Token is missing."

    try:
        url = cloudflare_endpoint(CLOUDFLARE_IMAGE_MODEL)
        response = requests.post(
            url,
            headers={
                "Authorization": f"Bearer {CLOUDFLARE_API_TOKEN}",
                "Content-Type": "application/json"
            },
            json={"prompt": prompt},
            timeout=180
        )

        if not response.ok:
            return None, f"Cloudflare error {response.status_code}: {response.text[:1000]}"

        content_type = response.headers.get("content-type", "")

        if "image" in content_type:
            return response.content, None

        try:
            data = response.json()
            result = data.get("result", {})
            image_data = result.get("image")

            if image_data:
                return base64.b64decode(image_data), None

            return None, json.dumps(data)[:1200]
        except Exception:
            return None, "The image provider returned an unsupported response."

    except Exception as exc:
        return None, str(exc)


def edit_image(image_file, prompt):
    if not CLOUDFLARE_ACCOUNT_ID or not CLOUDFLARE_API_TOKEN:
        return None, "Cloudflare credentials are missing."

    try:
        image_file.seek(0)
        encoded = base64.b64encode(image_file.read()).decode("utf-8")

        response = requests.post(
            cloudflare_endpoint(CLOUDFLARE_EDIT_MODEL),
            headers={
                "Authorization": f"Bearer {CLOUDFLARE_API_TOKEN}",
                "Content-Type": "application/json"
            },
            json={
                "prompt": prompt,
                "image": encoded
            },
            timeout=180
        )

        if not response.ok:
            return None, f"Image editing error {response.status_code}: {response.text[:1000]}"

        if "image" in response.headers.get("content-type", ""):
            return response.content, None

        try:
            result = response.json().get("result", {})
            if result.get("image"):
                return base64.b64decode(result["image"]), None
            return None, str(result)[:1000]
        except Exception:
            return None, "Unsupported image editing response."

    except Exception as exc:
        return None, str(exc)


# ============================================================
# 12. WEB SEARCH — TAVILY
# ============================================================

def web_search(query):
    if not TAVILY_API_KEY:
        return None, "TAVILY_API_KEY is missing from Streamlit Secrets."

    try:
        response = requests.post(
            "https://api.tavily.com/search",
            json={
                "api_key": TAVILY_API_KEY,
                "query": query,
                "search_depth": "advanced",
                "max_results": 6,
                "include_answer": True
            },
            timeout=45
        )

        response.raise_for_status()
        return response.json(), None

    except Exception as exc:
        return None, str(exc)


# ============================================================
# 13. STOCK MARKET — FINNHUB
# ============================================================

def get_stock_quote(symbol):
    if not FINNHUB_API_KEY:
        return None, "FINNHUB_API_KEY is missing."

    try:
        response = requests.get(
            "https://finnhub.io/api/v1/quote",
            params={"symbol": symbol.upper(), "token": FINNHUB_API_KEY},
            timeout=20
        )
        response.raise_for_status()
        data = response.json()

        if not data or data.get("c") is None:
            return None, "No quote data found for this symbol."

        return data, None

    except Exception as exc:
        return None, str(exc)


def get_stock_candles(symbol, resolution="D", days=30):
    if not FINNHUB_API_KEY:
        return None, "Finnhub API key is missing."

    end_time = int(time.time())
    start_time = end_time - days * 86400

    try:
        response = requests.get(
            "https://finnhub.io/api/v1/stock/candle",
            params={
                "symbol": symbol.upper(),
                "resolution": resolution,
                "from": start_time,
                "to": end_time,
                "token": FINNHUB_API_KEY
            },
            timeout=30
        )
        response.raise_for_status()
        data = response.json()

        if data.get("s") != "ok":
            return None, "No candle data available."

        frame = pd.DataFrame({
            "Date": pd.to_datetime(data["t"], unit="s"),
            "Open": data["o"],
            "High": data["h"],
            "Low": data["l"],
            "Close": data["c"],
            "Volume": data["v"]
        })
        return frame, None

    except Exception as exc:
        return None, str(exc)


# ============================================================
# 14. VOICE — GROQ WHISPER + GTTS
# ============================================================

def transcribe_audio(audio_file):
    if not GROQ_API_KEY:
        return None, "Groq API key is missing."

    try:
        client = Groq(api_key=GROQ_API_KEY)
        audio_file.seek(0)

        transcription = client.audio.transcriptions.create(
            file=(
                audio_file.name or "recording.wav",
                audio_file.read()
            ),
            model="whisper-large-v3-turbo"
        )

        return transcription.text, None

    except Exception as exc:
        return None, str(exc)


def text_to_speech(text_value, language="en"):
    try:
        output = io.BytesIO()
        tts = gTTS(text=text_value[:4500], lang=language)
        tts.write_to_fp(output)
        output.seek(0)
        return output
    except Exception:
        return None


# ============================================================
# 15. HELPER FUNCTIONS
# ============================================================

def show_card(icon, title, description, tag=None):
    tag_html = f'<span class="ng-pill">{tag}</span>' if tag else ""
    st.markdown(
        f"""
        <div class="ng-card">
          <div class="ng-card-icon">{icon}</div>
          <div class="ng-card-title">{title}</div>
          <div class="ng-card-desc">{description}</div>
          <br>{tag_html}
        </div>
        """,
        unsafe_allow_html=True
    )


def go_to(page):
    st.session_state.page = page
    st.rerun()


def new_chat():
    st.session_state.conversation_id = None
    st.session_state.messages = []
    st.session_state.page = "AI Chat"
    st.rerun()


def current_user_id():
    if st.session_state.user:
        return st.session_state.user["id"]
    return None


def add_chat_message(role, content):
    st.session_state.messages.append({
        "role": role,
        "content": content
    })

    conversation_id = ensure_conversation()
    if conversation_id:
        save_message(conversation_id, role, content)


def load_conversation(conversation_id):
    st.session_state.conversation_id = conversation_id
    st.session_state.messages = get_messages(conversation_id)
    st.session_state.page = "AI Chat"
    st.rerun()


def make_ai_response(prompt, extra_context=""):
    full_prompt = prompt

    if extra_context:
        full_prompt = (
            "Use the following attached material when answering.\n\n"
            + extra_context[:25000]
            + "\n\nUser question:\n"
            + prompt
        )

    history = st.session_state.messages[-12:]
    answer, provider = ask_ai(full_prompt, history)
    return answer, provider


# ============================================================
# 16. LOGIN / REGISTER SCREEN
# ============================================================

def auth_screen():
    st.markdown(
        """
        <div class="ng-hero">
          <div class="ng-kicker">WELCOME TO YOUR CREATIVE UNIVERSE</div>
          <h1>NEXTGEN AI 🚀</h1>
          <p>One platform. Endless possibilities.</p>
          <span class="ng-pill">AI CHAT • VISION • IMAGE • VOICE • WEB</span>
        </div>
        """,
        unsafe_allow_html=True
    )

    left, center, right = st.columns([1, 1.2, 1])

    with center:
        login_tab, register_tab = st.tabs(["Sign In", "Create Account"])

        with login_tab:
            username = st.text_input("Username", key="login_username")
            password = st.text_input(
                "Password",
                type="password",
                key="login_password"
            )

            if st.button("Sign In →", use_container_width=True):
                user = login_user(username, password)
                if user:
                    st.session_state.authenticated = True
                    st.session_state.user = user
                    st.session_state.guest = False
                    st.rerun()
                else:
                    st.error("Incorrect username or password.")

        with register_tab:
            new_username = st.text_input("Choose username", key="reg_user")
            new_password = st.text_input(
                "Choose password",
                type="password",
                key="reg_pass"
            )
            confirm_password = st.text_input(
                "Confirm password",
                type="password",
                key="reg_confirm"
            )

            if st.button("Create Account", use_container_width=True):
                if new_password != confirm_password:
                    st.error("Passwords do not match.")
                else:
                    success, message = register_user(
                        new_username, new_password
                    )
                    if success:
                        st.success(message)
                    else:
                        st.error(message)

        st.divider()

        if st.button("Continue as Guest", use_container_width=True):
            st.session_state.authenticated = True
            st.session_state.guest = True
            st.session_state.user = None
            st.rerun()

        st.caption(
            "Guest conversations are temporary. Sign in to save chat history."
        )


if not st.session_state.authenticated:
    auth_screen()
    st.stop()


# ============================================================
# 17. SIDEBAR
# ============================================================

PAGES = [
    ("Dashboard", "🏠"),
    ("AI Chat", "💬"),
    ("Stock Market", "📈"),
    ("AI Vision", "👁️"),
    ("PDF Assistant", "📄"),
    ("Image Studio", "🎨"),
    ("Web Search", "🌐"),
    ("Voice Studio", "🎙️"),
    ("Live Call", "📞"),
    ("Coding Lab", "💻"),
    ("Study Assistant", "📚"),
    ("Video Studio", "🎬"),
    ("AI Tools", "🧰"),
    ("AI Skill Center", "🧠"),
    ("Settings", "⚙️"),
    ("About", "✨")
]

with st.sidebar:
    st.markdown(
        '<div class="ng-logo">🚀 NEXTGEN AI</div>',
        unsafe_allow_html=True
    )
    st.caption(TAGLINE)
    st.divider()

    if st.button("＋  New Chat", use_container_width=True):
        new_chat()

    st.markdown("**WORKSPACE**")

    for page_name, page_icon in PAGES:
        if st.button(
            f"{page_icon}  {page_name}",
            key="nav_" + page_name,
            use_container_width=True
        ):
            go_to(page_name)

    st.divider()
    st.markdown("**RECENT CHATS**")

    if st.session_state.user:
        conversations = get_conversations(st.session_state.user["id"])

        for conversation in conversations[:12]:
            title = conversation["title"] or "New Chat"
            if st.button(
                "💬 " + title[:27],
                key=f"history_{conversation['id']}",
                use_container_width=True
            ):
                load_conversation(conversation["id"])
    else:
        st.caption("Sign in to save and revisit conversations.")

    st.divider()

    if st.session_state.user:
        st.caption("Signed in as")
        st.markdown(
            f"**{st.session_state.user['username']}**"
        )
    else:
        st.caption("Guest session")

    if st.button("Log Out", use_container_width=True):
        for key in DEFAULT_STATE:
            if key in st.session_state:
                del st.session_state[key]
        st.rerun()


# ============================================================
# 18. DASHBOARD
# ============================================================

def dashboard_page():
    st.markdown(
        """
        <div class="ng-hero">
          <div class="ng-kicker">YOUR PERSONAL AI WORKSPACE</div>
          <h1>Think bigger.<br>Build beyond. ✨</h1>
          <p>Meet your AI-powered creative universe. Chat, create, learn,
          explore and build — all in one place.</p>
          <span class="ng-pill">NEXTGEN AI • 2026</span>
        </div>
        """,
        unsafe_allow_html=True
    )

    st.markdown("### Your workspace")

    a, b, c, d = st.columns(4)

    with a:
        st.metric("AI Workspace", "ACTIVE", "Ready to use")
    with b:
        st.metric("AI Engines", "2", "Groq + Gemini")
    with c:
        st.metric("Creative Tools", "8+", "Explore tools")
    with d:
        st.metric(
            "Account",
            "Guest" if st.session_state.guest else "Personal",
            "Session active"
        )

    st.markdown('<div class="ng-section">⚡ Quick Actions</div>',
                unsafe_allow_html=True)

    quick = st.columns(4)
    quick_items = [
        ("💬", "Start chatting", "Ask questions and work with AI", "AI Chat"),
        ("🎨", "Create an image", "Turn your imagination into images", "Image Studio"),
        ("📄", "Read a PDF", "Understand and summarize documents", "PDF Assistant"),
        ("🌐", "Explore the web", "Search for useful information", "Web Search")
    ]

    for col, item in zip(quick, quick_items):
        with col:
            show_card(*item[:3])
            if st.button("Open →", key="quick_" + item[1], use_container_width=True):
                go_to(item[3])

    st.markdown('<div class="ng-section">🚀 Explore NEXTGEN AI</div>',
                unsafe_allow_html=True)

    feature_rows = [
        [
            ("💬", "AI Chat", "Your intelligent assistant for ideas, questions and coding.", "AI Chat"),
            ("👁️", "AI Vision", "Upload an image and ask AI to understand it.", "AI Vision"),
            ("📈", "Stock Market", "Explore stock quotes and market charts.", "Stock Market")
        ],
        [
            ("🎨", "Image Studio", "Generate images with Cloudflare Flux.", "Image Studio"),
            ("🎙️", "Voice Studio", "Transcribe audio and listen to AI responses.", "Voice Studio"),
            ("📞", "Live Call", "Open your deployed real-time voice interface.", "Live Call")
        ],
        [
            ("📚", "Study Assistant", "Understand topics and prepare study material.", "Study Assistant"),
            ("💻", "Coding Lab", "Build, explain and debug code.", "Coding Lab"),
            ("🎬", "Video Studio", "Create scripts and prompts for AI videos.", "Video Studio")
        ]
    ]

    for row in feature_rows:
        cols = st.columns(3)
        for col, item in zip(cols, row):
            with col:
                show_card(*item[:3])
                if st.button("Explore →", key="feature_" + item[1], use_container_width=True):
                    go_to(item[3])

    st.markdown('<div class="ng-section">✨ Built for creativity</div>',
                unsafe_allow_html=True)

    st.markdown("""
    <div class="ng-card">
      <div class="ng-card-title">One platform. Endless possibilities.</div>
      <p class="ng-card-desc">
      NEXTGEN AI brings AI conversations, image creation, document help,
      web research, coding, learning and voice tools into one workspace.
      New features can be added as the platform grows.
      </p>
    </div>
    """, unsafe_allow_html=True)


# ============================================================
# 19. CHAT PAGE
# ============================================================

def chat_page():
    st.markdown("## 💬 AI Chat")
    st.caption("Talk to NEXTGEN AI. Your ideas start here.")

    if st.session_state.conversation_id and not st.session_state.messages:
        st.session_state.messages = get_messages(
            st.session_state.conversation_id
        )

    # Chat history
    for index, message in enumerate(st.session_state.messages):
        with st.chat_message(message["role"]):
            st.markdown(message["content"])

            if message["role"] == "assistant":
                col1, col2, col3 = st.columns([1, 1, 5])

                with col1:
                    if st.button("📋 Copy", key=f"copy_{index}"):
                        st.code(message["content"])

                with col2:
                    if st.button("🔊 Read", key=f"read_{index}"):
                        audio = text_to_speech(message["content"])
                        if audio:
                            st.audio(audio, format="audio/mp3")

    # Attachment popover: plus icon
    with st.popover("＋", help="Attach a file"):
        st.markdown("**Add to your message**")
        uploaded_files = st.file_uploader(
            "Upload PDF, image or text file",
            type=["pdf", "png", "jpg", "jpeg", "webp", "txt", "csv", "py", "md"],
            accept_multiple_files=True,
            key="chat_attachments"
        )

    attachment_context = ""
    if uploaded_files:
        for file in uploaded_files:
            ext = file.name.lower().split(".")[-1]

            if ext == "pdf":
                attachment_context += (
                    f"\n\n[PDF: {file.name}]\n"
                    + extract_pdf_text(file)
                )

            elif ext in ("txt", "md", "py", "csv"):
                try:
                    attachment_context += (
                        f"\n\n[File: {file.name}]\n"
                        + file.getvalue().decode("utf-8", errors="ignore")[:12000]
                    )
                except Exception:
                    pass

            elif ext in ("png", "jpg", "jpeg", "webp"):
                st.image(file, caption=file.name, width=180)
                attachment_context += (
                    f"\n\nAn image named {file.name} was attached. "
                    "Use AI Vision if detailed visual analysis is needed."
                )

    # Audio input
    audio_input = st.audio_input("🎙️ Record a voice message")

    if audio_input:
        if st.button("Transcribe voice message"):
            with st.spinner("Transcribing audio..."):
                text_value, error = transcribe_audio(audio_input)
            if error:
                st.error(error)
            else:
                st.session_state.voice_text = text_value
                st.success("Transcription ready.")
                st.text_area(
                    "Transcribed message",
                    value=text_value,
                    key="transcribed_preview"
                )

    # Chat composer
    prompt = st.chat_input("Message NEXTGEN AI...")

    if prompt:
        if not st.session_state.messages and not st.session_state.guest:
            conversation_id = ensure_conversation()
            if conversation_id:
                rename_conversation(conversation_id, prompt[:45])

        add_chat_message("user", prompt)

        with st.chat_message("user"):
            st.markdown(prompt)

        with st.chat_message("assistant"):
            with st.spinner("NEXTGEN AI is thinking..."):
                answer, provider = make_ai_response(
                    prompt,
                    attachment_context
                )
            st.markdown(answer)
            st.caption("Powered by " + provider)

        add_chat_message("assistant", answer)
        st.session_state.last_answer = answer
        st.rerun()

    if st.session_state.voice_text:
        if st.button("Send transcribed message to AI"):
            voice_prompt = st.session_state.voice_text
            st.session_state.voice_text = ""
            st.session_state.pending_prompt = voice_prompt
            st.rerun()


# ============================================================
# 20. STOCK MARKET PAGE
# ============================================================

def stock_page():
    st.markdown("## 📈 Stock Market Explorer")
    st.caption("Market information for learning and research.")

    symbol = st.text_input("Enter stock symbol", value="AAPL").upper().strip()

    if st.button("Get Stock Data", use_container_width=True):
        with st.spinner("Fetching market data..."):
            quote, error = get_stock_quote(symbol)

        if error:
            st.error(error)
        else:
            p1, p2, p3, p4 = st.columns(4)
            p1.metric("Current", f"{quote['c']:.2f}")
            p2.metric("Previous Close", f"{quote['pc']:.2f}")
            p3.metric("High", f"{quote['h']:.2f}")
            p4.metric("Low", f"{quote['l']:.2f}")

            frame, chart_error = get_stock_candles(symbol)

            if chart_error:
                st.warning(chart_error)
            else:
                fig = go.Figure()
                fig.add_trace(go.Candlestick(
                    x=frame["Date"],
                    open=frame["Open"],
                    high=frame["High"],
                    low=frame["Low"],
                    close=frame["Close"],
                    name=symbol
                ))
                fig.update_layout(
                    template="plotly_dark",
                    height=470,
                    title=f"{symbol} — Price Chart",
                    xaxis_rangeslider_visible=False,
                    paper_bgcolor="rgba(0,0,0,0)",
                    plot_bgcolor="rgba(0,0,0,0)"
                )
                st.plotly_chart(fig, use_container_width=True)

    st.info(
        "Market data may be delayed or incomplete. This page is for "
        "education and research, not personalized financial advice."
    )


# ============================================================
# 21. AI VISION PAGE
# ============================================================

def vision_page():
    st.markdown("## 👁️ AI Vision")
    st.caption("Upload an image and ask NEXTGEN AI about it.")

    image_file = st.file_uploader(
        "Upload an image",
        type=["png", "jpg", "jpeg", "webp"],
        key="vision_upload"
    )

    question = st.text_area(
        "What should AI examine?",
        value="Describe this image clearly."
    )

    if image_file:
        st.image(image_file, use_container_width=True)

        if st.button("Analyze Image", use_container_width=True):
            with st.spinner("Analyzing image..."):
                result = analyze_image(image_file, question)
            st.markdown("### AI Analysis")
            st.markdown(result)


# ============================================================
# 22. PDF ASSISTANT
# ============================================================

def pdf_page():
    st.markdown("## 📄 PDF Assistant")
    st.caption("Upload a PDF and ask questions about its contents.")

    pdf_file = st.file_uploader(
        "Choose PDF",
        type=["pdf"],
        key="pdf_upload"
    )

    if pdf_file:
        pdf_text = extract_pdf_text(pdf_file)

        if pdf_text.startswith("PDF reading error"):
            st.error(pdf_text)
            return

        st.success("PDF loaded successfully.")
        st.caption(f"Extracted characters: {len(pdf_text):,}")

        task = st.selectbox(
            "Choose an action",
            [
                "Summarize this PDF",
                "Explain it in simple language",
                "Create important questions",
                "Find key points",
                "Ask my own question"
            ]
        )

        custom_question = ""
        if task == "Ask my own question":
            custom_question = st.text_input("Your question")

        if st.button("Analyze PDF", use_container_width=True):
            prompt = custom_question or task
            with st.spinner("Reading your PDF..."):
                answer, provider = ask_ai(
                    prompt + "\n\nPDF CONTENT:\n" + pdf_text[:25000]
                )
            st.markdown(answer)
            st.caption("Powered by " + provider)


# ============================================================
# 23. IMAGE STUDIO
# ============================================================

def image_studio_page():
    st.markdown("## 🎨 Image Studio")
    st.caption("Create images with Cloudflare Flux.")

    tab1, tab2 = st.tabs(["Generate Image", "Edit Image"])

    with tab1:
        prompt = st.text_area(
            "Describe the image you want",
            placeholder="A cinematic futuristic city at night, neon lights, ultra detailed..."
        )

        if st.button("✨ Generate Image", use_container_width=True):
            if not prompt.strip():
                st.warning("Please enter an image prompt.")
            else:
                with st.spinner("Creating your image..."):
                    image_bytes, error = generate_image(prompt)

                if error:
                    st.error(error)
                else:
                    st.image(image_bytes, use_container_width=True)
                    st.download_button(
                        "Download Image",
                        data=image_bytes,
                        file_name="nextgen_ai_image.png",
                        mime="image/png",
                        use_container_width=True
                    )

    with tab2:
        source_image = st.file_uploader(
            "Upload image to edit",
            type=["png", "jpg", "jpeg", "webp"],
            key="edit_image_upload"
        )
        edit_prompt = st.text_area(
            "Describe the edit",
            placeholder="Change the background to a futuristic neon city..."
        )

        if source_image:
            st.image(source_image, width=300)

        if st.button("🪄 Edit Image", use_container_width=True):
            if not source_image or not edit_prompt.strip():
                st.warning("Upload an image and describe your edit.")
            else:
                with st.spinner("Editing image..."):
                    edited, error = edit_image(source_image, edit_prompt)

                if error:
                    st.error(error)
                else:
                    st.image(edited, use_container_width=True)
                    st.download_button(
                        "Download Edited Image",
                        data=edited,
                        file_name="nextgen_ai_edited.png",
                        mime="image/png"
                    )


# ============================================================
# 24. WEB SEARCH
# ============================================================

def web_search_page():
    st.markdown("## 🌐 Web Search")
    query = st.text_input(
        "What do you want to search?",
        placeholder="Search a topic..."
    )

    if st.button("Search Web", use_container_width=True):
        if not query.strip():
            st.warning("Enter a search query.")
        else:
            with st.spinner("Searching the web..."):
                data, error = web_search(query)

            if error:
                st.error(error)
            else:
                if data.get("answer"):
                    st.markdown("### Quick Answer")
                    st.write(data["answer"])

                st.markdown("### Search Results")

                for item in data.get("results", []):
                    st.markdown(f"**{item.get('title', 'Result')}**")
                    st.write(item.get("content", ""))
                    if item.get("url"):
                        st.markdown(f"[Open source]({item['url']})")
                    st.divider()


# ============================================================
# 25. VOICE STUDIO
# ============================================================

def voice_page():
    st.markdown("## 🎙️ Voice Studio")
    st.caption("Convert speech to text and text to speech.")

    tab1, tab2 = st.tabs(["Speech to Text", "Text to Speech"])

    with tab1:
        audio_file = st.audio_input("Record or upload audio")

        if audio_file and st.button("Transcribe Audio"):
            with st.spinner("Transcribing..."):
                text_value, error = transcribe_audio(audio_file)

            if error:
                st.error(error)
            else:
                st.text_area("Transcription", value=text_value, height=180)

    with tab2:
        text_value = st.text_area(
            "Enter text to speak",
            height=150
        )
        language = st.selectbox(
            "Language",
            ["en", "hi", "fr", "es", "de"]
        )

        if st.button("Generate Voice"):
            if not text_value.strip():
                st.warning("Enter some text.")
            else:
                with st.spinner("Generating audio..."):
                    audio = text_to_speech(text_value, language)

                if audio:
                    st.audio(audio, format="audio/mp3")
                    st.download_button(
                        "Download Audio",
                        data=audio,
                        file_name="nextgen_voice.mp3",
                        mime="audio/mpeg"
                    )
                else:
                    st.error("Could not generate audio.")


# ============================================================
# 26. LIVE CALL
# ============================================================

def live_call_page():
    st.markdown("## 📞 NEXTGEN AI — Live Voice Call")
    st.caption("Real-time voice interface")

    if not LIVE_VOICE_URL:
        st.warning(
            "LIVE_VOICE_URL is not configured in Streamlit Secrets."
        )
        st.markdown("""
        To enable Live Call, deploy your separate Cloudflare Live Voice
        React interface and add its public URL to Streamlit Secrets:

        `LIVE_VOICE_URL = "https://your-live-voice-interface.pages.dev"`

        This must be the deployed voice interface URL, not just the Worker API URL.
        """)
        return

    st.success("Live Voice interface URL configured.")

    st.components.v1.iframe(
        LIVE_VOICE_URL,
        height=720,
        scrolling=True
    )

    st.caption(
        "The live call works through your separately deployed voice interface. "
        "A URL alone does not create a realtime audio service."
    )


# ============================================================
# 27. CODING LAB
# ============================================================

def coding_page():
    st.markdown("## 💻 Coding Lab")

    language = st.selectbox(
        "Programming language",
        ["Python", "JavaScript", "HTML/CSS", "C++", "Java", "SQL"]
    )

    task = st.selectbox(
        "What do you need?",
        [
            "Write code",
            "Explain code",
            "Debug code",
            "Optimize code",
            "Create a project"
        ]
    )

    code = st.text_area(
        "Describe your task or paste your code",
        height=220
    )

    if st.button("Run AI Coding Assistant", use_container_width=True):
        if not code.strip():
            st.warning("Enter a task or code.")
        else:
            prompt = (
                f"Programming language: {language}\n"
                f"Task: {task}\n\n"
                f"User request/code:\n{code}\n\n"
                "Give a complete, correct and well-explained answer."
            )

            with st.spinner("Working on your code..."):
                answer, provider = ask_ai(prompt)

            st.markdown(answer)
            st.caption("Powered by " + provider)


# ============================================================
# 28. STUDY ASSISTANT
# ============================================================

def study_page():
    st.markdown("## 📚 Study Assistant")

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
            "Social Studies",
            "Computer Science",
            "General Knowledge"
        ]
    )

    class_level = st.selectbox(
        "Class / Level",
        ["Class 6", "Class 7", "Class 8", "Class 9", "Class 10", "Other"]
    )

    topic = st.text_input("Topic or chapter")
    action = st.selectbox(
        "Choose",
        [
            "Make short notes",
            "Explain the topic",
            "Create practice questions",
            "Create a quiz",
            "Give important definitions",
            "Solve a question"
        ]
    )

    if st.button("Start Learning", use_container_width=True):
        if not topic.strip():
            st.warning("Enter a topic.")
        else:
            prompt = (
                f"Subject: {subject}\n"
                f"Level: {class_level}\n"
                f"Topic: {topic}\n"
                f"Task: {action}\n"
                "Make the answer clear, accurate and age-appropriate."
            )

            with st.spinner("Preparing your study material..."):
                answer, provider = ask_ai(prompt)

            st.markdown(answer)
            st.caption("Powered by " + provider)


# ============================================================
# 29. VIDEO STUDIO
# ============================================================

def video_page():
    st.markdown("## 🎬 Video Studio")
    st.caption("Create scripts and prompts for AI video generators.")

    topic = st.text_input("Video topic")
    style = st.selectbox(
        "Video style",
        [
            "Cinematic",
            "Realistic",
            "3D Animation",
            "Anime",
            "Documentary",
            "Advertisement",
            "YouTube Shorts",
            "Instagram Reel"
        ]
    )

    duration = st.selectbox(
        "Video duration",
        ["15 seconds", "30 seconds", "60 seconds", "90 seconds", "2 minutes"]
    )

    language = st.selectbox(
        "Script language",
        ["Hindi", "Hinglish", "English"]
    )

    if st.button("Create Video Plan", use_container_width=True):
        if not topic.strip():
            st.warning("Enter your video topic.")
        else:
            prompt = f"""
Create a complete AI video production plan.

Topic: {topic}
Style: {style}
Duration: {duration}
Language: {language}

Include:
1. Strong opening hook.
2. Scene-by-scene breakdown.
3. Image prompt for every scene.
4. Video animation prompt for every scene.
5. Voiceover/dialogue.
6. Camera movement.
7. Sound and background music suggestions.
8. Editing instructions.

Keep the scene timing consistent with the total duration.
"""
            with st.spinner("Creating video plan..."):
                answer, provider = ask_ai(prompt)

            st.markdown(answer)
            st.caption("Powered by " + provider)


# ============================================================
# 30. AI TOOLS
# ============================================================

def tools_page():
    st.markdown("## 🧰 AI Tools")

    tools_data = [
        ("✍️", "Writing Assistant", "Write, rewrite and improve text."),
        ("📝", "Summary Maker", "Summarize long content."),
        ("💡", "Idea Generator", "Generate creative ideas."),
        ("📧", "Email Writer", "Draft clear professional emails."),
        ("📱", "Social Media", "Create captions and post ideas."),
        ("🧠", "Brainstorm", "Explore concepts and solutions.")
    ]

    cols = st.columns(3)
    for col, item in zip(cols, tools_data):
        with col:
            show_card(item[0], item[1], item[2])

    tool_name = st.selectbox(
        "Choose a tool",
        [
            "Writing Assistant",
            "Summary Maker",
            "Idea Generator",
            "Email Writer",
            "Social Media Caption",
            "Brainstorm"
        ]
    )

    user_input = st.text_area("Enter your content or request", height=180)

    if st.button("Generate", use_container_width=True):
        if not user_input.strip():
            st.warning("Enter some text first.")
        else:
            with st.spinner("Generating..."):
                answer, provider = ask_ai(
                    f"Use the {tool_name}. User input:\n{user_input}"
                )
            st.markdown(answer)
            st.caption("Powered by " + provider)


# ============================================================
# 31. AI SKILL CENTER
# ============================================================

def skill_center_page():
    st.markdown("## 🧠 AI Skill Center")
    st.caption("Learn how to work with AI effectively.")

    skills = {
        "Prompt Engineering": "Teach me prompt engineering from beginner to advanced with examples and practice tasks.",
        "Python Programming": "Create a structured beginner-to-advanced Python learning roadmap.",
        "AI Fundamentals": "Teach me AI fundamentals with simple explanations and examples.",
        "Web Development": "Create a practical web development learning roadmap.",
        "Data Analysis": "Teach me data analysis step by step with exercises."
    }

    skill = st.selectbox("Choose a learning path", list(skills.keys()))

    if st.button("Start Learning", use_container_width=True):
        with st.spinner("Preparing your learning path..."):
            answer, provider = ask_ai(skills[skill])
        st.markdown(answer)
        st.caption("Powered by " + provider)


# ============================================================
# 32. SETTINGS
# ============================================================

def settings_page():
    st.markdown("## ⚙️ Settings")

    st.markdown("### Account")
    if st.session_state.user:
        st.write("Username:", st.session_state.user["username"])
    else:
        st.write("Current mode: Guest")

    st.markdown("### API connection status")

    status_items = [
        ("Groq", bool(GROQ_API_KEY)),
        ("Gemini", bool(GEMINI_API_KEY)),
        ("Tavily", bool(TAVILY_API_KEY)),
        ("Finnhub", bool(FINNHUB_API_KEY)),
        ("Cloudflare", bool(CLOUDFLARE_ACCOUNT_ID and CLOUDFLARE_API_TOKEN)),
        ("Live Voice URL", bool(LIVE_VOICE_URL))
    ]

    for name, active in status_items:
        st.write(
            ("🟢 Connected" if active else "⚪ Not configured"),
            "—",
            name
        )

    st.info(
        "API keys are read from Streamlit Secrets or environment variables. "
        "Never share your private API keys in chat or public repositories."
    )

    st.markdown("### Chat history")

    if st.session_state.user:
        conversations = get_conversations(st.session_state.user["id"])
        st.write(f"Saved conversations: {len(conversations)}")

        if conversations:
            options = {
                f"{item['title']} (ID {item['id']})": item["id"]
                for item in conversations
            }

            selected = st.selectbox(
                "Choose a conversation to manage",
                list(options.keys())
            )

            col1, col2 = st.columns(2)

            with col1:
                new_title = st.text_input("New title")
                if st.button("Rename conversation"):
                    rename_conversation(options[selected], new_title)
                    st.success("Conversation renamed.")
                    st.rerun()

            with col2:
                confirm_delete = st.checkbox("Confirm deletion")
                if st.button("Delete conversation"):
                    if confirm_delete:
                        delete_conversation(options[selected])
                        if st.session_state.conversation_id == options[selected]:
                            st.session_state.conversation_id = None
                            st.session_state.messages = []
                        st.success("Conversation deleted.")
                        st.rerun()
                    else:
                        st.warning("Confirm deletion first.")
    else:
        st.caption("Guest conversations are not stored permanently.")


# ============================================================
# 33. ABOUT
# ============================================================

def about_page():
    st.markdown(
        """
        <div class="ng-hero">
          <div class="ng-kicker">MEET YOUR AI WORKSPACE</div>
          <h1>NEXTGEN AI 🚀</h1>
          <p>YOUR CREATIVE UNIVERSE</p>
          <span class="ng-pill">ONE PLATFORM • ENDLESS POSSIBILITIES</span>
        </div>
        """,
        unsafe_allow_html=True
    )

    st.markdown("""
    NEXTGEN AI is a multi-tool AI workspace built to bring intelligent
    conversations, image generation, document assistance, web research,
    voice tools, coding support and learning tools together.

    **Current capabilities**
    - AI chat with Groq and Gemini providers
    - AI image generation through Cloudflare Workers AI
    - Image understanding through Gemini
    - PDF text extraction and question answering
    - Web search through Tavily
    - Stock quote and chart data through Finnhub
    - Speech transcription through Groq Whisper
    - Text-to-speech through gTTS
    - Optional separate live voice interface

    Some capabilities depend on the availability, limits and configuration
    of their respective providers.
    """)

    st.divider()
    st.caption("NEXTGEN AI © 2026 | Powered by Artificial Intelligence")


# ============================================================
# 34. PAGE ROUTER
# ============================================================

page = st.session_state.page

if page == "Dashboard":
    dashboard_page()

elif page == "AI Chat":
    chat_page()

elif page == "Stock Market":
    stock_page()

elif page == "AI Vision":
    vision_page()

elif page == "PDF Assistant":
    pdf_page()

elif page == "Image Studio":
    image_studio_page()

elif page == "Web Search":
    web_search_page()

elif page == "Voice Studio":
    voice_page()

elif page == "Live Call":
    live_call_page()

elif page == "Coding Lab":
    coding_page()

elif page == "Study Assistant":
    study_page()

elif page == "Video Studio":
    video_page()

elif page == "AI Tools":
    tools_page()

elif page == "AI Skill Center":
    skill_center_page()

elif page == "Settings":
    settings_page()

elif page == "About":
    about_page()


# ============================================================
# 35. FOOTER
# ============================================================

st.markdown("---")
st.markdown(
    """
    <div style="text-align:center;color:#78849e;font-size:12px;padding:12px;">
      NEXTGEN AI © 2026<br>
      YOUR CREATIVE UNIVERSE
    </div>
    """,
    unsafe_allow_html=True
)
