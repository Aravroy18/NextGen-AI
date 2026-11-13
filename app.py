
# ============================================================
# NEXTGEN AI — PREMIUM AI WORKSPACE
# Single-file Streamlit application
# ============================================================

import os
import io
import re
import json
import time
import sqlite3
import base64
import hashlib
from datetime import datetime

import requests
import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import streamlit.components.v1 as components
from pypdf import PdfReader


# ============================================================
# 1. APP CONFIGURATION
# ============================================================

st.set_page_config(
    page_title="NEXTGEN AI",
    page_icon="✦",
    layout="wide",
    initial_sidebar_state="expanded"
)

APP_NAME = "NEXTGEN AI"
DB_FILE = "nextgen_ai.db"

GROQ_URL = "https://api.groq.com/openai/v1/chat/completions"
TAVILY_URL = "https://api.tavily.com/search"
FINNHUB_URL = "https://finnhub.io/api/v1"
OPENAI_URL = "https://api.openai.com/v1"

CHAT_MODEL = "openai/gpt-oss-120b"
REALTIME_MODEL = "gpt-realtime"
TTS_MODEL = "gpt-4o-mini-tts"
TRANSCRIBE_MODEL = "whisper-large-v3"

TTS_VOICES = [
    "alloy", "ash", "ballad", "coral", "echo",
    "fable", "nova", "onyx", "sage", "shimmer",
    "verse", "marin", "cedar"
]

REALTIME_VOICES = [
    "alloy", "ash", "ballad", "coral", "echo",
    "sage", "shimmer", "verse", "marin", "cedar"
]


# ============================================================
# 2. PREMIUM DARK UI
# ============================================================

st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&display=swap');

:root {
    --bg: #080a0f;
    --panel: #10141d;
    --panel2: #151b27;
    --border: rgba(255,255,255,.09);
    --text: #edf2fa;
    --muted: #929daf;
    --accent: #8b9cff;
}

html, body, [class*="css"] {
    font-family: 'Inter', sans-serif;
}

.stApp {
    background:
      radial-gradient(ellipse at 80% 0%, rgba(72,90,170,.12), transparent 36%),
      #080a0f;
    color: var(--text);
}

header[data-testid="stHeader"] {
    background: rgba(8,10,15,.8);
}

section[data-testid="stSidebar"] {
    background: #0c1018;
    border-right: 1px solid var(--border);
}

section[data-testid="stSidebar"] * {
    color: #e7ecf5;
}

.block-container {
    max-width: 1450px;
    padding-top: 2rem;
    padding-bottom: 4rem;
}

h1, h2, h3, h4 {
    letter-spacing: -0.7px;
}

p, label {
    color: #d5dbea;
}

.ng-brand {
    font-size: 23px;
    font-weight: 800;
    letter-spacing: 2px;
    color: #f5f7ff;
}

.ng-brand span {
    color: #91a1ff;
}

.ng-subtitle {
    color: #8994a8;
    font-size: 12px;
    letter-spacing: 2px;
    text-transform: uppercase;
}

.ng-card {
    background: linear-gradient(145deg, #141a26, #10141d);
    border: 1px solid var(--border);
    border-radius: 17px;
    padding: 21px;
    margin-bottom: 14px;
}

.ng-card-title {
    font-size: 13px;
    color: #9ca8bb;
    font-weight: 600;
    text-transform: uppercase;
    letter-spacing: 1px;
}

.ng-card-value {
    font-size: 27px;
    color: #f5f7ff;
    font-weight: 750;
    margin-top: 9px;
}

.ng-muted {
    color: #8994a8;
    font-size: 13px;
}

.ng-hero {
    padding: 27px;
    border: 1px solid rgba(142,158,255,.2);
    border-radius: 20px;
    background: linear-gradient(120deg, #151d31, #10141e 70%);
    margin-bottom: 24px;
}

.ng-hero h1 {
    font-size: clamp(28px, 4vw, 42px);
    margin-bottom: 7px;
}

.ng-hero p {
    color: #aab5c8;
    margin-bottom: 0;
}

.stButton > button {
    background: #202a42;
    color: #f5f7ff;
    border: 1px solid rgba(145,161,255,.25);
    border-radius: 10px;
    min-height: 42px;
    font-weight: 600;
    transition: .2s ease;
}

.stButton > button:hover {
    background: #2b3858;
    border-color: #91a1ff;
    color: white;
}

.stTextInput input,
.stTextArea textarea,
.stSelectbox div[data-baseweb="select"] > div {
    background: #111722 !important;
    color: #f1f4fa !important;
    border-color: #283246 !important;
    border-radius: 10px !important;
}

.stChatMessage {
    background: #111722;
    border: 1px solid var(--border);
    border-radius: 15px;
    padding: 12px;
    margin-bottom: 12px;
}

[data-testid="stChatInput"] {
    background: #111722 !important;
    border: 1px solid #34415a !important;
    border-radius: 16px !important;
}

[data-testid="stChatInput"] textarea {
    color: white !important;
}

.stFileUploader {
    background: #111722;
    border: 1px dashed #34415a;
    border-radius: 12px;
    padding: 10px;
}

hr {
    border-color: rgba(255,255,255,.08);
}

div[data-testid="stMetric"] {
    background: #111722;
    border: 1px solid var(--border);
    padding: 15px;
    border-radius: 14px;
}

footer {
    visibility: hidden;
}

#MainMenu {
    visibility: hidden;
}

.ng-footer {
    text-align: center;
    color: #657187;
    font-size: 11px;
    padding: 35px 0 5px;
    letter-spacing: 1px;
}
</style>
""", unsafe_allow_html=True)


# ============================================================
# 3. SECRETS
# ============================================================

def get_secret(name, default=""):
    try:
        value = st.secrets.get(name, "")
        if value:
            return str(value).strip()
    except Exception:
        pass

    return os.getenv(name, default).strip()


GROQ_API_KEY = get_secret("GROQ_API_KEY")
OPENAI_API_KEY = get_secret("OPENAI_API_KEY")
TAVILY_API_KEY = get_secret("TAVILY_API_KEY")
FINNHUB_API_KEY = get_secret("FINNHUB_API_KEY")


# ============================================================
# 4. DATABASE
# ============================================================

def db_connection():
    conn = sqlite3.connect(DB_FILE, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn


def initialize_database():
    conn = db_connection()
    cur = conn.cursor()

    # Existing database is reused. Existing tables are not deleted.

    cur.execute("""
        CREATE TABLE IF NOT EXISTS ng_v2_chats (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        )
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS ng_v2_messages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            chat_id INTEGER NOT NULL,
            role TEXT NOT NULL,
            content TEXT NOT NULL,
            created_at TEXT NOT NULL,
            FOREIGN KEY(chat_id) REFERENCES ng_v2_chats(id)
        )
    """)

    conn.commit()
    conn.close()


initialize_database()


def create_chat(title="New conversation"):
    now = datetime.now().isoformat(timespec="seconds")
    conn = db_connection()

    cur = conn.cursor()
    cur.execute(
        "INSERT INTO ng_v2_chats(title, created_at, updated_at) VALUES(?,?,?)",
        (title, now, now)
    )

    chat_id = cur.lastrowid
    conn.commit()
    conn.close()

    return chat_id


def save_message(chat_id, role, content):
    now = datetime.now().isoformat(timespec="seconds")
    conn = db_connection()

    conn.execute("""
        INSERT INTO ng_v2_messages(chat_id, role, content, created_at)
        VALUES(?,?,?,?)
    """, (chat_id, role, content, now))

    conn.execute("""
        UPDATE ng_v2_chats SET updated_at=? WHERE id=?
    """, (now, chat_id))

    conn.commit()
    conn.close()


def get_chats():
    conn = db_connection()

    rows = conn.execute("""
        SELECT * FROM ng_v2_chats
        ORDER BY updated_at DESC
    """).fetchall()

    conn.close()
    return rows


def get_messages(chat_id):
    conn = db_connection()

    rows = conn.execute("""
        SELECT role, content, created_at
        FROM ng_v2_messages
        WHERE chat_id=?
        ORDER BY id ASC
    """, (chat_id,)).fetchall()

    conn.close()
    return rows


def rename_chat(chat_id, title):
    conn = db_connection()

    conn.execute("""
        UPDATE ng_v2_chats SET title=?, updated_at=? WHERE id=?
    """, (title[:80], datetime.now().isoformat(timespec="seconds"), chat_id))

    conn.commit()
    conn.close()


def delete_chat(chat_id):
    conn = db_connection()

    conn.execute("DELETE FROM ng_v2_messages WHERE chat_id=?", (chat_id,))
    conn.execute("DELETE FROM ng_v2_chats WHERE id=?", (chat_id,))

    conn.commit()
    conn.close()


# ============================================================
# 5. SESSION STATE
# ============================================================

defaults = {
    "active_chat": None,
    "page": "Dashboard",
    "system_prompt": (
        "You are NEXTGEN AI, a capable and professional AI assistant. "
        "Give accurate, clear, structured and helpful answers. "
        "Respond in the language used by the user. "
        "Do not invent facts. If uncertain, say so."
    ),
    "temperature": 0.7,
    "chat_model": CHAT_MODEL,
    "last_response": "",
    "voice_name": "nova",
    "voice_speed": 1.0,
    "auto_speak": False,
    "search_enabled": False,
}

for key, value in defaults.items():
    if key not in st.session_state:
        st.session_state[key] = value


# ============================================================
# 6. API HELPERS
# ============================================================

def groq_chat(messages, temperature=0.7):
    if not GROQ_API_KEY:
        raise RuntimeError("GROQ_API_KEY is missing in Streamlit Secrets.")

    headers = {
        "Authorization": f"Bearer {GROQ_API_KEY}",
        "Content-Type": "application/json"
    }

    payload = {
        "model": st.session_state.chat_model,
        "messages": messages,
        "temperature": float(temperature),
        "max_tokens": 4096
    }

    response = requests.post(
        GROQ_URL,
        headers=headers,
        json=payload,
        timeout=90
    )

    if not response.ok:
        raise RuntimeError(
            f"Groq API error {response.status_code}: {response.text[:700]}"
        )

    data = response.json()
    return data["choices"][0]["message"]["content"]


def web_search(query):
    if not TAVILY_API_KEY:
        raise RuntimeError("TAVILY_API_KEY is missing.")

    response = requests.post(
        TAVILY_URL,
        json={
            "api_key": TAVILY_API_KEY,
            "query": query,
            "search_depth": "advanced",
            "max_results": 5,
            "include_answer": True
        },
        timeout=45
    )

    if not response.ok:
        raise RuntimeError(f"Search error: {response.text[:400]}")

    return response.json()


def generate_speech(text, voice="nova", speed=1.0):
    if not OPENAI_API_KEY:
        raise RuntimeError("OPENAI_API_KEY is missing.")

    response = requests.post(
        f"{OPENAI_URL}/audio/speech",
        headers={
            "Authorization": f"Bearer {OPENAI_API_KEY}",
            "Content-Type": "application/json"
        },
        json={
            "model": TTS_MODEL,
            "voice": voice,
            "input": text[:4000],
            "speed": float(speed),
            "instructions": (
                "Speak naturally, clearly and conversationally. "
                "Use a normal pace and avoid robotic delivery."
            ),
            "response_format": "mp3"
        },
        timeout=90
    )

    if not response.ok:
        raise RuntimeError(
            f"Speech API error {response.status_code}: {response.text[:500]}"
        )

    return response.content


def transcribe_audio(audio_file):
    if not GROQ_API_KEY:
        raise RuntimeError("GROQ_API_KEY is missing.")

    headers = {"Authorization": f"Bearer {GROQ_API_KEY}"}

    files = {
        "file": (
            audio_file.name,
            audio_file.getvalue(),
            audio_file.type or "audio/wav"
        )
    }

    data = {"model": TRANSCRIBE_MODEL}

    response = requests.post(
        "https://api.groq.com/openai/v1/audio/transcriptions",
        headers=headers,
        files=files,
        data=data,
        timeout=90
    )

    if not response.ok:
        raise RuntimeError(f"Transcription error: {response.text[:500]}")

    return response.json().get("text", "")


def create_realtime_token(voice="marin"):
    if not OPENAI_API_KEY:
        raise RuntimeError("OPENAI_API_KEY is missing.")

    if voice not in REALTIME_VOICES:
        voice = "marin"

    payload = {
        "expires_after": {
            "anchor": "created_at",
            "seconds": 600
        },
        "session": {
            "type": "realtime",
            "model": REALTIME_MODEL,
            "instructions": (
                "You are NEXTGEN AI. Be helpful, natural and clear. "
                "Speak Hindi when the user speaks Hindi and English "
                "when the user speaks English. Keep answers appropriate."
            ),
            "audio": {
                "output": {
                    "voice": voice
                },
                "input": {
                    "turn_detection": {
                        "type": "server_vad"
                    },
                    "transcription": {
                        "model": "gpt-4o-mini-transcribe"
                    }
                }
            }
        }
    }

    response = requests.post(
        f"{OPENAI_URL}/realtime/client_secrets",
        headers={
            "Authorization": f"Bearer {OPENAI_API_KEY}",
            "Content-Type": "application/json"
        },
        json=payload,
        timeout=30
    )

    if not response.ok:
        raise RuntimeError(
            f"Realtime API error {response.status_code}: {response.text[:500]}"
        )

    token = response.json().get("value")

    if not token:
        raise RuntimeError("Realtime API did not return a client token.")

    return token


# ============================================================
# 7. FILE / DOCUMENT PROCESSING
# ============================================================

def extract_pdf_text(uploaded_file):
    reader = PdfReader(io.BytesIO(uploaded_file.getvalue()))
    pages = []

    for index, page in enumerate(reader.pages):
        content = page.extract_text() or ""
        if content.strip():
            pages.append(f"\n[PAGE {index + 1}]\n{content}")

    return "\n".join(pages)


def process_uploaded_file(uploaded_file):
    if uploaded_file is None:
        return ""

    name = uploaded_file.name.lower()

    if name.endswith(".pdf"):
        return extract_pdf_text(uploaded_file)[:18000]

    if name.endswith((".txt", ".md", ".py", ".csv", ".json")):
        return uploaded_file.getvalue().decode(
            "utf-8", errors="replace"
        )[:18000]

    return (
        f"File attached: {uploaded_file.name}. "
        "This file type is not currently supported for text extraction."
    )


# ============================================================
# 8. CHAT RESPONSE ENGINE
# ============================================================

def build_messages(chat_id, user_prompt, extra_context=""):
    history = get_messages(chat_id)

    messages = [
        {
            "role": "system",
            "content": st.session_state.system_prompt
        }
    ]

    for item in history[-16:]:
        if item["role"] in ("user", "assistant"):
            messages.append({
                "role": item["role"],
                "content": item["content"][:12000]
            })

    final_prompt = user_prompt

    if extra_context:
        final_prompt += (
            "\n\nDOCUMENT / ATTACHMENT CONTEXT:\n"
            + extra_context[:18000]
        )

    messages.append({
        "role": "user",
        "content": final_prompt
    })

    return messages


def get_ai_answer(chat_id, prompt, extra_context=""):
    messages = build_messages(chat_id, prompt, extra_context)

    if st.session_state.search_enabled:
        try:
            search_data = web_search(prompt)

            search_context = json.dumps(
                search_data.get("results", []),
                ensure_ascii=False
            )[:10000]

            messages[0]["content"] += (
                "\nUse the following web search results as context. "
                "Clearly distinguish sourced information from uncertainty.\n"
                + search_context
            )

        except Exception as exc:
            st.warning(f"Web search was unavailable: {exc}")

    return groq_chat(
        messages,
        temperature=st.session_state.temperature
    )


# ============================================================
# 9. SIDEBAR NAVIGATION
# ============================================================

with st.sidebar:

    st.markdown(
        '<div class="ng-brand">NEXTGEN<span> AI</span></div>',
        unsafe_allow_html=True
    )

    st.markdown(
        '<div class="ng-subtitle">Intelligence workspace</div>',
        unsafe_allow_html=True
    )

    st.markdown("---")

    pages = [
        "Dashboard",
        "AI Chat",
        "Live Voice",
        "Voice Studio",
        "Web Research",
        "PDF Assistant",
        "Stock Market",
        "Chat History",
        "Settings",
        "About"
    ]

    for page_name in pages:
        if st.button(
            page_name,
            key=f"nav_{page_name}",
            use_container_width=True
        ):
            st.session_state.page = page_name
            st.rerun()

    st.markdown("---")

    if st.button("＋ New Chat", use_container_width=True):
        st.session_state.active_chat = create_chat()
        st.session_state.page = "AI Chat"
        st.rerun()

    st.markdown("### Recent conversations")

    recent_chats = get_chats()

    for chat in recent_chats[:8]:
        label = chat["title"][:26]

        if st.button(
            label,
            key=f"recent_{chat['id']}",
            use_container_width=True
        ):
            st.session_state.active_chat = chat["id"]
            st.session_state.page = "AI Chat"
            st.rerun()

    st.markdown("---")
    st.caption("NEXTGEN AI · Version 2.0")


# ============================================================
# 10. HEADER
# ============================================================

def page_header(title, subtitle):
    st.markdown(f"""
    <div style="margin-bottom:25px">
        <div style="font-size:12px;color:#91a1ff;
        letter-spacing:2px;font-weight:700">NEXTGEN AI WORKSPACE</div>
        <h1 style="font-size:32px;margin:8px 0 4px">{title}</h1>
        <div style="color:#929daf;font-size:14px">{subtitle}</div>
    </div>
    """, unsafe_allow_html=True)


def metric_card(title, value, description=""):
    st.markdown(f"""
    <div class="ng-card">
        <div class="ng-card-title">{title}</div>
        <div class="ng-card-value">{value}</div>
        <div class="ng-muted">{description}</div>
    </div>
    """, unsafe_allow_html=True)


# ============================================================
# 11. DASHBOARD
# ============================================================

def dashboard_page():
    page_header(
        "Your AI workspace",
        "A focused environment for thinking, research and productivity."
    )

    st.markdown("""
    <div class="ng-hero">
        <div class="ng-subtitle">YOUR INTELLIGENT ASSISTANT</div>
        <h1>Think clearly. Create more.</h1>
        <p>
        Chat with AI, explore documents, research topics and work
        with information from one professional workspace.
        </p>
    </div>
    """, unsafe_allow_html=True)

    chats = get_chats()

    total_messages = 0
    conn = db_connection()

    try:
        total_messages = conn.execute(
            "SELECT COUNT(*) FROM ng_v2_messages"
        ).fetchone()[0]
    except Exception:
        pass

    conn.close()

    col1, col2, col3 = st.columns(3)

    with col1:
        metric_card("Conversations", str(len(chats)), "Saved in your local database")

    with col2:
        metric_card("Messages", str(total_messages), "Conversation messages")

    with col3:
        metric_card("AI status", "Ready" if GROQ_API_KEY else "Setup needed",
                    "Groq connection configuration")

    st.markdown("### Explore workspace")

    c1, c2 = st.columns(2)

    with c1:
        with st.container(border=True):
            st.markdown("#### AI Chat")
            st.write("Ask questions, brainstorm, write and learn.")
            if st.button("Open AI Chat", key="dash_chat"):
                st.session_state.page = "AI Chat"
                st.rerun()

        with st.container(border=True):
            st.markdown("#### Document Assistant")
            st.write("Upload a PDF and ask questions about its contents.")
            if st.button("Open PDF Assistant", key="dash_pdf"):
                st.session_state.page = "PDF Assistant"
                st.rerun()

    with c2:
        with st.container(border=True):
            st.markdown("#### Live Voice")
            st.write("Talk with the AI using your microphone.")
            if st.button("Open Live Voice", key="dash_voice"):
                st.session_state.page = "Live Voice"
                st.rerun()

        with st.container(border=True):
            st.markdown("#### Web Research")
            st.write("Search the web and organize useful information.")
            if st.button("Open Research", key="dash_research"):
                st.session_state.page = "Web Research"
                st.rerun()


# ============================================================
# 12. CHAT PAGE
# ============================================================

def chat_page():
    page_header(
        "AI Chat",
        "A conversational workspace powered by your configured AI model."
    )

    if not st.session_state.active_chat:
        st.session_state.active_chat = create_chat()

    chat_id = st.session_state.active_chat
    history = get_messages(chat_id)

    # Display existing history
    for index, item in enumerate(history):
        with st.chat_message(item["role"]):
            st.markdown(item["content"])

            if item["role"] == "assistant":
                with st.popover("Message actions"):
                    st.code(item["content"], language=None)
                    st.caption("Use the copy control in the code block.")

    st.markdown("---")

    uploaded = st.file_uploader(
        "＋ Attach a document or text file",
        type=["pdf", "txt", "md", "py", "csv", "json"],
        key=f"chat_upload_{chat_id}"
    )

    audio_input = st.audio_input(
        "Record a voice message",
        key=f"chat_audio_{chat_id}"
    )

    if audio_input:
        if st.button("Transcribe recording", key=f"transcribe_{chat_id}"):
            try:
                with st.spinner("Transcribing..."):
                    transcript = transcribe_audio(audio_input)

                st.session_state["voice_transcript"] = transcript
                st.success("Transcription ready.")

            except Exception as exc:
                st.error(str(exc))

    prompt = st.chat_input("Message NEXTGEN AI...")

    if prompt is None and st.session_state.get("voice_transcript"):
        prompt = st.session_state.pop("voice_transcript")

    if prompt:
        attachment_context = ""

        if uploaded:
            try:
                attachment_context = process_uploaded_file(uploaded)
            except Exception as exc:
                st.error(f"Could not read attachment: {exc}")

        save_message(chat_id, "user", prompt)

        if len(history) == 0:
            rename_chat(chat_id, prompt[:55])

        with st.chat_message("user"):
            st.markdown(prompt)

        with st.chat_message("assistant"):
            with st.spinner("NEXTGEN AI is thinking..."):
                try:
                    answer = get_ai_answer(
                        chat_id,
                        prompt,
                        attachment_context
                    )

                    st.markdown(answer)

                    save_message(chat_id, "assistant", answer)
                    st.session_state.last_response = answer

                    if st.session_state.auto_speak and OPENAI_API_KEY:
                        audio_bytes = generate_speech(
                            answer,
                            st.session_state.voice_name,
                            st.session_state.voice_speed
                        )
                        st.audio(audio_bytes, format="audio/mp3")

                except Exception as exc:
                    st.error(f"AI response error: {exc}")

        st.rerun()

    if st.session_state.last_response:
        with st.expander("Latest response tools"):
            if st.button("Read latest response aloud"):
                try:
                    audio_bytes = generate_speech(
                        st.session_state.last_response,
                        st.session_state.voice_name,
                        st.session_state.voice_speed
                    )
                    st.audio(audio_bytes, format="audio/mp3")
                except Exception as exc:
                    st.error(str(exc))

            if st.button("Clear response tools"):
                st.session_state.last_response = ""
                st.rerun()


# ============================================================
# 13. LIVE VOICE PAGE
# ============================================================

def live_voice_page():
    page_header(
        "Live Voice",
        "Real-time voice conversation using browser microphone and WebRTC."
    )

    if not OPENAI_API_KEY:
        st.error("Add OPENAI_API_KEY to Streamlit Cloud Secrets to enable Live Voice.")
        return

    selected_voice = st.selectbox(
        "Assistant voice",
        REALTIME_VOICES,
        index=REALTIME_VOICES.index("marin")
    )

    st.info(
        "Your browser will request microphone permission. "
        "Use HTTPS and allow microphone access."
    )

    if st.button("Generate secure voice session", type="primary"):
        try:
            with st.spinner("Preparing secure session..."):
                token = create_realtime_token(selected_voice)

            # Token is short-lived. The permanent API key stays server-side.
            safe_token = json.dumps(token)

            html = """
            <!DOCTYPE html>
            <html>
            <head>
            <style>
            body {
                background:#0d121c;
                color:#eef2fb;
                font-family:Arial,sans-serif;
                text-align:center;
                padding:18px;
            }
            .panel {
                border:1px solid #303c55;
                background:#141c2a;
                padding:24px;
                border-radius:18px;
            }
            button {
                border:1px solid #596b9d;
                background:#28385c;
                color:white;
                padding:13px 24px;
                border-radius:10px;
                margin:8px;
                cursor:pointer;
                font-size:14px;
            }
            button:disabled { opacity:.45; }
            #status { color:#aebbd1; margin:15px; }
            </style>
            </head>
            <body>
            <div class="panel">
                <h2>NEXTGEN AI Voice</h2>
                <p id="status">Ready to connect</p>
                <button id="start">Start conversation</button>
                <button id="stop" disabled>End conversation</button>
                <audio id="remoteAudio" autoplay></audio>
            </div>

            <script>
            const TOKEN = __TOKEN__;

            let pc = null;
            let dc = null;
            let localStream = null;

            const status = document.getElementById("status");
            const start = document.getElementById("start");
            const stop = document.getElementById("stop");
            const audio = document.getElementById("remoteAudio");

            start.onclick = async () => {
                start.disabled = true;
                status.textContent = "Requesting microphone permission...";

                try {
                    localStream = await navigator.mediaDevices.getUserMedia({
                        audio: true
                    });

                    pc = new RTCPeerConnection();

                    pc.ontrack = (event) => {
                        audio.srcObject = event.streams[0];
                    };

                    localStream.getTracks().forEach(track => {
                        pc.addTrack(track, localStream);
                    });

                    dc = pc.createDataChannel("oai-events");

                    dc.onopen = () => {
                        status.textContent = "Connected — start speaking";
                        stop.disabled = false;
                    };

                    dc.onmessage = (event) => {
                        try {
                            const data = JSON.parse(event.data);
                            if (data.type === "error") {
                                status.textContent = "Voice error: " +
                                    (data.error?.message || "Unknown error");
                            }
                        } catch(e) {}
                    };

                    const offer = await pc.createOffer();
                    await pc.setLocalDescription(offer);

                    const response = await fetch(
                        "https://api.openai.com/v1/realtime/calls?model=gpt-realtime",
                        {
                            method: "POST",
                            body: offer.sdp,
                            headers: {
                                "Authorization": "Bearer " + TOKEN,
                                "Content-Type": "application/sdp"
                            }
                        }
                    );

                    if (!response.ok) {
                        throw new Error(await response.text());
                    }

                    const answer = {
                        type: "answer",
                        sdp: await response.text()
                    };

                    await pc.setRemoteDescription(answer);

                    status.textContent = "Connecting...";
                } catch(error) {
                    status.textContent = "Connection failed: " + error.message;
                    start.disabled = false;
                    stop.disabled = true;
                    if (pc) pc.close();
                    if (localStream) {
                        localStream.getTracks().forEach(t => t.stop());
                    }
                }
            };

            stop.onclick = () => {
                if (dc) dc.close();
                if (pc) pc.close();

                if (localStream) {
                    localStream.getTracks().forEach(t => t.stop());
                }

                audio.srcObject = null;
                status.textContent = "Conversation ended";
                start.disabled = false;
                stop.disabled = true;
            };
            </script>
            </body>
            </html>
            """

            html = html.replace("__TOKEN__", safe_token)

            components.html(html, height=330, scrolling=False)

        except Exception as exc:
            st.error(f"Could not start voice session: {exc}")


# ============================================================
# 14. VOICE STUDIO
# ============================================================

def voice_studio_page():
    page_header(
        "Voice Studio",
        "Convert text into natural AI speech."
    )

    if not OPENAI_API_KEY:
        st.error("OPENAI_API_KEY is required for speech generation.")
        return

    text_input = st.text_area(
        "Text to speak",
        height=180,
        placeholder="Enter the text you want NEXTGEN AI to speak..."
    )

    voice = st.selectbox(
        "Voice",
        TTS_VOICES,
        index=TTS_VOICES.index("nova")
    )

    speed = st.slider(
        "Speech speed",
        min_value=0.75,
        max_value=1.5,
        value=1.0,
        step=0.05
    )

    if st.button("Generate speech", type="primary"):
        if not text_input.strip():
            st.warning("Enter some text first.")
        else:
            try:
                with st.spinner("Generating audio..."):
                    audio_bytes = generate_speech(
                        text_input,
                        voice,
                        speed
                    )

                st.success("Speech generated.")
                st.audio(audio_bytes, format="audio/mp3")

                st.download_button(
                    "Download audio",
                    data=audio_bytes,
                    file_name="nextgen_ai_voice.mp3",
                    mime="audio/mpeg"
                )

            except Exception as exc:
                st.error(str(exc))


# ============================================================
# 15. WEB RESEARCH
# ============================================================

def research_page():
    page_header(
        "Web Research",
        "Search the web and turn results into useful summaries."
    )

    if not TAVILY_API_KEY:
        st.warning("Add TAVILY_API_KEY in Streamlit Secrets.")
        return

    query = st.text_input(
        "Research topic",
        placeholder="What would you like to research?"
    )

    depth = st.selectbox(
        "Search depth",
        ["basic", "advanced"]
    )

    if st.button("Search web", type="primary"):
        if not query.strip():
            st.warning("Enter a topic.")
            return

        try:
            with st.spinner("Searching the web..."):
                response = requests.post(
                    TAVILY_URL,
                    json={
                        "api_key": TAVILY_API_KEY,
                        "query": query,
                        "search_depth": depth,
                        "max_results": 8,
                        "include_answer": True
                    },
                    timeout=45
                )

            if not response.ok:
                raise RuntimeError(response.text[:500])

            data = response.json()

            if data.get("answer"):
                st.markdown("### Search summary")
                st.write(data["answer"])

            st.markdown("### Sources")

            for item in data.get("results", []):
                with st.container(border=True):
                    st.markdown(f"**{item.get('title', 'Source')}**")
                    st.write(item.get("content", "")[:700])

                    url = item.get("url")
                    if url:
                        st.markdown(f"[Open source]({url})")

        except Exception as exc:
            st.error(f"Research error: {exc}")


# ============================================================
# 16. PDF ASSISTANT
# ============================================================

def pdf_page():
    page_header(
        "PDF Assistant",
        "Upload a PDF and ask questions about its extracted text."
    )

    uploaded = st.file_uploader(
        "Upload PDF",
        type=["pdf"],
        key="pdf_assistant_upload"
    )

    if uploaded:
        try:
            pdf_text = extract_pdf_text(uploaded)

            if not pdf_text.strip():
                st.warning("No selectable text found in this PDF.")
                return

            st.success("PDF text extracted successfully.")

            with st.expander("Preview extracted text"):
                st.text(pdf_text[:6000])

            question = st.text_area(
                "Ask a question about this document",
                placeholder="Summarize this PDF or explain a specific section..."
            )

            if st.button("Ask about PDF", type="primary"):
                if not question.strip():
                    st.warning("Enter a question.")
                    return

                prompt = (
                    "Answer using the following PDF content. "
                    "If the answer is not present, say so. "
                    "Do not invent details.\n\n"
                    f"PDF CONTENT:\n{pdf_text[:18000]}\n\n"
                    f"QUESTION:\n{question}"
                )

                try:
                    with st.spinner("Analyzing document..."):
                        answer = groq_chat([
                            {
                                "role": "system",
                                "content": st.session_state.system_prompt
                            },
                            {
                                "role": "user",
                                "content": prompt
                            }
                        ])

                    st.markdown("### Answer")
                    st.markdown(answer)

                except Exception as exc:
                    st.error(str(exc))

        except Exception as exc:
            st.error(f"PDF processing error: {exc}")


# ============================================================
# 17. STOCK MARKET DASHBOARD
# ============================================================

def get_stock_quote(symbol):
    if not FINNHUB_API_KEY:
        raise RuntimeError("FINNHUB_API_KEY is missing.")

    response = requests.get(
        f"{FINNHUB_URL}/quote",
        params={
            "symbol": symbol,
            "token": FINNHUB_API_KEY
        },
        timeout=20
    )

    if not response.ok:
        raise RuntimeError(response.text[:300])

    return response.json()


def stock_page():
    page_header(
        "Market Overview",
        "Market information and educational stock analysis."
    )

    if not FINNHUB_API_KEY:
        st.warning("Add FINNHUB_API_KEY to enable live quote data.")
        return

    symbol = st.text_input(
        "Stock symbol",
        value="AAPL",
        placeholder="Example: AAPL, MSFT, NVDA"
    ).upper().strip()

    if st.button("Get market quote", type="primary"):
        if not re.fullmatch(r"[A-Z0-9.^-]{1,15}", symbol):
            st.warning("Enter a valid stock symbol.")
            return

        try:
            with st.spinner("Fetching market data..."):
                quote = get_stock_quote(symbol)

            current = quote.get("c", 0)
            previous = quote.get("pc", 0)
            change = quote.get("d", 0)
            percent = quote.get("dp", 0)

            if not current:
                st.warning("No quote data returned for this symbol.")
                return

            a, b, c = st.columns(3)

            with a:
                st.metric(
                    f"{symbol} price",
                    f"{current:.2f}",
                    f"{change:.2f}"
                )

            with b:
                st.metric("Change %", f"{percent:.2f}%")

            with c:
                st.metric("Previous close", f"{previous:.2f}")

            st.caption(
                "Quote data may be delayed or subject to provider limits."
            )

            st.markdown("### Basic interpretation")

            if change > 0:
                st.success("The latest quote is above the previous close.")
            elif change < 0:
                st.warning("The latest quote is below the previous close.")
            else:
                st.info("The latest quote is unchanged from the previous close.")

            st.info(
                "This page is for educational information only, "
                "not a recommendation to buy or sell."
            )

        except Exception as exc:
            st.error(f"Market data error: {exc}")


# ============================================================
# 18. CHAT HISTORY
# ============================================================

def history_page():
    page_header(
        "Chat History",
        "Review and manage your saved conversations."
    )

    chats = get_chats()

    if not chats:
        st.info("No saved conversations yet.")
        return

    for chat in chats:
        with st.container(border=True):
            left, right = st.columns([5, 1])

            with left:
                st.markdown(f"**{chat['title']}**")
                st.caption(f"Last updated: {chat['updated_at']}")

            with right:
                if st.button("Open", key=f"open_history_{chat['id']}"):
                    st.session_state.active_chat = chat["id"]
                    st.session_state.page = "AI Chat"
                    st.rerun()

            with st.expander("Manage conversation"):
                new_title = st.text_input(
                    "Conversation title",
                    value=chat["title"],
                    key=f"title_{chat['id']}"
                )

                c1, c2 = st.columns(2)

                with c1:
                    if st.button("Save title", key=f"save_title_{chat['id']}"):
                        rename_chat(chat["id"], new_title)
                        st.rerun()

                with c2:
                    if st.button("Delete chat", key=f"delete_{chat['id']}"):
                        delete_chat(chat["id"])

                        if st.session_state.active_chat == chat["id"]:
                            st.session_state.active_chat = None

                        st.rerun()


# ============================================================
# 19. SETTINGS
# ============================================================

def settings_page():
    page_header(
        "Settings",
        "Configure the AI workspace."
    )

    st.markdown("### Chat configuration")

    st.session_state.chat_model = st.selectbox(
        "Groq model",
        [
            "openai/gpt-oss-120b",
            "llama-3.3-70b-versatile",
            "llama-3.1-8b-instant"
        ],
        index=0
    )

    st.session_state.temperature = st.slider(
        "Response creativity",
        min_value=0.0,
        max_value=1.5,
        value=float(st.session_state.temperature),
        step=0.1
    )

    st.session_state.search_enabled = st.toggle(
        "Use web search in AI Chat",
        value=st.session_state.search_enabled
    )

    st.markdown("### Voice settings")

    st.session_state.voice_name = st.selectbox(
        "Default speech voice",
        TTS_VOICES,
        index=TTS_VOICES.index(st.session_state.voice_name)
        if st.session_state.voice_name in TTS_VOICES else 6
    )

    st.session_state.voice_speed = st.slider(
        "Default speech speed",
        0.75,
        1.5,
        float(st.session_state.voice_speed),
        0.05
    )

    st.session_state.auto_speak = st.toggle(
        "Automatically read AI responses aloud",
        value=st.session_state.auto_speak
    )

    st.markdown("### System instructions")

    new_prompt = st.text_area(
        "AI system instructions",
        value=st.session_state.system_prompt,
        height=150
    )

    if st.button("Save settings", type="primary"):
        st.session_state.system_prompt = new_prompt
        st.success("Settings saved for this session.")

    st.markdown("---")
    st.markdown("### API connection status")

    status_items = [
        ("Groq", GROQ_API_KEY),
        ("OpenAI", OPENAI_API_KEY),
        ("Tavily", TAVILY_API_KEY),
        ("Finnhub", FINNHUB_API_KEY)
    ]

    for name, key in status_items:
        if key:
            st.success(f"{name}: Configured")
        else:
            st.warning(f"{name}: Not configured")


# ============================================================
# 20. ABOUT
# ============================================================

def about_page():
    page_header(
        "About NEXTGEN AI",
        "A multi-tool AI workspace."
    )

    st.markdown("""
    <div class="ng-card">
        <h2>NEXTGEN AI</h2>
        <p class="ng-muted">One workspace. Multiple capabilities.</p>
        <hr>
        <p>
        NEXTGEN AI brings conversational AI, document assistance,
        web research, speech generation and market information
        into one interface.
        </p>
        <p class="ng-muted">
        Built with Python and Streamlit.
        </p>
    </div>
    """, unsafe_allow_html=True)

    st.markdown("### Current modules")

    modules = [
        "AI Chat and conversation history",
        "Document and PDF text assistant",
        "Web research",
        "Speech generation",
        "Realtime voice connection",
        "Stock quote lookup",
        "Session-based settings"
    ]

    for item in modules:
        st.markdown(f"- {item}")

    st.caption(
        "AI responses can be inaccurate. Verify important information "
        "with reliable sources."
    )


# ============================================================
# 21. PAGE ROUTER
# ============================================================

current_page = st.session_state.page

if current_page == "Dashboard":
    dashboard_page()

elif current_page == "AI Chat":
    chat_page()

elif current_page == "Live Voice":
    live_voice_page()

elif current_page == "Voice Studio":
    voice_studio_page()

elif current_page == "Web Research":
    research_page()

elif current_page == "PDF Assistant":
    pdf_page()

elif current_page == "Stock Market":
    stock_page()

elif current_page == "Chat History":
    history_page()

elif current_page == "Settings":
    settings_page()

elif current_page == "About":
    about_page()

else:
    dashboard_page()


# ============================================================
# 22. FOOTER
# ============================================================

st.markdown("""
<div class="ng-footer">
    NEXTGEN AI · INTELLIGENCE WORKSPACE · 2026
</div>
""", unsafe_allow_html=True)
