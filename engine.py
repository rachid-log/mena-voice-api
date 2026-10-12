"""Habibi-TTS voice engine and the store for saved voice clips."""
import json
import random
import re
import tempfile
import threading
from datetime import datetime, timezone
from importlib.resources import files
from pathlib import Path

import numpy as np
import torch
from f5_tts.infer.utils_infer import load_model, load_vocoder, preprocess_ref_audio_text
from habibi_tts.infer.utils_infer import infer_process
from habibi_tts.model.utils import dialect_id_map
from hydra.utils import get_class
from omegaconf import OmegaConf
from pydub import AudioSegment

from catalog import DEFAULT_MODEL, MODELS, download

MAX_REF_SECONDS = 12.0  # f5-tts cuts the reference clip here, so a longer clip no longer matches its transcript
MIN_REF_SECONDS = 2.0
VOICE_ID = re.compile(r"^[a-z0-9][a-z0-9_-]{0,63}$")


def _quiet(*_args, **_kwargs):
    pass


class VoiceEngine:
    """Loads Habibi-TTS once and turns (voice clip, transcript, text) into speech."""

    def __init__(self, preload=(DEFAULT_MODEL,)):
        cfg = OmegaConf.load(str(files("f5_tts").joinpath("configs/F5TTS_v1_Base.yaml")))
        self._model_cls = get_class(f"f5_tts.model.{cfg.model.backbone}")
        self._arch = cfg.model.arch
        self.mel_spec_type = cfg.model.mel_spec.mel_spec_type
        self.vocoder = load_vocoder(vocoder_name=self.mel_spec_type)
        self._models = {}
        self._lock = threading.Lock()  # one synthesis at a time on the GPU
        for name in preload:
            self.model(name)

    @property
    def loaded(self):
        return sorted(self._models)

    def model(self, name):
        if name not in self._models:
            ckpt, vocab = download(name)
            self._models[name] = load_model(
                self._model_cls, self._arch, ckpt, mel_spec_type=self.mel_spec_type, vocab_file=vocab
            )
        return self._models[name]

    def synthesize(self, ref_audio, ref_text, text, model=DEFAULT_MODEL, speed=1.0, steps=32, seed=None, dialect="MAR"):
        """Return (float32 waveform, sample rate, seed used)."""
        seed = random.randrange(2**31) if seed is None else seed
        dialect_id = dialect_id_map[dialect] if MODELS[model][2] else None
        with self._lock:
            torch.manual_seed(seed)
            ref_audio, ref_text = preprocess_ref_audio_text(ref_audio, ref_text, show_info=_quiet)
            wav, sr, _ = infer_process(
                ref_audio,
                ref_text,
                text,
                self.model(model),
                self.vocoder,
                mel_spec_type=self.mel_spec_type,
                show_info=_quiet,
                progress=None,
                speed=speed,
                nfe_step=steps,
                dialect_id=dialect_id,
            )
        return np.asarray(wav, dtype=np.float32), sr, seed


class VoiceStore:
    """Saved voices on disk: <root>/<voice_id>/ref.wav + meta.json."""

    def __init__(self, root, after_write=None):
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)
        self._after_write = after_write or (lambda: None)

    def _dir(self, voice_id):
        if not VOICE_ID.match(voice_id):
            raise ValueError("voice id: use 1-64 chars of a-z, 0-9, '-' or '_', starting with a letter or digit")
        return self.root / voice_id

    def save(self, voice_id, audio_bytes, filename, transcript):
        """Store a clip (any format ffmpeg reads) as 24 kHz mono WAV. Replaces an existing voice."""
        folder = self._dir(voice_id)
        transcript = transcript.strip()
        if not transcript:
            raise ValueError("transcript is empty: type exactly what is said in the clip")
        with tempfile.NamedTemporaryFile(suffix=Path(filename or "clip").suffix or ".bin") as tmp:
            tmp.write(audio_bytes)
            tmp.flush()
            try:
                clip = AudioSegment.from_file(tmp.name)
            except Exception as e:
                raise ValueError(f"could not read the audio file: {e}") from e
        seconds = len(clip) / 1000
        if seconds > MAX_REF_SECONDS:
            raise ValueError(f"clip is {seconds:.1f} s; keep it under {MAX_REF_SECONDS:.0f} s (6-11 s is best)")
        if seconds < MIN_REF_SECONDS:
            raise ValueError(f"clip is {seconds:.1f} s; record at least 6 s")
        folder.mkdir(parents=True, exist_ok=True)
        clip.set_channels(1).set_frame_rate(24000).export(folder / "ref.wav", format="wav")
        meta = {
            "id": voice_id,
            "transcript": transcript,
            "seconds": round(seconds, 2),
            "updated": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        }
        (folder / "meta.json").write_text(json.dumps(meta, ensure_ascii=False, indent=1), encoding="utf-8")
        self._after_write()
        return meta

    def get(self, voice_id):
        """Return (ref.wav path, meta). Raises KeyError if the voice does not exist."""
        folder = self._dir(voice_id)
        if not (folder / "meta.json").is_file():
            raise KeyError(voice_id)
        return str(folder / "ref.wav"), json.loads((folder / "meta.json").read_text(encoding="utf-8"))

    def list(self):
        return [self.get(d.name)[1] for d in sorted(self.root.iterdir()) if (d / "meta.json").is_file()]

    def delete(self, voice_id):
        folder = self._dir(voice_id)
        if not (folder / "meta.json").is_file():
            raise KeyError(voice_id)
        for f in folder.iterdir():
            f.unlink()
        folder.rmdir()
        self._after_write()
