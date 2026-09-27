# Run History — all ten registered candidates, both sessions

This page is the auditable run timeline of the benchmark (all times UTC, from the stored orchestrator state files, run states, per-model attempt logs, and per-page records). It exists so that the state of every registered candidate is unambiguous: which runs are **complete**, which are **partial (early-stopped, unranked)**, and which **failed** (with the exact recorded technical errors). No results were deleted, reset, or edited at any point.

## Session 1 — 2026-09-19 → 2026-09-20 (NVIDIA L40S)

| When (UTC) | Event |
|---|---|
| 2026-09-19 | Corpus frozen (462 pages, manifest SHA-256 `053225b0…ef40`); model registry pinned (10 candidates, revisions resolved); protocol/fairness policy frozen; GPU environment frozen; preflight + dry-run + CPU test suite passed |
| by 2026-09-20 00:31 | tencent/HunyuanOCR full run (462/462 PASS) and 5-page smoke completed in a first session on the same frozen corpus and protocol; included in the official result tree ("pre-orchestrator" run) |
| 2026-09-20 00:31 → 02:14 | amad-iq/amad-vlm6 smoke (5/5 PASS) + full run 462/462 PASS |
| 2026-09-20 02:14 → 04:51 | amad-iq/amad-vlm5 smoke (5/5 PASS) + full run 462/462 PASS |
| 2026-09-20 04:51 → 18:26 | YasserSami/Qari-OCR-0.4.0-VL-4B-Instruct smoke (5/5 PASS) + full run 462/462 PASS (two orchestrator attempts: attempt 1 paused by a server migration at 297/462, all PASS; attempt 2 completed and validated 462/462 at 18:26) |
| 2026-09-20 18:26 → 19:18 | context212/alhazen-ocr full run started; reached 25/462 pages (KITAB-R-0001…0025), all PASS |
| 2026-09-20 ~19:18 | **Controlled stop** (compute budget exhausted). The in-flight page was allowed to finish, workers terminated cleanly, no partial files (atomic writes verified), no results deleted or reset |

## Session 2 (resumed) — 2026-09-23 → 2026-09-24 (NVIDIA H200)

The benchmark was resumed on a second server against the same frozen corpus (every run state records the identical manifest SHA-256 `053225b0…ef40`). Because more than one candidate executed on the host at times, the controller recorded the timing class **`CONTENDED_NON_CANONICAL`** for this session — recorded here as part of the stop classifications below. **Runtime/speed measurements are out of scope for this public release and are not published.**

| When (UTC) | Event |
|---|---|
| 2026-09-23 21:52 | supervisor restart; context212/alhazen-ocr **full attempt 2** resumes from page 26 |
| 2026-09-23 22:32 / 22:38 | MBZUAI/AIN two 5-page prompt-candidate smokes (both 5/5 PASS) — its previously unresolved OCR invocation was resolved to "Extract all text from the image." (recorded verbatim in the run state) |
| 2026-09-23 22:45 → 09-24 04:36 | **MBZUAI/AIN full run 462/462 PASS** |
| 2026-09-24 07:29:48 | alhazen-ocr last completed page (MISRAJ-0339) — **401/462**, all PASS |
| 2026-09-24 07:33:46 | **Ownership handoff GLM → Codex, authorized by user.** Orchestrator state, verbatim: *"Controlled ownership handoff authorized by user; Alhazen partial preserved and excluded from competitive 462-page results."* — alhazen classified `EARLY_STOPPED_NONCOMPETITIVE`, `full_462_result: false` |
| 2026-09-24 07:35:50 | Second controller starts for the four remaining candidates; records `timing_class: CONTENDED_NON_CANONICAL` |
| 2026-09-24 07:36:00 | sherif1313/Arabic-GLM-OCR-v2 worker fails (rc=1, `KeyError: 'auto'` in engine dtype handling); loay/Arabic-OCR-DeepSeek-OCR-2 worker fails (rc=1, model load error) |
| 2026-09-24 07:38 → 10:53 | AhmedZaky1/DIMI-Arabic-OCR-V2 full run — 132/462 pages PASS before termination |
| 2026-09-24 07:39 → 11:02 | hastyle/olmOCR-arabic-lora-v2 full run — 188/462 pages PASS before termination (its documented `do_sample=true, temperature=0.1` invocation) |
| 2026-09-24 ~08:01–08:07 | sherif1313 smoke retry: first attempt had failed 5/5 with `FileNotFoundError` (page images not yet on that server); retry recorded 2/5 pages PASS, then abandoned — smoke never completed |
| 2026-09-24 11:03:11 | Controller terminates the DIMI and olmOCR workers (`returncode: -15`, SIGTERM); each run directory receives a stop record: `status: EARLY_STOPPED_NONCOMPETITIVE`, `full_462_result: false`, `timing_class: CONTENDED_NON_CANONICAL`, `stop_timestamp: 2026-09-24T11:05:39Z` |
| 2026-09-24 11:03:21 | Controller run finished; last evidence upload 11:20 |

## Final state per registered candidate (evidence-backed)

| Model | Pages | Status | Run ID(s) |
|---|---:|---|---|
| amad-iq/amad-vlm6 | 462/462 | **COMPLETE** (all PASS) | `amad-iq-amad-vlm6__full__7ae0bd41__e300109f4`, smoke `…af996eaa` |
| amad-iq/amad-vlm5 | 462/462 | **COMPLETE** (all PASS) | `amad-iq-amad-vlm5__full__679a7b90__e300109f4`, smoke `…53d42047` |
| tencent/HunyuanOCR | 462/462 | **COMPLETE** (all PASS) | `tencent-hunyuanocr__full__def73123`, smoke `…30200dc6` |
| YasserSami/Qari-OCR-0.4.0-VL-4B-Instruct | 462/462 | **COMPLETE** (all PASS) | `…qari…__full__09f6f187__e4ce1736c`, smoke `…30cc9f79` |
| MBZUAI/AIN | 462/462 | **COMPLETE** (all PASS; resumed session) | `mbzuai-ain__full__46808f9e`, smokes `…582ffd73`, `…60798b1c` |
| context212/alhazen-ocr | 401/462 | **PARTIAL / EARLY_STOPPED_NONCOMPETITIVE** (user-authorized controlled stop; 401/401 PASS; UNRANKED) | `context212-alhazen-ocr__full__532ac6c6__effa66a8b` (attempts 1+2), smoke `…76b661f7` |
| hastyle/olmOCR-arabic-lora-v2 | 188/462 | **PARTIAL / EARLY_STOPPED_NONCOMPETITIVE** (worker SIGTERM at controller finish; 188/188 PASS; UNRANKED) | `hastyle-olmocr-arabic-lora-v2__full__6137cb8b__e7963667b` |
| AhmedZaky1/DIMI-Arabic-OCR-V2 | 132/462 | **PARTIAL / EARLY_STOPPED_NONCOMPETITIVE** (worker SIGTERM at controller finish; 132/132 PASS; UNRANKED) | `ahmedzaky1-dimi-arabic-ocr-v2__full__0b9cc407__e596d728a` |
| loay/Arabic-OCR-DeepSeek-OCR-2 | 0/462 | **FAILED_INCOMPATIBLE** (model failed to load on every page; three smoke attempts also failed; 0 transcriptions produced) | `loay-arabic-ocr-deepseek-ocr-2__full__a997b4e1__e1488d635`, smoke `…2dc3d4a0` |
| sherif1313/Arabic-GLM-OCR-v2 | 0/462 | **FAILED_SMOKE** (smoke never completed — best attempt 2/5 pages; no full run started) | `sherif1313-arabic-glm-ocr-v2__smoke__089fb60a` |

## Notes

- **Per-page failures are confined to one run**: the only non-PASS page records in the entire benchmark are the 467 `MODEL_LOAD_ERROR` records of loay/Arabic-OCR-DeepSeek-OCR-2 (one smoke + one full run). No other model recorded a FAIL, TIMEOUT, OOM, INVALID_OUTPUT, or empty output, and no retries occurred anywhere. (One PASS record — MBZUAI/AIN, MISRAJ-0274 — contains an empty output, scored CER 1.0 by the documented empty-output rule.)
- "PARTIAL" refers to coverage: the three partial runs were ended by user-authorized controlled stops before completion. Their stop classifications (`EARLY_STOPPED_NONCOMPETITIVE`, `full_462_result: false`) and preserved quality statistics are quoted in `RESULTS.md` §3; no artifact states that they were stopped *because of* OCR quality.
- Model-level failure *behaviors* (e.g. repetition-loop tails inflating some pages' CER) are output characteristics of the models and are discussed in `RESULTS.md` and `LIMITATIONS.md`; they are not run failures and were never cleaned or filtered.
- The HunyuanOCR full run predates the orchestration layer but ran on the identical frozen corpus (manifest hash recorded in its run state), identical engine settings, and the same validation; its records pass the same integrity checks as the orchestrated runs.
- The resumed session used the same runner code and pinned revisions for every model; its controller status file is preserved (sanitized of server paths) at `results/orchestrator_resumed/`.
