"""Pre-download all pinned registry models + their base models (network-only).

Run with the GPU venv or prep venv; touches no GPU. Base-model revisions are
resolved at download time and recorded to outputs/base_model_pins.json for
provenance (registry models use their frozen YAML pins).
"""

import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from benchmark.constants import GIT_ROOT  # noqa: E402
from benchmark.models.registry import load_registry  # noqa: E402

from huggingface_hub import HfApi, snapshot_download  # noqa: E402

api = HfApi()

TARGETS = [
    # (repo, pinned_revision_or_None)
    ("amad-iq/amad-vlm6", None),
    ("amad-iq/amad-vlm5", None),
    ("Qwen/Qwen2.5-VL-7B-Instruct", None),
    ("YasserSami/Qari-OCR-0.4.0-VL-4B-Instruct", None),
    ("Qwen/Qwen3-VL-4B-Instruct", None),
    ("context212/alhazen-ocr", None),
    ("unsloth/Qwen3-VL-2B-Instruct", None),
    ("sherif1313/Arabic-GLM-OCR-v2", None),
    ("zai-org/GLM-OCR", None),
    ("AhmedZaky1/DIMI-Arabic-OCR-V2", None),
    ("AhmedZaky1/DIMI-Arabic-OCR", None),
    ("loay/Arabic-OCR-DeepSeek-OCR-2", None),
    ("unsloth/DeepSeek-OCR-2", None),
    ("hastyle/olmOCR-arabic-lora-v2", None),
    ("allenai/olmOCR-2-7B-1025", None),
    ("MBZUAI/AIN", None),
]

def resolve_pin(repo: str) -> str:
    reg = load_registry()
    if repo in reg:
        return reg[repo]["pinned_revision"]
    info = api.model_info(repo)
    return info.sha

def main() -> int:
    pins: dict[str, str] = {}
    pin_path = GIT_ROOT / "outputs" / "base_model_pins.json"
    if pin_path.exists():
        pins.update(json.loads(pin_path.read_text()))
    for repo, _ in TARGETS:
        try:
            rev = resolve_pin(repo)
            t0 = time.monotonic()
            print(f"=== {repo} @ {rev}", flush=True)
            snapshot_download(repo, revision=rev)
            pins[repo] = rev
            pin_path.write_text(json.dumps(pins, indent=2, sort_keys=True))
            print(f"=== {repo} done in {time.monotonic()-t0:.0f}s", flush=True)
        except Exception as exc:  # noqa: BLE001 - keep downloading the rest
            print(f"!!! {repo} FAILED: {type(exc).__name__}: {exc}", flush=True)
    print("ALL DONE", flush=True)
    return 0

if __name__ == "__main__":
    sys.exit(main())
