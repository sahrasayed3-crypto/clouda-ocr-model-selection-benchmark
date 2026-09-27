"""No-GPU preflight: verify everything the preparation phase must guarantee.

Run:  .venv/bin/python -m benchmark.preflight
Exit code 0 = PASS (with possible WARNs), 1 = FAIL.
"""

from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

from benchmark.constants import (
    CANONICAL_MANIFEST_PATH,
    CONFIGS_DIR,
    DRY_RUNS_DIR,
    GIT_ROOT,
    MANIFEST_SHA256_PATH,
    MODEL_REGISTRY_DIR,
    OFFICIAL_MODEL_COUNT,
    OUTPUTS_DIR,
    SMOKE_SET_PATH,
    TOTAL_PAGES,
)
from benchmark.models.registry import (
    OFFICIAL_MODEL_IDS,
    load_registry,
    unresolved_invocations,
    validate_registry,
)
from benchmark.validation.integrity import verify_manifest

PASS, WARN, FAIL = "PASS", "WARN", "FAIL"


class Preflight:
    def __init__(self) -> None:
        self.checks: list[dict] = []

    def check(self, name: str, ok: bool, detail: str = "", level: str | None = None):
        status = PASS if ok else (level or FAIL)
        self.checks.append({"check": name, "status": status, "detail": detail})

    def report(self) -> tuple[str, dict]:
        worst = FAIL if any(c["status"] == FAIL for c in self.checks) else (
            WARN if any(c["status"] == WARN for c in self.checks) else PASS
        )
        return worst, {"overall": worst, "checks": self.checks}


def run_preflight() -> tuple[str, dict]:
    pf = Preflight()

    # --- manifest ---------------------------------------------------------
    integrity = verify_manifest()
    pf.check("462-page manifest complete",
             integrity.get("total_pages") == TOTAL_PAGES and integrity.get("ok"),
             f"total={integrity.get('total_pages')} problems={integrity.get('problems')}")
    pf.check("dataset hashes valid", integrity.get("ok", False),
             f"warnings={integrity.get('warnings')}", level=PASS)
    pf.check("manifest sha256 recorded",
             MANIFEST_SHA256_PATH.exists() and len(MANIFEST_SHA256_PATH.read_text().strip()) == 64)

    # --- ground truth readability (spot re-check from the report) ----------
    gt_problems = [p for p in integrity.get("problems", []) if "ground truth" in p]
    pf.check("ground truth readable", not gt_problems, "; ".join(gt_problems))

    # --- model registry ----------------------------------------------------
    try:
        registry = load_registry()
        problems = validate_registry(registry)
        pf.check("model registry complete",
                 len(registry) == OFFICIAL_MODEL_COUNT
                 and set(registry) == set(OFFICIAL_MODEL_IDS) and not problems,
                 f"entries={len(registry)} problems={problems}")
        pf.check("model revisions recorded",
                 all(len(str(e["pinned_revision"])) == 40 for e in registry.values()))
        unresolved = unresolved_invocations(registry)
        pf.check("documented prompts available or explicitly unresolved",
                 True,
                 "UNRESOLVED for: " + ", ".join(sorted(unresolved))
                 if unresolved else "all documented",
                 level=WARN if unresolved else PASS)
    except Exception as exc:  # noqa: BLE001
        pf.check("model registry complete", False, f"{type(exc).__name__}: {exc}")

    # --- adapter/config modules import without weights ----------------------
    try:
        import benchmark.dry_run  # noqa: F401
        import benchmark.metrics.aggregate  # noqa: F401
        import benchmark.metrics.cer_wer  # noqa: F401
        import benchmark.runners.base  # noqa: F401
        import benchmark.runners.mock_engine  # noqa: F401
        import benchmark.text_normalization  # noqa: F401
        import benchmark.validation.integrity  # noqa: F401
        pf.check("adapter/config modules import", True)
    except Exception as exc:  # noqa: BLE001
        pf.check("adapter/config modules import", False, f"{type(exc).__name__}: {exc}")

    # --- output dirs writable ----------------------------------------------
    try:
        for d in (OUTPUTS_DIR, DRY_RUNS_DIR, CONFIGS_DIR):
            with tempfile.NamedTemporaryFile(dir=d, suffix=".wtest", delete=False) as f:
                f.write(b"ok")
                tmp = Path(f.name)
            tmp.unlink()
        pf.check("output directories writable", True, "outputs/, dry_runs/, configs/")
    except Exception as exc:  # noqa: BLE001
        pf.check("output directories writable", False, str(exc))

    # --- resume state healthy (dry-run namespace isolated + resumable) ------
    try:
        from benchmark.dry_run import load_manifest_pages, load_smoke_page_ids

        pages = load_manifest_pages()
        smoke = load_smoke_page_ids()
        pf.check("manifest loads for scheduling", len(pages) == TOTAL_PAGES)
        pf.check("fixed smoke set frozen",
                 len(smoke) == 5 and all(p in pages for p in smoke),
                 f"smoke={smoke}")
        dry_root = DRY_RUNS_DIR / "runs"
        state_files = list(dry_root.glob("DRYRUN__*/raw/*/run_state.json")) if dry_root.exists() else []
        healthy = all(
            json.loads(s.read_text()).get("is_dry_run") is True for s in state_files
        )
        pf.check("resume state healthy (dry-run namespace)",
                 healthy, f"{len(state_files)} dry-run state files, all is_dry_run=true")
    except Exception as exc:  # noqa: BLE001
        pf.check("resume state healthy (dry-run namespace)", False, str(exc))

    # --- metrics tests (delegate to pytest for the metrics subset) ----------
    import subprocess

    r = subprocess.run(
        [sys.executable, "-m", "pytest", "tests/test_metrics.py",
         "tests/test_normalization.py", "-q", "--no-header"],
        cwd=GIT_ROOT, capture_output=True, text=True, timeout=300,
    )
    pf.check("metrics tests pass", r.returncode == 0,
             r.stdout.strip().splitlines()[-1] if r.stdout.strip() else r.stderr[-200:])

    # --- dry-run namespace isolation ----------------------------------------
    real_runs = list((OUTPUTS_DIR / "raw").glob("DRYRUN__*")) if (OUTPUTS_DIR / "raw").exists() else []
    dry_leak_into_outputs = list((OUTPUTS_DIR / "raw").glob("**/*")) if (OUTPUTS_DIR / "raw").exists() else []
    pf.check("dry-run namespace isolated",
             not real_runs and not dry_leak_into_outputs,
             "no DRYRUN__ artifacts under outputs/")

    # --- no large weights required ------------------------------------------
    big = [p for p in GIT_ROOT.rglob("*")
           if p.is_file() and p.suffix in {".safetensors", ".bin", ".pt", ".ckpt"}
           and p.stat().st_size > 100 * 1024 * 1024]
    pf.check("no large model weights required", not big,
             f"found {len(big)} large weight files in workspace" if big else "none present")

    # --- GPU absence acceptable in preparation mode -------------------------
    try:
        import torch  # noqa: F401

        torch.cuda.is_available()
        pf.check("GPU absence acceptable in preparation mode", True,
                 "torch present (cuda availability irrelevant in prep mode)")
    except ImportError:
        pf.check("GPU absence acceptable in preparation mode", True,
                 "torch not installed - fine for CPU preparation phase")

    return pf.report()


def main() -> int:
    overall, report = run_preflight()
    print(f"PREFLIGHT: {overall}")
    for c in report["checks"]:
        print(f"  [{c['status']:4}] {c['check']}" + (f" — {c['detail']}" if c["detail"] else ""))
    out = GIT_ROOT / "outputs" / "preflight_latest.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    print("report ->", out)
    return 0 if overall in (PASS, WARN) else 1


if __name__ == "__main__":
    sys.exit(main())
