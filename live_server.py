import os

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response
from pydantic import BaseModel, Field

from voicecall import create_client_secret, generate_speech, VOICES


app = FastAPI(
    title="NEXTGEN AI Voice Server",
    version="2.0.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:8501",
        "http://127.0.0.1:8501"
    ],
    allow_credentials=False,
    allow_methods=["GET", "POST"],
    allow_headers=["Content-Type"]
)


class TokenRequest(BaseModel):
    voice: str = "marin"


class SpeechRequest(BaseModel):
    text: str = Field(min_length=1, max_length=4096)
    voice: str = "nova"
    speed: float = Field(default=1.15, ge=0.25, le=4.0)


@app.get("/")
def home():
    return {
        "app": "NEXTGEN AI Voice Server",
        "status": "online"
    }


@app.get("/health")
def health():
    return {"status": "healthy"}


@app.post("/token")
def token(data: TokenRequest):
    try:
        if data.voice not in VOICES:
            raise HTTPException(400, "Invalid voice")

        return {
            "client_secret": create_client_secret(data.voice)
        }

    except HTTPException:
        raise

    except Exception as error:
        raise HTTPException(500, str(error))


@app.post("/tts")
def tts(data: SpeechRequest):
    try:
        audio = generate_speech(
            text=data.text,
            voice=data.voice,
            speed=data.speed
        )

        return Response(
            content=audio,
            media_type="audio/mpeg",
            headers={
                "Content-Disposition": "inline; filename=nextgen.mp3"
            }
        )

    except Exception as error:
        raise HTTPException(500, str(error))


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "live_server:app",
        host="127.0.0.1",
        port=8765,
        reload=False
    )
