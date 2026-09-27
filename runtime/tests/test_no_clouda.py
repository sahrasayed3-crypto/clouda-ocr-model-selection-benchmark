"""The benchmark must be fully independent of the Clouda OCR product."""

import subprocess
import sys
from pathlib import Path

GIT_ROOT = Path(__file__).resolve().parent.parent

FORBIDDEN = [
    "clouda", "page_analyzer", "page analyzer", "trusted digital text gate",
    "ocr_self_review", "selective re-read", "semantic_understanding",
]

CODE_DIRS = ["benchmark", "scripts", "tests"]


def test_no_clouda_imports_or_references_in_code():
    offenders = []
    self_name = Path(__file__).name
    for d in CODE_DIRS:
        for py in (GIT_ROOT / d).rglob("*.py"):
            if py.name == self_name:
                continue  # this file documents the forbidden tokens themselves
            text = py.read_text(encoding="utf-8", errors="replace").lower()
            for token in FORBIDDEN:
                if token in text:
                    offenders.append(f"{py.relative_to(GIT_ROOT)}: {token}")
    assert not offenders, offenders


def test_import_of_benchmark_package_does_not_pull_clouda():
    code = (
        "import sys; import benchmark.runners.base; "
        "bad = [m for m in sys.modules if 'clouda' in m.lower()]; "
        "print('BAD:' + ','.join(bad))"
    )
    r = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True)
    assert r.returncode == 0
    assert "BAD:" in r.stdout and r.stdout.strip() == "BAD:"
