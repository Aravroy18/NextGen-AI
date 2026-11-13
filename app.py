import os
import io
import json
import base64
import sqlite3
import requests
import streamlit as st
from datetime import datetime

# =========================================================
# NEXTGEN AI — VERSION MAX
# =========================================================

st.set_page_config(
    page_title="NEXTGEN AI MAX",
    page_icon="✦",
    layout="wide",
    initial_sidebar_state="expanded"
)

APP_NAME = "NEXTGEN AI"
APP_VERSION = "VERSION MAX"
DB_PATH = "nextgen_max.db"

GROQ_MODEL = "openai/gpt-oss-120b"
GEMINI_MODEL = "gemini-2.5-flash"
IMAGE_MODEL = "@cf/black-forest-labs/flux-1-schnell"

# =========================================================
# SECRETS
# =========================================================

def get_secret(key, default=""):
    try:
        value = st.secrets.get(key)
        if value:
            return value
    except Exception:
        pass
    return os.getenv
