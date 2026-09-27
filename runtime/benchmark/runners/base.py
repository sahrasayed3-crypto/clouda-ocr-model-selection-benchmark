"""Benchmark runner core: scheduling, resume, atomic persistence, result schema.

Design guarantees:
- Deterministic page order: manifest order (sorted page_id).
- Resumable: per-page results are written atomically (tmp + os.replace) as
  individual JSON files; a page with a terminal-success record is never
  reprocessed; a crash mid-page leaves at most a partial tmp file that is
  discarded on restart.
- Duplicate-run prevention: a run_id directory is seeded with run_state.json
  containing the config hash; a later attempt to reuse the run_id with a
  different config hash is rejected.
- One model at a time: Runner is constructed per model run; engines are
  single-model abstractions.
- Standalone: no dependency on any external product OCR repository.
- Preparation mode: gpu_name / gpu_uuid_if_available / peak_vram_mb are null
  everywhere; nothing is fabricated.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import time
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Protocol

from benchmark.constants import RESULT_SCHEMA_VERSION
from benchmark.metrics.aggregate import FAILURE_STATUSES, SUCCESS_STATUS, score_page
from benchmark.text_normalization import normalize_text

OOM_MARKERS = (
    "out of memory", "outofmemoryerror", "cuda error 2", "couldn't allocate memory",
    "cudaoutofmemory", "oom killed",
)


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds")


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def sha256_json(obj) -> str:
    return sha256_text(json.dumps(obj, sort_keys=True, ensure_ascii=False))


def slugify(text: str) -> str:
    return re.sub(r"[^a-zA-Z0-9]+", "-", text).strip("-").lower()


def classify_exception(exc: BaseException) -> str:
    """Map an exception to a run status."""
    name = type(exc).__name__.lower()
    msg = str(exc).lower()
    if isinstance(exc, TimeoutError) or "timeout" in name:
        return "TIMEOUT"
    if "outofmemoryerror" in name or isinstance(exc, MemoryError) or any(
        m in msg for m in OOM_MARKERS
    ):
        return "OOM"
    return "FAIL"


def atomic_write_json(path: Path, obj: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + f".tmp-{uuid.uuid4().hex[:8]}")
    tmp.write_text(
        json.dumps(obj, indent=2, sort_keys=True, ensure_ascii=False),
        encoding="utf-8",
    )
    os.replace(tmp, path)  # atomic on POSIX


def atomic_write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + f".tmp-{uuid.uuid4().hex[:8]}")
    tmp.write_text(text, encoding="utf-8")
    os.replace(tmp, path)


class Engine(Protocol):
    """A single-model OCR engine (real GPU engines implement this later)."""

    model_id: str
    model_revision: str

    def load(self) -> None: ...

    def transcribe(
        self, image_path: Path, prompt: str, timeout_seconds: float | None
    ) -> dict:
        """Return dict(raw_output=..., dtype=..., input_dimensions=...,
        gpu_name=..., gpu_uuid_if_available=..., peak_vram_mb=...)."""
        ...


@dataclass
class RunConfig:
    model_id: str
    model_revision: str
    prompt: str
    generation_parameters: dict
    manifest_sha256: str
    page_ids: list[str]
    timeout_seconds: float | None = None
    max_retries: int = 0
    retry_on_statuses: list[str] = field(default_factory=lambda: ["OOM", "TIMEOUT"])
    is_dry_run: bool = False
    notes: str = ""

    def config_hash(self) -> str:
        return sha256_json(
            {
                "model_id": self.model_id,
                "model_revision": self.model_revision,
                "prompt": self.prompt,
                "generation_parameters": self.generation_parameters,
                "manifest_sha256": self.manifest_sha256,
                "page_ids": self.page_ids,
                "timeout_seconds": self.timeout_seconds,
                "max_retries": self.max_retries,
                "is_dry_run": self.is_dry_run,
            }
        )

    def new_run_id(self) -> str:
        prefix = "DRYRUN__" if self.is_dry_run else ""
        stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        return (
            f"{prefix}{slugify(self.model_id)}__{stamp}__"
            f"{self.config_hash()[:8]}-{uuid.uuid4().hex[:6]}"
        )


def make_run_result(
    *,
    run_id: str,
    config: RunConfig,
    page_id: str,
    status: str,
    raw_output: str | None = None,
    normalized_output: str | None = None,
    elapsed_seconds: float | None = None,
    gpu_name: str | None = None,
    gpu_uuid_if_available: str | None = None,
    peak_vram_mb: float | None = None,
    dtype: str | None = None,
    input_dimensions: dict | None = None,
    exception_type: str | None = None,
    exception_message: str | None = None,
    retry_count: int = 0,
    started_at: str | None = None,
    completed_at: str | None = None,
) -> dict:
    rec = {
        "schema_version": RESULT_SCHEMA_VERSION,
        "run_id": run_id,
        "is_dry_run": config.is_dry_run,
        "model_id": config.model_id,
        "model_revision": config.model_revision,
        "page_id": page_id,
        "status": status,
        "raw_output": raw_output,
        "normalized_output": normalized_output,
        "elapsed_seconds": elapsed_seconds,
        "gpu_name": gpu_name,
        "gpu_uuid_if_available": gpu_uuid_if_available,
        "peak_vram_mb": peak_vram_mb,
        "dtype": dtype,
        "input_dimensions": input_dimensions,
        "prompt_hash": sha256_text(config.prompt),
        "generation_config_hash": sha256_json(config.generation_parameters),
        "exception_type": exception_type,
        "exception_message": exception_message,
        "retry_count": retry_count,
        "started_at": started_at,
        "completed_at": completed_at,
    }
    return rec


class Runner:
    """Executes one model over the manifest pages with resume support."""

    def __init__(self, root: Path, run_id: str, config: RunConfig):
        self.root = Path(root)
        self.run_id = run_id
        self.config = config
        self.raw_dir = self.root / "raw" / run_id
        self.normalized_dir = self.root / "normalized" / run_id
        self.metrics_dir = self.root / "metrics" / run_id
        self.logs_dir = self.root / "logs" / run_id
        self.state_path = self.raw_dir / "run_state.json"

    # -- run identity -------------------------------------------------------
    def prepare(self) -> dict:
        if self.state_path.exists():
            state = json.loads(self.state_path.read_text())
            if state["config_hash"] != self.config.config_hash():
                raise RuntimeError(
                    f"run_id {self.run_id!r} already exists with a different config; "
                    "refusing to reuse run id (duplicate-run prevention)"
                )
            return state
        for d in (self.raw_dir, self.normalized_dir, self.metrics_dir, self.logs_dir):
            d.mkdir(parents=True, exist_ok=True)
        state = {
            "run_id": self.run_id,
            "config_hash": self.config.config_hash(),
            "model_id": self.config.model_id,
            "model_revision": self.config.model_revision,
            "is_dry_run": self.config.is_dry_run,
            "created_at": utc_now_iso(),
            "prompt": self.config.prompt,
            "generation_parameters": self.config.generation_parameters,
            "manifest_sha256": self.config.manifest_sha256,
            "page_ids": self.config.page_ids,
            "timeout_seconds": self.config.timeout_seconds,
            "max_retries": self.config.max_retries,
            "retry_policy": self.config.retry_on_statuses,
        }
        atomic_write_json(self.state_path, state)
        return state

    # -- resume -------------------------------------------------------------
    def page_result_path(self, page_id: str) -> Path:
        return self.raw_dir / f"{page_id}.json"

    def completed_pages(self) -> set[str]:
        """Pages with a stored terminal record (success OR recorded failure):
        a recorded failure is final for this run unless the retry policy says
        otherwise at run time; on restart we do not recompute them."""
        done: set[str] = set()
        if not self.raw_dir.exists():
            return done
        for f in self.raw_dir.glob("*.json"):
            if f.name == "run_state.json":
                continue
            try:
                rec = json.loads(f.read_text())
            except (json.JSONDecodeError, OSError):
                continue  # partial tmp leftovers are ignored by glob (*.tmp-* not matched)
            if rec.get("run_id") == self.run_id:
                done.add(rec["page_id"])
        return done

    # -- execution ----------------------------------------------------------
    def run(
        self,
        engine: Engine,
        pages: dict[str, dict],  # page_id -> {image_path, ground_truth_path, ...}
        gt_loader=None,
    ) -> list[dict]:
        state = self.prepare()
        assert state["run_id"] == self.run_id
        done = self.completed_pages()
        results: list[dict] = [
            json.loads(self.page_result_path(p).read_text()) for p in sorted(done)
        ]
        log_path = self.logs_dir / "events.jsonl"
        log_path.parent.mkdir(parents=True, exist_ok=True)

        def log_event(evt: dict) -> None:
            evt = {"ts": utc_now_iso(), **evt}
            with log_path.open("a", encoding="utf-8") as f:
                f.write(json.dumps(evt, ensure_ascii=False) + "\n")

        log_event({"event": "run_start", "pages_total": len(self.config.page_ids),
                   "already_complete": len(done)})

        try:
            engine.load()
        except Exception as exc:  # noqa: BLE001
            for page_id in self.config.page_ids:
                if page_id in done:
                    continue
                rec = make_run_result(
                    run_id=self.run_id, config=self.config, page_id=page_id,
                    status="MODEL_LOAD_ERROR",
                    exception_type=type(exc).__name__,
                    exception_message=str(exc)[:2000],
                    started_at=utc_now_iso(), completed_at=utc_now_iso(),
                )
                atomic_write_json(self.page_result_path(page_id), rec)
                results.append(rec)
            log_event({"event": "model_load_error", "error": str(exc)[:500]})
            return results

        for page_id in self.config.page_ids:  # deterministic manifest order
            if page_id in done:
                continue
            page = pages[page_id]
            started_at = utc_now_iso()
            t0 = time.monotonic()
            retry_count = 0
            rec: dict | None = None

            attempt_statuses: list[str] = []
            while True:
                try:
                    out = engine.transcribe(
                        Path(page["image_path"]),
                        self.config.prompt,
                        self.config.timeout_seconds,
                    )
                    raw = out.get("raw_output", "")
                    rec = make_run_result(
                        run_id=self.run_id, config=self.config, page_id=page_id,
                        status="PASS", raw_output=raw,
                        elapsed_seconds=round(time.monotonic() - t0, 6),
                        gpu_name=out.get("gpu_name"),
                        gpu_uuid_if_available=out.get("gpu_uuid_if_available"),
                        peak_vram_mb=out.get("peak_vram_mb"),
                        dtype=out.get("dtype"),
                        input_dimensions=out.get("input_dimensions"),
                        retry_count=retry_count,
                        started_at=started_at, completed_at=utc_now_iso(),
                    )
                    break
                except Exception as exc:  # noqa: BLE001
                    status = classify_exception(exc)
                    attempt_statuses.append(status)
                    can_retry = (
                        retry_count < self.config.max_retries
                        and status in self.config.retry_on_statuses
                    )
                    if can_retry:
                        retry_count += 1
                        continue
                    rec = make_run_result(
                        run_id=self.run_id, config=self.config, page_id=page_id,
                        status=status,
                        elapsed_seconds=round(time.monotonic() - t0, 6),
                        exception_type=type(exc).__name__,
                        exception_message=str(exc)[:2000],
                        retry_count=retry_count,
                        started_at=started_at, completed_at=utc_now_iso(),
                    )
                    break

            assert rec is not None
            # Quality scoring (separate from raw output; never overwrites it).
            if rec["status"] == SUCCESS_STATUS and gt_loader is not None:
                gt_text = gt_loader(page)
                normalized = normalize_text(rec["raw_output"] or "")
                rec["normalized_output"] = normalized
                rec["metrics"] = score_page(gt_text, rec["raw_output"] or "")

            atomic_write_json(self.page_result_path(page_id), rec)
            if rec.get("normalized_output") is not None:
                atomic_write_text(
                    self.normalized_dir / f"{page_id}.txt", rec["normalized_output"]
                )
            results.append(rec)
            log_event({
                "event": "page_done", "page_id": page_id,
                "status": rec["status"], "attempts": attempt_statuses or ["PASS"],
                "elapsed": rec.get("elapsed_seconds"),
            })

        log_event({"event": "run_end", "pages_total": len(results)})
        # Report rows follow the deterministic manifest order.
        order = {pid: i for i, pid in enumerate(self.config.page_ids)}
        results.sort(key=lambda r: order.get(r["page_id"], len(order)))
        return results
