import os
import io
import re
import json
import base64
import sqlite3
import requests
import streamlit as st
import streamlit.components.v1 as components

from datetime import datetime
from urllib.parse import quote

# ============================================================
# NEXTGEN AI — ULTRA EDITION
# ============================================================

st.set_page_config(
    page_title="NEXTGEN AI",
    page_icon="✦",
    layout="wide",
    initial_sidebar_state="expanded"
)

# ---------------- CONFIGURATION ----------------

GROQ_MODEL = "openai/gpt-oss-120b"
GEMINI_MODEL = "gemini-3.5-flash-lite"
IMAGE_MODEL = "@cf/black-forest-labs/flux-1-schnell"

DB_PATH = "nextgen_v5.db"


def get_secret(key, default=""):
    try:
        return st.secrets.get(key, os.getenv(key, default))
    except Exception:
        return os.getenv(key, default)


GROQ_KEY = get_secret("GROQ_API_KEY")
GEMINI_KEY = get_secret("GEMINI_API_KEY")
CF_ACCOUNT = get_secret("CLOUDFLARE_ACCOUNT_ID")
CF_TOKEN = get_secret("CLOUDFLARE_API_TOKEN")
CF_LIVE_URL = get_secret("CLOUDFLARE_VOICE_URL")
FINNHUB_KEY = get_secret("FINNHUB_API_KEY")

SYSTEM_PROMPT = """
You are NEXTGEN AI, an intelligent and helpful AI assistant.
Communicate naturally in Hindi or English according to the user.
Give accurate, clear, useful and well-structured answers.
Never invent facts, sources, API results or completed actions.
Explain difficult concepts in beginner-friendly language.
The creator of NEXTGEN AI is Arav.
Do not invent private information about the creator.
For financial topics, provide educational information and explain risks.
Never present uncertain predictions as guaranteed outcomes.
"""

# ---------------- DATABASE ----------------

def connect_db():
    return sqlite3.connect(DB_PATH, check_same_thread=False)


def init_db():
    con = connect_db()
    cur = con.cursor()

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

    con.commit()
    con.close()


def create_chat():
    con = connect_db()
    cur = con.cursor()
    cur.execute(
        "INSERT INTO v5_chats(title,created) VALUES(?,?)",
        ("New Chat", datetime.now().isoformat())
    )
    chat_id = cur.lastrowid
    con.commit()
    con.close()
    return chat_id


def all_chats():
    con = connect_db()
    rows = con.execute(
        "SELECT id,title,created FROM v5_chats ORDER BY id DESC"
    ).fetchall()
    con.close()
    return rows


def get_messages(chat_id):
    con = connect_db()
    rows = con.execute(
        "SELECT role,content FROM v5_messages WHERE chat_id=? ORDER BY id",
        (chat_id,)
    ).fetchall()
    con.close()
    return rows


def save_message(chat_id, role, content):
    con = connect_db()
    con.execute(
        """INSERT INTO v5_messages(chat_id,role,content,created)
           VALUES(?,?,?,?)""",
        (chat_id, role, content, datetime.now().isoformat())
    )
    con.commit()
    con.close()


def set_chat_title(chat_id, title):
    con = connect_db()
    con.execute(
        "UPDATE v5_chats SET title=? WHERE id=?",
        (title[:48], chat_id)
    )
    con.commit()
    con.close()


def remove_chat(chat_id):
    con = connect_db()
    con.execute("DELETE FROM v5_messages WHERE chat_id=?", (chat_id,))
    con.execute("DELETE FROM v5_chats WHERE id=?", (chat_id,))
    con.commit()
    con.close()


init_db()

# ---------------- AI ENGINES ----------------

def groq_request(messages):
    if not GROQ_KEY:
        raise RuntimeError("GROQ_API_KEY is missing.")

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
        timeout=90
    )

    response.raise_for_status()
    data = response.json()
    answer = data["choices"][0]["message"]["content"]

    if not answer:
        raise RuntimeError("The AI returned an empty answer.")

    return answer


def gemini_request(messages):
    if not GEMINI_KEY:
        raise RuntimeError("GEMINI_API_KEY is missing.")

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
    data = response.json()

    return data["candidates"][0]["content"]["parts"][0]["text"]


def ask_ai(messages):
    errors = []

    try:
        return groq_request(messages), "Groq"
    except Exception as exc:
        errors.append(f"Groq: {str(exc)[:250]}")

    try:
        return gemini_request(messages), "Gemini"
    except Exception as exc:
        errors.append(f"Gemini: {str(exc)[:250]}")

    raise RuntimeError("\n".join(errors))


# ---------------- SMART WEB SEARCH ----------------

def needs_web_search(query):
    prompt = f"""
Decide whether this question requires current internet information.
Return only YES or NO.

Search is useful for:
- Latest news and current affairs
- Current office holders
- Today's weather
- Live or recent market prices
- Current events, schedules and changing facts

Do not search for:
- General knowledge
- Maths calculations
- Writing and creative tasks
- Coding explanations
- Stable educational concepts

Question: {query}
"""

    try:
        result, _ = ask_ai([{"role": "user", "content": prompt}])
        return result.strip().upper().startswith("YES")
    except Exception:
        return False


def web_search(query):
    try:
        from ddgs import DDGS
        results = DDGS().text(query, max_results=5)
        items = []

        for item in results:
            items.append(
                f"Title: {item.get('title', '')}\n"
                f"URL: {item.get('href', '')}\n"
                f"Summary: {item.get('body', '')}"
            )

        return "\n\n".join(items)

    except Exception:
        try:
            from duckduckgo_search import DDGS
            results = DDGS().text(query, max_results=5)
            return "\n\n".join(
                f"{x.get('title', '')}\n{x.get('href', '')}\n{x.get('body', '')}"
                for x in results
            )
        except Exception as exc:
            return f"Search could not be completed: {exc}"


def smart_answer(messages):
    latest = messages[-1]["content"]

    if needs_web_search(latest):
        search_results = web_search(latest)

        if search_results and "could not be completed" not in search_results:
            prompt = (
                "Answer the user's question using the following web results. "
                "Clearly distinguish sourced facts from uncertainty. "
                "Do not invent information.\n\n"
                f"WEB RESULTS:\n{search_results}\n\n"
                f"USER QUESTION:\n{latest}"
            )

            return ask_ai([{"role": "user", "content": prompt}])

    return ask_ai(messages)


# ---------------- CLOUDFLARE IMAGE GENERATION ----------------

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
        timeout=180
    )

    response.raise_for_status()
    data = response.json()
    image_data = data.get("result", {}).get("image")

    if not image_data:
        raise RuntimeError(str(data))

    return base64.b64decode(image_data)


# ---------------- AUDIO TRANSCRIPTION ----------------

def transcribe_audio(audio_file):
    if not GROQ_KEY:
        raise RuntimeError("Groq key is missing.")

    response = requests.post(
        "https://api.groq.com/openai/v1/audio/transcriptions",
        headers={"Authorization": f"Bearer {GROQ_KEY}"},
        files={
            "file": (
                "recording.wav",
                audio_file.getvalue(),
                "audio/wav"
            )
        },
        data={"model": "whisper-large-v3-turbo"},
        timeout=90
    )

    response.raise_for_status()
    return response.json().get("text", "")


# ---------------- STOCK MARKET ----------------

def get_stock_quote(symbol):
    if not FINNHUB_KEY:
        raise RuntimeError("Add FINNHUB_API_KEY to your secrets.")

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

    if not data or data.get("c") is None:
        raise RuntimeError("No quote data returned.")

    return data


# ---------------- TOOL LIBRARY ----------------

TOOL_LIBRARY = {
    "Study & Education": [
        "Topic Explainer", "Explain Like I'm 12", "Short Notes Maker",
        "Detailed Notes Maker", "Chapter Summary", "MCQ Generator",
        "Quiz Generator", "Flashcard Creator", "Worksheet Maker",
        "Study Timetable", "Study Planner", "Maths Step Solver",
        "Science Explainer", "Physics Numericals Coach",
        "Chemistry Helper", "Biology Explainer", "History Notes",
        "Geography Explainer", "Civics Explainer", "Grammar Tutor",
        "Vocabulary Builder", "Word Meaning Helper",
        "Question Answer Maker", "Exam Revision Sheet",
        "Practice Test Maker", "Foundation Question Generator",
        "Doubt Solver", "Textbook Answer Helper",
        "Reading Comprehension Maker", "Spelling Practice"
    ],
    "Writing & Documents": [
        "Email Writer", "Formal Letter Writer", "Essay Writer",
        "Application Writer", "Notice Writer", "Speech Writer",
        "Story Writer", "Article Writer", "Report Writer",
        "Resume Builder", "Cover Letter Writer", "Blog Post Writer",
        "Social Media Caption", "Advertisement Copy",
        "Product Description", "Complaint Letter", "Apology Letter",
        "Press Release", "Newsletter Writer", "Meeting Agenda",
        "Project Documentation", "Biography Writer", "Debate Speech"
    ],
    "Coding & Development": [
        "Python Code Helper", "HTML Generator", "CSS Designer",
        "JavaScript Helper", "Code Explainer", "Code Debugger",
        "SQL Query Writer", "API Guide", "JSON Helper", "Regex Helper",
        "Git Command Helper", "Website Planner", "App Idea Generator",
        "Streamlit App Helper", "React Helper", "Flask Helper",
        "Django Helper", "Python Script Writer", "Code Converter",
        "Code Reviewer", "Algorithm Explainer", "Database Planner",
        "README Writer", "Unit Test Generator", "Error Explainer",
        "Frontend UI Planner", "Backend Architecture Helper"
    ],
    "YouTube & Creator Studio": [
        "YouTube Video Ideas", "YouTube Shorts Ideas", "Reel Ideas",
        "Video Script Writer", "Shorts Script Writer",
        "Thumbnail Concept", "Thumbnail Text Ideas",
        "Image Prompt Generator", "AI Video Prompt Generator",
        "Scene-by-Scene Planner", "Voiceover Script",
        "Character Creator", "Story Plot Generator", "Hook Generator",
        "Video Title Generator", "Hashtag Generator",
        "Channel Bio Writer", "Content Calendar",
        "Video Description SEO", "Pinned Comment Writer",
        "Faceless Video Planner", "Cinematic Video Script",
        "Animal Story Generator", "Character Dialogue Writer",
        "Camera Prompt Writer", "Video Editing Instructions"
    ],
    "Business & Marketing": [
        "Business Idea Generator", "Business Plan Writer",
        "Brand Name Maker", "Slogan Generator", "Marketing Strategy",
        "Marketing Calendar", "Customer Reply Writer",
        "Product Launch Planner", "Sales Pitch Writer",
        "Competitor Analysis Framework", "Target Audience Planner",
        "Customer Persona Builder", "Store Promotion Script",
        "Poster Copy Writer", "Flyer Content Writer",
        "Small Business Checklist", "Shop Advertisement Script",
        "Business WhatsApp Status", "Product Advertisement",
        "Small Shop Branding Assistant", "Business Growth Ideas"
    ],
    "Language & Translation": [
        "Hindi to English", "English to Hindi", "English Simplifier",
        "Hindi Proofreader", "English Proofreader", "Grammar Correction",
        "Text Rewriter", "Text Summarizer", "Vocabulary Practice",
        "Sentence Improver", "Bilingual Explanation",
        "English Speaking Practice", "Daily English Vocabulary",
        "English Conversation Coach", "Tense Practice Generator",
        "Active Passive Voice Tutor", "Pronunciation Practice",
        "Reading Fluency Practice", "English Error Finder"
    ],
    "Productivity": [
        "Daily Planner", "Weekly Planner", "Monthly Goal Planner",
        "To-Do List Maker", "Checklist Generator", "Decision Helper",
        "Brainstorming Assistant", "Goal Breakdown", "Routine Planner",
        "Habit Tracker Template", "Time Management Plan",
        "Project Planner", "Task Prioritizer", "Event Planner",
        "Revision Schedule", "Milestone Planner", "Focus Planner"
    ],
    "Creative & Design": [
        "Logo Concept Generator", "Poster Design Brief",
        "Rangoli Design Ideas", "Greeting Card Message",
        "Color Palette Suggestions", "Presentation Design Ideas",
        "Infographic Outline", "Mascot Character Concept",
        "Brand Identity Brief", "Photo Editing Prompt",
        "AI Art Style Prompt", "Storyboard Creator",
        "Festival Poster Concept", "Thumbnail Improvement Planner"
    ],
    "Research & Analysis": [
        "Research Topic Planner", "Research Question Generator",
        "Argument Builder", "Critical Thinking Coach",
        "Fact Check Checklist", "Source Evaluation Helper",
        "Compare Two Topics", "Problem Analysis", "Root Cause Analysis",
        "Decision Matrix", "Debate Preparation", "Case Study Explainer",
        "Data Explanation", "Table Summarizer", "Chart Recommendation"
    ],
    "Maths & Science": [
        "Algebra Practice Generator", "Geometry Problem Generator",
        "Mensuration Helper", "Percentage Calculator Explainer",
        "Ratio Proportion Tutor", "Speed Distance Time Solver",
        "Unit Conversion Explainer", "Electricity Concept Tutor",
        "Ohms Law Practice", "Motion Concept Explainer",
        "Force and Pressure Tutor", "Chemistry Equation Explainer",
        "Periodic Table Tutor", "Human Body Learning Guide",
        "Light and Sound Explainer", "Heat and Temperature Tutor"
    ],
    "Presentation & Office": [
        "PowerPoint Outline Maker", "Slide Content Writer",
        "Presentation Opening Script", "Presentation Closing Script",
        "Speaker Notes Generator", "Meeting Summary Writer",
        "Office Memo Writer", "Document Formatter",
        "Project Status Report", "Work Report Writer",
        "Training Material Planner", "Instruction Manual Writer"
    ]
}

TOOL_COUNT = sum(len(items) for items in TOOL_LIBRARY.values())


def run_tool(tool_name, details):
    prompt = f"""
You are running the NEXTGEN AI tool: {tool_name}.

Complete the user's task. Do not merely explain how to do it.
Use the user's language.
Use clear formatting and useful examples.
Ask a question only if an essential detail is missing.

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
    "pdf_text": "",
    "last_image": None,
    "liked": set(),
    "disliked": set()
}

for key, value in defaults.items():
    if key not in st.session_state:
        st.session_state[key] = value

if st.session_state.chat_id is None:
    st.session_state.chat_id = create_chat()

if not st.session_state.messages:
    st.session_state.messages = get_messages(st.session_state.chat_id)


# ---------------- DESIGN SYSTEM ----------------

st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800;900&display=swap');

html, body, [class*="css"] {
    font-family: Inter, sans-serif;
}

.stApp {
    background:
        radial-gradient(ellipse at 10% 0%, #30245f 0%, transparent 36%),
        radial-gradient(ellipse at 95% 4%, #163d61 0%, transparent 35%),
        linear-gradient(135deg, #080c18, #0b1020 55%, #090d19);
    color: #f6f6ff;
}

.block-container {
    max-width: 1500px;
    padding-top: 1.3rem;
    padding-bottom: 5rem;
}

[data-testid="stSidebar"] {
    background: linear-gradient(180deg, #111a30, #090f1e);
    border-right: 1px solid #303d60;
}

[data-testid="stSidebar"] button {
    border-radius: 12px;
    border: 1px solid transparent;
    background: transparent;
    color: #e0e7ff;
    text-align: left;
    min-height: 40px;
}

[data-testid="stSidebar"] button:hover {
    background: #242e4c;
    border-color: #59658e;
}

.brand {
    font-size: 29px;
    font-weight: 900;
    letter-spacing: -1.4px;
    padding: 8px 0 2px;
}

.brand span {
    color: #a99bff;
}

.sidebar-tag {
    color: #8999bd;
    font-size: 10px;
    letter-spacing: 2.4px;
    margin-bottom: 20px;
}

.hero {
    position: relative;
    overflow: hidden;
    border: 1px solid #5a5793;
    background: linear-gradient(115deg, #171e3e, #35265f 55%, #174263);
    border-radius: 27px;
    padding: 38px;
    margin-bottom: 25px;
    box-shadow: 0 18px 55px #0006;
}

.hero:after {
    content: "✦";
    position: absolute;
    right: 55px;
    top: 18px;
    font-size: 115px;
    color: #ffffff12;
}

.hero-label {
    color: #c9beff;
    font-size: 11px;
    font-weight: 800;
    letter-spacing: 3px;
}

.hero-title {
    font-size: clamp(34px, 5vw, 57px);
    font-weight: 900;
    line-height: 1.08;
    margin: 14px 0;
    color: white;
}

.hero-sub {
    color: #c5cce5;
    font-size: 14px;
    max-width: 850px;
    line-height: 1.7;
}

.section-kicker {
    color: #bcb1ff;
    font-size: 10px;
    font-weight: 800;
    letter-spacing: 2px;
}

.panel {
    border: 1px solid #354365;
    border-radius: 19px;
    padding: 21px;
    background: linear-gradient(145deg, #192540, #10182b);
    min-height: 145px;
    margin-bottom: 13px;
    box-shadow: 0 8px 24px #0002;
}

.panel-icon {
    font-size: 28px;
    margin-bottom: 10px;
}

.panel-title {
    font-size: 17px;
    font-weight: 800;
    color: white;
}

.panel-desc {
    font-size: 12px;
    color: #aebbd8;
    margin-top: 8px;
    line-height: 1.6;
}

.metric {
    border: 1px solid #364365;
    background: linear-gradient(145deg, #1b2945, #111a2c);
    padding: 18px;
    border-radius: 16px;
    min-height: 105px;
}

.metric-label {
    font-size: 11px;
    color: #aebbd8;
}

.metric-value {
    font-size: 25px;
    font-weight: 900;
    margin: 7px 0;
}

.metric-note {
    font-size: 11px;
    color: #a4b0cd;
}

.dash-feature {
    border: 1px solid #39496d;
    border-radius: 18px;
    padding: 20px;
    background: linear-gradient(135deg, #192844, #121a30);
    margin-bottom: 12px;
    min-height: 110px;
}

.dash-feature h3 {
    font-size: 17px;
    margin: 5px 0 7px;
    color: white;
}

.dash-feature p {
    font-size: 12px;
    color: #aebbd7;
    margin: 0;
    line-height: 1.5;
}

.dash-kicker {
    font-size: 10px;
    letter-spacing: 2px;
    color: #bcb2ff;
    font-weight: 800;
}

div.stButton > button,
div.stDownloadButton > button {
    border-radius: 12px;
    border: 1px solid #49577e;
    background: linear-gradient(120deg, #252f50, #382b66);
    color: white;
    font-weight: 700;
    min-height: 40px;
}

div.stButton > button:hover,
div.stDownloadButton > button:hover {
    border-color: #b0a5ff;
    color: white;
}

div[data-testid="stChatMessage"] {
    background: #141e32;
    border: 1px solid #2d3b5c;
    border-radius: 17px;
    padding: 14px;
    margin-bottom: 13px;
}

[data-testid="stChatInput"] {
    border: 1px solid #59658a !important;
    border-radius: 25px !important;
    background: #111a2c !important;
    box-shadow: 0 5px 25px #0005;
}

[data-testid="stChatInput"] textarea {
    color: white !important;
    font-size: 14px !important;
}

[data-testid="stChatInput"] button {
    border-radius: 50% !important;
}

div[data-testid="stFileUploader"] {
    border: 1px dashed #59658a;
    border-radius: 14px;
    background: #121b30;
    padding: 9px;
}

div[data-testid="stTextInput"] input,
div[data-testid="stTextArea"] textarea {
    background: #111a2d;
    color: white;
    border: 1px solid #3b496a;
    border-radius: 12px;
}

hr {
    border-color: #2b3854;
}

footer, #MainMenu {
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
        <div class="metric-note">{note}</div>
    </div>
    """, unsafe_allow_html=True)


def panel(icon, title, description):
    st.markdown(f"""
    <div class="panel">
        <div class="panel-icon">{icon}</div>
        <div class="panel-title">{title}</div>
        <div class="panel-desc">{description}</div>
    </div>
    """, unsafe_allow_html=True)


def open_page(page):
    st.session_state.page = page
    st.rerun()


def speak_text(text):
    safe_text = json.dumps(text, ensure_ascii=False)
    components.html(
        f"""
        <script>
        const text = {safe_text};
        if ("speechSynthesis" in window) {{
            window.speechSynthesis.cancel();
            const utterance = new SpeechSynthesisUtterance(text);
            utterance.lang = /[\\u0900-\\u097F]/.test(text) ? "hi-IN" : "en-US";
            utterance.rate = 0.96;
            utterance.pitch = 1.0;
            window.speechSynthesis.speak(utterance);
        }}
        </script>
        """,
        height=0
    )


def render_message_actions(index, content):
    st.caption("RESPONSE ACTIONS")

    c1, c2, c3, c4, c5, c6 = st.columns(6)

    with c1:
        st.button(
            "📋 Copy",
            key=f"copy_{index}",
            help="Select and copy the response"
        )

    with c2:
        if st.button("🔊 Read", key=f"read_{index}"):
            speak_text(content)
            st.toast("Read aloud requested.")

    with c3:
        if st.button("👍 Like", key=f"like_{index}"):
            st.session_state.liked.add(index)
            st.toast("Feedback saved for this session.")

    with c4:
        if st.button("👎 Dislike", key=f"dislike_{index}"):
            st.session_state.disliked.add(index)
            st.toast("Feedback saved for this session.")

    with c5:
        if st.button("↻ Regenerate", key=f"regen_{index}"):
            history = [
                {"role": r, "content": t}
                for r, t in st.session_state.messages[:index]
            ]
            if history:
                with st.spinner("Generating another answer..."):
                    try:
                        answer, provider = smart_answer(history)
                        st.session_state.messages.append(("assistant", answer))
                        save_message(
                            st.session_state.chat_id,
                            "assistant",
                            answer
                        )
                        st.session_state.last_provider = provider
                        st.rerun()
                    except Exception as exc:
                        st.error(str(exc))

    with c6:
        st.download_button(
            "↗ Share",
            data=content,
            file_name="nextgen_response.txt",
            mime="text/plain",
            key=f"share_{index}"
        )


# ============================================================
# SIDEBAR
# ============================================================

with st.sidebar:
    st.markdown(
        '<div class="brand">✦ NEXTGEN<span> AI</span></div>',
        unsafe_allow_html=True
    )

    st.markdown(
        '<div class="sidebar-tag">YOUR CREATIVE UNIVERSE</div>',
        unsafe_allow_html=True
    )

    if st.button("＋   New Chat", use_container_width=True):
        st.session_state.chat_id = create_chat()
        st.session_state.messages = []
        st.session_state.page = "AI Chat"
        st.rerun()

    st.markdown("---")
    st.caption("DISCOVER")

    navigation = [
        ("⌂", "Dashboard"),
        ("✦", "AI Chat"),
        ("▧", "AI Image Studio"),
        ("⌕", "Tool Center"),
        ("▤", "PDF Assistant"),
        ("◈", "Build Studio"),
        ("▥", "Market Hub"),
        ("◎", "English Academy")
    ]

    for icon, name in navigation:
        if st.button(
            f"{icon}   {name}",
            key=f"nav_{name}",
            use_container_width=True
        ):
            open_page(name)

    st.markdown("---")
    st.caption("YOUR SPACE")

    for icon, name in [
        ("◷", "Chat History"),
        ("▣", "My Creations"),
        ("⚙", "Settings"),
        ("ⓘ", "About")
    ]:
        if st.button(
            f"{icon}   {name}",
            key=f"nav_{name}",
            use_container_width=True
        ):
            open_page(name)

    st.markdown("---")
    st.caption("RECENT CHATS")

    for chat in all_chats()[:8]:
        if st.button(
            "•  " + (chat[1] or "New Chat")[:25],
            key=f"recent_{chat[0]}",
            use_container_width=True
        ):
            st.session_state.chat_id = chat[0]
            st.session_state.messages = get_messages(chat[0])
            st.session_state.page = "AI Chat"
            st.rerun()

    st.markdown("---")
    st.markdown(
        '<div class="metric-note">NEXTGEN AI · ULTRA EDITION<br>'
        'Created by Arav</div>',
        unsafe_allow_html=True
    )


page = st.session_state.page


# ============================================================
# DASHBOARD
# ============================================================

if page == "Dashboard":

    hero(
        "Imagine. Create. Discover.",
        "A smarter digital universe for ideas, learning, creativity and building."
    )

    st.markdown(
        '<div class="section-kicker">THE NEXTGEN EXPERIENCE</div>',
        unsafe_allow_html=True
    )

    st.markdown("## Your world, one workspace")

    a, b, c, d = st.columns(4)

    with a:
        metric("CREATIVE TOOLS", f"{TOOL_COUNT}+", "Explore your possibilities")

    with b:
        metric("WORKSPACES", "08", "Designed for your ideas")

    with c:
        metric("CHAT LIBRARY", f"{len(all_chats())}", "Your saved conversations")

    with d:
        metric("YOUR JOURNEY", "∞", "Learn something new every day")

    st.markdown("---")
    st.markdown("## Explore the universe")

    cards = [
        ("✦", "AI Universe", "Chat, ask questions, brainstorm and explore ideas.", "AI Chat"),
        ("◈", "Build Studio", "Plan websites, applications and coding projects.", "Build Studio"),
        ("▥", "Market Hub", "Explore market quotes, charts and financial concepts.", "Market Hub"),
        ("▧", "Creative Studio", "Create images and develop creative concepts.", "AI Image Studio"),
        ("🎓", "Study Hub", "Learn topics, practise questions and prepare for exams.", "Tool Center"),
        ("⚡", "Productivity", "Organise projects, plans, goals and daily tasks.", "Tool Center"),
        ("🌐", "Tool Universe", "Discover AI-powered helpers across many categories.", "Tool Center"),
        ("◎", "English Academy", "Practise vocabulary, grammar and conversation.", "English Academy")
    ]

    for start in range(0, len(cards), 2):
        left, right = st.columns(2, gap="large")

        for col, item in zip((left, right), cards[start:start + 2]):
            icon, title, desc, target = item

            with col:
                st.markdown(f"""
                <div class="dash-feature">
                    <div class="dash-kicker">DISCOVER YOUR NEXT IDEA</div>
                    <h3>{icon} {title}</h3>
                    <p>{desc}</p>
                </div>
                """, unsafe_allow_html=True)

                if st.button(
                    f"Explore {title} →",
                    key=f"dashboard_{title}",
                    use_container_width=True
                ):
                    open_page(target)

    st.markdown("---")
    st.markdown("## Quick launch")

    q1, q2, q3, q4 = st.columns(4)

    with q1:
        if st.button("✦ Start a conversation", use_container_width=True):
            open_page("AI Chat")

    with q2:
        if st.button("▧ Create an image", use_container_width=True):
            open_page("AI Image Studio")

    with q3:
        if st.button("⌕ Explore AI tools", use_container_width=True):
            open_page("Tool Center")

    with q4:
        if st.button("▤ Ask a PDF", use_container_width=True):
            open_page("PDF Assistant")

    st.markdown("---")
    st.markdown("## Your recent projects")

    recent = all_chats()[:5]

    if recent:
        for chat in recent:
            st.markdown(
                f"**{chat[1] or 'New Chat'}**  "
                f"<span style='color:#9aa9ca;font-size:12px;'>"
                f"{chat[2][:16]}</span>",
                unsafe_allow_html=True
            )
    else:
        st.info("Your new projects will appear here.")


# ============================================================
# AI CHAT
# ============================================================

elif page == "AI Chat":

    hero(
        "AI Universe",
        "Ask, explore, learn and create. Your next idea starts here."
    )

    for index, (role, content) in enumerate(st.session_state.messages):

        with st.chat_message(role):
            st.markdown(content)

            if role == "assistant":
                render_message_actions(index, content)

    if CF_LIVE_URL:
        st.link_button(
            "◉  Open Live Voice Experience",
            CF_LIVE_URL,
            use_container_width=True
        )

    st.caption(
        "You can type, attach documents, send an audio recording or use the voice experience."
    )

    submitted = st.chat_input(
        "Message NEXTGEN AI...",
        accept_file=True,
        accept_audio=True,
        file_type=["pdf", "txt", "png", "jpg", "jpeg"],
        max_upload_size=20
    )

    if submitted is not None:

        user_text = submitted.text or ""
        file_context = ""

        for uploaded in (submitted.files or []):

            filename = uploaded.name.lower()

            if filename.endswith(".txt"):
                file_context += (
                    "\n\n[Attached text]\n"
                    + uploaded.getvalue().decode(
                        "utf-8", errors="ignore"
                    )[:20000]
                )

            elif filename.endswith(".pdf"):
                try:
                    from pypdf import PdfReader

                    reader = PdfReader(io.BytesIO(uploaded.getvalue()))

                    extracted = "\n".join(
                        p.extract_text() or ""
                        for p in reader.pages
                    )

                    file_context += (
                        "\n\n[Attached PDF]\n"
                        + extracted[:25000]
                    )

                except Exception as exc:
                    st.warning(f"Could not read PDF: {exc}")

            elif filename.endswith((".png", ".jpg", ".jpeg")):
                st.info(
                    "Image attached. Image understanding needs a vision-capable "
                    "model integration."
                )

        if submitted.audio is not None:
            with st.spinner("Understanding your voice..."):
                try:
                    voice_text = transcribe_audio(submitted.audio)
                    user_text = (user_text + "\n" + voice_text).strip()
                except Exception as exc:
                    st.error(f"Audio transcription failed: {exc}")

        user_text = (user_text + file_context).strip()

        if user_text:

            st.session_state.messages.append(("user", user_text))

            save_message(
                st.session_state.chat_id,
                "user",
                user_text
            )

            if len(st.session_state.messages) == 1:
                set_chat_title(
                    st.session_state.chat_id,
                    user_text[:48]
                )

            api_messages = [
                {"role": role, "content": content}
                for role, content in st.session_state.messages[-20:]
            ]

            with st.spinner("Thinking..."):
                try:
                    answer, provider = smart_answer(api_messages)

                    st.session_state.messages.append(
                        ("assistant", answer)
                    )

                    save_message(
                        st.session_state.chat_id,
                        "assistant",
                        answer
                    )

                    st.session_state.last_provider = provider

                except Exception as exc:
                    st.error(f"Could not generate an answer: {exc}")

            st.rerun()


# ============================================================
# AI IMAGE STUDIO
# ============================================================

elif page == "AI Image Studio":

    hero(
        "Creative Studio",
        "Transform your imagination into original visual ideas."
    )

    prompt = st.text_area(
        "Describe your image",
        placeholder=(
            "Example: A futuristic city at night, glowing purple and blue "
            "lights, cinematic atmosphere..."
        ),
        height=130
    )

    aspect = st.selectbox(
        "Image format",
        ["Square", "Portrait", "Landscape"]
    )

    if st.button("✦ Create Image", use_container_width=True):

        if not prompt.strip():
            st.warning("Write an image description first.")

        else:
            final_prompt = prompt

            if aspect == "Portrait":
                final_prompt += ", portrait composition, vertical framing"
            elif aspect == "Landscape":
                final_prompt += ", wide landscape composition"

            with st.spinner("Creating your image..."):
                try:
                    image_data = cloudflare_image(final_prompt)

                    st.session_state.last_image = image_data

                    st.image(
                        image_data,
                        caption="Your NEXTGEN creation",
                        use_container_width=True
                    )

                    st.download_button(
                        "↓ Download Image",
                        data=image_data,
                        file_name="nextgen_creation.png",
                        mime="image/png"
                    )

                except Exception as exc:
                    st.error(f"Image generation failed: {exc}")

    if st.session_state.last_image:
        st.markdown("### Previous creation")
        st.image(
            st.session_state.last_image,
            use_container_width=True
        )


# ============================================================
# TOOL CENTER
# ============================================================

elif page == "Tool Center":

    hero(
        "Tool Universe",
        "Choose a tool, describe your goal and create something useful."
    )

    st.markdown(
        f"### {TOOL_COUNT}+ AI tool presets"
    )

    search_term = st.text_input(
        "⌕ Search tools",
        placeholder="Search writing, coding, study, creator tools..."
    )

    categories = list(TOOL_LIBRARY.keys())

    if search_term.strip():
        matching = {
            category: [
                tool for tool in tools
                if search_term.lower() in tool.lower()
            ]
            for category, tools in TOOL_LIBRARY.items()
        }

        matching = {
            category: tools
            for category, tools in matching.items()
            if tools
        }

        if not matching:
            st.info("No matching tools found.")
            category = None
        else:
            category = st.selectbox(
                "Category",
                list(matching.keys())
            )
            available_tools = matching[category]

    else:
        category = st.selectbox(
            "Select a category",
            categories
        )
        available_tools = TOOL_LIBRARY[category]

    if category:
        tool_name = st.selectbox(
            "Select a tool",
            available_tools
        )

        details = st.text_area(
            "Describe what you want",
            placeholder=(
                "Write your topic, language, level, style and requirements..."
            ),
            height=130
        )

        if st.button("Run Tool ✦", use_container_width=True):

            if not details.strip():
                st.warning("Enter your instructions first.")

            else:
                with st.spinner(f"Working on {tool_name}..."):
                    try:
                        result, provider = run_tool(
                            tool_name,
                            details
                        )

                        st.session_state.tool_result = {
                            "tool": tool_name,
                            "result": result,
                            "provider": provider
                        }

                    except Exception as exc:
                        st.error(str(exc))

        if st.session_state.tool_result:
            st.markdown("---")
            st.markdown(
                f"### {st.session_state.tool_result['tool']}"
            )
            st.markdown(
                st.session_state.tool_result["result"]
            )

            st.download_button(
                "↓ Download result",
                data=st.session_state.tool_result["result"],
                file_name="nextgen_tool_result.txt",
                mime="text/plain"
            )


# ============================================================
# PDF ASSISTANT
# ============================================================

elif page == "PDF Assistant":

    hero(
        "Document Intelligence",
        "Upload a PDF and explore its contents with AI."
    )

    pdf = st.file_uploader(
        "＋ Upload PDF document",
        type=["pdf"]
    )

    if pdf:
        try:
            from pypdf import PdfReader

            reader = PdfReader(io.BytesIO(pdf.getvalue()))

            pdf_text = "\n".join(
                page.extract_text() or ""
                for page in reader.pages
            )

            st.session_state.pdf_text = pdf_text

            st.success(
                f"Document loaded: {len(reader.pages)} pages"
            )

            st.text_area(
                "Extracted text preview",
                pdf_text[:5000],
                height=180
            )

            question = st.text_input(
                "Ask a question about this PDF"
            )

            if st.button("Ask about this document"):

                if not question.strip():
                    st.warning("Write a question first.")

                else:
                    prompt = f"""
Answer using the PDF content below.
If the answer is not present in the document, say so clearly.

PDF CONTENT:
{pdf_text[:45000]}

QUESTION:
{question}
"""

                    with st.spinner("Reading the document..."):
                        try:
                            answer, _ = ask_ai([
                                {"role": "user", "content": prompt}
                            ])
                            st.markdown(answer)

                        except Exception as exc:
                            st.error(str(exc))

        except Exception as exc:
            st.error(f"PDF error: {exc}")


# ============================================================
# BUILD STUDIO
# ============================================================

elif page == "Build Studio":

    hero(
        "Build Studio",
        "Turn your ideas into application plans, websites and code."
    )

    build_type = st.selectbox(
        "Choose your project",
        [
            "Website Builder",
            "Application Builder",
            "Python Project",
            "Streamlit Application",
            "HTML and CSS Page",
            "Business Website",
            "Portfolio Website",
            "Learning Project"
        ]
    )

    project_name = st.text_input(
        "Project name",
        placeholder="My awesome project"
    )

    requirements = st.text_area(
        "Describe your idea",
        placeholder=(
            "Explain what the project should do, its pages, features "
            "and design..."
        ),
        height=160
    )

    skill_level = st.selectbox(
        "Your coding level",
        ["Beginner", "Intermediate", "Advanced"]
    )

    if st.button("✦ Build My Project Plan", use_container_width=True):

        if not requirements.strip():
            st.warning("Describe your project first.")

        else:
            prompt = f"""
Act as a senior software developer and patient teacher.

PROJECT TYPE: {build_type}
PROJECT NAME: {project_name}
LEVEL: {skill_level}

REQUIREMENTS:
{requirements}

Create:
1. A clear project overview.
2. Main features.
3. Suggested folder structure.
4. Required packages.
5. Complete beginner-friendly implementation steps.
6. Code for the first working version.
7. How to run and test it.
8. Common errors and solutions.

Do not claim code was executed or tested unless it actually was.
"""

            with st.spinner("Designing your project..."):
                try:
                    result, _ = ask_ai([
                        {"role": "user", "content": prompt}
                    ])
                    st.markdown(result)

                    st.download_button(
                        "↓ Download project plan",
                        data=result,
                        file_name="project_plan.md",
                        mime="text/markdown"
                    )

                except Exception as exc:
                    st.error(str(exc))


# ============================================================
# MARKET HUB
# ============================================================

elif page == "Market Hub":

    hero(
        "Market Hub",
        "Explore market data, understand charts and learn financial concepts."
    )

    st.info(
        "Market information is for learning and research. "
        "It is not a personal investment recommendation."
    )

    symbol = st.text_input(
        "Enter stock symbol",
        value="AAPL",
        help="Examples: AAPL, MSFT, NVDA"
    ).strip().upper()

    if st.button("Get Market Quote", use_container_width=True):

        if not symbol:
            st.warning("Enter a stock symbol.")

        else:
            with st.spinner("Fetching market quote..."):
                try:
                    quote_data = get_stock_quote(symbol)

                    current = quote_data.get("c", 0)
                    previous = quote_data.get("pc", 0)
                    change = current - previous

                    a, b, c = st.columns(3)

                    with a:
                        metric("CURRENT PRICE", f"${current:.2f}", symbol)

                    with b:
                        metric("PREVIOUS CLOSE", f"${previous:.2f}", symbol)

                    with c:
                        metric("CHANGE", f"${change:.2f}", "Compared with previous close")

                    st.markdown("### Quote details")

                    st.json({
                        "Symbol": symbol,
                        "Open": quote_data.get("o"),
                        "High": quote_data.get("h"),
                        "Low": quote_data.get("l"),
                        "Current": current,
                        "Previous close": previous
                    })

                except Exception as exc:
                    st.error(f"Could not retrieve quote: {exc}")

    st.markdown("---")
    st.markdown("## Learn about the stock market")

    finance_topic = st.selectbox(
        "Choose a learning topic",
        [
            "What is the stock market?",
            "What is a stock?",
            "What is an index?",
            "What is market capitalisation?",
            "What is a dividend?",
            "What is volatility?",
            "What is diversification?",
            "How do stock charts work?",
            "What are the risks of investing?"
        ]
    )

    if st.button("Explain this topic"):
        with st.spinner("Preparing a simple explanation..."):
            try:
                answer, _ = ask_ai([
                    {
                        "role": "user",
                        "content": (
                            "Explain this financial education topic for a beginner "
                            "in simple language, with examples and risks where "
                            "relevant: " + finance_topic
                        )
                    }
                ])
                st.markdown(answer)

            except Exception as exc:
                st.error(str(exc))


# ============================================================
# ENGLISH ACADEMY
# ============================================================

elif page == "English Academy":

    hero(
        "English Academy",
        "Build confidence with vocabulary, grammar and everyday English."
    )

    mode = st.selectbox(
        "Choose your practice",
        [
            "Daily Vocabulary",
            "Grammar Practice",
            "Sentence Correction",
            "Conversation Practice",
            "Translate Hindi to English",
            "Translate English to Hindi",
            "Improve My Paragraph",
            "Speaking Practice Questions"
        ]
    )

    learner_text = st.text_area(
        "Write your answer or topic",
        placeholder="Type a sentence, paragraph or topic here...",
        height=130
    )

    if st.button("Start Practice", use_container_width=True):

        prompt = f"""
You are a friendly English teacher.
The learner is practising English.

ACTIVITY: {mode}
LEARNER INPUT: {learner_text}

Give a useful exercise or correction.
Explain mistakes kindly and clearly.
For vocabulary, give meanings and simple example sentences.
For grammar, explain the rule and give practice questions.
For conversation practice, ask one question at a time.
"""

        with st.spinner("Preparing your English practice..."):
            try:
                answer, _ = ask_ai([
                    {"role": "user", "content": prompt}
                ])
                st.markdown(answer)

            except Exception as exc:
                st.error(str(exc))


# ============================================================
# CHAT HISTORY
# ============================================================

elif page == "Chat History":

    hero(
        "Your Conversation Library",
        "Return to your saved ideas and previous conversations."
    )

    chats = all_chats()

    if not chats:
        st.info("No conversations yet.")

    for chat in chats:

        chat_id, title, created = chat

        with st.expander(
            f"{title or 'New Chat'}  ·  {created[:16]}"
        ):

            open_col, delete_col = st.columns(2)

            with open_col:
                if st.button(
                    "Open conversation",
                    key=f"history_open_{chat_id}"
                ):
                    st.session_state.chat_id = chat_id
                    st.session_state.messages = get_messages(chat_id)
                    st.session_state.page = "AI Chat"
                    st.rerun()

            with delete_col:
                if st.button(
                    "Delete",
                    key=f"history_delete_{chat_id}"
                ):
                    remove_chat(chat_id)

                    if st.session_state.chat_id == chat_id:
                        st.session_state.chat_id = create_chat()
                        st.session_state.messages = []

                    st.rerun()


# ============================================================
# MY CREATIONS
# ============================================================

elif page == "My Creations":

    hero(
        "My Creations",
        "A place for the work you create with NEXTGEN AI."
    )

    st.markdown("## Your workspace")

    st.markdown("""
    - Generated images can be saved from Image Studio.
    - Tool results can be downloaded as text files.
    - Project plans can be downloaded as Markdown.
    - Conversations remain available in Chat History.
    """)

    if st.button("Open Image Studio", use_container_width=True):
        open_page("AI Image Studio")


# ============================================================
# SETTINGS
# ============================================================

elif page == "Settings":

    hero(
        "Personal Workspace",
        "Adjust your workspace and explore your application setup."
    )

    st.markdown("### Interface")

    st.selectbox(
        "Preferred language",
        ["Automatic", "Hindi", "English"],
        key="preferred_language"
    )

    st.selectbox(
        "Response style",
        ["Balanced", "Simple", "Detailed"],
        key="response_style"
    )

    st.markdown("### Your workspace")

    st.write(f"Saved conversations: {len(all_chats())}")
    st.write(f"Available tool presets: {TOOL_COUNT}")
    st.write(f"Tool categories: {len(TOOL_LIBRARY)}")

    st.markdown("### API configuration")

    st.caption(
        "API credentials are managed through your Streamlit Secrets "
        "or environment variables."
    )

    st.markdown("""
    Example secret names:

    - `GROQ_API_KEY`
    - `GEMINI_API_KEY`
    - `CLOUDFLARE_ACCOUNT_ID`
    - `CLOUDFLARE_API_TOKEN`
    - `CLOUDFLARE_VOICE_URL`
    - `FINNHUB_API_KEY`
    """)


# ============================================================
# ABOUT
# ============================================================

elif page == "About":

    hero(
        "The Vision Behind NEXTGEN",
        "A student-built workspace for learning, creativity and technology."
    )

    st.markdown("""
    ## ✦ Arav

    **Student Developer · AI Enthusiast · Creator of NEXTGEN AI**

    Arav is a student at **Swami Vivekanand Shiksha Niketan**.
    He is interested in artificial intelligence, technology,
    coding and creative problem-solving.

    NEXTGEN AI is a project built around the idea of bringing
    useful AI-powered experiences together in one workspace.

    ### The NEXTGEN vision

    - Make technology easier to explore.
    - Help learners understand difficult topics.
    - Encourage creativity and original ideas.
    - Make application development more approachable.
    - Bring useful digital tools into one organised workspace.

    ### Explore the platform

    - AI Chat
    - Creative Studio
    - Tool Universe
    - Document Assistant
    - Build Studio
    - Market Hub
    - English Academy
    - Conversation Library

    ### Technology

    | Technology | Role |
    |---|---|
    | Python | Application development |
    | Streamlit | User interface |
    | SQLite | Conversation storage |
    | Groq | AI responses |
    | Gemini | AI responses |
    | Cloudflare | Image generation |
    | Finnhub | Market quote data |

    **One Platform. Endless Possibilities.**
    """)

    st.markdown("---")

    st.markdown(
        '<div class="hero">'
        '<div class="hero-label">CREATED WITH CURIOSITY</div>'
        '<div class="hero-title">NEXTGEN AI</div>'
        '<div class="hero-sub">Imagine. Create. Discover.</div>'
        '</div>',
        unsafe_allow_html=True
    )


# ============================================================
# FOOTER
# ============================================================

st.markdown("---")

st.markdown(
    """
    <div style="text-align:center;color:#8998b8;font-size:11px;padding:10px;">
        ✦ NEXTGEN AI · Imagine. Create. Discover. · 2026
    </div>
    """,
    unsafe_allow_html=True
)
