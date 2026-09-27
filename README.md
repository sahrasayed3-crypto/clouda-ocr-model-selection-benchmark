# Clouda OCR — Arabic OCR Model Selection Benchmark

**Clouda OCR evaluated existing OCR/VLM models to compare Arabic OCR quality, robustness, and speed for model selection.**

This repository publishes that evaluation in full: the frozen 462-page benchmark corpus (manifest, ground truth, and checksums), the complete per-page records for every completed run, the exact scorer and runner code, the pinned model revisions and prompts, and a full provenance/licensing record for reproducibility.

- Project page: https://cloudaocr.xyz
- Contact: contact@cloudaocr.xyz

**Version:** 1.0.0 (public release of the model-selection benchmark; run window 2026-09-19 → 2026-09-24 UTC, two sessions)

---

## 1. What was measured

Each model transcribed **462 Arabic document page images** (single-image, page-level OCR). Pages are real scanned/photographed document pages (books, journals, forms, tables, dense multi-column layouts) exported byte-identically from two public Apache-2.0 Hugging Face datasets:

| Subset | Source dataset | Pages |
|---|---|---:|
| MISRAJ | [Misraj/Misraj-DocOCR](https://huggingface.co/datasets/Misraj/Misraj-DocOCR) | 400 |
| KITAB-R | [Misraj/KITAB_pdf_to_markdown_reviewed](https://huggingface.co/datasets/Misraj/KITAB_pdf_to_markdown_reviewed) | 62 |
| **Total** | | **462** |

No images were resized, enhanced, distorted, or re-encoded: every model received the byte-identical page image. Ground truth is the reviewed markdown transcription shipped with each source dataset, used unmodified.

The corpus was frozen before any inference. Manifest SHA-256:
`053225b08d9e027f45085f120920b58af6d7adc4b149d74db50f0c289ca7ef40`

## 2. Registered candidates and their evidence-backed statuses

**Ten OCR/VLM models were registered as candidates in this model-selection process.** All ten were prepared before inference: Hugging Face revision pinned (resolved 2026-09-19), the model card fetched and archived, and the OCR invocation recorded verbatim where the card documents one (see `configs/models/*.yaml` and METHODOLOGY §3). The benchmark ran in two sessions on two servers (see `RUN_HISTORY.md`): **2026-09-19 → 09-20** (four single-model runs on one NVIDIA L40S, then a compute-budget controlled stop) and **2026-09-23 → 09-24** (resumed session on an NVIDIA H200, in which the remaining candidates were attempted). Final outcome: **five candidates completed all 462 pages**, three were stopped partway (classified `EARLY_STOPPED_NONCOMPETITIVE`, unranked), one failed model loading, and one never completed its smoke test.

### 2.1 Evaluated candidates (executed official benchmark runs)

| Model | Revision | Pages completed | Status |
|---|---|---:|---|
| amad-iq/amad-vlm6 | `7daf90cd5e5706173e159c88ca4e6dc2475a485e` | 462/462 | COMPLETE |
| amad-iq/amad-vlm5 | `bb481308f8776cb7e6e5a12f2cca448ab528b89c` | 462/462 | COMPLETE |
| tencent/HunyuanOCR | `47644ecc4fc854efa4f505155158831f36773ee4` | 462/462 | COMPLETE |
| YasserSami/Qari-OCR-0.4.0-VL-4B-Instruct | `2bd09259f868a77cdbfe35fc1dab40dc5c0a7716` | 462/462 | COMPLETE |
| MBZUAI/AIN | `20fc39f8c3cf97afea0ee8e47f43702239edb70d` | 462/462 | COMPLETE (resumed session) |
| context212/alhazen-ocr | `110b461e2389c97f68a1310370afeebb4a0b381f` | **401/462** | PARTIAL / EARLY_STOPPED_NONCOMPETITIVE — UNRANKED |
| AhmedZaky1/DIMI-Arabic-OCR-V2 | `8a7a293343fc91a6427a8c7a3ce69352870ea8a1` | **132/462** | PARTIAL / EARLY_STOPPED_NONCOMPETITIVE — UNRANKED |
| hastyle/olmOCR-arabic-lora-v2 | `f436e9a0abc93fc5d31231c294fbc40c6965106f` | **188/462** | PARTIAL / EARLY_STOPPED_NONCOMPETITIVE — UNRANKED |

Every completed run produced 462/462 PASS records with zero failures and zero retries. Every executed candidate except MBZUAI/AIN passed a 5-page smoke run first; AIN's invocation (not documented on its model card) was resolved during the resumed session and validated with two 5-page smoke runs before its full run (both PROMPT candidates passed; see METHODOLOGY §3). The three partial runs were ended by user-authorized controlled stops and are excluded from the leaderboard; their stops are described with the exact recorded wording in `RESULTS.md` §3.

### 2.2 Failed candidates

| Model | Revision | Pages | Status |
|---|---|---:|---|
| loay/Arabic-OCR-DeepSeek-OCR-2 | `3b279774135bf21835e2bfe6071663f5da227e1c` | 0/462 | FAILED_INCOMPATIBLE (model failed to load on every page; three smoke attempts also failed) |
| sherif1313/Arabic-GLM-OCR-v2 | `8c77ea85ff2b3ee29d5fb867ab2397e4418cf491` | 0/462 | FAILED_SMOKE (smoke run never completed — best attempt recorded 2/5 pages; no full run started) |

Both failures are backed by stored per-page error records and reports (`results/per_page_records/`, `results/reports/`); the exact technical errors are quoted in `RESULTS.md` §4. These are observed execution failures, not speculations from registry notes.

### 2.3 Not executed

No candidate ends the benchmark unexecuted: all ten registered candidates were either completed, stopped partway, or failed as above. (MBZUAI/AIN was initially held back on 2026-09-20 pending an OCR-prompt decision and was subsequently resolved and run, as reflected above.)

## 3. Primary leaderboard — complete 462/462 runs only

Ranked by the benchmark's canonical primary metric, **mean per-page Normalized Arabic CER** (lower is better). All values are **ratios** (0.4055 = 40.55%); percentages are shown for readability only. Metrics are macro-averages over all 462 per-page scores, recomputed and verified from the stored per-page records.

| Rank | Model | Valid pairs | Norm. Arabic CER | CER (raw) | Norm. WER | WER (raw) |
|---:|---|---:|---:|---:|---:|---:|
| 1 | amad-iq/amad-vlm6 | 462/462 | **0.4055** (40.55%) | 0.4086 (40.86%) | 0.5340 (53.40%) | 0.5360 (53.60%) |
| 2 | amad-iq/amad-vlm5 | 462/462 | 0.4062 (40.62%) | 1.0498 (104.98%) | 0.5425 (54.25%) | 0.5442 (54.42%) |
| 3 | tencent/HunyuanOCR | 462/462 | 0.4346 (43.46%) | 0.4381 (43.81%) | **0.5172 (51.72%)** | **0.5174 (51.74%)** |
| 4 | YasserSami/Qari-OCR-0.4.0-VL-4B-Instruct | 462/462 | 2.1634 (216.34%) | 2.1410 (214.10%) | 2.7285 (272.85%) | 2.7319 (273.19%) |
| 5 | MBZUAI/AIN | 462/462 | 2.1769 (217.69%) | 2.5003 (250.03%) | 2.4533 (245.33%) | 2.4561 (245.61%) |

Notes the reader should not skip:

- **Error rates are not capped at 1.0.** Insertion-heavy failures (e.g. repetition loops on a subset of pages) can push a page's edit distance beyond the reference length, and these pages are scored as-is. amad-vlm5's raw CER mean (1.0498) is driven by such a tail; its normalized-track mean is 0.4062. Qari-OCR's high means come from a recorded repetition-loop tail (54/462 pages with normalized CER > 1.0; maximum 108.98), and AIN shows a similar recorded tail (46/462 pages with normalized CER > 1.0; maximum 109.53) — genuine recorded behaviors of these models on this corpus, not scoring artifacts.
- **tencent/HunyuanOCR has the lowest WER but not the lowest CER.** Its OCR prompt is a *document-parse* prompt (markdown body-text extraction; tables as HTML, formulas as LaTeX), which shapes its output format; CER/WER are computed on plain text. Both metrics are published so readers can see this.
- **MBZUAI/AIN's prompt was not documented on its model card.** It was resolved during the resumed session ("Extract all text from the image.", recorded in its run state) and validated with two 5-page smoke runs before the full run.
- Models that did not complete all 462 pages are **not ranked**. The three partial runs are reported separately in [`RESULTS.md`](RESULTS.md) §3 and [`RUN_HISTORY.md`](RUN_HISTORY.md).

## 4. Runtime data: out of scope for this release

The benchmark collected per-page wall-clock timing and VRAM measurements internally, and the resumed session's controller recorded its execution-time conditions as `CONTENDED_NON_CANONICAL`. **Speed is not a published result of this release**: no seconds-per-page, runtime, or VRAM figures appear anywhere in this repository, and no speed comparisons are made — between models, sessions, or GPUs. Hardware details are retained only where needed for reproducibility (see `METHODOLOGY.md` §4 and `REPRODUCIBILITY.md` §1, §7).

## 5. Metric definitions

- **CER (character error rate)** = character-level Levenshtein distance between prediction and reference ÷ reference character length (codepoint-level).
- **WER (word error rate)** = word-level Levenshtein distance ÷ reference word count, where words are whitespace-separated tokens.
- **Normalized track** applies a deterministic, versioned Arabic-aware normalization policy (v1.0.0) **identically to prediction and ground truth** before scoring: NFC, removal of zero-width/bidi controls, folding of Arabic presentation forms, Arabic decimal/thousands separator unification between digits, newline unification, whitespace-run collapse, and end-trimming. Letter case, hamza variants, Arabic-Indic vs ASCII digits, punctuation identity, and markdown structure characters are deliberately **not** normalized, so genuine OCR errors are never hidden.
- Aggregation is the **macro mean over per-page scores** of PASS pages.
- Special cases: empty-vs-empty → 0.0; one side empty → 1.0 (empty output is never rewarded).

Exact implementation: [`runtime/benchmark/metrics/cer_wer.py`](runtime/benchmark/metrics/cer_wer.py), [`runtime/benchmark/text_normalization.py`](runtime/benchmark/text_normalization.py), [`runtime/benchmark/metrics/aggregate.py`](runtime/benchmark/metrics/aggregate.py).

## 6. Protocol highlights (full version in [`METHODOLOGY.md`](METHODOLOGY.md))

- **Direct measurement only.** No Clouda pipeline component was involved at any stage — each model was measured as-shipped, from its pinned Hugging Face revision, with its own documented prompt.
- **Same input for everyone.** Byte-identical page images; no resize/enhance/deskew/re-encode.
- **Documented prompts only.** Prompts are quoted verbatim from each model card in `configs/models/*.yaml` with their source; nothing was invented or borrowed between model families.
- **No differential post-processing.** Model-specific documented handling (e.g. amad thinking-block handling after the last `</think>`) is part of that model's documented invocation and is recorded. Raw output is stored once, atomically, and never modified; normalization lives in a separate track.
- **Greedy decoding** (temperature 0.0 → `do_sample=false`) with fixed `max_new_tokens` per run, zero retries, no per-page timeout — with two recorded exceptions: olmOCR-arabic-lora-v2 used its card-documented `temperature=0.1, do_sample=true` (partial run), and during the resumed session more than one candidate was on the host at times.
- **Holdout discipline.** The 462 pages are evaluation-only data and were never used to optimize anything.

## 7. What is in this repository

```
├── README.md, METHODOLOGY.md, RESULTS.md, RUN_HISTORY.md,
│   REPRODUCIBILITY.md, DATA_NOTICE.md, LIMITATIONS.md, CHECKSUMS.txt
├── manifests/            canonical 462-page manifest (+sha256), per-page export
│                         records, provenance/licensing, pinned source state
├── configs/              10 pinned model registry YAMLs, smoke set,
│                         base-model pins, preflight record
│                         (frozen environment summary: METHODOLOGY §4)
├── ground_truth/         462 ground-truth markdown files (Apache-2.0 sources)
├── results/              per-page records (per model), stored aggregate reports,
│                         normalized-track outputs, per-run event logs,
│                         sanitized resumed-session orchestration evidence
├── summaries/            FINAL_RESULTS.{csv,md}, MODEL_STATUS.csv
└── runtime/              the complete benchmark runner/scorer code, tests,
                          scripts, fairness policy, pinned requirements
```

Page **images are not redistributed** in this repository (≈608 MB); their SHA-256 hashes are in the manifest and a refetch procedure against the pinned source revisions is documented in [`REPRODUCIBILITY.md`](REPRODUCIBILITY.md). See [`DATA_NOTICE.md`](DATA_NOTICE.md).

## 8. Verification

`CHECKSUMS.txt` contains a SHA-256 for every file in this repository. Verify with:

```bash
sha256sum -c CHECKSUMS.txt
```

All leaderboard numbers in this README were recomputed offline from the stored per-page records with an independent re-implementation of the canonical scorer and matched the benchmark's own stored aggregates exactly (max per-page |Δ| = 0.0). See [`REPRODUCIBILITY.md`](REPRODUCIBILITY.md) for the recomputation procedure.

## 9. Limitations

Results are specific to this 462-page corpus, protocol, and hardware and must not be read as universal OCR rankings. Key limitations (full list in [`LIMITATIONS.md`](LIMITATIONS.md)):

- 5 of the 10 registered candidates completed the full corpus; three partial runs (classified `EARLY_STOPPED_NONCOMPETITIVE`, unranked) and two failed candidates (one incompatible, one smoke-incomplete) are disclosed with evidence, so the ranked comparison is over the five complete runs only.
- CER/WER on plain text penalize format divergence (e.g. markdown/HTML output styles) unevenly across models.
- **Runtime/speed measurements are out of scope for this release** and are not published; hardware details appear only for reproducibility.
- Ground truth is dataset-provided reviewed markdown, not a fresh double-annotated reference.

## 10. Licensing and attribution

- Benchmark **code** in `runtime/`: released under the Apache License 2.0 (see [`runtime/LICENSE`](runtime/LICENSE)).
- **Ground truth and page content** derive from `Misraj/Misraj-DocOCR` and `Misraj/KITAB_pdf_to_markdown_reviewed`, both published under **Apache-2.0** at the pinned revisions; attribution and license notices are preserved in [`DATA_NOTICE.md`](DATA_NOTICE.md) and `manifests/provenance.json`.
- Each evaluated **model's own license** is recorded verbatim in its registry YAML (e.g. `tencent/HunyuanOCR` is under the Tencent Hunyuan Community License, which is not an open-weight license); this repository distributes no model weights.

## 11. Citation

If you use this benchmark, please cite it (DOI to be minted with the archived release):

> Clouda OCR. (2026). *Clouda OCR — Arabic OCR Model Selection Benchmark: 462-page frozen evaluation of open OCR/VLM models on Arabic document OCR* (v1.0.0) [Data set + code]. Zenodo. DOI: TBD.

And the underlying corpus:

> Misraj. *Misraj-DocOCR* and *KITAB_pdf_to_markdown_reviewed* (revisions pinned in `manifests/provenance.json`), Apache-2.0.

## 12. Disclaimer

This benchmark was produced as an internal model-selection study and is released as-is, without modification of any recorded result. Partial and failed candidates are disclosed as such; no claim of state-of-the-art or universal superiority is made for any model, including on the basis of these results.
