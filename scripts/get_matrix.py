#!/usr/bin/env python3
import json
import os

items = []
if os.environ.get("RUN_01_STUDIO") == "true":
    items.append({"id": "01_studio", "label": "Part 1 • Studio (2.5D Documentary)"})
if os.environ.get("RUN_02_STICKTWIST") == "true":
    items.append({"id": "02_sticktwist", "label": "Part 2 • StickTwist (Paper Cutout IK)"})
if os.environ.get("RUN_03_KAOMEI") == "true":
    items.append({"id": "03_kaomei", "label": "Part 3 • Kaomei (Hand-Drawn + A6 Pop)"})
if os.environ.get("RUN_04_FUSION") == "true":
    items.append({"id": "04_fusion", "label": "Part 4 • Ultimate Fusion (All-in-One)"})

if not items:
    items.append({"id": "04_fusion", "label": "Part 4 • Ultimate Fusion (All-in-One)"})

output_path = os.environ.get("GITHUB_OUTPUT")
if output_path:
    with open(output_path, "a") as f:
        f.write(f"matrix={json.dumps({'include': items})}\n")