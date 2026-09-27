# Data Notice — sources, licensing, and redistribution

## 1. Corpus sources

The 462 benchmark pages derive entirely from two public Hugging Face datasets, used at pinned revisions:

| Subset | Source | Revision | Rows used | License (as published on the dataset card at the pinned revision) |
|---|---|---|---|---|
| MISRAJ (400 pages) | [Misraj/Misraj-DocOCR](https://huggingface.co/datasets/Misraj/Misraj-DocOCR) | `7177bf70f77ce259890d6af0bef53f18faf26ec9` | train rows 0–399 | Apache-2.0 |
| KITAB-R (62 pages) | [Misraj/KITAB_pdf_to_markdown_reviewed](https://huggingface.co/datasets/Misraj/KITAB_pdf_to_markdown_reviewed) | `8890d721c660cd027839bc8bc48634552fe7aec6` | train rows 0–61 | Apache-2.0 |

Per-page provenance (source row index, stable UUID where available, image/GT SHA-256, image dimensions) is recorded in `manifests/export_records.json` and `manifests/canonical_manifest.json`. License quotations and attribution notes are in `manifests/provenance.json`, recorded exactly as published on each dataset card ("nothing is inferred").

Attribution: Apache-2.0 requires retaining copyright and license notices. The upstream cards name no attribution requirement beyond Apache-2.0 itself and reference the Misraj-DocOCR paper (arXiv:2509.18174). If you use the ground truth in this repository, please cite both the upstream datasets (see README §11) and comply with Apache-2.0 notice retention.

## 2. What is redistributed here

| Content | Redistributed? | Basis |
|---|---|---|
| Ground-truth text (462 markdown files, `ground_truth/`) | **Yes** | Apache-2.0 source datasets; content unmodified, SHA-256-verified against the manifest, attribution given above |
| Per-page model outputs and metrics (`results/`) | **Yes** | outputs of the evaluated models on this corpus; no model weights, no third-party text beyond transcriptions of the benchmark pages |
| Manifests, export records, provenance, configs, code | **Yes** | original benchmark artifacts; code released under Apache-2.0 |
| **Page images** (`data/images/`, ≈608 MB) | **No** (hashes only) | Apache-2.0 sources would permit redistribution with notices, but images are omitted to keep the release lean and auditable rather than mirrored; every image's SHA-256 is in the manifest and a byte-identical refetch procedure is documented in `REPRODUCIBILITY.md` §3 |
| Model weights | **No** | never redistributed; each model's own license is recorded in its registry YAML (e.g. `tencent/HunyuanOCR` — Tencent Hunyuan Community License, a custom license with territorial restrictions) |

## 3. Content notes

- Page content is historical/scholarly Arabic text (books, journals, references, forms) as published by the upstream datasets; one page (MISRAJ-0109) contains English content — authentic upstream composition, recorded in the page's `language` field and in the integrity report.
- Ground truth is the upstream reviewed markdown, used verbatim; the benchmark did not re-annotate, filter, or edit any page.
- No personal data, credentials, or private infrastructure information is included in this repository. Hardware identifiers are limited to the **GPU model names** (`NVIDIA L40S` in session 1, `NVIDIA H200` in the resumed session 2) recorded per page by the runner; the per-record `gpu_uuid_if_available` field was **redacted (set to null)** before publication, and cloud-instance filesystem paths in the resumed-session orchestration evidence were replaced with `<server-root>` — see `REPRODUCIBILITY.md` §7.
