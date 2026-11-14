import os
import io
import re
import json
import sqlite3
import requests
import streamlit as st
import streamlit.components.v1 as components

from datetime import datetime
from dotenv import load_dotenv

load_dotenv()

# ============================================================
# NEXTGEN AI
# ============================================================

st.set_page_config(
    page_title="NEXTGEN AI",
    page_icon="✦",
    layout="wide",
    initial_sidebar_state="expanded"
)

APP_NAME = "NEXTGEN AI"
DB_PATH = "nextgen_v5.db"

GROK_MODEL = "grok-4.1"
GROQ_MODEL = "openai/gpt-oss-120b"
GEMINI_MODEL = "gemini-3.5-flash-lite"

GROK_KEY = os.getenv("GROK_API_KEY", "")
GROQ_KEY = os.getenv("GROQ_API_KEY", "")
GEMINI_KEY = os.getenv("GEMINI_API_KEY", "")
TAVILY_KEY = os.getenv("TAVILY_API_KEY", "")

CF_ACCOUNT = os.getenv("CLOUDFLARE_ACCOUNT_ID", "")
CF_TOKEN = os.getenv("CLOUDFLARE_API_TOKEN", "")
CF_LIVE_URL = os.getenv("CLOUDFLARE_VOICE_URL", "")

CREATOR_PROFILE = """
NEXTGEN AI was created by Arav.

Arav is a student at Swami Vivekanand Shiksha Niketan School.
He is a student developer and the creator of NEXTGEN AI.

He is interested in Artificial Intelligence, Python programming,
app development, technology, creative problem solving and digital
creativity.

He is continuously learning and exploring how modern AI systems
and software applications work.

When someone asks "Who is Arav?" or "Who am I?", introduce him
positively and respectfully using these facts.

Never invent awards, ranks, exam scores, qualifications,
professional experience, achievements or private information.
"""

SYSTEM_PROMPT = f"""
You are NEXTGEN AI, a helpful and intelligent AI assistant.

CREATOR PROFILE:
{CREATOR_PROFILE}

RULES:
- Reply in Hindi using Devanagari when the user writes in Hindi.
- Reply in English when the user writes in English.
- Be clear, friendly, accurate and helpful.
- Never invent facts, sources, prices or live information.
- Explain difficult topics in simple language.
- Use headings and bullet points when useful.
- Keep answers readable.
- For stock-market topics, provide educational information,
  explain risks and uncertainty, and never guarantee profits.
- Do not present personalized investment instructions as certainty.
"""

# ============================================================
# DATABASE
# ============================================================

def connect_db():
    return sqlite3.connect(DB_PATH, check_same_thread=False)


def init_db():
    con = connect_db()
    cur = con.cursor()

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

    cur.execute("""
        CREATE TABLE IF NOT EXISTS creations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT,
            content TEXT,
            created_at TEXT
        )
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS feedback (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            content TEXT,
            feedback TEXT,
            created_at TEXT
        )
    """)

    con.commit()
    con.close()


def create_chat(title="New Chat"):
    con = connect_db()
    cur = con.cursor()
    cur.execute(
        "INSERT INTO chats (title, created_at) VALUES (?, ?)",
        (title, datetime.now().isoformat())
    )
    chat_id = cur.lastrowid
    con.commit()
    con.close()
    return chat_id


def save_message(chat_id, role, content):
    con = connect_db()
    cur = con.cursor()

    cur.execute("""
        INSERT INTO messages (chat_id, role, content, created_at)
        VALUES (?, ?, ?, ?)
    """, (
        chat_id,
        role,
        content,
        datetime.now().isoformat()
    ))

    message_id = cur.lastrowid
    con.commit()
    con.close()
    return message_id


def get_messages(chat_id):
    con = connect_db()
    cur = con.cursor()

    cur.execute("""
        SELECT role, content
        FROM messages
        WHERE chat_id = ?
        ORDER BY id
    """, (chat_id,))

    rows = cur.fetchall()
    con.close()
    return rows


def get_chats():
    con = connect_db()
    cur = con.cursor()

    cur.execute("""
        SELECT id, title, created_at
        FROM chats
        ORDER BY id DESC
    """)

    rows = cur.fetchall()
    con.close()
    return rows


def update_chat_title(chat_id, title):
    con = connect_db()
    con.execute(
        "UPDATE chats SET title=? WHERE id=?",
        (title[:60], chat_id)
    )
    con.commit()
    con.close()


def delete_chat(chat_id):
    con = connect_db()
    con.execute("DELETE FROM messages WHERE chat_id=?", (chat_id,))
    con.execute("DELETE FROM chats WHERE id=?", (chat_id,))
    con.commit()
    con.close()


def save_creation(title, content):
    con = connect_db()
    con.execute("""
        INSERT INTO creations (title, content, created_at)
        VALUES (?, ?, ?)
    """, (title, content, datetime.now().isoformat()))
    con.commit()
    con.close()


def get_creations():
    con = connect_db()
    cur = con.cursor()
    cur.execute("""
        SELECT title, content, created_at
        FROM creations
        ORDER BY id DESC
    """)
    rows = cur.fetchall()
    con.close()
    return rows


init_db()

# ============================================================
# SESSION STATE
# ============================================================

defaults = {
    "page": "Dashboard",
    "chat_id": None,
    "messages": [],
    "pending_prompt": None,
    "last_answer": "",
    "last_prompt": "",
    "web_search_enabled": True
}

for key, value in defaults.items():
    if key not in st.session_state:
        st.session_state[key] = value

if st.session_state.chat_id is None:
    st.session_state.chat_id = create_chat()

# ============================================================
# DESIGN
# ============================================================

st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&display=swap');

html, body, [class*="css"] {
    font-family: 'Inter', sans-serif;
}

.stApp {
    background:
        radial-gradient(ellipse at 15% 5%, #20205a 0%, transparent 38%),
        radial-gradient(ellipse at 90% 10%, #30164f 0%, transparent 35%),
        linear-gradient(135deg, #080b1a, #10132b 55%, #0a1020);
    color: white;
}

section[data-testid="stSidebar"] {
    background: linear-gradient(180deg, #10132b, #0b1020);
    border-right: 1px solid rgba(255,255,255,0.08);
}

h1, h2, h3, h4, p, label, span {
    color: white;
}

.hero {
    padding: 35px;
    border-radius: 24px;
    background: linear-gradient(120deg,
        rgba(77,75,210,0.32),
        rgba(137,57,185,0.22));
    border: 1px solid rgba(255,255,255,0.12);
    margin-bottom: 24px;
}

.hero h1 {
    font-size: 42px;
    font-weight: 800;
    margin-bottom: 8px;
}

.panel {
    padding: 22px;
    border-radius: 18px;
    background: rgba(255,255,255,0.055);
    border: 1px solid rgba(255,255,255,0.10);
    margin-bottom: 16px;
}

.metric {
    padding: 20px;
    border-radius: 17px;
    background: linear-gradient(135deg,
        rgba(79,83,190,0.24),
        rgba(130,60,170,0.16));
    border: 1px solid rgba(255,255,255,0.12);
}

.metric h2 {
    font-size: 27px;
    margin: 5px 0;
}

.stButton > button {
    border-radius: 12px;
    border: 1px solid rgba(255,255,255,0.15);
    background: linear-gradient(110deg, #5556d9, #8749bb);
    color: white !important;
    font-weight: 600;
    min-height: 42px;
    transition: 0.2s;
}

.stButton > button:hover {
    border-color: #a8a5ff;
    transform: translateY(-1px);
}

.stTextInput input,
.stTextArea textarea {
    background: rgba(255,255,255,0.07) !important;
    color: white !important;
    border: 1px solid rgba(255,255,255,0.15) !important;
    border-radius: 12px !important;
}

[data-testid="stChatMessage"] {
    background: rgba(255,255,255,0.045);
    border: 1px solid rgba(255,255,255,0.08);
    border-radius: 16px;
}

[data-testid="stChatMessage"] p,
[data-testid="stChatMessage"] li,
[data-testid="stChatMessage"] div,
[data-testid="stMarkdownContainer"] p {
    color: #FFFFFF !important;
}

[data-testid="stChatInput"] textarea {
    color: white !important;
}

div[data-testid="stExpander"] {
    background: rgba(255,255,255,0.04);
    border-radius: 12px;
}

footer {
    visibility: hidden;
}

</style>
""", unsafe_allow_html=True)

# ============================================================
# AI PROVIDERS
# ============================================================

def grok_request(messages):
    if not GROK_KEY:
        raise RuntimeError("GROK_API_KEY is missing.")

    payload = {
        "model": GROK_MODEL,
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            *messages
        ],
        "temperature": 0.7,
        "max_tokens": 4096
    }

    response = requests.post(
        "https://api.x.ai/v1/chat/completions",
        headers={
            "Authorization": f"Bearer {GROK_KEY}",
            "Content-Type": "application/json"
        },
        json=payload,
        timeout=90
    )

    response.raise_for_status()
    data = response.json()
    return data["choices"][0]["message"]["content"]


def gemini_request(messages):
    if not GEMINI_KEY:
        raise RuntimeError("GEMINI_API_KEY is missing.")

    contents = []

    for message in messages:
        role = "model" if message["role"] == "assistant" else "user"

        contents.append({
            "role": role,
            "parts": [{"text": message["content"]}]
        })

    url = (
        "https://generativelanguage.googleapis.com/v1beta/models/"
        f"{GEMINI_MODEL}:generateContent?key={GEMINI_KEY}"
    )

    payload = {
        "system_instruction": {
            "parts": [{"text": SYSTEM_PROMPT}]
        },
        "contents": contents,
        "generationConfig": {
            "temperature": 0.7,
            "maxOutputTokens": 4096
        }
    }

    response = requests.post(
        url,
        json=payload,
        timeout=90
    )

    response.raise_for_status()
    data = response.json()

    return data["candidates"][0]["content"]["parts"][0]["text"]


def groq_request(messages):
    if not GROQ_KEY:
        raise RuntimeError("GROQ_API_KEY is missing.")

    payload = {
        "model": GROQ_MODEL,
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            *messages
        ],
        "temperature": 0.7,
        "max_completion_tokens": 4096
    }

    response = requests.post(
        "https://api.groq.com/openai/v1/chat/completions",
        headers={
            "Authorization": f"Bearer {GROQ_KEY}",
            "Content-Type": "application/json"
        },
        json=payload,
        timeout=90
    )

    response.raise_for_status()
    return response.json()["choices"][0]["message"]["content"]


def ask_ai(messages):
    errors = []

    providers = [
        ("Grok", grok_request),
        ("Gemini", gemini_request),
        ("Groq", groq_request)
    ]

    for provider_name, provider_function in providers:
        try:
            answer = provider_function(messages)

            if answer and answer.strip():
                return answer.strip(), provider_name

        except Exception as exc:
            errors.append(
                f"{provider_name}: {str(exc)[:250]}"
            )

    raise RuntimeError(
        "All AI providers failed:\n" + "\n".join(errors)
    )

# ============================================================
# SMART WEB SEARCH
# ============================================================

def needs_web_search(query):
    words = [
        "today", "latest", "current", "recent", "news",
        "weather", "live", "price", "stock price",
        "market today", "exchange rate", "who won",
        "this week", "right now", "breaking",
        "आज", "अभी", "ताजा", "ताज़ा", "लेटेस्ट",
        "मौजूदा", "समाचार", "खबर", "भाव",
        "शेयर प्राइस", "आज का मौसम", "लाइव"
    ]

    q = query.lower()
    return any(word in q for word in words)


def web_search(query, max_results=5):
    if not TAVILY_KEY:
        return ""

    response = requests.post(
        "https://api.tavily.com/search",
        json={
            "api_key": TAVILY_KEY,
            "query": query,
            "search_depth": "basic",
            "max_results": max_results,
            "include_answer": True
        },
        timeout=30
    )

    response.raise_for_status()
    data = response.json()

    results = []

    if data.get("answer"):
        results.append("Search summary: " + data["answer"])

    for item in data.get("results", []):
        results.append(
            f"Title: {item.get('title', '')}\n"
            f"Content: {item.get('content', '')}\n"
            f"URL: {item.get('url', '')}"
        )

    return "\n\n".join(results)


def smart_web_search(query):
    if not needs_web_search(query):
        return ""

    if not TAVILY_KEY:
        return ""

    try:
        return web_search(query)
    except Exception:
        return ""

# ============================================================
# FOLLOW-UP SUGGESTIONS
# ============================================================

def generate_followups(prompt, answer):
    instruction = f"""
Generate exactly five short follow-up questions based on this
conversation.

User question:
{prompt[:1000]}

Assistant answer:
{answer[:2500]}

Return ONLY a valid JSON array containing five short strings.
Do not include markdown or explanations.
"""

    try:
        result, _ = ask_ai([
            {"role": "user", "content": instruction}
        ])

        match = re.search(r"\[.*\]", result, re.DOTALL)

        if match:
            items = json.loads(match.group(0))

            if isinstance(items, list):
                items = [
                    str(item).strip()
                    for item in items
                    if str(item).strip()
                ]

                if len(items) >= 5:
                    return items[:5]

    except Exception:
        pass

    return [
        "इसे आसान भाषा में समझाओ",
        "एक उदाहरण देकर समझाओ",
        "इसके मुख्य पॉइंट बताओ",
        "इसका अगला स्टेप क्या है?",
        "इस विषय पर और जानकारी दो"
    ]

# ============================================================
# RESPONSE CONTROLS
# ============================================================

def response_controls(content, index):
    escaped = json.dumps(content)

    components.html(
        f"""
        <div style="
            display:flex;
            gap:8px;
            flex-wrap:wrap;
            font-family:Arial;
        ">
            <button onclick="copyText()"
                style="padding:8px 13px;border-radius:9px;
                background:#25294c;color:white;border:1px solid #555;">
                Copy
            </button>

            <button onclick="speakText()"
                style="padding:8px 13px;border-radius:9px;
                background:#4545a8;color:white;border:0;">
                🔊 Read Aloud
            </button>

            <button onclick="stopSpeech()"
                style="padding:8px 13px;border-radius:9px;
                background:#773b55;color:white;border:0;">
                ■ Stop
            </button>
        </div>

        <script>
        const answer = {escaped};

        function copyText() {{
            navigator.clipboard.writeText(answer);
        }}

        function speakText() {{
            window.speechSynthesis.cancel();

            const utterance = new SpeechSynthesisUtterance(answer);

            utterance.lang = /[\\u0900-\\u097F]/.test(answer)
                ? "hi-IN" : "en-US";

            window.speechSynthesis.speak(utterance);
        }}

        function stopSpeech() {{
            window.speechSynthesis.cancel();
        }}
        </script>
        """,
        height=48
    )

# ============================================================
# SIDEBAR
# ============================================================

with st.sidebar:
    st.markdown("# ✦ NEXTGEN AI")
    st.caption("Your intelligent workspace")

    st.markdown("---")

    navigation = [
        "Dashboard",
        "AI Chat",
        "AI Image Studio",
        "Stock Market",
        "Tool Center",
        "PDF Assistant",
        "Chat History",
        "My Creations",
        "Settings",
        "About"
    ]

    for item in navigation:
        if st.button(
            item,
            key=f"nav_{item}",
            use_container_width=True
        ):
            st.session_state.page = item
            st.rerun()

    st.markdown("---")
    st.caption("Recent conversations")

    for chat in get_chats()[:6]:
        if st.button(
            chat[1] or "New Chat",
            key=f"chat_{chat[0]}",
            use_container_width=True
        ):
            st.session_state.chat_id = chat[0]
            st.session_state.messages = get_messages(chat[0])
            st.session_state.page = "AI Chat"
            st.rerun()

    st.markdown("---")

    if st.button("＋ New Chat", use_container_width=True):
        st.session_state.chat_id = create_chat()
        st.session_state.messages = []
        st.session_state.page = "AI Chat"
        st.rerun()

    st.caption("NEXTGEN AI · Version 1.0")

# ============================================================
# DASHBOARD
# ============================================================

page = st.session_state.page

if page == "Dashboard":

    st.markdown("""
    <div class="hero">
        <h1>✦ NEXTGEN AI</h1>
        <p>Your personal AI workspace for learning,
        creativity, research and productivity.</p>
    </div>
    """, unsafe_allow_html=True)

    c1, c2, c3 = st.columns(3)

    with c1:
        st.markdown("""
        <div class="metric">
            <p>AI Assistant</p>
            <h2>Ready</h2>
            <small>Multi-provider AI</small>
        </div>
        """, unsafe_allow_html=True)

    with c2:
        st.markdown("""
        <div class="metric">
            <p>Smart Search</p>
            <h2>Enabled</h2>
            <small>Search when needed</small>
        </div>
        """, unsafe_allow_html=True)

    with c3:
        st.markdown("""
        <div class="metric">
            <p>Workspace</p>
            <h2>10 Tools</h2>
            <small>One AI platform</small>
        </div>
        """, unsafe_allow_html=True)

    st.markdown("## Explore NEXTGEN AI")

    cards = [
        ("AI Chat", "Chat with your AI assistant."),
        ("AI Image Studio", "Create images using AI."),
        ("Stock Market", "Explore market data and charts."),
        ("Tool Center", "Writing, coding and productivity."),
        ("PDF Assistant", "Work with PDF documents."),
        ("My Creations", "Access saved creations.")
    ]

    cols = st.columns(3)

    for i, (name, description) in enumerate(cards):
        with cols[i % 3]:
            st.markdown(
                f"""
                <div class="panel">
                    <h3>{name}</h3>
                    <p>{description}</p>
                </div>
                """,
                unsafe_allow_html=True
            )

            if st.button(
                f"Open {name}",
                key=f"open_{name}",
                use_container_width=True
            ):
                st.session_state.page = name
                st.rerun()

# ============================================================
# AI CHAT
# ============================================================

elif page == "AI Chat":

    st.markdown("## ✦ AI Chat")
    st.caption("Ask anything. NEXTGEN AI is ready.")

    if not st.session_state.messages:
        st.session_state.messages = get_messages(
            st.session_state.chat_id
        )

    for index, (role, content) in enumerate(
        st.session_state.messages
    ):
        with st.chat_message(role):
            st.markdown(content)

            if role == "assistant":
                response_controls(content, index)

    pending = st.session_state.pending_prompt
    user_text = pending

    if pending:
        st.session_state.pending_prompt = None

    try:
        chat_input = st.chat_input(
            "Message NEXTGEN AI...",
            accept_file=True,
            file_type=["txt", "pdf"],
            max_upload_size=20
        )
    except TypeError:
        chat_input = st.chat_input("Message NEXTGEN AI...")

    if chat_input:
        if isinstance(chat_input, str):
            user_text = chat_input
        else:
            user_text = getattr(chat_input, "text", "") or ""

    if user_text:

        user_text = user_text.strip()

        if user_text:
            st.session_state.messages.append(
                ("user", user_text)
            )

            save_message(
                st.session_state.chat_id,
                "user",
                user_text
            )

            with st.chat_message("user"):
                st.markdown(user_text)

            history = []

            for role, content in st.session_state.messages[-20:]:
                history.append({
                    "role": role,
                    "content": content
                })

            with st.chat_message("assistant"):
                with st.spinner("NEXTGEN AI is thinking..."):

                    try:
                        search_context = smart_web_search(user_text)

                        if search_context:
                            history.append({
                                "role": "user",
                                "content": (
                                    "Use this recent web information "
                                    "where relevant. Do not invent facts.\n\n"
                                    + search_context
                                )
                            })

                        answer, provider = ask_ai(history)

                        if search_context:
                            answer += (
                                "\n\n*Live web context was consulted. "
                                "Check linked source details for confirmation.*"
                            )

                        st.markdown(answer)
                        st.caption(f"Powered by {provider}")

                        response_controls(answer, len(
                            st.session_state.messages
                        ))

                        save_message(
                            st.session_state.chat_id,
                            "assistant",
                            answer
                        )

                        st.session_state.messages.append(
                            ("assistant", answer)
                        )

                        st.session_state.last_answer = answer
                        st.session_state.last_prompt = user_text

                        if len(st.session_state.messages) == 2:
                            update_chat_title(
                                st.session_state.chat_id,
                                user_text[:45]
                            )

                    except Exception as exc:
                        st.error(
                            "NEXTGEN AI could not respond. "
                            "Check your API keys and internet connection."
                        )
                        st.caption(str(exc)[:500])

            st.rerun()

    if st.session_state.last_answer:
        st.markdown("---")
        st.markdown("**Suggested next questions**")

        if st.button(
            "Generate suggestions",
            key="generate_followups"
        ):
            with st.spinner("Generating suggestions..."):
                suggestions = generate_followups(
                    st.session_state.last_prompt,
                    st.session_state.last_answer
                )

            st.session_state.followups = suggestions
            st.rerun()

        suggestions = st.session_state.get("followups", [])

        if suggestions:
            for start in range(0, len(suggestions), 3):
                cols = st.columns(3)

                for j, suggestion in enumerate(
                    suggestions[start:start + 3]
                ):
                    with cols[j]:
                        if st.button(
                            suggestion,
                            key=f"follow_{start}_{j}",
                            use_container_width=True
                        ):
                            st.session_state.pending_prompt = suggestion
                            st.rerun()

    st.markdown("---")

    if CF_LIVE_URL:
        st.link_button(
            "🎙 Open Live Voice",
            CF_LIVE_URL,
            use_container_width=True
        )
    else:
        st.caption(
            "Live Voice URL is not configured. "
            "Set CLOUDFLARE_VOICE_URL to enable the external voice link."
        )

    st.caption(
        "Grok Primary · Gemini Backup · Groq Fallback · Smart Search"
    )

# ============================================================
# IMAGE STUDIO
# ============================================================

elif page == "AI Image Studio":

    st.markdown("## ✦ AI Image Studio")
    st.caption("Create images with your text prompts.")

    prompt = st.text_area(
        "Describe your image",
        placeholder="A cinematic futuristic city at night..."
    )

    style = st.selectbox(
        "Image style",
        [
            "Cinematic",
            "Realistic",
            "Digital Art",
            "Anime",
            "Fantasy",
            "3D Render",
            "Minimal"
        ]
    )

    if st.button("Generate Image", use_container_width=True):

        if not prompt.strip():
            st.warning("Please enter an image prompt.")

        elif not CF_ACCOUNT or not CF_TOKEN:
            st.error(
                "Cloudflare API credentials are missing. "
                "Configure CLOUDFLARE_ACCOUNT_ID and "
                "CLOUDFLARE_API_TOKEN."
            )

        else:
            final_prompt = (
                f"{prompt}. Style: {style}. "
                "High quality, detailed composition."
            )

            url = (
                "https://api.cloudflare.com/client/v4/accounts/"
                f"{CF_ACCOUNT}/ai/run/@cf/black-forest-labs/flux-1-schnell"
            )

            with st.spinner("Creating your image..."):
                try:
                    response = requests.post(
                        url,
                        headers={
                            "Authorization": f"Bearer {CF_TOKEN}"
                        },
                        json={
                            "prompt": final_prompt,
                            "steps": 4
                        },
                        timeout=120
                    )

                    response.raise_for_status()

                    st.image(
                        response.content,
                        caption="Generated with NEXTGEN AI",
                        use_container_width=True
                    )

                    save_creation(
                        "AI Image",
                        final_prompt
                    )

                    st.success("Image generated successfully.")

                except Exception as exc:
                    st.error("Image generation failed.")
                    st.caption(str(exc)[:400])

# ============================================================
# STOCK MARKET
# ============================================================

elif page == "Stock Market":

    st.markdown("## ✦ Stock Market Explorer")
    st.caption(
        "Educational market-data explorer. "
        "Market data may be delayed or unavailable."
    )

    ticker = st.text_input(
        "Stock symbol",
        value="AAPL"
    ).upper().strip()

    st.info(
        "This section is for learning and market research. "
        "It does not provide guaranteed returns or personalized "
        "buy/sell instructions."
    )

    if st.button("Load Stock Chart", use_container_width=True):

        try:
            import yfinance as yf

            with st.spinner("Loading market data..."):
                stock = yf.Ticker(ticker)
                history = stock.history(period="1mo")

            if history.empty:
                st.warning("No market data found for this symbol.")

            else:
                st.markdown(f"### {ticker} — Recent Price History")

                st.line_chart(
                    history["Close"],
                    use_container_width=True
                )

                latest = float(history["Close"].iloc[-1])

                st.metric(
                    "Latest available close",
                    f"{latest:.2f}"
                )

                st.caption(
                    "Historical prices do not predict future performance."
                )

        except ImportError:
            st.error(
                "yfinance is not installed. Run: pip install yfinance"
            )

        except Exception as exc:
            st.error("Could not load stock data.")
            st.caption(str(exc)[:400])

    st.markdown("---")
    st.markdown("### Learn about investing")

    st.markdown("""
    - Understand what a stock represents.
    - Learn the difference between price and company value.
    - Study diversification and risk.
    - Compare historical performance carefully.
    - Never assume that past returns guarantee future returns.
    """)

# ============================================================
# TOOL CENTER
# ============================================================

elif page == "Tool Center":

    st.markdown("## ✦ Tool Center")
    st.caption("AI-powered tools for everyday tasks.")

    tool = st.selectbox(
        "Choose a tool",
        [
            "Writing Assistant",
            "Study Assistant",
            "Coding Assistant",
            "YouTube Ideas",
            "Story Generator",
            "Translation",
            "Email Writer",
            "Math Explainer",
            "Research Assistant",
            "Business Ideas"
        ]
    )

    details = st.text_area(
        "What do you want NEXTGEN AI to do?",
        height=150
    )

    if st.button("Run Tool", use_container_width=True):

        if not details.strip():
            st.warning("Enter your instructions first.")

        else:
            tool_prompt = f"""
            Act as a specialist {tool}.
            Help the user with this request:

            {details}

            Give a useful, structured and accurate result.
            """

            with st.spinner("Working..."):
                try:
                    result, provider = ask_ai([
                        {"role": "user", "content": tool_prompt}
                    ])

                    st.markdown("### Result")
                    st.markdown(result)
                    st.caption(f"Powered by {provider}")

                    save_creation(tool, result)

                except Exception as exc:
                    st.error("Tool request failed.")
                    st.caption(str(exc)[:400])

# ============================================================
# PDF ASSISTANT
# ============================================================

elif page == "PDF Assistant":

    st.markdown("## ✦ PDF Assistant")

    uploaded_pdf = st.file_uploader(
        "Upload a PDF document",
        type=["pdf"]
    )

    question = st.text_input(
        "What would you like to know about this PDF?"
    )

    if uploaded_pdf and question:

        if st.button("Ask about PDF"):

            try:
                from pypdf import PdfReader

                reader = PdfReader(uploaded_pdf)
                extracted_text = "\n".join(
                    page.extract_text() or ""
                    for page in reader.pages
                )

                if not extracted_text.strip():
                    st.warning(
                        "No readable text found. "
                        "This PDF may contain scanned pages."
                    )

                else:
                    pdf_prompt = f"""
                    Answer the user's question using the PDF text.

                    PDF TEXT:
                    {extracted_text[:25000]}

                    QUESTION:
                    {question}
                    """

                    with st.spinner("Reading the PDF..."):
                        answer, provider = ask_ai([
                            {"role": "user", "content": pdf_prompt}
                        ])

                    st.markdown(answer)
                    st.caption(f"Powered by {provider}")

            except ImportError:
                st.error("Install pypdf using: pip install pypdf")

            except Exception as exc:
                st.error("Could not process the PDF.")
                st.caption(str(exc)[:400])

# ============================================================
# CHAT HISTORY
# ============================================================

elif page == "Chat History":

    st.markdown("## ✦ Chat History")

    chats = get_chats()

    if not chats:
        st.info("No conversations yet.")

    for chat_id, title, created in chats:

        with st.expander(
            f"{title or 'New Chat'} · {created[:16]}"
        ):

            messages = get_messages(chat_id)

            for role, content in messages:
                st.markdown(
                    f"**{role.title()}**\n\n{content}"
                )

            c1, c2 = st.columns(2)

            with c1:
                if st.button(
                    "Open Chat",
                    key=f"history_open_{chat_id}"
                ):
                    st.session_state.chat_id = chat_id
                    st.session_state.messages = messages
                    st.session_state.page = "AI Chat"
                    st.rerun()

            with c2:
                if st.button(
                    "Delete Chat",
                    key=f"history_delete_{chat_id}"
                ):
                    delete_chat(chat_id)

                    if st.session_state.chat_id == chat_id:
                        st.session_state.chat_id = create_chat()
                        st.session_state.messages = []

                    st.rerun()

# ============================================================
# MY CREATIONS
# ============================================================

elif page == "My Creations":

    st.markdown("## ✦ My Creations")

    creations = get_creations()

    if not creations:
        st.info("Your saved creations will appear here.")

    for title, content, created in creations:
        with st.expander(
            f"{title} · {created[:16]}"
        ):
            st.markdown(content)

            st.download_button(
                "Download as TXT",
                data=content,
                file_name=f"{title.lower().replace(' ', '_')}.txt",
                mime="text/plain",
                key=f"download_{created}_{title}"
            )

# ============================================================
# SETTINGS
# ============================================================

elif page == "Settings":

    st.markdown("## ✦ Settings")

    st.markdown("### AI Provider Status")

    provider_status = {
        "Grok": bool(GROK_KEY),
        "Gemini": bool(GEMINI_KEY),
        "Groq": bool(GROQ_KEY),
        "Tavily Search": bool(TAVILY_KEY),
        "Cloudflare Images": bool(CF_ACCOUNT and CF_TOKEN)
    }

    for name, active in provider_status.items():
        if active:
            st.success(f"{name}: API key configured")
        else:
            st.warning(f"{name}: Not configured")

    st.markdown("---")

    st.markdown("### Web Search")

    st.session_state.web_search_enabled = st.toggle(
        "Allow automatic web search for current information",
        value=st.session_state.web_search_enabled
    )

    st.caption(
        "Search is only attempted for queries that appear to need "
        "current information."
    )

# ============================================================
# ABOUT
# ============================================================

elif page == "About":

    st.markdown("""
    <div class="hero">
        <h1>About NEXTGEN AI</h1>
        <p>An AI-powered workspace for learning, creativity,
        research and productivity.</p>
    </div>
    """, unsafe_allow_html=True)

    st.markdown("### About the Creator")

    st.markdown("""
    <div class="panel">
        <h2>Arav</h2>
        <p>
        Arav is a student at Swami Vivekanand Shiksha Niketan School
        and the creator of NEXTGEN AI.
        </p>
        <p>
        He is interested in Artificial Intelligence, Python,
        app development, technology and creative problem solving.
        He enjoys learning how software and AI applications are built.
        </p>
        <p>
        NEXTGEN AI represents his interest in exploring technology
        and building useful digital experiences.
        </p>
    </div>
    """, unsafe_allow_html=True)

    st.markdown("### Platform Features")

    st.markdown("""
    - Multi-provider AI assistant
    - Smart web search
    - AI Image Studio
    - PDF Assistant
    - Stock Market Explorer
    - Chat History
    - Saved Creations
    - Read Aloud controls
    """)

    st.caption(
        "NEXTGEN AI · Created by Arav · Version 1.0"
    )
