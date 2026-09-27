import pytest
import yaml

from benchmark.models.registry import (
    OFFICIAL_MODEL_IDS,
    load_registry,
    unresolved_invocations,
    validate_registry,
)

HAS_REGISTRY = len(list(__import__("benchmark.constants", fromlist=["MODEL_REGISTRY_DIR"]).MODEL_REGISTRY_DIR.glob("*.yaml"))) > 0


@pytest.mark.skipif(not HAS_REGISTRY, reason="registry not built yet")
def test_registry_has_exactly_official_10():
    entries = load_registry()
    assert set(entries) == set(OFFICIAL_MODEL_IDS)
    assert len(entries) == 10


@pytest.mark.skipif(not HAS_REGISTRY, reason="registry not built yet")
def test_all_pinned_revisions_are_full_shas():
    entries = load_registry()
    for mid, e in entries.items():
        rev = str(e["pinned_revision"])
        assert len(rev) == 40 and all(c in "0123456789abcdef" for c in rev.lower()), mid


@pytest.mark.skipif(not HAS_REGISTRY, reason="registry not built yet")
def test_registry_validation_clean():
    assert validate_registry(load_registry()) == []


def test_validation_flags_missing_entry_and_bad_sha():
    entries = {
        "a/b": {"model_id": "a/b", "pinned_revision": "short", "license": "x",
                "architecture": "arch", "base_model": None,
                "known_runtime_requirements": ""},
    }
    problems = validate_registry(entries)
    assert any("missing model entries" in p for p in problems)
    assert any("not a 40-hex" in p for p in problems)


def test_unresolved_prompt_handling():
    entries = {
        "m/with": {"documented_ocr_prompt": "Free OCR.", "expected_output_type": "text"},
        "m/without": {"documented_ocr_prompt": "UNRESOLVED", "expected_output_type": "UNRESOLVED"},
    }
    unresolved = unresolved_invocations(entries)
    assert unresolved == {"m/without": ["documented_ocr_prompt", "expected_output_type"]}


@pytest.mark.skipif(not HAS_REGISTRY, reason="registry not built yet")
def test_prompt_rule_no_invented_prompts():
    """Every documented prompt must trace to the model's own card; if a prompt
    is present, its source line must exist."""
    entries = load_registry()
    for mid, e in entries.items():
        prompt = str(e["documented_ocr_prompt"])
        if prompt != "UNRESOLVED":
            assert e.get("documented_ocr_prompt_source"), mid
