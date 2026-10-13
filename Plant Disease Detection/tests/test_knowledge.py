import re

import pytest

from backend import config, disease_info as di

LIST_KEYS = di.SECTION_KEYS_LISTS
MUST_HAVE_CONTENT = ("symptoms", "causes", "cultural", "prevention", "monitoring")  # for every non-healthy label


def test_every_model_class_has_an_entry():
    assert set(config.CLASS_NAMES) == set(di.INFO)


@pytest.mark.parametrize("label", list(di.INFO))
def test_all_languages_and_fields_present(label):
    for lang in di.LANGS:
        d = di.INFO[label][lang]
        assert d["name"].strip() and d["description"].strip()
        for key in LIST_KEYS:
            assert isinstance(d[key], list) and all(isinstance(x, str) and x.strip() for x in d[key]), (label, lang, key)


@pytest.mark.parametrize("label", [l for l in di.INFO if l != "Healthy"])
def test_diseases_have_real_content_in_every_language(label):
    for lang in di.LANGS:
        for key in MUST_HAVE_CONTENT:
            assert di.INFO[label][lang][key], (label, lang, key)


@pytest.mark.parametrize("label", list(di.INFO))
def test_translations_are_parallel_to_english(label):
    """Same number of bullets per section in every language, so nothing was silently left out."""
    for lang in ("kn", "hi"):
        for key in LIST_KEYS:
            assert len(di.INFO[label][lang][key]) == len(di.INFO[label]["en"][key]), (label, lang, key)


def test_translations_actually_use_the_right_script():
    kannada, devanagari = re.compile("[ಀ-೿]"), re.compile("[ऀ-ॿ]")
    for label in di.INFO:
        assert kannada.search(di.INFO[label]["kn"]["description"]) and not devanagari.search(di.INFO[label]["kn"]["description"])
        assert devanagari.search(di.INFO[label]["hi"]["description"]) and not kannada.search(di.INFO[label]["hi"]["description"])


DOSE = re.compile(r"\b\d+(\.\d+)?\s?(g|kg|ml|l|litre|liter|lit|gm|%)\s?(/|per)\s?(ha|acre|l|litre|liter|lit|kg|hill)", re.I)
DOSE_HI_KN = re.compile(r"\d+\s?(ग्राम|किग्रा|मिली|लीटर|ಗ್ರಾಂ|ಕೆ\.?ಜಿ|ಮಿ\.?ಲೀ|ಲೀಟರ್)")


def test_no_pesticide_doses_anywhere():
    """The brief forbids invented doses. Percentages of humidity and temperatures are fine; per-area or per-litre doses are not."""
    for label in di.INFO:
        for lang in di.LANGS:
            d = di.INFO[label][lang]
            text = " ".join([d["description"]] + [x for k in LIST_KEYS for x in d[k]])
            assert not DOSE.search(text), (label, lang, DOSE.search(text).group(0))
            assert not DOSE_HI_KN.search(text), (label, lang, DOSE_HI_KN.search(text).group(0))


@pytest.mark.parametrize("label", [l for l in di.INFO if l != "Healthy"])
@pytest.mark.parametrize("lang", di.LANGS)
def test_chemical_advice_always_ends_with_the_label_and_officer_note(label, lang):
    chem = di.get_info(label, lang)["management"]["chemical"]
    assert chem[-1] == di.CHEMICAL_NOTE[lang]


@pytest.mark.parametrize("lang", di.LANGS)
def test_get_info_combines_everything(lang):
    info = di.get_info("Blast", lang, "Moderate")
    assert info["name"] and info["disclaimer"] == di.DISCLAIMER[lang]
    assert info["severity_advice"] == di.SEVERITY[lang]["Moderate"]
    assert set(info["growth"]) == {"nutrient", "water", "spacing", "monitoring"}
    assert len(info["growth"]["nutrient"]) == len(di.INFO["Blast"][lang]["nutrient"]) + len(di.COMMON[lang]["nutrient"])
    assert info["sources"] and all(s["url"].startswith("http") for s in info["sources"])


def test_severity_rules():
    assert di.get_info("Healthy", "en", "Severe")["severity_advice"] == di.SEVERITY["en"]["None"]  # healthy ignores severity
    assert di.get_info("Blast", "en", None)["severity_advice"] == []
    assert di.get_info("Blast", "en", "Mild")["severity_advice"] != di.get_info("Blast", "en", "Severe")["severity_advice"]


def test_unknown_label_and_language():
    assert di.get_info("Not a disease") is None
    assert di.get_info("Blast", "xx")["lang"] == "en"  # falls back to English


def test_only_english_is_marked_reviewed():
    assert di.get_info("Blast", "en")["translation_reviewed"] is True
    assert di.get_info("Blast", "kn")["translation_reviewed"] is False and di.get_info("Blast", "hi")["translation_reviewed"] is False


def test_leaf_smut_source_caveat_is_visible():
    assert "not IRRI or TNAU" in di.INFO["Leaf Smut"]["en"]["description"]
    assert all(s["org"] not in ("IRRI Rice Knowledge Bank", "TNAU Agritech Portal") for s in map(di.SOURCES.get, di.SOURCE_IDS["Leaf Smut"]))


def test_names_helper():
    assert di.names("hi")["Tungro"].startswith("टुंग्रो")
    assert set(di.names("en")) == set(di.INFO)
