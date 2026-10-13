"""Checks the REAL trained models in models/ (exported from Colab). Skipped if they are not installed.

These do not measure accuracy (the notebook did, on the test split). They check that the exported files fit the app:
right classes, sane thresholds, the model loads and answers in the documented format.
"""
import json
from pathlib import Path

import pytest

from backend import config
from backend.services.inference import ModelRegistry
from conftest import synthetic_leaf

REAL = Path(__file__).resolve().parent.parent / "models"
pytestmark = pytest.mark.skipif(not (REAL / "calibration.json").exists(), reason="trained models are not installed in models/")


@pytest.fixture(scope="module")
def registry():
    return ModelRegistry(REAL)


def test_exported_files_match_the_app():
    cal = json.loads((REAL / "calibration.json").read_text(encoding="utf-8"))
    names = json.loads((REAL / "class_names.json").read_text(encoding="utf-8"))
    assert names == config.CLASS_NAMES == cal["class_names"]  # output index order must match training
    assert cal["ensemble"] == ["efficientnetv2s", "swin_t"]
    for m in cal["ensemble"]:
        spec = cal["models"][m]
        assert (REAL / spec["file"]).exists() and 0.3 < spec["temperature"] < 3 and spec["img_size"] in (224, 256, 288, 384)
    rej = cal["reject"]
    assert 0.3 < rej["min_confidence"] < 0.99 and 0.1 < rej["max_normalised_entropy"] < 1.0


def test_real_models_load_and_answer_in_the_documented_format(registry):
    assert registry.status() == {"ready": True, "reason": ""}
    r = registry.predict(synthetic_leaf(brown_fraction_of_leaf=0.1))
    assert set(r) >= {"label", "confidence", "rejected", "top3", "entropy", "severity", "heatmap_png_b64", "models_used"}
    assert r["models_used"] == ["efficientnetv2s", "swin_t"]
    assert len(r["top3"]) == 3 and 0 < r["confidence"] <= 1
    assert r["rejected"] or r["label"] in config.CLASS_NAMES
    assert r["rejected"] == (r["label"] is None)
