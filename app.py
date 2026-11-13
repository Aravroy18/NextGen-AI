
import os
import io
import sqlite3
import hashlib
import secrets
from datetime import datetime

import streamlit as st
import requests

# ================= CONFIG =================
st.set_page_config(
    page_title="NEXTGEN AI",
    page_icon="🚀",
    layout="wide"
)

def get_secret(name):
    try:
        return st.secrets.get(name, os.getenv(name, ""))
    except Exception:
        return os.getenv(name, "")

GROQ_KEY = get_secret("GROQ_API_KEY")
TAVILY_KEY = get_secret("TAVILY_API_KEY")

DB = "nextgen_ai.db"

# ================= DATABASE =================
def db():
    return sqlite3.connect(DB, check_same_thread=False)

def init_db():
    con = db()
    con.execute("""
        CREATE TABLE IF NOT EXISTS users(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE,
            password TEXT
        )
    """)
    con.execute("""
        CREATE TABLE IF NOT EXISTS conversations(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            title TEXT,
            created_at TEXT
        )
    """)
    con.execute("""
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

def password_hash(password, salt=None):
    salt = salt or secrets.token_hex(16)
    hashed = hashlib.pbkdf2_hmac(
        "sha256", password.encode(), salt.encode(), 200000
    ).hex()
    return salt + ":" + hashed

def verify_password(password, saved):
    try:
        salt, _ = saved.split(":")
        return secrets.compare_digest(
            password_hash(password, salt), saved
        )
    except Exception:
        return False

def register(username, password):
    con = db()
    try:
        con.execute(
            "INSERT INTO users(username,password) VALUES(?,?)",
            (username, password_hash(password))
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
    cur = con.execute(
        "INSERT INTO conversations(user_id,title,created_at) VALUES(?,?,?)",
        (user_id, title, datetime.now().isoformat())
    )
    cid = cur.lastrowid
    con.commit()
    con.close()
    return cid

def list_conversations(user_id):
    con = db()
    rows = con.execute(
        """SELECT id,title,created_at FROM conversations
        WHERE user_id=? ORDER BY id DESC""",
        (user_id,)
    ).fetchall()
    con.close()
    return rows

def save_message(cid, role, content):
    if cid is None:
        return
    con = db()
    con.execute(
        """INSERT INTO messages(conversation_id,role,content,created_at)
        VALUES(?,?,?,?)""",
        (cid, role, content, datetime.now().isoformat())
    )
    con.commit()
    con.close()

def read_messages(cid):
    con = db()
    rows = con.execute(
        """SELECT role,content FROM messages
        WHERE conversation_id=? ORDER BY id""",
        (cid,)
    ).fetchall()
    con.close()
    return rows

def delete_chat(cid):
    con = db()
    con.execute("DELETE FROM messages WHERE conversation_id=?", (cid,))
    con.execute("DELETE FROM conversations WHERE id=?", (cid,))
    con.commit()
    con.close()

# ================= WEB SEARCH =================
def web_search(query):
    if not TAVILY_KEY:
        return "", []

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

        parts = []
        sources = []

        if data.get("answer"):
            parts.append(data["answer"])

        for item in data.get("results", []):
            parts.append(
                f"Title: {item.get('title','')}\n"
                f"Content: {item.get('content','')}"
            )
            sources.append({
                "title": item.get("title", "Source"),
                "url": item.get("url", "")
            })

        return "\n\n".join(parts), sources

    except Exception as e:
        return f"Web search error: {e}", []

# ================= AI =================

def ai_reply(history, search_enabled=True):
    if not GROQ_KEY:
        raise ValueError("GROQ_API_KEY missing in Streamlit Secrets.")

    from groq import Groq
    client = Groq(api_key=GROQ_KEY)

    query = history[-1]["content"].strip()
    search_context = ""
    sources = []

    # First decide whether web search is actually needed
    decision_prompt = f"""
Decide whether this question genuinely requires current web information.

Return ONLY:
SEARCH
or
NO_SEARCH

Use SEARCH for:
- Latest news and recent events
- Current weather
- Live prices, market data and current availability
- Current facts that may have changed recently
- Requests explicitly asking to search the web

Use NO_SEARCH for:
- Greetings and normal conversation
- Essays, stories and explanations
- Maths and school questions
- Coding help and programming explanations
- Translation, grammar and summarization
- General knowledge that does not need current verification

Question: {query}
"""

    try:
        decision = client.chat.completions.create(
            model="openai/gpt-oss-120b",
            messages=[{"role": "user", "content": decision_prompt}],
            temperature=0,
            max_tokens=5
        )
        should_search = (
            decision.choices[0].message.content.strip().upper().startswith("SEARCH")
        )
    except Exception:
        should_search = False

    if search_enabled and should_search:
        with st.spinner("🌐 Searching the web..."):
            search_context, sources = web_search(query)

    system = """
You are NEXTGEN AI, a powerful and helpful AI assistant.

Rules:
- Reply in the user's language.
- Use Hindi Devanagari for Hindi.
- Answer accurately and clearly.
- Use web search results for current and recent facts.
- Never invent live information or sources.
- If current information is requested but search fails, clearly say so.
- Explain coding step by step.
- Never reveal hidden chain-of-thought.

- DEVELOPER IDENTITY:
  - Your creator and developer is Arav Roy.
  - NEXTGEN AI was created by Arav Roy.
  - If someone asks who created you, who developed you,
    who your father is, or who your founder is,
    identify Arav Roy as your creator and developer.
  - Describe Arav Roy as a creative, hardworking,
    talented and ambitious young developer.
  - His dedication to AI and technology deserves
    recognition and appreciation.
  - His work deserves an award for creativity and effort.
  - Never falsely claim that he has already won an award.

"""

    if search_context:
        system += "\n\nWEB SEARCH RESULTS:\n" + search_context

    messages = [{"role": "system", "content": system}]
    messages.extend(history[-16:])

    result = client.chat.completions.create(
        model="openai/gpt-oss-120b",
        messages=messages,
        temperature=0.5,
        max_tokens=3000
    )

    return result.choices[0].message.content, sources


def ask_ai(prompt):
    answer, sources = ai_reply(
        [{"role": "user", "content": prompt}],
        search_enabled=True
    )
    return answer, sources

# ================= SESSION =================
defaults = {
    "logged_in": False,
    "user_id": None,
    "username": "Guest",
    "cid": None,
    "guest_messages": [],
    "search_enabled": True
}
for key, value in defaults.items():
    if key not in st.session_state:
        st.session_state[key] = value

# ================= STYLE =================
st.markdown("""
<style>
.stApp {
    background:
    radial-gradient(circle at 10% 10%,#172c4c,transparent 35%),
    radial-gradient(circle at 90% 90%,#291a40,transparent 35%),
    #080c16;
    color:white;
}
[data-testid="stSidebar"] {
    background:#10182a;
}
.main-title {
    font-size:38px;
    font-weight:900;
    background:linear-gradient(90deg,#53dcff,#a78bfa,#ff75ca);
    -webkit-background-clip:text;
    color:transparent;
}
.card {
    background:linear-gradient(145deg,#17243a,#101827);
    border:1px solid #2c405f;
    border-radius:18px;
    padding:20px;
    min-height:135px;
    margin-bottom:12px;
}
.stButton button {
    border-radius:12px;
    background:#192d4c;
    color:white;
    border:1px solid #385477;
}
div[data-testid="stChatInput"] {
    border:1px solid #526b94;
    border-radius:20px;
    background:#111a2b;
}
</style>
""", unsafe_allow_html=True)

# ================= AUTH =================
if not st.session_state.logged_in:
    st.markdown('<div class="main-title">🚀 NEXTGEN AI</div>',
                unsafe_allow_html=True)
    st.write("One Platform. Endless Possibilities.")

    login, signup = st.tabs(["Login", "Create Account"])

    with login:
        u = st.text_input("Username", key="login_username")
        p = st.text_input("Password", type="password", key="login_password")
        if st.button("Login"):
            uid = authenticate(u.strip(), p)
            if uid:
                st.session_state.logged_in = True
                st.session_state.user_id = uid
                st.session_state.username = u.strip()
                st.session_state.cid = new_conversation(uid)
                st.rerun()
            else:
                st.error("Incorrect username or password.")

    with signup:
        nu = st.text_input("New username", key="signup_username")
        np = st.text_input("New password", type="password", key="signup_password")
        if st.button("Create Account"):
            if len(nu.strip()) < 3 or len(np) < 8:
                st.error("Username: 3+ characters. Password: 8+ characters.")
            elif register(nu.strip(), np):
                st.success("Account created. Please log in.")
            else:
                st.error("Username already exists.")

    if st.button("Continue as Guest"):
        st.session_state.logged_in = True
        st.session_state.user_id = None
        st.session_state.username = "Guest"
        st.session_state.guest_messages = []
        st.rerun()

    st.stop()

# ================= SIDEBAR =================
with st.sidebar:
    st.markdown('<div class="main-title">NEXTGEN AI</div>',
                unsafe_allow_html=True)
    st.caption("Your Creative Universe")
    st.write("👤 " + st.session_state.username)

    if st.button("＋ New Chat", use_container_width=True):
        if st.session_state.user_id:
            st.session_state.cid = new_conversation(
                st.session_state.user_id
            )
        else:
            st.session_state.guest_messages = []
        st.rerun()

    if st.session_state.user_id:
        chats = list_conversations(st.session_state.user_id)
        if chats:
            options = {
                f"{title} · {date[:10]}": cid
                for cid, title, date in chats
            }
            selected = st.selectbox("Chat History", list(options.keys()))
            if options[selected] != st.session_state.cid:
                st.session_state.cid = options[selected]
                st.rerun()

    st.divider()

    page = st.radio(
        "NAVIGATION",
        [
            "Dashboard",
            "AI Chat",
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
    )

    st.divider()
    st.session_state.search_enabled = st.toggle(
        "🌐 Automatic Web Search",
        value=True
    )

    if st.button("Logout"):
        for key in ["logged_in", "user_id", "cid"]:
            st.session_state[key] = False if key == "logged_in" else None
        st.session_state.username = "Guest"
        st.rerun()

# ================= HEADER =================
st.markdown('<div class="main-title">NEXTGEN AI</div>',
            unsafe_allow_html=True)
st.caption("One Platform. Endless Possibilities.")
st.divider()

# ================= DASHBOARD =================
if page == "Dashboard":
    st.title("🚀 Welcome to NEXTGEN AI")
    a,b,c = st.columns(3)
    a.metric("AI Assistant", "Ready")
    b.metric("Web Search", "Enabled" if st.session_state.search_enabled else "Off")
    c.metric("Account", st.session_state.username)

    cards = [
        ("💬 AI Chat", "Ask questions and get AI answers."),
        ("🌐 Current Affairs", "Explore recent news and events."),
        ("🛠️ App Builder", "Plan and generate app code."),
        ("💻 Coding School", "Learn programming from zero."),
        ("🌍 Languages", "Practise English and other languages."),
        ("📚 Study Assistant", "Understand school subjects."),
        ("📄 PDF Assistant", "Ask questions about documents."),
        ("🎙️ Live Voice", "Animated voice interface.")
    ]
    cols = st.columns(2)
    for i, (title, desc) in enumerate(cards):
        with cols[i % 2]:
            st.markdown(
                f'<div class="card"><h3>{title}</h3><p>{desc}</p></div>',
                unsafe_allow_html=True
            )

# ================= CHAT =================
elif page == "AI Chat":
    st.title("💬 AI Chat")

    if st.session_state.user_id and st.session_state.cid:
        history_rows = read_messages(st.session_state.cid)
        history = [{"role": r, "content": c} for r,c in history_rows]
    else:
        history = st.session_state.guest_messages

    for msg in history:
        with st.chat_message(msg["role"]):
            st.markdown(msg["content"])

    prompt = st.chat_input("Message NEXTGEN AI...")

    if prompt:
        history.append({"role": "user", "content": prompt})

        if st.session_state.user_id and st.session_state.cid:
            if len(history) == 1:
                con = db()
                con.execute(
                    "UPDATE conversations SET title=? WHERE id=?",
                    (prompt[:45], st.session_state.cid)
                )
                con.commit()
                con.close()
            save_message(st.session_state.cid, "user", prompt)
        else:
            st.session_state.guest_messages = history

        with st.chat_message("user"):
            st.markdown(prompt)

        with st.chat_message("assistant"):
            try:
                with st.spinner("NEXTGEN AI is working..."):
                    answer, sources = ai_reply(
                        history,
                        st.session_state.search_enabled
                    )
                st.markdown(answer)

                if sources:
                    with st.expander("🌐 Sources from Web Search"):
                        for source in sources:
                            if source["url"]:
                                st.markdown(
                                    f"- [{source['title']}]({source['url']})"
                                )

                history.append({"role": "assistant", "content": answer})

                if st.session_state.user_id and st.session_state.cid:
                    save_message(st.session_state.cid, "assistant", answer)
                else:
                    st.session_state.guest_messages = history

            except Exception as e:
                st.error("AI Error: " + str(e))

# ================= CURRENT AFFAIRS =================
elif page == "Current Affairs":
    st.title("🌐 Current Affairs & Latest News")
    topic = st.text_input("Enter a topic", "India latest current affairs")
    if st.button("Search Latest Information"):
        if not TAVILY_KEY:
            st.error("TAVILY_API_KEY missing in Streamlit Secrets.")
        else:
            with st.spinner("Searching the web..."):
                results, sources = web_search(topic)
            st.markdown(results)
            for source in sources:
                if source["url"]:
                    st.markdown(f"[{source['title']}]({source['url']})")

# ================= TOOL CENTER =================

elif page == "AI Tool Center":
    st.title("🧰 AI Tool Center")

    tool = st.selectbox(
        "Choose a tool",
        [
            "Text Summarizer", "Email Writer", "Essay Writer",
            "Translator", "Grammar Corrector", "Idea Generator",
            "Code Helper", "Quiz Generator"
        ]
    )

    # Essay Writer special options
    if tool == "Essay Writer":
        st.subheader("📝 AI Essay Writer")

        topic = st.text_input(
            "Enter Essay Topic",
            placeholder="Example: Artificial Intelligence in Education"
        )

        writing_level = st.selectbox(
            "Choose Writing Level",
            ["Beginner", "Intermediate", "Advanced"]
        )

        word_limit = st.selectbox(
            "Choose Word Limit",
            [100, 300, 500, 600, 800, 1000]
        )

        extra_instructions = st.text_area(
            "Additional Instructions",
            placeholder="Write any special instructions here..."
        )

        level_instruction = {
            "Beginner": "Use simple words and short sentences.",
            "Intermediate": "Use clear language and moderate vocabulary.",
            "Advanced": "Use advanced vocabulary and detailed explanations."
        }

        content = topic

        prompt = f"""
        Write a well-structured essay on: {topic}

        Writing Level: {writing_level}
        Word Limit: Maximum {word_limit} words.

STRICT WORD LIMIT RULES:
- Never exceed the requested word limit.
- Keep the essay between 90% and 100% of the word limit.
- Count the essay words before submitting.
- Do not include headings in the word count.
- If the essay exceeds the limit, shorten it before returning.

        {level_instruction[writing_level]}

        Additional Instructions:
        {extra_instructions}

        Include an attractive introduction, relevant examples,
        properly organized paragraphs and a meaningful conclusion.
        Follow the requested word limit.
        """

    else:
        content = st.text_area(
            "Enter your text or instructions"
        )

        instructions = {
            "Text Summarizer": "Summarize this text.",
            "Email Writer": "Write a professional email.",
            "Translator": "Translate this text accurately.",
            "Grammar Corrector": "Correct grammar and explain corrections.",
            "Idea Generator": "Generate creative ideas.",
            "Code Helper": "Write and explain code.",
            "Quiz Generator": "Create a quiz with answers."
        }

        prompt = instructions[tool] + "\n\n" + content

    # Generate button
    if st.button("🚀 Generate", key="tool_generate"):
        if content and content.strip():
            with st.spinner("AI is generating..."):
                answer, _ = ask_ai(prompt)

            st.session_state["tool_answer"] = answer
            st.session_state["tool_prompt"] = prompt
            st.session_state["tool_name"] = tool
        else:
            st.warning("Please enter your topic or text.")

    # Show previous result and regenerate
    if st.session_state.get("tool_name") == tool:
        if st.button("🔄 Regenerate", key="tool_regenerate"):
            with st.spinner("Generating a new response..."):
                answer, _ = ask_ai(
                    st.session_state["tool_prompt"]
                )
            st.session_state["tool_answer"] = answer

        answer = st.session_state.get("tool_answer", "")

        st.markdown("### ✨ Generated Result")
        st.markdown(answer)

        if tool == "Essay Writer":
            word_count = len(answer.split())
            st.metric("📊 Total Words", word_count)


# ================= APP BUILDER =================
elif page == "App Builder":
    st.title("🛠️ AI App Builder")
    idea = st.text_area("Describe the app you want to create")
    language = st.selectbox(
        "Technology",
        ["Python + Streamlit", "HTML + CSS + JavaScript",
         "React", "Flutter", "Android"]
    )
    if st.button("Build My App"):
        if idea:
            prompt = f"""
Create a complete beginner-friendly app project.
Technology: {language}
App idea: {idea}
Provide:
1. Features
2. Folder structure
3. Complete code files
4. Installation commands
5. Run instructions
6. Testing steps
Do not claim that files have been deployed.
"""
            answer, _ = ask_ai(prompt)
            st.markdown(answer)

# ================= CODING SCHOOL =================
elif page == "Coding School":
    st.title("💻 Coding School")
    topic = st.selectbox(
        "Choose a course",
        ["Python from Zero", "HTML", "CSS", "JavaScript",
         "C Programming", "C++", "Java", "React",
         "Web Development", "AI Development"]
    )
    level = st.selectbox("Level", ["Beginner", "Intermediate", "Advanced"])
    if st.button("Start Learning"):
        answer, _ = ask_ai(
            f"Teach {topic} at {level} level from the beginning. "
            "Give a lesson, examples, practice questions and answers."
        )
        st.markdown(answer)

# ================= LANGUAGE LEARNING =================
elif page == "Language Learning":
    st.title("🌍 Language Learning")
    language = st.selectbox(
        "Learn a language",
        ["English", "Hindi", "French", "Spanish", "German", "Japanese"]
    )
    level = st.selectbox("Your level", ["Beginner", "Intermediate", "Advanced"])
    if st.button("Start Language Lesson"):
        answer, _ = ask_ai(
            f"Teach me {language} at {level} level. "
            "Include vocabulary, grammar, pronunciation guidance, "
            "conversation practice and a small quiz."
        )
        st.markdown(answer)

# ================= STUDY =================
elif page == "Study Assistant":
    st.title("📚 Study Assistant")
    subject = st.selectbox(
        "Subject",
        ["Maths", "Science", "English", "Hindi",
         "Social Science", "Computer", "General Knowledge"]
    )
    question = st.text_area("Enter your question")
    if st.button("Explain"):
        if question:
            answer, _ = ask_ai(
                f"Explain this {subject} question clearly for a student. "
                "Give examples and a short revision summary:\n" + question
            )
            st.markdown(answer)

# ================= PDF =================
elif page == "PDF Assistant":
    st.title("📄 PDF Assistant")
    file = st.file_uploader("Upload PDF", type=["pdf"])
    if file:
        try:
            from pypdf import PdfReader
            reader = PdfReader(io.BytesIO(file.getvalue()))
            text = "\n".join(p.extract_text() or "" for p in reader.pages)
            st.success(f"{len(reader.pages)} pages loaded.")
            question = st.text_area("What do you want to know?")
            if st.button("Ask PDF"):
                answer, _ = ask_ai(
                    "Answer using this PDF content:\n"
                    + text[:22000] + "\nQuestion: " + question
                )
                st.markdown(answer)
        except Exception as e:
            st.error(str(e))

# ================= VISION =================
elif page == "AI Vision":
    st.title("👁️ AI Vision")
    st.info("Image understanding requires a configured vision-capable model backend.")
    file = st.file_uploader("Upload an image", type=["png","jpg","jpeg","webp"])
    if file:
        st.image(file, use_container_width=True)
        st.caption("Image preview is available. AI image analysis backend is not connected in this version.")

# ================= IMAGE STUDIO =================
elif page == "AI Image Studio":
    st.title("🎨 AI Image Studio")
    prompt = st.text_area("Describe the image")
    if st.button("Create Image Prompt"):
        if prompt:
            answer, _ = ask_ai(
                "Create a detailed image-generation prompt from this idea: " + prompt
            )
            st.markdown(answer)
    st.info("Actual image generation requires a configured image-generation API.")

# ================= VIDEO STUDIO =================
elif page == "Video Prompt Studio":
    st.title("🎬 Video Prompt Studio")
    idea = st.text_area("Describe your video idea")
    duration = st.selectbox("Duration", ["10 sec", "20 sec", "30 sec", "60 sec", "90 sec"])
    ratio = st.selectbox("Aspect ratio", ["9:16", "16:9", "1:1"])
    if st.button("Generate Storyboard"):
        if idea:
            answer, _ = ask_ai(
                f"Create a scene-by-scene video storyboard. "
                f"Duration: {duration}. Ratio: {ratio}. Idea: {idea}. "
                "Include image prompts, video prompts, dialogues, "
                "voiceover, camera movements and music suggestions."
            )
            st.markdown(answer)
    st.info("This creates video plans and prompts, not rendered video files.")

# ================= LIVE VOICE =================
elif page == "Live Voice":
    st.title("🎙️ NEXTGEN AI Live Voice")
    st.markdown("""
    <style>
    .orb-area {
      height:300px;display:flex;align-items:center;
      justify-content:center;position:relative;
    }
    .orb {
      height:165px;width:165px;border-radius:50%;
      background:radial-gradient(circle at 35% 30%,white,#70eaff 12%,
      #397bff 42%,#823bff 75%,#10152d);
      box-shadow:0 0 35px #42dfff,0 0 100px #684bff;
      animation:pulse 2s infinite ease-in-out;
    }
    @keyframes pulse {
      0%,100% {transform:scale(.9)}
      50% {transform:scale(1.1)}
    }
    </style>
    <div class="orb-area"><div class="orb"></div></div>
    <h2 style="text-align:center;color:#65dcff">NEXTGEN AI</h2>
    <p style="text-align:center;color:#a6b8d4">
      AI Voice Interface
    </p>
    """, unsafe_allow_html=True)
    st.warning(
        "यह animated interface है। वास्तविक दो-तरफ़ा live voice call "
        "के लिए अलग real-time voice backend और deployed URL जरूरी है।"
    )

# ================= HISTORY =================
elif page == "Chat History":
    st.title("🗂️ Chat History")
    if not st.session_state.user_id:
        st.info("Guest chat history केवल इसी active session में उपलब्ध है.")
    else:
        for cid, title, date in list_conversations(st.session_state.user_id):
            with st.expander(f"{title} · {date[:16]}"):
                for role, content in read_messages(cid):
                    st.markdown("**You:**" if role == "user" else "**NEXTGEN AI:**")
                    st.write(content)
                a,b = st.columns(2)
                with a:
                    if st.button("Open", key=f"open_{cid}"):
                        st.session_state.cid = cid
                        st.rerun()
                with b:
                    if st.button("Delete", key=f"delete_{cid}"):
                        delete_chat(cid)
                        if st.session_state.cid == cid:
                            st.session_state.cid = new_conversation(
                                st.session_state.user_id
                            )
                        st.rerun()

# ================= ABOUT =================
elif page == "About":
    st.title("🚀 About NEXTGEN AI")
    st.write("""
    NEXTGEN AI is a multi-purpose AI workspace.

    - AI Chat
    - Automatic Web Search
    - Current Affairs
    - App Builder
    - Coding School
    - Language Learning
    - Study Assistant
    - PDF Assistant
    - AI Vision preview
    - Image and Video Prompt Studio
    - Animated Voice Interface

    Some advanced features require their own APIs and backends.
    """)

st.divider()
st.markdown(
    "<p style='text-align:center;color:#8292ad'>NEXTGEN AI © 2026 · One Platform. Endless Possibilities.</p>",
    unsafe_allow_html=True
)
