# Fairness Policy (Primary Benchmark)

Version: 1.0 — frozen 2026-09-19

## Principles

1. **Direct measurement.** The Primary Benchmark measures each OCR/VLM model
   directly on the frozen 462-page set. No Clouda component is involved at any
   stage: no Page Analyzer, no Trusted Digital Text Gate, no OCR Self-Review,
   no Selective Re-read, no Semantic Understanding, no Clouda document pipeline.

2. **Same input for everyone.** Every model receives the byte-identical page
   image from `data/images/` (no resize, no enhancement, no deskew, no
   re-encode, nothing).

3. **Documented prompts only.** A model's prompt is its own documented OCR
   invocation (see `configs/models/*.yaml`, `documented_ocr_prompt` +
   `documented_ocr_prompt_source`). Where no prompt is documented the field is
   `UNRESOLVED` and the model is NOT run until that is resolved. Prompts are
   never invented or borrowed from another family.

4. **No differential post-processing.** Documented model-specific output
   handling (e.g. amad-vlm5/vlm6 thinking-block stripping after the last
   `</think>`) is part of that model's documented invocation and is applied
   only to that model, exactly as its card instructs. Any such handling is
   recorded in the registry and surfaced in reports. Beyond documented
   handling, no model gets extra correction, retries, restoration, cleanup,
   or other post-processing others do not receive. A retry policy, if used,
   is identical for all models and recorded in the run state.

5. **Raw output is sacred.** Raw model output is stored once, atomically, and
   never modified. Normalization happens in a separate track
   (`outputs/normalized/`, `normalized_output` field) and is deterministic,
   versioned, and applied identically to predictions and ground truth.

6. **One model at a time** per GPU for the official run.

7. **Holdout discipline.** The 462 pages are holdout data: never used for
   training, fine-tuning, LoRA, prompt optimization against GT, iterative
   correction against GT, or repeated scoring while tuning prompts. GT text is
   never shown to a model or copied into a prompt.

## Performance comparability rule

CER/WER are comparable across models regardless of which GPU ran them.
Inference speed and VRAM are comparable ONLY within the same GPU model; every
performance number records the exact GPU model. Cross-hardware speed ranking
is prohibited; rerun on the same hardware class if a fair speed ranking is
needed.

## Excluded tracks

`loay/arabic-ocr-synthetic-scans-faker-300k` and any distorted/restored/
augmented variant of the 462 pages are outside the Primary Benchmark. A
robustness track, if built later, is a separate track with separate results.
