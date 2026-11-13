
import os
import io
import re
import json
import base64
import sqlite3
import requests
import streamlit as st
import streamlit.components.v1 as components

from datetime import datetime
from dotenv import load_dotenv
from pypdf import PdfReader

load_dotenv()

# =========================================================
# NEXTGEN AI — VERSION MAX
# Original V7.1 inspired dark purple / blue interface
# =========================================================

st.set_page_config(
    page_title="NEXTGEN AI",
    page_icon="✦",
    layout="wide",
    initial_sidebar_state="expanded"
)

APP_NAME = "NEXTGEN AI"
DB_FILE = "nextgen_max.db"

GROQ_MODEL = os.getenv("GROQ_MODEL", "openai/gpt-oss-120b")
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-3.5-flash-lite")
IMAGE_MODEL = "@cf/black-forest-labs/flux-1-schnell"

# =========================================================
# CREATOR PROFILE
# =========================================================

CREATOR_PROFILE = """
NEXTGEN AI के creator Arav हैं।
Arav एक विद्यार्थी और AI/technology enthusiast हैं।
वे NEXTGEN AI नाम का अपना AI platform विकसित कर रहे हैं।
उनकी रुचि AI tools, app development, creative technology,
coding और digital content creation में है।
उनका YouTube project ARAVYX भी है।
वे अपने AI platform को लगातार बेहतर बनाने पर काम कर रहे हैं।

यदि कोई Arav के बारे में पूछे तो इसी उपलब्ध जानकारी के आधार पर
सम्मानजनक और सकारात्मक परिचय देना।
कोई निजी जानकारी, पता, फोन नंबर, पासवर्ड, स्कूल की निजी जानकारी,
या ऐसी बात नहीं बतानी जो इस प्रोफाइल में उपलब्ध नहीं है।
अज्ञात उपलब्धियों, पुरस्कारों या अनुभवों का आविष्कार नहीं करना।
"""

SYSTEM_PROMPT = f"""
You are NEXTGEN AI, a helpful, intelligent, friendly AI assistant.

You can communicate in Hindi, English and Hinglish.
Answer clearly, accurately and helpfully.
Never claim that you performed an action if you did not.
If you do not know something, say so honestly.

CREATOR PROFILE:
{CREATOR_PROFILE}

If the user asks about the creator Arav, NEXTGEN AI, or who made it,
use the creator profile above. Give a positive, detailed but factual
introduction. Do not invent personal facts.

You are an AI assistant, not a human.
"""

# =========================================================
# 550 NAMED AI WORKFLOWS
# 25 domains x 22 workflows = 550 unique workflows
# =========================================================

DOMAINS = [
    "Writing & Documents",
    "Study & Education",
    "Coding & Development",
    "YouTube & Content Creator",
    "Business & Marketing",
    "Language & Translation",
    "Productivity & Planning",
    "Creative & Design",
    "Everyday Assistant",
    "Career & Skills",
    "Data & Analysis",
    "Research & Thinking",
    "Advanced Study Tools",
    "AI Creator Studio",
    "Web & App Development",
    "Smart AI Assistants",
    "Maths & Science Lab",
    "Business Creator Tools",
    "Learning & Knowledge",
    "Presentation & Office",
    "Social Media Studio",
    "Storytelling & Entertainment",
    "Project Management",
    "Technology & Innovation",
    "Personal Productivity"
]

WORKFLOWS = [
    "Idea Generator",
    "Smart Planner",
    "Content Writer",
    "Step-by-Step Guide",
    "Expert Explainer",
    "Quality Checker",
    "Summary Maker",
    "Research Assistant",
    "Creative Brainstormer",
    "Professional Formatter",
    "Problem Solver",
    "Improvement Advisor",
    "Beginner Guide",
    "Advanced Guide",
    "Template Creator",
    "Checklist Builder",
    "Strategy Designer",
    "Comparison Assistant",
    "Question Generator",
    "Feedback Assistant",
    "Project Builder",
    "Final Output Creator"
]

TOOL_LIBRARY = {
    domain: [
        f"{domain} — {workflow}"
        for workflow in WORKFLOWS
    ]
    for domain in DOMAINS
}

TOOL_COUNT = sum(len(items) for items in TOOL_LIBRARY.values())

# =========================================================
# DATABASE
# =========================================================

def db():
    return sqlite3.connect(DB_FILE, check_same_thread=False)

def init_db():
    con = db()
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
            prompt TEXT,
            image BLOB,
            created_at TEXT
        )
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS feedback (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            message_id INTEGER,
            reaction TEXT,
            created_at TEXT
        )
    """)

    con.commit()
    con.close()

init_db()

def create_chat(title="New Chat"):
    con = db()
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
    con = db()
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

def update_last_assistant(chat_id, content):
    con = db()
    cur = con.cursor()
    cur.execute("""
        UPDATE messages
        SET content = ?, created_at = ?
        WHERE id = (
            SELECT id FROM messages
            WHERE chat_id = ? AND role = 'assistant'
            ORDER BY id DESC LIMIT 1
        )
    """, (content, datetime.now().isoformat(), chat_id))
    con.commit()
    con.close()

def get_messages(chat_id):
    con = db()
    cur = con.cursor()
    cur.execute("""
        SELECT id, role, content
        FROM messages
        WHERE chat_id = ?
        ORDER BY id ASC
    """, (chat_id,))
    rows = cur.fetchall()
    con.close()
    return rows

def get_chats():
    con = db()
    cur = con.cursor()
    cur.execute("""
        SELECT id, title, created_at
        FROM chats ORDER BY id DESC
    """)
    rows = cur.fetchall()
    con.close()
    return rows

def delete_chat(chat_id):
    con = db()
    cur = con.cursor()
    cur.execute("DELETE FROM messages WHERE chat_id=?", (chat_id,))
    cur.execute("DELETE FROM chats WHERE id=?", (chat_id,))
    con.commit()
    con.close()

def save_creation(prompt, image_bytes):
    con = db()
    cur = con.cursor()
    cur.execute("""
        INSERT INTO creations (prompt, image, created_at)
        VALUES (?, ?, ?)
    """, (prompt, image_bytes, datetime.now().isoformat()))
    con.commit()
    con.close()

# =========================================================
# API CONFIGURATION
# =========================================================

def get_secret(name):
    value = os.getenv(name, "")
    if value:
        return value

    try:
        return st.secrets.get(name, "")
    except Exception:
        return ""

def call_groq(messages):
    api_key = get_secret("GROQ_API_KEY")
    if not api_key:
        raise Exception("AI service configuration is missing.")

    payload = {
        "model": GROQ_MODEL,
        "messages": messages,
        "temperature": 0.7,
        "max_tokens": 3000
    }

    response = requests.post(
        "https://api.groq.com/openai/v1/chat/completions",
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json"
        },
        json=payload,
        timeout=90
    )

    response.raise_for_status()
    return response.json()["choices"][0]["message"]["content"]

def call_gemini(messages):
    api_key = get_secret("GEMINI_API_KEY")
    if not api_key:
        raise Exception("AI service configuration is missing.")

    conversation = "\n\n".join(
        f"{m['role']}: {m['content']}"
        for m in messages
    )

    url = (
        "https://generativelanguage.googleapis.com/v1beta/models/"
        f"{GEMINI_MODEL}:generateContent?key={api_key}"
    )

    response = requests.post(
        url,
        json={
            "contents": [{
                "parts": [{"text": conversation}]
            }]
        },
        timeout=90
    )

    response.raise_for_status()
    data = response.json()

    return data["candidates"][0]["content"]["parts"][0]["text"]

def ask_ai(messages):
    errors = []

    try:
        return call_groq(messages)
    except Exception as e:
        errors.append(str(e))

    try:
        return call_gemini(messages)
    except Exception as e:
        errors.append(str(e))

    return (
        "अभी AI से कनेक्शन नहीं हो पाया। कृपया API configuration "
        "और internet connection जाँचें।\n\n"
        "Technical detail: " + " | ".join(errors)
    )

def build_messages(chat_id, new_prompt):
    history = get_messages(chat_id)

    messages = [{"role": "system", "content": SYSTEM_PROMPT}]

    for _, role, content in history[-16:]:
        if role in ("user", "assistant"):
            messages.append({
                "role": role,
                "content": content
            })

    messages.append({
        "role": "user",
        "content": new_prompt
    })

    return messages

# =========================================================
# AUDIO TRANSCRIPTION
# =========================================================

def transcribe_audio(audio_file):
    api_key = get_secret("GROQ_API_KEY")
    if not api_key:
        return None

    try:
        response = requests.post(
            "https://api.groq.com/openai/v1/audio/transcriptions",
            headers={"Authorization": f"Bearer {api_key}"},
            files={
                "file": (
                    audio_file.name,
                    audio_file.getvalue(),
                    audio_file.type or "audio/wav"
                )
            },
            data={"model": "whisper-large-v3-turbo"},
            timeout=120
        )
        response.raise_for_status()
        return response.json().get("text", "")
    except Exception:
        return None

# =========================================================
# IMAGE GENERATION
# =========================================================

def generate_image(prompt):
    account_id = get_secret("CLOUDFLARE_ACCOUNT_ID")
    token = get_secret("CLOUDFLARE_API_TOKEN")

    if not account_id or not token:
        return None, "Image generation configuration is missing."

    url = (
        f"https://api.cloudflare.com/client/v4/accounts/"
        f"{account_id}/ai/run/{IMAGE_MODEL}"
    )

    try:
        response = requests.post(
            url,
            headers={"Authorization": f"Bearer {token}"},
            json={"prompt": prompt},
            timeout=120
        )
        response.raise_for_status()

        content_type = response.headers.get("content-type", "")

        if "image" in content_type:
            return response.content, None

        data = response.json()
        if data.get("success") and data.get("result"):
            result = data["result"]
            if isinstance(result, dict) and result.get("image"):
                return base64.b64decode(result["image"]), None

        return None, "Image service returned an unexpected response."

    except Exception as e:
        return None, str(e)

# =========================================================
# CSS — ORIGINAL PREMIUM DESIGN DIRECTION
# =========================================================

st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&display=swap');

html, body, [class*="css"] {
    font-family: 'Inter', sans-serif;
}

.stApp {
    background:
      radial-gradient(circle at 15% 5%, rgba(105,65,210,.16), transparent 30%),
      radial-gradient(circle at 90% 15%, rgba(40,105,220,.13), transparent 28%),
      #080d19;
    color: #f5f6ff;
}

[data-testid="stSidebar"] {
    background: linear-gradient(180deg,#111a30,#0a1020);
    border-right: 1px solid rgba(150,140,255,.12);
}

[data-testid="stSidebar"] * {
    color: #e8eaff;
}

.brand {
    font-size: 27px;
    font-weight: 800;
    letter-spacing: -1px;
    background: linear-gradient(90deg,#c9a7ff,#7b9dff);
    -webkit-background-clip: text;
    -webkit-text-fill-color: transparent;
}

.hero {
    padding: 32px;
    border-radius: 25px;
    background: linear-gradient(120deg,
        rgba(101,66,190,.30),
        rgba(36,90,170,.22));
    border: 1px solid rgba(173,151,255,.20);
    margin-bottom: 22px;
}

.hero h1 {
    font-size: 36px;
    font-weight: 800;
    margin-bottom: 8px;
}

.hero p {
    color: #c4c9e4;
    font-size: 15px;
}

.panel {
    padding: 20px;
    border-radius: 18px;
    background: rgba(18,27,48,.80);
    border: 1px solid rgba(145,145,220,.13);
    margin-bottom: 14px;
}

.metric {
    padding: 19px;
    border-radius: 17px;
    background: linear-gradient(145deg,#17223d,#10182b);
    border: 1px solid rgba(160,150,255,.15);
}

.metric-label {
    color: #aab3d2;
    font-size: 12px;
}

.metric-value {
    font-size: 26px;
    font-weight: 800;
    margin-top: 6px;
}

.small-status {
    display: inline-block;
    color: #c9c1ff;
    background: rgba(117,91,220,.16);
    border: 1px solid rgba(160,140,255,.22);
    border-radius: 30px;
    padding: 5px 12px;
    font-size: 11px;
    font-weight: 700;
}

.chat-user {
    background: linear-gradient(120deg,#47318a,#284b91);
    padding: 15px 18px;
    border-radius: 18px 18px 5px 18px;
    margin: 10px 0 15px 12%;
    color: white;
}

.chat-ai {
    background: rgba(22,32,55,.96);
    border: 1px solid rgba(145,145,220,.15);
    padding: 16px 18px;
    border-radius: 18px 18px 18px 5px;
    margin: 10px 12% 8px 0;
    color: #f0f1ff;
}

div.stButton > button {
    border-radius: 12px;
    border: 1px solid rgba(150,140,255,.20);
    background: linear-gradient(110deg,#6044b9,#315ca8);
    color: white;
    font-weight: 600;
    min-height: 38px;
}

div.stButton > button:hover {
    border-color: #b8a3ff;
    color: white;
}

.stTextInput input, .stTextArea textarea,
.stSelectbox div[data-baseweb="select"] {
    background: #111a2d !important;
    color: white !important;
    border-color: rgba(150,140,255,.20) !important;
    border-radius: 12px !important;
}

div[data-testid="stChatInput"] {
    border: 1px solid rgba(150,140,255,.25);
    border-radius: 18px;
}

.tool-chip {
    background: rgba(100,80,190,.16);
    border: 1px solid rgba(150,130,255,.20);
    padding: 10px;
    border-radius: 12px;
    color: #e7e5ff;
    font-size: 13px;
}

footer {visibility: hidden;}
#MainMenu {visibility: hidden;}
</style>
""", unsafe_allow_html=True)

# =========================================================
# SMALL CHAT ACTIONS
# =========================================================

def chat_actions(message_id, content):
    safe_text = json.dumps(content, ensure_ascii=False)

    c1, c2, c3, c4 = st.columns([1, 1, 1, 0.55])

    with c1:
        components.html(f"""
        <button onclick='copyText()'
        style="width:100%;padding:6px 3px;border-radius:8px;
        border:1px solid #39365d;background:#171d32;color:#ddd8ff;
        font-size:11px;cursor:pointer;">Copy</button>
        <script>
        const responseText = {safe_text};
        function copyText() {{
          if (navigator.clipboard && window.isSecureContext) {{
            navigator.clipboard.writeText(responseText);
          }} else {{
            const el=document.createElement('textarea');
            el.value=responseText;
            document.body.appendChild(el);
            el.select();
            document.execCommand('copy');
            el.remove();
          }}
        }}
        </script>
        """, height=35)

    with c2:
        st.caption("Tips · Use your browser's voice settings for clearer reading.")
        components.html(f"""
        <button onclick='readText()'
        style="width:100%;padding:6px 3px;border-radius:8px;
        border:1px solid #39365d;background:#171d32;color:#ddd8ff;
        font-size:11px;cursor:pointer;">🔊 Read Aloud</button>
        <script>
        const responseText = {safe_text};
        function readText() {{
          if (!('speechSynthesis' in window)) return;
          window.speechSynthesis.cancel();
          const utterance = new SpeechSynthesisUtterance(responseText);
          utterance.lang = 'hi-IN';
          utterance.rate = 1;
          window.speechSynthesis.speak(utterance);
        }}
        </script>
        """, height=35)

    with c3:
        st.download_button(
            "↗ Share",
            data=content,
            file_name="NEXTGEN_AI_Response.txt",
            mime="text/plain",
            key=f"share_{message_id}",
            use_container_width=True
        )

    with c4:
        with st.popover("⋯"):
            st.caption("Response options")
            if st.button("👍 Helpful", key=f"like_{message_id}"):
                save_feedback(message_id, "like")
                st.toast("Thanks for your feedback!")

            if st.button("👎 Not helpful", key=f"dislike_{message_id}"):
                save_feedback(message_id, "dislike")
                st.toast("Feedback saved.")

            if st.button("Copy as text", key=f"copy_{message_id}"):
                st.code(content)

def save_feedback(message_id, reaction):
    con = db()
    cur = con.cursor()
    cur.execute("""
        INSERT INTO feedback (message_id, reaction, created_at)
        VALUES (?, ?, ?)
    """, (message_id, reaction, datetime.now().isoformat()))
    con.commit()
    con.close()

# =========================================================
# SESSION STATE
# =========================================================

if "page" not in st.session_state:
    st.session_state.page = "Dashboard"

if "chat_id" not in st.session_state:
    chats = get_chats()
    st.session_state.chat_id = chats[0][0] if chats else create_chat()

if "last_prompt" not in st.session_state:
    st.session_state.last_prompt = ""

if "last_answer" not in st.session_state:
    st.session_state.last_answer = ""

# =========================================================
# SIDEBAR
# =========================================================

with st.sidebar:
    st.markdown('<div class="brand">✦ NEXTGEN AI</div>',
                unsafe_allow_html=True)
    st.caption("Your Creative Universe")
    st.markdown("---")

    if st.button("＋ New Chat", use_container_width=True):
        st.session_state.chat_id = create_chat()
        st.session_state.page = "AI Chat"
        st.session_state.last_prompt = ""
        st.rerun()

    st.markdown("### Workspace")

    pages = [
        "Dashboard",
        "AI Chat",
        "AI Image Studio",
        "Tool Center",
        "PDF Assistant"
    ]

    for page in pages:
        if st.button(
            page,
            key=f"nav_{page}",
            use_container_width=True
        ):
            st.session_state.page = page
            st.rerun()

    st.markdown("### Library")

    for page in [
        "Chat History",
        "My Creations",
        "Creator Profile",
        "Settings",
        "About"
    ]:
        if st.button(
            page,
            key=f"nav_{page}",
            use_container_width=True
        ):
            st.session_state.page = page
            st.rerun()

    st.markdown("---")
    st.markdown(
        '<span class="small-status">✦ NEXTGEN AI Ready</span>',
        unsafe_allow_html=True
    )
    st.caption("VERSION MAX · Created by Arav")

# =========================================================
# PAGE: DASHBOARD
# =========================================================

page = st.session_state.page

if page == "Dashboard":

    st.markdown("""
    <div class="hero">
      <span class="small-status">✦ AI ENGINE ACTIVE</span>
      <h1>Welcome to NEXTGEN AI</h1>
      <p>One Platform. Endless Possibilities.</p>
      <p>Your intelligent workspace for creativity, learning and productivity.</p>
    </div>
    """, unsafe_allow_html=True)

    m1, m2, m3, m4 = st.columns(4)

    metrics = [
        ("AI Workflows", f"{TOOL_COUNT}+"),
        ("AI Workspace", "All-in-One"),
        ("Chat History", str(len(get_chats()))),
        ("Version", "MAX")
    ]

    for col, (label, value) in zip(
        [m1, m2, m3, m4], metrics
    ):
        with col:
            st.markdown(f"""
            <div class="metric">
              <div class="metric-label">{label}</div>
              <div class="metric-value">{value}</div>
            </div>
            """, unsafe_allow_html=True)

    st.markdown("## Explore Your Workspace")

    features = [
        ("💬 AI Chat", "Chat with your intelligent assistant."),
        ("🎨 AI Image Studio", "Create images from your ideas."),
        ("🧰 Tool Center", "Explore 550 AI task workflows."),
        ("📄 PDF Assistant", "Ask questions about your documents."),
        ("📚 Chat History", "Continue your previous conversations."),
        ("👤 Creator Profile", "Discover the creator of NEXTGEN AI.")
    ]

    cols = st.columns(3)

    for i, (name, desc) in enumerate(features):
        with cols[i % 3]:
            st.markdown(f"""
            <div class="panel">
              <h3>{name}</h3>
              <p style="color:#aeb7d5">{desc}</p>
            </div>
            """, unsafe_allow_html=True)

            if st.button(
                f"Open {name}",
                key=f"open_{i}",
                use_container_width=True
            ):
                target = name.replace("💬 ", "").replace(
                    "🎨 ", ""
                ).replace("🧰 ", "").replace(
                    "📄 ", ""
                ).replace("📚 ", "").replace(
                    "👤 ", ""
                )
                st.session_state.page = target
                st.rerun()

# =========================================================
# PAGE: AI CHAT
# =========================================================

elif page == "AI Chat":

    st.markdown("""
    <div class="hero">
      <h1>💬 AI Chat</h1>
      <p>Ask anything. Create anything. Learn anything.</p>
    </div>
    """, unsafe_allow_html=True)

    chat_id = st.session_state.chat_id
    messages = get_messages(chat_id)

    for message_id, role, content in messages:
        if role == "user":
            st.markdown(
                f'<div class="chat-user">{content}</div>',
                unsafe_allow_html=True
            )
        else:
            st.markdown(
                f'<div class="chat-ai">{content}</div>',
                unsafe_allow_html=True
            )
            chat_actions(message_id, content)

    audio_file = st.file_uploader(
        "🎙️ Optional voice message",
        type=["wav", "mp3", "m4a", "ogg"],
        key="chat_audio"
    )

    if audio_file:
        if st.button("Transcribe Voice"):
            transcript = transcribe_audio(audio_file)
            if transcript:
                st.session_state.voice_text = transcript
                st.success("Voice converted to text.")
                st.text_area("Transcription", transcript)
            else:
                st.error("Voice transcription could not be completed.")

    prompt = st.chat_input("Message NEXTGEN AI...")

    if prompt:
        st.session_state.last_prompt = prompt

        save_message(chat_id, "user", prompt)

        with st.spinner("NEXTGEN AI is thinking..."):
            api_messages = build_messages(chat_id, prompt)
            answer = ask_ai(api_messages)

        st.session_state.last_answer = answer
        save_message(chat_id, "assistant", answer)
        st.rerun()

    if st.session_state.last_prompt:
        if st.button("↻ Regenerate Last Response"):
            with st.spinner("Generating a new response..."):
                history = get_messages(chat_id)
                previous = [
                    {"role": role, "content": content}
                    for _, role, content in history[:-1]
                    if role in ("user", "assistant")
                ]
                previous.append({
                    "role": "user",
                    "content": st.session_state.last_prompt
                })

                answer = ask_ai(
                    [{"role": "system", "content": SYSTEM_PROMPT}]
                    + previous
                )

                update_last_assistant(chat_id, answer)
                st.session_state.last_answer = answer
                st.rerun()

    voice_url = get_secret("CLOUDFLARE_VOICE_URL")
    if voice_url:
        st.link_button("🎧 Open Voice Experience", voice_url)
    else:
        st.caption(
            "Voice conversation service is not configured yet. "
            "Read Aloud and voice transcription are separate features."
        )

# =========================================================
# PAGE: AI IMAGE STUDIO
# =========================================================

elif page == "AI Image Studio":

    st.markdown("""
    <div class="hero">
      <h1>🎨 AI Image Studio</h1>
      <p>Turn your imagination into visuals.</p>
    </div>
    """, unsafe_allow_html=True)

    prompt = st.text_area(
        "Describe the image you want to create",
        placeholder="A cinematic futuristic city at night..."
    )

    reference = st.file_uploader(
        "Optional reference image",
        type=["png", "jpg", "jpeg"]
    )

    if reference:
        st.image(reference, caption="Reference image")

    if st.button("✦ Generate Image", use_container_width=True):
        if not prompt.strip():
            st.warning("Please enter an image prompt.")
        else:
            with st.spinner("Creating your image..."):
                image_bytes, error = generate_image(prompt)

            if image_bytes:
                st.image(image_bytes, use_container_width=True)
                save_creation(prompt, image_bytes)

                st.download_button(
                    "Download Image",
                    data=image_bytes,
                    file_name="nextgen_ai_image.png",
                    mime="image/png"
                )
                st.success("Image created and saved to My Creations.")
            else:
                st.error(error or "Image generation failed.")

    st.caption(
        "Reference images are currently shown as references; "
        "this page does not perform image editing."
    )

# =========================================================
# PAGE: TOOL CENTER
# =========================================================

elif page == "Tool Center":

    st.markdown("""
    <div class="hero">
      <h1>🧰 AI Tool Center</h1>
      <p>Explore your AI workflow library.</p>
    </div>
    """, unsafe_allow_html=True)

    st.markdown(
        f"**{TOOL_COUNT} named AI workflows available**"
    )

    category = st.selectbox(
        "Choose a category",
        list(TOOL_LIBRARY.keys())
    )

    selected_tool = st.selectbox(
        "Choose a tool",
        TOOL_LIBRARY[category]
    )

    user_input = st.text_area(
        "What would you like this tool to do?",
        placeholder="Describe your task..."
    )

    if st.button("Run AI Tool", use_container_width=True):
        if not user_input.strip():
            st.warning("Enter your task first.")
        else:
            tool_prompt = f"""
            Use this workflow: {selected_tool}

            User's task:
            {user_input}

            Provide a complete, useful, well-structured result.
            Explain assumptions. Do not invent facts.
            """

            with st.spinner("Running your AI workflow..."):
                result = ask_ai([
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": tool_prompt}
                ])

            st.markdown("### Result")
            st.markdown(result)

            st.download_button(
                "Download Result",
                data=result,
                file_name="nextgen_ai_tool_result.txt",
                mime="text/plain"
            )

# =========================================================
# PAGE: PDF ASSISTANT
# =========================================================

elif page == "PDF Assistant":

    st.markdown("""
    <div class="hero">
      <h1>📄 PDF Assistant</h1>
      <p>Upload a PDF and ask questions about its content.</p>
    </div>
    """, unsafe_allow_html=True)

    pdf_file = st.file_uploader(
        "Upload your PDF",
        type=["pdf"]
    )

    if pdf_file:
        try:
            reader = PdfReader(io.BytesIO(pdf_file.getvalue()))
            pdf_text = "\n".join(
                page.extract_text() or ""
                for page in reader.pages
            )

            st.success(
                f"PDF loaded · {len(reader.pages)} pages"
            )

            st.text_area(
                "Extracted text preview",
                pdf_text[:5000],
                height=180
            )

            question = st.text_input(
                "Ask a question about this PDF"
            )

            if st.button("Ask About PDF"):
                if question.strip():
                    pdf_prompt = f"""
                    Answer using the following PDF content.
                    If the answer is not present, say so honestly.

                    PDF CONTENT:
                    {pdf_text[:25000]}

                    QUESTION:
                    {question}
                    """

                    with st.spinner("Reading your document..."):
                        answer = ask_ai([
                            {"role": "system", "content": SYSTEM_PROMPT},
                            {"role": "user", "content": pdf_prompt}
                        ])

                    st.markdown("### Answer")
                    st.markdown(answer)

        except Exception as e:
            st.error(f"Could not read this PDF: {e}")

# =========================================================
# PAGE: CHAT HISTORY
# =========================================================

elif page == "Chat History":

    st.markdown("""
    <div class="hero">
      <h1>📚 Chat History</h1>
      <p>Your previous conversations.</p>
    </div>
    """, unsafe_allow_html=True)

    chats = get_chats()

    if not chats:
        st.info("No conversations yet.")
    else:
        for chat_id, title, created in chats:
            col1, col2, col3 = st.columns([4, 1, 1])

            with col1:
                st.markdown(
                    f"**{title or 'New Chat'}**"
                )
                st.caption(created[:19])

            with col2:
                if st.button("Open", key=f"history_open_{chat_id}"):
                    st.session_state.chat_id = chat_id
                    st.session_state.page = "AI Chat"
                    st.rerun()

            with col3:
                if st.button("Delete", key=f"history_delete_{chat_id}"):
                    delete_chat(chat_id)
                    if st.session_state.chat_id == chat_id:
                        st.session_state.chat_id = create_chat()
                    st.rerun()

# =========================================================
# PAGE: MY CREATIONS
# =========================================================

elif page == "My Creations":

    st.markdown("""
    <div class="hero">
      <h1>🖼️ My Creations</h1>
      <p>Your generated images.</p>
    </div>
    """, unsafe_allow_html=True)

    con = db()
    cur = con.cursor()
    cur.execute("""
        SELECT id, prompt, image, created_at
        FROM creations ORDER BY id DESC
    """)
    creations = cur.fetchall()
    con.close()

    if not creations:
        st.info("Your generated images will appear here.")
    else:
        for creation_id, prompt, image_bytes, created in creations:
            st.markdown(f"**{prompt}**")
            st.caption(created[:19])
            st.image(image_bytes, use_container_width=True)

            st.download_button(
                "Download",
                data=image_bytes,
                file_name=f"creation_{creation_id}.png",
                mime="image/png",
                key=f"creation_download_{creation_id}"
            )

# =========================================================
# PAGE: CREATOR PROFILE
# =========================================================

elif page == "Creator Profile":

    st.markdown("""
    <div class="hero">
      <span class="small-status">FOUNDER & CREATOR</span>
      <h1>Meet Arav</h1>
      <p>The creator behind NEXTGEN AI.</p>
    </div>
    """, unsafe_allow_html=True)

    st.markdown("""
    <div class="panel">
      <h2>👨‍💻 About Arav</h2>
      <p>
      Arav is a student with a strong interest in Artificial
      Intelligence, technology and digital creativity.
      </p>
      <p>
      He is developing NEXTGEN AI, an AI-powered platform designed
      to bring chat assistance, creative tools, image generation,
      document assistance and productivity workflows together
      in one workspace.
      </p>
      <p>
      He is also interested in coding, app development and
      content creation. His creative project includes ARAVYX.
      </p>
      <p>
      His goal is to keep learning, building and improving
      NEXTGEN AI step by step.
      </p>
    </div>
    """, unsafe_allow_html=True)

    st.caption(
        "This profile contains creator information supplied for "
        "NEXTGEN AI. It does not disclose private personal details."
    )

# =========================================================
# PAGE: SETTINGS
# =========================================================

elif page == "Settings":

    st.markdown("""
    <div class="hero">
      <h1>⚙️ Settings</h1>
      <p>Manage your NEXTGEN AI experience.</p>
    </div>
    """, unsafe_allow_html=True)

    st.markdown("### AI Configuration")

    st.markdown(
        '<span class="small-status">NEXTGEN AI Ready</span>',
        unsafe_allow_html=True
    )

    st.caption(
        "AI availability depends on the API configuration "
        "and the provider's service status."
    )

    st.markdown("### Creator Information")
    st.text_area(
        "Creator profile",
        CREATOR_PROFILE,
        height=180,
        disabled=True
    )

    st.markdown("### Local Data")
    st.caption(
        "Chat history, feedback and generated creations are "
        "stored in the local SQLite database."
    )

# =========================================================
# PAGE: ABOUT
# =========================================================

elif page == "About":

    st.markdown("""
    <div class="hero">
      <h1>✦ NEXTGEN AI</h1>
      <p>Your Creative Universe.</p>
    </div>
    """, unsafe_allow_html=True)

    st.markdown("""
    <div class="panel">
      <h2>About NEXTGEN AI</h2>
      <p>
      NEXTGEN AI is an AI-powered workspace created by Arav.
      It brings together AI chat, creative workflows, image
      generation, PDF assistance and productivity features.
      </p>
      <h3>Our Vision</h3>
      <p>
      To make useful AI capabilities accessible through one
      simple and creative platform.
      </p>
      <h3>Version</h3>
      <p>VERSION MAX</p>
      <h3>Creator</h3>
      <p>Arav</p>
    </div>
    """, unsafe_allow_html=True)

# =========================================================
# FOOTER
# =========================================================

st.markdown("---")
st.markdown(
    """
    <div style="text-align:center;color:#858eae;font-size:12px;padding:10px;">
      ✦ NEXTGEN AI · VERSION MAX · Created by Arav
    </div>
    """,
    unsafe_allow_html=True
)
