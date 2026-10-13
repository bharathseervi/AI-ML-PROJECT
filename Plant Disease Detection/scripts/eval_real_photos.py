"""Score the app on YOUR OWN phone photos, kept separate from the dataset test results.

1. Put your photos in a folder, e.g.  my_photos\\
2. Create the label sheet:   python scripts/eval_real_photos.py --init-template my_photos
   then open my_photos\\labels.csv and fill in the true_label column (see docs/TESTING_CHECKLIST.md).
   The true label must come from a person who knows (agriculture officer, KVK, experienced farmer), NOT from the app.
3. Run:                      python scripts/eval_real_photos.py my_photos
   (needs trained models in models/; or add  --api http://127.0.0.1:5000  to test through the running Flask server)

Output goes to results/real_photos_<time>/ : per_photo.csv, confusion.csv and summary.md (paste into report section 6.5).

labels.csv columns
  file        photo file name (required)
  true_label  one of the disease names below, or NotRice for a photo with no rice leaf (required)
  include     optional: put "no" to leave a photo out (for example the deliberately bad quality-test photos)
  plant_id    optional: which plant it came from (many photos of one plant are NOT independent test cases)
  confirmed_by, phone, date, place, lighting, background, notes   optional; lighting and background are used for a breakdown
"""
import argparse
import csv
import sys
from collections import Counter, defaultdict
from datetime import datetime
from math import sqrt
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

NOT_RICE = "NotRice"
REJECTED = "REJECTED"
IMAGE_EXT = {".jpg", ".jpeg", ".png"}
META_COLS = ["confirmed_by", "phone", "date", "place", "lighting", "background", "notes"]


# ------------------------------------------------------------------------------------------------
# pure functions (unit-tested)
# ------------------------------------------------------------------------------------------------
def wilson(k: int, n: int, z: float = 1.96):
    """95% Wilson confidence interval for k successes in n trials. (nan, nan) if n == 0."""
    if n == 0:
        return float("nan"), float("nan")
    p = k / n
    d = 1 + z * z / n
    c = (p + z * z / (2 * n)) / d
    m = z * sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return max(0.0, c - m), min(1.0, c + m)


def fmt_rate(k: int, n: int) -> str:
    if n == 0:
        return "n/a (0 photos)"
    lo, hi = wilson(k, n)
    return f"{k}/{n} = {k / n:.0%}  (95% CI {lo:.0%} to {hi:.0%})"


def read_labels(folder: Path, valid_labels: list[str]) -> list[dict]:
    """Read labels.csv, check every row, return the rows to evaluate. Raises ValueError with a clear message."""
    path = folder / "labels.csv"
    if not path.exists():
        raise ValueError(f"{path} not found. Create it with:  python scripts/eval_real_photos.py --init-template {folder}")
    with open(path, newline="", encoding="utf-8-sig") as f:
        rows = list(csv.DictReader(f))
    if not rows or "file" not in rows[0] or "true_label" not in rows[0]:
        raise ValueError("labels.csv needs at least the columns: file, true_label")
    allowed = {l.lower(): l for l in valid_labels + [NOT_RICE]}
    problems, out = [], []
    for i, r in enumerate(rows, start=2):  # row 1 is the header
        if (r.get("include") or "yes").strip().lower() in ("no", "n", "false", "0"):
            continue
        name, label = (r.get("file") or "").strip(), (r.get("true_label") or "").strip()
        if not name:
            continue
        if not label:
            problems.append(f"row {i} ({name}): true_label is empty")
            continue
        if label.lower() not in allowed:
            problems.append(f"row {i} ({name}): unknown label '{label}'. Use one of: {', '.join(sorted(allowed.values()))}")
            continue
        if not (folder / name).exists():
            problems.append(f"row {i}: file '{name}' not found in {folder}")
            continue
        r = dict(r)
        r["file"], r["true_label"] = name, allowed[label.lower()]
        out.append(r)
    if problems:
        raise ValueError("labels.csv has problems:\n  " + "\n  ".join(problems))
    if not out:
        raise ValueError("labels.csv has no photos to evaluate (all excluded or empty).")
    return out


def judge(record: dict) -> dict:
    """Add the outcome to one record: true label vs what the app answered."""
    true, rejected = record["true_label"], record["rejected"]
    pred = REJECTED if rejected else record["pred"]
    if true == NOT_RICE:
        outcome = "not_rice_rejected" if rejected else "not_rice_accepted"  # good / bad
        correct = rejected
    else:
        correct = (not rejected) and record["pred"] == true
        outcome = "correct" if correct else ("rejected" if rejected else "wrong")
    return {**record, "answer": pred, "correct": correct, "outcome": outcome,
            "top1_correct": record.get("top1") == true if true != NOT_RICE else None}


def summarise(records: list[dict]) -> dict:
    rice = [r for r in records if r["true_label"] != NOT_RICE]
    notrice = [r for r in records if r["true_label"] == NOT_RICE]
    accepted = [r for r in rice if not r["rejected"]]
    wrong_top1 = [r for r in rice if not r["top1_correct"]]
    caught = [r for r in wrong_top1 if r["rejected"]]

    per_class = {}
    for label in sorted({r["true_label"] for r in rice}):
        sub = [r for r in rice if r["true_label"] == label]
        per_class[label] = {"n": len(sub), "correct": sum(r["correct"] for r in sub),
                            "rejected": sum(r["rejected"] for r in sub),
                            "mean_conf": sum(r["confidence"] for r in sub) / len(sub)}

    conf = defaultdict(Counter)
    for r in records:
        conf[r["true_label"]][r["answer"]] += 1

    flagged = [r for r in rice if r["issues"]]
    clean = [r for r in rice if not r["issues"]]

    breakdown = {}
    for col in ("lighting", "background"):
        groups = defaultdict(list)
        for r in rice:
            v = (r.get(col) or "").strip()
            if v:
                groups[v].append(r)
        if len(groups) > 1:
            breakdown[col] = {k: (sum(x["correct"] for x in v), len(v)) for k, v in sorted(groups.items())}

    plants = [r.get("plant_id", "").strip() for r in records if (r.get("plant_id") or "").strip()]
    return {
        "n_total": len(records), "n_rice": len(rice), "n_notrice": len(notrice),
        "strict": (sum(r["correct"] for r in rice), len(rice)),
        "coverage": (len(accepted), len(rice)),
        "on_accepted": (sum(r["correct"] for r in accepted), len(accepted)),
        "top1_without_rejection": (sum(bool(r["top1_correct"]) for r in rice), len(rice)),
        "errors_caught": (len(caught), len(wrong_top1)),
        "notrice_rejected": (sum(r["rejected"] for r in notrice), len(notrice)),
        "per_class": per_class, "confusion": {k: dict(v) for k, v in conf.items()},
        "flagged": (sum(r["correct"] for r in flagged), len(flagged)),
        "unflagged": (sum(r["correct"] for r in clean), len(clean)),
        "breakdown": breakdown,
        "mistakes": [r for r in records if r["outcome"] in ("wrong", "not_rice_accepted")],
        "n_plants": len(set(plants)) if plants else None, "plant_photos": len(plants),
    }


def render_markdown(s: dict, title: str, extra_note: str = "") -> str:
    L = [f"# Real-world test: {title}", "",
         f"Photos evaluated: **{s['n_total']}** ({s['n_rice']} rice-leaf photos, {s['n_notrice']} non-rice photos).", ""]
    if s["n_plants"] is not None:
        L.append(f"Distinct plants (from plant_id): **{s['n_plants']}** for {s['plant_photos']} photos. "
                 "Photos of the same plant are not independent, so the effective sample size is closer to the number of plants.")
        L.append("")
    L += ["## Headline numbers (rice-leaf photos)", "",
          "| Measure | Result |", "|---|---|",
          f"| Strict accuracy (correct answer; 'unable to diagnose' counts as not correct) | {fmt_rate(*s['strict'])} |",
          f"| Coverage (the app gave an answer instead of refusing) | {fmt_rate(*s['coverage'])} |",
          f"| Accuracy on the answers it did give | {fmt_rate(*s['on_accepted'])} |",
          f"| Top-1 accuracy if it were never allowed to refuse | {fmt_rate(*s['top1_without_rejection'])} |",
          f"| Wrong top-1 answers that the rejection rule caught | {fmt_rate(*s['errors_caught'])} |",
          f"| Non-rice photos correctly refused | {fmt_rate(*s['notrice_rejected'])} |", ""]
    L += ["## Per class", "", "| True class | Photos | Correct | Refused | Mean confidence |", "|---|---:|---:|---:|---:|"]
    for k, v in s["per_class"].items():
        L.append(f"| {k} | {v['n']} | {v['correct']} | {v['rejected']} | {v['mean_conf']:.2f} |")
    L += ["", "## Confusion (rows = true label, columns = what the app answered)", ""]
    cols = sorted({a for row in s["confusion"].values() for a in row})
    L += ["| True \\ Answer | " + " | ".join(cols) + " |", "|---|" + "---:|" * len(cols)]
    for t, row in sorted(s["confusion"].items()):
        L.append(f"| {t} | " + " | ".join(str(row.get(c, 0)) for c in cols) + " |")
    L += ["", "## Photo-quality flags", "",
          f"* Correct among photos the quality check flagged: {fmt_rate(*s['flagged'])}",
          f"* Correct among photos not flagged: {fmt_rate(*s['unflagged'])}",
          "* (Small groups; treat as an observation, not a result.)", ""]
    for col, groups in s["breakdown"].items():
        L += [f"## By {col}", "", "| " + col + " | Correct / photos |", "|---|---|"]
        L += [f"| {k} | {fmt_rate(c, n)} |" for k, (c, n) in groups.items()]
        L.append("")
    L += ["## Mistakes", ""]
    if s["mistakes"]:
        L += ["| File | True | App answered | Confidence |", "|---|---|---|---:|"]
        L += [f"| {r['file']} | {r['true_label']} | {r['answer']} | {r['confidence']:.2f} |" for r in s["mistakes"]]
    else:
        L.append("None.")
    L += ["", "## Read this before quoting the numbers", "",
          "* With a small number of photos the confidence interval is wide. For example 22 correct out of 25 is 88%, but the true accuracy could plausibly be anywhere from about 70% to 96%. Quote the interval, not just the percentage.",
          "* These photos are a small sample from your own area. They show whether the dataset result carries over; they do not prove the app works everywhere.",
          "* The true labels must have been confirmed by a person who knows rice diseases, not by this app. Say who confirmed them in your report.",
          "* Report these numbers **separately** from the dataset test split; never average them together."]
    if extra_note:
        L += ["", extra_note]
    return "\n".join(L) + "\n"


# ------------------------------------------------------------------------------------------------
# predictors (in-process or through the Flask API)
# ------------------------------------------------------------------------------------------------
def inprocess_predictor(models_dir=None):
    from backend.services import quality
    from backend.services.image_io import load_image
    from backend.services.inference import ModelRegistry

    reg = ModelRegistry(models_dir)
    st = reg.status()
    if not st["ready"]:
        raise SystemExit(f"No trained model available: {st['reason']}\nCopy the exported files into models/ first (see README).")

    def predict(path: Path) -> dict:
        img = load_image(path.name, path.read_bytes())
        q = quality.assess(img)
        r = reg.predict(img)
        return {"pred": r["label"], "top1": r["top3"][0]["label"], "confidence": r["confidence"], "rejected": r["rejected"], "issues": q["issues"]}

    return predict, reg.class_names()


def api_predictor(url: str):
    import requests

    base = url.rstrip("/")
    try:
        health = requests.get(f"{base}/api/health", timeout=5).json()
    except Exception as exc:
        raise SystemExit(f"Cannot reach the API at {base}: {exc}")
    if not health.get("model_loaded"):
        raise SystemExit(f"The server has no trained model: {health.get('model_reason')}")

    def predict(path: Path) -> dict:
        r = requests.post(f"{base}/api/predict", files={"image": (path.name, path.read_bytes())}, timeout=120)
        if r.status_code != 200:
            raise SystemExit(f"{path.name}: server answered {r.status_code}: {r.text[:200]}")
        j = r.json()
        return {"pred": j["label"], "top1": j["top3"][0]["label"], "confidence": j["confidence"], "rejected": j["rejected"],
                "issues": j["quality"]["issues"]}

    return predict, health["classes"]


def init_template(folder: Path) -> Path:
    files = sorted(p.name for p in folder.iterdir() if p.suffix.lower() in IMAGE_EXT)
    if not files:
        raise SystemExit(f"No .jpg/.jpeg/.png photos found in {folder}")
    out = folder / "labels.csv"
    if out.exists():
        raise SystemExit(f"{out} already exists; not overwriting it.")
    with open(out, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["file", "true_label", "include", "plant_id", "confirmed_by", "phone", "date", "place", "lighting", "background", "notes"])
        for name in files:
            w.writerow([name, "", "yes", "", "", "", "", "", "", "", ""])
    return out


def evaluate(rows: list[dict], folder: Path, predict) -> list[dict]:
    records = []
    for i, r in enumerate(rows, 1):
        p = predict(folder / r["file"])
        rec = judge({**{c: r.get(c, "") for c in META_COLS + ["plant_id"]}, "file": r["file"], "true_label": r["true_label"], **p})
        print(f"[{i}/{len(rows)}] {r['file']:32s} true={r['true_label']:14s} app={rec['answer']:14s} {'OK ' if rec['correct'] else 'MISS'}")
        records.append(rec)
    return records


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Score the app on your own phone photos.")
    ap.add_argument("folder", type=Path, help="folder with the photos and labels.csv")
    ap.add_argument("--init-template", action="store_true", help="create labels.csv for the photos in the folder and stop")
    ap.add_argument("--api", default=None, help="test through a running Flask server instead of loading the models here")
    ap.add_argument("--models-dir", default=None)
    ap.add_argument("--out", type=Path, default=None)
    a = ap.parse_args(argv)

    if a.init_template:
        print("Created", init_template(a.folder), "\nFill in the true_label column, then run without --init-template.")
        return 0

    predict, classes = api_predictor(a.api) if a.api else inprocess_predictor(a.models_dir)
    try:
        rows = read_labels(a.folder, classes)
    except ValueError as exc:
        raise SystemExit(str(exc))
    records = evaluate(rows, a.folder, predict)
    summary = summarise(records)

    out = a.out or ROOT / "results" / f"real_photos_{datetime.now():%Y%m%d_%H%M%S}"
    out.mkdir(parents=True, exist_ok=True)
    cols = ["file", "true_label", "answer", "top1", "confidence", "rejected", "outcome", "correct", "issues"] + META_COLS + ["plant_id"]
    with open(out / "per_photo.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=cols, extrasaction="ignore")
        w.writeheader()
        for r in records:
            w.writerow({**r, "issues": " ".join(r["issues"])})
    labels = sorted({r["true_label"] for r in records} | {r["answer"] for r in records})
    with open(out / "confusion.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["true \\ answer"] + labels)
        for t in sorted(summary["confusion"]):
            w.writerow([t] + [summary["confusion"][t].get(c, 0) for c in labels])
    md = render_markdown(summary, f"{a.folder.name} ({datetime.now():%Y-%m-%d})")
    (out / "summary.md").write_text(md, encoding="utf-8")
    print("\n" + md)
    print("Saved to", out)
    return 0


if __name__ == "__main__":
    sys.exit(main())
