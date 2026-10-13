"""Inference tests with RANDOMLY initialised models (see conftest.write_fake_models).

They check the plumbing: loading from calibration.json, temperature scaling, ensembling, rejection, Grad-CAM,
severity gating and the API contract. Accuracy can only be judged with the real trained models.
"""
import base64
import io

import numpy as np
import pytest
import timm
import torch
from PIL import Image

from backend.app import create_app
from backend.services import gradcam
from backend.services.inference import ModelNotReady, ModelRegistry, normalised_entropy
from conftest import CLASSES, jpeg_bytes, synthetic_leaf, write_fake_models


@pytest.fixture()
def registry(fake_models_dir):
    return ModelRegistry(fake_models_dir)


def test_not_ready_when_folder_empty(tmp_path):
    reg = ModelRegistry(tmp_path)
    s = reg.status()
    assert not s["ready"] and "Missing in models/" in s["reason"]
    with pytest.raises(ModelNotReady):
        reg.predict(synthetic_leaf())


def test_not_ready_reports_missing_weight_file(tmp_path):
    d = write_fake_models(tmp_path / "m")
    (d / "resnet18.pt").unlink()
    assert "resnet18.pt" in ModelRegistry(d).status()["reason"]


def test_corrupt_weights_do_not_crash(tmp_path):
    d = write_fake_models(tmp_path / "m")
    (d / "resnet18.pt").write_bytes(b"not a checkpoint")
    s = ModelRegistry(d).status()
    assert not s["ready"] and "could not be loaded" in s["reason"]


def test_prediction_schema_and_probabilities(registry):
    r = registry.predict(synthetic_leaf(brown_fraction_of_leaf=0.2))
    assert registry.status()["ready"]
    assert r["rejected"] is False and r["label"] in CLASSES
    assert len(r["top3"]) == 3
    confs = [t["confidence"] for t in r["top3"]]
    assert confs == sorted(confs, reverse=True) and abs(r["confidence"] - confs[0]) < 1e-9
    assert 0 < sum(confs) <= 1.0 + 1e-6
    assert r["models_used"] == ["resnet18", "efficientnet_b0"]


def test_heatmap_is_a_png_image(registry):
    r = registry.predict(synthetic_leaf())
    img = Image.open(io.BytesIO(base64.b64decode(r["heatmap_png_b64"])))
    assert img.format == "PNG" and img.size == (224, 224)
    assert r["heatmap_model"] == "resnet18"  # first ensemble member that Grad-CAM supports


def test_severity_only_for_diseased_labels(registry):
    r = registry.predict(synthetic_leaf(brown_fraction_of_leaf=0.2))
    if r["label"] == "Healthy":
        assert r["severity"] is None
    else:
        assert r["severity"]["leaf_found"] and 0 <= r["severity"]["percent"] <= 100 and r["severity"]["overlay_png_b64"]


def test_rejection_by_low_confidence(tmp_path):
    d = write_fake_models(tmp_path / "m", reject=dict(min_confidence=0.99, max_normalised_entropy=1.0))
    r = ModelRegistry(d).predict(synthetic_leaf())  # random networks are never 99% sure
    assert r["rejected"] and r["label"] is None and "low_confidence" in r["reject_reasons"]
    assert r["heatmap_png_b64"] is None and r["severity"] is None
    assert len(r["top3"]) == 3  # the alternatives are still reported


def test_rejection_by_high_entropy(tmp_path):
    d = write_fake_models(tmp_path / "m", reject=dict(min_confidence=0.0, max_normalised_entropy=0.01))
    r = ModelRegistry(d).predict(synthetic_leaf())
    assert r["rejected"] and "high_entropy" in r["reject_reasons"]


def test_temperature_changes_confidence(tmp_path):
    img = synthetic_leaf()
    a = ModelRegistry(write_fake_models(tmp_path / "a")).predict(img)["confidence"]
    d = write_fake_models(tmp_path / "b")
    import json
    cal = json.loads((d / "calibration.json").read_text())
    for m in cal["models"].values():
        m["temperature"] = 0.2  # sharper
    (d / "calibration.json").write_text(json.dumps(cal))
    b = ModelRegistry(d).predict(img)["confidence"]
    assert b > a


def test_entropy_bounds():
    assert normalised_entropy(np.array([1.0, 0, 0, 0])) < 1e-6
    assert abs(normalised_entropy(np.full(4, 0.25)) - 1.0) < 1e-9


def test_gradcam_works_on_swin():
    model = timm.create_model("swin_tiny_patch4_window7_224", pretrained=False, num_classes=6).eval()
    assert gradcam.is_supported(model)
    x = torch.randn(1, 3, 224, 224)
    out = gradcam.heatmap_overlay(model, x, 2, np.full((224, 224, 3), 120, np.uint8))
    assert out.size == (224, 224)


def test_api_returns_full_result(registry):
    client = create_app(registry).test_client()
    r = client.post("/api/predict", data={"image": (io.BytesIO(jpeg_bytes(synthetic_leaf(brown_fraction_of_leaf=0.2))), "leaf.jpg")},
                    content_type="multipart/form-data")
    body = r.get_json()
    assert r.status_code == 200
    assert body["quality"]["ok"] is True and body["image"]["width"] == 512
    assert body["top3"] and "confidence" in body
    assert client.get("/api/health").get_json()["model_loaded"] is True


def test_api_503_still_reports_photo_quality():
    client = create_app(ModelRegistry("Z:/does/not/exist")).test_client()
    black = Image.fromarray(np.zeros((300, 300, 3), np.uint8))
    r = client.post("/api/predict", data={"image": (io.BytesIO(jpeg_bytes(black)), "black.jpg")}, content_type="multipart/form-data")
    body = r.get_json()
    assert r.status_code == 503 and "too_dark" in body["quality"]["issues"]
