"""CPU-only, no-model dry-run mode. Infrastructure validation ONLY.

Isolation guarantees (protocol §15):
- All artifacts go under dry_runs/ (its own namespace), never outputs/.
- Run IDs carry the DRYRUN__ prefix and is_dry_run=true; they can never be
  mistaken for real inference records.
- Reports generated here live in dry_runs/ as well.

Run:  .venv/bin/python -m benchmark.dry_run [--all-pages] [--inject-failures]
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from benchmark.constants import (
    CANONICAL_MANIFEST_PATH,
    DRY_RUNS_DIR,
    SMOKE_SET_PATH,
)
from benchmark.reporting.reports import failure_report, per_model_report
from benchmark.runners.base import Runner, RunConfig
from benchmark.runners.mock_engine import MockEngine


def load_manifest_pages() -> dict[str, dict]:
    manifest = json.loads(CANONICAL_MANIFEST_PATH.read_text(encoding="utf-8"))
    return {p["page_id"]: p for p in manifest["pages"]}


def load_smoke_page_ids() -> list[str]:
    smoke = json.loads(SMOKE_SET_PATH.read_text(encoding="utf-8"))
    return [p["page_id"] for p in smoke["pages"]]


def main() -> int:
    ap = argparse.ArgumentParser(description="CPU-only dry-run (mock outputs)")
    ap.add_argument("--all-pages", action="store_true",
                    help="exercise all 462 pages instead of the 5-page smoke set")
    ap.add_argument("--inject-failures", action="store_true",
                    help="inject mock OOM/TIMEOUT failures to exercise failure recording")
    ap.add_argument("--resume-probe", action="store_true",
                    help="run twice over the same run id to prove resume skips completed pages")
    args = ap.parse_args()

    pages = load_manifest_pages()
    page_ids = sorted(pages) if args.all_pages else load_smoke_page_ids()
    fail_pages = {}
    if args.inject_failures:
        fail_pages = {page_ids[0]: "OOM", page_ids[1]: "TIMEOUT", page_ids[2]: "FAIL"}

    config = RunConfig(
        model_id="mock/mock-ocr",
        model_revision="mock",
        prompt="[MOCK PROMPT - dry-run only]",
        generation_parameters={"mock": True},
        manifest_sha256="dry-run-does-not-score-against-manifest",
        page_ids=page_ids,
        is_dry_run=True,
        notes="infrastructure validation only; outputs are mock",
    )
    run_id = config.new_run_id()
    root = DRY_RUNS_DIR / "runs"
    runner = Runner(root, run_id, config)
    engine = MockEngine(fail_pages=fail_pages)

    results = runner.run(engine, pages)
    if args.resume_probe:
        before = len(results)
        results2 = runner.run(engine, pages)
        after = len(results2)
        assert after == before, "resume reprocessed pages"
        print(f"resume probe: {before} pages, re-run returned same {after} (no reprocessing)")

    # Dry-run's own report aggregates its own mock records (include_dry=True);
    # real reports built from outputs/ keep excluding dry records.
    per_model = per_model_report(runner.raw_dir, config.model_id, include_dry=True)
    fails = failure_report(runner.raw_dir, include_dry=True)

    out = {
        "dry_run": True,
        "run_id": run_id,
        "pages_exercised": len(page_ids),
        "per_model": per_model,
        "failures": fails if args.inject_failures else None,
    }
    out_path = DRY_RUNS_DIR / "last_dry_run_report.json"
    out_path.write_text(json.dumps(out, indent=2, ensure_ascii=False), encoding="utf-8")
    print(json.dumps({k: out[k] for k in ("dry_run", "run_id", "pages_exercised")},
                     indent=2))
    print("per-model:", json.dumps(per_model, indent=2, ensure_ascii=False))
    print("report ->", out_path)
    return 0


if __name__ == "__main__":
    sys.exit(main())
