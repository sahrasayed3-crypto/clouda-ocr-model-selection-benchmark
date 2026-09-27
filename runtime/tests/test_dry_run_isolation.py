import json
from pathlib import Path

import pytest

from benchmark.constants import DRY_RUNS_DIR, SMOKE_SET_PATH, TOTAL_PAGES
from benchmark.dry_run import load_manifest_pages, load_smoke_page_ids
from benchmark.runners.base import Runner, RunConfig
from benchmark.runners.mock_engine import MockEngine


def test_dry_run_namespace_is_separate(tmp_path):
    """Dry-run outputs go under dry_runs/, never under outputs/."""
    config = RunConfig(
        model_id="mock/iso-test", model_revision="0" * 40,
        prompt="mock", generation_parameters={}, manifest_sha256="0" * 64,
        page_ids=["P-001"], is_dry_run=True,
    )
    root = DRY_RUNS_DIR / "runs"
    run_id = config.new_run_id()
    assert run_id.startswith("DRYRUN__")
    runner = Runner(root, run_id, config)
    img = DRY_RUNS_DIR / "iso_test_img.png"
    img.write_bytes(b"x")
    pages = {"P-001": {"image_path": str(img), "ground_truth_path": ""}}
    results = runner.run(MockEngine(), pages)
    assert results[0]["is_dry_run"] is True
    assert "dry_runs" in str(runner.raw_dir)
    img.unlink()


def test_real_runner_never_writes_dry_prefix_into_outputs(tmp_path):
    config = RunConfig(
        model_id="real/never-run", model_revision="0" * 40,
        prompt="x", generation_parameters={}, manifest_sha256="0" * 64,
        page_ids=["P-001"], is_dry_run=False,
    )
    # construct only; never executed in preparation phase
    run_id = config.new_run_id()
    assert not run_id.startswith("DRYRUN__")


def test_dry_run_loaders_valid():
    pages = load_manifest_pages()
    assert len(pages) == TOTAL_PAGES
    smoke = load_smoke_page_ids()
    assert len(smoke) == 5
    assert set(smoke) <= set(pages)


def test_smoke_set_frozen_shape():
    smoke = json.loads(SMOKE_SET_PATH.read_text(encoding="utf-8"))
    assert len(smoke["pages"]) == 5
    for p in smoke["pages"]:
        assert {"page_id", "selection_reason", "source_dataset",
                "difficulty_characteristics"} <= set(p)
