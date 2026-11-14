
import streamlit as st
import streamlit.components.v1 as components
import requests
import json
import io
import os
import re
import html
import sqlite3
import base64
from datetime import datetime

# ============================================================
# NEXTGEN AI — MAX EDITION
# ============================================================

st.set_page_config(
    page_title="NEXTGEN AI",
    page_icon="✦",
    layout="wide",
    initial_sidebar_state="expanded"
)

# ============================================================
# SECRETS CONFIGURATION
# ============================================================

def get_secret(name, default=""):
    try:
        return st.secrets.get(name, default)
    except Exception:
        return default


GROQ_KEY = get_secret("GROQ_API_KEY")
GEMINI_KEY = get_secret("GEMINI_API_KEY")
OPENAI_KEY = get_secret("OPENAI_API_KEY")
TAVILY_KEY = get_secret("TAVILY_API_KEY")

GROQ_MODEL = get_secret(
    "GROQ_MODEL",
    "llama-3.3-70b-versatile"
)

GEMINI_MODEL = get_secret(
    "GEMINI_MODEL",
    "gemini-3.5-flash"
)

OPENAI_MODEL = get_secret(
    "OPENAI_MODEL",
    "gpt-4.1"
)

# ============================================================
# DATABASE
# ============================================================

DB_FILE = "nextgen_ai.db"


def init_db():
    conn = sqlite3.connect(DB_FILE)
    cur = conn.cursor()

    cur.execute("""
        CREATE TABLE IF NOT EXISTS chats (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT,
            created_at TEXT
        )
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS messages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            chat_id INTEGER,
            role TEXT,
            content TEXT,
            created_at TEXT
        )
    """)

    conn.commit()
    conn.close()


def create_chat():
    conn = sqlite3.connect(DB_FILE)
    cur = conn.cursor()

    cur.execute(
        "INSERT INTO chats (title, created_at) VALUES (?, ?)",
        ("New Chat", datetime.now().isoformat())
    )

    chat_id = cur.lastrowid
    conn.commit()
    conn.close()

    return chat_id


def get_chats():
    conn = sqlite3.connect(DB_FILE)
    cur = conn.cursor()

    cur.execute(
        "SELECT id, title FROM chats ORDER BY id DESC"
    )

    result = cur.fetchall()
    conn.close()

    return result


def save_message(chat_id, role, content):
    conn = sqlite3.connect(DB_FILE)
    cur = conn.cursor()

    cur.execute("""
        INSERT INTO messages
        (chat_id, role, content, created_at)
        VALUES (?, ?, ?, ?)
    """, (
        chat_id,
        role,
        content,
        datetime.now().isoformat()
    ))

    conn.commit()
    conn.close()


def get_messages(chat_id):
    conn = sqlite3.connect(DB_FILE)
    cur = conn.cursor()

    cur.execute("""
        SELECT role, content
        FROM messages
        WHERE chat_id = ?
        ORDER BY id ASC
    """, (chat_id,))

    result = cur.fetchall()
    conn.close()

    return [
        {"role": role, "content": content}
        for role, content in result
    ]


def update_chat_title(chat_id, title):
    conn = sqlite3.connect(DB_FILE)
    cur = conn.cursor()

    cur.execute(
        "UPDATE chats SET title = ? WHERE id = ?",
        (title[:45], chat_id)
    )

    conn.commit()
    conn.close()


init_db()

# ============================================================
# SESSION STATE
# ============================================================

if "chat_id" not in st.session_state:
    st.session_state.chat_id = create_chat()

if "messages" not in st.session_state:
    st.session_state.messages = []

if "pending_prompt" not in st.session_state:
    st.session_state.pending_prompt = None

if "last_prompt" not in st.session_state:
    st.session_state.last_prompt = ""

if "liked" not in st.session_state:
    st.session_state.liked = {}

if "page" not in st.session_state:
    st.session_state.page = "Dashboard"

if "uploaded_files" not in st.session_state:
    st.session_state.uploaded_files = []

# ============================================================
# PREMIUM CSS
# ============================================================

st.markdown("""
<style>

@import url(
'https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&display=swap'
);

:root {
    --bg: #080b14;
    --panel: #101625;
    --border: rgba(255,255,255,.09);
    --text: #f4f6ff;
    --muted: #929bb1;
    --accent: #9275ff;
}

html, body, [data-testid="stAppViewContainer"] {
    background: var(--bg);
    color: var(--text);
    font-family: Inter, sans-serif;
}

[data-testid="stHeader"] {
    background: transparent;
}

[data-testid="stSidebar"] {
    background: #0b1020;
    border-right: 1px solid var(--border);
}

.block-container {
    max-width: 1250px;
    padding-top: 2rem;
    padding-bottom: 5rem;
}

.hero {
    padding: 35px;
    border: 1px solid var(--border);
    border-radius: 25px;
    background:
        radial-gradient(
            circle at 90% 10%,
            rgba(117,83,255,.22),
            transparent 40%
        ),
        linear-gradient(135deg,#151c31,#0c1221);
    margin-bottom: 25px;
}

.eyebrow {
    color: #a997ff;
    letter-spacing: 4px;
    font-size: 12px;
    font-weight: 800;
}

.brand {
    font-size: 48px;
    font-weight: 800;
    color: white;
    margin-top: 12px;
    letter-spacing: -2px;
}

.tagline {
    color: #b4bdd0;
    margin-top: 10px;
    font-size: 15px;
}

.stat-card {
    background: #11192b;
    border: 1px solid var(--border);
    border-radius: 17px;
    padding: 20px;
}

.stat-value {
    font-size: 28px;
    font-weight: 800;
    color: white;
}

.stat-label {
    color: var(--muted);
    font-size: 12px;
    margin-top: 5px;
}

.feature-card {
    background: linear-gradient(145deg,#151e32,#0d1424);
    border: 1px solid var(--border);
    padding: 23px;
    border-radius: 18px;
    min-height: 140px;
    transition: .2s;
}

.feature-card:hover {
    border-color: #9275ff;
    transform: translateY(-3px);
}

.feature-icon {
    font-size: 25px;
    margin-bottom: 12px;
}

.feature-title {
    font-size: 16px;
    font-weight: 700;
    color: white;
}

.feature-desc {
    color: #9ba6bc;
    font-size: 12px;
    margin-top: 7px;
}

div[data-testid="stButton"] button {
    border-radius: 12px;
    border: 1px solid var(--border);
    background: #151d30;
    color: white;
    min-height: 40px;
    transition: .2s;
}

div[data-testid="stButton"] button:hover {
    border-color: #9275ff;
    color: white;
    background: #222442;
}

[data-testid="stChatMessage"] {
    background: #111827;
    border: 1px solid var(--border);
    border-radius: 17px;
    padding: 15px;
    margin-bottom: 15px;
}

[data-testid="stChatInput"] {
    border: 1px solid #37335d;
    border-radius: 22px;
}

h1, h2, h3 {
    color: white;
}

.muted {
    color: #929bb1;
}

hr {
    border-color: var(--border);
}

.small-action {
    color: #aeb6c9;
    font-size: 12px;
}

</style>
""", unsafe_allow_html=True)

# ============================================================
# AI PROVIDERS
# ============================================================

def groq_request(messages):

    if not GROQ_KEY:
        raise Exception("Groq API key missing")

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
            "max_tokens": 4096
        },
        timeout=90
    )

    response.raise_for_status()

    return response.json()["choices"][0]["message"]["content"]


def gemini_request(messages):

    if not GEMINI_KEY:
        raise Exception("Gemini API key missing")

    prompt = "\n\n".join(
        f"{m['role'].upper()}: {m['content']}"
        for m in messages
    )

    url = (
        "https://generativelanguage.googleapis.com/"
        f"v1beta/models/{GEMINI_MODEL}:generateContent"
    )

    response = requests.post(
        url,
        params={"key": GEMINI_KEY},
        json={
            "contents": [{
                "parts": [{"text": prompt}]
            }],
            "generationConfig": {
                "temperature": 0.7,
                "maxOutputTokens": 4096
            }
        },
        timeout=90
    )

    response.raise_for_status()

    data = response.json()

    return data["candidates"][0]["content"]["parts"][0]["text"]


def openai_request(messages):

    if not OPENAI_KEY:
        raise Exception("OpenAI API key missing")

    response = requests.post(
        "https://api.openai.com/v1/chat/completions",
        headers={
            "Authorization": f"Bearer {OPENAI_KEY}",
            "Content-Type": "application/json"
        },
        json={
            "model": OPENAI_MODEL,
            "messages": messages,
            "temperature": 0.7,
            "max_tokens": 4096
        },
        timeout=90
    )

    response.raise_for_status()

    return response.json()["choices"][0]["message"]["content"]


def ask_ai(messages):

    errors = []

    providers = [
        groq_request,
        gemini_request,
        openai_request
    ]

    for provider in providers:
        try:
            return provider(messages)
        except Exception as exc:
            errors.append(str(exc)[:250])

    raise Exception(
        "All configured AI providers failed. "
        + " | ".join(errors)
    )

# ============================================================
# SMART WEB SEARCH
# ============================================================

def needs_web_search(query):

    keywords = [
        "latest", "today", "current", "now",
        "news", "price", "weather", "recent",
        "2026", "stock price", "live",
        "अभी", "आज", "ताजा", "लेटेस्ट",
        "वर्तमान", "समाचार", "भाव"
    ]

    return any(
        word in query.lower()
        for word in keywords
    )


def smart_web_search(query):

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
            timeout=25
        )

        response.raise_for_status()

        results = response.json().get("results", [])

        return "\n".join(
            f"- {item['title']}: {item['content']} "
            f"({item['url']})"
            for item in results
        )

    except Exception:
        return ""

# ============================================================
# FILE EXTRACTION
# ============================================================

def extract_file_text(uploaded_file):

    name = uploaded_file.name.lower()

    try:

        if name.endswith(".txt"):
            return uploaded_file.getvalue().decode(
                "utf-8", errors="replace"
            )

        if name.endswith(".pdf"):
            import pypdf

            reader = pypdf.PdfReader(uploaded_file)

            return "\n".join(
                page.extract_text() or ""
                for page in reader.pages
            )

        if name.endswith(".docx"):
            from docx import Document

            document = Document(uploaded_file)

            return "\n".join(
                paragraph.text
                for paragraph in document.paragraphs
            )

    except Exception as exc:
        return f"File extraction error: {exc}"

    return ""

# ============================================================
# RESPONSE ACTIONS
# ============================================================

def response_actions(content, index):

    safe_content = json.dumps(content)

    c1, c2, c3, c4, c5 = st.columns(5)

    with c1:
        st.button(
            "📋",
            key=f"copy_{index}",
            help="Copy response",
            on_click=lambda: st.session_state.update(
                copy_text=content
            )
        )

    with c2:
        st.button(
            "🔊",
            key=f"read_{index}",
            help="Read aloud",
            on_click=lambda: st.session_state.update(
                read_text=content
            )
        )

    with c3:
        st.button(
            "👍",
            key=f"like_{index}",
            help="Like",
            on_click=lambda: st.session_state.liked.update(
                {index: "like"}
            )
        )

    with c4:
        st.button(
            "👎",
            key=f"dislike_{index}",
            help="Dislike",
            on_click=lambda: st.session_state.liked.update(
                {index: "dislike"}
            )
        )

    with c5:
        st.button(
            "↻",
            key=f"regen_{index}",
            help="Regenerate",
            on_click=lambda: st.session_state.update(
                pending_prompt=st.session_state.last_prompt
            )
        )

    if st.session_state.liked.get(index) == "like":
        st.caption("Thanks for your feedback!")

    elif st.session_state.liked.get(index) == "dislike":
        st.caption("Feedback received.")

    if st.session_state.get("copy_text") == content:
        st.code(content, language=None)

    if st.session_state.get("read_text") == content:

        components.html(
            f"""
            <script>
            const text = {safe_content};
            if (window.parent.speechSynthesis) {{
                window.parent.speechSynthesis.cancel();
                let utterance = new SpeechSynthesisUtterance(text);
                utterance.lang = "hi-IN";
                window.parent.speechSynthesis.speak(utterance);
            }}
            </script>
            """,
            height=0
        )

        st.session_state.read_text = None

# ============================================================
# SIDEBAR
# ============================================================

with st.sidebar:

    st.markdown("""
    <div style="padding:10px 5px;">
        <div style="font-size:13px;color:#a997ff;
        letter-spacing:3px;font-weight:800;">
        INTELLIGENT WORKSPACE
        </div>
        <div style="font-size:25px;font-weight:800;
        margin-top:8px;color:white;">
        ✦ NEXTGEN AI
        </div>
    </div>
    """, unsafe_allow_html=True)

    st.divider()

    st.markdown("### Workspace")

    pages = {
        "Dashboard": "⌂",
        "AI Chat": "✦",
        "Stock Market": "▥",
        "Image Studio": "▧",
        "Tool Center": "⚒",
        "App Builder": "⌘",
        "Website Builder": "◇",
        "Learn & Explore": "▤",
        "PDF Assistant": "▧"
    }

    for page, icon in pages.items():

        if st.button(
            f"{icon}  {page}",
            key=f"nav_{page}",
            use_container_width=True
        ):
            st.session_state.page = page
            st.rerun()

    st.divider()

    st.markdown("### Chat History")

    if st.button(
        "＋ New Chat",
        use_container_width=True
    ):
        st.session_state.chat_id = create_chat()
        st.session_state.messages = []
        st.session_state.page = "AI Chat"
        st.rerun()

    for chat_id, title in get_chats()[:30]:

        if st.button(
            f"◦ {title}",
            key=f"history_{chat_id}",
            use_container_width=True
        ):
            st.session_state.chat_id = chat_id
            st.session_state.messages = get_messages(chat_id)
            st.session_state.page = "AI Chat"
            st.rerun()

    st.divider()

    st.markdown("""
    **Account**

    Guest

    <span style="color:#929bb1;font-size:12px;">
    NEXTGEN AI MAX
    </span>
    """, unsafe_allow_html=True)

# ============================================================
# DASHBOARD
# ============================================================

page = st.session_state.page

if page == "Dashboard":

    st.markdown("""
    <div class="hero">
        <div class="eyebrow">INTELLIGENT WORKSPACE</div>
        <div class="brand">NEXTGEN AI</div>
        <div class="tagline">
        Think clearly. Create freely. Learn continuously.
        </div>
    </div>
    """, unsafe_allow_html=True)

    c1, c2, c3 = st.columns(3)

    with c1:
        st.markdown("""
        <div class="stat-card">
            <div class="stat-value">40,000+</div>
            <div class="stat-label">WORKSPACE</div>
        </div>
        """, unsafe_allow_html=True)

    with c2:
        st.markdown("""
        <div class="stat-card">
            <div class="stat-value">MAX</div>
            <div class="stat-label">AI ASSISTANTS</div>
        </div>
        """, unsafe_allow_html=True)

    with c3:
        st.markdown("""
        <div class="stat-card">
            <div class="stat-value">Guest</div>
            <div class="stat-label">ACCOUNT</div>
        </div>
        """, unsafe_allow_html=True)

    st.markdown("## Your workspace")

    descriptions = {
        "AI Chat": (
            "✦",
            "Ask questions, write, learn and solve problems."
        ),
        "Stock Market": (
            "▥",
            "Explore market data and understand price movements."
        ),
        "Image Studio": (
            "▧",
            "Create images and review your generated work."
        ),
        "Tool Center": (
            "⚒",
            "Useful tools for everyday tasks."
        ),
        "App Builder": (
            "⌘",
            "Generate starter code for app ideas."
        ),
        "Website Builder": (
            "◇",
            "Create website layouts and starter files."
        ),
        "Learn & Explore": (
            "▤",
            "Learn technology and new subjects."
        ),
        "PDF Assistant": (
            "▧",
            "Work with supported PDF documents."
        )
    }

    items = list(descriptions.items())

    for start in range(0, len(items), 2):

        cols = st.columns(2)

        for col, (name, details) in zip(
            cols, items[start:start + 2]
        ):

            icon, description = details

            with col:

                st.markdown(
                    f"""
                    <div class="feature-card">
                        <div class="feature-icon">{icon}</div>
                        <div class="feature-title">{name}</div>
                        <div class="feature-desc">
                        {description}
                        </div>
                    </div>
                    """,
                    unsafe_allow_html=True
                )

                if st.button(
                    f"Open {name} →",
                    key=f"open_{name}",
                    use_container_width=True
                ):
                    st.session_state.page = name
                    st.rerun()

# ============================================================
# AI CHAT
# ============================================================

elif page == "AI Chat":

    st.title("✦ AI Chat")
    st.caption(
        "Ask anything. Your intelligent assistant is ready."
    )

    # Display previous messages

    for i, message in enumerate(
        st.session_state.messages
    ):

        with st.chat_message(message["role"]):

            st.markdown(message["content"])

            if message["role"] == "assistant":
                response_actions(
                    message["content"], i
                )

    # Attachment support

    with st.expander("＋ Attach files and images"):

        uploaded = st.file_uploader(
            "Upload your files",
            type=[
                "png", "jpg", "jpeg",
                "pdf", "txt", "docx"
            ],
            accept_multiple_files=True,
            key="chat_upload"
        )

        if uploaded:
            st.session_state.uploaded_files = uploaded

            for file in uploaded:
                st.caption(f"📎 {file.name}")

    # Voice input

    audio = None

    with st.expander("🎙 Voice input"):
        audio = st.audio_input(
            "Record your message",
            key="chat_audio"
        )

        st.caption(
            "Audio recording is available. "
            "Transcription requires a configured speech service."
        )

    if st.session_state.pending_prompt:

        prompt = st.session_state.pending_prompt
        st.session_state.pending_prompt = None

        st.session_state.last_prompt = prompt

        context_messages = [
            {"role": "system", "content":
             "You are NEXTGEN AI, a helpful intelligent assistant. "
             "Give accurate, clear and useful answers."}
        ]

        context_messages.extend(
            st.session_state.messages[:-1]
        )

        context_messages.append({
            "role": "user",
            "content": prompt
        })

        with st.chat_message("assistant"):

            with st.spinner("Thinking..."):

                try:
                    answer = ask_ai(context_messages)

                    st.markdown(answer)

                    st.session_state.messages.append({
                        "role": "assistant",
                        "content": answer
                    })

                    save_message(
                        st.session_state.chat_id,
                        "assistant",
                        answer
                    )

                    response_actions(
                        answer,
                        len(st.session_state.messages) - 1
                    )

                except Exception as exc:
                    st.error(f"AI Error: {exc}")

        st.rerun()

    prompt = st.chat_input(
        "Message NEXTGEN AI...",
        accept_file=True,
        file_type=[
            "png", "jpg", "jpeg",
            "pdf", "txt", "docx"
        ]
    )

    if prompt:

        if hasattr(prompt, "text"):
            user_prompt = prompt.text or ""
            attached = prompt.files or []
        else:
            user_prompt = str(prompt)
            attached = []

        file_context = []

        for file in (
            list(attached)
            + list(st.session_state.uploaded_files)
        ):

            extracted = extract_file_text(file)

            if extracted:
                file_context.append(
                    f"\nFILE: {file.name}\n{extracted[:12000]}"
                )

        if file_context:
            user_prompt += (
                "\n\nUploaded file content:\n"
                + "\n".join(file_context)
            )

        if not user_prompt.strip():
            st.warning("Please enter a message.")
            st.stop()

        st.session_state.last_prompt = user_prompt

        st.session_state.messages.append({
            "role": "user",
            "content": user_prompt
        })

        save_message(
            st.session_state.chat_id,
            "user",
            user_prompt
        )

        if len(st.session_state.messages) == 1:
            update_chat_title(
                st.session_state.chat_id,
                user_prompt[:40]
            )

        web_context = ""

        if needs_web_search(user_prompt):
            web_context = smart_web_search(user_prompt)

        context_messages = [
            {
                "role": "system",
                "content":
                "You are NEXTGEN AI. "
                "Be helpful, accurate and clear. "
                "If web search context is supplied, "
                "use it carefully and distinguish facts "
                "from uncertainty.\n"
                + (
                    "WEB SEARCH CONTEXT:\n" + web_context
                    if web_context else ""
                )
            }
        ]

        context_messages.extend(
            st.session_state.messages[-21:]
        )

        with st.chat_message("user"):
            st.markdown(user_prompt)

        with st.chat_message("assistant"):

            with st.spinner("Thinking..."):

                try:

                    answer = ask_ai(context_messages)

                    st.markdown(answer)

                    st.session_state.messages.append({
                        "role": "assistant",
                        "content": answer
                    })

                    save_message(
                        st.session_state.chat_id,
                        "assistant",
                        answer
                    )

                    response_actions(
                        answer,
                        len(st.session_state.messages) - 1
                    )

                except Exception as exc:
                    st.error(f"AI Error: {exc}")

        st.rerun()

# ============================================================
# STOCK MARKET
# ============================================================

elif page == "Stock Market":

    st.title("▥ Stock Market")
    st.caption("Market insights and AI-powered analysis")

    symbol = st.text_input(
        "Enter stock symbol",
        value="AAPL"
    ).upper().strip()

    period = st.selectbox(
        "Chart period",
        ["1mo", "3mo", "6mo", "1y", "2y"]
    )

    if st.button("Load Stock Chart"):

        try:
            import yfinance as yf

            stock = yf.Ticker(symbol)
            history = stock.history(period=period)

            if history.empty:
                st.warning("No market data found.")
            else:
                st.line_chart(
                    history["Close"],
                    height=350
                )

                st.metric(
                    "Latest Close",
                    f"{history['Close'].iloc[-1]:.2f}"
                )

                st.session_state.stock_data = {
                    "symbol": symbol,
                    "history": history
                }

        except Exception as exc:
            st.error(f"Market data error: {exc}")

    if st.button("✦ Analyze with AI"):

        data = st.session_state.get("stock_data")

        if data:

            history = data["history"]

            information = (
                f"Stock: {data['symbol']}\n"
                f"Recent closing prices:\n"
                f"{history['Close'].tail(10).to_string()}"
            )

            try:
                analysis = ask_ai([
                    {
                        "role": "system",
                        "content":
                        "You are an educational financial analysis assistant. "
                        "Explain trends, risks and uncertainty. "
                        "Never promise returns."
                    },
                    {
                        "role": "user",
                        "content":
                        "Analyze this stock data:\n" + information
                    }
                ])

                st.markdown("### AI Analysis")
                st.markdown(analysis)

            except Exception as exc:
                st.error(str(exc))

        else:
            st.warning("Load a stock chart first.")

    st.info(
        "Stock information is educational, not investment advice."
    )

# ============================================================
# IMAGE STUDIO
# ============================================================

elif page == "Image Studio":

    st.title("▧ Image Studio")

    st.write(
        "Create, upload and review your images."
    )

    image_prompt = st.text_area(
        "Describe your image",
        placeholder="Describe the image you want..."
    )

    st.file_uploader(
        "＋ Upload reference image",
        type=["png", "jpg", "jpeg"]
    )

    st.info(
        "Image generation requires a configured image-generation provider."
    )

    if st.button("Generate Image"):
        st.warning(
            "Connect an image-generation service to enable generation."
        )

# ============================================================
# TOOL CENTER
# ============================================================

elif page == "Tool Center":

    st.title("⚒ Tool Center")

    tool = st.selectbox(
        "Select a tool",
        [
            "Word Counter",
            "Text Case Converter",
            "Calculator",
            "Text Summarizer"
        ]
    )

    if tool == "Word Counter":

        text_input = st.text_area("Enter text")

        if text_input:
            st.metric(
                "Words",
                len(text_input.split())
            )
            st.metric(
                "Characters",
                len(text_input)
            )

    elif tool == "Text Case Converter":

        text_input = st.text_area("Enter text")

        if text_input:
            st.code(text_input.upper())

    elif tool == "Calculator":

        expression = st.text_input(
            "Enter arithmetic expression"
        )

        if st.button("Calculate"):

            try:
                import ast
                import operator

                operations = {
                    ast.Add: operator.add,
                    ast.Sub: operator.sub,
                    ast.Mult: operator.mul,
                    ast.Div: operator.truediv,
                    ast.Pow: operator.pow,
                    ast.USub: operator.neg,
                    ast.UAdd: operator.pos
                }

                def calculate(node):

                    if isinstance(node, ast.Expression):
                        return calculate(node.body)

                    if isinstance(node, ast.Constant):
                        if type(node.value) in (int, float):
                            return node.value

                    if isinstance(node, ast.UnaryOp):
                        op = operations.get(type(node.op))
                        if op:
                            return op(calculate(node.operand))

                    if isinstance(node, ast.BinOp):
                        op = operations.get(type(node.op))
                        if op:
                            return op(
                                calculate(node.left),
                                calculate(node.right)
                            )

                    raise ValueError("Unsupported expression")

                result = calculate(
                    ast.parse(expression, mode="eval")
                )

                st.success(str(result))

            except Exception:
                st.error("Invalid calculation.")

    elif tool == "Text Summarizer":

        content = st.text_area("Enter text to summarize")

        if st.button("Summarize"):

            if content:

                try:
                    result = ask_ai([
                        {
                            "role": "user",
                            "content":
                            "Summarize this text:\n" + content
                        }
                    ])

                    st.markdown(result)

                except Exception as exc:
                    st.error(str(exc))

# ============================================================
# APP BUILDER
# ============================================================

elif page == "App Builder":

    st.title("⌘ App Builder")

    description = st.text_area(
        "Describe your application",
        placeholder="Build a modern AI application..."
    )

    language = st.selectbox(
        "Programming language",
        ["Python", "JavaScript", "HTML/CSS", "React"]
    )

    if st.button("Generate App Code"):

        try:

            result = ask_ai([
                {
                    "role": "system",
                    "content":
                    "You are an expert software developer. "
                    "Generate complete, organized code."
                },
                {
                    "role": "user",
                    "content":
                    f"Build this application using {language}:\n"
                    + description
                }
            ])

            st.markdown(result)

        except Exception as exc:
            st.error(str(exc))

# ============================================================
# WEBSITE BUILDER
# ============================================================

elif page == "Website Builder":

    st.title("◇ Website Builder")

    website_description = st.text_area(
        "Describe your website"
    )

    style = st.selectbox(
        "Website style",
        [
            "Premium Dark",
            "Modern Light",
            "Minimal",
            "Business",
            "Portfolio"
        ]
    )

    if st.button("Generate Website"):

        try:

            result = ask_ai([
                {
                    "role": "system",
                    "content":
                    "You are an expert frontend developer. "
                    "Generate a complete responsive website."
                },
                {
                    "role": "user",
                    "content":
                    f"Create a {style} website:\n"
                    + website_description
                }
            ])

            st.code(result, language="html")

        except Exception as exc:
            st.error(str(exc))

# ============================================================
# LEARN & EXPLORE
# ============================================================

elif page == "Learn & Explore":

    st.title("▤ Learn & Explore")

    subject = st.selectbox(
        "Choose a subject",
        [
            "Science",
            "Mathematics",
            "Computer Science",
            "Artificial Intelligence",
            "Technology",
            "English",
            "General Knowledge"
        ]
    )

    question = st.text_input(
        "What do you want to learn?"
    )

    if st.button("Start Learning"):

        try:

            answer = ask_ai([
                {
                    "role": "system",
                    "content":
                    "You are an excellent teacher. "
                    "Explain concepts step by step with examples."
                },
                {
                    "role": "user",
                    "content":
                    f"Teach me {subject}: {question}"
                }
            ])

            st.markdown(answer)

        except Exception as exc:
            st.error(str(exc))

# ============================================================
# PDF ASSISTANT
# ============================================================

elif page == "PDF Assistant":

    st.title("▧ PDF Assistant")

    pdf = st.file_uploader(
        "Upload a PDF document",
        type=["pdf"]
    )

    if pdf:

        try:

            import pypdf

            reader = pypdf.PdfReader(pdf)

            pdf_text = "\n".join(
                page.extract_text() or ""
                for page in reader.pages
            )

            st.success(
                f"PDF loaded: {len(reader.pages)} pages"
            )

            st.text_area(
                "Extracted text",
                pdf_text[:10000],
                height=180
            )

            question = st.text_input(
                "Ask a question about this PDF"
            )

            if st.button("Ask PDF Assistant"):

                try:

                    result = ask_ai([
                        {
                            "role": "system",
                            "content":
                            "Answer using the supplied PDF content. "
                            "Say when information is not present."
                        },
                        {
                            "role": "user",
                            "content":
                            f"PDF CONTENT:\n{pdf_text[:30000]}\n\n"
                            f"QUESTION:\n{question}"
                        }
                    ])

                    st.markdown(result)

                except Exception as exc:
                    st.error(str(exc))

        except Exception as exc:
            st.error(f"PDF Error: {exc}")

# ============================================================
# FOOTER
# ============================================================

st.markdown("""
<div style="
    text-align:center;
    padding:30px 0;
    color:#737f96;
    font-size:12px;
">
    ✦ NEXTGEN AI MAX EDITION
    <br>
    Think clearly. Create freely. Learn continuously.
</div>
""", unsafe_allow_html=True)
