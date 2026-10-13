"""Tests for scripts/eval_real_photos.py (the scorer for the user's own phone photos)."""
import csv
import math
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
import eval_real_photos as E  # noqa: E402
from conftest import CLASSES, synthetic_leaf, write_fake_models  # noqa: E402


# ---- statistics -----------------------------------------------------------------------------------
def test_wilson_interval_matches_known_values():
    lo, hi = E.wilson(22, 25)
    assert 0.69 < lo < 0.72 and 0.95 < hi < 0.97          # "88%" is really about 70%-96%
    lo, hi = E.wilson(25, 25)
    assert 0.86 < lo < 0.88 and hi == pytest.approx(1.0)  # even 25/25 does not prove 100%
    assert all(math.isnan(x) for x in E.wilson(0, 0))
    assert E.fmt_rate(0, 0).startswith("n/a")
    assert "88%" in E.fmt_rate(22, 25) and "95% CI" in E.fmt_rate(22, 25)


# ---- label sheet -----------------------------------------------------------------------------------
def make_folder(tmp_path, rows, files=None):
    folder = tmp_path / "photos"
    folder.mkdir()
    for name in files if files is not None else [r["file"] for r in rows]:
        synthetic_leaf().save(folder / name)
    with open(folder / "labels.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=["file", "true_label", "include", "plant_id", "lighting"], extrasaction="ignore")
        w.writeheader()
        w.writerows(rows)
    return folder


def test_read_labels_accepts_valid_rows_case_insensitively_and_skips_excluded(tmp_path):
    folder = make_folder(tmp_path, [
        {"file": "a.jpg", "true_label": "blast"}, {"file": "b.jpg", "true_label": "NOTRICE"},
        {"file": "c.jpg", "true_label": "Tungro", "include": "no"}])
    rows = E.read_labels(folder, CLASSES)
    assert [(r["file"], r["true_label"]) for r in rows] == [("a.jpg", "Blast"), ("b.jpg", "NotRice")]


@pytest.mark.parametrize("rows,files,message", [
    ([{"file": "a.jpg", "true_label": ""}], None, "true_label is empty"),
    ([{"file": "a.jpg", "true_label": "Bacterial Leaf Blight"}], None, "unknown label"),
    ([{"file": "ghost.jpg", "true_label": "Blast"}], [], "not found"),
])
def test_read_labels_reports_every_problem_clearly(tmp_path, rows, files, message):
    folder = make_folder(tmp_path, rows, files)
    with pytest.raises(ValueError, match=message):
        E.read_labels(folder, CLASSES)


def test_read_labels_missing_csv_and_nothing_to_evaluate(tmp_path):
    (tmp_path / "empty").mkdir()
    with pytest.raises(ValueError, match="--init-template"):
        E.read_labels(tmp_path / "empty", CLASSES)
    folder = make_folder(tmp_path, [{"file": "a.jpg", "true_label": "Blast", "include": "no"}])
    with pytest.raises(ValueError, match="no photos"):
        E.read_labels(folder, CLASSES)


def test_init_template_lists_photos_and_never_overwrites(tmp_path):
    folder = tmp_path / "p"
    folder.mkdir()
    synthetic_leaf().save(folder / "b.jpg")
    synthetic_leaf().save(folder / "a.png")
    (folder / "notes.txt").write_text("x")
    out = E.init_template(folder)
    rows = list(csv.DictReader(open(out, encoding="utf-8")))
    assert [r["file"] for r in rows] == ["a.png", "b.jpg"] and all(r["true_label"] == "" for r in rows)
    with pytest.raises(SystemExit):
        E.init_template(folder)


# ---- scoring rules -----------------------------------------------------------------------------------
def rec(true, pred=None, rejected=False, top1=None, conf=0.9, issues=(), **extra):
    return E.judge({"file": f"{true}_{pred}_{rejected}.jpg", "true_label": true, "pred": None if rejected else pred,
                    "top1": top1 or pred, "confidence": conf, "rejected": rejected, "issues": list(issues), **extra})


def test_judge_rules():
    assert rec("Blast", "Blast")["outcome"] == "correct"
    assert rec("Blast", "Tungro")["outcome"] == "wrong"
    r = rec("Blast", rejected=True, top1="Blast")
    assert r["outcome"] == "rejected" and r["correct"] is False and r["top1_correct"] is True   # refusing is not "correct"
    assert rec("NotRice", rejected=True, top1="Healthy")["outcome"] == "not_rice_rejected"
    assert rec("NotRice", "Healthy")["outcome"] == "not_rice_accepted" and rec("NotRice", "Healthy")["correct"] is False


def test_summary_numbers():
    records = [
        rec("Blast", "Blast"), rec("Blast", "Blast"), rec("Blast", "Tungro", top1="Tungro"),
        rec("Tungro", rejected=True, top1="Blast"),           # would have been wrong, rejection caught it
        rec("Tungro", rejected=True, top1="Tungro"),          # would have been right, refusing cost a correct answer
        rec("NotRice", rejected=True, top1="Healthy"), rec("NotRice", "Healthy"),
    ]
    s = E.summarise(records)
    assert (s["n_total"], s["n_rice"], s["n_notrice"]) == (7, 5, 2)
    assert s["strict"] == (2, 5) and s["coverage"] == (3, 5) and s["on_accepted"] == (2, 3)
    assert s["top1_without_rejection"] == (3, 5)              # Blast, Blast, and Tungro#2 had top-1 right
    assert s["errors_caught"] == (1, 2)                       # 2 wrong top-1s (Tungro answer, rejected Blast-for-Tungro); 1 caught
    assert s["notrice_rejected"] == (1, 2)
    assert s["per_class"]["Blast"]["correct"] == 2 and s["per_class"]["Tungro"]["rejected"] == 2
    assert s["confusion"]["Blast"] == {"Blast": 2, "Tungro": 1} and s["confusion"]["Tungro"] == {E.REJECTED: 2}
    assert {m["outcome"] for m in s["mistakes"]} == {"wrong", "not_rice_accepted"}


def test_summary_handles_quality_flags_breakdowns_and_plants():
    records = [rec("Blast", "Blast", issues=["blurry"], lighting="sun", plant_id="p1"),
               rec("Blast", "Tungro", lighting="shade", plant_id="p1"),
               rec("Tungro", "Tungro", lighting="sun", plant_id="p2")]
    s = E.summarise(records)
    assert s["flagged"] == (1, 1) and s["unflagged"] == (1, 2)
    assert s["breakdown"]["lighting"] == {"shade": (0, 1), "sun": (2, 2)}
    assert s["n_plants"] == 2 and s["plant_photos"] == 3


def test_markdown_contains_intervals_and_warnings():
    md = E.render_markdown(E.summarise([rec("Blast", "Blast"), rec("Blast", "Tungro")]), "test")
    for must in ("Strict accuracy", "95% CI", "Per class", "Confusion", "Mistakes", "70% to 96%", "separately", "confirmed by a person"):
        assert must in md, must


def test_markdown_with_only_one_kind_of_photo_does_not_crash():
    E.render_markdown(E.summarise([rec("NotRice", rejected=True, top1="Blast")]), "only non-rice")
    E.render_markdown(E.summarise([rec("Blast", "Blast")]), "only rice")


# ---- end to end -----------------------------------------------------------------------------------------
def test_main_runs_end_to_end_with_stand_in_models(tmp_path):
    models = write_fake_models(tmp_path / "models")
    folder = make_folder(tmp_path, [{"file": f"leaf{i}.jpg", "true_label": CLASSES[i % 6], "plant_id": f"p{i}"} for i in range(4)]
                         + [{"file": "hand.jpg", "true_label": "NotRice"}])
    out = tmp_path / "out"
    assert E.main([str(folder), "--models-dir", str(models), "--out", str(out)]) == 0
    assert {p.name for p in out.iterdir()} == {"per_photo.csv", "confusion.csv", "summary.md"}
    per = list(csv.DictReader(open(out / "per_photo.csv", encoding="utf-8")))
    assert len(per) == 5 and {r["file"] for r in per} == {"leaf0.jpg", "leaf1.jpg", "leaf2.jpg", "leaf3.jpg", "hand.jpg"}
    assert "Real-world test" in (out / "summary.md").read_text(encoding="utf-8")


def test_main_stops_clearly_when_no_model_is_installed(tmp_path):
    folder = make_folder(tmp_path, [{"file": "a.jpg", "true_label": "Blast"}])
    with pytest.raises(SystemExit) as exc:
        E.main([str(folder), "--models-dir", str(tmp_path / "no_models")])
    assert "No trained model" in str(exc.value)


def test_main_init_template(tmp_path):
    folder = tmp_path / "p"
    folder.mkdir()
    synthetic_leaf().save(folder / "x.jpg")
    assert E.main([str(folder), "--init-template"]) == 0 and (folder / "labels.csv").exists()
