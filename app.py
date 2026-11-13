# ============================================================
# NEXTGEN AI — AI SUPER APP
# Single-file Streamlit application
# ============================================================
# Install:
# pip install streamlit requests pandas plotly pypdf pillow
#
# Run:
# streamlit run app.py
#
# Streamlit Cloud Secrets:
# XAI_API_KEY = "..."
# GEMINI_API_KEY = "..."
# GEMINI_MODEL = "gemini-2.5-flash"
# TAVILY_API_KEY = "..."
# FINNHUB_API_KEY = "..."
# CLOUDFLARE_ACCOUNT_ID = "..."
# CLOUDFLARE_API_TOKEN = "..."
# CLOUDFLARE_IMAGE_MODEL = "xai/grok-imagine-image"
# ============================================================

import streamlit as st
import requests
import sqlite3
import hashlib
import secrets
import json
import re
import io
import os
import time
from datetime import datetime
from typing import Optional

import pandas as pd

try:
    from pypdf import PdfReader
except Exception:
    PdfReader = None

# -------------------- PAGE CONFIG --------------------

st.set_page_config(
    page_title="NEXTGEN AI",
    page_icon="🚀",
    layout="wide",
    initial_sidebar_state="expanded"
)

APP_NAME = "NEXTGEN AI"
DB_PATH = "nextgen_ai.db"

# -------------------- PREMIUM UI --------------------

st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&display=swap');

html, body, [class*="css"] {
    font-family: 'Inter', sans-serif;
}
.stApp {
    background:
      radial-gradient(circle at 10% 0%, rgba(35,90,170,.18), transparent 28%),
      radial-gradient(circle at 90% 10%, rgba(80,60,180,.12), transparent 25%),
      #080c14;
    color: #edf3ff;
}
section[data-testid="stSidebar"] {
    background: #0c1220;
    border-right: 1px solid #1d2b43;
}
.block-container {
    padding-top: 1.5rem;
    max-width: 1500px;
}
h1, h2, h3 {
    letter-spacing: -0.7px;
}
div[data-testid="stMetric"] {
    background: linear-gradient(145deg,#111d30,#0c1422);
    border: 1px solid #233956;
    padding: 17px;
    border-radius: 16px;
}
.stButton > button {
    border-radius: 11px;
    border: 1px solid #31527c;
    background: linear-gradient(120deg,#1763b4,#5146b9);
    color: white;
    font-weight: 650;
    min-height: 42px;
}
.stButton > button:hover {
    border-color: #76b9ff;
    color: white;
    box-shadow: 0 0 18px #2563eb55;
}
.stTextInput input, .stTextArea textarea, .stSelectbox div,
.stNumberInput input {
    background: #101a2a !important;
    color: #edf3ff !important;
    border-radius: 10px !important;
}
div[data-testid="stChatMessage"] {
    background: #101a2a;
    border: 1px solid #243752;
    border-radius: 15px;
    padding: 12px;
}
.ng-hero {
    padding: 28px;
    border: 1px solid #28466b;
    border-radius: 22px;
    background: linear-gradient(125deg,#10213a,#171637 65%,#10213a);
    margin-bottom: 20px;
}
.ng-card {
    background: linear-gradient(145deg,#111d30,#0c1422);
    border: 1px solid #253b59;
    border-radius: 16px;
    padding: 17px;
    min-height: 105px;
}
.ng-muted { color: #9db0ca; }
.ng-tag {
    display:inline-block;
    padding:5px 10px;
    border:1px solid #31527c;
    border-radius:20px;
    color:#a9d1ff;
    font-size:12px;
}
a { color: #7dbbff !important; }
</style>
""", unsafe_allow_html=True)

# -------------------- SECRETS --------------------

def get_secret(key, default=""):
    try:
        value = st.secrets.get(key, default)
        return str(value) if value is not None else default
    except Exception:
        return os.getenv(key, default)

XAI_API_KEY = get_secret("XAI_API_KEY")
GEMINI_API_KEY = get_secret("GEMINI_API_KEY")
GEMINI_MODEL = get_secret("GEMINI_MODEL", "gemini-2.5-flash")
TAVILY_API_KEY = get_secret("TAVILY_API_KEY")
FINNHUB_API_KEY = get_secret("FINNHUB_API_KEY")
CF_ACCOUNT_ID = get_secret("CLOUDFLARE_ACCOUNT_ID")
CF_API_TOKEN = get_secret("CLOUDFLARE_API_TOKEN")
CF_IMAGE_MODEL = get_secret(
    "CLOUDFLARE_IMAGE_MODEL",
    "xai/grok-imagine-image"
)

# -------------------- DATABASE --------------------

def db():
    return sqlite3.connect(DB_PATH, check_same_thread=False)

def init_db():
    con = db()
    cur = con.cursor()

    cur.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            created_at TEXT NOT NULL
        )
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS chats (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_key TEXT NOT NULL,
            title TEXT NOT NULL,
            created_at TEXT NOT NULL
        )
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS messages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            chat_id INTEGER NOT NULL,
            role TEXT NOT NULL,
            content TEXT NOT NULL,
            created_at TEXT NOT NULL
        )
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS generated_items (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_key TEXT NOT NULL,
            tool_name TEXT NOT NULL,
            prompt TEXT NOT NULL,
            result TEXT NOT NULL,
            created_at TEXT NOT NULL
        )
    """)

    con.commit()
    con.close()

init_db()

def password_hash(password, salt=None):
    salt = salt or secrets.token_hex(16)
    digest = hashlib.pbkdf2_hmac(
        "sha256", password.encode(), salt.encode(), 180000
    ).hex()
    return salt + "$" + digest

def verify_password(password, stored):
    try:
        salt, digest = stored.split("$", 1)
        return password_hash(password, salt) == stored
    except Exception:
        return False

def register_user(username, password):
    con = db()
    try:
        con.execute(
            "INSERT INTO users(username,password_hash,created_at) VALUES(?,?,?)",
            (username, password_hash(password), datetime.now().isoformat())
        )
        con.commit()
        return True, "Account created."
    except sqlite3.IntegrityError:
        return False, "This username already exists."
    finally:
        con.close()

def login_user(username, password):
    con = db()
    row = con.execute(
        "SELECT password_hash FROM users WHERE username=?",
        (username,)
    ).fetchone()
    con.close()
    return bool(row and verify_password(password, row[0]))

# -------------------- SESSION STATE --------------------

defaults = {
    "user_key": None,
    "username": None,
    "guest": False,
    "current_chat": None,
    "chat_messages": [],
    "page": "Dashboard",
    "model": "Auto",
    "last_result": "",
}
for key, value in defaults.items():
    if key not in st.session_state:
        st.session_state[key] = value

def current_user_key():
    return st.session_state.user_key or "guest-session"

# -------------------- CHAT DATABASE --------------------

def create_chat(title="New Chat"):
    con = db()
    cur = con.cursor()
    cur.execute(
        "INSERT INTO chats(user_key,title,created_at) VALUES(?,?,?)",
        (current_user_key(), title[:70], datetime.now().isoformat())
    )
    chat_id = cur.lastrowid
    con.commit()
    con.close()
    return chat_id

def get_chats():
    con = db()
    rows = con.execute(
        "SELECT id,title,created_at FROM chats WHERE user_key=? ORDER BY id DESC",
        (current_user_key(),)
    ).fetchall()
    con.close()
    return rows

def rename_chat(chat_id, title):
    con = db()
    con.execute(
        "UPDATE chats SET title=? WHERE id=? AND user_key=?",
        (title[:70], chat_id, current_user_key())
    )
    con.commit()
    con.close()

def delete_chat(chat_id):
    con = db()
    con.execute("DELETE FROM messages WHERE chat_id=?", (chat_id,))
    con.execute(
        "DELETE FROM chats WHERE id=? AND user_key=?",
        (chat_id, current_user_key())
    )
    con.commit()
    con.close()

def save_message(chat_id, role, content):
    con = db()
    con.execute(
        "INSERT INTO messages(chat_id,role,content,created_at) VALUES(?,?,?,?)",
        (chat_id, role, content, datetime.now().isoformat())
    )
    con.commit()
    con.close()

def load_messages(chat_id):
    con = db()
    rows = con.execute(
        "SELECT role,content FROM messages WHERE chat_id=? ORDER BY id",
        (chat_id,)
    ).fetchall()
    con.close()
    return [{"role": r, "content": c} for r, c in rows]

def save_generated(tool_name, prompt, result):
    con = db()
    con.execute(
        """INSERT INTO generated_items
        (user_key,tool_name,prompt,result,created_at)
        VALUES(?,?,?,?,?)""",
        (
            current_user_key(), tool_name, prompt, result,
            datetime.now().isoformat()
        )
    )
    con.commit()
    con.close()

# -------------------- AI ENGINES --------------------

def xai_chat(messages, model="grok-4.7"):
    if not XAI_API_KEY:
        raise RuntimeError("XAI_API_KEY is missing in Streamlit Secrets.")

    response = requests.post(
        "https://api.x.ai/v1/chat/completions",
        headers={
            "Authorization": f"Bearer {XAI_API_KEY}",
            "Content-Type": "application/json"
        },
        json={
            "model": model,
            "messages": messages,
            "temperature": 0.7
        },
        timeout=120
    )
    if not response.ok:
        raise RuntimeError(f"xAI API error {response.status_code}: {response.text[:700]}")
    data = response.json()
    return data["choices"][0]["message"]["content"]

def gemini_chat(messages, model=None):
    if not GEMINI_API_KEY:
        raise RuntimeError("GEMINI_API_KEY is missing in Streamlit Secrets.")

    model = model or GEMINI_MODEL
    contents = []
    system_text = ""

    for item in messages:
        role = item.get("role", "user")
        content = item.get("content", "")
        if role == "system":
            system_text += content + "\n"
        else:
            contents.append({
                "role": "model" if role == "assistant" else "user",
                "parts": [{"text": str(content)}]
            })

    payload = {"contents": contents}
    if system_text:
        payload["systemInstruction"] = {
            "parts": [{"text": system_text}]
        }

    url = (
        "https://generativelanguage.googleapis.com/v1beta/"
        f"models/{model}:generateContent?key={GEMINI_API_KEY}"
    )
    response = requests.post(url, json=payload, timeout=120)
    if not response.ok:
        raise RuntimeError(
            f"Gemini API error {response.status_code}: {response.text[:700]}"
        )

    data = response.json()
    return data["candidates"][0]["content"]["parts"][0]["text"]

def ai_reply(messages, preferred=None):
    preferred = preferred or st.session_state.model
    errors = []

    if preferred in ("Auto", "Grok"):
        if XAI_API_KEY:
            try:
                return xai_chat(messages), "Grok"
            except Exception as e:
                errors.append("Grok: " + str(e))
        elif preferred == "Grok":
            errors.append("Grok API key missing.")

    if preferred in ("Auto", "Gemini"):
        if GEMINI_API_KEY:
            try:
                return gemini_chat(messages), "Gemini"
            except Exception as e:
                errors.append("Gemini: " + str(e))
        elif preferred == "Gemini":
            errors.append("Gemini API key missing.")

    raise RuntimeError("\n".join(errors) or "No AI provider is configured.")

# -------------------- SMART WEB SEARCH --------------------

def needs_web_search(text):
    patterns = [
        r"\b(latest|today|current|now|live|recent|2026|this week)\b",
        r"\b(news|weather|price today|stock price|score|standings)\b",
        r"(आज|अभी|ताज़ा|लेटेस्ट|वर्तमान|मौसम|आज का भाव|खबर)"
    ]
    return any(re.search(p, text, re.I) for p in patterns)

def web_search(query):
    if not TAVILY_API_KEY:
        return "Web search is not configured. Add TAVILY_API_KEY in Secrets."

    response = requests.post(
        "https://api.tavily.com/search",
        json={
            "api_key": TAVILY_API_KEY,
            "query": query,
            "search_depth": "basic",
            "max_results": 5,
            "include_answer": True
        },
        timeout=45
    )
    if not response.ok:
        return f"Search error: {response.status_code} {response.text[:300]}"

    data = response.json()
    lines = []
    if data.get("answer"):
        lines.append("Search summary: " + data["answer"])

    for item in data.get("results", []):
        lines.append(
            f"- {item.get('title','Source')}\n"
            f"  {item.get('content','')}\n"
            f"  URL: {item.get('url','')}"
        )
    return "\n\n".join(lines) or "No results found."

# -------------------- AI TOOL CENTER: 120+ TOOLS --------------------

TOOL_GROUPS = {
"AI Writing Studio": [
"AI Email Writer", "Email Reply Writer", "Formal Email Writer",
"Friendly Email Writer", "Follow-up Email Writer", "Apology Email Writer",
"Thank-you Email Writer", "Meeting Request Email", "Leave Application Writer",
"School Application Writer", "Permission Letter Writer",
"Complaint Letter Writer", "Invitation Writer", "Notice Writer",
"Report Writer", "Essay Writer", "Paragraph Writer", "Article Writer",
"Blog Writer", "Story Writer", "Poem Writer", "Speech Writer",
"Debate Writer", "Project Writer", "Assignment Writer",
"Resume Builder", "Cover Letter Writer", "Bio Writer",
"Product Description Writer", "Ad Copy Writer", "Social Caption Writer",
"YouTube Description Writer", "YouTube Title Generator",
"WhatsApp Message Writer", "Birthday Wish Writer",
"Professional Message Writer", "Text Rewriter", "Grammar Corrector",
"Tone Changer", "Text Improver", "Text Shortener",
"Text Expander", "Text Summarizer", "Bullet Point Maker",
"Headline Generator", "Tagline Generator", "Slogan Generator",
"Hashtag Generator", "Content Calendar Maker"
],
"AI Study Center": [
"Homework Helper", "Study Notes Maker", "Chapter Summarizer",
"Question Answer Maker", "MCQ Generator", "Quiz Generator",
"Flashcard Maker", "Math Explainer", "Science Explainer",
"History Explainer", "Geography Explainer", "Grammar Tutor",
"Vocabulary Builder", "Spelling Practice", "Reading Comprehension",
"Study Planner", "Revision Planner", "Exam Practice Maker",
"Formula Sheet Maker", "Concept Explainer", "Difficult Word Explainer",
"Lesson Planner", "Project Topic Generator", "Speech for School",
"School Timetable Maker"
],
"AI Developer Center": [
"Python Code Generator", "HTML Generator", "CSS Generator",
"JavaScript Generator", "Code Explainer", "Bug Explainer",
"Code Reviewer", "Code Comment Writer", "SQL Query Helper",
"Regex Generator", "JSON Formatter Helper", "API Documentation Writer",
"Website Idea Generator", "Website Planner", "Landing Page Copy Writer",
"App Idea Generator", "App Feature Planner", "UI Text Writer",
"Git Command Explainer", "Algorithm Explainer"
],
"AI Business & Productivity": [
"Business Idea Generator", "Business Plan Writer", "Brand Name Generator",
"Brand Slogan Generator", "Marketing Plan Maker", "Customer Reply Writer",
"Customer Support Response", "Product Research Brief",
"SWOT Analysis Maker", "Pros and Cons Maker", "Decision Helper",
"Meeting Agenda Maker", "Meeting Notes Formatter", "Task Planner",
"Daily Planner", "Goal Planner", "Checklist Maker",
"Presentation Outline Maker", "Slide Content Writer",
"Interview Question Maker", "Interview Practice", "Event Plan Maker"
],
"AI Creator Studio": [
"Video Script Writer", "Reel Script Writer", "Shorts Hook Generator",
"Video Scene Planner", "Storyboard Writer", "Photo Prompt Generator",
"Image Prompt Enhancer", "Video Prompt Generator",
"Thumbnail Text Generator", "Thumbnail Concept Maker",
"Podcast Script Writer", "Podcast Topic Generator",
"Character Creator", "World Builder", "Dialogue Writer",
"Creative Idea Generator", "Meme Caption Writer",
"Instagram Bio Writer", "Channel Name Generator"
],
"AI Language & Documents": [
"Translator", "Hindi to English", "English to Hindi",
"Simple Language Rewriter", "PDF Question Answer",
"PDF Summarizer", "Document Summarizer", "Key Point Extractor",
"Table to Text Helper", "Formal Language Converter",
"Proofreading Assistant", "Citation Helper", "Research Outline Maker"
],
"AI Everyday Tools": [
"Calculator Explainer", "Unit Conversion Explainer",
"Recipe Idea Generator", "Travel Itinerary Draft",
"Gift Idea Generator", "Routine Planner", "Packing Checklist",
"Book Summary Helper", "Movie Review Draft",
"Personal Knowledge Organizer", "Question Generator",
"Random Learning Topic", "Decision Matrix Maker"
]
}

ALL_TOOLS = [
    (group, tool)
    for group, tools in TOOL_GROUPS.items()
    for tool in tools
]

# -------------------- TOOL PROMPT ENGINE --------------------

def tool_instruction(tool_name, user_input, tone, length, language):
    return f"""
You are NEXTGEN AI's specialized tool: {tool_name}.

Perform the task directly. Do not merely explain how to do it.
Use the user's supplied information. Never invent personal facts,
email addresses, dates, qualifications, citations, or business details.
If key details are missing, use clearly marked placeholders.
For email and letter tools, create a complete ready-to-edit draft.
For study tools, explain clearly and accurately at the requested level.
For coding tools, provide usable code and explain assumptions.
For summaries, preserve the original meaning.
For translations, preserve tone and meaning.

Language: {language}
Tone: {tone}
Length: {length}

User request:
{user_input}
"""

# -------------------- CLOUDLFARE IMAGE STUDIO --------------------

def cloudflare_image(prompt, aspect_ratio="1:1", reference_image=None):
    if not CF_ACCOUNT_ID or not CF_API_TOKEN:
        raise RuntimeError(
            "Cloudflare is not configured. Add CLOUDFLARE_ACCOUNT_ID "
            "and CLOUDFLARE_API_TOKEN to Streamlit Secrets."
        )

    input_data = {
        "prompt": prompt,
        "aspect_ratio": aspect_ratio
    }

    # Reference-image editing support depends on the selected model's
    # accepted input schema. Do not silently send an unsupported payload.
    if reference_image is not None:
        raise RuntimeError(
            "Reference-image editing needs a model-specific image input "
            "payload. Text-to-image is available in this configuration."
        )

    url = (
        "https://api.cloudflare.com/client/v4/accounts/"
        f"{CF_ACCOUNT_ID}/ai/run/{CF_IMAGE_MODEL}"
    )
    response = requests.post(
        url,
        headers={
            "Authorization": f"Bearer {CF_API_TOKEN}",
            "Content-Type": "application/json"
        },
        json={"input": input_data},
        timeout=180
    )
    if not response.ok:
        raise RuntimeError(
            f"Cloudflare error {response.status_code}: {response.text[:600]}"
        )
    data = response.json()
    if not data.get("success", True):
        raise RuntimeError(str(data.get("errors", data)))

    result = data.get("result", {})
    image_url = result.get("image")
    if image_url:
        return image_url
    if result.get("image"):
        return result["image"]
    raise RuntimeError("Image response did not contain an image URL.")

# -------------------- PDF READER --------------------

def extract_pdf_text(uploaded_file):
    if PdfReader is None:
        raise RuntimeError("Install pypdf to use PDF Assistant.")
    reader = PdfReader(uploaded_file)
    pages = []
    for i, page in enumerate(reader.pages):
        text = page.extract_text() or ""
        if text.strip():
            pages.append(f"\n--- Page {i+1} ---\n{text}")
    return "\n".join(pages)

# -------------------- AUTH SCREEN --------------------

def auth_screen():
    st.markdown("""
    <div class="ng-hero">
      <span class="ng-tag">YOUR CREATIVE UNIVERSE</span>
      <h1>🚀 NEXTGEN AI</h1>
      <h3>One Platform. 100+ AI Tools.</h3>
      <p class="ng-muted">Chat • Create • Write • Study • Build • Explore</p>
    </div>
    """, unsafe_allow_html=True)

    login_tab, register_tab = st.tabs(["Login", "Create Account"])

    with login_tab:
        username = st.text_input("Username", key="login_user")
        password = st.text_input("Password", type="password", key="login_pass")
        if st.button("Login", use_container_width=True):
            if login_user(username.strip(), password):
                st.session_state.user_key = "user:" + username.strip()
                st.session_state.username = username.strip()
                st.session_state.guest = False
                st.rerun()
            else:
                st.error("Incorrect username or password.")

    with register_tab:
        new_user = st.text_input("Choose username", key="reg_user")
        new_pass = st.text_input("Choose password", type="password", key="reg_pass")
        confirm = st.text_input("Confirm password", type="password")
        if st.button("Create Account", use_container_width=True):
            if len(new_user.strip()) < 3:
                st.error("Username must contain at least 3 characters.")
            elif len(new_pass) < 8:
                st.error("Use a password with at least 8 characters.")
            elif new_pass != confirm:
                st.error("Passwords do not match.")
            else:
                ok, message = register_user(new_user.strip(), new_pass)
                if ok:
                    st.success(message + " Please log in.")
                else:
                    st.error(message)

    st.divider()
    if st.button("Continue as Guest", use_container_width=True):
        st.session_state.user_key = "guest-" + secrets.token_hex(8)
        st.session_state.username = "Guest"
        st.session_state.guest = True
        st.rerun()

# -------------------- LOGIN CHECK --------------------

if not st.session_state.user_key:
    auth_screen()
    st.stop()

# -------------------- SIDEBAR --------------------

with st.sidebar:
    st.markdown("# 🚀 NEXTGEN AI")
    st.caption("One Platform. Endless Possibilities.")
    st.divider()

    pages = [
        "Dashboard",
        "AI Chat",
        "AI Tool Center",
        "Writing Studio",
        "Study Center",
        "Image Studio",
        "PDF Assistant",
        "Smart Web Search",
        "Developer Center",
        "Productivity Center",
        "Stock Dashboard",
        "My Creations",
        "Settings",
        "About"
    ]

    selected_page = st.radio(
        "WORKSPACE",
        pages,
        index=pages.index(st.session_state.page)
        if st.session_state.page in pages else 0
    )
    st.session_state.page = selected_page

    st.divider()
    st.markdown("### 💬 Chat History")

    if st.button("＋ New Chat", use_container_width=True):
        st.session_state.current_chat = create_chat()
        st.session_state.chat_messages = []
        st.session_state.page = "AI Chat"
        st.rerun()

    chat_rows = get_chats()
    for chat_id, title, created in chat_rows[:15]:
        c1, c2 = st.columns([4, 1])
        with c1:
            if st.button("💬 " + title[:24], key=f"open_{chat_id}"):
                st.session_state.current_chat = chat_id
                st.session_state.chat_messages = load_messages(chat_id)
                st.session_state.page = "AI Chat"
                st.rerun()
        with c2:
            if st.button("⋯", key=f"del_{chat_id}"):
                st.session_state["manage_chat"] = chat_id

    if st.session_state.get("manage_chat"):
        cid = st.session_state.manage_chat
        st.warning("Manage selected chat")
        new_title = st.text_input("Rename chat", key=f"rename_{cid}")
        a, b = st.columns(2)
        if a.button("Save", key=f"save_{cid}"):
            if new_title.strip():
                rename_chat(cid, new_title.strip())
            st.session_state.manage_chat = None
            st.rerun()
        if b.button("Delete", key=f"delete_{cid}"):
            delete_chat(cid)
            if st.session_state.current_chat == cid:
                st.session_state.current_chat = None
                st.session_state.chat_messages = []
            st.session_state.manage_chat = None
            st.rerun()

    st.divider()
    st.caption("Signed in as " + str(st.session_state.username))
    if st.button("Log out", use_container_width=True):
        for key in ["user_key", "username", "guest", "current_chat"]:
            st.session_state[key] = None
        st.session_state.chat_messages = []
        st.rerun()

# -------------------- DASHBOARD --------------------

def dashboard():
    st.markdown("""
    <div class="ng-hero">
      <span class="ng-tag">AI WORKSPACE</span>
      <h1>Welcome to NEXTGEN AI 🚀</h1>
      <h3>Your all-in-one AI platform.</h3>
      <p class="ng-muted">Write, learn, research, create and build — all in one place.</p>
    </div>
    """, unsafe_allow_html=True)

    a, b, c, d = st.columns(4)
    a.metric("AI Tools", "120+")
    b.metric("AI Models", "2")
    c.metric("Workspace", "All-in-One")
    d.metric("Account", "Guest" if st.session_state.guest else "Member")

    st.subheader("Explore your workspace")
    cards = [
        ("💬", "AI Chat", "Chat with Grok and Gemini"),
        ("✍️", "Writing Studio", "Emails, letters, essays and more"),
        ("🎓", "Study Center", "Notes, quizzes and explanations"),
        ("🎨", "Image Studio", "Create images with Cloudflare"),
        ("📄", "PDF Assistant", "Ask questions about PDF files"),
        ("🔎", "Smart Web Search", "Research with source links"),
        ("💻", "Developer Center", "Code, debug and explain"),
        ("⚡", "Productivity Center", "Plan, organize and create")
    ]
    for start in range(0, len(cards), 4):
        cols = st.columns(4)
        for col, item in zip(cols, cards[start:start+4]):
            with col:
                st.markdown(
                    f"""<div class="ng-card">
                    <h2>{item[0]}</h2><b>{item[1]}</b>
                    <p class="ng-muted">{item[2]}</p></div>""",
                    unsafe_allow_html=True
                )

    st.subheader("Quick Start")
    q1, q2, q3 = st.columns(3)
    if q1.button("Write an Email", use_container_width=True):
        st.session_state.page = "Writing Studio"
        st.rerun()
    if q2.button("Make Study Notes", use_container_width=True):
        st.session_state.page = "Study Center"
        st.rerun()
    if q3.button("Open AI Chat", use_container_width=True):
        st.session_state.page = "AI Chat"
        st.rerun()

# -------------------- CHAT WORKSPACE --------------------

def chat_page():
    st.title("💬 AI Chat")
    st.caption("Chat with Grok or Gemini. Auto mode tries the configured providers.")

    st.session_state.model = st.selectbox(
        "AI Model",
        ["Auto", "Grok", "Gemini"],
        index=["Auto", "Grok", "Gemini"].index(st.session_state.model)
        if st.session_state.model in ["Auto", "Grok", "Gemini"] else 0
    )

    if st.session_state.current_chat is None:
        if st.button("Start a new conversation"):
            st.session_state.current_chat = create_chat()
            st.session_state.chat_messages = []
            st.rerun()

    for message in st.session_state.chat_messages:
        with st.chat_message(message["role"]):
            st.markdown(message["content"])

    uploaded = st.file_uploader(
        "Attach a text file or PDF (optional)",
        type=["txt", "md", "pdf"],
        key="chat_attachment"
    )

    prompt = st.chat_input("Message NEXTGEN AI...")
    if prompt:
        extra = ""
        if uploaded:
            if uploaded.name.lower().endswith(".pdf"):
                extra = extract_pdf_text(uploaded)[:18000]
            else:
                extra = uploaded.getvalue().decode("utf-8", errors="ignore")[:18000]

        user_content = prompt
        if extra:
            user_content += "\n\nAttached document content:\n" + extra

        if st.session_state.current_chat is None:
            st.session_state.current_chat = create_chat(prompt[:50])

        st.session_state.chat_messages.append(
            {"role": "user", "content": user_content}
        )
        save_message(st.session_state.current_chat, "user", user_content)

        with st.chat_message("user"):
            st.markdown(prompt)
            if uploaded:
                st.caption("Attachment: " + uploaded.name)

        with st.chat_message("assistant"):
            with st.spinner("NEXTGEN AI is thinking..."):
                try:
                    messages = [
                        {
                            "role": "system",
                            "content": (
                                "You are NEXTGEN AI, a helpful, safe, accurate "
                                "AI assistant. Reply in the user's language. "
                                "Be clear and practical."
                            )
                        }
                    ] + st.session_state.chat_messages[-16:]

                    if needs_web_search(prompt):
                        search_context = web_search(prompt)
                        messages.append({
                            "role": "system",
                            "content": "Relevant web search results:\n" + search_context
                        })

                    answer, provider = ai_reply(messages)
                    st.markdown(answer)
                    st.caption("Powered by " + provider)
                    st.session_state.chat_messages.append(
                        {"role": "assistant", "content": answer}
                    )
                    save_message(st.session_state.current_chat, "assistant", answer)
                except Exception as e:
                    st.error(str(e))

# -------------------- TOOL CENTER --------------------

def tool_center(default_group=None):
    st.title("🧰 AI Tool Center")
    st.caption(f"{len(ALL_TOOLS)} tools • One AI engine • Multiple workflows")

    groups = list(TOOL_GROUPS.keys())
    group = st.selectbox(
        "Choose a category",
        groups,
        index=groups.index(default_group) if default_group in groups else 0
    )

    tools = TOOL_GROUPS[group]
    selected_tool = st.selectbox("Choose your AI tool", tools)

    st.markdown(f"### ✨ {selected_tool}")
    st.info("अपना विवरण लिखो। AI तुम्हारे लिए पूरा परिणाम तैयार करेगा।")

    language = st.selectbox(
        "Output language",
        ["Hindi", "English", "Hinglish", "User's language"]
    )
    tone = st.selectbox(
        "Tone",
        ["Professional", "Friendly", "Formal", "Creative",
         "Simple", "Detailed", "Academic"]
    )
    length = st.selectbox(
        "Answer length",
        ["Short", "Medium", "Detailed"]
    )

    prompt = st.text_area(
        "What should NEXTGEN AI create?",
        height=180,
        placeholder=(
            "Example: Write a professional email to my teacher "
            "requesting two days of leave..."
        )
    )

    model = st.selectbox(
        "Generation model",
        ["Auto", "Grok", "Gemini"],
        key="tool_model"
    )

    if st.button("✨ Generate", use_container_width=True):
        if not prompt.strip():
            st.warning("Please enter your instructions first.")
        else:
            full_prompt = tool_instruction(
                selected_tool, prompt, tone, length, language
            )
            with st.spinner(f"{selected_tool} is working..."):
                try:
                    result, provider = ai_reply(
                        [{"role": "user", "content": full_prompt}],
                        model
                    )
                    st.session_state.last_result = result
                    save_generated(selected_tool, prompt, result)
                    st.success(f"Created with {provider}")
                except Exception as e:
                    st.error(str(e))

    if st.session_state.last_result:
        st.divider()
        st.subheader("Your Result")
        st.markdown(st.session_state.last_result)
        st.download_button(
            "⬇️ Download as TXT",
            data=st.session_state.last_result,
            file_name="nextgen_ai_result.txt",
            mime="text/plain",
            use_container_width=True
        )
        if st.button("Clear result"):
            st.session_state.last_result = ""
            st.rerun()

# -------------------- IMAGE STUDIO --------------------

def image_studio():
    st.title("🎨 AI Image Studio")
    st.caption("Text-to-image using your configured Cloudflare model.")

    prompt = st.text_area(
        "Describe the image",
        height=140,
        placeholder="A cinematic futuristic city at night..."
    )
    ratio = st.selectbox(
        "Aspect ratio",
        ["1:1", "16:9", "9:16", "3:4", "4:3"]
    )
    st.caption(
        "Image generation may incur Cloudflare usage charges. "
        "Check your Cloudflare account pricing before generating."
    )

    if st.button("Generate Image", use_container_width=True):
        if not prompt.strip():
            st.warning("Enter an image prompt.")
        else:
            with st.spinner("Generating image..."):
                try:
                    image_url = cloudflare_image(prompt, ratio)
                    st.image(image_url, caption="Generated with Cloudflare")
                    st.markdown(f"[Open generated image]({image_url})")
                except Exception as e:
                    st.error(str(e))

# -------------------- PDF ASSISTANT --------------------

def pdf_assistant():
    st.title("📄 PDF Assistant")
    file = st.file_uploader("Upload a PDF", type=["pdf"])
    if not file:
        st.info("Upload a PDF to summarize it or ask questions.")
        return

    try:
        text = extract_pdf_text(file)
    except Exception as e:
        st.error(str(e))
        return

    st.success(f"PDF loaded • {len(text)} characters extracted")
    task = st.selectbox(
        "Choose an action",
        [
            "Summarize this PDF",
            "Make study notes",
            "Generate questions",
            "Explain difficult topics",
            "Ask my own question"
        ]
    )
    question = st.text_area(
        "Your question or instructions",
        placeholder="What are the most important points?"
    )

    if st.button("Analyze PDF", use_container_width=True):
        instruction = (
            f"Task: {task}\nUser instructions: {question}\n\n"
            "Use only the supplied PDF content for document-specific claims. "
            "If the answer is not present, say so.\n\n"
            f"PDF CONTENT:\n{text[:26000]}"
        )
        with st.spinner("Reading your PDF..."):
            try:
                answer, provider = ai_reply(
                    [{"role": "user", "content": instruction}]
                )
                st.markdown(answer)
                st.caption("Powered by " + provider)
            except Exception as e:
                st.error(str(e))

# -------------------- WEB SEARCH --------------------

def search_page():
    st.title("🔎 Smart Web Search")
    st.caption("Search the web and get a readable source list.")
    query = st.text_input("What do you want to research?")
    if st.button("Search Web", use_container_width=True):
        if not query.strip():
            st.warning("Enter a search query.")
        else:
            with st.spinner("Searching..."):
                result = web_search(query)
                st.markdown(result)

# -------------------- STOCK DASHBOARD --------------------

def stock_dashboard():
    st.title("📈 Stock Dashboard")
    st.caption("Educational market information. Not investment advice.")

    if not FINNHUB_API_KEY:
        st.warning("Add FINNHUB_API_KEY to Streamlit Secrets to enable quotes.")
        return

    symbol = st.text_input("Stock symbol", "AAPL").upper().strip()
    if st.button("Get Quote", use_container_width=True):
        try:
            response = requests.get(
                "https://finnhub.io/api/v1/quote",
                params={"symbol": symbol, "token": FINNHUB_API_KEY},
                timeout=25
            )
            response.raise_for_status()
            data = response.json()

            if not data.get("c"):
                st.warning("No quote returned for this symbol.")
                return

            c1, c2, c3, c4 = st.columns(4)
            c1.metric("Current", data.get("c"))
            c2.metric("Change", data.get("d"))
            c3.metric("Change %", data.get("dp"))
            c4.metric("Previous Close", data.get("pc"))
            st.caption("Data supplied by Finnhub. Check exchange hours and delays.")
        except Exception as e:
            st.error(str(e))

# -------------------- MY CREATIONS --------------------

def my_creations():
    st.title("🗂️ My Creations")
    con = db()
    rows = con.execute(
        """SELECT tool_name,prompt,result,created_at
        FROM generated_items WHERE user_key=?
        ORDER BY id DESC LIMIT 50""",
        (current_user_key(),)
    ).fetchall()
    con.close()

    if not rows:
        st.info("Your generated content will appear here.")
        return

    for tool_name, prompt, result, created_at in rows:
        with st.expander(f"{tool_name} • {created_at[:16]}"):
            st.caption(prompt)
            st.markdown(result)
            st.download_button(
                "Download",
                result,
                file_name="creation.txt",
                key="download_" + str(abs(hash(created_at + tool_name)))
            )

# -------------------- SETTINGS --------------------

def settings_page():
    st.title("⚙️ Settings")
    st.subheader("Provider configuration")
    providers = [
        ("xAI Grok", bool(XAI_API_KEY)),
        ("Google Gemini", bool(GEMINI_API_KEY)),
        ("Tavily Web Search", bool(TAVILY_API_KEY)),
        ("Cloudflare Image", bool(CF_ACCOUNT_ID and CF_API_TOKEN)),
        ("Finnhub Stocks", bool(FINNHUB_API_KEY))
    ]

    for name, ready in providers:
        st.write(
            ("🟢 " if ready else "⚪ ") + name +
            (" — configured" if ready else " — not configured")
        )

    st.divider()
    st.subheader("Current model settings")
    st.write("Gemini model:", GEMINI_MODEL)
    st.write("Cloudflare image model:", CF_IMAGE_MODEL)
    st.info(
        "API keys are read from Streamlit Cloud Secrets. "
        "Never place secret keys in public GitHub code."
    )

# -------------------- ABOUT --------------------

def about_page():
    st.title("🚀 About NEXTGEN AI")
    st.markdown("""
    NEXTGEN AI is an all-in-one AI workspace.

    **Available areas**
    - AI Chat with Grok and Gemini
    - 100+ AI writing, study, developer and productivity tools
    - PDF Assistant
    - Smart Web Search
    - Cloudflare Image Studio
    - Stock quote dashboard
    - Chat history and generated creations
    - Guest mode and account login

    **Important**
    - Some AI providers and image services may charge for usage.
    - Free tiers have limits and can change.
    - Email tools create drafts; they do not send email.
    - Video generation, live voice calling, and advanced image editing
      need additional supported API integrations.
    - Market information is educational and may be delayed.
    """)

# -------------------- PAGE ROUTER --------------------

page = st.session_state.page

if page == "Dashboard":
    dashboard()

elif page == "AI Chat":
    chat_page()

elif page == "AI Tool Center":
    tool_center()

elif page == "Writing Studio":
    tool_center("AI Writing Studio")

elif page == "Study Center":
    tool_center("AI Study Center")

elif page == "Image Studio":
    image_studio()

elif page == "PDF Assistant":
    pdf_assistant()

elif page == "Smart Web Search":
    search_page()

elif page == "Developer Center":
    tool_center("AI Developer Center")

elif page == "Productivity Center":
    tool_center("AI Business & Productivity")

elif page == "Stock Dashboard":
    stock_dashboard()

elif page == "My Creations":
    my_creations()

elif page == "Settings":
    settings_page()

elif page == "About":
    about_page()

# -------------------- FOOTER --------------------

st.divider()
st.markdown(
    "<center><span class='ng-muted'>"
    "NEXTGEN AI © 2026 • Built for creativity, learning and productivity"
    "</span></center>",
    unsafe_allow_html=True
)
