"""Session history helpers (CSV export, summary, previous scan) and the read-aloud widget HTML."""
import csv
import io
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "frontend"))
import session_tools as S  # noqa: E402
import speech  # noqa: E402

H = [
    {"id": "a", "date": "2026-10-10 10:00", "disease": "Blast", "confidence": "91.2%", "severity": "Mild"},
    {"id": "b", "date": "2026-10-10 10:05", "disease": "—", "confidence": "36.6%", "severity": "—"},
    {"id": "c", "date": "2026-10-10 10:09", "disease": "Blast", "confidence": "88.0%", "severity": "Moderate"},
    {"id": "d", "date": "2026-10-10 10:12", "disease": "Tungro", "confidence": "95.5%", "severity": "—"},
]


def test_csv_export_is_excel_friendly_and_correct():
    raw = S.history_csv(H, {"Blast": "ಬ್ಲಾಸ್ಟ್ ರೋಗ (Blast)", "Tungro": "टुंग्रो रोग (Tungro)"})
    assert raw.startswith(b"\xef\xbb\xbf")                                   # BOM so Excel reads UTF-8 (Kannada, Hindi)
    rows = list(csv.reader(io.StringIO(raw.decode("utf-8-sig"))))
    assert rows[0] == ["date", "diagnosed", "disease", "disease_local_name", "confidence_percent", "severity_estimate_experimental"]
    assert rows[1] == ["2026-10-10 10:00", "yes", "Blast", "ಬ್ಲಾಸ್ಟ್ ರೋಗ (Blast)", "91.2", "Mild"]
    assert rows[2] == ["2026-10-10 10:05", "no", "", "", "36.6", ""]            # refused photo: no disease, no severity
    assert rows[4][5] == ""                                                      # "—" severity is written empty
    assert len(rows) == 5


def test_csv_export_of_an_empty_history_is_just_the_header():
    assert len(list(csv.reader(io.StringIO(S.history_csv([]).decode("utf-8-sig"))))) == 1


def test_summary():
    s = S.summarize(H)
    assert (s["total"], s["diagnosed"], s["refused"]) == (4, 3, 1)
    assert s["most_common"] == ("Blast", 2) and s["by_disease"] == {"Blast": 2, "Tungro": 1}
    assert S.summarize([])["most_common"] is None


def test_previous_scan():
    assert S.previous_scan(H, "c")["id"] == "b"
    assert S.previous_scan(H, "a") is None                                       # nothing before the first scan
    assert S.previous_scan(H, None)["id"] == "c"                                 # unknown id: relative to the newest
    assert S.previous_scan([], "x") is None


# ---- read-aloud widget ---------------------------------------------------------------------------
def extract_lines(html: str):
    m = re.search(r"const LINES = (\".*\");", html)
    return json.loads(json.loads(m.group(1)))                                   # a JS string holding JSON


def test_speech_html_roundtrips_text_in_every_language():
    for lang, text in (("en", "Blast. Split nitrogen."), ("kn", "ಬ್ಲಾಸ್ಟ್ ರೋಗ"), ("hi", "ब्लास्ट रोग")):
        html = speech.speech_html([text, "second line"], lang, "Read aloud", "note")
        assert extract_lines(html) == [text, "second line"]
        assert speech.LANG_CODES[lang] in html


def test_speech_html_cannot_be_broken_out_of():
    nasty = ['</script><script>alert(1)</script>', 'quote " and \' and \\ and \n newline', "line separator", "<img src=x onerror=alert(1)>"]
    html = speech.speech_html(nasty, "en", "<b>x</b>", "<i>y</i>")
    assert extract_lines(html) == nasty                                          # content survives exactly
    assert html.count("</script>") == 1 and "<script>alert" not in html           # only our own closing tag
    assert "<b>x</b>" not in html and "<i>y</i>" not in html                      # label and note are escaped


def test_unknown_language_falls_back_to_english_voice():
    assert "en-IN" in speech.speech_html(["x"], "zz", "Read", "n")
