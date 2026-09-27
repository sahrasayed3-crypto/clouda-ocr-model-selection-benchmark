"""Mock OCR engine for CPU-only dry-run mode.

Produces deterministic, obviously-fake output derived from the page_id so
that normalization/metrics/reporting pipelines are exercised end-to-end
without any model. Output text is clearly marked as mock. Supports optional
failure injection (fail page_ids with a given status) to exercise failure
recording and resume behavior.
"""

from __future__ import annotations

import hashlib
import time
from pathlib import Path


class MockEngine:
    model_id = "mock/mock-ocr"
    model_revision = "mock"

    def __init__(self, fail_pages: dict[str, str] | None = None, simulated_latency: float = 0.0):
        self.fail_pages = fail_pages or {}
        self.simulated_latency = simulated_latency
        self._loaded = False

    def load(self) -> None:
        self._loaded = True

    def transcribe(
        self, image_path: Path, prompt: str, timeout_seconds: float | None
    ) -> dict:
        page_id = image_path.stem
        if self.simulated_latency:
            time.sleep(self.simulated_latency)
        if page_id in self.fail_pages:
            status = self.fail_pages[page_id]
            if status == "TIMEOUT":
                raise TimeoutError(f"mock timeout for {page_id}")
            if status == "OOM":
                raise MemoryError(f"CUDA out of memory (mock) for {page_id}")
            raise RuntimeError(f"mock injected failure ({status}) for {page_id}")

        digest = hashlib.sha256(page_id.encode()).hexdigest()[:16]
        raw = (
            "[MOCK OCR OUTPUT]\n"
            f"page_id={page_id}\n"
            f"digest={digest}\n"
            "نص تجريبي وهمي لأغراض التحقق من البنية التحتية فقط.\n"
            "[/MOCK OCR OUTPUT]\n"
        )
        return {
            "raw_output": raw,
            "dtype": "mock",
            "input_dimensions": None,  # real engine fills this; mock stays null
            "gpu_name": None,
            "gpu_uuid_if_available": None,
            "peak_vram_mb": None,
        }
