# =========================================================
# 🚀 NEXTGEN AI ULTRA — COMPLETE APP.PY
# Built by Arav | Python + Streamlit + SQLite
# =========================================================

import streamlit as st
import sqlite3
import requests
import os
import io
import json
import time
import base64
import uuid
from datetime import datetime

try:
    from groq import Groq
except ImportError:
    Groq = None

try:
    from google import genai
except ImportError:
    genai = None

try:
    from pypdf import PdfReader
except ImportError:
    PdfReader = None

try:
    from PIL import Image
except ImportError:
    Image = None

try:
    from gtts import gTTS
except ImportError:
    gTTS = None

try:
    import plotly.graph_objects as go
except ImportError:
    go = None


# ---------------- PAGE CONFIG ----------------

st.set_page_config(
    page_title="NEXTGEN AI ULTRA",
    page_icon="🚀",
    layout="wide",
    initial_sidebar_state="expanded"
)


# ---------------- DESIGN ----------------

st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=DM+Sans:wght@400;500;600;700;800&family=Space+Grotesk:wght@500;600;700&display=swap');

.stApp {
    background:
    radial-gradient(circle at 10% 0%, #191638 0%, transparent 35%),
    radial-gradient(circle at 90% 10%, #082b38 0%, transparent 30%),
    #080a12;
    color: #ffffff;
    font-family: 'DM Sans', sans-serif;
}

[data-testid="stSidebar"] {
    background: #0c1020;
    border-right: 1px solid #252c47;
}

.block-container {
    max-width: 1450px;
    padding-top: 2rem;
}

h1,h2,h3 {
    font-family: 'Space Grotesk', sans-serif;
}

.hero {
    padding: 35px;
    border-radius: 25px;
    background: linear-gradient(120deg,#30246b,#122e4b,#101827);
    border: 1px solid #424b7d;
    margin-bottom: 25px;
}

.hero h1 {
    font-size: 43px;
    margin-bottom: 5px;
}

.hero p {
    color: #c2cbea;
    font-size: 17px;
}

.panel {
    background: linear-gradient(145deg,#151c30,#101522);
    border: 1px solid #2a3654;
    padding: 20px;
    border-radius: 19px;
    margin-bottom: 15px;
}

.stButton button {
    background: linear-gradient(120deg,#7357ff,#287bdc);
    border: none;
    border-radius: 12px;
    color: white;
    font-weight: 700;
    min-height: 42px;
}

.stButton button:hover {
    filter: brightness(1.2);
    border: 1px solid #9bdfff;
}

.stTextInput input,
.stTextArea textarea,
.stSelectbox div[data-baseweb="select"] > div {
    background: #101626 !important;
    color: white !important;
    border: 1px solid #34415e !important;
    border-radius: 12px !important;
}

[data-testid="stChatInput"] {
    background: #101626 !important;
    border: 1px solid #3a4665 !important;
    border-radius: 17px !important;
}

[data-testid="stChatInput"] textarea {
    color: white !important;
    background: #101626 !important;
}

[data-testid="stMetric"] {
    background: #141c30;
    border: 1px solid #303c5b;
    border-radius: 16px;
    padding: 16px;
}

[data-testid="stFileUploader"] {
    background: #111827;
    border-radius: 15px;
}

.stTabs [data-baseweb="tab"] {
    background: #151b2c;
    border-radius: 10px;
}

hr {
    border-color: #29334b;
}
</style>
""", unsafe_allow_html=True)


# ---------------- DATABASE ----------------

DB = "nextgen_ai.db"

def database():
    return sqlite3.connect(DB, check_same_thread=False)

def initialize():
    with database() as con:
        con.execute("""
        CREATE TABLE IF NOT EXISTS ultra_chats(
            id TEXT PRIMARY KEY,
            title TEXT,
            created TEXT
        )
        """)
        con.execute("""
        CREATE TABLE IF NOT EXISTS ultra_messages(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            chat_id TEXT,
            role TEXT,
            content TEXT,
            created TEXT
        )
        """)
        con.execute("""
        CREATE TABLE IF NOT EXISTS ultra_notes(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT,
            content TEXT,
            created TEXT
        )
        """)
        con.execute("""
        CREATE TABLE IF NOT EXISTS ultra_watchlist(
            symbol TEXT PRIMARY KEY
        )
        """)
        con.commit()

initialize()


def new_chat():
    cid = str(uuid.uuid4())
    with database() as con:
        con.execute(
            "INSERT INTO ultra_chats VALUES(?,?,?)",
            (cid, "New conversation", str(datetime.now()))
        )
        con.commit()
    return cid


def save_message(cid, role, content):
    with database() as con:
        con.execute("""
        INSERT INTO ultra_messages(chat_id,role,content,created)
        VALUES(?,?,?,?)
        """, (cid, role, content, str(datetime.now())))

        if role == "user":
            row = con.execute(
                "SELECT title FROM ultra_chats WHERE id=?", (cid,)
            ).fetchone()

            if row and row[0] == "New conversation":
                title = content[:45].replace("\n", " ")
                con.execute(
                    "UPDATE ultra_chats SET title=? WHERE id=?",
                    (title, cid)
                )

        con.commit()


def load_messages(cid):
    with database() as con:
        return con.execute("""
        SELECT role,content FROM ultra_messages
        WHERE chat_id=? ORDER BY id
        """, (cid,)).fetchall()


# ---------------- API CONFIGURATION ----------------

def secret(name):
    try:
        return str(st.secrets.get(name, "")).strip()
    except Exception:
        return os.getenv(name, "").strip()


GROQ_KEY = secret("GROQ_API_KEY")
GEMINI_KEY = secret("GEMINI_API_KEY")
TAVILY_KEY = secret("TAVILY_API_KEY")
FINNHUB_KEY = secret("FINNHUB_API_KEY")
CF_TOKEN = secret("CLOUDFLARE_API_TOKEN")
CF_ACCOUNT = secret("CLOUDFLARE_ACCOUNT_ID")


SYSTEM_PROMPT = """
You are NEXTGEN AI, a helpful and intelligent assistant.
Respond in the user's language, Hindi or English.
Explain complicated topics in simple steps.
For school topics, teach clearly and use examples.
Never reveal API keys or private information.

If asked who created NEXTGEN AI, answer:
NEXTGEN AI was created and developed by Arav,
a Class 7 student and young technology enthusiast from India.
It is built using Python, Streamlit, SQLite and integrated AI services.
Arav developed the platform, not the underlying foundation models.

Do not claim guaranteed financial returns.
Do not invent facts.
"""


# ---------------- AI ENGINE ----------------

def groq_answer(prompt, history):
    if not GROQ_KEY or Groq is None:
        raise Exception("Groq API key or package is missing.")

    client = Groq(api_key=GROQ_KEY)

    messages = [
        {"role": "system", "content": SYSTEM_PROMPT}
    ]

    for role, content in history[-12:]:
        if role in ("user", "assistant"):
            messages.append({
                "role": role,
                "content": content[:10000]
            })

    messages.append({
        "role": "user",
        "content": prompt
    })

    result = client.chat.completions.create(
        model="openai/gpt-oss-120b",
        messages=messages,
        temperature=0.65,
        max_completion_tokens=3000
    )

    return result.choices[0].message.content


def gemini_answer(prompt, history):
    if not GEMINI_KEY or genai is None:
        raise Exception("Gemini API key or package is missing.")

    client = genai.Client(api_key=GEMINI_KEY)

    transcript = []

    for role, content in history[-12:]:
        transcript.append(f"{role}: {content[:6000]}")

    transcript.append("user: " + prompt)

    response = client.models.generate_content(
        model="gemini-3.8-flash",
        contents=SYSTEM_PROMPT + "\n" + "\n".join(transcript)
    )

    return response.text


def ask_ai(prompt, history=None, provider="Auto"):
    history = history or []
    errors = []

    if provider in ("Auto", "Groq"):
        try:
            return groq_answer(prompt, history), "Groq"
        except Exception as e:
            errors.append("Groq: " + str(e))

    if provider in ("Auto", "Gemini"):
        try:
            return gemini_answer(prompt, history), "Gemini"
        except Exception as e:
            errors.append("Gemini: " + str(e))

    raise Exception("\n".join(errors))


# ---------------- COMMON FUNCTIONS ----------------

def hero(title, subtitle):
    st.markdown(f"""
    <div class="hero">
        <div style="color:#a9b8ff;font-weight:800;letter-spacing:3px">
            NEXTGEN AI · ULTRA WORKSPACE
        </div>
        <h1>{title}</h1>
        <p>{subtitle}</p>
    </div>
    """, unsafe_allow_html=True)


def answer_box(prompt):
    try:
        with st.spinner("NEXTGEN AI is thinking..."):
            answer, provider = ask_ai(
                prompt,
                provider=st.session_state.get("provider", "Auto")
            )
        st.markdown("### ✨ AI Response")
        st.markdown(answer)
        st.session_state.last_answer = answer
        st.caption("Powered by " + provider)
        return answer
    except Exception as e:
        st.error(str(e))
        return None


def download_answer(text, filename="nextgen_result.txt"):
    st.download_button(
        "⬇️ Download result",
        text,
        file_name=filename
    )


# ---------------- SESSION ----------------

if "page" not in st.session_state:
    st.session_state.page = "Dashboard"

if "chat_id" not in st.session_state:
    st.session_state.chat_id = new_chat()

if "provider" not in st.session_state:
    st.session_state.provider = "Auto"

if "last_answer" not in st.session_state:
    st.session_state.last_answer = ""


# ---------------- SIDEBAR ----------------

with st.sidebar:
    st.markdown("# 🚀 NEXTGEN AI")
    st.caption("ULTRA EDITION · VERSION 2.0")
    st.divider()

    navigation = {
        "HOME": [
            "Dashboard",
            "AI Chat",
            "Chat History"
        ],
        "AI TOOLS": [
            "AI Vision",
            "PDF Assistant",
            "Web Research",
            "Image Studio",
            "Voice Studio"
        ],
        "PRODUCTIVITY": [
            "Coding Lab",
            "Study Assistant",
            "Chess Coach",
            "Video Studio",
            "Smart Notes"
        ],
        "MARKETS": [
            "Stock Market",
            "Market Academy"
        ],
        "SYSTEM": [
            "AI Skill Center",
            "Settings",
            "About"
        ]
    }

    for group, pages in navigation.items():
        st.caption(group)

        for page in pages:
            if st.button(
                ("✦ " if st.session_state.page == page else "　") + page,
                key="nav_" + page,
                use_container_width=True
            ):
                st.session_state.page = page
                st.rerun()

    st.divider()

    st.session_state.provider = st.selectbox(
        "AI Provider",
        ["Auto", "Groq", "Gemini"]
    )

    if st.button("＋ NEW CHAT", use_container_width=True):
        st.session_state.chat_id = new_chat()
        st.session_state.page = "AI Chat"
        st.rerun()


# =========================================================
# DASHBOARD
# =========================================================

if st.session_state.page == "Dashboard":

    hero(
        "Your Creative Universe.",
        "One intelligent platform for learning, creating, exploring and building."
    )

    with database() as con:
        total_chats = con.execute(
            "SELECT COUNT(*) FROM ultra_chats"
        ).fetchone()[0]

        total_messages = con.execute(
            "SELECT COUNT(*) FROM ultra_messages"
        ).fetchone()[0]

        total_notes = con.execute(
            "SELECT COUNT(*) FROM ultra_notes"
        ).fetchone()[0]

    a,b,c,d = st.columns(4)

    a.metric("Conversations", total_chats)
    b.metric("Messages", total_messages)
    c.metric("Saved Notes", total_notes)
    d.metric("AI Workspace", "ONLINE")

    st.markdown("## ✨ Explore NEXTGEN AI")

    cards = [
        ("💬", "AI Chat", "Intelligent conversations"),
        ("👁️", "AI Vision", "Understand images"),
        ("📄", "PDF Assistant", "Study documents"),
        ("🌐", "Web Research", "Research online"),
        ("🎨", "Image Studio", "Create AI artwork"),
        ("🎙️", "Voice Studio", "Voice transcription"),
        ("💻", "Coding Lab", "Build software"),
        ("🎓", "Study Assistant", "Learn smarter"),
        ("♟️", "Chess Coach", "Chess analysis"),
        ("🎬", "Video Studio", "Create video plans"),
        ("📝", "Smart Notes", "Save your ideas"),
        ("📈", "Stock Market", "Explore markets")
    ]

    for start in range(0, len(cards), 4):
        cols = st.columns(4)

        for col, card in zip(cols, cards[start:start+4]):
            with col:
                st.markdown(f"""
                <div class="panel">
                    <div style="font-size:35px">{card[0]}</div>
                    <h3>{card[1]}</h3>
                    <p style="color:#9ba9c7">{card[2]}</p>
                </div>
                """, unsafe_allow_html=True)

                if st.button("Open →", key="card_"+card[1]):
                    st.session_state.page = card[1]
                    st.rerun()

    st.markdown("## ⚡ Quick Ask")

    quick = st.text_input(
        "Ask anything",
        placeholder="What would you like to explore?"
    )

    if st.button("Ask NEXTGEN AI") and quick.strip():
        st.session_state.chat_id = new_chat()
        st.session_state.quick_prompt = quick
        st.session_state.page = "AI Chat"
        st.rerun()


# =========================================================
# AI CHAT
# =========================================================

elif st.session_state.page == "AI Chat":

    hero(
        "AI Chat",
        "Your intelligent assistant. Ask, learn, create and explore."
    )

    cid = st.session_state.chat_id

    history = load_messages(cid)

    if not history:
        st.markdown("""
        <div class="panel">
            <h2>👋 Welcome to NEXTGEN AI</h2>
            <p>Start with a question, upload a file, or choose a task.</p>
        </div>
        """, unsafe_allow_html=True)

    for role, content in history:
        with st.chat_message(role):
            st.markdown(content)

    if "quick_prompt" in st.session_state:
        prompt = st.session_state.pop("quick_prompt")
        save_message(cid, "user", prompt)
        with st.chat_message("user"):
            st.markdown(prompt)

        try:
            previous = load_messages(cid)[:-1]
            result, engine = ask_ai(prompt, previous, st.session_state.provider)
            save_message(cid, "assistant", result)

            with st.chat_message("assistant"):
                st.markdown(result)
                st.caption("Powered by " + engine)

            st.rerun()

        except Exception as e:
            st.error(str(e))

    user_input = st.chat_input(
        "Message NEXTGEN AI...",
        accept_file="multiple",
        file_type=[
            "pdf","txt","md","py","js","html","css",
            "json","csv","png","jpg","jpeg","webp"
        ]
    )

    if user_input:

        if isinstance(user_input, str):
            prompt = user_input
            files = []
        else:
            prompt = getattr(user_input, "text", "") or ""
            files = getattr(user_input, "files", []) or []

        attached_text = ""

        for file in files:
            name = file.name.lower()

            if name.endswith(".pdf") and PdfReader:
                try:
                    reader = PdfReader(io.BytesIO(file.getvalue()))
                    attached_text += "\n\nPDF CONTENT:\n"
                    for page in reader.pages[:50]:
                        attached_text += (page.extract_text() or "") + "\n"
                except Exception as e:
                    attached_text += "\nPDF reading error: " + str(e)

            elif name.endswith((".txt",".md",".py",".js",".json",".csv")):
                attached_text += "\n\nFILE CONTENT:\n"
                attached_text += file.getvalue().decode(
                    "utf-8", errors="replace"
                )[:30000]

            elif name.endswith((".png",".jpg",".jpeg",".webp")):
                attached_text += (
                    f"\nImage attached: {file.name}. "
                    "Use AI Vision to analyze the image."
                )

        prompt = prompt or "Please analyze the attached file."
        prompt += attached_text

        save_message(cid, "user", prompt)

        with st.chat_message("user"):
            st.markdown(prompt[:3000])

        try:
            previous = load_messages(cid)[:-1]
            result, engine = ask_ai(
                prompt, previous, st.session_state.provider
            )

            save_message(cid, "assistant", result)

            with st.chat_message("assistant"):
                st.markdown(result)
                st.caption("Powered by " + engine)

            st.session_state.last_answer = result
            st.rerun()

        except Exception as e:
            st.error("AI response failed: " + str(e))

    with st.expander("🔊 Read latest answer aloud"):
        lang = st.selectbox(
            "Language",
            ["en", "hi"],
            format_func=lambda x: "English" if x == "en" else "Hindi"
        )

        if st.button("Generate speech"):
            if gTTS and st.session_state.last_answer:
                try:
                    audio_buffer = io.BytesIO()
                    gTTS(
                        st.session_state.last_answer[:4000],
                        lang=lang
                    ).write_to_fp(audio_buffer)

                    st.audio(audio_buffer.getvalue(), format="audio/mp3")
                except Exception as e:
                    st.error(str(e))
            else:
                st.warning("No answer available or gTTS is not installed.")

    st.caption(
        "The + attachment control is provided by Streamlit. "
        "A custom in-bar microphone and live voice-call UI needs a separate frontend component."
    )


# =========================================================
# CHAT HISTORY
# =========================================================

elif st.session_state.page == "Chat History":

    hero("Chat History", "Your saved conversations.")

    with database() as con:
        chats = con.execute(
            "SELECT * FROM ultra_chats ORDER BY created DESC"
        ).fetchall()

    for chat in chats:

        with st.container(border=True):
            col1, col2, col3 = st.columns([5,1,1])

            with col1:
                st.markdown("**" + chat[1] + "**")
                st.caption(chat[2])

            with col2:
                if st.button("Open", key="open_"+chat[0]):
                    st.session_state.chat_id = chat[0]
                    st.session_state.page = "AI Chat"
                    st.rerun()

            with col3:
                if st.button("Delete", key="delete_"+chat[0]):
                    with database() as con:
                        con.execute(
                            "DELETE FROM ultra_messages WHERE chat_id=?",
                            (chat[0],)
                        )
                        con.execute(
                            "DELETE FROM ultra_chats WHERE id=?",
                            (chat[0],)
                        )
                        con.commit()
                    st.rerun()


# =========================================================
# AI VISION
# =========================================================

elif st.session_state.page == "AI Vision":

    hero("AI Vision", "Upload an image and ask questions about it.")

    image_file = st.file_uploader(
        "Upload image",
        type=["png","jpg","jpeg","webp"]
    )

    question = st.text_area(
        "What should I analyze?",
        "Describe this image in detail."
    )

    if image_file:
        st.image(image_file, use_container_width=True)

        if st.button("Analyze Image"):

            if not GEMINI_KEY or genai is None:
                st.error("Configure GEMINI_API_KEY and install google-genai.")
            else:
                try:
                    client = genai.Client(api_key=GEMINI_KEY)

                    from google.genai import types

                    response = client.models.generate_content(
                        model="gemini-3.8-flash",
                        contents=[
                            types.Part.from_bytes(
                                data=image_file.getvalue(),
                                mime_type=image_file.type
                            ),
                            SYSTEM_PROMPT + "\n" + question
                        ]
                    )

                    st.markdown(response.text)

                except Exception as e:
                    st.error(str(e))


# =========================================================
# PDF ASSISTANT
# =========================================================

elif st.session_state.page == "PDF Assistant":

    hero("PDF Assistant", "Convert your documents into useful knowledge.")

    pdf = st.file_uploader("Upload PDF", type=["pdf"])

    task = st.selectbox(
        "Select task",
        [
            "Summarize document",
            "Make detailed notes",
            "Create questions and answers",
            "Explain difficult topics",
            "Create revision sheet",
            "Find important definitions"
        ]
    )

    if pdf and st.button("Process PDF"):

        if PdfReader is None:
            st.error("Install pypdf.")
        else:
            try:
                reader = PdfReader(io.BytesIO(pdf.getvalue()))

                content = ""

                for page in reader.pages[:80]:
                    content += (page.extract_text() or "") + "\n"

                prompt = f"""
                Task: {task}
                Analyze this document carefully:
                {content[:40000]}
                """

                answer = answer_box(prompt)

                if answer:
                    download_answer(answer, "pdf_notes.txt")

            except Exception as e:
                st.error(str(e))


# =========================================================
# WEB RESEARCH
# =========================================================

elif st.session_state.page == "Web Research":

    hero("Web Research", "Search the web and build organized research reports.")

    query = st.text_input("Research topic")

    depth = st.selectbox("Search depth", ["basic","advanced"])

    number = st.slider("Results", 3, 10, 6)

    if st.button("Search Web"):

        if not TAVILY_KEY:
            st.error("Configure TAVILY_API_KEY.")
        else:
            try:
                response = requests.post(
                    "https://api.tavily.com/search",
                    json={
                        "api_key": TAVILY_KEY,
                        "query": query,
                        "search_depth": depth,
                        "max_results": number,
                        "include_answer": True
                    },
                    timeout=35
                )

                response.raise_for_status()
                data = response.json()

                if data.get("answer"):
                    st.markdown("### Quick Answer")
                    st.write(data["answer"])

                for item in data.get("results", []):

                    with st.container(border=True):
                        st.markdown("**" + item.get("title","Source") + "**")
                        st.write(item.get("content","")[:1200])

                        if item.get("url"):
                            st.markdown(
                                f"[Open source]({item['url']})"
                            )

            except Exception as e:
                st.error(str(e))


# =========================================================
# IMAGE STUDIO
# =========================================================

elif st.session_state.page == "Image Studio":

    hero("Image Studio", "Turn your imagination into original artwork.")

    prompt = st.text_area(
        "Image description",
        height=140,
        placeholder="Describe your dream image..."
    )

    style = st.selectbox(
        "Art style",
        [
            "Cinematic",
            "Photorealistic",
            "Anime",
            "3D Render",
            "Digital Art",
            "Fantasy",
            "Minimal Poster"
        ]
    )

    ratio = st.selectbox(
        "Image ratio",
        ["Square 1:1","Landscape 16:9","Portrait 9:16"]
    )

    if st.button("Generate Image"):

        if not CF_TOKEN or not CF_ACCOUNT:
            st.error("Configure Cloudflare API credentials.")
        else:
            try:
                dimensions = {
                    "Square 1:1": (1024,1024),
                    "Landscape 16:9": (1024,576),
                    "Portrait 9:16": (576,1024)
                }

                width, height = dimensions[ratio]

                url = (
                    "https://api.cloudflare.com/client/v4/accounts/"
                    + CF_ACCOUNT
                    + "/ai/run/@cf/black-forest-labs/flux-1-schnell"
                )

                response = requests.post(
                    url,
                    headers={
                        "Authorization": "Bearer " + CF_TOKEN
                    },
                    json={
                        "prompt": prompt + ", " + style + ", high detail",
                        "width": width,
                        "height": height,
                        "num_steps": 4
                    },
                    timeout=120
                )

                response.raise_for_status()

                if "image" in response.headers.get("content-type",""):
                    image_bytes = response.content
                else:
                    data = response.json()
                    encoded = data.get("result",{}).get("image")

                    if not encoded:
                        raise Exception(str(data)[:1000])

                    image_bytes = base64.b64decode(encoded)

                st.image(image_bytes, use_container_width=True)

                st.download_button(
                    "Download Image",
                    image_bytes,
                    "nextgen_image.png",
                    "image/png"
                )

            except Exception as e:
                st.error(str(e))


# =========================================================
# VOICE STUDIO
# =========================================================

elif st.session_state.page == "Voice Studio":

    hero("Voice Studio", "Speak, transcribe and ask AI.")

    st.info(
        "This version supports recording and transcription. "
        "Continuous live two-way voice calling requires a real-time audio service."
    )

    audio = st.audio_input("Record your voice")

    if audio:

        st.audio(audio)

        if st.button("Transcribe"):

            if not GROQ_KEY or Groq is None:
                st.error("Configure GROQ_API_KEY and install groq.")
            else:
                try:
                    client = Groq(api_key=GROQ_KEY)

                    result = client.audio.transcriptions.create(
                        file=("recording.wav", audio.getvalue()),
                        model="whisper-large-v3-turbo",
                        response_format="text"
                    )

                    st.session_state.transcript = str(result)

                except Exception as e:
                    st.error(str(e))

    transcript = st.text_area(
        "Your transcript",
        value=st.session_state.get("transcript","")
    )

    if st.button("Ask AI") and transcript.strip():
        answer_box(transcript)


# =========================================================
# CODING LAB
# =========================================================

elif st.session_state.page == "Coding Lab":

    hero("Coding Lab", "Your AI coding companion.")

    task = st.selectbox(
        "Choose coding task",
        [
            "Build a project",
            "Fix an error",
            "Explain code",
            "Optimize code",
            "Write tests",
            "Review code"
        ]
    )

    language = st.selectbox(
        "Programming language",
        ["Python","JavaScript","HTML/CSS","C++","Java","SQL","Other"]
    )

    code = st.text_area("Code / Requirements", height=260)

    error = st.text_area("Error message (optional)")

    if st.button("Generate Code Solution"):

        prompt = f"""
        Task: {task}
        Language: {language}
        Code:
        {code}
        Error:
        {error}

        Give a clear explanation and complete code.
        """

        answer = answer_box(prompt)

        if answer:
            download_answer(answer, "coding_solution.md")


# =========================================================
# STUDY ASSISTANT
# =========================================================

elif st.session_state.page == "Study Assistant":

    hero("Study Assistant", "Your personal learning and revision workspace.")

    tab1, tab2, tab3 = st.tabs([
        "Explain Topic",
        "Practice Quiz",
        "Study Planner"
    ])

    with tab1:

        subject = st.selectbox(
            "Subject",
            ["Science","Maths","English","Social Studies","Computer","Hindi"]
        )

        grade = st.selectbox(
            "Class",
            ["Class 7","Class 8","Class 9","Class 10","Other"]
        )

        topic = st.text_input("Chapter / Topic")

        level = st.selectbox(
            "Difficulty",
            ["Easy","School Level","Advanced","Challenge"]
        )

        if st.button("Explain Topic"):

            answer_box(
                f"Teach {topic} for {grade}, subject {subject}. "
                f"Difficulty: {level}. Include examples, definitions and recap."
            )

    with tab2:

        topic = st.text_input("Quiz topic")

        count = st.slider("Questions",5,20,10)

        difficulty = st.selectbox(
            "Quiz difficulty",
            ["Easy","Medium","Hard","Mixed"]
        )

        if st.button("Create Quiz"):

            answer_box(
                f"Create {count} multiple choice questions about {topic}. "
                f"Difficulty: {difficulty}. Add answer key and explanations."
            )

    with tab3:

        subjects = st.text_input(
            "Subjects",
            "Science, Maths, English"
        )

        days = st.slider("Plan duration",3,30,7)

        hours = st.slider("Daily study time",1,8,3)

        if st.button("Create Study Plan"):

            answer = answer_box(
                f"Create a realistic {days}-day study plan for {subjects}. "
                f"{hours} study hours per day. Include revision, practice and breaks."
            )

            if answer:
                download_answer(answer,"study_plan.txt")


# =========================================================
# CHESS COACH
# =========================================================

elif st.session_state.page == "Chess Coach":

    hero(
        "Chess Coach ♟️",
        "Analyze your game, understand tactics and find stronger moves."
    )

    st.info(
        "Enter the complete moves or current FEN. "
        "AI suggestions should be checked on a legal chessboard."
    )

    side = st.radio(
        "Your side",
        ["White","Black"],
        horizontal=True
    )

    moves = st.text_area(
        "Enter chess moves",
        height=120,
        placeholder="1. e4 e5 2. Nf3 Nc6 3. Bb5 a6"
    )

    fen = st.text_input("Current FEN (optional)")

    opponent_move = st.text_input(
        "Opponent's last move (optional)"
    )

    task = st.selectbox(
        "What do you need?",
        [
            "Find strong candidate moves",
            "Understand opponent's plan",
            "Find tactical opportunities",
            "Review mistakes",
            "Learn a winning strategy",
            "Explain position simply"
        ]
    )

    if st.button("Analyze Chess Position"):

        if not moves.strip() and not fen.strip():
            st.warning("Enter moves or FEN first.")
        else:
            prompt = f"""
            Act as a chess coach.
            My side: {side}
            Moves: {moves}
            FEN: {fen}
            Opponent's last move: {opponent_move}
            Task: {task}

            Analyze carefully.
            Give candidate moves only when reasonably confident.
            Explain the idea, opponent replies and risks.
            Do not invent a forced win.
            If the position is unclear, explain what information is missing.
            """

            answer_box(prompt)

    st.markdown("""
    <div class="panel">
    <h3>♟️ Basic winning principles</h3>
    1. Control the centre.
    2. Develop your knights and bishops.
    3. Keep your king safe.
    4. Avoid leaving pieces undefended.
    5. Before every move, check your opponent's threats.
    </div>
    """, unsafe_allow_html=True)


# =========================================================
# VIDEO STUDIO
# =========================================================

elif st.session_state.page == "Video Studio":

    hero("Video Studio", "Create cinematic AI video scripts and scene prompts.")

    topic = st.text_input("Video topic")

    platform = st.selectbox(
        "Platform",
        [
            "YouTube Shorts",
            "Instagram Reels",
            "YouTube Landscape",
            "Advertisement",
            "School Presentation"
        ]
    )

    duration = st.slider("Duration (seconds)",10,180,30)

    language = st.selectbox(
        "Language",
        ["Hindi Devanagari","Hinglish","English"]
    )

    style = st.selectbox(
        "Video style",
        [
            "Cinematic",
            "Funny",
            "Emotional",
            "Educational",
            "Epic",
            "Professional"
        ]
    )

    options = st.multiselect(
        "Include in output",
        [
            "Hook",
            "Photo prompts",
            "Scene-by-scene video prompts",
            "Dialogue",
            "Voiceover",
            "Camera movement",
            "Background music",
            "Transitions",
            "Caption and hashtags"
        ],
        default=[
            "Hook",
            "Photo prompts",
            "Scene-by-scene video prompts",
            "Dialogue",
            "Voiceover"
        ]
    )

    if st.button("Create Video Blueprint") and topic.strip():

        prompt = f"""
        Create a complete video blueprint.
        Topic: {topic}
        Platform: {platform}
        Duration: {duration} seconds
        Language: {language}
        Style: {style}
        Include: {options}

        Give timed scenes, image prompts, video prompts,
        dialogues, camera movement, transitions, sound design
        and a strong ending. Make prompts easy to copy.
        """

        answer = answer_box(prompt)

        if answer:
            download_answer(answer,"video_blueprint.md")


# =========================================================
# SMART NOTES
# =========================================================

elif st.session_state.page == "Smart Notes":

    hero("Smart Notes", "Save your ideas, study notes and project plans.")

    title = st.text_input("Note title")

    content = st.text_area("Write your note", height=180)

    if st.button("Save Note"):

        if title.strip() and content.strip():

            with database() as con:
                con.execute("""
                INSERT INTO ultra_notes(title,content,created)
                VALUES(?,?,?)
                """, (
                    title,
                    content,
                    str(datetime.now())
                ))
                con.commit()

            st.success("Note saved!")
            st.rerun()

    with database() as con:
        notes = con.execute(
            "SELECT * FROM ultra_notes ORDER BY id DESC"
        ).fetchall()

    for note in notes:

        with st.expander(note[1]):

            st.write(note[2])
            st.caption(note[3])

            if st.button("Delete Note", key="note_"+str(note[0])):

                with database() as con:
                    con.execute(
                        "DELETE FROM ultra_notes WHERE id=?",
                        (note[0],)
                    )
                    con.commit()

                st.rerun()


# =========================================================
# STOCK MARKET
# =========================================================

elif st.session_state.page == "Stock Market":

    hero("Global Market Desk", "Explore stock quotes and historical price data.")

    st.warning(
        "Educational market information only. "
        "Market data can be delayed and is not investment advice."
    )

    symbol = st.text_input("Stock symbol", "AAPL").upper()

    period = st.selectbox(
        "Chart period",
        ["30 Days","90 Days","180 Days","1 Year"]
    )

    days = {
        "30 Days":30,
        "90 Days":90,
        "180 Days":180,
        "1 Year":365
    }[period]

    if st.button("Load Stock Data"):

        if not FINNHUB_KEY:
            st.error("Configure FINNHUB_API_KEY.")
        else:
            try:
                response = requests.get(
                    "https://finnhub.io/api/v1/quote",
                    params={
                        "symbol":symbol,
                        "token":FINNHUB_KEY
                    },
                    timeout=20
                )

                response.raise_for_status()
                quote = response.json()

                if not quote.get("c"):
                    raise Exception("No quote found for this ticker.")

                a,b,c,d = st.columns(4)

                a.metric("Current Price",quote["c"],quote["d"])
                b.metric("Previous Close",quote["pc"])
                c.metric("Day High",quote["h"])
                d.metric("Day Low",quote["l"])

                end = int(time.time())
                start = end - days*86400

                candle = requests.get(
                    "https://finnhub.io/api/v1/stock/candle",
                    params={
                        "symbol":symbol,
                        "resolution":"D",
                        "from":start,
                        "to":end,
                        "token":FINNHUB_KEY
                    },
                    timeout=25
                )

                candle.raise_for_status()
                data = candle.json()

                if data.get("s") == "ok" and go:

                    fig = go.Figure(
                        data=[
                            go.Candlestick(
                                x=[
                                    datetime.fromtimestamp(x)
                                    for x in data["t"]
                                ],
                                open=data["o"],
                                high=data["h"],
                                low=data["l"],
                                close=data["c"]
                            )
                        ]
                    )

                    fig.update_layout(
                        template="plotly_dark",
                        height=450,
                        xaxis_rangeslider_visible=False
                    )

                    st.plotly_chart(
                        fig,
                        use_container_width=True
                    )

                else:
                    st.info("Historical chart data unavailable.")

            except Exception as e:
                st.error(str(e))


# =========================================================
# MARKET ACADEMY
# =========================================================

elif st.session_state.page == "Market Academy":

    hero("Market Academy", "Understand financial markets step by step.")

    topic = st.selectbox(
        "Choose lesson",
        [
            "What is a stock?",
            "How stock exchanges work",
            "Candlestick charts",
            "Market capitalization",
            "Risk and diversification",
            "Bull and bear markets",
            "Index funds and ETFs",
            "How to read a company profile",
            "Common market mistakes"
        ]
    )

    level = st.selectbox(
        "Learning level",
        ["Beginner","Intermediate","Advanced"]
    )

    if st.button("Start Lesson"):

        answer_box(
            f"Teach {topic} at {level} level. "
            "Include examples, glossary, recap and quiz. "
            "Keep this educational, not personalized financial advice."
        )


# =========================================================
# AI SKILL CENTER
# =========================================================

elif st.session_state.page == "AI Skill Center":

    hero("AI Skill Center", "Check your connected tools and available capabilities.")

    integrations = [
        ("Groq AI",bool(GROQ_KEY)),
        ("Gemini AI",bool(GEMINI_KEY)),
        ("Tavily Web Search",bool(TAVILY_KEY)),
        ("Finnhub Market Data",bool(FINNHUB_KEY)),
        ("Cloudflare Image Generation",bool(CF_TOKEN and CF_ACCOUNT))
    ]

    for name, ready in integrations:

        a,b = st.columns([4,1])

        a.markdown("**"+name+"**")

        b.success("READY") if ready else b.warning("NOT SET")

    st.markdown("### Platform capabilities")

    st.write("""
    - AI conversations
    - Persistent chat history
    - Image understanding
    - PDF analysis
    - Web research
    - Image generation
    - Voice transcription
    - Text-to-speech
    - Coding assistance
    - Study assistance
    - Chess coaching
    - Video prompt generation
    - Smart notes
    - Stock market data
    """)


# =========================================================
# SETTINGS
# =========================================================

elif st.session_state.page == "Settings":

    hero("Settings", "Manage your NEXTGEN AI workspace.")

    st.selectbox(
        "Default AI provider",
        ["Auto","Groq","Gemini"],
        key="provider_settings"
    )

    st.markdown("### Database")

    st.code(DB)

    st.markdown("### API key safety")

    st.info("""
    Store keys in Streamlit Cloud Secrets or local environment variables.
    Never publish API keys in GitHub or paste them into chat.
    """)

    st.markdown("### Clear ULTRA data")

    confirm = st.checkbox(
        "I understand that this deletes ULTRA chats, notes and watchlist."
    )

    if st.button("Clear ULTRA Data",disabled=not confirm):

        with database() as con:
            for table in [
                "ultra_messages",
                "ultra_chats",
                "ultra_notes",
                "ultra_watchlist"
            ]:
                con.execute(f"DELETE FROM {table}")

            con.commit()

        st.session_state.chat_id = new_chat()
        st.success("ULTRA data cleared. Older app tables were not touched.")


# =========================================================
# ABOUT
# =========================================================

elif st.session_state.page == "About":

    hero("About NEXTGEN AI", "One platform. Endless possibilities.")

    st.markdown("""
    <div class="panel">
        <div style="color:#9caeff;font-weight:800;letter-spacing:3px">
            CREATED BY ARAV
        </div>
        <h1>🚀 NEXTGEN AI</h1>
        <h3>Your Creative Universe</h3>
        <p>
        NEXTGEN AI is created and developed by Arav,
        a Class 7 student and young technology enthusiast from India.
        </p>
        <p>
        Built using Python, Streamlit, SQLite and integrated AI services.
        </p>
    </div>
    """, unsafe_allow_html=True)

    st.caption(
        "The underlying AI models are supplied by external providers. "
        "This project does not claim to have trained those models."
    )


# ---------------- FOOTER ----------------

st.divider()

st.markdown(
    "<center style='color:#8995b4'>"
    "🚀 NEXTGEN AI ULTRA · Built by Arav · 2026"
    "<br>AI can make mistakes. Verify important information."
    "</center>",
    unsafe_allow_html=True
)
