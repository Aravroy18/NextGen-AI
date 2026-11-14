
# ============================================================
# NEXTGEN AI — ULTRA EDITION
# Single-file Streamlit AI Workspace
# ============================================================

import os
import io
import re
import json
import uuid
import time
import html
import sqlite3
import zipfile
import requests
import streamlit as st
import streamlit.components.v1 as components

from datetime import datetime
from dotenv import load_dotenv

load_dotenv()

# ============================================================
# CONFIGURATION
# ============================================================

APP_NAME = "NEXTGEN AI"
DB_PATH = "nextgen_history.db"

st.set_page_config(
    page_title=APP_NAME,
    page_icon="✦",
    layout="wide",
    initial_sidebar_state="expanded"
)

def get_secret(name, default=""):
    try:
        value = st.secrets.get(name, default)
        if value:
            return str(value)
    except Exception:
        pass
    return os.getenv(name, default)


GROQ_KEY = get_secret("GROQ_API_KEY")
GEMINI_KEY = get_secret("GEMINI_API_KEY")
OPENAI_KEY = get_secret("OPENAI_API_KEY")
ANTHROPIC_KEY = get_secret("ANTHROPIC_API_KEY")

TAVILY_KEY = get_secret("TAVILY_API_KEY")
FINNHUB_KEY = get_secret("FINNHUB_API_KEY")

CF_ACCOUNT = get_secret("CLOUDFLARE_ACCOUNT_ID")
CF_TOKEN = get_secret("CLOUDFLARE_API_TOKEN")

GROQ_MODEL = get_secret(
    "GROQ_MODEL",
    "llama-3.3-70b-versatile"
)

GEMINI_MODEL = get_secret(
    "GEMINI_MODEL",
    "gemini-2.5-flash"
)

OPENAI_MODEL = get_secret(
    "OPENAI_MODEL",
    "gpt-4.1-mini"
)

ANTHROPIC_MODEL = get_secret(
    "ANTHROPIC_MODEL",
    "claude-3-5-haiku-latest"
)

# ============================================================
# DATABASE — SAFE MIGRATION
# ============================================================

def db():
    return sqlite3.connect(
        DB_PATH,
        timeout=30,
        check_same_thread=False
    )


def init_db():
    con = db()
    cur = con.cursor()

    cur.execute("""
        CREATE TABLE IF NOT EXISTS chats (
            id TEXT PRIMARY KEY,
            title TEXT,
            created TEXT,
            updated TEXT
        )
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS messages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            chat_id TEXT,
            role TEXT,
            content TEXT,
            created TEXT
        )
    """)

    # Migrate old chats table
    chat_columns = {
        row[1] for row in
        cur.execute("PRAGMA table_info(chats)").fetchall()
    }

    if "title" not in chat_columns:
        cur.execute("ALTER TABLE chats ADD COLUMN title TEXT")

    if "created" not in chat_columns:
        cur.execute("ALTER TABLE chats ADD COLUMN created TEXT")

    if "updated" not in chat_columns:
        cur.execute("ALTER TABLE chats ADD COLUMN updated TEXT")

    # Migrate old messages table
    message_columns = {
        row[1] for row in
        cur.execute("PRAGMA table_info(messages)").fetchall()
    }

    required = {
        "chat_id": "TEXT",
        "role": "TEXT",
        "content": "TEXT",
        "created": "TEXT"
    }

    for column, datatype in required.items():
        if column not in message_columns:
            cur.execute(
                f"ALTER TABLE messages ADD COLUMN {column} {datatype}"
            )

    now = datetime.now().isoformat()

    cur.execute("""
        UPDATE chats
        SET created = COALESCE(created, ?)
        WHERE created IS NULL
    """, (now,))

    cur.execute("""
        UPDATE chats
        SET updated = COALESCE(updated, created, ?)
        WHERE updated IS NULL
    """, (now,))

    cur.execute("""
        CREATE INDEX IF NOT EXISTS idx_messages_chat
        ON messages(chat_id)
    """)

    con.commit()
    con.close()


def create_chat():
    chat_id = str(uuid.uuid4())
    now = datetime.now().isoformat()

    con = db()
    con.execute("""
        INSERT INTO chats(id,title,created,updated)
        VALUES(?,?,?,?)
    """, (chat_id, "New Chat", now, now))
    con.commit()
    con.close()

    return chat_id


def get_chats():
    con = db()

    rows = con.execute("""
        SELECT id, title
        FROM chats
        ORDER BY COALESCE(updated,created) DESC
    """).fetchall()

    con.close()
    return rows


def get_messages(chat_id):
    con = db()

    rows = con.execute("""
        SELECT role,content
        FROM messages
        WHERE chat_id=?
        ORDER BY id ASC
    """, (chat_id,)).fetchall()

    con.close()

    return [
        {"role": role, "content": content}
        for role, content in rows
        if role in ("user", "assistant")
    ]


def save_message(chat_id, role, content):
    con = db()
    now = datetime.now().isoformat()

    con.execute("""
        INSERT INTO messages(chat_id,role,content,created)
        VALUES(?,?,?,?)
    """, (chat_id, role, content, now))

    if role == "user":
        title = content[:48].replace("\n", " ")
        con.execute("""
            UPDATE chats
            SET title=?, updated=?
            WHERE id=?
        """, (title, now, chat_id))
    else:
        con.execute("""
            UPDATE chats SET updated=? WHERE id=?
        """, (now, chat_id))

    con.commit()
    con.close()


def delete_chat(chat_id):
    con = db()
    con.execute("DELETE FROM messages WHERE chat_id=?", (chat_id,))
    con.execute("DELETE FROM chats WHERE id=?", (chat_id,))
    con.commit()
    con.close()


init_db()

# ============================================================
# SESSION STATE
# ============================================================

defaults = {
    "page": "AI Chat",
    "chat_id": None,
    "messages": [],
    "provider": "Auto",
    "last_answer": "",
    "generated_files": {},
    "stock_symbol": "AAPL",
    "pdf_text": "",
    "vision_result": "",
    "notice": ""
}

for key, value in defaults.items():
    if key not in st.session_state:
        st.session_state[key] = value

if not st.session_state.chat_id:
    st.session_state.chat_id = create_chat()

if not st.session_state.messages:
    st.session_state.messages = get_messages(
        st.session_state.chat_id
    )

# ============================================================
# PREMIUM CSS
# ============================================================

st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&display=swap');

html, body, [class*="css"] {
    font-family: Inter, sans-serif;
}

.stApp {
    background:
        radial-gradient(ellipse at 50% -15%, #1b2544 0%, transparent 48%),
        #080b13;
    color: #f5f7ff;
}

header[data-testid="stHeader"] {
    background: transparent;
}

section[data-testid="stSidebar"] {
    background: #0d1220;
    border-right: 1px solid #263149;
}

section[data-testid="stSidebar"] > div {
    background: #0d1220;
}

.brand {
    font-size: 29px;
    font-weight: 800;
    letter-spacing: -1.5px;
    background: linear-gradient(90deg,#9caeff,#d5a5ff,#6ee7d8);
    -webkit-background-clip: text;
    color: transparent;
}

.brand-sub {
    font-size: 11px;
    color: #8793aa;
    letter-spacing: 2px;
}

.hero {
    text-align: center;
    padding: 35px 8px 25px;
}

.hero-logo {
    font-size: clamp(34px,5vw,52px);
    font-weight: 800;
    letter-spacing: -2px;
    background: linear-gradient(90deg,#a5b4fc,#d8b4fe,#5eead4);
    -webkit-background-clip: text;
    color: transparent;
}

.hero-sub {
    color: #8793aa;
    font-size: 14px;
}

.panel {
    background: linear-gradient(145deg,#151e30,#101725);
    border: 1px solid #293650;
    border-radius: 18px;
    padding: 19px;
    margin-bottom: 13px;
}

.small-muted {
    color: #8491a9;
    font-size: 12px;
}

.stButton button {
    border-radius: 11px;
    border: 1px solid #34425e;
    background: #18243a;
    color: #f3f5ff;
    transition: all .2s ease;
}

.stButton button:hover {
    border-color: #a5b4fc;
    color: white;
    background: #24334e;
}

.stDownloadButton button {
    border-radius: 10px;
}

div[data-testid="stChatMessage"] {
    background: transparent;
    border: none;
}

div[data-testid="stChatInput"] {
    border: 1px solid #384765;
    border-radius: 17px;
    background: #121b2c;
}

div[data-testid="stChatInput"] textarea {
    color: white !important;
}

div[data-testid="stFileUploader"] {
    background: #111a2a;
    border: 1px dashed #405171;
    border-radius: 14px;
    padding: 10px;
}

div[data-testid="stMetric"] {
    background: #121b2b;
    border: 1px solid #283750;
    padding: 15px;
    border-radius: 15px;
}

input, textarea {
    color: white !important;
}

hr {
    border-color: #27334a;
}

footer {
    visibility: hidden;
}
</style>
""", unsafe_allow_html=True)

# ============================================================
# AI SYSTEM PROMPT
# ============================================================

SYSTEM_PROMPT = """
You are NEXTGEN AI, an advanced and helpful AI assistant.

You should:
- Understand the user's intent before answering.
- Give accurate, clear and useful answers.
- Respond in the user's language.
- Explain complex concepts in simple steps.
- Help with coding, software, mathematics, science and creativity.
- Use conversation history as context.
- Never invent web search results, live prices or tool outputs.
- Mention uncertainty when information is uncertain.
- For financial questions, provide educational analysis and explain risks.
- Never guarantee investment returns.
- Do not claim a tool was used unless it actually was.
- Keep answers organized and practical.
"""

# ============================================================
# WEB SEARCH
# ============================================================

def web_search(query):
    if not TAVILY_KEY:
        return ""

    response = requests.post(
        "https://api.tavily.com/search",
        json={
            "api_key": TAVILY_KEY,
            "query": query,
            "search_depth": "advanced",
            "max_results": 5
        },
        timeout=25
    )

    response.raise_for_status()
    data = response.json()

    results = []

    for item in data.get("results", []):
        results.append(
            "TITLE: " + str(item.get("title", "")) +
            "\nURL: " + str(item.get("url", "")) +
            "\nCONTENT: " + str(item.get("content", ""))
        )

    return "\n\n".join(results)


def should_search(query):
    words = [
        "latest", "today", "current", "news",
        "weather", "price", "stock", "share",
        "live", "recent", "2026", "2027",
        "अभी", "आज", "ताजा", "लेटेस्ट",
        "शेयर", "मौसम", "भाव", "न्यूज",
        "कीमत", "वर्तमान", "कौन जीता"
    ]

    q = query.lower()
    return any(word in q for word in words)


# ============================================================
# GROQ
# ============================================================

def groq_request(messages):
    if not GROQ_KEY:
        raise RuntimeError("Groq API key is missing")

    response = requests.post(
        "https://api.groq.com/openai/v1/chat/completions",
        headers={
            "Authorization": f"Bearer {GROQ_KEY}",
            "Content-Type": "application/json"
        },
        json={
            "model": GROQ_MODEL,
            "messages": messages,
            "temperature": 0.7,
            "max_tokens": 4000
        },
        timeout=100
    )

    response.raise_for_status()

    return response.json()["choices"][0]["message"]["content"]


# ============================================================
# GEMINI
# ============================================================

def gemini_request(messages):
    if not GEMINI_KEY:
        raise RuntimeError("Gemini API key is missing")

    system = SYSTEM_PROMPT
    contents = []

    for msg in messages:
        if msg["role"] == "system":
            system = msg["content"]
            continue

        role = "model" if msg["role"] == "assistant" else "user"

        contents.append({
            "role": role,
            "parts": [{"text": msg["content"]}]
        })

    response = requests.post(
        "https://generativelanguage.googleapis.com/v1beta/models/"
        + GEMINI_MODEL + ":generateContent",
        params={"key": GEMINI_KEY},
        json={
            "systemInstruction": {
                "parts": [{"text": system}]
            },
            "contents": contents,
            "generationConfig": {
                "temperature": 0.7,
                "maxOutputTokens": 4000
            }
        },
        timeout=100
    )

    response.raise_for_status()
    data = response.json()

    return data["candidates"][0]["content"]["parts"][0]["text"]


# ============================================================
# OPENAI
# ============================================================

def openai_request(messages):
    if not OPENAI_KEY:
        raise RuntimeError("OpenAI API key is missing")

    response = requests.post(
        "https://api.openai.com/v1/chat/completions",
        headers={
            "Authorization": f"Bearer {OPENAI_KEY}",
            "Content-Type": "application/json"
        },
        json={
            "model": OPENAI_MODEL,
            "messages": messages,
            "temperature": 0.7,
            "max_tokens": 4000
        },
        timeout=100
    )

    response.raise_for_status()

    return response.json()["choices"][0]["message"]["content"]


# ============================================================
# ANTHROPIC
# ============================================================

def anthropic_request(messages):
    if not ANTHROPIC_KEY:
        raise RuntimeError("Anthropic API key is missing")

    system = SYSTEM_PROMPT
    conversation = []

    for msg in messages:
        if msg["role"] == "system":
            system = msg["content"]
        else:
            conversation.append({
                "role": msg["role"],
                "content": msg["content"]
            })

    response = requests.post(
        "https://api.anthropic.com/v1/messages",
        headers={
            "x-api-key": ANTHROPIC_KEY,
            "anthropic-version": "2023-06-01",
            "content-type": "application/json"
        },
        json={
            "model": ANTHROPIC_MODEL,
            "max_tokens": 4000,
            "system": system,
            "messages": conversation
        },
        timeout=100
    )

    response.raise_for_status()

    return response.json()["content"][0]["text"]


# ============================================================
# AUTOMATIC MODEL ROUTER
# ============================================================

def ask_ai(messages, selected="Auto"):
    providers = {
        "Groq": (GROQ_KEY, groq_request),
        "Gemini": (GEMINI_KEY, gemini_request),
        "OpenAI": (OPENAI_KEY, openai_request),
        "Claude": (ANTHROPIC_KEY, anthropic_request)
    }

    if selected != "Auto":
        key, function = providers[selected]

        if not key:
            raise RuntimeError(
                selected + " API key is not configured."
            )

        return function(messages), selected

    errors = []

    # Automatic fallback order
    order = ["Groq", "Gemini", "OpenAI", "Claude"]

    for name in order:
        key, function = providers[name]

        if not key:
            continue

        try:
            return function(messages), name

        except Exception as exc:
            errors.append(
                name + ": " + str(exc)[:250]
            )

    raise RuntimeError(
        "No configured AI provider could answer.\n"
        + ("\n".join(errors) if errors else
           "Add at least one AI API key in Streamlit Secrets.")
    )


# ============================================================
# SMART AI RESPONSE
# ============================================================

def generate_answer(prompt, history, selected="Auto"):
    messages = [
        {"role": "system", "content": SYSTEM_PROMPT}
    ]

    messages.extend(history[-18:])

    search_context = ""

    if should_search(prompt):
        try:
            results = web_search(prompt)

            if results:
                search_context = (
                    "\n\nWEB SEARCH RESULTS:\n"
                    + results
                    + "\nUse these results carefully. "
                    "Cite source URLs in your answer."
                )

        except Exception:
            search_context = (
                "\nWeb search was attempted but unavailable. "
                "Do not invent current facts."
            )

    if search_context:
        messages.append({
            "role": "system",
            "content": search_context
        })

    return ask_ai(messages, selected)


# ============================================================
# PDF READER
# ============================================================

def extract_pdf(uploaded_file):
    try:
        from pypdf import PdfReader

        reader = PdfReader(uploaded_file)
        pages = []

        for page in reader.pages:
            pages.append(page.extract_text() or "")

        return "\n\n".join(pages)

    except ImportError:
        raise RuntimeError(
            "PDF support requires pypdf in requirements.txt"
        )


# ============================================================
# VOICE TRANSCRIPTION
# ============================================================

def transcribe_audio(audio_file):
    if not GROQ_KEY:
        raise RuntimeError(
            "Voice transcription requires GROQ_API_KEY"
        )

    audio_file.seek(0)

    response = requests.post(
        "https://api.groq.com/openai/v1/audio/transcriptions",
        headers={
            "Authorization": f"Bearer {GROQ_KEY}"
        },
        files={
            "file": (
                "recording.wav",
                audio_file,
                "audio/wav"
            )
        },
        data={
            "model": "whisper-large-v3"
        },
        timeout=120
    )

    response.raise_for_status()

    return response.json().get("text", "")


# ============================================================
# CLOUDFLARE IMAGE GENERATION
# ============================================================

def generate_image(prompt):
    if not CF_ACCOUNT or not CF_TOKEN:
        raise RuntimeError(
            "Cloudflare account ID or API token is missing"
        )

    model = "@cf/black-forest-labs/flux-1-schnell"

    url = (
        "https://api.cloudflare.com/client/v4/accounts/"
        + CF_ACCOUNT
        + "/ai/run/"
        + model
    )

    response = requests.post(
        url,
        headers={
            "Authorization": "Bearer " + CF_TOKEN
        },
        json={
            "prompt": prompt
        },
        timeout=180
    )

    response.raise_for_status()

    return response.content


# ============================================================
# FINNHUB STOCK DATA
# ============================================================

def stock_quote(symbol):
    if not FINNHUB_KEY:
        raise RuntimeError("FINNHUB_API_KEY is missing")

    response = requests.get(
        "https://finnhub.io/api/v1/quote",
        params={
            "symbol": symbol.upper(),
            "token": FINNHUB_KEY
        },
        timeout=20
    )

    response.raise_for_status()
    data = response.json()

    if not data or not data.get("c"):
        raise RuntimeError(
            "No quote data available for this symbol"
        )

    return data


def stock_profile(symbol):
    response = requests.get(
        "https://finnhub.io/api/v1/stock/profile2",
        params={
            "symbol": symbol.upper(),
            "token": FINNHUB_KEY
        },
        timeout=20
    )

    response.raise_for_status()
    return response.json()


def stock_candles(symbol, resolution="D"):
    import pandas as pd

    end = int(time.time())
    start = end - (90 * 24 * 60 * 60)

    response = requests.get(
        "https://finnhub.io/api/v1/stock/candle",
        params={
            "symbol": symbol.upper(),
            "resolution": resolution,
            "from": start,
            "to": end,
            "token": FINNHUB_KEY
        },
        timeout=30
    )

    response.raise_for_status()
    data = response.json()

    if data.get("s") != "ok":
        raise RuntimeError("No historical candle data available")

    return pd.DataFrame({
        "Date": pd.to_datetime(data["t"], unit="s"),
        "Open": data["o"],
        "High": data["h"],
        "Low": data["l"],
        "Close": data["c"],
        "Volume": data["v"]
    })


# ============================================================
# APP BUILDER
# ============================================================

def build_project(prompt):
    system = """
You are a software project generator.

Return ONLY valid JSON in this format:
{
  "project_name": "project",
  "files": [
    {
      "path": "index.html",
      "content": "complete file content"
    }
  ]
}

Create a complete small project.
Include all necessary source files.
Do not use markdown fences.
Never omit required code.
"""

    messages = [
        {"role": "system", "content": system},
        {"role": "user", "content": prompt}
    ]

    answer, provider = ask_ai(messages, "Auto")

    cleaned = re.sub(
        r"^```(?:json)?\s*|\s*```$",
        "",
        answer.strip(),
        flags=re.IGNORECASE
    )

    data = json.loads(cleaned)

    files = data.get("files", [])

    if not files:
        raise RuntimeError("AI returned no project files")

    return data, provider


def create_zip(files):
    output = io.BytesIO()

    with zipfile.ZipFile(
        output,
        "w",
        zipfile.ZIP_DEFLATED
    ) as archive:

        for item in files:
            path = item["path"].replace("\\", "/")

            if path.startswith("/") or ".." in path.split("/"):
                continue

            archive.writestr(
                path,
                item["content"]
            )

    output.seek(0)
    return output.getvalue()


# ============================================================
# SIDEBAR
# ============================================================

with st.sidebar:

    st.markdown(
        '<div class="brand">✦ NEXTGEN AI</div>'
        '<div class="brand-sub">INTELLIGENT WORKSPACE</div>',
        unsafe_allow_html=True
    )

    st.write("")

    if st.button(
        "＋  New Chat",
        use_container_width=True,
        key="new_chat"
    ):
        st.session_state.chat_id = create_chat()
        st.session_state.messages = []
        st.rerun()

    st.divider()

    st.markdown("### Workspace")

    pages = [
        "AI Chat",
        "Build Studio",
        "Creative Studio",
        "Vision Studio",
        "PDF Assistant",
        "Stock Dashboard",
        "Settings"
    ]

    for page_name in pages:
        if st.button(
            page_name,
            key="nav_" + page_name,
            use_container_width=True,
            type=(
                "primary"
                if st.session_state.page == page_name
                else "secondary"
            )
        ):
            st.session_state.page = page_name
            st.rerun()

    st.divider()

    st.markdown("### Chat History")

    for cid, title in get_chats()[:35]:

        col1, col2 = st.columns([5, 1])

        with col1:
            if st.button(
                "● " + (title or "New Chat")[:25],
                key="history_" + str(cid),
                use_container_width=True
            ):
                st.session_state.chat_id = cid
                st.session_state.messages = get_messages(cid)
                st.session_state.page = "AI Chat"
                st.rerun()

        with col2:
            if st.button(
                "×",
                key="remove_" + str(cid)
            ):
                st.session_state.delete_chat_id = cid
                st.rerun()

    if st.session_state.get("delete_chat_id"):
        st.warning("Delete selected chat?")

        if st.button("Confirm Delete", key="confirm_delete"):
            target = st.session_state.delete_chat_id
            delete_chat(target)

            if target == st.session_state.chat_id:
                st.session_state.chat_id = create_chat()
                st.session_state.messages = []

            st.session_state.delete_chat_id = None
            st.rerun()

    st.divider()

    st.markdown("### AI Status")

    providers = [
        ("Groq", GROQ_KEY),
        ("Gemini", GEMINI_KEY),
        ("OpenAI", OPENAI_KEY),
        ("Claude", ANTHROPIC_KEY),
        ("Web Search", TAVILY_KEY),
        ("Cloudflare", CF_TOKEN),
        ("Finnhub", FINNHUB_KEY)
    ]

    for name, key in providers:
        status = "Connected" if key else "Not configured"
        color = "#5ee7a0" if key else "#e5a56b"

        st.markdown(
            f'<div style="display:flex;justify-content:space-between;'
            f'padding:5px 0;font-size:12px">'
            f'<span>{html.escape(name)}</span>'
            f'<span style="color:{color}">{status}</span></div>',
            unsafe_allow_html=True
        )

    st.divider()
    st.caption("NEXTGEN AI • ULTRA EDITION")


# ============================================================
# MAIN HEADER
# ============================================================

st.markdown("""
<div class="hero">
    <div class="hero-logo">✦ NEXTGEN AI</div>
    <div class="hero-sub">
        Think smarter. Create faster. Build anything.
    </div>
</div>
""", unsafe_allow_html=True)


# ============================================================
# AI CHAT PAGE
# ============================================================

if st.session_state.page == "AI Chat":

    top1, top2 = st.columns([3, 1])

    with top1:
        st.markdown("### AI Chat")
        st.caption("Your intelligent AI assistant")

    with top2:
        selected_provider = st.selectbox(
            "AI Engine",
            ["Auto", "Groq", "Gemini", "OpenAI", "Claude"],
            index=0,
            key="chat_provider"
        )

    # Welcome cards
    if not st.session_state.messages:

        st.markdown(
            "<h3 style='text-align:center'>"
            "What would you like to explore?"
            "</h3>",
            unsafe_allow_html=True
        )

        a, b, c = st.columns(3)

        with a:
            st.markdown(
                '<div class="panel">💻 <b>Build</b>'
                '<p class="small-muted">Create apps and websites</p></div>',
                unsafe_allow_html=True
            )

        with b:
            st.markdown(
                '<div class="panel">🌐 <b>Research</b>'
                '<p class="small-muted">Explore and understand topics</p></div>',
                unsafe_allow_html=True
            )

        with c:
            st.markdown(
                '<div class="panel">📊 <b>Analyze</b>'
                '<p class="small-muted">Understand data and markets</p></div>',
                unsafe_allow_html=True
            )

    # Display conversation
    for index, message in enumerate(st.session_state.messages):

        with st.chat_message(message["role"]):
            st.markdown(message["content"])

            if message["role"] == "assistant":
                with st.popover("Message actions"):
                    st.code(
                        message["content"],
                        language=None
                    )

                    st.caption(
                        "Use the code block copy control to copy this answer."
                    )

    # Attachments
    with st.expander("＋ Attach files and documents"):
        uploaded = st.file_uploader(
            "Upload PDF, TXT or supported document",
            type=["pdf", "txt", "csv", "md"],
            key="chat_attachment"
        )

    if uploaded:
        st.caption("Attached: " + uploaded.name)

    # Voice input
    with st.expander("🎙 Voice input"):
        audio = st.audio_input("Record your message")

        if audio:
            if st.button("Transcribe voice", key="transcribe_chat"):
                try:
                    transcript = transcribe_audio(audio)
                    st.session_state.voice_text = transcript
                    st.success("Transcription complete")
                    st.text_area(
                        "Transcribed message",
                        value=transcript,
                        key="transcribed_text"
                    )
                except Exception as exc:
                    st.error(str(exc))

    # Main chat input
    prompt = st.chat_input("Message NEXTGEN AI...")

    if prompt:

        full_prompt = prompt

        if uploaded:
            try:
                if uploaded.name.lower().endswith(".pdf"):
                    pdf_content = extract_pdf(uploaded)
                    full_prompt += (
                        "\n\nDocument content:\n"
                        + pdf_content[:25000]
                    )

                elif uploaded.name.lower().endswith(".txt"):
                    full_prompt += (
                        "\n\nDocument content:\n"
                        + uploaded.getvalue().decode(
                            "utf-8",
                            errors="replace"
                        )[:25000]
                    )

                elif uploaded.name.lower().endswith(".md"):
                    full_prompt += (
                        "\n\nDocument content:\n"
                        + uploaded.getvalue().decode(
                            "utf-8",
                            errors="replace"
                        )[:25000]
                    )

                else:
                    full_prompt += (
                        "\n\nUploaded file: "
                        + uploaded.name
                        + ". Please explain what information "
                        "you need from this file."
                    )

            except Exception as exc:
                st.error("Attachment error: " + str(exc))

        save_message(
            st.session_state.chat_id,
            "user",
            full_prompt
        )

        st.session_state.messages.append({
            "role": "user",
            "content": full_prompt
        })

        with st.chat_message("user"):
            st.markdown(prompt)

            if uploaded:
                st.caption("📎 " + uploaded.name)

        with st.chat_message("assistant"):

            with st.spinner("NEXTGEN AI is thinking..."):

                try:
                    answer, provider = generate_answer(
                        full_prompt,
                        st.session_state.messages[:-1],
                        selected_provider
                    )

                    st.markdown(answer)
                    st.caption("AI Engine: " + provider)

                    save_message(
                        st.session_state.chat_id,
                        "assistant",
                        answer
                    )

                    st.session_state.messages.append({
                        "role": "assistant",
                        "content": answer
                    })

                    st.session_state.last_answer = answer

                except Exception as exc:
                    st.error(
                        "NEXTGEN AI could not respond.\n\n"
                        + str(exc)
                    )

        st.rerun()


# ============================================================
# BUILD STUDIO
# ============================================================

elif st.session_state.page == "Build Studio":

    st.markdown("## 🛠 Build Studio")
    st.caption("Generate starter projects using AI.")

    project_type = st.selectbox(
        "Project type",
        [
            "Website",
            "Web Application",
            "Python Application",
            "Portfolio",
            "Landing Page",
            "Dashboard"
        ]
    )

    project_prompt = st.text_area(
        "Describe your project",
        placeholder=(
            "Example: Build a modern portfolio website "
            "with responsive design and contact section."
        ),
        height=150
    )

    if st.button("✦ Generate Project", type="primary"):

        if not project_prompt.strip():
            st.warning("Describe your project first.")

        else:
            with st.spinner("AI is building your project..."):

                try:
                    data, provider = build_project(
                        project_type + "\n" + project_prompt
                    )

                    files = data["files"]

                    st.success(
                        "Project generated using " + provider
                    )

                    st.markdown(
                        "### " + data.get(
                            "project_name",
                            "Generated Project"
                        )
                    )

                    for item in files:
                        with st.expander(item["path"]):
                            st.code(
                                item["content"],
                                language="text"
                            )

                    archive = create_zip(files)

                    st.download_button(
                        "⬇ Download Project ZIP",
                        data=archive,
                        file_name="nextgen_project.zip",
                        mime="application/zip"
                    )

                except Exception as exc:
                    st.error(
                        "Project generation failed: " + str(exc)
                    )


# ============================================================
# CREATIVE STUDIO
# ============================================================

elif st.session_state.page == "Creative Studio":

    st.markdown("## 🎨 Creative Studio")
    st.caption("Generate images with Cloudflare AI.")

    image_prompt = st.text_area(
        "Describe the image",
        placeholder=(
            "A futuristic neon city at night, cinematic lighting..."
        ),
        height=130
    )

    if st.button("Generate Image", type="primary"):

        if not image_prompt.strip():
            st.warning("Enter an image description.")

        else:
            with st.spinner("Creating image..."):

                try:
                    image_bytes = generate_image(image_prompt)

                    st.image(
                        image_bytes,
                        caption="Generated by Cloudflare AI",
                        use_container_width=True
                    )

                    st.download_button(
                        "Download Image",
                        data=image_bytes,
                        file_name="nextgen_image.png",
                        mime="image/png"
                    )

                except Exception as exc:
                    st.error(str(exc))


# ============================================================
# VISION STUDIO
# ============================================================

elif st.session_state.page == "Vision Studio":

    st.markdown("## 👁 Vision Studio")
    st.caption("Upload an image and ask AI to understand it.")

    image_file = st.file_uploader(
        "Upload an image",
        type=["png", "jpg", "jpeg", "webp"],
        key="vision_upload"
    )

    vision_question = st.text_input(
        "What should AI understand?",
        value="Describe this image in detail."
    )

    if image_file:
        st.image(
            image_file,
            use_container_width=True
        )

    if st.button("Analyze Image", type="primary"):

        if not image_file:
            st.warning("Upload an image first.")

        elif not GEMINI_KEY:
            st.error(
                "Vision analysis requires GEMINI_API_KEY."
            )

        else:
            try:
                import base64

                encoded = base64.b64encode(
                    image_file.getvalue()
                ).decode("utf-8")

                mime = image_file.type or "image/jpeg"

                response = requests.post(
                    "https://generativelanguage.googleapis.com/v1beta/models/"
                    + GEMINI_MODEL + ":generateContent",
                    params={"key": GEMINI_KEY},
                    json={
                        "contents": [{
                            "parts": [
                                {"text": vision_question},
                                {
                                    "inline_data": {
                                        "mime_type": mime,
                                        "data": encoded
                                    }
                                }
                            ]
                        }]
                    },
                    timeout=100
                )

                response.raise_for_status()

                result = response.json()["candidates"][0][
                    "content"
                ]["parts"][0]["text"]

                st.markdown("### Analysis")
                st.write(result)

            except Exception as exc:
                st.error(str(exc))


# ============================================================
# PDF ASSISTANT
# ============================================================

elif st.session_state.page == "PDF Assistant":

    st.markdown("## 📄 PDF Assistant")

    pdf = st.file_uploader(
        "Upload PDF",
        type=["pdf"],
        key="pdf_upload"
    )

    if pdf:
        if st.button("Extract PDF Text"):

            try:
                st.session_state.pdf_text = extract_pdf(pdf)
                st.success("PDF text extracted.")

            except Exception as exc:
                st.error(str(exc))

    if st.session_state.pdf_text:

        st.text_area(
            "Extracted content",
            value=st.session_state.pdf_text[:20000],
            height=250
        )

        question = st.text_input(
            "Ask something about this PDF"
        )

        if st.button("Ask about PDF"):

            if question.strip():

                prompt = (
                    "Answer using this PDF content:\n\n"
                    + st.session_state.pdf_text[:25000]
                    + "\n\nQuestion: "
                    + question
                )

                with st.spinner("Analyzing document..."):

                    try:
                        answer, provider = ask_ai([
                            {
                                "role": "system",
                                "content": SYSTEM_PROMPT
                            },
                            {
                                "role": "user",
                                "content": prompt
                            }
                        ])

                        st.markdown(answer)
                        st.caption("AI Engine: " + provider)

                    except Exception as exc:
                        st.error(str(exc))


# ============================================================
# STOCK DASHBOARD
# ============================================================

elif st.session_state.page == "Stock Dashboard":

    st.markdown("## 📈 Stock Market Dashboard")

    st.caption(
        "Market information is for educational purposes only."
    )

    symbol = st.text_input(
        "Stock symbol",
        value=st.session_state.stock_symbol
    ).upper().strip()

    if st.button("Load Market Data", type="primary"):

        if not FINNHUB_KEY:
            st.error("Add FINNHUB_API_KEY in Streamlit Secrets.")

        elif not symbol:
            st.warning("Enter a stock symbol.")

        else:
            try:
                quote = stock_quote(symbol)
                profile = stock_profile(symbol)

                st.session_state.stock_quote = quote
                st.session_state.stock_profile = profile
                st.session_state.stock_symbol = symbol

            except Exception as exc:
                st.error(str(exc))

    if st.session_state.get("stock_quote"):

        quote = st.session_state.stock_quote
        profile = st.session_state.get(
            "stock_profile",
            {}
        )

        st.markdown(
            "### " + profile.get("name", symbol)
        )

        c1, c2, c3 = st.columns(3)

        c1.metric(
            "Current Price",
            f"${quote.get('c', 0):,.2f}"
        )

        c2.metric(
            "Change",
            f"${quote.get('d', 0):,.2f}",
            f"{quote.get('dp', 0):.2f}%"
        )

        c3.metric(
            "Previous Close",
            f"${quote.get('pc', 0):,.2f}"
        )

        try:
            import pandas as pd

            chart = stock_candles(symbol)

            st.markdown("### Historical Price")

            st.line_chart(
                chart.set_index("Date")["Close"]
            )

            st.dataframe(
                chart.tail(15),
                use_container_width=True
            )

        except Exception as exc:
            st.info("Historical chart unavailable: " + str(exc))

        st.warning(
            "This is market information, not a personalized "
            "investment recommendation. Prices may be delayed."
        )


# ============================================================
# SETTINGS
# ============================================================

elif st.session_state.page == "Settings":

    st.markdown("## ⚙ Settings")

    st.markdown("### AI Provider Status")

    for name, key in [
        ("Groq", GROQ_KEY),
        ("Gemini", GEMINI_KEY),
        ("OpenAI", OPENAI_KEY),
        ("Anthropic", ANTHROPIC_KEY),
        ("Tavily Search", TAVILY_KEY),
        ("Cloudflare", CF_TOKEN),
        ("Finnhub", FINNHUB_KEY)
    ]:

        c1, c2 = st.columns([2, 1])

        c1.write(name)

        if key:
            c2.success("Configured")
        else:
            c2.warning("Missing")

    st.divider()

    st.markdown("### Model Configuration")

    st.code(
        "Groq: " + GROQ_MODEL + "\n"
        "Gemini: " + GEMINI_MODEL + "\n"
        "OpenAI: " + OPENAI_MODEL + "\n"
        "Claude: " + ANTHROPIC_MODEL
    )

    st.caption(
        "Model names can be changed through Streamlit Secrets."
    )

    st.divider()

    st.markdown("### Database")

    if st.button("Check Database"):

        try:
            con = db()

            chat_count = con.execute(
                "SELECT COUNT(*) FROM chats"
            ).fetchone()[0]

            message_count = con.execute(
                "SELECT COUNT(*) FROM messages"
            ).fetchone()[0]

            con.close()

            st.success("Database connection successful.")

            a, b = st.columns(2)

            a.metric("Chats", chat_count)
            b.metric("Messages", message_count)

        except Exception as exc:
            st.error(str(exc))


# ============================================================
# FOOTER
# ============================================================

st.markdown("""
<div style="
text-align:center;
padding:35px 0 15px;
color:#74819a;
font-size:11px;
">
✦ NEXTGEN AI • ULTRA EDITION
<br>
An intelligent workspace
</div>
""", unsafe_allow_html=True)
