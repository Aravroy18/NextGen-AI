
import os
import re
import json
import hmac
import hashlib
import secrets
import sqlite3
from datetime import datetime

import streamlit as st
import requests
from groq import Groq
from PIL import Image
from pypdf import PdfReader

try:
    from google import genai
    from google.genai import types
except ImportError:
    genai = None
    types = None

# ==================================================
# NEXTGEN AI - CONFIGURATION
# API KEYS: STREAMLIT SECRETS
# ==================================================

st.set_page_config(
    page_title="NEXTGEN AI",
    page_icon="🚀",
    layout="wide",
    initial_sidebar_state="expanded"
)

def get_secret(name, default=""):
    try:
        return st.secrets.get(name, default)
    except Exception:
        return os.getenv(name, default)

GROQ_KEY = get_secret("GROQ_API_KEY")
GEMINI_KEY = get_secret("GEMINI_API_KEY")
TAVILY_KEY = get_secret("TAVILY_API_KEY")
FINNHUB_KEY = get_secret("FINNHUB_API_KEY")

GROQ_MODEL = get_secret("GROQ_MODEL", "openai/gpt-oss-120b")
GEMINI_MODEL = get_secret("GEMINI_MODEL", "gemini-2.5-flash")

DB_PATH = "nextgen_users.db"

# ==================================================
# DATABASE
# ==================================================

def db():
    return sqlite3.connect(DB_PATH, check_same_thread=False)

def init_db():
    with db() as con:
        con.execute("""
        CREATE TABLE IF NOT EXISTS users(
            username TEXT PRIMARY KEY,
            salt TEXT NOT NULL,
            password_hash TEXT NOT NULL
        )
        """)
        con.execute("""
        CREATE TABLE IF NOT EXISTS messages(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT NOT NULL,
            role TEXT NOT NULL,
            content TEXT NOT NULL,
            created_at TEXT NOT NULL
        )
        """)

init_db()

def make_hash(password, salt):
    return hashlib.pbkdf2_hmac(
        "sha256", password.encode(), salt.encode(), 200000
    ).hex()

def register(username, password):
    username = username.strip()

    if not re.fullmatch(r"[A-Za-z0-9_]{3,24}", username):
        return False, "Username 3–24 characters का होना चाहिए।"

    if len(password) < 8:
        return False, "Password कम से कम 8 characters का होना चाहिए।"

    salt = secrets.token_hex(16)
    digest = make_hash(password, salt)

    try:
        with db() as con:
            con.execute(
                "INSERT INTO users VALUES(?,?,?)",
                (username, salt, digest)
            )
        return True, "Account created successfully!"
    except sqlite3.IntegrityError:
        return False, "Username पहले से मौजूद है।"

def verify_login(username, password):
    with db() as con:
        row = con.execute(
            "SELECT salt,password_hash FROM users WHERE username=?",
            (username.strip(),)
        ).fetchone()

    if not row:
        return False

    return hmac.compare_digest(
        make_hash(password, row[0]), row[1]
    )

def save_message(username, role, content):
    with db() as con:
        con.execute(
            """INSERT INTO messages
            (username,role,content,created_at)
            VALUES(?,?,?,?)""",
            (
                username,
                role,
                content,
                datetime.now().isoformat(timespec="seconds")
            )
        )

def load_history(username, limit=200):
    with db() as con:
        rows = con.execute(
            """SELECT role,content,created_at
            FROM messages WHERE username=?
            ORDER BY id DESC LIMIT ?""",
            (username, limit)
        ).fetchall()

    return list(reversed(rows))

def clear_history(username):
    with db() as con:
        con.execute(
            "DELETE FROM messages WHERE username=?",
            (username,)
        )

# ==================================================
# PREMIUM UI
# ==================================================

st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&display=swap');

html, body, [class*="css"] {
    font-family: Inter, sans-serif;
}
.stApp {
    background:
      radial-gradient(ellipse at 10% 0%,#18254b,transparent 35%),
      radial-gradient(ellipse at 90% 10%,#251344,transparent 35%),
      #080b14;
    color:#f5f7ff;
}
section[data-testid="stSidebar"] {
    background:#0d1221;
    border-right:1px solid #27304b;
}
.hero {
    padding:28px;
    border:1px solid #303d66;
    border-radius:22px;
    background:linear-gradient(125deg,#18284d,#17142f,#24163b);
    margin-bottom:22px;
}
.hero h1 {
    font-size:40px;
    font-weight:800;
    margin:0;
}
.hero p {color:#c1c9e8;}
.panel {
    padding:20px;
    background:#11182a;
    border:1px solid #273451;
    border-radius:17px;
    margin-bottom:15px;
}
div.stButton > button {
    border-radius:12px;
    border:1px solid #43588c;
    background:linear-gradient(110deg,#315bca,#713ec2);
    color:white;
    font-weight:650;
    min-height:42px;
}
.stTextInput input,.stTextArea textarea {
    background:#10182a;
    color:white;
    border-radius:10px;
}
div[data-testid="stChatMessage"] {
    border:1px solid #273451;
    border-radius:15px;
    background:#101729;
    padding:12px;
}
</style>
""", unsafe_allow_html=True)

def hero(title, subtitle):
    st.markdown(
        f'<div class="hero"><h1>{title}</h1><p>{subtitle}</p></div>',
        unsafe_allow_html=True
    )

# ==================================================
# AUTOMATIC WEB SEARCH
# ==================================================

def should_search(query):
    triggers = [
        "latest", "current", "today", "now", "news",
        "weather", "price", "stock", "live", "score",
        "schedule", "recent", "update", "2026",
        "आज", "अभी", "ताजा", "ताज़ा", "मौसम",
        "कीमत", "शेयर", "खबर", "लेटेस्ट", "वर्तमान",
        "इस सप्ताह", "आज का", "नया अपडेट"
    ]

    q = query.lower()
    return any(word in q for word in triggers)

def search_web(query):
    if not TAVILY_KEY:
        return "Web search API key configured नहीं है।"

    try:
        response = requests.post(
            "https://api.tavily.com/search",
            json={
                "api_key": TAVILY_KEY,
                "query": query,
                "max_results": 5,
                "search_depth": "basic"
            },
            timeout=20
        )

        response.raise_for_status()
        results = response.json().get("results", [])

        if not results:
            return "No useful results found."

        return "\n\n".join(
            f"Title: {x.get('title')}\n"
            f"URL: {x.get('url')}\n"
            f"Content: {x.get('content')}"
            for x in results
        )

    except Exception as e:
        return f"Web search error: {e}"

# ==================================================
# AI ENGINE
# ==================================================

def ask_ai(prompt, history=None, use_web=True, system=None):

    if not GROQ_KEY:
        return "GROQ_API_KEY Secrets में नहीं मिली।"

    if use_web and should_search(prompt):
        results = search_web(prompt)

        prompt += (
            "\n\nWEB SEARCH RESULTS:\n"
            + results
            + "\nUse sources carefully and include source URLs. "
            "If search failed, clearly say current information could not be verified."
        )

    messages = [{
        "role": "system",
        "content": system or (
            "You are NEXTGEN AI, a helpful and accurate AI assistant. "
            "Reply in the user's language. Explain clearly. "
            "Never invent facts or sources."
        )
    }]

    if history:
        messages.extend(history[-12:])

    messages.append({"role": "user", "content": prompt})

    try:
        client = Groq(api_key=GROQ_KEY)

        response = client.chat.completions.create(
            model=GROQ_MODEL,
            messages=messages,
            temperature=0.6,
            max_tokens=1800
        )

        return response.choices[0].message.content or "No response."

    except Exception as e:
        return f"AI Error: {e}"

def gemini_client():
    if not GEMINI_KEY:
        raise RuntimeError("GEMINI_API_KEY Secrets में नहीं मिली।")

    if genai is None:
        raise RuntimeError("google-genai package install नहीं है।")

    return genai.Client(api_key=GEMINI_KEY)

# ==================================================
# SESSION STATE
# ==================================================

if "user" not in st.session_state:
    st.session_state.user = None

if "guest" not in st.session_state:
    st.session_state.guest = False

if "page" not in st.session_state:
    st.session_state.page = "Dashboard"

if "chat" not in st.session_state:
    st.session_state.chat = []

# ==================================================
# LOGIN / SIGNUP
# ==================================================

if not st.session_state.user:

    hero("🚀 NEXTGEN AI", "One Platform. Endless Possibilities.")

    left, right = st.columns(2)

    with left:
        st.markdown("### Your AI Universe")
        st.markdown("""
        - 💬 Intelligent AI Chat
        - 🌐 Automatic Web Search
        - 👁️ AI Vision
        - 📄 PDF Assistant
        - 🎨 AI Image Studio
        - 🎙️ Voice Studio
        - 🎬 Video Prompt Studio
        - 📈 Stock Explorer
        """)

    with right:
        t1, t2, t3 = st.tabs(["Login", "Create Account", "Guest"])

        with t1:
            username = st.text_input("Username", key="login_username")
            password = st.text_input(
                "Password", type="password", key="login_password"
            )

            if st.button("Login", use_container_width=True):
                if verify_login(username, password):
                    st.session_state.user = username.strip()
                    st.rerun()
                else:
                    st.error("Username या password गलत है।")

        with t2:
            new_username = st.text_input("New username")
            new_password = st.text_input(
                "New password", type="password"
            )

            if st.button("Create Account", use_container_width=True):
                ok, message = register(new_username, new_password)
                if ok:
                    st.success(message + " अब Login करो।")
                else:
                    st.error(message)

        with t3:
            if st.button("Continue as Guest"):
                st.session_state.user = "Guest"
                st.session_state.guest = True
                st.rerun()

    st.stop()

USER = st.session_state.user
GUEST = st.session_state.guest

# ==================================================
# SIDEBAR NAVIGATION
# ==================================================

with st.sidebar:

    st.markdown("# 🚀 NEXTGEN AI")
    st.caption("Your Creative Universe")

    pages = [
        "Dashboard",
        "AI Chat",
        "AI Tool Center",
        "AI Vision",
        "PDF Assistant",
        "AI Image Studio",
        "Voice Studio",
        "Stock Market Explorer",
        "Video Prompt Studio",
        "Chat History",
        "About"
    ]

    st.session_state.page = st.radio(
        "NAVIGATION",
        pages,
        index=pages.index(st.session_state.page)
        if st.session_state.page in pages else 0
    )

    st.divider()
    st.write("👤", USER)
    st.caption("API STATUS")
    st.write("Groq:", "🟢" if GROQ_KEY else "🔴")
    st.write("Gemini:", "🟢" if GEMINI_KEY else "🔴")
    st.write("Web Search:", "🟢" if TAVILY_KEY else "🟡")
    st.write("Finnhub:", "🟢" if FINNHUB_KEY else "🔴")

    if st.button("Logout", use_container_width=True):
        st.session_state.user = None
        st.session_state.guest = False
        st.session_state.chat = []
        st.rerun()

page = st.session_state.page

# ==================================================
# DASHBOARD
# ==================================================

if page == "Dashboard":

    hero("NEXTGEN AI 🚀", "One Platform. Endless Possibilities.")

    st.markdown(f"### Welcome, {USER} 👋")
    st.write("Your personal AI workspace is ready.")

    cols = st.columns(4)

    features = [
        ("💬 AI Chat", "Ask anything"),
        ("👁️ AI Vision", "Understand images"),
        ("📄 PDF Assistant", "Read documents"),
        ("🎬 Video Studio", "Build storyboards")
    ]

    for col, (name, description) in zip(cols, features):
        with col:
            st.markdown(
                f'<div class="panel"><h3>{name}</h3><p>{description}</p></div>',
                unsafe_allow_html=True
            )

    st.info("Current questions can trigger automatic web search.")

# ==================================================
# AI CHAT
# ==================================================

elif page == "AI Chat":

    hero("💬 AI Chat", "Talk to your intelligent AI assistant.")

    c1, c2 = st.columns(2)

    with c1:
        if st.button("＋ New Chat"):
            st.session_state.chat = []
            st.rerun()

    with c2:
        if st.button("Clear Visible Chat"):
            st.session_state.chat = []
            st.rerun()

    if not st.session_state.chat and not GUEST:
        old = load_history(USER, 30)
        st.session_state.chat = [
            {"role": r, "content": c}
            for r, c, t in old
        ]

    for message in st.session_state.chat:
        with st.chat_message(message["role"]):
            st.markdown(message["content"])

    prompt = st.chat_input("Message NEXTGEN AI...")

    if prompt:

        st.session_state.chat.append(
            {"role": "user", "content": prompt}
        )

        if not GUEST:
            save_message(USER, "user", prompt)

        with st.chat_message("user"):
            st.markdown(prompt)

        with st.chat_message("assistant"):

            with st.spinner("NEXTGEN AI is thinking..."):

                history = [
                    {"role": m["role"], "content": m["content"]}
                    for m in st.session_state.chat[:-1][-12:]
                ]

                answer = ask_ai(prompt, history)
                st.markdown(answer)

        st.session_state.chat.append(
            {"role": "assistant", "content": answer}
        )

        if not GUEST:
            save_message(USER, "assistant", answer)

        st.rerun()

# ==================================================
# AI TOOL CENTER
# ==================================================

elif page == "AI Tool Center":

    hero("🧰 AI Tool Center", "Tools for learning, creativity and productivity.")

    categories = {
        "Study Assistant": [
            "Explain a topic", "Make short notes",
            "Create quiz questions", "Explain difficult words"
        ],
        "Creative Studio": [
            "YouTube video ideas", "Story generator",
            "Instagram caption", "Video script"
        ],
        "Coding Assistant": [
            "Explain code", "Debug code",
            "Write Python code", "Build website plan"
        ],
        "Productivity": [
            "Make a daily plan", "Write an email",
            "Summarize text", "Generate checklist"
        ]
    }

    category = st.selectbox("Category", list(categories))
    tool = st.selectbox("Choose tool", categories[category])
    content = st.text_area("Your instructions", height=140)

    if st.button("Generate with AI", use_container_width=True):

        if content.strip():

            with st.spinner("Generating..."):
                result = ask_ai(
                    f"Tool: {tool}\nCategory: {category}\nRequest: {content}",
                    use_web=False
                )

            st.markdown("### Result")
            st.markdown(result)

            st.download_button(
                "Download Result",
                result,
                "nextgen_result.txt"
            )

        else:
            st.warning("पहले instructions लिखो।")

# ==================================================
# AI VISION
# ==================================================

elif page == "AI Vision":

    hero("👁️ AI Vision", "Upload an image and ask questions about it.")

    uploaded = st.file_uploader(
        "Upload image",
        type=["png", "jpg", "jpeg", "webp"]
    )

    question = st.text_area(
        "What should AI understand?",
        "Describe this image in detail."
    )

    if uploaded:

        image = Image.open(uploaded).convert("RGB")
        st.image(image, use_container_width=True)

        if st.button("Analyze Image"):

            try:
                client = gemini_client()

                response = client.models.generate_content(
                    model=GEMINI_MODEL,
                    contents=[question, image]
                )

                st.markdown(response.text)

            except Exception as e:
                st.error(str(e))

# ==================================================
# PDF ASSISTANT
# ==================================================

elif page == "PDF Assistant":

    hero("📄 PDF Assistant", "Understand your documents with AI.")

    pdf = st.file_uploader("Upload PDF", type=["pdf"])

    task = st.selectbox(
        "Choose task",
        ["Summarize PDF", "Explain PDF", "Make notes", "Ask questions"]
    )

    question = st.text_area("Your question (optional)")

    if pdf:

        try:
            reader = PdfReader(pdf)

            document = "\n".join(
                p.extract_text() or ""
                for p in reader.pages[:35]
            )

            st.success(f"{len(reader.pages)} pages loaded.")

            if st.button("Process PDF"):

                if document.strip():

                    with st.spinner("Reading PDF..."):

                        result = ask_ai(
                            f"Task: {task}\nQuestion: {question}\nPDF:\n{document[:24000]}",
                            use_web=False
                        )

                    st.markdown(result)

                    st.download_button(
                        "Download Notes",
                        result,
                        "nextgen_pdf_notes.txt"
                    )

                else:
                    st.warning("PDF में readable text नहीं मिला।")

        except Exception as e:
            st.error(str(e))

# ==================================================
# AI IMAGE STUDIO
# ==================================================

elif page == "AI Image Studio":

    hero("🎨 AI Image Studio", "Create professional AI image prompts.")

    subject = st.text_input("Image subject")

    style = st.selectbox(
        "Style",
        ["Cinematic", "Photorealistic", "Anime",
         "3D Render", "Digital Art", "Fantasy", "Minimal"]
    )

    ratio = st.selectbox(
        "Aspect ratio",
        ["1:1", "9:16", "16:9", "4:5"]
    )

    details = st.text_area("Extra details")

    if st.button("Create Image Prompt"):

        if subject.strip():

            prompt = f"""
            Write a detailed image generation prompt.
            Subject: {subject}
            Style: {style}
            Aspect ratio: {ratio}
            Details: {details}
            Include composition, lighting, camera and negative prompt.
            """

            result = ask_ai(prompt, use_web=False)

            st.code(result)

            st.download_button(
                "Download Prompt",
                result,
                "image_prompt.txt"
            )

        else:
            st.warning("Image subject लिखो।")

    st.caption("यह module image prompts बनाता है, actual images generate नहीं करता।")

# ==================================================
# VOICE STUDIO
# ==================================================

elif page == "Voice Studio":

    hero("🎙️ Voice Studio", "Record or upload audio for AI assistance.")

    audio = None

    if hasattr(st, "audio_input"):
        audio = st.audio_input("Record your voice")

    uploaded = st.file_uploader(
        "Or upload audio",
        type=["wav", "mp3", "m4a", "ogg"]
    )

    if audio is None and uploaded is not None:
        audio = uploaded

    task = st.selectbox(
        "Audio task",
        ["Transcribe", "Summarize", "Extract key points"]
    )

    if audio and st.button("Process Audio"):

        try:
            client = gemini_client()

            part = types.Part.from_bytes(
                data=audio.getvalue(),
                mime_type=getattr(audio, "type", None) or "audio/wav"
            )

            response = client.models.generate_content(
                model=GEMINI_MODEL,
                contents=[task + " this audio.", part]
            )

            st.markdown(response.text)

        except Exception as e:
            st.error(str(e))

# ==================================================
# STOCK MARKET EXPLORER
# ==================================================

elif page == "Stock Market Explorer":

    hero("📈 Stock Market Explorer", "Explore stock quotes using Finnhub.")

    symbol = st.text_input("Stock symbol", "AAPL").upper().strip()

    if st.button("Get Stock Quote"):

        if not FINNHUB_KEY:
            st.error("FINNHUB_API_KEY Secrets में नहीं मिली।")

        else:

            try:
                response = requests.get(
                    "https://finnhub.io/api/v1/quote",
                    params={
                        "symbol": symbol,
                        "token": FINNHUB_KEY
                    },
                    timeout=15
                )

                response.raise_for_status()
                data = response.json()

                if not data.get("c"):
                    st.warning("Quote नहीं मिला। Symbol जाँचें।")

                else:

                    a, b, c = st.columns(3)

                    a.metric("Current Price", data["c"])
                    b.metric("Change", data["d"])
                    c.metric("Change %", data["dp"])

                    st.write("High:", data.get("h"))
                    st.write("Low:", data.get("l"))
                    st.write("Open:", data.get("o"))
                    st.write("Previous Close:", data.get("pc"))

                    st.caption(
                        "Market data may be delayed. Educational use only."
                    )

            except Exception as e:
                st.error(str(e))

# ==================================================
# VIDEO PROMPT STUDIO
# ==================================================

elif page == "Video Prompt Studio":

    hero("🎬 Video Prompt Studio", "Create cinematic AI video storyboards.")

    concept = st.text_area("Video concept")

    duration = st.selectbox(
        "Duration",
        ["20 seconds", "30 seconds", "45 seconds",
         "60 seconds", "90 seconds"]
    )

    ratio = st.selectbox(
        "Video format",
        ["9:16 Vertical", "16:9 Landscape", "1:1 Square"]
    )

    language = st.selectbox(
        "Dialogue language",
        ["Hindi", "Hinglish", "English"]
    )

    platform = st.selectbox(
        "Platform",
        ["YouTube Shorts", "Instagram Reels", "YouTube"]
    )

    if st.button("Generate Video Storyboard"):

        if concept.strip():

            prompt = f"""
            Create a complete AI video storyboard.
            Concept: {concept}
            Duration: {duration}
            Format: {ratio}
            Dialogue language: {language}
            Platform: {platform}

            Include:
            1. Opening hook
            2. Scene-by-scene breakdown
            3. Image prompt for every scene
            4. Video animation prompt for every scene
            5. Exact dialogues and voiceover
            6. Camera movement and transitions
            7. Background music and sound effects
            Keep character appearance consistent.
            """

            with st.spinner("Creating storyboard..."):
                result = ask_ai(prompt, use_web=False)

            st.markdown(result)

            st.download_button(
                "Download Storyboard",
                result,
                "video_storyboard.txt"
            )

        else:
            st.warning("पहले video concept लिखो।")

# ==================================================
# CHAT HISTORY & BACKUP
# ==================================================

elif page == "Chat History":

    hero("🗂️ Chat History", "Your saved conversations and backups.")

    if GUEST:

        st.info("Guest messages database में save नहीं होतीं।")

    else:

        history = load_history(USER, 500)

        st.write(f"Total saved messages: {len(history)}")

        for role, content, created in reversed(history):

            with st.expander(f"{role.upper()} • {created}"):
                st.markdown(content)

        if history:

            backup = [
                {
                    "role": r,
                    "content": c,
                    "created_at": t
                }
                for r, c, t in history
            ]

            st.download_button(
                "Download Chat Backup",
                json.dumps(backup, ensure_ascii=False, indent=2),
                "nextgen_chat_backup.json",
                mime="application/json"
            )

        if st.button("Delete All Saved History"):

            clear_history(USER)
            st.session_state.chat = []

            st.success("History deleted.")
            st.rerun()

# ==================================================
# ABOUT
# ==================================================

elif page == "About":

    hero("✨ About NEXTGEN AI", "Your Creative Universe.")

    st.markdown("""
    ### Our Mission
    One platform for AI-powered learning, creativity and productivity.

    ### Features
    - AI Chat with automatic web search
    - AI Vision
    - PDF Assistant
    - AI Image Prompt Studio
    - Voice Studio
    - Stock Market Explorer
    - Video Prompt Studio
    - AI Tool Center
    - Login and saved chat history

    ### Technology
    Python • Streamlit • Groq • Gemini • Tavily • Finnhub • SQLite

    **NEXTGEN AI © 2026**
    """)

st.markdown("---")
st.markdown(
    "<center><small>NEXTGEN AI © 2026 | Built with AI 🚀</small></center>",
    unsafe_allow_html=True
)
