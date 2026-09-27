import json

import pytest

from benchmark.runners.base import (
    Runner,
    RunConfig,
    classify_exception,
    make_run_result,
)
from benchmark.runners.mock_engine import MockEngine


def make_config(tmp_path, page_ids, **kw):
    kw.setdefault("is_dry_run", True)
    return RunConfig(
        model_id="mock/test-model",
        model_revision="a" * 40,
        prompt="test prompt",
        generation_parameters={"do_sample": False},
        manifest_sha256="0" * 64,
        page_ids=page_ids,
        **kw,
    )


def make_pages(tmp_path, page_ids):
    pages = {}
    for pid in page_ids:
        img = tmp_path / f"{pid}.png"
        img.write_bytes(b"fake")
        pages[pid] = {"image_path": str(img), "ground_truth_path": ""}
    return pages


def test_page_order_is_deterministic_manifest_order(tmp_path):
    ids = ["P-003", "P-001", "P-002"]
    config = make_config(tmp_path, ids)
    runner = Runner(tmp_path / "outputs", config.new_run_id(), config)
    results = runner.run(MockEngine(), make_pages(tmp_path, ids))
    assert [r["page_id"] for r in results] == ids  # manifest (config) order preserved


def test_atomic_result_writes_no_tmp_leftovers(tmp_path):
    ids = ["P-001", "P-002"]
    config = make_config(tmp_path, ids)
    runner = Runner(tmp_path / "outputs", config.new_run_id(), config)
    runner.run(MockEngine(), make_pages(tmp_path, ids))
    leftovers = list(runner.raw_dir.glob("*.tmp-*"))
    assert leftovers == []
    for pid in ids:
        rec = json.loads((runner.raw_dir / f"{pid}.json").read_text())
        assert rec["status"] == "PASS"


def test_resume_skips_completed_pages(tmp_path):
    ids = ["P-001", "P-002", "P-003"]
    config = make_config(tmp_path, ids)
    run_id = config.new_run_id()
    runner = Runner(tmp_path / "outputs", run_id, config)
    pages = make_pages(tmp_path, ids)

    # simulate crash: only first page completed
    (tmp_path / "outputs" / "raw" / run_id).mkdir(parents=True)
    done = make_run_result(run_id=run_id, config=config, page_id="P-001",
                           status="PASS", raw_output="x")
    (runner.page_result_path("P-001")).write_text(json.dumps(done))

    engine_calls = []
    real_transcribe = MockEngine.transcribe

    def counting(self, image_path, prompt, timeout):
        engine_calls.append(image_path.stem)
        return real_transcribe(self, image_path, prompt, timeout)

    MockEngine.transcribe = counting
    try:
        results = runner.run(MockEngine(), pages)
    finally:
        MockEngine.transcribe = real_transcribe
    assert sorted(engine_calls) == ["P-002", "P-003"]  # P-001 not reprocessed
    assert [r["page_id"] for r in results] == sorted(ids)


def test_duplicate_run_prevention(tmp_path):
    config = make_config(tmp_path, ["P-001"])
    run_id = config.new_run_id()
    Runner(tmp_path / "outputs", run_id, config).run(
        MockEngine(), make_pages(tmp_path, ["P-001"]))
    other_config = make_config(tmp_path, ["P-001"])
    other_config.prompt = "different prompt"
    with pytest.raises(RuntimeError, match="refusing to reuse run id"):
        Runner(tmp_path / "outputs", run_id, other_config).prepare()


def test_failure_recording_and_retry_policy(tmp_path):
    ids = ["P-001", "P-002"]
    config = make_config(tmp_path, ids, max_retries=2)
    runner = Runner(tmp_path / "outputs", config.new_run_id(), config)
    engine = MockEngine(fail_pages={"P-001": "OOM"})
    results = runner.run(engine, make_pages(tmp_path, ids))
    by_id = {r["page_id"]: r for r in results}
    assert by_id["P-001"]["status"] == "OOM"
    assert by_id["P-001"]["retry_count"] == 2  # retried per policy, then recorded
    assert by_id["P-001"]["exception_type"] == "MemoryError"
    assert by_id["P-002"]["status"] == "PASS"


def test_timeout_and_model_load_error_classification(tmp_path):
    assert classify_exception(TimeoutError("t")) == "TIMEOUT"
    assert classify_exception(MemoryError("CUDA out of memory")) == "OOM"
    assert classify_exception(RuntimeError("boom")) == "FAIL"

    config = make_config(tmp_path, ["P-001"])
    runner = Runner(tmp_path / "outputs", config.new_run_id(), config)

    class BrokenLoad:
        model_id = "broken"
        model_revision = "x" * 40

        def load(self):
            raise RuntimeError("safetensors missing")

        def transcribe(self, *a, **k):  # pragma: no cover
            raise AssertionError

    results = runner.run(BrokenLoad(), make_pages(tmp_path, ["P-001"]))
    assert results[0]["status"] == "MODEL_LOAD_ERROR"


def test_result_schema_fields_and_null_gpu_in_prep(tmp_path):
    config = make_config(tmp_path, ["P-001"])
    runner = Runner(tmp_path / "outputs", config.new_run_id(), config)
    results = runner.run(MockEngine(), make_pages(tmp_path, ["P-001"]))
    rec = results[0]
    for field in ("run_id", "model_id", "model_revision", "page_id", "status",
                  "raw_output", "normalized_output", "elapsed_seconds", "gpu_name",
                  "gpu_uuid_if_available", "peak_vram_mb", "dtype",
                  "input_dimensions", "prompt_hash", "generation_config_hash",
                  "exception_type", "exception_message", "retry_count",
                  "started_at", "completed_at"):
        assert field in rec, f"missing schema field {field}"
    # preparation mode: no fabricated GPU measurements
    assert rec["gpu_name"] is None
    assert rec["gpu_uuid_if_available"] is None
    assert rec["peak_vram_mb"] is None
    assert rec["is_dry_run"] is True


def test_dry_run_id_prefix_and_real_ids_differ(tmp_path):
    dry = make_config(tmp_path, ["P-001"], is_dry_run=True)
    real = make_config(tmp_path, ["P-001"], is_dry_run=False)
    assert dry.new_run_id().startswith("DRYRUN__")
    assert not real.new_run_id().startswith("DRYRUN__")
