
import os
import io
import re
import json
import base64
import sqlite3
import zipfile
import requests
import streamlit as st
import streamlit.components.v1 as components

from datetime import datetime, timedelta
from dotenv import load_dotenv

load_dotenv()

# ============================================================
# NEXTGEN AI — COMPLETE PREMIUM WORKSPACE
# ============================================================

st.set_page_config(
    page_title="NEXTGEN AI",
    page_icon="✦",
    layout="wide",
    initial_sidebar_state="expanded"
)

APP_NAME = "NEXTGEN AI"
DB_PATH = os.path.join(
    os.path.dirname(os.path.abspath(__file__)),
    "nextgen_ai_v2.db"
)

GEMINI_KEY = os.getenv("GEMINI_API_KEY", "")
GROQ_KEY = os.getenv("GROQ_API_KEY", "")
FINNHUB_KEY = os.getenv("FINNHUB_API_KEY", "")

CLOUDFLARE_ACCOUNT_ID = os.getenv("CLOUDFLARE_ACCOUNT_ID", "")
CLOUDFLARE_API_TOKEN = os.getenv("CLOUDFLARE_API_TOKEN", "")

GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-3.5-flash")
GROQ_MODEL = os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile")
IMAGE_MODEL = os.getenv(
    "CLOUDFLARE_IMAGE_MODEL",
    "@cf/black-forest-labs/flux-1-schnell"
)

SYSTEM_PROMPT = """
You are NEXTGEN AI, a capable and friendly AI assistant.

Rules:
- Answer in the language used by the user.
- Be accurate, clear, useful and well structured.
- Explain difficult concepts in beginner-friendly language.
- Never invent live data, sources, actions or API results.
- Clearly state uncertainty when information is incomplete.
- For school topics, teach step by step.
- For coding, provide complete and properly formatted code.
- For finance, provide educational information and explain risks.
- Never promise investment returns or guaranteed predictions.
- For creative work, offer original and detailed ideas.
- Never claim to have generated or uploaded a file unless it happened.
"""

# ============================================================
# DATABASE
# ============================================================

def get_db():
    conn = sqlite3.connect(
        DB_PATH,
        timeout=30,
        check_same_thread=False
    )
    conn.execute("PRAGMA busy_timeout = 30000")
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db():
    with get_db() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS chats (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT DEFAULT 'New Chat',
                created_at TEXT
            )
        """)

        conn.execute("""
            CREATE TABLE IF NOT EXISTS messages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                chat_id INTEGER NOT NULL,
                role TEXT NOT NULL,
                content TEXT NOT NULL,
                created_at TEXT,
                FOREIGN KEY(chat_id) REFERENCES chats(id)
                    ON DELETE CASCADE
            )
        """)

        conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_messages_chat
            ON messages(chat_id)
        """)
        conn.commit()


def create_chat(title="New Chat"):
    with get_db() as conn:
        cur = conn.execute(
            "INSERT INTO chats(title, created_at) VALUES(?, ?)",
            (title, datetime.now().isoformat())
        )
        conn.commit()
        return cur.lastrowid


def get_chats():
    with get_db() as conn:
        return conn.execute("""
            SELECT id, title, created_at
            FROM chats ORDER BY id DESC
        """).fetchall()


def get_messages(chat_id):
    with get_db() as conn:
        rows = conn.execute("""
            SELECT role, content FROM messages
            WHERE chat_id = ? ORDER BY id ASC
        """, (chat_id,)).fetchall()

    return [{"role": r, "content": c} for r, c in rows]


def save_message(chat_id, role, content):
    with get_db() as conn:
        conn.execute("""
            INSERT INTO messages(chat_id, role, content, created_at)
            VALUES (?, ?, ?, ?)
        """, (
            chat_id, role, content, datetime.now().isoformat()
        ))
        conn.commit()


def update_chat_title(chat_id, title):
    with get_db() as conn:
        conn.execute(
            "UPDATE chats SET title=? WHERE id=?",
            ((title or "New Chat").strip()[:45], chat_id)
        )
        conn.commit()


def delete_chat(chat_id):
    with get_db() as conn:
        conn.execute("DELETE FROM messages WHERE chat_id=?", (chat_id,))
        conn.execute("DELETE FROM chats WHERE id=?", (chat_id,))
        conn.commit()


init_db()

# ============================================================
# SESSION STATE
# ============================================================

DEFAULTS = {
    "page": "AI Chat",
    "chat_id": None,
    "messages": [],
    "last_answer": "",
    "last_image": None,
    "last_image_prompt": "",
    "market_symbol": "AAPL",
    "market_data": None,
    "analysis_result": "",
    "pdf_result": "",
    "vision_result": "",
    "creative_prompt": "",
    "chat_upload_key": 0,
    "pending_prompt": None,
    "project_files": {},
    "project_name": "my_project",
    "project_type": "Website",
    "project_summary": ""
}

for key, value in DEFAULTS.items():
    if key not in st.session_state:
        st.session_state[key] = value

if st.session_state.chat_id is None:
    st.session_state.chat_id = create_chat()
    st.session_state.messages = []


def switch_chat(chat_id):
    st.session_state.chat_id = chat_id
    st.session_state.messages = get_messages(chat_id)
    st.session_state.page = "AI Chat"


def new_chat():
    st.session_state.chat_id = create_chat()
    st.session_state.messages = []
    st.session_state.page = "AI Chat"
    st.session_state.last_answer = ""


# ============================================================
# DESIGN SYSTEM
# ============================================================

st.markdown("""
<style>
#MainMenu {visibility:hidden;}
footer {visibility:hidden;}
header {visibility:hidden;}

.stApp {
    background: #090b10;
    color: #f5f5f7;
}

[data-testid="stSidebar"] {
    background: #10131b;
    border-right: 1px solid #252a36;
}

[data-testid="stSidebar"] button {
    border-radius: 10px;
}

.main .block-container {
    max-width: 1050px;
    padding-top: 2rem;
    padding-bottom: 2rem;
}

h1, h2, h3 {
    color: #ffffff;
}

.brand {
    font-size: 25px;
    font-weight: 800;
    letter-spacing: 1px;
    color: #ffffff;
}

.brand span {
    color: #8b7cff;
}

.subtitle {
    color: #858b9b;
    font-size: 13px;
}

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
}

.assistant-card {
    background: #101722;
    border: 1px solid #263348;
    border-radius: 17px;
    padding: 17px;
    margin: 12px 0;
}

.stButton button {
    border-radius: 11px;
    border: 1px solid #343b4c;
    background: #171c28;
    color: white;
    min-height: 42px;
}

.stButton button:hover {
    border-color: #8b7cff;
    color: white;
}

[data-testid="stChatInput"] {
    border: 1px solid #45405f;
    border-radius: 18px;
    background: #111522;
}

[data-testid="stChatInput"] textarea {
    color: white !important;
    -webkit-text-fill-color: white !important;
}

section[data-testid="stFileUploader"] {
    background: #121722;
    border-radius: 14px;
    padding: 10px;
}

.market-box {
    background: #141a27;
    border: 1px solid #30384a;
    border-radius: 13px;
    padding: 15px;
}

.small-muted {
    color: #8b91a1;
    font-size: 12px;
}

/* ALL ANSWERS — PURE WHITE */

.stMarkdown,
.stMarkdown *,
[data-testid="stMarkdownContainer"],
[data-testid="stMarkdownContainer"] *,
[data-testid="stChatMessage"],
[data-testid="stChatMessage"] *,
[data-testid="stAlert"] *,
.stCode,
.stCode *,
pre,
pre *,
code,
table,
th,
td {
    color: #FFFFFF !important;
}

.stTextInput input,
.stTextArea textarea {
    color: #FFFFFF !important;
    -webkit-text-fill-color: #FFFFFF !important;
}

.stSelectbox div,
.stRadio label,
.stCheckbox label {
    color: #FFFFFF;
}

[data-testid="stChatInput"] textarea {
    color: #FFFFFF !important;
    -webkit-text-fill-color: #FFFFFF !important;
}

.project-box {
    background: #111827;
    border: 1px solid #30384a;
    border-radius: 15px;
    padding: 16px;
    margin: 10px 0;
}

</style>
""", unsafe_allow_html=True)


# ============================================================
# COMMON UI HELPERS
# ============================================================

def hero(title, subtitle=""):
    st.markdown(f"## {title}")
    if subtitle:
        st.caption(subtitle)
    st.divider()


def safe_error(exc):
    st.error(str(exc)[:700])


def add_chat_message(role, content):
    st.session_state.messages.append({
        "role": role,
        "content": content
    })
    save_message(st.session_state.chat_id, role, content)


def read_aloud(text, key="read"):
    safe_text = json.dumps(str(text))

    components.html(
        f"""
        <div style="padding:5px 0;">
            <button id="read_{key}" style="
                background:#252d42;color:white;
                border:1px solid #414b66;
                border-radius:9px;padding:8px 13px;
                cursor:pointer;">
                🔊 Read Aloud
            </button>
            <script>
            const speechText = {safe_text};
            const btn = document.getElementById("read_{key}");
            btn.onclick = function() {{
                if (!window.speechSynthesis) {{
                    btn.innerText = "Speech unavailable";
                    return;
                }}
                window.speechSynthesis.cancel();
                const utterance = new SpeechSynthesisUtterance(speechText);
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


def render_answer(text, key="answer"):
    st.markdown(text)
    read_aloud(text, key)


# ============================================================
# GROQ AI ENGINE
# ============================================================

def groq_request(messages):
    if not GROQ_KEY:
        raise RuntimeError("GROQ_API_KEY is missing.")

    url = "https://api.groq.com/openai/v1/chat/completions"

    headers = {
        "Authorization": f"Bearer {GROQ_KEY}",
        "Content-Type": "application/json"
    }

    formatted = []

    for msg in messages:
        role = msg.get("role", "user")
        if role not in ("system", "user", "assistant"):
            role = "user"

        formatted.append({
            "role": role,
            "content": str(msg.get("content", ""))
        })

    payload = {
        "model": GROQ_MODEL,
        "messages": formatted,
        "temperature": 0.7,
        "max_tokens": 3500
    }

    response = requests.post(
        url, headers=headers, json=payload, timeout=90
    )
    response.raise_for_status()

    data = response.json()
    answer = data["choices"][0]["message"]["content"]

    if not answer:
        raise RuntimeError("Groq returned an empty answer.")

    return answer


# ============================================================
# GEMINI AI ENGINE
# ============================================================

def gemini_request(messages):
    if not GEMINI_KEY:
        raise RuntimeError("GEMINI_API_KEY is missing.")

    from google import genai

    client = genai.Client(api_key=GEMINI_KEY)
    system_instruction = SYSTEM_PROMPT
    contents = []

    for msg in messages:
        role = msg.get("role", "user")
        content = str(msg.get("content", ""))

        if role == "system":
            system_instruction += "\n" + content
            continue

        contents.append({
            "role": "model" if role == "assistant" else "user",
            "parts": [{"text": content}]
        })

    response = client.models.generate_content(
        model=GEMINI_MODEL,
        contents=contents,
        config={
            "system_instruction": system_instruction,
            "temperature": 0.7
        }
    )

    if not response.text:
        raise RuntimeError("Gemini returned an empty answer.")

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
            errors.append("Groq: " + str(exc)[:220])

    if GEMINI_KEY:
        try:
            return gemini_request(messages)
        except Exception as exc:
            errors.append("Gemini: " + str(exc)[:220])

    if not GROQ_KEY and not GEMINI_KEY:
        return (
            "AI API key missing. Add GROQ_API_KEY or "
            "GEMINI_API_KEY to your .env file."
        )

    raise RuntimeError(" | ".join(errors))


def ask_single(prompt):
    return ask_ai([
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": prompt}
    ])


# ============================================================
# PDF READER
# ============================================================

def read_pdf(uploaded_file):
    from pypdf import PdfReader

    reader = PdfReader(uploaded_file)
    pages = []

    for page in reader.pages:
        page_text = page.extract_text()
        if page_text:
            pages.append(page_text)

    return "\n\n".join(pages)[:45000]


# ============================================================
# VISION — GEMINI IMAGE UNDERSTANDING
# ============================================================

def analyze_image(uploaded_file, prompt):
    if not GEMINI_KEY:
        raise RuntimeError(
            "Image understanding requires GEMINI_API_KEY."
        )

    from google import genai
    from google.genai import types

    client = genai.Client(api_key=GEMINI_KEY)

    image_part = types.Part.from_bytes(
        data=uploaded_file.getvalue(),
        mime_type=uploaded_file.type
    )

    response = client.models.generate_content(
        model=GEMINI_MODEL,
        contents=[prompt, image_part]
    )

    if not response.text:
        raise RuntimeError("No image analysis was returned.")

    return response.text


# ============================================================
# CREATIVE STUDIO — CLOUDFLARE IMAGE GENERATION
# ============================================================

def generate_image(prompt):
    if not CLOUDFLARE_ACCOUNT_ID or not CLOUDFLARE_API_TOKEN:
        raise RuntimeError(
            "Add CLOUDFLARE_ACCOUNT_ID and "
            "CLOUDFLARE_API_TOKEN to enable image generation."
        )

    url = (
        "https://api.cloudflare.com/client/v4/accounts/"
        + CLOUDFLARE_ACCOUNT_ID
        + "/ai/run/"
        + IMAGE_MODEL
    )

    headers = {
        "Authorization": f"Bearer {CLOUDFLARE_API_TOKEN}",
        "Content-Type": "application/json"
    }

    response = requests.post(
        url,
        headers=headers,
        json={"prompt": prompt},
        timeout=120
    )
    response.raise_for_status()

    if "image" in response.headers.get("content-type", ""):
        return response.content

    data = response.json()

    if isinstance(data.get("result"), dict):
        image_data = data["result"].get("image")
        if image_data:
            return base64.b64decode(image_data)

    raise RuntimeError("Image API did not return a supported image.")


# ============================================================
# FINNHUB STOCK DATA
# ============================================================

def finnhub_get(endpoint, params):
    if not FINNHUB_KEY:
        raise RuntimeError("FINNHUB_API_KEY is missing.")

    params = dict(params)
    params["token"] = FINNHUB_KEY

    response = requests.get(
        "https://finnhub.io/api/v1/" + endpoint,
        params=params,
        timeout=25
    )
    response.raise_for_status()
    return response.json()


def get_stock_quote(symbol):
    return finnhub_get("quote", {"symbol": symbol.upper()})


def get_stock_profile(symbol):
    return finnhub_get("stock/profile2", {"symbol": symbol.upper()})


def get_stock_news(symbol):
    end_date = datetime.now().date()
    start_date = end_date - timedelta(days=7)

    return finnhub_get("company-news", {
        "symbol": symbol.upper(),
        "from": start_date.isoformat(),
        "to": end_date.isoformat()
    })


def get_stock_candles(symbol, resolution="D", days=90):
    end_time = int(datetime.now().timestamp())
    start_time = int(
        (datetime.now() - timedelta(days=days)).timestamp()
    )

    return finnhub_get("stock/candle", {
        "symbol": symbol.upper(),
        "resolution": resolution,
        "from": start_time,
        "to": end_time
    })


def money(value):
    try:
        return f"${float(value):,.2f}"
    except (ValueError, TypeError):
        return "N/A"


# ============================================================
# STOCK LEARNING CONTENT
# ============================================================

STOCK_LESSONS = {
    "Stock Market Basics": """
# Stock Market Basics

A stock represents a small ownership share in a company.

- **Stock:** A share of company ownership.
- **Exchange:** A marketplace where securities trade.
- **Ticker:** A short symbol used to identify a company.
- **Shareholder:** A person or institution holding shares.
- **Index:** A group of securities used to track a market.

Buyers and sellers place orders. Prices change as supply,
demand and expectations change.

A rising price does not guarantee future gains.
""",
    "NSE, BSE and Global Markets": """
# NSE, BSE and Global Markets

### India
- NSE: National Stock Exchange.
- BSE: Bombay Stock Exchange.
- NIFTY 50: A major Indian equity index.
- SENSEX: A major BSE index.

### Global examples
- NYSE
- NASDAQ
- S&P 500

Different markets have different trading hours, rules and currencies.
""",
    "Candlestick Charts": """
# Candlestick Charts

Each candle summarizes price movement over a selected time interval.

- Open: Price at the start.
- High: Highest price.
- Low: Lowest price.
- Close: Price at the end.

A candle describes historical activity; it cannot guarantee
what the next price will be.
""",
    "Volume and Liquidity": """
# Volume and Liquidity

**Volume** measures how many shares traded during a period.

**Liquidity** describes how easily something can be bought or sold
without causing a large price change.

High volume does not automatically mean a stock is a good investment.
""",
    "Risk and Diversification": """
# Risk and Diversification

Risk is the possibility that an outcome differs from expectations.

Examples include company risk, market risk, economic risk,
currency risk and liquidity risk.

Diversification spreads exposure. It can reduce some risks,
but cannot remove all risk.
""",
    "Fundamental Analysis": """
# Fundamental Analysis

Fundamental analysis studies a company's business and financial health.

Common topics include revenue, profit, debt, cash flow,
business model, competition, management and valuation.

One financial ratio is not enough to understand a company.
""",
    "Technical Analysis": """
# Technical Analysis

Technical analysis studies historical prices and trading activity.

Common concepts include trend, support and resistance,
moving averages, RSI, volume and volatility.

These tools do not guarantee future price movements.
""",
    "ETFs and Index Funds": """
# ETFs and Index Funds

An ETF is a fund that trades on an exchange.
An index fund aims to track a selected index.

Study what it holds, its costs, tracking difference,
risks and benchmark before evaluating a fund.
"""
}


# ============================================================
# PROJECT BUILDER ENGINE
# ============================================================

def clean_filename(name):
    name = re.sub(r"[^a-zA-Z0-9_-]+", "_", name.strip())
    return name.strip("_")[:50] or "my_project"


def extract_json_object(text):
    text = text.strip()

    text = re.sub(
        r"^```(?:json)?\s*|\s*```$",
        "",
        text,
        flags=re.IGNORECASE
    ).strip()

    start = text.find("{")
    end = text.rfind("}")

    if start == -1 or end == -1:
        raise ValueError("AI did not return a valid project JSON.")

    return json.loads(text[start:end + 1])


def build_project(project_type, name, description, features, style):
    """
    Ask AI for a complete multi-file project.
    The AI must return a JSON object containing files.
    """

    safe_name = clean_filename(name)

    if project_type == "Website":
        instructions = """
Create a complete responsive website project.

Preferred files:
- index.html
- style.css
- script.js
- README.md

Use clean HTML, CSS and JavaScript.
Make navigation, buttons and forms work where appropriate.
Make the layout responsive for mobile and desktop.
Do not use fake claims or fake payment processing.
If a backend is required, explain that separately.
"""
    else:
        instructions = """
Create a complete Python Streamlit application project.

Preferred files:
- app.py
- requirements.txt
- README.md

Include all imports, application code and setup instructions.
Use a clean interface and working interactions.
Do not pretend external APIs are configured.
Put API keys in environment variables, never hardcode secrets.
"""

    prompt = f"""
You are a senior software developer and project architect.

Build a useful, detailed project from the user's brief.

PROJECT TYPE: {project_type}
PROJECT NAME: {safe_name}
USER REQUIREMENTS:
{description}

REQUESTED FEATURES:
{features}

DESIGN PREFERENCE:
{style}

{instructions}

Return ONLY valid JSON in this exact structure:
{{
  "project_name": "{safe_name}",
  "summary": "Short project description",
  "files": {{
    "index.html": "complete file contents",
    "style.css": "complete file contents",
    "script.js": "complete file contents",
    "README.md": "complete file contents"
  }}
}}

For an app, use app.py, requirements.txt and README.md instead.
Include only files relevant to the project type.
Every file must contain complete usable content.
Do not use placeholders such as 'write code here'.
Do not omit important sections.
Escape newlines and quotation marks correctly for valid JSON.
"""

    raw = ask_single(prompt)
    data = extract_json_object(raw)

    files = data.get("files", {})

    if not isinstance(files, dict) or not files:
        raise ValueError("The project response did not contain files.")

    cleaned_files = {}

    for filename, content in files.items():
        filename = str(filename).replace("\\", "/").strip()
        if (
            filename.startswith("/")
            or ".." in filename.split("/")
            or not filename
        ):
            continue

        if isinstance(content, str):
            cleaned_files[filename] = content

    if not cleaned_files:
        raise ValueError("No valid project files were returned.")

    return {
        "project_name": safe_name,
        "summary": str(data.get("summary", "")),
        "files": cleaned_files
    }


def create_project_zip(project):
    memory_file = io.BytesIO()

    with zipfile.ZipFile(
        memory_file,
        "w",
        zipfile.ZIP_DEFLATED
    ) as zip_file:

        for filename, content in project["files"].items():
            zip_file.writestr(
                project["project_name"] + "/" + filename,
                content
            )

    memory_file.seek(0)
    return memory_file.getvalue()


# ============================================================
# SIDEBAR NAVIGATION
# ============================================================

PAGES = {
    "✦ AI Chat": "AI Chat",
    "📈 Stock Market Learning": "Stock Market",
    "🔍 Stock Analysis": "Stock Analysis",
    "👁 Vision": "Vision",
    "🎨 Creative Studio": "Creative Studio",
    "📄 PDF Assistant": "PDF Assistant",
    "🛠 Build Studio": "Build Studio",
    "⚙ Settings": "Settings"
}

with st.sidebar:
    st.markdown(
        '<div class="brand">✦ NEXTGEN <span>AI</span></div>',
        unsafe_allow_html=True
    )
    st.caption("Your intelligent workspace")
    st.divider()

    if st.button("＋  New Chat", use_container_width=True):
        new_chat()
        st.rerun()

    st.markdown("### Workspace")

    for label, page_name in PAGES.items():
        if st.button(
            label,
            key="nav_" + page_name,
            use_container_width=True
        ):
            st.session_state.page = page_name
            st.rerun()

    st.divider()
    st.markdown("### Chat History")

    for cid, title, created in get_chats()[:20]:
        if st.button(
            "◉  " + (title or "New Chat"),
            key=f"history_{cid}",
            use_container_width=True
        ):
            switch_chat(cid)
            st.rerun()

    st.divider()
    st.caption("NEXTGEN AI • Premium Edition")
    st.caption("AI responses may contain errors.")


# ============================================================
# PAGE ROUTER
# ============================================================

page = st.session_state.page


# ============================================================
# AI CHAT
# ============================================================

if page == "AI Chat":
    hero(
        "✦ NEXTGEN AI",
        "Ask anything. Think bigger. Create more."
    )

    if not st.session_state.messages:
        st.markdown("### Welcome to NEXTGEN AI")
        st.write(
            "Your workspace for learning, creativity, "
            "research, coding and everyday questions."
        )

        st.markdown("#### Try asking")

        suggestions = [
            "Explain artificial intelligence simply.",
            "Help me understand a difficult science topic.",
            "Create a professional website in Python.",
            "Give me creative YouTube video ideas."
        ]

        cols = st.columns(2)

        for index, suggestion in enumerate(suggestions):
            with cols[index % 2]:
                if st.button(
                    suggestion,
                    key=f"suggest_{index}",
                    use_container_width=True
                ):
                    st.session_state.pending_prompt = suggestion
                    st.rerun()

    for i, message in enumerate(st.session_state.messages):
        with st.chat_message(
            "user" if message["role"] == "user" else "assistant"
        ):
            st.markdown(message["content"])

            if message["role"] == "assistant":
                read_aloud(message["content"], f"mainchat_{i}")

    uploaded = st.file_uploader(
        "＋ Attach an image or PDF",
        type=["png", "jpg", "jpeg", "webp", "pdf"],
        key=f"chat_file_{st.session_state.chat_upload_key}"
    )

    prompt = st.chat_input("Message NEXTGEN AI...")

    if st.session_state.pending_prompt:
        prompt = st.session_state.pending_prompt
        st.session_state.pending_prompt = None

    if prompt:
        user_content = prompt

        if uploaded:
            user_content += f"\n\n[Attached file: {uploaded.name}]"

        add_chat_message("user", user_content)

        if len(st.session_state.messages) == 1:
            update_chat_title(st.session_state.chat_id, prompt[:40])

        with st.spinner("NEXTGEN AI is thinking..."):
            try:
                if uploaded and uploaded.type == "application/pdf":
                    pdf_text = read_pdf(uploaded)

                    if not pdf_text.strip():
                        raise RuntimeError(
                            "No readable text found in the PDF."
                        )

                    history = [
                        {"role": "system", "content": SYSTEM_PROMPT},
                        {
                            "role": "user",
                            "content": (
                                "Use this PDF to answer the question.\n\n"
                                f"Question: {prompt}\n\n"
                                f"PDF content:\n{pdf_text}"
                            )
                        }
                    ]
                    answer = ask_ai(history)

                elif uploaded and uploaded.type.startswith("image/"):
                    answer = analyze_image(uploaded, prompt)

                else:
                    history = [
                        {"role": "system", "content": SYSTEM_PROMPT}
                    ]

                    for item in st.session_state.messages[:-1]:
                        history.append(item)

                    history.append({
                        "role": "user",
                        "content": prompt
                    })

                    answer = ask_ai(history)

            except Exception as exc:
                answer = "AI Error: " + str(exc)

        add_chat_message("assistant", answer)
        st.session_state.last_answer = answer
        st.rerun()


# ============================================================
# STOCK MARKET LEARNING HUB
# ============================================================

elif page == "Stock Market":
    hero(
        "📈 Stock Market Learning Hub",
        "Learn market concepts, explore charts and understand data."
    )

    st.info(
        "Educational workspace only. This page does not provide "
        "personalized investment instructions."
    )

    tab1, tab2, tab3 = st.tabs([
        "📊 Market Explorer",
        "📚 Learn",
        "🧠 Practice Quiz"
    ])

    with tab1:
        st.markdown("### Explore a Stock")

        symbol = st.text_input(
            "Stock Symbol",
            value=st.session_state.market_symbol,
            key="learning_symbol"
        ).strip().upper()

        period = st.selectbox(
            "Chart period",
            ["1 Month", "3 Months", "6 Months", "1 Year"]
        )

        days_map = {
            "1 Month": 30,
            "3 Months": 90,
            "6 Months": 180,
            "1 Year": 365
        }

        if st.button("Load Market Data"):
            try:
                quote = get_stock_quote(symbol)
                profile = get_stock_profile(symbol)
                candles = get_stock_candles(
                    symbol, "D", days_map[period]
                )

                if candles.get("s") != "ok":
                    raise RuntimeError(
                        "Historical candle data is unavailable."
                    )

                st.session_state.market_symbol = symbol
                st.session_state.market_data = {
                    "quote": quote,
                    "profile": profile,
                    "candles": candles
                }

            except Exception as exc:
                safe_error(exc)

        market = st.session_state.market_data

        if market:
            quote = market["quote"]
            profile = market["profile"]
            candles = market["candles"]

            st.markdown(f"### {profile.get('name', symbol)}")

            c1, c2, c3 = st.columns(3)

            c1.metric("Current Price", money(quote.get("c")))
            c2.metric(
                "Daily Change",
                f"{quote.get('d', 0):.2f}",
                f"{quote.get('dp', 0):.2f}%"
            )
            c3.metric("Previous Close", money(quote.get("pc")))

            import pandas as pd

            chart_df = pd.DataFrame({
                "Date": pd.to_datetime(candles["t"], unit="s"),
                "Open": candles["o"],
                "High": candles["h"],
                "Low": candles["l"],
                "Close": candles["c"],
                "Volume": candles["v"]
            }).set_index("Date")

            st.markdown("### Historical Price Chart")
            st.line_chart(chart_df[["Close"]])

            st.markdown("### Trading Volume")
            st.bar_chart(chart_df[["Volume"]])

            st.markdown("### Recent Historical Data")
            st.dataframe(
                chart_df.tail(15),
                use_container_width=True
            )

            st.caption(
                "Historical data describes the past, not future prices."
            )
        else:
            st.caption("Enter a symbol and load data to explore its chart.")

    with tab2:
        st.markdown("### Learn the Stock Market")

        lesson_name = st.selectbox(
            "Choose a learning topic",
            list(STOCK_LESSONS.keys())
        )

        st.markdown(STOCK_LESSONS[lesson_name])
        st.divider()

        st.markdown("### Ask the AI Teacher")

        learning_question = st.text_area(
            "What would you like to understand?",
            placeholder="Explain candlestick charts with an example."
        )

        if st.button("Explain This Topic"):
            if learning_question.strip():
                try:
                    with st.spinner("Preparing your lesson..."):
                        result = ask_single(
                            "Teach this stock market topic in a "
                            "beginner-friendly educational way. "
                            "Use examples and explain risks.\n\n"
                            + learning_question
                        )
                    render_answer(result, "stock_learning")
                except Exception as exc:
                    safe_error(exc)

    with tab3:
        st.markdown("### Stock Market Basics Quiz")

        questions = [
            (
                "What does a stock represent?",
                [
                    "A share of company ownership",
                    "A bank loan",
                    "A currency note",
                    "A company building"
                ],
                0,
                "A stock represents a share of ownership in a company."
            ),
            (
                "What does volume measure?",
                [
                    "Company age",
                    "Number of shares traded",
                    "Company employees",
                    "Market opening time"
                ],
                1,
                "Volume measures how many shares traded during a period."
            ),
            (
                "What does diversification mean?",
                [
                    "Buying only one stock",
                    "Ignoring risk",
                    "Spreading exposure",
                    "Predicting prices"
                ],
                2,
                "Diversification spreads exposure across investments."
            )
        ]

        answers = []

        for i, question in enumerate(questions):
            answers.append(
                st.radio(
                    question[0],
                    question[1],
                    key=f"stock_quiz_{i}"
                )
            )

        if st.button("Check My Answers"):
            score = 0

            for i, question in enumerate(questions):
                selected_index = question[1].index(answers[i])

                if selected_index == question[2]:
                    score += 1
                    st.success(f"Question {i + 1}: Correct. {question[3]}")
                else:
                    st.warning(
                        f"Question {i + 1}: Correct answer: "
                        f"{question[1][question[2]]}. {question[3]}"
                    )

            st.metric("Your Score", f"{score}/{len(questions)}")


# ============================================================
# STOCK ANALYSIS
# ============================================================

elif page == "Stock Analysis":
    hero(
        "🔍 AI Stock Analysis",
        "Understand company information, news and risk factors."
    )

    st.info(
        "Educational analysis only. Not a personalized buy/sell signal."
    )

    symbol = st.text_input(
        "Company Stock Symbol",
        value="AAPL",
        key="analysis_symbol"
    ).strip().upper()

    if st.button("Run AI Stock Analysis"):
        try:
            with st.spinner("Collecting company information..."):
                quote = get_stock_quote(symbol)
                profile = get_stock_profile(symbol)
                news = get_stock_news(symbol)

            news_text = "\n".join(
                item.get("headline", "") for item in news[:8]
            )

            prompt = f"""
Analyze this company using only supplied information.

Symbol: {symbol}
Company: {profile.get('name', symbol)}
Industry: {profile.get('finnhubIndustry', 'Unknown')}
Country: {profile.get('country', 'Unknown')}
Exchange: {profile.get('exchange', 'Unknown')}

Current quote:
Current: {quote.get('c')}
Change: {quote.get('d')}
Percentage change: {quote.get('dp')}
Previous close: {quote.get('pc')}
Day high: {quote.get('h')}
Day low: {quote.get('l')}

Recent headlines:
{news_text}

Explain:
1. Company overview
2. Quote data meaning
3. Recent news context
4. Possible business and market risks
5. Questions a learner should research
6. Missing information
7. Beginner-friendly summary

Do not invent financial statements or valuation ratios.
Do not guarantee returns or issue a personalized buy/sell instruction.
"""

            with st.spinner("NEXTGEN AI is analyzing..."):
                result = ask_single(prompt)

            st.session_state.analysis_result = result

            st.markdown(f"### {profile.get('name', symbol)}")

            c1, c2, c3 = st.columns(3)
            c1.metric("Current Price", money(quote.get("c")))
            c2.metric(
                "Daily Change",
                f"{quote.get('d', 0):.2f}",
                f"{quote.get('dp', 0):.2f}%"
            )
            c3.metric("Previous Close", money(quote.get("pc")))

            st.markdown("### AI Research Report")
            render_answer(result, "stock_analysis")

            if news:
                st.markdown("### Recent Company Headlines")
                for item in news[:5]:
                    st.markdown(
                        f"- **{item.get('headline', 'Untitled')}** "
                        f"— {item.get('source', 'News source')}"
                    )

        except Exception as exc:
            safe_error(exc)

    elif st.session_state.analysis_result:
        st.markdown("### Previous Analysis")
        render_answer(
            st.session_state.analysis_result,
            "stock_analysis_previous"
        )


# ============================================================
# VISION
# ============================================================

elif page == "Vision":
    hero(
        "👁 AI Vision",
        "Upload an image and ask NEXTGEN AI to understand it."
    )

    image = st.file_uploader(
        "＋ Upload Image",
        type=["png", "jpg", "jpeg", "webp"],
        key="vision_upload"
    )

    question = st.text_area(
        "What should I analyze?",
        placeholder="Describe this image or read visible text."
    )

    if image:
        st.image(image, caption=image.name, use_container_width=True)

        if st.button("Analyze Image"):
            try:
                with st.spinner("Analyzing image..."):
                    result = analyze_image(
                        image,
                        question.strip() or "Describe this image."
                    )

                st.session_state.vision_result = result
                st.markdown("### Vision Result")
                render_answer(result, "vision_result")

            except Exception as exc:
                safe_error(exc)

    elif st.session_state.vision_result:
        st.markdown("### Previous Vision Result")
        render_answer(
            st.session_state.vision_result,
            "vision_previous"
        )


# ============================================================
# CREATIVE STUDIO
# ============================================================

elif page == "Creative Studio":
    hero(
        "🎨 Creative Studio",
        "Create image prompts and generate images."
    )

    tab1, tab2 = st.tabs(["Image Creator", "Prompt Studio"])

    with tab1:
        subject = st.text_input(
            "What do you want to create?",
            placeholder="A futuristic city at sunset"
        )

        style = st.selectbox(
            "Art Style",
            [
                "Photorealistic", "Anime", "Cartoon", "3D Animation",
                "Cinematic", "Watercolor", "Oil Painting",
                "Digital Art", "Fantasy", "Cyberpunk", "Minimalist",
                "Comic Book", "Pixel Art", "Sketch", "Surrealism",
                "Paper Cut Art", "Clay Art", "Low Poly 3D",
                "Vintage Poster", "Neon Art"
            ]
        )

        ratio = st.selectbox(
            "Aspect Ratio",
            [
                "1:1 Square",
                "9:16 Portrait",
                "16:9 Landscape",
                "4:5 Portrait",
                "3:2 Landscape"
            ]
        )

        lighting = st.selectbox(
            "Lighting",
            [
                "Cinematic lighting",
                "Golden hour",
                "Soft natural light",
                "Neon lighting",
                "Studio lighting",
                "Dramatic shadows"
            ]
        )

        quality = st.selectbox(
            "Detail",
            [
                "Highly detailed",
                "Clean and simple",
                "Ultra-detailed textures",
                "Professional composition"
            ]
        )

        extra = st.text_area(
            "Additional details",
            placeholder="Colors, background, mood, camera angle..."
        )

        if st.button("Build Image Prompt"):
            if not subject.strip():
                st.warning("Enter an image subject first.")
            else:
                st.session_state.creative_prompt = (
                    f"{subject}. Art style: {style}. "
                    f"Aspect ratio: {ratio}. Lighting: {lighting}. "
                    f"Quality: {quality}. Additional details: {extra}. "
                    "Original composition, clear subject and careful details."
                )

        if st.session_state.creative_prompt:
            st.markdown("### Your Generated Prompt")
            st.code(st.session_state.creative_prompt)

            if st.button("Generate Image"):
                try:
                    with st.spinner("Creating your image..."):
                        image_bytes = generate_image(
                            st.session_state.creative_prompt
                        )

                    st.session_state.last_image = image_bytes
                    st.session_state.last_image_prompt = (
                        st.session_state.creative_prompt
                    )

                except Exception as exc:
                    safe_error(exc)

        if st.session_state.last_image:
            st.markdown("### Last Creation")
            st.image(
                st.session_state.last_image,
                use_container_width=True
            )
            st.download_button(
                "Download Last Image",
                data=st.session_state.last_image,
                file_name="nextgen_creation.png",
                mime="image/png"
            )

    with tab2:
        st.markdown("### AI Prompt Assistant")

        prompt_goal = st.text_area(
            "Describe your creative idea",
            placeholder="A dramatic thumbnail for a science video."
        )

        if st.button("Improve My Prompt"):
            if prompt_goal.strip():
                try:
                    with st.spinner("Improving prompt..."):
                        improved = ask_single(
                            "Create a detailed professional image "
                            "generation prompt. Include subject, "
                            "composition, lighting, background, style, "
                            "camera perspective and visual details.\n\n"
                            + prompt_goal
                        )

                    st.markdown("### Improved Prompt")
                    render_answer(improved, "improved_prompt")

                except Exception as exc:
                    safe_error(exc)


# ============================================================
# PDF ASSISTANT
# ============================================================

elif page == "PDF Assistant":
    hero(
        "📄 PDF Assistant",
        "Understand documents, extract information and ask questions."
    )

    pdf = st.file_uploader(
        "＋ Upload PDF Document",
        type=["pdf"],
        key="pdf_upload"
    )

    question = st.text_area(
        "Ask a question about this PDF",
        placeholder="Summarize this document or explain a chapter."
    )

    if pdf and st.button("Analyze PDF"):
        try:
            with st.spinner("Reading PDF..."):
                document = read_pdf(pdf)

                if not document.strip():
                    raise RuntimeError(
                        "No readable text was found in this PDF."
                    )

                prompt = f"""
Use the document content below to answer the user's request.

User request:
{question or "Give a clear summary of this PDF."}

Document content:
{document}

Rules:
- Use the document as the main source.
- Do not invent information missing from it.
- Explain difficult terms simply.
- Mention if the document does not contain the answer.
"""

                result = ask_single(prompt)

            st.session_state.pdf_result = result
            st.markdown("### PDF Answer")
            render_answer(result, "pdf_answer")

        except Exception as exc:
            safe_error(exc)

    if st.session_state.pdf_result and not pdf:
        st.markdown("### Previous PDF Answer")
        render_answer(st.session_state.pdf_result, "pdf_previous")


# ============================================================
# BUILD STUDIO — APP BUILDER + WEBSITE BUILDER
# ============================================================

elif page == "Build Studio":
    hero(
        "🛠 Build Studio",
        "Turn your idea into a multi-file software project."
    )

    st.markdown("""
    Build a website or Python app from a written brief.
    NEXTGEN AI will create project files and package them for download.
    """)

    app_tab, web_tab, files_tab = st.tabs([
        "📱 App Builder",
        "🌐 Website Builder",
        "📁 My Project"
    ])

    with app_tab:
        st.markdown("### AI App Builder")

        app_name = st.text_input(
            "App Name",
            value="my_ai_app",
            key="app_builder_name"
        )

        app_description = st.text_area(
            "What should your app do?",
            height=130,
            placeholder=(
                "Example: Build a student productivity app with "
                "tasks, notes, timetable, progress tracking and a "
                "clean dark dashboard."
            ),
            key="app_builder_description"
        )

        app_features = st.text_area(
            "Features you want",
            height=100,
            placeholder=(
                "Login screen, dashboard, notes, search, "
                "database, charts, settings..."
            ),
            key="app_builder_features"
        )

        app_design = st.selectbox(
            "Design Style",
            [
                "Premium dark dashboard",
                "Modern minimal",
                "Light professional",
                "Neon futuristic",
                "Colorful and friendly"
            ],
            key="app_builder_design"
        )

        if st.button(
            "✦ Build My App",
            key="build_app_button",
            use_container_width=True
        ):
            if not app_description.strip():
                st.warning("First describe the app you want to build.")
            else:
                try:
                    with st.spinner(
                        "NEXTGEN AI is planning and building your app..."
                    ):
                        project = build_project(
                            "App",
                            app_name,
                            app_description,
                            app_features,
                            app_design
                        )

                    st.session_state.project_files = project["files"]
                    st.session_state.project_name = project["project_name"]
                    st.session_state.project_type = "App"
                    st.session_state.project_summary = project["summary"]

                    st.success("App project files have been generated.")
                    st.rerun()

                except Exception as exc:
                    safe_error(exc)

    with web_tab:
        st.markdown("### AI Website Builder")

        website_name = st.text_input(
            "Website Name",
            value="my_website",
            key="website_builder_name"
        )

        website_description = st.text_area(
            "Describe your website",
            height=130,
            placeholder=(
                "Example: Create a professional stationery shop "
                "website with homepage, product sections, contact "
                "details, gallery and mobile responsive layout."
            ),
            key="website_builder_description"
        )

        website_features = st.text_area(
            "Website Features",
            height=100,
            placeholder=(
                "Home page, about section, product cards, "
                "contact form, gallery, navigation..."
            ),
            key="website_builder_features"
        )

        website_design = st.selectbox(
            "Website Design",
            [
                "Premium modern",
                "Dark futuristic",
                "Minimal clean",
                "Business professional",
                "Creative colorful",
                "Portfolio style"
            ],
            key="website_builder_design"
        )

        if st.button(
            "✦ Build My Website",
            key="build_website_button",
            use_container_width=True
        ):
            if not website_description.strip():
                st.warning("First describe the website you want.")
            else:
                try:
                    with st.spinner(
                        "NEXTGEN AI is creating your website files..."
                    ):
                        project = build_project(
                            "Website",
                            website_name,
                            website_description,
                            website_features,
                            website_design
                        )

                    st.session_state.project_files = project["files"]
                    st.session_state.project_name = project["project_name"]
                    st.session_state.project_type = "Website"
                    st.session_state.project_summary = project["summary"]

                    st.success("Website project files have been generated.")
                    st.rerun()

                except Exception as exc:
                    safe_error(exc)

    with files_tab:
        st.markdown("### Your Generated Project")

        files = st.session_state.project_files

        if files:
            st.markdown(
                f"**Project:** {st.session_state.project_name}"
            )
            st.markdown(
                f"**Type:** {st.session_state.project_type}"
            )

            if st.session_state.project_summary:
                st.write(st.session_state.project_summary)

            st.divider()
            st.markdown("### Project Files")

            selected_file = st.selectbox(
                "Choose a file to preview",
                list(files.keys())
            )

            st.code(
                files[selected_file],
                language=(
                    "python" if selected_file.endswith(".py")
                    else "html" if selected_file.endswith(".html")
                    else "css" if selected_file.endswith(".css")
                    else "javascript" if selected_file.endswith(".js")
                    else "text"
                )
            )

            zip_bytes = create_project_zip({
                "project_name": st.session_state.project_name,
                "files": files
            })

            st.download_button(
                "⬇ Download Complete Project ZIP",
                data=zip_bytes,
                file_name=st.session_state.project_name + ".zip",
                mime="application/zip",
                use_container_width=True
            )

            st.download_button(
                "⬇ Download Selected File",
                data=files[selected_file],
                file_name=selected_file.split("/")[-1],
                mime="text/plain",
                key="download_selected_project_file"
            )

            st.info(
                "Before publishing, install dependencies, configure "
                "your own API keys, test the project and deploy it "
                "to a suitable hosting service."
            )

        else:
            st.info(
                "Your generated project will appear here. "
                "First create an app or website."
            )


# ============================================================
# SETTINGS
# ============================================================

elif page == "Settings":
    hero(
        "⚙ Settings",
        "Manage your API configuration and workspace information."
    )

    st.markdown("### API Configuration")

    st.write(
        "Gemini API key:",
        "Available" if GEMINI_KEY else "Not configured"
    )
    st.write(
        "Groq API key:",
        "Available" if GROQ_KEY else "Not configured"
    )
    st.write(
        "Finnhub API key:",
        "Available" if FINNHUB_KEY else "Not configured"
    )
    st.write(
        "Cloudflare image API:",
        (
            "Available"
            if CLOUDFLARE_ACCOUNT_ID and CLOUDFLARE_API_TOKEN
            else "Not configured"
        )
    )

    st.divider()
    st.markdown("### Model Configuration")

    st.write("Gemini model:", GEMINI_MODEL)
    st.write("Groq model:", GROQ_MODEL)
    st.write("Image model:", IMAGE_MODEL)

    st.divider()
    st.markdown("### Workspace")

    st.write("Application:", APP_NAME)
    st.write("Database:", "SQLite")
    st.write("Chat history:", "Saved locally in the database")

    st.caption(
        "API keys are loaded from environment variables or your .env file. "
        "Never share your API keys publicly."
    )

    st.divider()

    st.markdown("### Chat Management")

    if st.button("＋ Start a New Chat"):
        new_chat()
        st.rerun()


# ============================================================
# FALLBACK
# ============================================================

else:
    st.session_state.page = "AI Chat"
    st.rerun()


# ============================================================
# FOOTER
# ============================================================

st.divider()

st.caption(
    "✦ NEXTGEN AI • Built for learning, creativity and exploration."
)
