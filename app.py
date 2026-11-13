import os
import io
import sqlite3
from pathlib import Path

import requests
import streamlit as st
import streamlit.components.v1 as components

from pypdf import PdfReader

from voicecall import (
    create_client_secret,
    generate_speech,
    VOICES,
    REALTIME_VOICES
)

# ---------------- CONFIG ----------------

st.set_page_config(
    page_title="NEXTGEN AI",
    page_icon="✦",
    layout="wide",
    initial_sidebar_state="expanded"
)

DB_PATH = Path(__file__).with_name("nextgen_ai.db")


# ---------------- SECRETS ----------------

def secret(name, default=""):
    try:
        value = st.secrets.get(name, default)
        if value:
            return str(value)
    except Exception:
        pass

    return os.getenv(name, default)


GROQ_API_KEY = secret("GROQ_API_KEY")
OPENAI_API_KEY = secret("OPENAI_API_KEY")
TAVILY_API_KEY = secret("TAVILY_API_KEY")


# ---------------- DATABASE ----------------

def db():
    return sqlite3.connect(DB_PATH, check_same_thread=False)


def init_db():
    with db() as con:
        con.execute("""
            CREATE TABLE IF NOT EXISTS ng_v2_chats (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        con.execute("""
            CREATE TABLE IF NOT EXISTS ng_v2_messages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                chat_id INTEGER NOT NULL,
                role TEXT NOT NULL,
                content TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)


init_db()


def create_chat():
    with db() as con:
        cur = con.execute(
            "INSERT INTO ng_v2_chats (title) VALUES (?)",
            ("New conversation",)
        )
        return cur.lastrowid


def save_message(chat_id, role, content):
    with db() as con:
        con.execute(
            """
            INSERT INTO ng_v2_messages
            (chat_id, role, content)
            VALUES (?, ?, ?)
            """,
            (chat_id, role, content)
        )


def get_chats():
    with db() as con:
        return con.execute(
            """
            SELECT id, title, created_at
            FROM ng_v2_chats
            ORDER BY id DESC
            """
        ).fetchall()


def get_messages(chat_id):
    with db() as con:
        return con.execute(
            """
            SELECT role, content
            FROM ng_v2_messages
            WHERE chat_id = ?
            ORDER BY id ASC
            """,
            (chat_id,)
        ).fetchall()


def update_title(chat_id, title):
    title = title.strip().replace("\n", " ")[:55]

    if not title:
        return

    with db() as con:
        con.execute(
            "UPDATE ng_v2_chats SET title=? WHERE id=?",
            (title, chat_id)
        )


# ---------------- AI ENGINE ----------------

def groq_chat(messages):
    if not GROQ_API_KEY:
        raise RuntimeError("GROQ_API_KEY is missing in Secrets.")

    response = requests.post(
        "https://api.groq.com/openai/v1/chat/completions",
        headers={
            "Authorization": f"Bearer {GROQ_API_KEY}",
            "Content-Type": "application/json"
        },
        json={
            "model": "openai/gpt-oss-120b",
            "messages": messages,
            "temperature": 0.7,
            "max_tokens": 1800
        },
        timeout=90
    )

    if not response.ok:
        raise RuntimeError(
            f"Groq error {response.status_code}: "
            f"{response.text[:600]}"
        )

    data = response.json()

    return data["choices"][0]["message"]["content"]


def web_search(query):
    if not TAVILY_API_KEY:
        return "Web search is not configured. Add TAVILY_API_KEY."

    response = requests.post(
        "https://api.tavily.com/search",
        json={
            "api_key": TAVILY_API_KEY,
            "query": query,
            "search_depth": "basic",
            "max_results": 5
        },
        timeout=30
    )

    if not response.ok:
        raise RuntimeError("Web search failed.")

    results = response.json().get("results", [])

    lines = []

    for item in results:
        lines.append(
            f"Title: {item.get('title', '')}\n"
            f"URL: {item.get('url', '')}\n"
            f"Content: {item.get('content', '')}"
        )

    return "\n\n".join(lines)


# ---------------- FILE READER ----------------

def read_upload(upload):
    name = upload.name.lower()

    if name.endswith(".txt"):
        return upload.getvalue().decode(
            "utf-8",
            errors="ignore"
        )

    if name.endswith(".pdf"):
        reader = PdfReader(io.BytesIO(upload.getvalue()))

        pages = []

        for page in reader.pages:
            pages.append(page.extract_text() or "")

        return "\n\n".join(pages)

    return (
        f"User attached {upload.name}. "
        "This file type is not text-extractable in this version."
    )


# ---------------- VOICE TRANSCRIPTION ----------------

def transcribe_audio(audio_file):
    if not GROQ_API_KEY:
        raise RuntimeError("GROQ_API_KEY is missing.")

    files = {
        "file": (
            "recording.wav",
            audio_file.getvalue(),
            "audio/wav"
        )
    }

    response = requests.post(
        "https://api.groq.com/openai/v1/audio/transcriptions",
        headers={
            "Authorization": f"Bearer {GROQ_API_KEY}"
        },
        data={
            "model": "whisper-large-v3-turbo",
            "response_format": "json"
        },
        files=files,
        timeout=90
    )

    if not response.ok:
        raise RuntimeError(
            f"Transcription failed: {response.text[:400]}"
        )

    return response.json().get("text", "")


# ---------------- PREMIUM UI ----------------

st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&display=swap');

:root {
    --bg: #090b10;
    --panel: #111722;
    --border: #252e3d;
    --muted: #8e9aad;
    --text: #f4f6fa;
    --accent: #647bff;
}

html, body, [data-testid="stAppViewContainer"] {
    background: var(--bg);
    color: var(--text);
    font-family: Inter, sans-serif;
}

[data-testid="stHeader"] {
    background: rgba(9,11,16,.92);
}

[data-testid="stSidebar"] {
    background: #0d1119;
    border-right: 1px solid var(--border);
}

[data-testid="stSidebar"] * {
    color: #e7ebf3;
}

.block-container {
    max-width: 1150px;
    padding-top: 2rem;
    padding-bottom: 5rem;
}

h1, h2, h3 {
    letter-spacing: -0.6px;
}

.hero {
    padding: 28px;
    border: 1px solid var(--border);
    border-radius: 20px;
    background: linear-gradient(130deg,#151d2b,#10141e 65%,#11172a);
    margin-bottom: 22px;
}

.hero-title {
    font-size: 34px;
    font-weight: 800;
    letter-spacing: -1.3px;
}

.hero-sub {
    color: var(--muted);
    margin-top: 8px;
}

.metric-card {
    border: 1px solid var(--border);
    background: var(--panel);
    border-radius: 16px;
    padding: 20px;
    min-height: 110px;
}

.metric-label {
    color: var(--muted);
    font-size: 13px;
}

.metric-value {
    font-size: 25px;
    font-weight: 750;
    margin-top: 8px;
}

[data-testid="stChatMessage"] {
    border: 1px solid #202838;
    background: #111722;
    border-radius: 15px;
    padding: 12px;
    margin-bottom: 12px;
}

[data-testid="stChatInput"] {
    background: #111722;
    border: 1px solid #39445a;
    border-radius: 18px;
}

[data-testid="stChatInput"] textarea {
    color: #ffffff !important;
    background: transparent !important;
}

[data-testid="stChatInput"] button {
    color: #ffffff !important;
}

[data-testid="stFileUploader"] {
    background: #101722;
    border: 1px dashed #354057;
    border-radius: 13px;
}

.stButton > button {
    border-radius: 11px;
    border: 1px solid #303b50;
    background: #171f2d;
    color: #f4f6fa;
    font-weight: 600;
    min-height: 40px;
}

.stButton > button:hover {
    border-color: #647bff;
    color: white;
}

div.stButton > button[kind="primary"] {
    background: #586fff;
    border-color: #586fff;
}

input, textarea, [data-baseweb="select"] {
    color: #ffffff !important;
}

[data-baseweb="select"] > div {
    background: #111722;
    border-color: #30394a;
}

hr {
    border-color: #252e3d;
}

footer {
    visibility: hidden;
}

</style>
""", unsafe_allow_html=True)


# ---------------- SESSION STATE ----------------

if "chat_id" not in st.session_state:
    st.session_state.chat_id = None

if "page" not in st.session_state:
    st.session_state.page = "Dashboard"

if "voice_choice" not in st.session_state:
    st.session_state.voice_choice = "marin"

if "last_answer" not in st.session_state:
    st.session_state.last_answer = ""


# ---------------- SIDEBAR ----------------

with st.sidebar:

    st.markdown("## ✦ NEXTGEN AI")
    st.caption("INTELLIGENCE • CREATIVITY • PRODUCTIVITY")

    st.divider()

    pages = [
        "Dashboard",
        "AI Chat",
        "Live Voice",
        "Voice Studio",
        "Web Research",
        "Chat History",
        "Settings",
        "About"
    ]

    for page_name in pages:
        if st.button(
            page_name,
            key="nav_" + page_name,
            use_container_width=True
        ):
            st.session_state.page = page_name
            st.rerun()

    st.divider()

    if st.button("＋ New chat", use_container_width=True):
        st.session_state.chat_id = create_chat()
        st.session_state.page = "AI Chat"
        st.rerun()

    st.caption("NEXTGEN AI · Version 2.0")


# ---------------- DASHBOARD ----------------

if st.session_state.page == "Dashboard":

    st.markdown("""
    <div class="hero">
        <div class="hero-title">Your AI workspace.</div>
        <div class="hero-sub">
            One intelligent platform for conversations, voice,
            research and productivity.
        </div>
    </div>
    """, unsafe_allow_html=True)

    c1, c2, c3 = st.columns(3)

    with c1:
        st.markdown("""
        <div class="metric-card">
            <div class="metric-label">AI ENGINE</div>
            <div class="metric-value">Groq</div>
        </div>
        """, unsafe_allow_html=True)

    with c2:
        st.markdown("""
        <div class="metric-card">
            <div class="metric-label">VOICE SYSTEM</div>
            <div class="metric-value">Realtime</div>
        </div>
        """, unsafe_allow_html=True)

    with c3:
        st.markdown("""
        <div class="metric-card">
            <div class="metric-label">WORKSPACE</div>
            <div class="metric-value">Connected</div>
        </div>
        """, unsafe_allow_html=True)

    st.write("")
    st.subheader("Explore your workspace")

    a, b = st.columns(2)

    with a:
        if st.button("Open AI Chat", use_container_width=True):
            st.session_state.page = "AI Chat"
            st.rerun()

        if st.button("Open Voice Studio", use_container_width=True):
            st.session_state.page = "Voice Studio"
            st.rerun()

    with b:
        if st.button("Start Live Voice", use_container_width=True):
            st.session_state.page = "Live Voice"
            st.rerun()

        if st.button("Open Web Research", use_container_width=True):
            st.session_state.page = "Web Research"
            st.rerun()


# ---------------- AI CHAT ----------------

elif st.session_state.page == "AI Chat":

    st.markdown("## AI Chat")
    st.caption("Ask anything. Your conversations are saved locally.")

    if not st.session_state.chat_id:
        st.session_state.chat_id = create_chat()

    chat_id = st.session_state.chat_id
    messages = get_messages(chat_id)

    for index, (role, content) in enumerate(messages):
        with st.chat_message(role):
            st.markdown(content)

            if role == "assistant":
                with st.expander("Message actions"):
                    st.code(content, language=None)

                    if st.button(
                        "Read this answer",
                        key=f"read_{index}"
                    ):
                        st.session_state.last_answer = content
                        st.session_state.page = "Voice Studio"
                        st.rerun()

    # Separate recording control: Streamlit's native chat composer
    # cannot place a custom mic button inside its input bar.
    recording = st.audio_input("Record a voice message")

    if recording:
        if st.button("Transcribe recording"):
            try:
                transcript = transcribe_audio(recording)
                st.session_state.voice_transcript = transcript
                st.success("Transcription ready.")
                st.text_area(
                    "Edit your transcription",
                    value=transcript,
                    key="edited_transcript"
                )
            except Exception as error:
                st.error(str(error))

    if "edited_transcript" in st.session_state:
        if st.button("Send transcribed message"):
            st.session_state.pending_message = (
                st.session_state.edited_transcript
            )
            del st.session_state.edited_transcript
            st.rerun()

    prompt = st.chat_input(
        "Message NEXTGEN AI...",
        accept_file="multiple",
        file_type=["pdf", "txt", "png", "jpg", "jpeg"]
    )

    pending = st.session_state.pop("pending_message", None)

    if prompt or pending:

        if prompt:
            user_text = prompt.text or ""
            attached_files = prompt.files or []
        else:
            user_text = pending
            attached_files = []

        extracted = []

        for upload in attached_files:
            try:
                extracted.append(
                    f"\n\nAttachment: {upload.name}\n"
                    + read_upload(upload)[:12000]
                )
            except Exception as error:
                extracted.append(
                    f"\nAttachment error: {error}"
                )

        full_text = user_text + "\n".join(extracted)

        if not full_text.strip():
            st.warning("Write a message or attach a file.")
            st.stop()

        if not messages:
            update_title(chat_id, user_text or "File conversation")

        save_message(chat_id, "user", full_text)

        with st.chat_message("user"):
            st.markdown(user_text or "Please review the attachment.")
            for upload in attached_files:
                st.caption("Attached: " + upload.name)

        history = [
            {
                "role": role,
                "content": content
            }
            for role, content in get_messages(chat_id)[-16:]
        ]

        history.insert(
            0,
            {
                "role": "system",
                "content": (
                    "You are NEXTGEN AI, a capable, accurate and "
                    "friendly assistant. Answer in the user's language. "
                    "Use clear formatting. Do not invent facts."
                )
            }
        )

        with st.chat_message("assistant"):
            with st.spinner("Thinking..."):
                try:
                    answer = groq_chat(history)
                    st.markdown(answer)
                    save_message(chat_id, "assistant", answer)
                    st.session_state.last_answer = answer

                except Exception as error:
                    st.error(str(error))


# ---------------- LIVE VOICE ----------------

elif st.session_state.page == "Live Voice":

    st.markdown("## Live Voice")
    st.caption("Real-time speech-to-speech conversation.")

    if not OPENAI_API_KEY:
        st.error(
            "OPENAI_API_KEY is missing. Add it in Streamlit Secrets."
        )

    else:
        voice = st.selectbox(
            "Live voice",
            options=VOICES,
            index=VOICES.index("marin")
        )

        if st.button("Prepare live voice session"):
            try:
                token = create_client_secret(voice)

                html_path = Path(__file__).with_name("liveVoice.html")

                html = html_path.read_text(encoding="utf-8")

                html = html.replace(
                    "__CLIENT_SECRET__",
                    token
                )

                components.html(
                    html,
                    height=470,
                    scrolling=True
                )

            except Exception as error:
                st.error(f"Could not prepare voice session: {error}")

        st.info(
            "Press Start call in the voice panel. Allow microphone access "
            "when your browser asks."
        )


# ---------------- VOICE STUDIO ----------------

elif st.session_state.page == "Voice Studio":

    st.markdown("## Voice Studio")
    st.caption("Choose a voice and generate speech.")

    default_text = st.session_state.get("last_answer", "")

    text = st.text_area(
        "Text to speak",
        value=default_text,
        height=180,
        placeholder="Enter the text you want NEXTGEN AI to speak..."
    )

    voice = st.selectbox(
        "Choose voice",
        options=VOICES,
        index=VOICES.index("nova")
    )

    speed = st.slider(
        "Speaking speed",
        min_value=0.7,
        max_value=1.8,
        value=1.15,
        step=0.05
    )

    style = st.selectbox(
        "Speaking style",
        [
            "Speak naturally and clearly.",
            "Speak confidently and energetically.",
            "Speak calmly and professionally.",
            "Speak like a friendly teacher.",
            "Speak with expressive storytelling."
        ]
    )

    if st.button("Generate voice", type="primary"):
        if not text.strip():
            st.warning("Enter some text first.")

        else:
            try:
                with st.spinner("Generating voice..."):
                    audio = generate_speech(
                        text=text,
                        voice=voice,
                        speed=speed,
                        instructions=style
                    )

                st.audio(audio, format="audio/mp3")

                st.download_button(
                    "Download audio",
                    data=audio,
                    file_name="nextgen_voice.mp3",
                    mime="audio/mpeg"
                )

                st.caption("This audio is AI-generated.")

            except Exception as error:
                st.error(str(error))


# ---------------- WEB RESEARCH ----------------

elif st.session_state.page == "Web Research":

    st.markdown("## Web Research")
    st.caption("Search the web and ask AI to summarize the findings.")

    query = st.text_input(
        "What do you want to research?",
        placeholder="Enter your research topic..."
    )

    if st.button("Search web", type="primary"):
        if not query.strip():
            st.warning("Enter a search topic.")

        else:
            try:
                with st.spinner("Searching..."):
                    result = web_search(query)

                st.markdown("### Search results")
                st.markdown(result)

                st.markdown("### AI summary")

                summary = groq_chat([
                    {
                        "role": "system",
                        "content": (
                            "Summarize the supplied research accurately. "
                            "Keep source URLs in the answer."
                        )
                    },
                    {
                        "role": "user",
                        "content": (
                            f"Research question: {query}\n\n"
                            f"Search results:\n{result}"
                        )
                    }
                ])

                st.markdown(summary)

            except Exception as error:
                st.error(str(error))


# ---------------- CHAT HISTORY ----------------

elif st.session_state.page == "Chat History":

    st.markdown("## Chat History")

    chats = get_chats()

    if not chats:
        st.info("No conversations saved yet.")

    for chat in chats:
        chat_id, title, created = chat

        with st.expander(f"{title} · {created}"):
            history = get_messages(chat_id)

            for role, content in history:
                with st.chat_message(role):
                    st.markdown(content)

            if st.button(
                "Continue this chat",
                key=f"continue_{chat_id}"
            ):
                st.session_state.chat_id = chat_id
                st.session_state.page = "AI Chat"
                st.rerun()


# ---------------- SETTINGS ----------------

elif st.session_state.page == "Settings":

    st.markdown("## Settings")

    st.write("API connection status")

    st.write(
        "Groq:",
        "Connected" if GROQ_API_KEY else "Not configured"
    )

    st.write(
        "OpenAI:",
        "Connected" if OPENAI_API_KEY else "Not configured"
    )

    st.write(
        "Tavily:",
        "Connected" if TAVILY_API_KEY else "Not configured"
    )

    st.info(
        "Keep all API keys in Streamlit Secrets. "
        "Never put private keys inside HTML or JavaScript."
    )


# ---------------- ABOUT ----------------

elif st.session_state.page == "About":

    st.markdown("## About NEXTGEN AI")

    st.markdown("""
    NEXTGEN AI is an AI workspace for:

    - AI conversations
    - Persistent chat history
    - Voice transcription
    - AI text-to-speech
    - Real-time voice conversations
    - Web research
    - PDF and text attachments

    **Built with Python, Streamlit and AI APIs.**
    """)

    st.caption("NEXTGEN AI · 2026")
