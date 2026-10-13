"""Typesetting, PDF report and the /api/info, /api/classes, /api/report endpoints."""
import base64
import io
import json

import pytest
from PIL import Image

from backend import disease_info as di
from backend.app import create_app
from backend.services import pdf_report, typeset
from conftest import jpeg_bytes, synthetic_leaf

pymupdf = pytest.importorskip("pymupdf")  # dev-only PDF renderer used to check the pages


def heatmap_b64():
    buf = io.BytesIO()
    Image.new("RGB", (64, 64), (220, 40, 40)).save(buf, "PNG")
    return base64.b64encode(buf.getvalue()).decode()


def result(**over):
    r = {"label": "Blast", "confidence": 0.91, "rejected": False, "reject_reasons": [],
         "top3": [{"label": "Blast", "confidence": 0.91}, {"label": "Brown Spot", "confidence": 0.05}],
         "heatmap_png_b64": heatmap_b64(), "severity": {"leaf_found": True, "percent": 12.0, "level": "Moderate"},
         "quality": {"issues": []}}
    r.update(over)
    return r


PHOTO = jpeg_bytes(synthetic_leaf(brown_fraction_of_leaf=0.1))


def pdf_text(pdf: bytes) -> str:
    return " ".join(p.get_text() for p in pymupdf.open(stream=pdf, filetype="pdf"))


# ---- typesetting ----------------------------------------------------------------------------
def test_script_runs_pick_the_right_font():
    assert typeset.split_runs("ಬ್ಲಾಸ್ಟ್ (Blast) 25-30") == [("kn", "ಬ್ಲಾಸ್ಟ್ ("), ("latin", "Blast) 25-30")]
    assert typeset.split_runs("क्षेत्र °C")[0][0] == "hi"


def test_shaping_really_happens():
    """Conjuncts and ligatures mean the glyph count differs from the character count. Plain per-character drawing would not."""
    kn = typeset.face("kn").shape("ಕ್ರಿಯೆ")
    hi = typeset.face("hi").shape("क्षेत्र")
    assert len(kn) != len("ಕ್ರಿಯೆ") and len(hi) != len("क्षेत्र")
    assert sum(g[1] for g in hi) > 0


@pytest.mark.parametrize("lang", ["en", "kn", "hi"])
def test_wrapped_lines_fit_the_page(lang):
    ts = typeset.typesetter_for(lang)
    text = di.get_info("Sheath Blight", lang, "Mild")["description"]
    lines = typeset.wrap(ts, text, 10, 300)
    assert len(lines) > 1 and all(ts.width(ln, 10) <= 300 + 0.01 for ln in lines)
    assert len(typeset.wrap(ts, "x" * 400, 10, 100)) > 1  # an unbreakable token is hard-broken, not dropped


def test_english_text_is_encodable_by_the_pdf_standard_font():
    """English uses Helvetica (cp1252). A character outside it would print as a wrong glyph."""
    for label in di.INFO:
        d = di.INFO[label]["en"]
        for text in [d["name"], d["description"]] + [x for k in di.SECTION_KEYS_LISTS for x in d[k]]:
            text.encode("cp1252")
    for text in di.COMMON["en"]["nutrient"] + di.COMMON["en"]["water"] + [di.DISCLAIMER["en"], di.CHEMICAL_NOTE["en"]]:
        text.encode("cp1252")
    for value in pdf_report.S["en"].values():
        for text in (value if isinstance(value, list) else [value]):
            text.encode("cp1252")


# ---- PDF ---------------------------------------------------------------------------------------
@pytest.mark.parametrize("lang", ["en", "kn", "hi"])
@pytest.mark.parametrize("label", list(di.INFO))
def test_report_builds_for_every_label_and_language(label, lang):
    sev = None if label == "Healthy" else {"leaf_found": True, "percent": 30.0, "level": "Severe"}
    pdf = pdf_report.build_report(result(label=label, severity=sev), PHOTO, lang)
    doc = pymupdf.open(stream=pdf, filetype="pdf")
    assert pdf[:5] == b"%PDF-" and 1 <= doc.page_count <= 6
    assert len(pdf) < 3_000_000


def test_english_report_has_selectable_text():
    text = pdf_text(pdf_report.build_report(result(label="Brown Spot"), PHOTO, "en"))
    for must in ("Rice Leaf Disease Report", "Brown Spot", "91.0%", "Moderate", "Experimental", "KVK", "knowledgebank.irri.org", "Doses are NOT given"):
        assert must in text, must


@pytest.mark.parametrize("lang", ["kn", "hi"])
def test_indic_report_pages_have_ink_and_use_vector_glyphs(lang):
    doc = pymupdf.open(stream=pdf_report.build_report(result(), PHOTO, lang), filetype="pdf")
    pix = doc[0].get_pixmap(dpi=50)
    dark = sum(1 for i in range(0, len(pix.samples), pix.n) if pix.samples[i] < 120)
    assert dark > 2000  # real ink on the page
    assert len(doc[0].get_text().strip()) < 400  # drawn as outlines, not as (wrongly shaped) character text


def test_rejected_report_has_no_treatment_advice():
    pdf = pdf_report.build_report(result(label=None, rejected=True, reject_reasons=["low_confidence"], heatmap_png_b64=None,
                                         severity=None, quality={"issues": ["blurry"]}), PHOTO, "en")
    text = pdf_text(pdf)
    assert "Unable to diagnose reliably" in text and "NOT reliable" in text and "Photo tips" in text
    assert "Management" not in text and "Chemical" not in text


def test_severity_not_found_and_healthy_wording():
    assert "Not enough green leaf" in pdf_text(pdf_report.build_report(result(severity={"leaf_found": False}), PHOTO, "en"))
    assert "not calculated for a healthy leaf" in pdf_text(pdf_report.build_report(result(label="Healthy", severity=None), PHOTO, "en"))


def test_damaged_heatmap_does_not_stop_the_report():
    pdf = pdf_report.build_report(result(heatmap_png_b64="!!!not base64 or an image!!!"), PHOTO, "en")
    assert pdf[:5] == b"%PDF-"


def test_unknown_label_is_an_error():
    with pytest.raises(ValueError):
        pdf_report.build_report(result(label="Not a disease"), PHOTO, "en")


# ---- API ---------------------------------------------------------------------------------------
@pytest.fixture()
def client():
    return create_app().test_client()


def post_report(client, res, lang="en", photo=PHOTO, name="leaf.jpg"):
    return client.post("/api/report", data={"image": (io.BytesIO(photo), name), "result": json.dumps(res), "lang": lang},
                       content_type="multipart/form-data")


def test_report_endpoint_returns_a_pdf(client):
    r = post_report(client, result(), "kn")
    assert r.status_code == 200 and r.mimetype == "application/pdf" and r.data[:5] == b"%PDF-"
    assert "attachment" in r.headers["Content-Disposition"] and ".pdf" in r.headers["Content-Disposition"]


def test_report_rejects_bad_requests(client):
    assert client.post("/api/report", data={"result": "{}"}, content_type="multipart/form-data").status_code == 400  # no image
    r = client.post("/api/report", data={"image": (io.BytesIO(PHOTO), "a.jpg"), "result": "not json"}, content_type="multipart/form-data")
    assert r.status_code == 400 and r.get_json()["error"] == "bad_result"
    assert post_report(client, result(label="<script>alert(1)</script>")).status_code == 400
    assert post_report(client, result(severity={"leaf_found": True, "level": "Catastrophic", "percent": 5})).status_code == 400
    assert post_report(client, result(confidence="abc")).status_code == 400
    r = client.post("/api/report", data={"image": (io.BytesIO(b"not an image"), "a.jpg"), "result": json.dumps(result())},
                    content_type="multipart/form-data")
    assert r.status_code == 400 and r.get_json()["error"] == "bad_image"


def test_report_accepts_a_realistic_large_result(client):
    """A real /api/predict response is ~0.6 MB (heatmap + severity overlay as base64). Werkzeug's default 500 KB
    form-field cap used to reject it with HTTP 413; this guards the fix."""
    rng_png = io.BytesIO()
    Image.effect_noise((512, 512), 90).convert("RGB").save(rng_png, "PNG")  # noisy image => big PNG
    big = base64.b64encode(rng_png.getvalue()).decode()
    res = result(heatmap_png_b64=big, severity={"leaf_found": True, "percent": 8.0, "level": "Mild", "overlay_png_b64": big})
    assert len(json.dumps(res)) > 600_000
    assert post_report(client, res).status_code == 200


def test_report_clamps_untrusted_numbers(client):
    r = post_report(client, result(confidence=7, severity={"leaf_found": True, "level": "Mild", "percent": 5000}))
    assert r.status_code == 200
    text = pdf_text(r.data)
    assert "100.0%" in text and "5000" not in text


def test_info_endpoint(client):
    body = client.get("/api/info?label=Tungro&lang=hi&severity=Severe").get_json()
    assert body["name"].startswith("टुंग्रो") and body["severity_advice"] and body["sources"]
    assert body["section_titles"]["symptoms"] == "लक्षण"
    assert body["translation_reviewed"] is False
    assert client.get("/api/info?label=Nope").status_code == 404
    assert client.get("/api/info?label=Blast&lang=zz").get_json()["lang"] == "en"


def test_classes_endpoint(client):
    names = client.get("/api/classes?lang=kn").get_json()["names"]
    assert set(names) == set(di.INFO) and "ಬ್ಲಾಸ್ಟ್" in names["Blast"]
