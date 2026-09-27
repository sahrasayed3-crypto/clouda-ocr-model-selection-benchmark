"""HuggingFace transformers GPU engine for the official benchmark.

Implements the benchmark.runners.base.Engine protocol for chat-template VLM
checkpoints served through AutoProcessor + an image-text-to-text model class.
Nothing here is model-specific by hard-coding: behavior comes from the
registry YAML (configs/models/*.yaml) plus explicit CLI overrides recorded in
the run config.

Guarantees preserved from the runner core:
- No image distortion: images are passed to the model's own processor as-is
  (PIL, opened read-only from the frozen export).
- No quantization, no CPU offload: full-precision weights on one CUDA device.
- Raw output is stored verbatim; normalization/scoring happen downstream in
  the Runner, never inside the engine.
"""

from __future__ import annotations

import subprocess
import time
from pathlib import Path

import torch
from PIL import Image

DTORCH = {
    "bfloat16": torch.bfloat16,
    "float16": torch.float16,
    "float32": torch.float32,
}


def _gpu_uuid() -> str | None:
    try:
        out = subprocess.run(
            ["nvidia-smi", "--query-gpu=uuid", "--format=csv,noheader"],
            capture_output=True, text=True, timeout=10, check=True,
        )
        return out.stdout.strip().splitlines()[0] or None
    except Exception:  # noqa: BLE001 - uuid is informational
        return None


class HfVlmEngine:
    """Single-model OCR engine over a local HF checkpoint.

    Required constructor args:
      model_id, model_revision: pinned HF repo + 40-hex revision.
      dtype: torch dtype for weights.
      attn_implementation: "sdpa" | "eager" | "flash_attention_2".
      max_new_tokens: hard decoding cap (per page).
      model_class: optional exact class path (e.g.
        "transformers.HunYuanVLForConditionalGeneration"); falls back to
        AutoModelForImageTextToText when None.
      generation_kwargs: extra sampling params from the registry YAML
        (translated: temperature 0.0 -> greedy decoding).
      chat_style: "image_content_list" (messages with typed content parts)
        or "raw_text" (apply_chat_template on text, image passed separately).
      stop_tokens: optional list of stop strings handled post-hoc (raw output
        keeps everything the model produced; the stop handling only trims the
        recorded normalized transcription when the tokenizer lacks a real
        stop-id mechanism).
    """

    def __init__(
        self,
        *,
        model_id: str,
        model_revision: str,
        dtype: str = "bfloat16",
        attn_implementation: str = "sdpa",
        max_new_tokens: int = 8192,
        model_class: str | None = None,
        generation_kwargs: dict | None = None,
        chat_style: str = "image_content_list",
        stop_tokens: list[str] | None = None,
        device: str = "cuda:0",
        base_repo: str | None = None,
        base_revision: str | None = None,
        processor_repo: str | None = None,
        processor_revision: str | None = None,
        think_end_marker: str | None = None,
    ) -> None:
        self.model_id = model_id
        self.model_revision = model_revision
        self.dtype = DTORCH[dtype]
        self.dtype_name = dtype
        self.attn_implementation = attn_implementation
        self.max_new_tokens = max_new_tokens
        self.model_class = model_class
        self.generation_kwargs = dict(generation_kwargs or {})
        self.chat_style = chat_style
        self.stop_tokens = list(stop_tokens or [])
        self.device = device
        # Adapter repos (registry model_id is a PEFT adapter): weights load
        # from base_repo/base_revision, then the registry model attaches as
        # the adapter. Protocol: base is always the unquantized bf16 model,
        # never the bnb-4bit clone some adapter cards name.
        self.base_repo = base_repo
        self.base_revision = base_revision
        self.processor_repo = processor_repo or (base_repo or model_id)
        self.processor_revision = processor_revision or (base_revision or model_revision)
        self.think_end_marker = think_end_marker
        self._gpu_uuid = _gpu_uuid()
        self.model = None
        self.processor = None

    # -- Engine protocol ----------------------------------------------------
    def load(self) -> None:
        from transformers import AutoProcessor

        if self.model_class:
            module_path, _, cls_name = self.model_class.rpartition(".")
            import importlib
            cls = getattr(importlib.import_module(module_path), cls_name)
        else:
            from transformers import AutoModelForImageTextToText as cls  # noqa: N813

        self.processor = AutoProcessor.from_pretrained(
            self.processor_repo, revision=self.processor_revision,
        )
        weights_repo = self.base_repo or self.model_id
        weights_rev = self.base_revision or self.model_revision
        self.model = cls.from_pretrained(
            weights_repo,
            revision=weights_rev,
            dtype=self.dtype,
            attn_implementation=self.attn_implementation,
            device_map=self.device,
        )
        if self.base_repo:
            from peft import PeftModel

            self.model = PeftModel.from_pretrained(
                self.model, self.model_id, revision=self.model_revision
            )
        self.model.eval()

    def transcribe(
        self, image_path: Path, prompt: str, timeout_seconds: float | None
    ) -> dict:
        assert self.model is not None and self.processor is not None, "load() first"
        image = Image.open(image_path)
        image.load()  # read fully; the frozen export must stay untouched
        in_w, in_h = image.size

        messages = [{
            "role": "user",
            "content": [
                {"type": "image", "image": image},
                {"type": "text", "text": prompt},
            ],
        }]

        torch.cuda.synchronize()
        torch.cuda.reset_peak_memory_stats(self.device)
        t0 = time.monotonic()

        if self.chat_style == "image_content_list":
            inputs = self.processor.apply_chat_template(
                messages,
                add_generation_prompt=True,
                tokenize=True,
                return_dict=True,
                return_tensors="pt",
            ).to(self.device)
        elif self.chat_style == "no_template":
            # For processors with no chat template (e.g. DeepSeek-OCR family):
            # the documented prompt string goes straight into the processor
            # next to the image.
            inputs = self.processor(
                text=[prompt], images=[image], return_tensors="pt"
            ).to(self.device)
        else:  # raw_text: template the text, pass the image separately
            text = self.processor.apply_chat_template(
                messages, add_generation_prompt=True, tokenize=False
            )
            inputs = self.processor(
                text=[text], images=[image], return_tensors="pt"
            ).to(self.device)

        with torch.inference_mode():
            gen_kwargs = {
                "max_new_tokens": self.max_new_tokens,
                **self.generation_kwargs,
            }
            temperature = gen_kwargs.get("temperature")
            if temperature is None or float(temperature) == 0.0:
                gen_kwargs["do_sample"] = False  # greedy; sampled params off
                gen_kwargs.pop("temperature", None)
                gen_kwargs.pop("top_p", None)
                gen_kwargs.pop("top_k", None)
            else:
                gen_kwargs.setdefault("do_sample", True)
            out_ids = self.model.generate(**inputs, **gen_kwargs)

        torch.cuda.synchronize()
        elapsed = time.monotonic() - t0
        peak_mb = round(
            torch.cuda.max_memory_allocated(self.device) / (1024 * 1024), 1
        )

        new_ids = out_ids[0][inputs["input_ids"].shape[1]:]
        raw = self.processor.tokenizer.decode(
            new_ids, skip_special_tokens=True
        ).strip()
        if self.think_end_marker and self.think_end_marker in raw:
            # Thinking models (amad-vlm5/6): the documented invocation keeps
            # the text after the closing think marker as the transcription.
            raw = raw.rsplit(self.think_end_marker, 1)[1].strip()
        if timeout_seconds is not None and elapsed > timeout_seconds:
            raise TimeoutError(
                f"generation exceeded {timeout_seconds}s ({elapsed:.1f}s)"
            )

        return {
            "raw_output": raw,
            "dtype": self.dtype_name,
            "input_dimensions": {"width": in_w, "height": in_h},
            "gpu_name": torch.cuda.get_device_name(0),
            "gpu_uuid_if_available": self._gpu_uuid,
            "peak_vram_mb": peak_mb,
        }
