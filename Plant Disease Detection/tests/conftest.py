"""Shared test helpers."""
import io
import json

import numpy as np
import pytest
import timm
import torch
from PIL import Image

from backend import config  # noqa: E402

CLASSES = ["Blast", "Brown Spot", "Healthy", "Leaf Smut", "Sheath Blight", "Tungro"]


def synthetic_leaf(size=512, brown_fraction_of_leaf=0.0, seed=0) -> Image.Image:
    """A plain-background photo: beige background, a green rectangular leaf (~34% of the image) and brown squares
    covering `brown_fraction_of_leaf` of the leaf. The true affected percent is therefore known."""
    rng = np.random.default_rng(seed)
    a = np.zeros((size, size, 3), np.uint8)
    a[:] = (205, 185, 150)                                   # beige background (not green)
    lo, hi = size // 5, size - size // 5
    a[lo:hi, lo:hi] = (55, 140, 50)                          # leaf
    leaf_px = (hi - lo) ** 2
    target = int(brown_fraction_of_leaf * leaf_px)
    side = max(4, int((target / 4) ** 0.5)) if target else 0  # four equal squares
    for (cy, cx) in [(lo + 40, lo + 40), (lo + 40, hi - 40 - side), (hi - 40 - side, lo + 40), (hi - 40 - side, hi - 40 - side)]:
        if side:
            a[cy:cy + side, cx:cx + side] = (115, 65, 25)    # brown lesion
    noise = rng.integers(-6, 7, a.shape)                     # mild camera noise
    return Image.fromarray(np.clip(a.astype(int) + noise, 0, 255).astype(np.uint8))


def jpeg_bytes(img: Image.Image) -> bytes:
    buf = io.BytesIO()
    img.save(buf, "JPEG")
    return buf.getvalue()


def write_fake_models(path, reject=None, models=(("resnet18", "resnet18"), ("efficientnet_b0", "efficientnet_b0"))):
    """Create a models/ folder with RANDOMLY initialised networks in the same layout the Colab export produces.
    This tests loading, calibration, rejection, Grad-CAM and the API. It says nothing about accuracy."""
    path.mkdir(parents=True, exist_ok=True)
    torch.manual_seed(0)
    spec = {}
    for key, arch in models:
        model = timm.create_model(arch, pretrained=False, num_classes=len(CLASSES))
        torch.save(model.state_dict(), path / f"{key}.pt")
        spec[key] = dict(file=f"{key}.pt", timm_name=arch, img_size=224, mean=[0.485, 0.456, 0.406], std=[0.229, 0.224, 0.225],
                         temperature=1.7, kwargs={})
    (path / "class_names.json").write_text(json.dumps(CLASSES))
    (path / "calibration.json").write_text(json.dumps(dict(
        class_names=CLASSES, models=spec, ensemble=[k for k, _ in models],
        reject=reject or dict(min_confidence=0.0, max_normalised_entropy=1.0))))
    return path


@pytest.fixture(scope="session")
def fake_models_dir(tmp_path_factory):
    return write_fake_models(tmp_path_factory.mktemp("models_accept"))


@pytest.fixture(autouse=True)
def isolate_models_dir(tmp_path, monkeypatch):
    """Tests must not depend on whether trained models happen to be installed in models/. Point the default at an empty
    folder; tests that need models pass their own folder. (tests/test_real_models.py checks the installed ones explicitly.)"""
    monkeypatch.setattr(config, "MODELS_DIR", tmp_path / "no_models_here")
