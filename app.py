import os
import io
import time
import json
import requests
import streamlit as st
import streamlit.components.v1 as components

from dotenv import load_dotenv
from google import genai
from google.genai import types
from PIL import Image
from pypdf import PdfReader

try:
    from streamlit_mic_recorder import speech_to_text
except Exception:
    speech_to_text = None

try:
    from voice_call import create_live_token
except Exception:
    create_live_token = None

load_dotenv()

st.set_page_config(
    page_title="NEXTGEN AI",
    page_icon="✦",
    layout="wide",
    initial_sidebar_state="expanded",
)

API_KEY = ""
try:
    API_KEY = st.secrets.get("GEMINI_API_KEY", "")
except Exception:
    pass

if not API_KEY:
    API_KEY = os.getenv("GEMINI_API_KEY", "")

MODEL = os.getenv("GEMINI_MODEL", "gemini-3.5-flash-lite")

SYSTEM_INSTRUCTION = """
You are NEXTGEN AI, an independent AI platform created and developed by Arav.
Google Gemini may provide the underlying AI model, but NEXTGEN AI is the platform
created and owned by Arav.

Be helpful, accurate, respectful, and clear. Respond in the language used by
the user. Explain difficult topics in a student-friendly way when appropriate.

CURRENT INFORMATION RULE:
For questions about current or recent facts (including current office holders,
government positions, prices, news, events, policies, and sports results), use
Google Search when it is enabled. Prefer recent official sources for government
and public information. Check the date and distinguish current office holders
from former office holders. Never invent a search result or claim that you
searched if search was not enabled or did not work. If live search is unavailable,
clearly say that your information may be outdated.

IDENTITY:
If asked who created NEXTGEN AI, say that Arav created and developed the
NEXTGEN AI platform. Do not claim that Arav created the underlying Gemini model.
"""

st.markdown(
    """
    <style>
    :root {
        --ink: #171923;
        --muted: #687080;
        --line: #e8eaf0;
        --soft: #f7f8fb;
        --accent: #5b5ce2;
        --accent2: #7778f5;
    }
    .stApp {
        background: #ffffff;
        color: var(--ink);
    }
    [data-testid="stHeader"] {
        background: rgba(255,255,255,0.92);
    }
    [data-testid="stSidebar"] {
        background: #fbfbfd;
        border-right: 1px solid var(--line);
    }
    [data-testid="stSidebar"] * {
        color: #252938;
    }
    h1, h2, h3, h4, p, label, .stMarkdown {
        color: var(--ink);
    }
    h1 { letter-spacing: -1.2px; font-weight: 750; }
    .brand-mark {
        display: flex; align-items: center; gap: 10px;
        font-size: 22px; font-weight: 800; letter-spacing: -0.7px;
        padding: 5px 0 2px 0;
    }
    .brand-icon {
        display: inline-flex; align-items: center; justify-content: center;
        width: 38px; height: 38px; border-radius: 13px;
        color: white; font-size: 20px;
        background: linear-gradient(135deg, #5b5ce2, #8989ff);
        box-shadow: 0 6px 18px rgba(91,92,226,.18);
    }
    .hero {
        padding: 34px 36px; border: 1px solid #e9e9f7;
        border-radius: 24px;
        background: radial-gradient(circle at 90% 10%, #eeedff 0, transparent 32%),
                    linear-gradient(135deg, #ffffff, #f8f8ff);
        margin: 8px 0 22px 0;
    }
    .hero-kicker {
        color: #5b5ce2; font-size: 12px; font-weight: 800;
        letter-spacing: 1.5px; text-transform: uppercase;
    }
    .hero h1 { font-size: clamp(32px, 5vw, 48px); margin: 8px 0; }
    .hero p { color: #697084; font-size: 16px; margin-bottom: 0; }
    .feature-card {
        border: 1px solid var(--line); border-radius: 17px;
        padding: 18px; background: white; min-height: 128px;
        box-shadow: 0 3px 14px rgba(25,30,60,.035);
    }
    .feature-icon { font-size: 23px; margin-bottom: 8px; }
    .feature-title { font-weight: 750; color: #202333; }
    .feature-desc { color: #747b8c; font-size: 13px; margin-top: 4px; }
    .small-muted { color: #7a8190; font-size: 13px; }
    .stButton > button {
        border-radius: 11px; border: 1px solid #e3e5ee;
        background: #ffffff; color: #222638; font-weight: 650;
        min-height: 42px; transition: all .15s ease;
    }
    .stButton > button:hover {
        border-color: #7778f5; color: #5556d8;
        background: #f8f8ff;
    }
    .stButton > button[kind="primary"] {
        background: linear-gradient(135deg, #5b5ce2, #7778f5);
        color: white; border: 0;
    }
    [data-testid="stChatMessage"] {
        background: #ffffff; border: 1px solid #eceef4;
        border-radius: 16px; padding: 12px 14px;
        box-shadow: 0 2px 10px rgba(20,25,50,.025);
    }
    [data-testid="stChatInput"] {
        border-radius: 16px;
    }
    .footer {
        text-align: center; color: #9298a6; font-size: 12px;
        border-top: 1px solid #eef0f4; padding: 22px 0 8px 0;
        margin-top: 35px;
    }
    div[data-testid="stMetric"] {
        background: #fff; border: 1px solid #eceef4;
        padding: 14px; border-radius: 15px;
    }
    </style>
    """,
    unsafe_allow_html=True,
)

defaults = {
    "messages": [],
    "client": None,
    "last_provider": "Not used yet",
    "live_token": None,
    "last_image_bytes": None,
}

for key, value in defaults.items():
    if key not in st.session_state:
        st.session_state[key] = value


def get_client():
    if not API_KEY:
        raise ValueError(
            "GEMINI_API_KEY नहीं मिली। Streamlit Secrets में API key जोड़ें।"
        )

    if st.session_state.client is None:
        st.session_state.client = genai.Client(
            api_key=API_KEY,
            http_options=types.HttpOptions(timeout=60000),
        )

    return st.session_state.client


def generate_answer(contents, use_web=False, extra_instruction=None):
    client = get_client()

    system_text = SYSTEM_INSTRUCTION
    if extra_instruction:
        system_text += "\n\nTASK MODE:\n" + extra_instruction

    config = {
        "system_instruction": system_text,
        "max_output_tokens": 4096,
        "temperature": 0.65,
    }

    if use_web:
        config["tools"] = [
            types.Tool(google_search=types.GoogleSearch())
        ]

    response = client.models.generate_content(
        model=MODEL,
        contents=contents,
        config=types.GenerateContentConfig(**config),
    )

    answer = getattr(response, "text", None)
    if not answer:
        raise ValueError("AI ने खाली जवाब दिया। कृपया दोबारा कोशिश करें।")

    sources = []

    if use_web and getattr(response, "candidates", None):
        metadata = getattr(
            response.candidates[0],
            "grounding_metadata",
            None,
        )

        chunks = getattr(metadata, "grounding_chunks", []) or []
        seen = set()

        for chunk in chunks:
            web_source = getattr(chunk, "web", None)

            if web_source:
                uri = getattr(web_source, "uri", None)
                title = getattr(web_source, "title", None) or uri

                if uri and uri not in seen:
                    seen.add(uri)
                    sources.append(f"- [{title}]({uri})")

    if sources:
        answer += "\n\n**Sources checked:**\n" + "\n".join(sources)

    st.session_state.last_provider = (
        "Gemini + Google Search" if use_web else "Gemini"
    )

    return answer


def show_voice_player(text):
    safe_text = json.dumps(text, ensure_ascii=False)

    html = f"""
    <div style="font-family:Arial;display:flex;gap:8px;align-items:center">
      <button onclick="speakText()" style="border:1px solid #ddd;border-radius:9px;padding:8px 12px;background:white">▶ Listen</button>
      <button onclick="speechSynthesis.pause()" style="border:1px solid #ddd;border-radius:9px;padding:8px 12px;background:white">Ⅱ Pause</button>
      <button onclick="speechSynthesis.cancel()" style="border:1px solid #ddd;border-radius:9px;padding:8px 12px;background:white">■ Stop</button>
    </div>
    <script>
      const textToSpeak = {safe_text};

      function speakText() {{
        speechSynthesis.cancel();
        const u = new SpeechSynthesisUtterance(textToSpeak);
        u.lang = /[\\u0900-\\u097F]/.test(textToSpeak) ? "hi-IN" : "en-IN";
        speechSynthesis.speak(u);
      }}
    </script>
    """

    components.html(html, height=48)


with st.sidebar:
    st.markdown(
        '<div class="brand-mark"><span class="brand-icon">✦</span> NEXTGEN AI</div>',
        unsafe_allow_html=True,
    )

    st.caption("YOUR INTELLIGENT WORKSPACE")
    st.divider()

    page = st.radio(
        "WORKSPACE",
        [
            "Home",
            "AI Chat",
            "AI Vision",
            "PDF Assistant",
            "AI Image",
            "AI Video",
            "Study Assistant",
            "Text Tools",
            "About",
        ],
        label_visibility="visible",
    )

    st.divider()
    st.caption("SYSTEM STATUS")

    if API_KEY:
        st.success("Gemini API configured")
    else:
        st.error("Gemini API key missing")

    st.caption(f"Model: {MODEL}")
    st.caption(f"Last engine: {st.session_state.last_provider}")

    if st.button("Clear chat history", use_container_width=True):
        st.session_state.messages = []
        st.rerun()


if page == "Home":
    st.markdown(
        """
        <div class="hero">
          <div class="hero-kicker">One platform · Endless possibilities</div>
          <h1>Meet your new AI workspace.</h1>
          <p>Think, learn, create and explore — all in one place with NEXTGEN AI.</p>
        </div>
        """,
        unsafe_allow_html=True,
    )

    c1, c2, c3 = st.columns(3)
    c1.metric("Chat messages", len(st.session_state.messages))
    c2.metric("AI workspaces", "8")
    c3.metric("Platform", "Ready" if API_KEY else "Setup needed")

    st.subheader("Explore NEXTGEN AI")

    features = [
        ("💬", "AI Chat", "Ask questions and brainstorm ideas."),
        ("🌐", "Live Web Search", "Check current information with web grounding."),
        ("👁️", "AI Vision", "Upload an image and ask questions."),
        ("📄", "PDF Assistant", "Read documents and ask about their content."),
        ("🎨", "AI Image", "Create images from text prompts."),
        ("🎙️", "Voice", "Use microphone input and listen to answers."),
        ("📚", "Study Assistant", "Understand topics and practice concepts."),
        ("🛠️", "Text Tools", "Summarize, rewrite and translate text."),
    ]

    cols = st.columns(4)

    for i, (emoji, title, desc) in enumerate(features):
        with cols[i % 4]:
            st.markdown(
                f'<div class="feature-card"><div class="feature-icon">{emoji}</div>'
                f'<div class="feature-title">{title}</div>'
                f'<div class="feature-desc">{desc}</div></div>',
                unsafe_allow_html=True,
            )

    st.info(
        "Tip: AI answers about current events should use the Live Web Search option "
        "inside AI Chat. Always verify important information from official sources."
    )
