import datetime
from google import genai
from google.genai import types

LIVE_MODEL = "gemini-3.8-live"

def create_live_token(api_key):
    client = genai.Client(
    api_key=api_key,
    http_options=types.HttpOptions(api_version="v1alpha")
)

    now = datetime.datetime.now(datetime.timezone.utc)

    token = client.auth_tokens.create(
        config={
            "uses": 1,
            "expire_time": now + datetime.timedelta(minutes=30),
            "new_session_expire_time": now + datetime.timedelta(minutes=1),
            "live_constrained_parameters": {
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

    return token.name
