"""REST API around the voice engine. Works the same on Modal and on a local machine."""
import io
import os
import secrets
import tempfile
from typing import Literal

import numpy as np
import soundfile as sf
from f5_tts.infer.utils_infer import remove_silence_for_generated_wav
from fastapi import Depends, FastAPI, File, Form, Header, HTTPException, UploadFile
from fastapi.responses import FileResponse, Response
from habibi_tts.model.utils import dialect_id_map
from pydantic import BaseModel, Field
from pydub import AudioSegment

from catalog import DEFAULT_MODEL, MODELS
from engine import VoiceEngine, VoiceStore

MAX_TEXT_CHARS = 2000


class TTSRequest(BaseModel):
    voice: str = Field(description="Id of a saved voice (PUT /voices/{id})")
    text: str = Field(min_length=1, max_length=MAX_TEXT_CHARS, description="Darija in Arabic script")
    model: Literal[tuple(MODELS)] = Field(
        DEFAULT_MODEL,
        description="mar, msa, egy, alg, irq: Apache-2.0 (commercial OK). sau, uae, unified: non-commercial only.",
    )
    dialect: Literal[tuple(dialect_id_map)] = Field(
        "MAR", description="Dialect of the text. Only the 'unified' model reads it; 'mar' is always Moroccan."
    )
    speed: float = Field(1.0, ge=0.5, le=2.0)
    steps: int = Field(32, ge=8, le=64, description="More steps = slightly cleaner, slower")
    seed: int | None = Field(None, ge=0, description="Same seed + same input = same audio")
    format: Literal["wav", "mp3"] = "wav"
    remove_silence: bool = False


def _encode(wav: np.ndarray, sr: int, fmt: str, remove_silence: bool) -> bytes:
    with tempfile.TemporaryDirectory() as tmp:
        path = os.path.join(tmp, "out.wav")
        sf.write(path, wav, sr)
        if remove_silence:
            remove_silence_for_generated_wav(path)
        if fmt == "mp3":
            buf = io.BytesIO()
            AudioSegment.from_wav(path).export(buf, format="mp3", bitrate="192k")
            return buf.getvalue()
        with open(path, "rb") as f:
            return f.read()


def create_app(engine: VoiceEngine, store: VoiceStore, token: str) -> FastAPI:
    if not token:
        raise RuntimeError("API_TOKEN is empty: refusing to serve an open API")
    expected = f"Bearer {token}".encode()

    def require_token(authorization: str = Header(default="")):
        if not secrets.compare_digest(authorization.encode(), expected):
            raise HTTPException(401, "missing or wrong 'Authorization: Bearer <API_TOKEN>' header")

    app = FastAPI(
        title="MENA Voice API",
        version="1.1",
        description="Voice cloning in Moroccan Darija, Standard Arabic and other Arabic dialects, with Habibi-TTS.",
    )
    auth = [Depends(require_token)]

    @app.get("/health")
    def health():
        return {"ok": True, "models_loaded": engine.loaded, "models": {name: m[3] for name, m in MODELS.items()}}

    @app.get("/voices", dependencies=auth)
    def list_voices():
        return store.list()

    @app.put("/voices/{voice_id}", dependencies=auth)
    async def save_voice(voice_id: str, audio: UploadFile = File(...), transcript: str = Form(...)):
        try:
            return store.save(voice_id, await audio.read(), audio.filename, transcript)
        except ValueError as e:
            raise HTTPException(422, str(e)) from e

    @app.get("/voices/{voice_id}", dependencies=auth)
    def get_voice(voice_id: str):
        return _lookup(voice_id)[1]

    @app.get("/voices/{voice_id}/audio", dependencies=auth)
    def get_voice_audio(voice_id: str):
        return FileResponse(_lookup(voice_id)[0], media_type="audio/wav", filename=f"{voice_id}.wav")

    @app.delete("/voices/{voice_id}", dependencies=auth, status_code=204)
    def delete_voice(voice_id: str):
        _lookup(voice_id)
        store.delete(voice_id)

    @app.post("/tts", dependencies=auth, response_class=Response)
    def tts(req: TTSRequest):
        ref_wav, meta = _lookup(req.voice)
        wav, sr, seed = engine.synthesize(
            ref_wav, meta["transcript"], req.text.strip(), req.model, req.speed, req.steps, req.seed, req.dialect
        )
        body = _encode(wav, sr, req.format, req.remove_silence)
        return Response(
            body,
            media_type="audio/mpeg" if req.format == "mp3" else "audio/wav",
            headers={
                "X-Seed": str(seed),
                "X-Audio-Seconds": f"{len(wav) / sr:.2f}",
                "Content-Disposition": f'attachment; filename="{req.voice}_{seed}.{req.format}"',
            },
        )

    def _lookup(voice_id):
        try:
            return store.get(voice_id)
        except ValueError as e:
            raise HTTPException(422, str(e)) from e
        except KeyError as e:
            raise HTTPException(404, f"no voice '{voice_id}'. Save one with PUT /voices/{voice_id}") from e

    return app
