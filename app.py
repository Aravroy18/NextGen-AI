import os
import io
import time
import requests
import streamlit as st
import streamlit.components.v1 as components
import json

from dotenv import load_dotenv
from google import genai
from google.genai import types
from PIL import Image
from pypdf import PdfReader
from voice_call import create_live_token
from streamlit_mic_recorder import speech_to_text


# ==========================================
# NEXTGEN AI - VERSION 4.0
# ==========================================

load_dotenv()

st.set_page_config(
    page_title="NEXTGEN AI",
    page_icon="🚀",
    layout="wide",
    initial_sidebar_state="expanded"
)

# ==========================================
# API CONFIGURATION
# ==========================================

API_KEY = ""

try:
    API_KEY = st.secrets.get("GEMINI_API_KEY", "")
except Exception:
    pass

if not API_KEY:
    API_KEY = os.getenv("GEMINI_API_KEY", "")

MODEL = "gemini-3.5-flash-lite"


# ==========================================
# SYSTEM INSTRUCTION
# ==========================================

SYSTEM_INSTRUCTION = """
You are NEXTGEN AI, an independent AI platform.

PLATFORM IDENTITY:
- Platform Name: NEXTGEN AI
- Creator: Arav
- Developer: Arav
- Owner: Arav

IDENTITY RULES:

If the user asks who created, developed, built,
or owns NEXTGEN AI, answer:

"NEXTGEN AI was created and developed by Arav.
Arav is the owner of NEXTGEN AI."

In Hindi:

"NEXTGEN AI को Arav ने बनाया और विकसित किया है।
Arav ही NEXTGEN AI के मालिक हैं।"

Google Gemini may provide the underlying AI technology.
However, Arav is the creator, developer, and owner
of the NEXTGEN AI platform.

Answer clearly, accurately, and politely.
Use the user's language whenever possible.
"""


# ==========================================
# DESIGN
# ==========================================

st.markdown("""
<style>

.stApp {
    background: linear-gradient(
        135deg,
        #080817,
        #11112b,
        #080817
    );
    color: white;
}

[data-testid="stSidebar"] {
    background: #101026;
    border-right: 1px solid #29294f;
}

h1, h2, h3 {
    color: #a78bfa !important;
}

p, label {
    color: #e2e8f0;
}

.stButton button {
    background: linear-gradient(
        90deg,
        #7c3aed,
        #2563eb
    );
    color: white;
    border: none;
    border-radius: 12px;
    padding: 10px 20px;
    font-weight: bold;
}

[data-testid="stChatMessage"] {
    background: #15152e;
    border: 1px solid #29294f;
    border-radius: 14px;
}

.hero {
    padding: 25px;
    border-radius: 18px;
    background: linear-gradient(
        120deg,
        #171735,
        #252052,
        #10244b
    );
    border: 1px solid #454078;
    margin-bottom: 25px;
}

.footer {
    text-align: center;
    color: #8888aa;
    padding: 20px;
}

</style>
""", unsafe_allow_html=True)


# ==========================================
# SESSION STATE
# ==========================================

if "messages" not in st.session_state:
    st.session_state.messages = []

if "client" not in st.session_state:
    st.session_state.client = None

if "last_provider" not in st.session_state:
    st.session_state.last_provider = "Not used yet"

if "live_token" not in st.session_state:
    st.session_state.live_token = None


# ==========================================
# GEMINI CONNECTION
# ==========================================

def get_client():

    if not API_KEY:
        raise ValueError(
            "GEMINI_API_KEY नहीं मिली। "
            "Streamlit Secrets में API key जोड़ें।"
        )

    if st.session_state.client is None:

        st.session_state.client = genai.Client(
            api_key=API_KEY,
            http_options=types.HttpOptions(
                timeout=30000
            )
        )

    return st.session_state.client


# ==========================================
# AI ENGINE
# ==========================================

def generate_answer(contents, use_web=False):

    client = get_client()

    config = {
        "system_instruction": SYSTEM_INSTRUCTION,
        "max_output_tokens": 2048,
        "temperature": 0.7
    }

    # Enable Google Search grounding
    if use_web:
        config["tools"] = [
            types.Tool(
                google_search=types.GoogleSearch()
            )
        ]

    response = client.models.generate_content(
        model=MODEL,
        contents=contents,
        config=types.GenerateContentConfig(**config)
    )

    if not response.text:
        raise ValueError("AI ने खाली जवाब दिया।")

    answer = response.text

    # Extract grounded web sources
    if use_web and response.candidates:
        metadata = getattr(
            response.candidates[0],
            "grounding_metadata",
            None
        )

        chunks = getattr(
            metadata,
            "grounding_chunks",
            []
        ) or []

        sources = []
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
            answer += "\n\n**Sources:**\n" + "\n".join(sources)

    st.session_state.last_provider = (
        "Gemini + Google Search" if use_web
        else "Gemini Direct"
    )

    return answer


# ==========================================
# TEXT TO SPEECH ENGINE
# ==========================================

def show_voice_player(text, auto_play=True):

    safe_text = json.dumps(text, ensure_ascii=False)

    auto = "true" if auto_play else "false"

    voice_html = f"""
    <div style="
        background:#15152e;
        padding:14px;
        border-radius:14px;
        border:1px solid #454078;
        display:flex;
        gap:8px;
        flex-wrap:wrap;
    ">

      <button onclick="speakText()">▶ Play</button>
      <button onclick="window.speechSynthesis.pause()">⏸ Pause</button>
      <button onclick="window.speechSynthesis.resume()">▶ Resume</button>
      <button onclick="window.speechSynthesis.cancel()">⏹ Stop</button>

    </div>

    <script>
    const textToSpeak = {safe_text};
    const autoPlay = {auto};

    function speakText() {{
        window.speechSynthesis.cancel();

        const speech = new SpeechSynthesisUtterance(textToSpeak);

        speech.lang = /[\\u0900-\\u097F]/.test(textToSpeak)
            ? "hi-IN" : "en-IN";

        speech.rate = 1;
        speech.pitch = 1;

        window.speechSynthesis.speak(speech);
    }}

    window.onload = function() {{
        if (autoPlay) {{
            speakText();
        }}
    }};
    </script>
    """

    components.html(voice_html, height=85)

# ==========================================
# SIDEBAR
# ==========================================

st.sidebar.markdown("# 🚀 NEXTGEN AI")
st.sidebar.caption("YOUR CREATIVE UNIVERSE")

st.sidebar.markdown("---")
page = st.sidebar.radio(
    "NAVIGATION",
    [
        "🏠 Dashboard",
        "AI Chat",
        "AI Vision",
        "PDF Assistant",
        "AI Image",
        "AI Video",
        "About"
    ]
)


st.sidebar.markdown("---")
st.sidebar.markdown("### SYSTEM STATUS")

if API_KEY:
    st.sidebar.success("API KEY CONFIGURED")
else:
    st.sidebar.error("API KEY MISSING")

st.sidebar.caption("AI Engine: Gemini")
st.sidebar.caption(
    f"Last Provider: {st.session_state.last_provider}"
)

st.sidebar.markdown("---")

if st.sidebar.button("🗑️ Clear All Chats"):

    st.session_state.messages = []
    st.rerun()



# ==========================================
# MAIN HEADER
# ==========================================

st.title("🚀NEXTGEN AI")

st.subheader("One Platform. Endless Possibilities.")

st.write("Your intelligent AI universe.")


# ==========================================
# PAGE 0: DASHBOARD
# ==========================================

if page == "🏠 Dashboard":

    st.markdown("""
    <div style="
        background:linear-gradient(120deg,#090920,#25105c,#101f52);
        padding:40px;
        border-radius:24px;
        border:1px solid #7857ff;
        box-shadow:0 0 30px #5125a855;
    ">
        <h1 style="color:white;font-size:42px;">
            🚀 NEXTGEN AI
        </h1>
        <h2 style="color:#c4b5fd;">
            Welcome to Your AI Universe
        </h2>
        <p style="color:#e2e8f0;font-size:18px;">
            One Platform. Endless Possibilities.
        </p>
        <p style="color:#a5b4fc;">
            Discover the future of Artificial Intelligence.
        </p>
    </div>
    """, unsafe_allow_html=True)

    st.write("")

    st.subheader("⚡ SYSTEM OVERVIEW")

    col1, col2, col3, col4 = st.columns(4)

    with col1:
        st.metric("AI Messages", len(st.session_state.messages))

    with col2:
        st.metric("AI Tools", "5")

    with col3:
        st.metric("AI Engine", "Gemini")

    with col4:
        st.metric("Platform", "ONLINE" if API_KEY else "OFFLINE")

    st.markdown("---")

    st.subheader("🌌 EXPLORE YOUR AI UNIVERSE")

    c1, c2, c3 = st.columns(3)

    with c1:
        st.markdown("""
        <div style="background:linear-gradient(145deg,#171735,#29205b);
        padding:25px;border-radius:18px;border:1px solid #7657ff;">
        <h2>💬 AI CHAT</h2>
        <p>Meet your intelligent AI assistant.</p>
        <p style="color:#a78bfa;">Ask • Learn • Create</p>
        </div>
        """, unsafe_allow_html=True)

    with c2:
        st.markdown("""
        <div style="background:linear-gradient(145deg,#171735,#173b60);
        padding:25px;border-radius:18px;border:1px solid #398bff;">
        <h2>👁️ AI VISION</h2>
        <p>Let AI understand your images.</p>
        <p style="color:#93c5fd;">Upload • Analyze • Discover</p>
        </div>
        """, unsafe_allow_html=True)

    with c3:
        st.markdown("""
        <div style="background:linear-gradient(145deg,#171735,#44205b);
        padding:25px;border-radius:18px;border:1px solid #c084fc;">
        <h2>📄 PDF AI</h2>
        <p>Explore and understand PDF documents.</p>
        <p style="color:#d8b4fe;">Read • Ask • Understand</p>
        </div>
        """, unsafe_allow_html=True)

    st.write("")

    c4, c5, c6 = st.columns(3)

    with c4:
        st.markdown("""
        <div style="background:linear-gradient(145deg,#171735,#553018);
        padding:25px;border-radius:18px;border:1px solid #fb923c;">
        <h2>🎨 AI IMAGE</h2>
        <p>Transform imagination into images.</p>
        <p style="color:#fdba74;">Imagine • Generate</p>
        </div>
        """, unsafe_allow_html=True)

    with c5:
        st.markdown("""
        <div style="background:linear-gradient(145deg,#171735,#173e46);
        padding:25px;border-radius:18px;border:1px solid #2dd4bf;">
        <h2>🎬 AI VIDEO</h2>
        <p>Explore AI-powered video creation.</p>
        <p style="color:#5eead4;">Create • Visualize</p>
        </div>
        """, unsafe_allow_html=True)

    with c6:
        st.markdown("""
        <div style="background:linear-gradient(145deg,#171735,#512044);
        padding:25px;border-radius:18px;border:1px solid #f472b6;">
        <h2>🎙️ LIVE VOICE</h2>
        <p>Experience real-time AI conversations.</p>
        <p style="color:#f9a8d4;">Speak • Interact</p>
        </div>
        """, unsafe_allow_html=True)

    st.markdown("---")

    st.markdown("""
    <div style="text-align:center;padding:20px;">
        <h2 style="color:#a78bfa;">THE FUTURE STARTS HERE</h2>
        <p>Powered by Artificial Intelligence | Created by Arav</p>
    </div>
    """, unsafe_allow_html=True)
# ==========================================
# PAGE 1: AI CHAT
# ==========================================

elif page == "AI Chat":

    st.header("💬 AI Chat Assistant")

    st.caption(
        "Ask questions, learn, create and explore."
    )

    # CHAT HISTORY
    for msg in st.session_state.messages:
        with st.chat_message(msg["role"]):
            st.markdown(msg["content"])

    # LIVE VOICE CALL
    st.markdown("---")

    if st.button("📞 Start Live Call"):
        st.session_state.live_token = None

        try:
            if not API_KEY:
                st.error("GEMINI_API_KEY missing")
            else:
                with st.spinner("Generating fresh Live Token..."):
                    new_token = create_live_token(API_KEY)

                if new_token:
                    st.session_state.live_token = new_token
                    st.success("Fresh Live Token generated!")
                else:
                    st.error("Token generate नहीं हुआ।")

        except Exception as e:
            st.session_state.live_token = None
            st.error(f"Live API Error: {e}")

    # --------------------------------------
    # CHAT HISTORY
    # --------------------------------------

    for msg in st.session_state.messages:

        with st.chat_message(msg["role"]):
            st.markdown(msg["content"])

    # --------------------------------------
    # LIVE VOICE CALL
    # --------------------------------------

        # Live Voice
    st.markdown("---")

    if st.button("📞 Start Live Call"):

        st.session_state.live_token = None

        try:
            if not API_KEY:
                st.error("GEMINI_API_KEY missing")

            else:
                with st.spinner("Generating fresh Live Token..."):
                    new_token = create_live_token(API_KEY)

                if not new_token:
                    st.error("Token generate नहीं हुआ।")

                else:
                    st.session_state.live_token = new_token
                    st.success("Fresh Live Token generated!")

        except Exception as e:
            st.session_state.live_token = None
            st.error(f"Live API Error: {e}")

    if st.session_state.live_token:

        try:
            with open(
                "live_voice.html",
                "r",
                encoding="utf-8"
            ) as f:
                voice_html = f.read()

            if "__LIVE_TOKEN__" not in voice_html:
                st.error(
                    "HTML में __LIVE_TOKEN__ placeholder नहीं मिला।"
                )

            else:
                voice_html = voice_html.replace(
                    "__LIVE_TOKEN__",
                    st.session_state.live_token
                )

                if "__LIVE_TOKEN__" in voice_html:
                    st.error("Token HTML में replace नहीं हुआ।")

                else:
                    components.html(
                        voice_html,
                        height=600,
                        scrolling=True
                    )

        except Exception as e:
            st.error(f"Voice Interface Error: {e}")
    # --------------------------------------
    # MICROPHONE
    # --------------------------------------

    st.markdown("---")
    st.subheader("🎤 Voice Input")

    voice_text = speech_to_text(
        language="hi-IN",
        start_prompt="🎤 Start Speaking",
        stop_prompt="⏹️ Stop Recording",
        just_once=True,
        key="nextgen_chat_mic"
    )

    # --------------------------------------
    # CHAT INPUT + GALLERY
    # --------------------------------------

    chat_value = st.chat_input(
        "Message NEXTGEN AI...",
        accept_file=True,
        file_type=["png", "jpg", "jpeg", "webp"]
    )

    prompt = ""
    uploaded_image = None

    # Text and gallery input
    if chat_value:

        prompt = chat_value.text or ""

        if chat_value.files:

            try:
                uploaded_image = Image.open(
                    io.BytesIO(
                        chat_value.files[0].getvalue()
                    )
                ).convert("RGB")

            except Exception as e:
                st.error(f"Image Upload Error: {e}")

    # Microphone input
    if voice_text and not prompt:
        prompt = voice_text

    # --------------------------------------
    # SEND MESSAGE TO AI
    # --------------------------------------

    if prompt or uploaded_image:

        if not prompt:
            prompt = "Please analyze this image."

        user_message = prompt

        if uploaded_image:
            user_message += " [Image attached]"

        st.session_state.messages.append({
            "role": "user",
            "content": user_message
        })

        with st.chat_message("user"):

            st.markdown(prompt)

            if uploaded_image:
                st.image(
                    uploaded_image,
                    caption="Attached Image",
                    width=300
                )

        # AI RESPONSE
                # AI RESPONSE
        with st.chat_message("assistant"):
            try:
                recent_messages = (
                    st.session_state.messages[-10:]
                )

                history = "\n\n".join(
                    f'{m["role"].upper()}: {m["content"]}'
                    for m in recent_messages
                )

                if uploaded_image:
                    contents = [
                        history,
                        uploaded_image
                    ]
                else:
                    contents = history

                with st.spinner(
                    "NEXTGEN AI is thinking..."
                ):
                    answer = generate_answer(contents)

                st.markdown(answer)

            except Exception as e:
                answer = f"AI Error: {str(e)}"
                st.error(answer)

        st.session_state.messages.append({
            "role": "assistant",
            "content": answer
        })

                            

            


                

# ==========================================
# PAGE 2: AI VISION
# ==========================================

elif page == "AI Vision":

    st.header("👁️ AI Vision")

    st.write(
        "Upload an image and let AI understand it."
    )

    uploaded_image = st.file_uploader(
        "Upload your image",
        type=["png", "jpg", "jpeg", "webp"]
    )

    question = st.text_input(
        "What would you like to know about this image?",
        key="vision_question"
    )

    if uploaded_image:

        try:

            image = Image.open(
                io.BytesIO(uploaded_image.getvalue())
            ).convert("RGB")

            st.image(
                image,
                caption="Uploaded Image",
                use_container_width=True
            )

            if st.button("🔍 Analyze Image"):

                contents = [
                    question or "Describe this image in detail.",
                    image
                ]

                with st.spinner("AI is analyzing..."):

                    answer = generate_answer(contents)

                st.success("Analysis complete")
                st.markdown(answer)

        except Exception as e:

            st.error(f"Vision Error: {e}")


# ==========================================
# PAGE 3: PDF ASSISTANT
# ==========================================

elif page == "PDF Assistant":

    st.header("📄 PDF Assistant")

    st.write(
        "Upload a PDF and ask questions about its content."
    )

    pdf_file = st.file_uploader(
        "Upload PDF Document",
        type=["pdf"]
    )

    if pdf_file:

        try:

            reader = PdfReader(pdf_file)

            pdf_text = "\n".join(
                pdf_page.extract_text() or ""
                for pdf_page in reader.pages
            )

            st.success(
                f"PDF Loaded: {len(reader.pages)} Pages"
            )

            st.text_area(
                "PDF Preview",
                pdf_text[:5000],
                height=180
            )

            question = st.text_input(
                "Ask something about your PDF",
                key="pdf_question"
            )

            if st.button("🤖 Ask AI About PDF"):

                if not question.strip():

                    st.warning(
                        "Please enter a question."
                    )

                elif not pdf_text.strip():

                    st.warning(
                        "No readable text found in this PDF."
                    )

                else:

                    contents = (
                        "Answer using the following PDF content. "
                        "If the answer is not present, say so.\n\n"
                        + pdf_text[:40000]
                        + "\n\nQuestion: "
                        + question
                    )

                    try:

                        with st.spinner("Reading PDF..."):

                            answer = generate_answer(contents)

                        st.markdown(answer)

                    except Exception as e:

                        st.error(f"PDF Error: {e}")

        except Exception as e:

            st.error(
                f"Could not read PDF: {e}"
            )


elif page == "AI Image":
    st.title("🎨 AI Image Generator")
    st.write("Describe your imagination and generate an AI image.")

    image_prompt = st.text_area(
        "Describe your image",
        placeholder="A futuristic city at night, neon lights, cinematic..."
    )

    if st.button("✨ Generate Image"):
        if not image_prompt.strip():
            st.warning("Please enter an image description.")
        else:
            BASE_URL = "https://aihorde.net/api/v2"

            headers = {
                "apikey": "0000000000",
                "Client-Agent": "NEXTGEN_AI:1.0:Arav"
            }

            payload = {
                "prompt": image_prompt,
                "params": {
                    "width": 512,
                    "height": 512,
                    "steps": 20,
                    "n": 1
                },
                "nsfw": False,
                "censor_nsfw": True
            }

            try:
                with st.spinner("Submitting your image request..."):
                    response = requests.post(
                        f"{BASE_URL}/generate/async",
                        headers=headers,
                        json=payload,
                        timeout=30
                    )
                    response.raise_for_status()
                    request_id = response.json()["id"]

                progress = st.progress(0)
                status_text = st.empty()
                completed = False

                for attempt in range(60):
                    time.sleep(5)

                    check = requests.get(
                        f"{BASE_URL}/generate/check/{request_id}",
                        headers=headers,
                        timeout=30
                    )
                    check.raise_for_status()
                    check_data = check.json()

                    progress.progress((attempt + 1) / 60)

                    if check_data.get("done"):
                        completed = True
                        break

                    status_text.write(
                        f"Generating image... Please wait ({attempt + 1}/60)"
                    )

                if not completed:
                    st.warning(
                        "Image is taking longer than expected. "
                        "Please try again later."
                    )
                else:
                    with st.spinner("Loading your image..."):
                        result = requests.get(
                            f"{BASE_URL}/generate/status/{request_id}",
                            headers=headers,
                            timeout=60
                        )
                        result.raise_for_status()

                        generations = result.json().get("generations", [])

                        if not generations:
                            st.error("No image was returned. Please try again.")
                        else:
                            image_url = generations[0].get("img")

                            if image_url:
                                image_response = requests.get(
                                    image_url,
                                    timeout=60
                                )
                                image_response.raise_for_status()
                                image_bytes = image_response.content

                                st.success("Image generated successfully!")
                                st.image(image_bytes, use_container_width=True)

                                st.download_button(
                                    "⬇️ Download Image",
                                    data=image_bytes,
                                    file_name="nextgen_ai_image.png",
                                    mime="image/png"
                                )
                            else:
                                st.error("Image URL was not returned.")

            except requests.exceptions.RequestException as e:
                st.error(f"Image service connection error: {e}")
            except Exception as e:
                st.error(f"Image Generation Error: {e}")

        

                

                    

        




# ==========================================
# PAGE 5: AI VIDEO
# ==========================================

elif page == "AI Video":

    st.header("🎬 AI Video Generator")

    st.write(
        "Turn your ideas into videos."
    )

    video_prompt = st.text_area(
        "Describe your video idea"
    )

    st.info(
        "Video generation API अभी कनेक्ट नहीं है। "
        "इसे भविष्य में जोड़ेंगे।"
    )

    st.button(
        "🎥 Generate Video",
        disabled=True
    )


# ==========================================
# PAGE 6: ABOUT
# ==========================================

elif page == "About":

    st.header("🌍 About NEXTGEN AI")

    st.markdown("""
## Welcome to NEXTGEN AI

NEXTGEN AI is an AI-powered creative platform.

### Our Features

- AI Chat
- Live Voice
- AI Vision
- PDF Assistant
- AI Image Interface
- AI Video Interface

### Creator & Developer

Arav

### Technology

- Python
- Streamlit
- Google Gemini API
- Pillow
- PyPDF

### Our Vision

One Platform. Endless Possibilities.
""")


# ==========================================
# FOOTER
# ==========================================

st.markdown("---")

footer_html = (
    '<div class="footer">'
    'NEXTGEN AI © 2026<br>'
    'Created by Arav<br>'
    'Powered by Artificial Intelligence'
    '</div>'
)

st.markdown(
    footer_html,
    unsafe_allow_html=True
)
