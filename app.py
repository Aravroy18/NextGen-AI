
import os
import io
import sqlite3
import hashlib
import secrets
import requests
import pandas as pd
import streamlit as st
import base64

from datetime import datetime
from dotenv import load_dotenv
from PIL import Image
from pypdf import PdfReader
from google import genai
from google.genai import types

# =========================================================
# 1. CONFIGURATION
# =========================================================

load_dotenv()

st.set_page_config(
    page_title="NEXTGEN AI",
    page_icon="🚀",
    layout="wide",
    initial_sidebar_state="expanded"
)

GEMINI_KEY = os.getenv("GEMINI_API_KEY", "")
FINNHUB_KEY = os.getenv("FINNHUB_API_KEY", "")

MODEL = os.getenv("MODEL", "gemini-3.8-flash")
DB_PATH = "nextgen_users.db"

# =========================================================
# 2. DATABASE
# =========================================================

def get_db():
    return sqlite3.connect(DB_PATH, check_same_thread=False)


def init_db():
    conn = get_db()
    cur = conn.cursor()

    cur.execute("""
        CREATE TABLE IF NOT EXISTS users (
            username TEXT PRIMARY KEY,
            salt TEXT NOT NULL,
            password_hash TEXT NOT NULL
        )
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS messages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT NOT NULL,
            role TEXT NOT NULL,
            content TEXT NOT NULL,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
    """)

    conn.commit()
    conn.close()


def hash_password(password, salt):
    return hashlib.pbkdf2_hmac(
        "sha256",
        password.encode(),
        salt.encode(),
        200000
    ).hex()


def create_user(username, password):
    conn = get_db()
    cur = conn.cursor()

    salt = secrets.token_hex(16)
    password_hash = hash_password(password, salt)

    try:
        cur.execute(
            "INSERT INTO users VALUES (?, ?, ?)",
            (username, salt, password_hash)
        )
        conn.commit()
        return True
    except sqlite3.IntegrityError:
        return False
    finally:
        conn.close()


def verify_user(username, password):
    conn = get_db()
    cur = conn.cursor()

    cur.execute(
        "SELECT salt, password_hash FROM users WHERE username=?",
        (username,)
    )
    result = cur.fetchone()
    conn.close()

    if not result:
        return False

    salt, saved_hash = result
    return hash_password(password, salt) == saved_hash


def save_message(username, role, content):
    if username == "Guest":
        return

    conn = get_db()
    cur = conn.cursor()

    cur.execute(
        "INSERT INTO messages (username, role, content) VALUES (?, ?, ?)",
        (username, role, str(content))
    )

    conn.commit()
    conn.close()


def load_messages(username):
    conn = get_db()
    cur = conn.cursor()

    cur.execute(
        """
        SELECT role, content
        FROM messages
        WHERE username=?
        ORDER BY id ASC
        """,
        (username,)
    )

    data = cur.fetchall()
    conn.close()

    return [
        {"role": role, "content": content}
        for role, content in data
    ]


init_db()

# =========================================================
# 3. AI CLIENT
# =========================================================

@st.cache_resource
def get_client():
    if not GEMINI_KEY:
        return None

    return genai.Client(api_key=GEMINI_KEY)


def generate_answer(contents, system_instruction=None):
    client = get_client()

    if client is None:
        raise ValueError(
            "GEMINI_API_KEY missing. Please check your .env file."
        )

    config = None

    if system_instruction:
        config = types.GenerateContentConfig(
            system_instruction=system_instruction,
            temperature=0.7
        )

    response = client.models.generate_content(
        model=MODEL,
        contents=contents,
        config=config
    )

    return response.text or "AI could not generate a response."



# =========================================================
# 4. 50 AI TOOLS
# =========================================================

AI_STUDIOS = {
    "🚀 AI Development Studio": [
        "AI Coding Studio",
        "AI Website Builder",
        "AI Android App Builder",
        "AI School App Builder",
        "AI Game Builder",
        "Database Builder",
        "AI Bug Fixer",
        "API Generator",
        "UI/UX Designer",
        "Code Converter"
    ],

    "🧠 AI Intelligence Center": [
        "AI Research Assistant",
        "AI Web Search",
        "AI Deep Research",
        "AI Memory Planner",
        "AI Personality Modes",
        "AI Math Solver",
        "AI Science Assistant",
        "AI Language Translator",
        "AI Fact Checker",
        "AI Question Generator"
    ],

    "🎨 AI Creative Studio": [
        "AI Logo Maker",
        "AI Thumbnail Maker",
        "AI Poster Designer",
        "AI Story Generator",
        "AI Comic Creator",
        "AI Music Idea Studio",
        "AI Voice Script Generator",
        "AI Presentation Maker",
        "AI Video Script Editor",
        "AI Social Media Manager"
    ],

    "🎓 AI Student Hub": [
        "AI Homework Helper",
        "AI Notes Maker",
        "AI Quiz Generator",
        "AI Flashcard Maker",
        "AI Timetable Planner",
        "AI Exam Preparation",
        "AI PDF to Notes",
        "AI Doubt Solver",
        "AI Dictionary",
        "AI Learning Roadmap"
    ],

    "⚡ AI Productivity Center": [
        "AI Email Writer",
        "AI Resume Builder",
        "AI Document Editor",
        "AI Spreadsheet Assistant",
        "AI PDF Helper",
        "AI Meeting Summarizer",
        "AI To-Do Planner",
        "AI Calendar Planner",
        "AI Mind Map Generator",
        "AI File Organizer"
    ]
}


TOOL_INSTRUCTIONS = {
    "AI Coding Studio": "Write clean, understandable code. Explain important parts and show how to use it.",
    "AI Website Builder": "Create a complete website plan and provide HTML, CSS and JavaScript code.",
    "AI Android App Builder": "Design an Android application and provide code, screens and setup instructions. Do not claim to compile an APK.",
    "AI School App Builder": "Design a school management application with student, teacher and admin modules.",
    "AI Game Builder": "Create a game concept, mechanics and starter code.",
    "Database Builder": "Design a database schema and provide SQL queries.",
    "AI Bug Fixer": "Analyze the supplied code, identify likely bugs and provide corrected code.",
    "API Generator": "Design API endpoints and provide example implementation.",
    "UI/UX Designer": "Create a detailed UI/UX plan, screen structure and design system.",
    "Code Converter": "Convert code between programming languages and explain differences.",

    "AI Research Assistant": "Prepare a structured research report and distinguish facts from assumptions.",
    "AI Web Search": "Explain that live web search is not connected unless an external search API is configured. Give a research plan.",
    "AI Deep Research": "Create a detailed research report using your available knowledge and clearly identify information needing verification.",
    "AI Memory Planner": "Organize the information supplied by the user into a useful reference plan. Do not claim permanent memory.",
    "AI Personality Modes": "Respond using the tone and style requested by the user.",
    "AI Math Solver": "Solve step by step and explain the mathematical reasoning.",
    "AI Science Assistant": "Explain science concepts with examples and accurate terminology.",
    "AI Language Translator": "Translate accurately and preserve meaning.",
    "AI Fact Checker": "Evaluate claims, identify uncertainty and explain what sources should verify them.",
    "AI Question Generator": "Generate questions with answers and difficulty levels.",

    "AI Logo Maker": "Create a detailed logo design concept and an image-generation prompt.",
    "AI Thumbnail Maker": "Create a high-impact thumbnail concept, layout and image prompt.",
    "AI Poster Designer": "Create poster copy, visual layout and image prompt.",
    "AI Story Generator": "Write an original engaging story.",
    "AI Comic Creator": "Create a comic with panels, dialogue and image prompts.",
    "AI Music Idea Studio": "Create an original music concept, mood and production brief. Do not reproduce copyrighted lyrics.",
    "AI Voice Script Generator": "Write a natural voiceover script.",
    "AI Presentation Maker": "Create a slide-by-slide presentation outline and content.",
    "AI Video Script Editor": "Improve scripts, dialogue, hooks and scene transitions.",
    "AI Social Media Manager": "Create platform-appropriate captions, post ideas and content calendars.",

    "AI Homework Helper": "Teach the student step by step and explain the answer clearly.",
    "AI Notes Maker": "Create organized notes with headings, definitions and examples.",
    "AI Quiz Generator": "Generate a quiz with an answer key.",
    "AI Flashcard Maker": "Create question-answer flashcards.",
    "AI Timetable Planner": "Create a realistic study timetable with breaks.",
    "AI Exam Preparation": "Create a revision strategy and practice questions.",
    "AI PDF to Notes": "Convert supplied text into clear notes.",
    "AI Doubt Solver": "Explain the student's doubt in simple language.",
    "AI Dictionary": "Give meaning, pronunciation guidance and example sentences.",
    "AI Learning Roadmap": "Create a step-by-step learning path.",

    "AI Email Writer": "Write a clear and professional email.",
    "AI Resume Builder": "Create a truthful resume using only supplied details.",
    "AI Document Editor": "Improve structure, clarity and grammar.",
    "AI Spreadsheet Assistant": "Explain spreadsheet formulas and provide examples.",
    "AI PDF Helper": "Help organize, explain or summarize supplied PDF text.",
    "AI Meeting Summarizer": "Summarize supplied meeting notes into decisions and tasks.",
    "AI To-Do Planner": "Turn goals into an organized task list.",
    "AI Calendar Planner": "Create a schedule from supplied dates and tasks.",
    "AI Mind Map Generator": "Create a hierarchical text-based mind map.",
    "AI File Organizer": "Suggest a safe folder structure and file naming system."
}


def show_ai_tool_center():
    st.markdown("## 🚀 AI TOOL CENTER")
    st.caption("50 intelligent tools. One creative universe.")

    studio = st.selectbox(
        "Choose your studio",
        list(AI_STUDIOS.keys())
    )

    tool = st.selectbox(
        "Choose your AI tool",
        AI_STUDIOS[studio]
    )

    st.markdown(f"### ✨ {tool}")

    task = st.text_area(
        "Describe what you want to do",
        height=150,
        placeholder="Write your task here..."
    )

    if st.button(
        "🚀 Generate with NEXTGEN AI",
        use_container_width=True
    ):
        if not task.strip():
            st.warning("Please enter your task.")
            return

        instruction = TOOL_INSTRUCTIONS.get(
            tool,
            "Help the user with the requested task."
        )

        prompt = f"""
You are NEXTGEN AI.

Selected studio: {studio}
Selected tool: {tool}

Your instructions:
{instruction}

User request:
{task}

Provide a useful, accurate and well-organized answer.
Use headings and examples where useful.
Do not claim to have performed actions that you cannot actually perform.
"""

        
        with st.spinner("NEXTGEN AI is thinking..."):
            try:
                answer = generate_answer(prompt)

                st.markdown("### ✨ Your Result")
                st.markdown(answer)

            except Exception as e:
                error_text = str(e)

                if "503" in error_text or "UNAVAILABLE" in error_text:
                    st.warning(
                        "Gemini is currently busy. "
                        "Please try again after a short wait."
                    )

                elif "429" in error_text or "RESOURCE_EXHAUSTED" in error_text:
                    st.warning(
                        "Gemini API usage limit reached. "
                        "Please check your API quota."
                    )

                else:
                    st.error(f"AI Tool Error: {error_text}")



# =========================================================
# 5. FINNHUB STOCK MARKET
# =========================================================

def finnhub_get(endpoint, params=None):
    if not FINNHUB_KEY:
        raise ValueError("FINNHUB_API_KEY missing in .env")

    params = params or {}
    params["token"] = FINNHUB_KEY

    response = requests.get(
        f"https://finnhub.io/api/v1/{endpoint}",
        params=params,
        timeout=15
    )

    response.raise_for_status()
    return response.json()


@st.cache_data(ttl=60)
def get_stock_quote(symbol):
    return finnhub_get("quote", {"symbol": symbol})


@st.cache_data(ttl=3600)
def get_company_profile(symbol):
    return finnhub_get("stock/profile2", {"symbol": symbol})


@st.cache_data(ttl=300)
def get_market_news():
    return finnhub_get(
        "news",
        {"category": "general"}
    )


def show_stock_market():
    st.markdown("## 📈 STOCK MARKET CENTER")
    st.caption("Market information for educational purposes.")

    symbol = st.text_input(
        "Enter stock symbol",
        value="AAPL"
    ).strip().upper()

    if st.button("Get Stock Data"):
        if not symbol:
            st.warning("Enter a stock symbol.")
            return

        try:
            quote = get_stock_quote(symbol)
            profile = get_company_profile(symbol)

            price = quote.get("c", 0)
            previous = quote.get("pc", 0)
            change = quote.get("d", 0)
            percent = quote.get("dp", 0)

            col1, col2, col3 = st.columns(3)

            col1.metric("Current Price", f"{price}")
            col2.metric("Change", f"{change}")
            col3.metric("Change %", f"{percent}%")

            st.markdown("### Company Profile")

            st.write(
                f"**Company:** {profile.get('name', symbol)}"
            )
            st.write(
                f"**Exchange:** {profile.get('exchange', 'N/A')}"
            )
            st.write(
                f"**Industry:** {profile.get('finnhubIndustry', 'N/A')}"
            )
            st.write(
                f"**Currency:** {profile.get('currency', 'N/A')}"
            )

            if price and previous:
                st.markdown("### AI Explanation")

                prompt = f"""
Explain this stock quote in simple educational language.

Symbol: {symbol}
Current price: {price}
Previous close: {previous}
Change: {change}
Percentage change: {percent}

Do not give buy or sell advice.
Explain that prices can change.
"""

                with st.spinner("Explaining market data..."):
                    st.markdown(generate_answer(prompt))

        except Exception as e:
            st.error(f"Stock API Error: {e}")

    st.divider()
    st.markdown("### 📰 General Market News")

    if st.button("Load Market News"):
        try:
            news = get_market_news()

            for item in news[:8]:
                st.markdown(f"**{item.get('headline', 'News')}**")
                st.caption(item.get("source", ""))
                st.write(item.get("summary", ""))
                if item.get("url"):
                    st.markdown(
                        f"[Read article]({item['url']})"
                    )
                st.divider()

        except Exception as e:
            st.error(f"News Error: {e}")

    st.caption(
        "Educational information only. Not investment advice."
    )


# =========================================================
# 6. AI VISION
# =========================================================

def show_ai_vision():
    st.markdown("## 👁️ AI VISION")
    st.write("Upload an image and ask NEXTGEN AI about it.")

    uploaded = st.file_uploader(
        "Upload image",
        type=["png", "jpg", "jpeg", "webp"],
        key="vision_upload"
    )

    question = st.text_area(
        "What should AI analyze?",
        placeholder="Describe this image..."
    )

    if uploaded:
        image = Image.open(uploaded).convert("RGB")
        st.image(image, use_container_width=True)

        if st.button("Analyze Image", use_container_width=True):
            prompt = question.strip() or "Describe this image."

            with st.spinner("Analyzing image..."):
                try:
                    answer = generate_answer([prompt, image])
                    st.markdown("### AI Analysis")
                    st.markdown(answer)
                except Exception as e:
                    st.error(f"Vision Error: {e}")


# =========================================================
# 7. PDF ASSISTANT
# =========================================================

def show_pdf_assistant():
    st.markdown("## 📄 PDF ASSISTANT")

    uploaded = st.file_uploader(
        "Upload a PDF",
        type=["pdf"],
        key="pdf_upload"
    )

    question = st.text_area(
        "Ask something about your PDF",
        placeholder="Summarize this document..."
    )

    if uploaded and st.button("Analyze PDF"):
        try:
            reader = PdfReader(uploaded)

            text = "\n".join(
                page.extract_text() or ""
                for page in reader.pages
            )

            if not text.strip():
                st.warning(
                    "No selectable text found. Scanned PDFs may need OCR."
                )
                return

            st.success(
                f"Extracted text from {len(reader.pages)} pages."
            )

            prompt = f"""
Answer the user's question using the PDF text below.
If the answer is not in the document, say so.
Do not invent information.

PDF TEXT:
{text[:50000]}

USER QUESTION:
{question or "Summarize this PDF with headings."}
"""

            with st.spinner("Reading PDF..."):
                st.markdown(generate_answer(prompt))

        except Exception as e:
            st.error(f"PDF Error: {e}")


# =========================================================
# 8. VOICE STUDIO
# =========================================================

def show_voice_studio():
    st.markdown("## 🎙️ VOICE STUDIO")
    st.caption("Ask a question using an audio recording.")

    audio = st.audio_input("Record your voice")

    if audio:
        st.audio(audio)

        if st.button("Analyze Voice"):
            try:
                audio_bytes = audio.getvalue()

                audio_part = types.Part.from_bytes(
                    data=audio_bytes,
                    mime_type=audio.type or "audio/wav"
                )

                with st.spinner("Understanding audio..."):
                    answer = generate_answer([
                        "Understand this audio. Transcribe it and answer if it contains a question.",
                        audio_part
                    ])

                    st.markdown("### AI Response")
                    st.markdown(answer)

            except Exception as e:
                st.error(f"Voice Error: {e}")


# =========================================================
# 9. AI IMAGE PROMPT STUDIO
# =========================================================


def show_image_studio():
    import os
    import base64
    import requests
    import streamlit as st

    st.markdown("""
    <div style="padding:22px;border-radius:18px;
    background:linear-gradient(120deg,#17113b,#101d38);
    border:1px solid #7048d8;">
        <h1 style="color:#c7a7ff;margin:0;">🎨 NEXTGEN AI IMAGE STUDIO</h1>
        <p style="color:#c9c6e8;">Turn your imagination into reality.</p>
    </div>
    """, unsafe_allow_html=True)

    st.write("### ✨ Describe Your Imagination")

    idea = st.text_area(
        "Your Image Prompt",
        placeholder="Example: A majestic lion sitting on a golden royal throne...",
        height=120,
        max_chars=1500
    )

    st.caption("Tip: Describe the subject, environment and details for better results.")

    st.write("### 🎭 Visual Settings")

    c1, c2 = st.columns(2)

    with c1:
        style = st.selectbox(
            "Image Style",
            [
                "Ultra Realistic",
                "3D Animation",
                "Anime",
                "Cinematic",
                "Fantasy Art",
                "Digital Art",
                "Cartoon",
                "Oil Painting",
                "Cyberpunk",
                "Product Photography"
            ]
        )

        image_format = st.selectbox(
            "Image Format",
            ["1:1 Square", "16:9 Landscape", "9:16 Portrait", "4:5 Portrait"]
        )

        lighting = st.selectbox(
            "Lighting Effects",
            [
                "Cinematic Lighting",
                "Golden Hour",
                "Neon Glow",
                "Soft Studio Lighting",
                "Dramatic Lighting",
                "Natural Lighting"
            ]
        )

    with c2:
        camera = st.selectbox(
            "Camera Angle",
            [
                "Eye Level",
                "Low Angle",
                "High Angle",
                "Top Down",
                "Close Up",
                "Wide Shot",
                "Portrait Shot"
            ]
        )

        color_mood = st.selectbox(
            "Color Mood",
            [
                "Vibrant Colors",
                "Warm Colors",
                "Cool Colors",
                "Dark Moody",
                "Pastel Colors",
                "Black and White"
            ]
        )

        background = st.selectbox(
            "Background Selection",
            [
                "Automatic",
                "Royal Palace",
                "Futuristic City",
                "Nature",
                "Professional Studio",
                "Minimal Background",
                "Custom Background"
            ]
        )

    custom_bg = ""
    if background == "Custom Background":
        custom_bg = st.text_input(
            "Describe Your Background",
            placeholder="Example: A beautiful mountain landscape"
        )

    negative_prompt = st.text_area(
        "Negative Prompt (Optional)",
        placeholder="Example: blurry, low quality, distorted details...",
        height=75
    )

    with st.expander("💡 Prompt Enhancement Preview"):
        st.write(
            "Your selected style, lighting, camera angle, "
            "colors and background will be combined with your prompt "
            "to create a more descriptive image request."
        )

    st.caption(
        "Note: Image format is currently a prompt instruction; "
        "the model may not return an exact aspect ratio."
    )

    if st.button("✨ GENERATE IMAGE", use_container_width=True):

        if not idea.strip():
            st.warning("Please describe your image first.")
            return

        account_id = st.secrets.get(
            "CLOUDFLARE_ACCOUNT_ID",
            os.getenv("CLOUDFLARE_ACCOUNT_ID")
        )

        api_token = st.secrets.get(
            "CLOUDFLARE_API_TOKEN",
            os.getenv("CLOUDFLARE_API_TOKEN")
        )

        if not account_id or not api_token:
            st.error("Cloudflare credentials are missing.")
            return

        background_text = custom_bg if custom_bg else background

        prompt = f"""
        {idea.strip()}.

        Visual Style: {style}.
        Image Composition: {image_format}.
        Lighting: {lighting}.
        Camera Angle: {camera}.
        Color Mood: {color_mood}.
        Background: {background_text}.

        Create a visually impressive, high-detail image.
        Maintain a clear main subject, realistic textures,
        balanced composition and professional visual quality.
        """

        if negative_prompt.strip():
            prompt += (
                "\nAvoid these elements: "
                + negative_prompt.strip()
            )

        model = "@cf/black-forest-labs/flux-1-schnell"

        url = (
            f"https://api.cloudflare.com/client/v4/accounts/"
            f"{account_id}/ai/run/{model}"
        )

        headers = {
            "Authorization": f"Bearer {api_token}",
            "Content-Type": "application/json"
        }

        payload = {
            "prompt": prompt,
            "steps": 4
        }

        try:
            with st.spinner("🎨 NEXTGEN AI is creating your image..."):

                response = requests.post(
                    url,
                    headers=headers,
                    json=payload,
                    timeout=180
                )

                if response.status_code != 200:
                    st.error(
                        f"Generation Error {response.status_code}: "
                        f"{response.text[:1000]}"
                    )
                    return

                result = response.json()
                image_b64 = result.get("result", {}).get("image")

                if not image_b64:
                    st.error("No image was returned by the AI model.")
                    return

                image_bytes = base64.b64decode(image_b64)

                st.success("🎉 Your image is ready!")

                st.image(
                    image_bytes,
                    caption="Generated with NEXTGEN AI",
                    use_container_width=True
                )

                st.download_button(
                    "⬇️ Download Your Image",
                    data=image_bytes,
                    file_name="nextgen_ai_image.png",
                    mime="image/png",
                    use_container_width=True
                )

        except requests.exceptions.Timeout:
            st.error("Generation timed out. Please try again.")

        except Exception as e:
            st.error(f"Image Generation Error: {e}")

    


# =========================================================
# 10. AI VIDEO STUDIO
# =========================================================

def show_video_studio():
    import os
    import requests
    import streamlit as st

    st.markdown("""
    <div style="
        padding:22px;
        border-radius:18px;
        background:linear-gradient(120deg,#17113b,#101d38);
        border:1px solid #7048d8;">
        <h1 style="color:#c7a7ff;margin:0;">
            🎬 NEXTGEN AI VIDEO STUDIO
        </h1>
        <p style="color:#c9c6e8;">
            Turn your imagination into cinematic videos.
        </p>
    </div>
    """, unsafe_allow_html=True)

    st.write("### ✨ Describe Your Video")

    prompt = st.text_area(
        "Your Video Idea",
        placeholder="A majestic lion walking through a royal palace...",
        height=120,
        max_chars=2500
    )

    st.caption(
        "Write one simple line or a detailed prompt. "
        "AI will use your description to generate a video."
    )

    with st.expander("⚙️ Advanced Settings (Optional)"):

        style = st.selectbox(
            "Visual Style",
            [
                "Automatic",
                "Cinematic Realistic",
                "3D Animation",
                "Anime",
                "Fantasy",
                "Cartoon",
                "Professional Film"
            ]
        )

        camera = st.selectbox(
            "Camera Movement",
            [
                "Automatic",
                "Smooth Tracking Shot",
                "Slow Zoom In",
                "Wide Cinematic Shot",
                "Close Up"
            ]
        )

        ratio = st.selectbox(
            "Video Format",
            ["9:16", "16:9", "1:1", "4:3", "3:4"]
        )

    col1, col2 = st.columns(2)

    with col1:
        duration = st.slider(
            "Video Duration (seconds)",
            min_value=5,
            max_value=15,
            value=5
        )

    with col2:
        resolution = st.selectbox(
            "Resolution",
            ["480P", "720P", "1080P"]
        )

    st.info(
        "Video generation uses Cloudflare's paid model. "
        "Check the charges before generating."
    )

    approved = st.checkbox(
        "A parent/guardian has approved any applicable usage charges."
    )

    if st.button(
        "🎬 GENERATE VIDEO",
        use_container_width=True
    ):

        if not prompt.strip():
            st.warning("Please enter a video idea.")
            return

        if not approved:
            st.warning(
                "Please get parent/guardian approval before generation."
            )
            return

        try:
            account_id = st.secrets.get(
                "CLOUDFLARE_ACCOUNT_ID",
                os.getenv("CLOUDFLARE_ACCOUNT_ID")
            )

            api_token = st.secrets.get(
                "CLOUDFLARE_API_TOKEN",
                os.getenv("CLOUDFLARE_API_TOKEN")
            )

        except Exception:
            account_id = os.getenv("CLOUDFLARE_ACCOUNT_ID")
            api_token = os.getenv("CLOUDFLARE_API_TOKEN")

        if not account_id or not api_token:
            st.error("Cloudflare credentials are missing.")
            return

        final_prompt = f"""
        {prompt.strip()}.

        Visual style: {style}.
        Camera movement: {camera}.
        Create a coherent cinematic video with smooth motion,
        detailed visuals and professional composition.
        """

        url = (
            "https://api.cloudflare.com/client/v4/accounts/"
            f"{account_id}/ai/run"
        )

        headers = {
            "Authorization": f"Bearer {api_token}",
            "Content-Type": "application/json"
        }

        payload = {
            "model": "alibaba/wan-3.0",
            "input": {
                "prompt": final_prompt,
                "resolution": resolution,
                "ratio": ratio,
                "duration": duration
            }
        }

        try:
            with st.spinner(
                "🎬 NEXTGEN AI is creating your video..."
            ):
                response = requests.post(
                    url,
                    headers=headers,
                    json=payload,
                    timeout=300
                )

                if response.status_code != 200:
                    st.error(
                        f"Cloudflare Error {response.status_code}"
                    )
                    st.code(response.text[:1500])
                    return

                data = response.json()
                video_url = data.get("result", {}).get("video")

                if not video_url:
                    st.error(
                        "Video is not ready or no video URL was returned."
                    )
                    st.write(data)
                    return

                video_response = requests.get(
                    video_url,
                    timeout=180
                )
                video_response.raise_for_status()

                video_bytes = video_response.content

                st.success("🎉 Your video is ready!")

                st.video(video_bytes)

                st.download_button(
                    "⬇️ Download Video",
                    data=video_bytes,
                    file_name="nextgen_ai_video.mp4",
                    mime="video/mp4",
                    use_container_width=True
                )

        except requests.exceptions.Timeout:
            st.error(
                "Video generation timed out. "
                "Check Cloudflare usage before trying again."
            )

        except requests.exceptions.RequestException as e:
            st.error(f"Network Error: {e}")

        except Exception as e:
            st.error(f"Video Generation Error: {e}")

# =========================================================
# 11. AI CHAT
# =========================================================

def show_chat():
    st.markdown("## 💬 NEXTGEN AI CHAT")
    st.caption("Your intelligent creative assistant.")

    for message in st.session_state.messages:
        with st.chat_message(message["role"]):
            st.markdown(message["content"])

    # Keep the original chat input style and placeholder.
    user_prompt = st.chat_input("Message NEXTGEN AI...")

    if user_prompt:
        st.session_state.messages.append({
            "role": "user",
            "content": user_prompt
        })

        save_message(
            st.session_state.username,
            "user",
            user_prompt
        )

        with st.chat_message("user"):
            st.markdown(user_prompt)

        history = st.session_state.messages[-12:]

        contents = []

        for item in history:
            contents.append(
                f"{item['role'].upper()}: {item['content']}"
            )

        
        system_instruction = """
You are NEXTGEN AI, a helpful, accurate and creative AI assistant.
Your tagline is YOUR CREATIVE UNIVERSE.

Respond in the language used by the user.
Explain difficult topics clearly.
Never claim to have performed actions you cannot perform.
For financial topics, provide educational information only.

CREATOR IDENTITY:

Your creator and developer is Aarav Roy,
a talented, creative, hardworking and ambitious young developer
who studies at Swami Vivekanand Shiksha Niketan (SVSN).

He is passionate about Artificial Intelligence, programming,
technology, innovation and building useful digital products.

He has a creative mind, a strong desire to learn and the
determination to turn innovative ideas into reality.

NEXTGEN AI is a result of his creativity, dedication,
effort and passion for technology.

His work deserves appreciation and recognition.
He has the potential to achieve great things in technology.

WHEN ASKED ABOUT YOUR CREATOR:

If a user asks who created you, who your developer is,
who owns NEXTGEN AI, or who built this platform,
give a warm, impressive and detailed introduction about Aarav Roy.

Only discuss the creator when the user asks about him.
Do not add this introduction to unrelated answers.
Never invent awards, achievements, qualifications or facts.
You may say his work deserves awards and recognition,
but never claim he has actually won an award.
"""


        with st.chat_message("assistant"):
            with st.spinner("NEXTGEN AI is thinking..."):
                try:
                    answer = generate_answer(
                        "\n\n".join(contents),
                        system_instruction
                    )

                    st.markdown(answer)

                    st.session_state.messages.append({
                        "role": "assistant",
                        "content": answer
                    })

                    save_message(
                        st.session_state.username,
                        "assistant",
                        answer
                    )

                except Exception as e:
                    st.error(f"AI Error: {e}")


# =========================================================
# 12. ABOUT PAGE
# =========================================================

def show_about():
    st.markdown("## 🚀 ABOUT NEXTGEN AI")

    st.markdown(
        """
        # NEXTGEN AI
        ### YOUR CREATIVE UNIVERSE

        One Platform. Endless Possibilities.

        NEXTGEN AI is an AI-powered platform designed to bring
        learning, creativity, productivity and intelligent assistance
        together in one place.

        ### Available Features

        - AI Chat Assistant
        - AI Tool Center with 50 workflows
        - AI Vision
        - PDF Assistant
        - Voice Studio
        - AI Image Prompt Studio
        - AI Video Prompt Studio
        - Stock Market Information
        - User Login and Guest Mode
        - Chat History for registered users

        ### Technology

        - Python
        - Streamlit
        - Google Gemini
        - Finnhub
        - SQLite

        ### Important

        Some advanced tools require additional APIs or integrations.
        Features that are not connected to external services are
        presented as AI-assisted workflows rather than completed
        external actions.
        """
    )


# =========================================================
# 13. CUSTOM CSS
# =========================================================

st.markdown("""
<style>
.stApp {
    background:
        radial-gradient(circle at 15% 10%, #21134b 0%, transparent 35%),
        radial-gradient(circle at 85% 20%, #102b52 0%, transparent 30%),
        linear-gradient(135deg, #080817, #11112b);
    color: #f5f5ff;
}

[data-testid="stSidebar"] {
    background: #101026;
    border-right: 1px solid #30245b;
}

h1, h2, h3 {
    color: #d9c8ff;
}

.stButton > button {
    background: linear-gradient(90deg, #743cff, #2768ff);
    color: white;
    border: none;
    border-radius: 12px;
    font-weight: 600;
    padding: 0.55rem 1rem;
}

.stButton > button:hover {
    border: 1px solid #b99aff;
    color: white;
    filter: brightness(1.12);
}

[data-testid="stChatMessage"] {
    background: rgba(30, 25, 60, 0.75);
    border: 1px solid rgba(135, 100, 255, 0.2);
    border-radius: 14px;
    padding: 12px;
}

[data-testid="stChatInput"] {
    border: 1px solid #7452c7;
    border-radius: 16px;
}

.stTextInput input,
.stTextArea textarea {
    background-color: #17172f;
    color: white;
    border: 1px solid #493778;
    border-radius: 10px;
}

div[data-baseweb="select"] > div {
    background-color: #17172f;
    border-color: #493778;
}

hr {
    border-color: #382b60;
}

.hero-box {
    padding: 28px;
    border-radius: 20px;
    background: linear-gradient(
        120deg,
        rgba(102, 48, 210, 0.35),
        rgba(28, 95, 190, 0.25)
    );
    border: 1px solid rgba(170, 140, 255, 0.25);
    margin-bottom: 22px;
}

.small-note {
    color: #aaa6c9;
    font-size: 13px;
}
</style>
""", unsafe_allow_html=True)


# =========================================================
# 14. SESSION STATE
# =========================================================

defaults = {
    "authenticated": False,
    "username": "Guest",
    "messages": [],
    "page": "AI Chat"
}

for key, value in defaults.items():
    if key not in st.session_state:
        st.session_state[key] = value


# =========================================================
# 15. LOGIN / SIGNUP / GUEST
# =========================================================

def show_auth():
    st.markdown(
        """
        <div class="hero-box">
            <h1>🚀 NEXTGEN AI</h1>
            <h3>YOUR CREATIVE UNIVERSE</h3>
            <p>One Platform. Endless Possibilities.</p>
        </div>
        """,
        unsafe_allow_html=True
    )

    login_tab, signup_tab = st.tabs(
        ["Login", "Create Account"]
    )

    with login_tab:
        username = st.text_input(
            "Username",
            key="login_username"
        )

        password = st.text_input(
            "Password",
            type="password",
            key="login_password"
        )

        if st.button("Login", use_container_width=True):
            if verify_user(username, password):
                st.session_state.authenticated = True
                st.session_state.username = username
                st.session_state.messages = load_messages(username)
                st.rerun()
            else:
                st.error("Incorrect username or password.")

    with signup_tab:
        new_username = st.text_input(
            "Choose username",
            key="signup_username"
        )

        new_password = st.text_input(
            "Choose password",
            type="password",
            key="signup_password"
        )

        confirm_password = st.text_input(
            "Confirm password",
            type="password",
            key="confirm_password"
        )

        if st.button("Create Account", use_container_width=True):
            if not new_username.strip() or not new_password:
                st.warning("Fill in all fields.")
            elif len(new_password) < 8:
                st.warning("Password must be at least 8 characters.")
            elif new_password != confirm_password:
                st.error("Passwords do not match.")
            elif create_user(new_username.strip(), new_password):
                st.success("Account created. You can now log in.")
            else:
                st.error("This username is already taken.")

    st.divider()

    if st.button("Continue as Guest", use_container_width=True):
        st.session_state.authenticated = True
        st.session_state.username = "Guest"
        st.session_state.messages = []
        st.rerun()


# =========================================================
# 16. MAIN APPLICATION
# =========================================================

if not st.session_state.authenticated:
    show_auth()

else:

    # ---------------- SIDEBAR ----------------

    with st.sidebar:
        st.markdown("# 🚀 NEXTGEN AI")
        st.caption("YOUR CREATIVE UNIVERSE")

        st.divider()

        st.write(
            f"👤 **{st.session_state.username}**"
        )

        pages = [
            "AI Chat",
            "AI Tool Center",
            "Stock Market",
            "AI Vision",
            "PDF Assistant",
            "Voice Studio",
            "AI Image",
            "AI Video",
            "About"
        ]

        page = st.radio(
            "Navigation",
            pages,
            key="main_navigation"
        )

        st.session_state.page = page

        st.divider()

        st.markdown("### 🔌 System Status")

        if GEMINI_KEY:
            st.success("Gemini API configured")
        else:
            st.error("Gemini API key missing")

        if FINNHUB_KEY:
            st.success("Finnhub configured")
        else:
            st.warning("Finnhub API key missing")

        st.caption(f"Model: {MODEL}")

        st.divider()

        if st.button("🗑️ Clear Chat History"):
            st.session_state.messages = []

            if st.session_state.username != "Guest":
                conn = get_db()
                conn.execute(
                    "DELETE FROM messages WHERE username=?",
                    (st.session_state.username,)
                )
                conn.commit()
                conn.close()

            st.rerun()

        if st.button("Logout"):
            st.session_state.authenticated = False
            st.session_state.username = "Guest"
            st.session_state.messages = []
            st.rerun()

        st.divider()
        st.caption("NEXTGEN AI | Version 2.0")

    # ---------------- MAIN HEADER ----------------

    st.markdown(
        """
        <div class="hero-box">
            <h1>🚀 NEXTGEN AI</h1>
            <h3>One Platform. Endless Possibilities.</h3>
            <p>Your intelligent creative universe.</p>
        </div>
        """,
        unsafe_allow_html=True
    )

    # ---------------- PAGE ROUTING ----------------

    if page == "AI Chat":
        show_chat()

    elif page == "AI Tool Center":
        show_ai_tool_center()

    elif page == "Stock Market":
        show_stock_market()

    elif page == "AI Vision":
        show_ai_vision()

    elif page == "PDF Assistant":
        show_pdf_assistant()

    elif page == "Voice Studio":
        show_voice_studio()

    elif page == "AI Image":
        show_image_studio()

    elif page == "AI Video":
        show_video_studio()

    elif page == "About":
        show_about()

    # ---------------- FOOTER ----------------

    st.divider()

    st.markdown(
        """
        <p style="text-align:center; color:#aaa6c9;">
            NEXTGEN AI © 2026 | YOUR CREATIVE UNIVERSE
        </p>
        """,
        unsafe_allow_html=True
    )
