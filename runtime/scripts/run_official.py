"""Official benchmark run driver (GPU, real inference).

Scope:
  --scope smoke : the frozen 5-page smoke set (configs/smoke_set.json)
  --scope full  : all 462 manifest pages, manifest order, resumable

Run identity is deterministic per (model, scope, config): the run_id embeds
the config hash, so re-invoking the same command resumes the same run
directory; changing any frozen input creates a new run_id.

Usage:
  .venv-gpu/bin/python scripts/run_official.py --model-id tencent/HunyuanOCR --scope smoke
  .venv-gpu/bin/python scripts/run_official.py --model-id tencent/HunyuanOCR --scope full
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from benchmark.constants import (  # noqa: E402
    CANONICAL_MANIFEST_PATH,
    GIT_ROOT,
    OUTPUTS_DIR,
    SMOKE_SET_PATH,
)
from benchmark.models.registry import load_registry  # noqa: E402
from benchmark.reporting.reports import (  # noqa: E402
    failure_report,
    per_model_report,
)
from benchmark.runners.base import Runner, RunConfig, sha256_text, slugify  # noqa: E402
from benchmark.runners.hf_engine import HfVlmEngine  # noqa: E402


def load_manifest_pages() -> dict[str, dict]:
    manifest = json.loads(CANONICAL_MANIFEST_PATH.read_text(encoding="utf-8"))
    return {p["page_id"]: p for p in manifest["pages"]}


def load_smoke_page_ids() -> list[str]:
    smoke = json.loads(SMOKE_SET_PATH.read_text(encoding="utf-8"))
    return [p["page_id"] for p in smoke["pages"]]


def gt_loader(page: dict) -> str:
    return (GIT_ROOT / page["ground_truth_path"]).read_text(encoding="utf-8")


def build_engine(entry: dict, args: argparse.Namespace,
                 base_revision: str | None) -> HfVlmEngine:
    gen = dict(entry.get("generation_parameters") or {})
    gen.pop("source", None)
    return HfVlmEngine(
        model_id=entry["model_id"],
        model_revision=entry["pinned_revision"],
        dtype=str(entry.get("recommended_dtype", "bfloat16")).split()[0],
        attn_implementation=args.attn,
        max_new_tokens=args.max_new_tokens,
        model_class=args.model_class,
        generation_kwargs=gen,
        chat_style=args.chat_style,
        base_repo=args.base_repo,
        base_revision=base_revision,
        processor_repo=args.processor_repo,
        processor_revision=args.processor_revision,
        think_end_marker=args.think_end_marker,
    )


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--model-id", required=True)
    ap.add_argument("--scope", choices=["smoke", "full"], required=True)
    ap.add_argument("--attn", default="sdpa",
                    help="attention backend (recorded in the run config)")
    ap.add_argument("--max-new-tokens", type=int, default=None,
                    help="decoding cap; defaults to the YAML-documented value, else 8192")
    ap.add_argument("--model-class", default=None,
                    help="exact model class path overriding Auto resolution")
    ap.add_argument("--base-repo", default=None,
                    help="base weights repo when the registry model_id is a PEFT adapter")
    ap.add_argument("--base-revision", default=None,
                    help="base weights revision (default: resolved pin from outputs/base_model_pins.json)")
    ap.add_argument("--processor-repo", default=None,
                    help="repo to load the processor from (defaults to model-id)")
    ap.add_argument("--processor-revision", default=None)
    ap.add_argument("--think-end-marker", default=None,
                    help="strip everything before this marker (thinking models)")
    ap.add_argument("--chat-style", default="image_content_list",
                    choices=["image_content_list", "raw_text", "no_template"])
    ap.add_argument("--timeout-seconds", type=float, default=None)
    args = ap.parse_args()

    registry = load_registry()
    if args.model_id not in registry:
        print(f"model {args.model_id!r} not in registry", file=sys.stderr)
        return 2
    entry = registry[args.model_id]

    documented_max_new = (entry.get("generation_parameters") or {}).get(
        "max_new_tokens"
    )
    if args.max_new_tokens is None:
        args.max_new_tokens = (
            int(documented_max_new) if documented_max_new else 8192
        )

    base_revision = args.base_revision
    if args.base_repo and not base_revision:
        pins_path = OUTPUTS_DIR / "base_model_pins.json"
        pins = json.loads(pins_path.read_text()) if pins_path.exists() else {}
        base_revision = pins.get(args.base_repo)
        if not base_revision:
            print(
                f"no pinned revision recorded for base {args.base_repo!r} "
                "(run scripts/predownload_models.py first)", file=sys.stderr,
            )
            return 2

    pages = load_manifest_pages()
    if args.scope == "smoke":
        page_ids = load_smoke_page_ids()
    else:
        page_ids = sorted(pages)

    config = RunConfig(
        model_id=entry["model_id"],
        model_revision=entry["pinned_revision"],
        prompt=entry["documented_ocr_prompt"],
        generation_parameters={
            **{k: v for k, v in (entry.get("generation_parameters") or {}).items()
               if k != "source"},
            "max_new_tokens": args.max_new_tokens,
        },
        manifest_sha256=(
            GIT_ROOT / "benchmark/manifests/canonical_manifest.sha256"
        ).read_text().strip(),
        page_ids=page_ids,
        timeout_seconds=args.timeout_seconds,
        notes=(
            f"engine=HfVlmEngine attn={args.attn} chat_style={args.chat_style} "
            f"model_class={args.model_class or 'auto'} "
            f"base={args.base_repo or 'self'} "
            f"base_revision={base_revision or '-'} "
            f"processor={args.processor_repo or 'default'} "
            f"think_end_marker={args.think_end_marker or 'none'}"
        ),
    )
    # Engine-configuration deltas (adapter/processor/think handling) are not
    # part of RunConfig's hash; make them explicit in the run id so two
    # different engine configs can never share a run directory.
    engine_tag = ""
    if args.base_repo or args.processor_repo or args.think_end_marker:
        engine_tag = "__e" + sha256_text(
            json.dumps([args.base_repo, base_revision,
                        args.processor_repo, args.processor_revision,
                        args.think_end_marker, args.chat_style,
                        args.model_class])
        )[:8]
    run_id = (
        f"{slugify(entry['model_id'])}__{args.scope}__"
        f"{config.config_hash()[:8]}{engine_tag}"
    )
    runner = Runner(OUTPUTS_DIR, run_id, config)
    engine = build_engine(entry, args, base_revision)

    print(f"run_id: {run_id}")
    print(f"model:  {entry['model_id']} @ {entry['pinned_revision']}")
    print(f"prompt: {config.prompt[:120]}")
    results = runner.run(engine, pages, gt_loader=gt_loader)

    statuses: dict[str, int] = {}
    for r in results:
        statuses[r["status"]] = statuses.get(r["status"], 0) + 1
    print("statuses:", json.dumps(statuses))

    per_model = per_model_report(runner.raw_dir, entry["model_id"], include_dry=False)
    fails = failure_report(runner.raw_dir, include_dry=False)
    report = {
        "run_id": run_id,
        "scope": args.scope,
        "per_model": per_model,
        "failures": fails,
    }
    report_path = OUTPUTS_DIR / "reports"
    report_path.mkdir(parents=True, exist_ok=True)
    out = report_path / f"{run_id}.json"
    out.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    print("report ->", out)
    print("per-model:", json.dumps(per_model, indent=2, ensure_ascii=False)[:2000])

    failed = sum(v for k, v in statuses.items() if k != "PASS")
    return 0 if failed == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
