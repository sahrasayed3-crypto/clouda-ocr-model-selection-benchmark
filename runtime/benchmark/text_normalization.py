"""Deterministic, versioned OCR text normalization (Arabic-aware).

Policy (NORMALIZATION_POLICY_VERSION = 1.0.0):
- Operates on BOTH sides of a comparison identically (prediction and ground truth).
- Never mutates stored raw output; normalization produces a separate track.
- Deterministic, locale-free (no locale-dependent casing/table), pure functions.
- Conservative: only normalizes differences that are demonstrably NOT the OCR
  model's fault (Unicode presentation forms, bidi marks, invisible controls);
  it does NOT touch genuine content differences (letters, digits, punctuation
  of content, markdown structure symbols).

Steps applied in order:
 N1  NFC unicode normalization (canonical composition)
 N2  remove zero-width and bidi control characters (U+200B..U+200F, U+202A..U+202E,
     U+2066..U+2069, U+FEFF) -- layout artifacts, not content
 N3  map Arabic Presentation Forms (FB50..FDFF, FE70..FEFF) to base Arabic block
     via NFC/NFKC on those ranges only (NFKC is applied to presentation forms,
     which is exactly what they exist for: contextual glyph variants)
 N4  normalize whitespace runs to a single space, strip leading/trailing space
 N5  unify newlines to \n, collapse 3+ newlines to 2 (paragraph break)
 N6  unify Arabic decimal separators U+066B/ARABIC DECIMAL SEPARATOR and
     U+066C (thousands) to ASCII '.' and ',' ONLY when between digits --
     same visual content, different codepoint (kept conservative)

Explicitly NOT normalized (documented decisions, to avoid hiding OCR errors):
- letter case (Arabic has none; Latin case errors are real OCR errors)
- hamza variants (ء/أ/إ/آ), taa marbuta vs haa, yaa vs alif maqsura
  (alef/yaa normalization IS common in Arabic NLP but is exactly the kind of
  substitution that can hide genuine recognition errors; left intact here)
- punctuation (Arabic comma vs Latin comma are distinct tokens)
- digits: Arabic-Indic vs Eastern Arabic-Indic vs ASCII digits are NOT folded
  (misreading ٥ as 5 is a genuine OCR question; folding would hide it)
- markdown structure characters (#, *, |, -) -- structure is scored
"""

from __future__ import annotations

import re
import unicodedata

from benchmark.constants import NORMALIZATION_POLICY_VERSION

ZERO_WIDTH_BIDI = re.compile(
    "[\u200b\u200c\u200d\u200e\u200f\u202a\u202b\u202c\u202d\u202e"
    "\u2066\u2067\u2068\u2069\ufeff]"
)
WHITESPACE_RUN = re.compile(r"[ \t\f\v\r]+")
NEWLINE_RUN = re.compile(r"\n{3,}")
# Arabic decimal/thousands separators between digits.
ARABIC_DECIMAL = re.compile(r"(?<=\d)\u066b(?=\d)")
ARABIC_THOUSANDS = re.compile(r"(?<=\d)\u066c(?=\d)")


def _fold_presentation_forms(text: str) -> str:
    """NFKC-map Arabic presentation forms to their canonical base codepoints.

    Applied per-character so that the rest of the text is untouched by NFKC
    (full-text NFKC would also fold things like ligature fi and superscripts,
    which can hide genuine OCR differences).
    """
    out: list[str] = []
    for ch in text:
        cp = ord(ch)
        if 0xFB50 <= cp <= 0xFDFF or 0xFE70 <= cp <= 0xFEFF:
            out.append(unicodedata.normalize("NFKC", ch))
        else:
            out.append(ch)
    return "".join(out)


def normalize_text(text: str) -> str:
    """Apply normalization policy v1.0.0. Deterministic, pure."""
    if text is None:
        return ""
    s = unicodedata.normalize("NFC", text)
    s = ZERO_WIDTH_BIDI.sub("", s)
    s = _fold_presentation_forms(s)
    s = ARABIC_DECIMAL.sub(".", s)
    s = ARABIC_THOUSANDS.sub(",", s)
    s = s.replace("\r\n", "\n").replace("\r", "\n")
    s = WHITESPACE_RUN.sub(" ", s)
    s = NEWLINE_RUN.sub("\n\n", s)
    s = s.strip()
    return s


def strip_think_blocks(text: str) -> str:
    """Model-output-only helper: keep only text after the LAST </think>.

    Applies the amad-vlm5/vlm6 documented handling. If a <think> opens but
    never closes, returns "" (budget exhausted - a recorded failure mode).
    """
    if "</think>" in text:
        return text.rsplit("</think>", 1)[1].strip()
    if "<think>" in text:
        return ""
    return text.strip()


NORMALIZATION_STEPS = ["NFC", "strip-zero-width-bidi", "fold-arabic-presentation-forms",
                       "arabic-decimal-separators", "newline-unify", "whitespace-collapse",
                       "strip"]


def policy_metadata() -> dict:
    return {
        "version": NORMALIZATION_POLICY_VERSION,
        "steps": NORMALIZATION_STEPS,
        "not_normalized": [
            "letter case (Latin)",
            "hamza variants",
            "taa marbuta / yaa forms",
            "Arabic-Indic vs ASCII digits",
            "punctuation identity",
            "markdown structure characters",
        ],
        "applied_identically_to": ["prediction", "ground_truth"],
    }
