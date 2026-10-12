"""Build the Habibi-TTS Darija voice-clone Colab notebook."""
import json
import sys

OUT = sys.argv[1] if len(sys.argv) > 1 else "darija_voice_clone.ipynb"


def md(text):
    return {"cell_type": "markdown", "metadata": {}, "source": text.strip("\n").splitlines(keepends=True)}


def code(text, form=True):
    meta = {"cellView": "form"} if form else {}
    return {
        "cell_type": "code",
        "execution_count": None,
        "metadata": meta,
        "outputs": [],
        "source": text.strip("\n").splitlines(keepends=True),
    }


cells = [
    md(r"""
# Darija voice clone · Habibi-TTS

Clone your voice in Moroccan Darija with [Habibi-TTS](https://github.com/SWivid/Habibi-TTS). It is free and open source.

**Before you start:** `Runtime → Change runtime type → T4 GPU`.

**Run the cells from top to bottom.** The first run takes about 5–8 min (install + a 1.35 GB model). After that, each sentence takes a few seconds.

### Record your voice clip
- **6–11 seconds long.** The model cuts everything after 12 s. Then your transcript no longer matches the audio, and the clone breaks.
- **Quiet room.** Phone close to your mouth. No music, no echo.
- **Talk the way you want the clone to talk.** It copies the energy, speed and mood of the clip.
- **A WhatsApp voice note works.** `.opus`, `.ogg`, `.m4a`, `.mp3` and `.wav` are all fine.

### Write the text
- **Arabic script only**, not Arabizi (3, 7, 9). The model only knows Arabic letters.
- **Write numbers as words:** "عشرين", not "20".
- **Use punctuation** (`،` `.` `؟`). It gives the voice places to breathe.

### Licenses
- **MAR specialized** model: Apache 2.0. Fine for commercial use.
- **Unified + MAR tag** model: CC-BY-NC-SA 4.0. **Non-commercial use only.**
- Clone **your own voice**, or a voice you have permission to use.
"""),
    code(r"""
#@title 1 · Check the GPU
import subprocess, sys

try:
    gpu = subprocess.run(
        ["nvidia-smi", "--query-gpu=name,memory.total", "--format=csv,noheader"],
        capture_output=True, text=True,
    ).stdout.strip()
except FileNotFoundError:
    gpu = ""

print("Python", sys.version.split()[0])
if gpu:
    print("GPU:", gpu)
else:
    print("NO GPU. Go to Runtime → Change runtime type → T4 GPU, then run this cell again.")
"""),
    code(r"""
#@title 2 · Install Habibi-TTS (about 3–5 min)
#@markdown Red `pip's dependency resolver` errors about other Colab packages are normal. Ignore them.
# Habibi-TTS needs torch < 2.9, so pin torch 2.8 and the packages built for it.
!pip install -q "torch==2.8.0" "torchaudio==2.8.0" "torchvision==0.23.0" "torchcodec==0.7.0" habibi-tts
!python -c "import torch, torchaudio; print('torch', torch.__version__, '| torchaudio', torchaudio.__version__, '| GPU', torch.cuda.is_available())"
"""),
    code(r"""
#@title 3 · Load the model (about 1–2 min the first time)
import datetime
import os

import torch

if not torch.__version__.startswith("2.8"):
    raise RuntimeError(
        f"torch {torch.__version__} is loaded, not 2.8. Do Runtime → Restart session, then run from cell 3."
    )

import soundfile as sf
from cached_path import cached_path
from f5_tts.infer.utils_infer import (
    load_model,
    load_vocoder,
    preprocess_ref_audio_text,
    remove_silence_for_generated_wav,
)
from habibi_tts.infer.utils_infer import infer_process
from habibi_tts.model.utils import dialect_id_map
from hydra.utils import get_class
from importlib.resources import files
from IPython.display import Audio, display
from omegaconf import OmegaConf

HF = "hf://SWivid/Habibi-TTS"
# name -> (checkpoint, vocab, dialect tag). The specialized model takes no tag; the unified one needs MAR's tag.
# Called directly because habibi-tts_infer-cli rejects --dialect MAR (v0.1.1).
MODELS = {
    "MAR specialized": (f"{HF}/Specialized/MAR/model_100000.safetensors", f"{HF}/Specialized/MAR/vocab.txt", None),
    "Unified + MAR tag": (f"{HF}/Unified/model_200000.safetensors", f"{HF}/Unified/vocab.txt", dialect_id_map["MAR"]),
}
DEFAULT_MODEL = "MAR specialized"
SAMPLE_REF_AUDIO = str(files("habibi_tts").joinpath("assets/MAR.mp3"))
SAMPLE_REF_TEXT = "إذا بغيتي شي صوت باللهجة المغربية للإعلانات ديالك هذا أحسن واحد غادي تلقاه."
OUT_DIR = "/content/outputs"

model_cfg = OmegaConf.load(str(files("f5_tts").joinpath("configs/F5TTS_v1_Base.yaml")))
model_cls = get_class(f"f5_tts.model.{model_cfg.model.backbone}")
mel_spec_type = model_cfg.model.mel_spec.mel_spec_type
vocoder = load_vocoder(vocoder_name=mel_spec_type)
_loaded = {}


def get_model(name):
    if name not in _loaded:
        ckpt, vocab, _ = MODELS[name]
        _loaded[name] = load_model(
            model_cls,
            model_cfg.model.arch,
            str(cached_path(ckpt)),
            mel_spec_type=mel_spec_type,
            vocab_file=str(cached_path(vocab)),
        )
    return _loaded[name]


def clone(ref_audio, ref_text, gen_text, model_name=DEFAULT_MODEL, speed=1.0, steps=32):
    # Cuts the clip to 12 s max; an empty ref_text makes Whisper transcribe it.
    ref_audio, ref_text = preprocess_ref_audio_text(ref_audio, ref_text or "")
    wav, sr, _ = infer_process(
        ref_audio,
        ref_text,
        gen_text.strip(),
        get_model(model_name),
        vocoder,
        mel_spec_type=mel_spec_type,
        speed=speed,
        nfe_step=int(steps),
        dialect_id=MODELS[model_name][2],
    )
    return wav, sr


get_model(DEFAULT_MODEL)
print("Ready on", "GPU" if torch.cuda.is_available() else "CPU (this will be very slow)")
"""),
    code(r"""
#@title 4 · Your voice clip
#@markdown Keep **USE_SAMPLE_VOICE** ticked for a first test with the built-in Moroccan voice.
#@markdown Untick it and run this cell to upload your own 6–11 s clip.
USE_SAMPLE_VOICE = True  #@param {type:"boolean"}

from pydub import AudioSegment

if USE_SAMPLE_VOICE:
    REF_AUDIO = SAMPLE_REF_AUDIO
else:
    from google.colab import files as colab_files

    uploaded = colab_files.upload()
    REF_AUDIO = os.path.abspath(list(uploaded)[-1])

secs = len(AudioSegment.from_file(REF_AUDIO)) / 1000
print(f"{os.path.basename(REF_AUDIO)} · {secs:.1f} s")
if secs > 12:
    print("WARNING: longer than 12 s. The model keeps only ~12 s, so your transcript will not match. Trim it and upload again.")
elif secs < 4:
    print("WARNING: very short. A 6–11 s clip clones better.")
display(Audio(REF_AUDIO))
"""),
    code(r"""
#@title 5 · What you say in the clip
#@markdown Type **exactly** what you say in your clip, in Arabic script. It is ignored while USE_SAMPLE_VOICE is ticked.
#@markdown Leave it empty to let Whisper guess. Whisper is weak on Darija: read the `ref_text` line it prints in cell 6, fix it here, then run cells 5 and 6 again.
REF_TEXT = ""  #@param {type:"string"}

ref_text = SAMPLE_REF_TEXT if USE_SAMPLE_VOICE else REF_TEXT.strip()
print("Transcript:", ref_text or "(empty → Whisper will guess)")
"""),
    code(r"""
#@title 6 · Say new text in your voice
#@markdown Darija text in Arabic script. Numbers as words.
GEN_TEXT = "السلام عليكم، أنا كنجرب واحد البرنامج جديد كيقلد الصوت ديالي بالدارجة. واش كيبان ليك بحال إلا أنا اللي كنهضر؟"  #@param {type:"string"}
#@markdown **MAR specialized** = commercial OK. **Unified + MAR tag** = non-commercial only. Try both and compare.
MODEL = "MAR specialized"  #@param ["MAR specialized", "Unified + MAR tag"]
SPEED = 1.0  #@param {type:"slider", min:0.7, max:1.3, step:0.05}
#@markdown More steps = slightly cleaner, but slower. 32 is the default.
STEPS = 32  #@param {type:"slider", min:16, max:64, step:8}
REMOVE_LONG_SILENCES = False  #@param {type:"boolean"}

wav, sr = clone(REF_AUDIO, ref_text, GEN_TEXT, MODEL, SPEED, STEPS)
os.makedirs(OUT_DIR, exist_ok=True)
tag = "mar" if MODEL == "MAR specialized" else "unified"
out_path = f"{OUT_DIR}/clone_{tag}_{datetime.datetime.now():%Y%m%d_%H%M%S}.wav"
sf.write(out_path, wav, sr)
if REMOVE_LONG_SILENCES:
    remove_silence_for_generated_wav(out_path)
print("Saved:", out_path)
display(Audio(out_path))
"""),
    md(r"""
### If it sounds off
- **Wrong words or mumbling** → the transcript in cell 5 does not match the clip exactly. Fix it, word for word.
- **Clip got cut** → it was longer than 12 s. Trim it to 6–11 s.
- **Accent drifts toward Egyptian or Gulf** → switch MODEL and compare.
- **Flat or tired voice** → record a livelier clip. The mood of the clip carries over.
- **Too fast or too slow** → move SPEED.
"""),
    code(r"""
#@title 7 · Copy your audio files to Google Drive (optional)
#@markdown Saves everything in `/content/outputs` to **My Drive → Darija Voice Clone → outputs**. Colab deletes local files when the session ends.
import shutil

from google.colab import drive

drive.mount("/content/drive")
dest = "/content/drive/MyDrive/Darija Voice Clone/outputs"
os.makedirs(dest, exist_ok=True)
names = sorted(os.listdir(OUT_DIR))
for name in names:
    shutil.copy2(os.path.join(OUT_DIR, name), dest)
print(f"Copied {len(names)} file(s) to My Drive → Darija Voice Clone → outputs")
"""),
    code(r"""
#@title 8 · Mini studio: record with your mic (optional)
#@markdown A small app inside Colab: record or upload, type, generate, repeat.
#@markdown If the mic does not work inside Colab, tick **PUBLIC_LINK** and run again. It opens the studio in a new tab through a random `gradio.live` link. Anyone with that link can use it while this notebook runs.
#@markdown **Warning:** free Colab bans "bypassing the notebook UI to interact primarily via a web UI". If you work mostly through the public link, Colab can end the session without warning. Use it for quick tests only. For remote use, deploy the Modal API instead (see the README of github.com/rachid-log/mena-voice-api).
PUBLIC_LINK = False  #@param {type:"boolean"}

import gradio as gr


def studio(ref_audio, ref_text, gen_text, model_name, speed, steps):
    if not ref_audio:
        raise gr.Error("Record or upload your voice first.")
    if not gen_text.strip():
        raise gr.Error("Write the text to say.")
    wav, sr = clone(ref_audio, ref_text, gen_text, model_name, speed, steps)
    return sr, wav


with gr.Blocks() as demo:
    gr.Markdown("## Darija voice clone\nRecord 6–11 s. Type exactly what you said. Then write the new text.")
    with gr.Row():
        with gr.Column():
            ref_in = gr.Audio(sources=["microphone", "upload"], type="filepath", label="Your voice (6–11 s)")
            ref_txt = gr.Textbox(label="What you said in the clip (empty = Whisper guesses)", rtl=True)
            gen_txt = gr.Textbox(
                label="New text to say in your voice", lines=4, rtl=True,
                value=globals().get("GEN_TEXT", ""),
            )
            model_in = gr.Dropdown(list(MODELS), value=DEFAULT_MODEL, label="Model")
            speed_in = gr.Slider(0.7, 1.3, value=1.0, step=0.05, label="Speed")
            steps_in = gr.Slider(16, 64, value=32, step=8, label="Steps")
            btn = gr.Button("Generate", variant="primary")
        out = gr.Audio(label="Your clone", type="numpy")
    btn.click(studio, [ref_in, ref_txt, gen_txt, model_in, speed_in, steps_in], out)

demo.launch(share=PUBLIC_LINK)
"""),
]

nb = {
    "cells": cells,
    "metadata": {
        "accelerator": "GPU",
        "colab": {"gpuType": "T4", "provenance": [], "name": "Darija voice clone · Habibi-TTS"},
        "kernelspec": {"display_name": "Python 3", "name": "python3"},
        "language_info": {"name": "python"},
    },
    "nbformat": 4,
    "nbformat_minor": 0,
}

with open(OUT, "w", encoding="utf-8") as f:
    json.dump(nb, f, ensure_ascii=False, indent=1)
print("wrote", OUT)
