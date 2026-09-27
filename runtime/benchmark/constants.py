"""Project-wide constants: paths, pinned dataset revisions, fixed counts.

The pinned revisions below were resolved from the Hugging Face Hub API on
2026-09-19 and are the ONLY revisions the official Primary Benchmark may use.
Changing them is a protocol change and requires rebuilding the manifest.
"""

from __future__ import annotations

from pathlib import Path

GIT_ROOT = Path(__file__).resolve().parent.parent

DATA_DIR = GIT_ROOT / "data"
IMAGE_DIR = DATA_DIR / "images"
GT_DIR = DATA_DIR / "ground_truth"

MANIFEST_DIR = GIT_ROOT / "benchmark" / "manifests"
EXPORT_RECORDS_PATH = MANIFEST_DIR / "export_records.json"
SOURCE_STATE_PATH = MANIFEST_DIR / "pinned_source_state.json"
CANONICAL_MANIFEST_PATH = MANIFEST_DIR / "canonical_manifest.json"
MANIFEST_SHA256_PATH = MANIFEST_DIR / "canonical_manifest.sha256"
DATASET_INTEGRITY_REPORT_PATH = MANIFEST_DIR / "dataset_integrity_report.json"

OUTPUTS_DIR = GIT_ROOT / "outputs"
RAW_OUTPUT_DIR = OUTPUTS_DIR / "raw"
NORMALIZED_OUTPUT_DIR = OUTPUTS_DIR / "normalized"
METRICS_OUTPUT_DIR = OUTPUTS_DIR / "metrics"
LOGS_OUTPUT_DIR = OUTPUTS_DIR / "logs"

# Dry-run namespace: COMPLETELY separate from outputs/. Mock data must never
# leak into real benchmark artifacts.
DRY_RUNS_DIR = GIT_ROOT / "dry_runs"

CONFIGS_DIR = GIT_ROOT / "configs"
MODEL_REGISTRY_DIR = GIT_ROOT / "configs" / "models"
SMOKE_SET_PATH = GIT_ROOT / "configs" / "smoke_set.json"

# ---------------------------------------------------------------------------
# Official Primary Benchmark dataset pins (resolved 2026-09-19).
# ---------------------------------------------------------------------------

DOCOCR_DATASET = "Misraj/Misraj-DocOCR"
DOCOCR_PINNED_REVISION = "7177bf70f77ce259890d6af0bef53f18faf26ec9"
DOCOCR_ROW_COUNT = 400

KITAB_DATASET = "Misraj/KITAB_pdf_to_markdown_reviewed"
KITAB_PINNED_REVISION = "8890d721c660cd027839bc8bc48634552fe7aec6"
KITAB_ROW_COUNT = 62

TOTAL_PAGES = DOCOCR_ROW_COUNT + KITAB_ROW_COUNT  # 462

# Explicitly EXCLUDED from the official Primary Benchmark.
EXCLUDED_DATASETS = ["loay/arabic-ocr-synthetic-scans-faker-300k"]

# ---------------------------------------------------------------------------
# Fixed scope of the official run.
# ---------------------------------------------------------------------------

OFFICIAL_MODEL_COUNT = 10

BENCHMARK_PROTOCOL_VERSION = "1.0.0"
NORMALIZATION_POLICY_VERSION = "1.0.0"
RESULT_SCHEMA_VERSION = "1.0.0"

# Deterministic page order: sorted page_id (MISRAJ-0001..0400, then KITAB-R-0001..0062).
def canonical_page_order(page_ids: list[str]) -> list[str]:
    return sorted(page_ids)
