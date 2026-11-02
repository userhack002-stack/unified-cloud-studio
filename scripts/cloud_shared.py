#!/usr/bin/env python3
"""
Shared Cloud Core for Unified 4-in-1 Studio.
Handles:
1. Cloud-Only Guard & Config Loader
2. 100% Free LLM Router (Gemini API Free -> OpenRouter :free -> Deterministic Offline Fallback)
3. Anti-AI Slop Scrubber (from shahed1475-Studio voice-rules.md)
4. 5-Stage Heartbeat Script Generator & Prompt Logger (from kaomei)
5. Free Neural Voice Synthesis (Kokoro-82M CPU w/ token timestamps OR Edge-TTS)
6. Procedural Math SFX & Sidechain Auto-Ducked Music (from StickTwist & kaomei)
"""
import hashlib
import json
import math
import os
import re
import shutil
import subprocess
import sys
import urllib.request
import urllib.error
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CONFIG_PATH = ROOT / "config" / "master-config.json"

FORBIDDEN_AI_WORDS = [
    "delve", "tapestry", "leverage", "utilize", "facilitate", "streamline",
    "robust", "seamless", "navigate", "unlock", "harness", "foster",
    "fundamentally", "essentially", "ultimately", "crucially", "notably",
    "landscape", "ecosystem", "paradigm", "realm", "game-changer", "deep dive",
    "in today's fast-paced world", "without further ado", "smash that like button"
]

def load_config():
    return json.loads(CONFIG_PATH.read_text(encoding="utf-8"))

def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1048576), b""):
            h.update(chunk)
    return h.hexdigest()

def scrub_ai_slop(text: str) -> str:
    cleaned = text
    for word in FORBIDDEN_AI_WORDS:
        cleaned = re.sub(rf"\b{re.escape(word)}\b", "", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"\s{2,}", " ", cleaned).replace("â€”", ", ")
    return cleaned.strip()

def call_free_llm(prompt: str, cfg: dict) -> str:
    """Tries Google Gemini Free API first, then OpenRouter :free models, then deterministic fallback."""
    gemini_key = os.environ.get("GEMINI_API_KEY", "").strip()
    openrouter_key = os.environ.get("OPENROUTER_API_KEY", "").strip()

    if gemini_key:
        try:
            model = cfg["free_ai_routing"].get("gemini_direct_model", "gemini-2.5-flash")
            url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={gemini_key}"
            payload = json.dumps({
                "contents": [{"parts": [{"text": prompt}]}],
                "generationConfig": {"temperature": 0.7}
            }).encode("utf-8")
            req = urllib.request.Request(url, data=payload, headers={"Content-Type": "application/json"}, method="POST")
            with urllib.request.urlopen(req, timeout=60) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                return data["candidates"][0]["content"]["parts"][0]["text"]
        except Exception as e:
            print(f"[LLM Router] Gemini Free API notice: {e}", flush=True)

    if openrouter_key:
        for model_key in ["script_model_free", "fallback_model_free"]:
            model = cfg["free_ai_routing"].get(model_key, "meta-llama/llama-3.3-70b-instruct:free")
            try:
                url = "https://openrouter.ai/api/v1/chat/completions"
                payload = json.dumps({
                    "model": model,
                    "messages": [{"role": "user", "content": prompt}],
                    "temperature": 0.7
                }).encode("utf-8")
                req = urllib.request.Request(
                    url, data=payload,
                    headers={
                        "Authorization": f"Bearer {openrouter_key}",
                        "Content-Type": "application/json",
                        "HTTP-Referer": "https://github.com/unified-cloud-studio"
                    },
                    method="POST"
                )
                with urllib.request.urlopen(req, timeout=60) as resp:
                    data = json.loads(resp.read().decode("utf-8"))
                    return data["choices"][0]["message"]["content"]
            except Exception as e:
                print(f"[LLM Router] OpenRouter ({model}) notice: {e}", flush=True)

    return ""

def generate_5stage_package(engine_id: str, cfg: dict, out_dir: Path) -> dict:
    """
    Generates a 6-beat (5-Stage Heartbeat Engine) script + visual prompts + SFX cues.
    Logs everything visibly to stdout (for GitHub Actions tab visibility) and saves to disk.
    """
    topic_cfg = cfg["global_topic"]
    topic = topic_cfg["topic"]

    prompt = f"""You are writing for Engine {engine_id}.
Topic: {topic}
Niche: {topic_cfg['niche']}
Follow the 5-Stage High-Completion Heartbeat Engine AND strict anti-AI voice rules (no 'delve', 'tapestry', 'leverage', 'game-changer', no greetings).
Return ONLY valid JSON with this exact schema:
{{
  "title": "Under 60 chars, curiosity + concrete noun",
  "thumbnail_text": "3 WORDS MAX",
  "beats": [
    {{"stage": "1_Golden_Hook", "label": "THE $10,000 FREEZE", "scene": "shock", "prop": "phone", "sfx": "notification", "text": "Spoken line 1 (18-22 words)", "visual_prompt": "Detailed scene & motion description"}},
    {{"stage": "2_Disrupt_Assumption", "label": "NOT GREED. FEAR.", "scene": "rules", "prop": "note", "sfx": "paper", "text": "Spoken line 2 (18-22 words)", "visual_prompt": "Detailed scene & motion description"}},
    {{"stage": "3_Insider_Mechanism", "label": "CORTISOL SPIKE", "scene": "room", "prop": "console", "sfx": "whoosh", "text": "Spoken line 3 (18-22 words)", "visual_prompt": "Detailed scene & motion description"}},
    {{"stage": "4_Escalation_Trap", "label": "CHASING THE LOSS", "scene": "deal", "prop": "cash", "sfx": "step", "text": "Spoken line 4 (18-22 words)", "visual_prompt": "Detailed scene & motion description"}},
    {{"stage": "5_Ultimate_Truth", "label": "PRE-COMMIT THE EXIT", "scene": "reveal", "prop": "key", "sfx": "reveal", "text": "Spoken line 5 (18-22 words)", "visual_prompt": "Detailed scene & motion description"}},
    {{"stage": "6_Payoff_Callback", "label": "SYSTEM OVER EMOTION", "scene": "winner", "prop": "mug", "sfx": "notification", "text": "Spoken line 6 (18-22 words)", "visual_prompt": "Detailed scene & motion description"}}
  ]
}}"""

    raw = call_free_llm(prompt, cfg)
    package = None
    if raw:
        m = re.search(r"\{[\s\S]*\}", raw)
        if m:
            try:
                package = json.loads(m.group(0))
            except Exception:
                package = None

    if not package or not isinstance(package.get("beats"), list) or len(package["beats"]) < 6:
        # High-craft deterministic fallback tailored to the configured topic
        package = {
            "title": "Why 90% of Traders Freeze at the Worst Second",
            "thumbnail_text": "FROZEN AT ZERO",
            "beats": [
                {
                    "stage": "1_Golden_Hook",
                    "label": "THE 3-SECOND FREEZE",
                    "scene": "shock",
                    "prop": "phone",
                    "sfx": "notification",
                    "text": "At two fifty-nine, the chart dropped four percent, and my thumb froze right above the sell button.",
                    "visual_prompt": f"[{engine_id}] High-contrast close-up of character staring at a glowing red screen drop; sudden camera push-in."
                },
                {
                    "stage": "2_Disrupt_Assumption",
                    "label": "NOT IGNORANCE. BIOLOGY.",
                    "scene": "rules",
                    "prop": "note",
                    "sfx": "paper",
                    "text": "Most people think bad trades come from bad math. In reality, your brain treats a paper loss like a physical predator.",
                    "visual_prompt": f"[{engine_id}] Character steps back as three warning cards snap onto the board with a sharp red cross."
                },
                {
                    "stage": "3_Insider_Mechanism",
                    "label": "LOSS AVERSION TRAP",
                    "scene": "room",
                    "prop": "console",
                    "sfx": "whoosh",
                    "text": "Losing one hundred dollars hurts twice as much as winning one hundred feels good. So you hold the loser just to avoid admitting it.",
                    "visual_prompt": f"[{engine_id}] Balance scale tips sharply downward under a heavy red block while the clock ticks backward."
                },
                {
                    "stage": "4_Escalation_Trap",
                    "label": "HOPE IS NOT A PLAN",
                    "scene": "deal",
                    "prop": "cash",
                    "sfx": "step",
                    "text": "Every second you wait for the bounce, you stop being a strategist and start bargaining with a screen that cannot hear you.",
                    "visual_prompt": f"[{engine_id}] Character reaches toward floating banknotes that dissolve into dotted lines before contact."
                },
                {
                    "stage": "5_Ultimate_Truth",
                    "label": "DECIDE BEFORE ENTRY",
                    "scene": "reveal",
                    "prop": "key",
                    "sfx": "reveal",
                    "text": "Professionals never decide their exit while the candle is moving. They lock the stop-loss before a single dollar is at risk.",
                    "visual_prompt": f"[{engine_id}] Character turns a solid brass key locking a clean rule-card in place; camera settles."
                },
                {
                    "stage": "6_Payoff_Callback",
                    "label": "BORING WINS.",
                    "scene": "winner",
                    "prop": "mug",
                    "sfx": "notification",
                    "text": "When the next drop came, the order fired automatically. I drank my coffee in silence. Which rule saves you when panic hits?",
                    "visual_prompt": f"[{engine_id}] Calm wide shot; character sets mug on counter as the progress bar completes cleanly."
                }
            ]
        }

    for b in package["beats"]:
        b["text"] = scrub_ai_slop(b["text"])

    # Print visibly to GitHub Actions console tab!
    print("\n" + "=" * 72, flush=True)
    print(f" LIVE SCRIPT & PROMPTS FOR ENGINE: {engine_id}", flush=True)
    print(f" TITLE: {package['title']}  |  THUMBNAIL: {package['thumbnail_text']}", flush=True)
    print("=" * 72, flush=True)

    txt_lines = [
        f"ENGINE: {engine_id}",
        f"GENERATED_AT_UTC: {datetime.now(timezone.utc).isoformat()}",
        f"TOPIC: {topic}",
        f"TITLE: {package['title']}",
        f"THUMBNAIL_HOOK: {package['thumbnail_text']}",
        "=" * 72,
        ""
    ]
    for idx, b in enumerate(package["beats"], 1):
        line_info = (
            f"[Beat {idx:02d} | {b['stage']} | Scene: {b['scene']} | Prop: {b['prop']} | SFX: {b['sfx']}]\n"
            f"  LABEL        : {b['label']}\n"
            f"  SPOKEN VO    : \"{b['text']}\"\n"
            f"  VISUAL PROMPT: {b['visual_prompt']}\n"
        )
        print(line_info, flush=True)
        txt_lines.append(line_info)

    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / f"{engine_id}_script_and_prompts.txt").write_text("\n".join(txt_lines), encoding="utf-8")
    (out_dir / f"{engine_id}_package.json").write_text(json.dumps(package, indent=2), encoding="utf-8")
    return package

def synthesize_voice_and_tokens(package: dict, out_dir: Path, voice_engine="kokoro_82m_cpu", voice_name="am_michael", speed=0.98):
    """
    Synthesizes narration and extracts exact word-level timestamps.
    Uses Kokoro-82M CPU (from StickTwist) when selected/available, falling back cleanly to Edge-TTS / espeak-ng.
    """
    import numpy as np
    import soundfile as sf

    sr = 24000
    out_dir.mkdir(parents=True, exist_ok=True)
    timeline = []
    full_audio_parts = []
    clock = 0.0

    use_kokoro = (voice_engine == "kokoro_82m_cpu")
    kokoro_pipe = None
    if use_kokoro:
        try:
            import torch
            from kokoro import KPipeline, KModel
            torch.set_num_threads(2)
            model = KModel(repo_id="hexgrad/Kokoro-82M").to("cpu").eval()
            kokoro_pipe = KPipeline(lang_code="a", repo_id="hexgrad/Kokoro-82M", model=model)
            print(f"[Audio] Loaded Kokoro-82M CPU neural voice: {voice_name}", flush=True)
        except Exception as e:
            print(f"[Audio] Kokoro fallback to Edge-TTS ({e})", flush=True)
            kokoro_pipe = None

    for i, beat in enumerate(package["beats"]):
        text = beat["text"]
        beat_tokens = []
        segment = None

        if kokoro_pipe is not None:
            arrays = []
            chunk_clock = 0.0
            for res in kokoro_pipe(text, voice=voice_name, speed=speed, split_pattern=r"\n+"):
                gs, ps, audio = res
                if audio is None:
                    continue
                arr = audio.detach().cpu().numpy() if hasattr(audio, "detach") else np.asarray(audio)
                secs = len(arr) / sr
                for tok in getattr(res, "tokens", None) or []:
                    st = getattr(tok, "start_ts", None)
                    en = getattr(tok, "end_ts", None)
                    if st is not None and en is not None and en > st:
                        beat_tokens.append({
                            "text": tok.text.strip(),
                            "start": round(clock + chunk_clock + max(0.0, st), 3),
                            "end": round(clock + chunk_clock + min(secs, en), 3)
                        })
                arrays.append(arr)
                chunk_clock += secs
            if arrays:
                segment = np.concatenate(arrays)

        if segment is None:
            # Edge-TTS or espeak-ng fallback
            tmp_mp3 = out_dir / f"beat_{i}.mp3"
            tmp_wav = out_dir / f"beat_{i}.wav"
            edge_ok = False
            if shutil.which("edge-tts"):
                r = subprocess.run([
                    "edge-tts", "--voice", "en-US-ChristopherNeural",
                    "--text", text, "--write-media", str(tmp_mp3)
                ], capture_output=True)
                edge_ok = (r.returncode == 0 and tmp_mp3.exists() and tmp_mp3.stat().st_size > 200)
            if edge_ok:
                subprocess.run([
                    "ffmpeg", "-y", "-v", "error", "-i", str(tmp_mp3),
                    "-ar", str(sr), "-ac", "1", str(tmp_wav)
                ], check=True)
            else:
                subprocess.run([
                    "espeak-ng", "-v", "en-us", "-s", "155", "-w", str(tmp_wav), text
                ], check=True)
            segment, _ = sf.read(str(tmp_wav), dtype="float32")
            if segment.ndim > 1:
                segment = segment[:, 0]

        spoken_secs = len(segment) / sr
        if not beat_tokens:
            # Proportional character-weighted token timing if native tokens weren't returned
            words = text.split()
            weights = [max(1, len(re.sub(r"\W", "", w))) for w in words]
            total_w = sum(weights) or 1
            el = 0
            for w, wg in zip(words, weights):
                st = clock + spoken_secs * (el / total_w)
                el += wg
                en = clock + spoken_secs * (el / total_w)
                beat_tokens.append({"text": w, "start": round(st, 3), "end": round(en, 3)})

        timeline.append({
            "index": i,
            "stage": beat["stage"],
            "label": beat["label"],
            "scene": beat["scene"],
            "prop": beat["prop"],
            "sfx": beat["sfx"],
            "text": text,
            "visual_prompt": beat["visual_prompt"],
            "start": round(clock, 3),
            "spoken_seconds": round(spoken_secs, 3),
            "end": round(clock + spoken_secs + 0.18, 3),
            "tokens": beat_tokens
        })
        full_audio_parts.extend([segment, np.zeros(round(0.18 * sr), dtype=np.float32)])
        clock += spoken_secs + 0.18

    raw_wav = out_dir / "voice_raw.wav"
    clean_wav = out_dir / "voice_clean.wav"
    sf.write(str(raw_wav), np.concatenate(full_audio_parts), sr, subtype="PCM_16")
    subprocess.run([
        "ffmpeg", "-y", "-v", "error", "-i", str(raw_wav),
        "-af", "loudnorm=I=-16:TP=-1.5:LRA=7", "-ar", str(sr), "-ac", "1", str(clean_wav)
    ], check=True)

    # Procedural Music & SFX with Sidechain Auto-Ducking (from StickTwist audio_auditions.py)
    total_secs = clock
    n_samples = round(total_secs * sr)
    bed = np.zeros(n_samples, dtype=np.float32)
    beat_len = 60.0 / 92.0
    pitches = [146.83, 220.0, 261.63, 220.0, 164.81, 246.94, 293.66, 246.94]
    for idx in range(int(total_secs / (beat_len / 2)) + 1):
        at = idx * (beat_len / 2)
        st_i = round(at * sr)
        cnt = min(round(beat_len * 0.85 * sr), n_samples - st_i)
        if cnt <= 0:
            continue
        t = np.arange(cnt) / sr
        env = np.minimum(t / 0.025, 1.0) * np.exp(-t / 0.45)
        freq = pitches[idx % len(pitches)]
        tone = np.sin(2 * np.pi * freq * t) + 0.18 * np.sin(2 * np.pi * freq * 2 * t)
        bed[st_i:st_i + cnt] += (0.05 * env * tone).astype(np.float32)

    sfx_track = np.zeros(n_samples, dtype=np.float32)
    rng = np.random.default_rng(42)
    for b in timeline:
        at_i = round((b["start"] + 0.08) * sr)
        kind = b.get("sfx", "pop")
        dur_s = 0.42 if kind in ("paper", "whoosh", "notification") else 0.22
        t = np.arange(round(dur_s * sr)) / sr
        if kind == "paper":
            snd = 0.10 * np.diff(rng.normal(0, 1, len(t)), prepend=0) * (np.sin(np.pi * t / dur_s) ** 2)
        elif kind == "whoosh":
            snd = 0.12 * rng.normal(0, 1, len(t)) * (np.sin(np.pi * t / dur_s) ** 3)
        elif kind == "notification":
            snd = 0.12 * (np.sin(2 * np.pi * 880 * t) + 0.45 * np.sin(2 * np.pi * 1320 * t)) * np.exp(-t * 9)
        elif kind == "reveal":
            snd = 0.13 * (np.sin(2 * np.pi * 110 * t) + 0.35 * np.sin(2 * np.pi * 220 * t)) * np.exp(-t * 4.5)
        else:
            snd = 0.12 * np.sin(2 * np.pi * (480 - 700 * t) * t) * np.exp(-t * 22)
        cnt = min(len(snd), n_samples - at_i)
        if cnt > 0:
            sfx_track[at_i:at_i + cnt] += snd[:cnt].astype(np.float32)

    bed_wav = out_dir / "music_bed.wav"
    sfx_wav = out_dir / "sfx_track.wav"
    mixed_m4a = out_dir / "master_mix.m4a"
    sf.write(str(bed_wav), bed, sr, subtype="PCM_16")
    sf.write(str(sfx_wav), sfx_track, sr, subtype="PCM_16")

    filters = (
        "[0:a]asplit=2[voice][key];"
        "[1:a]volume=0.28[music];"
        "[music][key]sidechaincompress=threshold=0.015:ratio=6:attack=15:release=300[duck];"
        "[2:a]volume=0.40[fx];"
        "[voice][duck][fx]amix=inputs=3:duration=first:normalize=0,alimiter=limit=0.92:level=false[out]"
    )
    subprocess.run([
        "ffmpeg", "-y", "-v", "error",
        "-i", str(clean_wav), "-i", str(bed_wav), "-i", str(sfx_wav),
        "-filter_complex", filters, "-map", "[out]",
        "-c:a", "aac", "-b:a", "192k", str(mixed_m4a)
    ], check=True)

    (out_dir / "timeline.json").write_text(json.dumps(timeline, indent=2), encoding="utf-8")
    return mixed_m4a, timeline, total_secs
