
import os
import datetime
from google import genai

LIVE_MODEL = "gemini-3.8-live"


def create_live_token(api_key=None):

    api_key = api_key or os.getenv("GEMINI_API_KEY")

    if not api_key:
        raise ValueError("GEMINI_API_KEY missing.")

    client = genai.Client(
        api_key=api_key,
        http_options={"api_version": "v1beta"}
    )

    now = datetime.datetime.now(datetime.timezone.utc)

    expire_time = (
        now + datetime.timedelta(minutes=30)
    ).isoformat().replace("+00:00", "Z")

    new_session_expire_time = (
        now + datetime.timedelta(minutes=1)
    ).isoformat().replace("+00:00", "Z")

    token = client.auth_tokens.create(
        config={
            "uses": 1,
            "expire_time": expire_time,
            "new_session_expire_time": new_session_expire_time,
            "live_connect_constraints": {
                "model": LIVE_MODEL,
                "config": {
                    "response_modalities": ["AUDIO"],
                    "input_audio_transcription": {},
                    "output_audio_transcription": {},
                    "session_resumption": {}
                }
            }
        }
    )

    if not token.name:
        raise RuntimeError("Gemini Live token generation failed.")

    return token.name
