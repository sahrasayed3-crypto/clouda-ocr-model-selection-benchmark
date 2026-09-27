# Final Results — Clouda OCR Arabic OCR Model Selection Benchmark (462 pages)

Machine-readable copies: `FINAL_RESULTS.csv` (quality numbers) and `MODEL_STATUS.csv` (run states).
Full precision and per-page provenance: `results/reports/*.json` and `results/per_page_records/`.

Values are ratios (0.405471 = 40.5471%). Macro mean over per-page scores. The benchmark ran in two sessions (see `RUN_HISTORY.md`); only OCR quality metrics are published — runtime/speed measurements are out of scope for this public release.

## Complete runs (462/462 valid pairs) — ranked by mean per-page Normalized Arabic CER

| Rank | Model | Norm. CER | CER (raw) | Norm. WER | WER (raw) | Session |
|---:|---|---:|---:|---:|---:|---|
| 1 | amad-iq/amad-vlm6 | **0.405471** | 0.408645 | 0.533982 | 0.536017 | 1 |
| 2 | amad-iq/amad-vlm5 | 0.406228 | 1.049789 | 0.542530 | 0.544223 | 1 |
| 3 | tencent/HunyuanOCR | 0.434648 | 0.438131 | **0.517221** | **0.517424** | 1 |
| 4 | YasserSami/Qari-OCR-0.4.0-VL-4B-Instruct | 2.163387 | 2.140999 | 2.728452 | 2.731869 | 1 |
| 5 | MBZUAI/AIN | 2.176870 | 2.500256 | 2.453322 | 2.456118 | 2 |

## Partial runs (PARTIAL / EARLY_STOPPED_NONCOMPETITIVE / UNRANKED)

| Model | Valid | Norm. CER | CER (raw) | Norm. WER | WER (raw) | Status |
|---|---:|---:|---:|---:|---:|---|
| context212/alhazen-ocr | 401/462 | 6.650819 | 6.583623 | 7.018676 | 7.018951 | user-authorized controlled stop ("…excluded from competitive 462-page results"), EARLY_STOPPED_NONCOMPETITIVE |
| hastyle/olmOCR-arabic-lora-v2 | 188/462 | 0.818020 | 0.821075 | 1.020268 | 1.021254 | worker SIGTERM at controller finish; EARLY_STOPPED_NONCOMPETITIVE |
| AhmedZaky1/DIMI-Arabic-OCR-V2 | 132/462 | 0.985716 | 0.981777 | 0.926597 | 0.927402 | worker SIGTERM at controller finish; EARLY_STOPPED_NONCOMPETITIVE |

Not comparable to the 462-page table or to each other (different page-prefix coverage; some dominated by extreme output-length failures).

## Failed candidates (no benchmark result exists)

- **loay/Arabic-OCR-DeepSeek-OCR-2 — FAILED_INCOMPATIBLE:** model failed to load on every page (smoke 5/5 and full run 462/462 `MODEL_LOAD_ERROR`; three smoke attempts including two transformers-version retries); 0 transcriptions produced.
- **sherif1313/Arabic-GLM-OCR-v2 — FAILED_SMOKE:** smoke run never completed (first attempt 5/5 `FAIL` on missing page images; retry recorded 2/5 pages PASS, then abandoned; controller-level engine-build `KeyError: 'auto'`); no full run started.

## Context statistics (recomputed from stored per-page metrics)

| Model | Median page norm. CER | Pages with norm. CER > 1.0 | Max page norm. CER |
|---|---:|---:|---:|
| amad-iq/amad-vlm6 | 0.151 | 17/462 | 9.38 |
| amad-iq/amad-vlm5 | 0.176 | 23/462 | 14.14 |
| tencent/HunyuanOCR | 0.201 | 14/462 | 9.06 |
| YasserSami/Qari-OCR-0.4.0-VL-4B-Instruct | 0.192 | 54/462 | 108.98 |
| MBZUAI/AIN | 0.608 | 46/462 | 109.53 |
| context212/alhazen-ocr (partial) | 0.992 | 79/401 | 382.69 |
| hastyle/olmOCR-arabic-lora-v2 (partial) | 0.300 | 17/188 | 27.07 |
| AhmedZaky1/DIMI-Arabic-OCR-V2 (partial) | 0.243 | 8/132 | 22.85 |

These show that macro means are inflated by a minority of catastrophic pages (repetition loops / extreme over-long outputs) while typical-page medians are often much closer together — the failure tails are genuine recorded model behavior and were scored as-is.
