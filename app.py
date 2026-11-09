import os
import io
import streamlit as st


API_KEY = ""

try:
    API_KEY = st.secrets.get("GEMINI_API_KEY", "")
except Exception:
    pass

if not API_KEY:
    API_KEY = os.getenv("GEMINI_API_KEY", "")
from dotenv import load_dotenv
from google import genai
from PIL import Image
from pypdf import PdfReader

from google.genai import types


# ==========================================
# NEXTGEN AI - VERSION 3.0
# Gemini + Auto-Pilot
# ==========================================

load_dotenv()

st.set_page_config(
    page_title="NEXTGEN AI",
    page_icon="🚀",
    layout="wide",
    initial_sidebar_state="expanded"
)

API_KEY = ""

try:
    API_KEY = st.secrets.get("GEMINI_API_KEY", "")
except Exception:
    pass

if not API_KEY:
    API_KEY = os.getenv("GEMINI_API_KEY", "")
MODEL = "gemini-2.5-flash-lite"


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
    background: linear-gradient(90deg, #7c3aed, #2563eb);
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


# ==========================================
# GEMINI CONNECTION
# ==========================================

def get_client():
    if not API_KEY:
        raise ValueError("GEMINI_API_KEY नहीं मिली।")

    if st.session_state.client is None:
        st.session_state.client = genai.Client(
            api_key=API_KEY,
            http_options=types.HttpOptions(timeout=30000)
        )

    return st.session_state.client


# ==========================================
# AUTO-PILOT AI ENGINE
# ==========================================

def generate_answer(contents):
    client = get_client()

    response = client.models.generate_content(
        model=MODEL,
        contents=contents,
        config=types.GenerateContentConfig(
            max_output_tokens=256,
            temperature=0.7
        )
    )

    if not response.text:
        raise ValueError("Gemini ने खाली जवाब दिया।")

    st.session_state.last_provider = "Gemini Direct"
    return response.text


# ==========================================
# SIDEBAR
# ==========================================

st.sidebar.markdown("# 🚀 NEXTGEN AI")
st.sidebar.caption("YOUR CREATIVE UNIVERSE")

st.sidebar.markdown("---")

page = st.sidebar.radio(
    "NAVIGATION",
    [
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
st.sidebar.caption("AI Engine: Gemini Direct")
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

st.markdown("""
<div class="hero">
    <h1>🚀 NEXTGEN AI</h1>
    <h3>One Platform. Endless Possibilities.</h3>
    <p>Your intelligent AI universe.</p>
</div>
""", unsafe_allow_html=True)


# ==========================================
# PAGE 1: AI CHAT
# ==========================================

if page == "AI Chat":

    st.header("💬 AI Chat Assistant")

    st.caption(
        "Ask questions, learn, create and explore."
    )

    for msg in st.session_state.messages:
        with st.chat_message(msg["role"]):
            st.markdown(msg["content"])

    prompt = st.chat_input(
        "Message NEXTGEN AI..."
    )

    if prompt:

        st.session_state.messages.append({
            "role": "user",
            "content": prompt
        })

        with st.chat_message("user"):
            st.markdown(prompt)

        with st.chat_message("assistant"):

            try:

                recent_messages = (
                    st.session_state.messages[-10:]
                )

                history = "\n\n".join(
                    f'{m["role"].upper()}: {m["content"]}'
                    for m in recent_messages
                )

                contents = (
                    "You are NEXTGEN AI, a helpful, "
                    "intelligent and friendly AI assistant. "
                    "Answer clearly and accurately. "
                    "Use the user's language when possible.\n\n"
                    + history
                )

                with st.spinner("NEXTGEN AI is thinking..."):
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

        image = Image.open(
            io.BytesIO(uploaded_image.getvalue())
        )

        st.image(
            image,
            caption="Uploaded Image",
            use_container_width=True
        )

        if st.button("🔍 Analyze Image"):

            try:

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
                page.extract_text() or ""
                for page in reader.pages
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
                    st.warning("Please enter a question.")

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
            st.error(f"Could not read PDF: {e}")


# ==========================================
# PAGE 4: AI IMAGE
# ==========================================

elif page == "AI Image":

    st.header("🎨 AI Image Generator")

    st.write(
        "Create images from your imagination."
    )

    image_prompt = st.text_area(
        "Describe the image you want to create"
    )

    st.info(
        "Image generation API अभी कनेक्ट नहीं है। "
        "इसे चालू करने के लिए अलग image-generation service चाहिए।"
    )

    st.button(
        "✨ Generate Image",
        disabled=True
    )


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
    ### Welcome to NEXTGEN AI

    NEXTGEN AI is an AI-powered creative platform.

    ### Our Features

    - AI Chat
    - AI Vision
    - PDF Assistant
    - AI Image Interface
    - AI Video Interface
    - Auto-Pilot Retry System

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

st.markdown("""
<div class="footer">
    NEXTGEN AI © 2026
    <br>
    Powered by Artificial Intelligence
</div>
""", unsafe_allow_html=True)
