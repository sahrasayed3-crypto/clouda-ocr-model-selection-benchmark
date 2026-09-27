"""Model registry: load and validate the 10 pinned model configuration entries.

Entries live in configs/models/*.yaml. Validation enforces:
- exactly the official 10 model ids present
- every entry has a pinned revision (40-hex sha)
- every required field present (UNRESOLVED is a legal explicit value)
- adapter models declare their base-model requirement
"""

from __future__ import annotations

from pathlib import Path

import yaml

from benchmark.constants import MODEL_REGISTRY_DIR

OFFICIAL_MODEL_IDS = [
    "tencent/HunyuanOCR",
    "amad-iq/amad-vlm6",
    "amad-iq/amad-vlm5",
    "YasserSami/Qari-OCR-0.4.0-VL-4B-Instruct",
    "context212/alhazen-ocr",
    "sherif1313/Arabic-GLM-OCR-v2",
    "AhmedZaky1/DIMI-Arabic-OCR-V2",
    "loay/Arabic-OCR-DeepSeek-OCR-2",
    "hastyle/olmOCR-arabic-lora-v2",
    "MBZUAI/AIN",
]

REQUIRED_FIELDS = [
    "model_id",
    "pinned_revision",
    "architecture",
    "base_model",
    "processor_class",
    "tokenizer_class",
    "required_transformers_version",
    "required_custom_code",
    "recommended_dtype",
    "recommended_attention_backend",
    "image_input_format",
    "documented_ocr_prompt",
    "generation_parameters",
    "special_stop_tokens",
    "expected_output_type",
    "license",
    "known_runtime_requirements",
    "estimated_vram_class",
    "notes",
]

UNRESOLVED = "UNRESOLVED"


def load_registry(registry_dir: Path = MODEL_REGISTRY_DIR) -> dict[str, dict]:
    entries: dict[str, dict] = {}
    for path in sorted(registry_dir.glob("*.yaml")):
        entry = yaml.safe_load(path.read_text(encoding="utf-8"))
        model_id = entry["model_id"]
        if model_id in entries:
            raise ValueError(f"duplicate registry entry for {model_id}")
        entries[model_id] = entry
    return entries


def validate_registry(entries: dict[str, dict]) -> list[str]:
    problems: list[str] = []
    ids = set(entries)
    expected = set(OFFICIAL_MODEL_IDS)
    missing = expected - ids
    extra = ids - expected
    if missing:
        problems.append(f"missing model entries: {sorted(missing)}")
    if extra:
        problems.append(f"unexpected extra model entries: {sorted(extra)}")

    for model_id, entry in entries.items():
        for field in REQUIRED_FIELDS:
            if field not in entry or entry[field] is None and field != "base_model":
                if field not in entry:
                    problems.append(f"{model_id}: missing field '{field}'")
        rev = str(entry.get("pinned_revision", ""))
        if len(rev) != 40 or any(c not in "0123456789abcdef" for c in rev.lower()):
            problems.append(f"{model_id}: pinned_revision is not a 40-hex sha: {rev!r}")
        arch = str(entry.get("architecture", ""))
        if "lora" in arch.lower() or "adapter" in arch.lower() or "peft" in str(
            entry.get("known_runtime_requirements", "")
        ).lower():
            if not entry.get("adapter_requirements") and not str(
                entry.get("base_model")
            ):
                problems.append(
                    f"{model_id}: adapter-style model must declare base_model/adapter_requirements"
                )
        if not str(entry.get("license", "")).strip():
            problems.append(f"{model_id}: empty license")
    return problems


def unresolved_invocations(entries: dict[str, dict]) -> dict[str, list[str]]:
    """Models whose documented invocation is UNRESOLVED (prompt or output type)."""
    out: dict[str, list[str]] = {}
    for model_id, entry in entries.items():
        unresolved = [
            field
            for field in ("documented_ocr_prompt", "expected_output_type")
            if UNRESOLVED in str(entry.get(field, ""))
        ]
        if unresolved:
            out[model_id] = unresolved
    return out


def registry_summary(entries: dict[str, dict]) -> list[dict]:
    return [
        {
            "model_id": e["model_id"],
            "pinned_revision": e["pinned_revision"],
            "architecture": e["architecture"],
            "license": e["license"],
            "documented_ocr_prompt": e["documented_ocr_prompt"],
            "estimated_vram_class": e["estimated_vram_class"],
        }
        for _, e in sorted(entries.items())
    ]
