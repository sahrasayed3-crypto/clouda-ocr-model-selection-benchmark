"""CER and WER metrics (deterministic, dependency-free).

CER/WER = Levenshtein distance / reference length, both computed on the
NORMALIZED track unless the caller passes raw strings deliberately.
Distance uses the classic dynamic-programming algorithm with two rows.
Special cases (documented):
- empty reference and empty hypothesis -> 0.0
- empty reference, non-empty hypothesis -> 1.0
- empty hypothesis, non-empty reference -> 1.0 (with note)
Both directions are errors; the convention above avoids division by zero
while never rewarding empty output.
"""

from __future__ import annotations


def levenshtein(a: list[str] | str, b: list[str] | str) -> int:
    if a == b:
        return 0
    if not a:
        return len(b)
    if not b:
        return len(a)
    prev = list(range(len(b) + 1))
    for i, ca in enumerate(a, start=1):
        cur = [i] + [0] * len(b)
        for j, cb in enumerate(b, start=1):
            cost = 0 if ca == cb else 1
            cur[j] = min(prev[j] + 1, cur[j - 1] + 1, prev[j - 1] + cost)
        prev = cur
    return prev[-1]


def cer(reference: str, hypothesis: str) -> float:
    ref, hyp = list(reference), list(hypothesis)
    if not ref and not hyp:
        return 0.0
    if not ref or not hyp:
        return 1.0
    return levenshtein(ref, hyp) / len(ref)


def wer(reference: str, hypothesis: str) -> float:
    ref, hyp = reference.split(), hypothesis.split()
    if not ref and not hyp:
        return 0.0
    if not ref or not hyp:
        return 1.0
    return levenshtein(ref, hyp) / len(ref)
