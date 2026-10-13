"""Shrink RiceLeafDiseaseBD for Colab and attach capture times.

Run on your PC (uses the project's .venv; Pillow only, no other packages):

    .venv\\Scripts\\python.exe scripts\\prepare_dataset.py

What it does
  * Reads ONLY "Original images/". It never touches "Annotated images", which have red
    boxes drawn on the leaves; training on those would let the model learn the boxes.
  * Resizes every image from 1024x1024 to SIZE x SIZE (default 320) -> ~10x smaller upload.
  * Reads "Dataset metadata.xlsx" and records each photo's capture time (parsed from the
    original camera filename). The notebook uses it to keep photos taken seconds apart
    in the same train/val/test split.
  * Writes RiceLeaf_<SIZE>.zip containing <Class>/<file>.jpg and metadata.csv.

Upload the result to Google Drive at  MyDrive/rice_project/data/RiceLeaf_320.zip
"""
import argparse
import csv
import html
import io
import re
import sys
import zipfile
from datetime import datetime, timezone
from pathlib import Path

from PIL import Image

ROOT = Path(__file__).resolve().parent.parent
DATASET_DIR = ROOT / "RiceLeafDiseaseBD A Field-Based Annotated Smartpho"

# Metadata/zip folder name -> clean class name (folder-safe, underscores).
CLASS_MAP = {
    "Blast": "Blast",
    "Brown spot": "Brown_Spot",
    "Healthy": "Healthy",
    "Leaf smut": "Leaf_Smut",
    "Rice Tungro": "Tungro",
    "Sheath blight": "Sheath_Blight",
}
# The spreadsheet's lower-case class labels differ from the folder names in a few places.
META_CLASS_TO_FOLDER = {
    "Blast": "Blast", "blast": "Blast",
    "Brown spot": "Brown spot", "brown spot": "Brown spot",
    "Healthy": "Healthy",
    "Leaf smut": "Leaf smut",
    "Rice Tungro": "Rice Tungro",
    "Sheath blight": "Sheath blight",
}
INNER = "RiceLeafDiseaseBD/Original images"


def read_xlsx_rows(path: Path) -> list[list[str]]:
    """Minimal .xlsx reader (first sheet) using only the standard library."""
    with zipfile.ZipFile(path) as x:
        shared = x.read("xl/sharedStrings.xml").decode("utf8")
        # One <si> per string; rich-text strings have several <t> pieces to join.
        strings = [
            html.unescape("".join(re.findall(r"<t[^>]*>([^<]*)</t>", si)))
            for si in re.findall(r"<si>(.*?)</si>", shared, flags=re.S)
        ]
        sheet = x.read("xl/worksheets/sheet1.xml").decode("utf8")
    rows = []
    for row in re.findall(r"<row[^>]*>(.*?)</row>", sheet, flags=re.S):
        cells = {}
        for col, attrs, inner in re.findall(r'<c r="([A-Z]+)\d+"([^>]*?)(?:/>|>(.*?)</c>)', row, flags=re.S):
            v = re.search(r"<v>(.*?)</v>", inner or "")
            val = v.group(1) if v else ""
            if 't="s"' in attrs and val:
                val = strings[int(val)]
            cells[col] = val
        rows.append([cells.get(c, "") for c in "ABCDEFGHI"])
    return rows


_STAMP = re.compile(r"(20\d{2})(\d{2})(\d{2})[_-]?(\d{2})(\d{2})(\d{2})")
_EPOCH_MS = re.compile(r"^(\d{13})\D")


def parse_capture_time(name: str) -> str:
    """Capture time (ISO string) from a phone filename, or '' if it cannot be parsed.

    Handles 20250425_173915.jpg, IMG20250401165527.jpg, PXL_20250410_..., 1743593818130.jpg
    """
    m = _STAMP.search(name)
    if m:
        try:
            return datetime(*map(int, m.groups())).isoformat()
        except ValueError:
            return ""
    m = _EPOCH_MS.match(name)
    if m:
        return datetime.fromtimestamp(int(m.group(1)) / 1000, tz=timezone.utc).replace(tzinfo=None).isoformat()
    return ""


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--zip", type=Path, default=DATASET_DIR / "RiceLeafDiseaseBD.zip")
    ap.add_argument("--metadata", type=Path, default=DATASET_DIR / "Dataset metadata.xlsx")
    ap.add_argument("--out", type=Path, default=ROOT / "data_prepared")
    ap.add_argument("--size", type=int, default=320)
    ap.add_argument("--limit-per-class", type=int, default=0, help="debug: only first N images per class")
    args = ap.parse_args()

    rows = read_xlsx_rows(args.metadata)
    header, rows = rows[0], rows[1:]
    assert header[:3] == ["Class", "Original_Filename", "New_Filename"], f"unexpected header: {header}"

    args.out.mkdir(parents=True, exist_ok=True)
    out_zip = args.out / (f"RiceLeaf_{args.size}.zip" if not args.limit_per_class else f"RiceLeaf_{args.size}_debug.zip")

    per_class = {}
    kept, skipped, no_time = [], [], 0
    with zipfile.ZipFile(args.zip) as src, zipfile.ZipFile(out_zip, "w", zipfile.ZIP_STORED) as dst:
        for i, (cls, orig, new, *_rest) in enumerate(rows, 1):
            folder = META_CLASS_TO_FOLDER.get(cls)
            if folder is None:
                skipped.append((cls, new, "unknown class"))
                continue
            per_class[folder] = per_class.get(folder, 0) + 1
            if args.limit_per_class and per_class[folder] > args.limit_per_class:
                continue
            try:
                with src.open(f"{INNER}/{folder}/{new}") as f:
                    img = Image.open(io.BytesIO(f.read()))
                    img.load()
                # Squash to a square exactly like the dataset authors did (no crop, no padding),
                # so train-time and app-time images have the same geometry.
                img = img.convert("RGB").resize((args.size, args.size), Image.LANCZOS)
            except Exception as exc:  # unreadable / missing file
                skipped.append((cls, new, repr(exc)))
                continue
            buf = io.BytesIO()
            img.save(buf, "JPEG", quality=95)
            clean = CLASS_MAP[folder]
            dst.writestr(f"{clean}/{new}", buf.getvalue())
            ts = parse_capture_time(orig)
            no_time += ts == ""
            kept.append((clean, new, orig, ts))
            if i % 500 == 0:
                print(f"  {i}/{len(rows)} processed", flush=True)

        meta = io.StringIO()
        w = csv.writer(meta, lineterminator="\n")
        w.writerow(["class", "file", "orig_name", "capture_ts"])
        w.writerows(kept)
        dst.writestr("metadata.csv", meta.getvalue())

    print(f"\nWrote {out_zip}  ({out_zip.stat().st_size / 1e6:.0f} MB)")
    print(f"Images kept: {len(kept)}   skipped: {len(skipped)}   without parseable capture time: {no_time}")
    for clean in sorted({k[0] for k in kept}):
        print(f"  {clean:14s} {sum(1 for k in kept if k[0] == clean)}")
    for s in skipped[:10]:
        print("  SKIPPED:", s)
    return 0


if __name__ == "__main__":
    sys.exit(main())
