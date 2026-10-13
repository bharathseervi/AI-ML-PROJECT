"""Measure blur / brightness scores on real dataset photos to choose the thresholds in backend/config.py.

    .venv\\Scripts\\python.exe scripts\\measure_quality_thresholds.py [--per-class 250]

It samples photos from "Original images/" in the dataset zip, then reports:
  * the score distribution of the real photos (these are acceptable photos, so almost none should be flagged);
  * the same photos after artificial damage (Gaussian blur, darkening, brightening) to see how well the
    candidate threshold separates good from bad.
Artificial damage is only a proxy for real bad phone photos. Re-check with your own blurry / dark photos.
"""
import argparse
import io
import random
import sys
import zipfile
from pathlib import Path

import numpy as np
from PIL import Image, ImageEnhance, ImageFilter

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from backend.services import quality  # noqa: E402

ZIP = ROOT / "RiceLeafDiseaseBD A Field-Based Annotated Smartpho" / "RiceLeafDiseaseBD.zip"
INNER = "RiceLeafDiseaseBD/Original images/"


def pct(a, qs=(0.5, 1, 2, 5, 50, 95, 99, 99.5)):
    return "  ".join(f"p{q}={np.percentile(a, q):.1f}" for q in qs)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--per-class", type=int, default=250)
    ap.add_argument("--seed", type=int, default=0)
    a = ap.parse_args()

    random.seed(a.seed)
    with zipfile.ZipFile(ZIP) as z:
        by = {}
        for n in z.namelist():
            if n.startswith(INNER) and n.lower().endswith(".jpg"):
                by.setdefault(n[len(INNER):].split("/")[0], []).append(n)
        names = [n for v in by.values() for n in random.sample(v, min(a.per_class, len(v)))]
        print(f"sampled {len(names)} photos from {len(by)} classes")

        base, blur2, blur4, dark, bright = [], [], [], [], []
        for n in names:
            im = Image.open(io.BytesIO(z.read(n))).convert("RGB")
            base.append(quality.measure(im))
            blur2.append(quality.measure(im.filter(ImageFilter.GaussianBlur(2))))
            blur4.append(quality.measure(im.filter(ImageFilter.GaussianBlur(4))))
            dark.append(quality.measure(ImageEnhance.Brightness(im).enhance(0.35)))
            bright.append(quality.measure(ImageEnhance.Brightness(im).enhance(1.8)))

    col = lambda rows, k: np.array([r[k] for r in rows])  # noqa: E731
    print("\n== BLUR SCORE (Laplacian variance, lower = blurrier)")
    print("real photos      :", pct(col(base, "blur_score")))
    print("after blur sigma2:", pct(col(blur2, "blur_score")))
    print("after blur sigma4:", pct(col(blur4, "blur_score")))
    print("\n== BRIGHTNESS (mean grey, 0-255)")
    print("real photos      :", pct(col(base, "brightness")))
    print("darkened x0.35   :", pct(col(dark, "brightness")))
    print("brightened x1.8  :", pct(col(bright, "brightness")))
    print("\n== NEAR-WHITE PIXEL SHARE (%)")
    print("real photos      :", pct(100 * col(base, "saturated_frac")))
    print("brightened x1.8  :", pct(100 * col(bright, "saturated_frac")))

    print("\n== Candidate thresholds: share of photos flagged")
    for t in (10, 15, 20, 30, 40, 60, 80):
        print(f"blur < {t:3d}: real {100*(col(base,'blur_score')<t).mean():5.1f}%  sigma2 {100*(col(blur2,'blur_score')<t).mean():5.1f}%  sigma4 {100*(col(blur4,'blur_score')<t).mean():5.1f}%")
    for t in (30, 40, 50, 60, 70):
        print(f"mean < {t:3d}: real {100*(col(base,'brightness')<t).mean():5.1f}%  darkened {100*(col(dark,'brightness')<t).mean():5.1f}%")
    for t in (200, 210, 220, 230, 240):
        print(f"mean > {t:3d}: real {100*(col(base,'brightness')>t).mean():5.1f}%  brightened {100*(col(bright,'brightness')>t).mean():5.1f}%")
    for t in (0.05, 0.10, 0.15, 0.20, 0.30):
        print(f"white share > {t:4.2f}: real {100*(col(base,'saturated_frac')>t).mean():5.1f}%  brightened {100*(col(bright,'saturated_frac')>t).mean():5.1f}%")


if __name__ == "__main__":
    main()
