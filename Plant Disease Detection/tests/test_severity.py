"""Severity tests on SYNTHETIC leaves with a known affected area.

They prove the arithmetic and the guards work. They do NOT prove the method is accurate on real field
photos: it was measured to be unreliable there (see the docstring of backend/services/severity.py).
"""
import numpy as np
from PIL import Image

from backend.services import severity
from conftest import synthetic_leaf


def test_clean_leaf_scores_near_zero():
    r = severity.estimate(synthetic_leaf(brown_fraction_of_leaf=0.0))
    assert r["leaf_found"] and r["percent"] < 2.0 and r["level"] == "Mild"


def test_known_brown_area_is_recovered():
    for frac in (0.08, 0.20, 0.40):
        r = severity.estimate(synthetic_leaf(brown_fraction_of_leaf=frac))
        assert abs(r["percent"] - 100 * frac) < 4.0, (frac, r)


def test_levels_follow_percent():
    assert severity.level_for(3) == "Mild"
    assert severity.level_for(15) == "Moderate"
    assert severity.level_for(60) == "Severe"
    assert [severity.estimate(synthetic_leaf(brown_fraction_of_leaf=f))["level"] for f in (0.05, 0.18, 0.40)] == ["Mild", "Moderate", "Severe"]


def test_no_leaf_is_reported_not_guessed():
    blue = Image.fromarray(np.full((300, 300, 3), (40, 60, 200), np.uint8))
    r = severity.estimate(blue)
    assert r["leaf_found"] is False and r["percent"] is None and r["level"] is None


def test_overlay_is_returned_on_request():
    r = severity.estimate(synthetic_leaf(brown_fraction_of_leaf=0.2), with_overlay=True)
    assert r["overlay"].size[0] > 0


def test_check_samples_writes_overlays(tmp_path):
    p = tmp_path / "leaf.jpg"
    synthetic_leaf(brown_fraction_of_leaf=0.2).save(p)
    rows = severity.check_samples([p], tmp_path / "out")
    assert rows[0]["leaf_found"] and (tmp_path / "out" / "leaf_severity.png").exists() and (tmp_path / "out" / "severity_check.csv").exists()
