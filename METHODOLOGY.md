# Benchmark Methodology and Protocol

Version 1.0 — protocol frozen 2026-09-19 before any full-run inference; run window **2026-09-19 → 2026-09-24 UTC**, across two sessions on two servers (session 1: NVIDIA L40S with sequential single-model execution; session 2 (resumed): NVIDIA H200).

This document describes the exact protocol of the Clouda OCR model-selection benchmark: a direct, frozen evaluation of existing OCR/VLM models on 462 Arabic document pages, run to compare Arabic OCR quality and robustness for model selection.

## 1. Corpus construction

- **462 pages, frozen.** 400 pages from `Misraj/Misraj-DocOCR` (rows 0–399 of the pinned `train` split, parquet order) and 62 pages from `Misraj/KITAB_pdf_to_markdown_reviewed` (rows 0–61, parquet order).
- Source revisions pinned and resolved 2026-09-19:
  - `Misraj/Misraj-DocOCR` @ `7177bf70f77ce259890d6af0bef53f18faf26ec9` (license: apache-2.0)
  - `Misraj/KITAB_pdf_to_markdown_reviewed` @ `8890d721c660cd027839bc8bc48634552fe7aec6` (license: apache-2.0)
- Page IDs are stable: `MISRAJ-0001`..`MISRAJ-0400`, `KITAB-R-0001`..`KITAB-R-0062`. Canonical order is sorted by page ID (deterministic).
- Images are byte-identical PNG exports from the source parquet; ground truth is the reviewed markdown from the dataset, UTF-8, unmodified.
- `loay/arabic-ocr-synthetic-scans-faker-300k` was planned as a third source in an early draft and was **explicitly excluded** from the frozen corpus by protocol (reserved for a possible separate robustness track).
- Machine-readable provenance: `manifests/provenance.json`, `manifests/export_records.json` (per-page source row/UUID, image and GT SHA-256), `manifests/pinned_source_state.json`.
- Integrity report at build time (`manifests/dataset_integrity_report.json`): 0 problems; 1 informational warning — MISRAJ-0109 contains English content (authentic dataset composition, retained unaltered; the page's `language` field records this).

Canonical manifest: `manifests/canonical_manifest.json`, SHA-256
`053225b08d9e027f45085f120920b58af6d7adc4b149d74db50f0c289ca7ef40` (declared in `canonical_manifest.sha256`).

## 2. Fairness policy (frozen v1.0, `runtime/docs/fairness.md`)

1. **Direct measurement.** Each model is measured directly on the frozen 462-page set. No Clouda component is involved at any stage.
2. **Same input for everyone.** Every model receives the byte-identical page image from the frozen export — no resize, no enhancement, no deskew, no re-encode.
3. **Documented prompts only.** A model's prompt is its own documented OCR invocation (recorded verbatim with source in `configs/models/*.yaml`). Where no prompt is documented the field is `UNRESOLVED` and the model is **not run** until resolved. Prompts are never invented or borrowed from another model family.
4. **No differential post-processing.** Documented model-specific output handling (e.g. amad-vlm5/vlm6 thinking-block handling: keep only the text after the last `</think>`, exactly as the model card instructs) is applied only to that model and is recorded. Beyond documented handling, no model receives extra correction, retries, restoration, or cleanup that others do not. The retry policy is identical for all models and recorded in each run state (`max_retries=0` for all runs in this release).
5. **Raw output is sacred.** Raw model output is stored once, atomically, and never modified. Normalization happens in a separate track (`results/normalized/`, `normalized_output` field) and is deterministic, versioned (v1.0.0), and applied identically to predictions and ground truth.
6. **One model at a time** per GPU for the official runs.
7. **Holdout discipline.** The 462 pages are evaluation-only data: never used to optimize prompts against their ground truth, never exposed as GT to a model, never used for any later product purpose.

## 3. Model registry and prompts

All ten registered models have pinned 40-hex HF revisions (resolved 2026-09-19). Prompts actually used per run (recorded in each `run_state.json` and in the registry YAMLs):

### Evaluated models (ran official runs)

| Model | Prompt (verbatim) | Decoding actually used |
|---|---|---|
| amad-iq/amad-vlm6 | `Extract the text in the image. Give me the final text, nothing else.` (model card quickstart) | greedy (`do_sample=false`), `max_new_tokens=4096`, `repetition_penalty=1.05`; documented thinking-block handling |
| amad-iq/amad-vlm5 | same as amad-vlm6 (same lineage) | same as amad-vlm6 |
| tencent/HunyuanOCR | `提取文档图片中正文的所有信息用markdown格式表示，其中页眉、页脚部分忽略，表格用html格式表达，文档中公式用latex格式表示，按照阅读顺序组织进行解析。` (model card locked `doc_parse` task prompt) | temperature 0.0 → greedy, `max_new_tokens=8192`, `repetition_penalty=1.08` (top_p/top_k dropped under greedy) |
| YasserSami/Qari-OCR-0.4.0-VL-4B-Instruct | `Free OCR.` (model card quickstart) | `max_new_tokens=8192` (greedy) |
| MBZUAI/AIN | `Extract all text from the image.` (resolved during the resumed session; not documented on the model card — two prompt candidates were smoke-tested, both passed, and the selected prompt is recorded verbatim in the run state) | `max_new_tokens=8192` (greedy) |
| context212/alhazen-ocr | `Extract all the text from this image, preserving the original reading order.` (model card) | temperature 0.0 → greedy, `max_new_tokens=8192` |
| hastyle/olmOCR-arabic-lora-v2 | olmOCR `build_no_anchoring_v4_yaml_prompt()` string (documented upstream invocation) | `temperature=0.1, do_sample=true`, `max_new_tokens=8192` (the invocation documented by its upstream card) |
| AhmedZaky1/DIMI-Arabic-OCR-V2 | `استخرج النص العربي والأرقام الموجودة في هذه الصورة بدقة عالية.` (model card) | `max_new_tokens=8192` (greedy) |

Adapter-based models (Qari-OCR, alhazen-ocr, olmOCR-arabic-lora-v2, DIMI-Arabic-OCR-V2) ran on their pinned base checkpoints (`Qwen/Qwen3-VL-4B-Instruct` @ `ebb281ec70b05090aa6165b016eac8ec08e71b17`, `unsloth/Qwen3-VL-2B-Instruct` @ `c033353209356cf00d986d05c89a01c94b94c4a1`, `Qwen/Qwen3-VL-4B-Instruct` for the olmOCR adapter), unquantized bf16; base pins are recorded in `configs/base_model_pins.json`.

### Failed models (execution evidence, not registry speculation)

| Model | Prompt attempted (verbatim) | Exactly what failed |
|---|---|---|
| loay/Arabic-OCR-DeepSeek-OCR-2 | `Free OCR` (model card) | model never loaded: smoke 5/5 `MODEL_LOAD_ERROR` (`StrictDataclassFieldValidationError`), three smoke attempts including two transformers-version retries, full run 462/462 `MODEL_LOAD_ERROR` (`ValueError`), 0 successful pages |
| sherif1313/Arabic-GLM-OCR-v2 | `Text Recognition:` (model card) | smoke run never completed: first attempt 5×`FAIL` (`FileNotFoundError` — page images not yet present on that server), retry recorded 2/5 pages PASS then abandoned; a controller-level attempt failed earlier with `KeyError: 'auto'` (dtype handling in the engine build); no full run started |

## 4. Inference environments (frozen)

**Session 1 (2026-09-19 → 09-20)** — as recorded in the benchmark's frozen GPU runtime record (summarized here; the raw record is withheld from the release because it embeds the rental instance's local venv path):

- GPU: single **NVIDIA L40S** (46,068 MiB), driver 580.178.04, CUDA driver 13.0
- Host: Ubuntu 24.04 (Linux 6.8.0-1063-aws), x86_64, 124 GB RAM
- Python 3.12.11 (GPU venv); key packages: torch 2.8.0+cu128, torchvision 0.23.0+cu128, transformers 5.17.0, accelerate 1.15.0, peft 0.18.1, tokenizers 0.23.2, safetensors 0.8.0, pillow 12.3.0, numpy 1.26.4
- `hunyuan_vl` model support verified native in transformers 5.17.0 on 2026-09-19

**Session 2, resumed (2026-09-23 → 09-24)** — second server, second orchestration layer:

- GPU: **NVIDIA H200** (per-page records carry `gpu_name`); Python 3.12 venv; same pinned model revisions and runner code
- More than one candidate executed on the host at times; the controller recorded **`timing_class: CONTENDED_NON_CANONICAL`** for this session. Runtime/speed measurements are **out of scope for this public release** and are not published; this GPU detail is retained for reproducibility only
- MBZUAI/AIN's OCR invocation was resolved in this session and validated with two 5-page smokes before its full run (see §3)

Both sessions used the same engine (`benchmark.runners.hf_engine.HfVlmEngine` via `scripts/run_official.py`): `device_map=cuda:0`; **no quantization, no CPU offload**; attention backend default SDPA; images passed to each model's own processor unmodified (PIL, opened read-only). Preparation/CI environment (CPU-only): Python 3.12, packages pinned in `runtime/requirements.lock`; GPU-phase pins in `runtime/requirements-gpu.lock`.

Per-page records in both sessions store: GPU name, dtype, input image dimensions, start/end timestamps, model revision, prompts hashes, and the four quality metrics. The benchmark also collected per-page elapsed time and peak VRAM internally; those runtime fields are **redacted from this public release** (speed is out of scope — see `REPRODUCIBILITY.md` §7).

## 5. Run procedure

1. **Smoke gate:** each model first ran the fixed 5-page smoke set (`configs/smoke_set.json`: MISRAJ-0166, KITAB-R-0002, MISRAJ-0084, MISRAJ-0216, MISRAJ-0185 — chosen to cover clean text, medium-quality scans, dense TOC, tables, and two-column academic layout). Actual peak VRAM was measured before committing to the full run. MBZUAI/AIN, whose card documents no OCR prompt, was validated with two 5-page smokes (one per prompt candidate) before its full run.
2. **Full run:** one model at a time over all 462 pages in deterministic manifest order, resumable, each per-page record written atomically (tmp + rename) and never overwritten; zero retries configured; no per-page timeout.
3. **Scoring at run time:** for each PASS page, the runner computes `score_page(gt, raw_output)` (raw + normalized tracks) and stores the per-page metrics in the record; the normalized transcription is additionally written to `results/normalized/<run>/<page_id>.txt`.
4. **Post-run reporting:** aggregates are computed from the stored per-page records only (no re-inference) by `runtime/benchmark/reporting/reports.py`; stored aggregate reports are in `results/reports/`.
5. **Ranking:** quality ranking uses normalized-track CER/WER over stored outputs only.

**Two sessions, one queue.** Session 1 (09-19/20, L40S) completed four candidates and stopped partway into alhazen-ocr (compute budget). Session 2 (09-23/24, H200) resumed alhazen-ocr, resolved and ran MBZUAI/AIN, and attempted the remaining queue: DIMI-Arabic-OCR-V2 and olmOCR-arabic-lora-v2 ran partially and were ended by user-authorized controlled stops (worker SIGTERM; stop records classify them `EARLY_STOPPED_NONCOMPETITIVE`, `full_462_result: false` — more than one candidate was on the host at times), DeepSeek-OCR-2 failed model loading (see §3), and Arabic-GLM-OCR-v2 never completed its smoke. Every session-2 run used the identical frozen manifest and runner code; the sanitized controller status and logs are preserved under `results/orchestrator_resumed/`, and the full timeline is in [`RUN_HISTORY.md`](RUN_HISTORY.md).

## 6. Metrics

Definitions (exact code: `runtime/benchmark/metrics/cer_wer.py`, `aggregate.py`, `text_normalization.py`):

- **CER** = `levenshtein(reference_chars, hypothesis_chars) / len(reference_chars)`, computed on Unicode codepoints.
- **WER** = `levenshtein(reference_words, hypothesis_words) / len(reference_words)`, words = whitespace-separated tokens.
- **Normalization policy v1.0.0** (applied identically to prediction and GT; never mutates stored raw output):
  1. NFC canonical composition
  2. remove zero-width and bidi control characters (U+200B–U+200F, U+202A–U+202E, U+2066–U+2069, U+FEFF)
  3. fold Arabic presentation forms (U+FB50–U+FDFF, U+FE70–U+FEFF) to base letters via per-character NFKC
  4. Arabic decimal separator U+066B → `.` and thousands separator U+066C → `,`, **only between digits**
  5. unify newlines (`\r\n`, `\r` → `\n`)
  6. collapse runs of space/tab/VT/FF/CR to a single space
  7. collapse 3+ consecutive newlines to a paragraph break (`\n\n`); trim ends
- **Deliberately NOT normalized** (documented decisions, to avoid hiding OCR errors): Latin letter case; hamza variants (أ/إ/آ/ء); taa marbuta vs haa; yaa vs alif maqsura; Arabic-Indic vs ASCII digits; punctuation identity; markdown structure characters (`#`, `*`, `|`, `-`).
- **Special cases:** empty ref + empty hyp → 0.0; exactly one empty → 1.0 (empty output is never rewarded). Error ratios are **not capped at 1.0** — insertion-heavy failures legitimately exceed the reference length and are scored as-is.
- **Aggregation:** macro mean over per-page metrics of PASS pages, in manifest order. (The benchmark also computed timing aggregates internally; runtime is out of scope for this release and those fields are redacted — see `REPRODUCIBILITY.md` §7.)

Both raw and normalized tracks are reported for every metric. The **normalized track is the primary ranking key** (`mean_cer_normalized`); the raw track is published alongside because format-inflated raw outputs (markdown/HTML/lap-of-luxury repetition) are model behaviors readers should see.

## 7. Verification and integrity

- Manifest SHA-256 verified against `canonical_manifest.sha256`.
- All 462 ground-truth files and all 462 page images hash-match the manifest (`ground_truth_sha256`, `image_sha256`).
- Every run record carries: `model_revision` (cross-checked against the registry pin), `prompt_hash`, `generation_config_hash`, manifest SHA-256 (in `run_state.json`), and the run ID (deterministic from the run config). Every run state in both sessions records the identical canonical manifest hash.
- Zero `.tmp-*` partial files existed at each stop; per-page writes are atomic.
- The public leaderboard numbers were additionally recomputed offline from the stored per-page records with an independent re-implementation of the canonical scorer: every per-page metric matched the stored value with max |Δ| = 0.0, and recomputed aggregates matched the stored reports (for the resumed-session run, recomputed AIN aggregates matched its stored report to ≤ 8.9e-16). Procedure in [`REPRODUCIBILITY.md`](REPRODUCIBILITY.md).
