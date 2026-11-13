
# ============================================================
# NEXTGEN AI — PREMIUM AI SUPER APP
# Version 3.0 | Single File | Streamlit
# ============================================================
#
# Install:
# pip install streamlit requests pandas pypdf pillow
#
# Run:
# streamlit run app.py
#
# Streamlit Cloud Secrets:
# XAI_API_KEY = "..."
# XAI_MODEL = "grok-3"
# GEMINI_API_KEY = "..."
# GEMINI_MODEL = "gemini-2.5-flash"
# TAVILY_API_KEY = "..."
# FINNHUB_API_KEY = "..."
# OWNER_NAME = "Arav"
# OWNER_PUBLIC_BIO = "Creator of NEXTGEN AI..."
#
# ============================================================

import streamlit as st
import sqlite3
import requests
import hashlib
import secrets
import re
import os
import json
import base64
from datetime import datetime

try:
    import pandas as pd
except Exception:
    pd = None

try:
    from pypdf import PdfReader
except Exception:
    PdfReader = None


# ============================================================
# 1. APP CONFIG
# ============================================================

st.set_page_config(
    page_title="NEXTGEN AI — Super App",
    page_icon="🚀",
    layout="wide",
    initial_sidebar_state="expanded"
)

APP_NAME = "NEXTGEN AI"
APP_VERSION = "3.0"
DB_PATH = "nextgen_ai_v3.db"


# ============================================================
# 2. SECRETS
# ============================================================

def secret(key, default=""):
    try:
        value = st.secrets.get(key, default)
        return str(value) if value is not None else default
    except Exception:
        return os.getenv(key, default)


XAI_API_KEY = secret("XAI_API_KEY")
XAI_MODEL = secret("XAI_MODEL", "grok-3")

GEMINI_API_KEY = secret("GEMINI_API_KEY")
GEMINI_MODEL = secret("GEMINI_MODEL", "gemini-2.5-flash")

TAVILY_API_KEY = secret("TAVILY_API_KEY")
FINNHUB_API_KEY = secret("FINNHUB_API_KEY")

OWNER_NAME = secret("OWNER_NAME", "Arav")
OWNER_PUBLIC_BIO = secret(
    "OWNER_PUBLIC_BIO",
    "Arav is the creator of NEXTGEN AI, an all-in-one AI platform "
    "built to bring AI chat, writing, learning, creativity and "
    "productivity tools into one workspace."
)


# ============================================================
# 3. PREMIUM UI
# ============================================================

st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=DM+Sans:wght@400;500;600;700;800&family=Space+Grotesk:wght@500;600;700&display=swap');

:root {
    --bg: #080b13;
    --panel: #101624;
    --panel2: #141d2e;
    --line: rgba(148,180,230,.15);
    --blue: #6ca8ff;
    --purple: #a78bfa;
    --cyan: #67e8f9;
    --text: #f2f6ff;
    --muted: #94a3b8;
}

html, body, [class*="css"] {
    font-family: 'DM Sans', sans-serif;
}

.stApp {
    background:
      radial-gradient(ellipse at 12% 0%, rgba(38,102,190,.19), transparent 34%),
      radial-gradient(ellipse at 88% 8%, rgba(125,75,210,.16), transparent 32%),
      radial-gradient(ellipse at 50% 100%, rgba(20,100,130,.08), transparent 40%),
      var(--bg);
    color: var(--text);
}

header[data-testid="stHeader"] {
    background: rgba(8,11,19,.65);
}

.block-container {
    max-width: 1500px;
    padding-top: 1.7rem;
    padding-bottom: 4rem;
}

section[data-testid="stSidebar"] {
    background: linear-gradient(180deg,#0c1220,#0a0f19);
    border-right: 1px solid var(--line);
}

section[data-testid="stSidebar"] > div {
    padding-top: 1.2rem;
}

h1,h2,h3 {
    font-family: 'Space Grotesk', sans-serif !important;
    letter-spacing: -.6px;
    color: #f5f8ff;
}

p, label, span {
    color: inherit;
}

div[data-testid="stMetric"] {
    background: linear-gradient(145deg,#17243a,#101827);
    border: 1px solid rgba(110,160,230,.2);
    padding: 18px;
    border-radius: 18px;
    box-shadow: 0 10px 35px rgba(0,0,0,.12);
}

div[data-testid="stMetricLabel"] {
    color: #a9bad4;
}

div[data-testid="stMetricValue"] {
    color: #f5f8ff;
    font-family: 'Space Grotesk',sans-serif;
}

.stButton > button {
    border: 1px solid rgba(116,164,239,.27);
    border-radius: 12px;
    color: #f6f9ff;
    background: linear-gradient(110deg,#1c4f91,#493c91);
    min-height: 43px;
    font-weight: 650;
    transition: .2s ease;
}

.stButton > button:hover {
    border-color: #8dc4ff;
    box-shadow: 0 0 22px rgba(70,140,255,.24);
    transform: translateY(-1px);
    color: white;
}

.stTextInput input,
.stTextArea textarea,
.stSelectbox div[data-baseweb="select"],
.stNumberInput input {
    background: #111a2a !important;
    color: #edf4ff !important;
    border: 1px solid #293b58 !important;
    border-radius: 12px !important;
}

.stTextArea textarea {
    line-height: 1.6;
}

div[data-testid="stChatMessage"] {
    background: linear-gradient(145deg,#131e30,#101725);
    border: 1px solid rgba(130,170,230,.15);
    border-radius: 18px;
    padding: 14px;
    margin-bottom: 12px;
}

div[data-testid="stExpander"] {
    background: rgba(17,27,44,.72);
    border: 1px solid var(--line);
    border-radius: 14px;
}

hr {
    border-color: rgba(148,180,230,.13);
}

.ng-brand {
    font-family: 'Space Grotesk',sans-serif;
    font-size: 24px;
    font-weight: 800;
    letter-spacing: -1px;
    background: linear-gradient(100deg,#fff,#7db8ff,#b8a4ff);
    -webkit-background-clip: text;
    -webkit-text-fill-color: transparent;
}

.ng-hero {
    position: relative;
    overflow: hidden;
    border-radius: 25px;
    padding: 34px;
    border: 1px solid rgba(126,177,255,.27);
    background:
      radial-gradient(circle at 85% 15%,rgba(125,100,255,.25),transparent 35%),
      linear-gradient(125deg,#142641,#171a39 58%,#102b3b);
    box-shadow: 0 22px 65px rgba(0,0,0,.24);
    margin-bottom: 24px;
}

.ng-hero h1 {
    font-size: clamp(32px,5vw,55px);
    margin: 10px 0 5px 0;
    line-height: 1.08;
}

.ng-hero p {
    color: #b8c9e4;
    font-size: 15px;
    max-width: 650px;
}

.ng-eyebrow {
    color: #9cc8ff;
    font-size: 11px;
    font-weight: 800;
    letter-spacing: 2px;
    text-transform: uppercase;
}

.ng-panel {
    border: 1px solid var(--line);
    border-radius: 18px;
    padding: 19px;
    background: linear-gradient(145deg,rgba(23,35,56,.93),rgba(13,20,33,.96));
    box-shadow: 0 12px 35px rgba(0,0,0,.13);
    min-height: 130px;
}

.ng-panel h3 {
    font-size: 17px;
    margin: 7px 0;
}

.ng-panel p {
    color: #9eafc8;
    font-size: 13px;
    margin-bottom: 0;
}

.ng-icon {
    font-size: 27px;
}

.ng-pill {
    display: inline-block;
    border: 1px solid rgba(125,180,255,.3);
    background: rgba(70,130,220,.12);
    color: #a9d2ff;
    padding: 5px 11px;
    border-radius: 30px;
    font-size: 11px;
    font-weight: 700;
}

.ng-small {
    color: #93a5bf;
    font-size: 12px;
}

.ng-divider {
    height: 1px;
    background: linear-gradient(90deg,transparent,#314766,transparent);
    margin: 20px 0;
}

.ng-feature {
    background: linear-gradient(145deg,#162641,#12182b);
    border: 1px solid rgba(130,170,240,.19);
    padding: 18px;
    border-radius: 17px;
}

.ng-feature strong {
    font-size: 14px;
}

.ng-feature p {
    font-size: 12px;
    color: #9eb0ca;
    margin: 5px 0 0 0;
}

.stTabs [data-baseweb="tab-list"] {
    gap: 8px;
}

.stTabs [data-baseweb="tab"] {
    background: #111a2a;
    border-radius: 10px;
    padding: 10px 16px;
}

.stTabs [aria-selected="true"] {
    background: #243e67 !important;
}

footer {
    visibility: hidden;
}
</style>
""", unsafe_allow_html=True)


# ============================================================
# 4. DATABASE — NEW TABLE NAMES TO AVOID OLD DB ERRORS
# ============================================================

def db():
    return sqlite3.connect(DB_PATH, check_same_thread=False)

def init_db():
    con = db()
    cur = con.cursor()

    cur.execute("""
        CREATE TABLE IF NOT EXISTS ng3_users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            created_at TEXT NOT NULL
        )
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS ng3_chats (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_key TEXT NOT NULL,
            title TEXT NOT NULL,
            created_at TEXT NOT NULL
        )
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS ng3_messages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            chat_id INTEGER NOT NULL,
            role TEXT NOT NULL,
            content TEXT NOT NULL,
            created_at TEXT NOT NULL
        )
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS ng3_creations (
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


# ============================================================
# 5. SESSION STATE
# ============================================================

DEFAULTS = {
    "user_key": None,
    "username": None,
    "guest": False,
    "page": "Dashboard",
    "chat_id": None,
    "messages": [],
    "model_choice": "Auto",
    "last_tool_result": "",
    "last_tool_name": "",
    "last_image": None,
    "search_results": "",
    "owner_profile": True,
}

for key, value in DEFAULTS.items():
    if key not in st.session_state:
        st.session_state[key] = value


def user_key():
    return st.session_state.user_key or "guest"


# ============================================================
# 6. AUTHENTICATION
# ============================================================

def hash_password(password, salt=None):
    salt = salt or secrets.token_hex(16)
    digest = hashlib.pbkdf2_hmac(
        "sha256",
        password.encode("utf-8"),
        salt.encode("utf-8"),
        180000
    ).hex()
    return salt + "$" + digest


def check_password(password, stored):
    try:
        salt, _ = stored.split("$", 1)
        return hash_password(password, salt) == stored
    except Exception:
        return False


def create_account(username, password):
    con = db()
    try:
        con.execute(
            "INSERT INTO ng3_users(username,password_hash,created_at) VALUES(?,?,?)",
            (username, hash_password(password), datetime.now().isoformat())
        )
        con.commit()
        return True, "Account created successfully."
    except sqlite3.IntegrityError:
        return False, "Username already exists."
    finally:
        con.close()


def authenticate(username, password):
    con = db()
    row = con.execute(
        "SELECT password_hash FROM ng3_users WHERE username=?",
        (username,)
    ).fetchone()
    con.close()
    return bool(row and check_password(password, row[0]))


def auth_page():
    st.markdown("""
    <div class="ng-hero">
      <div class="ng-eyebrow">YOUR AI UNIVERSE STARTS HERE</div>
      <h1>Welcome to NEXTGEN AI.</h1>
      <p>One intelligent workspace for writing, learning, creating,
      researching and building.</p>
      <span class="ng-pill">100+ AI TOOLS • ONE WORKSPACE</span>
    </div>
    """, unsafe_allow_html=True)

    left, right = st.columns([1.1, 1])

    with left:
        st.markdown("### ✨ A smarter way to create")
        st.markdown("""
        - 💬 AI Chat with configurable models
        - ✍️ Writing and communication tools
        - 🎓 Study and learning assistant
        - 💻 Developer workspace
        - 🔎 Web research and PDF assistant
        - 🎨 Creative prompt studio
        """)

    with right:
        login_tab, signup_tab = st.tabs(["Sign In", "Create Account"])

        with login_tab:
            u = st.text_input("Username", key="auth_login_user")
            p = st.text_input("Password", type="password", key="auth_login_pass")
            if st.button("Sign In →", use_container_width=True):
                if authenticate(u.strip(), p):
                    st.session_state.user_key = "user:" + u.strip()
                    st.session_state.username = u.strip()
                    st.session_state.guest = False
                    st.rerun()
                else:
                    st.error("Incorrect username or password.")

        with signup_tab:
            nu = st.text_input("Choose username", key="auth_new_user")
            np = st.text_input("Choose password", type="password", key="auth_new_pass")
            cp = st.text_input("Confirm password", type="password", key="auth_confirm_pass")
            if st.button("Create Account →", use_container_width=True):
                if len(nu.strip()) < 3:
                    st.error("Username must have at least 3 characters.")
                elif len(np) < 8:
                    st.error("Password must have at least 8 characters.")
                elif np != cp:
                    st.error("Passwords do not match.")
                else:
                    ok, msg = create_account(nu.strip(), np)
                    if ok:
                        st.success(msg + " You can now sign in.")
                    else:
                        st.error(msg)

    st.divider()
    if st.button("Continue as Guest", use_container_width=True):
        guest_id = secrets.token_hex(12)
        st.session_state.user_key = "guest:" + guest_id
        st.session_state.username = "Guest"
        st.session_state.guest = True
        st.rerun()


if not st.session_state.user_key:
    auth_page()
    st.stop()


# ============================================================
# 7. CHAT DATABASE FUNCTIONS
# ============================================================

def create_chat(title="New Conversation"):
    con = db()
    cur = con.cursor()
    cur.execute(
        "INSERT INTO ng3_chats(user_key,title,created_at) VALUES(?,?,?)",
        (user_key(), title[:65], datetime.now().isoformat())
    )
    cid = cur.lastrowid
    con.commit()
    con.close()
    return cid


def list_chats():
    con = db()
    rows = con.execute(
        "SELECT id,title,created_at FROM ng3_chats "
        "WHERE user_key=? ORDER BY id DESC",
        (user_key(),)
    ).fetchall()
    con.close()
    return rows


def rename_chat(cid, title):
    con = db()
    con.execute(
        "UPDATE ng3_chats SET title=? WHERE id=? AND user_key=?",
        (title[:65], cid, user_key())
    )
    con.commit()
    con.close()


def remove_chat(cid):
    con = db()
    con.execute("DELETE FROM ng3_messages WHERE chat_id=?", (cid,))
    con.execute(
        "DELETE FROM ng3_chats WHERE id=? AND user_key=?",
        (cid, user_key())
    )
    con.commit()
    con.close()


def save_message(cid, role, content):
    con = db()
    con.execute(
        "INSERT INTO ng3_messages(chat_id,role,content,created_at) VALUES(?,?,?,?)",
        (cid, role, content, datetime.now().isoformat())
    )
    con.commit()
    con.close()


def read_messages(cid):
    con = db()
    rows = con.execute(
        "SELECT role,content FROM ng3_messages WHERE chat_id=? ORDER BY id",
        (cid,)
    ).fetchall()
    con.close()
    return [{"role": r, "content": c} for r, c in rows]


def save_creation(tool, prompt, result):
    con = db()
    con.execute(
        """INSERT INTO ng3_creations
        (user_key,tool_name,prompt,result,created_at)
        VALUES(?,?,?,?,?)""",
        (
            user_key(), tool, prompt, result,
            datetime.now().isoformat()
        )
    )
    con.commit()
    con.close()


# ============================================================
# 8. AI PROVIDERS
# ============================================================

def xai_generate(messages):
    if not XAI_API_KEY:
        raise RuntimeError("XAI_API_KEY is not configured.")

    response = requests.post(
        "https://api.x.ai/v1/chat/completions",
        headers={
            "Authorization": f"Bearer {XAI_API_KEY}",
            "Content-Type": "application/json"
        },
        json={
            "model": XAI_MODEL,
            "messages": messages,
            "temperature": 0.7
        },
        timeout=120
    )

    if not response.ok:
        raise RuntimeError(
            f"xAI error {response.status_code}: {response.text[:500]}"
        )

    data = response.json()
    return data["choices"][0]["message"]["content"]


def gemini_generate(messages):
    if not GEMINI_API_KEY:
        raise RuntimeError("GEMINI_API_KEY is not configured.")

    system_text = ""
    contents = []

    for m in messages:
        role = m.get("role", "user")
        content = str(m.get("content", ""))

        if role == "system":
            system_text += content + "\n"
        else:
            contents.append({
                "role": "model" if role == "assistant" else "user",
                "parts": [{"text": content}]
            })

    payload = {"contents": contents}

    if system_text:
        payload["systemInstruction"] = {
            "parts": [{"text": system_text}]
        }

    url = (
        "https://generativelanguage.googleapis.com/v1beta/"
        f"models/{GEMINI_MODEL}:generateContent"
    )

    response = requests.post(
        url,
        params={"key": GEMINI_API_KEY},
        json=payload,
        timeout=120
    )

    if not response.ok:
        raise RuntimeError(
            f"Gemini error {response.status_code}: {response.text[:500]}"
        )

    data = response.json()
    return data["candidates"][0]["content"]["parts"][0]["text"]


def generate_ai(messages, model="Auto"):
    errors = []

    if model in ("Auto", "Grok") and XAI_API_KEY:
        try:
            return xai_generate(messages), "Grok"
        except Exception as e:
            errors.append("Grok: " + str(e))

    if model in ("Auto", "Gemini") and GEMINI_API_KEY:
        try:
            return gemini_generate(messages), "Gemini"
        except Exception as e:
            errors.append("Gemini: " + str(e))

    if not errors:
        errors.append("No configured AI provider. Add API keys in Streamlit Secrets.")

    raise RuntimeError("\n".join(errors))


# ============================================================
# 9. OWNER / CREATOR PROFILE
# ============================================================

OWNER_RULES = f"""
You are NEXTGEN AI, an intelligent assistant.

PUBLIC CREATOR PROFILE:
Creator name: {OWNER_NAME}
Creator bio: {OWNER_PUBLIC_BIO}

PLATFORM:
NEXTGEN AI is an AI workspace with chat, writing, study,
developer, research, document and creative tools.

If asked who created NEXTGEN AI, say that its creator is {OWNER_NAME}.
If asked about the owner, only share the public bio above.
Do not invent private information, age, address, school,
phone number, achievements or personal history.
If a fact is not supplied, say it has not been publicly provided.

Be accurate, friendly, helpful and safe.
Reply in the user's language.
"""


# ============================================================
# 10. SMART WEB SEARCH
# ============================================================

def should_search(query):
    patterns = [
        r"\b(latest|today|current|right now|live|recent|this week)\b",
        r"\b(news|weather|stock price|market price|score|schedule)\b",
        r"(आज|अभी|ताज़ा|लेटेस्ट|वर्तमान|मौसम|आज का भाव|ताजा खबर)"
    ]
    return any(re.search(p, query, re.I) for p in patterns)


def tavily_search(query):
    if not TAVILY_API_KEY:
        return "Web search is not configured. Add TAVILY_API_KEY."

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
        raise RuntimeError("Search error: " + response.text[:400])

    data = response.json()
    output = []

    if data.get("answer"):
        output.append("SEARCH SUMMARY:\n" + data["answer"])

    for item in data.get("results", []):
        output.append(
            f"TITLE: {item.get('title','')}\n"
            f"SUMMARY: {item.get('content','')}\n"
            f"SOURCE: {item.get('url','')}"
        )

    return "\n\n".join(output)


# ============================================================
# 11. TOOL CENTER — 120+ TOOLS
# ============================================================

TOOL_GROUPS = {
    "✍️ Writing Studio": [
        "AI Email Writer", "Email Reply Writer", "Formal Email Writer",
        "Friendly Email Writer", "Follow-up Email Writer",
        "Apology Email Writer", "Thank You Email Writer",
        "Meeting Request Email", "Leave Application Writer",
        "School Application Writer", "Permission Letter Writer",
        "Complaint Letter Writer", "Invitation Writer",
        "Notice Writer", "Report Writer", "Essay Writer",
        "Paragraph Writer", "Article Writer", "Blog Writer",
        "Story Writer", "Poem Writer", "Speech Writer",
        "Debate Writer", "Project Writer", "Assignment Writer",
        "Resume Builder", "Cover Letter Writer", "Professional Bio Writer",
        "Product Description Writer", "Ad Copy Writer",
        "Social Media Caption Writer", "YouTube Description Writer",
        "YouTube Title Generator", "WhatsApp Message Writer",
        "Birthday Wish Writer", "Professional Message Writer",
        "Text Rewriter", "Grammar Corrector", "Tone Changer",
        "Text Improver", "Text Shortener", "Text Expander",
        "Text Summarizer", "Bullet Point Maker", "Headline Generator",
        "Tagline Generator", "Slogan Generator", "Hashtag Generator",
        "Content Calendar Maker"
    ],

    "🎓 Study Center": [
        "Homework Helper", "Study Notes Maker", "Chapter Summarizer",
        "Question Answer Maker", "MCQ Generator", "Quiz Generator",
        "Flashcard Maker", "Math Explainer", "Science Explainer",
        "History Explainer", "Geography Explainer", "Grammar Tutor",
        "Vocabulary Builder", "Spelling Practice", "Reading Comprehension",
        "Study Planner", "Revision Planner", "Exam Practice Maker",
        "Formula Sheet Maker", "Concept Explainer", "Difficult Word Explainer",
        "Lesson Planner", "Project Topic Generator", "School Speech Writer",
        "School Timetable Maker"
    ],

    "💻 Developer Center": [
        "Python Code Generator", "HTML Generator", "CSS Generator",
        "JavaScript Generator", "Code Explainer", "Bug Explainer",
        "Code Reviewer", "Code Comment Writer", "SQL Query Helper",
        "Regex Generator", "JSON Helper", "API Documentation Writer",
        "Website Idea Generator", "Website Planner", "Landing Page Writer",
        "App Idea Generator", "App Feature Planner", "UI Text Writer",
        "Git Command Explainer", "Algorithm Explainer"
    ],

    "📊 Business & Productivity": [
        "Business Idea Generator", "Business Plan Writer",
        "Business Name Generator", "Brand Slogan Generator",
        "Marketing Plan Maker", "Customer Reply Writer",
        "Customer Support Response", "SWOT Analysis Maker",
        "Pros and Cons Maker", "Decision Helper",
        "Meeting Agenda Maker", "Meeting Notes Formatter",
        "Task Planner", "Daily Planner", "Goal Planner",
        "Checklist Maker", "Presentation Outline Maker",
        "Slide Content Writer", "Interview Question Maker",
        "Interview Practice", "Event Plan Maker"
    ],

    "🎬 Creator Studio": [
        "Video Script Writer", "Reel Script Writer",
        "Shorts Hook Generator", "Video Scene Planner",
        "Storyboard Writer", "Photo Prompt Generator",
        "Image Prompt Enhancer", "Video Prompt Generator",
        "Thumbnail Text Generator", "Thumbnail Concept Maker",
        "Podcast Script Writer", "Podcast Topic Generator",
        "Character Creator", "World Builder", "Dialogue Writer",
        "Creative Idea Generator", "Meme Caption Writer",
        "Instagram Bio Writer", "Channel Name Generator"
    ],

    "🌍 Language & Documents": [
        "Translator", "Hindi to English", "English to Hindi",
        "Simple Language Rewriter", "PDF Summarizer",
        "Document Summarizer", "Key Point Extractor",
        "Table to Text Helper", "Formal Language Converter",
        "Proofreading Assistant", "Research Outline Maker"
    ],

    "⚡ Everyday Tools": [
        "Calculator Explainer", "Unit Conversion Explainer",
        "Recipe Idea Generator", "Travel Itinerary Draft",
        "Gift Idea Generator", "Routine Planner",
        "Packing Checklist", "Book Summary Helper",
        "Movie Review Draft", "Knowledge Organizer",
        "Question Generator", "Learning Topic Generator",
        "Decision Matrix Maker"
    ]
}

TOOL_COUNT = sum(len(v) for v in TOOL_GROUPS.values())


def tool_prompt(tool, user_text, language, tone, length):
    return f"""
You are a specialized AI tool inside NEXTGEN AI.
Tool: {tool}

Task: Complete the user's request. Produce the actual result,
not instructions about how to do it.

Language: {language}
Tone: {tone}
Length: {length}

Important:
- Do not invent facts or personal details.
- Use placeholders for missing information.
- For emails, create a complete editable email draft.
- For letters, include an appropriate greeting and closing.
- For school tasks, explain clearly and at an appropriate level.
- For coding, provide complete code where practical.
- For summaries, preserve the source meaning.
- Clearly mention uncertainty when necessary.

USER REQUEST:
{user_text}
"""


def tool_center(category=None):
    st.markdown("""
    <div class="ng-hero">
      <div class="ng-eyebrow">YOUR AI TOOLBOX</div>
      <h1>AI Tool Center.</h1>
      <p>One workspace. Hundreds of ways to write, learn, create and build.</p>
      <span class="ng-pill">SMART AI TOOLS</span>
    </div>
    """, unsafe_allow_html=True)

    categories = list(TOOL_GROUPS.keys())

    if category not in categories:
        category = categories[0]

    chosen_category = st.selectbox(
        "Explore categories",
        categories,
        index=categories.index(category)
    )

    tools = TOOL_GROUPS[chosen_category]
    chosen_tool = st.selectbox("Select a tool", tools)

    st.markdown(f"### {chosen_tool}")

    c1, c2, c3 = st.columns(3)

    with c1:
        language = st.selectbox(
            "Language",
            ["Hindi", "English", "Hinglish", "User's language"]
        )

    with c2:
        tone = st.selectbox(
            "Tone",
            ["Professional", "Friendly", "Formal", "Creative", "Simple"]
        )

    with c3:
        length = st.selectbox(
            "Length",
            ["Short", "Medium", "Detailed"]
        )

    user_text = st.text_area(
        "Describe what you want",
        height=180,
        placeholder="Write your instructions here..."
    )

    model = st.selectbox(
        "AI Model",
        ["Auto", "Grok", "Gemini"],
        key="tool_model_choice"
    )

    if st.button("✨ Generate Result", use_container_width=True):
        if not user_text.strip():
            st.warning("Please enter your instructions.")
        else:
            prompt = tool_prompt(
                chosen_tool, user_text, language, tone, length
            )

            with st.spinner(f"{chosen_tool} is working..."):
                try:
                    result, provider = generate_ai(
                        [{"role": "system", "content": OWNER_RULES},
                         {"role": "user", "content": prompt}],
                        model
                    )

                    st.session_state.last_tool_result = result
                    st.session_state.last_tool_name = chosen_tool
                    save_creation(chosen_tool, user_text, result)

                    st.success("Your result is ready • " + provider)

                except Exception as e:
                    st.error(str(e))

    if st.session_state.last_tool_result:
        st.markdown('<div class="ng-divider"></div>', unsafe_allow_html=True)
        st.markdown("### ✨ Your Result")
        st.markdown(st.session_state.last_tool_result)

        st.download_button(
            "⬇️ Download Result",
            data=st.session_state.last_tool_result,
            file_name="nextgen_result.txt",
            mime="text/plain",
            use_container_width=True
        )

        if st.button("Clear Result"):
            st.session_state.last_tool_result = ""
            st.rerun()


# ============================================================
# 12. PDF ASSISTANT
# ============================================================

def pdf_assistant():
    st.title("📄 PDF Intelligence")
    st.caption("Upload a document and ask questions about its contents.")

    if PdfReader is None:
        st.error("Install pypdf: pip install pypdf")
        return

    file = st.file_uploader("Upload PDF", type=["pdf"])

    if not file:
        st.info("Your document workspace will appear here after upload.")
        return

    try:
        reader = PdfReader(file)
        pages = []
        for index, page in enumerate(reader.pages):
            text = page.extract_text() or ""
            pages.append(f"PAGE {index+1}\n{text}")
        document_text = "\n\n".join(pages)
    except Exception as e:
        st.error("Could not read this PDF: " + str(e))
        return

    st.success(f"PDF loaded • {len(reader.pages)} pages")

    task = st.selectbox(
        "Choose an action",
        [
            "Summarize PDF",
            "Make detailed notes",
            "Generate MCQs",
            "Extract key points",
            "Explain difficult topics",
            "Answer my question"
        ]
    )

    question = st.text_area("Instructions / Question")

    if st.button("Analyze Document", use_container_width=True):
        prompt = f"""
        Task: {task}
        User question: {question}

        Use the document below. Do not invent details.
        If the answer is not in the PDF, say so.

        DOCUMENT:
        {document_text[:26000]}
        """

        with st.spinner("Analyzing document..."):
            try:
                answer, provider = generate_ai(
                    [{"role": "system", "content": OWNER_RULES},
                     {"role": "user", "content": prompt}]
                )
                st.markdown(answer)
                st.caption("Powered by " + provider)
            except Exception as e:
                st.error(str(e))


# ============================================================
# 13. WEB RESEARCH
# ============================================================

def research_page():
    st.markdown("""
    <div class="ng-hero">
      <div class="ng-eyebrow">RESEARCH WORKSPACE</div>
      <h1>Smart Web Research.</h1>
      <p>Find information and review source links in one place.</p>
    </div>
    """, unsafe_allow_html=True)

    query = st.text_input(
        "What do you want to research?",
        placeholder="Search a topic, product, technology or current event..."
    )

    if st.button("🔎 Search the Web", use_container_width=True):
        if not query.strip():
            st.warning("Enter a search query.")
        else:
            with st.spinner("Searching the web..."):
                try:
                    result = tavily_search(query)
                    st.session_state.search_results = result
                except Exception as e:
                    st.error(str(e))

    if st.session_state.search_results:
        st.markdown("### Search Results")
        st.markdown(st.session_state.search_results)


# ============================================================
# 14. IMAGE PROMPT STUDIO
# ============================================================

def image_prompt_studio():
    st.markdown("""
    <div class="ng-hero">
      <div class="ng-eyebrow">CREATOR WORKSPACE</div>
      <h1>Image Prompt Studio.</h1>
      <p>Turn simple ideas into detailed prompts for image-generation models.</p>
    </div>
    """, unsafe_allow_html=True)

    idea = st.text_area(
        "Describe your image idea",
        height=140,
        placeholder="A futuristic AI city with glowing blue buildings..."
    )

    style = st.selectbox(
        "Visual style",
        [
            "Cinematic photorealistic",
            "3D animation",
            "Anime",
            "Minimal modern",
            "Fantasy art",
            "Luxury advertising",
            "Digital illustration"
        ]
    )

    ratio = st.selectbox(
        "Aspect ratio",
        ["9:16", "16:9", "1:1", "4:5", "3:4"]
    )

    if st.button("Generate Image Prompt", use_container_width=True):
        if not idea.strip():
            st.warning("Describe your idea first.")
        else:
            prompt = f"""
            Create a detailed image-generation prompt.
            Idea: {idea}
            Style: {style}
            Aspect ratio: {ratio}

            Include subject, composition, lighting, camera,
            background, atmosphere, color palette and details.
            Do not generate an image; generate the prompt text.
            """

            with st.spinner("Creating prompt..."):
                try:
                    result, provider = generate_ai(
                        [{"role": "user", "content": prompt}]
                    )
                    st.markdown("### Your Image Prompt")
                    st.code(result)
                    st.caption("Created with " + provider)
                    st.download_button(
                        "Download Prompt",
                        result,
                        file_name="image_prompt.txt"
                    )
                except Exception as e:
                    st.error(str(e))


# ============================================================
# 15. STOCK DASHBOARD
# ============================================================

def stock_page():
    st.markdown("""
    <div class="ng-hero">
      <div class="ng-eyebrow">MARKET WORKSPACE</div>
      <h1>Market Watch.</h1>
      <p>Explore stock quote information. Educational use only.</p>
    </div>
    """, unsafe_allow_html=True)

    if not FINNHUB_API_KEY:
        st.warning("Add FINNHUB_API_KEY to enable stock quotes.")
        return

    symbol = st.text_input("Stock ticker", "AAPL").strip().upper()

    if st.button("Get Market Quote", use_container_width=True):
        try:
            response = requests.get(
                "https://finnhub.io/api/v1/quote",
                params={
                    "symbol": symbol,
                    "token": FINNHUB_API_KEY
                },
                timeout=25
            )
            response.raise_for_status()
            data = response.json()

            if not data.get("c"):
                st.warning("No quote found for this symbol.")
                return

            a, b, c, d = st.columns(4)
            a.metric("Current Price", data.get("c"))
            b.metric("Change", data.get("d"))
            c.metric("Change %", data.get("dp"))
            d.metric("Previous Close", data.get("pc"))

            st.caption("Data from Finnhub. Market data may be delayed.")
        except Exception as e:
            st.error(str(e))

    st.info("This page provides market information, not personalized investment advice.")


# ============================================================
# 16. CHAT WORKSPACE
# ============================================================

def chat_page():
    st.markdown("""
    <div class="ng-hero">
      <div class="ng-eyebrow">YOUR AI ASSISTANT</div>
      <h1>Let's create something.</h1>
      <p>Ask questions, brainstorm, learn, write and explore ideas.</p>
    </div>
    """, unsafe_allow_html=True)

    model = st.selectbox(
        "Choose AI",
        ["Auto", "Grok", "Gemini"],
        key="main_chat_model"
    )

    if st.session_state.chat_id is None:
        if st.button("＋ Start New Chat"):
            st.session_state.chat_id = create_chat()
            st.session_state.messages = []
            st.rerun()

    for item in st.session_state.messages:
        with st.chat_message(item["role"]):
            st.markdown(item["content"])

    attachment = st.file_uploader(
        "＋ Attach a TXT, MD or PDF file",
        type=["txt", "md", "pdf"],
        key="chat_file"
    )

    prompt = st.chat_input("Message NEXTGEN AI...")

    if prompt:
        extra = ""

        if attachment:
            if attachment.name.lower().endswith(".pdf"):
                if PdfReader is None:
                    st.error("Install pypdf to read PDFs.")
                    return
                reader = PdfReader(attachment)
                extra = "\n".join(
                    page.extract_text() or "" for page in reader.pages
                )[:14000]
            else:
                extra = attachment.getvalue().decode(
                    "utf-8", errors="ignore"
                )[:14000]

        user_content = prompt
        if extra:
            user_content += "\n\nATTACHED FILE CONTENT:\n" + extra

        if st.session_state.chat_id is None:
            st.session_state.chat_id = create_chat(prompt[:55])

        st.session_state.messages.append({
            "role": "user",
            "content": user_content
        })

        save_message(
            st.session_state.chat_id, "user", user_content
        )

        with st.chat_message("user"):
            st.markdown(prompt)
            if attachment:
                st.caption("Attached: " + attachment.name)

        with st.chat_message("assistant"):
            with st.spinner("Thinking..."):
                try:
                    messages = [
                        {"role": "system", "content": OWNER_RULES}
                    ] + st.session_state.messages[-18:]

                    if should_search(prompt):
                        try:
                            web_context = tavily_search(prompt)
                            messages.append({
                                "role": "system",
                                "content": (
                                    "Fresh web search results. "
                                    "Use them for current claims and include "
                                    "the supplied source URLs in your answer:\n"
                                    + web_context
                                )
                            })
                        except Exception as search_error:
                            messages.append({
                                "role": "system",
                                "content": "Web search unavailable: "
                                + str(search_error)
                            })

                    answer, provider = generate_ai(messages, model)
                    st.markdown(answer)
                    st.caption("Powered by " + provider)

                    st.session_state.messages.append({
                        "role": "assistant",
                        "content": answer
                    })

                    save_message(
                        st.session_state.chat_id,
                        "assistant",
                        answer
                    )

                except Exception as e:
                    st.error(str(e))


# ============================================================
# 17. CREATION LIBRARY
# ============================================================

def creations_page():
    st.title("🗂️ My Creations")
    st.caption("Your saved AI-generated results.")

    con = db()
    rows = con.execute(
        """SELECT tool_name,prompt,result,created_at
        FROM ng3_creations
        WHERE user_key=?
        ORDER BY id DESC LIMIT 60""",
        (user_key(),)
    ).fetchall()
    con.close()

    if not rows:
        st.info("Your creations will appear here.")
        return

    for index, (tool, prompt, result, created) in enumerate(rows):
        with st.expander(f"✨ {tool} — {created[:16]}"):
            st.caption(prompt)
            st.markdown(result)
            st.download_button(
                "Download",
                result,
                file_name=f"creation_{index+1}.txt",
                key=f"creation_download_{index}"
            )


# ============================================================
# 18. DASHBOARD COMPONENTS
# ============================================================

def dashboard():
    st.markdown(f"""
    <div class="ng-hero">
      <div class="ng-eyebrow">WELCOME TO YOUR AI UNIVERSE</div>
      <h1>Think bigger.<br>Build with AI.</h1>
      <p>
        Meet your creative workspace. Write, learn, research,
        build and explore — powered by AI.
      </p>
      <span class="ng-pill">NEXTGEN AI • VERSION {APP_VERSION}</span>
    </div>
    """, unsafe_allow_html=True)

    # Stats
    a, b, c, d = st.columns(4)
    a.metric("AI TOOLS", f"{TOOL_COUNT}+")
    b.metric("AI PROVIDERS", "2")
    c.metric("WORKSPACE", "All-in-One")
    d.metric("ACCOUNT", "Guest" if st.session_state.guest else "Member")

    st.markdown("## ✨ Your Workspace")
    st.caption("Everything you need, organized in one place.")

    sections = [
        ("💬", "AI Chat", "Meet your AI assistant", "Chat, ask and explore."),
        ("✍️", "Writing Studio", "Words that work", "Emails, letters, essays and more."),
        ("🎓", "Study Center", "Learn smarter", "Notes, quizzes and explanations."),
        ("🎨", "Image Studio", "Create visual ideas", "Detailed prompts for image models."),
        ("📄", "PDF Assistant", "Understand documents", "Summaries, questions and notes."),
        ("🔎", "Web Research", "Explore information", "Search the web and review sources."),
        ("💻", "Developer Center", "Build with AI", "Code, explain and debug."),
        ("⚡", "Productivity", "Get organized", "Plans, ideas and useful drafts.")
    ]

    for start in range(0, len(sections), 4):
        cols = st.columns(4)
        for col, item in zip(cols, sections[start:start+4]):
            with col:
                st.markdown(f"""
                <div class="ng-panel">
                  <div class="ng-icon">{item[0]}</div>
                  <h3>{item[1]}</h3>
                  <p><b>{item[2]}</b><br>{item[3]}</p>
                </div>
                """, unsafe_allow_html=True)

                if st.button(
                    "Open Workspace →",
                    key="open_" + item[1],
                    use_container_width=True
                ):
                    mapping = {
                        "AI Chat": "AI Chat",
                        "Writing Studio": "Writing Studio",
                        "Study Center": "Study Center",
                        "Image Studio": "Image Studio",
                        "PDF Assistant": "PDF Assistant",
                        "Web Research": "Web Research",
                        "Developer Center": "Developer Center",
                        "Productivity": "Productivity"
                    }
                    st.session_state.page = mapping[item[1]]
                    st.rerun()

    st.markdown('<div class="ng-divider"></div>', unsafe_allow_html=True)
    st.markdown("## 🚀 Quick Launch")

    q1, q2, q3, q4 = st.columns(4)

    with q1:
        if st.button("✉️ Write an Email", use_container_width=True):
            st.session_state.page = "Writing Studio"
            st.rerun()

    with q2:
        if st.button("📝 Make Study Notes", use_container_width=True):
            st.session_state.page = "Study Center"
            st.rerun()

    with q3:
        if st.button("💻 Generate Code", use_container_width=True):
            st.session_state.page = "Developer Center"
            st.rerun()

    with q4:
        if st.button("🔎 Research Topic", use_container_width=True):
            st.session_state.page = "Web Research"
            st.rerun()

    st.markdown('<div class="ng-divider"></div>', unsafe_allow_html=True)

    st.markdown("## 🌟 Meet the Creator")

    st.markdown(f"""
    <div class="ng-feature">
      <div class="ng-eyebrow">BUILT WITH A VISION</div>
      <h2>{OWNER_NAME}</h2>
      <p>{OWNER_PUBLIC_BIO}</p>
      <span class="ng-pill">CREATOR OF NEXTGEN AI</span>
    </div>
    """, unsafe_allow_html=True)


# ============================================================
# 19. SETTINGS
# ============================================================

def settings_page():
    st.title("⚙️ Settings")
    st.caption("Manage your workspace and check provider connections.")

    st.markdown("### AI Provider Status")

    providers = [
        ("xAI Grok", bool(XAI_API_KEY)),
        ("Google Gemini", bool(GEMINI_API_KEY)),
        ("Tavily Search", bool(TAVILY_API_KEY)),
        ("Finnhub Market Data", bool(FINNHUB_API_KEY))
    ]

    for name, connected in providers:
        icon = "🟢" if connected else "⚪"
        status = "Configured" if connected else "Not configured"
        st.write(f"{icon} **{name}** — {status}")

    st.divider()

    st.markdown("### Model Configuration")
    st.write("xAI model:", XAI_MODEL)
    st.write("Gemini model:", GEMINI_MODEL)

    st.divider()

    st.markdown("### Public Creator Profile")
    st.write("Creator:", OWNER_NAME)
    st.write(OWNER_PUBLIC_BIO)

    st.info(
        "API keys are read from Streamlit Cloud Secrets. "
        "Never put private API keys in public source code."
    )

    st.divider()
    st.markdown("### Storage")
    st.warning(
        "This version uses SQLite. Streamlit Cloud's local filesystem "
        "may reset during redeployment or app restarts. Use a persistent "
        "database for important production data."
    )


# ============================================================
# 20. ABOUT PAGE
# ============================================================

def about_page():
    st.markdown("""
    <div class="ng-hero">
      <div class="ng-eyebrow">ABOUT THE PLATFORM</div>
      <h1>One Platform.<br>Endless Possibilities.</h1>
      <p>NEXTGEN AI brings useful AI workflows into one workspace.</p>
    </div>
    """, unsafe_allow_html=True)

    st.markdown("### What you can do")
    st.markdown("""
    - Chat with configured AI models.
    - Draft emails, letters, essays and messages.
    - Generate study notes, quizzes and explanations.
    - Create code and understand programming concepts.
    - Research topics using web search.
    - Summarize PDF documents.
    - Create image-generation prompts.
    - Explore stock quote information.
    """)

    st.markdown("### Platform Creator")
    st.markdown(f"**{OWNER_NAME}**")
    st.write(OWNER_PUBLIC_BIO)

    st.caption("NEXTGEN AI • Version " + APP_VERSION)


# ============================================================
# 21. SIDEBAR NAVIGATION
# ============================================================

NAVIGATION = [
    ("🏠", "Dashboard"),
    ("💬", "AI Chat"),
    ("🧰", "AI Tool Center"),
    ("✍️", "Writing Studio"),
    ("🎓", "Study Center"),
    ("🎨", "Image Studio"),
    ("📄", "PDF Assistant"),
    ("🔎", "Web Research"),
    ("💻", "Developer Center"),
    ("⚡", "Productivity"),
    ("📈", "Stock Dashboard"),
    ("🗂️", "My Creations"),
    ("⚙️", "Settings"),
    ("ℹ️", "About")
]

with st.sidebar:
    st.markdown('<div class="ng-brand">✦ NEXTGEN AI</div>', unsafe_allow_html=True)
    st.caption("YOUR INTELLIGENT WORKSPACE")
    st.markdown('<span class="ng-pill">VERSION 3.0</span>', unsafe_allow_html=True)

    st.markdown("---")
    st.markdown("#### WORKSPACE")

    for icon, label in NAVIGATION:
        if st.button(
            f"{icon}  {label}",
            key="nav_" + label,
            use_container_width=True
        ):
            st.session_state.page = label
            st.rerun()

    st.markdown("---")
    st.markdown("#### RECENT CHATS")

    if st.button("＋ New Conversation", use_container_width=True):
        st.session_state.chat_id = create_chat()
        st.session_state.messages = []
        st.session_state.page = "AI Chat"
        st.rerun()

    for cid, title, created in list_chats()[:8]:
        left, right = st.columns([5, 1])

        with left:
            if st.button(
                "💬 " + title[:22],
                key=f"history_{cid}",
                use_container_width=True
            ):
                st.session_state.chat_id = cid
                st.session_state.messages = read_messages(cid)
                st.session_state.page = "AI Chat"
                st.rerun()

        with right:
            if st.button("⋯", key=f"manage_{cid}"):
                st.session_state["manage_chat_id"] = cid

    if st.session_state.get("manage_chat_id"):
        cid = st.session_state.manage_chat_id
        with st.expander("Manage conversation", expanded=True):
            title = st.text_input("New title", key=f"title_{cid}")

            if st.button("Rename", key=f"rename_{cid}"):
                if title.strip():
                    rename_chat(cid, title.strip())
                st.session_state.manage_chat_id = None
                st.rerun()

            if st.button("Delete chat", key=f"delete_{cid}"):
                remove_chat(cid)
                if st.session_state.chat_id == cid:
                    st.session_state.chat_id = None
                    st.session_state.messages = []
                st.session_state.manage_chat_id = None
                st.rerun()

    st.markdown("---")
    st.caption("SIGNED IN AS")
    st.markdown("**" + str(st.session_state.username) + "**")

    if st.button("Sign Out", use_container_width=True):
        for key in [
            "user_key", "username", "guest",
            "chat_id", "messages"
        ]:
            st.session_state[key] = None
        st.session_state.messages = []
        st.rerun()


# ============================================================
# 22. MAIN ROUTER
# ============================================================

page = st.session_state.page

if page == "Dashboard":
    dashboard()

elif page == "AI Chat":
    chat_page()

elif page == "AI Tool Center":
    tool_center()

elif page == "Writing Studio":
    tool_center("✍️ Writing Studio")

elif page == "Study Center":
    tool_center("🎓 Study Center")

elif page == "Image Studio":
    image_prompt_studio()

elif page == "PDF Assistant":
    pdf_assistant()

elif page == "Web Research":
    research_page()

elif page == "Developer Center":
    tool_center("💻 Developer Center")

elif page == "Productivity":
    tool_center("📊 Business & Productivity")

elif page == "Stock Dashboard":
    stock_page()

elif page == "My Creations":
    creations_page()

elif page == "Settings":
    settings_page()

elif page == "About":
    about_page()

else:
    dashboard()


# ============================================================
# 23. FOOTER
# ============================================================

st.markdown("---")
st.markdown(
    """
    <div style="text-align:center;padding:12px 0 4px 0;">
      <div class="ng-brand">✦ NEXTGEN AI</div>
      <div class="ng-small">
        THINK BIGGER • CREATE MORE • BUILD THE FUTURE
      </div>
      <div class="ng-small">© 2026 NEXTGEN AI</div>
    </div>
    """,
    unsafe_allow_html=True
)
