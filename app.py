import os
import io
import json
import base64
import sqlite3
import requests
import streamlit as st
from datetime import datetime

# =========================================================
# NEXTGEN AI — VERSION MAX (original dark purple/blue design)
# =========================================================
st.set_page_config(page_title="NEXTGEN AI MAX", page_icon="✦", layout="wide", initial_sidebar_state="expanded")
DB_PATH = "nextgen_max.db"

# ------------------------- API CONFIG --------------------
def secret(key, default=""):
    try:
        value = st.secrets.get(key)
        if value:
            return str(value)
    except Exception:
        pass
    return os.getenv(key, default)

XAI_API_KEY = secret("XAI_API_KEY")
OPENAI_API_KEY = secret("OPENAI_API_KEY")
GEMINI_API_KEY = secret("GEMINI_API_KEY")
TAVILY_API_KEY = secret("TAVILY_API_KEY")
CF_ACCOUNT_ID = secret("CLOUDFLARE_ACCOUNT_ID")
CF_API_TOKEN = secret("CLOUDFLARE_API_TOKEN")
XAI_MODEL = secret("XAI_MODEL", "grok-4.7")
OPENAI_MODEL = secret("OPENAI_MODEL", "gpt-5-mini")
GEMINI_MODEL = secret("GEMINI_MODEL", "gemini-3.5-flash")
IMAGE_MODEL = secret("CLOUDFLARE_IMAGE_MODEL", "@cf/black-forest-labs/flux-1-schnell")
GEMINI_IMAGE_MODEL = secret("GEMINI_IMAGE_MODEL", "gemini-3.1-flash-image")

# ------------------------- DATABASE ----------------------
def db():
    conn = sqlite3.connect(DB_PATH, timeout=20)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    with db() as con:
        con.execute("CREATE TABLE IF NOT EXISTS chats(id INTEGER PRIMARY KEY AUTOINCREMENT,title TEXT,created TEXT)")
        con.execute("CREATE TABLE IF NOT EXISTS messages(id INTEGER PRIMARY KEY AUTOINCREMENT,chat_id INTEGER,role TEXT,content TEXT,created TEXT)")
        con.execute("CREATE TABLE IF NOT EXISTS creations(id INTEGER PRIMARY KEY AUTOINCREMENT,kind TEXT,content TEXT,created TEXT)")

def create_chat():
    with db() as con:
        cur = con.execute("INSERT INTO chats(title,created) VALUES(?,?)", ("New Chat", datetime.now().isoformat(timespec="seconds")))
        return cur.lastrowid

def get_chats():
    with db() as con:
        return con.execute("SELECT * FROM chats ORDER BY id DESC").fetchall()

def get_messages(chat_id):
    with db() as con:
        return con.execute("SELECT * FROM messages WHERE chat_id=? ORDER BY id", (chat_id,)).fetchall()

def save_message(chat_id, role, content):
    with db() as con:
        con.execute("INSERT INTO messages(chat_id,role,content,created) VALUES(?,?,?,?)", (chat_id, role, content, datetime.now().isoformat(timespec="seconds")))

def update_message(message_id, content):
    with db() as con:
        con.execute("UPDATE messages SET content=?, created=? WHERE id=?", (content, datetime.now().isoformat(timespec="seconds"), message_id))

def update_title(chat_id, title):
    with db() as con:
        con.execute("UPDATE chats SET title=? WHERE id=? AND title='New Chat'", (title[:45], chat_id))

def delete_chat(chat_id):
    with db() as con:
        con.execute("DELETE FROM messages WHERE chat_id=?", (chat_id,))
        con.execute("DELETE FROM chats WHERE id=?", (chat_id,))

def save_creation(kind, content):
    with db() as con:
        con.execute("INSERT INTO creations(kind,content,created) VALUES(?,?,?)", (kind, content, datetime.now().isoformat(timespec="seconds")))

def get_creations():
    with db() as con:
        return con.execute("SELECT * FROM creations ORDER BY id DESC").fetchall()

init_db()

# ------------------------- TOOL LIBRARY ------------------
TOOL_LIBRARY = {
    "Writing & Documents": ["Email Writer", "Essay Writer", "Article Writer", "Blog Writer", "Letter Writer", "Report Writer", "Paragraph Writer", "Grammar Checker", "Proofreader", "Text Rewriter"],
    "Study & Education": ["MCQ Generator", "Quiz Generator", "Flashcard Creator", "Study Notes", "Chapter Explainer", "Homework Helper", "Revision Planner", "Question Answer Generator", "Practice Test", "Study Guide"],
    "Coding & Development": ["Code Generator", "Code Debugger", "Code Explainer", "Python Assistant", "HTML Generator", "CSS Generator", "JavaScript Assistant", "SQL Assistant", "Regex Helper", "Code Reviewer"],
    "YouTube & Content Creator": ["Video Script Writer", "YouTube Description", "Title Generator", "Hashtag Generator", "Video Ideas", "Shorts Ideas", "Thumbnail Concept", "Storyboard Creator", "Channel Bio", "Content Planner"],
    "Business & Marketing": ["Business Plan", "Marketing Strategy", "Brand Name", "Product Description", "Ad Copy Writer", "Slogan Generator", "SWOT Analysis", "Customer Persona", "Market Research", "Business Ideas"],
    "Language & Translation": ["Hindi to English", "English to Hindi", "Text Translator", "Vocabulary Builder", "Sentence Correction", "Pronunciation Guide", "Language Practice", "Synonym Finder", "Antonym Finder", "Grammar Tutor"],
    "Productivity & Planning": ["Study Timetable", "Daily Planner", "Task Planner", "Goal Planner", "Habit Tracker Ideas", "Time Manager", "Weekly Planner", "Project Planner", "Priority Organizer", "Routine Builder"],
    "Creative & Design": ["Image Prompt Generator", "Logo Ideas", "Poster Concept", "Banner Concept", "Color Palette Ideas", "Creative Writing", "Story Generator", "Poem Writer", "Character Creator", "Design Brief"],
    "Everyday Assistant": ["General Assistant", "Decision Helper", "Message Writer", "Shopping List", "Travel Planner", "Recipe Ideas", "Event Planner", "Explanation Assistant", "Daily Advice", "Information Organizer"],
    "Career & Skills": ["Resume Writer", "Interview Practice", "Cover Letter", "Skill Roadmap", "Career Exploration", "Portfolio Ideas", "Communication Practice", "Learning Plan", "Professional Bio", "Presentation Practice"],
    "Data & Analysis": ["Data Explainer", "Table Analyzer", "Data Summary", "Trend Explanation", "Chart Suggestions", "Spreadsheet Helper", "Data Cleaning Ideas", "Report Analysis", "Comparison Tool", "Statistics Tutor"],
    "Research & Thinking": ["Research Assistant", "Research Question Generator", "Topic Explorer", "Critical Thinking", "Argument Builder", "Pros and Cons", "Fact Explanation", "Idea Organizer", "Concept Comparison", "Problem Solver"],
    "Advanced Study Tools": ["Maths Step Solver", "Science Explainer", "Physics Tutor", "Chemistry Tutor", "Biology Tutor", "History Explainer", "Geography Tutor", "Exam Practice", "Concept Revision", "Doubt Solver"],
    "AI Creator Studio": ["AI Image Prompt", "AI Video Prompt", "Scene Generator", "Voiceover Script", "Character Prompt", "Animation Concept", "Cinematic Prompt", "Music Concept", "Visual Storytelling", "Creative Direction"],
    "Web & App Development": ["Website Planner", "App Idea Generator", "UI Content Writer", "Landing Page Copy", "Frontend Helper", "Backend Helper", "API Explainer", "Database Planner", "Website Debugger", "App Feature Planner"],
    "Smart AI Assistants": ["Personal AI Assistant", "Study Assistant", "Coding Assistant", "Writing Assistant", "Research Assistant", "Creative Assistant", "Planning Assistant", "Learning Assistant", "Business Assistant", "General AI Helper"],
    "Maths & Science Lab": ["Algebra Helper", "Geometry Explainer", "Equation Solver", "Unit Converter", "Physics Formula Guide", "Chemistry Formula Guide", "Scientific Concept Explainer", "Graph Explanation", "Numerical Practice", "Maths Quiz"],
    "Business Creator Tools": ["Startup Name Generator", "Business Proposal", "Product Ideas", "Pricing Strategy", "Brand Story", "Sales Pitch", "Business Presentation", "Customer Feedback Questions", "Business Checklist", "Growth Ideas"],
    "Learning & Knowledge": ["Topic Summarizer", "Text Summarizer", "Knowledge Guide", "Beginner Roadmap", "Quick Learning Notes", "Concept Map", "Question Generator", "Memory Techniques", "Revision Questions", "Explain Like Beginner"],
    "Presentation & Office": ["Presentation Outline", "Slide Content Writer", "Meeting Notes", "Agenda Creator", "Office Email", "Document Formatter", "Speech Writer", "Project Report", "Presentation Summary", "Professional Document"]
}
TOOL_COUNT = sum(len(v) for v in TOOL_LIBRARY.values())

SYSTEM_PROMPT = """You are NEXTGEN AI, created as a learning and technology project by Arav. Be accurate, clear, friendly and useful. Support Hindi (Devanagari) and English. Match the user's language. For school topics, explain step by step. Never invent facts, sources, tool actions or completed work. If uncertain, say so. Format answers neatly. Keep answer text readable in white/dark UI."""

# ------------------------- SMART WEB SEARCH ------------
def needs_web_search(text):
    """Conservative intent check: search only for freshness, sources or external facts."""
    q = (text or "").lower().strip()
    triggers = [
        "latest", "today", "right now", "currently", "current price", "live price", "news", "recent", "this week", "2026",
        "source", "sources", "citation", "research online", "search the web", "look up", "verify online", "website",
        "weather", "forecast", "near me", "nearby", "opening hours", "release date", "update", "stock price", "score today"
    ]
    return any(t in q for t in triggers)

def tavily_search(query):
    if not TAVILY_API_KEY:
        return ""
    r = requests.post("https://api.tavily.com/search", json={"api_key": TAVILY_API_KEY, "query": query, "search_depth": "basic", "max_results": 5, "include_answer": True}, timeout=9)
    r.raise_for_status()
    data = r.json()
    lines = []
    if data.get("answer"):
        lines.append("Search summary: " + data["answer"])
    for item in data.get("results", [])[:5]:
        lines.append(f"- {item.get('title','Source')}: {item.get('content','')[:700]} ({item.get('url','')})")
    return "\n".join(lines)

# ------------------------- PROVIDER REQUESTS -------------
def _openai_compatible_request(url, key, model, messages, timeout=14):
    payload = {"model": model, "messages": [{"role": "system", "content": SYSTEM_PROMPT}] + messages, "temperature": 0.55, "max_completion_tokens": 2500}
    r = requests.post(url, headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"}, json=payload, timeout=timeout)
    r.raise_for_status()
    data = r.json()
    content = data["choices"][0]["message"]["content"]
    if isinstance(content, list):
        content = "\n".join(x.get("text", "") for x in content if isinstance(x, dict))
    if not content:
        raise RuntimeError("Provider returned an empty answer")
    return content

def xai_request(messages):
    if not XAI_API_KEY: raise RuntimeError("XAI_API_KEY not configured")
    return _openai_compatible_request("https://api.x.ai/v1/chat/completions", XAI_API_KEY, XAI_MODEL, messages)

def openai_request(messages):
    if not OPENAI_API_KEY: raise RuntimeError("OPENAI_API_KEY not configured")
    return _openai_compatible_request("https://api.openai.com/v1/chat/completions", OPENAI_API_KEY, OPENAI_MODEL, messages)

def gemini_request(messages):
    if not GEMINI_API_KEY: raise RuntimeError("GEMINI_API_KEY not configured")
    contents = []
    for item in messages:
        role = "user" if item.get("role") == "user" else "model"
        contents.append({"role": role, "parts": [{"text": str(item.get("content", ""))}]})
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{GEMINI_MODEL}:generateContent?key={GEMINI_API_KEY}"
    r = requests.post(url, json={"systemInstruction": {"parts": [{"text": SYSTEM_PROMPT}]}, "contents": contents, "generationConfig": {"temperature": 0.55, "maxOutputTokens": 2500}}, timeout=14)
    r.raise_for_status()
    data = r.json()
    parts = data.get("candidates", [{}])[0].get("content", {}).get("parts", [])
    answer = "\n".join(p.get("text", "") for p in parts if p.get("text"))
    if not answer: raise RuntimeError("Gemini returned an empty answer")
    return answer

def ask_ai(messages, allow_search=True):
    messages = list(messages)
    search_note = ""
    last_user = next((m.get("content", "") for m in reversed(messages) if m.get("role") == "user"), "")
    if allow_search and needs_web_search(last_user) and TAVILY_API_KEY:
        try:
            results = tavily_search(last_user)
            if results:
                search_note = "\n\nUse these current web results where relevant. Cite the URLs in your answer and distinguish sourced facts from your own explanation:\n" + results
                for i in range(len(messages) - 1, -1, -1):
                    if messages[i].get("role") == "user":
                        messages[i] = {"role": "user", "content": messages[i].get("content", "") + search_note}
                        break
        except Exception:
            # Search is optional: a search outage must not block the AI response.
            pass
    errors = []
    providers = [("Grok", xai_request, XAI_API_KEY), ("OpenAI", openai_request, OPENAI_API_KEY), ("Gemini", gemini_request, GEMINI_API_KEY)]
    for name, fn, key in providers:
        if not key: continue
        try:
            return fn(messages), name
        except Exception as e:
            errors.append(f"{name}: {str(e)[:220]}")
    if not errors:
        raise RuntimeError("No AI keys configured. Add XAI_API_KEY, OPENAI_API_KEY and/or GEMINI_API_KEY in Streamlit Secrets.")
    raise RuntimeError("All configured AI providers failed. " + " | ".join(errors))

def run_tool(tool_name, details):
    prompt = f"Perform this task: {tool_name}\n\nUser instructions:\n{details}\n\nGive a useful, well-structured result."
    return ask_ai([{"role": "user", "content": prompt}], allow_search=True)[0]

# ------------------------- IMAGE GENERATION --------------
def cloudflare_image(prompt):
    if not CF_ACCOUNT_ID or not CF_API_TOKEN: raise RuntimeError("Cloudflare credentials missing")
    url = f"https://api.cloudflare.com/client/v4/accounts/{CF_ACCOUNT_ID}/ai/run/{IMAGE_MODEL}"
    r = requests.post(url, headers={"Authorization": f"Bearer {CF_API_TOKEN}"}, json={"prompt": prompt}, timeout=50)
    r.raise_for_status()
    data = r.json()
    image = data.get("result", {}).get("image")
    if image: return base64.b64decode(image)
    raise RuntimeError("Cloudflare did not return an image")

def gemini_image(prompt):
    if not GEMINI_API_KEY: raise RuntimeError("Gemini image backup key missing")
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{GEMINI_IMAGE_MODEL}:generateContent?key={GEMINI_API_KEY}"
    r = requests.post(url, json={"contents": [{"role": "user", "parts": [{"text": "Generate an image: " + prompt}]}], "generationConfig": {"responseModalities": ["IMAGE", "TEXT"]}}, timeout=60)
    r.raise_for_status()
    parts = r.json().get("candidates", [{}])[0].get("content", {}).get("parts", [])
    for part in parts:
        inline = part.get("inlineData") or part.get("inline_data")
        if inline and inline.get("data"):
            return base64.b64decode(inline["data"])
    raise RuntimeError("Gemini image model returned no image data")

def generate_image(prompt):
    errors = []
    for name, fn in [("Cloudflare", cloudflare_image), ("Gemini", gemini_image)]:
        try: return fn(prompt), name
        except Exception as e: errors.append(f"{name}: {str(e)[:180]}")
    raise RuntimeError("Image providers failed. " + " | ".join(errors))

# ------------------------- AUDIO -------------------------
def transcribe_audio(audio_file):
    """Recorded audio: OpenAI transcription first, Gemini audio understanding fallback."""
    raw = audio_file.getvalue() if hasattr(audio_file, "getvalue") else bytes(audio_file)
    filename = getattr(audio_file, "name", "voice.webm")
    mime = getattr(audio_file, "type", "audio/webm") or "audio/webm"
    errors = []
    if OPENAI_API_KEY:
        try:
            r = requests.post("https://api.openai.com/v1/audio/transcriptions", headers={"Authorization": f"Bearer {OPENAI_API_KEY}"}, files={"file": (filename, raw, mime)}, data={"model": "gpt-transcribe", "response_format": "json"}, timeout=35)
            r.raise_for_status()
            text = r.json().get("text", "").strip()
            if text: return text, "OpenAI Transcription"
        except Exception as e: errors.append("OpenAI transcription: " + str(e)[:160])
    if GEMINI_API_KEY:
        try:
            encoded = base64.b64encode(raw).decode("ascii")
            url = f"https://generativelanguage.googleapis.com/v1beta/models/{GEMINI_MODEL}:generateContent?key={GEMINI_API_KEY}"
            r = requests.post(url, json={"contents": [{"role": "user", "parts": [{"text": "Transcribe this audio accurately in its original language. Return only the transcript."}, {"inline_data": {"mime_type": mime, "data": encoded}}]}]}, timeout=35)
            r.raise_for_status()
            parts = r.json().get("candidates", [{}])[0].get("content", {}).get("parts", [])
            transcript = " ".join(p.get("text", "") for p in parts).strip()
            if transcript: return transcript, "Gemini Audio Backup"
        except Exception as e: errors.append("Gemini audio: " + str(e)[:160])
    raise RuntimeError("Audio transcription unavailable. " + " | ".join(errors))

def openai_tts(text_to_read):
    if not OPENAI_API_KEY: raise RuntimeError("OPENAI_API_KEY missing for TTS")
    r = requests.post("https://api.openai.com/v1/audio/speech", headers={"Authorization": f"Bearer {OPENAI_API_KEY}", "Content-Type": "application/json"}, json={"model": "gpt-4o-mini-tts", "voice": "alloy", "input": text_to_read[:3500], "response_format": "mp3"}, timeout=40)
    r.raise_for_status()
    return r.content

def cloudflare_tts(text_to_read):
    if not CF_ACCOUNT_ID or not CF_API_TOKEN: raise RuntimeError("Cloudflare credentials missing")
    url = f"https://api.cloudflare.com/client/v4/accounts/{CF_ACCOUNT_ID}/ai/run/@cf/deepgram/aura-1"
    r = requests.post(url, headers={"Authorization": f"Bearer {CF_API_TOKEN}"}, json={"text": text_to_read[:2500]}, timeout=35)
    r.raise_for_status()
    if r.headers.get("content-type", "").startswith("audio/"): return r.content
    try:
        payload = r.json()
        if payload.get("result", {}).get("audio"): return base64.b64decode(payload["result"]["audio"])
    except Exception: pass
    raise RuntimeError("Cloudflare TTS returned no audio")

def make_speech(text_to_read):
    errors = []
    for name, fn in [("OpenAI Voice", openai_tts), ("Cloudflare Voice", cloudflare_tts)]:
        try: return fn(text_to_read), name
        except Exception as e: errors.append(name + ": " + str(e)[:150])
    raise RuntimeError("TTS unavailable: " + " | ".join(errors))

# ------------------------- CSS: ORIGINAL COLORS ----------
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800;900&display=swap');
html, body, [class*="css"] {font-family:'Inter',sans-serif; color:#fff;}
.stApp {background:radial-gradient(ellipse at 10% 0%,#24204e 0%,transparent 35%),radial-gradient(ellipse at 90% 15%,#142b55 0%,transparent 35%),linear-gradient(140deg,#070b18,#0c1022 55%,#090d1b);color:#fff;}
.block-container {max-width:1450px;padding-top:1.4rem;padding-bottom:5rem;}
[data-testid="stSidebar"] {background:linear-gradient(180deg,#111a30,#0a1020);border-right:1px solid #39466b;}
[data-testid="stSidebar"] * {color:#e8eaff;}
[data-testid="stSidebar"] .stButton>button {text-align:left;min-height:42px;border:1px solid #29395c;background:linear-gradient(110deg,#182541,#111b31);border-radius:11px;padding-left:14px;}
[data-testid="stSidebar"] .stButton>button:hover {background:linear-gradient(110deg,#30275f,#1b3760);border-color:#8775d8;}
.brand {font-size:27px;font-weight:900;letter-spacing:-1px;padding:8px 0;}.brand span{color:#a78bfa;}
.hero {padding:34px;border-radius:25px;border:1px solid #51418c;background:radial-gradient(circle at 90% 20%,#41409b55,transparent 35%),linear-gradient(120deg,#171a3a,#142344);box-shadow:0 15px 45px #0005;margin-bottom:25px;}
.hero-label,.dash-kicker{color:#b5a5ff;font-size:11px;font-weight:800;letter-spacing:2px;text-transform:uppercase;}
.hero-title{font-size:clamp(32px,5vw,53px);font-weight:900;letter-spacing:-2px;margin:8px 0;}.hero-sub{color:#c1c8e5;line-height:1.7;}
.panel{padding:20px;border-radius:18px;background:linear-gradient(145deg,#151d35,#10182b);border:1px solid #2c3858;margin-bottom:14px;}
.tool-stat{padding:23px;border-radius:20px;background:linear-gradient(140deg,#201d49,#132c4b);border:1px solid #55469a;margin:12px 0;}
.small-muted{color:#c0c9e3;font-size:13px;}
div[data-testid="stChatMessage"]{padding:9px 13px!important;margin-bottom:8px!important;border-radius:15px!important;border:1px solid #2b3655;background:#111a2d;}
div[data-testid="stChatMessage"] p, .stMarkdown, .stMarkdown p, .stMarkdown li, .stMarkdown span {color:#fff;}
.stButton>button{border:1px solid #574c9b;border-radius:12px;background:linear-gradient(120deg,#6049b7,#3456a0);color:white;font-weight:700;transition:.2s;}
.stButton>button:hover{border-color:#b7a4ff;transform:translateY(-1px);color:white;}
.stTextInput input,.stTextArea textarea,.stSelectbox div[data-baseweb="select"]{background:#10182b!important;border:1px solid #39466b!important;border-radius:13px!important;color:white!important;}
[data-testid="stChatInput"]{border-radius:22px!important;border:1px solid #554a91!important;background:#10182b!important;}
[data-testid="stMetricValue"], [data-testid="stMetricLabel"]{color:#fff!important;}
hr{border-color:#283653;}
</style>
""", unsafe_allow_html=True)

# ------------------------- UI HELPERS --------------------
def hero(title, subtitle):
    st.markdown(f'<div class="hero"><div class="hero-label">NEXTGEN AI • VERSION MAX</div><div class="hero-title">{title}</div><div class="hero-sub">{subtitle}</div></div>', unsafe_allow_html=True)

def panel(icon, title, description):
    st.markdown(f'<div class="panel"><div style="font-size:23px">{icon}</div><h3 style="margin:8px 0;color:white">{title}</h3><div class="small-muted">{description}</div></div>', unsafe_allow_html=True)

def metric(label, value, icon):
    st.markdown(f'<div class="panel"><div class="small-muted">{icon} {label}</div><div style="font-size:27px;font-weight:900;margin-top:8px;color:white">{value}</div></div>', unsafe_allow_html=True)

# ------------------------- SESSION STATE -----------------
if "page" not in st.session_state: st.session_state.page = "Dashboard"
if "chat_id" not in st.session_state: st.session_state.chat_id = create_chat()
if "tool_result" not in st.session_state: st.session_state.tool_result = None
if "tool_name" not in st.session_state: st.session_state.tool_name = None
if "speech_audio" not in st.session_state: st.session_state.speech_audio = None

def go(page): st.session_state.page = page

# ------------------------- SIDEBAR -----------------------
with st.sidebar:
    st.markdown('<div class="brand">✦ NEXTGEN <span>AI</span></div>', unsafe_allow_html=True)
    st.caption("VERSION MAX • Your Creative Universe")
    if st.button("✚  New Chat", use_container_width=True):
        st.session_state.chat_id = create_chat(); go("AI Chat"); st.rerun()
    st.markdown("---"); st.caption("✦  WORKSPACE")
    pages = [("▦", "Dashboard"), ("✧", "AI Chat"), ("🎨", "AI Image Studio"), ("⚡", "Tool Center"), ("▤", "PDF Assistant")]
    for symbol, p in pages:
        if st.button(f"{symbol}   {p}", use_container_width=True, key="nav_"+p): go(p); st.rerun()
    st.markdown("---"); st.caption("▣  LIBRARY")
    for symbol, p in [("◷", "Chat History"), ("✦", "My Creations"), ("⚙", "Settings"), ("ⓘ", "About")]:
        if st.button(f"{symbol}   {p}", use_container_width=True, key="nav_"+p): go(p); st.rerun()
    st.markdown("---"); st.caption("◷  RECENT CONVERSATIONS")
    for chat in get_chats()[:7]:
        if st.button("💬  "+(chat["title"] or "New Chat")[:25], key=f"recent_{chat['id']}", use_container_width=True):
            st.session_state.chat_id = chat["id"]; go("AI Chat"); st.rerun()
    st.markdown("---"); st.caption("NEXTGEN AI MAX © 2026"); st.caption("Created by Arav")

# ------------------------- PAGES -------------------------
page = st.session_state.page
if page == "Dashboard":
    hero("One Platform. Endless Possibilities.", "Explore AI chat, creativity, productivity, learning and intelligent tools — all in one workspace.")
    a,b,c,d = st.columns(4)
    with a: metric("WORKSPACE POSSIBILITIES", "4,000+", "✦")
    with b: metric("AI TOOLS", f"{TOOL_COUNT}+", "⚡")
    with c: metric("CATEGORIES", len(TOOL_LIBRARY), "▦")
    with d: metric("AI ENGINES", "3", "🤖")
    st.markdown("## ✦ Explore Workspace")
    cols = st.columns(3)
    features = [("💬","AI Chat","Grok, OpenAI and Gemini fallback chat."),("🎨","AI Image Studio","Cloudflare image generation with Gemini backup."),("🧰","Tool Center",f"{TOOL_COUNT} ready-to-use tools across 20 categories."),("📄","PDF Assistant","Upload a PDF and ask questions about its contents."),("📚","Chat History","Continue previous conversations anytime."),("⚙️","Settings","Check your connected AI providers and services.")]
    for i,item in enumerate(features):
        with cols[i%3]: panel(*item)
    st.markdown("## 🚀 Workspace Overview")
    left,right = st.columns([1.4,1])
    with left:
        st.markdown('<div class="tool-stat"><div class="dash-kicker">BUILT FOR IDEAS</div><h2 style="color:white;margin-bottom:6px">Your creative command centre</h2><p class="small-muted">Move from learning to coding, writing, research and image creation without leaving NEXTGEN AI.</p></div>', unsafe_allow_html=True)
    with right:
        panel("⚡","Smart provider routing","Primary AI first, then configured backups automatically.")
        panel("🌐","Smart web search","Search is triggered for fresh or source-dependent questions, not every chat.")
    st.markdown("## ✦ Quick Access")
    q1,q2,q3 = st.columns(3)
    with q1:
        if st.button("💬  Start a conversation",use_container_width=True): go("AI Chat"); st.rerun()
    with q2:
        if st.button("🎨  Create an image",use_container_width=True): go("AI Image Studio"); st.rerun()
    with q3:
        if st.button("⚡  Explore all tools",use_container_width=True): go("Tool Center"); st.rerun()

elif page == "AI Chat":
    hero("AI Chat", "Ask anything. Learn anything. Create anything.")
    messages = get_messages(st.session_state.chat_id)
    if not messages:
        st.markdown('<div class="tool-stat"><h3 style="color:white">Hello! Welcome to NEXTGEN AI ✦</h3><p class="small-muted">Your AI assistant is ready. Type your first question below.</p></div>', unsafe_allow_html=True)
    for msg in messages:
        with st.chat_message(msg["role"]):
            st.markdown(msg["content"])
            if msg["role"] == "assistant":
                c1,c2,c3,c4,c5 = st.columns(5)
                with c1:
                    st.code(msg["content"], language=None)  # Streamlit code block includes a copy control.
                with c2:
                    if st.button("🔊 Read", key=f"read_{msg['id']}"):
                        try:
                            audio, voice_provider = make_speech(msg["content"])
                            st.session_state.speech_audio = audio
                            st.session_state.speech_provider = voice_provider
                            st.rerun()
                        except Exception as e: st.warning(f"Voice service unavailable: {e}")
                with c3:
                    st.download_button("⬇️ Download", msg["content"], file_name=f"nextgen_answer_{msg['id']}.txt", mime="text/plain", key=f"download_{msg['id']}")
                with c4:
                    if st.button("👍", key=f"like_{msg['id']}"): st.toast("Thanks for your feedback!")
                with c5:
                    if st.button("↻", key=f"regen_{msg['id']}"):
                        st.session_state.regenerate_id = msg["id"]; st.rerun()
    if st.session_state.speech_audio:
        st.audio(st.session_state.speech_audio, format="audio/mp3")
        st.caption("Voice: " + st.session_state.get("speech_provider", "Generated speech"))
    if st.session_state.get("regenerate_id"):
        target_id = st.session_state.pop("regenerate_id")
        history = get_messages(st.session_state.chat_id); prior=[]
        for m in history:
            if m["id"] == target_id: break
            prior.append({"role":m["role"],"content":m["content"]})
        try:
            with st.spinner("Generating a fresh answer..."):
                answer, provider = ask_ai(prior)
            update_message(target_id, answer); st.toast(f"Regenerated with {provider}"); st.rerun()
        except Exception as e: st.error(str(e))
    prompt = st.chat_input("Message NEXTGEN AI...", accept_file=True, accept_audio=True, file_type=["pdf","txt","png","jpg","jpeg"])
    if prompt:
        user_text = prompt.text or ""
        if prompt.files:
            for uploaded in prompt.files:
                if uploaded.type == "text/plain": user_text += "\n\n" + uploaded.getvalue().decode("utf-8",errors="ignore")
                elif uploaded.name.lower().endswith(".pdf"):
                    try:
                        from pypdf import PdfReader
                        reader=PdfReader(uploaded); pdf_text="\n".join(p.extract_text() or "" for p in reader.pages)
                        user_text += "\n\nPDF CONTENT:\n" + pdf_text[:28000]
                    except Exception as e: user_text += f"\nPDF reading error: {e}"
                else: user_text += f"\nAttached image: {uploaded.name}. Image understanding is not enabled for this attachment path."
        if getattr(prompt,"audio",None):
            try:
                transcript, transcription_provider = transcribe_audio(prompt.audio)
                user_text += "\n\nVoice transcription: " + transcript
                st.info(f"Voice converted to text using {transcription_provider}.")
            except Exception as e: st.warning(f"Could not transcribe audio: {e}")
        if user_text.strip():
            save_message(st.session_state.chat_id,"user",user_text); update_title(st.session_state.chat_id,user_text)
            history=[{"role":m["role"],"content":m["content"]} for m in get_messages(st.session_state.chat_id)]
            try:
                with st.spinner("NEXTGEN AI is thinking..."):
                    answer, provider = ask_ai(history)
                save_message(st.session_state.chat_id,"assistant",answer)
                st.toast(f"Answered with {provider}")
                st.rerun()
            except Exception as e: st.error(f"AI could not respond: {e}")

elif page == "AI Image Studio":
    hero("AI Image Studio", "Turn your imagination into visuals.")
    prompt=st.text_area("Describe your image",placeholder="A cinematic futuristic city at night...")
    if st.button("✨ Generate Image",use_container_width=True):
        if not prompt.strip(): st.warning("Please enter an image prompt.")
        else:
            try:
                with st.spinner("Creating your image..."):
                    image_data, provider=generate_image(prompt)
                st.image(image_data,use_container_width=True,caption=f"Generated with {provider}")
                st.download_button("⬇️ Download Image",image_data,file_name="nextgen_creation.png",mime="image/png")
                save_creation("image",prompt)
            except Exception as e: st.error(str(e))

elif page == "Tool Center":
    hero("AI Tool Center",f"Explore {TOOL_COUNT} tools across 20 categories.")
    category=st.selectbox("Choose Category",list(TOOL_LIBRARY.keys()))
    tool=st.selectbox("Choose Tool",TOOL_LIBRARY[category])
    details=st.text_area("Your Instructions",placeholder="Describe what you want the AI to create...")
    if st.button("🚀 Run Tool",use_container_width=True):
        if not details.strip(): st.warning("Please enter your instructions.")
        else:
            try:
                with st.spinner(f"Running {tool}..."):
                    result=run_tool(tool,details)
                st.session_state.tool_result=result; st.session_state.tool_name=tool; save_creation("tool",f"{tool}: {details}")
            except Exception as e: st.error(str(e))
    if st.session_state.tool_result:
        st.markdown("### ✦ Result"); st.markdown(st.session_state.tool_result)
        st.download_button("⬇️ Download Result",st.session_state.tool_result,file_name="nextgen_result.txt")

elif page == "PDF Assistant":
    hero("PDF Assistant","Upload a PDF and ask questions about its contents.")
    uploaded=st.file_uploader("Upload PDF",type=["pdf"])
    if uploaded:
        try:
            from pypdf import PdfReader
            reader=PdfReader(uploaded); pdf_text="\n".join(p.extract_text() or "" for p in reader.pages)
            st.success(f"PDF loaded successfully — {len(reader.pages)} pages.")
            question=st.text_area("Ask a question about this PDF")
            if st.button("Ask PDF Assistant"):
                if not question.strip(): st.warning("Enter a question.")
                else:
                    prompt_text="Answer using the following PDF content. If the answer is not present, say so.\n\n"+pdf_text[:45000]+"\n\nQuestion: "+question
                    try:
                        with st.spinner("Analyzing PDF..."):
                            answer,provider=ask_ai([{"role":"user","content":prompt_text}],allow_search=False)
                        st.markdown("### Answer"); st.markdown(answer); st.caption(f"Answered with {provider}")
                    except Exception as e: st.error(str(e))
        except Exception as e: st.error(f"Could not read PDF: {e}")

elif page == "Chat History":
    hero("Chat History","Your previous conversations in one place.")
    chats=get_chats()
    if not chats: st.info("No conversations yet.")
    for chat in chats:
        col1,col2,col3=st.columns([6,2,1])
        with col1: st.markdown(f"**{chat['title']}**"); st.caption(chat["created"])
        with col2:
            if st.button("Open",key=f"open_{chat['id']}"): st.session_state.chat_id=chat["id"]; go("AI Chat"); st.rerun()
        with col3:
            if st.button("🗑️",key=f"delete_{chat['id']}"): delete_chat(chat["id"]); st.rerun()

elif page == "My Creations":
    hero("My Creations","Your saved AI creation records.")
    creations=get_creations()
    if not creations: st.info("Your creations will appear here.")
    for item in creations:
        with st.expander(f"{item['kind'].upper()} • {item['created']}"): st.write(item["content"])

elif page == "Settings":
    hero("Settings","Manage your NEXTGEN AI workspace.")
    panel("🎨","Appearance","NEXTGEN AI keeps its original dark premium purple-blue interface.")
    panel("💬","Chat History","Conversations are stored locally in the SQLite database.")
    panel("🤖","AI Provider Priority","Grok → OpenAI → Gemini. A configured backup is tried automatically if an earlier provider fails.")
    panel("🌐","Smart Web Search","Tavily is used only when a query appears to need current or source-based information.")
    panel("🎙️","Voice","OpenAI TTS first, Cloudflare Aura voice backup. Recorded audio transcription uses OpenAI first, then Gemini.")
    st.markdown("### API Status")
    statuses=[("Grok / xAI",bool(XAI_API_KEY)),("OpenAI",bool(OPENAI_API_KEY)),("Gemini",bool(GEMINI_API_KEY)),("Tavily Search",bool(TAVILY_API_KEY)),("Cloudflare Image",bool(CF_ACCOUNT_ID and CF_API_TOKEN))]
    for name,ok in statuses: st.write(f"{'🟢' if ok else '⚪'} **{name}:** {'Configured' if ok else 'Not configured'}")
    st.caption("Provider speed depends on internet, API load, account limits and model response time; sub-second replies cannot be guaranteed.")

elif page == "About":
    hero("Meet the Creator","A young mind with big ideas, a passion for technology and a vision to build something extraordinary.")
    st.markdown('<div class="hero"><div class="hero-label">FOUNDER & CREATOR</div><div class="hero-title">ARAV</div><div class="hero-sub">Student Developer | AI Enthusiast | Young Innovator</div></div>',unsafe_allow_html=True)
    st.markdown("## 👨‍💻 About Arav")
    st.markdown("Arav is a curious student interested in Artificial Intelligence, Python programming, application development and modern technology. He enjoys exploring new ideas, experimenting with AI tools and developing creative digital projects.")
    st.markdown("## 🚀 The Journey")
    st.markdown("NEXTGEN AI began with an idea: bring useful AI capabilities together in one clear and simple workspace. The project continues to grow through learning, experimentation and improvements.")
    st.markdown("## ✦ Skills & Interests")
    for item in [("🤖","Artificial Intelligence","Exploring AI assistants and intelligent applications."),("💻","Python Development","Learning to build applications and useful software."),("🌐","Web & App Development","Creating digital experiences and interactive platforms."),("🎨","Creative Technology","Combining imagination, design and technology."),("📚","Continuous Learning","Learning new concepts and improving step by step."),("🎬","Content Creation","Exploring digital creativity and AI-powered content.")]: panel(*item)
    st.markdown("## 🌟 Vision & Mission")
    st.markdown("Make artificial intelligence easier to explore and more useful through one workspace. **Dream Big. Learn Every Day. Build Something Amazing.**")
    st.markdown('<div class="tool-stat"><div class="dash-kicker">FOUNDER\'S MESSAGE</div><h2 style="color:white;">One idea can start something big.</h2><p class="small-muted">NEXTGEN AI is a learning journey, a creative project and a vision that grows with every improvement.</p><h3 style="color:#bcb2ff;">— Arav</h3></div>',unsafe_allow_html=True)
    st.caption("NEXTGEN AI VERSION MAX © 2026 | Created by Arav")

# ------------------------- FOOTER ------------------------
st.markdown("---")
st.markdown("<center><span style='color:#aeb9d4;font-size:12px'>✦ NEXTGEN AI — VERSION MAX • Created by Arav • 2026</span></center>",unsafe_allow_html=True)
