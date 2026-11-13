import os
import io
import sqlite3
import base64
import requests
import streamlit as st
from datetime import datetime

# =========================================================
# NEXTGEN AI — VERSION MAX
# =========================================================

st.set_page_config(
    page_title="NEXTGEN AI MAX",
    page_icon="✦",
    layout="wide",
    initial_sidebar_state="expanded"
)

DB_PATH = "nextgen_max.db"

# =========================================================
# API CONFIGURATION
# =========================================================

def secret(key, default=""):
    try:
        value = st.secrets.get(key)
        if value:
            return value
    except Exception:
        pass
    return os.getenv(key, default)


GROQ_API_KEY = secret("GROQ_API_KEY")
GEMINI_API_KEY = secret("GEMINI_API_KEY")
CF_ACCOUNT_ID = secret("CLOUDFLARE_ACCOUNT_ID")
CF_API_TOKEN = secret("CLOUDFLARE_API_TOKEN")
CLOUDFLARE_VOICE_URL = secret("CLOUDFLARE_VOICE_URL")

GROQ_MODEL = "openai/gpt-oss-120b"
GEMINI_MODEL = "gemini-3.5-flash"
IMAGE_MODEL = "@cf/black-forest-labs/flux-1-schnell"

# =========================================================
# DATABASE
# =========================================================

def db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    with db() as con:
        con.execute("""
            CREATE TABLE IF NOT EXISTS chats(
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT,
                created TEXT
            )
        """)
        con.execute("""
            CREATE TABLE IF NOT EXISTS messages(
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                chat_id INTEGER,
                role TEXT,
                content TEXT,
                created TEXT
            )
        """)
        con.execute("""
            CREATE TABLE IF NOT EXISTS creations(
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                kind TEXT,
                content TEXT,
                created TEXT
            )
        """)


def create_chat():
    with db() as con:
        cur = con.execute(
            "INSERT INTO chats(title,created) VALUES(?,?)",
            ("New Chat", datetime.now().isoformat())
        )
        return cur.lastrowid


def get_chats():
    with db() as con:
        return con.execute(
            "SELECT * FROM chats ORDER BY id DESC"
        ).fetchall()


def get_messages(chat_id):
    with db() as con:
        return con.execute(
            "SELECT * FROM messages WHERE chat_id=? ORDER BY id",
            (chat_id,)
        ).fetchall()


def save_message(chat_id, role, content):
    with db() as con:
        con.execute("""
            INSERT INTO messages(chat_id,role,content,created)
            VALUES(?,?,?,?)
        """, (
            chat_id, role, content, datetime.now().isoformat()
        ))


def update_title(chat_id, title):
    with db() as con:
        con.execute(
            "UPDATE chats SET title=? WHERE id=? AND title='New Chat'",
            (title[:45], chat_id)
        )


def delete_chat(chat_id):
    with db() as con:
        con.execute("DELETE FROM messages WHERE chat_id=?", (chat_id,))
        con.execute("DELETE FROM chats WHERE id=?", (chat_id,))


def save_creation(kind, content):
    with db() as con:
        con.execute(
            "INSERT INTO creations(kind,content,created) VALUES(?,?,?)",
            (kind, content, datetime.now().isoformat())
        )


def get_creations():
    with db() as con:
        return con.execute(
            "SELECT * FROM creations ORDER BY id DESC"
        ).fetchall()


init_db()

# =========================================================
# TOOL LIBRARY — 20 CATEGORIES
# =========================================================

TOOL_LIBRARY = {
    "Writing & Documents": [
        "Email Writer", "Essay Writer", "Article Writer",
        "Blog Writer", "Letter Writer", "Report Writer",
        "Paragraph Writer", "Grammar Checker", "Proofreader",
        "Text Rewriter"
    ],
    "Study & Education": [
        "MCQ Generator", "Quiz Generator", "Flashcard Creator",
        "Study Notes", "Chapter Explainer", "Homework Helper",
        "Revision Planner", "Question Answer Generator",
        "Practice Test", "Study Guide"
    ],
    "Coding & Development": [
        "Code Generator", "Code Debugger", "Code Explainer",
        "Python Assistant", "HTML Generator", "CSS Generator",
        "JavaScript Assistant", "SQL Assistant", "Regex Helper",
        "Code Reviewer"
    ],
    "YouTube & Content Creator": [
        "Video Script Writer", "YouTube Description",
        "Title Generator", "Hashtag Generator",
        "Video Ideas", "Shorts Ideas", "Thumbnail Concept",
        "Storyboard Creator", "Channel Bio", "Content Planner"
    ],
    "Business & Marketing": [
        "Business Plan", "Marketing Strategy", "Brand Name",
        "Product Description", "Ad Copy Writer", "Slogan Generator",
        "SWOT Analysis", "Customer Persona", "Market Research",
        "Business Ideas"
    ],
    "Language & Translation": [
        "Hindi to English", "English to Hindi",
        "Text Translator", "Vocabulary Builder",
        "Sentence Correction", "Pronunciation Guide",
        "Language Practice", "Synonym Finder",
        "Antonym Finder", "Grammar Tutor"
    ],
    "Productivity & Planning": [
        "Study Timetable", "Daily Planner", "Task Planner",
        "Goal Planner", "Habit Tracker Ideas", "Time Manager",
        "Weekly Planner", "Project Planner",
        "Priority Organizer", "Routine Builder"
    ],
    "Creative & Design": [
        "Image Prompt Generator", "Logo Ideas",
        "Poster Concept", "Banner Concept",
        "Color Palette Ideas", "Creative Writing",
        "Story Generator", "Poem Writer",
        "Character Creator", "Design Brief"
    ],
    "Everyday Assistant": [
        "General Assistant", "Decision Helper",
        "Message Writer", "Shopping List",
        "Travel Planner", "Recipe Ideas",
        "Event Planner", "Explanation Assistant",
        "Daily Advice", "Information Organizer"
    ],
    "Career & Skills": [
        "Resume Writer", "Interview Practice",
        "Cover Letter", "Skill Roadmap",
        "Career Exploration", "Portfolio Ideas",
        "Communication Practice", "Learning Plan",
        "Professional Bio", "Presentation Practice"
    ],
    "Data & Analysis": [
        "Data Explainer", "Table Analyzer",
        "Data Summary", "Trend Explanation",
        "Chart Suggestions", "Spreadsheet Helper",
        "Data Cleaning Ideas", "Report Analysis",
        "Comparison Tool", "Statistics Tutor"
    ],
    "Research & Thinking": [
        "Research Assistant", "Research Question Generator",
        "Topic Explorer", "Critical Thinking",
        "Argument Builder", "Pros and Cons",
        "Fact Explanation", "Idea Organizer",
        "Concept Comparison", "Problem Solver"
    ],
    "Advanced Study Tools": [
        "Maths Step Solver", "Science Explainer",
        "Physics Tutor", "Chemistry Tutor",
        "Biology Tutor", "History Explainer",
        "Geography Tutor", "Exam Practice",
        "Concept Revision", "Doubt Solver"
    ],
    "AI Creator Studio": [
        "AI Image Prompt", "AI Video Prompt",
        "Scene Generator", "Voiceover Script",
        "Character Prompt", "Animation Concept",
        "Cinematic Prompt", "Music Concept",
        "Visual Storytelling", "Creative Direction"
    ],
    "Web & App Development": [
        "Website Planner", "App Idea Generator",
        "UI Content Writer", "Landing Page Copy",
        "Frontend Helper", "Backend Helper",
        "API Explainer", "Database Planner",
        "Website Debugger", "App Feature Planner"
    ],
    "Smart AI Assistants": [
        "Personal AI Assistant", "Study Assistant",
        "Coding Assistant", "Writing Assistant",
        "Research Assistant", "Creative Assistant",
        "Planning Assistant", "Learning Assistant",
        "Business Assistant", "General AI Helper"
    ],
    "Maths & Science Lab": [
        "Algebra Helper", "Geometry Explainer",
        "Equation Solver", "Unit Converter",
        "Physics Formula Guide", "Chemistry Formula Guide",
        "Scientific Concept Explainer", "Graph Explanation",
        "Numerical Practice", "Maths Quiz"
    ],
    "Business Creator Tools": [
        "Startup Name Generator", "Business Proposal",
        "Product Ideas", "Pricing Strategy",
        "Brand Story", "Sales Pitch",
        "Business Presentation", "Customer Feedback Questions",
        "Business Checklist", "Growth Ideas"
    ],
    "Learning & Knowledge": [
        "Topic Summarizer", "Text Summarizer",
        "Knowledge Guide", "Beginner Roadmap",
        "Quick Learning Notes", "Concept Map",
        "Question Generator", "Memory Techniques",
        "Revision Questions", "Explain Like Beginner"
    ],
    "Presentation & Office": [
        "Presentation Outline", "Slide Content Writer",
        "Meeting Notes", "Agenda Creator",
        "Office Email", "Document Formatter",
        "Speech Writer", "Project Report",
        "Presentation Summary", "Professional Document"
    ]
}

TOOL_COUNT = sum(len(v) for v in TOOL_LIBRARY.values())

# =========================================================
# AI ENGINE
# =========================================================

SYSTEM_PROMPT = """
You are NEXTGEN AI, a helpful and intelligent AI assistant.
You were created as a learning and technology project by Arav.
Answer clearly, accurately and politely.
Support Hindi and English.
Never claim that an action was completed if it was not.
Explain educational topics step by step.
"""


def groq_request(messages):
    if not GROQ_API_KEY:
        raise RuntimeError("GROQ_API_KEY is missing.")

    payload = {
        "model": GROQ_MODEL,
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT}
        ] + messages,
        "temperature": 0.6,
        "max_completion_tokens": 3000
    }

    response = requests.post(
        "https://api.groq.com/openai/v1/chat/completions",
        headers={
            "Authorization": f"Bearer {GROQ_API_KEY}",
            "Content-Type": "application/json"
        },
        json=payload,
        timeout=60
    )

    response.raise_for_status()
    return response.json()["choices"][0]["message"]["content"]


def gemini_request(messages):
    if not GEMINI_API_KEY:
        raise RuntimeError("GEMINI_API_KEY is missing.")

    contents = []
    for item in messages:
        contents.append({
            "role": "user" if item["role"] == "user" else "model",
            "parts": [{"text": item["content"]}]
        })

    url = (
        "https://generativelanguage.googleapis.com/v1beta/models/"
        + GEMINI_MODEL
        + ":generateContent?key="
        + GEMINI_API_KEY
    )

    response = requests.post(
        url,
        json={
            "systemInstruction": {
                "parts": [{"text": SYSTEM_PROMPT}]
            },
            "contents": contents
        },
        timeout=45
    )

    response.raise_for_status()
    data = response.json()
    return data["candidates"][0]["content"]["parts"][0]["text"]


def ask_ai(messages):
    errors = []

    if GROQ_API_KEY:
        try:
            return groq_request(messages), "Groq"
        except Exception as e:
            errors.append(f"Groq: {e}")

    if GEMINI_API_KEY:
        try:
            return gemini_request(messages), "Gemini"
        except Exception as e:
            errors.append(f"Gemini: {e}")

    raise RuntimeError(
        "AI provider unavailable. " + " | ".join(errors)
        if errors else
        "Add GROQ_API_KEY or GEMINI_API_KEY to your environment."
    )


def run_tool(tool_name, details):
    prompt = f"""
    Perform this task: {tool_name}

    User instructions:
    {details}

    Give a useful, well-structured result.
    """
    return ask_ai([{"role": "user", "content": prompt}])[0]


# =========================================================
# IMAGE GENERATION
# =========================================================

def cloudflare_image(prompt):
    if not CF_ACCOUNT_ID or not CF_API_TOKEN:
        raise RuntimeError("Cloudflare credentials are missing.")

    url = (
        f"https://api.cloudflare.com/client/v4/accounts/"
        f"{CF_ACCOUNT_ID}/ai/run/{IMAGE_MODEL}"
    )

    response = requests.post(
        url,
        headers={"Authorization": f"Bearer {CF_API_TOKEN}"},
        json={"prompt": prompt},
        timeout=120
    )

    response.raise_for_status()
    data = response.json()

    if "result" in data and "image" in data["result"]:
        return base64.b64decode(data["result"]["image"])

    raise RuntimeError("Image generation returned no image.")


# =========================================================
# CSS — DARK PREMIUM PURPLE BLUE
# =========================================================

st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800;900&display=swap');

html, body, [class*="css"] {
    font-family: 'Inter', sans-serif;
}

.stApp {
    background:
        radial-gradient(ellipse at 10% 0%, #24204e 0%, transparent 35%),
        radial-gradient(ellipse at 90% 15%, #142b55 0%, transparent 35%),
        linear-gradient(140deg, #070b18, #0c1022 55%, #090d1b);
    color: #f5f5ff;
}

.block-container {
    max-width: 1450px;
    padding-top: 1.4rem;
    padding-bottom: 5rem;
}

[data-testid="stSidebar"] {
    background: linear-gradient(180deg, #111a30, #0a1020);
    border-right: 1px solid #2c3858;
}

[data-testid="stSidebar"] * {
    color: #e8eaff;
}

.brand {
    font-size: 27px;
    font-weight: 900;
    letter-spacing: -1px;
    padding: 8px 0;
}

.brand span {
    color: #a78bfa;
}

.hero {
    padding: 34px;
    border-radius: 25px;
    border: 1px solid #51418c;
    background:
        radial-gradient(circle at 90% 20%, #41409b55, transparent 35%),
        linear-gradient(120deg, #171a3a, #142344);
    box-shadow: 0 15px 45px #0005;
    margin-bottom: 25px;
}

.hero-label, .dash-kicker {
    color: #b5a5ff;
    font-size: 11px;
    font-weight: 800;
    letter-spacing: 2px;
    text-transform: uppercase;
}

.hero-title {
    font-size: clamp(32px, 5vw, 53px);
    font-weight: 900;
    letter-spacing: -2px;
    margin: 8px 0;
}

.hero-sub {
    color: #c1c8e5;
    line-height: 1.7;
}

.panel {
    padding: 20px;
    border-radius: 18px;
    background: linear-gradient(145deg, #151d35, #10182b);
    border: 1px solid #2c3858;
    margin-bottom: 14px;
}

.tool-stat {
    padding: 23px;
    border-radius: 20px;
    background: linear-gradient(140deg, #201d49, #132c4b);
    border: 1px solid #55469a;
    margin: 12px 0;
}

.small-muted {
    color: #9da8c8;
    font-size: 13px;
}

div[data-testid="stChatMessage"] {
    padding: 9px 13px !important;
    margin-bottom: 8px !important;
    border-radius: 15px !important;
    border: 1px solid #2b3655;
    background: #111a2d;
}

div[data-testid="stChatMessage"] p {
    font-size: 14px;
    line-height: 1.6;
}

.stButton > button {
    border: 1px solid #574c9b;
    border-radius: 12px;
    background: linear-gradient(120deg, #6049b7, #3456a0);
    color: white;
    font-weight: 700;
    transition: .2s;
}

.stButton > button:hover {
    border-color: #b7a4ff;
    transform: translateY(-1px);
    color: white;
}

.stTextInput input, .stTextArea textarea,
.stSelectbox div[data-baseweb="select"] {
    background: #10182b !important;
    border: 1px solid #39466b !important;
    border-radius: 13px !important;
    color: white !important;
}

[data-testid="stChatInput"] {
    border-radius: 22px !important;
    border: 1px solid #554a91 !important;
    background: #10182b !important;
}

hr {
    border-color: #283653;
}

</style>
""", unsafe_allow_html=True)


# =========================================================
# UI HELPERS
# =========================================================

def hero(title, subtitle):
    st.markdown(f"""
    <div class="hero">
        <div class="hero-label">NEXTGEN AI • VERSION MAX</div>
        <div class="hero-title">{title}</div>
        <div class="hero-sub">{subtitle}</div>
    </div>
    """, unsafe_allow_html=True)


def panel(icon, title, description):
    st.markdown(f"""
    <div class="panel">
        <div style="font-size:23px">{icon}</div>
        <h3 style="margin:8px 0;color:white">{title}</h3>
        <div class="small-muted">{description}</div>
    </div>
    """, unsafe_allow_html=True)


def metric(label, value, icon):
    st.markdown(f"""
    <div class="panel">
        <div class="small-muted">{icon} {label}</div>
        <div style="font-size:27px;font-weight:900;margin-top:8px">
            {value}
        </div>
    </div>
    """, unsafe_allow_html=True)


# =========================================================
# SESSION STATE
# =========================================================

if "page" not in st.session_state:
    st.session_state.page = "Dashboard"

if "chat_id" not in st.session_state:
    st.session_state.chat_id = create_chat()

if "tool_result" not in st.session_state:
    st.session_state.tool_result = None

if "tool_name" not in st.session_state:
    st.session_state.tool_name = None


def go(page):
    st.session_state.page = page


# =========================================================
# SIDEBAR
# =========================================================

with st.sidebar:
    st.markdown(
        '<div class="brand">✦ NEXTGEN <span>AI</span></div>',
        unsafe_allow_html=True
    )
    st.caption("VERSION MAX • Your Creative Universe")

    if st.button("＋  New Chat", use_container_width=True):
        st.session_state.chat_id = create_chat()
        go("AI Chat")
        st.rerun()

    st.markdown("---")
    st.caption("WORKSPACE")

    pages = [
        "Dashboard",
        "AI Chat",
        "AI Image Studio",
        "Tool Center",
        "PDF Assistant"
    ]

    for p in pages:
        if st.button(p, use_container_width=True, key="nav_"+p):
            go(p)
            st.rerun()

    st.markdown("---")
    st.caption("LIBRARY")

    for p in ["Chat History", "My Creations", "Settings", "About"]:
        if st.button(p, use_container_width=True, key="nav_"+p):
            go(p)
            st.rerun()

    st.markdown("---")
    st.caption("RECENT CONVERSATIONS")

    for chat in get_chats()[:7]:
        if st.button(
            "💬 " + (chat["title"] or "New Chat")[:25],
            key=f"recent_{chat['id']}",
            use_container_width=True
        ):
            st.session_state.chat_id = chat["id"]
            go("AI Chat")
            st.rerun()

    st.markdown("---")
    st.caption("NEXTGEN AI MAX © 2026")
    st.caption("Created by Arav")


# =========================================================
# DASHBOARD
# =========================================================

page = st.session_state.page

if page == "Dashboard":

    hero(
        "One Platform. Endless Possibilities.",
        "Explore AI chat, creativity, productivity, learning and intelligent tools — all in one workspace."
    )

    a, b, c, d = st.columns(4)

    with a:
        metric("AI TOOLS", TOOL_COUNT, "✦")
    with b:
        metric("CATEGORIES", len(TOOL_LIBRARY), "▦")
    with c:
        metric("AI CHAT", "Ready", "💬")
    with d:
        metric("VERSION", "MAX", "🚀")

    st.markdown("## ✦ Explore Workspace")

    cols = st.columns(3)

    features = [
        ("💬", "AI Chat", "Ask questions and explore ideas."),
        ("🎨", "AI Image Studio", "Create AI-generated images."),
        ("🧰", "Tool Center", "Explore 20 AI tool categories."),
        ("📄", "PDF Assistant", "Ask questions about PDF documents."),
        ("📚", "Chat History", "Continue previous conversations."),
        ("⚙️", "Settings", "Manage your workspace.")
    ]

    for i, item in enumerate(features):
        with cols[i % 3]:
            panel(*item)

    st.markdown("## 🚀 Your AI Workspace")
    st.write(
        "NEXTGEN AI brings useful AI experiences together in a single interface."
    )


# =========================================================
# AI CHAT
# =========================================================

elif page == "AI Chat":

    hero(
        "AI Chat",
        "Ask anything. Learn anything. Create anything."
    )

    messages = get_messages(st.session_state.chat_id)

    if not messages:
        st.markdown("""
        <div class="tool-stat">
            <h3 style="color:white">Hello! Welcome to NEXTGEN AI ✦</h3>
            <p class="small-muted">
                Your AI assistant is ready. Type your first question below.
            </p>
        </div>
        """, unsafe_allow_html=True)

    for index, msg in enumerate(messages):
        with st.chat_message(msg["role"]):
            st.markdown(msg["content"])

            if msg["role"] == "assistant":
                c1, c2, c3, c4, c5 = st.columns(5)

                with c1:
                    if st.button("📋 Copy", key=f"copy_{msg['id']}"):
                        st.code(msg["content"])

                with c2:
                    if st.button("🔊 Read", key=f"read_{msg['id']}"):
                        st.components.v1.html(
                            f"""
                            <script>
                            const text = {json.dumps(msg["content"])};
                            const utterance = new SpeechSynthesisUtterance(text);
                            speechSynthesis.speak(utterance);
                            </script>
                            """,
                            height=0
                        )

                with c3:
                    st.button("👍", key=f"like_{msg['id']}")

                with c4:
                    st.button("👎", key=f"dislike_{msg['id']}")

                with c5:
                    if st.button("↻", key=f"regen_{msg['id']}"):
                        st.session_state.regenerate_id = msg["id"]
                        st.rerun()

    if st.session_state.get("regenerate_id"):
        target_id = st.session_state.pop("regenerate_id")
        history = get_messages(st.session_state.chat_id)
        prior = []
        for m in history:
            if m["id"] == target_id:
                break
            prior.append({"role": m["role"], "content": m["content"]})

        try:
            with st.spinner("Regenerating..."):
                answer, provider = ask_ai(prior)
            save_message(st.session_state.chat_id, "assistant", answer)
            st.rerun()
        except Exception as e:
            st.error(str(e))

    prompt = st.chat_input(
        "Message NEXTGEN AI...",
        accept_file=True,
        accept_audio=True,
        file_type=["pdf", "txt", "png", "jpg", "jpeg"]
    )

    if prompt:
        user_text = prompt.text or ""

        if prompt.files:
            for uploaded in prompt.files:
                if uploaded.type == "text/plain":
                    user_text += "\n\n" + uploaded.getvalue().decode(
                        "utf-8", errors="ignore"
                    )
                elif uploaded.name.lower().endswith(".pdf"):
                    try:
                        from pypdf import PdfReader
                        reader = PdfReader(uploaded)
                        pdf_text = "\n".join(
                            page.extract_text() or ""
                            for page in reader.pages
                        )
                        user_text += "\n\nPDF CONTENT:\n" + pdf_text[:30000]
                    except Exception as e:
                        user_text += f"\nPDF reading error: {e}"
                else:
                    user_text += (
                        f"\nAttached image: {uploaded.name}. "
                        "Image understanding is not enabled in this version."
                    )

        if prompt.audio:
            st.warning(
                "Audio received. Configure a transcription service "
                "to convert audio into text."
            )

        if user_text.strip():
            save_message(
                st.session_state.chat_id, "user", user_text
            )

            current = get_messages(st.session_state.chat_id)
            history = [
                {"role": m["role"], "content": m["content"]}
                for m in current
            ]

            update_title(
                st.session_state.chat_id, user_text
            )

            try:
                with st.spinner("NEXTGEN AI is thinking..."):
                    answer, provider = ask_ai(history)

                save_message(
                    st.session_state.chat_id, "assistant", answer
                )

                st.rerun()

            except Exception as e:
                st.error(f"AI could not respond: {e}")


# =========================================================
# AI IMAGE STUDIO
# =========================================================

elif page == "AI Image Studio":

    hero(
        "AI Image Studio",
        "Turn your imagination into visuals."
    )

    prompt = st.text_area(
        "Describe your image",
        placeholder="A cinematic futuristic city at night..."
    )

    if st.button("✨ Generate Image", use_container_width=True):
        if not prompt.strip():
            st.warning("Please enter an image prompt.")
        else:
            try:
                with st.spinner("Creating your image..."):
                    image_data = cloudflare_image(prompt)

                st.image(image_data, use_container_width=True)
                st.download_button(
                    "⬇️ Download Image",
                    image_data,
                    file_name="nextgen_creation.png",
                    mime="image/png"
                )

                save_creation("image", prompt)

            except Exception as e:
                st.error(str(e))


# =========================================================
# TOOL CENTER
# =========================================================

elif page == "Tool Center":

    hero(
        "AI Tool Center",
        f"Explore {TOOL_COUNT} tools across 20 categories."
    )

    category = st.selectbox(
        "Choose Category",
        list(TOOL_LIBRARY.keys())
    )

    tool = st.selectbox(
        "Choose Tool",
        TOOL_LIBRARY[category]
    )

    details = st.text_area(
        "Your Instructions",
        placeholder="Describe what you want the AI to create..."
    )

    if st.button("🚀 Run Tool", use_container_width=True):
        if not details.strip():
            st.warning("Please enter your instructions.")
        else:
            try:
                with st.spinner(f"Running {tool}..."):
                    result = run_tool(tool, details)

                st.session_state.tool_result = result
                st.session_state.tool_name = tool
                save_creation("tool", f"{tool}: {details}")

            except Exception as e:
                st.error(str(e))

    if st.session_state.tool_result:
        st.markdown("### ✦ Result")
        st.markdown(st.session_state.tool_result)

        st.download_button(
            "⬇️ Download Result",
            st.session_state.tool_result,
            file_name="nextgen_result.txt"
        )


# =========================================================
# PDF ASSISTANT
# =========================================================

elif page == "PDF Assistant":

    hero(
        "PDF Assistant",
        "Upload a PDF and ask questions about its contents."
    )

    uploaded = st.file_uploader(
        "Upload PDF",
        type=["pdf"]
    )

    if uploaded:
        try:
            from pypdf import PdfReader

            reader = PdfReader(uploaded)
            pdf_text = "\n".join(
                page.extract_text() or ""
                for page in reader.pages
            )

            st.success(
                f"PDF loaded successfully — {len(reader.pages)} pages."
            )

            question = st.text_area(
                "Ask a question about this PDF"
            )

            if st.button("Ask PDF Assistant"):
                if not question.strip():
                    st.warning("Enter a question.")
                else:
                    prompt = (
                        "Answer using the following PDF content.\n\n"
                        + pdf_text[:45000]
                        + "\n\nQuestion: "
                        + question
                    )

                    try:
                        with st.spinner("Analyzing PDF..."):
                            answer, provider = ask_ai([
                                {"role": "user", "content": prompt}
                            ])

                        st.markdown("### Answer")
                        st.markdown(answer)

                    except Exception as e:
                        st.error(str(e))

        except Exception as e:
            st.error(f"Could not read PDF: {e}")


# =========================================================
# CHAT HISTORY
# =========================================================

elif page == "Chat History":

    hero(
        "Chat History",
        "Your previous conversations in one place."
    )

    chats = get_chats()

    if not chats:
        st.info("No conversations yet.")

    for chat in chats:
        col1, col2, col3 = st.columns([6, 2, 1])

        with col1:
            st.markdown(
                f"**{chat['title']}**"
            )
            st.caption(chat["created"])

        with col2:
            if st.button("Open", key=f"open_{chat['id']}"):
                st.session_state.chat_id = chat["id"]
                go("AI Chat")
                st.rerun()

        with col3:
            if st.button("🗑️", key=f"delete_{chat['id']}"):
                delete_chat(chat["id"])
                st.rerun()


# =========================================================
# MY CREATIONS
# =========================================================

elif page == "My Creations":

    hero(
        "My Creations",
        "Your saved AI creation records."
    )

    creations = get_creations()

    if not creations:
        st.info("Your creations will appear here.")

    for item in creations:
        with st.expander(
            f"{item['kind'].upper()} • {item['created']}"
        ):
            st.write(item["content"])


# =========================================================
# SETTINGS
# =========================================================

elif page == "Settings":

    hero(
        "Settings",
        "Manage your NEXTGEN AI workspace."
    )

    panel(
        "🎨",
        "Appearance",
        "NEXTGEN AI uses its dark premium purple-blue interface."
    )

    panel(
        "💬",
        "Chat History",
        "Conversations are stored locally in the SQLite database."
    )

    panel(
        "🤖",
        "AI Providers",
        "Configure Groq and Gemini API keys in environment variables or Streamlit secrets."
    )

    panel(
        "🎙️",
        "Voice",
        "Browser speech playback is available. Full live voice calling requires a streaming voice backend."
    )

    st.markdown("### API Status")

    st.write(
        "Groq:",
        "Connected key found" if GROQ_API_KEY else "API key missing"
    )

    st.write(
        "Gemini:",
        "Connected key found" if GEMINI_API_KEY else "API key missing"
    )

    st.write(
        "Cloudflare:",
        "Configured" if CF_ACCOUNT_ID and CF_API_TOKEN else "Not configured"
    )


# =========================================================
# ABOUT
# =========================================================

elif page == "About":

    hero(
        "Meet the Creator",
        "A young mind with big ideas, a passion for technology "
        "and a vision to build something extraordinary."
    )

    st.markdown("""
    <div class="hero">
        <div class="hero-label">FOUNDER & CREATOR</div>
        <div class="hero-title">ARAV</div>
        <div class="hero-sub">
            Student Developer | AI Enthusiast | Young Innovator
        </div>
    </div>
    """, unsafe_allow_html=True)

    st.markdown("## 👨‍💻 About Arav")

    st.markdown("""
    Arav is a curious and ambitious student who believes that
    learning, creativity and technology can create amazing possibilities.

    He studies at **Swami Vivekanand Shiksha Niketan** and is
    interested in Artificial Intelligence, Python programming,
    application development and modern technology.

    Alongside his studies, he enjoys exploring new ideas,
    experimenting with AI tools and developing creative digital projects.

    He believes that age should never limit curiosity,
    imagination or the desire to learn something new.
    """)

    st.markdown("## 🚀 The Journey")

    st.markdown("""
    The journey of NEXTGEN AI began with an idea:

    **What if multiple useful AI capabilities could come together
    in one beautiful and simple platform?**

    Instead of keeping that idea only in imagination, Arav started
    exploring programming, AI services, APIs and application design.

    Through experimentation, learning and continuous improvement,
    that idea began taking the shape of NEXTGEN AI.
    """)

    st.markdown("## ✦ Skills & Interests")

    skills = [
        ("🤖", "Artificial Intelligence", "Exploring AI assistants and intelligent applications."),
        ("💻", "Python Development", "Learning to build applications and useful software."),
        ("🌐", "Web & App Development", "Creating digital experiences and interactive platforms."),
        ("🎨", "Creative Technology", "Combining imagination, design and technology."),
        ("📚", "Continuous Learning", "Learning new concepts and improving step by step."),
        ("🎬", "Content Creation", "Exploring digital creativity and AI-powered content.")
    ]

    for item in skills:
        panel(*item)

    st.markdown("## 🌟 Vision & Mission")

    st.markdown("""
    The vision behind NEXTGEN AI is to make artificial intelligence
    easier to explore, more useful and accessible through one workspace.

    Arav wants to keep learning, improving his development skills
    and building meaningful technology projects.

    **Dream Big. Learn Every Day. Build Something Amazing.**
    """)

    st.markdown("---")

    st.markdown("""
    <div class="tool-stat">
        <div class="dash-kicker">FOUNDER'S MESSAGE</div>
        <h2 style="color:white;">One idea can start something big.</h2>
        <p class="small-muted">
            NEXTGEN AI is a learning journey, a creative project
            and a vision that grows with every improvement.
        </p>
        <h3 style="color:#bcb2ff;">— Arav</h3>
    </div>
    """, unsafe_allow_html=True)

    st.caption(
        "NEXTGEN AI VERSION MAX © 2026 | Created by Arav"
    )


# =========================================================
# FOOTER
# =========================================================

st.markdown("---")
st.markdown(
    "<center><span style='color:#8996b9;font-size:12px'>"
    "✦ NEXTGEN AI — VERSION MAX • Created by Arav • 2026"
    "</span></center>",
    unsafe_allow_html=True
)
