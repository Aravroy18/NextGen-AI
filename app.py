
import os
import json
import base64
import sqlite3
import requests
import streamlit as st
import streamlit.components.v1 as components
from datetime import datetime

# =========================================================
# NEXTGEN AI — VERSION 4.0
# =========================================================

st.set_page_config(
    page_title="NEXTGEN AI",
    page_icon="✦",
    layout="wide",
    initial_sidebar_state="expanded"
)

# -------------------- CONFIG --------------------

GROQ_MODEL = "openai/gpt-oss-120b"
GEMINI_MODEL = "gemini-3.5-flash-lite"
CF_IMAGE_MODEL = "@cf/black-forest-labs/flux-1-schnell"
CF_WHISPER_MODEL = "@cf/openai/whisper-large-v3-turbo"

def secret(key, default=""):
    try:
        return st.secrets.get(key, os.getenv(key, default))
    except Exception:
        return os.getenv(key, default)

GROQ_KEY = secret("GROQ_API_KEY")
GEMINI_KEY = secret("GEMINI_API_KEY")
CF_ACCOUNT = secret("CLOUDFLARE_ACCOUNT_ID")
CF_TOKEN = secret("CLOUDFLARE_API_TOKEN")
CF_VOICE_URL = secret("CLOUDFLARE_VOICE_URL")

DB = "nextgen_v4.db"

# -------------------- DATABASE --------------------

def db():
    return sqlite3.connect(DB, check_same_thread=False)

def init_db():
    con = db()
    cur = con.cursor()
    cur.execute("""
        CREATE TABLE IF NOT EXISTS conversations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT,
            created TEXT
        )
    """)
    cur.execute("""
        CREATE TABLE IF NOT EXISTS messages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            chat_id INTEGER,
            role TEXT,
            content TEXT,
            created TEXT
        )
    """)
    con.commit()
    con.close()

def new_chat():
    con = db()
    cur = con.cursor()
    cur.execute(
        "INSERT INTO conversations(title, created) VALUES (?,?)",
        ("New Chat", datetime.now().isoformat())
    )
    chat_id = cur.lastrowid
    con.commit()
    con.close()
    return chat_id

def get_chats():
    con = db()
    rows = con.execute(
        "SELECT id,title,created FROM conversations ORDER BY id DESC"
    ).fetchall()
    con.close()
    return rows

def save_message(chat_id, role, content):
    con = db()
    con.execute(
        "INSERT INTO messages(chat_id,role,content,created) VALUES (?,?,?,?)",
        (chat_id, role, content, datetime.now().isoformat())
    )
    con.commit()
    con.close()

def load_messages(chat_id):
    con = db()
    rows = con.execute(
        "SELECT role,content FROM messages WHERE chat_id=? ORDER BY id",
        (chat_id,)
    ).fetchall()
    con.close()
    return rows

def rename_chat(chat_id, title):
    con = db()
    con.execute(
        "UPDATE conversations SET title=? WHERE id=?",
        (title[:60], chat_id)
    )
    con.commit()
    con.close()

def delete_chat(chat_id):
    con = db()
    con.execute("DELETE FROM messages WHERE chat_id=?", (chat_id,))
    con.execute("DELETE FROM conversations WHERE id=?", (chat_id,))
    con.commit()
    con.close()

init_db()

# -------------------- PREMIUM DESIGN --------------------

st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800;900&display=swap');

html, body, [class*="css"] {
    font-family: Inter, sans-serif;
}

.stApp {
    background:
      radial-gradient(ellipse at 15% 0%, #24205b 0%, transparent 38%),
      radial-gradient(ellipse at 90% 10%, #182c51 0%, transparent 34%),
      #080b16;
    color: #f4f5ff;
}

[data-testid="stSidebar"] {
    background: linear-gradient(180deg,#10172b,#0b1020);
    border-right: 1px solid #29314c;
}

[data-testid="stSidebar"] * {
    color: #e8eaff;
}

.block-container {
    padding-top: 1.5rem;
    max-width: 1450px;
}

h1,h2,h3 {
    color: #ffffff !important;
    letter-spacing: -0.7px;
}

.hero {
    padding: 35px;
    border-radius: 25px;
    background: linear-gradient(120deg,#171e3d,#30245e 55%,#182d4b);
    border: 1px solid #55528b;
    box-shadow: 0 15px 55px #0007;
    margin-bottom: 25px;
}

.hero-tag {
    color: #b8adff;
    font-size: 12px;
    font-weight: 800;
    letter-spacing: 3px;
}

.hero-title {
    font-size: clamp(35px,5vw,58px);
    font-weight: 900;
    line-height: 1.1;
    margin: 12px 0;
}

.hero-sub {
    color: #c5c9e5;
    font-size: 15px;
}

.panel {
    background: linear-gradient(145deg,#151d32,#101629);
    border: 1px solid #303b5b;
    border-radius: 19px;
    padding: 22px;
    min-height: 130px;
    box-shadow: 0 8px 30px #0003;
}

.panel-title {
    font-size: 18px;
    font-weight: 800;
    margin-bottom: 9px;
}

.panel-desc {
    color: #aab4d2;
    font-size: 13px;
    line-height: 1.6;
}

.metric {
    background: #141d32;
    border: 1px solid #303b5b;
    border-radius: 16px;
    padding: 17px;
}

.metric-label {
    color: #9eaccb;
    font-size: 12px;
}

.metric-value {
    font-size: 25px;
    font-weight: 900;
    margin-top: 5px;
}

.brand {
    font-size: 25px;
    font-weight: 900;
    letter-spacing: -1px;
    padding: 10px 0 20px;
}

.brand span {
    color: #a99aff;
}

.small-muted {
    color: #9aa7c6;
    font-size: 12px;
}

div.stButton > button {
    border-radius: 12px;
    border: 1px solid #414b70;
    background: linear-gradient(120deg,#252e50,#34285f);
    color: white;
    font-weight: 700;
    min-height: 42px;
    transition: .2s;
}

div.stButton > button:hover {
    border-color: #a99aff;
    background: linear-gradient(120deg,#394575,#514080);
}

div[data-testid="stChatMessage"] {
    background: #141b2d;
    border: 1px solid #2d3854;
    border-radius: 17px;
    padding: 14px;
    margin-bottom: 12px;
}

div[data-testid="stTextInput"] input {
    background: #10172a;
    color: white;
    border: 1px solid #394361;
    border-radius: 12px;
    min-height: 43px;
}

div[data-testid="stFileUploader"] {
    background: #10172a;
    border: 1px dashed #5c6290;
    border-radius: 12px;
    padding: 7px;
}

div[data-testid="stAudioInput"] {
    background: #10172a;
    border: 1px solid #414b70;
    border-radius: 12px;
    padding: 5px;
}

hr {
    border-color: #28324d;
}

footer {visibility: hidden;}
#MainMenu {visibility: hidden;}
</style>
""", unsafe_allow_html=True)

# -------------------- AI ENGINE --------------------

SYSTEM_PROMPT = """
You are NEXTGEN AI, a helpful, accurate, multilingual AI assistant.
Be clear, useful, respectful and honest.
Never invent facts, links, or actions.
The platform creator is Arav.
If asked who created NEXTGEN AI, say it was created by Arav.
Do not invent private information about the creator.
"""

def groq_answer(messages):
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
            "temperature": 0.65,
            "max_tokens": 4096
        },
        timeout=45
    )
    response.raise_for_status()
    answer = response.json()["choices"][0]["message"]["content"]
    if not answer:
        raise RuntimeError("Groq returned an empty answer.")
    return answer

def gemini_answer(messages):
    if not GEMINI_KEY:
        raise RuntimeError("GEMINI_API_KEY is missing.")

    contents = []
    for item in messages:
        contents.append({
            "role": "model" if item["role"] == "assistant" else "user",
            "parts": [{"text": item["content"]}]
        })

    url = (
        "https://generativelanguage.googleapis.com/v1beta/models/"
        f"{GEMINI_MODEL}:generateContent?key={GEMINI_KEY}"
    )

    response = requests.post(
        url,
        json={
            "system_instruction": {
                "parts": [{"text": SYSTEM_PROMPT}]
            },
            "contents": contents,
            "generationConfig": {
                "temperature": 0.65,
                "maxOutputTokens": 4096
            }
        },
        timeout=35
    )
    response.raise_for_status()
    data = response.json()
    return data["candidates"][0]["content"]["parts"][0]["text"]

def ask_ai(messages):
    # Main: Groq. Backup: exactly one Gemini attempt.
    try:
        return groq_answer(messages), "Groq"
    except Exception as groq_error:
        if not GEMINI_KEY:
            raise RuntimeError(
                f"Groq failed and Gemini backup is not configured. "
                f"Groq error: {groq_error}"
            )
        try:
            return gemini_answer(messages), "Gemini Backup"
        except Exception as gemini_error:
            raise RuntimeError(
                "Both AI services failed. "
                f"Groq: {groq_error} | Gemini: {gemini_error}"
            )

# -------------------- CLOUDFLARE HELPERS --------------------

def cloudflare_endpoint(model):
    if not CF_ACCOUNT or not CF_TOKEN:
        raise RuntimeError("Cloudflare Account ID or API Token missing.")
    return (
        "https://api.cloudflare.com/client/v4/accounts/"
        f"{CF_ACCOUNT}/ai/run/{model}"
    )

def generate_image(prompt):
    response = requests.post(
        cloudflare_endpoint(CF_IMAGE_MODEL),
        headers={
            "Authorization": f"Bearer {CF_TOKEN}",
            "Content-Type": "application/json"
        },
        json={"prompt": prompt, "steps": 4},
        timeout=120
    )
    response.raise_for_status()
    data = response.json()

    image_data = data.get("result", {}).get("image")
    if not image_data:
        raise RuntimeError(f"Cloudflare image response: {data}")

    return base64.b64decode(image_data)

def transcribe_audio(audio_file):
    audio_b64 = base64.b64encode(audio_file.getvalue()).decode("utf-8")
    response = requests.post(
        cloudflare_endpoint(CF_WHISPER_MODEL),
        headers={
            "Authorization": f"Bearer {CF_TOKEN}",
            "Content-Type": "application/json"
        },
        json={"audio": audio_b64, "task": "transcribe"},
        timeout=90
    )
    response.raise_for_status()
    result = response.json().get("result", {})
    return result.get("text", "")

# -------------------- SESSION --------------------

if "chat_id" not in st.session_state:
    st.session_state.chat_id = new_chat()

if "messages" not in st.session_state:
    st.session_state.messages = []

if "page" not in st.session_state:
    st.session_state.page = "Dashboard"

if "pending_prompt" not in st.session_state:
    st.session_state.pending_prompt = ""

if "attachment_text" not in st.session_state:
    st.session_state.attachment_text = ""

# -------------------- SIDEBAR --------------------

with st.sidebar:
    st.markdown(
        '<div class="brand">✦ NEXTGEN<span> AI</span></div>',
        unsafe_allow_html=True
    )
    st.caption("YOUR CREATIVE INTELLIGENCE PLATFORM")
    st.markdown("---")

    if st.button("＋  New Chat", use_container_width=True):
        st.session_state.chat_id = new_chat()
        st.session_state.messages = []
        st.session_state.page = "AI Chat"
        st.rerun()

    st.markdown("### WORKSPACE")

    pages = {
        "⌂  Dashboard": "Dashboard",
        "✦  AI Chat": "AI Chat",
        "▧  AI Image Studio": "AI Image Studio",
        "⌕  Tool Center": "Tool Center",
        "▤  PDF Assistant": "PDF Assistant",
        "◷  Chat History": "Chat History",
        "▣  My Creations": "My Creations",
        "⚙  Settings": "Settings",
        "ⓘ  About": "About"
    }

    for label, page in pages.items():
        if st.button(label, key=f"nav_{page}", use_container_width=True):
            st.session_state.page = page
            st.rerun()

    st.markdown("---")
    st.markdown("### RECENT CHATS")

    chats = get_chats()
    for chat in chats[:8]:
        title = chat[1] or "New Chat"
        if st.button("▸ " + title[:24], key=f"history_{chat[0]}",
                     use_container_width=True):
            st.session_state.chat_id = chat[0]
            st.session_state.messages = load_messages(chat[0])
            st.session_state.page = "AI Chat"
            st.rerun()

    st.markdown("---")
    st.markdown(
        '<div class="small-muted">NEXTGEN AI • VERSION 4.0<br>'
        'Built for creativity, learning and productivity.</div>',
        unsafe_allow_html=True
    )

# -------------------- PAGE HEADER --------------------

page = st.session_state.page

def hero(title, subtitle, tag="NEXTGEN AI PLATFORM"):
    st.markdown(f"""
    <div class="hero">
      <div class="hero-tag">{tag}</div>
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

# =========================================================
# DASHBOARD
# =========================================================

if page == "Dashboard":
    hero(
        "Think Beyond Limits.",
        "One intelligent workspace for ideas, answers, creativity and productivity."
    )

    a, b, c, d = st.columns(4)
    with a:
        metric("AI ENGINE", "GROQ", "Primary assistant")
    with b:
        metric("BACKUP ENGINE", "GEMINI", "Automatic one-time fallback")
    with c:
        metric("IMAGE ENGINE", "CLOUDFLARE", "FLUX image generation")
    with d:
        metric("WORKSPACE", "ALL-IN-ONE", "Your AI creative space")

    st.markdown("## Explore your workspace")

    cards = [
        ("✦", "AI Chat", "Ask questions, brainstorm, learn and create."),
        ("▧", "AI Image Studio", "Generate images from your imagination."),
        ("⌕", "Tool Center", "Writing, study, coding and productivity tools."),
        ("▤", "PDF Assistant", "Upload a PDF and ask questions about it.")
    ]

    cols = st.columns(2)
    for i, (icon, title, desc) in enumerate(cards):
        with cols[i % 2]:
            st.markdown(f"""
            <div class="panel">
              <div style="font-size:27px">{icon}</div>
              <div class="panel-title">{title}</div>
              <div class="panel-desc">{desc}</div>
            </div>
            """, unsafe_allow_html=True)
            if st.button("Open " + title, key=f"open_{title}",
                         use_container_width=True):
                st.session_state.page = title
                st.rerun()

    st.markdown("## Built for your ideas")
    st.markdown("""
    - **Smart AI Chat:** Groq first, Gemini only if the main request fails.
    - **Creative Studio:** Cloudflare image generation.
    - **Voice Input:** Record your prompt from the chat composer.
    - **File Attachments:** Add documents to your conversation.
    - **Chat History:** Return to your previous conversations.
    """)

# =========================================================
# AI CHAT
# =========================================================

elif page == "AI Chat":
    st.markdown("## ✦ AI Chat")
    st.caption("Your intelligent assistant • Groq primary • Gemini backup")

    # Display conversation
    for role, content in st.session_state.messages:
        with st.chat_message(role):
            st.markdown(content)

    # -------------------- COMPOSER --------------------
    # All composer controls are placed inside one bordered container.
    with st.container(border=True):
        st.markdown(
            '<div style="font-weight:800;margin-bottom:8px">'
            '✦ Message NEXTGEN AI</div>',
            unsafe_allow_html=True
        )

        col_plus, col_input, col_mic, col_live, col_send = st.columns(
            [0.8, 5.0, 1.1, 1.25, 0.9],
            vertical_alignment="center"
        )

        with col_plus:
            st.markdown("**＋**")
            attachment = st.file_uploader(
                " ",
                type=["txt", "pdf", "png", "jpg", "jpeg"],
                key="chat_attachment",
                label_visibility="collapsed"
            )

        with col_input:
            prompt = st.text_input(
                "Message",
                placeholder="Ask anything...",
                label_visibility="collapsed",
                key="chat_prompt"
            )

        with col_mic:
            audio = st.audio_input(
                "Mic",
                key="chat_mic",
                label_visibility="collapsed"
            )

        with col_live:
            if CF_VOICE_URL:
                st.link_button("◉ Live", CF_VOICE_URL,
                               use_container_width=True)
            else:
                st.button(
                    "◉ Live",
                    disabled=True,
                    help="Configure CLOUDFLARE_VOICE_URL to enable Cloudflare Live Voice.",
                    use_container_width=True
                )

        with col_send:
            send = st.button("➤", key="send_chat", use_container_width=True)

        # Attachment extraction
        attachment_content = ""
        if attachment is not None:
            if attachment.name.lower().endswith(".txt"):
                attachment_content = attachment.getvalue().decode(
                    "utf-8", errors="ignore"
                )
            elif attachment.name.lower().endswith(".pdf"):
                try:
                    from pypdf import PdfReader
                    import io
                    reader = PdfReader(io.BytesIO(attachment.getvalue()))
                    attachment_content = "\n".join(
                        page.extract_text() or "" for page in reader.pages
                    )
                except Exception as e:
                    st.error(f"Could not read PDF: {e}")
            else:
                st.info("Image attached. Image understanding is not enabled in this build.")

        # Microphone transcription through Cloudflare Whisper
        if audio is not None:
            if st.button("Transcribe microphone recording", key="transcribe_mic"):
                try:
                    transcript = transcribe_audio(audio)
                    st.session_state.chat_prompt = transcript
                    st.success("Voice converted to text. Press ➤ to send.")
                    st.rerun()
                except Exception as e:
                    st.error(f"Cloudflare transcription error: {e}")

        if send:
            user_prompt = (prompt or "").strip()

            if attachment_content:
                user_prompt += (
                    "\n\n[Attached document content]\n" +
                    attachment_content[:25000]
                )

            if user_prompt:
                st.session_state.messages.append(("user", user_prompt))
                save_message(st.session_state.chat_id, "user", user_prompt)

                # Rename chat from first message
                if len(st.session_state.messages) == 1:
                    rename_chat(st.session_state.chat_id, user_prompt[:45])

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

    if st.session_state.messages:
        st.caption(
            "Last response provider: " +
            st.session_state.get("last_provider", "Automatic")
        )

    st.caption(
        "Plus = attachment • Mic = voice-to-text • Live = Cloudflare Voice Agent"
    )

# =========================================================
# AI IMAGE STUDIO
# =========================================================

elif page == "AI Image Studio":
    hero(
        "AI Image Studio",
        "Turn your imagination into images using Cloudflare Workers AI."
    )

    prompt = st.text_area(
        "Describe the image you want",
        placeholder="A cinematic futuristic city at night, dramatic lighting...",
        height=130
    )

    if st.button("✦ Generate Image", use_container_width=True):
        if not prompt.strip():
            st.warning("Write an image prompt first.")
        else:
            with st.spinner("Creating your image with Cloudflare..."):
                try:
                    image_bytes = generate_image(prompt)
                    st.image(image_bytes, caption="Generated with Cloudflare FLUX")
                    st.download_button(
                        "Download Image",
                        data=image_bytes,
                        file_name="nextgen_ai_image.jpg",
                        mime="image/jpeg"
                    )
                except Exception as e:
                    st.error(f"Image generation failed: {e}")

# =========================================================
# TOOL CENTER
# =========================================================

elif page == "Tool Center":
    hero(
        "AI Tool Center",
        "A collection of practical AI-powered tools for everyday work."
    )

    tools = {
        "Writing": [
            "Email Writer", "Formal Letter Writer", "Essay Writer",
            "Application Writer", "Notice Writer", "Speech Writer",
            "Story Writer", "Paragraph Writer", "Article Writer",
            "Resume Helper", "Cover Letter Writer", "Report Writer",
            "Blog Writer", "Social Media Caption", "Product Description",
            "YouTube Description", "Video Script", "Ad Copy",
            "Invitation Writer", "Thank You Note"
        ],
        "Study": [
            "Explain a Topic", "Short Notes", "Detailed Notes",
            "Quiz Maker", "MCQ Maker", "Flashcard Maker",
            "Question Answer Maker", "Chapter Summary",
            "Practice Worksheet", "Study Planner", "Vocabulary Builder",
            "Grammar Helper", "Maths Explanation", "Science Explainer",
            "History Explainer", "Geography Explainer"
        ],
        "Developer": [
            "Python Helper", "HTML Generator", "CSS Helper",
            "JavaScript Helper", "Debugging Assistant", "Code Explainer",
            "SQL Helper", "Regex Helper", "API Explainer",
            "Website Planner", "App Idea Generator", "JSON Formatter"
        ],
        "Business": [
            "Business Idea Generator", "Business Plan Writer",
            "Brand Name Generator", "Slogan Generator",
            "Marketing Planner", "Customer Reply Writer",
            "Product Research Planner", "Presentation Outline",
            "Meeting Summary", "Project Planner"
        ],
        "Creator": [
            "YouTube Ideas", "Reel Ideas", "Thumbnail Ideas",
            "Video Hook Generator", "Scene Prompt Writer",
            "Image Prompt Writer", "Voiceover Script",
            "Character Creator", "Story Plot Generator",
            "Content Calendar", "Hashtag Ideas", "Channel Bio Writer"
        ],
        "Language": [
            "Hindi to English", "English to Hindi", "Text Rewriter",
            "Proofreader", "Grammar Correction", "Simple Explanation",
            "Professional Tone", "Friendly Tone", "Text Summarizer",
            "Translation Helper"
        ],
        "Everyday": [
            "Daily Planner", "Checklist Maker", "Decision Helper",
            "Gift Ideas", "Travel Planner", "Recipe Ideas",
            "Routine Planner", "Goal Planner", "Problem Solver",
            "Brainstorming Assistant"
        ]
    }

    category = st.selectbox("Choose a category", list(tools.keys()))
    selected_tool = st.selectbox("Choose your tool", tools[category])

    tool_prompt = st.text_area(
        "Enter your details",
        placeholder=f"Tell AI what you need for {selected_tool}...",
        height=130
    )

    if st.button("Run Tool ✦", use_container_width=True):
        if tool_prompt.strip():
            request_text = (
                f"Use the following tool: {selected_tool}.\n"
                f"User's requirements:\n{tool_prompt}"
            )
            with st.spinner("Working..."):
                try:
                    result, provider = ask_ai([
                        {"role": "user", "content": request_text}
                    ])
                    st.markdown("### Result")
                    st.markdown(result)
                    st.caption(f"Generated using {provider}")
                except Exception as e:
                    st.error(str(e))
        else:
            st.warning("Enter your requirements first.")

    total_tools = sum(len(v) for v in tools.values())
    st.caption(f"{total_tools}+ tool presets available.")

# =========================================================
# PDF ASSISTANT
# =========================================================

elif page == "PDF Assistant":
    hero(
        "PDF Assistant",
        "Upload a PDF and ask questions about its readable text."
    )

    pdf = st.file_uploader("Upload PDF", type=["pdf"], key="pdf_page")

    if pdf:
        try:
            from pypdf import PdfReader
            import io
            reader = PdfReader(io.BytesIO(pdf.getvalue()))
            pdf_text = "\n".join(
                page.extract_text() or "" for page in reader.pages
            )
            st.success(f"PDF loaded • {len(reader.pages)} pages")
            question = st.text_input("Ask something about this PDF")

            if st.button("Ask about PDF"):
                if question.strip():
                    with st.spinner("Reading your PDF..."):
                        answer, provider = ask_ai([{
                            "role": "user",
                            "content": (
                                "Answer using this PDF text:\n" +
                                pdf_text[:45000] +
                                "\n\nQuestion: " + question
                            )
                        }])
                    st.markdown(answer)
                    st.caption(provider)
        except Exception as e:
            st.error(f"PDF error: {e}")

# =========================================================
# CHAT HISTORY
# =========================================================

elif page == "Chat History":
    hero("Chat History", "Your previous conversations in one place.")

    for chat in get_chats():
        chat_id, title, created = chat
        with st.expander(f"{title}  •  {created[:16]}"):
            col1, col2 = st.columns(2)

            with col1:
                if st.button("Open Chat", key=f"open_chat_{chat_id}"):
                    st.session_state.chat_id = chat_id
                    st.session_state.messages = load_messages(chat_id)
                    st.session_state.page = "AI Chat"
                    st.rerun()

            with col2:
                if st.button("Delete", key=f"delete_chat_{chat_id}"):
                    delete_chat(chat_id)
                    if st.session_state.chat_id == chat_id:
                        st.session_state.chat_id = new_chat()
                        st.session_state.messages = []
                    st.rerun()

# =========================================================
# MY CREATIONS
# =========================================================

elif page == "My Creations":
    hero(
        "My Creations",
        "Your saved work and generated content."
    )
    st.info(
        "Your chat conversations are available in Chat History. "
        "A separate cloud-based creations gallery can be added with persistent storage."
    )

# =========================================================
# SETTINGS
# =========================================================

elif page == "Settings":
    hero("Settings", "Manage your NEXTGEN AI configuration.")

    st.markdown("### AI routing")
    st.success(f"Main model: {GROQ_MODEL}")
    st.success(f"Backup model: {GEMINI_MODEL}")
    st.info("Model selection is automatic. No model selector is shown.")

    st.markdown("### Cloudflare")
    st.write(f"Image model: `{CF_IMAGE_MODEL}`")
    st.write(f"Voice transcription: `{CF_WHISPER_MODEL}`")
    st.write(
        "Live Voice URL: Configured"
        if CF_VOICE_URL else
        "Live Voice URL: Not configured"
    )

    st.markdown("### API configuration")
    st.caption(
        "Add API keys in Streamlit Cloud → Settings → Secrets. "
        "Never paste secret keys into public code or GitHub."
    )

# =========================================================
# ABOUT
# =========================================================

elif page == "About":
    hero(
        "About NEXTGEN AI",
        "One platform. Endless possibilities."
    )

    st.markdown("""
    ## Created by Arav

    NEXTGEN AI is an independent AI platform built to bring together
    learning, creativity, writing, productivity and intelligent assistance.

    **Main AI:** Groq  
    **Backup AI:** Gemini  
    **Image AI:** Cloudflare Workers AI  
    **Voice services:** Cloudflare integration
    """)

    st.caption("NEXTGEN AI © 2026")
