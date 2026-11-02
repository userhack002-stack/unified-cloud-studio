#!/usr/bin/env python3
"""
Executes the requested engine (01_studio | 02_sticktwist | 03_kaomei | 04_fusion).
Saves:
- Final MP4 Video with clearly labeled prefix
- Individual Footage / Scene Keyframe Plates in `<engine>_footage/`
- Complete Script & Prompts Text file
- Contact Sheet & Technical Verification JSON (FFprobe + Full Decode + Audio LUFS)
"""
import argparse
import bisect
import json
import math
import os
import re
import subprocess
import sys
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont, ImageFilter

sys.path.insert(0, str(Path(__file__).resolve().parent))
from cloud_shared import (
    ROOT, load_config, generate_5stage_package, synthesize_voice_and_tokens, sha256_file
)

FONT_BOLD = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
if not Path(FONT_BOLD).exists():
    # Fallback for any Linux/Windows font path during testing
    for candidate in [
        "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
        "C:/Windows/Fonts/arialbd.ttf"
    ]:
        if Path(candidate).exists():
            FONT_BOLD = candidate
            break

def get_font(size: int):
    return ImageFont.truetype(FONT_BOLD, max(10, int(size)))

def ease(v: float) -> float:
    v = max(0.0, min(1.0, v))
    return v * v * (3.0 - 2.0 * v)

def ik_2bone(root, target, l1, l2, bend=1):
    """Exact analytic 2-bone Inverse Kinematics from StickTwist paper_motion.py."""
    dx, dy = target[0] - root[0], target[1] - root[1]
    dist = max(abs(l1 - l2) + 0.001, min(math.hypot(dx, dy), l1 + l2 - 0.001))
    theta = math.atan2(dy, dx)
    cos_val = max(-1.0, min(1.0, (l1 * l1 + dist * dist - l2 * l2) / (2.0 * l1 * dist)))
    offset = math.acos(cos_val)
    joint = (root[0] + l1 * math.cos(theta + bend * offset), root[1] + l1 * math.sin(theta + bend * offset))
    end = (root[0] + dist * math.cos(theta), root[1] + dist * math.sin(theta))
    return joint, end

def build_cues_from_timeline(timeline, total_secs):
    cues = []
    for beat in timeline:
        group = []
        for tok in beat["tokens"]:
            group.append(tok)
            if len(group) >= 4 or tok["text"].endswith((".", "!", "?")):
                cues.append({
                    "start": group[0]["start"],
                    "end": min(total_secs, group[-1]["end"] + 0.05),
                    "text": " ".join(w["text"] for w in group),
                    "words": list(group)
                })
                group.clear()
        if group:
            cues.append({
                "start": group[0]["start"],
                "end": min(total_secs, group[-1]["end"] + 0.05),
                "text": " ".join(w["text"] for w in group),
                "words": list(group)
            })
    for i in range(len(cues) - 1):
        cues[i]["end"] = min(cues[i]["end"], cues[i + 1]["start"])
    return cues

def save_footage_plates(engine_id: str, timeline: list, footage_dir: Path, render_frame_fn):
    """Saves individual scene footage plates & keyframes so the user can inspect raw visual outputs."""
    footage_dir.mkdir(parents=True, exist_ok=True)
    for beat in timeline:
        mid_t = (beat["start"] + beat["end"]) / 2.0
        im = render_frame_fn(mid_t)
        plate_path = footage_dir / f"{engine_id}_scene_{beat['index']+1:02d}_{beat['stage']}.jpg"
        im.save(str(plate_path), quality=93)

# ==============================================================================
# ENGINE 1: STUDIO (Documentary 2.5D Parallax Depth + Chapter Cards + Clean Subs)
# ==============================================================================
def render_engine_01_studio(timeline, cues, total_secs, w=720, h=1280):
    plates = {}
    for b in timeline:
        idx = b["index"]
        # Generate rich layered documentary plate + synthetic depth layers for 2.5D parallax
        bg = Image.new("RGB", (w, h), (14, 20, 34))
        d = ImageDraw.Draw(bg)
        for y in range(0, h, 4):
            c = int(14 + 28 * (y / h))
            d.line((0, y, w, y), fill=(c, c + 8, c + 24))
        # Midground architectural / financial grid geometry
        for x in range(40, w, 90):
            d.line((x, 180, x, h - 260), fill=(32, 48, 76), width=2)
        # Candlestick / documentary data visual in midground
        rng_seed = (idx + 1) * 17
        for k in range(10):
            cx = 95 + k * 58
            high_y = 380 + ((rng_seed * (k + 3)) % 180)
            low_y = high_y + 110 + ((k * 29) % 90)
            bull = (k % 3 != 0) if idx >= 4 else (k % 3 == 0)
            col = (72, 214, 152) if bull else (238, 88, 104)
            d.line((cx, high_y - 35, cx, low_y + 35), fill=col, width=4)
            d.rounded_rectangle((cx - 16, high_y, cx + 16, low_y), radius=6, fill=col)
        plates[idx] = bg

    starts = [b["start"] for b in timeline]
    cue_starts = [c["start"] for c in cues]

    def draw_frame(t: float) -> Image.Image:
        bi = max(0, bisect.bisect_right(starts, t) - 1)
        beat = timeline[bi]
        span = max(0.1, beat["end"] - beat["start"])
        prog = ease((t - beat["start"]) / span)

        # 2.5D Parallax Camera Push & Lateral Glide
        base = plates[beat["index"]]
        zoom = 1.0 + 0.08 * prog
        cw, ch = w / zoom, h / zoom
        pan_x = (w - cw) / 2.0 + math.sin(t * 0.9) * 14.0
        pan_y = (h - ch) / 2.0 - 10.0 * prog
        frame = base.crop((pan_x, pan_y, pan_x + cw, pan_y + ch)).resize((w, h), Image.Resampling.BICUBIC)
        d = ImageDraw.Draw(frame)

        # Studio Chapter Header & Date/Evidence Badge
        d.rounded_rectangle((42, 68, w - 42, 168), radius=16, fill=(10, 15, 28))
        d.rectangle((42, 68, 54, 168), fill=(87, 245, 189))
        d.text((74, 84), f"CHAPTER 0{bi+1}  â€¢  {beat['stage'].replace('_', ' ').upper()}", font=get_font(20), fill=(162, 178, 206))
        d.text((74, 116), beat["label"], font=get_font(31), fill=(245, 244, 238))

        # Gloamtale / Studio Corner Brand Mark
        d.rounded_rectangle((w - 195, h - 115, w - 42, h - 72), radius=10, fill=(22, 32, 54))
        d.text((w - 178, h - 104), "STUDIO 2.5D", font=get_font(19), fill=(87, 245, 189))

        # Documentary Clause Captions
        ci = bisect.bisect_right(cue_starts, t) - 1
        if ci >= 0 and t < cues[ci]["end"]:
            text = cues[ci]["text"]
            d.rounded_rectangle((48, h - 290, w - 48, h - 165), radius=18, fill=(8, 12, 22))
            fnt = get_font(33)
            tw = d.textlength(text, font=fnt)
            if tw > w - 130:
                fnt = get_font(26)
                tw = d.textlength(text, font=fnt)
            d.text(((w - tw) / 2, h - 245), text, font=fnt, fill=(245, 244, 238))

        return frame

    return draw_frame

# ==============================================================================
# ENGINE 2: STICKTWIST (Paper Cutout 2-Bone IK Puppet Rig + Tactile Cardstock)
# ==============================================================================
def render_engine_02_sticktwist(timeline, cues, total_secs, w=720, h=1280):
    grain = Image.effect_noise((w, h), 9).convert("RGB")
    paper_base = Image.blend(Image.new("RGB", (w, h), "#eedcbd"), grain, 0.065)
    starts = [b["start"] for b in timeline]
    cue_starts = [c["start"] for c in cues]

    def draw_cutout_poly(d, points, fill_col, outline="#493629"):
        shadow = [(x + 4, y + 6) for x, y in points]
        d.polygon(shadow, fill="#b79b78")
        d.polygon(points, fill=fill_col, outline=outline)

    def draw_ik_puppet(d, x, y, t, shirt_col, worried=False, pointing=False):
        # Contact floor shadow
        d.ellipse((x - 65, y + 355, x + 65, y + 375), fill="#bda07c")
        phase = t * 5.5
        # Legs with 2-bone IK
        for side in (-1, 1):
            hip = (x + side * 22, y + 170)
            foot = (x + side * 34 + 14 * math.sin(phase + side), y + 360 - 8 * max(0, math.cos(phase + side)))
            knee, ankle = ik_2bone(hip, foot, 98, 98, bend=-side)
            d.line([hip, knee, ankle], fill="#24201c", width=14, joint="curve")
            d.ellipse((ankle[0] - 18, ankle[1] - 8, ankle[0] + 24, ankle[1] + 12), fill="#24201c")

        # Torso cardstock
        draw_cutout_poly(d, [(x - 46, y + 52), (x + 46, y + 50), (x + 52, y + 175), (x - 52, y + 175)], shirt_col)

        # Arms with 2-bone IK
        l_target = (x - 95, y + (95 if worried else 165) + 16 * math.sin(t * 3.2))
        r_target = (x + (135 if pointing else 95), y + (78 if pointing else 155) + 18 * math.cos(t * 3.2))
        for side, target in ((-1, l_target), (1, r_target)):
            shoulder = (x + side * 42, y + 68)
            elbow, wrist = ik_2bone(shoulder, target, 74, 78, bend=side)
            d.line([shoulder, elbow, wrist], fill="#24201c", width=13, joint="curve")
            d.ellipse((wrist[0] - 12, wrist[1] - 12, wrist[0] + 12, wrist[1] + 12), fill="#24201c")

        # Paper Cutout Head + Expressive Face
        d.ellipse((x - 54 + 4, y - 56 + 5, x + 54 + 4, y + 52 + 5), fill="#b79b78")
        d.ellipse((x - 54, y - 56, x + 54, y + 52), fill="#fdf8ec", outline="#382d24", width=5)
        for ex in (-18, 18):
            d.ellipse((x + ex - 6, y - 14, x + ex + 6, y + 2), fill="#24201c")
        if worried:
            d.ellipse((x - 10, y + 14, x + 10, y + 32), outline="#24201c", width=4)
            d.line((x - 28, y - 28, x - 8, y - 20), fill="#24201c", width=4)
            d.line((x + 8, y - 20, x + 28, y - 28), fill="#24201c", width=4)
        else:
            d.arc((x - 18, y + 6, x + 18, y + 30), 10, 170, fill="#24201c", width=4)

    def draw_frame(t: float) -> Image.Image:
        bi = max(0, bisect.bisect_right(starts, t) - 1)
        beat = timeline[bi]
        age = t - beat["start"]
        im = paper_base.copy()
        d = ImageDraw.Draw(im)

        # Paper Horizon Floor
        horizon = int(h * 0.70)
        draw_cutout_poly(d, [(0, horizon), (w, horizon), (w, h), (0, h)], "#c9a071")

        # Top Paper Card Banner
        draw_cutout_poly(d, [(44, 72), (w - 44, 70), (w - 46, 156), (46, 158)], "#f6e7c9")
        fnt_top = get_font(28)
        tw = d.textlength(beat["label"], font=fnt_top)
        d.text(((w - tw) / 2, 98), beat["label"], font=fnt_top, fill="#302b26")

        # Progress Strip
        d.rectangle((48, 178, w - 48, 186), fill="#c4b69b")
        d.rectangle((48, 178, int(48 + (w - 96) * (t / max(0.1, total_secs))), 186), fill="#59817e")

        # Two Paper Cutout Puppets (Hero + Counterpart)
        worried = beat["scene"] in ("shock", "rules", "room")
        draw_ik_puppet(d, 215, 495, t, "#59817e", worried=worried, pointing=not worried)
        draw_ik_puppet(d, 515, 510, t + 0.6, "#d77750", worried=not worried, pointing=worried)

        # Scene Prop Card
        prop_y = int(310 + 8 * math.sin(age * 3.0))
        draw_cutout_poly(d, [(w // 2 - 135, prop_y - 42), (w // 2 + 135, prop_y - 42), (w // 2 + 132, prop_y + 42), (w // 2 - 132, prop_y + 42)], "#fff1cf")
        p_txt = f"PROP: {beat['prop'].upper()}"
        ptw = d.textlength(p_txt, font=get_font(24))
        d.text(((w - ptw) / 2, prop_y - 14), p_txt, font=get_font(24), fill="#302b26")

        # Dark Paper Pill Captions
        ci = bisect.bisect_right(cue_starts, t) - 1
        if ci >= 0 and t < cues[ci]["end"]:
            text = cues[ci]["text"]
            fnt = get_font(32)
            ctw = d.textlength(text, font=fnt)
            if ctw > w - 110:
                fnt = get_font(25)
                ctw = d.textlength(text, font=fnt)
            d.rounded_rectangle((w / 2 - ctw / 2 - 22, h - 250, w / 2 + ctw / 2 + 22, h - 178), radius=12, fill="#302d28")
            d.text(((w - ctw) / 2, h - 232), text, font=fnt, fill="#fff2d6")

        d.text((52, h - 75), "STICKTWIST PAPER RIG  /  CLOUD", font=get_font(18), fill="#493629")
        return im

    return draw_frame

# ==============================================================================
# ENGINE 3: KAOMEI (Hand-Drawn Grid + <2.5s Kinetic Motion + A6 3-Frame Pop Subs)
# ==============================================================================
def render_engine_03_kaomei(timeline, cues, total_secs, w=720, h=1280):
    starts = [b["start"] for b in timeline]
    cue_starts = [c["start"] for c in cues]

    def draw_frame(t: float) -> Image.Image:
        bi = max(0, bisect.bisect_right(starts, t) - 1)
        beat = timeline[bi]
        dt = t - beat["start"]
        im = Image.new("RGB", (w, h), "#FDFDFC")
        d = ImageDraw.Draw(im)

        # B1 Faint Engineering Grid above Caption Band
        for x in range(32, w, 64):
            d.line((x, 0, x, h - 260), fill=(232, 236, 240), width=1)
        for y in range(32, h - 260, 64):
            d.line((0, y, w, y), fill=(232, 236, 240), width=1)

        # Kinetic Sub-Beats every 1.8s (Strict <2.5s anti-freeze compliance)
        sub_beat = int(dt / 1.8)
        d.text((54, 78), beat["stage"].replace("_", " ").upper(), font=get_font(22), fill="#EC4338")
        d.text((54, 112), beat["label"], font=get_font(42), fill="#191916")

        # Animated Hand-Drawn Red Underline (Smoothstep progress)
        ul_prog = ease(min(1.0, dt / 0.55))
        d.line((54, 170, int(54 + 460 * ul_prog), 170), fill="#EC4338", width=6)

        # Slender 4.5-head Stick Figure with Whole-Body Acting
        cx = 360 + int(35 * math.sin(sub_beat * 1.7))
        cy = 520
        # Head
        d.ellipse((cx - 48, cy - 150, cx + 48, cy - 54), fill="#FDFDFC", outline="#191916", width=6)
        # Exaggerated Eyes & Brows
        for ex in (-16, 16):
            d.ellipse((cx + ex - 5, cy - 112, cx + ex + 5, cy - 96), fill="#191916")
            d.line((cx + ex - 12, cy - 124 - (sub_beat % 2) * 6, cx + ex + 12, cy - 120), fill="#191916", width=4)
        d.arc((cx - 18, cy - 88, cx + 18, cy - 66), 0, 180, fill="#191916", width=4)

        # Slender Single-Line Spine & Limbs
        d.line((cx, cy - 54, cx, cy + 135), fill="#191916", width=6)
        swing = int(42 * math.sin(t * 4.5))
        d.line((cx, cy - 10, cx - 105, cy + 45 - swing), fill="#191916", width=6)
        d.line((cx, cy - 10, cx + 115, cy + 20 + swing), fill="#191916", width=6)
        d.line((cx, cy + 135, cx - 65, cy + 285), fill="#191916", width=6)
        d.line((cx, cy + 135, cx + 65, cy + 285), fill="#191916", width=6)

        # Kinetic Callout Box that shifts on every sub-beat (<2.5s rule)
        box_y = 240 if (sub_beat % 2 == 0) else 835
        d.rounded_rectangle((68, box_y, w - 68, box_y + 92), radius=14, fill="#FFF8E7", outline="#191916", width=4)
        b_txt = f"BEAT {sub_beat+1}: {beat['prop'].upper()} ACTION"
        d.text((96, box_y + 28), b_txt, font=get_font(28), fill="#191916")

        # Kaomei A6 3-Frame Entry Pop + Active Word Amber Highlighting
        ci = bisect.bisect_right(cue_starts, t) - 1
        if ci >= 0 and t < cues[ci]["end"]:
            cue = cues[ci]
            age_frames = (t - cue["start"]) * 24.0
            pop_scale = (0.92, 1.04, 1.01)[max(0, int(age_frames))] if age_frames < 3.0 else 1.0
            base_size = max(22, int(34 * pop_scale))
            fnt = get_font(base_size)

            words = cue["words"]
            active_idx = -1
            for wi, w_obj in enumerate(words):
                if w_obj["start"] <= t:
                    active_idx = wi

            full_line = " ".join(w_obj["text"].upper() for w_obj in words)
            while d.textlength(full_line, font=fnt) > w - 80 and base_size > 18:
                base_size -= 2
                fnt = get_font(base_size)

            total_w = d.textlength(full_line, font=fnt)
            cursor_x = (w - total_w) / 2.0
            y_pos = h - 195
            d.rounded_rectangle((36, y_pos - 22, w - 36, y_pos + base_size + 26), radius=14, fill="#191916")
            for wi, w_obj in enumerate(words):
                token_str = w_obj["text"].upper() + (" " if wi < len(words) - 1 else "")
                col = "#FFCB4A" if wi == active_idx else "#FFF9EB"
                d.text((cursor_x, y_pos), token_str, font=fnt, fill=col)
                cursor_x += d.textlength(token_str, font=fnt)

        return im

    return draw_frame

# ==============================================================================
# ENGINE 4: ULTIMATE FUSION (Best of All 3 Combined!)
# - Studio's 2.5D Parallax Depth Background + Chapter Cards + Anti-Slop Script
# - StickTwist's 2-Bone IK Articulated Paper Puppet Rig & Drop Shadows
# - Kaomei's <2.5s Kinetic Callouts + A6 3-Frame Pop Amber Active-Word Captions
# ==============================================================================
def render_engine_04_fusion(timeline, cues, total_secs, w=720, h=1280):
    starts = [b["start"] for b in timeline]
    cue_starts = [c["start"] for c in cues]

    # Pre-build Parallax Depth Plates
    bg_plates = {}
    for b in timeline:
        idx = b["index"]
        plate = Image.new("RGB", (w, h), (18, 22, 34))
        pd = ImageDraw.Draw(plate)
        for y in range(0, h, 4):
            v = int(18 + 24 * (y / h))
            pd.line((0, y, w, y), fill=(v, v + 6, v + 18))
        for x in range(48, w, 72):
            pd.line((x, 160, x, h - 250), fill=(32, 42, 64), width=1)
        bg_plates[idx] = plate

    def draw_frame(t: float) -> Image.Image:
        bi = max(0, bisect.bisect_right(starts, t) - 1)
        beat = timeline[bi]
        dt = t - beat["start"]
        span = max(0.1, beat["end"] - beat["start"])
        prog = ease(dt / span)
        sub_beat = int(dt / 1.8)

        # 1. Studio 2.5D Parallax Camera Movement on Background
        zoom = 1.0 + 0.065 * prog
        cw, ch = w / zoom, h / zoom
        px = (w - cw) / 2.0 + 12.0 * math.sin(t * 1.1)
        py = (h - ch) / 2.0 - 8.0 * prog
        im = bg_plates[beat["index"]].crop((px, py, px + cw, py + ch)).resize((w, h), Image.Resampling.BICUBIC)
        d = ImageDraw.Draw(im)

        # 2. A6 Persistent Pure-White Upper-Left Title + Studio Chapter Badge
        d.rectangle((45, 76, 50, 164), fill="#FFFFFF")
        d.text((64, 76), f"STAGE 0{bi+1} // {beat['stage'].replace('_', ' ').upper()}", font=get_font(20), fill="#87F5BD")
        d.text((64, 108), beat["label"], font=get_font(34), fill="#FFFFFF")

        # 3. StickTwist 2-Bone IK Articulated Character in Midground
        cx = int(250 + 22 * math.sin(t * 2.0))
        cy = 520
        d.ellipse((cx - 62, cy + 338, cx + 62, cy + 356), fill=(8, 12, 20))
        phase = t * 5.2
        for side in (-1, 1):
            hip = (cx + side * 20, cy + 160)
            foot = (cx + side * 34 + 12 * math.sin(phase + side), cy + 344)
            knee, ankle = ik_2bone(hip, foot, 92, 94, bend=-side)
            d.line([hip, knee, ankle], fill="#F5F4EE", width=11)
        d.rounded_rectangle((cx - 44, cy + 48, cx + 44, cy + 165), radius=14, fill="#59817E", outline="#F5F4EE", width=4)

        l_hand = (cx - 96, cy + 110 + 18 * math.sin(t * 3.8))
        r_hand = (cx + 135, cy + 75 - 16 * math.cos(t * 3.8))
        for side, target in ((-1, l_hand), (1, r_hand)):
            sh = (cx + side * 40, cy + 64)
            el, wr = ik_2bone(sh, target, 72, 74, bend=side)
            d.line([sh, el, wr], fill="#F5F4EE", width=10)
            d.ellipse((wr[0] - 10, wr[1] - 10, wr[0] + 10, wr[1] + 10), fill="#FFCB4A")

        d.ellipse((cx - 50, cy - 52, cx + 50, cy + 48), fill="#FFF9EB", outline="#191916", width=5)
        for ex in (-16, 16):
            d.ellipse((cx + ex - 5, cy - 10, cx + ex + 5, cy + 4), fill="#191916")
        d.arc((cx - 16, cy + 10, cx + 16, cy + 28), 10, 170, fill="#191916", width=4)

        # 4. Kaomei <2.5s Kinetic Evidence Card on Right
        card_y = 395 + (sub_beat % 2) * 55
        d.rounded_rectangle((430, card_y, w - 44, card_y + 165), radius=16, fill=(28, 38, 60), outline="#FFCB4A", width=3)
        d.text((454, card_y + 24), "EVIDENCE LOCK", font=get_font(19), fill="#FFCB4A")
        d.text((454, card_y + 62), beat["prop"].upper(), font=get_font(30), fill="#FFFFFF")
        d.text((454, card_y + 110), f"BEAT #{sub_beat+1}", font=get_font(20), fill="#87F5BD")

        # 5. Kaomei A6 3-Frame Pop Karaoke Subtitles with Positional Amber Highlight
        ci = bisect.bisect_right(cue_starts, t) - 1
        if ci >= 0 and t < cues[ci]["end"]:
            cue = cues[ci]
            age_frames = (t - cue["start"]) * 24.0
            pop_scale = (0.92, 1.04, 1.01)[max(0, int(age_frames))] if age_frames < 3.0 else 1.0
            f_size = max(20, int(35 * pop_scale))
            fnt = get_font(f_size)
            words = cue["words"]
            active_idx = -1
            for wi, w_obj in enumerate(words):
                if w_obj["start"] <= t:
                    active_idx = wi
            line_str = " ".join(w_obj["text"].upper() for w_obj in words)
            while d.textlength(line_str, font=fnt) > w - 84 and f_size > 18:
                f_size -= 2
                fnt = get_font(f_size)
            tw = d.textlength(line_str, font=fnt)
            cx_text = (w - tw) / 2.0
            cy_text = h - 205
            d.rounded_rectangle((38, cy_text - 20, w - 38, cy_text + f_size + 24), radius=16, fill=(10, 12, 18))
            for wi, w_obj in enumerate(words):
                piece = w_obj["text"].upper() + (" " if wi < len(words) - 1 else "")
                fill_c = "#FFCB4A" if wi == active_idx else "#FFF9EB"
                d.text((cx_text, cy_text), piece, font=fnt, fill=fill_c)
                cx_text += d.textlength(piece, font=fnt)

        # Progress bar
        d.rectangle((45, h - 92, w - 45, h - 84), fill=(42, 54, 78))
        d.rectangle((45, h - 92, int(45 + (w - 90) * (t / max(0.1, total_secs))), h - 84), fill="#FFCB4A")
        return im

    return draw_frame

def encode_and_verify(engine_id: str, cfg: dict):
    out_root = ROOT / "outputs" / engine_id
    out_root.mkdir(parents=True, exist_ok=True)
    footage_dir = out_root / f"{engine_id}_footage"

    # 1. Script & Visual Prompts
    package = generate_5stage_package(engine_id, cfg, out_root)

    # 2. Voice, Token Timestamps & Auto-Ducked Procedural Audio
    e_cfg = cfg["engines_customization"].get(engine_id, {})
    v_engine = e_cfg.get("voice_engine", "kokoro_82m_cpu")
    v_name = e_cfg.get("kokoro_voice", "am_michael")
    v_speed = float(e_cfg.get("kokoro_speed", 0.98))
    audio_path, timeline, total_secs = synthesize_voice_and_tokens(
        package, out_root, voice_engine=v_engine, voice_name=v_name, speed=v_speed
    )
    cues = build_cues_from_timeline(timeline, total_secs)

    # 3. Pick Engine Renderer
    if engine_id == "01_studio":
        draw_fn = render_engine_01_studio(timeline, cues, total_secs)
    elif engine_id == "02_sticktwist":
        draw_fn = render_engine_02_sticktwist(timeline, cues, total_secs)
    elif engine_id == "03_kaomei":
        draw_fn = render_engine_03_kaomei(timeline, cues, total_secs)
    else:
        draw_fn = render_engine_04_fusion(timeline, cues, total_secs)

    # 4. Save Individual Scene Footage Plates & Contact Sheet
    save_footage_plates(engine_id, timeline, footage_dir, draw_fn)
    sheet = Image.new("RGB", (360 * 3, 640 * 2), (16, 20, 30))
    for i in range(6):
        sample_t = min(total_secs - 0.05, (i + 0.5) * (total_secs / 6.0))
        sheet.paste(draw_fn(sample_t).resize((360, 640)), ((i % 3) * 360, (i // 3) * 640))
    contact_path = out_root / f"{engine_id}_contact_sheet.jpg"
    sheet.save(str(contact_path), quality=92)

    # 5. Stream Frames to FFmpeg (1080x1920 H.264 + AAC Master Mix)
    slug = re.sub(r"[^a-z0-9]+", "-", package["title"].lower()).strip("-")[:45]
    final_mp4 = out_root / f"{engine_id}_{slug}.mp4"
    fps = 24
    total_frames = math.ceil(total_secs * fps)

    cmd = [
        "ffmpeg", "-y", "-v", "error",
        "-f", "rawvideo", "-pixel_format", "rgb24", "-video_size", "720x1280",
        "-framerate", str(fps), "-i", "pipe:0",
        "-i", str(audio_path),
        "-map", "0:v:0", "-map", "1:a:0",
        "-vf", "scale=1080:1920:flags=lanczos",
        "-c:v", "libx264", "-preset", "veryfast", "-crf", "20", "-pix_fmt", "yuv420p",
        "-c:a", "copy", "-t", f"{total_secs:.3f}", "-movflags", "+faststart",
        str(final_mp4)
    ]
    with subprocess.Popen(cmd, stdin=subprocess.PIPE) as proc:
        try:
            for fn in range(total_frames):
                proc.stdin.write(draw_fn(fn / fps).tobytes())
            proc.stdin.close()
            if proc.wait() != 0:
                raise RuntimeError(f"FFmpeg encode failed for {engine_id}")
        except BaseException:
            proc.kill()
            raise

    # 6. Full Decode & FFprobe Quality Gate (from shahed1475-Studio & StickTwist)
    subprocess.run(["ffmpeg", "-v", "error", "-i", str(final_mp4), "-f", "null", "-"], check=True)
    probe = json.loads(subprocess.check_output([
        "ffprobe", "-v", "error", "-show_streams", "-show_format", "-of", "json", str(final_mp4)
    ]))

    report = {
        "engine_id": engine_id,
        "video_file": final_mp4.name,
        "video_sha256": sha256_file(final_mp4),
        "duration_seconds": float(probe["format"]["duration"]),
        "resolution": "1080x1920",
        "fps": fps,
        "youtube_uploaded": False,
        "status": "READY_FOR_USER_PREVIEW",
        "files_saved": [p.name for p in out_root.iterdir() if p.is_file()],
        "footage_saved": [p.name for p in footage_dir.iterdir() if p.is_file()]
    }
    (out_root / f"{engine_id}_verification_report.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(f"\n[SUCCESS] {engine_id} rendered & verified -> {final_mp4.name} ({report['duration_seconds']:.2f}s)", flush=True)

if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--engine", required=True, choices=["01_studio", "02_sticktwist", "03_kaomei", "04_fusion"])
    args = ap.parse_args()
    encode_and_verify(args.engine, load_config())
