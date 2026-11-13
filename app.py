
import os
import re
import io
import hmac
import hashlib
import secrets
import sqlite3
from datetime import datetime

import streamlit as st
import requests
from dotenv import load_dotenv
from groq import Groq
from PIL import Image
from pypdf import PdfReader

try:
    from google import genai
    from google.genai import types
except ImportError:
    genai = None
    types = None

load_dotenv()

# ================= CONFIG =================

st.set_page_config(
    page_title="NEXTGEN AI",
    page_icon="🚀",
    layout="wide"
)

APP_NAME = "NEXTGEN AI"
DB = "nextgen_users.db"

GROQ_KEY = os.getenv("GROQ_API_KEY", "")
GEMINI_KEY = os.getenv("GEMINI_API_KEY", "")
TAVILY_KEY = os.getenv("TAVILY_API_KEY", "")
FINNHUB_KEY = os.getenv("FINNHUB_API_KEY", "")

GROQ_MODEL = os.getenv(
    "GROQ_MODEL",
    "openai/gpt-oss-120b"
)

GEMINI_MODEL = os.getenv(
    "GEMINI_MODEL",
    "gemini-2.5-flash"
)

# ================= PREMIUM CSS =================

st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800;900&display=swap');

html, body, [class*="css"] {
    font-family: Inter, sans-serif;
}

.stApp {
    background:
    radial-gradient(circle at 10% 0%, #102b40 0%, transparent 35%),
    radial-gradient(circle at 90% 10%, #241442 0%, transparent 35%),
    #080b14;
    color: #f1f5f9;
}

[data-testid="stSidebar"] {
    background: #0c1220;
    border-right: 1px solid #263348;
}

.block-container {
    max-width: 1400px;
    padding-top: 2rem;
}

.hero {
    padding: 30px;
    border-radius: 22px;
    border: 1px solid #29435b;
    background: linear-gradient(120deg, #10283b, #211638);
    margin-bottom: 24px;
}

.hero h1 {
    font-size: 42px;
    font-weight: 900;
}

.gradient {
    background: linear-gradient(90deg, #22d3ee, #a78bfa);
    -webkit-background-clip: text;
    color: transparent;
}

.panel {
    background: #111b2b;
    border: 1px solid #29364b;
    border-radius: 18px;
    padding: 20px;
}

div.stButton > button {
    border-radius: 12px;
    font-weight: 700;
    border: 1px solid #31516b;
}

div.stButton > button[kind="primary"] {
    background: linear-gradient(90deg, #0891b2, #7c3aed);
    border: none;
}

[data-testid="stChatMessage"] {
    background: #111b2b;
    border: 1px solid #29364b;
    border-radius: 16px;
}

.small {
    color: #9caec4;
    font-size: 13px;
}
</style>
""", unsafe_allow_html=True)

# ================= DATABASE =================

def get_db():
    conn = sqlite3.connect(DB)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS users (
            username TEXT PRIMARY KEY,
            salt BLOB NOT NULL,
            password_hash BLOB NOT NULL
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS messages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT,
            role TEXT,
            content TEXT,
            created_at TEXT
        )
    """)
    conn.commit()
    return conn

def hash_password(password, salt):
    return hashlib.pbkdf2_hmac(
        "sha256",
        password.encode(),
        salt,
        200000
    )

def signup(username, password):
    username = username.strip()

    if not re.fullmatch(r"[A-Za-z0-9_]{3,24}", username):
        return False, "Username 3–24 characters का होना चाहिए।"

    if len(password) < 8:
        return False, "Password कम से कम 8 characters का रखें।"

    salt = secrets.token_bytes(16)
    hashed = hash_password(password, salt)

    try:
        with get_db() as conn:
            conn.execute(
                "INSERT INTO users VALUES (?, ?, ?)",
                (username, salt, hashed)
            )
        return True, "Account successfully created!"
    except sqlite3.IntegrityError:
        return False, "Username पहले से मौजूद है।"

def login(username, password):
    with get_db() as conn:
        row = conn.execute(
            "SELECT salt, password_hash FROM users WHERE username=?",
            (username.strip(),)
        ).fetchone()

    if not row:
        return False

    return hmac.compare_digest(
        hash_password(password, row[0]),
        row[1]
    )

def save_message(username, role, content):
    if username == "Guest":
        return

    with get_db() as conn:
        conn.execute(
            """INSERT INTO messages
            (username, role, content, created_at)
            VALUES (?, ?, ?, ?)""",
            (
                username,
                role,
                content,
                datetime.now().isoformat()
            )
        )

def load_history(username):
    if username == "Guest":
        return []

    with get_db() as conn:
        rows = conn.execute(
            """SELECT role, content FROM messages
            WHERE username=? ORDER BY id DESC LIMIT 80""",
            (username,)
        ).fetchall()

    return [
        {"role": role, "content": content}
        for role, content in reversed(rows)
    ]

# ================= AI CLIENTS =================

def get_groq():
    if not GROQ_KEY:
        raise RuntimeError("GROQ_API_KEY .env में नहीं मिली।")
    return Groq(api_key=GROQ_KEY)

def get_gemini():
    if not GEMINI_KEY or genai is None:
        raise RuntimeError("Gemini API key या package उपलब्ध नहीं है।")
    return genai.Client(api_key=GEMINI_KEY)

# ================= AUTOMATIC WEB SEARCH =================

def should_search(query):
    """
    Search only when the question is likely to need fresh information.
    """
    patterns = [
        r"\blatest\b",
        r"\bcurrent\b",
        r"\btoday\b",
        r"\bnow\b",
        r"\b2026\b",
        r"\bnews\b",
        r"\bprice\b",
        r"\bweather\b",
        r"\bschedule\b",
        r"\bscore\b",
        r"\bupdate\b",
        r"\brecent\b",
        r"आज",
        r"अभी",
        r"ताज़ा",
        r"लेटेस्ट",
        r"न्यूज़",
        r"समाचार",
        r"मौसम",
        r"भाव",
        r"कीमत",
        r"अभी का",
        r"वर्तमान",
        r"कब होगा",
        r"कब है",
    ]

    return any(
        re.search(pattern, query, re.IGNORECASE)
        for pattern in patterns
    )

def search_web(query):
    if not TAVILY_KEY:
        return []

    try:
        response = requests.post(
            "https://api.tavily.com/search",
            json={
                "api_key": TAVILY_KEY,
                "query": query,
                "search_depth": "basic",
                "max_results": 5
            },
            timeout=15
        )

        response.raise_for_status()
        data = response.json()

        return data.get("results", [])

    except Exception:
        return []

# ================= CHAT ENGINE =================

def generate_chat(messages):

    latest_question = messages[-1]["content"]

    search_results = []

    if should_search(latest_question):
        search_results = search_web(latest_question)

    system_prompt = """
You are NEXTGEN AI, a premium intelligent assistant.

Rules:
1. Reply in the user's language.
2. Use Hindi in Devanagari when the user writes Hindi.
3. Give fast, accurate and useful answers.
4. Explain school topics at an appropriate student level.
5. Never invent facts, sources or search results.
6. If live search results are supplied, use them carefully.
7. Include source URLs when using search results.
8. If information is uncertain, say so.
"""

    api_messages = [
        {"role": "system", "content": system_prompt}
    ]

    for message in messages[-20:]:
        if message["role"] in ["user", "assistant"]:
            api_messages.append(message)

    if search_results:
        search_context = "\nLIVE WEB SEARCH RESULTS:\n"

        for item in search_results:
            search_context += (
                f"\nTitle: {item.get('title', '')}"
                f"\nURL: {item.get('url', '')}"
                f"\nContent: {item.get('content', '')}\n"
            )

        api_messages.append({
            "role": "system",
            "content": search_context
        })

    response = get_groq().chat.completions.create(
        model=GROQ_MODEL,
        messages=api_messages,
        temperature=0.6,
        max_tokens=1800
    )

    answer = response.choices[0].message.content

    if should_search(latest_question) and not TAVILY_KEY:
        answer += (
            "\n\n*Note: Live Web Search configure नहीं है। "
            "यह उत्तर AI की उपलब्ध जानकारी पर आधारित है।*"
        )

    return answer or "मुझे उत्तर नहीं मिल पाया।"

# ================= LOGIN SCREEN =================

def login_screen():

    st.markdown("""
    <div class="hero">
        <h1>🚀 NEXTGEN <span class="gradient">AI</span></h1>
        <p>Your Creative Universe.</p>
        <p class="small">One Platform. Endless Possibilities.</p>
    </div>
    """, unsafe_allow_html=True)

    login_tab, signup_tab, guest_tab = st.tabs(
        ["Login", "Create Account", "Guest"]
    )

    with login_tab:
        username = st.text_input("Username", key="login_user")
        password = st.text_input(
            "Password",
            type="password",
            key="login_pass"
        )

        if st.button("Login", type="primary"):
            if login(username, password):
                st.session_state.authenticated = True
                st.session_state.username = username.strip()
                st.session_state.messages = load_history(username.strip())
                st.rerun()
            else:
                st.error("Username या password गलत है।")

    with signup_tab:
        username = st.text_input("New username", key="signup_user")
        password = st.text_input(
            "New password",
            type="password",
            key="signup_pass"
        )

        if st.button("Create Account", type="primary"):
            ok, message = signup(username, password)

            if ok:
                st.success(message)
            else:
                st.error(message)

    with guest_tab:
        st.write("बिना account के NEXTGEN AI इस्तेमाल करें।")

        if st.button("Continue as Guest"):
            st.session_state.authenticated = True
            st.session_state.username = "Guest"
            st.session_state.messages = []
            st.rerun()

# ================= PAGE FUNCTIONS =================

def dashboard():

    st.markdown("""
    <div class="hero">
        <h1>Welcome to <span class="gradient">NEXTGEN AI</span></h1>
        <p>Your intelligent workspace starts here.</p>
    </div>
    """, unsafe_allow_html=True)

    cols = st.columns(4)

    labels = [
        ("AI CHAT", "Ready"),
        ("AI VISION", "Image AI"),
        ("PDF AI", "Document AI"),
        ("AI TOOLS", "50 Workflows")
    ]

    for col, item in zip(cols, labels):
        with col:
            st.markdown(
                f'<div class="panel"><h3>{item[0]}</h3>'
                f'<h2>{item[1]}</h2></div>',
                unsafe_allow_html=True
            )

    st.write("")
    st.subheader("✨ Your Workspace")
    st.write(
        "AI Chat · AI Vision · PDF Assistant · Voice Studio · "
        "Stock Market · Video Prompt Studio"
    )

def chat_page():

    st.markdown("""
    <div class="hero">
        <h1>💬 AI <span class="gradient">Chat</span></h1>
        <p>Ask anything. Create anything. Learn anything.</p>
    </div>
    """, unsafe_allow_html=True)

    if st.button("＋ New Chat"):
        st.session_state.messages = []
        st.rerun()

    for message in st.session_state.messages:
        with st.chat_message(message["role"]):
            st.markdown(message["content"])

    prompt = st.chat_input("Message NEXTGEN AI...")

    if prompt:
        user_message = {
            "role": "user",
            "content": prompt
        }

        st.session_state.messages.append(user_message)

        save_message(
            st.session_state.username,
            "user",
            prompt
        )

        with st.chat_message("user"):
            st.markdown(prompt)

        with st.chat_message("assistant"):
            with st.spinner("NEXTGEN AI is thinking..."):
                try:
                    answer = generate_chat(
                        st.session_state.messages
                    )
                    st.markdown(answer)
                except Exception as error:
                    answer = f"Error: {error}"
                    st.error(answer)

        st.session_state.messages.append({
            "role": "assistant",
            "content": answer
        })

        save_message(
            st.session_state.username,
            "assistant",
            answer
        )

def vision_page():

    st.title("👁️ AI Vision")

    uploaded = st.file_uploader(
        "Upload an image",
        type=["png", "jpg", "jpeg", "webp"]
    )

    question = st.text_area(
        "Ask about this image",
        "Describe this image."
    )

    if uploaded:
        image = Image.open(uploaded).convert("RGB")
        st.image(image, use_container_width=True)

        if st.button("Analyze Image", type="primary"):
            try:
                with st.spinner("Analyzing image..."):
                    client = get_gemini()

                    response = client.models.generate_content(
                        model=GEMINI_MODEL,
                        contents=[question, image]
                    )

                    st.markdown(response.text)

            except Exception as error:
                st.error(str(error))

def pdf_page():

    st.title("📄 PDF Assistant")

    uploaded = st.file_uploader(
        "Upload PDF",
        type=["pdf"]
    )

    question = st.text_area(
        "Your question",
        "Summarize this PDF."
    )

    if uploaded and st.button("Analyze PDF", type="primary"):

        try:
            reader = PdfReader(io.BytesIO(uploaded.getvalue()))

            text = "\n".join(
                page.extract_text() or ""
                for page in reader.pages
            )

            if not text.strip():
                st.warning(
                    "PDF में selectable text नहीं मिला। "
                    "यह scanned PDF हो सकती है।"
                )
            else:
                with st.spinner("Reading PDF..."):
                    client = get_gemini()

                    response = client.models.generate_content(
                        model=GEMINI_MODEL,
                        contents=(
                            "Use this PDF text to answer the question.\n\n"
                            + text[:80000]
                            + "\n\nQuestion: "
                            + question
                        )
                    )

                    st.markdown(response.text)

        except Exception as error:
            st.error(str(error))

def voice_page():

    st.title("🎙️ Voice Studio")

    audio = st.audio_input("Record audio")

    if audio and st.button("Analyze Audio"):

        try:
            client = get_gemini()

            audio_part = types.Part.from_bytes(
                data=audio.getvalue(),
                mime_type="audio/wav"
            )

            response = client.models.generate_content(
                model=GEMINI_MODEL,
                contents=[
                    "Transcribe this audio and summarize it.",
                    audio_part
                ]
            )

            st.markdown(response.text)

        except Exception as error:
            st.error(str(error))

def stock_page():

    st.title("📈 Stock Market Explorer")

    if not FINNHUB_KEY:
        st.warning("FINNHUB_API_KEY .env में जोड़ें।")
        return

    symbol = st.text_input("Stock symbol", "AAPL").upper().strip()

    if st.button("Get Stock Data"):

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
                st.error("Quote नहीं मिला।")
                return

            c1, c2, c3 = st.columns(3)

            c1.metric("Current Price", data.get("c"))
            c2.metric("Change", data.get("d"))
            c3.metric("Change %", data.get("dp"))

            st.info(
                "यह educational market information है, "
                "investment advice नहीं।"
            )

        except Exception as error:
            st.error(str(error))

def video_page():

    st.title("🎬 Video Prompt Studio")

    idea = st.text_area("Your video idea")

    duration = st.slider(
        "Duration (seconds)",
        10, 120, 30
    )

    scenes = st.slider(
        "Number of scenes",
        2, 10, 4
    )

    ratio = st.selectbox(
        "Aspect Ratio",
        ["9:16", "16:9", "1:1"]
    )

    style = st.selectbox(
        "Video Style",
        ["Cinematic", "3D Animation", "Anime", "Realistic", "Fantasy"]
    )

    if st.button("Generate Video Plan", type="primary"):

        if not idea.strip():
            st.warning("पहले video idea लिखें।")
            return

        prompt = f"""
Create a professional {duration}-second video.
Aspect ratio: {ratio}
Style: {style}
Number of scenes: {scenes}

Idea:
{idea}

Create {scenes} scenes.
For every scene include:
- Duration
- Visual description
- Camera movement
- Lighting
- Sound effects
- Dialogue or voiceover

Keep character and visual continuity.
Finish with one combined master prompt.
"""

        st.code(prompt, language="text")

        st.download_button(
            "Download Video Prompt",
            prompt,
            "nextgen_video_prompt.txt",
            "text/plain"
        )

        st.caption(
            "यह prompt/storyboard बनाता है, actual video render नहीं।"
        )

def tool_center():

    st.title("🧰 AI Tool Center")

    categories = {
        "Student": [
            "Chapter Notes",
            "Science Tutor",
            "Math Solver",
            "Quiz Maker",
            "Exam Planner"
        ],
        "Creative": [
            "YouTube Script",
            "Video Prompt",
            "Image Prompt",
            "Story Writer",
            "Advertisement"
        ],
        "Development": [
            "Python Helper",
            "Website Builder",
            "Code Reviewer",
            "App Planner"
        ],
        "Productivity": [
            "Summarizer",
            "Translator",
            "Email Writer",
            "Daily Planner"
        ]
    }

    category = st.selectbox(
        "Category",
        list(categories.keys())
    )

    tool = st.selectbox(
        "Choose tool",
        categories[category]
    )

    task = st.text_area("Describe your task")

    if st.button("Generate", type="primary"):

        if not task.strip():
            st.warning("अपना task लिखें।")
            return

        messages = [{
            "role": "user",
            "content": f"Act as {tool}. Help with this task:\n{task}"
        }]

        try:
            with st.spinner("Generating..."):
                st.markdown(generate_chat(messages))
        except Exception as error:
            st.error(str(error))

def about_page():

    st.title("✨ About NEXTGEN AI")

    st.markdown("""
    <div class="panel">
        <h2>One Platform. Endless Possibilities.</h2>
        <p>AI-powered workspace for learning, creativity and productivity.</p>
        <p>Built with Python, Streamlit, Groq, Gemini and Finnhub.</p>
    </div>
    """, unsafe_allow_html=True)

# ================= SESSION STATE =================

if "authenticated" not in st.session_state:
    st.session_state.authenticated = False

if "username" not in st.session_state:
    st.session_state.username = "Guest"

if "messages" not in st.session_state:
    st.session_state.messages = []

# ================= MAIN APP =================

get_db()

if not st.session_state.authenticated:
    login_screen()
    st.stop()

PAGES = {
    "Dashboard": dashboard,
    "AI Chat": chat_page,
    "AI Tool Center": tool_center,
    "Stock Market": stock_page,
    "AI Vision": vision_page,
    "PDF Assistant": pdf_page,
    "Voice Studio": voice_page,
    "Video Prompt Studio": video_page,
    "About": about_page
}

with st.sidebar:

    st.markdown("## 🚀 NEXTGEN AI")
    st.caption("YOUR CREATIVE UNIVERSE")

    st.divider()

    selected = st.radio(
        "WORKSPACE",
        list(PAGES.keys())
    )

    st.divider()

    st.write("👤", st.session_state.username)

    st.caption(
        "AI Chat: " + ("Connected" if GROQ_KEY else "API key missing")
    )

    st.caption(
        "Web Search: " + ("Configured" if TAVILY_KEY else "Not configured")
    )

    if st.button("Logout", use_container_width=True):
        st.session_state.authenticated = False
        st.session_state.username = "Guest"
        st.session_state.messages = []
        st.rerun()

PAGES[selected]()
