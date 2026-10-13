"""Photo quality check: blur (Laplacian variance), too dark, overexposed.

Returns codes only; the frontend turns them into messages in the user's language.
The thresholds live in config.py and were measured on real field photos
(see scripts/measure_quality_thresholds.py). They are heuristics: a plain,
low-detail background can look "blurry" even when the leaf is sharp.
"""
import cv2
import numpy as np
from PIL import Image

from backend import config


def grey_for_quality(img: Image.Image) -> np.ndarray:
    """Grey image at a fixed size, so blur scores do not depend on the camera resolution."""
    w, h = img.size
    scale = config.QUALITY_SIDE_PX / max(w, h)
    if scale < 1:
        img = img.resize((max(1, round(w * scale)), max(1, round(h * scale))), Image.LANCZOS)
    return cv2.cvtColor(np.asarray(img.convert("RGB")), cv2.COLOR_RGB2GRAY)


def measure(img: Image.Image) -> dict:
    grey = grey_for_quality(img)
    return {
        "blur_score": float(cv2.Laplacian(grey, cv2.CV_64F).var()),  # low = blurry
        "brightness": float(grey.mean()),                            # 0 (black) .. 255 (white)
        "saturated_frac": float((grey >= 250).mean()),               # share of near-white pixels
    }


def assess(img: Image.Image) -> dict:
    m = measure(img)
    issues = []
    if m["blur_score"] < config.BLUR_MIN_LAPLACIAN_VAR:
        issues.append("blurry")
    if m["brightness"] < config.DARK_MAX_MEAN:
        issues.append("too_dark")
    if m["brightness"] > config.BRIGHT_MIN_MEAN or m["saturated_frac"] > config.BRIGHT_MAX_SATURATED_FRAC:
        issues.append("overexposed")
    return {"ok": not issues, "issues": issues, **{k: round(v, 3) for k, v in m.items()}}
