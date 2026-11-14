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
import streamlit as st
import streamlit.components.v1 as components

from datetime import datetime
from dotenv import load_dotenv

load_dotenv()

# ============================================================
# NEXTGEN AI V8
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
The creator of NEXTGEN AI is Arav.
Do not invent private information about the creator.
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

TOOL_COUNT = sum(len(v) for v in TOOL_LIBRARY.values())


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
    "last_user_prompt": ""
}

for key, value in defaults.items():
    if key not in st.session_state:
        st.session_state[key] = value


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
    st.caption("WORKSPACE")

    navigation = [
        ("⌂", "Dashboard"),
        ("✦", "AI Chat"),
        ("▧", "AI Image Studio"),
        ("⌕", "Tool Center"),
        ("▤", "PDF Assistant")
    ]

    for icon_text, name in navigation:
        if st.button(
            f"{icon_text}   {name}",
            key=f"nav_{name}",
            use_container_width=True
        ):
            st.session_state.page = name
            st.rerun()

    st.markdown("---")
    st.caption("YOUR LIBRARY")

    for icon_text, name in [
        ("◷", "Chat History"),
        ("▣", "My Creations"),
        ("⚙", "Settings"),
        ("ⓘ", "About")
    ]:
        if st.button(
            f"{icon_text}   {name}",
            key=f"nav_{name}",
            use_container_width=True
        ):
            st.session_state.page = name
            st.rerun()

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
        '<div class="small-muted">NEXTGEN AI V8<br>'
        'Created by Arav</div>',
        unsafe_allow_html=True
    )


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
        f'{TOOL_COUNT}+ AI tool presets</h2>'
        f'<div class="small-muted">Study, coding, writing, creator workflows and more.</div>'
        f'</div>',
        unsafe_allow_html=True
    )

    a, b, c, d = st.columns(4)

    with a:
        metric("MAIN AI", "GROQ", "Primary assistant")

    with b:
        metric("BACKUP AI", "GEMINI", "Automatic fallback")

    with c:
        metric("EXTRA AI", "OPENAI + CLAUDE", "Additional providers")

    with d:
        metric("AI TOOLBOX", f"{TOOL_COUNT}+", "Working tool presets")

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

    st.markdown("## Built for your workflow")

    st.markdown("""
    - **AI Chat:** Groq, Gemini, OpenAI and Claude fallback.
    - **AI Tool Center:** Task presets for different workflows.
    - **Coding School:** Beginner-friendly coding lessons.
    - **AI Image Studio:** Cloudflare FLUX image generation.
    - **PDF Assistant:** Document question answering.
    - **Chat History:** Saved conversations linked to your account.
    """)


# ============================================================
# AI CHAT
# ============================================================

elif page == "AI Chat":

    st.markdown("## ✦ AI Chat")
    st.caption("Ask anything. Your assistant is ready.")

    for index, (role, content) in enumerate(st.session_state.messages):

        with st.chat_message(role):
            st.markdown(content)

            if role == "assistant":
                safe_text = html.escape(content)

                c1, c2, c3, c4, c5 = st.columns(5)

                with c1:
                    st.download_button(
                        "Copy / Save",
                        data=content,
                        file_name="nextgen_answer.txt",
                        mime="text/plain",
                        key=f"copy_{index}"
                    )

                with c2:
                    if st.button("Read Aloud", key=f"read_{index}"):
                        components.html(
                            f"""
                            <script>
                            const text = {json.dumps(content)};
                            if ('speechSynthesis' in window) {{
                                window.speechSynthesis.cancel();
                                const msg = new SpeechSynthesisUtterance(text);
                                window.speechSynthesis.speak(msg);
                            }}
                            </script>
                            """,
                            height=0
                        )
                        st.toast("Read Aloud requested.")

                with c3:
                    st.download_button(
                        "Share",
                        data=content,
                        file_name="NEXTGEN_shared_answer.txt",
                        mime="text/plain",
                        key=f"share_{index}"
                    )

                with c4:
                    if st.button("Like", key=f"like_{index}"):
                        st.toast("Thanks for your feedback!")

                with c5:
                    if index == len(st.session_state.messages) - 1:
                        if st.button("Regenerate", key=f"regen_{index}"):
                            st.session_state.regenerate = True
                            st.rerun()

    with st.expander("＋  Add tools and attachments", expanded=False):

        chat_tool = st.selectbox(
            "Choose an optional chat tool",
            [
                "None",
                "Explain simply",
                "Coding Assistant",
                "Study Tutor",
                "Writing Assistant",
                "Creative Assistant",
                "Research Helper"
            ],
            key="chat_plus_tool"
        )

        uploaded_file = st.file_uploader(
            "Attach PDF or text file",
            type=["pdf", "txt"],
            key="chat_attachment"
        )

        audio_file = st.file_uploader(
            "Add voice recording",
            type=["wav", "mp3", "m4a", "ogg"],
            key="chat_voice"
        )

    if st.session_state.get("regenerate"):

        st.session_state.regenerate = False

        previous_user = next(
            (
                content for role, content
                in reversed(st.session_state.messages)
                if role == "user"
            ),
            None
        )

        if previous_user:
            with st.spinner("Regenerating answer..."):
                try:
                    history = [
                        {"role": r, "content": c}
                        for r, c in st.session_state.messages[:-1]
                    ]
                    answer, provider = ask_ai(history)
                    st.session_state.messages.append(("assistant", answer))
                    save_message(
                        st.session_state.chat_id,
                        USER_ID,
                        "assistant",
                        answer
                    )
                    st.session_state.last_provider = provider
                except Exception as exc:
                    st.error(str(exc))

        st.rerun()

    user_prompt = st.chat_input("Message NEXTGEN AI...")

    if user_prompt:

        attachment_text = ""

        if uploaded_file:
            if uploaded_file.name.lower().endswith(".txt"):
                attachment_text = uploaded_file.getvalue().decode(
                    "utf-8", errors="ignore"
                )[:20000]

            elif uploaded_file.name.lower().endswith(".pdf"):
                try:
                    from pypdf import PdfReader
                    reader = PdfReader(
                        io.BytesIO(uploaded_file.getvalue())
                    )
                    attachment_text = "\n".join(
                        p.extract_text() or ""
                        for p in reader.pages
                    )[:25000]
                except Exception as exc:
                    st.error("PDF reading failed: " + str(exc))

        if audio_file:
            try:
                voice_text = transcribe_audio(audio_file)
                user_prompt += "\n\nVoice input: " + voice_text
            except Exception as exc:
                st.warning("Voice transcription failed: " + str(exc))

        if attachment_text:
            user_prompt += "\n\nAttached document:\n" + attachment_text

        if chat_tool != "None":
            user_prompt = (
                "Use this mode: " + chat_tool +
                "\n\nUser request: " + user_prompt
            )

        st.session_state.messages.append(("user", user_prompt))

        save_message(
            st.session_state.chat_id,
            USER_ID,
            "user",
            user_prompt
        )

        if len(st.session_state.messages) == 1:
            set_chat_title(
                st.session_state.chat_id,
                USER_ID,
                user_prompt[:48]
            )

        api_messages = [
            {"role": r, "content": c}
            for r, c in st.session_state.messages[-20:]
        ]

        with st.spinner("NEXTGEN AI is thinking..."):
            try:
                answer, provider = ask_ai(api_messages)

                st.session_state.messages.append(("assistant", answer))

                save_message(
                    st.session_state.chat_id,
                    USER_ID,
                    "assistant",
                    answer
                )

                st.session_state.last_provider = provider

            except Exception as exc:
                st.error(str(exc))

        st.rerun()

    st.caption(
        f"Response engine: {st.session_state.last_provider}"
    )


# ============================================================
# AI IMAGE STUDIO
# ============================================================

elif page == "AI Image Studio":

    hero(
        "AI Image Studio",
        "Bring your imagination to life with Cloudflare FLUX."
    )

    st.markdown("### Describe your image")

    image_mode = st.selectbox(
        "＋ Choose image feature",
        [
            "Text to Image",
            "Cinematic Image",
            "Anime Style Prompt",
            "Logo Concept",
            "Poster Concept",
            "Thumbnail Concept",
            "Fantasy Art",
            "Product Image Concept"
        ]
    )

    prompt = st.text_area(
        "Image prompt",
        placeholder="Describe the image you want to create...",
        height=100,
        key="image_prompt"
    )

    aspect = st.selectbox(
        "Image format",
        ["Square", "Portrait", "Landscape"]
    )

    if st.button("✦ Generate Image", use_container_width=True):

        if not prompt.strip():
            st.warning("Please write an image prompt.")

        else:
            full_prompt = (
                image_mode + ". " + prompt +
                ". Composition: " + aspect + "."
            )

            with st.spinner("Creating your image..."):
                try:
                    result = cloudflare_image(full_prompt)

                    st.image(result, use_container_width=True)

                    st.download_button(
                        "↓ Download Image",
                        data=result,
                        file_name="nextgen_image.png",
                        mime="image/png"
                    )

                except Exception as exc:
                    st.error("Image generation failed: " + str(exc))


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
        f'{TOOL_COUNT}+ AI tools</h2>'
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
                    result, provider = run_tool(tool_name, details)

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
        f"{TOOL_COUNT} working prompt-based tool presets "
        f"across {len(TOOL_LIBRARY)} categories."
    )


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
                    st.caption("Generated by " + provider)

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
        "Settings",
        "Your AI platform configuration."
    )

    st.markdown("### AI Routing")

    st.success(f"Main: Groq — {GROQ_MODEL}")
    st.success(f"Backup: Gemini — {GEMINI_MODEL}")
    st.info(f"Additional: OpenAI — {OPENAI_MODEL}")
    st.info(f"Additional: Claude — {CLAUDE_MODEL}")

    st.markdown("### Provider Key Status")

    for name, key in [
        ("Groq", GROQ_KEY),
        ("Gemini", GEMINI_KEY),
        ("OpenAI", OPENAI_KEY),
        ("Claude", ANTHROPIC_KEY),
        ("Cloudflare", CF_TOKEN)
    ]:
        if key:
            st.success(name + " API key configured.")
        else:
            st.warning(name + " API key not configured.")

    st.markdown("### Image Generation")
    st.info("Cloudflare model: " + IMAGE_MODEL)

    st.markdown("### Account")
    st.write("Username:", st.session_state.user["username"])
    st.write("Account type:", "Guest" if st.session_state.user.get("is_guest", False) else "Registered account")

    st.caption(
        "Manage API credentials in Streamlit Cloud → "
        "Settings → Secrets."
    )


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

    Arav is a student at **Swami Vivekanand Shiksha Niketan**.
    He is interested in artificial intelligence, technology,
    coding and creative problem-solving.

    NEXTGEN AI brings multiple AI-powered capabilities together
    in one workspace.

    ### Platform Features

    - AI Chat Assistant
    - AI Image Studio
    - AI Tool Center
    - Coding School
    - PDF Assistant
    - Chat History
    - Account Login and Sign Up
    - Continue as Guest
    - Automatic sign-in after account creation
    - Multiple AI providers

    ### Technology

    | Technology | Purpose |
    |---|---|
    | Groq | Main AI engine |
    | Gemini | AI fallback |
    | OpenAI | Additional AI provider |
    | Claude | Additional AI provider |
    | Cloudflare | Image generation |
    | Python | Application development |
    | Streamlit | User interface |
    | SQLite | Account and chat storage |

    **One Platform. Endless Possibilities.**
    """)

    st.caption("NEXTGEN AI © 2026 · Created by Arav")
