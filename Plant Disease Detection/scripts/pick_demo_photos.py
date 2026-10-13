"""Pick demo photos that the REAL models answer confidently and correctly, from the dataset's held-out TEST split.

    python scripts/pick_demo_photos.py [--per-class-sample 40] [--keep 4]

Writes demo_photos/verified/ (the original 1024 px photos) and demo_photos/verified/README.md (what to expect).
These are chosen BECAUSE the model does well on them, so they are for demonstrating the app, NOT evidence of accuracy.
The script also prints the share of the sampled test photos that were answered, and how often those answers were right,
for all sampled photos (not just the chosen ones), which is the honest picture.
"""
import argparse
import io
import random
import sys
import zipfile
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from backend.services.image_io import load_image  # noqa: E402
from backend.services.inference import ModelRegistry  # noqa: E402

DATASET_ZIP = ROOT / "RiceLeafDiseaseBD A Field-Based Annotated Smartpho" / "RiceLeafDiseaseBD.zip"
INNER = "RiceLeafDiseaseBD/Original images/"
FOLDER = {"Blast": "Blast", "Brown_Spot": "Brown spot", "Healthy": "Healthy", "Leaf_Smut": "Leaf smut", "Sheath_Blight": "Sheath blight", "Tungro": "Rice Tungro"}
DISPLAY = {"Blast": "Blast", "Brown_Spot": "Brown Spot", "Healthy": "Healthy", "Leaf_Smut": "Leaf Smut", "Sheath_Blight": "Sheath Blight", "Tungro": "Tungro"}


def wilson(k, n, z=1.96):
    if n == 0:
        return float("nan"), float("nan")
    p = k / n
    d = 1 + z * z / n
    c = (p + z * z / (2 * n)) / d
    m = z * np.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return c - m, c + m


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--per-class-sample", type=int, default=40)
    ap.add_argument("--keep", type=int, default=4)
    ap.add_argument("--seed", type=int, default=7)
    ap.add_argument("--out", type=Path, default=ROOT / "demo_photos" / "verified")
    a = ap.parse_args(argv)

    sp = pd.read_csv(ROOT / "results" / "colab_outputs" / "outputs" / "splits" / "splits.csv")
    test = sp[sp.split == "test"]
    reg = ModelRegistry()
    if not reg.status()["ready"]:
        raise SystemExit("models/ is not ready: " + reg.status()["reason"])
    rng = random.Random(a.seed)
    rows = []
    with zipfile.ZipFile(DATASET_ZIP) as z:
        for cls, grp in test.groupby("class"):
            for _, r in grp.sample(min(a.per_class_sample, len(grp)), random_state=a.seed).iterrows():
                fname = r["path"].split("/", 1)[1]
                raw = z.read(f"{INNER}{FOLDER[cls]}/{fname}")
                res = reg.predict(load_image(fname, raw))
                rows.append({"true": DISPLAY[cls], "answer": None if res["rejected"] else res["label"], "conf": res["confidence"],
                             "rejected": res["rejected"], "file": fname, "raw": raw, "heat": bool(res["heatmap_png_b64"]),
                             "sev": (res["severity"] or {}).get("level") if (res["severity"] or {}).get("leaf_found") else None})
            print(f"  scored {cls}", flush=True)

    df = pd.DataFrame(rows)
    n, answered = len(df), int((~df.rejected).sum())
    correct = int(((~df.rejected) & (df.answer == df.true)).sum())
    lo, hi = wilson(correct, answered)
    print(f"\nSampled TEST photos: {n} | answered: {answered} ({answered / n:.0%}) | correct among answered: {correct}/{answered} = {correct / max(1, answered):.0%} (95% CI {lo:.0%}-{hi:.0%})")
    print("(all sampled photos, not only the chosen ones)")

    a.out.mkdir(parents=True, exist_ok=True)
    for old in a.out.glob("*.jpg"):
        old.unlink()
    lines = ["# Verified demo photos", "",
             "Held-out TEST photos from RiceLeafDiseaseBD (the model never trained on them) that the trained model answers confidently and correctly. "
             "They were **chosen because the model does well on them**, so they show the app working; they are **not** evidence of accuracy.", "",
             f"Honest picture from {n} randomly sampled test photos: the app answered {answered} ({answered / n:.0%}) and was right on {correct} of those ({correct / max(1, answered):.0%}; 95% CI {lo:.0%} to {hi:.0%}).", "",
             "| File | Disease | App answer | Confidence | Severity (experimental) |", "|---|---|---|---:|---|"]
    for cls in DISPLAY.values():
        good = df[(df.true == cls) & (~df.rejected) & (df.answer == cls)].sort_values("conf", ascending=False).head(a.keep)
        for _, r in good.iterrows():
            name = f"{cls.replace(' ', '_')}__{r['file'].replace(' ', '_')}"
            (a.out / name).write_bytes(r["raw"])
            lines.append(f"| {name} | {cls} | {r['answer']} | {r['conf']:.0%} | {r['sev'] or '-'} |")
        print(f"  {cls}: kept {len(good)}")
    (a.out / "README.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print("\nSaved to", a.out)
    return 0


if __name__ == "__main__":
    sys.exit(main())
