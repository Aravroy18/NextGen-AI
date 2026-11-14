
import streamlit as st
import sqlite3
import requests
import os
import json
import hashlib
import secrets
import base64
from datetime import datetime
from io import BytesIO
from pypdf import PdfReader

# =========================================================
# NEXTGEN AI V6
# =========================================================

st.set_page_config(
    page_title="NEXTGEN AI",
    page_icon="🚀",
    layout="wide",
    initial_sidebar_state="expanded"
)

# -------------------- CONFIG -----------------------------

APP_NAME = "NEXTGEN AI"
DB_PATH = "nextgen_ai.db"

GROQ_MODEL = "openai/gpt-oss-120b"
GEMINI_MODEL = "gemini-3.5-flash-lite"
IMAGE_MODEL = "@cf/black-forest-labs/flux-1-schnell"

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
CF_ACCOUNT_ID = get_secret("CLOUDFLARE_ACCOUNT_ID")
CF_API_TOKEN = get_secret("CLOUDFLARE_API_TOKEN")
CF_LIVE_URL = get_secret("CLOUDFLARE_VOICE_URL")

# -------------------- DATABASE --------------------------

def db():
    return sqlite3.connect(DB_PATH, check_same_thread=False)

def init_db():
    con = db()
    cur = con.cursor()

    cur.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE,
            password_hash TEXT,
            created_at TEXT
        )
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS conversations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            title TEXT,
            created_at TEXT
        )
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS messages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            conversation_id INTEGER,
            role TEXT,
            content TEXT,
            created_at TEXT
        )
    """)

    con.commit()
    con.close()

init_db()

def hash_password(password, salt=None):
    salt = salt or secrets.token_hex(16)
    digest = hashlib.pbkdf2_hmac(
        "sha256",
        password.encode(),
        salt.encode(),
        150000
    ).hex()
    return salt + "$" + digest

def verify_password(password, saved):
    try:
        salt, digest = saved.split("$", 1)
        return secrets.compare_digest(
            hash_password(password, salt).split("$", 1)[1],
            digest
        )
    except Exception:
        return False

def register_user(username, password):
    con = db()
    try:
        con.execute(
            "INSERT INTO users(username,password_hash,created_at) VALUES(?,?,?)",
            (username, hash_password(password), datetime.now().isoformat())
        )
        con.commit()
        return True
    except sqlite3.IntegrityError:
        return False
    finally:
        con.close()

def login_user(username, password):
    con = db()
    row = con.execute(
        "SELECT id,password_hash FROM users WHERE username=?",
        (username,)
    ).fetchone()
    con.close()

    if row and verify_password(password, row[1]):
        return row[0]
    return None

def create_chat(user_id, title="New Chat"):
    con = db()
    cur = con.cursor()
    cur.execute(
        "INSERT INTO conversations(user_id,title,created_at) VALUES(?,?,?)",
        (user_id, title, datetime.now().isoformat())
    )
    chat_id = cur.lastrowid
    con.commit()
    con.close()
    return chat_id

def get_chats(user_id):
    con = db()
    rows = con.execute(
        "SELECT id,title,created_at FROM conversations WHERE user_id=? ORDER BY id DESC",
        (user_id,)
    ).fetchall()
    con.close()
    return rows

def get_messages(chat_id):
    con = db()
    rows = con.execute(
        "SELECT role,content FROM messages WHERE conversation_id=? ORDER BY id",
        (chat_id,)
    ).fetchall()
    con.close()
    return rows

def save_message(chat_id, role, content):
    con = db()
    con.execute(
        "INSERT INTO messages(conversation_id,role,content,created_at) VALUES(?,?,?,?)",
        (chat_id, role, content, datetime.now().isoformat())
    )
    con.commit()
    con.close()

def rename_chat(chat_id, title):
    con = db()
    con.execute(
        "UPDATE conversations SET title=? WHERE id=?",
        (title[:70], chat_id)
    )
    con.commit()
    con.close()

def delete_chat(chat_id):
    con = db()
    con.execute("DELETE FROM messages WHERE conversation_id=?", (chat_id,))
    con.execute("DELETE FROM conversations WHERE id=?", (chat_id,))
    con.commit()
    con.close()

# -------------------- AI ENGINES ------------------------

def groq_chat(messages):
    if not GROQ_API_KEY:
        raise Exception("GROQ_API_KEY missing")

    response = requests.post(
        "https://api.groq.com/openai/v1/chat/completions",
        headers={
            "Authorization": f"Bearer {GROQ_API_KEY}",
            "Content-Type": "application/json"
        },
        json={
            "model": GROQ_MODEL,
            "messages": messages,
            "temperature": 0.7,
            "max_completion_tokens": 4096
        },
        timeout=90
    )

    response.raise_for_status()
    return response.json()["choices"][0]["message"]["content"]

def gemini_chat(messages):
    if not GEMINI_API_KEY:
        raise Exception("GEMINI_API_KEY missing")

    contents = []
    for item in messages:
        role = "user" if item["role"] == "user" else "model"
        contents.append({
            "role": role,
            "parts": [{"text": item["content"]}]
        })

    response = requests.post(
        f"https://generativelanguage.googleapis.com/v1beta/models/{GEMINI_MODEL}:generateContent?key={GEMINI_API_KEY}",
        json={"contents": contents},
        timeout=90
    )
    response.raise_for_status()
    data = response.json()
    return data["candidates"][0]["content"]["parts"][0]["text"]

def ask_ai(messages):
    try:
        return groq_chat(messages), "Groq"
    except Exception as groq_error:
        try:
            return gemini_chat(messages), "Gemini Backup"
        except Exception as gemini_error:
            return (
                "दोनों AI services अभी जवाब नहीं दे पाईं।\n\n"
                f"Groq: {str(groq_error)[:250]}\n"
                f"Gemini: {str(gemini_error)[:250]}",
                "Unavailable"
            )

# -------------------- WEB SEARCH ------------------------

def web_search(query):
    if not TAVILY_API_KEY:
        return "Web Search के लिए TAVILY_API_KEY configure नहीं है।"

    try:
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
        response.raise_for_status()
        results = response.json().get("results", [])

        if not results:
            return "कोई परिणाम नहीं मिला।"

        return "\n\n".join(
            f"**{item.get('title', 'Result')}**\n"
            f"{item.get('content', '')}\n"
            f"Source: {item.get('url', '')}"
            for item in results
        )
    except Exception as e:
        return f"Search error: {e}"

# -------------------- IMAGE GENERATION ------------------

def generate_image(prompt):
    if not CF_ACCOUNT_ID or not CF_API_TOKEN:
        return None, "Cloudflare credentials configure नहीं हैं।"

    url = (
        f"https://api.cloudflare.com/client/v4/accounts/"
        f"{CF_ACCOUNT_ID}/ai/run/{IMAGE_MODEL}"
    )

    try:
        response = requests.post(
            url,
            headers={"Authorization": f"Bearer {CF_API_TOKEN}"},
            json={"prompt": prompt, "steps": 4},
            timeout=120
        )
        response.raise_for_status()
        data = response.json()

        image_data = data.get("result", {}).get("image")
        if not image_data:
            return None, "Image response में image data नहीं मिला।"

        return base64.b64decode(image_data), None

    except Exception as e:
        return None, str(e)

# -------------------- AUDIO TRANSCRIPTION ---------------

def transcribe_audio(audio_file):
    if not GROQ_API_KEY:
        return None, "Groq API key missing."

    try:
        response = requests.post(
            "https://api.groq.com/openai/v1/audio/transcriptions",
            headers={"Authorization": f"Bearer {GROQ_API_KEY}"},
            files={
                "file": (
                    "recording.wav",
                    audio_file.getvalue(),
                    "audio/wav"
                )
            },
            data={"model": "whisper-large-v3-turbo"},
            timeout=120
        )
        response.raise_for_status()
        return response.json().get("text", ""), None
    except Exception as e:
        return None, str(e)

# -------------------- PDF READER ------------------------

def extract_pdf(file):
    try:
        reader = PdfReader(BytesIO(file.getvalue()))
        return "\n".join(
            page.extract_text() or ""
            for page in reader.pages
        )
    except Exception as e:
        return f"PDF पढ़ने में समस्या: {e}"

# =========================================================
# 200+ PROMPT-BASED AI TOOLS
# =========================================================

TOOL_LIBRARY = {
    "✍️ Writing": [
        "Email Writer", "Professional Letter", "Application Writer",
        "Essay Writer", "Article Writer", "Blog Writer",
        "Story Writer", "Poem Writer", "Speech Writer",
        "Report Writer", "Summary Writer", "Paragraph Writer",
        "Creative Writing", "Notice Writer", "Invitation Writer",
        "Resume Writer", "Cover Letter", "Biography Writer",
        "Debate Writer", "Dialogue Writer", "Review Writer",
        "Introduction Writer", "Conclusion Writer", "Script Writer",
        "Content Rewriter", "Proofreading Assistant"
    ],

    "📚 Study & Education": [
        "Chapter Explainer", "Short Notes Maker", "Long Notes Maker",
        "Question Answer Maker", "MCQ Generator", "Flashcard Maker",
        "Quiz Generator", "Revision Planner", "Study Timetable",
        "Exam Preparation", "Difficult Topic Simplifier",
        "Vocabulary Builder", "Grammar Tutor", "Literature Explainer",
        "History Explainer", "Geography Tutor", "Science Tutor",
        "Maths Tutor", "Physics Explainer", "Chemistry Explainer",
        "Biology Explainer", "Homework Helper", "Concept Comparer",
        "Formula Explainer", "Practice Worksheet", "Memory Techniques"
    ],

    "💻 Developer": [
        "Python Assistant", "HTML Generator", "CSS Generator",
        "JavaScript Assistant", "C++ Assistant", "Java Assistant",
        "SQL Assistant", "Code Explainer", "Code Debugger",
        "Code Optimizer", "Regex Helper", "API Planner",
        "Website Planner", "App Idea Generator", "UI Planner",
        "Database Designer", "Git Helper", "README Writer",
        "Algorithm Explainer", "Pseudocode Writer", "JSON Helper",
        "Python Project Ideas", "Frontend Mentor", "Backend Mentor",
        "Code Documentation", "Programming Roadmap"
    ],

    "🎬 Creator Studio": [
        "YouTube Video Ideas", "YouTube Script Writer",
        "Shorts Script Writer", "Reels Idea Generator",
        "Video Hook Generator", "Thumbnail Text Ideas",
        "Thumbnail Prompt Maker", "Photo Prompt Maker",
        "Video Prompt Maker", "Scene Planner", "Dialogue Writer",
        "Voiceover Script", "Storytelling Assistant",
        "Channel Description", "Video Description",
        "YouTube Title Generator", "Hashtag Generator",
        "Content Calendar", "Character Creator",
        "Animation Story Writer", "Ad Script Writer",
        "Brand Story Writer", "Podcast Script", "Intro Generator",
        "Outro Generator", "Caption Writer"
    ],

    "🏢 Business": [
        "Business Idea Generator", "Business Plan Writer",
        "Brand Name Generator", "Slogan Generator",
        "Product Description", "Marketing Strategy",
        "Advertisement Writer", "Customer Reply Writer",
        "Business Email", "Shop Promotion Script",
        "Product Comparison", "Market Research Planner",
        "Presentation Writer", "Pitch Deck Outline",
        "Customer Feedback Analyzer", "Business SWOT",
        "Pricing Strategy Planner", "Small Business Planner",
        "Brand Identity Planner", "Sales Copy Writer",
        "Campaign Planner", "Business Bio"
    ],

    "🌐 Language": [
        "English Grammar Coach", "Hindi Writing Helper",
        "English Conversation Practice", "Hindi Translator",
        "English Translator", "Vocabulary Practice",
        "Sentence Corrector", "Pronunciation Guide",
        "Synonym Finder", "Antonym Finder",
        "Word Meaning Explainer", "Tense Practice",
        "Active Passive Tutor", "Direct Indirect Tutor",
        "Comprehension Helper", "Letter Format Tutor",
        "Daily English Practice", "Speaking Practice",
        "Language Learning Plan", "Sentence Builder",
        "Punctuation Helper", "Paragraph Improvement"
    ],

    "🧠 Productivity": [
        "Daily Planner", "Weekly Planner", "Goal Planner",
        "Task Organizer", "Time Management Coach",
        "Focus Session Planner", "Habit Tracker Template",
        "Project Planner", "Priority Organizer",
        "Decision Helper", "Meeting Agenda",
        "Meeting Summary", "Checklist Maker",
        "Personal Roadmap", "Routine Builder",
        "Deadline Planner", "Brainstorming Assistant",
        "Problem Solving Coach", "Learning Roadmap",
        "Productivity Tips", "Event Planner", "Travel Planner"
    ],

    "🔬 Research": [
        "Research Topic Ideas", "Research Question Maker",
        "Research Outline", "Fact Explanation",
        "Topic Comparison", "Pros And Cons",
        "Case Study Outline", "Survey Question Maker",
        "Interview Question Maker", "Research Summary",
        "Source Evaluation Guide", "Argument Builder",
        "Critical Thinking Coach", "Timeline Maker",
        "Debate Research Planner", "Data Explanation",
        "Report Outline", "Literature Review Planner",
        "Presentation Research", "Study Reference Organizer"
    ],

    "🎨 Design & Creativity": [
        "Logo Prompt Maker", "Poster Prompt Maker",
        "Banner Prompt Maker", "Wallpaper Prompt Maker",
        "Color Palette Ideas", "Brand Design Planner",
        "UI Design Ideas", "Website Layout Ideas",
        "App Interface Ideas", "Presentation Design",
        "Infographic Content", "Social Post Design",
        "Mascot Character Ideas", "Typography Suggestions",
        "Room Decoration Ideas", "Festival Decoration Ideas",
        "Drawing Ideas", "Art Project Planner",
        "Creative Concept Generator", "Visual Storyboard"
    ],

    "🎯 Career & Skills": [
        "Skill Development Plan", "Career Exploration",
        "Interview Practice", "Communication Coach",
        "Public Speaking Coach", "Leadership Skills",
        "Teamwork Coach", "Problem Solving Practice",
        "Critical Thinking Practice", "Portfolio Planner",
        "Personal Introduction", "Professional Bio",
        "Presentation Practice", "Learning Path Finder",
        "Project Portfolio Ideas", "Study Skills Coach",
        "Career Goal Planner", "Confidence Building Activities",
        "Time Management Practice", "Digital Skills Roadmap"
    ],

    "🧮 Maths & Science": [
        "Maths Concept Explainer", "Algebra Tutor",
        "Geometry Tutor", "Mensuration Tutor",
        "Number System Tutor", "Percentage Tutor",
        "Ratio Proportion Tutor", "Electricity Explainer",
        "Circuit Explainer", "Motion Explainer",
        "Force Explainer", "Light Explainer",
        "Sound Explainer", "Heat Explainer",
        "Chemical Reaction Explainer", "Atom Explainer",
        "Human Body Explainer", "Plant Biology Explainer",
        "Scientific Method Tutor", "Lab Report Planner",
        "Unit Conversion Explainer", "Formula Practice Maker"
    ],

    "📱 Social Media": [
        "Instagram Bio Writer", "Instagram Caption Writer",
        "Instagram Content Ideas", "Facebook Post Writer",
        "WhatsApp Status Writer", "Social Media Calendar",
        "Hashtag Research Ideas", "Engagement Ideas",
        "Community Post Writer", "Announcement Writer",
        "Profile Description", "Short Quote Generator",
        "Festival Post Writer", "Educational Post Writer",
        "Motivational Post Writer", "Social Media Brand Voice",
        "Post Series Planner", "Audience Persona Planner",
        "Content Repurposing", "Creator Growth Planner"
    ],

    "🌍 Everyday Assistant": [
        "General Knowledge Tutor", "Daily Learning Topic",
        "Simple Explanation", "Idea Generator",
        "Conversation Starter", "Gift Idea Generator",
        "Event Invitation", "Travel Checklist",
        "Packing Checklist", "Recipe Idea Planner",
        "Book Recommendation Ideas", "Movie Discussion Questions",
        "Personal Journal Prompts", "Reflection Questions",
        "Daily Motivation", "Decision Comparison",
        "Information Organizer", "Question Generator",
        "Fun Quiz Maker", "Knowledge Challenge"
    ]
}

TOOL_COUNT = sum(len(v) for v in TOOL_LIBRARY.values())

def tool_description(name):
    return (
        f"{name}: यह AI Tool तुम्हारे दिए गए विषय और निर्देश के आधार पर "
        "उपयोगी, व्यवस्थित और स्पष्ट परिणाम तैयार करेगा।"
    )

def run_tool(name, details):
    prompt = f"""
You are NEXTGEN AI's specialized tool: {name}.

Complete the user's task directly.

Instructions:
- Give a useful and accurate result.
- Use headings and bullet points when helpful.
- Match the user's requested language.
- Explain difficult ideas clearly.
- Do not invent facts or claim external actions were completed.
- Ask at most one clarification only when essential.

User's task:
{details}
"""
    return ask_ai([{"role": "user", "content": prompt}])

# =========================================================
# SESSION STATE
# =========================================================

defaults = {
    "user_id": None,
    "username": None,
    "guest": False,
    "page": "Dashboard",
    "active_chat": None,
    "tool_result": None,
    "tool_provider": None,
    "last_image": None,
    "pdf_text": "",
    "chat_input_text": ""
}

for key, value in defaults.items():
    if key not in st.session_state:
        st.session_state[key] = value

# -------------------- LOGIN ------------------------------

def login_screen():
    st.markdown(
        "<div class='hero'><div class='eyebrow'>WELCOME TO YOUR CREATIVE UNIVERSE</div>"
        "<h1>🚀 NEXTGEN AI</h1>"
        "<p>One Platform. Endless Possibilities.</p></div>",
        unsafe_allow_html=True
    )

    login_tab, register_tab = st.tabs(["Login", "Create Account"])

    with login_tab:
        username = st.text_input("Username", key="login_username")
        password = st.text_input("Password", type="password", key="login_password")

        if st.button("Login", use_container_width=True):
            uid = login_user(username.strip(), password)
            if uid:
                st.session_state.user_id = uid
                st.session_state.username = username.strip()
                st.rerun()
            else:
                st.error("Username या password सही नहीं है।")

    with register_tab:
        new_user = st.text_input("Choose Username", key="reg_username")
        new_pass = st.text_input("Choose Password", type="password", key="reg_password")

        if st.button("Create Account", use_container_width=True):
            if len(new_user.strip()) < 3 or len(new_pass) < 6:
                st.warning("Username कम से कम 3 और password कम से कम 6 characters का रखें।")
            elif register_user(new_user.strip(), new_pass):
                st.success("Account बन गया! अब Login करें।")
            else:
                st.error("यह username पहले से मौजूद है।")

    if st.button("Continue as Guest", use_container_width=True):
        st.session_state.guest = True
        st.session_state.username = "Guest"
        st.session_state.user_id = -1
        st.rerun()

# -------------------- STYLING ---------------------------

st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&display=swap');

html, body, [class*="css"] {
    font-family: 'Inter', sans-serif;
}

.stApp {
    background:
      radial-gradient(ellipse at 10% 0%, rgba(90,60,180,.14), transparent 35%),
      #080b16;
    color: #f5f6ff;
}

[data-testid="stSidebar"] {
    background: #0d1221;
    border-right: 1px solid rgba(150,150,255,.13);
}

[data-testid="stSidebar"] * {
    color: #e9eaff;
}

.hero {
    padding: 34px 30px;
    border: 1px solid rgba(145,120,255,.28);
    border-radius: 22px;
    background: linear-gradient(120deg, #171c39, #25164a, #111b35);
    margin-bottom: 24px;
}

.hero h1 {
    font-size: clamp(32px, 5vw, 54px);
    font-weight: 800;
    margin: 8px 0;
    letter-spacing: -2px;
}

.hero p {
    color: #c5c8e8;
    font-size: 17px;
    margin-bottom: 0;
}

.eyebrow {
    color: #b9a6ff;
    font-size: 11px;
    font-weight: 800;
    letter-spacing: 2px;
}

.section-title {
    font-size: 23px;
    font-weight: 750;
    margin: 24px 0 12px;
}

.info-card {
    padding: 19px;
    background: rgba(25,31,55,.82);
    border: 1px solid rgba(150,150,255,.16);
    border-radius: 17px;
    min-height: 125px;
}

.info-card h3 {
    font-size: 17px;
    margin: 0 0 8px;
}

.info-card p {
    color: #b7bdd8;
    font-size: 13px;
    margin: 0;
}

.creator-card {
    background: linear-gradient(135deg,#171d3a,#261a48);
    border: 1px solid rgba(170,140,255,.25);
    border-radius: 20px;
    padding: 25px;
}

.small-muted {
    color: #aeb5d0;
    font-size: 13px;
}

div[data-testid="stChatInput"] {
    border-radius: 18px !important;
}

button[kind="primary"] {
    border-radius: 12px !important;
}

.stButton button {
    border-radius: 12px;
    font-weight: 600;
}

div[data-testid="stExpander"] {
    border: 1px solid rgba(150,150,255,.15);
    border-radius: 14px;
}

[data-testid="stMetric"] {
    background: rgba(25,31,55,.75);
    padding: 15px;
    border: 1px solid rgba(150,150,255,.12);
    border-radius: 14px;
}
</style>
""", unsafe_allow_html=True)

# =========================================================
# APP AUTHENTICATION
# =========================================================

if st.session_state.user_id is None:
    login_screen()
    st.stop()

# =========================================================
# SIDEBAR
# =========================================================

PAGES = [
    "Dashboard",
    "AI Chat",
    "Tool Center",
    "Image Studio",
    "PDF Assistant",
    "Web Search",
    "Creator Profile"
]

with st.sidebar:
    st.markdown("## 🚀 NEXTGEN AI")
    st.caption("Your Creative Universe")
    st.divider()

    st.markdown(f"**Welcome, {st.session_state.username}**")

    for page in PAGES:
        if st.button(
            page,
            key="nav_" + page,
            use_container_width=True,
            type="primary" if st.session_state.page == page else "secondary"
        ):
            st.session_state.page = page
            st.rerun()

    st.divider()
    st.caption(f"✨ {TOOL_COUNT}+ Prompt-based AI Tools")
    st.caption("⚡ Groq + Gemini Backup")
    st.caption("🎨 Cloudflare Image Studio")

    if st.session_state.user_id != -1:
        st.markdown("### Recent Chats")
        for chat in get_chats(st.session_state.user_id)[:8]:
            if st.button(
                "💬 " + (chat[1] or "New Chat")[:27],
                key=f"sidechat_{chat[0]}",
                use_container_width=True
            ):
                st.session_state.active_chat = chat[0]
                st.session_state.page = "AI Chat"
                st.rerun()

    if st.button("＋ New Chat", use_container_width=True):
        if st.session_state.user_id != -1:
            st.session_state.active_chat = create_chat(st.session_state.user_id)
        else:
            st.session_state.active_chat = None
        st.session_state.page = "AI Chat"
        st.rerun()

    st.divider()

    if st.button("Logout", use_container_width=True):
        for key in ["user_id", "username", "guest", "active_chat"]:
            st.session_state[key] = defaults.get(key)
        st.rerun()

# =========================================================
# DASHBOARD
# =========================================================

if st.session_state.page == "Dashboard":

    st.markdown("""
    <div class="hero">
      <div class="eyebrow">WELCOME TO NEXTGEN AI</div>
      <h1>Your Ideas. Your AI. Your Universe. 🚀</h1>
      <p>Chat, create, learn, explore and build something amazing.</p>
    </div>
    """, unsafe_allow_html=True)

    a, b, c, d = st.columns(4)

    a.metric("AI Tools", f"{TOOL_COUNT}+")
    b.metric("AI Engines", "2")
    c.metric("Creative Studio", "Ready")
    d.metric("Your Workspace", "Active")

    st.markdown('<div class="section-title">⚡ Quick Actions</div>', unsafe_allow_html=True)

    cols = st.columns(3)
    quick_actions = [
        ("💬 AI Chat", "Ask questions and explore ideas.", "AI Chat"),
        ("🧰 Tool Center", "Discover specialized AI tools.", "Tool Center"),
        ("🎨 Image Studio", "Create images from your imagination.", "Image Studio"),
        ("📄 PDF Assistant", "Understand your documents.", "PDF Assistant"),
        ("🌐 Web Search", "Explore information from the web.", "Web Search"),
        ("👨‍💻 Creator Profile", "Meet the creator of NEXTGEN AI.", "Creator Profile")
    ]

    for i, (title, desc, page) in enumerate(quick_actions):
        with cols[i % 3]:
            st.markdown(
                f'<div class="info-card"><h3>{title}</h3><p>{desc}</p></div>',
                unsafe_allow_html=True
            )
            if st.button("Open →", key=f"quick_{i}", use_container_width=True):
                st.session_state.page = page
                st.rerun()

    st.markdown('<div class="section-title">🔥 Popular Tools</div>', unsafe_allow_html=True)

    popular = [
        "YouTube Script Writer",
        "Chapter Explainer",
        "Python Assistant",
        "Photo Prompt Maker",
        "Email Writer",
        "Study Timetable"
    ]

    popular_cols = st.columns(3)
    for i, name in enumerate(popular):
        with popular_cols[i % 3]:
            if st.button("✨ " + name, key=f"popular_{i}", use_container_width=True):
                st.session_state.selected_tool = name
                st.session_state.page = "Tool Center"
                st.rerun()

    st.markdown('<div class="section-title">🌟 About NEXTGEN AI</div>', unsafe_allow_html=True)
    st.markdown("""
    <div class="info-card">
      <h3>One Platform. Endless Possibilities.</h3>
      <p>
      NEXTGEN AI is a creative AI workspace designed to help people
      learn, write, code, research and create. New features and improvements
      are being developed continuously.
      </p>
    </div>
    """, unsafe_allow_html=True)

# =========================================================
# AI CHAT
# =========================================================

elif st.session_state.page == "AI Chat":

    st.title("💬 AI Chat")
    st.caption("Talk to NEXTGEN AI. Ask, learn, create and explore.")

    if st.session_state.user_id != -1:
        chats = get_chats(st.session_state.user_id)

        if chats:
            with st.expander("🕘 Full Chat History"):
                for chat in chats:
                    col1, col2 = st.columns([5, 1])
                    with col1:
                        if st.button(
                            "💬 " + (chat[1] or "New Chat"),
                            key=f"history_{chat[0]}",
                            use_container_width=True
                        ):
                            st.session_state.active_chat = chat[0]
                            st.rerun()
                    with col2:
                        if st.button("🗑️", key=f"delete_{chat[0]}"):
                            delete_chat(chat[0])
                            if st.session_state.active_chat == chat[0]:
                                st.session_state.active_chat = None
                            st.rerun()

    if (
        st.session_state.user_id != -1
        and st.session_state.active_chat is None
    ):
        if st.button("＋ Start New Conversation"):
            st.session_state.active_chat = create_chat(
                st.session_state.user_id
            )
            st.rerun()

    chat_id = st.session_state.active_chat

    history = get_messages(chat_id) if chat_id else []

    for role, content in history:
        with st.chat_message(role):
            st.markdown(content)

    # Compact composer: Plus and Mic are native Streamlit controls.
    with st.container(border=True):
        if CF_LIVE_URL:
            st.link_button(
                "◉ Open Live Voice",
                CF_LIVE_URL,
                help="Opens your separately deployed Cloudflare Voice Agent."
            )
        else:
            st.caption("◉ Live Voice: Configure CLOUDFLARE_VOICE_URL in Secrets.")

        submitted = st.chat_input(
            "Message NEXTGEN AI...",
            key="nextgen_chat_input",
            accept_file=True,
            accept_audio=True,
            file_type=["pdf", "txt", "png", "jpg", "jpeg"],
            max_upload_size=20
        )

    if submitted:
        user_text = (submitted.text or "").strip()

        attachments = []
        attachment_context = ""

        for file in (submitted.files or []):
            if file.type == "application/pdf":
                attachment_context += "\n\nPDF CONTENT:\n" + extract_pdf(file)[:15000]
                attachments.append(file.name)
            elif file.type.startswith("text/") or file.name.endswith(".txt"):
                attachment_context += "\n\nFILE CONTENT:\n" + file.getvalue().decode("utf-8", errors="ignore")[:10000]
                attachments.append(file.name)
            else:
                attachments.append(file.name)
                attachment_context += (
                    f"\n\nUser attached {file.name}. "
                    "The file is attached, but this chat version cannot visually inspect it."
                )

        audio_text = ""
        if submitted.audio:
            with st.spinner("🎙️ Transcribing audio..."):
                audio_text, audio_error = transcribe_audio(submitted.audio)
            if audio_error:
                st.warning("Audio transcription: " + audio_error)
            elif audio_text:
                user_text = (user_text + "\n" + audio_text).strip()

        if user_text or attachment_context:
            if not user_text:
                user_text = "Please help me understand the attached file."

            full_text = user_text + attachment_context

            if st.session_state.user_id != -1 and chat_id is None:
                chat_id = create_chat(
                    st.session_state.user_id,
                    user_text[:45] or "New Chat"
                )
                st.session_state.active_chat = chat_id

            if chat_id:
                save_message(chat_id, "user", full_text)

            with st.chat_message("user"):
                st.markdown(user_text)
                if attachments:
                    st.caption("📎 " + ", ".join(attachments))

            previous = [
                {"role": role, "content": content}
                for role, content in history[-16:]
            ]

            previous.append({"role": "user", "content": full_text})

            with st.chat_message("assistant"):
                with st.spinner("NEXTGEN AI is thinking..."):
                    answer, provider = ask_ai(previous)
                st.markdown(answer)
                st.caption("⚡ Powered by " + provider)

            if chat_id:
                save_message(chat_id, "assistant", answer)
                if not history:
                    rename_chat(chat_id, user_text[:45] or "New Chat")

            st.rerun()

# =========================================================
# TOOL CENTER
# =========================================================

elif st.session_state.page == "Tool Center":

    st.title("🧰 AI Tool Center")
    st.caption(
        f"Explore {TOOL_COUNT}+ prompt-based AI tools. "
        "पहले Category चुनें, फिर अपना Tool चुनें।"
    )

    categories = list(TOOL_LIBRARY.keys())

    selected_category = st.selectbox(
        "① Choose a Category",
        categories,
        key="tool_category"
    )

    available_tools = TOOL_LIBRARY[selected_category]

    default_tool = st.session_state.get("selected_tool")
    default_index = (
        available_tools.index(default_tool)
        if default_tool in available_tools else 0
    )

    selected_tool = st.selectbox(
        "② Choose Your AI Tool",
        available_tools,
        index=default_index,
        key="tool_choice"
    )

    st.session_state.selected_tool = selected_tool

    st.markdown(
        f'<div class="info-card"><h3>✨ {selected_tool}</h3>'
        f'<p>{tool_description(selected_tool)}</p></div>',
        unsafe_allow_html=True
    )

    st.markdown("### ③ Tell the AI what you need")

    details = st.text_area(
        "Your Instructions",
        placeholder=f"Write your requirements for {selected_tool}...",
        height=150,
        key="tool_details"
    )

    if st.button("🚀 Run AI Tool", type="primary", use_container_width=True):
        if not details.strip():
            st.warning("पहले अपनी requirements लिखें।")
        else:
            with st.spinner(f"{selected_tool} is working..."):
                result, provider = run_tool(selected_tool, details)

            st.session_state.tool_result = result
            st.session_state.tool_provider = provider

    if st.session_state.tool_result:
        st.divider()
        st.markdown("### ✨ Tool Result")
        st.markdown(st.session_state.tool_result)
        st.caption("Powered by " + str(st.session_state.tool_provider))

        st.download_button(
            "⬇️ Download Result",
            data=st.session_state.tool_result,
            file_name="nextgen_ai_result.txt",
            mime="text/plain"
        )

    st.divider()
    st.markdown("### 🔎 Browse Categories")

    for category, tools_list in TOOL_LIBRARY.items():
        with st.expander(f"{category} — {len(tools_list)} Tools"):
            st.write(" • ".join(tools_list))

# =========================================================
# IMAGE STUDIO
# =========================================================

elif st.session_state.page == "Image Studio":

    st.title("🎨 AI Image Studio")
    st.caption("Turn your imagination into images.")

    prompt = st.text_area(
        "Describe the image you want",
        placeholder="Example: A futuristic city at night, cinematic lighting, ultra detailed...",
        height=130
    )

    with st.expander("＋ Add Reference Image"):
        reference = st.file_uploader(
            "Upload a reference image",
            type=["png", "jpg", "jpeg"]
        )
        if reference:
            st.image(reference, caption="Reference preview", width=250)
            st.info(
                "Reference image preview is available. "
                "Reference-based editing is not enabled in this version."
            )

    if st.button("✨ Generate Image", type="primary", use_container_width=True):
        if not prompt.strip():
            st.warning("पहले image prompt लिखें।")
        else:
            with st.spinner("Creating your image..."):
                image_data, error = generate_image(prompt)

            if error:
                st.error(error)
            elif image_data:
                st.session_state.last_image = image_data
                st.success("Image generated!")

    if st.session_state.last_image:
        st.image(st.session_state.last_image, use_container_width=True)
        st.download_button(
            "⬇️ Download Image",
            data=st.session_state.last_image,
            file_name="nextgen_ai_image.png",
            mime="image/png"
        )

# =========================================================
# PDF ASSISTANT
# =========================================================

elif st.session_state.page == "PDF Assistant":

    st.title("📄 PDF Assistant")
    st.caption("Upload a PDF and ask questions about its contents.")

    pdf_file = st.file_uploader(
        "Upload PDF",
        type=["pdf"]
    )

    if pdf_file:
        if st.button("Read PDF", use_container_width=True):
            with st.spinner("Reading document..."):
                st.session_state.pdf_text = extract_pdf(pdf_file)
            st.success("PDF text extracted.")

    if st.session_state.pdf_text:
        st.text_area(
            "Extracted Text Preview",
            st.session_state.pdf_text[:5000],
            height=180
        )

        question = st.text_input(
            "Ask something about this PDF"
        )

        if st.button("Ask About PDF"):
            if question.strip():
                prompt = (
                    "Answer using the following PDF content. "
                    "If the answer is not present, say so clearly.\n\n"
                    "PDF CONTENT:\n"
                    + st.session_state.pdf_text[:18000]
                    + "\n\nQUESTION:\n"
                    + question
                )
                with st.spinner("Analyzing PDF..."):
                    answer, provider = ask_ai([
                        {"role": "user", "content": prompt}
                    ])
                st.markdown(answer)
                st.caption("Powered by " + provider)

# =========================================================
# WEB SEARCH
# =========================================================

elif st.session_state.page == "Web Search":

    st.title("🌐 Web Search")
    st.caption("Search for information using the configured search service.")

    query = st.text_input(
        "What do you want to search?",
        placeholder="Search a topic..."
    )

    if st.button("🔍 Search Web", type="primary"):
        if query.strip():
            with st.spinner("Searching..."):
                result = web_search(query)
            st.markdown(result)

# =========================================================
# CREATOR PROFILE
# =========================================================

elif st.session_state.page == "Creator Profile":

    st.title("👨‍💻 Meet the Creator")

    st.markdown("""
    <div class="creator-card">
      <div class="eyebrow">THE MIND BEHIND NEXTGEN AI</div>
      <h1 style="font-size:38px;margin:12px 0;">ARAV 🚀</h1>
      <h3>Student Developer | AI Enthusiast | Creator</h3>
      <p style="color:#d0d2eb;line-height:1.8;">
      Hi! I'm Arav, a student developer who loves learning about
      technology, artificial intelligence and creative projects.
      I enjoy experimenting with new ideas and building useful digital
      experiences.
      </p>
    </div>
    """, unsafe_allow_html=True)

    st.markdown("### 🌟 About Arav")

    left, right = st.columns(2)

    with left:
        st.markdown("""
        <div class="info-card">
          <h3>💡 Curious Learner</h3>
          <p>Always exploring new ideas, skills and technologies.</p>
        </div>
        """, unsafe_allow_html=True)

    with right:
        st.markdown("""
        <div class="info-card">
          <h3>💻 Student Developer</h3>
          <p>Learning by building projects and solving problems.</p>
        </div>
        """, unsafe_allow_html=True)

    st.markdown("### 🚀 The NEXTGEN AI Journey")

    st.markdown("""
    <div class="info-card">
      NEXTGEN AI is a project created from curiosity, creativity and
      a passion for technology.

      The goal is to bring AI chat, creative tools, learning assistance
      and productivity features together in one platform.

      The platform is continuously being improved, and new features
      are being developed step by step.
    </div>
    """, unsafe_allow_html=True)

    st.markdown("### 🎯 Creator's Vision")
    st.write(
        "To keep learning, keep building and make technology easier "
        "and more useful for everyone."
    )

    st.caption("NEXTGEN AI © 2026 | Created by Arav")

# =========================================================
# FOOTER
# =========================================================

st.markdown("---")
st.markdown(
    "<div style='text-align:center;color:#858ba8;font-size:12px;'>"
    "🚀 NEXTGEN AI | Your Creative Universe | © 2026"
    "</div>",
    unsafe_allow_html=True
)
