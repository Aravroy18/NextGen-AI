
import os
import io
import re
import json
import time
import sqlite3
import zipfile
import requests
import streamlit as st

from datetime import datetime
from dotenv import load_dotenv

load_dotenv()

# ============================================================
# NEXTGEN AI — COMPLETE EDITION
# ============================================================

st.set_page_config(
    page_title="NEXTGEN AI",
    page_icon="✦",
    layout="wide",
    initial_sidebar_state="expanded"
)

# -------------------- CONFIG --------------------

GROK_KEY = os.getenv("GROK_API_KEY", "").strip()
GEMINI_KEY = os.getenv("GEMINI_API_KEY", "").strip()
GROQ_KEY = os.getenv("GROQ_API_KEY", "").strip()
TAVILY_KEY = os.getenv("TAVILY_API_KEY", "").strip()
FINNHUB_KEY = os.getenv("FINNHUB_API_KEY", "").strip()

GROK_MODEL = os.getenv("GROK_MODEL", "grok-4.7")
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")
GROQ_MODEL = os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile")

DB_FILE = "nextgen_v5.db"

# -------------------- DATABASE --------------------

def get_db():
    return sqlite3.connect(DB_FILE, check_same_thread=False)

def init_db():
    con = get_db()
    cur = con.cursor()

    cur.execute("""
        CREATE TABLE IF NOT EXISTS chats (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            chat_id TEXT,
            role TEXT,
            content TEXT,
            created_at TEXT
        )
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS creations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT,
            category TEXT,
            content TEXT,
            created_at TEXT
        )
    """)

    con.commit()
    con.close()

init_db()

def save_message(chat_id, role, content):
    con = get_db()
    con.execute(
        "INSERT INTO chats(chat_id, role, content, created_at) VALUES(?,?,?,?)",
        (chat_id, role, content, datetime.now().isoformat())
    )
    con.commit()
    con.close()

def get_messages(chat_id):
    con = get_db()
    rows = con.execute(
        "SELECT role, content FROM chats WHERE chat_id=? ORDER BY id",
        (chat_id,)
    ).fetchall()
    con.close()
    return [{"role": r[0], "content": r[1]} for r in rows]

def save_creation(title, category, content):
    con = get_db()
    con.execute(
        "INSERT INTO creations(title, category, content, created_at) VALUES(?,?,?,?)",
        (title, category, content, datetime.now().isoformat())
    )
    con.commit()
    con.close()

# -------------------- SESSION STATE --------------------

defaults = {
    "page": "Dashboard",
    "chat_id": "main",
    "messages": [],
    "web_search_enabled": True,
    "auto_provider": True,
    "last_provider": "",
    "last_search": "",
    "stock_watchlist": ["AAPL", "MSFT", "NVDA", "RELIANCE.NS", "TCS.NS"],
}

for key, value in defaults.items():
    if key not in st.session_state:
        st.session_state[key] = value

# -------------------- DESIGN --------------------

st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&display=swap');

html, body, [class*="css"] {
    font-family: Inter, sans-serif;
}

.stApp {
    background:
        radial-gradient(circle at 10% 0%, #17213b 0%, transparent 30%),
        radial-gradient(circle at 90% 10%, #24143c 0%, transparent 30%),
        #080b13;
    color: #f5f7ff;
}

[data-testid="stSidebar"] {
    background: #0d1220;
    border-right: 1px solid #202b40;
}

[data-testid="stHeader"] {
    background: transparent;
}

h1, h2, h3 {
    color: #f5f7ff !important;
}

p, label, span {
    color: #c8d0e0;
}

div.stButton > button {
    border-radius: 12px;
    border: 1px solid #34425d;
    background: linear-gradient(135deg, #17233c, #11182a);
    color: white;
    font-weight: 600;
    transition: 0.2s;
}

div.stButton > button:hover {
    border-color: #8b7cff;
    color: white;
    background: #202c48;
}

div[data-testid="stMetric"] {
    background: #111827;
    border: 1px solid #25334b;
    padding: 18px;
    border-radius: 16px;
}

.card {
    background: linear-gradient(145deg, #141d30, #0e1422);
    border: 1px solid #293752;
    padding: 20px;
    border-radius: 17px;
    min-height: 145px;
    margin-bottom: 12px;
}

.card h3 {
    margin-top: 0;
    font-size: 19px;
}

.card p {
    color: #aebbd0;
    font-size: 13px;
}

.hero {
    background: linear-gradient(120deg, #182b4a, #29204b, #121b31);
    border: 1px solid #39466d;
    padding: 30px;
    border-radius: 22px;
    margin-bottom: 22px;
}

.hero h1 {
    font-size: 38px;
    margin-bottom: 5px;
}

.small-muted {
    color: #8998b1;
    font-size: 12px;
}

.stTextInput input, .stTextArea textarea, .stSelectbox div {
    background: #101827 !important;
    color: white !important;
    border-radius: 10px !important;
}

hr {
    border-color: #25334b;
}
</style>
""", unsafe_allow_html=True)

# -------------------- HELPERS --------------------

def set_page(page):
    st.session_state.page = page

def show_card(title, description, icon="✦"):
    st.markdown(
        f"""
        <div class="card">
            <h3>{icon} {title}</h3>
            <p>{description}</p>
        </div>
        """,
        unsafe_allow_html=True
    )

def extract_json(text):
    text = text.strip()
    text = re.sub(r"^```(?:json)?", "", text)
    text = re.sub(r"```$", "", text)
    match = re.search(r"\{.*\}|\[.*\]", text, re.S)
    if not match:
        raise ValueError("AI ने valid JSON नहीं दिया।")
    return json.loads(match.group(0))

# -------------------- SMART SEARCH DETECTION --------------------

def needs_web_search(query):
    q = query.lower().strip()

    keywords = [
        "latest", "today", "current", "right now", "breaking",
        "news", "weather", "live", "recent", "this week",
        "2026", "2025", "price today", "stock price",
        "score today", "match result", "who won",
        "आज", "अभी", "ताजा", "ताज़ा", "लेटेस्ट",
        "मौसम", "आज का भाव", "शेयर प्राइस",
        "न्यूज़", "समाचार", "वर्तमान", "लाइव",
        "कौन जीता", "आज का स्कोर", "अभी क्या हुआ",
        "नया अपडेट", "हाल ही में"
    ]

    if any(word in q for word in keywords):
        return True

    question_patterns = [
        "what happened", "what is happening",
        "who is the current", "current president",
        "current prime minister", "latest version",
        "आज कौन", "अभी कौन", "वर्तमान में कौन"
    ]

    return any(pattern in q for pattern in question_patterns)

# -------------------- GROK NATIVE WEB SEARCH --------------------

def grok_web_search(query, history=None):
    if not GROK_KEY:
        raise RuntimeError("Grok API key उपलब्ध नहीं है।")

    messages = []
    if history:
        for item in history[-8:]:
            if item.get("role") in ("user", "assistant"):
                messages.append({
                    "role": item["role"],
                    "content": item["content"]
                })

    messages.append({"role": "user", "content": query})

    response = requests.post(
        "https://api.x.ai/v1/responses",
        headers={
            "Authorization": f"Bearer {GROK_KEY}",
            "Content-Type": "application/json"
        },
        json={
            "model": GROK_MODEL,
            "input": messages,
            "tools": [{"type": "web_search"}]
        },
        timeout=90
    )

    response.raise_for_status()
    data = response.json()

    if data.get("output_text"):
        return data["output_text"]

    output_text = []
    for item in data.get("output", []):
        if item.get("type") == "message":
            for part in item.get("content", []):
                if part.get("type") in ("output_text", "text"):
                    output_text.append(part.get("text", ""))

    answer = "\n".join(output_text).strip()
    if not answer:
        raise RuntimeError("Grok Search से कोई text response नहीं मिला।")

    return answer

# -------------------- TAVILY FALLBACK SEARCH --------------------

def tavily_search(query):
    if not TAVILY_KEY:
        return ""

    response = requests.post(
        "https://api.tavily.com/search",
        json={
            "api_key": TAVILY_KEY,
            "query": query,
            "search_depth": "basic",
            "max_results": 5,
            "include_answer": True
        },
        timeout=35
    )

    response.raise_for_status()
    data = response.json()

    results = []

    if data.get("answer"):
        results.append("Search summary: " + data["answer"])

    for item in data.get("results", []):
        results.append(
            "Title: " + item.get("title", "") +
            "\nURL: " + item.get("url", "") +
            "\nContent: " + item.get("content", "")[:1000]
        )

    return "\n\n".join(results)

# -------------------- AI PROVIDERS --------------------

SYSTEM_PROMPT = """
You are NEXTGEN AI, a helpful, intelligent and friendly AI assistant.

Your creator is Arav, a student at Swami Vivekanand Shiksha Niketan School.
Arav is interested in AI, Python, app development, technology and creative
problem solving. He is building NEXTGEN AI as a learning and development project.

When asked who created NEXTGEN AI, explain that it is Arav's project.
When asked who Arav is, describe him positively using only these known facts.
Never invent awards, ranks, marks, achievements or qualifications.

Rules:
- Answer in the language used by the user.
- Be clear, useful, accurate and respectful.
- For coding, give complete and properly indented code when requested.
- Explain errors step by step.
- Never pretend that you executed or tested code if you did not.
- If information may be outdated, say so.
- Use web search context when it is provided.
- Do not invent sources, facts or citations.
- For stock market topics, provide educational information only.
  Do not promise profits or tell a young user to make real-money investments.
- If a user asks for a dangerous or age-restricted activity, respond safely.
"""

def grok_request(messages):
    response = requests.post(
        "https://api.x.ai/v1/chat/completions",
        headers={
            "Authorization": f"Bearer {GROK_KEY}",
            "Content-Type": "application/json"
        },
        json={
            "model": GROK_MODEL,
            "messages": messages,
            "temperature": 0.6
        },
        timeout=75
    )
    response.raise_for_status()
    return response.json()["choices"][0]["message"]["content"]

def gemini_request(messages):
    if not GEMINI_KEY:
        raise RuntimeError("Gemini API key नहीं मिली।")

    contents = []

    for msg in messages:
        role = "model" if msg["role"] == "assistant" else "user"
        contents.append({
            "role": role,
            "parts": [{"text": msg["content"]}]
        })

    url = (
        "https://generativelanguage.googleapis.com/v1beta/models/"
        + GEMINI_MODEL
        + ":generateContent?key="
        + GEMINI_KEY
    )

    response = requests.post(
        url,
        json={
            "systemInstruction": {
                "parts": [{"text": SYSTEM_PROMPT}]
            },
            "contents": contents,
            "generationConfig": {
                "temperature": 0.6
            }
        },
        timeout=75
    )

    response.raise_for_status()
    data = response.json()

    return data["candidates"][0]["content"]["parts"][0]["text"]

def groq_request(messages):
    response = requests.post(
        "https://api.groq.com/openai/v1/chat/completions",
        headers={
            "Authorization": f"Bearer {GROQ_KEY}",
            "Content-Type": "application/json"
        },
        json={
            "model": GROQ_MODEL,
            "messages": messages,
            "temperature": 0.6
        },
        timeout=75
    )
    response.raise_for_status()
    return response.json()["choices"][0]["message"]["content"]

def ask_ai(messages):
    errors = []

    providers = [
        ("Grok", GROK_KEY, grok_request),
        ("Gemini", GEMINI_KEY, gemini_request),
        ("Groq", GROQ_KEY, groq_request)
    ]

    for name, key, function in providers:
        if not key:
            continue

        try:
            answer = function(messages)
            if answer:
                st.session_state.last_provider = name
                return answer
        except Exception as exc:
            errors.append(f"{name}: {str(exc)[:250]}")

    raise RuntimeError(
        "कोई AI provider जवाब नहीं दे पाया।\n\n"
        + "\n".join(errors)
    )

# -------------------- SMART AI ROUTER --------------------

def smart_ai_answer(prompt, history):
    search_used = False
    search_method = ""

    if (
        st.session_state.web_search_enabled
        and needs_web_search(prompt)
    ):
        # First preference: Grok native web search
        if GROK_KEY:
            try:
                answer = grok_web_search(prompt, history)
                st.session_state.last_provider = "Grok Web Search"
                st.session_state.last_search = "Grok Native Search"
                return answer, "Grok Native Web Search"
            except Exception:
                pass

        # Fallback: Tavily search + AI response
        if TAVILY_KEY:
            try:
                search_context = tavily_search(prompt)
                if search_context:
                    search_used = True
                    search_method = "Tavily"

                    messages = [
                        {"role": "system", "content": SYSTEM_PROMPT},
                        *history[-10:],
                        {
                            "role": "user",
                            "content": (
                                prompt
                                + "\n\nUse these web search results. "
                                "Mention uncertainty and include source URLs "
                                "where available:\n\n"
                                + search_context
                            )
                        }
                    ]

                    answer = ask_ai(messages)
                    st.session_state.last_search = "Tavily"
                    return answer, "Tavily Search"

            except Exception:
                pass

    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        *history[-10:],
        {"role": "user", "content": prompt}
    ]

    answer = ask_ai(messages)
    st.session_state.last_search = "Not used"
    return answer, "No Web Search"

# -------------------- SIDEBAR --------------------

with st.sidebar:
    st.markdown("# ✦ NEXTGEN AI")
    st.caption("Your personal AI workspace")

    st.markdown("---")

    menu = [
        "Dashboard",
        "AI Chat",
        "Stock Market",
        "Tool Center",
        "App Builder",
        "Website Builder",
        "Learn & Explore",
        "PDF Assistant",
        "My Creations",
        "Settings",
        "About"
    ]

    for item in menu:
        if st.button(
            ("● " if st.session_state.page == item else "○ ") + item,
            key="nav_" + item,
            use_container_width=True
        ):
            set_page(item)
            st.rerun()

    st.markdown("---")
    st.markdown("**AI Providers**")

    st.caption("Grok: " + ("Connected" if GROK_KEY else "Not configured"))
    st.caption("Gemini: " + ("Connected" if GEMINI_KEY else "Not configured"))
    st.caption("Groq: " + ("Connected" if GROQ_KEY else "Not configured"))

    st.markdown("---")
    st.caption("NEXTGEN AI • Version 2.0")

# ============================================================
# DASHBOARD
# ============================================================

page = st.session_state.page

if page == "Dashboard":

    st.markdown("""
    <div class="hero">
        <h1>✦ NEXTGEN AI</h1>
        <p>Your intelligent workspace for AI, coding, learning and creativity.</p>
        <p class="small-muted">Think smarter. Build better. Explore more.</p>
    </div>
    """, unsafe_allow_html=True)

    c1, c2, c3 = st.columns(3)
    c1.metric("AI Providers", sum(bool(x) for x in [
        GROK_KEY, GEMINI_KEY, GROQ_KEY
    ]))
    c2.metric(
        "Smart Web Search",
        "ON" if st.session_state.web_search_enabled else "OFF"
    )
    c3.metric("Workspace", "Ready")

    st.markdown("## Explore your workspace")

    items = [
        ("AI Chat", "Chat with your AI assistant.", "✦"),
        ("Stock Market", "Explore market data and stock charts.", "📈"),
        ("Tool Center", "Useful tools for everyday tasks.", "🧰"),
        ("App Builder", "Generate starter app projects.", "⚙️"),
        ("Website Builder", "Create website starter projects.", "🌐"),
        ("Learn & Explore", "Learn technology and new concepts.", "📚"),
        ("PDF Assistant", "Read and summarize PDF documents.", "📄"),
        ("My Creations", "View your saved projects.", "🗂️"),
    ]

    cols = st.columns(4)

    for i, (title, desc, icon) in enumerate(items):
        with cols[i % 4]:
            show_card(title, desc, icon)
            if st.button("Open " + title, key="open_" + title,
                         use_container_width=True):
                set_page(title)
                st.rerun()

# ============================================================
# AI CHAT
# ============================================================

elif page == "AI Chat":

    st.title("✦ AI Chat")
    st.caption("Ask questions, write code, learn and create.")

    if not st.session_state.messages:
        st.session_state.messages = get_messages(
            st.session_state.chat_id
        )

    for msg in st.session_state.messages:
        with st.chat_message(msg["role"]):
            st.markdown(msg["content"])

    prompt = st.chat_input("Message NEXTGEN AI...")

    if prompt:
        st.session_state.messages.append({
            "role": "user",
            "content": prompt
        })

        save_message(st.session_state.chat_id, "user", prompt)

        with st.chat_message("user"):
            st.markdown(prompt)

        with st.chat_message("assistant"):
            with st.spinner("NEXTGEN AI is thinking..."):
                try:
                    history = st.session_state.messages[:-1]
                    answer, search_status = smart_ai_answer(
                        prompt,
                        history
                    )

                    st.markdown(answer)
                    st.caption(
                        "Provider: "
                        + st.session_state.last_provider
                        + " • Search: "
                        + search_status
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

                except Exception as exc:
                    st.error(str(exc))

    col1, col2 = st.columns(2)

    with col1:
        if st.button("＋ New Chat"):
            st.session_state.chat_id = (
                "chat_" + str(int(time.time()))
            )
            st.session_state.messages = []
            st.rerun()

    with col2:
        if st.button("Clear Current Chat"):
            con = get_db()
            con.execute(
                "DELETE FROM chats WHERE chat_id=?",
                (st.session_state.chat_id,)
            )
            con.commit()
            con.close()
            st.session_state.messages = []
            st.rerun()

# ============================================================
# STOCK MARKET — EDUCATIONAL
# ============================================================

elif page == "Stock Market":

    st.title("📈 Stock Market Explorer")
    st.caption(
        "Educational market dashboard. Not financial advice."
    )

    try:
        import yfinance as yf
        import pandas as pd
    except ImportError:
        st.warning("Install yfinance and pandas to use this section.")
        st.code("pip install yfinance pandas")
        st.stop()

    symbol = st.text_input(
        "Enter stock symbol",
        value="AAPL"
    ).strip().upper()

    period = st.selectbox(
        "Chart period",
        ["1mo", "3mo", "6mo", "1y", "2y", "5y"]
    )

    if st.button("Analyze Stock", type="primary"):
        if symbol:
            try:
                ticker = yf.Ticker(symbol)
                hist = ticker.history(period=period)

                if hist.empty:
                    st.warning("No market data found for this symbol.")
                else:
                    latest = float(hist["Close"].iloc[-1])
                    previous = (
                        float(hist["Close"].iloc[-2])
                        if len(hist) > 1 else latest
                    )

                    change = latest - previous
                    percentage = (
                        (change / previous) * 100
                        if previous else 0
                    )

                    a, b, c = st.columns(3)
                    a.metric("Latest Close", f"{latest:.2f}")
                    b.metric("Daily Change", f"{change:.2f}")
                    c.metric("Change %", f"{percentage:.2f}%")

                    st.markdown("### Price Chart")
                    st.line_chart(hist["Close"])

                    st.markdown("### Historical Data")
                    st.dataframe(
                        hist.tail(20),
                        use_container_width=True
                    )

                    st.info(
                        "यह historical data है। इससे future returns "
                        "की गारंटी नहीं मिलती। किसी stock में पैसा लगाने "
                        "का फैसला केवल इस chart के आधार पर न करें।"
                    )

            except Exception as exc:
                st.error("Market data error: " + str(exc))

    st.markdown("---")
    st.markdown("### Watchlist")

    watchlist_text = st.text_area(
        "One symbol per line",
        value="\n".join(st.session_state.stock_watchlist)
    )

    if st.button("Save Watchlist"):
        st.session_state.stock_watchlist = [
            x.strip().upper()
            for x in watchlist_text.splitlines()
            if x.strip()
        ]
        st.success("Watchlist saved for this session.")

    if st.session_state.stock_watchlist:
        st.write(", ".join(st.session_state.stock_watchlist))

    st.caption(
        "Market data may be delayed or unavailable. "
        "Use this section for learning, not trading decisions."
    )

# ============================================================
# TOOL CENTER
# ============================================================

elif page == "Tool Center":

    st.title("🧰 Tool Center")

    tool = st.selectbox(
        "Choose a tool",
        [
            "Word Counter",
            "Text Case Converter",
            "Percentage Calculator",
            "Simple Calculator",
            "JSON Formatter",
            "Password Strength Checker"
        ]
    )

    if tool == "Word Counter":
        text_value = st.text_area("Enter text")
        words = len(text_value.split())
        characters = len(text_value)
        st.metric("Words", words)
        st.metric("Characters", characters)

    elif tool == "Text Case Converter":
        text_value = st.text_area("Enter text")
        option = st.selectbox(
            "Conversion",
            ["UPPERCASE", "lowercase", "Title Case"]
        )

        if option == "UPPERCASE":
            result = text_value.upper()
        elif option == "lowercase":
            result = text_value.lower()
        else:
            result = text_value.title()

        st.text_area("Result", result)

    elif tool == "Percentage Calculator":
        total = st.number_input("Total", min_value=0.0)
        percentage = st.number_input("Percentage", min_value=0.0)
        if st.button("Calculate Percentage"):
            st.success(f"Result: {total * percentage / 100:.2f}")

    elif tool == "Simple Calculator":
        a = st.number_input("First number")
        b = st.number_input("Second number")
        operation = st.selectbox(
            "Operation",
            ["Add", "Subtract", "Multiply", "Divide"]
        )

        if st.button("Calculate"):
            if operation == "Add":
                result = a + b
            elif operation == "Subtract":
                result = a - b
            elif operation == "Multiply":
                result = a * b
            else:
                result = "Cannot divide by zero" if b == 0 else a / b

            st.success(str(result))

    elif tool == "JSON Formatter":
        raw_json = st.text_area("Paste JSON")
        if st.button("Format JSON"):
            try:
                formatted = json.dumps(
                    json.loads(raw_json),
                    indent=4,
                    ensure_ascii=False
                )
                st.code(formatted, language="json")
            except Exception as exc:
                st.error(str(exc))

    elif tool == "Password Strength Checker":
        password = st.text_input(
            "Enter a sample password",
            type="password"
        )

        if password:
            score = 0
            score += len(password) >= 12
            score += bool(re.search(r"[A-Z]", password))
            score += bool(re.search(r"[a-z]", password))
            score += bool(re.search(r"[0-9]", password))
            score += bool(re.search(r"[^A-Za-z0-9]", password))

            if score >= 4:
                st.success("This sample has several strong features.")
            elif score >= 2:
                st.warning("This sample could be stronger.")
            else:
                st.error("This sample is easy to guess.")

            st.caption("Do not enter a real password here.")

# ============================================================
# APP BUILDER
# ============================================================

elif page == "App Builder":

    st.title("⚙️ AI App Builder")
    st.caption("Generate a starter project from your idea.")

    idea = st.text_area(
        "Describe your app",
        placeholder="Example: A student task manager with notes and reminders."
    )

    language = st.selectbox(
        "Technology",
        ["Python + Streamlit", "HTML + CSS + JavaScript", "Python"]
    )

    if st.button("Generate App Project", type="primary"):
        if not idea.strip():
            st.warning("Please describe your app first.")
        else:
            prompt = f"""
Create a practical starter project for this app:

{idea}

Technology: {language}

Return ONLY valid JSON in this exact format:
{{
  "project_name": "project name",
  "description": "short description",
  "files": [
    {{
      "name": "app.py",
      "content": "complete source code"
    }}
  ]
}}

Include all essential files. Keep the project safe and beginner-friendly.
"""

            with st.spinner("Building your starter project..."):
                try:
                    result = ask_ai([
                        {"role": "system", "content": SYSTEM_PROMPT},
                        {"role": "user", "content": prompt}
                    ])

                    project = extract_json(result)

                    st.session_state.generated_project = project

                    st.success(
                        "Project generated: "
                        + project.get("project_name", "New Project")
                    )

                except Exception as exc:
                    st.error(str(exc))

    if st.session_state.get("generated_project"):
        project = st.session_state.generated_project
        st.markdown("### Generated Files")

        files = project.get("files", [])

        for index, file in enumerate(files):
            with st.expander(file.get("name", f"file_{index}.txt")):
                edited = st.text_area(
                    "Edit file",
                    value=file.get("content", ""),
                    height=250,
                    key=f"app_edit_{index}"
                )
                file["content"] = edited

        if st.button("Save to My Creations"):
            save_creation(
                project.get("project_name", "App Project"),
                "App Builder",
                json.dumps(project, ensure_ascii=False)
            )
            st.success("Saved to My Creations.")

        if st.button("Prepare App ZIP"):
            memory_file = io.BytesIO()

            with zipfile.ZipFile(
                memory_file,
                "w",
                zipfile.ZIP_DEFLATED
            ) as zip_file:
                for file in files:
                    name = os.path.basename(file.get("name", "file.txt"))
                    zip_file.writestr(name, file.get("content", ""))

            st.download_button(
                "Download App ZIP",
                data=memory_file.getvalue(),
                file_name="nextgen_app_project.zip",
                mime="application/zip"
            )

# ============================================================
# WEBSITE BUILDER
# ============================================================

elif page == "Website Builder":

    st.title("🌐 AI Website Builder")

    idea = st.text_area(
        "Describe your website",
        placeholder="Example: A modern portfolio website for a student developer."
    )

    if st.button("Generate Website", type="primary"):
        if not idea.strip():
            st.warning("Describe your website first.")
        else:
            prompt = f"""
Create a complete beginner-friendly website.

Website idea:
{idea}

Return ONLY valid JSON:
{{
  "project_name": "Website name",
  "files": [
    {{"name": "index.html", "content": "complete HTML"}},
    {{"name": "style.css", "content": "complete CSS"}},
    {{"name": "script.js", "content": "complete JavaScript"}}
  ]
}}

Use responsive design and safe code.
"""

            with st.spinner("Creating your website..."):
                try:
                    result = ask_ai([
                        {"role": "system", "content": SYSTEM_PROMPT},
                        {"role": "user", "content": prompt}
                    ])

                    st.session_state.generated_website = extract_json(result)
                    st.success("Website starter generated.")

                except Exception as exc:
                    st.error(str(exc))

    if st.session_state.get("generated_website"):
        project = st.session_state.generated_website
        files = project.get("files", [])

        for index, file in enumerate(files):
            with st.expander(file.get("name", f"file_{index}.txt")):
                file["content"] = st.text_area(
                    "Edit file",
                    value=file.get("content", ""),
                    height=250,
                    key=f"web_edit_{index}"
                )

        if st.button("Save Website"):
            save_creation(
                project.get("project_name", "Website"),
                "Website Builder",
                json.dumps(project, ensure_ascii=False)
            )
            st.success("Website saved.")

        if st.button("Prepare Website ZIP"):
            memory_file = io.BytesIO()

            with zipfile.ZipFile(
                memory_file,
                "w",
                zipfile.ZIP_DEFLATED
            ) as zip_file:
                for file in files:
                    name = os.path.basename(file.get("name", "file.txt"))
                    zip_file.writestr(name, file.get("content", ""))

            st.download_button(
                "Download Website ZIP",
                data=memory_file.getvalue(),
                file_name="nextgen_website.zip",
                mime="application/zip"
            )

# ============================================================
# LEARN & EXPLORE
# ============================================================

elif page == "Learn & Explore":

    st.title("📚 Learn & Explore")

    topic = st.text_input(
        "What do you want to learn?",
        placeholder="Python, AI, science, mathematics..."
    )

    level = st.selectbox(
        "Learning level",
        ["Beginner", "Intermediate", "Advanced"]
    )

    if st.button("Start Learning", type="primary"):
        if topic.strip():
            prompt = f"""
Teach me about: {topic}
Level: {level}

Give:
1. Simple explanation
2. Important concepts
3. Practical examples
4. Common mistakes
5. Five practice questions
Use age-appropriate and clear language.
"""

            with st.spinner("Preparing your lesson..."):
                try:
                    answer = ask_ai([
                        {"role": "system", "content": SYSTEM_PROMPT},
                        {"role": "user", "content": prompt}
                    ])
                    st.markdown(answer)
                except Exception as exc:
                    st.error(str(exc))

# ============================================================
# PDF ASSISTANT
# ============================================================

elif page == "PDF Assistant":

    st.title("📄 PDF Assistant")
    st.caption("Upload a PDF to summarize or ask questions about it.")

    uploaded_pdf = st.file_uploader(
        "Upload PDF",
        type=["pdf"]
    )

    if uploaded_pdf:
        try:
            from pypdf import PdfReader

            reader = PdfReader(uploaded_pdf)
            pdf_text = "\n".join(
                page.extract_text() or ""
                for page in reader.pages
            )

            st.success(
                f"PDF loaded • {len(reader.pages)} pages"
            )

            st.text_area(
                "Extracted text preview",
                pdf_text[:4000],
                height=180
            )

            task = st.selectbox(
                "Choose task",
                ["Summarize PDF", "Ask a question"]
            )

            question = ""
            if task == "Ask a question":
                question = st.text_input("Your question")

            if st.button("Process PDF"):
                if not pdf_text.strip():
                    st.warning(
                        "No readable text found. This PDF may be scanned."
                    )
                else:
                    if task == "Summarize PDF":
                        prompt = (
                            "Summarize this document in clear points:\n"
                            + pdf_text[:25000]
                        )
                    else:
                        prompt = (
                            "Answer this question using only the PDF "
                            "content. If the answer is missing, say so.\n"
                            "Question: " + question
                            + "\nPDF:\n" + pdf_text[:25000]
                        )

                    with st.spinner("Reading your PDF..."):
                        answer = ask_ai([
                            {"role": "system", "content": SYSTEM_PROMPT},
                            {"role": "user", "content": prompt}
                        ])
                        st.markdown(answer)

        except ImportError:
            st.error("Install pypdf: pip install pypdf")
        except Exception as exc:
            st.error("PDF error: " + str(exc))

# ============================================================
# MY CREATIONS
# ============================================================

elif page == "My Creations":

    st.title("🗂️ My Creations")

    con = get_db()
    rows = con.execute(
        "SELECT id, title, category, created_at, content "
        "FROM creations ORDER BY id DESC"
    ).fetchall()
    con.close()

    if not rows:
        st.info("Your saved projects will appear here.")
    else:
        for row in rows:
            with st.expander(
                f"{row[1]} • {row[2]} • {row[3][:10]}"
            ):
                st.code(row[4][:5000])

                st.download_button(
                    "Download saved content",
                    data=row[4],
                    file_name=f"creation_{row[0]}.json",
                    mime="application/json",
                    key=f"creation_download_{row[0]}"
                )

# ============================================================
# SETTINGS
# ============================================================

elif page == "Settings":

    st.title("⚙️ Settings")

    st.markdown("### Smart Web Search")

    st.session_state.web_search_enabled = st.toggle(
        "Enable automatic web search",
        value=st.session_state.web_search_enabled,
        help="Search is attempted only when the question needs current information."
    )

    st.markdown("### AI Provider Configuration")

    st.caption(
        "API keys are read from your local .env file. "
        "Do not paste private API keys into chat."
    )

    st.write(
        "Grok: " + ("Configured" if GROK_KEY else "Not configured")
    )
    st.write(
        "Gemini: " + ("Configured" if GEMINI_KEY else "Not configured")
    )
    st.write(
        "Groq: " + ("Configured" if GROQ_KEY else "Not configured")
    )
    st.write(
        "Tavily: " + ("Configured" if TAVILY_KEY else "Not configured")
    )

    st.markdown("### Model Configuration")
    st.code(
        f"Grok: {GROK_MODEL}\n"
        f"Gemini: {GEMINI_MODEL}\n"
        f"Groq: {GROQ_MODEL}"
    )

    st.markdown("### Search Routing")
    st.write("1. Detect whether the question needs current information.")
    st.write("2. Try Grok native Web Search.")
    st.write("3. If unavailable, try Tavily.")
    st.write("4. If search is unnecessary, use the normal AI provider chain.")

    st.info(
        "If both Grok native search and Tavily are unavailable, "
        "NEXTGEN AI will try to answer without live search."
    )

# ============================================================
# ABOUT
# ============================================================

elif page == "About":

    st.title("✦ About NEXTGEN AI")

    st.markdown("""
    NEXTGEN AI is an AI workspace project created by Arav.

    **Project interests**
    - Artificial Intelligence
    - Python programming
    - App and website development
    - Technology and learning
    - Creative problem solving

    **AI providers**
    - Grok
    - Gemini
    - Groq

    **Other features**
    - Smart Web Search
    - Stock Market Explorer
    - PDF Assistant
    - App Builder
    - Website Builder
    - Tool Center

    NEXTGEN AI is a learning and development project.
    """)

# -------------------- FOOTER --------------------

st.markdown("---")
st.markdown(
    "<p style='text-align:center;color:#77849b;font-size:12px;'>"
    "✦ NEXTGEN AI • Built for learning, creativity and innovation"
    "</p>",
    unsafe_allow_html=True
)
