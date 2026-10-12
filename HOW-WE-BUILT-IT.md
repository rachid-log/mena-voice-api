# How we built the MENA Voice API

This is the build journey, step by step. The goal: clone a voice in **Moroccan Darija**,
with high quality, for free or almost free. Then call it from anywhere as a **REST API**, so
an automation (n8n, Remotion) can voice Instagram reels.

It covers what we tried, what failed, and why each decision was made. Built on 2026-10-12 by
Rachid Ait Mohand, with Claude Code as a pair programmer.

```mermaid
flowchart LR
  A[Pick a model] --> B[Read its code]
  B --> C[Colab notebook]
  C --> D[Test on a laptop CPU]
  D --> E[Remote API options]
  E --> F[FastAPI + Modal]
  F --> G[Local API tests]
  G --> H[Deploy on Modal]
  H --> I[Your own voice]
  I --> J[Dialects + MENA]
  J --> K[Reels + publish]
```

---

## Step 1. Pick a model that speaks Darija

Darija is a low-resource language. Most voice-cloning tools are trained on English and
Standard Arabic. We compared the options in October 2026:

| Option | Darija | Voice cloning | Free | Verdict |
|---|---|---|---|---|
| ElevenLabs | Ready-made Darija voices (Ghizlane, Jawad) | Yes | Free tier probably has **no** cloning (sources disagree); Starter is $5/mo | Most polished, but cloning is paid |
| Fish Audio, MiniMax | Not confirmed | Yes (10–15 s clip) | Limited | Untested on Darija |
| Chatterbox multilingual | Arabic, leans toward Standard Arabic | Yes, open source | Yes | No dialect data |
| **Habibi-TTS** | **A model trained on Moroccan data (`MAR`)** | **Zero-shot, no training** | **Open source** | **Chosen** |

**Why Habibi-TTS:**
- It has **specialized dialect models**: Moroccan, Standard Arabic, Egyptian, Algerian, Iraqi,
  Saudi and Emirati. It also has a **unified** model for 12 dialects.
- **Zero-shot cloning:** give it a short clip and its transcript, and it speaks new text in that
  voice. No fine-tuning.
- **The Moroccan weights are Apache-2.0**, so commercial use is allowed. (The unified, Saudi and
  Emirati weights are non-commercial.)
- Its paper claims it **matches ElevenLabs on naturalness and beats it on speaker similarity**.
  That's the authors' own benchmark, not peer-reviewed.

---

## Step 2. Read the code before trusting it

We cloned the repo and read the inference code before writing anything. Three findings shaped
everything after:

1. **The CLI cannot run Moroccan.** In habibi-tts 0.1.1, `infer_cli.py` checks the dialect
   against a list that has `IRQ` twice and **no `MAR`**. Its "specialized" branch also has no
   case for `MAR`. So `habibi-tts_infer-cli --dialect MAR` fails.
   → **We call the Python functions directly** (`load_model`, `preprocess_ref_audio_text`,
   `infer_process`), exactly as the official Gradio app does.
2. **torch must stay below 2.9.** `habibi-tts` pins `torch>=2.4,<2.9`. Colab and fresh machines
   ship newer torch. Installing habibi then downgrades torch but leaves torchaudio and
   torchvision on the newer version, and imports break.
   → **We pin the set together:** `torch==2.8.0`, `torchaudio==2.8.0`, `torchvision==0.23.0`,
   `torchcodec==0.7.0`.
3. **The reference clip is cut at 12 seconds.** F5-TTS's `preprocess_ref_audio_text` clips
   the reference to about 12 s, at a silence if it can find one. A longer clip then no longer
   matches its transcript, and the clone produces garbage.
   → **The API refuses clips over 12 s** and recommends 8–10 s.

We also checked the model files on Hugging Face: `Specialized/MAR/model_100000.safetensors`
(1.35 GB) plus a `vocab.txt` of Arabic characters. **Latin letters and digits are not in the
vocabulary.** So brand names must be spelled in Arabic and numbers written as words.

---

## Step 3. A Colab notebook for the first test

Colab gives a free T4 GPU, so it was the cheapest place to hear the model.

- We **generated the notebook from a Python script** (`colab/build_notebook.py`) instead of
  hand-editing JSON, so it can be rebuilt and versioned.
- Cells: GPU check → pinned install → load the model → upload a clip (with a duration check) →
  transcript → generate → copy to Drive → an optional Gradio "mini studio" with a microphone.
- It ships with **a built-in Moroccan sample voice**, so the first run proves the pipeline
  before you record anything.
- We **uploaded it to Google Drive** through the Drive connector, with the MIME type
  `application/vnd.google.colaboratory`, so it opens straight in Colab.

**Result on Colab:** Python 3.13, Tesla T4, `torch 2.8.0+cu128`, "Ready on GPU". The pins work.

---

## Step 4. Prove it on a laptop CPU first

Before trusting Colab, we ran the notebook's own cells on a laptop **CPU** with a small test
harness. It stubs the Colab-only parts and runs cells 3–6 plus the Gradio UI build.

Problems on the way:
- **The laptop runs Python 3.14**, and torch 2.8 has no wheels for it. → `uv venv --python 3.12`.
- **The laptop had no `ffmpeg`**, so pydub couldn't read the sample MP3. → `static-ffmpeg` in
  the test environment only.
- **`/tmp` was a RAM disk (tmpfs).** Putting 3+ GB of packages and weights there could fill
  memory. → The test environment went to `~/.cache/habibi-test` on disk.
- **The first model download died** with a Hugging Face Xet CDN error (`CAS Client Error`)
  during a network blip. → `HF_HUB_DISABLE_XET=1` (plain HTTP, resumable). It then took about
  26 min on a slow line.

**Result:** 8.4 s of Darija in **94 s on CPU** (16 steps). To check the audio without trusting
our ears alone, we transcribed it with **Whisper large-v3**. It heard the target sentence with
only two tiny differences. (Whisper tends to turn Darija into Standard Arabic, so it's a sanity
check, not a quality score.)

---

## Step 5. Can the notebook become an API?

We wanted to call the voice remotely. We explored every route:

| Route | What we found | Decision |
|---|---|---|
| Gradio share link from Colab | Every Gradio app exposes an API. But **Colab bans "web service offerings" on all runtimes**, and bans "interacting primarily via a web UI" on the free tier. Sessions end without warning, and the URL changes each restart. | ❌ Not for an API |
| The official Habibi Space on Hugging Face | It runs on ZeroGPU and has a public `/basic_tts` endpoint. **Our anonymous test call was refused:** `You have exceeded your ZeroGPU runs limit`. Free accounts get about 3.5–5 GPU-min/day, and your clip goes to someone else's Space. | ❌ Too little quota |
| Laptop + Cloudflare Tunnel | Free and private, but about **94 s per clip** on CPU, and the laptop must stay on | ❌ Too slow |
| The existing VPS | CPU only, 1 vCPU | ❌ Slower than the laptop |
| **Modal serverless GPU** | Real HTTPS endpoint, scales to zero, **$30/month of free credit**, T4 at about $0.59/h | ✅ **Chosen** |

---

## Step 6. Design the API

We split the code so the same logic runs on Modal, locally and in tests:

- **`catalog.py`**: the list of weights and their licenses. It imports nothing heavy, so the Modal
  image can bake the weights with it.
- **`engine.py`**: `VoiceEngine` loads the vocoder and models **once**, then synthesizes. A lock
  keeps one synthesis at a time on the GPU. `VoiceStore` saves voices as
  `<id>/ref.wav + meta.json`.
- **`api.py`**: FastAPI with a Bearer-token check, input validation (Pydantic), WAV/MP3 output
  and useful headers (`X-Seed`, `X-Audio-Seconds`).
- **`modal_app.py`**: the deployment, with cost guards.

Design choices:
- **Save a voice once, then reference it by id** (`PUT /voices/{id}`). Clients send only text
  afterward. That's simpler for n8n and saves upload time.
- **Validate early with clear messages:** clips must be 2–12 s, the transcript can't be empty,
  voice ids are `a-z 0-9 - _` (this also blocks path tricks), and the text is at most
  2000 characters.
- **Seeds are returned and accepted**, so a good take can be reproduced exactly.
- **The API refuses to start without a token.** No accidental open API.

**Local test matrix (CPU, all passed):** no token → 401, wrong token → 401, bad voice id → 422,
empty transcript → 422, save → 200, list → 200, reference audio → 200, unknown voice → 404,
unknown model → 422, `/tts` → MP3 with `seed=42`, delete → 204, then get → 404. Whisper heard
the generated sentence correctly.

---

## Step 7. Deploy on Modal (and every snag)

1. **Account:** the Starter plan showed **$30 of credit**.
2. **Login:** `uvx modal setup` showed **no output** when run inside Claude Code's `!` shell.
   It was waiting for a browser approval nobody could see. → We ran `uvx modal token new` in the
   background, read the `token-flow` link from its output, and the user approved it in the
   browser.
3. **Secret:** `modal secret create --from-dotenv` stopped with `Need the python-dotenv package`.
   → `uvx --with python-dotenv modal secret create …`. The token was generated straight into
   `.env` (chmod 600) and **never printed**.
4. **First deploy:** the image built fine. That's four layers: Debian + ffmpeg, about 50 s of
   packages, the code, and the baked 1.35 GB weights. Then it **failed:**
   `Please add a payment method to use T4 GPU functions.` Credits alone don't unlock GPUs.
5. **Billing:** the user added a card. We then read the billing page together. A **usage
   limit** of $42.50 with $30 of credit still allows **$12.50 out of pocket**, so the
   recommendation is a usage limit equal to the credit.
6. **Redeploy:** about 5 s, because the image was cached.

**Live results on a T4:** cold start **37 s**; `/tts` **5.5–7.8 s** for about 6 s of speech at
32 steps; no token → 401.

---

## Step 8. The real voice

- The first real clip was **10.75 s** of Darija, saved as voice `rachid`. The first test clip
  came back in **8.7 s**.
- **Two snags here:**
  - A safety check in the assistant's auto mode blocked one local inspection command. The user
    ran the upload himself.
  - With `curl -s`, a failed upload printed **nothing**. → All examples now use
    `curl -sS -w "HTTP %{http_code}"`.
- **Playing audio on Linux:** `xdg-open` did nothing because no default audio app was set.
  → `gst-play-1.0 file.mp3`.

---

## Step 9. Dialects, Standard Arabic and licenses

- We tested an AI reel hook in Darija with the **`mar`** model, then with **`unified`**.
- For **Standard Arabic**, the unified model needs to know the text's dialect. So we added a
  **`dialect`** field to `/tts`. We tested Standard Arabic with a Darija reference clip, then
  with a new **11.01 s Standard Arabic clip** (voice `rachid-msa`). Matching the clip's language
  to the output's language matters for the accent.
- **License check:** the unified model is **CC-BY-NC-SA** (non-commercial). For a business's
  reels, it's out.
- Then the key find: Habibi also ships **specialized MSA, Egyptian, Algerian and Iraqi models,
  all Apache-2.0**. We added them (plus the non-commercial Saudi and Emirati ones) to the
  catalog. That's what turned a Darija tool into a **MENA** voice API, with commercial-safe
  Standard Arabic.

---

## Step 10. Use it for real: a Darija reel

The first production use was an Instagram reel for **Intropera's weekly AI roundup (2026-W42)**:

1. A sub-agent read the roundup and wrote a **9-line Darija script**. Each line has a caption
   with Latin brand names and a spoken text with brand names in Arabic letters (جيميناي،
   أوبن إي آي) and numbers as words (ميتين وسبعين).
2. **The user approved the script before any GPU time was spent.**
3. Then (still in progress when this was written): one API call per line, with fixed seeds.
   The existing glassy Remotion reel is reused, with Arabic right-to-left captions and
   on-screen text, and real brand logos.

**Estimated cost of a reel's voice:** about $0.04 per pass, $0.10–0.15 with retakes.

---

## Step 11. Publish

- **License:** Apache-2.0 for the code. It matches the commercial-safe weights. The weights
  keep their own licenses and are downloaded, not redistributed (see `NOTICE`).
- **What stays out of the repo:** `.env` (the token), saved voice clips, generated audio, and
  **the live endpoint URL**. Every request to that URL wakes the GPU, even a rejected one. The
  README explains Modal proxy auth as the stronger option.
- **`.intropera.json`** + a 16:9 cover put the project on intropera.com. Extra images in
  `media/` are for LinkedIn.

---

## Lessons

- **Read the code of the model you depend on.** The CLI bug and the 12 s clip limit were in the
  code, not in the docs.
- **Pin the whole torch family together**, not only torch.
- **Test the exact notebook/API code on a CPU first.** It's slow, but it catches wiring bugs
  before you spend GPU time.
- **Read the platform's terms before turning a notebook into an API.** Colab bans it.
- **Every request to a serverless GPU costs money, even a 401.** Keep the URL private, or reject
  requests at the edge.
- **Credits ≠ a spending cap.** Set the usage limit to your credit.
- **Check licenses per model, not per project.** Here the same repo has Apache and
  non-commercial weights side by side.
- **Spend nothing until the content is approved:** script first, voice second, render last.
