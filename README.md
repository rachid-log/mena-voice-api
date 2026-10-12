# MENA Voice API

[![License: Apache-2.0](https://img.shields.io/badge/license-Apache--2.0-6050DC.svg)](LICENSE)
[![Open in Colab](https://colab.research.google.com/assets/colab-badge.svg)](https://colab.research.google.com/github/rachid-log/mena-voice-api/blob/main/colab/darija_voice_clone.ipynb)

A REST API that **clones a voice from a 6–11 second clip** and speaks **Moroccan Darija**,
**Modern Standard Arabic** and other Arabic dialects. It wraps
[Habibi-TTS](https://github.com/SWivid/Habibi-TTS) and runs on a **serverless GPU on
[Modal](https://modal.com)** for a few cents per batch. It also runs on your own machine
(CPU, slow) or in a free Colab notebook.

- **Save a voice once:** upload a short clip and its exact transcript.
- **Then send text, get audio back:** WAV or MP3, in that voice.
- **Built for automation:** one HTTP call per line, so n8n, Make, scripts or a video
  pipeline (Remotion) can voice whole reels.

> How the project was built, step by step, with every dead end: **[HOW-WE-BUILT-IT.md](HOW-WE-BUILT-IT.md)**.

---

## Contents

1. [Models and licenses](#1-models-and-licenses)
2. [Try it in Colab (no setup)](#2-try-it-in-colab-no-setup)
3. [Deploy on your own Modal account](#3-deploy-on-your-own-modal-account)
4. [Record a good voice clip](#4-record-a-good-voice-clip)
5. [API reference](#5-api-reference)
6. [Examples: curl, Python, n8n](#6-examples-curl-python-n8n)
7. [Writing text the model can read](#7-writing-text-the-model-can-read)
8. [Costs](#8-costs)
9. [Security](#9-security)
10. [Troubleshooting: every problem we hit](#10-troubleshooting-every-problem-we-hit)
11. [Run locally (CPU)](#11-run-locally-cpu)
12. [Project layout](#12-project-layout)
13. [Credits and license](#13-credits-and-license)

---

## 1. Models and licenses

The code in this repo is **Apache-2.0**. The **model weights are not in this repo**: they are
downloaded from [Hugging Face](https://huggingface.co/SWivid/Habibi-TTS) and keep **their own
license**. That license decides whether you can use the audio commercially.

| `model` | Speaks | Weights license | Commercial use | Baked into the image |
|---|---|---|---|---|
| `mar` (default) | Moroccan Darija | Apache-2.0 | ✅ yes | ✅ yes |
| `msa` | Modern Standard Arabic | Apache-2.0 | ✅ yes | no (downloads on first use) |
| `egy` | Egyptian | Apache-2.0 | ✅ yes | no |
| `alg` | Algerian | Apache-2.0 | ✅ yes | no |
| `irq` | Iraqi | Apache-2.0 | ✅ yes | no |
| `sau` | Saudi / Gulf | CC-BY-NC-SA-4.0 | ❌ non-commercial only | no |
| `uae` | Emirati | CC-BY-NC-SA-4.0 | ❌ non-commercial only | no |
| `unified` | 12 dialects, chosen with the `dialect` field | CC-BY-NC-SA-4.0 | ❌ non-commercial only | no |

- **Specialized models** (`mar`, `msa`, …) speak one dialect. They ignore the `dialect` field.
- **`unified`** reads the `dialect` field: `MAR`, `MSA`, `SAU`, `UAE`, `ALG`, `IRQ`, `EGY`,
  `OMN`, `TUN`, `LEV`, `SDN`, `LBY` or `UNK` (unknown).
- **The voice and the language are separate.** A voice saved from a Darija clip can read Standard
  Arabic, but it keeps some Moroccan accent. For the cleanest result, record the clip in the same
  dialect you want to generate.
- **Only clone voices you have permission to use.**

---

## 2. Try it in Colab (no setup)

[`colab/darija_voice_clone.ipynb`](colab/darija_voice_clone.ipynb) runs the Moroccan model on
Colab's free T4 GPU. Open it with the badge at the top.

1. `Runtime → Change runtime type → T4 GPU`.
2. Run the cells from top to bottom. The first run takes about 5–8 min: an install plus a 1.35 GB
   model download.
3. Keep **USE_SAMPLE_VOICE** ticked for a first test. Untick it to upload your own clip.

Colab notes:
- **Cell 3 says "torch X is loaded, not 2.8".** Do `Runtime → Restart session`, then run from cell 3.
- **Cell 8 (mini studio) has a PUBLIC_LINK box.** Free Colab bans "bypassing the notebook UI to
  interact primarily via a web UI", and **all** Colab runtimes ban "web service offerings".
  Use the public link for quick tests only. **Never use Colab as an API**: deploy on Modal instead
  (next section).
- **Colab deletes files when the session ends.** Cell 7 copies your audio to Google Drive.

---

## 3. Deploy on your own Modal account

About 10 minutes. You need [`uv`](https://docs.astral.sh/uv/) (for `uvx`) and a terminal.
You do **not** need Python packages or a GPU on your machine: the image builds on Modal.

### 3.1 Create the account and protect your wallet

1. Sign up at [modal.com/signup](https://modal.com/signup). The Starter plan includes
   **$30 of compute per month**.
2. **Add a card.** Modal refuses GPU functions without one, even with credits left. The deploy
   fails with: `Please add a payment method to use T4 GPU functions.`
3. **Cap your spending.** Open **Settings → Usage & billing**. There are two limits:

   | Setting | What it caps | Set it to |
   |---|---|---|
   | **Usage limit** | Total usage, **credits included** | **30.00** (your credit). Then you never pay out of pocket. |
   | **Spend limit** | What you pay **after** credits | Any value. With the usage limit at 30, real charges stay at $0. |

   Example: a usage limit of $42.50 with $30 of credit means you can be charged up to **$12.50**.
   Volume storage keeps billing even after the limits are hit, but voice clips are a few KB.

### 3.2 Log in from your terminal

```bash
git clone https://github.com/rachid-log/mena-voice-api.git
cd mena-voice-api
uvx modal setup
```

- It opens a browser page. Click **Approve**.
- **If nothing prints or nothing opens** (some terminals and AI tools hide the output), run
  `uvx modal token new` instead. It prints a `https://modal.com/token-flow/tf-…` link. Open it
  and approve.
- **Check it worked:** `uvx modal profile current` prints your workspace name. If you see
  `Token missing. Could not authenticate client`, the login did not finish.

### 3.3 Make your API token and store it as a Modal secret

```bash
python3 -c "import secrets; print('API_TOKEN=' + secrets.token_urlsafe(32))" > .env && chmod 600 .env
uvx --with python-dotenv modal secret create darija-voice-api --from-dotenv .env
```

- `.env` holds the token your clients send. It is in `.gitignore`. **Never commit it.**
- Without `--with python-dotenv`, the CLI stops with `Need the python-dotenv package installed`.
- Already created? Add `--force` to overwrite it (see [3.8 Rotate the token](#38-rotate-the-token)).

### 3.4 Deploy

```bash
uvx modal deploy modal_app.py
```

- **The first deploy takes about 2–3 minutes.** It builds the image in four layers: Debian +
  ffmpeg, the Python packages (torch 2.8 with CUDA 12.8, habibi-tts, FastAPI), your code, and
  **baking the `mar` model + vocoder into the image** so cold starts skip the download.
- **Later deploys take seconds**, because Modal caches the layers. Changing `catalog.py` rebuilds
  the weight layer. Changing `engine.py` or `api.py` does not.
- The output ends with your URL:
  `https://<workspace>--darija-voice.modal.run`. Modal labels it "(unauthenticated)". That only
  means Modal adds no login of its own. **The app checks your Bearer token on every route except
  `/health`.**

### 3.5 First calls

```bash
URL=https://<workspace>--darija-voice.modal.run
set -a && . ./.env && set +a          # loads API_TOKEN without printing it

curl -sS -m 300 "$URL/health"         # first call: ~40 s (the GPU wakes up)
```

Then [save a voice](#6-examples-curl-python-n8n) and generate. Measured on a T4:

| Step | Time |
|---|---|
| Cold start (GPU wakes, model loads) | about **37 s** |
| `/tts`, about 6 s of speech, 32 steps, warm | about **5.5–9 s** |
| First call to a non-baked model (e.g. `msa`) | about **+15–25 s** (1.35 GB download) |
| GPU stays warm after the last request | **2 min** (`scaledown_window`) |

### 3.6 Change the names, GPU or cost guards

Everything lives in [`modal_app.py`](modal_app.py):

| What | Where | Default |
|---|---|---|
| App name (for `modal app stop`, the dashboard) | `modal.App("darija-voice-api")` | `darija-voice-api` |
| URL label → `https://<workspace>--<label>.modal.run` | `@modal.asgi_app(label=...)` | `darija-voice` |
| Volume holding saved voices | `modal.Volume.from_name(...)` | `darija-voices` |
| Secret holding `API_TOKEN` | `modal.Secret.from_name(...)` | `darija-voice-api` |
| GPU | env `VOICE_GPU` at deploy time | `T4` (about $0.59/h). `L4` is faster (about $0.80/h). |
| Max GPU containers | `max_containers` | `1`: requests wait in line. Never two GPUs billing at once. |
| Idle time before shutdown | `scaledown_window` | `120` s |
| Request timeout | `timeout` | `600` s |

`VOICE_GPU=L4 uvx modal deploy modal_app.py` deploys on an L4. If you rename the secret, create
it under the new name first.

### 3.7 Bake another model

Only `mar` is baked. If you mostly use `msa` (or another model), bake it too so cold starts
don't download 1.35 GB. In `modal_app.py`, change `bake_weights()`:

```python
download(DEFAULT_MODEL)
download("msa")          # +1.35 GB in the image
download_vocoder()
```

and in `engine.py` / `modal_app.py` you can preload it: `VoiceEngine(preload=("mar", "msa"))`.
Each preloaded model adds about 0.7 GB of GPU memory (fp16). A T4 has 16 GB.

### 3.8 Rotate the token

```bash
python3 -c "import secrets; print('API_TOKEN=' + secrets.token_urlsafe(32))" > .env && chmod 600 .env
uvx --with python-dotenv modal secret create darija-voice-api --from-dotenv .env --force
uvx modal deploy modal_app.py        # new containers read the new secret
```

Then update every client (n8n credential, scripts).

### 3.9 Redeploy safely

- A deploy swaps the running container. **A request in flight at that moment can fail.** Deploy
  between batches, or have clients retry once after 60 s.
- Saved voices survive deploys: they live in the Volume, not in the image.

### 3.10 Stop or remove everything

```bash
uvx modal app stop darija-voice-api          # stops the app; the URL goes dead
uvx modal volume delete darija-voices        # deletes saved voices (asks to confirm)
uvx modal secret delete darija-voice-api     # deletes the token secret
```

---

## 4. Record a good voice clip

- **8–10 seconds is best. The allowed range is 2–12 s.** The model cuts the reference at 12 s,
  and then the transcript no longer matches, so the API refuses longer clips.
- **The transcript must match the clip word for word**, in Arabic script. A wrong transcript is
  the main cause of mumbling and wrong words.
- **One or two full sentences.** Stop at the end of a sentence, not mid-word.
- **Quiet room, phone about 20 cm away.** No music, fan or echo.
- **Talk the way you want the output to sound.** The clone copies energy, speed and mood.
- **Same dialect as your output** for the cleanest accent (see [section 1](#1-models-and-licenses)).
- Any format ffmpeg reads works: `.m4a`, `.mp3`, `.wav`, `.ogg`, `.opus` (WhatsApp voice notes).
  The API stores it as 24 kHz mono WAV.

---

## 5. API reference

Every route except `GET /health` needs `Authorization: Bearer <API_TOKEN>`.
Interactive docs: `<URL>/docs` (OpenAPI).

| Method | Path | What it does | Success |
|---|---|---|---|
| `GET` | `/health` | Up check, loaded models, and each model's license. No auth. | 200 |
| `PUT` | `/voices/{id}` | Save or replace a voice. Multipart: `audio` (file) + `transcript` (text). | 200 + voice JSON |
| `GET` | `/voices` | List saved voices. | 200 |
| `GET` | `/voices/{id}` | One voice's details. | 200 |
| `GET` | `/voices/{id}/audio` | The stored reference clip (24 kHz mono WAV). | 200 |
| `DELETE` | `/voices/{id}` | Delete a voice. | 204 |
| `POST` | `/tts` | JSON in, audio out. | 200 + audio |

**Voice ids:** 1–64 characters of `a-z 0-9 - _`, starting with a letter or digit.

### `POST /tts` body

| Field | Default | Rule |
|---|---|---|
| `voice` | required | A saved voice id. |
| `text` | required | 1–2000 characters, **Arabic script**. Long text is split at punctuation and joined with a short cross-fade. |
| `model` | `"mar"` | See [section 1](#1-models-and-licenses). |
| `dialect` | `"MAR"` | Only `unified` reads it. |
| `speed` | `1.0` | 0.5–2.0. `1.1` cuts about 9 % of the length. |
| `steps` | `32` | 8–64. More steps = slightly cleaner, slower. |
| `seed` | random | 0 or more. Same seed + same input = same audio. |
| `format` | `"wav"` | `"wav"` (24 kHz mono, 16-bit) or `"mp3"`. |
| `remove_silence` | `false` | Cuts long pauses inside the result. |

**Response headers:** `X-Seed` (the seed used: keep it to reproduce a good take),
`X-Audio-Seconds`, `Content-Disposition`.

> `X-Audio-Seconds` is decided from the **text length** before generation. A mumbled take has
> the same length as a good one. Only listening tells them apart.

### Errors

| Code | When | Body says |
|---|---|---|
| 401 | Missing or wrong token | `missing or wrong 'Authorization: Bearer <API_TOKEN>' header` |
| 404 | Unknown voice | `no voice '<id>'. Save one with PUT /voices/<id>` |
| 422 | Clip over 12 s or under 2 s, empty transcript, unreadable audio, bad voice id, a field out of range, unknown model or dialect | The exact reason |
| 500 / 502 | Rare: a deploy swapped the container mid-request | Retry once after 60 s |

---

## 6. Examples: curl, Python, n8n

### curl

```bash
URL=https://<workspace>--darija-voice.modal.run
set -a && . ./.env && set +a

# Save a voice once (quote the whole -F value if the file name has spaces or brackets)
curl -sS -w "\nHTTP %{http_code}\n" -X PUT "$URL/voices/rachid" \
  -H "Authorization: Bearer $API_TOKEN" \
  -F "audio=@$HOME/Downloads/my clip (1).m4a" \
  -F "transcript=هادا تيست ديال الصوت ديالي بالدارجة المغربية"

# Speak (Darija, commercial-safe)
curl -sS -w "HTTP %{http_code}\n" -X POST "$URL/tts" \
  -H "Authorization: Bearer $API_TOKEN" -H "Content-Type: application/json" \
  -d '{"voice":"rachid","text":"السلام عليكم، مرحبا بيكم فهاد الفيديو الجديد.","format":"mp3"}' \
  -o out.mp3

# Speak Standard Arabic, commercial-safe
curl -sS -X POST "$URL/tts" -H "Authorization: Bearer $API_TOKEN" -H "Content-Type: application/json" \
  -d '{"voice":"rachid-msa","model":"msa","text":"مرحبًا بكم في هذه الحلقة الجديدة.","format":"mp3"}' -o out-msa.mp3
```

- Use **`-sS`**, not `-s`. Plain `-s` hides errors, so a failed upload prints nothing at all.
- **Don't put `"` or `$` inside the shell text.** Either one breaks the command. Use Python
  for text like that.

### Python

```python
import os, requests

URL = "https://<workspace>--darija-voice.modal.run"
H = {"Authorization": f"Bearer {os.environ['API_TOKEN']}"}

with open("clip.m4a", "rb") as f:
    r = requests.put(f"{URL}/voices/rachid", headers=H,
                     files={"audio": f}, data={"transcript": "هادا تيست ديال الصوت ديالي"}, timeout=300)
r.raise_for_status()

r = requests.post(f"{URL}/tts", headers=H, timeout=300, json={
    "voice": "rachid", "model": "mar", "format": "mp3", "seed": 42,
    "text": "واش عارف بلي الذكاء الاصطناعي ولا كيدير خدمة عشرة ديال الناس فدقيقة وحدة؟",
})
r.raise_for_status()
open("hook.mp3", "wb").write(r.content)
print("seed", r.headers["X-Seed"], "seconds", r.headers["X-Audio-Seconds"])
```

### n8n

- **HTTP Request** node → `POST {{URL}}/tts`, **Send Body: JSON**, body as above.
- **Authentication:** Generic Credential Type → **Header Auth**. Name `Authorization`, value
  `Bearer <API_TOKEN>`.
- **Options → Response → Response Format: File.** The audio lands in the binary field `data`.
- **Options → Timeout: 120000** (120 s) or more. A cold start takes about 40 s, and n8n's
  default timeout can cut it.
- **Many lines:** loop over items. With `max_containers=1` they run one after another on one GPU.

---

## 7. Writing text the model can read

- **Arabic letters only.** The vocabulary holds Arabic characters. Latin letters, digits and
  Arabizi (3, 7, 9) are skipped or turned into silence.
- **Spell brand names in Arabic:** جيميناي (Gemini), ميسترال (Mistral), أوبن إي آي (OpenAI),
  كلود (Claude). For captions on screen you can keep the Latin name: keep two texts, one shown
  and one spoken.
- **Numbers as words:** عشرين, not 20. ميتين وسبعين, not 270.
- **Punctuation gives the voice breaths:** `،` `.` `؟`.
- **Diacritics (تشكيل) are optional.** They can help with Standard Arabic.
- **Short lines (4–7 s each) are easier to retake** than one long paragraph. Keep the `seed` of
  every good take.

---

## 8. Costs

Modal T4: **$0.000164 per second** (about $0.59/h). You pay while a container is up, including
the cold start and the 2 min idle window.

| Job | GPU time | Cost |
|---|---|---|
| One batch: cold start + 9 short lines + 2 min idle | about 4 min | **about $0.04** |
| A 50 s reel with 2–3 retake passes | about 10 min | **about $0.10–0.15** |
| $30 of monthly credit | about 50 T4-hours | **about 1,000 batches** |

These are measured timings times the published price. Check your real usage in the Modal
dashboard.

---

## 9. Security

- **Keep your URL private.** Every request wakes the GPU, **even one rejected with 401**,
  because the token check runs inside the GPU container. Anyone who knows the URL can burn your
  credit with junk requests. The usage limit caps the damage.
- **Stronger option: Modal proxy auth.** Set `@modal.asgi_app(label=..., requires_proxy_auth=True)`
  and create a proxy token in **Settings → Proxy tokens**. Modal then rejects requests without
  `Modal-Key` / `Modal-Secret` headers **at its edge, before any container starts**. Clients
  send those two headers plus the Bearer token.
- **The token lives in two places only:** `.env` (chmod 600, git-ignored) and the Modal secret.
  Rotate it if it leaks ([3.8](#38-rotate-the-token)).
- **Voices are personal data.** Saved clips stay in your Modal Volume. They're never logged or
  returned except through `GET /voices/{id}/audio` with the token.
- **Consent.** Clone only voices you have permission to use. Habibi's non-commercial models
  forbid commercial use of their output.

---

## 10. Troubleshooting: every problem we hit

### Modal account and deploy

| Symptom | Cause | Fix |
|---|---|---|
| `uvx modal setup` prints nothing | It waits for a browser approval, and some terminals and AI tools hide the prompt | `uvx modal token new`, open the printed `token-flow` link, approve |
| `Token missing. Could not authenticate client` | Login never finished | Redo 3.2. Check with `uvx modal profile current` |
| `Need the python-dotenv package installed` | `--from-dotenv` needs an extra package | `uvx --with python-dotenv modal secret create …` |
| `Please add a payment method to use T4 GPU functions.` | GPUs need a card, even with credits | Add a card, then set the **usage limit** to your credit (3.1) |
| `Secret 'darija-voice-api' not found` on deploy | Secret missing or renamed | Create it (3.3), or match the name in `modal_app.py` |
| The first request takes about 40 s, n8n times out | Cold start | Raise the client timeout to ≥120 s, or call `/health` first to warm up |
| A request fails with 500/502 right after a deploy | The container was swapped mid-request | Retry once after 60 s; deploy between batches |
| Requests wait in line | `max_containers=1` (the cost guard) | Expected. Raise it only if you accept two GPUs billing at once |
| The first call to `msa` (or any non-`mar` model) is slow | It downloads 1.35 GB on each cold start | Bake it (3.7) |

### Requests and audio quality

| Symptom | Cause | Fix |
|---|---|---|
| `curl -s …` prints **nothing** | `-s` hides curl's own errors (bad path, DNS, timeout) | Use `-sS -w "\nHTTP %{http_code}\n"` |
| 401 | Missing header, wrong token, or token rotated without redeploy | `Authorization: Bearer <token>`. Load `.env`. Redeploy after rotating |
| 404 `no voice '…'` | Voice not saved, deleted, or wrong id | `PUT /voices/{id}` first. Check `GET /voices` |
| 422 `clip is 14.3 s` | Clip over 12 s or under 2 s | Trim to 8–10 s |
| 422 on `PUT` with a valid clip | Voice id has capitals, dots or spaces | Use `a-z 0-9 - _` |
| A file name with spaces or `(1)` fails in curl | Shell quoting | Quote the whole value: `-F "audio=@/path/my clip (1).m4a"` |
| A transcript with `"` or `$` breaks the command | Shell quoting | Remove them, or send from Python |
| Mumbling, missing or wrong words | The transcript doesn't match the clip | Fix the transcript word for word, `PUT` again |
| Brand names or numbers vanish | Latin letters and digits aren't in the vocabulary | Spell them in Arabic, numbers as words (section 7) |
| Standard Arabic sounds Moroccan | The voice clip was Darija, and/or `mar` was used | Record an MSA clip, use `model: "msa"` |
| `unified` sounds like the wrong dialect | Wrong `dialect` tag | Set `dialect` to match the text |
| A good take can't be reproduced | Random seed | Keep `X-Seed`, send it as `seed` |
| A bad take has the "right" length | Length comes from text, not from the audio | Listen. There's no automatic check |

### Local run and Colab

| Symptom | Cause | Fix |
|---|---|---|
| `pip install torch==2.8.0` finds no wheel | Python 3.14: torch 2.8 has no wheels for it | `uv venv --python 3.12` |
| `operator torchvision::nms does not exist` | torchvision built for another torch | Pin `torchvision==0.23.0` with `torch==2.8.0` (`requirements.txt`) |
| `Couldn't find ffmpeg` / pydub can't read `.mp3` or `.m4a` | No ffmpeg on the machine | `sudo apt install ffmpeg`, or `pip install static-ffmpeg` and call `static_ffmpeg.add_paths()` |
| `torchcodec` error about `libavutil.so` | FFmpeg shared libs missing | This code never imports torchcodec. Ignore it, or install ffmpeg 4–7 libs |
| `CAS Client Error` / timeouts while downloading weights | Hugging Face Xet CDN on a flaky network | `export HF_HUB_DISABLE_XET=1` and retry (downloads resume) |
| `habibi-tts_infer-cli --dialect MAR` fails an assertion | Bug in habibi-tts 0.1.1's CLI: its dialect list skips `MAR` | Use this API or the Python functions (`engine.py`) |
| Colab: `torch X is loaded, not 2.8` | torch was imported before the install | `Runtime → Restart session`, run from cell 3 |
| Colab session ended without warning | Public Gradio link used as the main UI on the free tier | Use the notebook UI, or this API |
| Hugging Face Space API: `exceeded your ZeroGPU runs limit` | Anonymous ZeroGPU quota is tiny (free accounts get about 3.5–5 GPU-min/day) | Log in with an HF token, or deploy your own (this repo) |
| Linux: `xdg-open out.mp3` plays nothing | No default audio app set | `gst-play-1.0 out.mp3` |

---

## 11. Run locally (CPU)

Works on any machine, but slowly: **about 80–95 s for 8 s of speech** at 16 steps on a laptop CPU.
Good for testing the API, or for batch jobs that can wait.

```bash
uv venv --python 3.12 .venv && . .venv/bin/activate
uv pip install -r requirements.txt
sudo apt install ffmpeg                       # pydub needs it to read m4a/mp3
set -a && . ./.env && set +a
python serve_local.py                         # http://127.0.0.1:8000/docs
```

- `HOST`, `PORT` and `VOICES_DIR` (default `voices/`) are environment variables.
- Exposing it to the internet (for example with a Cloudflare Tunnel) works, but keep the token
  on: the API refuses to start without `API_TOKEN`.

---

## 12. Project layout

| File | Role |
|---|---|
| [`catalog.py`](catalog.py) | Which weights exist, their licenses, and how to download them. Light, so the image can bake weights with it. |
| [`engine.py`](engine.py) | `VoiceEngine` (loads the models once, synthesizes) and `VoiceStore` (saved voices on disk). |
| [`api.py`](api.py) | The FastAPI app: routes, validation, auth, WAV/MP3 encoding. |
| [`modal_app.py`](modal_app.py) | Modal deployment: image, GPU, volume, secret, cost guards. |
| [`serve_local.py`](serve_local.py) | Run on your own machine. |
| [`colab/build_notebook.py`](colab/build_notebook.py) | Builds the Colab notebook (`python3 colab/build_notebook.py colab/darija_voice_clone.ipynb`). |
| [`.intropera.json`](.intropera.json) + [`.intropera/`](.intropera/) | Project card for [intropera.com](https://intropera.com). |
| [`media/`](media/) | Images for LinkedIn and social posts. |
| [`HOW-WE-BUILT-IT.md`](HOW-WE-BUILT-IT.md) | The build journey, step by step. |

---

## 13. Credits and license

- **Code:** Apache-2.0, © 2026 Rachid Ait Mohand. See [LICENSE](LICENSE) and [NOTICE](NOTICE).
- **Speech model:** [Habibi-TTS](https://github.com/SWivid/Habibi-TTS) by the SJTU X-LANCE team
  (code MIT; weights per [section 1](#1-models-and-licenses)), built on
  [F5-TTS](https://github.com/SWivid/F5-TTS) (MIT).
- **Vocoder:** [Vocos](https://github.com/gemelo-ai/vocos) `charactr/vocos-mel-24khz` (MIT).
- **Serverless GPU:** [Modal](https://modal.com).
