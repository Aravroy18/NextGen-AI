import os
import requests


OPENAI_BASE = "https://api.openai.com/v1"

REALTIME_MODEL = "gpt-realtime"

TTS_MODEL = "gpt-4o-mini-tts"

VOICES = [
    "alloy",
    "ash",
    "ballad",
    "coral",
    "echo",
    "fable",
    "nova",
    "onyx",
    "sage",
    "shimmer",
    "verse",
    "marin",
    "cedar",
]
REALTIME_VOICES = [
    "alloy",
    "ash",
    "ballad",
    "coral",
    "echo",
    "sage",
    "shimmer",
    "verse",
    "marin",
    "cedar"
]

def get_api_key():
    return os.getenv("OPENAI_API_KEY", "").strip()


def create_client_secret(voice="marin"):
    key = get_api_key()

    if not key:
        raise RuntimeError("OPENAI_API_KEY is missing.")

    if voice not in VOICES:
        voice = "marin"
   if voice not in REALTIME_VOICES:
    voice = "marin"
    payload = {
        "expires_after": {
            "anchor": "created_at",
            "seconds": 600
        },
        "session": {
            "type": "realtime",
            "model": REALTIME_MODEL,
            "instructions": (
                "You are NEXTGEN AI, a helpful, natural and friendly "
                "AI assistant. Speak clearly and naturally. "
                "Use Hindi when the user speaks Hindi and English "
                "when the user speaks English. Keep answers useful."
            ),
            "audio": {
                "output": {
                    "voice": voice
                },
                "input": {
                    "turn_detection": {
                        "type": "server_vad"
                    },
                    "transcription": {
                        "model": "gpt-4o-mini-transcribe",
                        "language": "hi"
                    }
                }
            }
        }
    }

    response = requests.post(
        f"{OPENAI_BASE}/realtime/client_secrets",
        headers={
            "Authorization": f"Bearer {key}",
            "Content-Type": "application/json"
        },
        json=payload,
        timeout=30
    )

    if not response.ok:
        raise RuntimeError(
            f"Realtime token error: {response.status_code} "
            f"{response.text[:500]}"
        )

    data = response.json()

    token = data.get("value")

    if not token:
        raise RuntimeError("No client token returned.")

    return token


def generate_speech(
    text,
    voice="nova",
    speed=1.15,
    instructions="Speak naturally, clearly and confidently."
):
    key = get_api_key()

    if not key:
        raise RuntimeError("OPENAI_API_KEY is missing.")

    if not text.strip():
        raise ValueError("Text cannot be empty.")

    if voice not in VOICES:
        voice = "nova"

    speed = max(0.25, min(float(speed), 4.0))

    response = requests.post(
        f"{OPENAI_BASE}/audio/speech",
        headers={
            "Authorization": f"Bearer {key}",
            "Content-Type": "application/json"
        },
        json={
            "model": TTS_MODEL,
            "voice": voice,
            "input": text[:4096],
            "speed": speed,
            "instructions": instructions,
            "response_format": "mp3"
        },
        timeout=90
    )

    if not response.ok:
        raise RuntimeError(
            f"Speech API error: {response.status_code} "
            f"{response.text[:500]}"
        )

    return response.content
