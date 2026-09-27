import unicodedata

from benchmark.text_normalization import (
    normalize_text,
    policy_metadata,
    strip_think_blocks,
)


def test_nfc_composition():
    raw = "\u0623\u064e\u0644\u0650\u0641"  # decomposed diacritics
    assert normalize_text(raw) == unicodedata.normalize("NFC", raw)


def test_zero_width_and_bidi_removed():
    text = "عربي\u200b\u200fيوم"
    assert normalize_text(text) == "عربييوم"


def test_presentation_forms_folded():
    # lam-alef presentation form ligature -> base letters
    lig = "\uFEFB"  # ARABIC LIGATURE LAM WITH ALEF ISOLATED FORM
    assert normalize_text(lig) == "لا"
    # contextual heh form FEE9 -> heh
    assert normalize_text("\uFEE9") == "ه"


def test_arabic_decimal_separator_between_digits():
    assert normalize_text("١٢\u066b٥") == "١٢.٥"
    # not between digits: untouched
    assert normalize_text("نهاية\u066b") == "نهاية\u066b"


def test_whitespace_collapsed_but_newlines_kept():
    text = "سطر  أول\tثاني\n\n\n\nسطر  ثالث"
    out = normalize_text(text)
    assert "سطر أول ثاني" in out
    assert "\n\n" in out
    assert "\n\n\n" not in out


def test_content_differences_NOT_hidden():
    # hamza variants are NOT folded (would hide real OCR errors)
    assert normalize_text("علي") != normalize_text("على")
    assert normalize_text("أحتاج") != normalize_text("احتاج")
    # Arabic-Indic vs ASCII digits NOT folded
    assert normalize_text("١٤٤٧") != normalize_text("1447")
    # taa marbuta NOT folded
    assert normalize_text("مدرسة") != normalize_text("مدرسه")


def test_deterministic_and_idempotent():
    text = "نص\u200b تجريبي  مع\u066b أرقام"
    once = normalize_text(text)
    assert normalize_text(once) == once


def test_strip_think_blocks():
    assert strip_think_blocks("<think>reasoning</think>النتيجة") == "النتيجة"
    # keeps only text after the LAST closing tag
    assert strip_think_blocks("<think>a</think>mid<think>b</think>final") == "final"
    # open think without close = budget exhausted -> empty
    assert strip_think_blocks("<think>never finished") == ""
    assert strip_think_blocks("plain") == "plain"


def test_policy_metadata_present():
    meta = policy_metadata()
    assert meta["version"]
    assert meta["applied_identically_to"] == ["prediction", "ground_truth"]
