
import datetime
from google import genai
from google.genai import types

LIVE_MODEL = "gemini-3.8-live"


def create_live_token(api_key):
    client = genai.Client(
        api_key=api_key,
        http_options=types.HttpOptions(
            api_version="v1alpha"
        )
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
        raise ValueError("Live token generate नहीं हुआ।")

    return token.name
