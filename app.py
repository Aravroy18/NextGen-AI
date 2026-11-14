
import os
import io
import re
import json
import time
import sqlite3
import requests
import streamlit as st
import streamlit.components.v1 as components

from datetime import datetime
from dotenv import load_dotenv

load_dotenv()

# ============================================================
# NEXTGEN AI — PREMIUM EDITION
# ============================================================

st.set_page_config(
    page_title="NEXTGEN AI",
    page_icon="✦",
    layout="wide",
    initial_sidebar_state="expanded"
)

# ============================================================
# API CONFIGURATION
# ============================================================

GEMINI_KEY = os.getenv("GEMINI_API_KEY", "")
GROQ_KEY = os.getenv("GROQ_API_KEY", "")
FINNHUB_KEY = os.getenv("FINNHUB_API_KEY", "")

GEMINI_MODEL = os.getenv(
    "GEMINI_MODEL",
    "gemini-2.5-flash"
)

GROQ_MODEL = os.getenv(
    "GROQ_MODEL",
    "llama-3.3-70b-versatile"
)

# ============================================================
# DATABASE
# ============================================================

DB_PATH = "nextgen_ai.db"


def get_db():
    return sqlite3.connect(DB_PATH)


def init_db():

    with get_db() as conn:

        conn.execute("""
            CREATE TABLE IF NOT EXISTS chats (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT,
                created_at TEXT
            )
        """)

        conn.execute("""
            CREATE TABLE IF NOT EXISTS messages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                chat_id INTEGER,
                role TEXT,
                content TEXT,
                created_at TEXT
            )
        """)


def create_chat():

    with get_db() as conn:

        cur = conn.execute(
            "INSERT INTO chats (title, created_at) VALUES (?, ?)",
            (
                "New Chat",
                datetime.now().isoformat()
            )
        )

        return cur.lastrowid


def get_chats():

    with get_db() as conn:

        return conn.execute(
            "SELECT id, title FROM chats ORDER BY id DESC"
        ).fetchall()


def save_message(chat_id, role, content):

    with get_db() as conn:

        conn.execute(
            """
            INSERT INTO messages
            (chat_id, role, content, created_at)
            VALUES (?, ?, ?, ?)
            """,
            (
                chat_id,
                role,
                content,
                datetime.now().isoformat()
            )
        )


def get_messages(chat_id):

    with get_db() as conn:

        rows = conn.execute(
            """
            SELECT role, content
            FROM messages
            WHERE chat_id = ?
            ORDER BY id ASC
            """,
            (chat_id,)
        ).fetchall()

    return [
        {"role": r, "content": c}
        for r, c in rows
    ]


def update_chat_title(chat_id, title):

    with get_db() as conn:

        conn.execute(
            "UPDATE chats SET title=? WHERE id=?",
            (title[:45], chat_id)
        )


init_db()

# ============================================================
# SESSION STATE
# ============================================================

if "chat_id" not in st.session_state:
    st.session_state.chat_id = create_chat()

if "messages" not in st.session_state:
    st.session_state.messages = []

if "page" not in st.session_state:
    st.session_state.page = "AI Chat"

if "pending_prompt" not in st.session_state:
    st.session_state.pending_prompt = None


def switch_chat(chat_id):

    st.session_state.chat_id = chat_id

    st.session_state.messages = get_messages(chat_id)

    st.session_state.page = "AI Chat"


def new_chat():

    st.session_state.chat_id = create_chat()

    st.session_state.messages = []

    st.session_state.page = "AI Chat"


# ============================================================
# PREMIUM CSS + PURE WHITE ANSWER TEXT
# ============================================================

st.markdown("""
<style>

/* HIDE STREAMLIT DEFAULT ELEMENTS */

#MainMenu {
    visibility: hidden;
}

footer {
    visibility: hidden;
}

header {
    visibility: hidden;
}

/* MAIN APP */

.stApp {
    background: #090b10;
    color: #FFFFFF;
}

/* SIDEBAR */

[data-testid="stSidebar"] {
    background: #10131b;
    border-right: 1px solid #252a36;
}

[data-testid="stSidebar"] button {
    border-radius: 10px;
}

/* MAIN CONTAINER */

.main .block-container {
    max-width: 1050px;
    padding-top: 2rem;
    padding-bottom: 2rem;
}

/* HEADINGS */

h1, h2, h3 {
    color: #FFFFFF !important;
}

/* BRAND */

.brand {
    font-size: 25px;
    font-weight: 800;
    letter-spacing: 1px;
    color: #FFFFFF;
}

.brand span {
    color: #8b7cff !important;
}

/* SUBTITLE */

.subtitle {
    color: #858b9b;
    font-size: 13px;
}

/* CHAT CARDS */

.chat-card {
    background: #121722;
    border: 1px solid #252d3b;
    border-radius: 17px;
    padding: 17px;
    margin: 12px 0;
}

.user-card {
    background: #191d2a;
    border: 1px solid #30364a;
    border-radius: 17px;
    padding: 16px;
    margin: 12px 0;
    color: #FFFFFF !important;
}

.assistant-card {
    background: #101722;
    border: 1px solid #263348;
    border-radius: 17px;
    padding: 17px;
    margin: 12px 0;
    color: #FFFFFF !important;
}

.user-card *,
.assistant-card * {
    color: #FFFFFF !important;
}

/* BUTTONS */

.stButton button {
    border-radius: 11px;
    border: 1px solid #343b4c;
    background: #171c28;
    color: #FFFFFF !important;
    min-height: 42px;
}

.stButton button:hover {
    border-color: #8b7cff;
    color: #FFFFFF !important;
}

/* CHAT INPUT */

[data-testid="stChatInput"] {
    border: 1px solid #45405f;
    border-radius: 18px;
}

[data-testid="stChatInput"] textarea {
    color: #FFFFFF !important;
    -webkit-text-fill-color: #FFFFFF !important;
}

[data-testid="stChatInput"] textarea::placeholder {
    color: #a0a5b2 !important;
    -webkit-text-fill-color: #a0a5b2 !important;
}

/* FILE UPLOADER */

section[data-testid="stFileUploader"] {
    background: #121722;
    border-radius: 14px;
    padding: 10px;
}

/* MARKET BOX */

.market-box {
    background: #141a27;
    border: 1px solid #30384a;
    border-radius: 13px;
    padding: 15px;
}

/* MUTED TEXT */

.small-muted {
    color: #8b91a1;
    font-size: 12px;
}

/* ============================================================
   PURE WHITE FONT — ALL AI ANSWERS
   ============================================================ */

/* ALL MARKDOWN ANSWERS */

.stMarkdown,
.stMarkdown *,
[data-testid="stMarkdownContainer"],
[data-testid="stMarkdownContainer"] * {
    color: #FFFFFF !important;
}

/* CHAT MESSAGES */

[data-testid="stChatMessage"],
[data-testid="stChatMessage"] * {
    color: #FFFFFF !important;
}

/* CHAT ANSWER CONTENT */

[data-testid="stChatMessageContent"],
[data-testid="stChatMessageContent"] * {
    color: #FFFFFF !important;
}

/* PARAGRAPHS AND HEADINGS */

.stMarkdown p,
.stMarkdown span,
.stMarkdown div,
.stMarkdown li,
.stMarkdown h1,
.stMarkdown h2,
.stMarkdown h3,
.stMarkdown h4,
.stMarkdown h5,
.stMarkdown h6,
.stMarkdown strong,
.stMarkdown em,
.stMarkdown blockquote {
    color: #FFFFFF !important;
}

/* TABLES */

.stMarkdown table,
.stMarkdown th,
.stMarkdown td {
    color: #FFFFFF !important;
}

/* CODE */

.stMarkdown pre,
.stMarkdown pre *,
.stMarkdown code,
.stCode,
.stCode * {
    color: #FFFFFF !important;
}

/* LINKS */

.stMarkdown a {
    color: #FFFFFF !important;
    text-decoration: underline;
}

/* ALERT CONTENT */

[data-testid="stAlert"] *,
[data-testid="stNotification"] * {
    color: #FFFFFF !important;
}

/* INPUT TEXT */

.stTextInput input,
.stTextArea textarea {
    color: #FFFFFF !important;
    -webkit-text-fill-color: #FFFFFF !important;
}

/* SELECTED BRAND ACCENT */

.brand span {
    color: #8b7cff !important;
}

</style>
""", unsafe_allow_html=True)


# ============================================================
# GROQ REQUEST
# ============================================================

def groq_request(messages):

    if not GROQ_KEY:
        raise Exception("GROQ_API_KEY is missing")

    url = "https://api.groq.com/openai/v1/chat/completions"

    headers = {
        "Authorization": f"Bearer {GROQ_KEY}",
        "Content-Type": "application/json"
    }

    formatted = []

    for msg in messages:

        formatted.append({
            "role": msg["role"],
            "content": msg["content"]
        })

    payload = {
        "model": GROQ_MODEL,
        "messages": formatted,
        "temperature": 0.7,
        "max_tokens": 3000
    }

    response = requests.post(
        url,
        headers=headers,
        json=payload,
        timeout=60
    )

    response.raise_for_status()

    data = response.json()

    return data["choices"][0]["message"]["content"]


# ============================================================
# GEMINI REQUEST
# ============================================================

def gemini_request(messages):

    if not GEMINI_KEY:
        raise Exception("GEMINI_API_KEY is missing")

    from google import genai

    client = genai.Client(api_key=GEMINI_KEY)

    contents = []

    for msg in messages:

        role = (
            "model"
            if msg["role"] == "assistant"
            else "user"
        )

        contents.append({
            "role": role,
            "parts": [
                {"text": msg["content"]}
            ]
        })

    response = client.models.generate_content(
        model=GEMINI_MODEL,
        contents=contents
    )

    if not response.text:
        raise Exception("Gemini returned an empty response")

    return response.text


# ============================================================
# AI ROUTER
# ============================================================

def ask_ai(messages):

    errors = []

    if GROQ_KEY:

        try:
            return groq_request(messages)

        except Exception as exc:
            errors.append("Groq: " + str(exc)[:200])

    if GEMINI_KEY:

        try:
            return gemini_request(messages)

        except Exception as exc:
            errors.append("Gemini: " + str(exc)[:200])

    if not GROQ_KEY and not GEMINI_KEY:
        return (
            "AI API key missing. Please add GROQ_API_KEY "
            "or GEMINI_API_KEY to your .env file."
        )

    raise Exception(" | ".join(errors))


# ============================================================
# FINNHUB MARKET DATA
# ============================================================

def get_stock_quote(symbol):

    if not FINNHUB_KEY:
        raise Exception("FINNHUB_API_KEY is missing")

    url = "https://finnhub.io/api/v1/quote"

    response = requests.get(
        url,
        params={
            "symbol": symbol.upper(),
            "token": FINNHUB_KEY
        },
        timeout=20
    )

    response.raise_for_status()

    data = response.json()

    if not data.get("c"):
        raise Exception("No stock data available")

    return data


def get_stock_profile(symbol):

    response = requests.get(
        "https://finnhub.io/api/v1/stock/profile2",
        params={
            "symbol": symbol.upper(),
            "token": FINNHUB_KEY
        },
        timeout=20
    )

    response.raise_for_status()

    return response.json()


def get_stock_news(symbol):

    from datetime import timedelta

    end = datetime.now().date()
    start = end - timedelta(days=7)

    response = requests.get(
        "https://finnhub.io/api/v1/company-news",
        params={
            "symbol": symbol.upper(),
            "from": start.isoformat(),
            "to": end.isoformat(),
            "token": FINNHUB_KEY
        },
        timeout=20
    )

    response.raise_for_status()

    return response.json()


# ============================================================
# IMAGE SUPPORT
# ============================================================

def image_request(uploaded_file, prompt):

    if not GEMINI_KEY:
        raise Exception("Gemini API key required for image analysis")

    from google import genai
    from google.genai import types

    client = genai.Client(api_key=GEMINI_KEY)

    image_bytes = uploaded_file.getvalue()

    image_part = types.Part.from_bytes(
        data=image_bytes,
        mime_type=uploaded_file.type
    )

    response = client.models.generate_content(
        model=GEMINI_MODEL,
        contents=[
            prompt,
            image_part
        ]
    )

    return response.text


# ============================================================
# PDF SUPPORT
# ============================================================

def read_pdf(uploaded_file):

    from pypdf import PdfReader

    reader = PdfReader(uploaded_file)

    pages = []

    for page in reader.pages:

        text = page.extract_text()

        if text:
            pages.append(text)

    return "\n".join(pages)[:30000]


# ============================================================
# READ ALOUD
# ============================================================

def read_aloud(text, key):

    safe_text = json.dumps(text)

    components.html(
        f"""
        <div style="
            background:#151b29;
            padding:8px 12px;
            border-radius:10px;
            display:inline-block;
        ">
        <button id="read_{key}" style="
            background:#252d42;
            color:white;
            border:1px solid #414b66;
            border-radius:9px;
            padding:8px 13px;
            cursor:pointer;
        ">🔊 Read Aloud</button>
        <script>
        const text = {safe_text};
        const btn = document.getElementById("read_{key}");

        btn.onclick = function() {{

            if (!window.speechSynthesis) {{
                btn.innerText = "Speech unavailable";
                return;
            }}

            window.speechSynthesis.cancel();

            const utterance = new SpeechSynthesisUtterance(text);

            utterance.lang = "en-IN";
            utterance.rate = 1;

            window.speechSynthesis.speak(utterance);

            btn.innerText = "▶ Speaking...";
            utterance.onend = () => {{
                btn.innerText = "🔊 Read Aloud";
            }};
        }};
        </script>
        </div>
        """,
        height=55
    )


# ============================================================
# SIDEBAR
# ============================================================

with st.sidebar:

    st.markdown(
        '<div class="brand">✦ NEXTGEN <span>AI</span></div>',
        unsafe_allow_html=True
    )

    st.caption("Your intelligent workspace")

    st.divider()

    if st.button(
        "＋  New Chat",
        use_container_width=True
    ):
        new_chat()
        st.rerun()

    st.markdown("### Workspace")

    pages = {
        "✦ AI Chat": "AI Chat",
        "📈 Stock Market": "Stock Market",
        "🔍 Stock Analysis": "Stock Analysis",
        "👁 Vision": "Vision",
        "📄 PDF Assistant": "PDF Assistant",
        "⚙ Settings": "Settings"
    }

    for label, page_name in pages.items():

        if st.button(
            label,
            use_container_width=True,
            key="page_" + page_name
        ):

            st.session_state.page = page_name
            st.rerun()

    st.divider()

    st.markdown("### Chat History")

    chats = get_chats()

    for cid, title in chats:

        if st.button(
            "◉  " + (title or "New Chat"),
            key=f"chat_{cid}",
            use_container_width=True
        ):

            switch_chat(cid)
            st.rerun()

    st.divider()

    st.caption("NEXTGEN AI • Premium Edition")
    st.caption("AI responses can contain errors.")


# ============================================================
# MAIN HEADER
# ============================================================

page = st.session_state.page

if page == "AI Chat":

    st.markdown("## ✦ NEXTGEN AI")

    st.caption(
        "Ask anything. Think bigger. Create more."
    )

    st.divider()

    # DISPLAY MESSAGES

    for i, message in enumerate(st.session_state.messages):

        if message["role"] == "user":

            st.markdown(
                f"""
                <div class="user-card">
                    <b>YOU</b><br><br>
                    {__import__('html').escape(message['content'])}
                </div>
                """,
                unsafe_allow_html=True
            )

        else:

            st.markdown(
                f"""
                <div class="assistant-card">
                    <b>✦ NEXTGEN AI</b><br><br>
                </div>
                """,
                unsafe_allow_html=True
            )

            st.markdown(message["content"])

            read_aloud(
                message["content"],
                f"chat_{st.session_state.chat_id}_{i}"
            )

    # FILE UPLOAD

    uploaded = st.file_uploader(
        "＋ Attach image or PDF",
        type=["png", "jpg", "jpeg", "webp", "pdf"],
        key="chat_upload"
    )

    # CHAT INPUT

    prompt = st.chat_input(
        "Message NEXTGEN AI..."
    )

    if prompt:

        st.session_state.messages.append({
            "role": "user",
            "content": prompt
        })

        save_message(
            st.session_state.chat_id,
            "user",
            prompt
        )

        if len(st.session_state.messages) == 1:

            update_chat_title(
                st.session_state.chat_id,
                prompt[:40]
            )

        with st.spinner("NEXTGEN AI is thinking..."):

            try:

                history = [
                    {
                        "role": "system",
                        "content": (
                            "You are NEXTGEN AI, a helpful, "
                            "accurate and intelligent assistant. "
                            "Answer in the language used by the user. "
                            "Be clear and explain uncertainty."
                        )
                    }
                ]

                for msg in st.session_state.messages[:-1]:
                    history.append(msg)

                history.append({
                    "role": "user",
                    "content": prompt
                })

                answer = ask_ai(history)

            except Exception as exc:

                answer = (
                    "AI Error: " + str(exc)
                )

        st.session_state.messages.append({
            "role": "assistant",
            "content": answer
        })

        save_message(
            st.session_state.chat_id,
            "assistant",
            answer
        )

        st.rerun()


# ============================================================
# STOCK MARKET DASHBOARD
# ============================================================

elif page == "Stock Market":

    st.markdown("## 📈 Global Stock Market")

    st.caption("Market data powered by Finnhub")

    symbol = st.text_input(
        "Search Stock Symbol",
        value="AAPL"
    ).strip().upper()

    if st.button("Get Market Data"):

        try:

            data = get_stock_quote(symbol)

            profile = get_stock_profile(symbol)

            st.markdown(
                f"### {profile.get('name', symbol)}"
            )

            col1, col2, col3 = st.columns(3)

            col1.metric(
                "Current Price",
                f"${data['c']}"
            )

            col2.metric(
                "Change",
                f"{data['d']:.2f}",
                f"{data['dp']:.2f}%"
            )

            col3.metric(
                "Previous Close",
                f"${data['pc']}"
            )

            st.caption(
                "Market data may be delayed. "
                "Verify before making financial decisions."
            )

        except Exception as exc:

            st.error(str(exc))


# ============================================================
# STOCK ANALYSIS
# ============================================================

elif page == "Stock Analysis":

    st.markdown("## 🔍 AI Stock Analysis")

    symbol = st.text_input(
        "Enter Stock Symbol",
        value="AAPL"
    ).strip().upper()

    if st.button("Analyze Stock"):

        try:

            quote = get_stock_quote(symbol)

            profile = get_stock_profile(symbol)

            news = get_stock_news(symbol)

            st.markdown(
                f"### {profile.get('name', symbol)}"
            )

            st.metric(
                "Current Price",
                f"${quote['c']}",
                f"{quote['dp']:.2f}%"
            )

            news_text = "\n".join(
                [
                    n.get("headline", "")
                    for n in news[:5]
                ]
            )

            analysis_prompt = f"""
            Analyze this stock educationally.

            Symbol: {symbol}
            Company: {profile.get('name', symbol)}
            Current price: {quote['c']}
            Change: {quote['d']}
            Percentage change: {quote['dp']}
            Recent news:
            {news_text}

            Explain:
            1. Company overview
            2. Market movement
            3. Potential risks
            4. Important factors to research
            5. Questions an investor should consider.

            Do not guarantee returns or give personalized
            buy/sell instructions.
            """

            with st.spinner("Analyzing..."):

                result = ask_ai([
                    {
                        "role": "user",
                        "content": analysis_prompt
                    }
                ])

            st.markdown(result)

        except Exception as exc:

            st.error(str(exc))


# ============================================================
# VISION
# ============================================================

elif page == "Vision":

    st.markdown("## 👁 AI Vision")

    st.caption(
        "Upload an image and ask NEXTGEN AI about it."
    )

    image = st.file_uploader(
        "Upload Image",
        type=["png", "jpg", "jpeg", "webp"]
    )

    question = st.text_input(
        "What should I analyze?"
    )

    if image:

        st.image(
            image,
            use_container_width=True
        )

        if st.button("Analyze Image"):

            try:

                with st.spinner("Analyzing image..."):

                    result = image_request(
                        image,
                        question or "Describe this image."
                    )

                st.markdown(result)

                read_aloud(result, "vision")

            except Exception as exc:

                st.error(str(exc))


# ============================================================
# PDF ASSISTANT
# ============================================================

elif page == "PDF Assistant":

    st.markdown("## 📄 PDF Assistant")

    pdf = st.file_uploader(
        "Upload PDF",
        type=["pdf"]
    )

    question = st.text_input(
        "Ask something about the PDF"
    )

    if pdf:

        if st.button("Analyze PDF"):

            try:

                with st.spinner("Reading PDF..."):

                    document = read_pdf(pdf)

                    if not document.strip():
                        raise Exception(
                            "No readable text found in PDF."
                        )

                    result = ask_ai([
                        {
                            "role": "user",
                            "content": (
                                "Analyze this PDF and answer "
                                "the question using its contents.\n\n"
                                "Question: "
                                + (
                                    question
                                    or "Summarize this PDF."
                                )
                                + "\n\nPDF CONTENT:\n"
                                + document
                            )
                        }
                    ])

                st.markdown(result)

                read_aloud(result, "pdf")

            except Exception as exc:

                st.error(str(exc))


# ============================================================
# SETTINGS
# ============================================================

elif page == "Settings":

    st.markdown("## ⚙ Settings")

    st.caption("NEXTGEN AI configuration")

    st.markdown("### API Status")

    st.write(
        "Gemini:",
        "Connected" if GEMINI_KEY else "API key missing"
    )

    st.write(
        "Groq:",
        "Connected" if GROQ_KEY else "API key missing"
    )

    st.write(
        "Finnhub:",
        "Connected" if FINNHUB_KEY else "API key missing"
    )

    st.divider()

    st.markdown("### Model Configuration")

    st.write("Gemini Model:", GEMINI_MODEL)

    st.write("Groq Model:", GROQ_MODEL)

    st.divider()

    st.caption(
        "API keys are loaded from your local .env file."
    )

# ============================================================
# END
# ============================================================
