import json
from pathlib import Path

import pytest

from benchmark.constants import (
    CANONICAL_MANIFEST_PATH,
    MANIFEST_SHA256_PATH,
    TOTAL_PAGES,
)
from benchmark.validation.integrity import verify_manifest

MANIFEST_PRESENT = CANONICAL_MANIFEST_PATH.exists()


@pytest.mark.skipif(not MANIFEST_PRESENT, reason="manifest not built yet")
def test_manifest_count_is_462():
    manifest = json.loads(CANONICAL_MANIFEST_PATH.read_text(encoding="utf-8"))
    assert manifest["page_count"] == TOTAL_PAGES == 462
    assert len(manifest["pages"]) == 462


@pytest.mark.skipif(not MANIFEST_PRESENT, reason="manifest not built yet")
def test_manifest_page_ids_unique():
    manifest = json.loads(CANONICAL_MANIFEST_PATH.read_text(encoding="utf-8"))
    ids = [p["page_id"] for p in manifest["pages"]]
    assert len(set(ids)) == len(ids) == 462


@pytest.mark.skipif(not MANIFEST_PRESENT, reason="manifest not built yet")
def test_manifest_self_sha256_matches():
    recorded = MANIFEST_SHA256_PATH.read_text().strip()
    assert len(recorded) == 64
    report = verify_manifest()
    assert report["manifest_sha256"] == recorded


@pytest.mark.skipif(not MANIFEST_PRESENT, reason="manifest not built yet")
def test_manifest_split_counts():
    report = verify_manifest()
    assert report["misraj_pages"] == 400
    assert report["kitab_reviewed_pages"] == 62


@pytest.mark.skipif(not MANIFEST_PRESENT, reason="manifest not built yet")
def test_manifest_deterministic_page_order():
    manifest = json.loads(CANONICAL_MANIFEST_PATH.read_text(encoding="utf-8"))
    ids = [p["page_id"] for p in manifest["pages"]]
    assert ids == sorted(ids)


@pytest.mark.skipif(not MANIFEST_PRESENT, reason="manifest not built yet")
def test_full_integrity_verification_passes():
    report = verify_manifest()
    assert report["ok"], report["problems"]
    assert not report["problems"]


def test_integrity_detects_missing_image(tmp_path, monkeypatch):
    """Build a tiny synthetic manifest and verify detection logic."""
    import hashlib

    from benchmark.constants import GIT_ROOT

    img = tmp_path / "P-001.png"
    img.write_bytes(b"not-a-real-png-but-consistent")
    gt = tmp_path / "P-001.md"
    gt.write_text("نص عربي", encoding="utf-8")
    data = img.read_bytes()
    manifest = {
        "manifest_version": 1,
        "page_count": 1,
        "pages": [{
            "page_id": "P-001",
            "source_dataset": "test",
            "source_revision": "0" * 40,
            "source_split": "train",
            "source_row_or_stable_id": "row-0",
            "source_record_identifier": "test:train:row=0",
            "image_path": str(img),
            "ground_truth_path": str(gt),
            "image_sha256": hashlib.sha256(data).hexdigest(),
            "ground_truth_sha256": hashlib.sha256("نص عربي".encode()).hexdigest(),
            "ground_truth_format": "text/markdown",
            "language": "ar",
            "metadata": {},
        }],
    }
    mp = tmp_path / "m.json"
    mp.write_text(json.dumps(manifest), encoding="utf-8")

    import benchmark.validation.integrity as integ

    monkeypatch.setattr(integ, "CANONICAL_MANIFEST_PATH", mp)
    monkeypatch.setattr(integ, "MANIFEST_SHA256_PATH", tmp_path / "m.sha")
    report = integ.verify_manifest(mp)
    # sha file missing -> hash mismatch flagged
    assert any("sha256 mismatch" in p for p in report["problems"])

    # now write correct hash -> passes structure checks (PIL verify will flag
    # the fake png, proving corrupt-image detection works)
    (tmp_path / "m.sha").write_text(report["manifest_sha256"] + "\n")
    report2 = integ.verify_manifest(mp)
    assert any("corrupt images" in p for p in report2["problems"])
