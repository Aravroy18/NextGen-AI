
import os
import io
import streamlit as st
from PIL import Image
from google import genai
from google.genai import types
from pypdf import PdfReader

# ==========================================
# NEXTGEN AI - COMPLETE APPLICATION
# ==========================================

st.set_page_config(
    page_title="NEXTGEN AI",
    page_icon="✨",
    layout="wide",
    initial_sidebar_state="expanded"
)

# IMPORTANT: UPDATED GEMINI MODEL
MODEL = os.getenv("GEMINI_MODEL", "gemini-3.8-flash")

# ==========================================
# WHITE PREMIUM DESIGN
# ==========================================

st.markdown("""
<style>
.stApp {
    background: #ffffff;
    color: #171717;
}
[data-testid="stSidebar"] {
    background: #f8fafc;
    border-right: 1px solid #e5e7eb;
}
.block-container {
    max-width: 1250px;
    padding-top: 2rem;
}
.hero {
    padding: 30px;
    border: 1px solid #e5e7eb;
    border-radius: 20px;
    background: linear-gradient(135deg,#ffffff,#eef2ff);
}
.feature-card {
    background: white;
    border: 1px solid #e5e7eb;
    border-radius: 16px;
    padding: 20px;
    margin-bottom: 12px;
}
.stButton button {
    border-radius: 12px;
    min-height: 42px;
}
</style>
""", unsafe_allow_html=True)


# ==========================================
# GEMINI API CONNECTION
# ==========================================

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
        raise RuntimeError(
            "GEMINI_API_KEY नहीं मिली। "
            "Streamlit Secrets में API key सेट करो।"
        )

    client = get_client(api_key)

    contents = [prompt] if image is None else [prompt, image]

    response = client.models.generate_content(
        model=MODEL,
        contents=contents,
        config=types.GenerateContentConfig(
            temperature=0.7,
            max_output_tokens=2048
        )
    )

    answer = response.text

    if not answer:
        raise RuntimeError("AI से कोई जवाब नहीं मिला।")

    return answer


def show_error(error):
    st.error(str(error))


# ==========================================
# SIDEBAR
# ==========================================

with st.sidebar:

    st.markdown("# ✨ NEXTGEN AI")
    st.caption("One Platform. Endless Possibilities.")

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
            "About"
        ]
    )

    st.divider()

    st.caption("AI MODEL")
    st.code(MODEL)

    if get_api_key():
        st.success("API Key Configured")
    else:
        st.warning("API Key Missing")


# ==========================================
# HOME DASHBOARD
# ==========================================

if page == "Home":

    st.markdown("""
    <div class="hero">
        <h1 style="color:#171717">
            Welcome to NEXTGEN AI ✨
        </h1>
        <p style="color:#64748b;font-size:18px">
            Your intelligent AI workspace.
            Learn, create and explore with AI.
        </p>
    </div>
    """, unsafe_allow_html=True)

    st.write("")

    st.subheader("Explore Your Workspace")

    features = [
        ("💬", "AI Chat", "Ask anything."),
        ("👁️", "AI Vision", "Understand images."),
        ("📄", "PDF Assistant", "Read and analyse PDFs."),
        ("🎨", "AI Image", "Create image prompts."),
        ("🎬", "AI Video", "Create video prompts."),
        ("📚", "Study Assistant", "Learn smarter."),
        ("✍️", "Text Tools", "Improve your writing."),
        ("ℹ️", "About", "About NEXTGEN AI.")
    ]

    cols = st.columns(4)

    for i, (emoji, title, desc) in enumerate(features):

        with cols[i % 4]:

            st.markdown(
                f"""
                <div class="feature-card">
                    <div style="font-size:28px">{emoji}</div>
                    <h4 style="color:#171717">{title}</h4>
                    <p style="color:#64748b">{desc}</p>
                </div>
                """,
                unsafe_allow_html=True
            )


# ==========================================
# AI CHAT
# ==========================================

elif page == "AI Chat":

    st.title("💬 AI Chat")
    st.caption("Chat with NEXTGEN AI.")

    if "chat_messages" not in st.session_state:
        st.session_state.chat_messages = []

    col1, col2 = st.columns([5, 1])

    with col2:

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

            with st.spinner("NEXTGEN AI is thinking..."):

                try:

                    history = st.session_state.chat_messages[-12:]

                    conversation = "\n".join(
                        f'{m["role"]}: {m["content"]}'
                        for m in history
                    )

                    answer = ask_model(
                        "You are NEXTGEN AI, a helpful, intelligent assistant. "
                        "Reply in the same language as the user. "
                        "Give accurate and useful answers. "
                        "Never invent current information.\n\n"
                        + conversation
                    )

                    st.markdown(answer)

                    st.session_state.chat_messages.append({
                        "role": "assistant",
                        "content": answer
                    })

                except Exception as e:
                    show_error(e)


# ==========================================
# AI VISION
# ==========================================

elif page == "AI Vision":

    st.title("👁️ AI Vision")
    st.write("Upload an image and ask questions about it.")

    image_file = st.file_uploader(
        "Upload Image",
        type=["png", "jpg", "jpeg", "webp"]
    )

    question = st.text_area(
        "Ask about your image",
        value="Describe this image in detail."
    )

    if image_file:

        try:

            image = Image.open(image_file).convert("RGB")

            st.image(
                image,
                caption="Uploaded Image",
                use_container_width=True
            )

            if st.button("Analyse Image", type="primary"):

                with st.spinner("Analysing image..."):

                    answer = ask_model(question, image)

                    st.markdown("### AI Analysis")
                    st.write(answer)

        except Exception as e:
            show_error(e)


# ==========================================
# PDF ASSISTANT
# ==========================================

elif page == "PDF Assistant":

    st.title("📄 PDF Assistant")
    st.write("Upload a PDF and ask questions about it.")

    pdf_file = st.file_uploader(
        "Upload PDF",
        type=["pdf"]
    )

    if pdf_file:

        try:

            reader = PdfReader(io.BytesIO(pdf_file.getvalue()))

            pdf_text = "\n\n".join(
                page.extract_text() or ""
                for page in reader.pages
            )

            st.success(
                f"PDF Loaded: {len(reader.pages)} pages"
            )

            if not pdf_text.strip():

                st.warning(
                    "इस PDF में selectable text नहीं मिला। "
                    "यह scanned PDF हो सकती है।"
                )

            else:

                question = st.text_area(
                    "Ask a question about this PDF"
                )

                if st.button("Ask PDF", type="primary") and question.strip():

                    with st.spinner("Reading PDF..."):

                        answer = ask_model(
                            "Answer using the following PDF text. "
                            "If information is missing, say so.\n\n"
                            + pdf_text[:60000]
                            + "\n\nQuestion: "
                            + question
                        )

                        st.markdown(answer)

        except Exception as e:
            show_error(e)


# ==========================================
# AI IMAGE PROMPT STUDIO
# ==========================================

elif page == "AI Image":

    st.title("🎨 AI Image Generator")
    st.caption("Create professional image-generation prompts.")

    st.info(
        "इस version में image prompt बनता है। "
        "Actual image generation engine अभी connected नहीं है।"
    )

    subject = st.text_input(
        "Describe your image",
        placeholder="A futuristic city at night..."
    )

    style = st.selectbox(
        "Choose Style",
        [
            "Cinematic Realistic",
            "3D Animation",
            "Anime",
            "Digital Art",
            "Photorealistic",
            "Fantasy"
        ]
    )

    ratio = st.selectbox(
        "Aspect Ratio",
        ["9:16", "16:9", "1:1", "4:5"]
    )

    details = st.text_area("Extra Details")

    if st.button("Generate Image Prompt", type="primary") and subject.strip():

        with st.spinner("Creating prompt..."):

            try:

                result = ask_model(
                    f"Create an extremely detailed image generation prompt. "
                    f"Subject: {subject}. Style: {style}. "
                    f"Aspect ratio: {ratio}. Extra details: {details}. "
                    "Include lighting, composition, camera details, "
                    "quality and a negative prompt."
                )

                st.markdown("### Your Image Prompt")
                st.write(result)

                st.download_button(
                    "Download Prompt",
                    result,
                    file_name="nextgen_image_prompt.txt"
                )

            except Exception as e:
                show_error(e)


# ==========================================
# AI VIDEO PROMPT STUDIO
# ==========================================

elif page == "AI Video":

    st.title("🎬 AI Video Generator")

    st.info(
        "यह version video prompts बनाता है। "
        "Actual MP4 generation engine अभी connected नहीं है।"
    )

    idea = st.text_area(
        "Describe your video idea"
    )

    duration = st.selectbox(
        "Video Duration",
        ["10 seconds", "20 seconds", "25 seconds", "30 seconds"]
    )

    ratio = st.selectbox(
        "Video Format",
        ["9:16 Vertical", "16:9 Landscape", "1:1 Square"]
    )

    if st.button("Generate Video Prompt", type="primary") and idea.strip():

        with st.spinner("Creating video prompt..."):

            try:

                result = ask_model(
                    f"Create a professional AI video generation prompt. "
                    f"Duration: {duration}. Format: {ratio}. "
                    f"Concept: {idea}. "
                    "Describe camera movement, motion, lighting, "
                    "environment and visual consistency. "
                    "Keep it as one continuous video."
                )

                st.markdown("### Video Generation Prompt")
                st.write(result)

                st.download_button(
                    "Download Video Prompt",
                    result,
                    file_name="nextgen_video_prompt.txt"
                )

            except Exception as e:
                show_error(e)


# ==========================================
# STUDY ASSISTANT
# ==========================================

elif page == "Study Assistant":

    st.title("📚 Study Assistant")
    st.caption("Your AI learning companion.")

    topic = st.text_input(
        "Enter Topic or Chapter"
    )

    grade = st.selectbox(
        "Select Class",
        [
            "Class 6",
            "Class 7",
            "Class 8",
            "Class 9",
            "Class 10"
        ]
    )

    task = st.selectbox(
        "Choose Study Mode",
        [
            "Explain Topic",
            "Make Detailed Notes",
            "Important Questions",
            "Practice Quiz",
            "Explain Difficult Question"
        ]
    )

    language = st.selectbox(
        "Choose Language",
        ["Hindi", "English", "Hinglish"]
    )

    if st.button("Start Learning", type="primary") and topic.strip():

        with st.spinner("Preparing study material..."):

            try:

                answer = ask_model(
                    f"You are an excellent school tutor. "
                    f"Class: {grade}. Topic: {topic}. "
                    f"Task: {task}. Language: {language}. "
                    "Teach clearly with examples and accurate explanations."
                )

                st.markdown(answer)

            except Exception as e:
                show_error(e)


# ==========================================
# TEXT TOOLS
# ==========================================

elif page == "Text Tools":

    st.title("✍️ Text Tools")

    tool = st.selectbox(
        "Choose Text Tool",
        [
            "Summarise",
            "Translate",
            "Improve Writing",
            "Fix Grammar",
            "Make Key Points",
            "Change Tone"
        ]
    )

    source = st.text_area(
        "Enter your text",
        height=220
    )

    language = st.selectbox(
        "Translate Into",
        ["Hindi", "English", "French", "Spanish", "German"]
    )

    if st.button("Process Text", type="primary") and source.strip():

        instructions = {
            "Summarise": "Summarise this text accurately.",
            "Translate": f"Translate this text into {language}.",
            "Improve Writing": "Improve clarity and readability.",
            "Fix Grammar": "Correct spelling and grammar.",
            "Make Key Points": "Extract the important points as bullets.",
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
                file_name="nextgen_text_result.txt"
            )

        except Exception as e:
            show_error(e)


# ==========================================
# ABOUT
# ==========================================

elif page == "About":

    st.title("ℹ️ About NEXTGEN AI")

    st.markdown("""
    # ✨ NEXTGEN AI

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

    ### Technology

    Gemini API powers the AI responses.

    ### Important Information

    Image and Video currently generate prompts only.
    Actual image and video generation engines are not connected.

    Live Web Search and Voice Calling are not connected yet.

    ### Creator

    Built by Arav.
    """)

    st.caption("NEXTGEN AI © 2026")
