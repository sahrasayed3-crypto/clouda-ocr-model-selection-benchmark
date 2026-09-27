# Results — 462-Page Model-Selection Benchmark

All values below are taken from the benchmark's own stored aggregates (`results/reports/*.json`) and were **independently re-verified offline** from the stored per-page records (see `REPRODUCIBILITY.md`). Error metrics are **ratios** (0.4055 = 40.55%); percentages in parentheses are for readability only. Run window: **2026-09-19 → 2026-09-24 UTC**, across two sessions on two servers (see `RUN_HISTORY.md`). Only OCR quality metrics are published — runtime/speed measurements are out of scope for this release (see `REPRODUCIBILITY.md` §7).

## 1. Primary leaderboard — complete runs only (462/462 valid pairs)

Ranked by **mean per-page Normalized Arabic CER** (the benchmark's canonical primary metric; lower is better).

| Rank | Model | HF revision | Valid | Norm. CER | CER (raw) | Norm. WER | WER (raw) |
|---:|---|---|---:|---:|---:|---:|---:|
| 1 | amad-iq/amad-vlm6 | `7daf90cd5e5706173e159c88ca4e6dc2475a485e` | 462/462 | **0.405471** | 0.408645 | 0.533982 | 0.536017 |
| 2 | amad-iq/amad-vlm5 | `bb481308f8776cb7e6e5a12f2cca448ab528b89c` | 462/462 | 0.406228 | 1.049789 | 0.542530 | 0.544223 |
| 3 | tencent/HunyuanOCR | `47644ecc4fc854efa4f505155158831f36773ee4` | 462/462 | 0.434648 | 0.438131 | **0.517221** | **0.517424** |
| 4 | YasserSami/Qari-OCR-0.4.0-VL-4B-Instruct | `2bd09259f868a77cdbfe35fc1dab40dc5c0a7716` | 462/462 | 2.163387 | 2.140999 | 2.728452 | 2.731869 |
| 5 | MBZUAI/AIN | `20fc39f8c3cf97afea0ee8e47f43702239edb70d` | 462/462 | 2.176870 | 2.500256 | 2.453322 | 2.456118 |

Reading notes (also in the README; repeated here so the table is never read alone):

- Error ratios are not capped at 1.0 — insertion-heavy failure tails (repetition loops on a minority of pages) are scored as-is.
- amad-vlm5's raw-track CER mean (1.0498) is dominated by such a tail (23/462 pages with normalized CER > 1.0, max raw page CER 308.57); its normalized-track mean is 0.4062 and its median per-page normalized CER is 0.176.
- Qari-OCR's high means come from a recorded repetition-loop tail: 54/462 pages with normalized CER > 1.0 (max 108.98); its median per-page normalized CER is 0.192. AIN shows a similar recorded tail: 46/462 pages with normalized CER > 1.0 (max 109.53); median 0.608. These are genuine recorded behaviors of the models on this corpus, not scoring artifacts.
- tencent/HunyuanOCR leads on both WER tracks but not on CER; its prompt is a document-parse prompt (markdown body text, tables as HTML, formulas as LaTeX), which affects plain-text CER/WER differently. Both tracks are published.
- **MBZUAI/AIN's OCR prompt is not documented on its model card.** It was resolved during the resumed session ("Extract all text from the image.", recorded verbatim in the run state) and validated with two 5-page smoke runs before the full run.
- The gap between ranks 1 and 2 on the primary metric (0.405471 vs 0.406228) is small; ranks are reported, not significance-tested. Ranks 4 and 5 (2.1634 vs 2.1769) are likewise close.

## 2. Runtime data: out of scope

The benchmark collected per-run timing and VRAM measurements internally, and the resumed session's controller recorded its execution-time conditions as `CONTENDED_NON_CANONICAL`. Speed is **not a published result** of this release: no per-model runtime or VRAM figures appear in this repository and no speed comparisons are made. Hardware details retained for reproducibility only are in `METHODOLOGY.md` §4.

## 3. Partial runs — PARTIAL / EARLY_STOPPED_NONCOMPETITIVE / UNRANKED — NOT comparable to the table above

Three candidates were stopped partway by user-authorized controlled stops and are excluded from the leaderboard. All recorded pages are PASS; each run directory carries a stop record with the classification `EARLY_STOPPED_NONCOMPETITIVE`, `full_462_result: false`, and `timing_class: CONTENDED_NON_CANONICAL`. **These numbers must not be read as 462-page results.**

| Model | Valid | Norm. CER | CER (raw) | Norm. WER | WER (raw) | Status |
|---|---:|---:|---:|---:|---:|---|
| context212/alhazen-ocr | 401/462 | 6.650819 | 6.583623 | 7.018676 | 7.018951 | PARTIAL / EARLY_STOPPED_NONCOMPETITIVE — UNRANKED |
| hastyle/olmOCR-arabic-lora-v2 | 188/462 | 0.818020 | 0.821075 | 1.020268 | 1.021254 | PARTIAL / EARLY_STOPPED_NONCOMPETITIVE — UNRANKED |
| AhmedZaky1/DIMI-Arabic-OCR-V2 | 132/462 | 0.985716 | 0.981777 | 0.926597 | 0.927402 | PARTIAL / EARLY_STOPPED_NONCOMPETITIVE — UNRANKED |

Exactly as recorded in the artifacts (no additional interpretation):

- **context212/alhazen-ocr** — the orchestrator state records: *"Controlled ownership handoff authorized by user; Alhazen partial preserved and excluded from competitive 462-page results."* (status `EARLY_STOPPED_NONCOMPETITIVE`, `full_462_result: false`). The run consists of a 09-20 leg (25 pages, stopped by the session-1 compute-budget stop) and a 09-23/24 resume to 401 pages (last completed page MISRAJ-0339). Its preserved partial quality is poor (median per-page normalized CER 0.992; 79/401 pages with normalized CER > 1.0; max 382.69).
- **AhmedZaky1/DIMI-Arabic-OCR-V2** — the controller terminated the worker (`returncode: -15`, i.e. SIGTERM) at 2026-09-24T11:03:11Z; the run's stop record (`partial_stop_metadata.json`) records `status: EARLY_STOPPED_NONCOMPETITIVE`, `full_462_result: false`, `timing_class: CONTENDED_NON_CANONICAL`, `stop_timestamp: 2026-09-24T11:05:39Z`, 132 successful pages, 0 failed pages.
- **hastyle/olmOCR-arabic-lora-v2** — same mechanism: worker `returncode: -15` at 2026-09-24T11:03:11Z; stop record with `EARLY_STOPPED_NONCOMPETITIVE`, `full_462_result: false`, 188 successful pages, 0 failed pages.

No artifact states that these runs were stopped *because of* poor OCR quality; the recorded classifications and the preserved partial quality statistics are both given above so readers can judge from the evidence.

## 4. Failed candidates — no benchmark result exists

| Model | Pages | Status | Exactly what the artifacts record |
|---|---:|---|---|
| loay/Arabic-OCR-DeepSeek-OCR-2 | 0/462 | **FAILED_INCOMPATIBLE** | smoke run: 5/5 pages `MODEL_LOAD_ERROR` (`StrictDataclassFieldValidationError`); three smoke attempts (including two transformers-version retries, `v446`/`v517`) all failed; full run: **462/462 pages `MODEL_LOAD_ERROR` (`ValueError`), 0 successful pages** (stored report: `failure_rate: 1.0`). The model never produced a single transcription. |
| sherif1313/Arabic-GLM-OCR-v2 | 0/462 | **FAILED_SMOKE** | the 5-page smoke run never completed: first attempt 5×`FAIL` (`FileNotFoundError` — page images not yet present on that server), retry attempt recorded 2/5 pages PASS before being abandoned; a controller-level attempt failed earlier with `KeyError: 'auto'` (dtype handling in the engine build). No full run was ever started. |

Both failures are execution facts stored in per-page records and aggregate reports (`results/per_page_records/`, `results/reports/`) — not inferences from registry notes.

## 5. Smoke runs (5-page gate, not scored for ranking)

Smoke coverage across the benchmark: amad-vlm6, amad-vlm5, tencent/HunyuanOCR, Qari-OCR, alhazen-ocr — 5/5 PASS each; MBZUAI/AIN — two 5-page prompt-candidate smokes, both 5/5 PASS; loay/Arabic-OCR-DeepSeek-OCR-2 — 0/5 (model-load failure, three attempts); sherif1313/Arabic-GLM-OCR-v2 — incomplete (2/5 recorded pages in the final attempt). Smoke records are included under `results/per_page_records/`; they are not part of any leaderboard.

## 6. Failure accounting (all runs)

Across all 3,535 per-page records (18 run directories, both sessions): **3,068 PASS**; the only per-page failures are **467 `MODEL_LOAD_ERROR` records, all from loay/Arabic-OCR-DeepSeek-OCR-2** (one smoke + one full run). There are no FAIL, TIMEOUT, OOM, or INVALID_OUTPUT records from any other model and zero retries. Exactly one PASS record has an empty output (MBZUAI/AIN, MISRAJ-0274) — scored CER 1.0 by the documented empty-output rule and already included in its stored aggregates. The candidate-level outcomes are: **5 COMPLETE, 3 PARTIAL (EARLY_STOPPED_NONCOMPETITIVE, unranked), 1 FAILED_INCOMPATIBLE, 1 FAILED_SMOKE** — all disclosed above with evidence.
