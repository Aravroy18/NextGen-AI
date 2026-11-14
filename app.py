
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
# NEXTGEN AI — PREMIUM COMPLETE EDITION
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
# SECRETS MANAGER
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

CLOUDFLARE_ACCOUNT_ID = get_secret(
    "CLOUDFLARE_ACCOUNT_ID"
)

CLOUDFLARE_API_TOKEN = get_secret(
    "CLOUDFLARE_API_TOKEN"
)

TAVILY_KEY = get_secret("TAVILY_API_KEY")

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
# OWNER INFORMATION
# ============================================================

OWNER_PROFILE = """
The owner and creator of this personal AI workspace is Arav Roy.

Arav Roy is a curious young learner and technology enthusiast.
He studies in Class 7 at Swami Vivekanand Shiksha Niketan.

He is interested in:
- Artificial Intelligence
- Python programming
- Software development
- Building AI applications
- Stock market education
- Cricket and sports
- Creative content creation
- YouTube and digital projects
- Learning new technologies

His YouTube project is called ARAVYX.

He enjoys experimenting with ideas and building projects.
He is ambitious, creative and interested in improving his
technical and academic skills.

When someone asks who Arav Roy is, explain these known facts
in a warm and positive way.

Never invent awards, achievements, qualifications, exam marks,
financial status or personal facts that are not known.

Never claim that Arav has won an award unless confirmed.
"""

SYSTEM_PROMPT = f"""
You are NEXTGEN AI.

You are an intelligent, helpful, friendly and capable AI assistant.

OWNER INFORMATION:
{OWNER_PROFILE}

BEHAVIOUR:
1. Respond in the language used by the user.
2. Support English and Hindi.
3. Be accurate and honest.
4. Explain difficult topics simply.
5. For programming, provide complete working code.
6. For school topics, teach step by step.
7. Never invent facts, API results or live information.
8. Never claim an action happened if it did not.
9. Explain uncertainty honestly.
10. Keep answers clear and useful.

CODING:
- Prefer complete solutions.
- Include necessary imports.
- Explain installation requirements.
- Avoid unnecessary placeholders.
- Mention limitations honestly.

FINANCE:
- Explain financial risks.
- Never guarantee investment returns.
- Do not pretend historical data predicts the future.
- Treat stock information as educational.

IDENTITY:
You are NEXTGEN AI, not ChatGPT.
Never pretend to be another AI product.

You are designed to help users learn, build, research and create.
"""


# ============================================================
# DATABASE
# ============================================================

def db():
    conn = sqlite3.connect(
        DB_PATH,
        timeout=30,
        check_same_thread=False
    )
    conn.execute("PRAGMA foreign_keys=ON")
    conn.execute("PRAGMA busy_timeout=30000")
    return conn


def init_db():
    with db() as conn:

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
                FOREIGN KEY(chat_id)
                REFERENCES chats(id)
                ON DELETE CASCADE
            )
        """)

        conn.execute("""
            CREATE INDEX IF NOT EXISTS message_chat_idx
            ON messages(chat_id)
        """)

        conn.commit()


def new_chat():
    with db() as conn:
        cursor = conn.execute(
            "INSERT INTO chats(title,created) VALUES(?,?)",
            ("New Chat", datetime.now().isoformat())
        )
        conn.commit()
        return cursor.lastrowid


def get_chats():
    with db() as conn:
        return conn.execute("""
            SELECT id,title,created
            FROM chats
            ORDER BY id DESC
        """).fetchall()


def get_messages(chat_id):
    with db() as conn:
        rows = conn.execute("""
            SELECT role,content
            FROM messages
            WHERE chat_id=?
            ORDER BY id
        """, (chat_id,)).fetchall()

    return [
        {"role": role, "content": content}
        for role, content in rows
    ]


def save_message(chat_id, role, content):
    with db() as conn:
        conn.execute("""
            INSERT INTO messages(
                chat_id,role,content,created
            )
            VALUES(?,?,?,?)
        """, (
            chat_id,
            role,
            content,
            datetime.now().isoformat()
        ))
        conn.commit()


def rename_chat(chat_id, title):
    with db() as conn:
        conn.execute("""
            UPDATE chats
            SET title=?
            WHERE id=?
        """, (title[:45], chat_id))
        conn.commit()


def remove_chat(chat_id):
    with db() as conn:
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
    "last_answer": "",
    "project_files": {},
    "project_name": "",
    "project_summary": "",
    "last_image": None,
    "stock_result": None,
    "pdf_result": "",
    "vision_result": ""
}

for key, value in DEFAULTS.items():
    if key not in st.session_state:
        st.session_state[key] = value

if st.session_state.chat_id is None:
    st.session_state.chat_id = new_chat()
    st.session_state.messages = []


def switch_chat(chat_id):
    st.session_state.chat_id = chat_id
    st.session_state.messages = get_messages(chat_id)
    st.session_state.page = "AI Chat"


def start_new_chat():
    st.session_state.chat_id = new_chat()
    st.session_state.messages = []
    st.session_state.last_answer = ""
    st.session_state.page = "AI Chat"


def add_message(role, content):
    st.session_state.messages.append({
        "role": role,
        "content": content
    })

    save_message(
        st.session_state.chat_id,
        role,
        content
    )


# ============================================================
# PREMIUM CSS
# ============================================================

st.markdown("""
<style>

#MainMenu {visibility:hidden;}
footer {visibility:hidden;}
header {visibility:hidden;}

.stApp {
    background:#090b10;
    color:#ffffff;
}

[data-testid="stSidebar"] {
    background:#10131b;
    border-right:1px solid #272c39;
}

[data-testid="stSidebar"] button {
    background:transparent;
    color:#ffffff;
    border:1px solid transparent;
    border-radius:10px;
    text-align:left;
}

[data-testid="stSidebar"] button:hover {
    background:#202538;
    border-color:#5551a8;
}

.main .block-container {
    max-width:1050px;
    padding-top:2rem;
    padding-bottom:4rem;
}

h1,h2,h3,h4 {
    color:#ffffff !important;
}

p,li,label {
    color:#e6e8ef;
}

.brand {
    font-size:26px;
    font-weight:900;
    letter-spacing:1px;
    color:white;
}

.brand span {
    color:#9184ff;
}

.muted {
    color:#858da0;
    font-size:13px;
}

.hero {
    background:linear-gradient(
        120deg,#17172a,#111a2b
    );
    border:1px solid #30344b;
    padding:24px;
    border-radius:20px;
    margin-bottom:20px;
}

.stButton button {
    background:#191e2c;
    border:1px solid #343b50;
    border-radius:12px;
    color:white;
    min-height:42px;
}

.stButton button:hover {
    background:#292642;
    border-color:#8176e8;
    color:white;
}

[data-testid="stChatInput"] {
    background:#151927;
    border:1px solid #49436e;
    border-radius:18px;
}

[data-testid="stChatInput"] textarea {
    color:white !important;
    -webkit-text-fill-color:white !important;
}

[data-testid="stChatMessage"] {
    background:transparent;
    border:none;
}

[data-testid="stMarkdownContainer"] {
    color:white;
}

[data-testid="stMarkdownContainer"] p,
[data-testid="stMarkdownContainer"] li {
    color:#f5f5f7 !important;
}

.stTextInput input,
.stTextArea textarea {
    color:white !important;
    -webkit-text-fill-color:white !important;
    background:#151927 !important;
}

.stSelectbox div {
    color:white;
}

.stFileUploader {
    background:#131927;
    border-radius:14px;
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
    padding:15px;
    border-radius:12px;
    border:1px solid #30394a;
}

hr {
    border-color:#303547;
}

</style>
""", unsafe_allow_html=True)


# ============================================================
# COMMON HELPERS
# ============================================================

def hero(title, subtitle=""):
    st.markdown(
        f"""
        <div class="hero">
            <h2>{title}</h2>
            <div class="muted">{subtitle}</div>
        </div>
        """,
        unsafe_allow_html=True
    )


def show_error(error):
    st.error(str(error)[:800])


def read_aloud(text, key="read"):
    safe = json.dumps(str(text))

    html_code = """
    <button id="btn___ID__" style="
        background:#242b40;
        color:white;
        padding:9px 15px;
        border:1px solid #505b7b;
        border-radius:10px;
        cursor:pointer;">
        🔊 Read Aloud
    </button>

    <script>
    const textValue = __TEXT__;
    const button = document.getElementById("btn___ID__");

    button.onclick = () => {
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

        speech.onend = () => {
            button.innerText = "🔊 Read Aloud";
        };
    };
    </script>
    """

    html_code = html_code.replace("__TEXT__", safe)
    html_code = html_code.replace("__ID__", str(key))

    components.html(html_code, height=55)


def render_answer(answer, key="answer"):
    st.markdown(answer)
    read_aloud(answer, key)


# ============================================================
# GROQ ENGINE
# ============================================================

def groq_request(messages):

    if not GROQ_KEY:
        raise RuntimeError("Groq API key missing.")

    formatted = []

    for message in messages:
        role = message["role"]

        if role not in ["system", "user", "assistant"]:
            continue

        formatted.append({
            "role": role,
            "content": str(message["content"])
        })

    response = requests.post(
        "https://api.groq.com/openai/v1/chat/completions",
        headers={
            "Authorization": f"Bearer {GROQ_KEY}",
            "Content-Type": "application/json"
        },
        json={
            "model": GROQ_MODEL,
            "messages": formatted,
            "temperature": 0.7,
            "max_tokens": 5000
        },
        timeout=90
    )

    response.raise_for_status()

    result = response.json()

    answer = result["choices"][0]["message"]["content"]

    if not answer:
        raise RuntimeError("Groq returned an empty answer.")

    return answer


# ============================================================
# GEMINI ENGINE
# ============================================================

def gemini_request(messages):

    if not GEMINI_KEY:
        raise RuntimeError("Gemini API key missing.")

    from google import genai

    client = genai.Client(api_key=GEMINI_KEY)

    history = []

    system = SYSTEM_PROMPT

    for item in messages:

        role = item["role"]
        content = str(item["content"])

        if role == "system":
            system += "\n" + content
            continue

        history.append({
            "role": "model" if role == "assistant" else "user",
            "parts": [{"text": content}]
        })

    response = client.models.generate_content(
        model=GEMINI_MODEL,
        contents=history,
        config={
            "system_instruction": system,
            "temperature": 0.7,
            "max_output_tokens": 5000
        }
    )

    if not response.text:
        raise RuntimeError("Gemini returned an empty answer.")

    return response.text


# ============================================================
# OPENAI ENGINE
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

    result = response.json()

    return result["choices"][0]["message"]["content"]


# ============================================================
# ANTHROPIC ENGINE
# ============================================================

def anthropic_request(messages):

    if not ANTHROPIC_KEY:
        raise RuntimeError("Anthropic API key missing.")

    system = SYSTEM_PROMPT

    conversation = []

    for item in messages:

        if item["role"] == "system":
            system += "\n" + item["content"]
        elif item["role"] in ["user", "assistant"]:
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
            "system": system,
            "messages": conversation
        },
        timeout=90
    )

    response.raise_for_status()

    data = response.json()

    return "".join(
        item.get("text", "")
        for item in data.get("content", [])
        if item.get("type") == "text"
    )


# ============================================================
# AI ROUTER WITH FALLBACK
# ============================================================

def ask_ai(messages, provider="Auto"):

    providers = {
        "Groq": groq_request,
        "Gemini": gemini_request,
        "OpenAI": openai_request,
        "Claude": anthropic_request
    }

    if provider != "Auto":

        if provider not in providers:
            raise RuntimeError("Invalid AI provider.")

        return providers[provider](messages)

    errors = []

    for name, function in providers.items():

        key_available = {
            "Groq": GROQ_KEY,
            "Gemini": GEMINI_KEY,
            "OpenAI": OPENAI_KEY,
            "Claude": ANTHROPIC_KEY
        }[name]

        if not key_available:
            continue

        try:
            answer = function(messages)

            if answer and answer.strip():
                return answer

        except Exception as exc:
            errors.append(
                f"{name}: {str(exc)[:180]}"
            )

    if not errors:
        raise RuntimeError(
            "No AI API keys configured in Streamlit Secrets."
        )

    raise RuntimeError(" | ".join(errors))


def ask_single(prompt):

    return ask_ai([
        {
            "role": "system",
            "content": SYSTEM_PROMPT
        },
        {
            "role": "user",
            "content": prompt
        }
    ])


# ============================================================
# VOICE INPUT — GROQ WHISPER
# ============================================================

def transcribe_audio(audio_file):

    if not GROQ_KEY:
        raise RuntimeError(
            "Groq API key required for voice transcription."
        )

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
# PDF ENGINE
# ============================================================

def read_pdf(file):

    from pypdf import PdfReader

    reader = PdfReader(file)

    pages = []

    for index, page in enumerate(reader.pages):

        text = page.extract_text() or ""

        if text.strip():
            pages.append(
                f"PAGE {index + 1}\n{text}"
            )

    return "\n\n".join(pages)[:50000]


# ============================================================
# IMAGE VISION
# ============================================================

def analyze_image(file, prompt):

    if not GEMINI_KEY:
        raise RuntimeError(
            "Gemini API key required for image understanding."
        )

    from google import genai
    from google.genai import types

    client = genai.Client(api_key=GEMINI_KEY)

    image_part = types.Part.from_bytes(
        data=file.getvalue(),
        mime_type=file.type
    )

    response = client.models.generate_content(
        model=GEMINI_MODEL,
        contents=[
            prompt or "Describe this image.",
            image_part
        ],
        config={
            "system_instruction": SYSTEM_PROMPT
        }
    )

    if not response.text:
        raise RuntimeError("No vision response returned.")

    return response.text


# ============================================================
# CLOUDFLARE IMAGE GENERATOR
# ============================================================

def generate_image(prompt):

    if not CLOUDFLARE_ACCOUNT_ID:
        raise RuntimeError("Cloudflare Account ID missing.")

    if not CLOUDFLARE_API_TOKEN:
        raise RuntimeError("Cloudflare API token missing.")

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
        json={
            "prompt": prompt
        },
        timeout=180
    )

    response.raise_for_status()

    if "image" in response.headers.get(
        "content-type", ""
    ):
        return response.content

    data = response.json()

    image_data = data.get("result", {}).get("image")

    if image_data:
        return base64.b64decode(image_data)

    raise RuntimeError("Image generation failed.")


# ============================================================
# FINNHUB STOCK ENGINE
# ============================================================

def finnhub(endpoint, params):

    if not FINNHUB_KEY:
        raise RuntimeError("Finnhub API key missing.")

    params = dict(params)

    params["token"] = FINNHUB_KEY

    response = requests.get(
        "https://finnhub.io/api/v1/" + endpoint,
        params=params,
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
# PROJECT BUILDER
# ============================================================

def clean_name(name):

    value = re.sub(
        r"[^a-zA-Z0-9_-]+",
        "_",
        name
    )

    return value.strip("_")[:50] or "my_project"


def extract_project_json(raw):

    raw = raw.strip()

    raw = re.sub(
        r"^```(?:json)?\s*|\s*```$",
        "",
        raw,
        flags=re.I
    ).strip()

    start = raw.find("{")
    end = raw.rfind("}")

    if start < 0 or end < 0:
        raise ValueError("Invalid project JSON returned.")

    return json.loads(raw[start:end + 1])


def build_project(project_type, name, description, features, design):

    name = clean_name(name)

    if project_type == "Website":

        instruction = """
Create a complete responsive website.

Files should include:
index.html
style.css
script.js
README.md

Use HTML, CSS and JavaScript.
Make navigation and interactions work.
Use responsive design.
"""

    else:

        instruction = """
Create a complete Python Streamlit application.

Files should include:
app.py
requirements.txt
README.md

Include imports, complete implementation,
installation and running instructions.
"""

    prompt = f"""
You are a senior software engineer.

Create a complete project.

Project type: {project_type}

Project name: {name}

Description:
{description}

Features:
{features}

Design:
{design}

{instruction}

Return ONLY valid JSON:

{{
    "summary": "Project summary",
    "files": {{
        "filename": "complete file content"
    }}
}}

Do not return explanations outside JSON.
Do not use placeholder code.
Do not invent API keys.
Use environment variables for secrets.
"""

    answer = ask_single(prompt)

    data = extract_project_json(answer)

    files = data.get("files", {})

    if not isinstance(files, dict) or not files:
        raise ValueError("No project files returned.")

    cleaned = {}

    for filename, content in files.items():

        filename = str(filename).replace("\\", "/")

        if (
            filename.startswith("/")
            or ".." in filename.split("/")
            or not filename.strip()
        ):
            continue

        if isinstance(content, str):
            cleaned[filename] = content

    if not cleaned:
        raise ValueError("No valid project files.")

    return {
        "name": name,
        "summary": data.get("summary", ""),
        "files": cleaned
    }


def make_zip(project):

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
# SIDEBAR
# ============================================================

PAGES = [
    ("✦ AI Chat", "AI Chat"),
    ("👁 Vision", "Vision"),
    ("🎨 Creative Studio", "Creative Studio"),
    ("📄 PDF Assistant", "PDF Assistant"),
    ("📈 Stock Market", "Stock Market"),
    ("🔍 Stock Analysis", "Stock Analysis"),
    ("🛠 Build Studio", "Build Studio"),
    ("⚙ Settings", "Settings")
]


with st.sidebar:

    st.markdown(
        '<div class="brand">✦ NEXTGEN <span>AI</span></div>',
        unsafe_allow_html=True
    )

    st.caption("Your Intelligent Workspace")

    st.divider()

    if st.button(
        "＋  New Chat",
        use_container_width=True
    ):
        start_new_chat()
        st.rerun()

    st.markdown("### Workspace")

    for label, page_name in PAGES:

        if st.button(
            label,
            key="nav_" + page_name,
            use_container_width=True
        ):
            st.session_state.page = page_name
            st.rerun()

    st.divider()

    st.markdown("### Chat History")

    for chat_id, title, created in get_chats()[:30]:

        if st.button(
            "◉  " + (title or "New Chat"),
            key=f"history_{chat_id}",
            use_container_width=True
        ):
            switch_chat(chat_id)
            st.rerun()

    st.divider()

    st.caption("NEXTGEN AI Premium")
    st.caption("Built for Arav Roy")


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
        "Ask anything. Learn anything. Build anything."
    )

    provider = st.selectbox(
        "AI Model",
        [
            "Auto",
            "Groq",
            "Gemini",
            "OpenAI",
            "Claude"
        ],
        index=[
            "Auto",
            "Groq",
            "Gemini",
            "OpenAI",
            "Claude"
        ].index(st.session_state.provider)
    )

    st.session_state.provider = provider

    if not st.session_state.messages:

        st.markdown("### Welcome to NEXTGEN AI")

        st.write(
            "Your personal workspace for learning, "
            "coding, research and creativity."
        )

        suggestions = [
            "Introduce yourself.",
            "Teach me Python programming.",
            "Explain artificial intelligence.",
            "Help me create a professional website."
        ]

        cols = st.columns(2)

        for index, suggestion in enumerate(suggestions):

            with cols[index % 2]:

                if st.button(
                    suggestion,
                    key=f"suggestion_{index}",
                    use_container_width=True
                ):
                    st.session_state.pending_prompt = suggestion
                    st.rerun()

    # Chat messages

    for index, message in enumerate(
        st.session_state.messages
    ):

        with st.chat_message(message["role"]):

            st.markdown(message["content"])

            if message["role"] == "assistant":

                read_aloud(
                    message["content"],
                    f"chat_{index}"
                )

    # Attachments

    attachment = st.file_uploader(
        "＋ Attach Image or PDF",
        type=[
            "png",
            "jpg",
            "jpeg",
            "webp",
            "pdf"
        ],
        key="chat_attachment"
    )

    # Microphone

    st.markdown("#### 🎙 Voice Input")

    if hasattr(st, "audio_input"):

        audio = st.audio_input(
            "Record your message",
            key="chat_audio"
        )

        if audio:

            if st.button("Convert Voice to Text"):

                try:

                    with st.spinner("Transcribing voice..."):

                        transcript = transcribe_audio(audio)

                    if transcript:

                        st.session_state.voice_prompt = transcript

                        st.success(
                            "Voice converted successfully."
                        )

                        st.code(transcript)

                    else:
                        st.warning("No speech detected.")

                except Exception as exc:
                    show_error(exc)

    else:

        st.info(
            "Upgrade Streamlit to a version supporting audio_input."
        )

    prompt = st.chat_input(
        "Message NEXTGEN AI..."
    )

    if st.session_state.get("voice_prompt"):

        if st.button("Send Voice Message"):

            prompt = st.session_state.voice_prompt

            st.session_state.voice_prompt = ""

    if st.session_state.get("pending_prompt"):

        prompt = st.session_state.pending_prompt

        st.session_state.pending_prompt = None

    if prompt:

        user_text = prompt

        add_message("user", user_text)

        if len(st.session_state.messages) == 1:

            rename_chat(
                st.session_state.chat_id,
                user_text[:40]
            )

        try:

            with st.spinner("NEXTGEN AI is thinking..."):

                if attachment:

                    if attachment.type == "application/pdf":

                        document = read_pdf(attachment)

                        if not document.strip():
                            raise ValueError(
                                "PDF contains no readable text."
                            )

                        history = [
                            {
                                "role": "system",
                                "content": SYSTEM_PROMPT
                            },
                            {
                                "role": "user",
                                "content": (
                                    f"Question: {user_text}\n\n"
                                    f"PDF content:\n{document}"
                                )
                            }
                        ]

                        answer = ask_ai(history, provider)

                    elif attachment.type.startswith("image/"):

                        answer = analyze_image(
                            attachment,
                            user_text
                        )

                    else:

                        answer = ask_single(user_text)

                else:

                    history = [
                        {
                            "role": "system",
                            "content": SYSTEM_PROMPT
                        }
                    ]

                    history.extend(
                        st.session_state.messages[:-1][-30:]
                    )

                    answer = ask_ai(
                        history,
                        provider
                    )

            add_message("assistant", answer)

            st.session_state.last_answer = answer

        except Exception as exc:

            error_answer = (
                "AI Error: " + str(exc)[:700]
            )

            add_message(
                "assistant",
                error_answer
            )

        st.rerun()


# ============================================================
# VISION
# ============================================================

elif page == "Vision":

    hero(
        "👁 AI Vision",
        "Understand images using artificial intelligence."
    )

    image = st.file_uploader(
        "Upload an image",
        type=["png", "jpg", "jpeg", "webp"],
        key="vision_image"
    )

    question = st.text_area(
        "What should I understand?",
        placeholder="Describe this image..."
    )

    if image:

        st.image(
            image,
            use_container_width=True
        )

        if st.button("Analyze Image"):

            try:

                with st.spinner("Analyzing image..."):

                    result = analyze_image(
                        image,
                        question
                    )

                st.session_state.vision_result = result

                render_answer(
                    result,
                    "vision_answer"
                )

            except Exception as exc:
                show_error(exc)

    elif st.session_state.vision_result:

        render_answer(
            st.session_state.vision_result,
            "old_vision"
        )


# ============================================================
# CREATIVE STUDIO
# ============================================================

elif page == "Creative Studio":

    hero(
        "🎨 Creative Studio",
        "Create original AI images."
    )

    subject = st.text_area(
        "Describe your image",
        placeholder="A futuristic cinematic city..."
    )

    c1, c2 = st.columns(2)

    with c1:

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
                "Watercolor",
                "Minimalist"
            ]
        )

        ratio = st.selectbox(
            "Aspect Ratio",
            [
                "1:1",
                "9:16",
                "16:9",
                "4:5",
                "3:2"
            ]
        )

    with c2:

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
        "Extra details"
    )

    if st.button(
        "Generate AI Image",
        use_container_width=True
    ):

        if not subject.strip():

            st.warning("Enter an image description.")

        else:

            full_prompt = f"""
            {subject}

            Style: {style}
            Aspect ratio: {ratio}
            Lighting: {lighting}
            Quality: {quality}
            Details: {extra}

            Original composition, detailed artwork.
            """

            try:

                with st.spinner("Creating image..."):

                    result = generate_image(full_prompt)

                st.session_state.last_image = result

            except Exception as exc:

                show_error(exc)

    if st.session_state.last_image:

        st.markdown("### Generated Image")

        st.image(
            st.session_state.last_image,
            use_container_width=True
        )

        st.download_button(
            "Download Image",
            data=st.session_state.last_image,
            file_name="nextgen_image.png",
            mime="image/png"
        )


# ============================================================
# PDF ASSISTANT
# ============================================================

elif page == "PDF Assistant":

    hero(
        "📄 PDF Assistant",
        "Read documents and ask questions."
    )

    pdf = st.file_uploader(
        "Upload PDF",
        type=["pdf"],
        key="pdf_file"
    )

    question = st.text_area(
        "Ask about your document",
        placeholder="Summarize this PDF..."
    )

    if pdf and st.button("Analyze PDF"):

        try:

            with st.spinner("Reading PDF..."):

                content = read_pdf(pdf)

                if not content.strip():
                    raise ValueError(
                        "No readable text found."
                    )

                answer = ask_single(
                    f"""
                    Answer using the following document.

                    User question:
                    {question or "Summarize the document."}

                    Document:
                    {content}

                    Do not invent information.
                    """
                )

            st.session_state.pdf_result = answer

            render_answer(
                answer,
                "pdf_result"
            )

        except Exception as exc:
            show_error(exc)

    if st.session_state.pdf_result and not pdf:

        render_answer(
            st.session_state.pdf_result,
            "previous_pdf"
        )


# ============================================================
# STOCK MARKET
# ============================================================

elif page == "Stock Market":

    hero(
        "📈 Stock Market Explorer",
        "Explore company prices, historical charts and market concepts."
    )

    st.info(
        "Educational information only. Not personalized investment advice."
    )

    symbol = st.text_input(
        "Stock Symbol",
        value="AAPL"
    ).strip().upper()

    period = st.selectbox(
        "Historical Period",
        ["1 Month", "3 Months", "6 Months", "1 Year"]
    )

    days = {
        "1 Month": 30,
        "3 Months": 90,
        "6 Months": 180,
        "1 Year": 365
    }[period]

    if st.button("Load Stock Data"):

        try:

            with st.spinner("Fetching market data..."):

                quote = stock_quote(symbol)

                profile = stock_profile(symbol)

                candles = stock_candles(
                    symbol,
                    days
                )

                if candles.get("s") != "ok":

                    raise ValueError(
                        "Historical data unavailable."
                    )

                st.session_state.stock_result = {
                    "quote": quote,
                    "profile": profile,
                    "candles": candles
                }

        except Exception as exc:
            show_error(exc)

    market = st.session_state.stock_result

    if market:

        quote = market["quote"]

        profile = market["profile"]

        candles = market["candles"]

        st.markdown(
            f"### {profile.get('name', symbol)}"
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

        import pandas as pd

        dataframe = pd.DataFrame({
            "Date": pd.to_datetime(
                candles["t"],
                unit="s"
            ),
            "Close": candles["c"],
            "Open": candles["o"],
            "High": candles["h"],
            "Low": candles["l"],
            "Volume": candles["v"]
        })

        dataframe = dataframe.set_index("Date")

        st.markdown("### Price Chart")

        st.line_chart(
            dataframe[["Close"]]
        )

        st.markdown("### Volume Chart")

        st.bar_chart(
            dataframe[["Volume"]]
        )

        st.dataframe(
            dataframe.tail(15),
            use_container_width=True
        )

        st.caption(
            "Historical prices do not guarantee future performance."
        )


# ============================================================
# STOCK ANALYSIS
# ============================================================

elif page == "Stock Analysis":

    hero(
        "🔍 AI Stock Research",
        "Understand company data, news and risk factors."
    )

    symbol = st.text_input(
        "Company Symbol",
        value="AAPL",
        key="analysis_symbol"
    ).strip().upper()

    if st.button("Analyze Company"):

        try:

            with st.spinner("Collecting information..."):

                quote = stock_quote(symbol)

                profile = stock_profile(symbol)

                news = stock_news(symbol)

                headlines = "\n".join(
                    item.get("headline", "")
                    for item in news[:10]
                )

                prompt = f"""
                Analyze this company educationally.

                Symbol: {symbol}

                Company: {profile.get('name', 'Unknown')}

                Industry: {profile.get('finnhubIndustry', 'Unknown')}

                Country: {profile.get('country', 'Unknown')}

                Current Price: {quote.get('c')}

                Change: {quote.get('d')}

                Change Percentage: {quote.get('dp')}

                Previous Close: {quote.get('pc')}

                Recent Headlines:
                {headlines}

                Explain:

                1. Company overview.
                2. Price information.
                3. Recent news.
                4. Possible business risks.
                5. What a student should research.
                6. Missing information.
                7. Beginner summary.

                Never invent financial data.
                Do not provide guaranteed predictions.
                """

            with st.spinner("AI is researching..."):

                result = ask_single(prompt)

            st.markdown(
                f"### {profile.get('name', symbol)}"
            )

            st.metric(
                "Current Price",
                f"${quote.get('c', 0):,.2f}"
            )

            render_answer(
                result,
                "stock_report"
            )

            st.markdown("### Recent News Headlines")

            for item in news[:7]:

                st.write(
                    "• " + item.get("headline", "News")
                )

        except Exception as exc:
            show_error(exc)


# ============================================================
# BUILD STUDIO
# ============================================================

elif page == "Build Studio":

    hero(
        "🛠 Build Studio",
        "Create applications and websites using AI."
    )

    app_tab, website_tab, project_tab = st.tabs([
        "📱 App Builder",
        "🌐 Website Builder",
        "📁 My Project"
    ])

    with app_tab:

        st.markdown("### AI Application Builder")

        app_name = st.text_input(
            "Application Name",
            "my_ai_app",
            key="app_name"
        )

        app_description = st.text_area(
            "Describe your application",
            height=130,
            key="app_description"
        )

        app_features = st.text_area(
            "Features",
            placeholder="Dashboard, login, search, database...",
            key="app_features"
        )

        app_design = st.selectbox(
            "Design",
            [
                "Premium Dark",
                "Modern Minimal",
                "Neon",
                "Professional",
                "Colorful"
            ],
            key="app_design"
        )

        if st.button(
            "✦ Build My App",
            use_container_width=True
        ):

            if not app_description.strip():

                st.warning("Describe your app first.")

            else:

                try:

                    with st.spinner("Building application..."):

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

                    st.success("Project generated successfully.")

                except Exception as exc:
                    show_error(exc)

    with website_tab:

        st.markdown("### AI Website Builder")

        website_name = st.text_input(
            "Website Name",
            "my_website",
            key="website_name"
        )

        website_description = st.text_area(
            "Describe your website",
            height=130,
            key="website_description"
        )

        website_features = st.text_area(
            "Website Features",
            key="website_features"
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
            key="website_design"
        )

        if st.button(
            "✦ Build My Website",
            use_container_width=True
        ):

            if not website_description.strip():

                st.warning("Describe your website first.")

            else:

                try:

                    with st.spinner("Creating website..."):

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

                    st.success("Website files generated.")

                except Exception as exc:
                    show_error(exc)

    with project_tab:

        files = st.session_state.project_files

        if files:

            st.markdown(
                f"### {st.session_state.project_name}"
            )

            st.write(
                st.session_state.project_summary
            )

            selected = st.selectbox(
                "Preview File",
                list(files.keys())
            )

            extension = selected.split(".")[-1]

            language = {
                "py": "python",
                "html": "html",
                "css": "css",
                "js": "javascript",
                "json": "json",
                "md": "markdown"
            }.get(extension, "text")

            st.code(
                files[selected],
                language=language
            )

            project = {
                "name": st.session_state.project_name,
                "files": files
            }

            st.download_button(
                "⬇ Download Complete Project ZIP",
                data=make_zip(project),
                file_name=project["name"] + ".zip",
                mime="application/zip",
                use_container_width=True
            )

            st.info(
                "Install dependencies, configure API keys, "
                "test the generated project and deploy it separately."
            )

        else:

            st.info(
                "Build an app or website first. "
                "Your project files will appear here."
            )


# ============================================================
# SETTINGS
# ============================================================

elif page == "Settings":

    hero(
        "⚙ Settings",
        "Manage your AI workspace."
    )

    st.markdown("### API Connections")

    services = {
        "Groq": GROQ_KEY,
        "Gemini": GEMINI_KEY,
        "OpenAI": OPENAI_KEY,
        "Claude": ANTHROPIC_KEY,
        "Finnhub": FINNHUB_KEY,
        "Cloudflare": CLOUDFLARE_API_TOKEN,
        "Tavily": TAVILY_KEY
    }

    for name, key in services.items():

        status = "Connected key available" if key else "Not configured"

        st.write(
            f"**{name}:** {status}"
        )

    st.divider()

    st.markdown("### Model Information")

    st.write("Groq:", GROQ_MODEL)

    st.write("Gemini:", GEMINI_MODEL)

    st.write("OpenAI:", OPENAI_MODEL)

    st.write("Claude:", ANTHROPIC_MODEL)

    st.divider()

    st.markdown("### Workspace")

    st.write("Application:", APP_NAME)

    st.write("Database:", "SQLite")

    st.write("History:", "Locally stored")

    st.caption(
        "API keys are loaded from Streamlit Secrets or environment variables."
    )

    st.warning(
        "Never share your API keys or publish them in source code."
    )

    st.divider()

    if st.button("＋ Create New Chat"):

        start_new_chat()

        st.rerun()

    st.markdown("### Delete Current Chat")

    if st.button("Delete This Chat"):

        remove_chat(st.session_state.chat_id)

        st.session_state.chat_id = new_chat()

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
    ">
        ✦ NEXTGEN AI<br>
        Your Personal Intelligent Workspace
        <br>
        Built for learning, creativity and innovation.
    </div>
    """,
    unsafe_allow_html=True
)
