
import os
import io
import sqlite3
import base64
import requests
import streamlit as st
from datetime import datetime

# =====================================================
# NEXTGEN AI V5
# =====================================================

st.set_page_config(
    page_title="NEXTGEN AI",
    page_icon="✦",
    layout="wide",
    initial_sidebar_state="expanded"
)

# ---------------- CONFIG ----------------

GROQ_MODEL = "openai/gpt-oss-120b"
GEMINI_MODEL = "gemini-3.5-flash-lite"
IMAGE_MODEL = "@cf/black-forest-labs/flux-1-schnell"

def get_secret(key):
    try:
        return st.secrets.get(key, os.getenv(key, ""))
    except Exception:
        return os.getenv(key, "")

GROQ_KEY = get_secret("GROQ_API_KEY")
GEMINI_KEY = get_secret("GEMINI_API_KEY")
CF_ACCOUNT = get_secret("CLOUDFLARE_ACCOUNT_ID")
CF_TOKEN = get_secret("CLOUDFLARE_API_TOKEN")
CF_LIVE_URL = get_secret("CLOUDFLARE_VOICE_URL")

DB_PATH = "nextgen_v5.db"

SYSTEM_PROMPT = """
You are NEXTGEN AI, a helpful and intelligent AI assistant.
Give clear, accurate and useful answers.
You can communicate in Hindi and English.
Never invent facts or claim to have performed actions you did not perform.
The creator of NEXTGEN AI is Arav.
Do not invent private information about the creator.
"""

# ---------------- DATABASE ----------------

def connect_db():
    return sqlite3.connect(DB_PATH, check_same_thread=False)

def init_db():
    con = connect_db()
    cur = con.cursor()

    cur.execute("""
        CREATE TABLE IF NOT EXISTS v5_chats(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT,
            created TEXT
        )
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS v5_messages(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            chat_id INTEGER,
            role TEXT,
            content TEXT,
            created TEXT
        )
    """)

    con.commit()
    con.close()

def create_chat():
    con = connect_db()
    cur = con.cursor()
    cur.execute(
        "INSERT INTO v5_chats(title,created) VALUES(?,?)",
        ("New Chat", datetime.now().isoformat())
    )
    chat_id = cur.lastrowid
    con.commit()
    con.close()
    return chat_id

def all_chats():
    con = connect_db()
    rows = con.execute(
        "SELECT id,title,created FROM v5_chats ORDER BY id DESC"
    ).fetchall()
    con.close()
    return rows

def get_messages(chat_id):
    con = connect_db()
    rows = con.execute(
        "SELECT role,content FROM v5_messages WHERE chat_id=? ORDER BY id",
        (chat_id,)
    ).fetchall()
    con.close()
    return rows

def save_message(chat_id, role, content):
    con = connect_db()
    con.execute(
        """INSERT INTO v5_messages(chat_id,role,content,created)
           VALUES(?,?,?,?)""",
        (chat_id, role, content, datetime.now().isoformat())
    )
    con.commit()
    con.close()

def set_chat_title(chat_id, title):
    con = connect_db()
    con.execute(
        "UPDATE v5_chats SET title=? WHERE id=?",
        (title[:48], chat_id)
    )
    con.commit()
    con.close()

def remove_chat(chat_id):
    con = connect_db()
    con.execute("DELETE FROM v5_messages WHERE chat_id=?", (chat_id,))
    con.execute("DELETE FROM v5_chats WHERE id=?", (chat_id,))
    con.commit()
    con.close()

init_db()

# ---------------- AI ROUTING ----------------

def groq_request(messages):
    if not GROQ_KEY:
        raise RuntimeError("GROQ_API_KEY is missing.")

    response = requests.post(
        "https://api.groq.com/openai/v1/chat/completions",
        headers={
            "Authorization": f"Bearer {GROQ_KEY}",
            "Content-Type": "application/json"
        },
        json={
            "model": GROQ_MODEL,
            "messages": [
                {"role": "system", "content": SYSTEM_PROMPT},
                *messages
            ],
            "temperature": 0.6,
            "max_completion_tokens": 4096
        },
        timeout=60
    )
    response.raise_for_status()
    result = response.json()
    answer = result["choices"][0]["message"]["content"]
    if not answer:
        raise RuntimeError("Groq returned an empty response.")
    return answer

def gemini_request(messages):
    if not GEMINI_KEY:
        raise RuntimeError("GEMINI_API_KEY is missing.")

    contents = []
    for msg in messages:
        contents.append({
            "role": "model" if msg["role"] == "assistant" else "user",
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
            "system_instruction": {
                "parts": [{"text": SYSTEM_PROMPT}]
            },
            "contents": contents,
            "generationConfig": {
                "temperature": 0.6,
                "maxOutputTokens": 4096
            }
        },
        timeout=40
    )
    response.raise_for_status()
    data = response.json()
    return data["candidates"][0]["content"]["parts"][0]["text"]

def ask_ai(messages):
    # One Groq attempt, then at most one Gemini backup attempt.
    try:
        return groq_request(messages), "Groq"
    except Exception as main_error:
        if not GEMINI_KEY:
            raise RuntimeError(
                f"Groq failed; Gemini backup key is missing. {main_error}"
            )
        try:
            return gemini_request(messages), "Gemini Backup"
        except Exception as backup_error:
            raise RuntimeError(
                f"Groq failed: {main_error}\n"
                f"Gemini backup failed: {backup_error}"
            )

# ---------------- CLOUDFLARE IMAGE ----------------

def cloudflare_image(prompt):
    if not CF_ACCOUNT or not CF_TOKEN:
        raise RuntimeError("Cloudflare credentials are missing.")

    url = (
        "https://api.cloudflare.com/client/v4/accounts/"
        + CF_ACCOUNT
        + "/ai/run/"
        + IMAGE_MODEL
    )

    response = requests.post(
        url,
        headers={
            "Authorization": f"Bearer {CF_TOKEN}",
            "Content-Type": "application/json"
        },
        json={"prompt": prompt, "steps": 4},
        timeout=150
    )
    response.raise_for_status()
    data = response.json()

    image_data = data.get("result", {}).get("image")
    if not image_data:
        raise RuntimeError(str(data))

    return base64.b64decode(image_data)

# ---------------- AUDIO TRANSCRIPTION ----------------

def transcribe_audio(audio_file):
    if not GROQ_KEY:
        raise RuntimeError("Groq key is missing for transcription.")

    response = requests.post(
        "https://api.groq.com/openai/v1/audio/transcriptions",
        headers={"Authorization": f"Bearer {GROQ_KEY}"},
        files={
            "file": (
                "recording.wav",
                audio_file.getvalue(),
                "audio/wav"
            )
        },
        data={"model": "whisper-large-v3-turbo"},
        timeout=90
    )
    response.raise_for_status()
    return response.json().get("text", "")

# ---------------- SESSION ----------------

if "page" not in st.session_state:
    st.session_state.page = "Dashboard"

if "chat_id" not in st.session_state:
    st.session_state.chat_id = create_chat()

if "messages" not in st.session_state:
    st.session_state.messages = []

if "last_provider" not in st.session_state:
    st.session_state.last_provider = "Automatic"

# ---------------- DESIGN ----------------

st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800;900&display=swap');

html,body,[class*="css"] {
    font-family: Inter, sans-serif;
}

.stApp {
    background:
      radial-gradient(ellipse at 12% 0%,#28235a 0%,transparent 35%),
      radial-gradient(ellipse at 95% 5%,#172e50 0%,transparent 35%),
      #080c18;
    color: #f6f6ff;
}

.block-container {
    max-width: 1450px;
    padding-top: 1.6rem;
    padding-bottom: 5rem;
}

[data-testid="stSidebar"] {
    background: linear-gradient(180deg,#111a30,#0a1020);
    border-right: 1px solid #2c3858;
}

[data-testid="stSidebar"] > div {
    padding-top: 1.2rem;
}

[data-testid="stSidebar"] button {
    text-align: left;
    border-radius: 11px;
    background: transparent;
    border: 1px solid transparent;
    color: #dce3ff;
    min-height: 40px;
}

[data-testid="stSidebar"] button:hover {
    background: #242d4a;
    border-color: #414d76;
}

.brand {
    font-size: 27px;
    font-weight: 900;
    letter-spacing: -1.3px;
    padding: 5px 0;
}

.brand span {
    color: #a89aff;
}

.sidebar-tag {
    color: #8998bd;
    font-size: 10px;
    letter-spacing: 2px;
    margin-bottom: 18px;
}

.hero {
    border: 1px solid #55548b;
    background: linear-gradient(115deg,#171e3e,#30265d 55%,#183451);
    border-radius: 25px;
    padding: 34px;
    margin-bottom: 25px;
    box-shadow: 0 15px 50px #0005;
}

.hero-label {
    color: #c0b6ff;
    font-size: 11px;
    font-weight: 800;
    letter-spacing: 3px;
}

.hero-title {
    font-size: clamp(34px,5vw,55px);
    font-weight: 900;
    line-height: 1.1;
    margin: 13px 0;
    color: white;
}

.hero-sub {
    color: #c4cbe5;
    font-size: 14px;
}

.panel {
    border: 1px solid #303c5d;
    border-radius: 18px;
    padding: 21px;
    background: linear-gradient(145deg,#172139,#10172a);
    min-height: 125px;
    margin-bottom: 12px;
}

.panel-icon {
    font-size: 25px;
    margin-bottom: 8px;
}

.panel-title {
    font-size: 17px;
    font-weight: 800;
    color: white;
}

.panel-desc {
    font-size: 12px;
    color: #aab7d4;
    margin-top: 7px;
    line-height: 1.5;
}

.metric {
    border: 1px solid #303c5d;
    background: #141d32;
    padding: 17px;
    border-radius: 15px;
}

.metric-label {
    font-size: 11px;
    color: #aab6d4;
}

.metric-value {
    font-size: 23px;
    font-weight: 900;
    margin: 5px 0;
}

.small-muted {
    color: #9ca9c8;
    font-size: 11px;
}

div.stButton > button,
div.stLinkButton > a {
    border-radius: 11px;
    border: 1px solid #414d72;
    background: linear-gradient(120deg,#252f50,#34285e);
    color: white;
    font-weight: 700;
    min-height: 39px;
}

div.stButton > button:hover,
div.stLinkButton > a:hover {
    border-color: #aaa0ff;
    color: white;
}

div[data-testid="stChatMessage"] {
    background: #141d30;
    border: 1px solid #2b3855;
    border-radius: 17px;
    padding: 13px;
    margin-bottom: 12px;
}

/* Compact native chat composer */
.st-key-nextgen_chat_input {
    width: 100%;
}

[data-testid="stChatInput"] {
    border: 1px solid #515b7d !important;
    border-radius: 24px !important;
    background: #111a2c !important;
    box-shadow: 0 5px 25px #0004;
}

[data-testid="stChatInput"] textarea {
    color: white !important;
    font-size: 14px !important;
}

[data-testid="stChatInput"] button {
    border-radius: 50% !important;
}

div[data-testid="stFileUploader"] {
    border: 1px dashed #535f86;
    border-radius: 13px;
    background: #121b30;
    padding: 8px;
}

div[data-testid="stTextInput"] input,
div[data-testid="stTextArea"] textarea {
    background: #111a2d;
    color: white;
    border: 1px solid #394766;
    border-radius: 12px;
}

hr {
    border-color: #293550;
}

footer,#MainMenu {
    visibility: hidden;
}
</style>
""", unsafe_allow_html=True)

# ---------------- UI HELPERS ----------------

def hero(title, subtitle, label="NEXTGEN AI"):
    st.markdown(f"""
    <div class="hero">
      <div class="hero-label">{label}</div>
      <div class="hero-title">{title}</div>
      <div class="hero-sub">{subtitle}</div>
    </div>
    """, unsafe_allow_html=True)

def metric(label, value, note):
    st.markdown(f"""
    <div class="metric">
      <div class="metric-label">{label}</div>
      <div class="metric-value">{value}</div>
      <div class="small-muted">{note}</div>
    </div>
    """, unsafe_allow_html=True)

def panel(icon, title, description):
    st.markdown(f"""
    <div class="panel">
      <div class="panel-icon">{icon}</div>
      <div class="panel-title">{title}</div>
      <div class="panel-desc">{description}</div>
    </div>
    """, unsafe_allow_html=True)

# ---------------- SIDEBAR ----------------

with st.sidebar:
    st.markdown(
        '<div class="brand">✦ NEXTGEN<span> AI</span></div>',
        unsafe_allow_html=True
    )
    st.markdown(
        '<div class="sidebar-tag">YOUR AI WORKSPACE</div>',
        unsafe_allow_html=True
    )

    if st.button("＋   New Chat", use_container_width=True):
        st.session_state.chat_id = create_chat()
        st.session_state.messages = []
        st.session_state.page = "AI Chat"
        st.rerun()

    st.markdown("---")
    st.caption("WORKSPACE")

    navigation = [
        ("⌂", "Dashboard"),
        ("✦", "AI Chat"),
        ("▧", "AI Image Studio"),
        ("⌕", "Tool Center"),
        ("▤", "PDF Assistant")
    ]

    for icon, name in navigation:
        if st.button(
            f"{icon}   {name}",
            key=f"nav_{name}",
            use_container_width=True
        ):
            st.session_state.page = name
            st.rerun()

    st.markdown("---")
    st.caption("YOUR LIBRARY")

    for icon, name in [
        ("◷", "Chat History"),
        ("▣", "My Creations"),
        ("⚙", "Settings"),
        ("ⓘ", "About")
    ]:
        if st.button(
            f"{icon}   {name}",
            key=f"nav_{name}",
            use_container_width=True
        ):
            st.session_state.page = name
            st.rerun()

    st.markdown("---")
    st.caption("RECENT CONVERSATIONS")

    for chat in all_chats()[:7]:
        if st.button(
            "•  " + (chat[1] or "New Chat")[:25],
            key=f"recent_{chat[0]}",
            use_container_width=True
        ):
            st.session_state.chat_id = chat[0]
            st.session_state.messages = get_messages(chat[0])
            st.session_state.page = "AI Chat"
            st.rerun()

    st.markdown("---")
    st.markdown(
        '<div class="small-muted">NEXTGEN AI V5.0<br>'
        'Created by Arav</div>',
        unsafe_allow_html=True
    )

page = st.session_state.page

# =====================================================
# DASHBOARD
# =====================================================

if page == "Dashboard":
    hero(
        "Your Ideas. Your Intelligence.",
        "A smarter space for learning, creating, writing and exploring."
    )

    a,b,c,d = st.columns(4)
    with a:
        metric("MAIN AI", "GROQ", "Primary assistant")
    with b:
        metric("BACKUP AI", "GEMINI", "One automatic fallback")
    with c:
        metric("IMAGE AI", "CLOUDFLARE", "FLUX image generation")
    with d:
        metric("WORKSPACE", "ALL-IN-ONE", "Your creative universe")

    st.markdown("## Explore NEXTGEN AI")

    left,right = st.columns(2)

    with left:
        panel("✦", "AI Chat", "A clean, compact AI conversation experience.")
        if st.button("Open AI Chat", key="dash_chat", use_container_width=True):
            st.session_state.page = "AI Chat"
            st.rerun()

        panel("▧", "AI Image Studio", "Create images from your imagination.")
        if st.button("Open Image Studio", key="dash_image", use_container_width=True):
            st.session_state.page = "AI Image Studio"
            st.rerun()

    with right:
        panel("⌕", "AI Tool Center", "Writing, study, creator and productivity tools.")
        if st.button("Open Tool Center", key="dash_tools", use_container_width=True):
            st.session_state.page = "Tool Center"
            st.rerun()

        panel("▤", "PDF Assistant", "Ask questions about your documents.")
        if st.button("Open PDF Assistant", key="dash_pdf", use_container_width=True):
            st.session_state.page = "PDF Assistant"
            st.rerun()

    st.markdown("## Your AI workspace")
    st.markdown("""
    - Groq-powered main chat with automatic Gemini backup.
    - Compact chat composer with built-in attachment and microphone controls.
    - Cloudflare-powered image generation.
    - Conversation history and document assistance.
    """)

# =====================================================
# AI CHAT
# =====================================================

elif page == "AI Chat":
    st.markdown("## ✦ AI Chat")
    st.caption("Ask anything. Your assistant is ready.")

    for role, content in st.session_state.messages:
        with st.chat_message(role):
            st.markdown(content)

    # The native Streamlit composer contains its own Plus and Mic controls.
    # Live Voice is kept in the same compact composer area.
    with st.container(border=True):
        live_col, input_col = st.columns([1.0, 8.5], vertical_alignment="center")

        with live_col:
            if CF_LIVE_URL:
                st.link_button(
                    "◉ Live",
                    CF_LIVE_URL,
                    use_container_width=True
                )
            else:
                st.button(
                    "◉ Live",
                    disabled=True,
                    help="Add CLOUDFLARE_VOICE_URL in Streamlit Secrets.",
                    use_container_width=True
                )

        with input_col:
            submitted = st.chat_input(
                "Message NEXTGEN AI...",
                key="nextgen_chat_input",
                accept_file=True,
                accept_audio=True,
                file_type=["pdf", "txt", "png", "jpg", "jpeg"],
                max_upload_size=20
            )

    if submitted is not None:
        user_text = submitted.text or ""
        file_context = ""

        # Process uploaded files
        for uploaded in submitted.files:
            filename = uploaded.name.lower()

            if filename.endswith(".txt"):
                file_context += "\n\n[Attached text]\n"
                file_context += uploaded.getvalue().decode(
                    "utf-8", errors="ignore"
                )[:20000]

            elif filename.endswith(".pdf"):
                try:
                    from pypdf import PdfReader
                    reader = PdfReader(io.BytesIO(uploaded.getvalue()))
                    extracted = "\n".join(
                        p.extract_text() or "" for p in reader.pages
                    )
                    file_context += "\n\n[Attached PDF]\n"
                    file_context += extracted[:25000]
                except Exception as e:
                    st.warning(f"Could not read {uploaded.name}: {e}")

            elif filename.endswith((".png", ".jpg", ".jpeg")):
                st.info(
                    f"{uploaded.name} attached. Image understanding "
                    "is not enabled in this text-chat build."
                )

        if submitted.audio is not None:
            with st.spinner("Converting your voice to text..."):
                try:
                    voice_text = transcribe_audio(submitted.audio)
                    user_text = (user_text + "\n" + voice_text).strip()
                except Exception as e:
                    st.error(f"Voice transcription failed: {e}")

        user_text = (user_text + file_context).strip()

        if user_text:
            st.session_state.messages.append(("user", user_text))
            save_message(st.session_state.chat_id, "user", user_text)

            if len(st.session_state.messages) == 1:
                set_chat_title(st.session_state.chat_id, user_text[:48])

            api_messages = [
                {"role": role, "content": content}
                for role, content in st.session_state.messages[-20:]
            ]

            with st.spinner("NEXTGEN AI is thinking..."):
                try:
                    answer, provider = ask_ai(api_messages)
                    st.session_state.messages.append(("assistant", answer))
                    save_message(
                        st.session_state.chat_id, "assistant", answer
                    )
                    st.session_state.last_provider = provider
                except Exception as e:
                    st.error(str(e))

            st.rerun()

    st.caption(
        f"Response engine: {st.session_state.last_provider} "
        "• Plus and Mic are built into the chat input."
    )

# =====================================================
# IMAGE STUDIO
# =====================================================

elif page == "AI Image Studio":
    hero(
        "AI Image Studio",
        "Bring your imagination to life with Cloudflare FLUX."
    )

    st.markdown("### Describe your image")

    prompt = st.text_area(
        "Image prompt",
        placeholder="Describe the image you want to create...",
        height=90,
        label_visibility="collapsed"
    )

    # Compact Plus attachment control in Image Studio
    with st.expander("＋  Add reference image", expanded=False):
        reference = st.file_uploader(
            "Choose an image",
            type=["png", "jpg", "jpeg"],
            key="image_reference"
        )

        if reference:
            st.image(reference, caption="Selected reference image", width=220)
            st.caption(
                "Reference image preview is available. "
                "Reference-based editing is not enabled in this version."
            )

    if st.button("✦ Generate Image", use_container_width=True):
        if not prompt.strip():
            st.warning("Please write an image prompt.")
        else:
            with st.spinner("Creating your image..."):
                try:
                    result = cloudflare_image(prompt)
                    st.image(result, use_container_width=True)
                    st.download_button(
                        "↓ Download Image",
                        data=result,
                        file_name="nextgen_image.jpg",
                        mime="image/jpeg"
                    )
                except Exception as e:
                    st.error(f"Image generation failed: {e}")

# =====================================================
# TOOL CENTER
# =====================================================

elif page == "Tool Center":
    hero(
        "AI Tool Center",
        "Choose a tool and let NEXTGEN AI help you."
    )

    tools = {
        "Writing": [
            "Email Writer", "Letter Writer", "Essay Writer",
            "Application Writer", "Notice Writer", "Speech Writer",
            "Story Writer", "Article Writer", "Report Writer",
            "Resume Helper", "Cover Letter Writer", "Blog Writer",
            "Social Caption", "YouTube Description", "Ad Copy",
            "Product Description", "Invitation Writer"
        ],
        "Study": [
            "Topic Explainer", "Short Notes", "Detailed Notes",
            "MCQ Maker", "Quiz Maker", "Flashcard Maker",
            "Chapter Summary", "Worksheet Maker", "Study Planner",
            "Maths Explainer", "Science Explainer", "Grammar Helper",
            "Vocabulary Builder", "Question Answer Maker"
        ],
        "Developer": [
            "Python Helper", "HTML Generator", "CSS Helper",
            "JavaScript Helper", "Code Explainer", "Debugging Helper",
            "SQL Helper", "API Explainer", "Website Planner",
            "App Idea Generator", "JSON Helper"
        ],
        "Creator": [
            "YouTube Ideas", "Reel Ideas", "Video Script",
            "Thumbnail Ideas", "Image Prompt", "Video Prompt",
            "Voiceover Script", "Character Creator", "Story Plot",
            "Content Calendar", "Hashtag Ideas", "Channel Bio"
        ],
        "Business": [
            "Business Ideas", "Business Plan", "Brand Name",
            "Slogan Generator", "Marketing Planner", "Customer Reply",
            "Project Planner", "Meeting Summary", "Presentation Outline"
        ],
        "Language": [
            "Hindi to English", "English to Hindi", "Text Rewriter",
            "Proofreader", "Grammar Correction", "Simple Explanation",
            "Professional Tone", "Text Summarizer"
        ],
        "Everyday": [
            "Daily Planner", "Checklist Maker", "Decision Helper",
            "Gift Ideas", "Travel Planner", "Routine Planner",
            "Goal Planner", "Brainstorming Assistant"
        ]
    }

    category = st.selectbox("Category", list(tools.keys()))
    tool = st.selectbox("Choose a tool", tools[category])
    details = st.text_area(
        "Your instructions",
        placeholder="Tell NEXTGEN AI what you need...",
        height=100
    )

    if st.button("Run Tool ✦", use_container_width=True):
        if details.strip():
            with st.spinner("Creating your result..."):
                try:
                    result, provider = ask_ai([{
                        "role": "user",
                        "content": f"Use this tool: {tool}\n\n{details}"
                    }])
                    st.markdown("### Your Result")
                    st.markdown(result)
                    st.caption(f"Generated by {provider}")
                except Exception as e:
                    st.error(str(e))
        else:
            st.warning("Enter your instructions first.")

    st.caption(
        f"{sum(len(items) for items in tools.values())} AI tool presets."
    )

# =====================================================
# PDF ASSISTANT
# =====================================================

elif page == "PDF Assistant":
    hero(
        "PDF Assistant",
        "Upload a document and ask questions about its contents."
    )

    pdf = st.file_uploader(
        "＋  Upload PDF",
        type=["pdf"],
        key="pdf_assistant_upload"
    )

    if pdf:
        try:
            from pypdf import PdfReader
            reader = PdfReader(io.BytesIO(pdf.getvalue()))
            pdf_text = "\n".join(
                page.extract_text() or "" for page in reader.pages
            )

            st.success(f"Loaded {len(reader.pages)} pages.")
            question = st.text_input("Ask a question about this PDF")

            if st.button("Ask NEXTGEN AI"):
                if question.strip():
                    with st.spinner("Reading your document..."):
                        answer, provider = ask_ai([{
                            "role": "user",
                            "content": (
                                "Answer based on this PDF:\n"
                                + pdf_text[:45000]
                                + "\n\nQuestion: "
                                + question
                            )
                        }])
                    st.markdown(answer)
                    st.caption(provider)
        except Exception as e:
            st.error(f"PDF error: {e}")

# =====================================================
# CHAT HISTORY
# =====================================================

elif page == "Chat History":
    hero("Chat History", "Continue your previous conversations.")

    for chat in all_chats():
        chat_id, title, created = chat

        with st.expander(f"{title}  ·  {created[:16]}"):
            open_col, delete_col = st.columns(2)

            with open_col:
                if st.button("Open", key=f"history_open_{chat_id}"):
                    st.session_state.chat_id = chat_id
                    st.session_state.messages = get_messages(chat_id)
                    st.session_state.page = "AI Chat"
                    st.rerun()

            with delete_col:
                if st.button("Delete", key=f"history_delete_{chat_id}"):
                    remove_chat(chat_id)
                    if st.session_state.chat_id == chat_id:
                        st.session_state.chat_id = create_chat()
                        st.session_state.messages = []
                    st.rerun()

# =====================================================
# MY CREATIONS
# =====================================================

elif page == "My Creations":
    hero("My Creations", "Your creative workspace.")
    st.info(
        "Your conversations are saved in Chat History. "
        "A separate persistent gallery for generated images can be added next."
    )

# =====================================================
# SETTINGS
# =====================================================

elif page == "Settings":
    hero("Settings", "Your AI platform configuration.")

    st.markdown("### AI Routing")
    st.success(f"Main: Groq — {GROQ_MODEL}")
    st.success(f"Backup: Gemini — {GEMINI_MODEL}")
    st.caption("Gemini is called only once if the Groq request fails.")

    st.markdown("### Image Generation")
    st.info(f"Cloudflare model: {IMAGE_MODEL}")

    st.markdown("### Live Voice")
    if CF_LIVE_URL:
        st.success("Cloudflare Voice Agent URL configured.")
    else:
        st.warning("Cloudflare Voice Agent URL is not configured.")

    st.caption(
        "Manage API credentials in Streamlit Cloud → Settings → Secrets."
    )

# =====================================================
# ABOUT
# =====================================================

elif page == "About":
    hero(
        "About NEXTGEN AI",
        "One platform. Endless possibilities."
    )

    st.markdown("""
    ## Created by Arav

    NEXTGEN AI brings AI assistance, learning, writing,
    creativity and productivity together in one workspace.

    - Main AI: Groq
    - Backup AI: Gemini
    - Image generation: Cloudflare Workers AI
    - Voice agent: Cloudflare
    """)

    st.caption("NEXTGEN AI © 2026")
