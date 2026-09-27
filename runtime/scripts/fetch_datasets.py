#!/usr/bin/env python
"""Fetch the two official Primary Benchmark datasets at PINNED revisions and
export page images + ground truth losslessly into data/.

Design constraints enforced here:
- Revisions are pinned in benchmark/constants.py; nothing floats on `main`.
- Parquet shards are downloaded via snapshot_download at the pinned revision.
- Images are exported with ORIGINAL bytes (decode=False path). No re-encode,
  no resize, no rotation, no color change -- byte-identical to what the source
  parquet stores.
- Ground truth is exported as UTF-8 text, content untouched.
- The pinned revision is recorded BEFORE any row selection (see output json).

Run:  .venv/bin/python scripts/fetch_datasets.py
"""

from __future__ import annotations

import hashlib
import io
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

from benchmark.constants import (  # noqa: E402
    DATA_DIR,
    DOCOCR_DATASET,
    DOCOCR_PINNED_REVISION,
    DOCOCR_ROW_COUNT,
    GIT_ROOT,
    GT_DIR,
    IMAGE_DIR,
    KITAB_DATASET,
    KITAB_PINNED_REVISION,
    KITAB_ROW_COUNT,
    SOURCE_STATE_PATH,
)

# Project caches stay inside the Lightning workspace.
import os  # noqa: E402

os.environ.setdefault("HF_HOME", str(GIT_ROOT.parent / ".cache" / "huggingface"))

from datasets import Image as DatasetImage, load_dataset  # noqa: E402
from huggingface_hub import snapshot_download  # noqa: E402
from PIL import Image  # noqa: E402


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def contains_arabic(text: str) -> bool:
    return any("\u0600" <= c <= "\u06FF" or "\u0750" <= c <= "\u077F"
               or "\uFB50" <= c <= "\uFDFF" or "\uFE70" <= c <= "\uFEFF"
               for c in text)


def export_dataset(
    dataset_id: str,
    pinned_revision: str,
    expected_rows: int,
    split: str,
    id_prefix: str,
    has_uuid: bool,
) -> list[dict]:
    """Download pinned parquet shards and export rows in deterministic order.

    Row order is the parquet shard order + within-shard row order at the pinned
    revision, i.e. exactly `rows 0..N-1` of the pinned `train` split.
    """
    print(f"--- {dataset_id} @ {pinned_revision[:12]} ---")
    local = snapshot_download(
        repo_id=dataset_id,
        repo_type="dataset",
        revision=pinned_revision,
        allow_patterns=["data/*.parquet", "README.md"],
    )
    data_files = sorted((Path(local) / "data").glob("*.parquet"))
    if not data_files:
        raise RuntimeError(f"no parquet shards found for {dataset_id}")
    print(f"shards: {[p.name for p in data_files]}")

    ds = load_dataset("parquet", data_files=[str(p) for p in data_files], split="train")
    n = len(ds)
    if n != expected_rows:
        raise RuntimeError(
            f"{dataset_id}: pinned revision exposes {n} rows, expected {expected_rows}"
        )
    print(f"rows: {n} (matches expectation)")

    # Lossless access: keep the raw encoded bytes exactly as stored upstream.
    ds_raw = ds.cast_column("image", DatasetImage(decode=False))

    records: list[dict] = []
    seen_uuids: set[str] = set()
    for i in range(n):
        row_raw = ds_raw[i]
        row = ds[i]
        img_struct = row_raw["image"]
        img_bytes = img_struct["bytes"]
        if img_bytes is None:
            raise RuntimeError(f"{dataset_id} row {i}: image bytes missing")
        original_name = (img_struct.get("path") or "") or f"row_{i}.png"

        page_id = f"{id_prefix}-{i + 1:04d}"
        source_uuid = row.get("uuid") if has_uuid else None
        if has_uuid:
            if not source_uuid or source_uuid in seen_uuids:
                raise RuntimeError(
                    f"{dataset_id} row {i}: uuid missing/duplicate ({source_uuid})"
                )
            seen_uuids.add(source_uuid)

        suffix = Path(original_name).suffix.lower()
        if suffix not in {".png", ".jpg", ".jpeg", ".tif", ".tiff", ".bmp", ".webp"}:
            suffix = ".png"  # verified: all source images decode as PNG
        image_rel = f"images/{dataset_id.split('/')[-1]}/{page_id}{suffix}"
        gt_rel = f"ground_truth/{dataset_id.split('/')[-1]}/{page_id}.md"

        image_path = DATA_DIR / image_rel
        gt_path = DATA_DIR / gt_rel
        image_path.parent.mkdir(parents=True, exist_ok=True)
        gt_path.parent.mkdir(parents=True, exist_ok=True)

        image_path.write_bytes(img_bytes)  # byte-identical, no re-encode
        markdown: str = row["markdown"]
        gt_path.write_text(markdown, encoding="utf-8")

        # Inspect without modifying: decode a throwaway in-memory copy.
        with Image.open(io.BytesIO(img_bytes)) as im:
            fmt = im.format
            width, height = im.size
            im.verify()  # structural integrity check

        records.append(
            {
                "page_id": page_id,
                "source_dataset": dataset_id,
                "source_revision": pinned_revision,
                "source_split": split,
                "source_row_index": i,
                "source_record_identifier": (
                    f"{dataset_id}:{split}:row={i}"
                    + (f";uuid={source_uuid}" if source_uuid else "")
                ),
                "source_row_or_stable_id": source_uuid if source_uuid else f"row-{i}",
                "image_path": str(image_path.relative_to(REPO_ROOT)),
                "ground_truth_path": str(gt_path.relative_to(REPO_ROOT)),
                "image_sha256": sha256_bytes(img_bytes),
                "ground_truth_sha256": sha256_bytes(markdown.encode("utf-8")),
                "ground_truth_format": "text/markdown",
                "image_format": fmt,
                "image_width": width,
                "image_height": height,
                "image_bytes": len(img_bytes),
                "ground_truth_chars": len(markdown),
                # Deterministic per-page language: Arabic script presence in GT.
                "language": "ar" if contains_arabic(markdown) else "en",
            }
        )
        if (i + 1) % 50 == 0:
            print(f"  exported {i + 1}/{n}")

    return records


def main() -> None:
    IMAGE_DIR.mkdir(parents=True, exist_ok=True)
    GT_DIR.mkdir(parents=True, exist_ok=True)

    # Record pinning BEFORE row selection (audit trail).
    SOURCE_STATE_PATH.parent.mkdir(parents=True, exist_ok=True)
    SOURCE_STATE_PATH.write_text(
        json.dumps(
            {
                "dococr": {
                    "dataset": DOCOCR_DATASET,
                    "revision": DOCOCR_PINNED_REVISION,
                    "expected_rows": DOCOCR_ROW_COUNT,
                    "selection": "rows 0-399 of pinned train split (parquet order)",
                },
                "kitab_reviewed": {
                    "dataset": KITAB_DATASET,
                    "revision": KITAB_PINNED_REVISION,
                    "expected_rows": KITAB_ROW_COUNT,
                    "selection": "rows 0-61 of pinned train split (parquet order)",
                },
            },
            indent=2,
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    print("pinned source state recorded ->", SOURCE_STATE_PATH.relative_to(REPO_ROOT))

    dococr = export_dataset(
        DOCOCR_DATASET, DOCOCR_PINNED_REVISION, DOCOCR_ROW_COUNT, "train",
        "MISRAJ", has_uuid=True,
    )
    kitab = export_dataset(
        KITAB_DATASET, KITAB_PINNED_REVISION, KITAB_ROW_COUNT, "train",
        "KITAB-R", has_uuid=False,
    )

    out = REPO_ROOT / "benchmark" / "manifests" / "export_records.json"
    out.write_text(
        json.dumps(dococr + kitab, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    print(f"export records -> {out.relative_to(REPO_ROOT)}")
    print(f"TOTAL exported pages: {len(dococr) + len(kitab)}")


if __name__ == "__main__":
    main()
