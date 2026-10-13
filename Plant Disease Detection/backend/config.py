"""Central settings for the Flask backend."""
import os
from pathlib import Path

# Project root = the folder that contains backend/, frontend/ and models/.
ROOT = Path(__file__).resolve().parent.parent

# Trained weights and class_names.json are copied here after Colab training.
MODELS_DIR = Path(os.environ.get("MODELS_DIR", ROOT / "models"))

# Classes of the RiceLeafDiseaseBD dataset, in the same (alphabetical) order the
# training notebook uses. Once training has produced models/class_names.json,
# that file is the source of truth (the model's output index order must match
# the training order exactly). This list is only a display fallback.
CLASS_NAMES = [
    "Blast",
    "Brown Spot",
    "Healthy",
    "Leaf Smut",
    "Sheath Blight",
    "Tungro",
]

ALLOWED_EXT = {".jpg", ".jpeg", ".png"}
ALLOWED_FORMATS = {"JPEG", "PNG"}  # checked against the real file content, not just the name
MAX_UPLOAD_MB = 10
MAX_SIDE_PX = 1024  # phone photos are 12-50 MP; downscaling keeps CPU inference fast

# ---- Photo quality thresholds (backend/services/quality.py) -----------------------------
# Chosen with scripts/measure_quality_thresholds.py on 1,500 RiceLeafDiseaseBD photos (250 per class):
#   real photos: blur score p0.5 = 99 (so 40 flags 0% of them), mean brightness 89-155, near-white share <= 0.7%.
#   Artificially damaged copies (Gaussian blur sigma 2 / 4, brightness x0.35 / x1.8) are flagged at the rates
#   below. The dataset contains almost no bad photos, so these values are conservative starting points,
#   NOT validated on real bad phone photos. Re-check them in Stage 6 with your own blurry / dark photos.
QUALITY_SIDE_PX = 512          # photos are scaled to this longest side before measuring, so scores are comparable
BLUR_MIN_LAPLACIAN_VAR = 40.0  # below => "blurry": flags 0% real, 49% of sigma-2 blur, 100% of sigma-4 blur
DARK_MAX_MEAN = 60.0           # mean grey (0-255) below => "too dark": flags 0% real, 99.8% of x0.35 darkened
BRIGHT_MIN_MEAN = 200.0        # mean grey above => "overexposed": flags 0% real, 26% of x1.8 brightened
BRIGHT_MAX_SATURATED_FRAC = 0.10  # more than 10% near-white pixels => "overexposed": 0% real, 72% of x1.8

# ---- Severity (backend/services/severity.py) ---------------------------------------------
# Percent of leaf area affected. These cut-offs are this project's own choice, NOT an official scale.
SEVERITY_MILD_MAX = 10.0
SEVERITY_MODERATE_MAX = 25.0
