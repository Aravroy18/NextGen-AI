
import streamlit as st
import requests
import sqlite3
import hashlib
import secrets
import json
import base64
import re
import os
import uuid
from datetime import datetime
from io import BytesIO

# ============================================================
# NEXTGEN AI
# Single-file Streamlit AI platform
# ============================================================

st.set_page_config(
    page_title="NEXTGEN AI",
    page_icon="✦",
    layout="wide",
    initial_sidebar_state="expanded"
)

APP_NAME = "NEXTGEN AI"
DB_PATH = "nextgen_ai.db"

GEMINI_DEFAULT = "gemini-2.5-flash"
GROQ_DEFAULT = "llama-3.3-70b-versatile"

# ============================================================
# SECRETS
# ============================================================

def get_secret(key, default=""):
    try:
        value = st.secrets.get(key, "")
        if value:
            return str(value).strip()
    except Exception:
        pass
    return os.getenv(key, default).strip()


# ============================================================
# DATABASE
# ============================================================

def database():
    con = sqlite3.connect(DB_PATH, check_same_thread=False)
    con.row_factory = sqlite3.Row
    return con


def init_database():
    with database() as con:

        con.execute("""
        CREATE TABLE IF NOT EXISTS users(
            id TEXT PRIMARY KEY,
            username TEXT UNIQUE,
            password TEXT,
            created TEXT
        )
        """)

        con.execute("""
        CREATE TABLE IF NOT EXISTS chats(
            id TEXT PRIMARY KEY,
            user_id TEXT,
            title TEXT,
            created TEXT,
            updated TEXT
        )
        """)

        con.execute("""
        CREATE TABLE IF NOT EXISTS messages(
            id TEXT PRIMARY KEY,
            chat_id TEXT,
            role TEXT,
            content TEXT,
            created TEXT
        )
        """)


def make_password(password):
    salt = secrets.token_hex(16)
    digest = hashlib.pbkdf2_hmac(
        "sha256",
        password.encode(),
        salt.encode(),
        200000
    ).hex()
    return salt + ":" + digest


def check_password(password, saved):
    try:
        salt, digest = saved.split(":")
        test = hashlib.pbkdf2_hmac(
            "sha256",
            password.encode(),
            salt.encode(),
            200000
        ).hex()
        return secrets.compare_digest(test, digest)
    except Exception:
        return False


def register_user(username, password):
    if len(username) < 3:
        return False, "Username बहुत छोटा है।"

    if len(password) < 8:
        return False, "Password कम-से-कम 8 characters का रखें।"

    try:
        with database() as con:
            con.execute(
                "INSERT INTO users VALUES(?,?,?,?)",
                (
                    str(uuid.uuid4()),
                    username,
                    make_password(password),
                    datetime.now().isoformat()
                )
            )
        return True, "Account बन गया!"
    except sqlite3.IntegrityError:
        return False, "Username पहले से मौजूद है।"


def authenticate(username, password):
    with database() as con:
        user = con.execute(
            "SELECT * FROM users WHERE username=?",
            (username,)
        ).fetchone()

    if user and check_password(password, user["password"]):
        return {
            "id": user["id"],
            "username": user["username"]
        }

    return None


def new_chat(user_id, title="New chat"):
    chat_id = str(uuid.uuid4())
    timestamp = datetime.now().isoformat()

    with database() as con:
        con.execute(
            "INSERT INTO chats VALUES(?,?,?,?,?)",
            (chat_id, user_id, title, timestamp, timestamp)
        )

    return chat_id


def get_chats(user_id):
    with database() as con:
        return con.execute(
            "SELECT * FROM chats WHERE user_id=? ORDER BY updated DESC",
            (user_id,)
        ).fetchall()


def get_messages(chat_id):
    with database() as con:
        return con.execute(
            "SELECT role,content FROM messages WHERE chat_id=? ORDER BY rowid",
            (chat_id,)
        ).fetchall()


def save_message(chat_id, role, content):
    with database() as con:
        con.execute(
            "INSERT INTO messages VALUES(?,?,?,?,?)",
            (
                str(uuid.uuid4()),
                chat_id,
                role,
                content,
                datetime.now().isoformat()
            )
        )

        con.execute(
            "UPDATE chats SET updated=? WHERE id=?",
            (datetime.now().isoformat(), chat_id)
        )


def rename_chat(chat_id, title):
    with database() as con:
        con.execute(
            "UPDATE chats SET title=? WHERE id=?",
            (title[:70], chat_id)
        )


def remove_chat(chat_id):
    with database() as con:
        con.execute("DELETE FROM messages WHERE chat_id=?", (chat_id,))
        con.execute("DELETE FROM chats WHERE id=?", (chat_id,))


# ============================================================
# SMART WEB SEARCH
# ============================================================

def needs_web_search(question):
    q = question.lower()

    patterns = [
        r"\btoday\b",
        r"\bcurrently\b",
        r"\bright now\b",
        r"\blatest\b",
        r"\bcurrent\b",
        r"\brecent\b",
        r"\bbreaking\b",
        r"\bthis week\b",
        r"\bthis month\b",
        r"\btoday's\b",
        r"\b2026\b",
        r"\bnews\b",
        r"\bweather\b",
        r"\blive score\b",
        r"\bstock price\b",
        r"\bexchange rate\b",
        r"\bआज\b",
        r"\bअभी\b",
        r"\bफिलहाल\b",
        r"\bताजा\b",
        r"\bताज़ा\b",
        r"\bलेटेस्ट\b",
        r"\bवर्तमान\b",
        r"\bसमाचार\b",
        r"\bखबर\b",
        r"\bमौसम\b",
        r"\bवेब सर्च\b",
        r"\bइंटरनेट पर\b",
        r"\bस्रोत\b"
    ]

    return any(re.search(pattern, q) for pattern in patterns)


def tavily_search(query):
    api_key = get_secret("TAVILY_API_KEY")

    if not api_key:
        return "Tavily API key configured नहीं है।"

    try:
        response = requests.post(
            "https://api.tavily.com/search",
            json={
                "api_key": api_key,
                "query": query,
                "search_depth": "basic",
                "max_results": 5,
                "include_answer": True
            },
            timeout=30
        )

        response.raise_for_status()
        data = response.json()

        output = []

        if data.get("answer"):
            output.append(data["answer"])

        for item in data.get("results", []):
            output.append(
                "TITLE: " + item.get("title", "") +
                "\nCONTENT: " + item.get("content", "") +
                "\nURL: " + item.get("url", "")
            )

        return "\n\n".join(output) or "No search results."

    except Exception as error:
        return "Web search error: " + str(error)


# ============================================================
# GEMINI AI
# ============================================================

def gemini_chat(messages, system_prompt):
    api_key = get_secret("GEMINI_API_KEY")

    if not api_key:
        raise Exception("GEMINI_API_KEY Streamlit Secrets में नहीं मिली।")

    model = get_secret("GEMINI_MODEL", GEMINI_DEFAULT)

    contents = []

    for message in messages:
        contents.append({
            "role": "model" if message["role"] == "assistant" else "user",
            "parts": [{"text": message["content"]}]
        })

    url = (
        "https://generativelanguage.googleapis.com/v1beta/models/"
        + model + ":generateContent"
    )

    payload = {
        "system_instruction": {
            "parts": [{"text": system_prompt}]
        },
        "contents": contents,
        "generationConfig": {
            "temperature": 0.7,
            "maxOutputTokens": 4096
        }
    }

    response = requests.post(
        url,
        params={"key": api_key},
        json=payload,
        timeout=90
    )

    if not response.ok:
        raise Exception(
            f"Gemini API Error {response.status_code}: "
            + response.text[:500]
        )

    data = response.json()

    return "".join(
        part.get("text", "")
        for part in data["candidates"][0]["content"]["parts"]
    )


# ============================================================
# GROQ AI
# ============================================================

def groq_chat(messages, system_prompt):
    api_key = get_secret("GROQ_API_KEY")

    if not api_key:
        raise Exception("GROQ_API_KEY Streamlit Secrets में नहीं मिली।")

    model = get_secret("GROQ_MODEL", GROQ_DEFAULT)

    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": system_prompt}
        ] + messages,
        "temperature": 0.7,
        "max_tokens": 4096
    }

    response = requests.post(
        "https://api.groq.com/openai/v1/chat/completions",
        headers={
            "Authorization": "Bearer " + api_key,
            "Content-Type": "application/json"
        },
        json=payload,
        timeout=90
    )

    if not response.ok:
        raise Exception(
            f"Groq API Error {response.status_code}: "
            + response.text[:500]
        )

    return response.json()["choices"][0]["message"]["content"]


# ============================================================
# SMART MODEL ROUTER
# ============================================================

def select_model(mode):
    if mode == "Gemini":
        return "Gemini"

    if mode == "Groq":
        return "Groq"

    return "Gemini"


# ============================================================
# AI RESPONSE
# ============================================================

def get_ai_response(messages, provider, web_context=""):

    system_prompt = """
You are NEXTGEN AI.

You are a helpful, intelligent and accurate AI assistant.

Rules:

1. Reply in the user's language.
2. Be clear and helpful.
3. Never invent facts.
4. For current information, use provided web search context.
5. Include source URLs when web search context is provided.
6. If information is uncertain, explain uncertainty.
7. Remember the conversation context provided in messages.
8. Explain complex concepts step by step.
9. Help with coding, education, research, writing and creativity.
10. Never pretend to have performed an action you did not perform.
"""

    if web_context:
        system_prompt += "\n\nWEB SEARCH RESULTS:\n" + web_context

    if provider == "Groq":
        return groq_chat(messages, system_prompt)

    return gemini_chat(messages, system_prompt)


# ============================================================
# CLOUDFARE IMAGE GENERATION
# ============================================================

def cloudflare_generate(prompt, ratio, reference=None):

    account = get_secret("CLOUDFLARE_ACCOUNT_ID")
    token = get_secret("CLOUDFLARE_API_TOKEN")

    model = get_secret(
        "CLOUDFLARE_IMAGE_MODEL",
        "@cf/black-forest-labs/flux-1-schnell"
    )

    if not account or not token:
        raise Exception(
            "Cloudflare Account ID या API Token Streamlit Secrets में missing है।"
        )

    url = (
        f"https://api.cloudflare.com/client/v4/accounts/"
        f"{account}/ai/run/{model}"
    )

    payload = {
        "prompt": prompt,
        "aspect_ratio": ratio
    }

    if reference:
        payload["image"] = base64.b64encode(reference).decode()

    response = requests.post(
        url,
        headers={
            "Authorization": "Bearer " + token
        },
        json=payload,
        timeout=180
    )

    if not response.ok:
        raise Exception(
            f"Cloudflare Error {response.status_code}: "
            + response.text[:700]
        )

    if "image/" in response.headers.get("content-type", ""):
        return response.content

    data = response.json()
    result = data.get("result", {})

    if isinstance(result, dict):
        for key in ("image", "data", "output"):
            value = result.get(key)
            if isinstance(value, str):
                try:
                    return base64.b64decode(value)
                except Exception:
                    pass

    raise Exception(
        "Image response नहीं मिला। चुने गए Cloudflare model का "
        "input/output format जाँचें।"
    )


# ============================================================
# GROQ SPEECH TO TEXT
# ============================================================

def transcribe_audio(audio_bytes, filename="recording.wav"):

    api_key = get_secret("GROQ_API_KEY")

    if not api_key:
        raise Exception("Groq API key missing है।")

    response = requests.post(
        "https://api.groq.com/openai/v1/audio/transcriptions",
        headers={
            "Authorization": "Bearer " + api_key
        },
        files={
            "file": (filename, audio_bytes)
        },
        data={
            "model": "whisper-large-v3-turbo"
        },
        timeout=120
    )

    if not response.ok:
        raise Exception(response.text[:500])

    return response.json().get("text", "")


# ============================================================
# CSS
# ============================================================

st.markdown("""
<style>

.stApp {
    background: #090b10;
    color: #f2f4f8;
}

[data-testid="stSidebar"] {
    background: #0e1119;
    border-right: 1px solid #242b39;
}

.block-container {
    max-width: 1150px;
    padding-top: 2rem;
}

.brand {
    font-size: 28px;
    font-weight: 800;
    letter-spacing: -1px;
}

.hero {
    text-align: center;
    padding: 65px 10px 30px;
}

.hero h1 {
    font-size: 48px;
    font-weight: 800;
    letter-spacing: -2px;
}

.hero p {
    color: #929bad;
    font-size: 16px;
}

div[data-testid="stChatMessage"] {
    background: #111722;
    border: 1px solid #252d3b;
    border-radius: 16px;
    padding: 14px;
}

.stButton button {
    border-radius: 12px;
}

</style>
""", unsafe_allow_html=True)


# ============================================================
# INITIALIZATION
# ============================================================

init_database()

if "user" not in st.session_state:
    st.session_state.user = None

if "active_chat" not in st.session_state:
    st.session_state.active_chat = None

if "page" not in st.session_state:
    st.session_state.page = "Chat"


# ============================================================
# LOGIN SCREEN
# ============================================================

def login_screen():

    st.markdown("""
    <div class="hero">
        <h1>✦ NEXTGEN AI</h1>
        <p>Your AI workspace. Your possibilities.</p>
    </div>
    """, unsafe_allow_html=True)

    _, center, _ = st.columns([1, 1.4, 1])

    with center:

        login_tab, register_tab, guest_tab = st.tabs(
            ["Login", "Create Account", "Continue as Guest"]
        )

        with login_tab:

            username = st.text_input("Username", key="login_user")
            password = st.text_input(
                "Password",
                type="password",
                key="login_password"
            )

            if st.button("Login", use_container_width=True):

                user = authenticate(username, password)

                if user:
                    st.session_state.user = user
                    st.rerun()
                else:
                    st.error("Incorrect username or password.")

        with register_tab:

            username = st.text_input("New username", key="reg_user")
            password = st.text_input(
                "New password",
                type="password",
                key="reg_pass"
            )

            if st.button("Create Account", use_container_width=True):

                ok, message = register_user(username, password)

                if ok:
                    st.success(message)
                else:
                    st.error(message)

        with guest_tab:

            st.write("Explore NEXTGEN AI without creating an account.")

            if st.button("Continue as Guest", use_container_width=True):
                st.session_state.user = {
                    "id": "guest-" + str(uuid.uuid4()),
                    "username": "Guest"
                }
                st.session_state.guest_chats = {}
                st.rerun()


# ============================================================
# MAIN APPLICATION
# ============================================================

def main():

    if st.session_state.user is None:
        login_screen()
        return

    user = st.session_state.user
    user_id = user["id"]
    guest = user_id.startswith("guest-")

    # --------------------------------------------------------
    # SIDEBAR
    # --------------------------------------------------------

    with st.sidebar:

        st.markdown(
            '<div class="brand">✦ NEXTGEN AI</div>',
            unsafe_allow_html=True
        )

        st.caption("Welcome, " + user["username"])

        if st.button("＋ New Chat", use_container_width=True):

            if guest:
                chat_id = str(uuid.uuid4())
                st.session_state.guest_chats[chat_id] = {
                    "title": "New chat",
                    "messages": []
                }
            else:
                chat_id = new_chat(user_id)

            st.session_state.active_chat = chat_id
            st.session_state.page = "Chat"
            st.rerun()

        st.divider()

        pages = [
            "Chat",
            "Image Studio",
            "Files & PDF",
            "Settings"
        ]

        st.session_state.page = st.radio(
            "Workspace",
            pages,
            index=pages.index(st.session_state.page)
        )

        st.divider()

        st.markdown("### Chat History")

        if guest:
            chats = [
                {"id": k, **v}
                for k, v in st.session_state.guest_chats.items()
            ]
        else:
            chats = get_chats(user_id)

        for chat in chats:

            chat_id = chat["id"]

            if st.button(
                "💬 " + chat["title"][:25],
                key="chat_" + chat_id,
                use_container_width=True
            ):
                st.session_state.active_chat = chat_id
                st.session_state.page = "Chat"
                st.rerun()

        st.divider()

        if st.button("Logout", use_container_width=True):
            st.session_state.user = None
            st.session_state.active_chat = None
            st.rerun()

    # ========================================================
    # CHAT PAGE
    # ========================================================

    if st.session_state.page == "Chat":

        chat_id = st.session_state.active_chat

        if not chat_id:

            st.markdown("""
            <div class="hero">
                <h1>What can I help with?</h1>
                <p>Ask anything. Explore everything.</p>
            </div>
            """, unsafe_allow_html=True)

            if st.button("＋ Start New Chat", type="primary"):

                if guest:
                    chat_id = str(uuid.uuid4())
                    st.session_state.guest_chats[chat_id] = {
                        "title": "New chat",
                        "messages": []
                    }
                else:
                    chat_id = new_chat(user_id)

                st.session_state.active_chat = chat_id
                st.rerun()

            prompt = st.chat_input("Message NEXTGEN AI...")

            if prompt:

                if guest:
                    chat_id = str(uuid.uuid4())
                    st.session_state.guest_chats[chat_id] = {
                        "title": prompt[:45],
                        "messages": []
                    }
                else:
                    chat_id = new_chat(user_id, prompt[:45])

                st.session_state.active_chat = chat_id
                st.session_state.pending_prompt = prompt
                st.rerun()

            return

        # Load conversation
        if guest:
            record = st.session_state.guest_chats[chat_id]
            messages = record["messages"]
        else:
            messages = [
                dict(role=m["role"], content=m["content"])
                for m in get_messages(chat_id)
            ]

        for message in messages:

            with st.chat_message(message["role"]):
                st.markdown(message["content"])

        # ----------------------------------------------------
        # MODEL SELECTION
        # ----------------------------------------------------

        provider = st.session_state.get("provider", "Auto")

        # ----------------------------------------------------
        # VOICE INPUT
        # ----------------------------------------------------

        with st.expander("🎙 Voice input"):
            audio = st.audio_input("Record your question")

            if audio and st.button("Transcribe voice"):
                try:
                    text = transcribe_audio(audio.getvalue())
                    st.session_state.voice_text = text
                    st.success("Voice transcribed.")
                    st.text_area("Recognized text", text)
                except Exception as error:
                    st.error(str(error))

        # ----------------------------------------------------
        # CHAT COMPOSER
        # ----------------------------------------------------

        uploaded_file = st.file_uploader(
            "＋ Attach a file",
            type=["pdf", "txt", "csv", "png", "jpg", "jpeg"],
            key="chat_attachment"
        )

        prompt = st.chat_input("Message NEXTGEN AI...")

        if "pending_prompt" in st.session_state:
            prompt = st.session_state.pop("pending_prompt")

        if not prompt and st.session_state.get("voice_text"):
            if st.button("Use transcribed voice text"):
                prompt = st.session_state.pop("voice_text")

        if prompt:

            prompt_text = prompt

            if uploaded_file:

                file_bytes = uploaded_file.getvalue()

                if uploaded_file.name.lower().endswith(".pdf"):
                    try:
                        from pypdf import PdfReader
                        reader = PdfReader(BytesIO(file_bytes))
                        extracted = "\n".join(
                            page.extract_text() or ""
                            for page in reader.pages
                        )
                        prompt_text += "\n\nPDF CONTENT:\n" + extracted[:18000]
                    except Exception as error:
                        st.warning("PDF read error: " + str(error))

                elif uploaded_file.type.startswith("text/") or uploaded_file.name.endswith(".csv"):
                    prompt_text += "\n\nFILE CONTENT:\n"
                    prompt_text += file_bytes.decode(
                        "utf-8", errors="replace"
                    )[:12000]

            with st.chat_message("user"):
                st.markdown(prompt_text)

            if guest:
                record["messages"].append({
                    "role": "user",
                    "content": prompt_text
                })
            else:
                save_message(chat_id, "user", prompt_text)

            # ------------------------------------------------
            # SMART WEB SEARCH
            # ------------------------------------------------

            web_context = ""

            if needs_web_search(prompt_text):

                with st.spinner("Searching for current information..."):
                    web_context = tavily_search(prompt_text)

            # ------------------------------------------------
            # MODEL ROUTER
            # ------------------------------------------------

            selected_provider = select_model(provider)

            with st.chat_message("assistant"):

                try:

                    with st.spinner("NEXTGEN AI is thinking..."):

                        history = messages + [
                            {
                                "role": "user",
                                "content": prompt_text
                            }
                        ]

                        answer = get_ai_response(
                            history[-20:],
                            selected_provider,
                            web_context
                        )

                    st.markdown(answer)

                except Exception as error:

                    answer = "AI Error: " + str(error)
                    st.error(answer)

            if guest:
                record["messages"].append({
                    "role": "assistant",
                    "content": answer
                })
            else:
                save_message(chat_id, "assistant", answer)

            st.rerun()

    # ========================================================
    # IMAGE STUDIO
    # ========================================================

    elif st.session_state.page == "Image Studio":

        st.title("✦ Image Studio")

        st.caption("Create and edit images using Cloudflare AI.")

        prompt = st.text_area(
            "Describe your image or edit",
            placeholder="Create a cinematic futuristic city..."
        )

        reference = st.file_uploader(
            "Upload reference image for editing",
            type=["png", "jpg", "jpeg", "webp"]
        )

        c1, c2 = st.columns(2)

        with c1:
            ratio = st.selectbox(
                "Aspect Ratio",
                [
                    "1:1",
                    "9:16",
                    "16:9",
                    "4:3",
                    "3:4",
                    "3:2",
                    "2:3"
                ]
            )

        with c2:
            mode = st.selectbox(
                "Image Mode",
                ["Generate", "Edit with reference"]
            )

        if st.button("Generate Image", type="primary"):

            if not prompt.strip():
                st.warning("Enter an image prompt.")
            elif mode == "Edit with reference" and not reference:
                st.warning("Upload a reference image first.")
            else:
                try:

                    with st.spinner("Creating image..."):

                        image = cloudflare_generate(
                            prompt,
                            ratio,
                            reference.getvalue() if reference else None
                        )

                    st.image(
                        image,
                        caption="NEXTGEN AI Generated Image",
                        use_container_width=True
                    )

                    st.download_button(
                        "Download Image",
                        image,
                        file_name="nextgen-ai-image.png",
                        mime="image/png"
                    )

                except Exception as error:
                    st.error(str(error))

    # ========================================================
    # FILES AND PDF
    # ========================================================

    elif st.session_state.page == "Files & PDF":

        st.title("Files & PDF Assistant")

        file = st.file_uploader(
            "Upload your PDF or text file",
            type=["pdf", "txt", "csv"]
        )

        if file:

            if file.name.lower().endswith(".pdf"):

                try:
                    from pypdf import PdfReader

                    reader = PdfReader(BytesIO(file.getvalue()))

                    content = "\n".join(
                        page.extract_text() or ""
                        for page in reader.pages
                    )

                    st.text_area(
                        "Extracted PDF text",
                        content,
                        height=350
                    )

                    st.download_button(
                        "Download extracted text",
                        content,
                        file_name="extracted.txt"
                    )

                except Exception as error:
                    st.error(str(error))

            else:

                content = file.getvalue().decode(
                    "utf-8",
                    errors="replace"
                )

                st.text_area("File content", content, height=350)

    # ========================================================
    # SETTINGS
    # ========================================================

    elif st.session_state.page == "Settings":

        st.title("Settings")

        st.subheader("AI Provider")

        st.selectbox(
            "Choose AI model provider",
            ["Auto", "Gemini", "Groq"],
            key="provider"
        )

        st.caption(
            "Auto currently uses Gemini. Groq can be selected manually."
        )

        st.divider()

        st.subheader("API Connection Status")

        keys = {
            "Gemini": "GEMINI_API_KEY",
            "Groq": "GROQ_API_KEY",
            "Tavily": "TAVILY_API_KEY",
            "Cloudflare Account": "CLOUDFLARE_ACCOUNT_ID",
            "Cloudflare Token": "CLOUDFLARE_API_TOKEN"
        }

        for name, key in keys.items():

            configured = bool(get_secret(key))

            st.write(
                ("🟢 " if configured else "⚪ ")
                + name
                + ": "
                + ("Configured" if configured else "Not configured")
            )

        st.divider()

        st.subheader("About NEXTGEN AI")

        st.write(
            "NEXTGEN AI is an independent AI workspace created by Arav."
        )

        st.caption(
            "AI responses may contain errors. Verify important information."
        )


# ============================================================
# RUN APP
# ============================================================

if __name__ == "__main__":
    main()
