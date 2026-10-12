"""Run the Darija Voice API on this machine (CPU works, but slowly).

    API_TOKEN=... python serve_local.py            # http://127.0.0.1:8000/docs
"""
import os

import uvicorn

from api import create_app
from engine import VoiceEngine, VoiceStore

if __name__ == "__main__":
    app = create_app(
        VoiceEngine(),
        VoiceStore(os.environ.get("VOICES_DIR", "voices")),
        os.environ.get("API_TOKEN", ""),
    )
    uvicorn.run(app, host=os.environ.get("HOST", "127.0.0.1"), port=int(os.environ.get("PORT", "8000")))
