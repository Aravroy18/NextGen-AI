
import os
import io
import re
import json
import time
import uuid
import sqlite3
import requests
import streamlit as st
import streamlit.components.v1 as components

from datetime import datetime
from dotenv import load_dotenv

load_dotenv()

# ============================================================
# NEXTGEN AI — ULTRA PREMIUM EDITION
# ============================================================

APP_NAME = "NEXTGEN AI"
DB_PATH = "nextgen_history.db"

GROQ_KEY = os.getenv("GROQ_API_KEY", "")
GEMINI_KEY = os.getenv("GEMINI_API_KEY", "")
TAVILY_KEY = os.getenv("TAVILY_API_KEY", "")
FINNHUB_KEY = os.getenv("FINNHUB_API_KEY", "")

GROQ_MODEL = os.getenv(
    "GROQ_MODEL",
    "llama-3.3-70b-versatile"
)

GEMINI_MODEL = os.getenv(
    "GEMINI_MODEL",
    "gemini-3.5-flash"
)

st.set_page_config(
    page_title=APP_NAME,
    page_icon="✦",
    layout="wide",
    initial_sidebar_state="expanded"
)

# ============================================================
# DATABASE
# ============================================================

def db():
    return sqlite3.connect(DB_PATH, check_same_thread=False)


def init_db():
    con = db()
    cur = con.cursor()

    cur.execute("""
        CREATE TABLE IF NOT EXISTS chats(
            id TEXT PRIMARY KEY,
            title TEXT,
            created TEXT,
            updated TEXT
        )
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS messages(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            chat_id TEXT,
            role TEXT,
            content TEXT,
            created TEXT
        )
    """)

    con.commit()
    con.close()


def create_chat():
    chat_id = str(uuid.uuid4())
    now = datetime.now().isoformat()

    con = db()
    con.execute(
        "INSERT INTO chats VALUES(?,?,?,?)",
        (chat_id, "New Chat", now, now)
    )
    con.commit()
    con.close()

    return chat_id


def get_chats():
    con = db()
    rows = con.execute(
        "SELECT id,title FROM chats ORDER BY updated DESC"
    ).fetchall()
    con.close()
    return rows


def get_messages(chat_id):
    con = db()
    rows = con.execute(
        """SELECT role,content FROM messages
           WHERE chat_id=? ORDER BY id""",
        (chat_id,)
    ).fetchall()
    con.close()

    return [
        {"role": role, "content": content}
        for role, content in rows
    ]


def save_message(chat_id, role, content):
    con = db()
    now = datetime.now().isoformat()

    con.execute(
        """INSERT INTO messages(chat_id,role,content,created)
           VALUES(?,?,?,?)""",
        (chat_id, role, content, now)
    )

    if role == "user":
        title = content[:45].replace("\n", " ")
        con.execute(
            "UPDATE chats SET title=?,updated=? WHERE id=?",
            (title, now, chat_id)
        )
    else:
        con.execute(
            "UPDATE chats SET updated=? WHERE id=?",
            (now, chat_id)
        )

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

if "chat_id" not in st.session_state:
    st.session_state.chat_id = create_chat()

if "messages" not in st.session_state:
    st.session_state.messages = get_messages(
        st.session_state.chat_id
    )

if "processing" not in st.session_state:
    st.session_state.processing = False

# ============================================================
# PREMIUM DESIGN
# ============================================================

st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&display=swap');

html, body, [class*="css"] {
    font-family: 'Inter', sans-serif;
}

.stApp {
    background:
      radial-gradient(ellipse at 50% -20%, #18213b 0%, transparent 55%),
      #080b14;
    color: #f3f4f6;
}

section[data-testid="stSidebar"] {
    background: #0d1220;
    border-right: 1px solid #202a40;
}

header[data-testid="stHeader"] {
    background: transparent;
}

h1, h2, h3 {
    letter-spacing: -0.8px;
}

.hero {
    text-align: center;
    padding: 42px 10px 25px;
}

.logo {
    font-size: 43px;
    font-weight: 800;
    letter-spacing: -2px;
    background: linear-gradient(90deg,#8b9cff,#c084fc,#5eead4);
    -webkit-background-clip: text;
    color: transparent;
}

.subtitle {
    color: #8994aa;
    font-size: 14px;
}

.chat-card {
    background: #111827;
    border: 1px solid #27334b;
    border-radius: 18px;
    padding: 16px;
    margin: 12px 0;
}

.user-card {
    background: #19243a;
    border: 1px solid #344565;
    border-radius: 18px;
    padding: 15px;
    margin: 12px 0;
}

.status {
    background: #121c2c;
    border: 1px solid #263a54;
    border-radius: 12px;
    padding: 12px;
    color: #a5b4fc;
    font-size: 13px;
}

div[data-testid="stChatInput"] textarea {
    background: #131b2b !important;
    border: 1px solid #34435e !important;
    border-radius: 15px !important;
    color: white !important;
}

.stButton button {
    border-radius: 10px;
    border: 1px solid #34435e;
    background: #172239;
    color: white;
    transition: 0.2s;
}

.stButton button:hover {
    border-color: #9b8cff;
    color: white;
}

[data-testid="stMetric"] {
    background: #111827;
    padding: 15px;
    border-radius: 14px;
    border: 1px solid #26334b;
}

footer {
    visibility: hidden;
}
</style>
""", unsafe_allow_html=True)

# ============================================================
# WEB SEARCH
# ============================================================

def web_search(query):
    if not TAVILY_KEY:
        return ""

    try:
        response = requests.post(
            "https://api.tavily.com/search",
            json={
                "api_key": TAVILY_KEY,
                "query": query,
                "search_depth": "basic",
                "max_results": 5
            },
            timeout=20
        )

        response.raise_for_status()
        data = response.json()

        results = []

        for item in data.get("results", []):
            results.append(
                f"Title: {item.get('title','')}\n"
                f"URL: {item.get('url','')}\n"
                f"Content: {item.get('content','')}"
            )

        return "\n\n".join(results)

    except Exception:
        return ""


def needs_search(query):
    keywords = [
        "latest", "today", "current", "news",
        "weather", "price", "stock", "share",
        "2026", "live", "recent", "अभी",
        "आज", "ताजा", "लेटेस्ट", "शेयर",
        "मौसम", "भाव", "न्यूज", "कीमत"
    ]

    q = query.lower()

    return any(word in q for word in keywords)

# ============================================================
# GROQ AI
# ============================================================

def groq_request(messages):
    if not GROQ_KEY:
        raise RuntimeError("GROQ_API_KEY missing")

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
        timeout=90
    )

    response.raise_for_status()

    data = response.json()

    return data["choices"][0]["message"]["content"]


# ============================================================
# GEMINI AI
# ============================================================

def gemini_request(messages):
    if not GEMINI_KEY:
        raise RuntimeError("GEMINI_API_KEY missing")

    contents = []

    for message in messages:
        if message["role"] == "system":
            continue

        contents.append({
            "role": (
                "model"
                if message["role"] == "assistant"
                else "user"
            ),
            "parts": [{"text": message["content"]}]
        })

    system_instruction = next(
        (
            m["content"]
            for m in messages
            if m["role"] == "system"
        ),
        ""
    )

    response = requests.post(
        f"https://generativelanguage.googleapis.com/v1beta/models/{GEMINI_MODEL}:generateContent",
        params={"key": GEMINI_KEY},
        json={
            "systemInstruction": {
                "parts": [{"text": system_instruction}]
            },
            "contents": contents,
            "generationConfig": {
                "temperature": 0.7,
                "maxOutputTokens": 4000
            }
        },
        timeout=90
    )

    response.raise_for_status()

    data = response.json()

    return data["candidates"][0]["content"]["parts"][0]["text"]


# ============================================================
# AUTOMATIC MODEL ROUTER
# ============================================================

def ask_ai(messages):
    errors = []

    if GROQ_KEY:
        try:
            answer = groq_request(messages)
            return answer, "Groq"
        except Exception as exc:
            errors.append(f"Groq: {str(exc)[:200]}")

    if GEMINI_KEY:
        try:
            answer = gemini_request(messages)
            return answer, "Gemini"
        except Exception as exc:
            errors.append(f"Gemini: {str(exc)[:200]}")

    raise RuntimeError(
        "All configured AI providers failed.\n"
        + "\n".join(errors)
        if errors else
        "No AI API key configured. Add GROQ_API_KEY or GEMINI_API_KEY to .env."
    )

# ============================================================
# AI BRAIN
# ============================================================

SYSTEM_PROMPT = """
You are NEXTGEN AI, a powerful, intelligent and helpful AI assistant.

Your behavior:
1. Understand the user's actual intent.
2. Give accurate and useful answers.
3. Use the user's language.
4. Explain difficult concepts simply.
5. Help with coding, mathematics, science and technology.
6. Never invent facts, API results or live data.
7. Clearly explain uncertainty.
8. For financial topics, provide educational information,
   explain risks and never guarantee returns.
9. Remember the conversation context provided to you.
10. Use clean formatting and practical examples.
"""

def generate_answer(user_prompt, history):
    messages = [
        {"role": "system", "content": SYSTEM_PROMPT}
    ]

    recent_history = history[-16:]

    messages.extend(recent_history)

    extra_context = ""

    if needs_search(user_prompt):
        results = web_search(user_prompt)

        if results:
            extra_context = (
                "\n\nRelevant web search results:\n"
                + results
                + "\nUse these sources carefully. "
                "Do not invent information."
            )

    if extra_context:
        messages.append({
            "role": "system",
            "content": extra_context
        })

    return ask_ai(messages)

# ============================================================
# SIDEBAR
# ============================================================

with st.sidebar:

    st.markdown("""
    <div style="padding:12px 4px 20px">
      <div style="font-size:27px;font-weight:800;
      background:linear-gradient(90deg,#9baaff,#d2a2ff);
      -webkit-background-clip:text;color:transparent">
      ✦ NEXTGEN AI
      </div>
      <div style="color:#8591a8;font-size:12px">
      Intelligent AI Workspace
      </div>
    </div>
    """, unsafe_allow_html=True)

    if st.button("＋  New Chat", use_container_width=True):
        st.session_state.chat_id = create_chat()
        st.session_state.messages = []
        st.rerun()

    st.divider()

    st.markdown("### Recent Chats")

    chats = get_chats()

    for cid, title in chats:

        col1, col2 = st.columns([5, 1])

        with col1:
            if st.button(
                title[:28],
                key=f"chat_{cid}",
                use_container_width=True
            ):
                st.session_state.chat_id = cid
                st.session_state.messages = get_messages(cid)
                st.rerun()

        with col2:
            if st.button("⋯", key=f"delete_{cid}"):
                st.session_state.delete_target = cid

    if st.session_state.get("delete_target"):
        target = st.session_state.delete_target

        st.warning("Delete this conversation?")

        if st.button("Confirm Delete"):
            delete_chat(target)

            if target == st.session_state.chat_id:
                st.session_state.chat_id = create_chat()
                st.session_state.messages = []

            st.session_state.delete_target = None
            st.rerun()

    st.divider()

    st.markdown("### AI Providers")

    st.caption(
        f"Groq: {'Connected' if GROQ_KEY else 'API key missing'}"
    )

    st.caption(
        f"Gemini: {'Connected' if GEMINI_KEY else 'API key missing'}"
    )

    st.caption(
        f"Web Search: {'Available' if TAVILY_KEY else 'API key missing'}"
    )

    st.caption("Automatic model selection enabled")

    st.divider()

    st.caption("NEXTGEN AI • Version 2.0")

# ============================================================
# MAIN CHAT
# ============================================================

st.markdown("""
<div class="hero">
  <div class="logo">✦ NEXTGEN AI</div>
  <div class="subtitle">
    Your intelligent workspace. Ask, create, explore.
  </div>
</div>
""", unsafe_allow_html=True)

# ============================================================
# WELCOME SCREEN
# ============================================================

if not st.session_state.messages:

    st.markdown(
        "<h3 style='text-align:center'>How can I help you today?</h3>",
        unsafe_allow_html=True
    )

    st.markdown(
        "<p style='text-align:center;color:#8994aa'>"
        "Ask anything. Your AI assistant is ready."
        "</p>",
        unsafe_allow_html=True
    )

    c1, c2, c3 = st.columns(3)

    with c1:
        st.markdown(
            '<div class="chat-card">💻 <b>Coding</b><br>'
            '<small>Build apps and debug code</small></div>',
            unsafe_allow_html=True
        )

    with c2:
        st.markdown(
            '<div class="chat-card">🌐 <b>Research</b><br>'
            '<small>Understand topics and current events</small></div>',
            unsafe_allow_html=True
        )

    with c3:
        st.markdown(
            '<div class="chat-card">📊 <b>Finance</b><br>'
            '<small>Learn about stocks and markets</small></div>',
            unsafe_allow_html=True
        )

# ============================================================
# DISPLAY HISTORY
# ============================================================

for message in st.session_state.messages:

    role = message["role"]

    with st.chat_message(role):

        st.markdown(message["content"])

# ============================================================
# CHAT INPUT
# ============================================================

prompt = st.chat_input(
    "Message NEXTGEN AI...",
    disabled=st.session_state.processing
)

if prompt:

    st.session_state.processing = True

    save_message(
        st.session_state.chat_id,
        "user",
        prompt
    )

    st.session_state.messages.append({
        "role": "user",
        "content": prompt
    })

    with st.chat_message("user"):
        st.markdown(prompt)

    with st.chat_message("assistant"):

        placeholder = st.empty()

        with st.spinner("NEXTGEN AI is thinking..."):

            try:
                answer, provider = generate_answer(
                    prompt,
                    st.session_state.messages[:-1]
                )

                placeholder.markdown(answer)

                st.caption(f"Powered by {provider}")

                save_message(
                    st.session_state.chat_id,
                    "assistant",
                    answer
                )

                st.session_state.messages.append({
                    "role": "assistant",
                    "content": answer
                })

            except Exception as exc:

                error = (
                    "NEXTGEN AI could not respond.\n\n"
                    f"**Error:** {str(exc)}"
                )

                placeholder.error(error)

    st.session_state.processing = False
    st.rerun()

# ============================================================
# FOOTER
# ============================================================

st.markdown("""
<div style="text-align:center;padding:35px 0 15px;
color:#66738b;font-size:11px">
NEXTGEN AI • Built for intelligent conversations
</div>
""", unsafe_allow_html=True)
