# Unified 4-in-1 Cloud Video Studio

100% Cloud-Native (GitHub Actions + Free OpenRouter/Gemini + Kokoro-82M CPU + Optional Kaggle GPU).
**YouTube Auto-Upload is strictly DISABLED** so you can visually inspect all 4 outputs first.

## What Each of the 4 Engines Produces
| Engine ID | Output Video Prefix | Core Technology Used |
| :--- | :--- | :--- |
| **`01_studio`** | `01_studio_<slug>.mp4` | `shahed1475-Studio` 2.5D Parallax camera push, documentary chapter cards, anti-AI slop filter, -16 LUFS mastering |
| **`02_sticktwist`** | `02_sticktwist_<slug>.mp4` | `porkikk2-StickTwist` 2-Bone Inverse Kinematics (IK) paper-cutout puppet rig, cardstock drop shadows, Kokoro-82M voice |
| **`03_kaomei`** | `03_kaomei_<slug>.mp4` | `kaomei` B1/B2 hand-drawn grid, strict `<2.5s` visual change rule, and `a6_finish.py` 3-frame pop amber karaoke subtitles |
| **`04_fusion`** | `04_fusion_<slug>.mp4` | **Ultimate Upgrade:** Studio 2.5D Parallax + StickTwist 2-Bone IK Puppet + Kaomei A6 3-Frame Pop Karaoke Subtitles + Kokoro-82M Token Sync + Sidechain Auto-Ducked Procedural SFX |

## Where to Customize Everything (Single File!)
Open **`config/master-config.json`**:
- `global_topic.topic`: Change the topic/script brief for all 4 engines at once.
- `engines_customization.02_sticktwist.kokoro_voice`: Switch between `am_michael`, `bm_george`, `af_heart`.
- `engines_customization.02_sticktwist.character_hero_shirt`: Change character shirt hex colors.
- `engines_customization.03_kaomei.a6_active_word_color`: Change the active spoken word highlight color.

## How to Run on GitHub (3 Steps)
1. Push this folder to a **GitHub Repository**.
2. *(Optional)* In **Settings -> Secrets and variables -> Actions**, add `GEMINI_API_KEY` or `OPENROUTER_API_KEY` (uses 100% `:free` models; if left blank, the built-in 5-Stage deterministic script engine runs automatically at $0).
3. Go to **Actions -> 4-in-1 Cloud Video Studio -> Run workflow**. Select any 1, 2, 3, or all 4 engines. They will run **one by one (`max-parallel: 1`)**, display live scripts & prompts in their respective tabs, and save all `.mp4`, `.txt` prompts, and scene footage in **Releases (Drafts)** and **Workflow Artifacts**.
