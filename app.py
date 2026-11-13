
import os
import io
import json
import sqlite3
import hashlib
import secrets
import datetime
import streamlit as st
import streamlit.components.v1 as components
import requests

from groq import Groq
from google import genai
from pypdf import PdfReader


# =========================================================
# CONFIG
# =========================================================

st.set_page_config(
    page_title="NEXTGEN AI",
    page_icon="🚀",
    layout="wide",
    initial_sidebar_state="expanded"
)

def get_secret(name):
    try:
        return st.secrets.get(name, os.getenv(name, ""))
    except Exception:
        return os.getenv(name, "")

GROQ_KEY = get_secret("GROQ_API_KEY")
GEMINI_KEY = get_secret("GEMINI_API_KEY")
TAVILY_KEY = get_secret("TAVILY_API_KEY")

LIVE_MODEL = "gemini-3.8-live"
DB = "nextgen_ai.db"


# =========================================================
# DATABASE
# =========================================================

def db():
    return sqlite3.connect(DB, check_same_thread=False)

def init_db():
    con = db()
    cur = con.cursor()

    cur.execute("""
        CREATE TABLE IF NOT EXISTS users(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE,
            password TEXT
        )
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS conversations(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            title TEXT,
            created_at TEXT
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
    hashed = hashlib.pbkdf2_hmac(
        "sha256",
        password.encode(),
        salt.encode(),
        200000
    ).hex()
    return salt + ":" + hashed


def verify_password(password, stored):
    try:
        salt, old_hash = stored.split(":")
        new_hash = hashlib.pbkdf2_hmac(
            "sha256",
            password.encode(),
            salt.encode(),
            200000
        ).hex()
        return secrets.compare_digest(new_hash, old_hash)
    except Exception:
        return False


def register_user(username, password):
    con = db()
    try:
        con.execute(
            "INSERT INTO users(username,password) VALUES(?,?)",
            (username, hash_password(password))
        )
        con.commit()
        return True
    except sqlite3.IntegrityError:
        return False
    finally:
        con.close()


def login_user(username, password):
    con = db()
    row = con.execute(
        "SELECT id,password FROM users WHERE username=?",
        (username,)
    ).fetchone()
    con.close()

    if row and verify_password(password, row[1]):
        return row[0]
    return None


def new_chat(user_id):
    con = db()
    cur = con.cursor()
    cur.execute(
        "INSERT INTO conversations(user_id,title,created_at) VALUES(?,?,?)",
        (
            user_id,
            "New Chat",
            datetime.datetime.now().isoformat()
        )
    )
    cid = cur.lastrowid
    con.commit()
    con.close()
    return cid


def get_chats(user_id):
    con = db()
    rows = con.execute(
        """SELECT id,title FROM conversations
           WHERE user_id=? ORDER BY id DESC""",
        (user_id,)
    ).fetchall()
    con.close()
    return rows


def save_message(cid, role, content):
    con = db()
    con.execute(
        """INSERT INTO messages
           (conversation_id,role,content,created_at)
           VALUES(?,?,?,?)""",
        (cid, role, content, datetime.datetime.now().isoformat())
    )
    con.commit()
    con.close()


def get_messages(cid):
    con = db()
    rows = con.execute(
        """SELECT role,content FROM messages
           WHERE conversation_id=? ORDER BY id""",
        (cid,)
    ).fetchall()
    con.close()
    return [{"role": r, "content": c} for r, c in rows]


def update_chat_title(cid, title):
    con = db()
    con.execute(
        "UPDATE conversations SET title=? WHERE id=? AND title='New Chat'",
        (title[:45], cid)
    )
    con.commit()
    con.close()


def delete_chat(cid):
    con = db()
    con.execute("DELETE FROM messages WHERE conversation_id=?", (cid,))
    con.execute("DELETE FROM conversations WHERE id=?", (cid,))
    con.commit()
    con.close()


# =========================================================
# AI + WEB SEARCH
# =========================================================

def web_search(query):
    if not TAVILY_KEY:
        return ""

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

        output = []

        if data.get("answer"):
            output.append("Search summary: " + data["answer"])

        for item in data.get("results", []):
            output.append(
                item.get("title", "") + "\n" +
                item.get("content", "") + "\n" +
                item.get("url", "")
            )

        return "\n\n".join(output)

    except Exception as e:
        return "Web search unavailable: " + str(e)


def should_search(query):
    q = query.lower()

    keywords = [
        "today", "latest", "current", "news", "weather",
        "price today", "2026", "right now", "recent",
        "आज", "ताजा", "अभी", "लेटेस्ट", "समाचार",
        "मौसम", "आज का भाव", "वर्तमान"
    ]

    return any(word in q for word in keywords)


def ai_reply(history, prompt):
    if not GROQ_KEY:
        return "GROQ_API_KEY configured नहीं है।"

    context = ""

    if should_search(prompt):
        context = web_search(prompt)

    system = """
You are NEXTGEN AI, a helpful AI assistant created by Arav Roy.

Be accurate, friendly and clear.
Reply in the language used by the user.
Use Hindi in Devanagari when the user writes in Hindi.
Never invent facts, sources or capabilities.
If web search context is supplied, use it carefully.
"""

    if context:
        system += "\n\nWEB SEARCH CONTEXT:\n" + context

    try:
        client = Groq(api_key=GROQ_KEY)

        messages = [{"role": "system", "content": system}]

        for item in history[-16:]:
            if item["role"] in ["user", "assistant"]:
                messages.append({
                    "role": item["role"],
                    "content": item["content"]
                })

        messages.append({"role": "user", "content": prompt})

        result = client.chat.completions.create(
            model="openai/gpt-oss-120b",
            messages=messages,
            temperature=0.7,
            max_tokens=2500
        )

        answer = result.choices[0].message.content

        if context:
            answer += "\n\n---\n**Web search was used for this answer.**"

        return answer

    except Exception as e:
        return "AI error: " + str(e)


# =========================================================
# GEMINI LIVE TOKEN BACKEND
# =========================================================

def create_live_token():
    if not GEMINI_KEY:
        raise ValueError("GEMINI_API_KEY missing in Streamlit Secrets.")

    client = genai.Client(
        api_key=GEMINI_KEY,
        http_options={"api_version": "v1beta"}
    )

    now = datetime.datetime.now(datetime.timezone.utc)

    expire_time = (
        now + datetime.timedelta(minutes=30)
    ).isoformat().replace("+00:00", "Z")

    new_session_expire_time = (
        now + datetime.timedelta(minutes=1)
    ).isoformat().replace("+00:00", "Z")

    token = client.auth_tokens.create(
        config={
            "uses": 1,
            "expire_time": expire_time,
            "new_session_expire_time": new_session_expire_time,
            "live_connect_constraints": {
                "model": LIVE_MODEL,
                "config": {
                    "response_modalities": ["AUDIO"],
                    "input_audio_transcription": {},
                    "output_audio_transcription": {},
                    "session_resumption": {}
                }
            }
        }
    )

    if not token.name:
        raise ValueError("Gemini Live token generate नहीं हुआ।")

    return token.name


# =========================================================
# CUSTOM UI
# =========================================================

st.markdown("""
<style>
.stApp {
    background:
      radial-gradient(circle at 10% 10%, #17143d 0, transparent 30%),
      radial-gradient(circle at 90% 90%, #111d42 0, transparent 30%),
      #070711;
    color: white;
}
section[data-testid="stSidebar"] {
    background: #0c0c1b;
    border-right: 1px solid #29264b;
}
h1,h2,h3 {
    color: #f4f2ff;
}
div.stButton > button {
    border-radius: 12px;
    border: 1px solid #5142a5;
    background: linear-gradient(120deg,#29205c,#182b57);
    color: white;
    font-weight: 600;
    min-height: 42px;
}
div.stButton > button:hover {
    border-color: #a78bfa;
    color: white;
    box-shadow: 0 0 15px #704bff55;
}
.stTextInput input, .stTextArea textarea {
    background: #101022;
    color: white;
    border: 1px solid #39345f;
    border-radius: 12px;
}
[data-testid="stChatMessage"] {
    background: #111124;
    border: 1px solid #292747;
    border-radius: 16px;
    padding: 12px;
}
.hero {
    padding: 20px;
    border-radius: 18px;
    background: linear-gradient(120deg,#18133b,#111d3d);
    border: 1px solid #3c3472;
}
.small-muted {
    color: #a7a4c5;
}
.orb {
    width: 125px;
    height: 125px;
    margin: 25px auto;
    border-radius: 50%;
    background: radial-gradient(circle at 35% 30%,#d8c5ff,#8b5cf6 35%,#312e81 70%);
    box-shadow: 0 0 25px #8b5cf6, 0 0 65px #4f46e5;
    animation: pulse 2s infinite ease-in-out;
}
@keyframes pulse {
    0%,100% { transform:scale(0.94); box-shadow:0 0 25px #8b5cf6; }
    50% { transform:scale(1.08); box-shadow:0 0 75px #8b5cf6; }
}
</style>
""", unsafe_allow_html=True)


# =========================================================
# SESSION STATE
# =========================================================

defaults = {
    "logged_in": False,
    "user_id": None,
    "username": "Guest",
    "cid": None,
    "guest_messages": [],
    "page": "AI Chat",
    "auth_mode": "Login"
}

for key, value in defaults.items():
    if key not in st.session_state:
        st.session_state[key] = value


# =========================================================
# LOGIN
# =========================================================

def auth_screen():
    st.markdown(
        "<div class='hero'><h1>🚀 NEXTGEN AI</h1>"
        "<p class='small-muted'>One Platform. Endless Possibilities.</p></div>",
        unsafe_allow_html=True
    )

    mode = st.radio(
        "Account",
        ["Login", "Create Account", "Continue as Guest"],
        horizontal=True
    )

    if mode == "Continue as Guest":
        st.session_state.logged_in = True
        st.session_state.username = "Guest"
        st.session_state.user_id = None
        st.rerun()

    if mode == "Create Account":
        username = st.text_input("Username")
        password = st.text_input("Password", type="password")

        if st.button("Create Account", use_container_width=True):
            if len(username.strip()) < 3 or len(password) < 6:
                st.error("Username कम से कम 3 और password 6 characters का रखें।")
            elif register_user(username.strip(), password):
                st.success("Account created. अब Login करें।")
            else:
                st.error("यह username पहले से मौजूद है।")

    else:
        username = st.text_input("Username")
        password = st.text_input("Password", type="password")

        if st.button("Login", use_container_width=True):
            uid = login_user(username.strip(), password)

            if uid:
                st.session_state.logged_in = True
                st.session_state.user_id = uid
                st.session_state.username = username
                st.session_state.cid = new_chat(uid)
                st.rerun()
            else:
                st.error("Username या password गलत है।")


if not st.session_state.logged_in:
    auth_screen()
    st.stop()


# =========================================================
# SIDEBAR
# =========================================================

PAGES = [
    "AI Chat",
    "Dashboard",
    "Current Affairs",
    "AI Tool Center",
    "App Builder",
    "Coding School",
    "Language Learning",
    "Study Assistant",
    "PDF Assistant",
    "AI Vision",
    "AI Image Studio",
    "Video Prompt Studio",
    "Live Voice",
    "Chat History",
    "About"
]

with st.sidebar:
    st.markdown("## 🚀 NEXTGEN AI")
    st.caption("Your Creative Universe")

    st.markdown("---")
    st.write("👤 " + st.session_state.username)

    if st.button("＋ New Chat", use_container_width=True):
        if st.session_state.user_id:
            st.session_state.cid = new_chat(st.session_state.user_id)
        else:
            st.session_state.guest_messages = []
        st.session_state.page = "AI Chat"
        st.rerun()

    st.markdown("---")

    selected_page = st.radio(
        "NAVIGATION",
        PAGES,
        index=PAGES.index(st.session_state.page)
        if st.session_state.page in PAGES else 0
    )

    st.session_state.page = selected_page

    if st.session_state.user_id:
        chats = get_chats(st.session_state.user_id)

        if chats:
            st.markdown("### Recent Chats")
            labels = {f"{title} · #{cid}": cid for cid, title in chats[:10]}
            selected_chat = st.selectbox(
                "Open conversation",
                list(labels.keys())
            )

            if st.button("Open Selected Chat", use_container_width=True):
                st.session_state.cid = labels[selected_chat]
                st.session_state.page = "AI Chat"
                st.rerun()

    st.markdown("---")

    if st.button("Logout", use_container_width=True):
        for key in [
            "logged_in", "user_id", "username",
            "cid", "guest_messages"
        ]:
            if key in st.session_state:
                del st.session_state[key]
        st.rerun()


# =========================================================
# PAGE: AI CHAT
# =========================================================

if st.session_state.page == "AI Chat":

    st.markdown("# 💬 NEXTGEN AI")
    st.caption("Ask anything. Learn, create and explore.")

    if st.session_state.user_id:
        if not st.session_state.cid:
            st.session_state.cid = new_chat(st.session_state.user_id)

        messages = get_messages(st.session_state.cid)
    else:
        messages = st.session_state.guest_messages

    for index, msg in enumerate(messages):
        with st.chat_message(msg["role"]):
            st.markdown(msg["content"])

            if msg["role"] == "assistant":
                st.caption("NEXTGEN AI")
                if st.button("📋 Copy response", key=f"copy_{index}"):
                    st.code(msg["content"])

    prompt = st.chat_input("Message NEXTGEN AI...")

    if prompt:
        with st.chat_message("user"):
            st.markdown(prompt)

        if st.session_state.user_id:
            save_message(st.session_state.cid, "user", prompt)
        else:
            st.session_state.guest_messages.append({
                "role": "user",
                "content": prompt
            })

        with st.chat_message("assistant"):
            with st.spinner("NEXTGEN AI is thinking..."):
                answer = ai_reply(messages, prompt)
            st.markdown(answer)

        if st.session_state.user_id:
            save_message(st.session_state.cid, "assistant", answer)
            update_chat_title(st.session_state.cid, prompt)
        else:
            st.session_state.guest_messages.append({
                "role": "assistant",
                "content": answer
            })

        st.rerun()


# =========================================================
# PAGE: DASHBOARD
# =========================================================

elif st.session_state.page == "Dashboard":

    st.markdown("# 📊 Dashboard")
    st.markdown(
        "<div class='hero'><h2>Welcome to NEXTGEN AI</h2>"
        "<p>Your AI workspace is ready.</p></div>",
        unsafe_allow_html=True
    )

    c1, c2, c3 = st.columns(3)
    c1.metric("AI Assistant", "Online")
    c2.metric("Web Search", "Available" if TAVILY_KEY else "Not configured")
    c3.metric("Live Voice", "Ready" if GEMINI_KEY else "Needs API key")

    st.markdown("### Explore your workspace")
    a, b, c = st.columns(3)

    with a:
        st.info("💬 AI Chat\n\nChat with your assistant.")
    with b:
        st.info("🎙️ Live Voice\n\nTalk with NEXTGEN AI.")
    with c:
        st.info("📚 Study Assistant\n\nLearn and understand topics.")


# =========================================================
# PAGE: CURRENT AFFAIRS
# =========================================================

elif st.session_state.page == "Current Affairs":

    st.title("📰 Current Affairs")
    query = st.text_input("Enter a topic or question")

    if st.button("Search Current Affairs"):
        with st.spinner("Searching..."):
            result = web_search(query)
        st.write(result if result else "Search unavailable.")


# =========================================================
# PAGE: AI TOOL CENTER
# =========================================================

elif st.session_state.page == "AI Tool Center":

    st.title("🧰 AI Tool Center")

    tool = st.selectbox(
        "Choose a tool",
        [
            "Text Summarizer",
            "Email Writer",
            "Essay Writer",
            "Translator",
            "Grammar Corrector",
            "Idea Generator",
            "Code Helper",
            "Quiz Generator"
        ]
    )

    text_input = st.text_area("Enter your text or instructions", height=180)

    if st.button("Generate"):
        instruction = f"""
        Use the following tool: {tool}.
        Follow the user's request carefully.
        Input:
        {text_input}
        """
        with st.spinner("Generating..."):
            result = ai_reply([], instruction)
        st.markdown(result)


# =========================================================
# PAGE: APP BUILDER
# =========================================================

elif st.session_state.page == "App Builder":

    st.title("🛠️ AI App Builder")
    idea = st.text_area("Describe the app you want to build")

    if st.button("Generate App Plan"):
        prompt = (
            "Create a detailed app development plan, features, "
            "UI structure and starter code for this idea: " + idea
        )
        st.markdown(ai_reply([], prompt))


# =========================================================
# PAGE: CODING SCHOOL
# =========================================================

elif st.session_state.page == "Coding School":

    st.title("💻 Coding School")
    language = st.selectbox(
        "Choose a language",
        ["Python", "HTML", "CSS", "JavaScript", "SQL"]
    )
    topic = st.text_input("What do you want to learn?")

    if st.button("Start Learning"):
        st.markdown(
            ai_reply(
                [],
                f"Teach me {topic} in {language} from beginner to advanced "
                "with examples and a small practice exercise."
            )
        )


# =========================================================
# PAGE: LANGUAGE LEARNING
# =========================================================

elif st.session_state.page == "Language Learning":

    st.title("🌍 Language Learning")
    language = st.selectbox(
        "Learn",
        ["English", "Hindi", "French", "Spanish", "Japanese", "German"]
    )
    level = st.selectbox("Level", ["Beginner", "Intermediate", "Advanced"])

    if st.button("Create Lesson"):
        st.markdown(
            ai_reply(
                [],
                f"Create a {level} {language} lesson with vocabulary, "
                "grammar, examples and a short practice activity."
            )
        )


# =========================================================
# PAGE: STUDY ASSISTANT
# =========================================================

elif st.session_state.page == "Study Assistant":

    st.title("📚 Study Assistant")
    subject = st.text_input("Subject")
    question = st.text_area("Question or chapter topic")

    if st.button("Explain"):
        st.markdown(
            ai_reply(
                [],
                f"Explain this {subject} topic clearly with examples: {question}"
            )
        )


# =========================================================
# PAGE: PDF ASSISTANT
# =========================================================

elif st.session_state.page == "PDF Assistant":

    st.title("📄 PDF Assistant")
    uploaded = st.file_uploader("Upload a PDF", type=["pdf"])

    if uploaded:
        try:
            reader = PdfReader(uploaded)
            pdf_text = "\n".join(
                page.extract_text() or ""
                for page in reader.pages
            )

            st.success(f"{len(reader.pages)} pages loaded.")

            task = st.text_area(
                "What should NEXTGEN AI do with this PDF?",
                "Summarize this PDF."
            )

            if st.button("Analyze PDF"):
                st.markdown(
                    ai_reply(
                        [],
                        task + "\n\nPDF CONTENT:\n" + pdf_text[:25000]
                    )
                )
        except Exception as e:
            st.error("PDF error: " + str(e))


# =========================================================
# PAGE: AI VISION
# =========================================================

elif st.session_state.page == "AI Vision":

    st.title("👁️ AI Vision")
    st.info(
        "Image upload preview is available here. "
        "A working vision model backend is not configured in this version."
    )
    image_file = st.file_uploader(
        "Upload an image",
        type=["png", "jpg", "jpeg"]
    )

    if image_file:
        st.image(image_file, use_container_width=True)
        st.caption("Image preview loaded.")


# =========================================================
# PAGE: AI IMAGE STUDIO
# =========================================================

elif st.session_state.page == "AI Image Studio":

    st.title("🎨 AI Image Studio")
    prompt = st.text_area("Describe the image you want")

    if st.button("Create Image Prompt"):
        st.markdown(
            ai_reply(
                [],
                "Write a detailed image-generation prompt for: " + prompt
            )
        )

    st.caption("This version creates prompts; image rendering requires an image-generation backend.")


# =========================================================
# PAGE: VIDEO PROMPT STUDIO
# =========================================================

elif st.session_state.page == "Video Prompt Studio":

    st.title("🎬 Video Prompt Studio")
    idea = st.text_area("Describe your video idea")

    if st.button("Create Storyboard"):
        st.markdown(
            ai_reply(
                [],
                "Create a scene-by-scene video storyboard with "
                "visual prompts, camera movement and dialogue for: " + idea
            )
        )

    st.caption("This version creates video prompts, not rendered video files.")


# =========================================================
# PAGE: LIVE VOICE
# =========================================================

elif st.session_state.page == "Live Voice":

    st.title("🎙️ NEXTGEN AI Live Voice")
    st.caption("Real-time voice conversation powered by Gemini Live.")

    st.markdown(
        "<div class='orb'></div>",
        unsafe_allow_html=True
    )

    if not GEMINI_KEY:
        st.error("GEMINI_API_KEY missing. Add it in Streamlit Secrets.")
    else:
        if st.button("🔄 Generate Live Session", use_container_width=True):
            try:
                with st.spinner("Securing your live session..."):
                    token = create_live_token()
                st.session_state.live_token = token
                st.success("Temporary session token created.")
            except Exception as e:
                st.error("Could not start live session: " + str(e))

        token = st.session_state.get("live_token")

        if token:
            live_html = r"""
<!DOCTYPE html>
<html>
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<style>
body {
  margin:0; padding:16px; background:#080817; color:white;
  font-family:Arial,sans-serif; text-align:center;
}
.panel {
  max-width:680px; margin:auto; padding:22px;
  background:#15152e; border:1px solid #454078;
  border-radius:18px;
}
.orb {
  width:125px;height:125px;border-radius:50%;margin:24px auto;
  background:radial-gradient(circle at 35% 30%,#ddd6fe,#8b5cf6 40%,#312e81 75%);
  box-shadow:0 0 25px #8b5cf6,0 0 60px #4f46e5;
  animation:pulse 1.8s infinite;
}
@keyframes pulse {
  0%,100% {transform:scale(.92);box-shadow:0 0 20px #8b5cf6;}
  50% {transform:scale(1.08);box-shadow:0 0 70px #8b5cf6;}
}
#status {
  background:#252545;padding:12px;border-radius:10px;margin:15px 0;
}
button {
  padding:13px 19px;border:0;border-radius:10px;
  color:white;font-weight:bold;margin:5px;cursor:pointer;
}
#startBtn {background:#7c3aed;}
#stopBtn {background:#dc2626;}
button:disabled {opacity:.45;}
#conversation {
  margin-top:18px;padding:14px;min-height:120px;
  max-height:250px;overflow:auto;text-align:left;
  background:#0b0b20;border-radius:10px;white-space:pre-wrap;
}
.user {color:#93c5fd;margin-bottom:12px;}
.assistant {color:#c4b5fd;margin-bottom:12px;}
</style>
</head>
<body>
<div class="panel">
  <h2>🚀 NEXTGEN AI LIVE</h2>
  <div class="orb"></div>
  <div id="status">Status: Ready to connect</div>
  <button id="startBtn">📞 Start Live Call</button>
  <button id="stopBtn" disabled>⏹ End Call</button>
  <div id="conversation">Your live conversation will appear here.</div>
</div>

<script>
const TOKEN = "__LIVE_TOKEN__";
const MODEL = "gemini-3.8-live";

let ws = null, micStream = null, micContext = null;
let outputContext = null, processor = null, micSource = null;
let setupDone = false, nextPlayTime = 0;
let activeSources = new Set();

const statusBox = document.getElementById("status");
const conversation = document.getElementById("conversation");
const startBtn = document.getElementById("startBtn");
const stopBtn = document.getElementById("stopBtn");

function status(s) {
  statusBox.textContent = "Status: " + s;
}

function addMessage(type, message) {
  const div = document.createElement("div");
  div.className = type;
  div.textContent = (type === "user" ? "You: " : "NEXTGEN AI: ") + message;
  conversation.appendChild(div);
  conversation.scrollTop = conversation.scrollHeight;
}

function floatToPCM16(data) {
  const pcm = new Int16Array(data.length);
  for (let i=0;i<data.length;i++) {
    const s=Math.max(-1,Math.min(1,data[i]));
    pcm[i]=s<0?s*32768:s*32767;
  }
  return pcm;
}

function resample(input, sourceRate) {
  const target=16000;
  if(sourceRate===target) return input;
  const length=Math.floor(input.length*target/sourceRate);
  const output=new Float32Array(length);
  const ratio=sourceRate/target;
  for(let i=0;i<length;i++) {
    const pos=i*ratio, index=Math.floor(pos), frac=pos-index;
    const a=input[index]||0, b=input[index+1]||a;
    output[i]=a+(b-a)*frac;
  }
  return output;
}

function pcmBase64(pcm) {
  const bytes=new Uint8Array(pcm.buffer,pcm.byteOffset,pcm.byteLength);
  let binary="";
  for(let i=0;i<bytes.length;i++) binary+=String.fromCharCode(bytes[i]);
  return btoa(binary);
}

function base64Bytes(base64) {
  const binary=atob(base64), bytes=new Uint8Array(binary.length);
  for(let i=0;i<binary.length;i++) bytes[i]=binary.charCodeAt(i);
  return bytes;
}

async function startMicrophone() {
  micStream=await navigator.mediaDevices.getUserMedia({
    audio:{
      channelCount:1,
      echoCancellation:true,
      noiseSuppression:true,
      autoGainControl:true
    }
  });

  micContext=new AudioContext({sampleRate:16000});
  await micContext.resume();
  micSource=micContext.createMediaStreamSource(micStream);
  processor=micContext.createScriptProcessor(2048,1,1);

  processor.onaudioprocess=(event)=>{
    if(!setupDone||!ws||ws.readyState!==WebSocket.OPEN) return;
    const input=event.inputBuffer.getChannelData(0);
    const pcm=floatToPCM16(resample(input,micContext.sampleRate));
    ws.send(JSON.stringify({
      realtimeInput:{
        audio:{
          mimeType:"audio/pcm;rate=16000",
          data:pcmBase64(pcm)
        }
      }
    }));
  };

  micSource.connect(processor);
  processor.connect(micContext.destination);
}

async function playAudio(base64,mimeType) {
  if(!outputContext) return;
  const bytes=base64Bytes(base64);
  const count=Math.floor(bytes.length/2);
  const view=new DataView(bytes.buffer,bytes.byteOffset,bytes.byteLength);
  const samples=new Float32Array(count);

  for(let i=0;i<count;i++) samples[i]=view.getInt16(i*2,true)/32768;

  const match=(mimeType||"").match(/rate=(\d+)/);
  const rate=match?Number(match[1]):24000;
  const buffer=outputContext.createBuffer(1,count,rate);
  buffer.copyToChannel(samples,0);

  const source=outputContext.createBufferSource();
  source.buffer=buffer;
  source.connect(outputContext.destination);

  const start=Math.max(outputContext.currentTime,nextPlayTime);
  source.start(start);
  nextPlayTime=start+buffer.duration;
  activeSources.add(source);
  source.onended=()=>activeSources.delete(source);
}

function stopPlayback() {
  for(const source of activeSources) {
    try { source.stop(); } catch(e) {}
  }
  activeSources.clear();
  if(outputContext) nextPlayTime=outputContext.currentTime;
}

function stopMic() {
  setupDone=false;
  if(processor) {
    processor.disconnect();
    processor.onaudioprocess=null;
    processor=null;
  }
  if(micSource) { micSource.disconnect(); micSource=null; }
  if(micStream) {
    micStream.getTracks().forEach(t=>t.stop());
    micStream=null;
  }
  if(micContext) {
    micContext.close();
    micContext=null;
  }
}

async function startCall() {
  if(!TOKEN || TOKEN==="__LIVE_TOKEN__") {
    status("Temporary token missing. Refresh the page.");
    return;
  }

  startBtn.disabled=true;
  status("Connecting to Gemini Live...");

  try {
    outputContext=new AudioContext({sampleRate:24000});
    await outputContext.resume();

    const endpoint=
      "wss://generativelanguage.googleapis.com/ws/" +
      "google.ai.generativelanguage.v1beta.GenerativeService." +
      "BidiGenerateContent?access_token="+encodeURIComponent(TOKEN);

    ws=new WebSocket(endpoint);

    ws.onopen=()=>{
      status("Connected. Configuring AI...");
      ws.send(JSON.stringify({
        setup:{
          model:"models/"+MODEL,
          generationConfig:{responseModalities:["AUDIO"]},
          inputAudioTranscription:{},
          outputAudioTranscription:{}
        }
      }));
    };

    ws.onmessage=async(event)=>{
      try {
        const msg=JSON.parse(event.data);

        if(msg.error) {
          status("API Error: "+(msg.error.message||"Unknown error"));
          return;
        }

        if(msg.setupComplete) {
          setupDone=true;
          await startMicrophone();
          stopBtn.disabled=false;
          status("Live Call Active. Speak now!");
        }

        const content=msg.serverContent;
        if(!content) return;

        if(content.inputTranscription?.text)
          addMessage("user",content.inputTranscription.text);

        if(content.outputTranscription?.text)
          addMessage("assistant",content.outputTranscription.text);

        if(content.interrupted) stopPlayback();

        if(content.modelTurn?.parts) {
          for(const part of content.modelTurn.parts) {
            if(part.inlineData?.data)
              await playAudio(part.inlineData.data,part.inlineData.mimeType);
          }
        }

        if(content.turnComplete) status("AI replied. You can speak again.");
      } catch(e) {
        status("Message error: "+e.message);
      }
    };

    ws.onerror=()=>{
      status("Connection error. Check API/model availability.");
      startBtn.disabled=false;
    };

    ws.onclose=(event)=>{
      stopMic();
      setupDone=false;
      status("Connection closed ("+event.code+").");
      startBtn.disabled=false;
      stopBtn.disabled=true;
    };

  } catch(e) {
    status("Error: "+e.message);
    stopMic();
    startBtn.disabled=false;
  }
}

function stopCall() {
  status("Ending call...");
  stopMic();
  stopPlayback();

  if(ws && ws.readyState===WebSocket.OPEN) {
    ws.send(JSON.stringify({realtimeInput:{audioStreamEnd:true}}));
    ws.close();
  } else if(ws) {
    ws.close();
  }

  if(outputContext) {
    outputContext.close();
    outputContext=null;
  }

  ws=null;
  startBtn.disabled=false;
  stopBtn.disabled=true;
  status("Call ended.");
}

startBtn.addEventListener("click",startCall);
stopBtn.addEventListener("click",stopCall);
</script>
</body>
</html>
"""
            live_html = live_html.replace("__LIVE_TOKEN__", token)

            components.html(
                live_html,
                height=650,
                scrolling=True
            )

            st.caption(
                "Microphone permission दें। Live call शुरू करने के लिए "
                "ऊपर Start Live Call दबाएँ।"
            )


# =========================================================
# PAGE: CHAT HISTORY
# =========================================================

elif st.session_state.page == "Chat History":

    st.title("🕘 Chat History")

    if not st.session_state.user_id:
        st.info("Guest chats केवल इस browser session में उपलब्ध हैं.")
    else:
        chats = get_chats(st.session_state.user_id)

        if not chats:
            st.info("No conversations yet.")
        else:
            for cid, title in chats:
                with st.expander(title):
                    for message in get_messages(cid):
                        st.markdown(
                            ("**You:** " if message["role"] == "user"
                             else "**NEXTGEN AI:** ") + message["content"]
                        )

                    c1, c2 = st.columns(2)

                    with c1:
                        if st.button("Open", key=f"open_{cid}"):
                            st.session_state.cid = cid
                            st.session_state.page = "AI Chat"
                            st.rerun()

                    with c2:
                        if st.button("Delete", key=f"delete_{cid}"):
                            delete_chat(cid)
                            st.rerun()


# =========================================================
# PAGE: ABOUT
# =========================================================

elif st.session_state.page == "About":

    st.title("ℹ️ About NEXTGEN AI")

    st.markdown("""
    <div class="hero">
      <h2>🚀 NEXTGEN AI</h2>
      <p>One Platform. Endless Possibilities.</p>
      <p>NEXTGEN AI is an AI workspace created by Arav Roy.</p>
    </div>
    """, unsafe_allow_html=True)

    st.markdown("""
    ### Our vision
    To bring useful AI tools, learning assistance and creative
    workflows together in one simple platform.

    ### Available areas
    - AI Chat
    - Current Affairs
    - Study Assistant
    - PDF Assistant
    - AI Tools
    - Live Voice

    Some creative features require their own connected AI services.
    """)


# =========================================================
# FOOTER
# =========================================================

st.markdown("---")
st.caption("NEXTGEN AI © 2026 | Built by Arav Roy")
