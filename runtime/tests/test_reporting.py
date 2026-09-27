import json

from benchmark.reporting.reports import (
    benchmark_summary,
    failure_report,
    per_model_report,
    quality_ranking,
)


def store_run(run_dir, records):
    run_dir.mkdir(parents=True, exist_ok=True)
    for rec in records:
        (run_dir / f"{rec['page_id']}.json").write_text(json.dumps(rec))
    return run_dir


def make_rec(page_id, status, elapsed=None, vram=None, metrics=None, dry=False):
    return {
        "is_dry_run": dry,
        "run_id": "r1",
        "page_id": page_id,
        "status": status,
        "elapsed_seconds": elapsed,
        "peak_vram_mb": vram,
        "metrics": metrics,
    }


def test_report_states_not_run_for_missing_dir(tmp_path):
    rep = per_model_report(tmp_path / "does-not-exist", "m/x")
    assert rep["run_state"] == "NOT_RUN"


def test_aggregation_from_stored_results(tmp_path):
    m = {"cer_raw": 0.1, "wer_raw": 0.2, "cer_normalized": 0.05, "wer_normalized": 0.1}
    recs = [
        make_rec("P-001", "PASS", 2.0, 4096, m),
        make_rec("P-002", "PASS", 4.0, 8192, m),
        make_rec("P-003", "OOM"),
        make_rec("P-004", "TIMEOUT"),
    ]
    d = store_run(tmp_path / "raw" / "runA", recs)
    rep = per_model_report(d, "m/x")
    assert rep["successful_pages"] == 2
    assert rep["failed_pages"] == 2
    assert rep["failure_rate"] == 0.5
    assert rep["mean_sec_per_page"] == 3.0
    assert rep["median_sec_per_page"] == 3.0
    assert rep["peak_vram_mb"] == 8192
    assert rep["mean_cer_normalized"] == 0.05


def test_dry_run_records_excluded_from_real_reports(tmp_path):
    recs = [
        make_rec("P-001", "PASS", 1.0, 1024, {"cer_normalized": 0.0}),
        make_rec("P-002", "PASS", 1.0, 1024, {"cer_normalized": 0.0}, dry=True),
    ]
    d = store_run(tmp_path / "raw" / "runB", recs)
    rep = per_model_report(d, "m/x")
    assert rep["total_pages"] == 1  # dry record never counted


def test_quality_ranking_lower_error_first_and_not_run_last(tmp_path):
    d1 = store_run(tmp_path / "a", [make_rec("P-001", "PASS", 1, None,
                                             {"cer_normalized": 0.3})])
    d2 = store_run(tmp_path / "b", [make_rec("P-001", "PASS", 1, None,
                                             {"cer_normalized": 0.1})])
    d3 = tmp_path / "c"  # not run
    per_model = [per_model_report(d1, "m/worse"), per_model_report(d2, "m/better"),
                 per_model_report(d3, "m/notrun")]
    ranking = quality_ranking(per_model)
    assert ranking[0]["model_id"] == "m/better"
    assert ranking[1]["model_id"] == "m/worse"
    assert ranking[2] == {"rank": None, "model_id": "m/notrun",
                          "mean_cer_normalized": None}


def test_failure_report_groups_by_status(tmp_path):
    recs = [make_rec("P-001", "OOM"), make_rec("P-002", "OOM"),
            make_rec("P-003", "TIMEOUT")]
    d = store_run(tmp_path / "raw" / "runC", recs)
    fr = failure_report(d)
    assert fr["total_failures"] == 3
    assert fr["by_status"]["OOM"] == ["P-001", "P-002"]
    assert fr["by_status"]["TIMEOUT"] == ["P-003"]


def test_benchmark_summary_excludes_dry_runs():
    summary = benchmark_summary({})
    assert summary["dry_runs_excluded"] is True
