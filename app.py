
import os
import io
import sqlite3
import hashlib
import secrets
from datetime import datetime, date

import requests
import streamlit as st
import pandas as pd
from dotenv import load_dotenv
from google import genai
from google.genai import types
from PIL import Image
from pypdf import PdfReader

from auto_pilot import generate_with_autopilot

# =========================================
# NEXTGEN AI
# =========================================

load_dotenv()

st.set_page_config(
    page_title="NEXTGEN AI",
    page_icon="🚀",
    layout="wide"
)

GEMINI_KEY = os.getenv("GEMINI_API_KEY")
FINNHUB_KEY = os.getenv("FINNHUB_API_KEY")
MODEL = "gemini-3.8-flash"
DB_PATH = "nextgen_users.db"

# =========================================
# DATABASE
# =========================================

def database():
    con = sqlite3.connect(DB_PATH)
    con.execute("""
        CREATE TABLE IF NOT EXISTS users (
            username TEXT PRIMARY KEY,
            salt TEXT NOT NULL,
            password_hash TEXT NOT NULL
        )
    """)
    con.execute("""
        CREATE TABLE IF NOT EXISTS messages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT NOT NULL,
            role TEXT NOT NULL,
            content TEXT NOT NULL
        )
    """)
    con.commit()
    return con

def hash_password(password, salt):
    return hashlib.pbkdf2_hmac(
        "sha256",
        password.encode(),
        bytes.fromhex(salt),
        200000
    ).hex()

def signup(username, password):
    username = username.strip().lower()

    if len(username) < 3 or len(password) < 8:
        return False, "Username कम से कम 3 और password 8 characters का होना चाहिए।"

    salt = secrets.token_hex(16)
    hashed = hash_password(password, salt)

    con = database()

    try:
        con.execute(
            "INSERT INTO users VALUES (?, ?, ?)",
            (username, salt, hashed)
        )
        con.commit()
        return True, "Account created!"
    except sqlite3.IntegrityError:
        return False, "Username पहले से मौजूद है।"
    finally:
        con.close()

def login(username, password):
    con = database()

    row = con.execute(
        "SELECT salt, password_hash FROM users WHERE username=?",
        (username.strip().lower(),)
    ).fetchone()

    con.close()

    if not row:
        return False

    return secrets.compare_digest(
        hash_password(password, row[0]),
        row[1]
    )

def save_message(username, role, content):
    if username == "guest":
        return

    con = database()

    con.execute(
        "INSERT INTO messages (username, role, content) VALUES (?, ?, ?)",
        (username, role, content)
    )

    con.commit()
    con.close()

def load_messages(username):
    if username == "guest":
        return []

    con = database()

    rows = con.execute(
        "SELECT role, content FROM messages WHERE username=? ORDER BY id",
        (username,)
    ).fetchall()

    con.close()

    return [
        {"role": role, "content": content}
        for role, content in rows
    ]

# =========================================
# SESSION
# =========================================

defaults = {
    "authenticated": False,
    "username": None,
    "messages": [],
    "client": None,
    "last_provider": "Not used yet"
}

for key, value in defaults.items():
    if key not in st.session_state:
        st.session_state[key] = value

# =========================================
# DESIGN
# =========================================

st.markdown("""
<style>
.stApp {
    background: linear-gradient(
        135deg, #080817, #11112b, #080817
    );
    color: white;
}

[data-testid="stSidebar"] {
    background: #101026;
    border-right: 1px solid #29294f;
}

h1, h2, h3 {
    color: #a78bfa !important;
}

.stButton button {
    background: linear-gradient(90deg, #7c3aed, #2563eb);
    color: white;
    border: none;
    border-radius: 12px;
    font-weight: bold;
}

[data-testid="stChatMessage"] {
    background: #15152e;
    border: 1px solid #29294f;
    border-radius: 14px;
}

.hero {
    padding: 22px;
    border-radius: 18px;
    background: linear-gradient(
        120deg, #171735, #252052, #10244b
    );
    border: 1px solid #454078;
    margin-bottom: 20px;
}

.footer {
    text-align: center;
    color: #8888aa;
    padding: 20px;
}
</style>
""", unsafe_allow_html=True)

# =========================================
# GEMINI ENGINE
# =========================================

def get_client():

    if not GEMINI_KEY:
        raise ValueError("GEMINI_API_KEY missing in .env")

    if st.session_state.client is None:
        st.session_state.client = genai.Client(
            api_key=GEMINI_KEY
        )

    return st.session_state.client

def generate_answer(contents):

    client = get_client()

    answer, provider = generate_with_autopilot(
        client=client,
        model=MODEL,
        contents=contents
    )

    st.session_state.last_provider = provider

    return answer

# =========================================
# FINNHUB API ENGINE
# =========================================

FINNHUB_BASE = "https://finnhub.io/api/v1"

def finnhub_get(endpoint, params=None):

    if not FINNHUB_KEY:
        raise ValueError(
            "FINNHUB_API_KEY तुम्हारी .env फाइल में नहीं मिली।"
        )

    headers = {
        "X-Finnhub-Token": FINNHUB_KEY
    }

    response = requests.get(
        FINNHUB_BASE + endpoint,
        params=params or {},
        headers=headers,
        timeout=15
    )

    if response.status_code == 429:
        raise RuntimeError(
            "Finnhub API rate limit पूरी हो गई। थोड़ी देर बाद कोशिश करो।"
        )

    response.raise_for_status()

    return response.json()

@st.cache_data(ttl=30, show_spinner=False)
def get_stock_quote(symbol):

    return finnhub_get(
        "/quote",
        {"symbol": symbol}
    )

@st.cache_data(ttl=300, show_spinner=False)
def get_company_profile(symbol):

    return finnhub_get(
        "/stock/profile2",
        {"symbol": symbol}
    )

@st.cache_data(ttl=120, show_spinner=False)
def get_market_news():

    return finnhub_get(
        "/news",
        {"category": "general"}
    )

# =========================================
# AUTHENTICATION
# =========================================

def authentication_screen():

    st.markdown("""
    <div class="hero">
        <h1 style="text-align:center;">🚀 NEXTGEN AI</h1>
        <h3 style="text-align:center;">
            One Platform. Endless Possibilities.
        </h3>
        <p style="text-align:center;">
            Your Personal AI Universe
        </p>
    </div>
    """, unsafe_allow_html=True)

    _, center, _ = st.columns([1, 2, 1])

    with center:

        option = st.radio(
            "Choose Access",
            ["Guest Mode", "Sign Up", "Login"],
            horizontal=True
        )

        if option == "Guest Mode":

            st.info("Guest chats स्थायी रूप से सेव नहीं होंगी।")

            if st.button("Continue as Guest"):
                st.session_state.authenticated = True
                st.session_state.username = "guest"
                st.session_state.messages = []
                st.rerun()

        elif option == "Sign Up":

            st.subheader("Create Account")

            username = st.text_input("Username")
            password = st.text_input("Password", type="password")
            confirm = st.text_input("Confirm Password", type="password")

            if st.button("Create Account"):

                if password != confirm:
                    st.error("Passwords match नहीं करते।")
                else:
                    success, message = signup(username, password)

                    if success:
                        st.success(message)
                        st.info("अब Login विकल्प चुनो।")
                    else:
                        st.error(message)

        else:

            st.subheader("Welcome Back")

            username = st.text_input("Username", key="login_user")
            password = st.text_input(
                "Password",
                type="password",
                key="login_password"
            )

            if st.button("Login"):

                if login(username, password):

                    st.session_state.authenticated = True
                    st.session_state.username = username.strip().lower()
                    st.session_state.messages = load_messages(
                        st.session_state.username
                    )

                    st.rerun()

                else:
                    st.error("Wrong username or password.")

if not st.session_state.authenticated:
    authentication_screen()
    st.stop()

# =========================================
# SIDEBAR
# =========================================

st.sidebar.markdown("# 🚀 NEXTGEN AI")
st.sidebar.caption("YOUR CREATIVE UNIVERSE")

st.sidebar.markdown("---")

st.sidebar.success(
    f"User: {st.session_state.username}"
)

page = st.sidebar.radio(
    "NAVIGATION",
    [
        "AI Chat",
        "Stock Market",
        "AI Vision",
        "PDF Assistant",
        "Voice Studio",
        "AI Image",
        "AI Video",
        "About"
    ]
)

st.sidebar.markdown("---")

st.sidebar.markdown("### SYSTEM STATUS")

st.sidebar.write(
    "Gemini:",
    "🟢 Connected" if GEMINI_KEY else "🔴 Missing"
)

st.sidebar.write(
    "Finnhub:",
    "🟢 Configured" if FINNHUB_KEY else "🔴 Missing"
)

st.sidebar.caption(
    f"Last AI Provider: {st.session_state.last_provider}"
)

if st.sidebar.button("Clear Chat History"):

    st.session_state.messages = []

    if st.session_state.username != "guest":
        con = database()
        con.execute(
            "DELETE FROM messages WHERE username=?",
            (st.session_state.username,)
        )
        con.commit()
        con.close()

    st.rerun()

if st.sidebar.button("Logout"):

    st.session_state.authenticated = False
    st.session_state.username = None
    st.session_state.messages = []
    st.session_state.client = None

    st.rerun()

# =========================================
# MAIN HEADER
# =========================================

st.markdown("""
<div class="hero">
    <h1>🚀 NEXTGEN AI</h1>
    <h3>One Platform. Endless Possibilities.</h3>
    <p>Your intelligent AI universe.</p>
</div>
""", unsafe_allow_html=True)

# =========================================
# CHAT PROCESSOR
# =========================================

def process_chat(prompt, uploaded_file=None):

    user_content = prompt or "Please analyze the attached file."

    if uploaded_file:
        user_content += f"\n[File: {uploaded_file.name}]"

    st.session_state.messages.append({
        "role": "user",
        "content": user_content
    })

    save_message(
        st.session_state.username,
        "user",
        user_content
    )

    contents = [
        "You are NEXTGEN AI, a helpful and accurate AI assistant. "
        "Use the user's language. Never claim to have generated "
        "a file or image unless it was actually generated."
    ]

    for msg in st.session_state.messages[-12:]:
        contents.append(
            f'{msg["role"].upper()}: {msg["content"]}'
        )

    if uploaded_file:

        file_bytes = uploaded_file.getvalue()
        filename = uploaded_file.name.lower()

        if filename.endswith(
            (".png", ".jpg", ".jpeg", ".webp")
        ):
            contents.append(
                Image.open(io.BytesIO(file_bytes))
            )

        elif filename.endswith(".pdf"):

            reader = PdfReader(io.BytesIO(file_bytes))

            pdf_text = "\n".join(
                page.extract_text() or ""
                for page in reader.pages
            )

            contents.append(
                "PDF CONTENT:\n" + pdf_text[:30000]
            )

        elif filename.endswith(".txt"):

            contents.append(
                file_bytes.decode("utf-8", errors="replace")[:30000]
            )

    try:
        with st.spinner("NEXTGEN AI is thinking..."):
            answer = generate_answer(contents)

    except Exception as error:
        answer = f"AI Error: {error}"

    st.session_state.messages.append({
        "role": "assistant",
        "content": answer
    })

    save_message(
        st.session_state.username,
        "assistant",
        answer
    )

# =========================================
# AI CHAT
# =========================================

if page == "AI Chat":

    st.header("💬 AI Chat")

    for msg in st.session_state.messages:

        with st.chat_message(msg["role"]):
            st.markdown(msg["content"])

    uploaded_file = st.file_uploader(
        "➕ Attach image, PDF or text file",
        type=["png", "jpg", "jpeg", "webp", "pdf", "txt"],
        key="chat_file"
    )

    prompt = st.chat_input("Message NEXTGEN AI...")

    if prompt or uploaded_file:

        process_chat(
            prompt,
            uploaded_file
        )

        st.rerun()

# =========================================
# STOCK MARKET CENTER
# =========================================

elif page == "Stock Market":

    st.header("📈 NEXTGEN Stock Market Center")

    st.caption(
        "Market data powered by Finnhub"
    )

    if not FINNHUB_KEY:

        st.error(
            "FINNHUB_API_KEY नहीं मिली। .env में API key जोड़ो।"
        )

    else:

        st.success("Finnhub API configured")

        symbol = st.text_input(
            "Enter Stock Symbol",
            value="AAPL",
            help="उदाहरण: AAPL, MSFT, NVDA या तुम्हारा समर्थित Finnhub symbol"
        ).strip().upper()

        col1, col2 = st.columns(2)

        with col1:
            if st.button("🔍 Get Stock Data"):
                st.session_state["selected_stock"] = symbol

        with col2:
            if st.button("🔄 Refresh Data"):
                get_stock_quote.clear()
                get_company_profile.clear()
                st.session_state["selected_stock"] = symbol

        selected = st.session_state.get(
            "selected_stock",
            symbol
        )

        if selected:

            try:

                with st.spinner("Fetching Finnhub market data..."):

                    quote = get_stock_quote(selected)
                    profile = get_company_profile(selected)

                if not quote or quote.get("c") is None:
                    st.warning(
                        "इस symbol का quote उपलब्ध नहीं है। Symbol जाँचो।"
                    )

                else:

                    company_name = profile.get(
                        "name",
                        selected
                    )

                    st.subheader(
                        f"{company_name} ({selected})"
                    )

                    price = quote.get("c", 0)
                    change = quote.get("d", 0)
                    change_percent = quote.get("dp", 0)

                    currency = profile.get("currency", "USD")

                    c1, c2, c3 = st.columns(3)

                    c1.metric(
                        "Current Price",
                        f"{currency} {price:,.2f}",
                        f"{change:,.2f}"
                    )

                    c2.metric(
                        "Change %",
                        f"{change_percent:.2f}%"
                    )

                    c3.metric(
                        "Previous Close",
                        f"{currency} {quote.get('pc', 0):,.2f}"
                    )

                    st.markdown("### Today's Quote")

                    quote_table = pd.DataFrame({
                        "Metric": [
                            "Open",
                            "Day High",
                            "Day Low",
                            "Previous Close",
                            "Current Price"
                        ],
                        "Value": [
                            quote.get("o"),
                            quote.get("h"),
                            quote.get("l"),
                            quote.get("pc"),
                            quote.get("c")
                        ]
                    })

                    st.dataframe(
                        quote_table,
                        use_container_width=True,
                        hide_index=True
                    )

                    st.markdown("### Company Information")

                    p1, p2 = st.columns(2)

                    with p1:
                        st.write(
                            "**Industry:**",
                            profile.get("finnhubIndustry", "Not available")
                        )
                        st.write(
                            "**Exchange:**",
                            profile.get("exchange", "Not available")
                        )

                    with p2:
                        st.write(
                            "**Country:**",
                            profile.get("country", "Not available")
                        )
                        st.write(
                            "**Website:**",
                            profile.get("weburl", "Not available")
                        )

                    st.caption(
                        "Quote time is supplied by Finnhub. "
                        "Market prices may be delayed or unavailable "
                        "depending on the API plan and exchange."
                    )

                    st.markdown("### 🤖 AI Stock Explanation")

                    if st.button("Ask AI to Explain This Stock"):

                        try:

                            analysis_data = f"""
                            Company: {company_name}
                            Symbol: {selected}
                            Current price: {price}
                            Change: {change}
                            Change percent: {change_percent}
                            Previous close: {quote.get('pc')}
                            Day high: {quote.get('h')}
                            Day low: {quote.get('l')}
                            Industry: {profile.get('finnhubIndustry')}

                            Explain these figures in simple language.
                            Mention limitations and uncertainty.
                            Do not promise returns or make guaranteed predictions.
                            This is educational information, not investment advice.
                            """

                            with st.spinner("AI is explaining..."):
                                answer = generate_answer(analysis_data)

                            st.markdown(answer)

                        except Exception as error:
                            st.error(str(error))

            except Exception as error:
                st.error(f"Finnhub Error: {error}")

        st.markdown("---")
        st.subheader("🌍 General Market News")

        if st.button("Load Latest Market News"):

            try:

                news = get_market_news()

                if not news:
                    st.info("No news returned.")

                for item in news[:10]:

                    st.markdown(
                        f"### {item.get('headline', 'Market News')}"
                    )

                    st.write(
                        item.get("summary", "No summary available.")
                    )

                    if item.get("url"):
                        st.markdown(
                            f"[Read Article]({item['url']})"
                        )

                    st.caption(
                        f"Source: {item.get('source', 'Unknown')}"
                    )

                    st.divider()

            except Exception as error:
                st.error(f"News Error: {error}")

        st.warning(
            "यह शैक्षिक stock information है। "
            "यह guaranteed prediction या खरीदने-बेचने की सलाह नहीं है।"
        )

# =========================================
# AI VISION
# =========================================

elif page == "AI Vision":

    st.header("👁️ AI Vision")

    uploaded_image = st.file_uploader(
        "Upload Image",
        type=["png", "jpg", "jpeg", "webp"]
    )

    question = st.text_input(
        "What should AI analyze?"
    )

    if uploaded_image:

        image = Image.open(uploaded_image)

        st.image(
            image,
            use_container_width=True
        )

        if st.button("Analyze Image"):

            try:

                answer = generate_answer([
                    question or "Describe this image.",
                    image
                ])

                st.markdown(answer)

            except Exception as error:
                st.error(str(error))

# =========================================
# PDF ASSISTANT
# =========================================

elif page == "PDF Assistant":

    st.header("📄 PDF Assistant")

    pdf_file = st.file_uploader(
        "Upload PDF",
        type=["pdf"]
    )

    question = st.text_input(
        "Ask about your PDF"
    )

    if pdf_file and st.button("Ask AI"):

        try:

            reader = PdfReader(pdf_file)

            pdf_text = "\n".join(
                page.extract_text() or ""
                for page in reader.pages
            )

            if not pdf_text.strip():
                st.warning("No readable text found.")

            else:

                answer = generate_answer(
                    "Answer from this PDF:\n"
                    + pdf_text[:40000]
                    + "\nQuestion: "
                    + question
                )

                st.markdown(answer)

        except Exception as error:
            st.error(str(error))

# =========================================
# VOICE STUDIO
# =========================================

elif page == "Voice Studio":

    st.header("🎙️ Voice Studio")

    st.info(
        "यहाँ recorded audio को AI तक भेज सकते हो। "
        "Continuous Live Voice अभी अलग integration माँगता है।"
    )

    audio = st.audio_input("Record your voice")

    if audio and st.button("Send to AI"):

        try:

            audio_part = types.Part.from_bytes(
                data=audio.getvalue(),
                mime_type=audio.type or "audio/wav"
            )

            answer = generate_answer([
                "Listen to the audio and respond to the user.",
                audio_part
            ])

            st.markdown(answer)

        except Exception as error:
            st.error(str(error))

# =========================================
# AI IMAGE
# =========================================

elif page == "AI Image":

    st.header("🎨 AI Image Studio")

    st.info(
        "Image generation service अभी connected नहीं है।"
    )

    prompt = st.text_area("Describe your image")

    if st.button("Improve Image Prompt") and prompt.strip():

        try:

            answer = generate_answer(
                "Create a detailed image-generation prompt for: "
                + prompt
            )

            st.markdown(answer)

        except Exception as error:
            st.error(str(error))

# =========================================
# AI VIDEO
# =========================================

elif page == "AI Video":

    st.header("🎬 AI Video Studio")

    st.info(
        "Video generation API अभी connected नहीं है।"
    )

    prompt = st.text_area("Describe your video")

    if st.button("Create Video Script") and prompt.strip():

        try:

            answer = generate_answer(
                "Create a scene-by-scene video script for: "
                + prompt
            )

            st.markdown(answer)

        except Exception as error:
            st.error(str(error))

# =========================================
# ABOUT
# =========================================

elif page == "About":

    st.header("🌍 About NEXTGEN AI")

    st.markdown("""
    ## NEXTGEN AI

    One Platform. Endless Possibilities.

    ### Features

    - AI Chat
    - Guest Mode
    - Sign Up and Login
    - Chat History
    - AI Vision
    - PDF Assistant
    - Voice Recording Input
    - Finnhub Stock Market Data
    - Gemini AI
    - Auto-Pilot Retry System

    ### Upcoming Integrations

    - Continuous Live Voice
    - AI Image Generation
    - AI Video Generation
    - Website Builder
    - App Builder
    - AI Creator
    - Coding School
    - Advanced Finance Dashboard
    """)

# =========================================
# FOOTER
# =========================================

st.markdown("---")

st.markdown("""
<div class="footer">
    NEXTGEN AI © 2026
    <br>
    Powered by Artificial Intelligence
</div>
""", unsafe_allow_html=True)
