"""Canonical manifest: freeze the 462-page official Primary Benchmark.

The manifest is a deterministic JSON document (sorted keys, stable ordering by
page_id). Its SHA-256 is written alongside; any change to page selection,
order, or record content changes the hash and invalidates the freeze.

Run:  .venv/bin/python -m benchmark.manifests.build
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

from benchmark.constants import (
    CANONICAL_MANIFEST_PATH,
    EXPORT_RECORDS_PATH,
    MANIFEST_SHA256_PATH,
    TOTAL_PAGES,
)

# Fields promoted to the top level of each record; everything else becomes
# record.metadata.
TOP_LEVEL_FIELDS = [
    "page_id",
    "source_dataset",
    "source_revision",
    "source_split",
    "source_row_or_stable_id",
    "source_record_identifier",
    "image_path",
    "ground_truth_path",
    "image_sha256",
    "ground_truth_sha256",
    "ground_truth_format",
    "language",
]


def build_manifest(records: list[dict]) -> dict:
    ordered = sorted(records, key=lambda r: r["page_id"])
    pages = []
    for rec in ordered:
        top = {k: rec[k] for k in TOP_LEVEL_FIELDS}
        top["metadata"] = {
            k: rec[k] for k in sorted(rec) if k not in TOP_LEVEL_FIELDS
        }
        pages.append(top)

    return {
        "manifest_version": 1,
        "page_count": len(pages),
        "page_order": "sorted by page_id (deterministic)",
        "pages": pages,
    }


def manifest_bytes(manifest: dict) -> bytes:
    """Canonical serialization used for the manifest's own SHA-256."""
    return json.dumps(
        manifest, indent=2, sort_keys=True, ensure_ascii=False
    ).encode("utf-8")


def main() -> None:
    records = json.loads(EXPORT_RECORDS_PATH.read_text(encoding="utf-8"))
    if len(records) != TOTAL_PAGES:
        raise SystemExit(
            f"expected {TOTAL_PAGES} export records, found {len(records)}"
        )
    manifest = build_manifest(records)
    data = manifest_bytes(manifest)
    digest = hashlib.sha256(data).hexdigest()

    CANONICAL_MANIFEST_PATH.write_bytes(data)
    MANIFEST_SHA256_PATH.write_text(digest + "\n", encoding="utf-8")
    print(f"canonical manifest -> {CANONICAL_MANIFEST_PATH}")
    print(f"pages: {manifest['page_count']}")
    print(f"manifest sha256: {digest}")


if __name__ == "__main__":
    main()
