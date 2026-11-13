
import os
import io
import re
import json
import sqlite3
import hashlib
import secrets
from datetime import datetime
from urllib.parse import quote

import streamlit as st
import requests
from groq import Groq
from PIL import Image
from pypdf import PdfReader
from gtts import gTTS

try:
    from google import genai
    from google.genai import types
except ImportError:
    genai = None
    types = None


# =====================================================
# CONFIG
# =====================================================

st.set_page_config(
    page_title="NEXTGEN AI",
    page_icon="🚀",
    layout="wide",
    initial_sidebar_state="expanded"
)

DB = "nextgen_users.db"

def get_secret(name, default=""):
    try:
        value = st.secrets.get(name, default)
        if value:
            return value
    except Exception:
        pass
    return os.getenv(name, default)


GROQ_KEY = get_secret("GROQ_API_KEY")
GEMINI_KEY = get_secret("GEMINI_API_KEY")
TAVILY_KEY = get_secret("TAVILY_API_KEY")
FINNHUB_KEY = get_secret("FINNHUB_API_KEY")

# Optional Cloudflare configuration.
CF_ACCOUNT_ID = get_secret("CLOUDFLARE_ACCOUNT_ID")
CF_API_TOKEN = get_secret("CLOUDFLARE_API_TOKEN")
CF_IMAGE_MODEL = get_secret(
    "CLOUDFLARE_IMAGE_MODEL",
    "@cf/black-forest-labs/flux-1-schnell"
)
CF_VIDEO_ENDPOINT = get_secret("CLOUDFLARE_VIDEO_ENDPOINT")
LIVE_VOICE_URL = get_secret(
    "LIVE_VOICE_URL",
    "http://localhost:5173"
)

GROQ_MODEL = "llama-3.3-70b-versatile"
GEMINI_MODEL = "gemini-2.5-flash"


# =====================================================
# DATABASE
# =====================================================

def db():
    return sqlite3.connect(DB, check_same_thread=False)


def init_db():
    con = db()
    cur = con.cursor()

    cur.execute("""
        CREATE TABLE IF NOT EXISTS users(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE,
            password TEXT,
            created_at TEXT
        )
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS conversations(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            title TEXT,
            created_at TEXT,
            updated_at TEXT
        )
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS messages(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            conversation_id INTEGER,
            role TEXT,
            content TEXT,
            created_at TEXT
        )
    """)

    con.commit()
    con.close()


init_db()


def hash_password(password):
    salt = secrets.token_hex(16)
    value = hashlib.pbkdf2_hmac(
        "sha256",
        password.encode(),
        salt.encode(),
        200000
    ).hex()
    return salt + "$" + value


def verify_password(password, stored):
    try:
        salt, hashed = stored.split("$")
        value = hashlib.pbkdf2_hmac(
            "sha256",
            password.encode(),
            salt.encode(),
            200000
        ).hex()
        return secrets.compare_digest(value, hashed)
    except Exception:
        return False


def register(username, password):
    con = db()
    try:
        con.execute(
            "INSERT INTO users(username,password,created_at) VALUES(?,?,?)",
            (
                username,
                hash_password(password),
                datetime.now().isoformat()
            )
        )
        con.commit()
        return True
    except sqlite3.IntegrityError:
        return False
    finally:
        con.close()


def authenticate(username, password):
    con = db()
    row = con.execute(
        "SELECT id,password FROM users WHERE username=?",
        (username,)
    ).fetchone()
    con.close()

    if row and verify_password(password, row[1]):
        return row[0]
    return None


def new_conversation(user_id, title="New Chat"):
    con = db()
    cur = con.execute("""
        INSERT INTO conversations(user_id,title,created_at,updated_at)
        VALUES(?,?,?,?)
    """, (
        user_id,
        title,
        datetime.now().isoformat(),
        datetime.now().isoformat()
    ))
    cid = cur.lastrowid
    con.commit()
    con.close()
    return cid


def list_conversations(user_id):
    con = db()
    rows = con.execute("""
        SELECT id,title,updated_at
        FROM conversations
        WHERE user_id=?
        ORDER BY updated_at DESC
    """, (user_id,)).fetchall()
    con.close()
    return rows


def save_message(cid, role, content):
    con = db()
    con.execute("""
        INSERT INTO messages(conversation_id,role,content,created_at)
        VALUES(?,?,?,?)
    """, (
        cid,
        role,
        content,
        datetime.now().isoformat()
    ))
    con.execute(
        "UPDATE conversations SET updated_at=? WHERE id=?",
        (datetime.now().isoformat(), cid)
    )
    con.commit()
    con.close()


def read_messages(cid):
    con = db()
    rows = con.execute("""
        SELECT role,content
        FROM messages
        WHERE conversation_id=?
        ORDER BY id
    """, (cid,)).fetchall()
    con.close()
    return rows


def delete_chat(cid):
    con = db()
    con.execute(
        "DELETE FROM messages WHERE conversation_id=?",
        (cid,)
    )
    con.execute(
        "DELETE FROM conversations WHERE id=?",
        (cid,)
    )
    con.commit()
    con.close()


# =====================================================
# SESSION
# =====================================================

defaults = {
    "logged_in": False,
    "user_id": None,
    "username": "Guest",
    "cid": None,
    "deep": False,
    "voice_reply": False,
    "pending_prompt": None
}

for key, value in defaults.items():
    if key not in st.session_state:
        st.session_state[key] = value


# =====================================================
# DESIGN
# =====================================================

st.markdown("""
<style>
.stApp {
    background:
    radial-gradient(circle at 10% 10%,#152b4a,transparent 35%),
    radial-gradient(circle at 90% 90%,#30183f,transparent 35%),
    #080b14;
    color: #f4f6ff;
}
[data-testid="stSidebar"] {
    background: #0d1423;
    border-right: 1px solid #263a59;
}
.main-title {
    font-size: 38px;
    font-weight: 900;
    background: linear-gradient(90deg,#55d9ff,#a78bfa,#ff76c9);
    -webkit-background-clip: text;
    color: transparent;
}
.subtle {
    color: #9caac5;
}
.feature-card {
    background: linear-gradient(145deg,#17243a,#101827);
    border: 1px solid #2c405f;
    border-radius: 18px;
    padding: 20px;
    min-height: 135px;
    margin-bottom: 12px;
}
.stButton button {
    background: linear-gradient(100deg,#194d79,#47306e);
    color: white;
    border: 1px solid #395477;
    border-radius: 12px;
    font-weight: 650;
}
.stButton button:hover {
    border-color: #5ad8ff;
    color: white;
}
.stTextInput input,.stTextArea textarea {
    background: #111c30;
    color: white;
    border-radius: 12px;
}
div[data-testid="stChatInput"] {
    border: 1px solid #526b94;
    border-radius: 20px;
    background: #111a2b;
}
div[data-testid="stChatMessage"] {
    background: transparent;
}
</style>
""", unsafe_allow_html=True)


# =====================================================
# GROQ AI
# =====================================================

def groq_client():
    if not GROQ_KEY:
        raise ValueError("GROQ_API_KEY missing in Streamlit Secrets.")
    return Groq(api_key=GROQ_KEY)


def should_search(query):
    words = [
        "latest", "today", "current", "now", "news",
        "weather", "stock", "price", "market", "live",
        "2026", "recent", "आज", "अभी", "ताजा",
        "लेटेस्ट", "मौसम", "खबर", "शेयर", "भाव"
    ]
    q = query.lower()
    return any(w in q for w in words)


def web_search(query):
    if not TAVILY_KEY:
        return "Web search is unavailable: TAVILY_API_KEY missing."

    try:
        response = requests.post(
            "https://api.tavily.com/search",
            json={
                "api_key": TAVILY_KEY,
                "query": query,
                "search_depth": "advanced",
                "max_results": 5,
                "include_answer": True
            },
            timeout=25
        )
        response.raise_for_status()
        data = response.json()

        results = []

        if data.get("answer"):
            results.append(data["answer"])

        for item in data.get("results", []):
            results.append(
                f"{item.get('title')}\n"
                f"{item.get('content')}\n"
                f"Source: {item.get('url')}"
            )

        return "\n\n".join(results) or "No search results."

    except Exception as e:
        return f"Search error: {e}"


def ai_reply(history, deep=False, force_search=False):
    if not history:
        raise ValueError("No messages to send.")

    query = history[-1]["content"]
    search_context = ""

    if force_search or should_search(query):
        search_context = web_search(query)

    system = """
You are NEXTGEN AI, a friendly intelligent AI assistant.

Instructions:
- Respond in the user's language.
- Use Hindi Devanagari for Hindi.
- Give accurate and useful answers.
- Do not invent sources or live facts.
- Explain technical tasks step by step.
- Be clear when a feature is unavailable.
"""

    if deep:
        system += """
Use Deep Analysis mode:
- Examine assumptions.
- Compare possible approaches.
- Give a structured explanation and conclusion.
- Do not reveal private hidden reasoning.
"""

    if search_context:
        system += "\n\nWEB SEARCH RESULTS:\n" + search_context

    messages = [{"role": "system", "content": system}]
    messages.extend(history[-20:])

    return groq_client().chat.completions.create(
        model=GROQ_MODEL,
        messages=messages,
        stream=True,
        temperature=0.6,
        max_tokens=3000
    )


# =====================================================
# PDF
# =====================================================

def pdf_text(file):
    try:
        reader = PdfReader(io.BytesIO(file.getvalue()))
        return "\n".join(
            page.extract_text() or ""
            for page in reader.pages
        )[:30000]
    except Exception as e:
        return f"PDF error: {e}"


def ask_single(prompt, context=""):
    result = groq_client().chat.completions.create(
        model=GROQ_MODEL,
        messages=[
            {
                "role": "system",
                "content": "Be accurate. Use the supplied context when relevant."
            },
            {
                "role": "user",
                "content": prompt + "\n\n" + context
            }
        ]
    )
    return result.choices[0].message.content


# =====================================================
# GEMINI VISION
# =====================================================

def vision(image, question):
    if not GEMINI_KEY or genai is None:
        return "Gemini Vision is not configured."

    client = genai.Client(api_key=GEMINI_KEY)

    buffer = io.BytesIO()
    image.save(buffer, format="JPEG")

    response = client.models.generate_content(
        model=GEMINI_MODEL,
        contents=[
            question,
            types.Part.from_bytes(
                data=buffer.getvalue(),
                mime_type="image/jpeg"
            )
        ]
    )
    return response.text or "No response."


# =====================================================
# VOICE
# =====================================================

def transcribe(audio_bytes):
    result = groq_client().audio.transcriptions.create(
        file=("recording.wav", audio_bytes),
        model="whisper-large-v3-turbo",
        response_format="text"
    )
    return str(result)


def speech(text):
    buffer = io.BytesIO()
    gTTS(text=text[:4000], lang="hi").write_to_fp(buffer)
    buffer.seek(0)
    return buffer


# =====================================================
# CLOUDFLARE IMAGE
# =====================================================

def cloudflare_image(prompt):
    if not CF_ACCOUNT_ID or not CF_API_TOKEN:
        raise ValueError(
            "Add CLOUDFLARE_ACCOUNT_ID and CLOUDFLARE_API_TOKEN "
            "to Streamlit Secrets first."
        )

    url = (
        "https://api.cloudflare.com/client/v4/accounts/"
        + CF_ACCOUNT_ID
        + "/ai/run/"
        + quote(CF_IMAGE_MODEL, safe="@/-")
    )

    response = requests.post(
        url,
        headers={
            "Authorization": f"Bearer {CF_API_TOKEN}"
        },
        json={
            "prompt": prompt
        },
        timeout=180
    )

    response.raise_for_status()

    content_type = response.headers.get("content-type", "")

    if "image/" in content_type:
        return response.content

    data = response.json()

    if data.get("success") is False:
        raise ValueError(str(data.get("errors")))

    result = data.get("result", {})

    if result.get("image"):
        import base64
        return base64.b64decode(result["image"])

    raise ValueError("Cloudflare did not return an image.")


# =====================================================
# CLOUDFLARE VIDEO
# =====================================================

def cloudflare_video(prompt):
    if not CF_VIDEO_ENDPOINT:
        raise ValueError(
            "CLOUDFLARE_VIDEO_ENDPOINT is not configured. "
            "Add a supported video-generation endpoint to Secrets."
        )

    if not CF_API_TOKEN:
        raise ValueError("CLOUDFLARE_API_TOKEN is missing.")

    response = requests.post(
        CF_VIDEO_ENDPOINT,
        headers={
            "Authorization": f"Bearer {CF_API_TOKEN}",
            "Content-Type": "application/json"
        },
        json={"prompt": prompt},
        timeout=60
    )

    response.raise_for_status()
    return response.json()


# =====================================================
# AUTHENTICATION
# =====================================================

def auth_page():
    st.markdown(
        '<div class="main-title">🚀 NEXTGEN AI</div>',
        unsafe_allow_html=True
    )
    st.write("One Platform. Endless Possibilities.")

    login, signup = st.tabs(["Login", "Create Account"])

    with login:
        username = st.text_input("Username", key="login_user")
        password = st.text_input(
            "Password",
            type="password",
            key="login_pass"
        )

        if st.button("Login", use_container_width=True):
            uid = authenticate(username, password)

            if uid:
                st.session_state.logged_in = True
                st.session_state.user_id = uid
                st.session_state.username = username
                st.rerun()
            else:
                st.error("Incorrect username or password.")

    with signup:
        username = st.text_input("New username", key="new_user")
        password = st.text_input(
            "New password",
            type="password",
            key="new_pass"
        )

        if st.button("Create Account", use_container_width=True):
            if len(username.strip()) < 3:
                st.error("Username must have at least 3 characters.")
            elif len(password) < 8:
                st.error("Password must have at least 8 characters.")
            elif register(username.strip(), password):
                st.success("Account created. Now login.")
            else:
                st.error("Username already exists.")

    if st.button("Continue as Guest", use_container_width=True):
        st.session_state.logged_in = True
        st.session_state.user_id = None
        st.session_state.username = "Guest"
        st.rerun()


if not st.session_state.logged_in:
    auth_page()
    st.stop()


# =====================================================
# CONVERSATION
# =====================================================

if st.session_state.user_id and st.session_state.cid is None:
    st.session_state.cid = new_conversation(
        st.session_state.user_id
    )


# =====================================================
# SIDEBAR
# =====================================================

with st.sidebar:
    st.markdown(
        '<div class="main-title">🚀 NEXTGEN AI</div>',
        unsafe_allow_html=True
    )

    st.caption("Your Creative Universe")
    st.write("👤 " + st.session_state.username)

    if st.button("＋ New Chat", use_container_width=True):
        if st.session_state.user_id:
            st.session_state.cid = new_conversation(
                st.session_state.user_id
            )
        else:
            st.session_state.cid = None
        st.rerun()

    if st.session_state.user_id:
        chats = list_conversations(st.session_state.user_id)

        if chats:
            labels = {
                f"{title} ({date[:10]})": cid
                for cid, title, date in chats
            }

            current_index = next(
                (
                    i for i, cid in enumerate(labels.values())
                    if cid == st.session_state.cid
                ),
                0
            )

            selected = st.selectbox(
                "Recent conversations",
                list(labels.keys()),
                index=current_index
            )

            selected_id = labels[selected]

            if selected_id != st.session_state.cid:
                st.session_state.cid = selected_id
                st.rerun()

    st.divider()

    page = st.radio(
        "MAIN MENU",
        [
            "Dashboard",
            "AI Chat",
            "AI Tool Center",
            "AI Vision",
            "PDF Assistant",
            "AI Image Studio",
            "Voice Studio",
            "Live Voice",
            "Stock Market Explorer",
            "Video Prompt Studio",
            "Chat History",
            "About"
        ]
    )

    st.divider()

    st.session_state.deep = st.toggle(
        "🧠 Deep Analysis Mode",
        value=st.session_state.deep
    )

    st.session_state.voice_reply = st.toggle(
        "🔊 Spoken AI Replies",
        value=st.session_state.voice_reply
    )

    st.caption("Automatic web search is enabled when relevant.")

    if st.button("Logout", use_container_width=True):
        st.session_state.logged_in = False
        st.session_state.user_id = None
        st.session_state.username = "Guest"
        st.session_state.cid = None
        st.rerun()


# =====================================================
# HEADER
# =====================================================

st.markdown(
    '<div class="main-title">NEXTGEN AI</div>',
    unsafe_allow_html=True
)

st.markdown(
    '<p class="subtle">Your intelligent AI workspace</p>',
    unsafe_allow_html=True
)

st.divider()


# =====================================================
# DASHBOARD
# =====================================================

if page == "Dashboard":
    st.subheader("Welcome to NEXTGEN AI 👋")

    cards = [
        ("💬 AI Chat", "Ask questions and get intelligent answers."),
        ("👁️ AI Vision", "Understand and analyze images."),
        ("📄 PDF Assistant", "Summarize and ask questions about PDFs."),
        ("🎙️ Voice Studio", "Record, transcribe and hear responses."),
        ("📞 Live Voice", "Open real-time Cloudflare voice interface."),
        ("🎨 Image Studio", "Generate actual images with Cloudflare."),
        ("📈 Stock Explorer", "Explore available market quotes."),
        ("🎬 Video Studio", "Build video prompts and storyboards.")
    ]

    cols = st.columns(2)

    for i, (title, description) in enumerate(cards):
        with cols[i % 2]:
            st.markdown(
                f"""
                <div class="feature-card">
                    <h3>{title}</h3>
                    <p>{description}</p>
                </div>
                """,
                unsafe_allow_html=True
            )


# =====================================================
# AI CHAT
# =====================================================

elif page == "AI Chat":
    st.subheader("💬 NEXTGEN AI Chat")

    st.caption(
        "Attach files, ask questions, and get streamed responses."
    )

    if st.session_state.deep:
        st.info("Deep Analysis Mode is active.")

    if st.session_state.cid:
        history = read_messages(st.session_state.cid)
    else:
        history = []

    for role, content in history:
        with st.chat_message(role):
            st.markdown(content)

    audio = st.audio_input("🎙️ Record a message")

    if audio and st.button("Transcribe voice"):
        try:
            with st.spinner("Transcribing..."):
                st.session_state.pending_prompt = transcribe(
                    audio.getvalue()
                )
            st.success("Voice converted to text.")
            st.write(st.session_state.pending_prompt)
        except Exception as e:
            st.error(str(e))

    uploaded = st.file_uploader(
        "📎 Attach PDF, image or text file",
        type=["pdf", "png", "jpg", "jpeg", "webp", "txt", "csv"],
        accept_multiple_files=True
    )

    prompt = st.chat_input("Message NEXTGEN AI...")

    if prompt or st.session_state.pending_prompt:
        query = prompt or st.session_state.pending_prompt
        st.session_state.pending_prompt = None

        context_parts = []
        images = []

        for file in uploaded or []:
            name = file.name.lower()

            if name.endswith(".pdf"):
                context_parts.append(
                    f"PDF {file.name}:\n{pdf_text(file)}"
                )

            elif name.endswith((".png", ".jpg", ".jpeg", ".webp")):
                try:
                    images.append(
                        (file.name, Image.open(file).convert("RGB"))
                    )
                except Exception:
                    pass

            elif name.endswith((".txt", ".csv")):
                context_parts.append(
                    f"File {file.name}:\n"
                    + file.getvalue().decode(
                        "utf-8",
                        errors="ignore"
                    )[:15000]
                )

        if context_parts:
            query += "\n\nATTACHED CONTENT:\n" + "\n".join(
                context_parts
            )

        if images:
            query += "\n\nImage attachments: " + ", ".join(
                name for name, _ in images
            )

        if not query.strip() and not images:
            st.warning("Enter a message or attach a file.")
            st.stop()

        if images:
            for name, image in images:
                st.image(image, caption=name, width=300)
                with st.spinner("Analyzing image..."):
                    try:
                        result = vision(
                            image,
                            query or "Describe this image."
                        )
                        query += "\n\nIMAGE ANALYSIS:\n" + result
                    except Exception as e:
                        query += "\n\nImage analysis error: " + str(e)

        if st.session_state.cid is None:
            st.warning(
                "Guest chats are temporary. Create an account "
                "to save chat history."
            )
            st.stop()

        if not history:
            con = db()
            con.execute(
                "UPDATE conversations SET title=? WHERE id=?",
                (query[:45], st.session_state.cid)
            )
            con.commit()
            con.close()

        save_message(st.session_state.cid, "user", query)

        with st.chat_message("user"):
            st.markdown(query)

        updated = [
            {"role": r, "content": c}
            for r, c in read_messages(st.session_state.cid)
        ]

        with st.chat_message("assistant"):
            placeholder = st.empty()
            answer = ""

            try:
                with st.spinner("NEXTGEN AI is thinking..."):
                    stream = ai_reply(
                        updated,
                        deep=st.session_state.deep
                    )

                    for chunk in stream:
                        delta = chunk.choices[0].delta.content
                        if delta:
                            answer += delta
                            placeholder.markdown(answer + " ▌")

                placeholder.markdown(answer)

                save_message(
                    st.session_state.cid,
                    "assistant",
                    answer
                )

                if st.session_state.voice_reply:
                    try:
                        st.audio(
                            speech(answer),
                            format="audio/mp3"
                        )
                    except Exception as e:
                        st.warning("Speech error: " + str(e))

            except Exception as e:
                st.error("AI response failed.")
                st.code(str(e))


# =====================================================
# AI TOOL CENTER
# =====================================================

elif page == "AI Tool Center":
    st.subheader("🧰 AI Tool Center")

    tool = st.selectbox(
        "Choose tool",
        [
            "Text Summarizer",
            "Email Writer",
            "Essay Writer",
            "Code Helper",
            "Translator",
            "Study Assistant",
            "Idea Generator",
            "Grammar Corrector"
        ]
    )

    content = st.text_area("Enter your content", height=180)

    if st.button("Generate"):
        if content.strip():
            instructions = {
                "Text Summarizer": "Summarize the content.",
                "Email Writer": "Write a professional email.",
                "Essay Writer": "Write a structured essay.",
                "Code Helper": "Help with the code and explain it.",
                "Translator": "Translate the text accurately.",
                "Study Assistant": "Explain for a school student.",
                "Idea Generator": "Generate creative ideas.",
                "Grammar Corrector": "Correct grammar and spelling."
            }

            with st.spinner("Generating..."):
                try:
                    st.markdown(
                        ask_single(
                            instructions[tool],
                            content
                        )
                    )
                except Exception as e:
                    st.error(str(e))
        else:
            st.warning("Enter content first.")


# =====================================================
# AI VISION
# =====================================================

elif page == "AI Vision":
    st.subheader("👁️ AI Vision")

    file = st.file_uploader(
        "Upload image",
        type=["png", "jpg", "jpeg", "webp"]
    )

    question = st.text_area(
        "Ask about the image",
        value="Describe this image."
    )

    if file:
        image = Image.open(file).convert("RGB")
        st.image(image, use_container_width=True)

        if st.button("Analyze Image"):
            with st.spinner("Analyzing..."):
                try:
                    st.markdown(vision(image, question))
                except Exception as e:
                    st.error(str(e))


# =====================================================
# PDF ASSISTANT
# =====================================================

elif page == "PDF Assistant":
    st.subheader("📄 PDF Assistant")

    file = st.file_uploader("Upload PDF", type=["pdf"])

    if file:
        content = pdf_text(file)

        if content.startswith("PDF error"):
            st.error(content)
        else:
            st.success(
                f"PDF loaded. {len(content)} characters extracted."
            )

            task = st.selectbox(
                "Action",
                [
                    "Summarize",
                    "Explain",
                    "Important Points",
                    "Create Questions",
                    "Ask a Question"
                ]
            )

            question = st.text_area("Your question")

            if st.button("Process PDF"):
                instruction = {
                    "Summarize": "Summarize this PDF.",
                    "Explain": "Explain this PDF simply.",
                    "Important Points": "List important points.",
                    "Create Questions": "Create questions and answers.",
                    "Ask a Question": question
                }[task]

                with st.spinner("Processing..."):
                    try:
                        st.markdown(
                            ask_single(
                                instruction,
                                content[:25000]
                            )
                        )
                    except Exception as e:
                        st.error(str(e))


# =====================================================
# AI IMAGE STUDIO
# =====================================================

elif page == "AI Image Studio":
    st.subheader("🎨 AI Image Studio")

    prompt = st.text_area(
        "Describe the image you want to generate",
        height=120
    )

    ratio = st.selectbox(
        "Aspect ratio",
        ["1:1", "16:9", "9:16"]
    )

    if st.button("Generate Actual Image"):
        if not prompt.strip():
            st.warning("Enter an image prompt.")
        else:
            final_prompt = (
                prompt
                + f". Composition suitable for {ratio} aspect ratio."
            )

            try:
                with st.spinner("Generating image with Cloudflare..."):
                    image_bytes = cloudflare_image(final_prompt)

                st.image(
                    image_bytes,
                    caption="Generated by Cloudflare Workers AI",
                    use_container_width=True
                )

                st.download_button(
                    "Download Image",
                    data=image_bytes,
                    file_name="nextgen_image.png",
                    mime="image/png"
                )

            except Exception as e:
                st.error(str(e))


# =====================================================
# VOICE STUDIO
# =====================================================

elif page == "Voice Studio":
    st.subheader("🎙️ Voice Studio")

    audio = st.audio_input("Record your voice")

    if audio and st.button("Transcribe"):
        try:
            with st.spinner("Transcribing..."):
                transcript = transcribe(audio.getvalue())

            st.session_state.voice_transcript = transcript

        except Exception as e:
            st.error(str(e))

    transcript = st.session_state.get(
        "voice_transcript",
        ""
    )

    if transcript:
        st.text_area(
            "Recognized speech",
            value=transcript,
            height=100
        )

        if st.button("Ask AI"):
            try:
                answer = ask_single(
                    "Respond to this voice message:",
                    transcript
                )

                st.markdown(answer)

                st.audio(
                    speech(answer),
                    format="audio/mp3"
                )

            except Exception as e:
                st.error(str(e))


# =====================================================
# LIVE VOICE
# =====================================================

elif page == "Live Voice":
    st.subheader("📞 NEXTGEN AI Live Voice")

    st.write(
        "Start the separate Cloudflare real-time voice interface."
    )

    st.info(
        "The Live Voice Worker and React app must be deployed "
        "separately before this feature can connect."
    )

    st.link_button(
        "🚀 Open NEXTGEN AI Live Voice",
        LIVE_VOICE_URL
    )

    st.caption(
        "Configure LIVE_VOICE_URL in Streamlit Secrets "
        "with your deployed Cloudflare voice application URL."
    )


# =====================================================
# STOCK MARKET
# =====================================================

elif page == "Stock Market Explorer":
    st.subheader("📈 Stock Market Explorer")

    st.caption("Educational information, not investment advice.")

    symbol = st.text_input("Stock symbol", "AAPL")

    if st.button("Get Quote"):
        if not FINNHUB_KEY:
            st.error("FINNHUB_API_KEY missing.")
        else:
            try:
                response = requests.get(
                    "https://finnhub.io/api/v1/quote",
                    params={
                        "symbol": symbol.upper(),
                        "token": FINNHUB_KEY
                    },
                    timeout=15
                )
                response.raise_for_status()
                data = response.json()

                if not data.get("c"):
                    st.warning("No quote available.")
                else:
                    previous = data["pc"]
                    change = data["c"] - previous

                    a, b, c = st.columns(3)

                    a.metric("Current Price", data["c"])
                    b.metric("Previous Close", previous)
                    c.metric(
                        "Change",
                        round(change, 2),
                        round(
                            change / previous * 100,
                            2
                        ) if previous else None
                    )

                    st.json(data)

            except Exception as e:
                st.error(str(e))


# =====================================================
# VIDEO PROMPT STUDIO
# =====================================================

elif page == "Video Prompt Studio":
    st.subheader("🎬 Video Prompt Studio")

    concept = st.text_area(
        "Video concept",
        height=130
    )

    duration = st.selectbox(
        "Duration",
        ["10 seconds", "20 seconds", "30 seconds",
         "60 seconds", "90 seconds"]
    )

    ratio = st.selectbox(
        "Ratio",
        ["9:16", "16:9", "1:1"]
    )

    if st.button("Generate Storyboard"):
        if concept.strip():
            prompt = f"""
Create a professional video storyboard.

Concept: {concept}
Duration: {duration}
Ratio: {ratio}

Give:
- Scene breakdown
- Image prompts
- Video prompts
- Camera movement
- Dialogue
- Voiceover
- Sound effects
- Background music
- Editing directions
- Character continuity
"""
            try:
                with st.spinner("Creating storyboard..."):
                    st.markdown(ask_single(prompt))
            except Exception as e:
                st.error(str(e))

    st.divider()
    st.subheader("Actual Video Generation")

    video_prompt = st.text_area(
        "Video generation prompt",
        key="actual_video_prompt"
    )

    if st.button("Try Cloudflare Video Generation"):
        try:
            result = cloudflare_video(video_prompt)
            st.json(result)
            st.info(
                "Check the returned job status or video URL. "
                "The endpoint may require additional polling."
            )
        except Exception as e:
            st.error(str(e))


# =====================================================
# CHAT HISTORY
# =====================================================

elif page == "Chat History":
    st.subheader("🗂️ Chat History")

    if not st.session_state.user_id:
        st.info("Guest history is temporary.")
    else:
        chats = list_conversations(st.session_state.user_id)

        if not chats:
            st.info("No conversations yet.")

        for cid, title, date in chats:
            with st.expander(
                f"💬 {title} · {date[:16]}"
            ):
                for role, content in read_messages(cid):
                    st.markdown(
                        "**You:**" if role == "user"
                        else "**NEXTGEN AI:**"
                    )
                    st.write(content)

                a, b = st.columns(2)

                with a:
                    if st.button("Open", key=f"open{cid}"):
                        st.session_state.cid = cid
                        st.rerun()

                with b:
                    if st.button("Delete", key=f"delete{cid}"):
                        delete_chat(cid)

                        if st.session_state.cid == cid:
                            st.session_state.cid = None

                        st.rerun()


# =====================================================
# ABOUT
# =====================================================

elif page == "About":
    st.subheader("🚀 About NEXTGEN AI")

    st.markdown("""
    NEXTGEN AI is a multi-purpose AI workspace.

    **Modules**
    - AI Chat and Web Search
    - Deep Analysis
    - AI Vision
    - PDF Assistant
    - Voice Studio
    - Cloudflare Live Voice interface
    - Cloudflare Image Generation
    - Video Prompt Studio
    - Stock Market Explorer
    - Chat History

    **Technology**
    - Python
    - Streamlit
    - Groq
    - Gemini
    - Tavily
    - Finnhub
    - Cloudflare Workers AI
    - SQLite

    This project is under active development.
    """)


# =====================================================
# FOOTER
# =====================================================

st.divider()

st.markdown(
    """
    <div style="text-align:center;color:#8494ad;font-size:12px;">
        🚀 NEXTGEN AI © 2026<br>
        One Platform. Endless Possibilities.
    </div>
    """,
    unsafe_allow_html=True
)
