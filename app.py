
import os
import io
import json
import sqlite3
import html
import streamlit as st
import streamlit.components.v1 as components

from dotenv import load_dotenv
from google import genai
from google.genai import types
from PIL import Image
from pypdf import PdfReader

from auto_pilot import generate_with_autopilot

# =========================================
# NEXTGEN AI
# ChatGPT-style interface
# =========================================

load_dotenv()

APP_NAME = "NEXTGEN AI"
MODEL = "gemini-3.8-flash"
DB_FILE = "nextgen_history.db"

st.set_page_config(
    page_title="NEXTGEN AI",
    page_icon="🚀",
    layout="wide",
    initial_sidebar_state="expanded"
)

API_KEY = os.getenv("GEMINI_API_KEY")

# =========================================
# DATABASE
# =========================================

def init_db():
    conn = sqlite3.connect(DB_FILE)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS chats (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT,
            messages TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    conn.commit()
    conn.close()

def save_chat(title, messages, chat_id=None):
    conn = sqlite3.connect(DB_FILE)
    data = json.dumps(messages, ensure_ascii=False)

    if chat_id:
        conn.execute(
            "UPDATE chats SET title=?, messages=? WHERE id=?",
            (title, data, chat_id)
        )
    else:
        cur = conn.execute(
            "INSERT INTO chats (title, messages) VALUES (?, ?)",
            (title, data)
        )
        chat_id = cur.lastrowid

    conn.commit()
    conn.close()
    return chat_id

def get_chats():
    conn = sqlite3.connect(DB_FILE)
    rows = conn.execute(
        "SELECT id, title, messages FROM chats ORDER BY id DESC"
    ).fetchall()
    conn.close()
    return rows

init_db()

# =========================================
# SESSION STATE
# =========================================

defaults = {
    "messages": [],
    "chat_id": None,
    "client": None,
    "voice_enabled": True,
    "last_provider": "Not connected",
    "pending_files": []
}

for key, value in defaults.items():
    if key not in st.session_state:
        st.session_state[key] = value

# =========================================
# AI ENGINE
# =========================================

def get_client():
    if not API_KEY:
        raise ValueError(
            "GEMINI_API_KEY नहीं मिली। अपनी .env फाइल चेक करें।"
        )

    if st.session_state.client is None:
        st.session_state.client = genai.Client(
            api_key=API_KEY
        )

    return st.session_state.client

def ask_ai(contents):
    client = get_client()

    answer, provider = generate_with_autopilot(
        client=client,
        model=MODEL,
        contents=contents
    )

    st.session_state.last_provider = provider
    return answer

# =========================================
# DESIGN
# =========================================

st.markdown("""
<style>
#MainMenu, footer, header {
    visibility: hidden;
}

.stApp {
    background: #212121;
    color: #f5f5f5;
}

[data-testid="stSidebar"] {
    background: #171717;
    border-right: 1px solid #333;
}

[data-testid="stSidebar"] * {
    color: #eeeeee !important;
}

h1, h2, h3 {
    color: #f5f5f5;
}

.stChatMessage {
    border-radius: 16px;
}

[data-testid="stChatMessage"] {
    background: transparent;
    border: none;
}

.stChatInput textarea {
    background: #303030 !important;
    color: white !important;
}

.stButton button {
    border-radius: 12px;
    border: 1px solid #444;
    background: #303030;
    color: white;
}

.stButton button:hover {
    border-color: #999;
    color: white;
}

.hero {
    text-align: center;
    padding: 45px 10px 25px;
}

.hero h1 {
    font-size: 36px;
    font-weight: 700;
}

.hero p {
    color: #aaa;
    font-size: 15px;
}

.small-status {
    color: #aaa;
    font-size: 12px;
}

div[data-testid="stFileUploader"] {
    background: #292929;
    border-radius: 12px;
    padding: 8px;
}

</style>
""", unsafe_allow_html=True)

# =========================================
# SIDEBAR
# =========================================

with st.sidebar:

    st.markdown("# 🚀 NEXTGEN AI")
    st.caption("One Platform. Endless Possibilities.")

    st.markdown("---")

    if st.button("＋ New Chat", use_container_width=True):
        st.session_state.messages = []
        st.session_state.chat_id = None
        st.rerun()

    page = st.radio(
        "WORKSPACE",
        [
            "AI Chat",
            "AI Vision",
            "PDF Assistant",
            "Coding School",
            "Coding Assistant",
            "Website Builder",
            "Image Studio",
            "Video Studio",
            "Settings"
        ],
        label_visibility="visible"
    )

    st.markdown("---")
    st.markdown("### Recent Chats")

    for chat in get_chats()[:12]:
        chat_id, title, messages_json = chat

        if st.button(
            title[:30] if title else "New Chat",
            key=f"chat_{chat_id}",
            use_container_width=True
        ):
            st.session_state.chat_id = chat_id
            st.session_state.messages = json.loads(messages_json)
            st.session_state.page = "AI Chat"
            st.rerun()

    st.markdown("---")

    if API_KEY:
        st.success("AI Engine: Connected")
    else:
        st.error("API Key Missing")

    st.caption(
        f"Last AI Provider: {st.session_state.last_provider}"
    )

# =========================================
# CHAT PAGE
# =========================================

if page == "AI Chat":

    st.markdown("""
    <div class="hero">
        <h1>🚀 NEXTGEN AI</h1>
        <p>What can I help you with today?</p>
    </div>
    """, unsafe_allow_html=True)

    # Display conversation
    for msg in st.session_state.messages:
        with st.chat_message(msg["role"]):
            st.markdown(msg["content"])

            if msg["role"] == "assistant":
                safe_text = json.dumps(msg["content"])

                components.html(
                    f"""
                    <button onclick='
                    const text = {safe_text};
                    const utterance = new SpeechSynthesisUtterance(text);
                    utterance.lang = "hi-IN";
                    speechSynthesis.cancel();
                    speechSynthesis.speak(utterance);
                    ' style="
                    background:#303030;
                    color:white;
                    border:1px solid #555;
                    padding:7px 13px;
                    border-radius:10px;
                    cursor:pointer;">
                    🔊 Listen
                    </button>
                    """,
                    height=45
                )

    # Attachments
    with st.expander("＋ Attach files or images"):
        uploaded_files = st.file_uploader(
            "Choose files",
            type=[
                "png", "jpg", "jpeg", "webp",
                "pdf", "txt", "py", "js",
                "html", "css", "csv"
            ],
            accept_multiple_files=True
        )

        if uploaded_files:
            st.write(
                f"{len(uploaded_files)} file(s) attached."
            )

    # Microphone
    audio = None
    with st.expander("🎙️ Talk to NEXTGEN AI"):
        try:
            audio = st.audio_input("Record your question")
        except Exception:
            st.info(
                "Audio input आपके Streamlit version में उपलब्ध नहीं है। "
                "अपडेट करके फिर कोशिश करें।"
            )

    prompt = st.chat_input(
        "Message NEXTGEN AI..."
    )

    if prompt or audio:

        if prompt:
            user_text = prompt
        else:
            user_text = "Please listen to this audio and answer the spoken question."

        st.session_state.messages.append({
            "role": "user",
            "content": user_text
        })

        with st.chat_message("user"):
            st.markdown(user_text)

        contents = [
            "You are NEXTGEN AI, a helpful and intelligent assistant. "
            "Answer naturally in the user's language. "
            "Explain clearly and do not invent facts.\n\n"
        ]

        for msg in st.session_state.messages[-12:]:
            contents.append(
                f'{msg["role"].upper()}: {msg["content"]}'
            )

        for uploaded in uploaded_files or []:
            raw = uploaded.getvalue()
            mime = uploaded.type or "application/octet-stream"

            if mime.startswith("image/"):
                contents.append(
                    types.Part.from_bytes(
                        data=raw,
                        mime_type=mime
                    )
                )

            elif mime == "application/pdf":
                try:
                    reader = PdfReader(io.BytesIO(raw))
                    pdf_text = "\n".join(
                        p.extract_text() or ""
                        for p in reader.pages
                    )
                    contents.append(
                        f"Attached PDF ({uploaded.name}):\n"
                        + pdf_text[:20000]
                    )
                except Exception:
                    contents.append(
                        f"Could not read PDF: {uploaded.name}"
                    )

            elif mime.startswith("text/") or uploaded.name.endswith(
                (".py", ".js", ".html", ".css", ".csv")
            ):
                contents.append(
                    f"Attached file {uploaded.name}:\n"
                    + raw.decode("utf-8", errors="replace")[:15000]
                )

        if audio is not None:
            contents.append(
                types.Part.from_bytes(
                    data=audio.getvalue(),
                    mime_type=audio.type or "audio/wav"
                )
            )
            contents.append(
                "Understand the audio, transcribe the user's question "
                "if needed, and answer it."
            )

        with st.chat_message("assistant"):
            try:
                with st.spinner("NEXTGEN AI is thinking..."):
                    answer = ask_ai(contents)

                st.markdown(answer)

                safe_text = json.dumps(answer)

                components.html(
                    f"""
                    <button onclick='
                    const text = {safe_text};
                    const utterance = new SpeechSynthesisUtterance(text);
                    utterance.lang = "hi-IN";
                    speechSynthesis.cancel();
                    speechSynthesis.speak(utterance);
                    ' style="
                    background:#303030;
                    color:white;
                    border:1px solid #555;
                    padding:7px 13px;
                    border-radius:10px;
                    cursor:pointer;">
                    🔊 Listen to answer
                    </button>
                    """,
                    height=45
                )

            except Exception as e:
                answer = f"AI Error: {e}"
                st.error(answer)

        st.session_state.messages.append({
            "role": "assistant",
            "content": answer
        })

        title = (
            st.session_state.messages[0]["content"][:45]
            if st.session_state.messages else "New Chat"
        )

        st.session_state.chat_id = save_chat(
            title,
            st.session_state.messages,
            st.session_state.chat_id
        )

        st.rerun()

# =========================================
# VISION
# =========================================

elif page == "AI Vision":

    st.title("👁️ AI Vision")
    st.write("Upload an image and ask NEXTGEN AI about it.")

    image_file = st.file_uploader(
        "Upload Image",
        type=["png", "jpg", "jpeg", "webp"]
    )

    question = st.text_input(
        "What should I understand from this image?"
    )

    if image_file:
        image = Image.open(image_file)
        st.image(image, use_container_width=True)

        if st.button("Analyze Image"):
            try:
                with st.spinner("Analyzing image..."):
                    answer = ask_ai([
                        question or "Describe this image.",
                        image
                    ])
                st.markdown(answer)
            except Exception as e:
                st.error(str(e))

# =========================================
# PDF ASSISTANT
# =========================================

elif page == "PDF Assistant":

    st.title("📄 PDF Assistant")

    pdf = st.file_uploader(
        "Upload PDF",
        type=["pdf"]
    )

    if pdf:
        try:
            reader = PdfReader(pdf)
            text = "\n".join(
                p.extract_text() or ""
                for p in reader.pages
            )

            st.success(
                f"Loaded {len(reader.pages)} pages"
            )

            question = st.text_input(
                "Ask a question about this PDF"
            )

            if st.button("Ask PDF Assistant"):
                if question.strip():
                    answer = ask_ai(
                        "Use only this PDF content. "
                        "If the answer is missing, say so.\n\n"
                        + text[:40000]
                        + "\n\nQuestion: "
                        + question
                    )
                    st.markdown(answer)

        except Exception as e:
            st.error(f"PDF Error: {e}")

# =========================================
# CODING SCHOOL
# =========================================

elif page == "Coding School":

    st.title("🎓 NEXTGEN Coding School")
    st.write(
        "Learn programming from beginner to advanced level."
    )

    languages = [
        "Python", "JavaScript", "HTML",
        "CSS", "C", "C++", "Java", "SQL"
    ]

    language = st.selectbox(
        "Choose a programming language",
        languages
    )

    level = st.selectbox(
        "Choose your level",
        ["Beginner", "Intermediate", "Advanced"]
    )

    topic = st.text_input(
        "What do you want to learn?",
        placeholder="Example: Variables, Loops, Functions"
    )

    learning_mode = st.selectbox(
        "Learning mode",
        [
            "Detailed Lesson",
            "Practice Questions",
            "Quiz",
            "Mini Project",
            "Explain My Mistakes"
        ]
    )

    if st.button("Start Learning"):
        if not topic.strip():
            st.warning("Enter a topic first.")
        else:
            instruction = f"""
You are NEXTGEN Coding School, a patient programming teacher.

Teach {language}.
Student level: {level}.
Topic: {topic}.
Mode: {learning_mode}.

Rules:
1. Explain from the correct difficulty level.
2. Use simple language.
3. Give examples and code.
4. Explain each important line.
5. For quizzes, give questions and wait for answers.
6. For projects, give requirements and steps.
7. Never pretend code was executed if it was not.
"""
            try:
                with st.spinner("Preparing your lesson..."):
                    answer = ask_ai(instruction)
                st.markdown(answer)
            except Exception as e:
                st.error(str(e))

# =========================================
# CODING ASSISTANT
# =========================================

elif page == "Coding Assistant":

    st.title("💻 Coding Assistant")

    language = st.selectbox(
        "Programming language",
        [
            "Python", "JavaScript", "HTML",
            "CSS", "C", "C++", "Java", "SQL"
        ]
    )

    task = st.text_area(
        "Describe your coding problem or paste your code"
    )

    if st.button("Help Me Code"):
        if task.strip():
            try:
                answer = ask_ai(
                    f"""
Act as a careful {language} programming assistant.
Explain the solution, provide corrected code,
and describe common mistakes.

User request:
{task}
"""
                )
                st.markdown(answer)
            except Exception as e:
                st.error(str(e))

# =========================================
# WEBSITE BUILDER
# =========================================

elif page == "Website Builder":

    st.title("🌐 NEXTGEN Website Builder")

    idea = st.text_area(
        "Describe the website you want to build"
    )

    if st.button("Generate Website Code"):
        if idea.strip():
            try:
                answer = ask_ai(
                    "Create a responsive website using HTML, CSS "
                    "and JavaScript. Return complete code with "
                    "separate clearly labelled sections.\n\n"
                    + idea
                )
                st.code(answer, language="html")
            except Exception as e:
                st.error(str(e))

# =========================================
# IMAGE STUDIO
# =========================================

elif page == "Image Studio":

    st.title("🎨 Image Studio")

    prompt = st.text_area(
        "Describe the image you want to create"
    )

    if st.button("Create Image Prompt"):
        if prompt.strip():
            try:
                result = ask_ai(
                    "Create a detailed professional image-generation "
                    "prompt. Include subject, setting, lighting, "
                    "composition, camera and style.\n\n"
                    + prompt
                )
                st.text_area(
                    "Your Image Generation Prompt",
                    result,
                    height=220
                )
                st.info(
                    "यह अभी prompt generator है। वास्तविक image "
                    "rendering के लिए image-generation API जोड़नी होगी।"
                )
            except Exception as e:
                st.error(str(e))

# =========================================
# VIDEO STUDIO
# =========================================

elif page == "Video Studio":

    st.title("🎬 Video Studio")

    idea = st.text_area(
        "Describe your video idea"
    )

    duration = st.selectbox(
        "Video duration",
        ["10 seconds", "20 seconds", "30 seconds", "60 seconds"]
    )

    if st.button("Create Video Storyboard"):
        if idea.strip():
            try:
                result = ask_ai(
                    f"""
Create a professional video storyboard.
Duration: {duration}.
Include scenes, visual prompts, camera movements,
voiceover and background music suggestions.

Idea:
{idea}
"""
                )
                st.markdown(result)
                st.info(
                    "यह storyboard generator है। वास्तविक video "
                    "rendering के लिए video-generation API चाहिए।"
                )
            except Exception as e:
                st.error(str(e))

# =========================================
# SETTINGS
# =========================================

elif page == "Settings":

    st.title("⚙️ Settings")

    st.write("NEXTGEN AI configuration")

    st.write(
        "AI Provider: Google Gemini + Auto-Pilot"
    )

    st.write(
        "Current model: " + MODEL
    )

    st.write(
        "API Key Status: "
        + ("Configured" if API_KEY else "Missing")
    )

    st.checkbox(
        "Enable voice response",
        key="voice_enabled"
    )

    if st.button("Clear Current Conversation"):
        st.session_state.messages = []
        st.session_state.chat_id = None
        st.rerun()

    st.caption(
        "NEXTGEN AI | One Platform. Endless Possibilities."
    )

# =========================================
# FOOTER
# =========================================

st.markdown("---")
st.markdown(
    "<center style='color:#888'>"
    "NEXTGEN AI © 2026 | Powered by AI"
    "</center>",
    unsafe_allow_html=True
)
