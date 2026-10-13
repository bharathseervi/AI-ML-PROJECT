"""Frontend smoke tests using Streamlit's headless AppTest. Run: pytest tests/

The backend client is replaced with fakes, so these need no running server.
"""
import sys
from pathlib import Path

import pytest
from streamlit.testing.v1 import AppTest

FRONTEND = Path(__file__).resolve().parent.parent / "frontend"
sys.path.insert(0, str(FRONTEND))  # so `import api_client` works the way it does under `streamlit run`
import api_client  # noqa: E402

APP = str(FRONTEND / "app.py")


@pytest.fixture(autouse=True)
def fake_backend(monkeypatch):
    """Route the UI's API calls to the real Flask app running in-process (no network, no server)."""
    from backend.app import create_app

    client = create_app().test_client()
    monkeypatch.setattr(api_client, "health", lambda: {"status": "ok", "model_loaded": False})
    monkeypatch.setattr(api_client, "names", lambda lang: client.get(f"/api/classes?lang={lang}").get_json()["names"])

    def info(label, lang, severity=None):
        q = f"/api/info?label={label}&lang={lang}" + (f"&severity={severity}" if severity else "")
        r = client.get(q)
        return r.get_json() if r.status_code == 200 else None

    def report(image_bytes, filename, result, lang):
        import io
        import json

        r = client.post("/api/report", data={"image": (io.BytesIO(image_bytes), filename), "result": json.dumps(result), "lang": lang},
                        content_type="multipart/form-data")
        if r.status_code != 200:
            raise api_client.BackendError(r.get_json()["message"])
        return r.data

    monkeypatch.setattr(api_client, "info", info)
    monkeypatch.setattr(api_client, "report", report)


def test_renders_without_error():
    at = AppTest.from_file(APP, default_timeout=30).run()
    assert not at.exception
    assert at.title[0].value == "Rice Leaf Disease Detector"


def test_diagnose_without_photo_shows_hint():
    at = AppTest.from_file(APP, default_timeout=30).run()
    at.button[0].click().run()
    assert any("Add a photo first" in i.value for i in at.info)


def test_language_switch_to_kannada_and_hindi():
    at = AppTest.from_file(APP, default_timeout=30).run()
    at.selectbox[0].select("ಕನ್ನಡ").run()
    assert not at.exception and at.title[0].value == "ಭತ್ತದ ಎಲೆ ರೋಗ ಪತ್ತೆ"
    at.selectbox[0].select("हिन्दी").run()
    assert not at.exception and at.title[0].value == "धान पत्ती रोग पहचान"


def test_successful_result_is_rendered_with_history():
    # Fake backend response in the documented 200 schema (test data, not a real prediction).
    fake = {
        "label": "Blast",
        "confidence": 0.9,
        "rejected": False,
        "top3": [{"label": "Blast", "confidence": 0.9}, {"label": "Brown Spot", "confidence": 0.07}],
        "severity": {"level": "Mild", "percent": 4.2},
    }
    at = AppTest.from_file(APP, default_timeout=30)
    at.session_state["last"] = {"kind": "ok", "result": fake}
    at.session_state["history"] = [
        {"date": "2000-01-01 00:00", "disease": "Blast", "confidence": "90.0%", "severity": "Mild"}
    ]
    at.run()
    assert not at.exception
    assert at.subheader[0].value == "Blast"
    assert any("2000-01-01 00:00" in m.value for m in at.markdown)  # history row rendered


def test_model_not_ready_message():
    at = AppTest.from_file(APP, default_timeout=30)
    at.session_state["last"] = {"kind": "model_not_ready", "reason": "Missing in models/: x"}
    at.run()
    assert not at.exception
    assert any("not been trained" in i.value for i in at.info)


# ---- Stage 2 behaviour -----------------------------------------------------------------------
def _png_b64():
    import base64
    import io

    from PIL import Image

    buf = io.BytesIO()
    Image.new("RGB", (8, 8), (200, 30, 30)).save(buf, "PNG")
    return base64.b64encode(buf.getvalue()).decode()


def _ok_result(**over):
    r = {
        "label": "Blast", "confidence": 0.91, "rejected": False, "reject_reasons": [],
        "top3": [{"label": "Blast", "confidence": 0.91}, {"label": "Brown Spot", "confidence": 0.06}],
        "heatmap_png_b64": _png_b64(),
        "severity": {"leaf_found": True, "percent": 12.3, "level": "Moderate", "overlay_png_b64": _png_b64()},
        "quality": {"ok": True, "issues": []},
    }
    r.update(over)
    return {"kind": "ok", "result": r}


def test_quality_warnings_shown_even_without_model():
    at = AppTest.from_file(APP, default_timeout=30)
    at.session_state["last"] = {"kind": "model_not_ready", "reason": "x", "quality": {"ok": False, "issues": ["blurry", "too_dark"]}}
    at.run()
    texts = [w.value for w in at.warning]
    assert any("blurry" in t for t in texts) and any("too dark" in t for t in texts)


def test_full_result_renders_heatmap_severity_and_explanation():
    at = AppTest.from_file(APP, default_timeout=30)
    at.session_state["last"] = _ok_result()
    at.run()
    assert not at.exception
    assert at.subheader[0].value == "Blast"
    assert len(at.get("imgs")) == 2                                    # heatmap + severity overlay
    assert any("strongest signs of Blast" in c.value for c in at.caption)
    assert any(m.value == "12.3%" for m in at.metric)
    assert any("EXPERIMENTAL" in c.value for c in at.caption)         # severity limits are always shown


def test_rejected_result_shows_unable_to_diagnose():
    at = AppTest.from_file(APP, default_timeout=30)
    at.session_state["last"] = _ok_result(label=None, rejected=True, reject_reasons=["low_confidence"], heatmap_png_b64=None, severity=None)
    at.run()
    assert not at.exception
    assert any("Unable to diagnose reliably" in w.value for w in at.warning)
    assert any("not confident enough" in c.value for c in at.caption)
    texts = " ".join(m.value for m in at.markdown)
    assert "Closest possibilities (NOT reliable)" in texts and "Top 3 possibilities" not in texts
    captions = " ".join(c.value for c in at.caption)
    assert "No heatmap: the app was not confident enough" in captions            # says WHY, not just "none"
    assert "Severity is not calculated, because this photo could not be diagnosed reliably" in captions
    assert "Not available yet" not in captions                                    # the old, misleading wording


def test_history_marks_refused_photos_as_not_diagnosed():
    at = AppTest.from_file(APP, default_timeout=30)
    at.session_state["history"] = [{"date": "2000-01-01 00:00", "disease": "—", "confidence": "36.6%", "severity": "—"}]
    at.run()
    assert any("Not diagnosed" in m.value for m in at.markdown)


def test_healthy_leaf_has_no_severity_number():
    at = AppTest.from_file(APP, default_timeout=30)
    at.session_state["last"] = _ok_result(label="Healthy", severity=None)
    at.run()
    assert not at.exception
    assert any("healthy leaf" in c.value for c in at.caption)


def test_kannada_result_uses_translated_severity_level():
    at = AppTest.from_file(APP, default_timeout=30)
    at.session_state["last"] = _ok_result()
    at.run()
    at.selectbox[0].select("ಕನ್ನಡ").run()
    assert not at.exception
    assert any(m.label == "ಮಧ್ಯಮ" for m in at.metric)


# ---- Stage 3 behaviour -----------------------------------------------------------------------
def _with_image(res):
    import io

    from PIL import Image

    buf = io.BytesIO()
    Image.new("RGB", (200, 150), (60, 140, 50)).save(buf, "JPEG")
    return {**res, "id": "t1", "image_bytes": buf.getvalue(), "filename": "leaf.jpg"}


def test_advice_section_shows_knowledge_base_in_english():
    at = AppTest.from_file(APP, default_timeout=30)
    at.session_state["last"] = _with_image(_ok_result())
    at.run()
    assert not at.exception
    text = " ".join(m.value for m in at.markdown)
    for must in ("Symptoms", "Causes and favouring conditions", "Cultural practices", "Doses are NOT given", "Growth recommendations",
                 "Nutrient management", "knowledgebank.irri.org", "Contact your local agriculture officer"):
        assert must in text, must
    assert any("decision-support tool" in w.value for w in at.warning)


def test_advice_is_translated_and_flagged_unreviewed():
    at = AppTest.from_file(APP, default_timeout=30)
    at.session_state["last"] = _with_image(_ok_result())
    at.run()
    at.selectbox[0].select("हिन्दी").run()
    assert not at.exception
    text = " ".join(m.value for m in at.markdown)
    assert "लक्षण" in text and "कृषि पद्धतियाँ" in text
    assert at.subheader[0].value.startswith("ब्लास्ट")                       # localised disease name
    assert any("AI मॉडल" in c.value for c in at.caption)                      # unreviewed-translation notice


def test_no_advice_for_a_rejected_result():
    at = AppTest.from_file(APP, default_timeout=30)
    at.session_state["last"] = _with_image(_ok_result(label=None, rejected=True, reject_reasons=["low_confidence"], heatmap_png_b64=None, severity=None))
    at.run()
    assert not at.exception
    assert not any("Cultural practices" in m.value for m in at.markdown)


def test_pdf_button_creates_a_download():
    at = AppTest.from_file(APP, default_timeout=60)
    at.session_state["last"] = _with_image(_ok_result())
    at.run()
    assert not at.exception and not at.get("download_button")
    create = [b for b in at.button if b.label == "Create PDF report"]
    assert len(create) == 1
    create[0].click().run()
    assert not at.exception
    dl = at.get("download_button")
    assert len(dl) == 1
    assert at.session_state["pdf"]["bytes"][:5] == b"%PDF-" and at.session_state["pdf"]["lang"] == "en"


def test_pdf_is_rebuilt_when_language_changes():
    at = AppTest.from_file(APP, default_timeout=60)
    at.session_state["last"] = _with_image(_ok_result())
    at.run()
    [b for b in at.button if b.label == "Create PDF report"][0].click().run()
    assert len(at.get("download_button")) == 1
    at.selectbox[0].select("ಕನ್ನಡ").run()
    assert not at.get("download_button")                                       # the English PDF is not offered in Kannada
    assert any(b.label == "PDF ವರದಿ ರಚಿಸಿ" for b in at.button)


def test_history_is_translated_when_language_changes():
    at = AppTest.from_file(APP, default_timeout=30)
    at.session_state["history"] = [{"date": "2000-01-01 00:00", "disease": "Tungro", "confidence": "90.0%", "severity": "—"}]
    at.run()
    at.selectbox[0].select("ಕನ್ನಡ").run()
    assert any("ಟುಂಗ್ರೋ" in m.value for m in at.markdown)


# ---- session features: summary, CSV, previous scan, read-aloud -------------------------------------
HIST = [
    {"id": "a", "date": "2026-10-10 10:00", "disease": "Blast", "confidence": "91.2%", "severity": "Mild"},
    {"id": "b", "date": "2026-10-10 10:05", "disease": "—", "confidence": "36.6%", "severity": "—"},
    {"id": "t1", "date": "2026-10-10 10:09", "disease": "Blast", "confidence": "88.0%", "severity": "Moderate"},
]


def test_summary_and_csv_button_appear_with_history():
    at = AppTest.from_file(APP, default_timeout=30)
    at.session_state["history"] = HIST
    at.run()
    assert not at.exception
    assert any("Photos: 3 · Diagnosed: 2 · Not diagnosed: 1" in c.value and "Most common: Blast (2)" in c.value for c in at.caption)
    assert len(at.get("download_button")) == 1                                  # the CSV export


def test_summary_is_translated():
    at = AppTest.from_file(APP, default_timeout=30)
    at.session_state["history"] = HIST
    at.run()
    at.selectbox[0].select("हिन्दी").run()
    assert any("फोटो: 3" in c.value and "निदान हुआ: 2" in c.value for c in at.caption)


def test_history_severity_follows_the_language():
    at = AppTest.from_file(APP, default_timeout=30)
    at.session_state["history"] = HIST
    at.run()
    at.selectbox[0].select("ಕನ್ನಡ").run()
    text = " ".join(m.value for m in at.markdown)
    assert "ಸೌಮ್ಯ" in text and "ಮಧ್ಯಮ" in text                                  # Mild and Moderate in Kannada


def test_previous_scan_is_shown_for_the_current_result():
    at = AppTest.from_file(APP, default_timeout=30)
    at.session_state["history"] = HIST
    at.session_state["last"] = _with_image(_ok_result())                        # id "t1" matches the newest history row
    at.run()
    assert not at.exception
    assert any("Previous scan in this session (2026-10-10 10:05): Not diagnosed" in c.value and "This scan: Blast, Moderate" in c.value
               for c in at.caption)


def test_no_previous_scan_for_the_first_photo():
    at = AppTest.from_file(APP, default_timeout=30)
    at.session_state["history"] = [HIST[2]]
    at.session_state["last"] = _with_image(_ok_result())
    at.run()
    assert not any("Previous scan" in c.value for c in at.caption)


def test_read_aloud_widget_is_in_the_advice_section():
    at = AppTest.from_file(APP, default_timeout=30)
    at.session_state["last"] = _with_image(_ok_result())
    at.run()
    assert not at.exception
    assert len(at.get("iframe")) == 1                                            # the components.html read-aloud button
