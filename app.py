
import os
import io
import streamlit as st
from PIL import Image
from google import genai
from google.genai import types
from pypdf import PdfReader

st.set_page_config(
    page_title="NEXTGEN AI",
    page_icon="✨",
    layout="wide"
)

MODEL = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")

st.markdown("""
<style>
.stApp {background:#ffffff;color:#171717;}
[data-testid="stSidebar"] {background:#f8fafc;}
.block-container {max-width:1250px;padding-top:2rem;}
.hero {padding:25px;border:1px solid #e5e7eb;border-radius:20px;
background:linear-gradient(135deg,#fff,#f2f5ff);}
.stButton button {border-radius:12px;}
</style>
""", unsafe_allow_html=True)


def get_api_key():
    try:
        key = st.secrets.get("GEMINI_API_KEY", "")
    except Exception:
        key = ""
    return key or os.getenv("GEMINI_API_KEY", "")


@st.cache_resource
def get_client(api_key):
    return genai.Client(api_key=api_key)


def ask_model(prompt, image=None):
    api_key = get_api_key()
    if not api_key:
        raise RuntimeError("GEMINI_API_KEY सेट नहीं है।")

    client = get_client(api_key)
    contents = [prompt] if image is None else [prompt, image]

    response = client.models.generate_content(
        model=MODEL,
        contents=contents,
        config=types.GenerateContentConfig(
            temperature=0.6,
            max_output_tokens=2048
        )
    )

    if not response.text:
        raise RuntimeError("AI से खाली जवाब मिला।")
    return response.text


def show_error(error):
    st.error(str(error))


with st.sidebar:
    st.title("✨ NEXTGEN AI")
    st.caption("One Platform. Endless Possibilities.")
    page = st.radio("WORKSPACE", [
        "Home",
        "AI Chat",
        "AI Vision",
        "PDF Assistant",
        "AI Image",
        "AI Video",
        "Study Assistant",
        "Text Tools",
        "About"
    ])
    st.divider()
    st.caption("Model: " + MODEL)
    if get_api_key():
        st.success("API Connected")
    else:
        st.warning("API Key Not Configured")


# HOME
if page == "Home":
    st.markdown("""
    <div class="hero">
    <h1>Welcome to NEXTGEN AI ✨</h1>
    <p>Your intelligent AI workspace.</p>
    </div>
    """, unsafe_allow_html=True)

    st.subheader("Explore your workspace")

    features = [
        "💬 AI Chat",
        "👁️ AI Vision",
        "📄 PDF Assistant",
        "🎨 AI Image",
        "🎬 AI Video",
        "📚 Study Assistant",
        "✍️ Text Tools",
        "ℹ️ About"
    ]

    cols = st.columns(4)
    for i, feature in enumerate(features):
        with cols[i % 4]:
            st.container(border=True).markdown("### " + feature)


# AI CHAT
elif page == "AI Chat":
    st.title("💬 AI Chat")
    st.caption("Ask anything. Hindi and English supported.")

    if "chat_messages" not in st.session_state:
        st.session_state.chat_messages = []

    if st.button("Clear Chat"):
        st.session_state.chat_messages = []
        st.rerun()

    for msg in st.session_state.chat_messages:
        with st.chat_message(msg["role"]):
            st.markdown(msg["content"])

    prompt = st.chat_input("Message NEXTGEN AI...")

    if prompt:
        st.session_state.chat_messages.append({
            "role": "user",
            "content": prompt
        })

        with st.chat_message("user"):
            st.markdown(prompt)

        with st.chat_message("assistant"):
            with st.spinner("Thinking..."):
                try:
                    history = st.session_state.chat_messages[-12:]
                    conversation = "\n".join(
                        f'{m["role"]}: {m["content"]}'
                        for m in history
                    )

                    answer = ask_model(
                        "You are NEXTGEN AI, a helpful assistant. "
                        "Reply in the user's language. "
                        "Do not guess current facts you cannot verify.\n\n"
                        + conversation
                    )

                    st.markdown(answer)
                    st.session_state.chat_messages.append({
                        "role": "assistant",
                        "content": answer
                    })

                except Exception as e:
                    show_error(e)


# AI VISION
elif page == "AI Vision":
    st.title("👁️ AI Vision")
    st.write("Upload an image and ask questions.")

    image_file = st.file_uploader(
        "Upload Image",
        type=["png", "jpg", "jpeg", "webp"]
    )

    question = st.text_area(
        "Your question",
        value="Describe this image."
    )

    if image_file:
        image = Image.open(image_file).convert("RGB")
        st.image(image, use_container_width=True)

        if st.button("Analyse Image"):
            with st.spinner("Analysing..."):
                try:
                    st.markdown(ask_model(question, image))
                except Exception as e:
                    show_error(e)


# PDF ASSISTANT
elif page == "PDF Assistant":
    st.title("📄 PDF Assistant")

    pdf_file = st.file_uploader("Upload PDF", type=["pdf"])

    if pdf_file:
        try:
            reader = PdfReader(io.BytesIO(pdf_file.getvalue()))
            pdf_text = "\n".join(
                page.extract_text() or ""
                for page in reader.pages
            )

            st.success(f"{len(reader.pages)} pages loaded")

            question = st.text_area("Ask about this PDF")

            if st.button("Ask PDF") and question.strip():
                with st.spinner("Reading PDF..."):
                    answer = ask_model(
                        "Answer using this PDF. If the answer is missing, say so.\n"
                        + pdf_text[:60000]
                        + "\nQuestion: " + question
                    )
                    st.markdown(answer)

        except Exception as e:
            show_error(e)


# AI IMAGE
elif page == "AI Image":
    st.title("🎨 AI Image Prompt Studio")
    st.info("यह संस्करण image prompt बनाता है, image render नहीं करता।")

    subject = st.text_input("Describe your image")

    style = st.selectbox("Style", [
        "Cinematic Realistic",
        "3D Animation",
        "Anime",
        "Digital Art",
        "Photorealistic"
    ])

    ratio = st.selectbox("Aspect Ratio", [
        "9:16", "16:9", "1:1", "4:5"
    ])

    if st.button("Generate Image Prompt") and subject.strip():
        try:
            prompt = ask_model(
                f"Create a detailed image generation prompt. "
                f"Subject: {subject}. Style: {style}. Ratio: {ratio}. "
                "Include lighting, composition, details and a negative prompt."
            )
            st.markdown("### Generated Prompt")
            st.write(prompt)
            st.download_button(
                "Download Prompt",
                prompt,
                file_name="image_prompt.txt"
            )
        except Exception as e:
            show_error(e)


# AI VIDEO
elif page == "AI Video":
    st.title("🎬 AI Video Prompt Studio")
    st.info("यह वीडियो prompt बनाता है, MP4 render नहीं करता।")

    idea = st.text_area("Describe your video idea")

    duration = st.selectbox(
        "Duration",
        ["20 seconds", "25 seconds", "30 seconds"]
    )

    ratio = st.selectbox(
        "Video Ratio",
        ["9:16 Vertical", "16:9 Landscape", "1:1 Square"]
    )

    if st.button("Generate Video Prompt") and idea.strip():
        try:
            prompt = ask_model(
                f"Create a detailed single-generation AI video prompt. "
                f"Duration: {duration}. Ratio: {ratio}. Idea: {idea}. "
                "Describe camera motion, lighting and continuous movement."
            )
            st.markdown("### Video Prompt")
            st.write(prompt)
            st.download_button(
                "Download Prompt",
                prompt,
                file_name="video_prompt.txt"
            )
        except Exception as e:
            show_error(e)


# STUDY ASSISTANT
elif page == "Study Assistant":
    st.title("📚 Study Assistant")

    topic = st.text_input("Topic or Chapter")

    grade = st.selectbox(
        "Class",
        ["Class 6", "Class 7", "Class 8", "Class 9", "Class 10"]
    )

    task = st.selectbox("Choose task", [
        "Explain Topic",
        "Make Notes",
        "Important Questions",
        "Practice Quiz",
        "Explain Difficult Question"
    ])

    language = st.selectbox(
        "Language",
        ["Hindi", "English", "Hinglish"]
    )

    if st.button("Start Learning") and topic.strip():
        try:
            answer = ask_model(
                f"You are a school tutor. Class: {grade}. "
                f"Topic: {topic}. Task: {task}. Language: {language}. "
                "Explain with examples."
            )
            st.markdown(answer)
        except Exception as e:
            show_error(e)


# TEXT TOOLS
elif page == "Text Tools":
    st.title("✍️ Text Tools")

    tool = st.selectbox("Choose Tool", [
        "Summarise",
        "Translate",
        "Improve Writing",
        "Fix Grammar",
        "Make Key Points",
        "Change Tone"
    ])

    source = st.text_area("Enter your text")

    language = st.selectbox(
        "Translation Language",
        ["Hindi", "English", "French", "Spanish", "German"]
    )

    if st.button("Process Text") and source.strip():
        instructions = {
            "Summarise": "Summarise this text.",
            "Translate": f"Translate into {language}.",
            "Improve Writing": "Improve clarity and flow.",
            "Fix Grammar": "Correct grammar and spelling.",
            "Make Key Points": "Extract key points as bullets.",
            "Change Tone": "Rewrite in a friendly professional tone."
        }

        try:
            result = ask_model(
                instructions[tool] + "\n\n" + source
            )
            st.markdown("### Result")
            st.write(result)
            st.download_button(
                "Download Result",
                result,
                file_name="text_result.txt"
            )
        except Exception as e:
            show_error(e)


# ABOUT
elif page == "About":
    st.title("ℹ️ About NEXTGEN AI")

    st.markdown("""
    # NEXTGEN AI
    **One Platform. Endless Possibilities.**

    NEXTGEN AI is an AI-powered learning and creativity platform.

    ### Features
    - AI Chat
    - AI Vision
    - PDF Assistant
    - AI Image Prompt Studio
    - AI Video Prompt Studio
    - Study Assistant
    - Text Tools

    ### Important
    Gemini API is required for AI responses.

    Image and Video currently create prompts only.
    They do not render actual images or MP4 videos.

    Live Web Search and Voice Calling are not connected yet.
    """)

    st.caption("NEXTGEN AI · Created by Arav")
