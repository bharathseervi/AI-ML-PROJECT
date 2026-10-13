"""Extra analysis of the Colab results, using only the saved predictions (logits). No GPU and no retraining.

    python scripts/analyze_results.py            (reads results/colab_outputs/outputs, writes results/analysis/)

What it does
  1. 95% confidence intervals for accuracy and macro-F1, with a CLUSTER bootstrap (whole groups of near-identical
     photos are resampled together, because photos in one group are not independent).
  2. Paired comparison of the models (is the ensemble really no better than EfficientNetV2-S alone?).
  3. The rejection rule re-derived for every option (single models and the ensemble) with the SAME procedure as the
     notebook, plus accuracy at fixed coverage levels so the options are compared fairly.
     Sanity check: for the ensemble it must reproduce the notebook's thresholds and test numbers.
  4. A label-noise audit: confident-learning estimate of the share of wrong labels, a list of suspect photos, and the
     number of different-class photos taken within seconds of each other.
"""
import argparse
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
SINGLES = ["resnet18", "efficientnetv2s", "swin_t"]
LABEL = {"resnet18": "ResNet-18", "efficientnetv2s": "EfficientNetV2-S", "swin_t": "Swin-T", "ensemble": "Ensemble"}


# ------------------------------------------------------------------------------------------------
# small numeric helpers (unit-tested)
# ------------------------------------------------------------------------------------------------
def softmax(z, T=1.0):
    z = z / T
    z = z - z.max(1, keepdims=True)
    e = np.exp(z)
    return e / e.sum(1, keepdims=True)


def norm_entropy(p):
    return -(p * np.log(p + 1e-12)).sum(1) / np.log(p.shape[1])


def macro_f1(y, pred, k):
    f1 = []
    for c in range(k):
        tp = np.sum((pred == c) & (y == c))
        fp = np.sum((pred == c) & (y != c))
        fn = np.sum((pred != c) & (y == c))
        f1.append(0.0 if tp == 0 else 2 * tp / (2 * tp + fp + fn))
    return float(np.mean(f1))


def cluster_bootstrap(groups, n_boot=2000, seed=0):
    """Yield index arrays that resample whole groups with replacement."""
    rng = np.random.default_rng(seed)
    ids, inverse = np.unique(groups, return_inverse=True)
    members = [np.nonzero(inverse == g)[0] for g in range(len(ids))]
    for _ in range(n_boot):
        pick = rng.integers(0, len(ids), len(ids))
        yield np.concatenate([members[g] for g in pick])


def ci(values, lo=2.5, hi=97.5):
    return float(np.percentile(values, lo)), float(np.percentile(values, hi))


def choose_thresholds(p_val, y_val, target=0.95, min_coverage=0.5, entropy_pct=95):
    """Exactly the rule in the training notebook (section 10)."""
    conf, correct = p_val.max(1), p_val.argmax(1) == y_val
    order = np.argsort(-conf)
    cum_acc = np.cumsum(correct[order]) / np.arange(1, len(order) + 1)
    cov = np.arange(1, len(order) + 1) / len(order)
    ok = np.nonzero((cum_acc >= target) & (cov >= min_coverage))[0]
    conf_thr = float(max(conf[order][ok.max()], 0.5)) if len(ok) else float(np.quantile(conf, 0.2))
    ent_thr = float(np.percentile(norm_entropy(p_val)[correct], entropy_pct)) if correct.any() else 1.0
    return conf_thr, ent_thr


def apply_rejection(p, conf_thr, ent_thr):
    return (p.max(1) < conf_thr) | (norm_entropy(p) > ent_thr)


def rejection_report(p, y, conf_thr, ent_thr):
    rej = apply_rejection(p, conf_thr, ent_thr)
    correct = p.argmax(1) == y
    return {"coverage": float((~rej).mean()),
            "acc_accepted": float(correct[~rej].mean()) if (~rej).any() else float("nan"),
            "errors_caught": float(rej[~correct].mean()) if (~correct).any() else float("nan"),
            "overall_acc": float(correct.mean())}


def accuracy_at_coverage(p, y, coverages=(0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 1.0)):
    order = np.argsort(-p.max(1))
    correct = (p.argmax(1) == y)[order]
    return {c: float(correct[: max(1, int(round(c * len(y))))].mean()) for c in coverages}


def confident_joint(p, y, k):
    """Confident-learning estimate (Northcutt et al.): per-class thresholds, a confident joint, and the implied share of
    mislabelled examples. Assumes the probabilities are reasonably calibrated and noise depends only on the class."""
    t = np.array([p[y == j, j].mean() for j in range(k)])
    given = np.full(len(y), -1)
    for i in range(len(y)):
        cand = np.nonzero(p[i] >= t)[0]
        if len(cand):
            given[i] = cand[np.argmax(p[i][cand])]
    cj = np.zeros((k, k))
    for yi, gi in zip(y, given):
        if gi >= 0:
            cj[yi, gi] += 1
    cj = cj / cj.sum(axis=1, keepdims=True) * np.bincount(y, minlength=k)[:, None]   # calibrate rows to class sizes
    cj = cj / cj.sum() * len(y)
    off = cj.sum() - np.trace(cj)
    return cj, given, float(off / len(y))


def cross_class_neighbours(df, max_gap_s=10):
    """Pairs of photos taken within max_gap_s of each other (in time order, any class) and whether their classes differ."""
    d = df.dropna(subset=["capture_ts"]).copy()
    d["capture_ts"] = pd.to_datetime(d["capture_ts"], format="ISO8601", errors="coerce")
    d = d.dropna(subset=["capture_ts"]).sort_values("capture_ts").reset_index(drop=True)
    gap = d["capture_ts"].diff().dt.total_seconds().values[1:]
    differ = (d["class"].values[1:] != d["class"].values[:-1])
    near = gap <= max_gap_s
    pairs = np.nonzero(near & differ)[0]
    return {"near_pairs": int(near.sum()), "near_pairs_different_class": int((near & differ).sum()),
            "idx_pairs": [(int(i), int(i + 1)) for i in pairs], "frame": d}


# ------------------------------------------------------------------------------------------------
def load(base: Path, results: Path):
    names = json.loads((base / "class_names.json").read_text(encoding="utf-8"))
    cmp_ = pd.read_csv(results / "comparison_table.csv")
    temps = {}
    for key, label in (("resnet18", "Baseline CNN (ResNet-18)"), ("efficientnetv2s", "EfficientNetV2-S"), ("swin_t", "Swin-T")):
        temps[key] = float(cmp_.loc[cmp_["Model"] == label, "T"].iloc[0])
    sp = pd.read_csv(base / "splits" / "splits.csv")
    out = {"names": names, "splits": sp, "temps": temps, "val": {}, "test": {}}
    for split in ("val", "test"):
        for m in SINGLES:
            out[split][m] = softmax(np.load(base / f"logits_{m}_{split}.npy"), temps[m])
        out[split]["ensemble"] = np.mean([out[split]["efficientnetv2s"], out[split]["swin_t"]], axis=0)
    out["y"] = {s: sp[sp.split == s]["label"].values for s in ("val", "test")}
    out["g"] = {s: sp[sp.split == s]["group"].values for s in ("val", "test")}
    out["paths"] = {s: sp[sp.split == s]["path"].values for s in ("val", "test")}
    return out


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--base", type=Path, default=ROOT / "results" / "colab_outputs" / "outputs")
    ap.add_argument("--results", type=Path, default=ROOT / "results")
    ap.add_argument("--out", type=Path, default=ROOT / "results" / "analysis")
    ap.add_argument("--boot", type=int, default=2000)
    ap.add_argument("--no-images", action="store_true")
    a = ap.parse_args(argv)
    a.out.mkdir(parents=True, exist_ok=True)
    D = load(a.base, a.results)
    k = len(D["names"])
    yt, gt, yv = D["y"]["test"], D["g"]["test"], D["y"]["val"]
    models = SINGLES + ["ensemble"]
    L = ["# Extra analysis of the Colab results", "",
         "All numbers come from the saved predictions (logits) of the Colab run on the validation and test splits; nothing was retrained.", ""]

    # ---- 1. confidence intervals ---------------------------------------------------------------
    pt = D["test"]
    acc = {m: float((pt[m].argmax(1) == yt).mean()) for m in models}
    f1 = {m: macro_f1(yt, pt[m].argmax(1), k) for m in models}
    boot = {m: ([], []) for m in models}
    diffs = {("ensemble", "efficientnetv2s"): [], ("efficientnetv2s", "resnet18"): [], ("swin_t", "resnet18"): [], ("ensemble", "resnet18"): [], ("ensemble", "swin_t"): []}
    correct = {m: pt[m].argmax(1) == yt for m in models}
    for idx in cluster_bootstrap(gt, a.boot):
        for m in models:
            boot[m][0].append(correct[m][idx].mean())
            boot[m][1].append(macro_f1(yt[idx], pt[m].argmax(1)[idx], k))
        for (m1, m2) in diffs:
            diffs[(m1, m2)].append(correct[m1][idx].mean() - correct[m2][idx].mean())
    L += ["## 1. Test results with 95% confidence intervals", "",
          f"Cluster bootstrap ({a.boot} resamples; whole groups of near-identical photos are resampled together).", "",
          "| Model | Accuracy | 95% CI | Macro-F1 | 95% CI |", "|---|---:|---|---:|---|"]
    for m in models:
        lo, hi = ci(boot[m][0]); flo, fhi = ci(boot[m][1])
        L.append(f"| {LABEL[m]} | {acc[m]:.1%} | {lo:.1%} to {hi:.1%} | {f1[m]:.3f} | {flo:.3f} to {fhi:.3f} |")
    L += ["", "## 2. Paired comparison (difference in accuracy, same resamples)", "",
          "| Comparison | Difference | 95% CI | Share of resamples where the first is better | Verdict |", "|---|---:|---|---:|---|"]
    verdicts = {}
    for (m1, m2), d in diffs.items():
        d = np.array(d); lo, hi = ci(d)
        verdict = "no clear difference" if lo <= 0 <= hi else ("first is better" if lo > 0 else "second is better")
        verdicts[(m1, m2)] = verdict
        L.append(f"| {LABEL[m1]} minus {LABEL[m2]} | {acc[m1] - acc[m2]:+.1%} | {lo:+.1%} to {hi:+.1%} | {(d > 0).mean():.0%} | {verdict} |")
    try:
        from scipy.stats import binomtest
        b = int(np.sum(correct["ensemble"] & ~correct["efficientnetv2s"])); c = int(np.sum(~correct["ensemble"] & correct["efficientnetv2s"]))
        pv = binomtest(b, b + c, 0.5).pvalue if b + c else 1.0
        L += ["", f"McNemar exact test, ensemble vs EfficientNetV2-S: ensemble right and EfficientNetV2-S wrong on {b} photos, the reverse on {c}; p = {pv:.2f}. (Ignores photo grouping, so it is slightly optimistic.)"]
    except Exception:
        pass

    # ---- 3. rejection for every option -----------------------------------------------------------
    # selective accuracy: is the ensemble's advantage at equal coverage real? (cluster bootstrap)
    def sel_acc(pm, idx, cov):
        order = np.argsort(-pm[idx].max(1))
        cor = (pm[idx].argmax(1) == yt[idx])[order]
        return cor[: max(1, int(round(cov * len(idx))))].mean()

    sel = {c: [] for c in (0.3, 0.5, 0.7)}
    for idx in cluster_bootstrap(gt, min(a.boot, 1000), seed=1):
        for c in sel:
            sel[c].append(sel_acc(pt["ensemble"], idx, c) - sel_acc(pt["efficientnetv2s"], idx, c))
    L += ["", "## 3. The rejection rule for each option", "",
          "Thresholds are chosen on the VALIDATION split with the notebook's rule (accepted accuracy >= 95% with coverage >= 50%, entropy limit = 95th percentile among correct answers), then applied once to the test split.", "",
          "| Option | Confidence limit | Entropy limit | Test coverage | Test accuracy on accepted | Wrong answers refused | Overall accuracy |", "|---|---:|---:|---:|---:|---:|---:|"]
    rej = {}
    for m in models:
        ct, et = choose_thresholds(D["val"][m], yv)
        r = rejection_report(D["test"][m], yt, ct, et)
        rej[m] = (ct, et, r)
        L.append(f"| {LABEL[m]} | {ct:.3f} | {et:.3f} | {r['coverage']:.1%} | {r['acc_accepted']:.1%} | {r['errors_caught']:.1%} | {r['overall_acc']:.1%} |")
    L += ["", "Sanity check against the Colab notebook (ensemble): confidence 0.845, entropy 0.683, test coverage 50.5%, accuracy on accepted 92.7%, errors refused 85.3%. "
          f"This script gives {rej['ensemble'][0]:.3f}, {rej['ensemble'][1]:.3f}, {rej['ensemble'][2]['coverage']:.1%}, {rej['ensemble'][2]['acc_accepted']:.1%}, {rej['ensemble'][2]['errors_caught']:.1%}.", "",
          "### Accuracy among the photos each model is MOST confident about (test split, no thresholds involved)", "",
          "| Coverage (share of photos answered) | " + " | ".join(LABEL[m] for m in models) + " |", "|---|" + "---:|" * len(models)]
    cov_tab = {m: accuracy_at_coverage(pt[m], yt) for m in models}
    for c in cov_tab["ensemble"]:
        L.append(f"| {c:.0%} | " + " | ".join(f"{cov_tab[m][c]:.1%}" for m in models) + " |")
    L += ["", "**Is the ensemble's advantage at equal coverage real?** Accuracy of the ensemble minus EfficientNetV2-S among the photos each is most confident about (cluster bootstrap):", "",
          "| Coverage | Difference | 95% CI | Verdict |", "|---|---:|---|---|"]
    for c, d in sel.items():
        lo, hi = ci(d)
        verdict = "ensemble is better" if lo > 0 else ("EfficientNetV2-S is better" if hi < 0 else "no clear difference")
        L.append(f"| {c:.0%} | {cov_tab['ensemble'][c] - cov_tab['efficientnetv2s'][c]:+.1%} | {lo:+.1%} to {hi:+.1%} | {verdict} |")
    L += ["", "Note: for the single models the notebook's rule cannot reach 95% accepted accuracy with at least 50% coverage on validation data, so it falls back to a looser confidence limit and answers about 78% of photos at about 80-83% accuracy. That is why the rows of the threshold table above are not directly comparable; the fixed-coverage table is the fair comparison."]

    # ---- 4. label-noise audit ---------------------------------------------------------------------
    p_all = np.concatenate([D["val"]["ensemble"], D["test"]["ensemble"]])
    y_all = np.concatenate([yv, yt])
    path_all = np.concatenate([D["paths"]["val"], D["paths"]["test"]])
    cj, given, noise = confident_joint(p_all, y_all, k)
    L += ["", "## 4. Label-noise audit", "",
          f"**Confident-learning estimate** (validation + test photos, {len(y_all)} photos the models never trained on): about **{noise:.1%}** of the labels look wrong. "
          "This is an estimate that assumes the model's probabilities are roughly calibrated and that mistakes in labels depend only on the class. It is NOT confirmed by an expert; treat it as an order of magnitude.", "",
          "Estimated confusion between the GIVEN label (rows) and the label the model is confident it should be (columns):", "",
          "| Given \\ Likely true | " + " | ".join(D["names"]) + " |", "|---|" + "---:|" * k]
    for i, n in enumerate(D["names"]):
        L.append(f"| {n} | " + " | ".join(f"{cj[i, j]:.0f}" for j in range(k)) + " |")

    sus = np.nonzero((given >= 0) & (given != y_all))[0]
    margin = np.array([p_all[i, given[i]] - p_all[i, y_all[i]] for i in sus])
    sus = sus[np.argsort(-margin)]
    pd.DataFrame({"path": path_all[sus], "given_label": [D["names"][y_all[i]] for i in sus], "model_thinks": [D["names"][given[i]] for i in sus],
                  "prob_given": [round(float(p_all[i, y_all[i]]), 3) for i in sus], "prob_model": [round(float(p_all[i, given[i]]), 3) for i in sus]}
                 ).to_csv(a.out / "suspect_labels.csv", index=False)
    L += ["", f"{len(sus)} photos are flagged as having a suspect label; the full list is in `suspect_labels.csv` (most suspicious first) for an expert to check.", ""]

    sp = D["splits"]
    nb = cross_class_neighbours(sp)
    same = nb["near_pairs"] - nb["near_pairs_different_class"]
    L += ["**Photos of different classes taken within 10 seconds of each other** (in time order, all classes together): "
          f"{nb['near_pairs']} consecutive pairs were taken within 10 s; in {nb['near_pairs_different_class']} of them ({nb['near_pairs_different_class'] / max(1, nb['near_pairs']):.1%}) the two photos carry different class labels, "
          f"and in {same} they carry the same label. A different label within seconds does not prove an error (the photographer may have moved to another leaf), but it shows how close the classes are in time and place.", ""]

    # ---- montage of the most suspicious photos ---------------------------------------------------
    if not a.no_images:
        import zipfile
        from PIL import Image, ImageDraw
        zpath = ROOT / "data_prepared" / "RiceLeaf_320.zip"
        if zpath.exists() and len(sus):
            top = sus[:24]
            S = 200
            sheet = Image.new("RGB", (S * 6, (S + 28) * 4), "white")
            d = ImageDraw.Draw(sheet)
            with zipfile.ZipFile(zpath) as z:
                for n, i in enumerate(top):
                    im = Image.open(__import__("io").BytesIO(z.read(path_all[i]))).convert("RGB").resize((S, S))
                    x, y0 = (n % 6) * S, (n // 6) * (S + 28)
                    sheet.paste(im, (x, y0 + 28))
                    d.text((x + 3, y0 + 2), f"label: {D['names'][y_all[i]]}", fill=(0, 0, 0))
                    d.text((x + 3, y0 + 14), f"model: {D['names'][given[i]]}", fill=(170, 0, 0))
            sheet.save(a.out / "suspect_labels.png")
            L += ["![The 24 most suspicious labels](suspect_labels.png)", "", "*Top: the given label (black) and what the model is confident it should be (red).*", ""]

    (a.out / "analysis.md").write_text("\n".join(L) + "\n", encoding="utf-8")
    print("\n".join(L))
    print("\nSaved to", a.out)
    return 0


if __name__ == "__main__":
    sys.exit(main())
