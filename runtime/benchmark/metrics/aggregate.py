"""Aggregate metrics computed from STORED per-page results (no re-inference).

Quality metrics (CER/WER, raw + normalized) and run statistics (failure rate,
success count, sec/page mean/median/P95, peak VRAM) are reproducible from
outputs/ alone. Timing/VRAM are null until the GPU phase; the aggregator
reports them only when present and never fabricates values.
"""

from __future__ import annotations

import math
from pathlib import Path

from benchmark.metrics.cer_wer import cer, wer
from benchmark.text_normalization import normalize_text

SUCCESS_STATUS = "PASS"
FAILURE_STATUSES = {"FAIL", "OOM", "TIMEOUT", "MODEL_LOAD_ERROR", "INVALID_OUTPUT"}


def _percentile(sorted_values: list[float], p: float) -> float | None:
    if not sorted_values:
        return None
    if len(sorted_values) == 1:
        return sorted_values[0]
    k = (len(sorted_values) - 1) * p
    f, c = math.floor(k), math.ceil(k)
    if f == c:
        return sorted_values[int(k)]
    return sorted_values[f] * (c - k) + sorted_values[c] * (k - f)


def score_page(reference: str, hypothesis: str) -> dict:
    """Per-page quality scores on both tracks."""
    return {
        "cer_raw": cer(reference, hypothesis),
        "wer_raw": wer(reference, hypothesis),
        "cer_normalized": cer(normalize_text(reference), normalize_text(hypothesis)),
        "wer_normalized": wer(normalize_text(reference), normalize_text(hypothesis)),
    }


def aggregate_run(page_results: list[dict]) -> dict:
    """Aggregate one model-run's stored page results."""
    total = len(page_results)
    if total == 0:
        return {"total_pages": 0}

    successes = [r for r in page_results if r.get("status") == SUCCESS_STATUS]
    failures = [r for r in page_results if r.get("status") in FAILURE_STATUSES]

    durations = sorted(
        r["elapsed_seconds"] for r in successes
        if isinstance(r.get("elapsed_seconds"), (int, float))
    )
    vrams = [
        r["peak_vram_mb"] for r in successes
        if isinstance(r.get("peak_vram_mb"), (int, float))
    ]

    agg: dict = {
        "total_pages": total,
        "successful_pages": len(successes),
        "failed_pages": len(failures),
        "failure_rate": len(failures) / total,
        "failure_breakdown": {
            s: sum(1 for r in failures if r.get("status") == s)
            for s in sorted(FAILURE_STATUSES)
        },
    }

    if durations:
        agg["mean_sec_per_page"] = sum(durations) / len(durations)
        agg["median_sec_per_page"] = _percentile(durations, 0.5)
        agg["p95_sec_per_page"] = _percentile(durations, 0.95)
    else:
        agg["mean_sec_per_page"] = None
        agg["median_sec_per_page"] = None
        agg["p95_sec_per_page"] = None

    if vrams:
        agg["peak_vram_mb"] = max(vrams)
    else:
        agg["peak_vram_mb"] = None  # not fabricated until GPU phase

    if successes:
        keys = ["cer_raw", "wer_raw", "cer_normalized", "wer_normalized"]
        for k in keys:
            vals = [r["metrics"][k] for r in successes if r.get("metrics") and k in r["metrics"]]
            if vals:
                agg[f"mean_{k}"] = sum(vals) / len(vals)
            else:
                agg[f"mean_{k}"] = None

    return agg
