"""Tests for scripts/analyze_results.py (confidence intervals, rejection comparison, label-noise estimate)."""
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
import analyze_results as A  # noqa: E402

REAL = Path(__file__).resolve().parent.parent / "results" / "colab_outputs" / "outputs"


def test_softmax_and_entropy():
    p = A.softmax(np.array([[0.0, 0.0, 0.0, 0.0], [10.0, 0.0, 0.0, 0.0]]))
    assert np.allclose(p.sum(1), 1) and np.allclose(p[0], 0.25)
    e = A.norm_entropy(p)
    assert e[0] == pytest.approx(1.0) and e[1] < 0.01
    assert np.allclose(A.softmax(np.array([[2.0, 1.0]]), T=1.0), A.softmax(np.array([[4.0, 2.0]]), T=2.0))  # temperature


def test_macro_f1_matches_sklearn():
    from sklearn.metrics import f1_score
    rng = np.random.default_rng(0)
    y, pred = rng.integers(0, 5, 400), rng.integers(0, 5, 400)
    assert A.macro_f1(y, pred, 5) == pytest.approx(f1_score(y, pred, average="macro"))
    assert A.macro_f1(np.array([0, 1]), np.array([0, 0]), 2) == pytest.approx(f1_score([0, 1], [0, 0], average="macro", zero_division=0))


def test_cluster_bootstrap_keeps_groups_whole():
    groups = np.array([0, 0, 0, 1, 1, 2, 3, 3, 3, 3])
    for idx in A.cluster_bootstrap(groups, n_boot=50, seed=3):
        for g, size in ((0, 3), (1, 2), (2, 1), (3, 4)):
            n = int(np.sum(groups[idx] == g))
            assert n % size == 0          # a group is either absent or present as whole copies
    sizes = {len(i) for i in A.cluster_bootstrap(groups, n_boot=30, seed=1)}
    assert len(sizes) > 1                 # resampling groups changes the total size


def test_ci_is_ordered():
    lo, hi = A.ci(np.arange(100))
    assert lo < hi and 0 <= lo <= 5 and 94 <= hi <= 99


def synthetic_probs(n=3000, k=4, acc=0.8, seed=0):
    """Probabilities whose confidence is informative: right answers tend to be more confident."""
    rng = np.random.default_rng(seed)
    y = rng.integers(0, k, n)
    p = np.zeros((n, k))
    for i in range(n):
        right = rng.random() < acc
        c = y[i] if right else rng.choice([j for j in range(k) if j != y[i]])
        conf = rng.beta(8, 2) if right else rng.beta(3, 3)
        p[i] = (1 - conf) / (k - 1)
        p[i, c] = conf
    return p, y


def test_rejection_rule_trades_coverage_for_accuracy():
    p, y = synthetic_probs()
    ct, et = A.choose_thresholds(p[:1500], y[:1500])
    r = A.rejection_report(p[1500:], y[1500:], ct, et)
    assert r["coverage"] < 1 and r["acc_accepted"] > r["overall_acc"] and r["errors_caught"] > 0.3
    cov = A.accuracy_at_coverage(p, y)
    assert cov[0.3] >= cov[0.7] >= cov[1.0] - 1e-9          # fewer, more confident photos => higher accuracy
    assert cov[1.0] == pytest.approx((p.argmax(1) == y).mean())


def test_thresholds_fall_back_when_target_is_unreachable():
    p, y = synthetic_probs(acc=0.45)
    ct, _ = A.choose_thresholds(p, y, target=0.99)
    assert 0 < ct < 1                                          # no crash, a quantile fallback is used


def test_confident_joint_recovers_planted_label_noise():
    """Flip 15% of the labels at random; the estimate should be in the right ballpark (it is an estimate, not exact)."""
    p, y_true = synthetic_probs(n=4000, k=4, acc=0.9, seed=2)
    rng = np.random.default_rng(5)
    y = y_true.copy()
    flip = rng.random(len(y)) < 0.15
    y[flip] = (y[flip] + rng.integers(1, 4, flip.sum())) % 4
    _, given, noise = A.confident_joint(p, y, 4)
    assert 0.08 < noise < 0.25, noise
    _, _, clean_noise = A.confident_joint(p, y_true, 4)
    assert clean_noise < noise                                  # clean labels look cleaner
    flagged = (given >= 0) & (given != y)
    assert flip[flagged].mean() > 0.7                           # most flagged photos really are the flipped ones


def test_cross_class_neighbours():
    df = pd.DataFrame({"class": ["A", "A", "B", "B", "A"],
                       "capture_ts": ["2025-01-01T10:00:00", "2025-01-01T10:00:05", "2025-01-01T10:00:08", "2025-01-01T10:05:00", "2025-01-01T10:05:03"]})
    r = A.cross_class_neighbours(df, max_gap_s=10)
    assert r["near_pairs"] == 3                                  # 10:00:00-05 (A,A), 10:00:05-08 (A,B), 10:05:00-03 (B,A)
    assert r["near_pairs_different_class"] == 2                  # the A->B and the B->A steps; the A,A pair has the same class
    mixed = pd.DataFrame({"class": ["A", "B"], "capture_ts": ["2025-01-01T10:00:00.130000", "2025-01-01T10:00:02"]})  # mixed timestamp styles
    assert A.cross_class_neighbours(mixed)["near_pairs"] == 1


@pytest.mark.skipif(not (REAL / "logits_efficientnetv2s_test.npy").exists(), reason="Colab outputs not downloaded")
def test_reproduces_the_colab_numbers_from_the_real_logits(tmp_path):
    D = A.load(REAL, REAL.parent.parent)
    yv, yt = D["y"]["val"], D["y"]["test"]
    assert float((D["test"]["efficientnetv2s"].argmax(1) == yt).mean()) == pytest.approx(0.7550, abs=1e-4)
    assert float((D["test"]["ensemble"].argmax(1) == yt).mean()) == pytest.approx(0.7507, abs=1e-3)
    ct, et = A.choose_thresholds(D["val"]["ensemble"], yv)
    assert ct == pytest.approx(0.845, abs=0.005) and et == pytest.approx(0.683, abs=0.005)   # the notebook's thresholds
    r = A.rejection_report(D["test"]["ensemble"], yt, ct, et)
    assert r["coverage"] == pytest.approx(0.505, abs=0.005) and r["acc_accepted"] == pytest.approx(0.927, abs=0.005)
    assert A.main(["--boot", "40", "--no-images", "--out", str(tmp_path)]) == 0
    assert "Label-noise audit" in (tmp_path / "analysis.md").read_text(encoding="utf-8")
