
import os
import io
import re
import json
import time
import sqlite3
import requests
import html
from datetime import datetime, timedelta

import streamlit as st
import streamlit.components.v1 as components
from dotenv import load_dotenv

load_dotenv()

# ============================================================
# NEXTGEN AI — ULTIMATE AI WORKSPACE
# ============================================================

st.set_page_config(
    page_title="NEXTGEN AI",
    page_icon="✦",
    layout="wide",
    initial_sidebar_state="expanded"
)

# ============================================================
# CONFIGURATION
# ============================================================

GEMINI_KEY = os.getenv("GEMINI_API_KEY", "")
GROQ_KEY = os.getenv("GROQ_API_KEY", "")
FINNHUB_KEY = os.getenv("FINNHUB_API_KEY", "")

GEMINI_MODEL = os.getenv(
    "GEMINI_MODEL", "gemini-2.5-flash"
)

GROQ_MODEL = os.getenv(
    "GROQ_MODEL", "llama-3.3-70b-versatile"
)

DB_PATH = "nextgen_ai.db"

# ============================================================
# DATABASE
# ============================================================

def db():
    return sqlite3.connect(DB_PATH)

def init_db():
    with db() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS chats(
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT,
                created_at TEXT
            )
        """)

        conn.execute("""
            CREATE TABLE IF NOT EXISTS messages(
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                chat_id INTEGER,
                role TEXT,
                content TEXT,
                created_at TEXT
            )
        """)

def create_chat():
    with db() as conn:
        cur = conn.execute(
            "INSERT INTO chats(title,created_at) VALUES(?,?)",
            ("New Chat", datetime.now().isoformat())
        )
        return cur.lastrowid

def get_chats():
    with db() as conn:
        return conn.execute(
            "SELECT id,title FROM chats ORDER BY id DESC"
        ).fetchall()

def save_message(chat_id, role, content):
    with db() as conn:
        conn.execute("""
            INSERT INTO messages(chat_id,role,content,created_at)
            VALUES(?,?,?,?)
        """, (
            chat_id,
            role,
            content,
            datetime.now().isoformat()
        ))

def get_messages(chat_id):
    with db() as conn:
        rows = conn.execute("""
            SELECT role,content FROM messages
            WHERE chat_id=? ORDER BY id ASC
        """, (chat_id,)).fetchall()

    return [
        {"role": role, "content": content}
        for role, content in rows
    ]

def update_title(chat_id, title):
    with db() as conn:
        conn.execute(
            "UPDATE chats SET title=? WHERE id=?",
            (title[:45], chat_id)
        )

def delete_chat(chat_id):
    with db() as conn:
        conn.execute(
            "DELETE FROM messages WHERE chat_id=?",
            (chat_id,)
        )
        conn.execute(
            "DELETE FROM chats WHERE id=?",
            (chat_id,)
        )

init_db()

# ============================================================
# SESSION STATE
# ============================================================

defaults = {
    "chat_id": None,
    "messages": [],
    "page": "AI Chat",
    "stock_result": None,
    "analysis_result": None,
    "vision_result": None,
    "pdf_result": None,
    "studio_prompt": "",
    "last_stock_symbol": "AAPL",
    "watchlist": ["AAPL", "MSFT", "NVDA", "GOOGL"],
    "learning_progress": [],
    "language": "Auto"
}

for key, value in defaults.items():
    if key not in st.session_state:
        st.session_state[key] = value

if st.session_state.chat_id is None:
    st.session_state.chat_id = create_chat()

def new_chat():
    st.session_state.chat_id = create_chat()
    st.session_state.messages = []
    st.session_state.page = "AI Chat"

def open_chat(cid):
    st.session_state.chat_id = cid
    st.session_state.messages = get_messages(cid)
    st.session_state.page = "AI Chat"

# ============================================================
# PREMIUM DESIGN SYSTEM
# ============================================================

st.markdown("""
<style>

:root {
    --bg: #090b10;
    --panel: #111722;
    --panel2: #171e2b;
    --border: #283246;
    --accent: #927cff;
    --muted: #929bad;
    --white: #ffffff;
}

#MainMenu, footer, header {
    visibility: hidden;
}

.stApp {
    background: var(--bg);
    color: #FFFFFF !important;
}

.stMarkdown,
.stMarkdown *,
[data-testid="stMarkdownContainer"],
[data-testid="stMarkdownContainer"] *,
[data-testid="stChatMessage"],
[data-testid="stChatMessage"] * {
    color: #FFFFFF !important;
}

h1, h2, h3, h4, h5, h6 {
    color: #FFFFFF !important;
    font-weight: 700 !important;
}

p, li, label, span {
    color: #FFFFFF;
}

.main .block-container {
    max-width: 1150px;
    padding-top: 2rem;
    padding-bottom: 5rem;
}

[data-testid="stSidebar"] {
    background: #10141e;
    border-right: 1px solid #283246;
}

[data-testid="stSidebar"] * {
    color: #FFFFFF;
}

.brand {
    font-size: 27px;
    font-weight: 900;
    letter-spacing: 1px;
    color: #FFFFFF;
}

.brand span {
    color: #927cff !important;
}

.subtitle {
    color: #929bad !important;
    font-size: 13px;
}

.stButton button {
    background: #171e2b;
    color: #FFFFFF !important;
    border: 1px solid #30394e;
    border-radius: 12px;
    min-height: 42px;
    transition: .2s;
}

.stButton button:hover {
    background: #242b3e;
    border-color: #927cff;
}

[data-testid="stChatInput"] {
    background: #151b28;
    border: 1px solid #514774;
    border-radius: 18px;
}

[data-testid="stChatInput"] textarea {
    color: #FFFFFF !important;
    -webkit-text-fill-color: #FFFFFF !important;
}

[data-testid="stChatInput"] textarea::placeholder {
    color: #a3a9b6 !important;
}

.stTextInput input,
.stTextArea textarea {
    color: #FFFFFF !important;
    -webkit-text-fill-color: #FFFFFF !important;
    background: #141a26;
}

.stSelectbox div,
.stMultiSelect div {
    color: #FFFFFF;
}

.stTabs [data-baseweb="tab"] {
    color: #FFFFFF !important;
}

.stProgress > div > div {
    background: #927cff;
}

section[data-testid="stFileUploader"] {
    background: #121927;
    border: 1px solid #283246;
    border-radius: 14px;
    padding: 12px;
}

[data-testid="stMetric"] {
    background: #141b28;
    border: 1px solid #283246;
    padding: 15px;
    border-radius: 14px;
}

[data-testid="stMetricValue"] {
    color: #FFFFFF !important;
}

[data-testid="stAlert"] * {
    color: #FFFFFF !important;
}

div[data-testid="stExpander"] {
    background: #111722;
    border: 1px solid #283246;
    border-radius: 12px;
}

hr {
    border-color: #283246;
}

.card {
    background: #111722;
    border: 1px solid #283246;
    padding: 18px;
    border-radius: 16px;
    margin: 10px 0;
}

.user-card {
    background: #1b2030;
    border: 1px solid #343c55;
    padding: 16px;
    border-radius: 17px;
    margin: 12px 0;
    color: white;
}

.ai-card {
    background: #111925;
    border: 1px solid #303d52;
    padding: 17px;
    border-radius: 17px;
    margin: 12px 0;
    color: white;
}

.small-muted {
    color: #929bad !important;
    font-size: 12px;
}

.accent {
    color: #a18cff !important;
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
            "max_tokens": 4000
        },
        timeout=90
    )

    response.raise_for_status()
    data = response.json()

    return data["choices"][0]["message"]["content"]

def gemini_request(messages):
    if not GEMINI_KEY:
        raise Exception("Gemini API key missing")

    from google import genai

    client = genai.Client(api_key=GEMINI_KEY)

    system_text = ""
    contents = []

    for msg in messages:
        if msg["role"] == "system":
            system_text += msg["content"] + "\n"
            continue

        contents.append({
            "role": (
                "model" if msg["role"] == "assistant"
                else "user"
            ),
            "parts": [{"text": msg["content"]}]
        })

    response = client.models.generate_content(
        model=GEMINI_MODEL,
        contents=contents,
        config={
            "system_instruction": system_text
        } if system_text else None
    )

    if not response.text:
        raise Exception("Gemini returned empty response")

    return response.text

def ask_ai(messages):
    errors = []

    if GROQ_KEY:
        try:
            return groq_request(messages)
        except Exception as exc:
            errors.append("Groq: " + str(exc)[:250])

    if GEMINI_KEY:
        try:
            return gemini_request(messages)
        except Exception as exc:
            errors.append("Gemini: " + str(exc)[:250])

    if not errors:
        raise Exception(
            "Add GROQ_API_KEY or GEMINI_API_KEY to .env"
        )

    raise Exception(" | ".join(errors))

def ai_system_prompt():
    return """
You are NEXTGEN AI, a capable general-purpose assistant.

Rules:
- Answer in the user's language.
- Be helpful, accurate and clear.
- Explain complicated concepts step by step.
- Use headings and examples when useful.
- Never invent live data.
- Explain uncertainty.
- For financial topics, teach concepts and risks.
- Never promise investment profits.
- For image requests, create detailed visual prompts
  when direct image generation is unavailable.
- For coding, provide complete and correctly formatted code.
"""

# ============================================================
# FINNHUB MARKET DATA
# ============================================================

def finnhub_get(endpoint, params):
    if not FINNHUB_KEY:
        raise Exception("FINNHUB_API_KEY missing")

    params["token"] = FINNHUB_KEY

    response = requests.get(
        "https://finnhub.io/api/v1/" + endpoint,
        params=params,
        timeout=25
    )

    response.raise_for_status()
    return response.json()

def get_stock_quote(symbol):
    data = finnhub_get(
        "quote",
        {"symbol": symbol.upper()}
    )

    if not data or not data.get("c"):
        raise Exception(
            "Quote unavailable. Check the symbol or market."
        )

    return data

def get_stock_profile(symbol):
    return finnhub_get(
        "stock/profile2",
        {"symbol": symbol.upper()}
    )

def get_stock_news(symbol):
    end = datetime.now().date()
    start = end - timedelta(days=7)

    return finnhub_get(
        "company-news",
        {
            "symbol": symbol.upper(),
            "from": start.isoformat(),
            "to": end.isoformat()
        }
    )

def get_stock_candles(symbol, resolution="D", days=90):
    end = int(time.time())
    start = end - days * 86400

    data = finnhub_get(
        "stock/candle",
        {
            "symbol": symbol.upper(),
            "resolution": resolution,
            "from": start,
            "to": end
        }
    )

    if data.get("s") != "ok":
        raise Exception("Historical chart data unavailable")

    return data

def money(value):
    return f"${value:,.2f}"

# ============================================================
# STOCK CHARTS
# ============================================================

def show_stock_chart(symbol, days=90):
    data = get_stock_candles(symbol, days=days)

    import pandas as pd
    import plotly.graph_objects as go

    df = pd.DataFrame({
        "Date": pd.to_datetime(
            data["t"], unit="s"
        ),
        "Open": data["o"],
        "High": data["h"],
        "Low": data["l"],
        "Close": data["c"],
        "Volume": data["v"]
    })

    fig = go.Figure()

    fig.add_trace(go.Candlestick(
        x=df["Date"],
        open=df["Open"],
        high=df["High"],
        low=df["Low"],
        close=df["Close"],
        name=symbol
    ))

    fig.update_layout(
        title=f"{symbol} Price History",
        template="plotly_dark",
        paper_bgcolor="#111722",
        plot_bgcolor="#111722",
        font=dict(color="white"),
        height=450,
        xaxis_rangeslider_visible=False
    )

    st.plotly_chart(
        fig,
        use_container_width=True
    )

    volume_fig = go.Figure()

    volume_fig.add_trace(go.Bar(
        x=df["Date"],
        y=df["Volume"],
        name="Volume"
    ))

    volume_fig.update_layout(
        title="Trading Volume",
        template="plotly_dark",
        paper_bgcolor="#111722",
        plot_bgcolor="#111722",
        font=dict(color="white"),
        height=260
    )

    st.plotly_chart(
        volume_fig,
        use_container_width=True
    )

    return df

# ============================================================
# IMAGE VISION
# ============================================================

def analyze_image(uploaded_file, question):
    if not GEMINI_KEY:
        raise Exception(
            "Gemini API key is required for image analysis"
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
        contents=[
            question,
            image_part
        ]
    )

    return response.text

# ============================================================
# PDF ENGINE
# ============================================================

def extract_pdf(uploaded_file):
    from pypdf import PdfReader

    reader = PdfReader(uploaded_file)

    pages = []

    for number, page in enumerate(reader.pages, 1):
        content = page.extract_text() or ""

        if content.strip():
            pages.append(
                f"\nPAGE {number}\n{content}"
            )

    return "\n".join(pages)[:40000]

# ============================================================
# READ ALOUD
# ============================================================

def read_aloud(content, key):
    safe = json.dumps(content)

    components.html(
        f"""
        <button id="{key}" style="
            background:#20283a;
            border:1px solid #454f69;
            color:white;
            padding:9px 15px;
            border-radius:10px;
            cursor:pointer;
        ">🔊 Read Aloud</button>

        <script>
        const button = document.getElementById("{key}");
        const text = {safe};

        button.onclick = () => {{
            if (!window.speechSynthesis) {{
                button.innerText = "Speech unavailable";
                return;
            }}

            window.speechSynthesis.cancel();

            const utterance = new SpeechSynthesisUtterance(text);
            utterance.lang = "en-IN";
            utterance.rate = 1;

            utterance.onend = () => {{
                button.innerText = "🔊 Read Aloud";
            }};

            button.innerText = "▶ Speaking...";
            window.speechSynthesis.speak(utterance);
        }};
        </script>
        """,
        height=48
    )

# ============================================================
# CREATIVE STUDIO DATA
# ============================================================

STYLES = {
    "Anime": "High quality anime illustration, expressive eyes, detailed line art",
    "Cartoon": "Colorful professional cartoon illustration, smooth outlines",
    "3D Animation": "Beautiful high quality 3D animated render",
    "Cinematic": "Cinematic composition, dramatic lighting, film color grading",
    "Realistic": "Photorealistic details, natural lighting, realistic textures",
    "Fantasy": "Magical fantasy world, atmospheric lighting, imaginative scenery",
    "Cyberpunk": "Futuristic neon cyberpunk atmosphere",
    "Watercolor": "Traditional watercolor painting, artistic brush texture",
    "Oil Painting": "Detailed traditional oil painting",
    "Comic Book": "Dynamic comic book illustration, bold ink outlines",
    "Pixel Art": "Detailed retro pixel art",
    "Minimalist": "Clean minimalist composition",
    "Studio Portrait": "Professional studio portrait, soft lighting",
    "Architectural": "Professional architectural visualization",
    "Product Render": "Premium commercial product photography",
    "Clay 3D": "Soft clay 3D character design",
    "Paper Cut": "Layered paper cut illustration",
    "Vintage": "Vintage artistic film aesthetic"
}

ASPECTS = [
    "1:1 Square",
    "16:9 Landscape",
    "9:16 Portrait",
    "4:5 Portrait",
    "3:2 Landscape"
]

def create_image_prompt(
    subject,
    style,
    aspect,
    lighting,
    background,
    details
):
    return f"""
Create an original visual artwork.

SUBJECT:
{subject}

ART STYLE:
{STYLES[style]}

ASPECT RATIO:
{aspect}

LIGHTING:
{lighting}

BACKGROUND:
{background}

ADDITIONAL DETAILS:
{details}

QUALITY:
High detail, professional composition,
beautiful color harmony, clear focal subject,
careful visual balance, polished final artwork.

IMPORTANT:
Keep the main subject clearly visible.
Avoid unwanted text, watermarks and logos.
"""

# ============================================================
# SIDEBAR NAVIGATION
# ============================================================

PAGES = {
    "AI Chat": "✦ AI Chat",
    "Market Dashboard": "🌐 Market Dashboard",
    "Stock Learning": "🎓 Stock Learning",
    "Stock Analysis": "🔍 Stock Analysis",
    "Watchlist": "☆ Watchlist",
    "Vision": "👁 Vision",
    "Creative Studio": "🎨 Creative Studio",
    "PDF Assistant": "📄 PDF Assistant",
    "AI Tools": "⚡ AI Tools",
    "Settings": "⚙ Settings"
}

with st.sidebar:

    st.markdown(
        '<div class="brand">✦ NEXTGEN <span>AI</span></div>',
        unsafe_allow_html=True
    )

    st.caption("Your intelligent AI workspace")

    st.divider()

    if st.button("＋ New Chat", use_container_width=True):
        new_chat()
        st.rerun()

    st.markdown("### WORKSPACE")

    for page_name, label in PAGES.items():
        if st.button(
            label,
            key="nav_" + page_name,
            use_container_width=True
        ):
            st.session_state.page = page_name
            st.rerun()

    st.divider()

    st.markdown("### CHAT HISTORY")

    for cid, title in get_chats():
        c1, c2 = st.columns([4, 1])

        with c1:
            if st.button(
                "◉ " + (title or "New Chat"),
                key=f"open_{cid}",
                use_container_width=True
            ):
                open_chat(cid)
                st.rerun()

        with c2:
            if st.button(
                "×",
                key=f"delete_{cid}"
            ):
                delete_chat(cid)

                if st.session_state.chat_id == cid:
                    new_chat()

                st.rerun()

    st.divider()

    st.caption("NEXTGEN AI • Ultimate Workspace")

# ============================================================
# PAGE ROUTER
# ============================================================

page = st.session_state.page

# ============================================================
# 1. AI CHAT
# ============================================================

if page == "AI Chat":

    st.title("✦ NEXTGEN AI")

    st.caption(
        "Ask anything. Explore ideas. Build something amazing."
    )

    st.divider()

    for i, message in enumerate(st.session_state.messages):

        if message["role"] == "user":

            st.markdown(
                f"""
                <div class="user-card">
                    <b>YOU</b><br><br>
                    {html.escape(message["content"])}
                </div>
                """,
                unsafe_allow_html=True
            )

        else:

            st.markdown(
                '<div class="ai-card"><b>✦ NEXTGEN AI</b></div>',
                unsafe_allow_html=True
            )

            st.markdown(message["content"])

            read_aloud(
                message["content"],
                f"chat_read_{st.session_state.chat_id}_{i}"
            )

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
            update_title(
                st.session_state.chat_id,
                prompt
            )

        history = [
            {
                "role": "system",
                "content": ai_system_prompt()
            }
        ]

        history.extend(
            st.session_state.messages[-25:]
        )

        with st.spinner("NEXTGEN AI is thinking..."):

            try:
                answer = ask_ai(history)

            except Exception as exc:
                answer = f"AI Error: {exc}"

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
# 2. GLOBAL MARKET DASHBOARD
# ============================================================

elif page == "Market Dashboard":

    st.title("🌐 Global Market Dashboard")

    st.caption("Market information powered by Finnhub")

    symbols = [
        ("AAPL", "Apple"),
        ("MSFT", "Microsoft"),
        ("NVDA", "NVIDIA"),
        ("GOOGL", "Alphabet")
    ]

    if not FINNHUB_KEY:
        st.warning("Add FINNHUB_API_KEY to enable market data.")

    else:

        columns = st.columns(4)

        for i, (symbol, company) in enumerate(symbols):

            with columns[i]:

                try:
                    quote = get_stock_quote(symbol)

                    st.metric(
                        company,
                        money(quote["c"]),
                        f"{quote['dp']:.2f}%"
                    )

                except Exception:
                    st.metric(company, "Unavailable")

    st.divider()

    st.subheader("Explore a Market")

    market = st.selectbox(
        "Market",
        [
            "NASDAQ",
            "NYSE",
            "NSE India",
            "BSE India",
            "S&P 500",
            "Global Markets"
        ]
    )

    st.info(
        f"Selected market: {market}. "
        "Available symbols and coverage depend on Finnhub."
    )

    st.subheader("Market Learning")

    st.markdown("""
    - **Index:** A group of securities used to represent a market.
    - **Market Capitalization:** Company value based on its shares.
    - **Volume:** Number of shares traded.
    - **Volatility:** How much a price fluctuates.
    - **Liquidity:** How easily an asset can be traded.
    """)

    st.caption(
        "Quotes can be delayed or unavailable. "
        "This dashboard is educational."
    )

# ============================================================
# 3. STOCK LEARNING CENTER
# ============================================================

elif page == "Stock Learning":

    st.title("🎓 Stock Market Learning Center")

    st.caption(
        "Learn the stock market from beginner to advanced."
    )

    lessons = {
        "01 • Introduction to Stock Market": """
        A stock represents a unit of ownership in a company.

        Important concepts:

        1. Shares: Units of ownership.
        2. Stock Exchange: A marketplace for securities.
        3. Investor: A person who owns investments.
        4. Broker: A regulated intermediary.
        5. Index: A measure tracking a group of securities.

        Learning objective:
        Understand what shares and exchanges mean.
        """,

        "02 • Primary and Secondary Markets": """
        Primary Market:
        Companies issue securities to raise capital.

        Secondary Market:
        Existing securities are traded between participants.

        IPO:
        Initial Public Offering.

        Understand why companies issue shares
        and how exchange trading works.
        """,

        "03 • Bull and Bear Markets": """
        Bull Market:
        A period generally associated with rising prices.

        Bear Market:
        A period generally associated with falling prices.

        Learn about market sentiment,
        economic cycles and uncertainty.
        """,

        "04 • Candlestick Charts": """
        A candlestick displays four important values:

        Open: Starting price.
        High: Highest price.
        Low: Lowest price.
        Close: Ending price.

        Candlesticks help visualize price movement.
        They do not guarantee future direction.
        """,

        "05 • Volume and Liquidity": """
        Volume measures how much trading occurred.

        Liquidity describes how easily an asset
        can be bought or sold without greatly
        affecting its price.

        Learn the difference between both concepts.
        """,

        "06 • Fundamental Analysis": """
        Fundamental analysis studies a business.

        Important metrics:

        Revenue
        Net income
        Earnings per share
        P/E ratio
        Debt
        Cash flow
        Return on equity

        No single metric is enough to judge a company.
        """,

        "07 • Technical Analysis": """
        Technical analysis studies price and volume data.

        Topics:

        Support and resistance
        Moving averages
        RSI
        MACD
        Trend lines
        Trading volume

        Indicators are not guaranteed predictions.
        """,

        "08 • Risk Management": """
        Risk management means understanding
        what can go wrong.

        Learn about:

        Diversification
        Volatility
        Liquidity risk
        Market risk
        Concentration risk
        Time horizon

        Never assume a return is guaranteed.
        """,

        "09 • Mutual Funds and ETFs": """
        Mutual funds and ETFs can hold
        collections of financial assets.

        Learn about:
        - Expense ratios
        - Diversification
        - Tracking indexes
        - Fund objectives
        - Risks and fees
        """,

        "10 • Advanced Financial Concepts": """
        Advanced concepts:

        P/E and PEG ratios
        Discounted cash flow
        Free cash flow
        Portfolio diversification
        Interest rate sensitivity
        Macroeconomic indicators

        Study assumptions and limitations
        before interpreting financial models.
        """
    }

    selected_lesson = st.selectbox(
        "Choose your lesson",
        list(lessons.keys())
    )

    st.markdown("### " + selected_lesson)

    st.markdown(
        '<div class="card">' +
        lessons[selected_lesson].replace("\n", "<br>") +
        '</div>',
        unsafe_allow_html=True
    )

    if st.button("Mark Lesson Completed"):
        if selected_lesson not in st.session_state.learning_progress:
            st.session_state.learning_progress.append(
                selected_lesson
            )

    total = len(lessons)
    completed = len(st.session_state.learning_progress)

    st.subheader("Your Learning Progress")

    st.progress(completed / total)

    st.write(f"{completed} of {total} lessons completed")

    st.divider()

    st.subheader("🧠 Test Your Knowledge")

    questions = [
        (
            "What does a stock represent?",
            [
                "Ownership in a company",
                "A bank loan",
                "A currency",
                "A tax"
            ],
            0
        ),
        (
            "What does trading volume measure?",
            [
                "Company profit",
                "Number of units traded",
                "Company age",
                "Interest rate"
            ],
            1
        ),
        (
            "What does P/E stand for?",
            [
                "Price to Earnings",
                "Profit to Expense",
                "Portfolio Estimate",
                "Price to Exchange"
            ],
            0
        ),
        (
            "What does diversification help manage?",
            [
                "All market risk",
                "Concentration risk",
                "All losses",
                "All uncertainty"
            ],
            1
        )
    ]

    question, options, correct = questions[
        st.selectbox(
            "Select a question",
            range(len(questions)),
            format_func=lambda x: f"Question {x + 1}"
        )
    ]

    selected_answer = st.radio(
        question,
        options,
        key="learning_quiz_answer"
    )

    if st.button("Check Answer"):
        if options.index(selected_answer) == correct:
            st.success("Correct! Good understanding.")
        else:
            st.info(
                "Not quite. Review the lesson and try again."
            )

    st.divider()

    st.subheader("Ask AI to Teach You")

    learning_question = st.text_input(
        "What do you want to learn about the stock market?"
    )

    if st.button("Explain This Topic") and learning_question:

        with st.spinner("Preparing your lesson..."):

            try:
                answer = ask_ai([
                    {
                        "role": "system",
                        "content": (
                            "You are a patient stock market teacher. "
                            "Teach financial concepts step by step. "
                            "Explain definitions, examples, risks "
                            "and limitations. Do not provide "
                            "personalized buy or sell instructions."
                        )
                    },
                    {
                        "role": "user",
                        "content": learning_question
                    }
                ])

                st.markdown(answer)

            except Exception as exc:
                st.error(str(exc))

# ============================================================
# 4. STOCK ANALYSIS
# ============================================================

elif page == "Stock Analysis":

    st.title("🔍 AI Stock Analysis")

    st.caption(
        "Company research, market data, charts and educational AI analysis."
    )

    symbol = st.text_input(
        "Enter Stock Symbol",
        value=st.session_state.last_stock_symbol
    ).strip().upper()

    period = st.selectbox(
        "Chart Period",
        ["30 Days", "90 Days", "180 Days", "365 Days"]
    )

    days = {
        "30 Days": 30,
        "90 Days": 90,
        "180 Days": 180,
        "365 Days": 365
    }[period]

    if st.button("Analyze Company", type="primary"):

        try:

            quote = get_stock_quote(symbol)
            profile = get_stock_profile(symbol)

            st.session_state.last_stock_symbol = symbol

            st.session_state.stock_result = {
                "symbol": symbol,
                "quote": quote,
                "profile": profile
            }

            st.session_state.analysis_result = None

        except Exception as exc:
            st.error(f"Market data error: {exc}")

    result = st.session_state.stock_result

    if result and result["symbol"] == symbol:

        quote = result["quote"]
        profile = result["profile"]

        st.divider()

        st.subheader(
            profile.get("name") or symbol
        )

        c1, c2, c3, c4 = st.columns(4)

        c1.metric(
            "Current Price",
            money(quote["c"])
        )

        c2.metric(
            "Price Change",
            f"{quote['d']:.2f}"
        )

        c3.metric(
            "Change %",
            f"{quote['dp']:.2f}%"
        )

        c4.metric(
            "Previous Close",
            money(quote["pc"])
        )

        st.markdown("### Company Information")

        st.write(
            "Industry:",
            profile.get("finnhubIndustry", "Unavailable")
        )

        st.write(
            "Country:",
            profile.get("country", "Unavailable")
        )

        st.write(
            "Exchange:",
            profile.get("exchange", "Unavailable")
        )

        st.write(
            "Website:",
            profile.get("weburl", "Unavailable")
        )

        st.divider()

        st.markdown("### 📊 Historical Price Chart")

        try:
            show_stock_chart(symbol, days)

        except Exception as exc:
            st.warning(f"Chart unavailable: {exc}")

        st.divider()

        st.markdown("### 📰 Recent Company News")

        try:
            news = get_stock_news(symbol)

            for item in news[:7]:

                with st.expander(
                    item.get("headline", "News")
                ):

                    st.write(item.get("summary", ""))

                    if item.get("url"):
                        st.markdown(
                            f"[Read Original News]({item['url']})"
                        )

        except Exception as exc:
            st.info(f"News unavailable: {exc}")

        st.divider()

        st.markdown("### ✦ AI Educational Analysis")

        if st.button("Generate AI Analysis"):

            try:

                news_text = "\n".join([
                    item.get("headline", "")
                    for item in get_stock_news(symbol)[:5]
                ])

                analysis_prompt = f"""
                Prepare an educational company analysis.

                Symbol: {symbol}
                Company: {profile.get('name')}
                Industry: {profile.get('finnhubIndustry')}
                Country: {profile.get('country')}

                Current price: {quote['c']}
                Change: {quote['d']}
                Percentage change: {quote['dp']}
                Previous close: {quote['pc']}

                Recent news headlines:
                {news_text}

                Explain:

                1. Company overview
                2. Business model
                3. Market movement
                4. Fundamental factors to research
                5. Financial metrics to investigate
                6. Potential business risks
                7. Industry conditions
                8. Important questions for further research

                Separate confirmed data from interpretation.
                Do not invent missing financial metrics.
                Do not issue personalized buy or sell instructions.
                """

                with st.spinner("AI is researching the company..."):

                    answer = ask_ai([
                        {
                            "role": "system",
                            "content": ai_system_prompt()
                        },
                        {
                            "role": "user",
                            "content": analysis_prompt
                        }
                    ])

                st.session_state.analysis_result = answer

            except Exception as exc:
                st.error(str(exc))

        if st.session_state.analysis_result:
            st.markdown(
                st.session_state.analysis_result
            )

            read_aloud(
                st.session_state.analysis_result,
                "stock_analysis_read"
            )

    st.caption(
        "Educational research only. Market prices may be delayed. "
        "AI analysis can be incomplete or incorrect."
    )

# ============================================================
# 5. WATCHLIST
# ============================================================

elif page == "Watchlist":

    st.title("☆ My Watchlist")

    st.caption("Keep track of selected market symbols.")

    new_symbol = st.text_input(
        "Add a stock symbol"
    ).strip().upper()

    if st.button("＋ Add to Watchlist"):

        if new_symbol and new_symbol not in st.session_state.watchlist:
            st.session_state.watchlist.append(new_symbol)

    for symbol in st.session_state.watchlist:

        c1, c2, c3 = st.columns([2, 2, 1])

        c1.write(f"**{symbol}**")

        try:
            quote = get_stock_quote(symbol)

            c2.metric(
                "Price",
                money(quote["c"]),
                f"{quote['dp']:.2f}%"
            )

        except Exception:
            c2.write("Data unavailable")

        if c3.button("Remove", key="remove_" + symbol):
            st.session_state.watchlist.remove(symbol)
            st.rerun()

# ============================================================
# 6. VISION
# ============================================================

elif page == "Vision":

    st.title("👁 NEXTGEN Vision")

    st.caption(
        "Upload a picture and let AI understand its contents."
    )

    image = st.file_uploader(
        "＋ Upload Image",
        type=["png", "jpg", "jpeg", "webp"]
    )

    question = st.text_area(
        "Ask a question about the image",
        placeholder="Describe this image..."
    )

    if image:

        st.image(
            image,
            caption="Uploaded Image",
            use_container_width=True
        )

        if st.button("✦ Analyze Image", type="primary"):

            try:

                with st.spinner("Vision AI is analyzing..."):

                    answer = analyze_image(
                        image,
                        question or "Describe this image in detail."
                    )

                st.session_state.vision_result = answer

            except Exception as exc:
                st.error(str(exc))

    if st.session_state.vision_result:

        st.markdown("### Vision Result")

        st.markdown(
            st.session_state.vision_result
        )

        read_aloud(
            st.session_state.vision_result,
            "vision_read"
        )

# ============================================================
# 7. CREATIVE STUDIO
# ============================================================

elif page == "Creative Studio":

    st.title("🎨 NEXTGEN Creative Studio")

    st.caption(
        "Create professional visual concepts and image prompts."
    )

    st.markdown("### Create Your Visual")

    subject = st.text_area(
        "Describe what you want to create",
        placeholder=(
            "Example: A futuristic royal lion character "
            "wearing a black suit..."
        )
    )

    col1, col2 = st.columns(2)

    with col1:

        style = st.selectbox(
            "Art Style",
            list(STYLES.keys())
        )

        aspect = st.selectbox(
            "Aspect Ratio",
            ASPECTS
        )

        lighting = st.selectbox(
            "Lighting",
            [
                "Cinematic lighting",
                "Soft natural lighting",
                "Neon lighting",
                "Golden hour",
                "Studio lighting",
                "Dark dramatic lighting",
                "Dreamy lighting"
            ]
        )

    with col2:

        background = st.selectbox(
            "Background",
            [
                "Detailed cinematic background",
                "Minimal clean background",
                "Futuristic city",
                "Nature landscape",
                "Royal palace",
                "Dark studio",
                "Fantasy world",
                "Custom background"
            ]
        )

        details = st.text_area(
            "Extra Details",
            placeholder="Colors, clothes, mood, camera angle..."
        )

    st.markdown("### Available Styles")

    st.write(
        ", ".join(STYLES.keys())
    )

    if st.button("✦ Generate Creative Prompt", type="primary"):

        if not subject.strip():
            st.warning("First describe your visual idea.")

        else:

            result = create_image_prompt(
                subject,
                style,
                aspect,
                lighting,
                background,
                details
            )

            st.session_state.studio_prompt = result

    if st.session_state.studio_prompt:

        st.divider()

        st.markdown("### Your Generated Prompt")

        st.code(
            st.session_state.studio_prompt,
            language="text"
        )

        if st.button("Copy Prompt"):
            st.code(st.session_state.studio_prompt)

        st.info(
            "This is an image-generation prompt, not a rendered image. "
            "Connect an image-generation provider to generate the actual artwork."
        )

    st.divider()

    st.markdown("### ✦ AI Creative Assistant")

    creative_question = st.text_input(
        "Ask AI for creative ideas"
    )

    if st.button("Get Creative Ideas") and creative_question:

        try:

            answer = ask_ai([
                {
                    "role": "system",
                    "content": (
                        "You are a professional visual creative director. "
                        "Suggest detailed original concepts, composition, "
                        "lighting, color palettes and art direction."
                    )
                },
                {
                    "role": "user",
                    "content": creative_question
                }
            ])

            st.markdown(answer)

        except Exception as exc:
            st.error(str(exc))

# ============================================================
# 8. PDF ASSISTANT
# ============================================================

elif page == "PDF Assistant":

    st.title("📄 NEXTGEN PDF Assistant")

    st.caption(
        "Read, summarize and understand your documents."
    )

    pdf = st.file_uploader(
        "Upload PDF Document",
        type=["pdf"]
    )

    question = st.text_area(
        "What do you want to know about this PDF?",
        placeholder="Summarize this document..."
    )

    if pdf and st.button("Analyze PDF", type="primary"):

        try:

            with st.spinner("Reading PDF..."):

                document = extract_pdf(pdf)

                if not document.strip():
                    raise Exception(
                        "No extractable text found in this PDF."
                    )

                answer = ask_ai([
                    {
                        "role": "system",
                        "content": (
                            "You are a document analysis assistant. "
                            "Base answers on the supplied PDF text. "
                            "Mention when information is missing."
                        )
                    },
                    {
                        "role": "user",
                        "content": (
                            f"Question: {question or 'Summarize the PDF.'}"
                            f"\n\nDOCUMENT:\n{document}"
                        )
                    }
                ])

            st.session_state.pdf_result = answer

        except Exception as exc:
            st.error(str(exc))

    if st.session_state.pdf_result:

        st.markdown("### PDF Analysis")

        st.markdown(
            st.session_state.pdf_result
        )

        read_aloud(
            st.session_state.pdf_result,
            "pdf_read"
        )

# ============================================================
# 9. AI TOOLS CENTER
# ============================================================

elif page == "AI Tools":

    st.title("⚡ AI Tools Center")

    st.caption(
        "Writing, coding, translation and productivity."
    )

    tool = st.selectbox(
        "Choose an AI Tool",
        [
            "AI Writing Assistant",
            "Code Assistant",
            "Text Summarizer",
            "Translator",
            "Grammar Improver",
            "Study Assistant",
            "Idea Generator",
            "Email Writer",
            "Explain Like a Teacher",
            "Research Assistant"
        ]
    )

    user_input = st.text_area(
        "Enter your text or instructions",
        height=180
    )

    if st.button("✦ Run AI Tool", type="primary"):

        if not user_input.strip():
            st.warning("Enter something first.")

        else:

            instructions = {
                "AI Writing Assistant":
                    "Improve and create professional writing.",
                "Code Assistant":
                    "Explain, debug or write code. Give complete code.",
                "Text Summarizer":
                    "Summarize the supplied text accurately.",
                "Translator":
                    "Translate the text. Preserve its meaning.",
                "Grammar Improver":
                    "Correct grammar and explain important corrections.",
                "Study Assistant":
                    "Teach the topic step by step with examples.",
                "Idea Generator":
                    "Generate original creative ideas.",
                "Email Writer":
                    "Write a clear and professional email.",
                "Explain Like a Teacher":
                    "Explain simply with examples and steps.",
                "Research Assistant":
                    "Create a structured research overview and identify uncertainty."
            }

            try:

                with st.spinner("AI tool is working..."):

                    answer = ask_ai([
                        {
                            "role": "system",
                            "content": (
                                instructions[tool] +
                                " Be accurate and use the user's language."
                            )
                        },
                        {
                            "role": "user",
                            "content": user_input
                        }
                    ])

                st.markdown("### Result")

                st.markdown(answer)

                read_aloud(answer, "tool_read")

            except Exception as exc:
                st.error(str(exc))

# ============================================================
# 10. SETTINGS
# ============================================================

elif page == "Settings":

    st.title("⚙ NEXTGEN AI Settings")

    st.caption("Workspace and API configuration.")

    st.subheader("AI Provider Status")

    providers = [
        ("Groq", GROQ_KEY),
        ("Gemini", GEMINI_KEY),
        ("Finnhub", FINNHUB_KEY)
    ]

    for name, key in providers:

        if key:
            st.success(f"{name}: API key detected")
        else:
            st.warning(f"{name}: API key missing")

    st.divider()

    st.subheader("Model Configuration")

    st.write("Groq Model:", GROQ_MODEL)
    st.write("Gemini Model:", GEMINI_MODEL)

    st.divider()

    st.subheader("Workspace Information")

    st.write("Application: NEXTGEN AI")
    st.write("Version: 2.0")
    st.write("Database: SQLite")
    st.write("Current Chat ID:", st.session_state.chat_id)

    st.divider()

    st.subheader("Feature Status")

    features = {
        "AI Chat": "Implemented",
        "Chat History": "Implemented",
        "Gemini Integration": "Implemented",
        "Groq Integration": "Implemented",
        "Finnhub Quotes": "Implemented",
        "Historical Charts": "Implemented",
        "Stock Learning": "Implemented",
        "AI Stock Analysis": "Implemented",
        "Vision Analysis": "Implemented",
        "PDF Text Analysis": "Implemented",
        "Creative Prompt Studio": "Implemented",
        "Read Aloud": "Browser Speech",
        "Actual Image Generation": "Requires Image API",
        "Live Voice Conversation": "Not implemented"
    }

    for feature, status in features.items():
        st.write(f"**{feature}:** {status}")

    st.divider()

    st.caption(
        "Never share your API keys. Keep them in your local .env file."
    )

# ============================================================
# END OF NEXTGEN AI
# ============================================================
