
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
    "nextgen_history.db"
)


# ============================================================
# STREAMLIT SECRETS + ENVIRONMENT
# ============================================================

def get_secret(*names, default=""):
    for name in names:
        try:
            value = st.secrets.get(name)
            if value:
                return str(value)
        except Exception:
            pass

        value = os.getenv(name)
        if value:
            return str(value)

    return default


GROQ_KEY = get_secret("GROQ_API_KEY")
GEMINI_KEY = get_secret("GEMINI_API_KEY")
OPENAI_KEY = get_secret("OPENAI_API_KEY")
ANTHROPIC_KEY = get_secret("ANTHROPIC_API_KEY")

FINNHUB_KEY = get_secret("FINNHUB_API_KEY")
TAVILY_KEY = get_secret("TAVILY_API_KEY")

CLOUDFLARE_ACCOUNT_ID = get_secret("CLOUDFLARE_ACCOUNT_ID")
CLOUDFLARE_API_TOKEN = get_secret("CLOUDFLARE_API_TOKEN")

GROQ_MODEL = get_secret(
    "GROQ_MODEL",
    default="llama-3.3-70b-versatile"
)

GEMINI_MODEL = get_secret(
    "GEMINI_MODEL",
    default="gemini-2.5-flash"
)

OPENAI_MODEL = get_secret(
    "OPENAI_MODEL",
    default="gpt-4.1-mini"
)

ANTHROPIC_MODEL = get_secret(
    "ANTHROPIC_MODEL",
    default="claude-3-5-haiku-latest"
)

IMAGE_MODEL = get_secret(
    "CLOUDFLARE_IMAGE_MODEL",
    default="@cf/black-forest-labs/flux-1-schnell"
)


# ============================================================
# OWNER PROFILE
# ============================================================

OWNER_PROFILE = """
The owner and creator of this AI workspace is Arav Roy.

Known information:
- He studies in Class 7.
- His school is Swami Vivekanand Shiksha Niketan.
- He is interested in Artificial Intelligence.
- He is learning Python and software development.
- He enjoys building AI applications and websites.
- His YouTube project is ARAVYX.
- He is interested in cricket and sports.
- He likes creative technology projects.

When asked who Arav Roy is, describe these known facts
in a positive, respectful and natural way.

Do not invent awards, marks, achievements, qualifications,
personal details or facts that have not been confirmed.
"""

SYSTEM_PROMPT = f"""
You are NEXTGEN AI, an intelligent and helpful AI assistant.

OWNER INFORMATION:
{OWNER_PROFILE}

YOUR RULES:
1. Reply in the language used by the user.
2. Support Hindi and English.
3. Be friendly, accurate and clear.
4. Explain difficult topics step by step.
5. For coding requests, provide complete code when practical.
6. Never invent live information or claim a tool worked if it did not.
7. Be honest about uncertainty and limitations.
8. Keep educational explanations beginner-friendly.
9. Never reveal API keys or secrets.
10. Do not pretend to be ChatGPT or another AI product.

FINANCE:
Give educational explanations only.
Explain risks and uncertainty.
Do not guarantee returns or give personalized buy/sell instructions.

You are NEXTGEN AI, a personal learning and creation assistant.
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
    conn.execute("PRAGMA busy_timeout=30000")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def init_db():
    with get_db() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS chats(
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT,
                created TEXT
            )
        """)

        conn.execute("""
            CREATE TABLE IF NOT EXISTS messages(
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                chat_id INTEGER,
                role TEXT,
                content TEXT,
                created TEXT,
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
            "INSERT INTO chats(title,created) VALUES(?,?)",
            (title, datetime.now().isoformat())
        )
        conn.commit()
        return cur.lastrowid


def get_chats():
    with get_db() as conn:
        return conn.execute("""
            SELECT id,title,created
            FROM chats
            ORDER BY id DESC
        """).fetchall()


def get_messages(chat_id):
    with get_db() as conn:
        rows = conn.execute("""
            SELECT role,content
            FROM messages
            WHERE chat_id=?
            ORDER BY id ASC
        """, (chat_id,)).fetchall()

    return [
        {"role": role, "content": content}
        for role, content in rows
    ]


def save_message(chat_id, role, content):
    with get_db() as conn:
        conn.execute("""
            INSERT INTO messages(chat_id,role,content,created)
            VALUES(?,?,?,?)
        """, (
            chat_id,
            role,
            str(content),
            datetime.now().isoformat()
        ))
        conn.commit()


def update_chat_title(chat_id, title):
    with get_db() as conn:
        conn.execute(
            "UPDATE chats SET title=? WHERE id=?",
            (title[:45], chat_id)
        )
        conn.commit()


def delete_chat(chat_id):
    with get_db() as conn:
        conn.execute(
            "DELETE FROM messages WHERE chat_id=?",
            (chat_id,)
        )
        conn.execute(
            "DELETE FROM chats WHERE id=?",
            (chat_id,)
        )
        conn.commit()


init_db()


# ============================================================
# SESSION STATE
# ============================================================

DEFAULTS = {
    "page": "AI Chat",
    "chat_id": None,
    "messages": [],
    "provider": "Auto",
    "pending_prompt": None,
    "voice_prompt": "",
    "last_image": None,
    "pdf_result": "",
    "vision_result": "",
    "stock_result": None,
    "project_files": {},
    "project_name": "",
    "project_summary": ""
}

for key, value in DEFAULTS.items():
    if key not in st.session_state:
        st.session_state[key] = value

if st.session_state.chat_id is None:
    st.session_state.chat_id = create_chat()
    st.session_state.messages = []


def start_new_chat():
    st.session_state.chat_id = create_chat()
    st.session_state.messages = []
    st.session_state.page = "AI Chat"
    st.session_state.pending_prompt = None
    st.session_state.voice_prompt = ""


def open_chat(chat_id):
    st.session_state.chat_id = chat_id
    st.session_state.messages = get_messages(chat_id)
    st.session_state.page = "AI Chat"
    st.session_state.pending_prompt = None


def add_message(role, content):
    st.session_state.messages.append({
        "role": role,
        "content": str(content)
    })

    save_message(
        st.session_state.chat_id,
        role,
        content
    )


# ============================================================
# PREMIUM UI CSS
# ============================================================

st.markdown("""
<style>
#MainMenu {visibility:hidden;}
footer {visibility:hidden;}
header {visibility:hidden;}

.stApp {
    background:#090b10;
    color:#f7f7fb;
}

[data-testid="stSidebar"] {
    background:#10131b;
    border-right:1px solid #282d3b;
}

[data-testid="stSidebar"] > div:first-child {
    padding-top:1rem;
}

.main .block-container {
    max-width:900px;
    padding-top:2rem;
    padding-bottom:7rem;
}

h1,h2,h3,h4,h5 {
    color:#ffffff !important;
}

p,li,label {
    color:#e8eaf2;
}

[data-testid="stMarkdownContainer"] {
    color:#f5f5f8;
}

[data-testid="stMarkdownContainer"] p,
[data-testid="stMarkdownContainer"] li {
    color:#f0f1f5 !important;
}

[data-testid="stChatMessage"] {
    background:transparent;
    border:0;
    padding-top:1rem;
    padding-bottom:1rem;
}

[data-testid="stChatMessage"] p {
    color:#f5f5f8 !important;
}

.brand {
    font-size:25px;
    font-weight:900;
    letter-spacing:1px;
    color:#ffffff;
}

.brand span {
    color:#9485ff;
}

.small-muted {
    font-size:12px;
    color:#9299aa;
}

.hero {
    background:linear-gradient(120deg,#19192c,#111c2d);
    border:1px solid #343750;
    padding:23px;
    border-radius:19px;
    margin-bottom:20px;
}

.stButton button {
    background:#191e2c;
    color:#ffffff;
    border:1px solid #343b50;
    border-radius:12px;
    min-height:40px;
}

.stButton button:hover {
    background:#292642;
    border-color:#8176e8;
    color:white;
}

[data-testid="stChatInput"] {
    background:#151927;
    border:1px solid #514b75;
    border-radius:24px;
    box-shadow:0 5px 25px rgba(0,0,0,.28);
    padding:5px 10px;
}

[data-testid="stChatInput"] textarea {
    color:#ffffff !important;
    -webkit-text-fill-color:#ffffff !important;
}

.stTextInput input,
.stTextArea textarea {
    color:#ffffff !important;
    -webkit-text-fill-color:#ffffff !important;
    background:#151927 !important;
    border-radius:12px !important;
}

.stSelectbox div {
    color:#ffffff;
}

.stFileUploader {
    background:#131927;
    border-radius:13px;
}

.panel {
    background:#141a27;
    border:1px solid #30394a;
    border-radius:15px;
    padding:18px;
    margin:10px 0;
}

[data-testid="stMetric"] {
    background:#141a27;
    padding:14px;
    border-radius:12px;
    border:1px solid #30394a;
}

hr {
    border-color:#303547;
}

[data-testid="stSidebar"] [data-testid="stMarkdownContainer"] p {
    color:#e8eaf2 !important;
}

</style>
""", unsafe_allow_html=True)


# ============================================================
# COMMON UI HELPERS
# ============================================================

def hero(title, subtitle=""):
    st.markdown(
        f"""
        <div class="hero">
            <h2>{title}</h2>
            <div class="small-muted">{subtitle}</div>
        </div>
        """,
        unsafe_allow_html=True
    )


def show_error(error):
    st.error(str(error)[:900])


def read_aloud(text, key="read"):
    safe_text = json.dumps(str(text))
    safe_key = re.sub(r"[^a-zA-Z0-9_]", "_", str(key))

    html_code = """
    <button id="read___ID__" style="
        background:#20283a;
        color:white;
        padding:8px 13px;
        border:1px solid #505b7b;
        border-radius:18px;
        cursor:pointer;">
        🔊 Read aloud
    </button>

    <script>
    const textValue = __TEXT__;
    const button = document.getElementById("read___ID__");

    button.onclick = function() {
        if (!window.speechSynthesis) {
            button.innerText = "Speech unavailable";
            return;
        }

        window.speechSynthesis.cancel();

        const speech = new SpeechSynthesisUtterance(textValue);

        speech.lang = /[\\u0900-\\u097F]/.test(textValue)
            ? "hi-IN" : "en-IN";

        speech.rate = 1;
        window.speechSynthesis.speak(speech);

        button.innerText = "Speaking...";

        speech.onend = function() {
            button.innerText = "🔊 Read aloud";
        };
    };
    </script>
    """

    html_code = html_code.replace("__TEXT__", safe_text)
    html_code = html_code.replace("__ID__", safe_key)

    components.html(html_code, height=48)


def render_answer(answer, key="answer"):
    st.markdown(answer)
    read_aloud(answer, key)


# ============================================================
# GROQ
# ============================================================

def groq_request(messages):
    if not GROQ_KEY:
        raise RuntimeError("Groq API key missing.")

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
            "max_tokens": 5000
        },
        timeout=90
    )

    response.raise_for_status()

    data = response.json()
    answer = data["choices"][0]["message"]["content"]

    if not answer:
        raise RuntimeError("Groq returned an empty answer.")

    return answer


# ============================================================
# GEMINI
# ============================================================

def gemini_request(messages):
    if not GEMINI_KEY:
        raise RuntimeError("Gemini API key missing.")

    from google import genai

    client = genai.Client(api_key=GEMINI_KEY)

    system_text = SYSTEM_PROMPT
    conversation = []

    for item in messages:
        role = item["role"]
        content = str(item["content"])

        if role == "system":
            system_text += "\n" + content
        elif role in ("user", "assistant"):
            conversation.append({
                "role": "model" if role == "assistant" else "user",
                "parts": [{"text": content}]
            })

    response = client.models.generate_content(
        model=GEMINI_MODEL,
        contents=conversation,
        config={
            "system_instruction": system_text,
            "temperature": 0.7,
            "max_output_tokens": 5000
        }
    )

    if not response.text:
        raise RuntimeError("Gemini returned an empty answer.")

    return response.text


# ============================================================
# OPENAI
# ============================================================

def openai_request(messages):
    if not OPENAI_KEY:
        raise RuntimeError("OpenAI API key missing.")

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
            "max_tokens": 4500
        },
        timeout=90
    )

    response.raise_for_status()

    return response.json()["choices"][0]["message"]["content"]


# ============================================================
# CLAUDE
# ============================================================

def anthropic_request(messages):
    if not ANTHROPIC_KEY:
        raise RuntimeError("Anthropic API key missing.")

    system_text = SYSTEM_PROMPT
    conversation = []

    for item in messages:
        if item["role"] == "system":
            system_text += "\n" + str(item["content"])
        elif item["role"] in ("user", "assistant"):
            conversation.append({
                "role": item["role"],
                "content": str(item["content"])
            })

    response = requests.post(
        "https://api.anthropic.com/v1/messages",
        headers={
            "x-api-key": ANTHROPIC_KEY,
            "anthropic-version": "2023-06-01",
            "content-type": "application/json"
        },
        json={
            "model": ANTHROPIC_MODEL,
            "max_tokens": 4500,
            "system": system_text,
            "messages": conversation
        },
        timeout=90
    )

    response.raise_for_status()

    data = response.json()

    return "".join(
        part.get("text", "")
        for part in data.get("content", [])
        if part.get("type") == "text"
    )


# ============================================================
# AI ROUTER
# ============================================================

def ask_ai(messages, provider="Auto"):
    engines = {
        "Groq": (GROQ_KEY, groq_request),
        "Gemini": (GEMINI_KEY, gemini_request),
        "OpenAI": (OPENAI_KEY, openai_request),
        "Claude": (ANTHROPIC_KEY, anthropic_request)
    }

    if provider != "Auto":
        if provider not in engines:
            raise RuntimeError("Unknown AI provider.")

        key, function = engines[provider]

        if not key:
            raise RuntimeError(provider + " API key missing.")

        return function(messages)

    errors = []

    for name, (key, function) in engines.items():
        if not key:
            continue

        try:
            result = function(messages)
            if result and result.strip():
                return result
        except Exception as exc:
            errors.append(name + ": " + str(exc)[:180])

    if not errors:
        raise RuntimeError(
            "No AI API keys configured in Streamlit Secrets."
        )

    raise RuntimeError("All configured AI providers failed: " + " | ".join(errors))


def ask_single(prompt, provider="Auto"):
    return ask_ai([
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": str(prompt)}
    ], provider)


# ============================================================
# WEB SEARCH — TAVILY
# ============================================================

def web_search(query):
    if not TAVILY_KEY:
        raise RuntimeError("TAVILY_API_KEY is missing.")

    response = requests.post(
        "https://api.tavily.com/search",
        json={
            "api_key": TAVILY_KEY,
            "query": query,
            "search_depth": "advanced",
            "max_results": 6,
            "include_answer": False
        },
        timeout=45
    )

    response.raise_for_status()

    results = response.json().get("results", [])

    if not results:
        return "No search results found."

    formatted = []

    for item in results:
        formatted.append(
            "Title: " + str(item.get("title", "")) +
            "\nURL: " + str(item.get("url", "")) +
            "\nContent: " + str(item.get("content", ""))
        )

    return "\n\n".join(formatted)


# ============================================================
# VOICE TRANSCRIPTION — GROQ WHISPER
# ============================================================

def transcribe_audio(audio_file):
    if not GROQ_KEY:
        raise RuntimeError("Groq key required for transcription.")

    audio_file.seek(0)

    response = requests.post(
        "https://api.groq.com/openai/v1/audio/transcriptions",
        headers={
            "Authorization": f"Bearer {GROQ_KEY}"
        },
        files={
            "file": (
                "recording.wav",
                audio_file.getvalue(),
                "audio/wav"
            )
        },
        data={
            "model": "whisper-large-v3",
            "response_format": "json"
        },
        timeout=120
    )

    response.raise_for_status()

    return response.json().get("text", "")


# ============================================================
# PDF READER
# ============================================================

def read_pdf(uploaded_file):
    from pypdf import PdfReader

    reader = PdfReader(uploaded_file)
    pages = []

    for index, page in enumerate(reader.pages):
        page_text = page.extract_text() or ""

        if page_text.strip():
            pages.append(
                f"PAGE {index + 1}\n{page_text}"
            )

    return "\n\n".join(pages)[:50000]


# ============================================================
# IMAGE VISION
# ============================================================

def analyze_image(uploaded_file, prompt):
    if not GEMINI_KEY:
        raise RuntimeError("Gemini key required for Vision.")

    from google import genai
    from google.genai import types

    client = genai.Client(api_key=GEMINI_KEY)

    image_part = types.Part.from_bytes(
        data=uploaded_file.getvalue(),
        mime_type=uploaded_file.type
    )

    response = client.models.generate_content(
        model=GEMINI_MODEL,
        contents=[
            prompt or "Describe this image accurately.",
            image_part
        ],
        config={
            "system_instruction": SYSTEM_PROMPT
        }
    )

    if not response.text:
        raise RuntimeError("Vision returned no answer.")

    return response.text


# ============================================================
# CLOUDFLARE IMAGE GENERATION
# ============================================================

def generate_image(prompt):
    if not CLOUDFLARE_ACCOUNT_ID or not CLOUDFLARE_API_TOKEN:
        raise RuntimeError("Cloudflare credentials missing.")

    url = (
        "https://api.cloudflare.com/client/v4/accounts/"
        + CLOUDFLARE_ACCOUNT_ID
        + "/ai/run/"
        + IMAGE_MODEL
    )

    response = requests.post(
        url,
        headers={
            "Authorization": f"Bearer {CLOUDFLARE_API_TOKEN}",
            "Content-Type": "application/json"
        },
        json={"prompt": prompt},
        timeout=180
    )

    response.raise_for_status()

    if "image" in response.headers.get("content-type", ""):
        return response.content

    data = response.json()
    image_data = data.get("result", {}).get("image")

    if image_data:
        return base64.b64decode(image_data)

    raise RuntimeError("Cloudflare did not return an image.")


# ============================================================
# FINNHUB STOCK DATA
# ============================================================

def finnhub(endpoint, params):
    if not FINNHUB_KEY:
        raise RuntimeError("Finnhub API key missing.")

    query = dict(params)
    query["token"] = FINNHUB_KEY

    response = requests.get(
        "https://finnhub.io/api/v1/" + endpoint,
        params=query,
        timeout=30
    )

    response.raise_for_status()
    return response.json()


def stock_quote(symbol):
    return finnhub("quote", {"symbol": symbol.upper()})


def stock_profile(symbol):
    return finnhub(
        "stock/profile2",
        {"symbol": symbol.upper()}
    )


def stock_candles(symbol, days=90):
    end = int(datetime.now().timestamp())
    start = int(
        (datetime.now() - timedelta(days=days)).timestamp()
    )

    return finnhub(
        "stock/candle",
        {
            "symbol": symbol.upper(),
            "resolution": "D",
            "from": start,
            "to": end
        }
    )


def stock_news(symbol):
    today = datetime.now().date()
    start = today - timedelta(days=7)

    return finnhub(
        "company-news",
        {
            "symbol": symbol.upper(),
            "from": start.isoformat(),
            "to": today.isoformat()
        }
    )


# ============================================================
# APP + WEBSITE BUILDER
# ============================================================

def clean_project_name(name):
    cleaned = re.sub(
        r"[^a-zA-Z0-9_-]+",
        "_",
        str(name)
    )
    return cleaned.strip("_")[:50] or "my_project"


def parse_project_json(raw):
    raw = raw.strip()

    raw = re.sub(
        r"^```(?:json)?\s*|\s*```$",
        "",
        raw,
        flags=re.I
    ).strip()

    first = raw.find("{")
    last = raw.rfind("}")

    if first == -1 or last == -1:
        raise ValueError("AI did not return valid project JSON.")

    return json.loads(raw[first:last + 1])


def build_project(project_type, name, description, features, design):
    name = clean_project_name(name)

    if project_type == "Website":
        instructions = """
Create a complete responsive website.

Required files:
index.html
style.css
script.js
README.md

Use HTML, CSS and JavaScript.
Make navigation and buttons functional.
Include mobile responsive design.
Include accessible labels and basic SEO.
Avoid unnecessary external dependencies.
"""
    else:
        instructions = """
Create a complete Python Streamlit application.

Required files:
app.py
requirements.txt
README.md

Include all imports and complete implementation.
Include installation and running instructions.
Use environment variables for API secrets.
Include useful error handling.
"""

    prompt = f"""
Act as a senior software engineer.

Create a complete project.

Project type: {project_type}
Project name: {name}

Description:
{description}

Features:
{features}

Design:
{design}

{instructions}

Return ONLY valid JSON in this exact structure:

{{
  "summary": "Short project summary",
  "files": {{
    "filename": "complete file contents"
  }}
}}

Do not return markdown fences.
Do not include API secrets.
Do not invent credentials.
Do not return incomplete placeholder code.
"""

    answer = ask_single(prompt)
    data = parse_project_json(answer)

    files = data.get("files", {})

    if not isinstance(files, dict) or not files:
        raise ValueError("The AI returned no project files.")

    safe_files = {}

    for filename, content in files.items():
        filename = str(filename).replace("\\", "/")

        if (
            filename.startswith("/")
            or ".." in filename.split("/")
            or not filename.strip()
        ):
            continue

        if isinstance(content, str):
            safe_files[filename] = content

    if not safe_files:
        raise ValueError("No valid project files were generated.")

    return {
        "name": name,
        "summary": str(data.get("summary", "")),
        "files": safe_files
    }


def create_project_zip(project):
    memory = io.BytesIO()

    with zipfile.ZipFile(
        memory,
        "w",
        zipfile.ZIP_DEFLATED
    ) as archive:

        for filename, content in project["files"].items():
            archive.writestr(
                project["name"] + "/" + filename,
                content
            )

    memory.seek(0)
    return memory.getvalue()


# ============================================================
# SIDEBAR — NAVIGATION + CHAT HISTORY
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
        use_container_width=True,
        key="new_chat_sidebar"
    ):
        start_new_chat()
        st.rerun()

    st.markdown("### Workspace")

    page_options = [
        "AI Chat",
        "Vision",
        "Creative Studio",
        "PDF Assistant",
        "Stock Market",
        "Stock Analysis",
        "Build Studio",
        "Settings"
    ]

    current_page = st.session_state.page

    if current_page not in page_options:
        current_page = "AI Chat"

    selected_page = st.radio(
        "Navigation",
        page_options,
        index=page_options.index(current_page),
        label_visibility="collapsed",
        key="main_navigation"
    )

    if selected_page != st.session_state.page:
        st.session_state.page = selected_page
        st.rerun()

    st.divider()

    st.markdown("### Chat History")

    chats = get_chats()

    if not chats:
        st.caption("Your conversations will appear here.")

    for chat_id, title, created in chats[:40]:

        is_current = chat_id == st.session_state.chat_id

        label = ("● " if is_current else "○ ") + (
            title or "New Chat"
        )

        if st.button(
            label,
            key=f"sidebar_chat_{chat_id}",
            use_container_width=True
        ):
            open_chat(chat_id)
            st.rerun()

    st.divider()

    st.caption("NEXTGEN AI Premium")
    st.caption("Built for learning and creativity")


# ============================================================
# PAGE ROUTER
# ============================================================

page = st.session_state.page


# ============================================================
# AI CHAT — CHATGPT-INSPIRED INTERFACE
# ============================================================

if page == "AI Chat":

    # Top bar
    left, right = st.columns([5, 1])

    with left:
        st.markdown("### ✦ NEXTGEN AI")

    with right:
        provider_options = [
            "Auto",
            "Groq",
            "Gemini",
            "OpenAI",
            "Claude"
        ]

        provider = st.selectbox(
            "Model",
            provider_options,
            index=provider_options.index(
                st.session_state.provider
            ),
            label_visibility="collapsed",
            key="chat_provider"
        )

        st.session_state.provider = provider

    # Welcome screen
    if not st.session_state.messages:

        st.markdown(
            """
            <div style="
                text-align:center;
                padding-top:75px;
                padding-bottom:35px;
            ">
                <div style="font-size:42px;">✦</div>
                <h2>What can I help you with?</h2>
                <p style="color:#9299aa;">
                    Ask, learn, create and explore with NEXTGEN AI.
                </p>
            </div>
            """,
            unsafe_allow_html=True
        )

        suggestion_cols = st.columns(2)

        suggestions = [
            "Teach me Python step by step",
            "Help me build a professional website",
            "Explain artificial intelligence",
            "Give me a creative project idea"
        ]

        for index, suggestion in enumerate(suggestions):
            with suggestion_cols[index % 2]:
                if st.button(
                    suggestion,
                    key=f"chat_suggestion_{index}",
                    use_container_width=True
                ):
                    st.session_state.pending_prompt = suggestion
                    st.rerun()

    # Conversation area
    for index, message in enumerate(st.session_state.messages):

        with st.chat_message(message["role"]):

            st.markdown(message["content"])

            if message["role"] == "assistant":
                read_aloud(
                    message["content"],
                    "chat_answer_" + str(index)
                )

    # Search and attachment controls
    st.divider()

    control_left, control_right = st.columns([1, 1])

    with control_left:
        web_enabled = st.checkbox(
            "🌐 Web Search",
            value=False,
            key="chat_web_search"
        )

    with control_right:
        st.caption("Attach a file or use voice input below.")

    attachment = st.file_uploader(
        "＋ Attach an image or PDF",
        type=["png", "jpg", "jpeg", "webp", "pdf"],
        key="chat_attachment"
    )

    if attachment:
        st.caption("Attached: " + attachment.name)

    # Voice input
    with st.expander("🎙 Voice input", expanded=False):

        if hasattr(st, "audio_input"):

            audio = st.audio_input(
                "Record your message",
                key="chat_audio_input"
            )

            if audio and st.button(
                "Convert voice to text",
                key="transcribe_button"
            ):
                try:
                    with st.spinner("Converting voice..."):
                        transcript = transcribe_audio(audio)

                    if transcript.strip():
                        st.session_state.voice_prompt = transcript
                        st.success("Voice converted.")
                        st.code(transcript)
                    else:
                        st.warning("No speech was detected.")

                except Exception as exc:
                    show_error(exc)

        else:
            st.info(
                "Your Streamlit version does not support audio_input. "
                "Upgrade Streamlit to use microphone recording."
            )

        if st.session_state.voice_prompt:
            if st.button(
                "Send converted voice message",
                key="send_voice_button"
            ):
                st.session_state.pending_prompt = (
                    st.session_state.voice_prompt
                )
                st.session_state.voice_prompt = ""
                st.rerun()

    # Chat input — stays at the bottom of the chat page
    prompt = st.chat_input(
        "Message NEXTGEN AI...",
        key="main_chat_input"
    )

    if st.session_state.pending_prompt:
        prompt = st.session_state.pending_prompt
        st.session_state.pending_prompt = None

    # Process message
    if prompt:

        user_text = prompt.strip()

        if user_text:

            add_message("user", user_text)

            if len(st.session_state.messages) == 1:
                update_chat_title(
                    st.session_state.chat_id,
                    user_text[:40]
                )

            try:

                with st.spinner("NEXTGEN AI is thinking..."):

                    history = [
                        {
                            "role": "system",
                            "content": SYSTEM_PROMPT
                        }
                    ]

                    history.extend(
                        st.session_state.messages[:-1][-30:]
                    )

                    final_user_text = user_text

                    # PDF attachment
                    if attachment and attachment.type == "application/pdf":

                        pdf_text = read_pdf(attachment)

                        if not pdf_text.strip():
                            raise ValueError(
                                "No readable text found in this PDF."
                            )

                        final_user_text += (
                            "\n\nPDF DOCUMENT CONTENT:\n"
                            + pdf_text
                        )

                    # Image attachment
                    elif attachment and attachment.type.startswith("image/"):

                        answer = analyze_image(
                            attachment,
                            user_text
                        )

                        add_message("assistant", answer)
                        st.session_state.last_answer = answer
                        st.rerun()

                    # Web Search
                    if web_enabled:

                        with st.spinner("🌐 Searching the web..."):

                            search_results = web_search(user_text)

                        history.append({
                            "role": "system",
                            "content": (
                                "Use these web search results to answer "
                                "the user's question. Do not invent facts. "
                                "Mention useful source URLs in your answer.\n\n"
                                + search_results
                            )
                        })

                    history.append({
                        "role": "user",
                        "content": final_user_text
                    })

                    answer = ask_ai(
                        history,
                        st.session_state.provider
                    )

                add_message("assistant", answer)
                st.session_state.last_answer = answer

            except Exception as exc:

                error_text = (
                    "I could not complete that request.\n\n"
                    + str(exc)[:700]
                )

                add_message("assistant", error_text)

            st.rerun()


# ============================================================
# VISION
# ============================================================

elif page == "Vision":

    hero(
        "👁 AI Vision",
        "Understand and analyze images."
    )

    image_file = st.file_uploader(
        "Upload an image",
        type=["png", "jpg", "jpeg", "webp"],
        key="vision_upload"
    )

    question = st.text_area(
        "What would you like to know about this image?",
        placeholder="Describe this image..."
    )

    if image_file:

        st.image(
            image_file,
            use_container_width=True
        )

        if st.button("Analyze Image"):

            try:
                with st.spinner("Analyzing image..."):
                    result = analyze_image(
                        image_file,
                        question
                    )

                st.session_state.vision_result = result
                render_answer(result, "vision_result")

            except Exception as exc:
                show_error(exc)

    elif st.session_state.vision_result:
        render_answer(
            st.session_state.vision_result,
            "old_vision_result"
        )


# ============================================================
# CREATIVE STUDIO
# ============================================================

elif page == "Creative Studio":

    hero(
        "🎨 Creative Studio",
        "Generate original AI artwork with Cloudflare."
    )

    prompt = st.text_area(
        "Describe your image",
        height=120,
        placeholder="A futuristic cinematic city at night..."
    )

    col1, col2 = st.columns(2)

    with col1:
        style = st.selectbox(
            "Art Style",
            [
                "Photorealistic",
                "Anime",
                "3D Animation",
                "Cinematic",
                "Digital Art",
                "Fantasy",
                "Cyberpunk",
                "Cartoon",
                "Watercolor"
            ]
        )

        ratio = st.selectbox(
            "Aspect Ratio",
            ["1:1", "9:16", "16:9", "4:5", "3:2"]
        )

    with col2:
        lighting = st.selectbox(
            "Lighting",
            [
                "Cinematic",
                "Golden Hour",
                "Neon",
                "Studio",
                "Natural",
                "Dramatic"
            ]
        )

        quality = st.selectbox(
            "Quality",
            [
                "Highly Detailed",
                "Professional",
                "Clean Minimal",
                "Ultra Detailed"
            ]
        )

    extra = st.text_area(
        "Additional details",
        placeholder="Colors, background, camera angle..."
    )

    if st.button(
        "✦ Generate Image",
        use_container_width=True
    ):

        if not prompt.strip():
            st.warning("Please describe your image.")
        else:
            full_prompt = (
                prompt
                + "\nStyle: " + style
                + "\nAspect ratio: " + ratio
                + "\nLighting: " + lighting
                + "\nQuality: " + quality
                + "\nAdditional details: " + extra
            )

            try:
                with st.spinner("Generating image..."):
                    image_bytes = generate_image(full_prompt)

                st.session_state.last_image = image_bytes

            except Exception as exc:
                show_error(exc)

    if st.session_state.last_image:

        st.markdown("### Generated Image")

        st.image(
            st.session_state.last_image,
            use_container_width=True
        )

        st.download_button(
            "⬇ Download Image",
            data=st.session_state.last_image,
            file_name="nextgen_ai_image.png",
            mime="image/png"
        )


# ============================================================
# PDF ASSISTANT
# ============================================================

elif page == "PDF Assistant":

    hero(
        "📄 PDF Assistant",
        "Upload a document and ask questions about it."
    )

    pdf_file = st.file_uploader(
        "Upload PDF",
        type=["pdf"],
        key="pdf_upload"
    )

    question = st.text_area(
        "Your question",
        placeholder="Summarize this document..."
    )

    if pdf_file and st.button("Analyze PDF"):

        try:

            with st.spinner("Reading PDF..."):

                pdf_text = read_pdf(pdf_file)

                if not pdf_text.strip():
                    raise ValueError(
                        "This PDF has no extractable text."
                    )

                result = ask_single(
                    f"""
                    Answer using this PDF content.

                    Question:
                    {question or "Give me a clear summary."}

                    PDF:
                    {pdf_text}

                    Do not invent information.
                    """,
                    st.session_state.provider
                )

            st.session_state.pdf_result = result
            render_answer(result, "pdf_answer")

        except Exception as exc:
            show_error(exc)

    elif st.session_state.pdf_result:
        render_answer(
            st.session_state.pdf_result,
            "previous_pdf_answer"
        )


# ============================================================
# STOCK MARKET
# ============================================================

elif page == "Stock Market":

    hero(
        "📈 Stock Market Explorer",
        "Explore historical prices, charts and company information."
    )

    st.info(
        "Educational market information only. "
        "Not personalized investment advice."
    )

    symbol = st.text_input(
        "Stock Symbol",
        value="AAPL",
        key="market_symbol"
    ).strip().upper()

    period = st.selectbox(
        "Chart Period",
        ["1 Month", "3 Months", "6 Months", "1 Year"]
    )

    days = {
        "1 Month": 30,
        "3 Months": 90,
        "6 Months": 180,
        "1 Year": 365
    }[period]

    if st.button("Load Market Data"):

        try:

            with st.spinner("Fetching stock data..."):

                quote = stock_quote(symbol)
                profile = stock_profile(symbol)
                candles = stock_candles(symbol, days)

                if candles.get("s") != "ok":
                    raise ValueError(
                        "Historical data is unavailable."
                    )

                st.session_state.stock_result = {
                    "quote": quote,
                    "profile": profile,
                    "candles": candles,
                    "symbol": symbol
                }

        except Exception as exc:
            show_error(exc)

    market = st.session_state.stock_result

    if market:

        import pandas as pd

        quote = market["quote"]
        profile = market["profile"]
        candles = market["candles"]

        st.markdown(
            "### " + str(profile.get("name", symbol))
        )

        a, b, c = st.columns(3)

        a.metric(
            "Current Price",
            f"${quote.get('c', 0):,.2f}"
        )

        b.metric(
            "Daily Change",
            f"{quote.get('d', 0):,.2f}"
        )

        c.metric(
            "Change %",
            f"{quote.get('dp', 0):,.2f}%"
        )

        dataframe = pd.DataFrame({
            "Date": pd.to_datetime(candles["t"], unit="s"),
            "Close": candles["c"],
            "Open": candles["o"],
            "High": candles["h"],
            "Low": candles["l"],
            "Volume": candles["v"]
        })

        dataframe = dataframe.set_index("Date")

        st.markdown("### Price Chart")
        st.line_chart(dataframe[["Close"]])

        st.markdown("### Trading Volume")
        st.bar_chart(dataframe[["Volume"]])

        st.markdown("### Historical Data")
        st.dataframe(
            dataframe.tail(20),
            use_container_width=True
        )

        st.caption(
            "Historical performance does not guarantee future results."
        )


# ============================================================
# STOCK ANALYSIS
# ============================================================

elif page == "Stock Analysis":

    hero(
        "🔍 AI Stock Research",
        "Understand company information and possible risk factors."
    )

    symbol = st.text_input(
        "Company Symbol",
        value="AAPL",
        key="research_symbol"
    ).strip().upper()

    if st.button("Research Company"):

        try:

            with st.spinner("Collecting company information..."):

                quote = stock_quote(symbol)
                profile = stock_profile(symbol)
                news = stock_news(symbol)

                headlines = "\n".join(
                    item.get("headline", "")
                    for item in news[:10]
                )

                prompt = f"""
                Provide an educational company research report.

                Symbol: {symbol}
                Company: {profile.get('name', 'Unknown')}
                Industry: {profile.get('finnhubIndustry', 'Unknown')}
                Country: {profile.get('country', 'Unknown')}

                Current price: {quote.get('c')}
                Daily change: {quote.get('d')}
                Daily change percentage: {quote.get('dp')}
                Previous close: {quote.get('pc')}

                Recent news:
                {headlines}

                Explain:
                1. Company overview.
                2. Available price information.
                3. Recent news.
                4. Business risks.
                5. Important things to research.
                6. What information is missing.
                7. Beginner-friendly summary.

                Do not invent facts or predict guaranteed returns.
                Do not tell the user to buy or sell.
                """

            with st.spinner("Preparing AI report..."):
                report = ask_single(
                    prompt,
                    st.session_state.provider
                )

            st.markdown(
                "### " + str(profile.get("name", symbol))
            )

            st.metric(
                "Latest Available Price",
                f"${quote.get('c', 0):,.2f}"
            )

            render_answer(report, "stock_report")

            st.markdown("### Recent Headlines")

            for item in news[:7]:
                headline = item.get("headline", "")
                if headline:
                    st.write("• " + headline)

        except Exception as exc:
            show_error(exc)


# ============================================================
# BUILD STUDIO
# ============================================================

elif page == "Build Studio":

    hero(
        "🛠 Build Studio",
        "Generate app and website project files with AI."
    )

    app_tab, website_tab, project_tab = st.tabs([
        "📱 App Builder",
        "🌐 Website Builder",
        "📁 Project Files"
    ])

    with app_tab:

        st.markdown("### AI App Builder")

        app_name = st.text_input(
            "App Name",
            "my_ai_app",
            key="builder_app_name"
        )

        app_description = st.text_area(
            "Describe your app",
            height=120,
            key="builder_app_description"
        )

        app_features = st.text_area(
            "Features you need",
            placeholder="Dashboard, search, database, login...",
            key="builder_app_features"
        )

        app_design = st.selectbox(
            "App Design",
            [
                "Premium Dark",
                "Modern Minimal",
                "Neon",
                "Professional",
                "Colorful"
            ],
            key="builder_app_design"
        )

        if st.button(
            "✦ Build App",
            use_container_width=True
        ):

            if not app_description.strip():
                st.warning("Describe your app first.")
            else:
                try:
                    with st.spinner("Generating app files..."):
                        project = build_project(
                            "App",
                            app_name,
                            app_description,
                            app_features,
                            app_design
                        )

                    st.session_state.project_files = project["files"]
                    st.session_state.project_name = project["name"]
                    st.session_state.project_summary = project["summary"]

                    st.success("App project generated.")

                except Exception as exc:
                    show_error(exc)

    with website_tab:

        st.markdown("### AI Website Builder")

        website_name = st.text_input(
            "Website Name",
            "my_website",
            key="builder_website_name"
        )

        website_description = st.text_area(
            "Describe your website",
            height=120,
            key="builder_website_description"
        )

        website_features = st.text_area(
            "Website Features",
            placeholder="Home, About, Contact, Gallery...",
            key="builder_website_features"
        )

        website_design = st.selectbox(
            "Website Design",
            [
                "Premium Modern",
                "Business Professional",
                "Minimal",
                "Dark Futuristic",
                "Creative"
            ],
            key="builder_website_design"
        )

        if st.button(
            "✦ Build Website",
            use_container_width=True
        ):

            if not website_description.strip():
                st.warning("Describe your website first.")
            else:
                try:
                    with st.spinner("Generating website files..."):
                        project = build_project(
                            "Website",
                            website_name,
                            website_description,
                            website_features,
                            website_design
                        )

                    st.session_state.project_files = project["files"]
                    st.session_state.project_name = project["name"]
                    st.session_state.project_summary = project["summary"]

                    st.success("Website project generated.")

                except Exception as exc:
                    show_error(exc)

    with project_tab:

        files = st.session_state.project_files

        if files:

            st.markdown(
                "### " + st.session_state.project_name
            )

            st.write(
                st.session_state.project_summary
            )

            selected_file = st.selectbox(
                "Select a file to preview",
                list(files.keys())
            )

            extension = selected_file.rsplit(".", 1)[-1].lower()

            language_map = {
                "py": "python",
                "html": "html",
                "css": "css",
                "js": "javascript",
                "json": "json",
                "md": "markdown",
                "txt": "text"
            }

            st.code(
                files[selected_file],
                language=language_map.get(extension, "text")
            )

            project = {
                "name": st.session_state.project_name,
                "files": files
            }

            st.download_button(
                "⬇ Download Complete Project ZIP",
                data=create_project_zip(project),
                file_name=project["name"] + ".zip",
                mime="application/zip",
                use_container_width=True
            )

            st.info(
                "Review and test the generated files, install dependencies, "
                "configure secrets and then deploy the project."
            )

        else:

            st.info(
                "Your generated project files will appear here."
            )


# ============================================================
# SETTINGS
# ============================================================

elif page == "Settings":

    hero(
        "⚙ Settings",
        "API connection status and workspace information."
    )

    st.markdown("### API Connections")

    services = {
        "Groq": GROQ_KEY,
        "Gemini": GEMINI_KEY,
        "OpenAI": OPENAI_KEY,
        "Claude": ANTHROPIC_KEY,
        "Finnhub": FINNHUB_KEY,
        "Tavily Web Search": TAVILY_KEY,
        "Cloudflare": CLOUDFLARE_API_TOKEN
    }

    for service, key in services.items():

        if key:
            st.success(service + " — API key detected")
        else:
            st.warning(service + " — API key not configured")

    st.divider()

    st.markdown("### AI Models")

    st.write("Groq:", GROQ_MODEL)
    st.write("Gemini:", GEMINI_MODEL)
    st.write("OpenAI:", OPENAI_MODEL)
    st.write("Claude:", ANTHROPIC_MODEL)

    st.divider()

    st.markdown("### Workspace")

    st.write("Application:", APP_NAME)
    st.write("Database:", "SQLite")
    st.write("Chat history:", "Saved locally")

    st.warning(
        "Never share your API keys or place real secrets in public source code."
    )

    st.divider()

    if st.button("＋ Start New Chat"):
        start_new_chat()
        st.rerun()

    if st.button("Delete Current Chat"):
        delete_chat(st.session_state.chat_id)
        st.session_state.chat_id = create_chat()
        st.session_state.messages = []
        st.session_state.page = "AI Chat"
        st.rerun()


# ============================================================
# FOOTER
# ============================================================

st.divider()

st.markdown(
    """
    <div style="
        text-align:center;
        color:#858da0;
        padding:15px;
        font-size:13px;
    ">
        ✦ NEXTGEN AI<br>
        Your Personal Intelligent Workspace<br>
        Built for learning, creativity and innovation.
    </div>
    """,
    unsafe_allow_html=True
)
