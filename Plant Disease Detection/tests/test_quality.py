import numpy as np
from PIL import Image, ImageFilter

from backend.services import quality


def textured(size=600, seed=0):
    rng = np.random.default_rng(seed)
    base = rng.integers(60, 190, (size // 8, size // 8, 3)).astype(np.uint8)  # blocky detail at several scales
    img = Image.fromarray(base).resize((size, size), Image.BICUBIC)
    fine = rng.integers(-25, 26, (size, size, 3))
    return Image.fromarray(np.clip(np.asarray(img).astype(int) + fine, 0, 255).astype(np.uint8))


def test_sharp_normal_photo_is_ok():
    r = quality.assess(textured())
    assert r["ok"] and r["issues"] == []


def test_blurred_photo_is_flagged():
    r = quality.assess(textured().filter(ImageFilter.GaussianBlur(5)))
    assert "blurry" in r["issues"]


def test_dark_photo_is_flagged():
    dark = Image.fromarray((np.asarray(textured()) * 0.2).astype(np.uint8))
    assert "too_dark" in quality.assess(dark)["issues"]


def test_overexposed_photo_is_flagged():
    white = Image.fromarray(np.full((400, 400, 3), 255, np.uint8))
    assert "overexposed" in quality.assess(white)["issues"]


def test_score_does_not_depend_on_resolution():
    big = textured(1800)
    small = big.resize((600, 600), Image.LANCZOS)
    a, b = quality.measure(big)["blur_score"], quality.measure(small)["blur_score"]
    assert 0.5 < a / b < 2.0  # both are measured at the same fixed size
