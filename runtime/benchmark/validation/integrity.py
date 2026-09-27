"""Dataset integrity verification for the frozen 462-page manifest.

Checks (all deterministic, CPU-only, no network):
- manifest count == 462, unique page IDs, no duplicates
- every image file exists, hash matches, decodes cleanly (PIL verify)
- every GT file exists, hash matches, reads as UTF-8, contains Arabic
- manifest self-hash matches canonical_manifest.sha256
- page ordering is the canonical deterministic order
"""

from __future__ import annotations

import hashlib
import io
import json
from pathlib import Path

from benchmark.constants import (
    CANONICAL_MANIFEST_PATH,
    DOCOCR_PINNED_REVISION,
    DOCOCR_ROW_COUNT,
    GIT_ROOT,
    KITAB_PINNED_REVISION,
    KITAB_ROW_COUNT,
    MANIFEST_SHA256_PATH,
    TOTAL_PAGES,
)
from benchmark.manifests.build import manifest_bytes

ARABIC_RANGES = (
    ("\u0600", "\u06FF"),  # Arabic
    ("\u0750", "\u077F"),  # Arabic Supplement
    ("\uFB50", "\uFDFF"),  # Arabic Presentation Forms-A
    ("\uFE70", "\uFEFF"),  # Arabic Presentation Forms-B
)


def contains_arabic(text: str) -> bool:
    return any(
        any(lo <= c <= hi for lo, hi in ARABIC_RANGES) for c in text
    )


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def verify_manifest(manifest_path: Path = CANONICAL_MANIFEST_PATH) -> dict:
    problems: list[str] = []
    warnings: list[str] = []

    if not manifest_path.exists():
        return {"ok": False, "problems": [f"manifest missing: {manifest_path}"]}

    data = manifest_path.read_bytes()
    manifest = json.loads(data)

    # --- manifest self-hash -------------------------------------------------
    recomputed = hashlib.sha256(manifest_bytes(manifest)).hexdigest()
    recorded = MANIFEST_SHA256_PATH.read_text().strip() if MANIFEST_SHA256_PATH.exists() else None
    if recorded != recomputed:
        problems.append(
            f"manifest sha256 mismatch: recorded={recorded} recomputed={recomputed}"
        )

    pages = manifest["pages"]

    # --- counts and uniqueness ----------------------------------------------
    if len(pages) != TOTAL_PAGES:
        problems.append(f"page count {len(pages)} != {TOTAL_PAGES}")
    page_ids = [p["page_id"] for p in pages]
    if len(set(page_ids)) != len(page_ids):
        dupes = {x for x in page_ids if page_ids.count(x) > 1}
        problems.append(f"duplicate page ids: {sorted(dupes)}")
    if page_ids != sorted(page_ids):
        problems.append("pages not in canonical sorted order")

    expected_prefixes = {
        "MISRAJ-": DOCOCR_ROW_COUNT,
        "KITAB-R-": KITAB_ROW_COUNT,
    }
    for prefix, count in expected_prefixes.items():
        n = sum(1 for pid in page_ids if pid.startswith(prefix))
        if n != count:
            problems.append(f"{prefix}* count {n} != {count}")

    # --- pinned revisions ----------------------------------------------------
    for p in pages:
        expected_rev = (
            DOCOCR_PINNED_REVISION
            if p["page_id"].startswith("MISRAJ-")
            else KITAB_PINNED_REVISION
        )
        if p.get("source_revision") != expected_rev:
            problems.append(
                f"{p['page_id']}: revision {p.get('source_revision')} != pinned {expected_rev}"
            )

    # --- files, hashes, decodability -----------------------------------------
    corrupt_images: list[str] = []
    for p in pages:
        img = GIT_ROOT / p["image_path"]
        gt = GIT_ROOT / p["ground_truth_path"]
        if not img.exists():
            problems.append(f"{p['page_id']}: image missing {p['image_path']}")
            continue
        if not gt.exists():
            problems.append(f"{p['page_id']}: ground truth missing {p['ground_truth_path']}")
            continue
        if sha256_file(img) != p["image_sha256"]:
            problems.append(f"{p['page_id']}: image sha256 mismatch")
        if sha256_file(gt) != p["ground_truth_sha256"]:
            problems.append(f"{p['page_id']}: ground truth sha256 mismatch")
        try:
            from PIL import Image

            with Image.open(img) as im:
                im.verify()
        except Exception as exc:  # noqa: BLE001
            corrupt_images.append(f"{p['page_id']} ({exc})")
        try:
            text = gt.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            problems.append(f"{p['page_id']}: ground truth not valid UTF-8")
            continue
        if not contains_arabic(text):
            warnings.append(f"{p['page_id']}: no Arabic characters in ground truth")

    if corrupt_images:
        problems.append("corrupt images: " + "; ".join(corrupt_images[:5]))

    return {
        "ok": not problems,
        "total_pages": len(pages),
        "unique_page_ids": len(set(page_ids)),
        "misraj_pages": sum(1 for x in page_ids if x.startswith("MISRAJ-")),
        "kitab_reviewed_pages": sum(1 for x in page_ids if x.startswith("KITAB-R-")),
        "manifest_sha256": recomputed,
        "problems": problems,
        "warnings": warnings,
    }
