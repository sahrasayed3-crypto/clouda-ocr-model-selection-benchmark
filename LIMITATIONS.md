# Limitations

Read the results in `RESULTS.md` together with these limitations. None of the numbers in this repository were altered, filtered, or re-weighted; the limitations below describe how they should — and should not — be interpreted.

## Scope of the comparison

1. **Corpus-specific.** All results describe behavior on these 462 Arabic document pages under this protocol. They are not universal OCR rankings and make no claim about performance on other languages, domains, page types, or image conditions.
2. **Incomplete candidate coverage.** 5 of the 10 registered candidates completed; three are partial (401/462, 188/462, 132/462 — user-authorized early stops, disclosed, unranked); two failed on execution (one incompatible with the runtime stack, one smoke-incomplete) — all disclosed with evidence. Any "best model" claim is therefore limited to the five completed runs on this corpus.
3. **Single run per model.** Each completed model was run once. No variance/seed studies were performed (decoding was greedy, except olmOCR-arabic-lora-v2's documented `temperature=0.1` sampling in its incomplete partial run), so run-to-run variance is expected to be small but was not measured.
4. **Runtime out of scope.** The benchmark collected per-page timing and VRAM internally, and session 2's controller recorded its execution-time conditions as `CONTENDED_NON_CANONICAL`. Speed is **not a published result**: no runtime or VRAM figures appear in this release, no speed comparisons are made, and hardware details appear only for reproducibility.
5. **Resumed-session prompt provenance.** MBZUAI/AIN's OCR prompt is not documented on its model card; it was resolved during the resumed session and is recorded verbatim in the run state, with two prompt-candidate smokes. The recorded artifacts do not include the text of the authorization decision itself.
6. **Partial-run coverage.** The three partial runs cover different page prefixes of the same frozen order and are mutually incomparable as well as incomparable to the 462-page results; their small/partial samples are additionally dominated in some cases by extreme output-length failures.

## Metric limitations

7. **Plain-text scoring of formatted output.** CER/WER are computed on plain text; models whose documented prompt produces markdown/HTML/LaTeX (e.g. HunyuanOCR's document-parse prompt) are scored on that output as-is. This affects models unevenly; both raw and normalized tracks are published for transparency.
8. **Normalization is conservative by design.** The normalization policy (v1.0.0) only removes differences that cannot be the model's fault (presentation forms, bidi controls, separator codepoints, whitespace). It deliberately does not unify hamza variants, digit systems, or punctuation — so it never hides real errors, but it also leaves format-sensitive errors fully counted.
9. **Uncapped error ratios.** Insertion-heavy failures push per-page CER above 1.0 and macro means inherit that. This is intentional (failures are recorded, not clipped), but it means mean CER/WER are sensitive to a small number of catastrophic pages; median per-page values are provided as context.
10. **Dataset-provided ground truth.** References are the upstream reviewed markdown transcriptions, not a freshly double-annotated reference. Ground-truth conventions (markdown structure, whitespace) influence absolute CER/WER values.
11. **No significance testing.** Ranks are reported as computed. The gap between the top two models on the primary metric (0.405471 vs 0.406228) is small and no statistical significance is claimed.

## Protocol limitations

12. **Documented prompts only.** Each model ran with its own documented invocation where one exists. This is the fairest available "as-shipped" comparison but does not optimize any model's prompt; the single exception is MBZUAI/AIN, whose card documents no OCR prompt and whose invocation was resolved during the resumed session (see item 5).
13. **Model-specific documented post-processing.** The only post-processing applied is what each model's own card documents (e.g. thinking-block handling for the amad models). Cross-model differences in such handling are part of the "as-shipped" comparison, not controlled variables.
14. **Partial runs excluded from ranking.** The three partial runs (401/462, 188/462, 132/462) are published for completeness only and are not comparable to 462-page results or to each other (different page-prefix coverage; some dominated by extreme output-length failures).

## Provenance limitations

15. **Images not redistributed.** Page images are hash-referenced and refetchable byte-identically from the pinned source revisions; if upstream revisions ever disappear, images can be restored from any archive that retains them, but this repository itself does not mirror them.
16. **Hardware identifiers.** Per-page records include the GPU model name of the rented cloud instances used for the runs (recorded by the runner; retained for reproducibility only). GPU UUIDs are redacted (nulled) in the public records and identify no private infrastructure.
17. **Snapshot provenance.** This release was assembled from the benchmark's two preserved final states: the session-1 frozen snapshot (controlled stop, 2026-09-20) and the resumed-session evidence (2026-09-23/24), independently re-verified (manifest hashes, per-page metric recomputation). Operational detail beyond the per-run event logs and the sanitized controller evidence is not part of the release.
