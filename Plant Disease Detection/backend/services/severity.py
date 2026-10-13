"""Severity estimate: percent of leaf area that looks diseased, from HSV colour segmentation.

How it works (OpenCV hue runs 0-179; green is about 35-90):
  1. "Healthy" pixels = green hue with enough saturation and brightness.
  2. The leaf region = those green pixels, joined by a morphological close and with holes filled,
     so brown spots *inside* the leaf count as leaf. Pixels outside it (soil, hands) are ignored.
  3. "Lesion" pixels = non-green, coloured or dark pixels inside the leaf region
     (brown, yellow, orange, dark necrotic tissue, pale/grey blast centres).
  4. severity % = lesion pixels / leaf-region pixels * 100.

MEASURED VALIDITY (Stage 2 test on RiceLeafDiseaseBD field photos, ~300 diseased + 80 healthy):
  * Healthy leaves scored a median of ~5% "affected" (p90 ~14%): that is the noise floor.
  * Correlation (Spearman) with the dataset's hand-drawn lesion boxes was about 0 (-0.04 on 398 photos),
    and healthy and diseased photos got the same median. Other colour rules (colour-distance from the leaf's
    own median, central-leaf restriction, background-complexity guard) did not help.
  * Most Blast / Brown Spot lesions in this dataset are tiny (median annotated box ~1.4% of the image),
    i.e. about the size of the noise floor, so this method cannot resolve them on busy field photos.
  So treat the number as an EXPERIMENTAL rough guide. Values under ~10% mean "small or noise".
  It does measure correctly on clean synthetic leaves (see tests/test_severity.py), so the arithmetic is
  right; what fails is telling lesions apart from background and leaf texture in real field photos.
  A better route for the future: train a lesion detector on the dataset's YOLO boxes and count/measure those.

Limits (also shown to the user):
  * It only looks at colour. Shadows, glare, dust, dew, soil on the leaf and yellowing from
    other causes are counted as "lesion" or "healthy" depending on their colour.
  * A leaf photographed against a green background (other leaves, grass) is not separated from it.
  * Very yellow leaves (e.g. Tungro) can be counted as 100% lesion because yellow is not green.
  * It measures the photographed area, not the whole plant. It is an estimate, not a score
    from a trained pathologist. The Mild / Moderate / Severe cut-offs (config.py) are this
    project's own choice.

Try it on your own photos:
    python -m backend.services.severity photo1.jpg photo2.jpg --out severity_check
"""
import argparse
import csv
import io
import sys
from pathlib import Path

import cv2
import numpy as np
from PIL import Image

from backend import config

WORK_SIDE = 512            # analyse at this size: fast and independent of camera resolution
MIN_LEAF_FRACTION = 0.03   # fewer green pixels than this => we cannot find the leaf

GREEN_LO = (35, 40, 40)    # H, S, V lower bound for green
GREEN_HI = (90, 255, 255)
OPEN_K = 7                 # opening kernel used to cut thin bridges between the leaf and background plants
LESION_MIN_SAT = 50        # a lesion pixel must be clearly coloured ...
LESION_MIN_VAL = 40        # ... and not black (black gaps between leaves are background, not lesions)


def level_for(percent: float) -> str:
    if percent < config.SEVERITY_MILD_MAX:
        return "Mild"
    if percent <= config.SEVERITY_MODERATE_MAX:
        return "Moderate"
    return "Severe"


def estimate(img: Image.Image, with_overlay: bool = False) -> dict:
    """Return {"percent", "level", "leaf_found", ...}. percent/level are None if no leaf was found."""
    w, h = img.size
    s = WORK_SIDE / max(w, h)
    small = img.convert("RGB").resize((max(1, round(w * s)), max(1, round(h * s))), Image.LANCZOS)
    rgb = np.asarray(small)
    hsv = cv2.cvtColor(rgb, cv2.COLOR_RGB2HSV)

    green = cv2.inRange(hsv, np.array(GREEN_LO), np.array(GREEN_HI)) > 0
    green = cv2.morphologyEx(green.astype(np.uint8), cv2.MORPH_OPEN, np.ones((3, 3), np.uint8)) > 0

    if green.mean() < MIN_LEAF_FRACTION:
        return {"percent": None, "level": None, "leaf_found": False, "reason": "no_leaf_found"}

    # Leaf region = the single biggest green blob (the leaf the user is pointing at), with its gaps closed
    # and holes filled so lesions inside it count as leaf. An opening first cuts thin links to background plants.
    k = max(7, WORK_SIDE // 25) | 1
    kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (k, k))
    core = cv2.morphologyEx(green.astype(np.uint8), cv2.MORPH_OPEN, cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (OPEN_K, OPEN_K)))
    if core.sum() == 0:
        core = green.astype(np.uint8)
    n, labels, stats, _ = cv2.connectedComponentsWithStats(core, connectivity=8)
    biggest = 1 + int(np.argmax(stats[1:, cv2.CC_STAT_AREA]))
    blob = (labels == biggest).astype(np.uint8)
    blob = cv2.morphologyEx(blob, cv2.MORPH_CLOSE, kernel)
    contours, _ = cv2.findContours(blob, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    region = np.zeros_like(blob)
    cv2.drawContours(region, contours, -1, 1, thickness=cv2.FILLED)
    region = region > 0

    h_, s_, v_ = hsv[..., 0], hsv[..., 1], hsv[..., 2]
    coloured = (s_ >= LESION_MIN_SAT) & (v_ >= LESION_MIN_VAL)   # clearly coloured, not black: brown, yellow, orange
    lesion = region & ~green & coloured
    lesion = cv2.morphologyEx(lesion.astype(np.uint8), cv2.MORPH_OPEN, np.ones((2, 2), np.uint8)) > 0

    leaf_px = int(region.sum())
    percent = 100.0 * float(lesion.sum()) / max(1, leaf_px)
    out = {
        "percent": round(percent, 1),
        "level": level_for(percent),
        "leaf_found": True,
        "leaf_fraction": round(leaf_px / region.size, 3),
    }
    if with_overlay:
        vis = rgb.copy()
        vis[lesion] = (0.45 * vis[lesion] + 0.55 * np.array([255, 0, 0])).astype(np.uint8)  # lesions in red
        edge = cv2.morphologyEx(region.astype(np.uint8), cv2.MORPH_GRADIENT, np.ones((3, 3), np.uint8)) > 0
        vis[edge] = (0, 120, 255)                                                             # leaf outline in blue
        out["overlay"] = Image.fromarray(vis)
    return out


def to_png_bytes(img: Image.Image) -> bytes:
    buf = io.BytesIO()
    img.save(buf, "PNG")
    return buf.getvalue()


def check_samples(paths, out_dir=None) -> list[dict]:
    """Run the estimator on a few images, optionally saving overlays, and print a table."""
    out_dir = Path(out_dir) if out_dir else None
    if out_dir:
        out_dir.mkdir(parents=True, exist_ok=True)
    rows = []
    for p in map(Path, paths):
        with Image.open(p) as im:
            r = estimate(im.convert("RGB"), with_overlay=out_dir is not None)
        overlay = r.pop("overlay", None)
        if overlay is not None:
            overlay.save(out_dir / f"{p.stem}_severity.png")
        rows.append({"file": p.name, **r})
    print(f"{'file':32s} {'leaf?':6s} {'percent':>8s}  level")
    for r in rows:
        print(f"{r['file'][:32]:32s} {str(r['leaf_found']):6s} {str(r['percent']):>8s}  {r['level']}")
    if out_dir:
        with open(out_dir / "severity_check.csv", "w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=["file", "leaf_found", "percent", "level", "leaf_fraction", "reason"], extrasaction="ignore")
            w.writeheader()
            w.writerows(rows)
        print("overlays (red = lesion, blue = leaf outline) saved to", out_dir)
    return rows


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("images", nargs="+")
    ap.add_argument("--out", default=None, help="folder for overlay images")
    a = ap.parse_args()
    check_samples(a.images, a.out)
    sys.exit(0)
