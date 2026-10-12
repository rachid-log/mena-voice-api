"""Build the project images (Intropera card cover + LinkedIn media) from HTML with headless Chrome.

    python3 media/build_media.py            # writes .intropera/cover.png and media/linkedin/*.png

Needs Google Chrome (or Chromium) and an internet connection for Google Fonts.
"""
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CHROME = next((c for c in ("google-chrome", "google-chrome-stable", "chromium", "chromium-browser") if shutil.which(c)), None)

FONTS = (
    "https://fonts.googleapis.com/css2?family=Sora:wght@500;600;700"
    "&family=IBM+Plex+Sans:wght@400;500&family=IBM+Plex+Mono:wght@400;500"
    "&family=IBM+Plex+Sans+Arabic:wght@400;500;600&display=block"
)

HOOK_AR = "واش عارف بلي الذكاء الاصطناعي ولا كيدير خدمة عشرة ديال الناس فدقيقة وحدة؟"

# Line icons (24x24, stroke = currentColor).
ICON = {
    "mic": '<rect x="9" y="3" width="6" height="11" rx="3"/><path d="M5 11a7 7 0 0 0 14 0M12 18v3M8 21h8"/>',
    "chip": '<rect x="7" y="7" width="10" height="10" rx="2"/><path d="M9 2v3M15 2v3M9 19v3M15 19v3M2 9h3M2 15h3M19 9h3M19 15h3"/>',
    "speaker": '<path d="M4 9v6h4l5 4V5L8 9H4z"/><path d="M16.5 8.5a5 5 0 0 1 0 7M19 6a8.5 8.5 0 0 1 0 12"/>',
    "code": '<path d="M8 7l-5 5 5 5M16 7l5 5-5 5M14 4l-4 16"/>',
    "flow": '<circle cx="6" cy="6" r="2.5"/><circle cx="18" cy="18" r="2.5"/><path d="M8.5 6H14a4 4 0 0 1 4 4v5.5"/>',
}


def icon(name, size=40):
    return (
        f'<svg width="{size}" height="{size}" viewBox="0 0 24 24" fill="none" stroke="currentColor" '
        f'stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round">{ICON[name]}</svg>'
    )


def wave(n=34, h=56, seed=7):
    """Deterministic waveform bars."""
    bars, x = [], seed
    for i in range(n):
        x = (x * 1103515245 + 12345) % 2**31
        amp = 0.25 + 0.75 * abs(((i * 37) % 17) / 16 - 0.5) * 2 * (0.6 + 0.4 * (x % 100) / 100)
        bars.append(f'<i style="height:{max(6, int(h * amp))}px"></i>')
    return f'<div class="wave" style="height:{h}px">{"".join(bars)}</div>'


CSS = """
:root{--night:#0B0C11;--ink:#0E1016;--on:#EEF0F5;--muted:#9CA1B3;--acc:#8A7DF5;--pri:#6050DC;
--glass:rgba(255,255,255,.055);--edge:rgba(255,255,255,.13)}
*{box-sizing:border-box;margin:0;padding:0}
html,body{background:var(--night)}
body{width:VARW;height:VARH;overflow:hidden;zoom:VARZ}
.canvas{position:relative;width:DESW;height:DESH;overflow:hidden;color:var(--on);
font-family:'IBM Plex Sans',sans-serif;background:
radial-gradient(900px 700px at 85% 15%,rgba(96,80,220,.38),transparent 60%),
radial-gradient(800px 600px at 5% 95%,rgba(138,125,245,.22),transparent 60%),
linear-gradient(160deg,#0E1016,#0B0C11 60%)}
.grid{position:absolute;inset:0;background-image:linear-gradient(rgba(255,255,255,.035) 1px,transparent 1px),
linear-gradient(90deg,rgba(255,255,255,.035) 1px,transparent 1px);background-size:64px 64px;
mask-image:radial-gradient(ellipse at 60% 40%,#000 30%,transparent 75%)}
.glass{background:var(--glass);border:1px solid var(--edge);border-radius:28px;backdrop-filter:blur(24px);
box-shadow:inset 0 1px 0 rgba(255,255,255,.12),0 30px 80px rgba(0,0,0,.45)}
.label{font-family:'IBM Plex Mono',monospace;font-size:20px;letter-spacing:.14em;text-transform:uppercase;color:var(--acc)}
h1{font-family:Sora,sans-serif;font-weight:600;letter-spacing:-.02em;line-height:1.02}
.muted{color:var(--muted)}
.chips{display:flex;flex-wrap:wrap;gap:12px}
.chip{font-family:'IBM Plex Mono',monospace;font-size:20px;padding:10px 18px;border-radius:999px;
border:1px solid rgba(138,125,245,.45);background:rgba(96,80,220,.14);color:var(--on)}
.chip.nc{border-color:rgba(255,255,255,.18);background:rgba(255,255,255,.04);color:var(--muted)}
.ar{font-family:'IBM Plex Sans Arabic',sans-serif;direction:rtl;text-align:right}
.mono{font-family:'IBM Plex Mono',monospace}
.wave{display:flex;align-items:center;gap:6px}
.wave i{display:block;width:7px;border-radius:4px;background:linear-gradient(180deg,#B3A9FF,#6050DC)}
.ico{width:72px;height:72px;border-radius:20px;display:grid;place-items:center;color:#fff;flex:none;
background:linear-gradient(145deg,rgba(138,125,245,.55),rgba(96,80,220,.25));border:1px solid rgba(255,255,255,.18)}
.arrow{width:2px;height:34px;margin:6px 0 6px 64px;background:linear-gradient(var(--acc),transparent)}
.stat b{display:block;font-family:Sora,sans-serif;font-size:40px;font-weight:600}
.stat span{font-size:20px;color:var(--muted)}
.foot{position:absolute;left:0;right:0;bottom:44px;display:flex;justify-content:space-between;padding:0 110px;
font-family:'IBM Plex Mono',monospace;font-size:22px;color:var(--muted)}
.wm{font-family:Sora,sans-serif;font-weight:600;color:var(--on);letter-spacing:-.018em}
.wm i{font-style:normal;color:var(--acc)}
"""


def page(body, des_w, des_h, out_w, out_h):
    zoom = out_w / des_w
    css = (
        CSS.replace("VARW", f"{des_w}px").replace("VARH", f"{des_h}px").replace("VARZ", f"{zoom}")
        .replace("DESW", f"{des_w}px").replace("DESH", f"{des_h}px")
    )
    return (
        f'<!doctype html><html><head><meta charset="utf-8"><link rel="stylesheet" href="{FONTS}">'
        f"<style>{css}</style></head><body><div class=\"canvas\"><div class=\"grid\"></div>{body}</div></body></html>"
    )


def pipeline_card(width):
    return f"""
<div style="width:{width}px">
  <div class="glass" style="padding:30px 34px;display:flex;gap:26px;align-items:center">
    <div class="ico">{icon('mic')}</div>
    <div style="flex:1"><div class="label">1 · Your voice</div>
      <div style="font-size:30px;margin:6px 0 10px">A 10-second clip + its transcript</div>{wave(30, 46, 3)}</div>
  </div>
  <div class="arrow"></div>
  <div class="glass" style="padding:30px 34px;display:flex;gap:26px;align-items:center">
    <div class="ico">{icon('chip')}</div>
    <div><div class="label">2 · POST /tts</div>
      <div style="font-size:30px;margin-top:6px">Serverless GPU · FastAPI · Habibi-TTS</div></div>
  </div>
  <div class="arrow"></div>
  <div class="glass" style="padding:30px 34px;display:flex;gap:26px;align-items:center">
    <div class="ico">{icon('speaker')}</div>
    <div style="flex:1"><div class="label">3 · Speech in your voice</div>
      <div class="ar" style="font-size:31px;line-height:1.45;margin:8px 0 10px">{HOOK_AR}</div>{wave(30, 46, 11)}</div>
  </div>
</div>"""


def cover():
    """Landscape: the Intropera card (16:9) and the LinkedIn cover (1.91:1) share this layout."""
    return f"""
<div style="position:absolute;inset:0;display:flex;align-items:center;gap:80px;padding:0 110px">
  <div style="flex:1.05">
    <div class="label">Open source · Apache-2.0</div>
    <h1 style="font-size:124px;margin:26px 0 30px">MENA<br>Voice API</h1>
    <p class="muted" style="font-size:36px;line-height:1.4;max-width:820px">
      Clone a voice from a 10-second clip. Speak Moroccan Darija, Standard Arabic and more, over one REST call.</p>
    <div class="chips" style="margin:38px 0 46px">
      <span class="chip">Darija</span><span class="chip">Standard Arabic</span><span class="chip">Egyptian</span>
      <span class="chip">Algerian</span><span class="chip">Iraqi</span></div>
    <div style="display:flex;gap:22px">
      <div class="glass stat" style="padding:24px 28px"><b>≈ 6 s</b><span>per line, warm</span></div>
      <div class="glass stat" style="padding:24px 28px"><b>37 s</b><span>cold start</span></div>
      <div class="glass stat" style="padding:24px 28px"><b>≈ $0.04</b><span>per batch</span></div>
    </div>
  </div>
  {pipeline_card(760)}
</div>
<div class="foot"><span>github.com/rachid-log/mena-voice-api</span><span class="wm">intropera<i>.</i></span></div>"""


def how_it_works():
    steps = [
        ("mic", "Record 8–10 seconds", "Any format ffmpeg reads. Type exactly what you said.", "PUT /voices/{id}"),
        ("code", "Send the text", "Darija or Standard Arabic, in Arabic letters.", "POST /tts"),
        ("chip", "A GPU wakes up", "Modal starts a T4. Habibi-TTS clones the voice.", "37 s cold · 6 s warm"),
        ("flow", "Get WAV or MP3", "Into n8n, Remotion or a reel. Keep the good seeds.", "X-Seed · X-Audio-Seconds"),
    ]
    rows = "".join(
        f"""<div class="glass" style="padding:26px 34px;display:flex;gap:28px;align-items:flex-start;margin-bottom:18px">
  <div class="ico">{icon(ic)}</div>
  <div style="flex:1"><div class="label">{i + 1:02d}</div>
    <div style="font-family:Sora;font-weight:600;font-size:38px;margin:6px 0 8px">{t}</div>
    <div class="muted" style="font-size:24px;line-height:1.4">{d}</div>
    <div class="mono" style="font-size:22px;color:var(--acc);margin-top:12px">{code}</div></div>
</div>"""
        for i, (ic, t, d, code) in enumerate(steps)
    )
    return f"""
<div style="position:absolute;inset:0;padding:80px 80px">
  <div class="label">How it works</div>
  <h1 style="font-size:70px;margin:18px 0 36px">Your voice, in Darija,<br>from one API call.</h1>
  {rows}
</div>
<div class="foot" style="padding:0 80px"><span>MENA Voice API · Apache-2.0</span><span class="wm">intropera<i>.</i></span></div>"""


def api_call():
    curl = (
        'curl -X POST "$URL/tts" \\\n'
        '  -H "Authorization: Bearer $API_TOKEN" \\\n'
        "  -d '{\n"
        '    "voice": "rachid",\n'
        '    "model": "mar",\n'
        '    "text": "<span class="ar" style="display:inline">السلام عليكم، مرحبا بيكم</span>",\n'
        '    "format": "mp3"\n'
        "  }' -o hook.mp3"
    )
    models = (
        "".join(f'<span class="chip">{m} · Apache</span>' for m in ("mar", "msa", "egy", "alg", "irq"))
        + "".join(f'<span class="chip nc">{m} · non-commercial</span>' for m in ("sau", "uae", "unified"))
    )
    return f"""
<div style="position:absolute;inset:0;padding:90px 80px">
  <div class="label">One call</div>
  <h1 style="font-size:76px;margin:20px 0 40px">Text in.<br>Your voice out.</h1>
  <div class="glass" style="padding:34px 38px">
    <div style="display:flex;gap:10px;margin-bottom:22px"><i style="width:14px;height:14px;border-radius:50%;background:#ff5f57"></i>
      <i style="width:14px;height:14px;border-radius:50%;background:#febc2e"></i><i style="width:14px;height:14px;border-radius:50%;background:#28c840"></i></div>
    <pre class="mono" style="font-size:25px;line-height:1.55;white-space:pre-wrap;color:#D9DBF5">{curl}</pre>
  </div>
  <div class="glass" style="padding:28px 38px;margin-top:22px;display:flex;align-items:center;gap:26px">
    <div class="ico">{icon('speaker')}</div>
    <div style="flex:1"><div class="mono" style="font-size:24px;color:#7EE0A1">HTTP 200 · audio/mpeg</div>
      <div class="mono muted" style="font-size:22px;margin-top:6px">X-Seed: 42 · X-Audio-Seconds: 6.65</div></div>
    {wave(18, 52, 5)}
  </div>
  <div class="label" style="margin:40px 0 18px">Models</div>
  <div class="chips">{models}</div>
</div>
<div class="foot" style="padding:0 80px"><span>github.com/rachid-log/mena-voice-api</span><span class="wm">intropera<i>.</i></span></div>"""


# (output path, html, design size, output size)
JOBS = [
    (".intropera/cover.png", cover, (1920, 1080), (1920, 1080)),
    ("media/linkedin/01-cover-1200x627.png", cover, (1920, 1003), (1200, 627)),
    ("media/linkedin/02-how-it-works-1080x1350.png", how_it_works, (1080, 1350), (1080, 1350)),
    ("media/linkedin/03-api-call-1080x1350.png", api_call, (1080, 1350), (1080, 1350)),
]


def main():
    if not CHROME:
        sys.exit("Google Chrome or Chromium is needed")
    with tempfile.TemporaryDirectory() as tmp:
        for out, body, (dw, dh), (ow, oh) in JOBS:
            html = Path(tmp) / (Path(out).stem + ".html")
            html.write_text(page(body(), dw, dh, ow, oh), encoding="utf-8")
            target = ROOT / out
            target.parent.mkdir(parents=True, exist_ok=True)
            subprocess.run(
                [CHROME, "--headless=new", "--disable-gpu", "--hide-scrollbars", "--force-device-scale-factor=1",
                 f"--window-size={ow},{oh}", "--virtual-time-budget=15000", f"--screenshot={target}", html.as_uri()],
                check=True, capture_output=True,
            )
            print("wrote", out)


if __name__ == "__main__":
    main()
