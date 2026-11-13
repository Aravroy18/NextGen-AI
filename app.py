
import os
import io
import uuid
import streamlit as st
from dotenv import load_dotenv
from google import genai
from PIL import Image
from pypdf import PdfReader

# ================= CONFIG =================

load_dotenv()

st.set_page_config(
    page_title="NEXTGEN AI",
    page_icon="✦",
    layout="wide",
    initial_sidebar_state="expanded"
)

API_KEY = os.getenv("GEMINI_API_KEY")
MODEL = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")

@st.cache_resource
def get_client():
    if not API_KEY:
        return None
    return genai.Client(api_key=API_KEY)

client = get_client()

# ================= SESSION STATE =================

if "chats" not in st.session_state:
    st.session_state.chats = {}

if "active_chat" not in st.session_state:
    st.session_state.active_chat = None

if "page" not in st.session_state:
    st.session_state.page = "Chat"

def new_chat():
    chat_id = str(uuid.uuid4())

    st.session_state.chats[chat_id] = {
        "title": "New Chat",
        "messages": []
    }

    st.session_state.active_chat = chat_id
    st.session_state.page = "Chat"

def get_active_chat():
    chat_id = st.session_state.active_chat

    if not chat_id or chat_id not in st.session_state.chats:
        new_chat()

    return st.session_state.chats[
        st.session_state.active_chat
    ]

# ================= AI ENGINE =================

def ask_ai(prompt, history=None, image=None):

    if client is None:
        return "API KEY नहीं मिली। अपनी .env फाइल चेक करें।"

    try:

        contents = []

        if history:
            for msg in history[-12:]:

                role = (
                    "user"
                    if msg["role"] == "user"
                    else "model"
                )

                contents.append({
                    "role": role,
                    "parts": [{"text": msg["content"]}]
                })

        parts = [{"text": prompt}]

        if image is not None:
            parts.append(image)

        contents.append({
            "role": "user",
            "parts": parts
        })

        response = client.models.generate_content(
            model=MODEL,
            contents=contents,
            config={
                "system_instruction": (
                    "You are NEXTGEN AI, an intelligent "
                    "and helpful AI assistant. Answer clearly "
                    "and accurately in the user's language."
                )
            }
        )

        return response.text or "No response received."

    except Exception as e:
        return f"AI ERROR: {str(e)}"

# ================= DESIGN =================

st.markdown("""
<style>

@import url(
'https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&display=swap'
);

html, body, [class*="css"] {
    font-family: Inter, sans-serif;
}

.stApp {
    background: #212121;
    color: #ECECEC;
}

[data-testid="stSidebar"] {
    background: #171717;
    border-right: 1px solid #303030;
}

.brand {
    font-size: 25px;
    font-weight: 800;
    color: white;
    padding: 12px 5px 25px;
}

.brand span {
    color: #8B9EFF;
}

.stButton button {
    background: #292929;
    color: white;
    border: 1px solid #414141;
    border-radius: 10px;
    width: 100%;
    transition: 0.2s;
}

.stButton button:hover {
    background: #393939;
    border-color: #8B9EFF;
}

[data-testid="stChatMessage"] {
    background: transparent;
    border: none;
}

[data-testid="stChatInput"] {
    background: #303030;
    border: 1px solid #505050;
    border-radius: 18px;
}

[data-testid="stChatInput"] textarea {
    color: white;
}

.welcome {
    text-align: center;
    padding-top: 15vh;
}

.welcome h1 {
    font-size: 34px;
    font-weight: 700;
}

.welcome p {
    color: #AAAAAA;
}

footer {
    visibility: hidden;
}

#MainMenu {
    visibility: hidden;
}

</style>
""", unsafe_allow_html=True)

# ================= SIDEBAR =================

with st.sidebar:

    st.markdown(
        '<div class="brand">✦ NEXTGEN <span>AI</span></div>',
        unsafe_allow_html=True
    )

    if st.button("＋ New Chat", use_container_width=True):
        new_chat()
        st.rerun()

    if st.button("⌕ Explore AI Tools"):
        st.session_state.page = "Tools"
        st.rerun()

    if st.button("◈ AI Vision"):
        st.session_state.page = "Vision"
        st.rerun()

    if st.button("▤ PDF Assistant"):
        st.session_state.page = "PDF"
        st.rerun()

    if st.button("⚙ Settings"):
        st.session_state.page = "Settings"
        st.rerun()

    st.divider()

    st.caption("YOUR CHATS")

    for chat_id, chat in reversed(
        list(st.session_state.chats.items())
    ):

        if st.button(
            "▢ " + chat["title"][:25],
            key="chat_" + chat_id
        ):

            st.session_state.active_chat = chat_id
            st.session_state.page = "Chat"
            st.rerun()

    st.divider()

    st.markdown("**✦ NEXTGEN AI**")
    st.caption("Your Creative Universe")
    st.caption("Version 4.0")

# ================= CHAT PAGE =================

if st.session_state.page == "Chat":

    chat = get_active_chat()

    st.markdown(
        "<div style='text-align:right;color:#aaa;'>"
        "✦ NEXTGEN AI</div>",
        unsafe_allow_html=True
    )

    if not chat["messages"]:

        st.markdown("""
        <div class="welcome">
            <h1>What can I help you with?</h1>
            <p>
            Ask anything. Learn, create and explore
            with NEXTGEN AI.
            </p>
        </div>
        """, unsafe_allow_html=True)

        col1, col2, col3 = st.columns(3)

        with col1:
            st.markdown("### ✦ Learn")
            st.caption("Understand difficult topics.")

        with col2:
            st.markdown("### ⌘ Create")
            st.caption("Write, code and brainstorm.")

        with col3:
            st.markdown("### ◈ Analyze")
            st.caption("Understand files and images.")

    else:

        for msg in chat["messages"]:

            with st.chat_message(msg["role"]):
                st.markdown(msg["content"])

    with st.expander("＋ Attach a file"):

        attachment = st.file_uploader(
            "Upload Image or PDF",
            type=["png", "jpg", "jpeg", "webp", "pdf"],
            key="chat_attachment"
        )

    user_input = st.chat_input("Message NEXTGEN AI...")

    if user_input:

        old_history = chat["messages"].copy()

        chat["messages"].append({
            "role": "user",
            "content": user_input
        })

        if not old_history:
            chat["title"] = user_input[:35]

        image = None
        prompt = user_input

        if attachment is not None:

            if attachment.type == "application/pdf":

                try:
                    reader = PdfReader(
                        io.BytesIO(attachment.getvalue())
                    )

                    pdf_text = "\n".join(
                        page.extract_text() or ""
                        for page in reader.pages
                    )

                    prompt += (
                        "\n\nPDF CONTENT:\n"
                        + pdf_text[:60000]
                    )

                except Exception as e:
                    prompt += f"\nPDF error: {e}"

            else:

                image = Image.open(
                    io.BytesIO(attachment.getvalue())
                ).convert("RGB")

        with st.spinner("NEXTGEN AI is thinking..."):

            answer = ask_ai(
                prompt,
                history=old_history,
                image=image
            )

        chat["messages"].append({
            "role": "assistant",
            "content": answer
        })

        st.rerun()

# ================= VISION =================

elif st.session_state.page == "Vision":

    st.title("◈ AI Vision")

    file = st.file_uploader(
        "Upload an image",
        type=["png", "jpg", "jpeg", "webp"]
    )

    question = st.text_input(
        "Ask about this image",
        value="Describe this image."
    )

    if file:

        img = Image.open(file).convert("RGB")

        st.image(img, use_container_width=True)

        if st.button("Analyze Image"):

            with st.spinner("Analyzing..."):

                result = ask_ai(
                    question,
                    image=img
                )

            st.markdown("### Analysis")
            st.write(result)

# ================= PDF =================

elif st.session_state.page == "PDF":

    st.title("▤ PDF Assistant")

    file = st.file_uploader(
        "Upload PDF",
        type=["pdf"]
    )

    if file:

        try:

            reader = PdfReader(
                io.BytesIO(file.getvalue())
            )

            pdf_text = "\n".join(
                p.extract_text() or ""
                for p in reader.pages
            )

            st.success(
                f"{len(reader.pages)} pages loaded"
            )

            question = st.text_input(
                "Ask about your PDF"
            )

            if st.button("Ask PDF"):

                if not pdf_text.strip():
                    st.error("No readable text found.")

                elif question.strip():

                    with st.spinner("Reading PDF..."):

                        result = ask_ai(
                            "Use this PDF content:\n"
                            + pdf_text[:80000]
                            + "\nQuestion: "
                            + question
                        )

                    st.markdown("### Answer")
                    st.write(result)

            if st.button("Summarize PDF"):

                with st.spinner("Summarizing..."):

                    result = ask_ai(
                        "Summarize this PDF:\n"
                        + pdf_text[:80000]
                    )

                st.markdown(result)

        except Exception as e:
            st.error(str(e))

# ================= TOOLS =================

elif st.session_state.page == "Tools":

    st.title("Explore AI Tools")

    tools = [
        ("💬", "AI Chat", "AI conversations"),
        ("🌐", "Web Search", "Internet search"),
        ("🔬", "Deep Research", "Research topics"),
        ("📄", "PDF Assistant", "Analyze documents"),
        ("👁️", "AI Vision", "Understand images"),
        ("💻", "Coding Assistant", "Generate code"),
        ("✍️", "Writing Assistant", "Create content"),
        ("🌍", "Translator", "Translate languages"),
        ("📝", "Summarizer", "Summarize text"),
        ("🎓", "Study Assistant", "Learn and practice"),
        ("🧮", "Calculator", "Calculate values"),
        ("📊", "Data Analysis", "Analyze data"),
        ("🎨", "Image Studio", "Create image prompts"),
        ("🎬", "Video Studio", "Create video prompts"),
        ("📋", "Notes", "Organize notes"),
        ("🧠", "Quiz Generator", "Generate quizzes")
    ]

    cols = st.columns(3)

    for i, (icon, name, desc) in enumerate(tools):

        with cols[i % 3]:

            with st.container(border=True):

                st.markdown(f"### {icon} {name}")
                st.caption(desc)

                if name in [
                    "AI Chat",
                    "PDF Assistant",
                    "AI Vision"
                ]:
                    st.success("Available")

                else:
                    st.info("In Development")

# ================= SETTINGS =================

elif st.session_state.page == "Settings":

    st.title("⚙ Settings")

    st.subheader("NEXTGEN AI Configuration")

    st.write("AI Model:", MODEL)

    st.write(
        "API Status:",
        "Connected" if client else "API key missing"
    )

    st.caption(
        "API usage depends on provider limits."
    )

    if st.button("Clear All Chat History"):

        st.session_state.chats = {}
        st.session_state.active_chat = None

        st.rerun()

# ================= FOOTER =================

st.divider()

st.markdown("""
<div style="text-align:center;color:#777;padding:12px;">
    ✦ NEXTGEN AI © 2026
    <br>
    Your Creative Universe
</div>
""", unsafe_allow_html=True)
