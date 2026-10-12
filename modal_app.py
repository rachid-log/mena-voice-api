"""Deploy the MENA Voice API on Modal: one GPU container at most, off after 2 min idle.

    modal deploy modal_app.py
"""
import os

import modal

GPU = os.environ.get("VOICE_GPU", "T4")  # T4 ≈ $0.59/h, L4 ≈ $0.80/h (faster)


def bake_weights():
    from catalog import DEFAULT_MODEL, download, download_vocoder

    download(DEFAULT_MODEL)
    download_vocoder()


image = (
    modal.Image.debian_slim(python_version="3.12")
    .apt_install("ffmpeg")
    # habibi-tts needs torch < 2.9
    .uv_pip_install(
        "torch==2.8.0",
        "torchaudio==2.8.0",
        "torchvision==0.23.0",
        "torchcodec==0.7.0",
        "habibi-tts==0.1.1",
        "fastapi[standard]",
        "python-multipart",
    )
    # Bake the default model (1.35 GB) + vocoder into the image so cold starts skip the download.
    .add_local_python_source("catalog", copy=True)
    .run_function(bake_weights)
    .add_local_python_source("engine", "api")
)

app = modal.App("darija-voice-api")
voices = modal.Volume.from_name("darija-voices", create_if_missing=True)


@app.cls(
    image=image,
    gpu=GPU,
    volumes={"/data": voices},
    secrets=[modal.Secret.from_name("darija-voice-api")],  # holds API_TOKEN
    max_containers=1,
    scaledown_window=120,
    timeout=600,
)
class VoiceAPI:
    @modal.enter()
    def load(self):
        from engine import VoiceEngine

        self.engine = VoiceEngine()

    @modal.asgi_app(label="darija-voice")
    def web(self):
        from api import create_app
        from engine import VoiceStore

        return create_app(self.engine, VoiceStore("/data/voices", after_write=voices.commit), os.environ["API_TOKEN"])
