"""Report generation from stored results (no inference, no fabrication).

Templates rendered here: benchmark_summary, per_model_report, failure_report,
performance_report, quality_ranking, smoke_test_report. Every field is either
computed from stored page results or explicitly NOT_RUN/null. Dry-run results
(Namespace dry_runs/) are never mixed into real reports.
"""

from __future__ import annotations

import json
from pathlib import Path

from benchmark.constants import DRY_RUNS_DIR, OUTPUTS_DIR
from benchmark.metrics.aggregate import aggregate_run

NOT_RUN = "NOT_RUN"


def load_run_results(run_dir: Path, include_dry: bool = False) -> list[dict]:
    results = []
    for f in sorted(run_dir.glob("*.json")):
        if f.name == "run_state.json":
            continue
        rec = json.loads(f.read_text())
        if rec.get("is_dry_run") and not include_dry:
            continue  # defensive: dry-run records never enter real reports
        results.append(rec)
    return results


def per_model_report(run_dir: Path, model_id: str, include_dry: bool = False) -> dict:
    results = load_run_results(run_dir, include_dry=include_dry)
    if not results:
        return {"model_id": model_id, "run_state": NOT_RUN}
    agg = aggregate_run(results)
    return {"model_id": model_id, "run_id": results[0]["run_id"], "run_state": "COMPLETE", **agg}


def quality_ranking(per_model: list[dict], key: str = "mean_cer_normalized") -> list[dict]:
    """Rank models by ascending error (lower is better); models without the
    metric (not run / all failures) sort last with rank=null."""
    scored = [m for m in per_model if isinstance(m.get(key), (int, float))]
    scored.sort(key=lambda m: m[key])
    out = []
    for i, m in enumerate(scored, start=1):
        out.append({"rank": i, "model_id": m["model_id"], key: m[key]})
    for m in per_model:
        if m not in scored:
            out.append({"rank": None, "model_id": m["model_id"], key: None})
    return out


def failure_report(run_dir: Path, include_dry: bool = False) -> dict:
    results = load_run_results(run_dir, include_dry=include_dry)
    failures = [r for r in results if r["status"] != "PASS"]
    return {
        "total_failures": len(failures),
        "by_status": {
            s: [r["page_id"] for r in failures if r["status"] == s]
            for s in ("FAIL", "OOM", "TIMEOUT", "MODEL_LOAD_ERROR", "INVALID_OUTPUT")
        },
        "details": [
            {
                "page_id": r["page_id"],
                "status": r["status"],
                "exception_type": r.get("exception_type"),
                "exception_message": (r.get("exception_message") or "")[:300],
                "retry_count": r.get("retry_count"),
            }
            for r in failures
        ],
    }


def performance_report(run_dir: Path, gpu_model: str | None) -> dict:
    """Speed/VRAM numbers are ONLY comparable within the same GPU model; the
    report records gpu_model so cross-hardware ranking is never implied."""
    per_model = per_model_report(run_dir, "")
    return {
        "gpu_model": gpu_model,
        "comparability_note": (
            "Speed metrics are valid only within runs on the same GPU model."
            if gpu_model else "gpu_model not recorded; performance not comparable."
        ),
        "mean_sec_per_page": per_model.get("mean_sec_per_page"),
        "median_sec_per_page": per_model.get("median_sec_per_page"),
        "p95_sec_per_page": per_model.get("p95_sec_per_page"),
        "peak_vram_mb": per_model.get("peak_vram_mb"),
    }


def benchmark_summary(model_run_dirs: dict[str, Path]) -> dict:
    per_model = [
        per_model_report(d, mid) for mid, d in sorted(model_run_dirs.items())
    ]
    return {
        "report_version": 1,
        "models": per_model,
        "quality_ranking_normalized_cer": quality_ranking(per_model),
        "dry_runs_excluded": True,
    }


def smoke_test_report(smoke_run_dir: Path, smoke_page_ids: list[str]) -> dict:
    results = load_run_results(smoke_run_dir)
    by_page = {r["page_id"]: r["status"] for r in results}
    return {
        "smoke_page_ids": smoke_page_ids,
        "pages": [
            {"page_id": pid, "status": by_page.get(pid, NOT_RUN)}
            for pid in smoke_page_ids
        ],
        "all_pass": all(by_page.get(pid) == "PASS" for pid in smoke_page_ids)
        if results else False,
    }
