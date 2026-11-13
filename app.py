
import os
import io
import sqlite3
import base64
from datetime import datetime

import streamlit as st
import requests
import pandas as pd
import plotly.express as px
from dotenv import load_dotenv
from groq import Groq
from google import genai
from pypdf import PdfReader
from PIL import Image
from gtts import gTTS

load_dotenv()

# =====================================================
# APP CONFIG
# =====================================================

st.set_page_config(
    page_title="NEXTGEN AI",
    page_icon="🚀",
    layout="wide",
    initial_sidebar_state="expanded"
)

DB = "nextgen_ai.db"

GROQ_API_KEY = os.getenv("GROQ_API_KEY", "")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
TAVILY_API_KEY = os.getenv("TAVILY_API_KEY", "")
FINNHUB_API_KEY = os.getenv("FINNHUB_API_KEY", "")
CLOUDFLARE_API_TOKEN = os.getenv("CLOUDFLARE_API_TOKEN", "")
CLOUDFLARE_ACCOUNT_ID = os.getenv("CLOUDFLARE_ACCOUNT_ID", "")

# =====================================================
# DATABASE
# =====================================================

def connect_db():
    return sqlite3.connect(DB, check_same_thread=False)

def init_db():
    con = connect_db()
    cur = con.cursor()

    cur.execute("""
        CREATE TABLE IF NOT EXISTS ng2_chats(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id TEXT,
            title TEXT,
            created_at TEXT
        )
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS ng2_messages(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            chat_id INTEGER,
            role TEXT,
            content TEXT,
            created_at TEXT
        )
    """)

    con.commit()
    con.close()

def create_chat(user_id):
    con = connect_db()
    cur = con.cursor()
    cur.execute(
        "INSERT INTO ng2_chats(user_id,title,created_at) VALUES(?,?,?)",
        (user_id, "New Chat", datetime.now().isoformat())
    )
    chat_id = cur.lastrowid
    con.commit()
    con.close()
    return chat_id

def save_message(chat_id, role, content):
    con = connect_db()
    con.execute(
        "INSERT INTO ng2_messages(chat_id,role,content,created_at) VALUES(?,?,?,?)",
        (chat_id, role, content, datetime.now().isoformat())
    )
    con.commit()
    con.close()

def load_messages(chat_id):
    con = connect_db()
    rows = con.execute(
        "SELECT role,content FROM ng2_messages WHERE chat_id=? ORDER BY id",
        (chat_id,)
    ).fetchall()
    con.close()

    return [
        {"role": row[0], "content": row[1]}
        for row in rows
    ]

def get_chats(user_id):
    con = connect_db()
    rows = con.execute(
        "SELECT id,title FROM ng2_chats WHERE user_id=? ORDER BY id DESC",
        (user_id,)
    ).fetchall()
    con.close()
    return rows

def rename_chat(chat_id, title):
    con = connect_db()
    con.execute(
        "UPDATE ng2_chats SET title=? WHERE id=?",
        (title[:60], chat_id)
    )
    con.commit()
    con.close()

def delete_chat(chat_id):
    con = connect_db()
    con.execute(
        "DELETE FROM ng2_messages WHERE chat_id=?",
        (chat_id,)
    )
    con.execute(
        "DELETE FROM ng2_chats WHERE id=?",
        (chat_id,)
    )
    con.commit()
    con.close()

init_db()

# =====================================================
# SESSION STATE
# =====================================================

defaults = {
    "user_id": "guest",
    "chat_id": None,
    "messages": [],
    "page": "AI Chat",
    "last_prompt": "",
    "last_response": ""
}

for key, value in defaults.items():
    if key not in st.session_state:
        st.session_state[key] = value

# =====================================================
# DESIGN
# =====================================================

st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&display=swap');

html,body,[class*="css"]{
    font-family:Inter,sans-serif;
}

.stApp{
    background:#08090D;
    color:#F4F4F5;
}

[data-testid="stSidebar"]{
    background:#0E1016;
    border-right:1px solid #252733;
}

.block-container{
    max-width:1250px;
    padding-top:1.5rem;
    padding-bottom:5rem;
}

.brand{
    font-size:25px;
    font-weight:800;
    letter-spacing:-1px;
    background:linear-gradient(90deg,#A78BFA,#60A5FA);
    -webkit-background-clip:text;
    -webkit-text-fill-color:transparent;
}

.hero{
    text-align:center;
    padding:65px 10px 35px;
    animation:fade 0.7s ease;
}

.hero h1{
    font-size:clamp(35px,5vw,58px);
    font-weight:800;
    letter-spacing:-2px;
    background:linear-gradient(90deg,#fff,#aaa,#9B8AFF);
    -webkit-background-clip:text;
    -webkit-text-fill-color:transparent;
}

.hero p{
    color:#9295A3;
    font-size:16px;
}

.feature-card{
    background:linear-gradient(145deg,#171923,#101119);
    border:1px solid #292C3A;
    border-radius:17px;
    padding:20px;
    min-height:120px;
    transition:0.25s;
    margin-bottom:15px;
}

.feature-card:hover{
    border-color:#8B5CF6;
    transform:translateY(-3px);
}

.panel{
    background:#11131B;
    border:1px solid #292C38;
    border-radius:18px;
    padding:22px;
}

.small-muted{
    color:#9295A3;
    font-size:13px;
}

.stButton>button{
    border-radius:12px;
    border:1px solid #343747;
    background:#171923;
    color:white;
    min-height:42px;
    transition:0.2s;
}

.stButton>button:hover{
    border-color:#8B5CF6;
    background:#242033;
    color:white;
}

[data-testid="stChatInput"]{
    border:1px solid #454052!important;
    border-radius:20px!important;
    background:#15151E!important;
}

[data-testid="stChatInput"] textarea{
    color:white!important;
}

[data-testid="stChatMessage"]{
    background:transparent;
    border:1px solid #242632;
    border-radius:16px;
    padding:14px;
    margin-bottom:12px;
}

input,textarea{
    background:#151720!important;
    color:white!important;
}

hr{
    border-color:#292C38;
}

@keyframes fade{
    from{opacity:0;transform:translateY(12px);}
    to{opacity:1;transform:translateY(0);}
}
</style>
""", unsafe_allow_html=True)

# =====================================================
# AI ENGINE
# =====================================================

SYSTEM_PROMPT = """
You are NEXTGEN AI, a helpful and intelligent AI assistant.
Give clear, accurate and useful answers.
If the user speaks Hindi, respond in Hindi.
Never invent information or pretend a tool worked when it did not.
"""

def ask_ai(prompt, history=None):
    history = history or []
    groq_error = "Groq API key missing."

    if GROQ_API_KEY:
        try:
            client = Groq(api_key=GROQ_API_KEY)

            messages = [
                {"role": "system", "content": SYSTEM_PROMPT}
            ]

            for item in history[-12:]:
                if item["role"] in ("user", "assistant"):
                    messages.append({
                        "role": item["role"],
                        "content": item["content"]
                    })

            messages.append({
                "role": "user",
                "content": prompt
            })

            result = client.chat.completions.create(
                model="llama-3.3-70b-versatile",
                messages=messages,
                temperature=0.7,
                max_tokens=2500
            )

            return result.choices[0].message.content, "Groq"

        except Exception as e:
            groq_error = str(e)

    if GEMINI_API_KEY:
        try:
            client = genai.Client(api_key=GEMINI_API_KEY)

            result = client.models.generate_content(
                model="gemini-2.5-flash",
                contents=SYSTEM_PROMPT + "\n\n" + prompt
            )

            return result.text, "Gemini"

        except Exception as e:
            return (
                f"AI provider error.\nGroq: {groq_error}\nGemini: {e}",
                "Error"
            )

    return (
        "AI API configured नहीं है। GROQ_API_KEY या GEMINI_API_KEY जोड़ें।",
        "Configuration"
    )

# =====================================================
# WEB SEARCH
# =====================================================

def web_search(query):
    if not TAVILY_API_KEY:
        return "TAVILY_API_KEY configured नहीं है।"

    try:
        response = requests.post(
            "https://api.tavily.com/search",
            json={
                "api_key": TAVILY_API_KEY,
                "query": query,
                "search_depth": "advanced",
                "max_results": 6,
                "include_answer": True
            },
            timeout=30
        )

        response.raise_for_status()
        data = response.json()

        output = []

        if data.get("answer"):
            output.append("## Summary\n" + data["answer"])

        for item in data.get("results", []):
            output.append(
                f"### {item.get('title','Result')}\n"
                f"{item.get('content','')}\n"
                f"Source: {item.get('url','')}"
            )

        return "\n\n".join(output) or "No results found."

    except Exception as e:
        return f"Search error: {e}"

# =====================================================
# FINNHUB
# =====================================================

def finnhub_get(endpoint, params=None):
    if not FINNHUB_API_KEY:
        return None

    params = dict(params or {})
    params["token"] = FINNHUB_API_KEY

    try:
        response = requests.get(
            "https://finnhub.io/api/v1/" + endpoint,
            params=params,
            timeout=20
        )
        response.raise_for_status()
        return response.json()

    except Exception as e:
        st.error(f"Finnhub error: {e}")
        return None

# =====================================================
# SIDEBAR
# =====================================================

PAGES = [
    "Dashboard",
    "AI Chat",
    "Stock Market",
    "Stock Market Academy",
    "AI Vision",
    "PDF Assistant",
    "Image Studio",
    "Web Search",
    "Voice Studio",
    "Coding Lab",
    "Study Assistant",
    "Video Studio",
    "AI Tools",
    "AI Skill Center",
    "Settings",
    "About"
]

with st.sidebar:
    st.markdown(
        '<div class="brand">🚀 NEXTGEN AI</div>',
        unsafe_allow_html=True
    )

    st.caption("ONE PLATFORM. ENDLESS POSSIBILITIES.")
    st.divider()

    if st.button("＋ New Chat", use_container_width=True):
        st.session_state.chat_id = create_chat(
            st.session_state.user_id
        )
        st.session_state.messages = []
        st.session_state.page = "AI Chat"
        st.rerun()

    st.markdown("### WORKSPACE")

    for item in PAGES:
        label = ("● " if st.session_state.page == item else "") + item

        if st.button(
            label,
            key="nav_" + item,
            use_container_width=True
        ):
            st.session_state.page = item
            st.rerun()

    st.divider()
    st.markdown("### CHAT HISTORY")

    for cid, title in get_chats(st.session_state.user_id)[:20]:
        if st.button(
            "💬 " + title,
            key=f"history_{cid}",
            use_container_width=True
        ):
            st.session_state.chat_id = cid
            st.session_state.messages = load_messages(cid)
            st.session_state.page = "AI Chat"
            st.rerun()

    st.divider()
    st.caption("NEXTGEN AI • PRO VERSION")

# =====================================================
# TOP HEADER
# =====================================================

page = st.session_state.page

st.markdown(
    f"""
    <div style="
        display:flex;
        justify-content:space-between;
        align-items:center;
        border-bottom:1px solid #252733;
        padding-bottom:12px;">
        <span class="brand">NEXTGEN AI</span>
        <span class="small-muted">{page} · PRO WORKSPACE</span>
    </div>
    """,
    unsafe_allow_html=True
)

# =====================================================
# DASHBOARD
# =====================================================

if page == "Dashboard":

    st.markdown("""
    <div class="hero">
        <h1>Welcome to NEXTGEN AI</h1>
        <p>Your creative universe. One intelligent workspace.</p>
    </div>
    """, unsafe_allow_html=True)

    columns = st.columns(3)

    cards = [
        ("🤖", "AI Chat", "Ask questions and explore ideas."),
        ("👁️", "AI Vision", "Understand images with AI."),
        ("📄", "PDF Assistant", "Ask questions about documents."),
        ("📈", "Stock Market", "Explore market information."),
        ("🎨", "Image Studio", "Generate AI images."),
        ("🌐", "Web Search", "Research information online.")
    ]

    for i, (icon, title, desc) in enumerate(cards):
        with columns[i % 3]:
            st.markdown(
                f"""
                <div class="feature-card">
                    <h2>{icon}</h2>
                    <h3>{title}</h3>
                    <p class="small-muted">{desc}</p>
                </div>
                """,
                unsafe_allow_html=True
            )

    if st.button("💬 Start New Conversation", use_container_width=True):
        st.session_state.chat_id = create_chat(
            st.session_state.user_id
        )
        st.session_state.messages = []
        st.session_state.page = "AI Chat"
        st.rerun()

# =====================================================
# AI CHAT
# =====================================================

elif page == "AI Chat":

    if not st.session_state.messages:
        st.markdown("""
        <div class="hero">
            <h1>What can I help with?</h1>
            <p>Ask anything. Create something. Learn something new.</p>
        </div>
        """, unsafe_allow_html=True)

        a, b, c = st.columns(3)

        with a:
            st.markdown(
                '<div class="feature-card">💡<h3>Brainstorm</h3>'
                '<p class="small-muted">Explore new ideas.</p></div>',
                unsafe_allow_html=True
            )

        with b:
            st.markdown(
                '<div class="feature-card">💻<h3>Code</h3>'
                '<p class="small-muted">Build and debug projects.</p></div>',
                unsafe_allow_html=True
            )

        with c:
            st.markdown(
                '<div class="feature-card">📚<h3>Learn</h3>'
                '<p class="small-muted">Understand difficult topics.</p></div>',
                unsafe_allow_html=True
            )

    for message in st.session_state.messages:
        with st.chat_message(message["role"]):
            st.markdown(message["content"])

            if message["role"] == "assistant":
                with st.popover("•••"):
                    st.code(message["content"], language=None)

    prompt = st.chat_input("Message NEXTGEN AI...")

    if prompt:

        if not st.session_state.chat_id:
            st.session_state.chat_id = create_chat(
                st.session_state.user_id
            )

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
            rename_chat(st.session_state.chat_id, prompt[:45])

        with st.chat_message("user"):
            st.markdown(prompt)

        with st.chat_message("assistant"):
            with st.spinner("NEXTGEN AI is thinking..."):
                answer, provider = ask_ai(
                    prompt,
                    st.session_state.messages[:-1]
                )

                st.markdown(answer)
                st.caption("Powered by " + provider)

        st.session_state.messages.append({
            "role": "assistant",
            "content": answer
        })

        save_message(
            st.session_state.chat_id,
            "assistant",
            answer
        )

        st.session_state.last_prompt = prompt
        st.session_state.last_response = answer

        st.rerun()

    if st.session_state.last_prompt:
        if st.button("🔄 Regenerate last answer"):

            history = st.session_state.messages[:-1]

            with st.spinner("Generating another answer..."):
                answer, provider = ask_ai(
                    st.session_state.last_prompt,
                    history
                )

            con = connect_db()

            con.execute("""
                DELETE FROM ng2_messages
                WHERE id = (
                    SELECT id FROM ng2_messages
                    WHERE chat_id=? AND role='assistant'
                    ORDER BY id DESC LIMIT 1
                )
            """, (st.session_state.chat_id,))

            con.commit()
            con.close()

            if (
                st.session_state.messages
                and st.session_state.messages[-1]["role"] == "assistant"
            ):
                st.session_state.messages.pop()

            st.session_state.messages.append({
                "role": "assistant",
                "content": answer
            })

            save_message(
                st.session_state.chat_id,
                "assistant",
                answer
            )

            st.session_state.last_response = answer
            st.rerun()

# =====================================================
# STOCK MARKET
# =====================================================

elif page == "Stock Market":

    st.title("📈 Global Stock Market")

    st.caption(
        "Market data powered by Finnhub. "
        "Educational information only."
    )

    symbol = st.text_input(
        "Search stock symbol",
        value="AAPL"
    ).upper().strip()

    if st.button("Get Stock Data", use_container_width=True):

        data = finnhub_get(
            "quote",
            {"symbol": symbol}
        )

        if data and data.get("c") is not None:

            c1, c2, c3 = st.columns(3)

            c1.metric(
                "Current Price",
                f"${data.get('c', 0)}",
                f"{data.get('d', 0)}"
            )

            c2.metric(
                "Change %",
                f"{data.get('dp', 0):.2f}%"
            )

            c3.metric(
                "Previous Close",
                f"${data.get('pc', 0)}"
            )

            profile = finnhub_get(
                "stock/profile2",
                {"symbol": symbol}
            )

            if profile:
                st.subheader(profile.get("name", symbol))
                st.write(
                    "Industry:",
                    profile.get("finnhubIndustry", "N/A")
                )
                st.write(
                    "Exchange:",
                    profile.get("exchange", "N/A")
                )

        else:
            st.warning(
                "Stock data unavailable. Check symbol and API key."
            )

    st.info(
        "यह market information है, buy/sell recommendation नहीं।"
    )

# =====================================================
# STOCK ACADEMY
# =====================================================

elif page == "Stock Market Academy":

    st.title("📚 Stock Market Academy")

    topic = st.text_input(
        "What do you want to learn?",
        "What is the stock market?"
    )

    if st.button("Explain Topic"):
        with st.spinner("Preparing lesson..."):
            answer, _ = ask_ai(
                "Explain this stock market topic in simple language "
                "with examples:\n" + topic
            )
            st.markdown(answer)

# =====================================================
# AI VISION
# =====================================================

elif page == "AI Vision":

    st.title("👁️ AI Vision")

    uploaded = st.file_uploader(
        "Upload image",
        type=["png", "jpg", "jpeg", "webp"]
    )

    question = st.text_input(
        "Ask about the image",
        "Describe this image."
    )

    if uploaded:

        image = Image.open(uploaded).convert("RGB")

        st.image(
            image,
            use_container_width=True
        )

        if st.button("Analyze Image"):

            if not GEMINI_API_KEY:
                st.error("Gemini API key is required.")
            else:
                try:
                    client = genai.Client(
                        api_key=GEMINI_API_KEY
                    )

                    result = client.models.generate_content(
                        model="gemini-2.5-flash",
                        contents=[question, image]
                    )

                    st.markdown(result.text)

                except Exception as e:
                    st.error(str(e))

# =====================================================
# PDF ASSISTANT
# =====================================================

elif page == "PDF Assistant":

    st.title("📄 PDF Assistant")

    pdf = st.file_uploader(
        "Upload PDF",
        type=["pdf"]
    )

    if pdf:

        try:
            reader = PdfReader(pdf)

            document_text = "\n".join(
                page.extract_text() or ""
                for page in reader.pages
            )

            st.success(
                f"PDF loaded: {len(reader.pages)} pages"
            )

            question = st.text_input(
                "Ask a question about your PDF"
            )

            if st.button("Ask PDF Assistant"):

                with st.spinner("Reading your document..."):

                    answer, _ = ask_ai(
                        "Answer using the document content. "
                        "If the answer is not present, say so.\n\n"
                        "DOCUMENT:\n"
                        + document_text[:25000]
                        + "\n\nQUESTION:\n"
                        + question
                    )

                    st.markdown(answer)

        except Exception as e:
            st.error(str(e))

# =====================================================
# WEB SEARCH
# =====================================================

elif page == "Web Search":

    st.title("🌐 AI Web Search")

    query = st.text_input(
        "Search the web",
        placeholder="Enter your search query..."
    )

    if st.button("Search Web", use_container_width=True):

        with st.spinner("Searching the web..."):
            st.markdown(web_search(query))

# =====================================================
# IMAGE STUDIO
# =====================================================

elif page == "Image Studio":

    st.title("🎨 AI Image Studio")

    prompt = st.text_area(
        "Describe the image you want to create"
    )

    if st.button("Generate Image"):

        if not CLOUDFLARE_API_TOKEN or not CLOUDFLARE_ACCOUNT_ID:
            st.error("Cloudflare API credentials are missing.")

        else:
            try:
                url = (
                    "https://api.cloudflare.com/client/v4/accounts/"
                    + CLOUDFLARE_ACCOUNT_ID
                    + "/ai/run/@cf/black-forest-labs/flux-1-schnell"
                )

                response = requests.post(
                    url,
                    headers={
                        "Authorization":
                        "Bearer " + CLOUDFLARE_API_TOKEN
                    },
                    json={"prompt": prompt},
                    timeout=120
                )

                response.raise_for_status()

                result = response.json()

                image_data = (
                    result.get("result", {}).get("image")
                )

                if image_data:

                    image_bytes = base64.b64decode(
                        image_data
                    )

                    st.image(
                        image_bytes,
                        use_container_width=True
                    )

                    st.download_button(
                        "Download Image",
                        data=image_bytes,
                        file_name="nextgen_image.png",
                        mime="image/png"
                    )

                else:
                    st.error("Image was not returned.")

            except Exception as e:
                st.error(f"Image generation error: {e}")

# =====================================================
# VOICE STUDIO
# =====================================================

elif page == "Voice Studio":

    st.title("🎙️ Voice Studio")

    st.caption(
        "Record a message, convert speech to text "
        "and receive an AI answer."
    )

    audio = st.audio_input("Record your voice")

    if audio:

        st.audio(audio)

        if st.button("Transcribe and Ask AI"):

            if not GROQ_API_KEY:
                st.error("Groq API key is required.")

            else:
                try:
                    client = Groq(
                        api_key=GROQ_API_KEY
                    )

                    transcription = (
                        client.audio.transcriptions.create(
                            file=(
                                "recording.wav",
                                audio.getvalue()
                            ),
                            model="whisper-large-v3",
                            response_format="text"
                        )
                    )

                    st.write("Transcription:")
                    st.write(transcription)

                    with st.spinner("Generating answer..."):

                        answer, _ = ask_ai(
                            str(transcription)
                        )

                        st.markdown(answer)

                        tts = gTTS(
                            answer[:4000]
                        )

                        audio_buffer = io.BytesIO()

                        tts.write_to_fp(
                            audio_buffer
                        )

                        st.audio(
                            audio_buffer.getvalue(),
                            format="audio/mp3"
                        )

                except Exception as e:
                    st.error(str(e))

    st.info(
        "यह recording-based voice assistant है। "
        "Live voice calling के लिए अलग realtime audio integration चाहिए।"
    )

# =====================================================
# CODING LAB
# =====================================================

elif page == "Coding Lab":

    st.title("💻 Coding Lab")

    language = st.selectbox(
        "Programming language",
        [
            "Python",
            "JavaScript",
            "HTML/CSS",
            "C++",
            "Java",
            "SQL"
        ]
    )

    task = st.text_area(
        "What do you want to build or fix?"
    )

    if st.button("Generate Code"):

        with st.spinner("Writing code..."):

            answer, _ = ask_ai(
                f"Act as a coding tutor. Use {language}. "
                "Explain the solution and provide complete code.\n\n"
                + task
            )

            st.markdown(answer)

# =====================================================
# STUDY ASSISTANT
# =====================================================

elif page == "Study Assistant":

    st.title("🎓 Study Assistant")

    subject = st.selectbox(
        "Subject",
        [
            "Mathematics",
            "Science",
            "English",
            "Hindi",
            "Social Science",
            "Computer"
        ]
    )

    level = st.selectbox(
        "Class",
        [
            "Class 6",
            "Class 7",
            "Class 8",
            "Class 9",
            "Class 10"
        ]
    )

    question = st.text_area(
        "Enter your question"
    )

    if st.button("Solve / Explain"):

        with st.spinner("Preparing explanation..."):

            answer, _ = ask_ai(
                f"Act as a patient school teacher. "
                f"Explain at {level} level. "
                f"Subject: {subject}. "
                "Give step-by-step explanation.\n\n"
                + question
            )

            st.markdown(answer)

# =====================================================
# VIDEO STUDIO
# =====================================================

elif page == "Video Studio":

    st.title("🎬 Video Studio")

    idea = st.text_area(
        "Describe your video idea"
    )

    duration = st.selectbox(
        "Video duration",
        [
            "15 seconds",
            "30 seconds",
            "60 seconds",
            "90 seconds"
        ]
    )

    style = st.selectbox(
        "Video style",
        [
            "Cinematic",
            "Realistic",
            "Animated",
            "Documentary",
            "Social Media Reel"
        ]
    )

    if st.button("Create Video Plan"):

        with st.spinner("Creating scenes and prompts..."):

            answer, _ = ask_ai(
                f"Create a complete {duration} {style} video plan. "
                "Include scene-by-scene prompts, camera movement, "
                "dialogue, voiceover and transitions.\n\n"
                + idea
            )

            st.markdown(answer)

    st.caption(
        "यहाँ script और video prompts बनते हैं। "
        "Actual video rendering के लिए video API चाहिए।"
    )

# =====================================================
# AI TOOLS
# =====================================================

elif page == "AI Tools":

    st.title("🧰 AI Tools")

    tool = st.selectbox(
        "Choose a tool",
        [
            "Text Summarizer",
            "Grammar Corrector",
            "Email Writer",
            "Story Writer",
            "Translator",
            "Quiz Generator",
            "Prompt Generator"
        ]
    )

    content = st.text_area(
        "Enter text or instructions"
    )

    if st.button("Run Tool"):

        with st.spinner("Working..."):

            answer, _ = ask_ai(
                f"Perform this task: {tool}. "
                "Give the complete result.\n\n"
                + content
            )

            st.markdown(answer)

# =====================================================
# AI SKILL CENTER
# =====================================================

elif page == "AI Skill Center":

    st.title("🚀 AI Skill Center")

    skill = st.selectbox(
        "Choose a skill",
        [
            "Prompt Engineering",
            "Python Programming",
            "Web Development",
            "AI Basics",
            "Data Analysis",
            "Cyber Safety",
            "Creative Writing"
        ]
    )

    if st.button("Start Learning"):

        with st.spinner("Building your learning path..."):

            answer, _ = ask_ai(
                f"Create a beginner-friendly learning path "
                f"for {skill}. Include lessons, projects, "
                "practice tasks and a quiz."
            )

            st.markdown(answer)

# =====================================================
# SETTINGS
# =====================================================

elif page == "Settings":

    st.title("⚙️ Settings")

    st.subheader("API Configuration")

    keys = {
        "Groq AI": GROQ_API_KEY,
        "Gemini AI": GEMINI_API_KEY,
        "Tavily Web Search": TAVILY_API_KEY,
        "Finnhub Market Data": FINNHUB_API_KEY,
        "Cloudflare Image Generation": CLOUDFLARE_API_TOKEN
    }

    for name, value in keys.items():

        status = (
            "🟢 Configured"
            if value
            else "🔴 Not configured"
        )

        st.write(f"{status} — {name}")

    st.divider()

    st.subheader("Chat Management")

    chats = get_chats(
        st.session_state.user_id
    )

    if chats:

        selected = st.selectbox(
            "Select chat to delete",
            options=[item[0] for item in chats],
            format_func=lambda x: next(
                (
                    item[1]
                    for item in chats
                    if item[0] == x
                ),
                str(x)
            )
        )

        if st.button("Delete Selected Chat"):

            delete_chat(selected)

            if st.session_state.chat_id == selected:
                st.session_state.chat_id = None
                st.session_state.messages = []

            st.success("Chat deleted.")
            st.rerun()

    st.caption(
        "API keys को source code में hard-code न करें। "
        "उन्हें .env या Streamlit Secrets में रखें।"
    )

# =====================================================
# ABOUT
# =====================================================

elif page == "About":

    st.title("🚀 About NEXTGEN AI")

    st.markdown("""
    ## One Platform. Endless Possibilities.

    NEXTGEN AI is a multi-purpose AI workspace.

    Features:
    - AI Chat
    - AI Vision
    - PDF Assistant
    - Web Search
    - Stock Market Information
    - Image Studio
    - Voice Studio
    - Coding Lab
    - Study Assistant
    - Video Prompt Studio

    **Version:** 2.0

    Built with Python and Streamlit.
    """)

# =====================================================
# FOOTER
# =====================================================

st.markdown("""
<hr>
<div style="
    text-align:center;
    color:#777;
    font-size:12px;
    padding:10px;">
    NEXTGEN AI © 2026 · YOUR CREATIVE UNIVERSE
</div>
""", unsafe_allow_html=True)
