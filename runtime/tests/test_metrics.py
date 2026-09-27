import math

from benchmark.metrics.cer_wer import cer, levenshtein, wer


def test_levenshtein_basic():
    assert levenshtein("", "") == 0
    assert levenshtein("abc", "abc") == 0
    assert levenshtein("abc", "abd") == 1
    assert levenshtein("kitten", "sitting") == 3
    assert levenshtein("", "abc") == 3


def test_cer_perfect_and_empty():
    assert cer("", "") == 0.0
    assert cer("نص عربي", "نص عربي") == 0.0
    assert cer("hello", "") == 1.0  # empty hypothesis is a full error, never rewarded
    assert cer("", "hello") == 1.0


def test_cer_arabic_substitution():
    # one wrong letter out of six (extra alef in hypothesis)
    assert cer("الكتاب", "الكتااب") == 1 / 6


def test_cer_arabic_digit_confusion_counts():
    ref = "سنة ١٤٤٧"
    hyp = "سنة ١٤٤٨"
    assert cer(ref, hyp) == 1 / 8


def test_wer_basic():
    assert wer("السلام عليكم ورحمة الله", "السلام عليكم ورحمة الله") == 0.0
    assert wer("السلام عليكم", "السلام عليكم ورحمة") == 1 / 2
    assert wer("the cat sat", "the bat sat") == 1 / 3


def test_metrics_symmetric_normalization_track_distinct():
    ref = "مرحبا  بالعالم"
    hyp = "مرحبا بالعالم"
    # raw track penalizes the extra space; normalized track does not
    assert cer(ref, hyp) > 0.0
    from benchmark.text_normalization import normalize_text

    assert cer(normalize_text(ref), normalize_text(hyp)) == 0.0


def test_percentile_helper():
    from benchmark.metrics.aggregate import _percentile

    vals = [1.0, 2.0, 3.0, 4.0]
    assert _percentile(vals, 0.5) == 2.5
    assert _percentile(vals, 0.0) == 1.0
    assert _percentile(vals, 1.0) == 4.0
    assert _percentile([5.0], 0.95) == 5.0
    assert _percentile([], 0.5) is None
