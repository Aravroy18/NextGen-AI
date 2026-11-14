import os
import io
import re
import json
import time
import zipfile
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

SYSTEM_PROMPT = """
You are NEXTGEN AI, a helpful, capable, honest AI assistant.

Language:
- Reply in Hindi (Devanagari) when the user writes in Hindi.
- Reply in English when the user writes in English.
- Use clear, natural language.

Creator profile:
NEXTGEN AI was created by Arav.
Arav is a student at Swami Vivekanand Shiksha Niketan School.
He is interested in artificial intelligence, Python, app development,
technology, creative problem solving and digital creativity.
When asked who Arav is, introduce him positively and respectfully.
Do not invent awards, ranks, exam scores, qualifications, or achievements.

Rules:
- Be accurate and do not invent facts.
- Never claim that you performed an action you did not perform.
- For current information, use search results when available.
- If live data is unavailable, clearly say so.
- Explain coding steps clearly.
- For stock-market topics, provide educational information only.
  Explain uncertainty and risk. Never promise returns or guaranteed profits.
- Do not expose API keys, credentials, or private configuration.
"""

# ============================================================
# DATABASE
# ============================================================

def connect_db():
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    conn = connect_db()
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

    conn.commit()
    conn.close()


def create_chat(title="New Chat"):
    conn = connect_db()
    cur = conn.cursor()
    cur.execute(
        "INSERT INTO chats (title, created_at) VALUES (?, ?)",
        (title, datetime.now().isoformat())
    )
    chat_id = cur.lastrowid
    conn.commit()
    conn.close()
    return chat_id


def save_message(chat_id, role, content):
    conn = connect_db()
    conn.execute(
        """INSERT INTO messages (chat_id, role, content, created_at)
           VALUES (?, ?, ?, ?)""",
        (chat_id, role, content, datetime.now().isoformat())
    )
    conn.commit()
    conn.close()


def get_messages(chat_id):
    conn = connect_db()
    rows = conn.execute(
        """SELECT role, content FROM messages
           WHERE chat_id = ? ORDER BY id""",
        (chat_id,)
    ).fetchall()
    conn.close()
    return [{"role": r["role"], "content": r["content"]} for r in rows]


def get_chats():
    conn = connect_db()
    rows = conn.execute(
        "SELECT * FROM chats ORDER BY id DESC"
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def update_chat_title(chat_id, title):
    conn = connect_db()
    conn.execute(
        "UPDATE chats SET title = ? WHERE id = ?",
        (title[:60], chat_id)
    )
    conn.commit()
    conn.close()


def delete_chat(chat_id):
    conn = connect_db()
    conn.execute("DELETE FROM messages WHERE chat_id = ?", (chat_id,))
    conn.execute("DELETE FROM chats WHERE id = ?", (chat_id,))
    conn.commit()
    conn.close()


def save_creation(title, content):
    conn = connect_db()
    conn.execute(
        "INSERT INTO creations (title, content, created_at) VALUES (?, ?, ?)",
        (title, content, datetime.now().isoformat())
    )
    conn.commit()
    conn.close()


def get_creations():
    conn = connect_db()
    rows = conn.execute(
        "SELECT * FROM creations ORDER BY id DESC"
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


init_db()

# ============================================================
# SESSION STATE
# ============================================================

defaults = {
    "page": "Dashboard",
    "chat_id": None,
    "messages": [],
    "last_answer": "",
    "last_prompt": "",
    "followups": [],
    "web_search_enabled": True,
    "tool_output": "",
    "tool_prompt": "",
    "project_files": {},
    "project_type": "",
    "project_name": "",
    "selected_project_file": "",
    "stock_watchlist": ["AAPL", "MSFT", "NVDA", "RELIANCE.NS", "TCS.NS"],
}

for key, value in defaults.items():
    if key not in st.session_state:
        st.session_state[key] = value


def go_to(page):
    st.session_state.page = page
    st.rerun()


# ============================================================
# PREMIUM DESIGN
# ============================================================

st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800;900&display=swap');

html, body, [class*="css"] {
    font-family: 'Inter', sans-serif;
}

.stApp {
    background:
      radial-gradient(circle at 10% 0%, rgba(95,55,190,.16), transparent 30%),
      radial-gradient(circle at 90% 10%, rgba(20,120,220,.12), transparent 28%),
      #080b16;
    color: #f5f6ff;
}

header[data-testid="stHeader"] {
    background: rgba(8,11,22,.75);
}

[data-testid="stSidebar"] {
    background: linear-gradient(180deg,#10162a,#0b1020);
    border-right: 1px solid rgba(255,255,255,.08);
}

[data-testid="stSidebar"] * {
    color: #eef0ff;
}

.block-container {
    padding-top: 1.7rem;
    padding-bottom: 3rem;
    max-width: 1500px;
}

h1, h2, h3, h4, p, label {
    color: #f5f6ff;
}

.hero {
    padding: 34px;
    border-radius: 25px;
    background:
      linear-gradient(115deg,rgba(91,48,180,.40),rgba(21,87,160,.22)),
      #11182b;
    border: 1px solid rgba(170,150,255,.22);
    box-shadow: 0 18px 55px rgba(0,0,0,.25);
    margin-bottom: 22px;
}

.hero-kicker {
    color: #b9a7ff;
    font-size: 12px;
    font-weight: 800;
    letter-spacing: 2px;
    text-transform: uppercase;
}

.hero-title {
    font-size: clamp(30px,4vw,48px);
    line-height: 1.12;
    font-weight: 900;
    margin: 12px 0;
    color: white;
}

.hero-sub {
    color: #c4cbe0;
    font-size: 15px;
    line-height: 1.7;
    max-width: 800px;
}

.panel {
    background: linear-gradient(145deg,#151d32,#101729);
    border: 1px solid rgba(255,255,255,.08);
    padding: 22px;
    border-radius: 19px;
    margin-bottom: 16px;
}

.feature-card {
    background: linear-gradient(145deg,#171f36,#101729);
    border: 1px solid rgba(160,150,255,.14);
    border-radius: 18px;
    padding: 20px;
    min-height: 160px;
    margin-bottom: 12px;
    transition: .2s ease;
}

.feature-card:hover {
    border-color: rgba(160,140,255,.55);
    transform: translateY(-2px);
}

.feature-icon {
    font-size: 28px;
    margin-bottom: 12px;
}

.feature-title {
    font-size: 17px;
    font-weight: 800;
    color: white;
    margin-bottom: 7px;
}

.feature-desc {
    color: #aeb9d0;
    font-size: 12px;
    line-height: 1.6;
}

.metric-card {
    background: #121a2d;
    border: 1px solid rgba(255,255,255,.08);
    border-radius: 17px;
    padding: 17px;
}

.metric-label {
    color: #aab5ce;
    font-size: 12px;
}

.metric-value {
    color: white;
    font-size: 23px;
    font-weight: 800;
    margin-top: 5px;
}

div.stButton > button {
    border-radius: 11px;
    border: 1px solid rgba(170,150,255,.22);
    background: linear-gradient(100deg,#6944ce,#2869bb);
    color: white;
    font-weight: 700;
    min-height: 42px;
    transition: .2s ease;
}

div.stButton > button:hover {
    border-color: #a994ff;
    filter: brightness(1.13);
}

.stTextInput input, .stTextArea textarea,
.stSelectbox div[data-baseweb="select"],
.stNumberInput input {
    background: #111a2e !important;
    color: white !important;
    border-color: rgba(255,255,255,.13) !important;
    border-radius: 10px !important;
}

[data-testid="stChatMessage"] {
    background: rgba(20,29,49,.82);
    border: 1px solid rgba(255,255,255,.07);
    border-radius: 16px;
    padding: 14px;
    margin-bottom: 12px;
}

[data-testid="stChatInput"] {
    background: #111a2e;
    border: 1px solid rgba(160,145,255,.30);
    border-radius: 16px;
}

[data-testid="stChatInput"] textarea {
    color: white !important;
}

div[data-testid="stMarkdownContainer"] p {
    line-height: 1.65;
}

hr {
    border-color: rgba(255,255,255,.09);
}

.small-muted {
    color: #9eabc5;
    font-size: 12px;
}

.section-heading {
    font-size: 23px;
    font-weight: 850;
    margin: 15px 0 5px;
}

@media(max-width: 800px) {
    .hero { padding: 23px; }
    .feature-card { min-height: 140px; }
    .block-container { padding-left: 1rem; padding-right: 1rem; }
}
</style>
""", unsafe_allow_html=True)


def hero(title, subtitle, kicker="NEXTGEN AI"):
    st.markdown(f"""
    <div class="hero">
      <div class="hero-kicker">{kicker}</div>
      <div class="hero-title">{title}</div>
      <div class="hero-sub">{subtitle}</div>
    </div>
    """, unsafe_allow_html=True)


def feature_card(icon, title, description):
    st.markdown(f"""
    <div class="feature-card">
      <div class="feature-icon">{icon}</div>
      <div class="feature-title">{title}</div>
      <div class="feature-desc">{description}</div>
    </div>
    """, unsafe_allow_html=True)


# ============================================================
# AI PROVIDERS
# ============================================================

def grok_request(messages):
    if not GROK_KEY:
        raise RuntimeError("Grok API key is not configured.")

    payload = {
        "model": GROK_MODEL,
        "messages": [{"role": "system", "content": SYSTEM_PROMPT}] + messages,
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
        raise RuntimeError("Gemini API key is not configured.")

    url = (
        "https://generativelanguage.googleapis.com/v1beta/models/"
        f"{GEMINI_MODEL}:generateContent?key={GEMINI_KEY}"
    )

    contents = []
    for msg in messages:
        role = "model" if msg["role"] == "assistant" else "user"
        contents.append({
            "role": role,
            "parts": [{"text": msg["content"]}]
        })

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

    response = requests.post(url, json=payload, timeout=90)
    response.raise_for_status()
    data = response.json()

    return data["candidates"][0]["content"]["parts"][0]["text"]


def groq_request(messages):
    if not GROQ_KEY:
        raise RuntimeError("Groq API key is not configured.")

    payload = {
        "model": GROQ_MODEL,
        "messages": [{"role": "system", "content": SYSTEM_PROMPT}] + messages,
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
            errors.append(f"{provider_name}: {str(exc)[:220]}")

    raise RuntimeError(
        "कोई AI provider जवाब नहीं दे पाया। API keys, internet और model access जाँचें।\n"
        + "\n".join(errors)
    )


# ============================================================
# SMART WEB SEARCH
# ============================================================

def needs_web_search(query):
    keywords = [
        "latest", "today", "current", "news", "weather", "live",
        "price today", "stock price", "recent", "2026",
        "आज", "अभी", "ताजा", "ताज़ा", "लेटेस्ट", "मौसम",
        "आज का भाव", "शेयर प्राइस", "न्यूज़", "समाचार",
        "वर्तमान", "लाइव", "कब हुआ", "कौन जीता"
    ]
    q = query.lower()
    return any(word in q for word in keywords)


def web_search(query):
    if not TAVILY_KEY:
        return ""

    try:
        response = requests.post(
            "https://api.tavily.com/search",
            json={
                "api_key": TAVILY_KEY,
                "query": query,
                "search_depth": "basic",
                "max_results": 5,
                "include_answer": True
            },
            timeout=25
        )
        response.raise_for_status()
        data = response.json()

        results = []
        if data.get("answer"):
            results.append("Search summary: " + data["answer"])

        for item in data.get("results", []):
            results.append(
                f"Title: {item.get('title', '')}\n"
                f"URL: {item.get('url', '')}\n"
                f"Content: {item.get('content', '')[:900]}"
            )

        return "\n\n".join(results)

    except Exception:
        return ""


def smart_web_search(query):
    if not st.session_state.web_search_enabled:
        return ""
    if not needs_web_search(query):
        return ""
    return web_search(query)


# ============================================================
# RESPONSE UTILITIES
# ============================================================

def response_controls(content, index):
    safe_text = json.dumps(content)

    components.html(
        f"""
        <div style="display:flex;gap:8px;flex-wrap:wrap;margin:5px 0 12px;">
          <button onclick='copyText()'
            style="background:#202b45;color:white;border:1px solid #536080;
            border-radius:8px;padding:7px 12px;cursor:pointer;">Copy</button>
          <button onclick='speakText()'
            style="background:#202b45;color:white;border:1px solid #536080;
            border-radius:8px;padding:7px 12px;cursor:pointer;">Read aloud</button>
          <button onclick='stopSpeak()'
            style="background:#202b45;color:white;border:1px solid #536080;
            border-radius:8px;padding:7px 12px;cursor:pointer;">Stop</button>
        </div>
        <script>
        const answer = {safe_text};
        function copyText() {{
          navigator.clipboard.writeText(answer);
        }}
        function speakText() {{
          window.speechSynthesis.cancel();
          const utterance = new SpeechSynthesisUtterance(answer);
          utterance.lang = /[\\u0900-\\u097F]/.test(answer) ? "hi-IN" : "en-US";
          window.speechSynthesis.speak(utterance);
        }}
        function stopSpeak() {{
          window.speechSynthesis.cancel();
        }}
        </script>
        """,
        height=55
    )


def show_ai_answer(answer, provider):
    st.markdown(answer)
    st.caption(f"Response generated by {provider}")
    response_controls(answer, 0)


def run_ai_task(prompt, context=None):
    messages = []
    if context:
        messages.append({"role": "user", "content": context})
        messages.append({"role": "assistant", "content": "I understand the context."})

    messages.append({"role": "user", "content": prompt})
    search_context = smart_web_search(prompt)

    if search_context:
        messages[-1]["content"] += (
            "\n\nUse this web research if relevant. Do not invent facts.\n"
            + search_context
        )

    return ask_ai(messages)


# ============================================================
# SIDEBAR — COMPACT NAVIGATION
# ============================================================

with st.sidebar:
    st.markdown("""
    <div style="padding:12px 5px 18px;">
      <div style="font-size:27px;font-weight:900;letter-spacing:1px;">
        ✦ NEXTGEN
      </div>
      <div style="color:#9caad0;font-size:11px;letter-spacing:3px;">
        AI WORKSPACE
      </div>
    </div>
    """, unsafe_allow_html=True)

    st.button(
        "＋  New Chat",
        use_container_width=True,
        on_click=lambda: (
            st.session_state.update({
                "chat_id": create_chat(),
                "messages": [],
                "last_answer": "",
                "last_prompt": "",
                "followups": [],
                "page": "AI Chat"
            })
        )
    )

    st.markdown("---")

    main_pages = [
        "Dashboard",
        "AI Chat",
        "Stock Market",
        "Tool Center",
        "App Builder",
        "Website Builder",
        "Learn & Explore",
        "Image Studio",
        "PDF Assistant",
        "My Creations",
        "Chat History"
    ]

    if st.session_state.page not in main_pages:
        st.session_state.page = "Dashboard"

    selected_page = st.radio(
        "MAIN MENU",
        main_pages,
        index=main_pages.index(st.session_state.page)
    )

    if selected_page != st.session_state.page:
        st.session_state.page = selected_page
        st.session_state.last_answer = ""
        st.session_state.last_prompt = ""
        st.session_state.followups = []
        st.rerun()

    with st.expander("⚙️ Settings & About"):
        if st.button("Settings", use_container_width=True):
            go_to("Settings")
        if st.button("About NEXTGEN", use_container_width=True):
            go_to("About")

    st.markdown("---")
    st.caption("NEXTGEN AI • Premium Workspace")
    st.caption("Created by Arav")


# ============================================================
# DASHBOARD
# ============================================================

page = st.session_state.page

if page == "Dashboard":

    hero(
        "Your Ideas. Your AI. Your Workspace.",
        "एक ही जगह पर AI Chat, Coding, App Building, Website Building, "
        "Stock Learning, Creative Tools और Productivity.",
        "WELCOME TO NEXTGEN AI"
    )

    st.markdown("### ✦ Your AI Workspace")

    dashboard_items = [
        ("💬", "AI Chat", "AI से सवाल पूछें, ideas लें और coding में मदद पाएँ।", "AI Chat"),
        ("📈", "Stock Market", "Market charts, stock comparison और educational analysis।", "Stock Market"),
        ("🧰", "Tool Center", "Writing, study, coding, research और creator tools।", "Tool Center"),
        ("🧩", "App Builder", "AI से multi-file application project बनवाएँ।", "App Builder"),
        ("🌐", "Website Builder", "HTML, CSS और JavaScript वेबसाइट प्रोजेक्ट बनाएँ।", "Website Builder"),
        ("🎓", "Learn & Explore", "AI Tutor, lessons, quizzes और learning roadmaps।", "Learn & Explore"),
        ("🖼️", "Image Studio", "Cloudflare image API से images generate करें।", "Image Studio"),
        ("📄", "PDF Assistant", "PDF से text निकालकर उसका सार और जवाब पाएँ।", "PDF Assistant"),
        ("🗂️", "My Creations", "अपने saved AI outputs और projects देखें।", "My Creations"),
    ]

    for start in range(0, len(dashboard_items), 3):
        cols = st.columns(3)
        for col, item in zip(cols, dashboard_items[start:start + 3]):
            with col:
                feature_card(item[0], item[1], item[2])
                if st.button(
                    f"Open {item[1]}",
                    key=f"dash_{item[3]}",
                    use_container_width=True
                ):
                    go_to(item[3])

    st.markdown("---")
    st.markdown("### ⚡ Quick Actions")

    quick_cols = st.columns(4)
    quick_actions = [
        ("Start a Chat", "AI Chat"),
        ("Build an App", "App Builder"),
        ("Build a Website", "Website Builder"),
        ("Explore Tools", "Tool Center")
    ]

    for col, (label, destination) in zip(quick_cols, quick_actions):
        with col:
            if st.button(label, use_container_width=True):
                go_to(destination)

    st.markdown("---")
    st.markdown("### ✨ What makes NEXTGEN useful?")

    info_cols = st.columns(3)
    with info_cols[0]:
        feature_card("🧠", "Multi-AI Assistant", "Configured AI providers के जरिए जवाब पाने की सुविधा।")
    with info_cols[1]:
        feature_card("🛠️", "Build & Create", "App ideas, website projects, code और creative content।")
    with info_cols[2]:
        feature_card("📚", "Learn & Improve", "Concept explanations, practice questions और guided learning।")

# ============================================================
# AI CHAT
# ============================================================

elif page == "AI Chat":

    hero(
        "AI Chat",
        "अपने सवाल पूछें, ideas explore करें, code लिखें और मुश्किल topics समझें।",
        "AI WORKSPACE"
    )

    if st.session_state.chat_id is None:
        st.session_state.chat_id = create_chat()
        st.session_state.messages = []

    if not st.session_state.messages:
        st.session_state.messages = get_messages(st.session_state.chat_id)

    for i, message in enumerate(st.session_state.messages):
        with st.chat_message(message["role"]):
            st.markdown(message["content"])
            if message["role"] == "assistant":
                response_controls(message["content"], i)

    if CF_LIVE_URL:
        st.markdown(f"[🎙️ Open Voice Assistant]({CF_LIVE_URL})")
    else:
        st.caption("Voice link को Settings में Cloudflare Voice URL जोड़ने के बाद इस्तेमाल किया जा सकता है।")

    try:
        user_prompt = st.chat_input(
            "Message NEXTGEN AI...",
            accept_file=True,
            file_type=["txt", "pdf"],
            max_upload_size=20
        )
    except TypeError:
        user_prompt = st.chat_input("Message NEXTGEN AI...")

    if user_prompt:
        prompt_text = getattr(user_prompt, "text", "") or str(user_prompt)

        uploaded_files = getattr(user_prompt, "files", None) or []
        file_context = ""

        for uploaded in uploaded_files:
            try:
                if uploaded.name.lower().endswith(".txt"):
                    file_context += "\n\nFILE: " + uploaded.name + "\n"
                    file_context += uploaded.getvalue().decode("utf-8", errors="ignore")[:12000]
                elif uploaded.name.lower().endswith(".pdf"):
                    try:
                        from pypdf import PdfReader
                        reader = PdfReader(io.BytesIO(uploaded.getvalue()))
                        pdf_text = "\n".join(
                            page.extract_text() or "" for page in reader.pages[:15]
                        )
                        file_context += "\n\nPDF: " + uploaded.name + "\n" + pdf_text[:12000]
                    except Exception as exc:
                        file_context += f"\nPDF read error: {exc}"
            except Exception:
                pass

        if not prompt_text.strip():
            prompt_text = "Please analyze the attached file."

        if file_context:
            prompt_text += "\n\nAttached file content:\n" + file_context

        st.session_state.messages.append({
            "role": "user",
            "content": prompt_text
        })
        save_message(st.session_state.chat_id, "user", prompt_text)

        with st.chat_message("user"):
            st.markdown(prompt_text[:5000])

        with st.chat_message("assistant"):
            with st.spinner("NEXTGEN AI is thinking..."):
                try:
                    search_context = smart_web_search(prompt_text)

                    messages_for_ai = [
                        {"role": m["role"], "content": m["content"]}
                        for m in st.session_state.messages[-18:]
                    ]

                    if search_context:
                        messages_for_ai[-1]["content"] += (
                            "\n\nWeb search results. Use only relevant facts:\n"
                            + search_context
                        )

                    answer, provider = ask_ai(messages_for_ai)
                    st.markdown(answer)
                    st.caption(f"Response generated by {provider}")
                    response_controls(answer, len(st.session_state.messages))

                    st.session_state.messages.append({
                        "role": "assistant",
                        "content": answer
                    })
                    save_message(st.session_state.chat_id, "assistant", answer)

                    st.session_state.last_answer = answer
                    st.session_state.last_prompt = prompt_text
                    st.session_state.followups = []

                    if len(st.session_state.messages) == 2:
                        update_chat_title(
                            st.session_state.chat_id,
                            prompt_text[:45]
                        )

                except Exception as exc:
                    error_text = f"AI Error: {str(exc)}"
                    st.error(error_text)

        st.rerun()

    if st.session_state.last_answer:
        st.markdown("---")
        st.caption("Continue exploring")
        if st.button("✨ Generate 5 follow-up suggestions"):
            with st.spinner("Suggestions बन रहे हैं..."):
                try:
                    followup_prompt = (
                        "Based on this conversation, suggest exactly 5 short "
                        "useful follow-up questions. Return only a numbered list.\n\n"
                        f"User: {st.session_state.last_prompt}\n"
                        f"Assistant: {st.session_state.last_answer[:2500]}"
                    )
                    result, _ = ask_ai([{"role": "user", "content": followup_prompt}])
                    st.session_state.followups = [
                        line.strip() for line in result.splitlines()
                        if line.strip()
                    ][:5]
                except Exception:
                    st.session_state.followups = [
                        "Explain this in more detail",
                        "Give me an example",
                        "Make a step-by-step plan",
                        "What should I learn next?",
                        "Summarize the key points"
                    ]

        for suggestion in st.session_state.followups:
            if st.button(suggestion, key="follow_" + str(abs(hash(suggestion)))):
                st.session_state.pending_prompt = suggestion
                st.rerun()

    if st.session_state.get("pending_prompt"):
        pending = st.session_state.pending_prompt
        st.session_state.pending_prompt = None
        st.info("Suggested question: " + pending)
        st.caption("इसे ऊपर Chat box में भेजें।")


# ============================================================
# TOOL CENTER
# ============================================================

elif page == "Tool Center":

    hero(
        "Tool Center",
        "हर तरह के काम के लिए अलग-अलग AI tools — लिखना, पढ़ना, coding, "
        "research, content creation और planning.",
        "AI TOOLKIT"
    )

    tool_categories = {
        "✍️ Writing & Documents": [
            "Essay Writer", "Email Writer", "Paragraph Writer",
            "Story Writer", "Article Writer", "Report Maker",
            "Text Summarizer", "Rewrite & Improve", "Grammar Checker",
            "Formal Letter", "Speech Writer", "Notice Writer"
        ],
        "🎓 Study & Education": [
            "Topic Explainer", "Chapter Notes", "Question Answer Maker",
            "MCQ Quiz Maker", "Flashcard Maker", "Practice Test",
            "Study Timetable", "Revision Planner", "Difficult Word Explainer",
            "Step-by-Step Maths Explanation", "Science Concept Tutor"
        ],
        "💻 Coding & Development": [
            "Code Generator", "Code Explainer", "Debug My Code",
            "Python Helper", "HTML CSS JS Helper", "Streamlit App Helper",
            "SQL Query Helper", "Regex Helper", "API Integration Planner",
            "Code Optimizer", "Project Structure Generator"
        ],
        "🎬 YouTube & Creator": [
            "YouTube Video Ideas", "Video Script Writer", "Shorts Script",
            "Title Generator", "Description Generator", "Hashtag Generator",
            "Thumbnail Prompt", "Channel Bio Writer", "Content Calendar",
            "Voiceover Script", "Scene-by-Scene Planner"
        ],
        "🔎 Research & Thinking": [
            "Topic Research", "Compare Two Topics", "Pros & Cons",
            "Brainstorm Ideas", "Problem Solver", "Concept Map",
            "Research Outline", "Fact Check Questions"
        ],
        "📅 Productivity": [
            "Daily Planner", "Task Breakdown", "Checklist Maker",
            "Goal Planner", "Time Management Plan", "Project Planner",
            "Meeting Notes", "Decision Helper"
        ],
        "🎨 Creative Studio": [
            "Story Idea Generator", "Character Creator", "Dialogue Writer",
            "Caption Writer", "Slogan Generator", "Brand Name Ideas",
            "Creative Prompt Maker", "Festival Greeting Writer"
        ],
        "🏪 Business & Branding": [
            "Business Name Ideas", "Product Description",
            "Shop Promotion Script", "Marketing Plan",
            "Customer FAQ Writer", "Brand Identity Planner",
            "Social Media Post"
        ]
    }

    selected_category = st.selectbox(
        "Choose a category",
        list(tool_categories.keys())
    )

    selected_tool = st.selectbox(
        "Choose your tool",
        tool_categories[selected_category]
    )

    tool_instructions = {
        "Essay Writer": "Write a well-structured essay with introduction, body and conclusion.",
        "Email Writer": "Write a clear and polite email.",
        "Text Summarizer": "Summarize the text with key points.",
        "Grammar Checker": "Correct grammar and explain important corrections.",
        "Topic Explainer": "Teach the topic in simple steps with examples.",
        "Chapter Notes": "Create organized study notes with headings and key terms.",
        "MCQ Quiz Maker": "Create MCQs with answers and explanations.",
        "Flashcard Maker": "Create question-answer flashcards.",
        "Study Timetable": "Create a realistic study timetable with breaks.",
        "Code Generator": "Generate clean, commented code and explain how to run it.",
        "Code Explainer": "Explain the code step by step.",
        "Debug My Code": "Find likely bugs, explain them and provide corrected code.",
        "Python Helper": "Solve the Python programming task and explain it.",
        "YouTube Video Ideas": "Generate original and engaging video ideas.",
        "Video Script Writer": "Write a strong video script with hook, scenes and ending.",
        "Shorts Script": "Write a concise vertical-video script.",
        "Title Generator": "Suggest engaging, accurate titles.",
        "Thumbnail Prompt": "Create a detailed thumbnail image-generation prompt.",
        "Topic Research": "Create a structured research brief and identify uncertainties.",
        "Compare Two Topics": "Compare the topics fairly in a table.",
        "Pros & Cons": "List balanced advantages and disadvantages.",
        "Daily Planner": "Create a practical daily plan with priorities and breaks.",
        "Task Breakdown": "Break the project into manageable steps.",
        "Story Idea Generator": "Create an original story concept with characters and plot.",
        "Character Creator": "Create a memorable fictional character.",
        "Shop Promotion Script": "Write a friendly promotional script.",
        "Marketing Plan": "Create an age-appropriate, realistic marketing plan."
    }

    default_instruction = tool_instructions.get(
        selected_tool,
        "Complete this task clearly, accurately and in a useful format."
    )

    st.markdown("### ✦ Your Work Area")
    st.caption(default_instruction)

    tool_input = st.text_area(
        "Describe what you want",
        value=st.session_state.tool_prompt,
        height=180,
        placeholder="अपना topic, text, idea या code यहाँ लिखें..."
    )

    col_run, col_clear = st.columns([3, 1])

    with col_run:
        run_tool = st.button(
            "✦ Generate with AI",
            use_container_width=True
        )

    with col_clear:
        if st.button("Clear", use_container_width=True):
            st.session_state.tool_output = ""
            st.session_state.tool_prompt = ""
            st.rerun()

    if run_tool:
        if not tool_input.strip():
            st.warning("पहले अपना काम या topic लिखें।")
        else:
            full_prompt = (
                f"Tool: {selected_tool}\n"
                f"Instruction: {default_instruction}\n"
                f"User request:\n{tool_input}\n\n"
                "Give a complete, high-quality result. Use headings and examples where useful."
            )

            with st.spinner("AI tool काम कर रहा है..."):
                try:
                    output, provider = run_ai_task(full_prompt)
                    st.session_state.tool_output = output
                    st.session_state.tool_prompt = tool_input
                    st.session_state.tool_provider = provider
                except Exception as exc:
                    st.error(str(exc))

    if st.session_state.tool_output:
        st.markdown("---")
        st.markdown("### 📝 Generated Result")

        edited_output = st.text_area(
            "Edit your result",
            value=st.session_state.tool_output,
            height=350,
            key="tool_output_editor"
        )

        st.session_state.tool_output = edited_output

        a, b = st.columns(2)
        with a:
            if st.button("💾 Save to My Creations", use_container_width=True):
                save_creation(selected_tool, edited_output)
                st.success("Saved to My Creations.")

        with b:
            st.download_button(
                "⬇️ Download TXT",
                data=edited_output,
                file_name="nextgen_ai_result.txt",
                mime="text/plain",
                use_container_width=True
            )

        st.caption(
            "Generated by " + st.session_state.get("tool_provider", "AI")
        )


# ============================================================
# PROJECT BUILDER HELPERS
# ============================================================

def extract_json_files(text):
    cleaned = text.strip()

    cleaned = re.sub(r"^```(?:json)?\s*", "", cleaned)
    cleaned = re.sub(r"\s*```$", "", cleaned)

    try:
        data = json.loads(cleaned)
    except Exception:
        match = re.search(r"\{.*\}", cleaned, re.S)
        if not match:
            return None
        data = json.loads(match.group(0))

    files = data.get("files", [])
    output = {}

    for item in files:
        path = str(item.get("path", "")).strip().replace("\\", "/")
        content = str(item.get("content", ""))

        if not path or path.startswith("/") or ".." in path.split("/"):
            continue

        output[path] = content

    return output if output else None


def make_project_zip(files):
    buffer = io.BytesIO()

    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as archive:
        for path, content in files.items():
            archive.writestr(path, content)

    buffer.seek(0)
    return buffer.getvalue()


def project_builder(project_type):
    is_website = project_type == "Website"

    if is_website:
        title = "Website Builder"
        subtitle = (
            "अपना website idea लिखें। AI HTML, CSS और JavaScript की "
            "अलग-अलग files वाला पूरा starter project तैयार करेगा।"
        )
        kicker = "WEB DEVELOPMENT STUDIO"
        default_stack = "HTML, CSS, JavaScript"
        sample = "एक modern responsive portfolio website जिसमें Home, About, Projects और Contact sections हों।"
    else:
        title = "App Builder"
        subtitle = (
            "अपने app का idea बताइए। AI project structure, screens, "
            "features और starter code वाली files बनाएगा।"
        )
        kicker = "APPLICATION DEVELOPMENT STUDIO"
        default_stack = "Python + Streamlit"
        sample = "एक student productivity app जिसमें tasks, notes और study planner हों।"

    hero(title, subtitle, kicker)

    with st.form(f"{project_type.lower()}_builder_form"):
        project_name = st.text_input(
            "Project name",
            value="My " + project_type
        )

        idea = st.text_area(
            "Describe your project",
            value=sample,
            height=130
        )

        col1, col2 = st.columns(2)

        with col1:
            platform = st.selectbox(
                "Platform",
                ["Web", "Desktop", "Mobile concept", "Cross-platform"]
                if not is_website else ["Responsive website", "Landing page", "Web application"]
            )

            stack = st.selectbox(
                "Technology",
                [
                    default_stack,
                    "Python + Streamlit",
                    "Python + Flask",
                    "React + Vite",
                    "HTML, CSS, JavaScript",
                    "Node.js",
                    "Suggest the best stack"
                ]
            )

        with col2:
            design = st.selectbox(
                "Design style",
                [
                    "Premium dark",
                    "Modern minimal",
                    "Glassmorphism",
                    "Neon futuristic",
                    "Clean professional",
                    "Colorful friendly"
                ]
            )

            output_level = st.selectbox(
                "Build level",
                [
                    "Complete starter project",
                    "Detailed prototype",
                    "Simple beginner project"
                ]
            )

        features = st.text_area(
            "Features you want",
            placeholder="Login, dashboard, search, settings, database, responsive layout..."
        )

        submitted = st.form_submit_button(
            "✦ Generate Project",
            use_container_width=True
        )

    if submitted:
        if not project_name.strip() or not idea.strip():
            st.warning("Project name और project idea लिखें।")
        else:
            if is_website:
                project_instructions = """
Create a complete multi-file website project.
Include index.html, style.css and script.js as appropriate.
Make it responsive, accessible and visually polished.
Add functional navigation and working front-end interactions.
Do not claim backend, authentication, payment or database features
work unless you actually implement them.
Include README.md with setup instructions.
"""
            else:
                project_instructions = """
Create a complete multi-file application starter project.
Include all required source files and requirements.txt where appropriate.
Include README.md with exact installation and run instructions.
Make the code organized, readable and runnable with the chosen stack.
Do not claim features work unless implemented in the generated code.
"""

            prompt = f"""
You are a senior software engineer and project architect.

Build this project:
Name: {project_name}
Type: {project_type}
Idea: {idea}
Platform: {platform}
Technology: {stack}
Design: {design}
Build level: {output_level}
Requested features: {features}

{project_instructions}

Return ONLY valid JSON in this exact format:
{{
  "files": [
    {{
      "path": "README.md",
      "content": "file content here"
    }},
    {{
      "path": "src/example.py",
      "content": "file content here"
    }}
  ]
}}

Rules:
- Put complete source code in each file.
- Do not use markdown fences around the JSON.
- Use sensible file names.
- Include a README.
- Avoid placeholder-only files.
- Keep the project safe and legitimate.
"""

            with st.spinner("AI project की files बना रहा है..."):
                try:
                    result, provider = run_ai_task(prompt)
                    files = extract_json_files(result)

                    if not files:
                        files = {
                            "AI_PROJECT_OUTPUT.md": result,
                            "README.txt": (
                                "The AI response could not be parsed into separate files. "
                                "Open AI_PROJECT_OUTPUT.md to view the generated project."
                            )
                        }

                    st.session_state.project_files = files
                    st.session_state.project_type = project_type
                    st.session_state.project_name = project_name
                    st.session_state.project_provider = provider
                    st.success("Project files तैयार हैं।")

                except Exception as exc:
                    st.error(f"Project generation failed: {exc}")

    files = st.session_state.project_files

    if files and st.session_state.project_type == project_type:
        st.markdown("---")
        st.markdown("### 📁 Project Files")

        file_names = list(files.keys())

        selected_file = st.selectbox(
            "Choose a file to edit",
            file_names,
            key=f"{project_type}_file_select"
        )

        edited_content = st.text_area(
            "Edit file content",
            value=files[selected_file],
            height=350,
            key=f"{project_type}_editor_{selected_file}"
        )

        files[selected_file] = edited_content
        st.session_state.project_files = files

        col_a, col_b = st.columns(2)

        with col_a:
            st.download_button(
                "⬇️ Download Complete ZIP",
                data=make_project_zip(files),
                file_name=re.sub(
                    r"[^a-zA-Z0-9_-]+", "_",
                    st.session_state.project_name
                ) + ".zip",
                mime="application/zip",
                use_container_width=True
            )

        with col_b:
            if st.button("💾 Save Project to My Creations", use_container_width=True):
                project_text = json.dumps(files, ensure_ascii=False, indent=2)
                save_creation(
                    st.session_state.project_name,
                    project_text
                )
                st.success("Project saved.")

        st.caption(
            f"{len(files)} files • Generated by "
            + st.session_state.get("project_provider", "AI")
        )

        with st.expander("Preview all project files"):
            for file_path, file_content in files.items():
                st.markdown(f"**{file_path}**")
                st.code(file_content[:12000])


elif page == "App Builder":
    project_builder("App")

elif page == "Website Builder":
    project_builder("Website")


# ============================================================
# LEARN & EXPLORE
# ============================================================

elif page == "Learn & Explore":

    hero(
        "Learn & Explore",
        "एक AI Tutor जो topics समझाए, learning roadmap बनाए, quiz ले "
        "और practice में मदद करे।",
        "YOUR LEARNING SPACE"
    )

    subject = st.text_input(
        "Subject or topic",
        placeholder="जैसे Python, Algebra, Physics, English Grammar..."
    )

    level = st.selectbox(
        "Your learning level",
        ["Beginner", "School student", "Intermediate", "Advanced"]
    )

    mode = st.selectbox(
        "Choose learning mode",
        [
            "Explain a topic",
            "Create a learning roadmap",
            "Take a quiz",
            "Give practice questions",
            "Make revision notes",
            "Explain with examples"
        ]
    )

    learning_goal = st.text_area(
        "What do you want to learn?",
        placeholder="अपना learning goal या सवाल लिखें..."
    )

    if st.button("🎓 Start Learning", use_container_width=True):
        if not subject.strip():
            st.warning("पहले subject या topic लिखें।")
        else:
            prompt = f"""
Act as a friendly, patient tutor.

Subject/topic: {subject}
Student level: {level}
Mode: {mode}
Learning goal: {learning_goal}

Teach clearly and step by step.
Use age-appropriate examples.
For quizzes, provide questions first and answers with explanations afterward.
For roadmaps, divide learning into stages.
Do not invent textbook-specific facts.
"""
            with st.spinner("Your AI Tutor is preparing your lesson..."):
                try:
                    answer, provider = run_ai_task(prompt)
                    st.session_state.learn_output = answer
                    st.session_state.learn_provider = provider
                except Exception as exc:
                    st.error(str(exc))

    if st.session_state.get("learn_output"):
        st.markdown("---")
        st.markdown("### 📘 Your Learning Material")
        st.markdown(st.session_state.learn_output)

        if st.button("💾 Save Lesson"):
            save_creation(subject or "Learning Lesson", st.session_state.learn_output)
            st.success("Lesson saved to My Creations.")


# ============================================================
# STOCK MARKET
# ============================================================

elif page == "Stock Market":

    hero(
        "Stock Market Learning & Analysis",
        "Charts, watchlists, comparisons and market concepts. "
        "Market data may be delayed or unavailable depending on the data source.",
        "MARKET CENTER"
    )

    st.info(
        "यह section educational purpose के लिए है। यह personal investment advice "
        "नहीं है और किसी stock के profit की guarantee नहीं देता।"
    )

    tab1, tab2, tab3, tab4 = st.tabs([
        "📊 Stock Analysis",
        "⭐ Watchlist",
        "⚖️ Compare",
        "📚 Learn Market"
    ])

    try:
        import yfinance as yf
        yfinance_available = True
    except ImportError:
        yfinance_available = False

    with tab1:
        ticker = st.text_input(
            "Stock ticker",
            value="AAPL",
            help="Examples: AAPL, MSFT, RELIANCE.NS, TCS.NS"
        ).upper().strip()

        period = st.selectbox(
            "Chart period",
            ["1mo", "3mo", "6mo", "1y", "2y", "5y"]
        )

        if st.button("Load Stock Data", key="load_stock"):
            if not yfinance_available:
                st.error("yfinance installed नहीं है। PowerShell में चलाएँ: pip install yfinance")
            elif not ticker:
                st.warning("Ticker लिखें।")
            else:
                try:
                    data = yf.Ticker(ticker).history(period=period)

                    if data.empty:
                        st.warning("इस ticker के लिए data उपलब्ध नहीं है।")
                    else:
                        st.session_state.stock_data = data
                        st.session_state.stock_ticker = ticker
                        st.success(f"{ticker} data loaded.")

                except Exception as exc:
                    st.error(f"Market data error: {exc}")

        if st.session_state.get("stock_data") is not None:
            data = st.session_state.stock_data
            stock_ticker = st.session_state.stock_ticker

            if not data.empty:
                latest = float(data["Close"].dropna().iloc[-1])
                previous = (
                    float(data["Close"].dropna().iloc[-2])
                    if len(data["Close"].dropna()) > 1 else latest
                )
                change = latest - previous
                percent = (change / previous * 100) if previous else 0

                m1, m2, m3 = st.columns(3)
                m1.metric("Latest available close", f"{latest:,.2f}")
                m2.metric("Previous close", f"{previous:,.2f}")
                m3.metric("Change", f"{change:,.2f}", f"{percent:.2f}%")

                st.caption(
                    f"Ticker: {stock_ticker} • Last returned date: "
                    f"{data.index[-1].strftime('%Y-%m-%d')} • "
                    "This may not be a live quote."
                )

                st.markdown("### Price Chart")
                st.line_chart(data["Close"])

                if "Volume" in data.columns:
                    st.markdown("### Trading Volume")
                    st.bar_chart(data["Volume"])

                if st.button("Explain this stock data with AI"):
                    prompt = (
                        f"Explain this educational stock data for {stock_ticker}. "
                        f"Latest available close: {latest}. "
                        f"Previous close: {previous}. "
                        f"Percentage change: {percent:.2f}%. "
                        "Explain what these values mean, limitations and risks. "
                        "Do not tell the user to buy or sell."
                    )
                    with st.spinner("AI is explaining..."):
                        try:
                            explanation, provider = run_ai_task(prompt)
                            st.markdown(explanation)
                            st.caption(f"Explained by {provider}")
                        except Exception as exc:
                            st.error(str(exc))

    with tab2:
        st.markdown("### Your Watchlist")

        new_ticker = st.text_input("Add ticker to watchlist", key="watch_add")

        if st.button("＋ Add to Watchlist"):
            if new_ticker.strip():
                symbol = new_ticker.upper().strip()
                if symbol not in st.session_state.stock_watchlist:
                    st.session_state.stock_watchlist.append(symbol)
                st.rerun()

        if st.button("Refresh Watchlist"):
            if not yfinance_available:
                st.error("Install yfinance: pip install yfinance")
            else:
                rows = []
                for symbol in st.session_state.stock_watchlist:
                    try:
                        hist = yf.Ticker(symbol).history(period="5d")
                        if not hist.empty:
                            close = hist["Close"].dropna()
                            latest_value = float(close.iloc[-1])
                            old_value = float(close.iloc[-2]) if len(close) > 1 else latest_value
                            pct = ((latest_value - old_value) / old_value * 100) if old_value else 0
                            rows.append({
                                "Ticker": symbol,
                                "Latest available close": round(latest_value, 2),
                                "Change %": round(pct, 2)
                            })
                    except Exception:
                        continue

                if rows:
                    st.dataframe(rows, use_container_width=True)
                else:
                    st.warning("Watchlist data नहीं मिल पाया।")

        st.caption("Watchlist prices may be delayed. They are not guaranteed live quotes.")

    with tab3:
        symbols_text = st.text_input(
            "Compare tickers (comma separated)",
            value="AAPL,MSFT,NVDA"
        )

        if st.button("Compare Stocks"):
            if not yfinance_available:
                st.error("Install yfinance: pip install yfinance")
            else:
                symbols = [
                    x.strip().upper()
                    for x in symbols_text.split(",")
                    if x.strip()
                ][:5]

                try:
                    comparison = {}
                    for symbol in symbols:
                        history = yf.Ticker(symbol).history(period="6mo")
                        if not history.empty:
                            comparison[symbol] = history["Close"]

                    if comparison:
                        chart_data = __import__("pandas").DataFrame(comparison)
                        st.line_chart(chart_data)
                        st.caption(
                            "Different stocks have different prices and risk profiles. "
                            "This chart alone does not determine which is better."
                        )
                    else:
                        st.warning("Comparison data unavailable.")
                except Exception as exc:
                    st.error(str(exc))

    with tab4:
        st.markdown("### Stock Market Basics")

        lessons = {
            "What is a stock?": "A stock represents a small ownership share in a company.",
            "What is an index?": "An index tracks a selected group of securities to represent a market segment.",
            "What is diversification?": "Diversification means spreading exposure across different investments.",
            "What is volatility?": "Volatility describes how much a price changes over time.",
            "What is market capitalization?": "Market capitalization is share price multiplied by shares outstanding.",
            "What is a dividend?": "A dividend is a distribution a company may make to shareholders."
        }

        for lesson, explanation in lessons.items():
            with st.expander(lesson):
                st.write(explanation)

        market_question = st.text_input(
            "Ask AI to explain a market concept",
            placeholder="जैसे P/E ratio क्या होता है?"
        )

        if st.button("Explain Market Concept"):
            if market_question.strip():
                with st.spinner("Explaining..."):
                    try:
                        answer, provider = run_ai_task(
                            "Explain this stock market concept for learning, "
                            "with a simple example and important risks: "
                            + market_question
                        )
                        st.markdown(answer)
                        st.caption(f"Explained by {provider}")
                    except Exception as exc:
                        st.error(str(exc))


# ============================================================
# IMAGE STUDIO
# ============================================================

elif page == "Image Studio":

    hero(
        "Image Studio",
        "अपना image prompt लिखें और configured Cloudflare image model से image generate करें।",
        "CREATIVE STUDIO"
    )

    image_prompt = st.text_area(
        "Describe your image",
        height=130,
        placeholder="Describe the subject, background, lighting, style and composition..."
    )

    image_style = st.selectbox(
        "Style",
        [
            "Cinematic realistic",
            "3D animated",
            "Anime",
            "Digital art",
            "Minimal illustration",
            "Photorealistic",
            "Fantasy"
        ]
    )

    if st.button("🎨 Generate Image", use_container_width=True):
        if not (CF_ACCOUNT and CF_TOKEN):
            st.error(
                "Cloudflare Image API configured नहीं है। "
                "CLOUDFLARE_ACCOUNT_ID और CLOUDFLARE_API_TOKEN जोड़ें।"
            )
        elif not image_prompt.strip():
            st.warning("Image prompt लिखें।")
        else:
            final_prompt = f"{image_prompt}. Style: {image_style}."

            endpoint = (
                f"https://api.cloudflare.com/client/v4/accounts/{CF_ACCOUNT}"
                "/ai/run/@cf/black-forest-labs/flux-1-schnell"
            )

            with st.spinner("Image generating..."):
                try:
                    response = requests.post(
                        endpoint,
                        headers={"Authorization": f"Bearer {CF_TOKEN}"},
                        json={"prompt": final_prompt, "steps": 4},
                        timeout=120
                    )
                    response.raise_for_status()

                    image_bytes = response.content
                    st.image(image_bytes, caption="Generated by NEXTGEN AI")

                    st.download_button(
                        "⬇️ Download Image",
                        data=image_bytes,
                        file_name="nextgen_image.png",
                        mime="image/png"
                    )

                except Exception as exc:
                    st.error(f"Image generation failed: {exc}")


# ============================================================
# PDF ASSISTANT
# ============================================================

elif page == "PDF Assistant":

    hero(
        "PDF Assistant",
        "PDF upload करें और AI से summary, explanations, notes और questions पाएँ।",
        "DOCUMENT INTELLIGENCE"
    )

    pdf_file = st.file_uploader(
        "Upload a PDF",
        type=["pdf"]
    )

    pdf_task = st.selectbox(
        "What should AI do?",
        [
            "Summarize this PDF",
            "Create detailed notes",
            "Explain difficult concepts",
            "Create questions and answers",
            "Find key points"
        ]
    )

    if st.button("Analyze PDF", use_container_width=True):
        if not pdf_file:
            st.warning("पहले PDF upload करें।")
        else:
            try:
                from pypdf import PdfReader

                reader = PdfReader(io.BytesIO(pdf_file.getvalue()))
                extracted = "\n".join(
                    page.extract_text() or ""
                    for page in reader.pages[:30]
                )

                if not extracted.strip():
                    st.warning("इस PDF से readable text नहीं निकला। यह scanned PDF हो सकती है।")
                else:
                    with st.spinner("PDF पढ़ी जा रही है..."):
                        prompt = (
                            f"Task: {pdf_task}\n"
                            "Use only the provided document text. If something is missing, say so.\n\n"
                            + extracted[:26000]
                        )
                        answer, provider = run_ai_task(prompt)
                        st.markdown(answer)
                        st.caption(f"Analyzed by {provider}")
                        save_creation(
                            pdf_file.name + " - " + pdf_task,
                            answer
                        )

            except ImportError:
                st.error("pypdf installed नहीं है। PowerShell में चलाएँ: pip install pypdf")
            except Exception as exc:
                st.error(f"PDF error: {exc}")


# ============================================================
# MY CREATIONS
# ============================================================

elif page == "My Creations":

    hero(
        "My Creations",
        "Tool Center, lessons, PDF Assistant और generated projects से save किए गए काम।",
        "YOUR LIBRARY"
    )

    creations = get_creations()

    if not creations:
        st.info("अभी कोई saved creation नहीं है।")
    else:
        for creation in creations:
            with st.expander(
                f"📄 {creation['title']}  •  {creation['created_at'][:16]}"
            ):
                content = creation["content"]
                st.text_area(
                    "Saved content",
                    value=content,
                    height=220,
                    key=f"creation_{creation['id']}"
                )
                st.download_button(
                    "Download",
                    data=content,
                    file_name=f"creation_{creation['id']}.txt",
                    mime="text/plain",
                    key=f"download_creation_{creation['id']}"
                )


# ============================================================
# CHAT HISTORY
# ============================================================

elif page == "Chat History":

    hero(
        "Chat History",
        "अपनी पुरानी conversations खोलें और आगे जारी रखें।",
        "CONVERSATION LIBRARY"
    )

    chats = get_chats()

    if not chats:
        st.info("अभी कोई chat नहीं है।")
    else:
        for chat in chats:
            col1, col2, col3 = st.columns([5, 1, 1])

            with col1:
                st.markdown(f"**{chat['title']}**")
                st.caption(chat["created_at"][:16])

            with col2:
                if st.button("Open", key=f"open_chat_{chat['id']}"):
                    st.session_state.chat_id = chat["id"]
                    st.session_state.messages = get_messages(chat["id"])
                    st.session_state.last_answer = ""
                    st.session_state.last_prompt = ""
                    st.session_state.followups = []
                    go_to("AI Chat")

            with col3:
                if st.button("Delete", key=f"delete_chat_{chat['id']}"):
                    delete_chat(chat["id"])
                    if st.session_state.chat_id == chat["id"]:
                        st.session_state.chat_id = None
                        st.session_state.messages = []
                    st.rerun()


# ============================================================
# SETTINGS
# ============================================================

elif page == "Settings":

    hero(
        "Settings",
        "अपनी AI सुविधाओं और web search behavior को नियंत्रित करें।",
        "PREFERENCES"
    )

    st.markdown("### 🌐 Smart Web Search")

    st.session_state.web_search_enabled = st.toggle(
        "Enable automatic smart web search",
        value=st.session_state.web_search_enabled,
        help="Search केवल तब करने की कोशिश होगी जब सवाल में current या live information जरूरी हो।"
    )

    if st.session_state.web_search_enabled:
        st.success("Smart Web Search enabled.")
    else:
        st.info("Smart Web Search disabled.")

    st.markdown("---")
    st.markdown("### 🔐 API Configuration")

    st.caption(
        "API keys का वास्तविक मान यहाँ नहीं दिखाया जाएगा। "
        "केवल environment configuration का सामान्य संकेत दिया जाएगा।"
    )

    configured_count = sum([
        bool(GROK_KEY),
        bool(GEMINI_KEY),
        bool(GROQ_KEY)
    ])

    st.metric("AI providers configured", f"{configured_count}/3")

    st.caption(
        "Provider order: Grok → Gemini → Groq. "
        "हर जवाब के साथ इस्तेमाल हुए provider का नाम दिखेगा।"
    )

    st.markdown("---")
    st.markdown("### Required Python Packages")

    st.code(
        "pip install streamlit requests python-dotenv pypdf yfinance",
        language="powershell"
    )

    st.markdown("---")
    st.markdown("### Environment variables")

    st.code(
        "GROK_API_KEY=your_key\n"
        "GEMINI_API_KEY=your_key\n"
        "GROQ_API_KEY=your_key\n"
        "TAVILY_API_KEY=your_key\n"
        "CLOUDFLARE_ACCOUNT_ID=your_account_id\n"
        "CLOUDFLARE_API_TOKEN=your_token\n"
        "CLOUDFLARE_VOICE_URL=your_voice_url",
        language="text"
    )


# ============================================================
# ABOUT
# ============================================================

elif page == "About":

    hero(
        "About NEXTGEN AI",
        "A creative AI workspace for learning, building, researching and creating.",
        "ABOUT THE PLATFORM"
    )

    st.markdown("""
    <div class="panel">
      <h3>✦ NEXTGEN AI</h3>
      NEXTGEN AI is an AI-powered workspace designed to bring multiple
      useful capabilities into one application.
      <br><br>
      <b>Created by:</b> Arav
      <br>
      <b>School:</b> Swami Vivekanand Shiksha Niketan School
      <br><br>
      Arav is a student interested in artificial intelligence, Python,
      app development, technology, creative problem solving and digital creativity.
      <br><br>
      <b>Platform areas:</b>
      <ul>
        <li>AI Chat and multi-provider responses</li>
        <li>Tool Center and productivity tools</li>
        <li>App Builder and Website Builder</li>
        <li>Stock market learning and charts</li>
        <li>Learn & Explore</li>
        <li>Image Studio and PDF Assistant</li>
        <li>Chat History and My Creations</li>
      </ul>
    </div>
    """, unsafe_allow_html=True)

    st.caption("NEXTGEN AI • Built for creativity, learning and development.")
