# ============================================================
# NEXTGEN AI — COMPLETE STREAMLIT APP
# Authentication | Guest Mode | AI Chat | Finnhub | Cloudflare
# SQLite | Image Studio | Stock Learning | App & Website Builder
# ============================================================

import os
import io
import re
import json
import time
import uuid
import base64
import hashlib
import hmac
import sqlite3
import zipfile
import requests
import streamlit as st

from datetime import datetime, timedelta
from html import escape

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass


# ============================================================
# 1. APP CONFIGURATION
# ============================================================

st.set_page_config(
    page_title="NEXTGEN AI",
    page_icon="✦",
    layout="wide",
    initial_sidebar_state="expanded"
)

APP_NAME = "NEXTGEN AI"
DB_FILE = "nextgen_ai.sqlite3"

OPENAI_MODEL_DEFAULT = "gpt-4.1-mini"
GEMINI_MODEL_DEFAULT = "gemini-2.5-flash"
GROQ_MODEL_DEFAULT = "llama-3.3-70b-versatile"

CLOUDFLARE_MODEL_DEFAULT = (
    "@cf/black-forest-labs/flux-1-schnell"
)

SYSTEM_PROMPT = """
You are NEXTGEN AI, a helpful, intelligent, friendly and professional
AI assistant.

Your creator is Arav, a student at Swami Vivekanand Shiksha Niketan.
He is interested in AI, Python, technology, app development,
creative projects and learning new skills.

Be respectful, clear, useful and encouraging.
Use the language used by the user: Hindi, English or Hinglish.
Explain difficult topics in simple steps.
Do not invent facts, awards, achievements or personal details.
For current information, use web search when available.
For finance, provide educational information and explain risks.
Do not promise profits or give guaranteed stock predictions.
"""


# ============================================================
# 2. SECRET MANAGEMENT
# ============================================================

def get_secret(key, default=""):
    """
    Read secrets from Streamlit Secrets first,
    then from environment variables.
    Supports root secrets and [api_keys] / [models].
    """

    value = ""

    try:
        if key in st.secrets:
            value = st.secrets[key]

        if not value and "api_keys" in st.secrets:
            section = st.secrets["api_keys"]
            value = section.get(key, "")

        if not value and "models" in st.secrets:
            section = st.secrets["models"]
            value = section.get(key, "")

    except Exception:
        value = ""

    if not value:
        value = os.getenv(key, default)

    return str(value or default).strip()


OPENAI_KEY = get_secret("OPENAI_API_KEY")
GEMINI_KEY = get_secret("GEMINI_API_KEY")
GROQ_KEY = get_secret("GROQ_API_KEY")

FINNHUB_KEY = get_secret("FINNHUB_API_KEY")
TAVILY_KEY = get_secret("TAVILY_API_KEY")

CF_ACCOUNT_ID = get_secret("CLOUDFLARE_ACCOUNT_ID")
CF_API_TOKEN = get_secret("CLOUDFLARE_API_TOKEN")

OPENAI_MODEL = get_secret(
    "OPENAI_MODEL",
    OPENAI_MODEL_DEFAULT
)

GEMINI_MODEL = get_secret(
    "GEMINI_MODEL",
    GEMINI_MODEL_DEFAULT
)

GROQ_MODEL = get_secret(
    "GROQ_MODEL",
    GROQ_MODEL_DEFAULT
)

CF_IMAGE_MODEL = get_secret(
    "CLOUDFLARE_IMAGE_MODEL",
    CLOUDFLARE_MODEL_DEFAULT
)


# ============================================================
# 3. DATABASE
# ============================================================

def db_connect():
    con = sqlite3.connect(
        DB_FILE,
        timeout=30,
        check_same_thread=False
    )
    con.row_factory = sqlite3.Row
    return con


def init_database():
    with db_connect() as con:

        con.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                email TEXT UNIQUE NOT NULL,
                password_hash TEXT NOT NULL,
                salt TEXT NOT NULL,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
        """)

        con.execute("""
            CREATE TABLE IF NOT EXISTS chats (
                id TEXT PRIMARY KEY,
                user_id TEXT NOT NULL,
                title TEXT DEFAULT 'New Chat',
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
        """)

        con.execute("""
            CREATE TABLE IF NOT EXISTS messages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                chat_id TEXT NOT NULL,
                user_id TEXT NOT NULL,
                role TEXT NOT NULL,
                content TEXT NOT NULL,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
        """)

        con.execute("""
            CREATE TABLE IF NOT EXISTS creations (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id TEXT NOT NULL,
                title TEXT,
                category TEXT,
                content TEXT,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
        """)

        con.execute("""
            CREATE INDEX IF NOT EXISTS idx_messages_chat
            ON messages(chat_id, id)
        """)

        con.execute("""
            CREATE INDEX IF NOT EXISTS idx_chats_user
            ON chats(user_id, created_at)
        """)

        con.commit()


init_database()


# ============================================================
# 4. PASSWORD SECURITY
# ============================================================

def make_password_hash(password, salt=None):
    if salt is None:
        salt = os.urandom(16).hex()

    hashed = hashlib.pbkdf2_hmac(
        "sha256",
        password.encode("utf-8"),
        bytes.fromhex(salt),
        200000
    ).hex()

    return hashed, salt


def verify_password(password, saved_hash, salt):
    new_hash, _ = make_password_hash(password, salt)
    return hmac.compare_digest(new_hash, saved_hash)


# ============================================================
# 5. SESSION STATE
# ============================================================

SESSION_DEFAULTS = {
    "authenticated": False,
    "user_id": None,
    "user_name": "",
    "user_email": "",
    "guest_mode": False,
    "page": "Dashboard",
    "chat_id": None,
    "messages": [],
    "web_search_enabled": True,
    "last_provider": "Not connected",
    "last_search": "Not used",
    "generated_image": None,
    "generated_image_prompt": "",
    "generated_project": None,
    "generated_website": None,
    "stock_symbol": "AAPL",
    "stock_data": None,
    "stock_history": None,
    "image_rating": None
}

for key, value in SESSION_DEFAULTS.items():
    if key not in st.session_state:
        st.session_state[key] = value


# ============================================================
# 6. AUTHENTICATION FUNCTIONS
# ============================================================

def create_account(name, email, password):
    name = name.strip()
    email = email.strip().lower()

    if len(name) < 2:
        return False, "Please enter your name."

    if not re.match(r"^[^@\s]+@[^@\s]+\.[^@\s]+$", email):
        return False, "Please enter a valid email address."

    if len(password) < 8:
        return False, "Password must contain at least 8 characters."

    password_hash, salt = make_password_hash(password)
    user_id = str(uuid.uuid4())

    try:
        with db_connect() as con:
            con.execute("""
                INSERT INTO users
                (id, name, email, password_hash, salt)
                VALUES (?, ?, ?, ?, ?)
            """, (
                user_id,
                name,
                email,
                password_hash,
                salt
            ))
            con.commit()

        return True, user_id

    except sqlite3.IntegrityError:
        return False, "An account with this email already exists."

    except sqlite3.Error:
        return False, "Could not create account. Please try again."


def authenticate_user(email, password):
    email = email.strip().lower()

    try:
        with db_connect() as con:
            user = con.execute("""
                SELECT *
                FROM users
                WHERE email = ?
            """, (email,)).fetchone()

        if not user:
            return None

        if verify_password(
            password,
            user["password_hash"],
            user["salt"]
        ):
            return dict(user)

        return None

    except sqlite3.Error:
        return None


def start_user_session(user):
    st.session_state.authenticated = True
    st.session_state.guest_mode = False
    st.session_state.user_id = user["id"]
    st.session_state.user_name = user["name"]
    st.session_state.user_email = user["email"]
    st.session_state.page = "Dashboard"
    st.session_state.chat_id = None
    st.session_state.messages = []


def start_guest_session():
    guest_id = "guest_" + str(uuid.uuid4())

    st.session_state.authenticated = True
    st.session_state.guest_mode = True
    st.session_state.user_id = guest_id
    st.session_state.user_name = "Guest"
    st.session_state.user_email = ""
    st.session_state.page = "Dashboard"
    st.session_state.chat_id = None
    st.session_state.messages = []


def logout():
    for key in SESSION_DEFAULTS:
        if key in st.session_state:
            st.session_state[key] = SESSION_DEFAULTS[key]

    st.rerun()


# ============================================================
# 7. AUTHENTICATION SCREEN
# ============================================================

def authentication_screen():

    st.markdown("""
    <style>
    .auth-wrap {
        max-width: 650px;
        margin: 55px auto 20px auto;
        padding: 30px;
        border: 1px solid rgba(255,255,255,.12);
        border-radius: 22px;
        background: rgba(20,25,43,.92);
        box-shadow: 0 15px 50px rgba(0,0,0,.25);
    }
    .auth-title {
        font-size: 42px;
        font-weight: 800;
        text-align: center;
        color: white;
        letter-spacing: 1px;
    }
    .auth-subtitle {
        text-align: center;
        color: #c7cbd5;
        margin-bottom: 25px;
    }
    </style>
    """, unsafe_allow_html=True)

    st.markdown(
        '<div class="auth-wrap">'
        '<div class="auth-title">✦ NEXTGEN AI</div>'
        '<div class="auth-subtitle">'
        'Your intelligent workspace'
        '</div></div>',
        unsafe_allow_html=True
    )

    left, center, right = st.columns([1, 2, 1])

    with center:

        signup_tab, login_tab, guest_tab = st.tabs([
            "✦ Sign Up",
            "↪ Login",
            "Continue as Guest"
        ])

        with signup_tab:
            st.subheader("Create your account")

            with st.form("signup_form"):
                name = st.text_input("Full name")
                email = st.text_input("Email address")
                password = st.text_input(
                    "Password",
                    type="password"
                )
                confirm = st.text_input(
                    "Confirm password",
                    type="password"
                )

                submitted = st.form_submit_button(
                    "Create Account",
                    use_container_width=True
                )

                if submitted:

                    if password != confirm:
                        st.error("Passwords do not match.")

                    else:
                        success, result = create_account(
                            name,
                            email,
                            password
                        )

                        if success:
                            st.success("Account created successfully!")

                            user = {
                                "id": result,
                                "name": name.strip(),
                                "email": email.strip().lower()
                            }

                            start_user_session(user)
                            st.rerun()

                        else:
                            st.error(result)

        with login_tab:
            st.subheader("Welcome back")

            with st.form("login_form"):
                login_email = st.text_input(
                    "Email address",
                    key="login_email"
                )

                login_password = st.text_input(
                    "Password",
                    type="password",
                    key="login_password"
                )

                login_submit = st.form_submit_button(
                    "Login",
                    use_container_width=True
                )

                if login_submit:
                    user = authenticate_user(
                        login_email,
                        login_password
                    )

                    if user:
                        start_user_session(user)
                        st.rerun()
                    else:
                        st.error(
                            "Incorrect email or password."
                        )

        with guest_tab:
            st.subheader("Explore NEXTGEN AI")

            st.write(
                "Continue without creating an account. "
                "Guest data is kept separate from registered accounts."
            )

            if st.button(
                "Continue as Guest",
                use_container_width=True
            ):
                start_guest_session()
                st.rerun()

    st.caption(
        "Use an account only on a device you trust. "
        "Guest sessions are not a substitute for a registered account."
    )


# ============================================================
# 8. DATABASE CHAT FUNCTIONS
# ============================================================

def create_new_chat():
    chat_id = str(uuid.uuid4())
    user_id = st.session_state.user_id

    try:
        with db_connect() as con:
            con.execute("""
                INSERT INTO chats (id, user_id, title)
                VALUES (?, ?, ?)
            """, (
                chat_id,
                user_id,
                "New Chat"
            ))
            con.commit()

        st.session_state.chat_id = chat_id
        st.session_state.messages = []

        return chat_id

    except sqlite3.Error as exc:
        st.error(f"Could not create chat: {exc}")
        return None


def get_user_chats():
    user_id = st.session_state.user_id

    try:
        with db_connect() as con:
            rows = con.execute("""
                SELECT id, title, created_at
                FROM chats
                WHERE user_id = ?
                ORDER BY created_at DESC
            """, (user_id,)).fetchall()

        return [dict(row) for row in rows]

    except sqlite3.Error:
        return []


def get_messages(chat_id):
    if not chat_id:
        return []

    try:
        with db_connect() as con:
            rows = con.execute("""
                SELECT role, content
                FROM messages
                WHERE chat_id = ?
                  AND user_id = ?
                ORDER BY id ASC
            """, (
                chat_id,
                st.session_state.user_id
            )).fetchall()

        return [
            {
                "role": row["role"],
                "content": row["content"]
            }
            for row in rows
        ]

    except sqlite3.Error as exc:
        st.error(f"Chat history error: {exc}")
        return []


def save_message(chat_id, role, content):
    if not chat_id:
        return False

    try:
        with db_connect() as con:
            con.execute("""
                INSERT INTO messages
                (chat_id, user_id, role, content)
                VALUES (?, ?, ?, ?)
            """, (
                chat_id,
                st.session_state.user_id,
                role,
                str(content)
            ))

            if role == "user":
                title = str(content).strip()[:45]

                con.execute("""
                    UPDATE chats
                    SET title = ?
                    WHERE id = ? AND user_id = ?
                """, (
                    title or "New Chat",
                    chat_id,
                    st.session_state.user_id
                ))

            con.commit()

        return True

    except sqlite3.Error as exc:
        st.error(f"Could not save message: {exc}")
        return False


def delete_current_chat():
    chat_id = st.session_state.chat_id

    if not chat_id:
        return

    try:
        with db_connect() as con:
            con.execute("""
                DELETE FROM messages
                WHERE chat_id = ? AND user_id = ?
            """, (
                chat_id,
                st.session_state.user_id
            ))

            con.execute("""
                DELETE FROM chats
                WHERE id = ? AND user_id = ?
            """, (
                chat_id,
                st.session_state.user_id
            ))

            con.commit()

        st.session_state.chat_id = None
        st.session_state.messages = []

    except sqlite3.Error as exc:
        st.error(f"Could not delete chat: {exc}")


# ============================================================
# 9. AI RESPONSE HELPERS
# ============================================================

def extract_openai_text(data):
    if data.get("output_text"):
        return data["output_text"]

    output_text = []

    for item in data.get("output", []):
        for part in item.get("content", []):
            if part.get("type") in ("output_text", "text"):
                output_text.append(
                    part.get("text", "")
                )

    return "\n".join(output_text).strip()


def prepare_ai_input(messages):
    prepared = []

    for message in messages[-20:]:
        role = message.get("role", "user")

        if role not in ("user", "assistant"):
            continue

        prepared.append({
            "role": role,
            "content": str(message.get("content", ""))
        })

    return prepared


# ============================================================
# 10. OPENAI
# ============================================================

def openai_request(messages, use_web_search=False):

    if not OPENAI_KEY:
        raise RuntimeError("OpenAI API key is not configured.")

    payload = {
        "model": OPENAI_MODEL,
        "instructions": SYSTEM_PROMPT,
        "input": prepare_ai_input(messages)
    }

    if use_web_search:
        payload["tools"] = [
            {"type": "web_search"}
        ]

    response = requests.post(
        "https://api.openai.com/v1/responses",
        headers={
            "Authorization": f"Bearer {OPENAI_KEY}",
            "Content-Type": "application/json"
        },
        json=payload,
        timeout=90
    )

    if response.status_code >= 400:
        raise RuntimeError(
            f"OpenAI error {response.status_code}: "
            f"{response.text[:350]}"
        )

    data = response.json()
    answer = extract_openai_text(data)

    if not answer:
        raise RuntimeError("OpenAI returned an empty answer.")

    return answer


# ============================================================
# 11. GEMINI
# ============================================================

def gemini_request(messages):

    if not GEMINI_KEY:
        raise RuntimeError("Gemini API key is not configured.")

    contents = []

    for message in prepare_ai_input(messages):
        role = (
            "model"
            if message["role"] == "assistant"
            else "user"
        )

        contents.append({
            "role": role,
            "parts": [
                {"text": message["content"]}
            ]
        })

    url = (
        "https://generativelanguage.googleapis.com/v1beta/"
        f"models/{GEMINI_MODEL}:generateContent"
        f"?key={GEMINI_KEY}"
    )

    response = requests.post(
        url,
        json={
            "systemInstruction": {
                "parts": [{"text": SYSTEM_PROMPT}]
            },
            "contents": contents
        },
        timeout=90
    )

    if response.status_code >= 400:
        raise RuntimeError(
            f"Gemini error {response.status_code}: "
            f"{response.text[:350]}"
        )

    data = response.json()

    answer = (
        data.get("candidates", [{}])[0]
        .get("content", {})
        .get("parts", [{}])[0]
        .get("text", "")
    )

    if not answer:
        raise RuntimeError("Gemini returned an empty answer.")

    return answer


# ============================================================
# 12. GROQ
# ============================================================

def groq_request(messages):

    if not GROQ_KEY:
        raise RuntimeError("Groq API key is not configured.")

    chat_messages = [
        {
            "role": "system",
            "content": SYSTEM_PROMPT
        }
    ]

    chat_messages.extend(prepare_ai_input(messages))

    response = requests.post(
        "https://api.groq.com/openai/v1/chat/completions",
        headers={
            "Authorization": f"Bearer {GROQ_KEY}",
            "Content-Type": "application/json"
        },
        json={
            "model": GROQ_MODEL,
            "messages": chat_messages
        },
        timeout=90
    )

    if response.status_code >= 400:
        raise RuntimeError(
            f"Groq error {response.status_code}: "
            f"{response.text[:350]}"
        )

    data = response.json()

    answer = (
        data.get("choices", [{}])[0]
        .get("message", {})
        .get("content", "")
    )

    if not answer:
        raise RuntimeError("Groq returned an empty answer.")

    return answer


# ============================================================
# 13. AI PROVIDER ROUTER
# ============================================================

def ask_ai(messages):

    providers = [
        ("OpenAI", OPENAI_KEY, openai_request),
        ("Gemini", GEMINI_KEY, gemini_request),
        ("Groq", GROQ_KEY, groq_request)
    ]

    errors = []

    for provider_name, api_key, provider_function in providers:

        if not api_key:
            continue

        try:
            answer = provider_function(messages)

            st.session_state.last_provider = provider_name

            return answer

        except Exception as exc:
            errors.append(
                f"{provider_name}: {str(exc)[:250]}"
            )

    if not errors:
        raise RuntimeError(
            "No AI API key is configured. "
            "Add OPENAI_API_KEY, GEMINI_API_KEY "
            "or GROQ_API_KEY in Streamlit Secrets."
        )

    raise RuntimeError(
        "All configured AI providers failed:\n"
        + "\n".join(errors)
    )


# ============================================================
# 14. SMART WEB SEARCH
# ============================================================

def needs_web_search(query):

    keywords = [
        "today",
        "latest",
        "current",
        "now",
        "news",
        "weather",
        "price today",
        "live price",
        "recent",
        "2026",
        "अभी",
        "आज",
        "ताजा",
        "लेटेस्ट",
        "न्यूज़",
        "समाचार",
        "वर्तमान",
        "कीमत अभी"
    ]

    query_lower = query.lower()

    return any(
        keyword in query_lower
        for keyword in keywords
    )


def tavily_search(query):

    if not TAVILY_KEY:
        raise RuntimeError("Tavily API key is not configured.")

    response = requests.post(
        "https://api.tavily.com/search",
        json={
            "api_key": TAVILY_KEY,
            "query": query,
            "search_depth": "basic",
            "max_results": 5
        },
        timeout=35
    )

    if response.status_code >= 400:
        raise RuntimeError(
            f"Tavily error: {response.text[:250]}"
        )

    data = response.json()

    results = []

    for item in data.get("results", []):
        results.append(
            "Title: " + item.get("title", "") +
            "\nURL: " + item.get("url", "") +
            "\nContent: " + item.get("content", "")
        )

    return "\n\n".join(results)


def smart_ai_answer(messages):

    latest_prompt = messages[-1]["content"]

    if (
        st.session_state.web_search_enabled
        and needs_web_search(latest_prompt)
    ):

        if OPENAI_KEY:
            try:
                answer = openai_request(
                    messages,
                    use_web_search=True
                )

                st.session_state.last_provider = (
                    "OpenAI Web Search"
                )
                st.session_state.last_search = "OpenAI Web Search"

                return answer

            except Exception:
                pass

        if TAVILY_KEY:
            try:
                search_results = tavily_search(
                    latest_prompt
                )

                augmented = list(messages)

                augmented[-1] = {
                    "role": "user",
                    "content": (
                        latest_prompt
                        + "\n\nUse the following live search "
                        "results where relevant. Explain uncertainty "
                        "and do not invent facts:\n\n"
                        + search_results
                    )
                }

                answer = ask_ai(augmented)

                st.session_state.last_search = "Tavily"

                return answer

            except Exception:
                pass

        st.session_state.last_search = (
            "Search unavailable"
        )

    else:
        st.session_state.last_search = "Not used"

    return ask_ai(messages)


# ============================================================
# 15. CLOUDFLARE IMAGE GENERATION
# ============================================================

def generate_cloudflare_image(prompt):

    if not CF_ACCOUNT_ID or not CF_API_TOKEN:
        raise RuntimeError(
            "Cloudflare Account ID or API Token is missing."
        )

    endpoint = (
        "https://api.cloudflare.com/client/v4/accounts/"
        f"{CF_ACCOUNT_ID}/ai/run/{CF_IMAGE_MODEL}"
    )

    response = requests.post(
        endpoint,
        headers={
            "Authorization": f"Bearer {CF_API_TOKEN}",
            "Content-Type": "application/json"
        },
        json={
            "prompt": prompt,
            "steps": 4
        },
        timeout=180
    )

    if response.status_code >= 400:
        raise RuntimeError(
            f"Cloudflare error {response.status_code}: "
            f"{response.text[:400]}"
        )

    content_type = response.headers.get(
        "content-type", ""
    ).lower()

    if content_type.startswith("image/"):
        return response.content

    data = response.json()

    if data.get("success") is False:
        raise RuntimeError(
            str(data.get("errors", data))[:500]
        )

    result = data.get("result", {})

    image_data = None

    if isinstance(result, dict):
        image_data = (
            result.get("image")
            or result.get("data")
            or result.get("output")
        )

    elif isinstance(result, str):
        image_data = result

    if isinstance(image_data, list) and image_data:
        image_data = image_data[0]

    if not image_data:
        raise RuntimeError(
            "Cloudflare did not return an image."
        )

    if isinstance(image_data, str):
        if image_data.startswith("data:image"):
            image_data = image_data.split(",", 1)[1]

        return base64.b64decode(image_data)

    raise RuntimeError("Unsupported Cloudflare image response.")


# ============================================================
# 16. FINNHUB STOCK DATA
# ============================================================

def finnhub_quote(symbol):

    if not FINNHUB_KEY:
        raise RuntimeError(
            "FINNHUB_API_KEY is missing from Streamlit Secrets."
        )

    response = requests.get(
        "https://finnhub.io/api/v1/quote",
        params={
            "symbol": symbol.upper(),
            "token": FINNHUB_KEY
        },
        timeout=25
    )

    if response.status_code >= 400:
        raise RuntimeError(
            f"Finnhub quote error: {response.text[:250]}"
        )

    data = response.json()

    if not data or data.get("c") in (None, 0):
        raise RuntimeError(
            "Finnhub returned no quote. Check the symbol "
            "and your Finnhub API access."
        )

    return data


def finnhub_candles(symbol, days=30):

    if not FINNHUB_KEY:
        raise RuntimeError("Finnhub API key is missing.")

    end_time = int(time.time())
    start_time = int(
        (datetime.utcnow() - timedelta(days=days)).timestamp()
    )

    response = requests.get(
        "https://finnhub.io/api/v1/stock/candle",
        params={
            "symbol": symbol.upper(),
            "resolution": "D",
            "from": start_time,
            "to": end_time,
            "token": FINNHUB_KEY
        },
        timeout=30
    )

    if response.status_code >= 400:
        raise RuntimeError(
            f"Finnhub chart error: {response.text[:250]}"
        )

    data = response.json()

    if data.get("s") != "ok":
        raise RuntimeError(
            "Historical candles are unavailable for this symbol "
            "or API plan."
        )

    return data


def calculate_stock_summary(quote):

    current = float(quote.get("c", 0))
    previous = float(quote.get("pc", 0))
    change = float(quote.get("d", 0))
    percent = float(quote.get("dp", 0))

    direction = (
        "up"
        if change > 0
        else "down"
        if change < 0
        else "unchanged"
    )

    return {
        "current": current,
        "previous": previous,
        "change": change,
        "percent": percent,
        "direction": direction
    }


# ============================================================
# 17. CREATIONS DATABASE
# ============================================================

def save_creation(title, category, content):

    try:
        with db_connect() as con:
            con.execute("""
                INSERT INTO creations
                (user_id, title, category, content)
                VALUES (?, ?, ?, ?)
            """, (
                st.session_state.user_id,
                title,
                category,
                str(content)
            ))
            con.commit()

        return True

    except sqlite3.Error:
        return False


def get_creations():

    try:
        with db_connect() as con:
            rows = con.execute("""
                SELECT *
                FROM creations
                WHERE user_id = ?
                ORDER BY id DESC
            """, (
                st.session_state.user_id,
            )).fetchall()

        return [dict(row) for row in rows]

    except sqlite3.Error:
        return []


# ============================================================
# 18. DOWNLOAD HELPER
# ============================================================

def make_zip_file(filename, content):

    memory_file = io.BytesIO()

    with zipfile.ZipFile(
        memory_file,
        "w",
        zipfile.ZIP_DEFLATED
    ) as zip_file:

        zip_file.writestr(filename, content)

    memory_file.seek(0)

    return memory_file.getvalue()


# ============================================================
# 19. PROFESSIONAL DESIGN
# ============================================================

st.markdown("""
<style>
html, body, [class*="css"] {
    color: #ffffff !important;
}

.stApp {
    background:
        radial-gradient(
            circle at 15% 5%,
            rgba(70, 65, 145, .20),
            transparent 30%
        ),
        linear-gradient(
            135deg,
            #0b1020 0%,
            #11172a 55%,
            #0b1020 100%
        );
    color: #ffffff !important;
}

p, span, label, li, h1, h2, h3, h4, h5, h6 {
    color: #ffffff !important;
}

[data-testid="stSidebar"] {
    background: #101629;
    border-right: 1px solid rgba(255,255,255,.08);
}

[data-testid="stSidebar"] * {
    color: #ffffff !important;
}

.stButton > button {
    border-radius: 10px;
    border: 1px solid rgba(255,255,255,.13);
    background: #222b45;
    color: #ffffff !important;
    min-height: 42px;
    transition: .2s ease;
}

.stButton > button:hover {
    background: #39476b;
    border-color: #7889bd;
    color: white !important;
}

.stTextInput input,
.stTextArea textarea,
.stSelectbox div[data-baseweb="select"] {
    color: #ffffff !important;
    background: #151e33 !important;
}

.stTextInput input::placeholder,
.stTextArea textarea::placeholder {
    color: #aeb8cb !important;
}

[data-testid="stChatMessage"] {
    background: rgba(24,32,52,.85);
    border: 1px solid rgba(255,255,255,.08);
    border-radius: 15px;
}

[data-testid="stChatMessage"] p,
[data-testid="stChatMessage"] li,
[data-testid="stChatMessage"] span {
    color: #ffffff !important;
}

.stMetric {
    background: rgba(24,32,52,.75);
    border: 1px solid rgba(255,255,255,.08);
    border-radius: 14px;
    padding: 15px;
}

.stMetric label,
.stMetric [data-testid="stMetricValue"],
.stMetric [data-testid="stMetricDelta"] {
    color: white !important;
}

hr {
    border-color: rgba(255,255,255,.12);
}

[data-testid="stAlert"] {
    color: #ffffff !important;
}

footer {
    visibility: hidden;
}

#MainMenu {
    visibility: hidden;
}
</style>
""", unsafe_allow_html=True)


# ============================================================
# 20. COMMON UI HELPERS
# ============================================================

def set_page(page_name):
    st.session_state.page = page_name


def page_title(title, subtitle=None):
    st.title(title)

    if subtitle:
        st.caption(subtitle)


def answer_actions(text, key_prefix="answer"):

    col1, col2, col3 = st.columns([1, 1, 5])

    with col1:
        st.download_button(
            "↓ Download",
            data=text,
            file_name="nextgen_answer.txt",
            mime="text/plain",
            key=f"{key_prefix}_download"
        )

    with col2:
        if st.button(
            "Copy answer",
            key=f"{key_prefix}_copy"
        ):
            st.code(text)


def save_and_show_answer(title, category, content):

    st.markdown(content)

    answer_actions(
        content,
        key_prefix=str(uuid.uuid4())[:8]
    )

    if st.button(
        "＋ Save to My Creations",
        key="save_" + str(uuid.uuid4())[:8]
    ):
        if save_creation(title, category, content):
            st.success("Saved to My Creations.")


# ============================================================
# 21. AUTHENTICATION GATE
# ============================================================

if not st.session_state.authenticated:
    authentication_screen()
    st.stop()


# ============================================================
# 22. SIDEBAR
# ============================================================

PAGES = [
    ("⌂", "Dashboard"),
    ("✦", "AI Chat"),
    ("▥", "Stock Market"),
    ("▧", "Image Studio"),
    ("⚒", "Tool Center"),
    ("⌘", "App Builder"),
    ("◇", "Website Builder"),
    ("▤", "Learn & Explore"),
    ("▧", "PDF Assistant"),
    ("▣", "My Creations"),
    ("⚙", "Settings"),
    ("ⓘ", "About")
]

with st.sidebar:

    st.markdown("## ✦ NEXTGEN AI")
    st.caption("Your intelligent workspace")

    st.divider()

    st.markdown(
        f"**Welcome, {escape(st.session_state.user_name)}**"
    )

    if st.session_state.guest_mode:
        st.caption("Guest session")
    else:
        st.caption(st.session_state.user_email)

    st.divider()

    for symbol, page_name in PAGES:

        is_current = (
            st.session_state.page == page_name
        )

        if st.button(
            f"{symbol}  {page_name}",
            key="nav_" + page_name,
            use_container_width=True,
            type="primary" if is_current else "secondary"
        ):
            set_page(page_name)
            st.rerun()

    st.divider()

    st.caption("AI CHAT PROVIDERS")

    st.write(
        "OpenAI  " +
        ("● Connected" if OPENAI_KEY else "○ Not configured")
    )

    st.write(
        "Gemini  " +
        ("● Connected" if GEMINI_KEY else "○ Not configured")
    )

    st.write(
        "Groq  " +
        ("● Connected" if GROQ_KEY else "○ Not configured")
    )

    st.divider()

    if st.button(
        "↪ Logout",
        use_container_width=True
    ):
        logout()


# ============================================================
# 23. DASHBOARD
# ============================================================

page = st.session_state.page

if page == "Dashboard":

    st.markdown(
        """
        <div style="
            padding:34px 28px;
            border-radius:20px;
            border:1px solid rgba(255,255,255,.10);
            background:linear-gradient(
                120deg,
                rgba(36,48,82,.95),
                rgba(33,31,68,.95)
            );
        ">
            <div style="
                font-size:13px;
                letter-spacing:3px;
                color:#b8c4e8;
            ">INTELLIGENT WORKSPACE</div>

            <div style="
                font-size:42px;
                font-weight:800;
                color:white;
                margin-top:12px;
            ">NEXTGEN AI</div>

            <div style="
                font-size:16px;
                color:#e0e5f2;
                margin-top:10px;
            ">
                Think clearly. Create freely. Learn continuously.
            </div>
        </div>
        """,
        unsafe_allow_html=True
    )

    st.write("")

    c1, c2, c3 = st.columns(3)

    c1.metric("Workspace", "40,000+")
    c2.metric("AI Assistants", "3")
    c3.metric(
        "Account",
        "Guest" if st.session_state.guest_mode else "Registered"
    )

    st.subheader("Your workspace")

    dashboard_cards = [
        ("✦ AI Chat", "Ask questions, write, learn and solve problems."),
        ("▥ Stock Market", "Explore market data and understand price movements."),
        ("▧ Image Studio", "Create images and review your generated work."),
        ("⚒ Tool Center", "Useful tools for everyday tasks."),
        ("⌘ App Builder", "Generate starter code for app ideas."),
        ("◇ Website Builder", "Create website layouts and starter files."),
        ("▤ Learn & Explore", "Learn technology and new subjects."),
        ("▧ PDF Assistant", "Work with supported PDF documents.")
    ]

    for start in range(0, len(dashboard_cards), 2):

        cols = st.columns(2)

        for index, col in enumerate(cols):
            card_index = start + index

            if card_index >= len(dashboard_cards):
                continue

            title, description = dashboard_cards[card_index]

            with col:
                with st.container(border=True):
                    st.markdown(f"### {title}")
                    st.write(description)

                    destination = title.split(" ", 1)[1]

                    if st.button(
                        "Open",
                        key="dashboard_" + destination,
                        use_container_width=True
                    ):
                        set_page(destination)
                        st.rerun()


# ============================================================
# 24. AI CHAT
# ============================================================

elif page == "AI Chat":

    page_title(
        "✦ AI Chat",
        "Ask questions, explore ideas and work with your AI assistant."
    )

    chats = get_user_chats()

    top1, top2, top3 = st.columns([1, 1, 3])

    with top1:
        if st.button("＋ New Chat", use_container_width=True):
            create_new_chat()
            st.rerun()

    with top2:
        if st.button("Clear Chat", use_container_width=True):
            delete_current_chat()
            st.rerun()

    with top3:
        st.toggle(
            "Smart Web Search",
            key="web_search_enabled"
        )

    if chats:

        selected_chat = st.selectbox(
            "Chat history",
            options=[item["id"] for item in chats],
            format_func=lambda chat_id: next(
                (
                    item["title"]
                    for item in chats
                    if item["id"] == chat_id
                ),
                "Chat"
            ),
            index=next(
                (
                    index
                    for index, item in enumerate(chats)
                    if item["id"] == st.session_state.chat_id
                ),
                0
            )
        )

        if selected_chat != st.session_state.chat_id:
            st.session_state.chat_id = selected_chat
            st.session_state.messages = get_messages(
                selected_chat
            )
            st.rerun()

    if not st.session_state.chat_id:
        create_new_chat()

    if not st.session_state.messages:
        st.session_state.messages = get_messages(
            st.session_state.chat_id
        )

    for index, message in enumerate(
        st.session_state.messages
    ):

        with st.chat_message(message["role"]):
            st.markdown(message["content"])

            if message["role"] == "assistant":
                answer_actions(
                    message["content"],
                    key_prefix=f"chat_answer_{index}"
                )

    prompt = st.chat_input(
        "Message NEXTGEN AI..."
    )

    if prompt:

        current_chat = st.session_state.chat_id

        user_message = {
            "role": "user",
            "content": prompt
        }

        st.session_state.messages.append(user_message)

        save_message(
            current_chat,
            "user",
            prompt
        )

        with st.chat_message("user"):
            st.markdown(prompt)

        with st.chat_message("assistant"):

            with st.spinner("Thinking..."):

                try:
                    answer = smart_ai_answer(
                        st.session_state.messages
                    )

                    st.markdown(answer)

                    assistant_message = {
                        "role": "assistant",
                        "content": answer
                    }

                    st.session_state.messages.append(
                        assistant_message
                    )

                    save_message(
                        current_chat,
                        "assistant",
                        answer
                    )

                    st.caption(
                        "Provider: "
                        + st.session_state.last_provider
                        + "  |  Search: "
                        + st.session_state.last_search
                    )

                except Exception as exc:
                    st.error(str(exc))


# ============================================================
# 25. STOCK MARKET
# ============================================================

elif page == "Stock Market":

    page_title(
        "▥ Stock Market",
        "Market information powered by your Finnhub API key."
    )

    if not FINNHUB_KEY:
        st.error(
            "FINNHUB_API_KEY is missing. "
            "Add it to Streamlit Secrets."
        )
        st.stop()

    st.caption(
        "Market data availability depends on your Finnhub plan "
        "and the exchange's data permissions."
    )

    symbol = st.text_input(
        "Stock symbol",
        value=st.session_state.stock_symbol,
        placeholder="Example: AAPL"
    ).strip().upper()

    period = st.selectbox(
        "Historical chart period",
        ["7 days", "30 days", "90 days", "180 days", "365 days"],
        index=1
    )

    period_days = {
        "7 days": 7,
        "30 days": 30,
        "90 days": 90,
        "180 days": 180,
        "365 days": 365
    }[period]

    if st.button(
        "Analyze Stock",
        use_container_width=True
    ):

        if not re.match(r"^[A-Z0-9.\-]{1,20}$", symbol):
            st.error("Enter a valid stock symbol.")
        else:
            try:
                with st.spinner("Loading Finnhub market data..."):

                    quote = finnhub_quote(symbol)
                    history = finnhub_candles(
                        symbol,
                        period_days
                    )

                    st.session_state.stock_symbol = symbol
                    st.session_state.stock_data = quote
                    st.session_state.stock_history = history

            except Exception as exc:
                st.error(str(exc))

    quote = st.session_state.stock_data
    history = st.session_state.stock_history

    if quote and history:

        summary = calculate_stock_summary(quote)

        st.divider()
        st.subheader(f"{st.session_state.stock_symbol} — Market Overview")

        m1, m2, m3, m4 = st.columns(4)

        m1.metric(
            "Current Price",
            f"{summary['current']:,.2f}"
        )

        m2.metric(
            "Previous Close",
            f"{summary['previous']:,.2f}"
        )

        m3.metric(
            "Change",
            f"{summary['change']:+,.2f}"
        )

        m4.metric(
            "Change %",
            f"{summary['percent']:+.2f}%"
        )

        st.subheader("Historical Price Chart")

        chart_data = {
            "Close": history["c"],
            "Open": history["o"],
            "High": history["h"],
            "Low": history["l"]
        }

        st.line_chart(
            chart_data,
            height=350
        )

        st.subheader("Chart Analysis")

        close_prices = history["c"]

        if len(close_prices) >= 2:

            first_price = close_prices[0]
            last_price = close_prices[-1]

            if first_price:
                total_change = (
                    (last_price - first_price)
                    / first_price
                ) * 100
            else:
                total_change = 0

            st.write(
                f"Change across selected chart period: "
                f"{total_change:+.2f}%"
            )

            if len(close_prices) >= 20:
                moving_average = (
                    sum(close_prices[-20:]) / 20
                )

                st.write(
                    f"20-session simple average: "
                    f"{moving_average:.2f}"
                )

                if last_price > moving_average:
                    st.info(
                        "The latest close is above the "
                        "20-session average."
                    )
                else:
                    st.info(
                        "The latest close is below the "
                        "20-session average."
                    )

        st.caption(
            "These are descriptive indicators, not a prediction "
            "or a recommendation to buy or sell."
        )

        st.divider()

        st.subheader("Learn Stock Market")

        lesson = st.selectbox(
            "Choose a lesson",
            [
                "Stock Market Basics",
                "Candlestick Charts",
                "Support and Resistance",
                "Moving Averages",
                "Risk and Diversification",
                "Volume and Volatility"
            ]
        )

        lessons = {
            "Stock Market Basics":
                "A stock represents a share in a company. "
                "Prices can rise or fall based on many factors.",

            "Candlestick Charts":
                "Candles show open, high, low and close prices "
                "for a selected time period.",

            "Support and Resistance":
                "Support and resistance are commonly studied "
                "price areas. They are not guaranteed turning points.",

            "Moving Averages":
                "A moving average smooths historical prices "
                "to help study broad trends.",

            "Risk and Diversification":
                "Diversification spreads exposure across different "
                "assets. It does not eliminate risk.",

            "Volume and Volatility":
                "Volume measures trading activity. Volatility "
                "describes how much prices fluctuate."
        }

        st.write(lessons[lesson])

    else:
        st.info(
            "Enter a stock symbol and select Analyze Stock "
            "to load Finnhub data."
        )

    st.warning(
        "Educational use only. This section does not provide "
        "personalized investment or trading advice."
    )


# ============================================================
# 26. IMAGE STUDIO
# ============================================================

elif page == "Image Studio":

    page_title(
        "▧ Image Studio",
        "Create images with Cloudflare and manage your image gallery."
    )

    st.subheader("Create an image")

    prompt = st.text_area(
        "Describe the image you want",
        placeholder=(
            "Example: A cinematic futuristic city at sunset, "
            "detailed architecture, atmospheric lighting..."
        ),
        height=120
    )

    style = st.selectbox(
        "Image style",
        [
            "Realistic",
            "Cinematic",
            "Digital Art",
            "Anime",
            "3D Render",
            "Fantasy",
            "Minimal",
            "Watercolor",
            "Portrait",
            "Architecture"
        ]
    )

    extra_detail = st.text_input(
        "Additional details (optional)"
    )

    final_prompt = (
        prompt.strip()
        + f". Style: {style}."
        + (
            f" Additional details: {extra_detail}"
            if extra_detail.strip()
            else ""
        )
    )

    if st.button(
        "✦ Generate Image",
        use_container_width=True
    ):

        if not prompt.strip():
            st.warning("Please enter an image prompt.")

        else:
            try:
                with st.spinner(
                    "Creating your image with Cloudflare..."
                ):

                    image_bytes = generate_cloudflare_image(
                        final_prompt
                    )

                    st.session_state.generated_image = image_bytes
                    st.session_state.generated_image_prompt = final_prompt
                    st.session_state.image_rating = None

            except Exception as exc:
                st.error(str(exc))

    if st.session_state.generated_image:

        st.divider()
        st.subheader("Generated Image")

        st.image(
            st.session_state.generated_image,
            use_container_width=True
        )

        st.download_button(
            "↓ Download Image",
            data=st.session_state.generated_image,
            file_name="nextgen_image.png",
            mime="image/png",
            use_container_width=True
        )

        st.write("**Review this image**")

        rating = st.select_slider(
            "Your rating",
            options=[
                "Not good",
                "Needs improvement",
                "Good",
                "Very good",
                "Excellent"
            ],
            value="Good"
        )

        if st.button("Submit Review"):
            st.session_state.image_rating = rating
            st.success("Thank you for your review.")

        if st.button("＋ Save Image Prompt"):
            save_creation(
                "Generated Image Prompt",
                "Image Studio",
                st.session_state.generated_image_prompt
            )
            st.success("Prompt saved.")

    st.divider()

    st.subheader("＋ Add images from your device")

    uploaded_images = st.file_uploader(
        "Choose images from your gallery",
        type=["png", "jpg", "jpeg", "webp"],
        accept_multiple_files=True
    )

    if uploaded_images:

        st.write(
            f"{len(uploaded_images)} image(s) selected."
        )

        cols = st.columns(3)

        for index, uploaded in enumerate(uploaded_images):
            with cols[index % 3]:
                st.image(
                    uploaded,
                    caption=uploaded.name,
                    use_container_width=True
                )

                st.download_button(
                    "Download",
                    data=uploaded.getvalue(),
                    file_name=uploaded.name,
                    key=f"gallery_download_{index}"
                )


# ============================================================
# 27. TOOL CENTER
# ============================================================

elif page == "Tool Center":

    page_title(
        "⚒ Tool Center",
        "Simple tools for everyday work."
    )

    tool = st.selectbox(
        "Select a tool",
        [
            "Word Counter",
            "Text Case Converter",
            "Percentage Calculator",
            "Simple Calculator",
            "JSON Formatter",
            "Character Counter"
        ]
    )

    if tool == "Word Counter":

        text_value = st.text_area(
            "Enter text",
            height=180
        )

        words = len(text_value.split())
        characters = len(text_value)
        characters_no_spaces = len(
            text_value.replace(" ", "")
        )

        a, b, c = st.columns(3)

        a.metric("Words", words)
        b.metric("Characters", characters)
        c.metric("Without spaces", characters_no_spaces)

    elif tool == "Text Case Converter":

        text_value = st.text_area("Enter text")

        if st.button("UPPERCASE"):
            st.code(text_value.upper())

        if st.button("lowercase"):
            st.code(text_value.lower())

        if st.button("Title Case"):
            st.code(text_value.title())

        if st.button("Sentence Case"):
            st.code(text_value.capitalize())

    elif tool == "Percentage Calculator":

        number = st.number_input(
            "Enter number",
            value=100.0
        )

        percentage = st.number_input(
            "Percentage",
            value=10.0
        )

        if st.button("Calculate"):
            st.success(
                f"Result: {number * percentage / 100:.4f}"
            )

    elif tool == "Simple Calculator":

        first = st.number_input(
            "First number",
            value=0.0,
            key="calc_first"
        )

        operation = st.selectbox(
            "Operation",
            ["+", "-", "×", "÷"]
        )

        second = st.number_input(
            "Second number",
            value=0.0,
            key="calc_second"
        )

        if st.button("Calculate result"):

            if operation == "+":
                result = first + second

            elif operation == "-":
                result = first - second

            elif operation == "×":
                result = first * second

            else:
                result = (
                    first / second
                    if second != 0
                    else None
                )

            if result is None:
                st.error("Cannot divide by zero.")
            else:
                st.success(f"Result: {result}")

    elif tool == "JSON Formatter":

        raw_json = st.text_area(
            "Paste JSON",
            height=180
        )

        if st.button("Format JSON"):

            try:
                parsed = json.loads(raw_json)
                st.code(
                    json.dumps(
                        parsed,
                        indent=4,
                        ensure_ascii=False
                    ),
                    language="json"
                )

            except json.JSONDecodeError as exc:
                st.error(f"Invalid JSON: {exc}")

    elif tool == "Character Counter":

        text_value = st.text_area("Enter text")

        st.metric(
            "Characters",
            len(text_value)
        )


# ============================================================
# 28. APP BUILDER
# ============================================================

elif page == "App Builder":

    page_title(
        "⌘ App Builder",
        "Turn an idea into a starter application."
    )

    app_name = st.text_input(
        "Application name",
        value="My Next App"
    )

    app_description = st.text_area(
        "Describe your application",
        placeholder=(
            "Explain what the app should do, "
            "who will use it and its main features."
        ),
        height=140
    )

    app_platform = st.selectbox(
        "Platform",
        [
            "Python Streamlit",
            "HTML CSS JavaScript",
            "React Starter",
            "Python Desktop Starter"
        ]
    )

    if st.button(
        "Generate App Starter",
        use_container_width=True
    ):

        if not app_description.strip():
            st.warning("Describe your app idea first.")

        else:

            request_messages = [
                {
                    "role": "user",
                    "content": f"""
Create a practical starter project.

Application name: {app_name}
Platform: {app_platform}
Description: {app_description}

Return:
1. Project overview.
2. Folder structure.
3. Main starter code.
4. Setup instructions.
5. Important limitations.

Do not claim the project has been tested.
"""
                }
            ]

            try:
                with st.spinner("Building your starter project..."):
                    result = ask_ai(request_messages)

                st.session_state.generated_project = result

                save_creation(
                    app_name,
                    "App Builder",
                    result
                )

            except Exception as exc:
                st.error(str(exc))

    if st.session_state.generated_project:

        st.subheader("Generated App Plan")

        st.markdown(
            st.session_state.generated_project
        )

        st.download_button(
            "↓ Download project notes",
            data=st.session_state.generated_project,
            file_name="app_project_notes.md",
            mime="text/markdown"
        )


# ============================================================
# 29. WEBSITE BUILDER
# ============================================================

elif page == "Website Builder":

    page_title(
        "◇ Website Builder",
        "Generate a website starter with AI."
    )

    website_name = st.text_input(
        "Website name",
        value="My Website"
    )

    website_type = st.selectbox(
        "Website type",
        [
            "Portfolio",
            "Business Website",
            "Landing Page",
            "Blog",
            "Educational Website",
            "Online Store Layout"
        ]
    )

    website_description = st.text_area(
        "Describe your website",
        height=130
    )

    if st.button(
        "Generate Website",
        use_container_width=True
    ):

        if not website_description.strip():
            st.warning("Enter a website description.")

        else:

            request_messages = [
                {
                    "role": "user",
                    "content": f"""
Create a complete responsive starter website.

Name: {website_name}
Type: {website_type}
Description: {website_description}

Return:
- HTML
- CSS
- JavaScript if needed
- File names
- Setup instructions

Keep code in clearly labeled code blocks.
"""
                }
            ]

            try:
                with st.spinner("Creating website starter..."):
                    result = ask_ai(request_messages)

                st.session_state.generated_website = result

                save_creation(
                    website_name,
                    "Website Builder",
                    result
                )

            except Exception as exc:
                st.error(str(exc))

    if st.session_state.generated_website:

        st.subheader("Website Starter")

        st.markdown(
            st.session_state.generated_website
        )

        st.download_button(
            "↓ Download website notes",
            data=st.session_state.generated_website,
            file_name="website_starter.md",
            mime="text/markdown"
        )


# ============================================================
# 30. LEARN & EXPLORE
# ============================================================

elif page == "Learn & Explore":

    page_title(
        "▤ Learn & Explore",
        "Learn concepts with clear explanations and examples."
    )

    topic = st.text_input(
        "What would you like to learn?",
        placeholder="Example: Python loops"
    )

    level = st.selectbox(
        "Learning level",
        [
            "Beginner",
            "Intermediate",
            "Advanced"
        ]
    )

    if st.button(
        "Start Learning",
        use_container_width=True
    ):

        if not topic.strip():
            st.warning("Enter a topic first.")

        else:

            messages = [
                {
                    "role": "user",
                    "content": f"""
Teach me about: {topic}
Level: {level}

Explain in a structured way:
1. Simple definition.
2. Detailed explanation.
3. Examples.
4. Common mistakes.
5. Short revision notes.
6. Five practice questions.
"""
                }
            ]

            try:
                with st.spinner("Preparing your lesson..."):
                    answer = ask_ai(messages)

                st.markdown(answer)

                save_creation(
                    topic,
                    "Learning",
                    answer
                )

            except Exception as exc:
                st.error(str(exc))


# ============================================================
# 31. PDF ASSISTANT
# ============================================================

elif page == "PDF Assistant":

    page_title(
        "▧ PDF Assistant",
        "Upload a PDF and ask questions about its text."
    )

    uploaded_pdf = st.file_uploader(
        "Choose a PDF file",
        type=["pdf"]
    )

    pdf_text = ""

    if uploaded_pdf:

        try:
            from pypdf import PdfReader

            reader = PdfReader(uploaded_pdf)

            pages = []

            for pdf_page in reader.pages:
                pages.append(
                    pdf_page.extract_text() or ""
                )

            pdf_text = "\n\n".join(pages)

            st.success(
                f"PDF loaded: {len(reader.pages)} pages"
            )

            st.text_area(
                "Extracted text preview",
                pdf_text[:5000],
                height=180
            )

        except ImportError:
            st.error(
                "PDF reading requires the optional pypdf package. "
                "You can still use the AI Chat with copied text."
            )

        except Exception as exc:
            st.error(f"Could not read PDF: {exc}")

    question = st.text_input(
        "Ask something about the PDF"
    )

    if st.button("Ask PDF Assistant"):

        if not pdf_text:
            st.warning("Upload a readable PDF first.")

        elif not question.strip():
            st.warning("Enter your question.")

        else:

            messages = [
                {
                    "role": "user",
                    "content": (
                        "Answer using the following PDF text. "
                        "If the answer is not present, say so.\n\n"
                        "PDF TEXT:\n"
                        + pdf_text[:25000]
                        + "\n\nQUESTION:\n"
                        + question
                    )
                }
            ]

            try:
                with st.spinner("Reading and answering..."):
                    answer = ask_ai(messages)

                st.markdown(answer)

                save_creation(
                    "PDF: " + question[:40],
                    "PDF Assistant",
                    answer
                )

            except Exception as exc:
                st.error(str(exc))


# ============================================================
# 32. MY CREATIONS
# ============================================================

elif page == "My Creations":

    page_title(
        "▣ My Creations",
        "Your saved AI outputs and project notes."
    )

    creations = get_creations()

    if not creations:
        st.info("Your saved creations will appear here.")

    else:

        for item in creations:

            with st.expander(
                f"{item['title']} — {item['category']}"
            ):

                st.caption(item["created_at"])
                st.markdown(item["content"])

                st.download_button(
                    "Download",
                    data=item["content"],
                    file_name="creation.txt",
                    key=f"creation_{item['id']}"
                )


# ============================================================
# 33. SETTINGS
# ============================================================

elif page == "Settings":

    page_title(
        "⚙ Settings",
        "Application preferences and connection status."
    )

    st.subheader("AI Providers")

    provider_status = [
        ("OpenAI", OPENAI_KEY, OPENAI_MODEL),
        ("Gemini", GEMINI_KEY, GEMINI_MODEL),
        ("Groq", GROQ_KEY, GROQ_MODEL)
    ]

    for provider, key, model in provider_status:

        if key:
            st.success(
                f"{provider}: Configured — {model}"
            )
        else:
            st.warning(
                f"{provider}: API key not configured"
            )

    st.divider()

    st.subheader("Image Generation")

    if CF_API_TOKEN and CF_ACCOUNT_ID:
        st.success(
            "Cloudflare Image Generation: Configured"
        )
    else:
        st.warning(
            "Cloudflare credentials are not configured."
        )

    st.write("Image model:", CF_IMAGE_MODEL)

    st.divider()

    st.subheader("Stock Market")

    if FINNHUB_KEY:
        st.success("Finnhub API: Configured")
    else:
        st.warning("Finnhub API: Not configured")

    st.divider()

    st.subheader("Web Search")

    if TAVILY_KEY:
        st.success("Tavily Search: Configured")
    else:
        st.info(
            "Tavily is optional. OpenAI Web Search may be used "
            "when supported by your API access."
        )

    st.divider()

    st.subheader("Current Session")

    st.write(
        "Account type:",
        "Guest" if st.session_state.guest_mode else "Registered"
    )

    st.write(
        "AI provider used:",
        st.session_state.last_provider
    )

    st.write(
        "Last search status:",
        st.session_state.last_search
    )

    st.caption(
        "API keys are not displayed in this settings page."
    )


# ============================================================
# 34. ABOUT
# ============================================================

elif page == "About":

    page_title(
        "ⓘ About NEXTGEN AI",
        "An AI-powered workspace for learning, creating and exploring."
    )

    st.markdown("""
    ## NEXTGEN AI

    NEXTGEN AI brings multiple useful tools into one workspace.

    ### AI Chat
    - OpenAI
    - Gemini
    - Groq
    - Smart web search when configured

    ### Image Studio
    - Cloudflare image generation
    - Prompt and style selection
    - Gallery uploads
    - Image preview and download
    - Image review

    ### Stock Market
    - Finnhub market data
    - Quote overview
    - Historical chart data when available
    - Basic descriptive indicators
    - Stock market learning section

    ### Productivity
    - Tool Center
    - App Builder
    - Website Builder
    - Learn & Explore
    - PDF Assistant
    - My Creations

    ### Accounts
    - Sign Up
    - Login
    - Continue as Guest
    - Separate chat histories
    """)

    st.divider()

    st.caption(
        "NEXTGEN AI — Built for learning, creativity and productivity."
    )


# ============================================================
# 35. FALLBACK PAGE
# ============================================================

else:

    st.warning("Page not found.")

    if st.button("Return to Dashboard"):
        set_page("Dashboard")
        st.rerun()


# ============================================================
# 36. GLOBAL FOOTER
# ============================================================

st.divider()

st.markdown(
    """
    <div style="
        text-align:center;
        padding:12px;
        color:#c5ccdc;
        font-size:12px;
    ">
        ✦ NEXTGEN AI
        <br>
        Learn • Create • Explore
    </div>
    """,
    unsafe_allow_html=True
)
