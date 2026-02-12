#!/usr/bin/env python3
"""
Caring With Grace Logo Refresh - Master Build Script
Generates all SVG logo variants with consistent colors and multiple layouts.
"""

import os
import re
import subprocess
import xml.etree.ElementTree as ET
from PIL import Image

# ============================================================
# CONFIGURATION
# ============================================================

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
SVG_DIR = os.path.join(BASE_DIR, "svg")
PNG_DIR = os.path.join(BASE_DIR, "png")
WORK_DIR = "/tmp/cwg_trace"
SRC_IMAGE = os.path.join(BASE_DIR, "..", "Logos", "Logos",
                         "Caring With Grace Logo_Hi Res  increased pixels.png")

os.makedirs(SVG_DIR, exist_ok=True)
os.makedirs(PNG_DIR, exist_ok=True)

# Brand color palettes
COLORS = {
    "hotpink": {
        "name": "Vivid Hot Pink",
        "butterfly_fill": "#E0548A",
        "butterfly_dark": "#9E2D5E",
        "butterfly_light": "#F0A0BF",
        "text": "#1A1A1A",
        "tagline": "#3A3A3A",
        "teal_accent": "#9FD1D6",
    },
    "dustyrose": {
        "name": "Soft Dusty Rose",
        "butterfly_fill": "#D4899E",
        "butterfly_dark": "#8C4A60",
        "butterfly_light": "#EBBFCC",
        "text": "#1A1A1A",
        "tagline": "#3A3A3A",
        "teal_accent": "#9FD1D6",
    },
}

# Layout configurations
LAYOUTS = {
    "horizontal-tagline": {
        "desc": "Full logo with tagline",
        "use": "Website header, letterhead",
    },
    "horizontal": {
        "desc": "Logo text + butterfly, no tagline",
        "use": "Smaller headers, business cards",
    },
    "stacked": {
        "desc": "Butterfly on top, text below (squarish)",
        "use": "Social media profiles, square spaces",
    },
    "icon-butterfly": {
        "desc": "Butterfly only",
        "use": "Favicon, app icon, watermark",
    },
    "icon-cwg": {
        "desc": "CWG initials + butterfly",
        "use": "Favicon alt, small UI elements",
    },
}


# ============================================================
# HELPER: Extract SVG paths from potrace output
# ============================================================

def extract_paths_from_svg(svg_path):
    """Extract path data and transform from a potrace SVG file."""
    tree = ET.parse(svg_path)
    root = tree.getroot()
    ns = {"svg": "http://www.w3.org/2000/svg"}

    # Get viewBox dimensions
    vb = root.get("viewBox", "0 0 100 100")
    width_pt = root.get("width", "100pt").replace("pt", "")
    height_pt = root.get("height", "100pt").replace("pt", "")

    # Find all path elements
    paths = []
    for g in root.findall(".//svg:g", ns):
        transform = g.get("transform", "")
        for path in g.findall("svg:path", ns):
            paths.append({
                "d": path.get("d"),
                "transform": transform,
            })

    return {
        "viewBox": vb,
        "width_pt": float(width_pt),
        "height_pt": float(height_pt),
        "paths": paths,
    }


# ============================================================
# TRACE EXTRACTION (from hi-res source)
# ============================================================

def extract_and_trace():
    """Extract butterfly and text from source image, trace to SVG."""
    os.makedirs(WORK_DIR, exist_ok=True)

    img = Image.open(SRC_IMAGE).convert("RGBA")
    w, h = img.size
    pixels = img.load()
    print(f"Source image: {w}x{h}")

    # --- BUTTERFLY silhouette (pink fill layer) ---
    # Full butterfly bounding box from pixel analysis: x=1637-1957, y=19-319
    # Use generous crop to capture complete wings
    bx1, by1, bx2, by2 = 1625, 10, 1970, 330
    bw, bh = bx2 - bx1, by2 - by1
    pad = 15

    sil = Image.new("L", (bw + 2*pad, bh + 2*pad), 255)
    sp = sil.load()
    for x in range(bx1, bx2):
        for y in range(by1, by2):
            r, g, b, a = pixels[x, y]
            if a < 30:
                continue
            max_c, min_c = max(r, g, b), min(r, g, b)
            sat = max_c - min_c
            # Include pink/colored pixels AND the butterfly's own dark outlines
            # Butterfly darks have red tint (r > g), pure black text has r == g == b
            is_pink = r > 80 and r > g and sat > 15
            is_butterfly_dark = r > 35 and sat > 5 and (r - g > 3 or r - b > 3)
            is_pure_black_text = max_c < 50 and sat < 10
            if (is_pink or is_butterfly_dark) and not is_pure_black_text:
                sp[x - bx1 + pad, y - by1 + pad] = 0
    sil.save(f"{WORK_DIR}/bf_sil.bmp")
    subprocess.run(f"potrace {WORK_DIR}/bf_sil.bmp -s -o {WORK_DIR}/bf_sil.svg --turdsize 4 --alphamax 1.1",
                   shell=True, capture_output=True)

    # --- BUTTERFLY dark details (vein overlay) ---
    dark = Image.new("L", (bw + 2*pad, bh + 2*pad), 255)
    dp = dark.load()
    for x in range(bx1, bx2):
        for y in range(by1, by2):
            r, g, b, a = pixels[x, y]
            if a < 30:
                continue
            brightness = (r + g + b) / 3
            max_c = max(r, g, b)
            min_c = min(r, g, b)
            sat = max_c - min_c
            # Dark parts of butterfly with color tint, not pure black text
            is_pure_black = max_c < 40 and sat < 8
            if brightness < 140 and not is_pure_black and (sat > 5 or r > g):
                dp[x - bx1 + pad, y - by1 + pad] = 0
    dark.save(f"{WORK_DIR}/bf_dark.bmp")
    subprocess.run(f"potrace {WORK_DIR}/bf_dark.bmp -s -o {WORK_DIR}/bf_dark.svg --turdsize 3 --alphamax 1.0",
                   shell=True, capture_output=True)

    # --- MAIN TEXT "Caring with Grace" (no tagline) ---
    # Hybrid approach: color-based filtering + targeted butterfly exclusions.
    # The butterfly outlines have edge pixels that are indistinguishable from
    # text by color alone (both are near-black with sat~0), so we exclude
    # rectangular zones that contain ONLY butterfly and NO text:
    #   - Small butterfly: x=715-910, y<255 (safely above "g" in "Caring")
    #   - Main butterfly: x=1630-1980, y<340 (safely above "with", which starts y=343)
    tagline_y = int(h * 0.72)
    text_img = Image.new("L", (w, tagline_y), 255)
    tp = text_img.load()
    for x in range(w):
        for y in range(tagline_y):
            # Exclude butterfly-only zones (generously sized to catch edge artifacts)
            if 690 <= x <= 920 and y < 270:
                continue
            if 1620 <= x <= 1985 and y < 345:
                continue
            r, g, b, a = pixels[x, y]
            if a < 50:
                continue
            max_c = max(r, g, b)
            min_c = min(r, g, b)
            sat = max_c - min_c
            # Include genuinely dark pixels with low saturation (true black text)
            if max_c < 80 and sat < 15:
                tp[x, y] = 0
    text_img.save(f"{WORK_DIR}/text_main.bmp")
    subprocess.run(f"potrace {WORK_DIR}/text_main.bmp -s -o {WORK_DIR}/text_main.svg --turdsize 2 --alphamax 0.8 --opttolerance 0.15",
                   shell=True, capture_output=True)

    # --- TAGLINE "Helping those you love live with dignity" ---
    tag_y_start = int(h * 0.72)
    tag_img = Image.new("L", (w, h - tag_y_start), 255)
    tag_p = tag_img.load()
    for x in range(w):
        for y in range(tag_y_start, h):
            r, g, b, a = pixels[x, y]
            if a < 50:
                continue
            if max(r, g, b) < 120:
                tag_p[x, y - tag_y_start] = 0
    tag_img.save(f"{WORK_DIR}/tagline.bmp")
    subprocess.run(f"potrace {WORK_DIR}/tagline.bmp -s -o {WORK_DIR}/tagline.svg --turdsize 2 --alphamax 1.0 --opttolerance 0.2",
                   shell=True, capture_output=True)

    print("Tracing complete.")


# ============================================================
# MODERN BUTTERFLY (clean hand-crafted SVG paths)
# ============================================================

# Modern butterfly - monarch-style, 3/4 angle view matching original pose
# Wings slightly open, viewed from front-right, tilted body
# ViewBox: 0 0 300 280

# Left forewing (viewer's left, larger/front-facing)
MODERN_BF_LEFT_FOREWING = (
    "M 140 145 "  # body junction
    "C 130 120, 110 70, 80 40 "  # sweep up-left
    "C 65 25, 40 18, 25 25 "  # tip curves
    "C 12 32, 5 50, 8 70 "  # outer edge down
    "C 10 85, 18 100, 28 112 "  # scallop 1
    "C 22 118, 18 125, 25 132 "  # scallop 2
    "C 32 140, 48 148, 65 152 "  # scallop 3
    "C 85 155, 110 155, 130 150 "  # back to body
    "C 135 148, 138 147, 140 145 Z"
)

# Right forewing (viewer's right, extends upward)
MODERN_BF_RIGHT_FOREWING = (
    "M 155 142 "
    "C 168 115, 195 60, 220 30 "  # sweep up-right
    "C 235 15, 252 8, 265 12 "  # tip curves
    "C 278 18, 285 35, 282 55 "  # outer edge
    "C 280 68, 272 80, 264 90 "  # scallop 1
    "C 270 96, 275 102, 268 110 "  # scallop 2
    "C 260 120, 248 128, 232 134 "  # scallop 3
    "C 215 140, 195 143, 175 144 "
    "C 165 144, 158 143, 155 142 Z"
)

# Left hindwing (lower-left)
MODERN_BF_LEFT_HINDWING = (
    "M 135 155 "
    "C 120 165, 90 185, 65 200 "
    "C 48 210, 35 218, 30 228 "
    "C 25 240, 30 250, 42 255 "
    "C 55 260, 70 258, 85 250 "
    "C 100 242, 112 230, 125 215 "
    "C 132 205, 137 190, 140 175 "
    "C 140 165, 138 158, 135 155 Z"
)

# Right hindwing (lower-right)
MODERN_BF_RIGHT_HINDWING = (
    "M 160 152 "
    "C 172 162, 198 178, 220 190 "
    "C 238 198, 250 205, 258 215 "
    "C 265 225, 262 238, 252 245 "
    "C 240 252, 225 250, 210 242 "
    "C 195 232, 182 218, 172 202 "
    "C 166 192, 162 178, 160 165 "
    "C 159 158, 159 155, 160 152 Z"
)

# Body
MODERN_BF_BODY = (
    "M 147 130 "
    "C 145 140, 144 155, 144 170 "
    "C 144 190, 146 210, 148 225 "
    "C 149 230, 151 230, 152 225 "
    "C 154 210, 156 190, 156 170 "
    "C 156 155, 155 140, 153 130 "
    "C 151 125, 149 125, 147 130 Z"
)

# Antennae
MODERN_BF_ANTENNAE = (
    "M 147 132 C 140 110, 128 85, 118 72 "  # left antenna
    "M 118 72 C 115 68, 112 66, 110 68 C 108 70, 110 73, 113 74 "  # left tip ball
    "M 153 132 C 158 108, 170 82, 182 68 "  # right antenna
    "M 182 68 C 185 64, 188 63, 190 65 C 192 67, 190 70, 187 71 "  # right tip ball
)

# Wing veins (delicate lines radiating from body)
MODERN_BF_VEINS = (
    # Left forewing veins
    "M 140 145 C 118 115, 85 72, 55 42 "
    "M 138 148 C 108 128, 55 100, 15 80 "
    "M 135 150 C 105 145, 60 140, 30 130 "
    # Right forewing veins
    "M 155 142 C 178 108, 215 60, 245 32 "
    "M 158 144 C 190 125, 240 95, 275 70 "
    "M 160 145 C 192 140, 235 130, 268 115 "
    # Left hindwing veins
    "M 138 158 C 115 175, 80 205, 48 230 "
    "M 136 160 C 118 180, 95 210, 70 235 "
    # Right hindwing veins
    "M 158 155 C 180 172, 210 195, 240 220 "
    "M 160 157 C 178 175, 200 200, 225 228 "
)

# Edge spots (small white dots along wing edges - monarch pattern)
MODERN_BF_SPOTS = (
    # Left forewing edge
    "M 18 68 a 4 4 0 1 0 8 0 a 4 4 0 1 0 -8 0 "
    "M 24 108 a 3.5 3.5 0 1 0 7 0 a 3.5 3.5 0 1 0 -7 0 "
    "M 42 135 a 3.5 3.5 0 1 0 7 0 a 3.5 3.5 0 1 0 -7 0 "
    "M 72 30 a 3 3 0 1 0 6 0 a 3 3 0 1 0 -6 0 "
    # Right forewing edge
    "M 272 52 a 4 4 0 1 0 8 0 a 4 4 0 1 0 -8 0 "
    "M 268 88 a 3.5 3.5 0 1 0 7 0 a 3.5 3.5 0 1 0 -7 0 "
    "M 253 122 a 3.5 3.5 0 1 0 7 0 a 3.5 3.5 0 1 0 -7 0 "
    "M 240 14 a 3 3 0 1 0 6 0 a 3 3 0 1 0 -6 0 "
    # Left hindwing edge
    "M 35 238 a 3 3 0 1 0 6 0 a 3 3 0 1 0 -6 0 "
    "M 50 252 a 3 3 0 1 0 6 0 a 3 3 0 1 0 -6 0 "
    # Right hindwing edge
    "M 250 235 a 3 3 0 1 0 6 0 a 3 3 0 1 0 -6 0 "
    "M 238 248 a 3 3 0 1 0 6 0 a 3 3 0 1 0 -6 0 "
)


# ============================================================
# SVG ASSEMBLY
# ============================================================

def build_classic_butterfly_svg(color_key):
    """Build a multi-layer classic butterfly from traced paths, with clipPath."""
    colors = COLORS[color_key]

    sil_data = extract_paths_from_svg(f"{WORK_DIR}/bf_sil.svg")
    dark_data = extract_paths_from_svg(f"{WORK_DIR}/bf_dark.svg")

    # Get the viewBox from the silhouette
    vb = sil_data["viewBox"]

    svg_parts = []

    # Define clipPath from silhouette shape (to contain dark overlay)
    clip_paths = []
    for p in sil_data["paths"]:
        clip_paths.append(f'<path d="{p["d"]}" transform="{p["transform"]}"/>')
    svg_parts.append(f'<defs><clipPath id="bf-clip-{color_key}">{"".join(clip_paths)}</clipPath></defs>')

    # Layer 1: Pink silhouette fill
    for p in sil_data["paths"]:
        svg_parts.append(
            f'<path d="{p["d"]}" fill="{colors["butterfly_fill"]}" '
            f'transform="{p["transform"]}"/>'
        )
    # Layer 2: Dark detail overlay, clipped to silhouette
    svg_parts.append(f'<g clip-path="url(#bf-clip-{color_key})">')
    for p in dark_data["paths"]:
        svg_parts.append(
            f'<path d="{p["d"]}" fill="{colors["butterfly_dark"]}" '
            f'transform="{p["transform"]}"/>'
        )
    svg_parts.append('</g>')

    return {
        "content": "\n".join(svg_parts),
        "viewBox": vb,
        "width_pt": sil_data["width_pt"],
        "height_pt": sil_data["height_pt"],
    }


def build_modern_butterfly_svg(color_key):
    """Build a clean modern monarch butterfly from hand-crafted paths.
    Rotated ~20 degrees to match the original's dynamic 3/4 angle pose."""
    colors = COLORS[color_key]

    # Build the butterfly parts, then wrap in a rotation group
    inner_parts = [
        # Wing fills (pink)
        f'<path d="{MODERN_BF_LEFT_FOREWING}" fill="{colors["butterfly_fill"]}" />',
        f'<path d="{MODERN_BF_RIGHT_FOREWING}" fill="{colors["butterfly_fill"]}" />',
        f'<path d="{MODERN_BF_LEFT_HINDWING}" fill="{colors["butterfly_fill"]}" />',
        f'<path d="{MODERN_BF_RIGHT_HINDWING}" fill="{colors["butterfly_fill"]}" />',
        # Wing veins (dark lines)
        f'<path d="{MODERN_BF_VEINS}" fill="none" stroke="{colors["butterfly_dark"]}" stroke-width="1.8" stroke-linecap="round" opacity="0.6" />',
        # Wing edge outlines (subtle)
        f'<path d="{MODERN_BF_LEFT_FOREWING}" fill="none" stroke="{colors["butterfly_dark"]}" stroke-width="1.5" opacity="0.4" />',
        f'<path d="{MODERN_BF_RIGHT_FOREWING}" fill="none" stroke="{colors["butterfly_dark"]}" stroke-width="1.5" opacity="0.4" />',
        f'<path d="{MODERN_BF_LEFT_HINDWING}" fill="none" stroke="{colors["butterfly_dark"]}" stroke-width="1.5" opacity="0.4" />',
        f'<path d="{MODERN_BF_RIGHT_HINDWING}" fill="none" stroke="{colors["butterfly_dark"]}" stroke-width="1.5" opacity="0.4" />',
        # White edge spots (monarch pattern)
        f'<path d="{MODERN_BF_SPOTS}" fill="white" opacity="0.85" />',
        # Body (dark)
        f'<path d="{MODERN_BF_BODY}" fill="{colors["butterfly_dark"]}" />',
        # Antennae (dark, thin)
        f'<path d="{MODERN_BF_ANTENNAE}" fill="none" stroke="{colors["butterfly_dark"]}" stroke-width="1.5" stroke-linecap="round" />',
    ]

    # Wrap in rotation group: rotate 20 degrees around center (150, 135)
    svg_parts = [
        '<g transform="rotate(-20, 150, 135)">',
        *inner_parts,
        '</g>',
    ]

    return {
        "content": "\n".join(svg_parts),
        "viewBox": "0 0 300 270",
        "width": 300,
        "height": 270,
    }


def build_text_svg(color_key, include_tagline=False):
    """Build the text portion from traced paths."""
    colors = COLORS[color_key]

    text_data = extract_paths_from_svg(f"{WORK_DIR}/text_main.svg")
    svg_parts = []
    for p in text_data["paths"]:
        svg_parts.append(
            f'<path d="{p["d"]}" fill="{colors["text"]}" '
            f'transform="{p["transform"]}"/>'
        )

    result = {
        "content": "\n".join(svg_parts),
        "viewBox": text_data["viewBox"],
        "width_pt": text_data["width_pt"],
        "height_pt": text_data["height_pt"],
    }

    if include_tagline:
        tag_data = extract_paths_from_svg(f"{WORK_DIR}/tagline.svg")
        tag_parts = []
        for p in tag_data["paths"]:
            tag_parts.append(
                f'<path d="{p["d"]}" fill="{colors["tagline"]}" '
                f'transform="{p["transform"]}"/>'
            )
        result["tagline_content"] = "\n".join(tag_parts)
        result["tagline_viewBox"] = tag_data["viewBox"]
        result["tagline_width_pt"] = tag_data["width_pt"]
        result["tagline_height_pt"] = tag_data["height_pt"]

    return result


def assemble_horizontal_tagline(butterfly_style, color_key):
    """Full horizontal logo with tagline - similar to original layout."""
    colors = COLORS[color_key]
    text = build_text_svg(color_key, include_tagline=True)

    if butterfly_style == "classic":
        bf = build_classic_butterfly_svg(color_key)
    else:
        bf = build_modern_butterfly_svg(color_key)

    # Parse viewBox dimensions
    text_vb = [float(x) for x in text["viewBox"].split()]
    tag_vb = [float(x) for x in text["tagline_viewBox"].split()]

    text_w, text_h = text_vb[2], text_vb[3]
    tag_w, tag_h = tag_vb[2], tag_vb[3]

    if butterfly_style == "classic":
        bf_vb = [float(x) for x in bf["viewBox"].split()]
        bf_w, bf_h = bf_vb[2], bf_vb[3]
    else:
        bf_w, bf_h = 300, 270

    # Scale everything relative to text width
    total_w = text_w
    bf_scale = (text_h * 0.7) / bf_h
    scaled_bf_w = bf_w * bf_scale
    scaled_bf_h = bf_h * bf_scale

    # Position butterfly above-center of text
    bf_x = text_w * 0.35
    bf_y = 0

    text_y = scaled_bf_h * 0.5
    tag_y = text_y + text_h + tag_h * 0.1
    tag_scale = text_w * 0.85 / tag_w

    total_h = tag_y + tag_h * tag_scale + 20

    svg = f'''<?xml version="1.0" encoding="UTF-8"?>
<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {total_w} {total_h}" width="{total_w}" height="{total_h}">
  <title>Caring With Grace - Full Logo</title>
  <!-- Butterfly -->
  <g transform="translate({bf_x},{bf_y}) scale({bf_scale})">
    <svg viewBox="{bf["viewBox"]}" width="{bf_w}" height="{bf_h}">
      {bf["content"]}
    </svg>
  </g>
  <!-- Main text -->
  <g transform="translate(0,{text_y})">
    <svg viewBox="{text["viewBox"]}" width="{text_w}" height="{text_h}">
      {text["content"]}
    </svg>
  </g>
  <!-- Tagline -->
  <g transform="translate({text_w * 0.075},{tag_y}) scale({tag_scale})">
    <svg viewBox="{text["tagline_viewBox"]}" width="{tag_w}" height="{tag_h}">
      {text["tagline_content"]}
    </svg>
  </g>
</svg>'''

    return svg


def assemble_horizontal(butterfly_style, color_key):
    """Horizontal logo without tagline."""
    colors = COLORS[color_key]
    text = build_text_svg(color_key, include_tagline=False)

    if butterfly_style == "classic":
        bf = build_classic_butterfly_svg(color_key)
    else:
        bf = build_modern_butterfly_svg(color_key)

    text_vb = [float(x) for x in text["viewBox"].split()]
    text_w, text_h = text_vb[2], text_vb[3]

    if butterfly_style == "classic":
        bf_vb = [float(x) for x in bf["viewBox"].split()]
        bf_w, bf_h = bf_vb[2], bf_vb[3]
    else:
        bf_w, bf_h = 300, 270

    bf_scale = (text_h * 0.65) / bf_h
    scaled_bf_h = bf_h * bf_scale

    bf_x = text_w * 0.35
    bf_y = 0
    text_y = scaled_bf_h * 0.55

    total_h = text_y + text_h + 20

    svg = f'''<?xml version="1.0" encoding="UTF-8"?>
<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {text_w} {total_h}" width="{text_w}" height="{total_h}">
  <title>Caring With Grace - No Tagline</title>
  <g transform="translate({bf_x},{bf_y}) scale({bf_scale})">
    <svg viewBox="{bf["viewBox"]}" width="{bf_w}" height="{bf_h}">
      {bf["content"]}
    </svg>
  </g>
  <g transform="translate(0,{text_y})">
    <svg viewBox="{text["viewBox"]}" width="{text_w}" height="{text_h}">
      {text["content"]}
    </svg>
  </g>
</svg>'''

    return svg


def assemble_stacked(butterfly_style, color_key):
    """Stacked layout - butterfly centered on top, text below."""
    colors = COLORS[color_key]
    text = build_text_svg(color_key, include_tagline=False)

    if butterfly_style == "classic":
        bf = build_classic_butterfly_svg(color_key)
    else:
        bf = build_modern_butterfly_svg(color_key)

    text_vb = [float(x) for x in text["viewBox"].split()]
    text_w, text_h = text_vb[2], text_vb[3]

    if butterfly_style == "classic":
        bf_vb = [float(x) for x in bf["viewBox"].split()]
        bf_w, bf_h = bf_vb[2], bf_vb[3]
    else:
        bf_w, bf_h = 300, 270

    # Scale butterfly to be about 40% of text width
    bf_scale = (text_w * 0.3) / bf_w
    scaled_bf_w = bf_w * bf_scale
    scaled_bf_h = bf_h * bf_scale

    padding = 30
    bf_x = (text_w - scaled_bf_w) / 2
    bf_y = padding
    text_y = bf_y + scaled_bf_h + padding * 0.5

    total_h = text_y + text_h + padding

    svg = f'''<?xml version="1.0" encoding="UTF-8"?>
<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {text_w} {total_h}" width="{text_w}" height="{total_h}">
  <title>Caring With Grace - Stacked</title>
  <g transform="translate({bf_x},{bf_y}) scale({bf_scale})">
    <svg viewBox="{bf["viewBox"]}" width="{bf_w}" height="{bf_h}">
      {bf["content"]}
    </svg>
  </g>
  <g transform="translate(0,{text_y})">
    <svg viewBox="{text["viewBox"]}" width="{text_w}" height="{text_h}">
      {text["content"]}
    </svg>
  </g>
</svg>'''

    return svg


def assemble_icon_butterfly(butterfly_style, color_key):
    """Butterfly icon only."""
    if butterfly_style == "classic":
        bf = build_classic_butterfly_svg(color_key)
        bf_vb = [float(x) for x in bf["viewBox"].split()]
        bf_w, bf_h = bf_vb[2], bf_vb[3]
    else:
        bf = build_modern_butterfly_svg(color_key)
        bf_w, bf_h = 300, 270

    pad = 20
    size = max(bf_w, bf_h) + 2 * pad
    offset_x = (size - bf_w) / 2
    offset_y = (size - bf_h) / 2

    svg = f'''<?xml version="1.0" encoding="UTF-8"?>
<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {size} {size}" width="{size}" height="{size}">
  <title>Caring With Grace - Butterfly Icon</title>
  <g transform="translate({offset_x},{offset_y})">
    <svg viewBox="{bf["viewBox"]}" width="{bf_w}" height="{bf_h}">
      {bf["content"]}
    </svg>
  </g>
</svg>'''

    return svg


def assemble_icon_cwg(butterfly_style, color_key):
    """CwG initials with butterfly - compact square mark."""
    colors = COLORS[color_key]

    if butterfly_style == "classic":
        bf = build_classic_butterfly_svg(color_key)
        bf_vb = bf["viewBox"]
        bf_vb_parts = [float(x) for x in bf_vb.split()]
        bf_w, bf_h = bf_vb_parts[2], bf_vb_parts[3]
    else:
        bf = build_modern_butterfly_svg(color_key)
        bf_vb = bf["viewBox"]
        bf_w, bf_h = 300, 270

    size = 400
    bf_scale = (size * 0.50) / max(bf_w, bf_h)
    scaled_bf_w = bf_w * bf_scale
    scaled_bf_h = bf_h * bf_scale
    bf_x = (size - scaled_bf_w) / 2
    bf_y = size * 0.06

    # CwG text (lowercase 'w' matching original mini logo)
    text_y = bf_y + scaled_bf_h + size * 0.08

    svg = f'''<?xml version="1.0" encoding="UTF-8"?>
<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {size} {size}" width="{size}" height="{size}">
  <title>Caring With Grace - CwG Icon</title>
  <defs>
    <style>
      @import url('https://fonts.googleapis.com/css2?family=Playfair+Display:ital,wght@0,400;0,700;1,400&amp;display=swap');
      .cwg-text {{ font-family: 'Playfair Display', 'Georgia', serif; }}
    </style>
  </defs>
  <g transform="translate({bf_x},{bf_y}) scale({bf_scale})">
    <svg viewBox="{bf_vb}" width="{bf_w}" height="{bf_h}">
      {bf["content"]}
    </svg>
  </g>
  <text x="{size/2}" y="{text_y}" text-anchor="middle" dominant-baseline="hanging"
        class="cwg-text" font-size="{size * 0.26}" font-weight="700"
        fill="{colors['text']}" letter-spacing="2">CwG</text>
</svg>'''

    return svg


def assemble_mini_logo(butterfly_style, color_key):
    """Mini logo with rounded background - matches original mini logo concept.
    Butterfly overlaid with CwG text, rounded corners, suitable for favicons."""
    colors = COLORS[color_key]

    if butterfly_style == "classic":
        bf = build_classic_butterfly_svg(color_key)
        bf_vb = bf["viewBox"]
        bf_vb_parts = [float(x) for x in bf_vb.split()]
        bf_w, bf_h = bf_vb_parts[2], bf_vb_parts[3]
    else:
        bf = build_modern_butterfly_svg(color_key)
        bf_vb = bf["viewBox"]
        bf_w, bf_h = 300, 270

    size = 400
    radius = 40  # rounded corner radius
    padding = 25

    # Butterfly: centered, takes up most of the space
    bf_scale = (size - 2 * padding) * 0.65 / max(bf_w, bf_h)
    scaled_bf_w = bf_w * bf_scale
    scaled_bf_h = bf_h * bf_scale
    bf_x = (size - scaled_bf_w) / 2
    bf_y = padding + 10

    # CwG text overlaid at bottom
    text_y = size - padding - 10

    svg = f'''<?xml version="1.0" encoding="UTF-8"?>
<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {size} {size}" width="{size}" height="{size}">
  <title>Caring With Grace - Mini Logo</title>
  <defs>
    <style>
      @import url('https://fonts.googleapis.com/css2?family=Playfair+Display:ital,wght@0,400;0,700;1,400&amp;display=swap');
      .cwg-mini {{ font-family: 'Playfair Display', 'Georgia', serif; }}
    </style>
  </defs>
  <!-- Rounded background -->
  <rect x="0" y="0" width="{size}" height="{size}" rx="{radius}" ry="{radius}" fill="white" stroke="#e0e0e0" stroke-width="2"/>
  <!-- Butterfly -->
  <g transform="translate({bf_x},{bf_y}) scale({bf_scale})">
    <svg viewBox="{bf_vb}" width="{bf_w}" height="{bf_h}">
      {bf["content"]}
    </svg>
  </g>
  <!-- CwG text -->
  <text x="{size/2}" y="{text_y}" text-anchor="middle" dominant-baseline="auto"
        class="cwg-mini" font-size="{size * 0.22}" font-weight="700" font-style="italic"
        fill="{colors['text']}" letter-spacing="1">CwG</text>
</svg>'''

    return svg


# ============================================================
# MAIN BUILD
# ============================================================

ASSEMBLERS = {
    "horizontal-tagline": assemble_horizontal_tagline,
    "horizontal": assemble_horizontal,
    "stacked": assemble_stacked,
    "icon-butterfly": assemble_icon_butterfly,
    "icon-cwg": assemble_icon_cwg,
    "mini": assemble_mini_logo,
}


def build_all():
    """Build all 20 SVG variants and export PNGs."""

    # Step 1: Trace if needed
    if not os.path.exists(f"{WORK_DIR}/bf_sil.svg"):
        print("Tracing source image...")
        extract_and_trace()
    else:
        print("Using existing traces.")

    # Step 2: Build SVGs
    generated = []
    for layout_name, assembler in ASSEMBLERS.items():
        for bf_style in ["classic", "modern"]:
            for color_key in COLORS:
                filename = f"cwg-{layout_name}-{bf_style}-{color_key}.svg"
                filepath = os.path.join(SVG_DIR, filename)

                try:
                    svg_content = assembler(bf_style, color_key)
                    with open(filepath, "w") as f:
                        f.write(svg_content)
                    generated.append(filename)
                    print(f"  Created: {filename}")
                except Exception as e:
                    print(f"  FAILED: {filename} - {e}")

    # Step 3: Export PNGs
    print("\nExporting PNGs...")
    try:
        import cairosvg
        png_sizes = {
            "horizontal-tagline": [800, 1600, 3200],
            "horizontal": [600, 1200, 2400],
            "stacked": [400, 800, 1600],
            "icon-butterfly": [128, 256, 512, 1024],
            "icon-cwg": [128, 256, 512, 1024],
            "mini": [128, 256, 512, 1024],
        }

        for svg_name in generated:
            svg_path = os.path.join(SVG_DIR, svg_name)
            base_name = svg_name.replace(".svg", "")

            # Determine layout from filename
            for layout_key, sizes in png_sizes.items():
                if layout_key in svg_name:
                    for target_w in sizes:
                        png_name = f"{base_name}-{target_w}w.png"
                        png_path = os.path.join(PNG_DIR, png_name)
                        try:
                            cairosvg.svg2png(
                                url=svg_path,
                                write_to=png_path,
                                output_width=target_w,
                                background_color="transparent",
                            )
                        except Exception as e:
                            print(f"    PNG FAILED: {png_name} - {e}")
                    break
    except ImportError:
        print("  cairosvg not available, skipping PNG export.")

    print(f"\nDone! Generated {len(generated)} SVG files.")
    return generated


if __name__ == "__main__":
    build_all()
