"""The visual theme: CSS output, the photo background, the Streamlit config, and the dark-mode switch."""
import re
import sys
import tomllib
from pathlib import Path

import pytest
from streamlit.testing.v1 import AppTest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "frontend"))
import api_client  # noqa: E402
import theme  # noqa: E402

APP = str(ROOT / "frontend" / "app.py")


def test_css_is_complete_and_balanced():
    for dark in (False, True):
        c = theme.css(dark)
        assert c.startswith("\n<style>") and c.rstrip().endswith("</style>")
        assert not re.search(r"__[A-Za-z_]+__", c), "an unresolved placeholder is left in the CSS"
        assert c.count("{") == c.count("}")
        assert theme.BACKGROUND_URL in c and "backdrop-filter" in c


def test_dark_variant_really_differs():
    light, dark = theme.css(False), theme.css(True)
    assert light != dark
    assert "--text: #1b2a1f" in light and "--text: #edf5ee" in dark
    assert "--card: rgba(255,255,255,.88)" in light and "--card: rgba(17,27,20,.88)" in dark


def test_cards_are_only_the_real_bordered_containers():
    """The page root, the columns and the expander bodies use the same wrapper element; styling it bare once turned the
    whole page into one white card. The card selector must be restricted to direct children of the page's vertical block."""
    css = theme.css(False)
    assert theme.CARD in css
    # every use of the wrapper element is the restricted form (a bare wrapper selector would style the page root too)
    assert css.count("stVerticalBlockBorderWrapper") == css.count(theme.CARD) > 5
    assert theme.CARD.startswith('[data-testid="stVerticalBlock"] > ')


def test_photo_background_exists_and_is_served():
    img = ROOT / "frontend" / "static" / "background.jpg"
    assert img.exists() and 50_000 < img.stat().st_size < 3_000_000
    assert theme.BACKGROUND_URL == "/app/static/background.jpg"


def test_streamlit_config_is_where_streamlit_reads_it():
    """Streamlit reads .streamlit/config.toml from the folder it is launched in (the project root), not from frontend/."""
    cfg = tomllib.loads((ROOT / ".streamlit" / "config.toml").read_text(encoding="utf-8"))
    assert cfg["server"]["enableStaticServing"] is True and cfg["server"]["maxUploadSize"] == 10
    assert cfg["theme"]["base"] == "light" and not (ROOT / "frontend" / ".streamlit").exists()
    assert "Set-Location $root" in (ROOT / "run_dev.ps1").read_text(encoding="utf-8")


@pytest.fixture(autouse=True)
def backend_up(monkeypatch):
    monkeypatch.setattr(api_client, "health", lambda: {"status": "ok", "model_loaded": True})
    monkeypatch.setattr(api_client, "names", lambda lang: {})


def test_dark_mode_switch_changes_the_page():
    at = AppTest.from_file(APP, default_timeout=30).run()
    assert not at.exception and len(at.toggle) == 1
    css_light = " ".join(m.value for m in at.markdown if "<style>" in m.value)
    assert "--text: #1b2a1f" in css_light
    at.toggle[0].set_value(True).run()
    css_dark = " ".join(m.value for m in at.markdown if "<style>" in m.value)
    assert "--text: #edf5ee" in css_dark


def test_hero_shows_server_status_chip(monkeypatch):
    at = AppTest.from_file(APP, default_timeout=30).run()
    hero = " ".join(m.value for m in at.markdown if "hero-sub" in m.value)
    assert 'chip ok' in hero and "Server connected" in hero and "Calibrated AI" in hero
    monkeypatch.setattr(api_client, "health", lambda: None)
    at = AppTest.from_file(APP, default_timeout=30).run()
    hero = " ".join(m.value for m in at.markdown if "hero-sub" in m.value)
    assert "chip bad" in hero and "Cannot reach the server" in hero


def test_hero_text_is_html_escaped():
    at = AppTest.from_file(APP, default_timeout=30).run()
    hero = " ".join(m.value for m in at.markdown if "hero-sub" in m.value)
    assert "<script" not in hero


def test_hero_is_translated():
    at = AppTest.from_file(APP, default_timeout=30).run()
    at.selectbox[0].select("हिन्दी").run()
    hero = " ".join(m.value for m in at.markdown if "hero-sub" in m.value)
    assert "कैलिब्रेटेड AI" in hero and "सर्वर जुड़ा हुआ है" in hero
