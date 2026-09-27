r"""Autonomous benchmark supervisor: durable queue state machine.

Wraps the existing benchmark runner (scripts/run_official.py) as an isolated
worker subprocess and drives every model through:

  PENDING -> PREFLIGHT -> SMOKE -> FULL -> VALIDATE -> COMPLETE
      \-> BLOCKED (never runnable: e.g. unresolved prompt)
      \-> FAILED_FINAL (retry exhaustion / deterministic failure)

Crash resilience:
- State persists to outputs/orchestrator/state.json after every transition
  (atomic tmp+replace). The supervisor is restartable at any time; completed
  pages are never recomputed (the runner's own resume guarantee).
- Workers run as separate processes: GPU memory is fully reclaimable and a
  worker crash cannot take the supervisor down.
- Watchdog: if a worker stops making page progress beyond the stage
  threshold, it is terminated and the attempt is retried.
- Locking: outputs/orchestrator/lock.json with PID liveness check prevents
  duplicate supervisors.

Commands:
  python scripts/supervisor.py run [--once]     # foreground (use under setsid)
  python scripts/supervisor.py status           # one-shot status table
  python scripts/supervisor.py stop             # graceful stop (finishes page)
  python scripts/supervisor.py kill-worker      # terminate current worker only
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import shutil
import signal
import socket
import subprocess
import sys
import time
import uuid
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

ORCH_DIR = Path(os.environ.get(
    "CLOUDA_ORCH_STATE_DIR", ROOT / "outputs" / "orchestrator"))
STATE_PATH = ORCH_DIR / "state.json"
LOCK_PATH = ORCH_DIR / "lock.json"
LOGS_DIR = ORCH_DIR / "logs"
PY = ROOT / ".venv-gpu" / "bin" / "python"
WORKER = ROOT / "scripts" / "run_official.py"

TOTAL_PAGES = 462
SMOKE_ATTEMPTS = int(os.environ.get("CLOUDA_MAX_ATTEMPTS", "3"))
FULL_ATTEMPTS = int(os.environ.get("CLOUDA_MAX_ATTEMPTS", "3"))
WATCHDOG_POLL_S = float(os.environ.get("CLOUDA_POLL_S", "30"))
_HANG_ENV = os.environ.get("CLOUDA_HANG_S")
HANG_THRESHOLD_S = (
    {"smoke": int(_HANG_ENV), "full": int(_HANG_ENV)} if _HANG_ENV
    else {"smoke": 20 * 60, "full": 45 * 60}
)
BACKOFF_S = [int(x) for x in os.environ.get("CLOUDA_BACKOFF_S", "30,120,300").split(",")]
MIN_FREE_DISK_GB = 20
GPU_IDLE_MB = 2500

# Engine flags per model — MUST stay byte-identical to the flags already used
# for this session's runs (run_queue.sh / session 1) so that deterministic run
# ids match and completed pages are honored on resume.
QUEUE: list[dict] = [
    {"model": "amad-iq/amad-vlm6",
     "flags": ["--chat-style", "raw_text", "--think-end-marker", "</think>"]},
    {"model": "amad-iq/amad-vlm5",
     "flags": ["--chat-style", "raw_text", "--think-end-marker", "</think>"]},
    {"model": "YasserSami/Qari-OCR-0.4.0-VL-4B-Instruct",
     "flags": ["--chat-style", "raw_text",
               "--base-repo", "Qwen/Qwen3-VL-4B-Instruct"]},
    {"model": "context212/alhazen-ocr",
     "flags": ["--chat-style", "raw_text",
               "--base-repo", "unsloth/Qwen3-VL-2B-Instruct"]},
    {"model": "sherif1313/Arabic-GLM-OCR-v2",
     "flags": ["--chat-style", "raw_text"]},
    {"model": "AhmedZaky1/DIMI-Arabic-OCR-V2",
     "flags": ["--chat-style", "raw_text",
               "--base-repo", "Qwen/Qwen2.5-VL-7B-Instruct"]},
    {"model": "loay/Arabic-OCR-DeepSeek-OCR-2",
     "flags": ["--chat-style", "no_template",
               "--processor-repo", "unsloth/DeepSeek-OCR-2"]},
    {"model": "hastyle/olmOCR-arabic-lora-v2",
     "flags": ["--chat-style", "raw_text",
               "--base-repo", "allenai/olmOCR-2-7B-1025",
               "--processor-repo", "allenai/olmOCR-2-7B-1025"]},
]

PRECOMPLETED = {
    "tencent/HunyuanOCR": {
        "status": "COMPLETE",
        "stage": "COMPLETE",
        "smoke_run_id": "tencent-hunyuanocr__smoke__30200dc6",
        "full_run_id": "tencent-hunyuanocr__full__def73123",
        "note": "462/462 PASS; ran in session 1 before the orchestrator existed",
    },
    "MBZUAI/AIN": {
        "status": "BLOCKED",
        "stage": "BLOCKED",
        "note": ("documented_ocr_prompt UNRESOLVED (evidence: "
                 "configs/models/MBZUAI__AIN.yaml); owner decision required; "
                 "excluded from this L40S session by instruction"),
    },
}

MOCK_WORKER_ENV = "CLOUDA_ORCH_MOCK_WORKER"


def utcnow() -> str:
    return dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds")


def log(msg: str) -> None:
    line = f"[{utcnow()}] {msg}"
    LOGS_DIR.mkdir(parents=True, exist_ok=True)
    with (LOGS_DIR / "supervisor.log").open("a") as f:
        f.write(line + "\n")
    print(line, flush=True)


def atomic_write_json(path: Path, obj: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + f".tmp-{uuid.uuid4().hex[:8]}")
    tmp.write_text(json.dumps(obj, indent=2, sort_keys=True, ensure_ascii=False))
    os.replace(tmp, path)


# ---------------------------------------------------------------------------
# State
# ---------------------------------------------------------------------------

def default_state() -> dict:
    models = {}
    for spec in QUEUE:
        models[spec["model"]] = {
            "status": "PENDING", "stage": "PENDING",
            "attempts_smoke": 0, "attempts_full": 0,
            "started_at": None, "updated_at": None, "completed_at": None,
            "last_scope": None, "last_attempt": 0, "last_exit": None,
            "last_error": None, "last_progress_at": None,
            "pages_done": 0, "run_dir": None, "run_id": None,
        }
    for model, rec in PRECOMPLETED.items():
        models[model] = {
            "attempts_smoke": 0, "attempts_full": 0,
            "started_at": None, "updated_at": utcnow(),
            "completed_at": utcnow() if rec["status"] == "COMPLETE" else None,
            "last_scope": None, "last_attempt": 0, "last_exit": None,
            "last_error": None, "last_progress_at": None,
            "pages_done": TOTAL_PAGES if rec["status"] == "COMPLETE" else 0,
            "run_dir": None, "run_id": rec.get("full_run_id"),
            **rec,
        }
    return {
        "schema": 1,
        "run_uid": f"orch-{dt.datetime.now(dt.timezone.utc):%Y%m%dT%H%M%SZ}",
        "created_at": utcnow(),
        "git_sha": git_sha(),
        "manifest_sha256": (ROOT / "benchmark/manifests/canonical_manifest.sha256")
            .read_text().strip(),
        "queue_order": [s["model"] for s in QUEUE],
        "precompleted": sorted(PRECOMPLETED),
        "models": models,
        "current_model": None,
        "stop_requested": False,
    }


def git_sha() -> str:
    try:
        return subprocess.run(["git", "rev-parse", "HEAD"], cwd=ROOT,
                              capture_output=True, text=True,
                              check=True).stdout.strip()[:12]
    except Exception:  # noqa: BLE001
        return "unknown"


def load_state() -> dict:
    if STATE_PATH.exists():
        return json.loads(STATE_PATH.read_text())
    st = default_state()
    atomic_write_json(STATE_PATH, st)
    return st


def save_state(st: dict) -> None:
    atomic_write_json(STATE_PATH, st)


# ---------------------------------------------------------------------------
# Locking
# ---------------------------------------------------------------------------

def acquire_lock() -> bool:
    if LOCK_PATH.exists():
        try:
            old = json.loads(LOCK_PATH.read_text())
            os.kill(old["pid"], 0)
            log(f"another live supervisor holds the lock (pid {old['pid']})")
            return False
        except (ProcessLookupError, PermissionError):
            log("stale lock found (owner dead); taking over")
        except (json.JSONDecodeError, KeyError):
            log("corrupt lock file; taking over")
    atomic_write_json(LOCK_PATH, {
        "pid": os.getpid(), "hostname": socket.gethostname(),
        "started_at": utcnow(),
    })
    return True


def release_lock() -> None:
    if LOCK_PATH.exists():
        try:
            if json.loads(LOCK_PATH.read_text())["pid"] == os.getpid():
                LOCK_PATH.unlink()
        except Exception:  # noqa: BLE001
            pass


# ---------------------------------------------------------------------------
# Preflight
# ---------------------------------------------------------------------------

def preflight(model: str, spec: dict) -> tuple[bool, str]:
    if os.environ.get(MOCK_WORKER_ENV):
        return True, "ok (mock mode)"
    if not PY.exists():
        return False, f"gpu venv missing: {PY}"
    if not shutil.which("nvidia-smi"):
        return False, "nvidia-smi not found; GPU required"
    try:
        q = subprocess.run(
            ["nvidia-smi", "--query-gpu=memory.used,memory.total",
             "--format=csv,noheader,nounits"],
            capture_output=True, text=True, check=True, timeout=15)
        used, total = (int(x) for x in q.stdout.strip().splitlines()[0].split(","))
        if used > GPU_IDLE_MB:
            return False, f"GPU busy: {used} MiB used (baseline check {GPU_IDLE_MB})"
    except Exception as exc:  # noqa: BLE001
        return False, f"nvidia-smi failed: {exc}"
    free = shutil.disk_usage(ROOT).free / 1e9
    if free < MIN_FREE_DISK_GB:
        return False, f"low disk: {free:.1f} GB free"
    # weights present?
    try:
        from huggingface_hub import snapshot_download
        pins = json.loads((ROOT / "outputs/base_model_pins.json").read_text())
        repos = [(model, pins[model])]
        flags = spec.get("flags", [])
        if "--base-repo" in flags:
            base = flags[flags.index("--base-repo") + 1]
            repos.append((base, pins[base]))
        if "--processor-repo" in flags:
            proc = flags[flags.index("--processor-repo") + 1]
            if proc not in [r[0] for r in repos]:
                repos.append((proc, pins[proc]))
        for repo, rev in repos:
            snapshot_download(repo, revision=rev, local_files_only=True)
    except Exception as exc:  # noqa: BLE001
        return False, f"weights missing for {model}: {exc}"
    # no stale worker for this model
    out = subprocess.run(["ps", "-eo", "args"], capture_output=True, text=True)
    for line in out.stdout.splitlines():
        if "run_official.py" in line and model in line and "grep" not in line:
            return False, f"stale worker already running: {line.strip()}"
    return True, "ok"


# ---------------------------------------------------------------------------
# Worker management
# ---------------------------------------------------------------------------

def worker_cmd(scope: str, spec: dict) -> list[str]:
    if os.environ.get(MOCK_WORKER_ENV):
        return [os.environ[MOCK_WORKER_ENV], spec["model"], scope]
    return [str(PY), str(WORKER), "--model-id", spec["model"],
            "--scope", scope, *spec.get("flags", [])]


def find_run_dir(model: str, scope: str) -> Path | None:
    """Newest raw run dir for this model+scope (slug prefix match).

    CLOUDA_ORCH_RAW_DIR redirects the scan root (orchestrator self-tests use a
    scratch dir; real runs always use outputs/raw)."""
    raw_root = Path(os.environ.get("CLOUDA_ORCH_RAW_DIR",
                                   ROOT / "outputs" / "raw"))
    slug = model.replace("/", "-").replace("_", "-").replace(".", "-").lower()
    prefix = {"smoke": f"{slug}__smoke__", "full": f"{slug}__full__"}[scope]
    cands = sorted(raw_root.glob(prefix + "*"),
                   key=lambda p: p.stat().st_mtime)
    return cands[-1] if cands else None


def pages_done(run_dir: Path | None) -> int:
    if not run_dir or not run_dir.exists():
        return 0
    return len([f for f in run_dir.glob("*.json") if f.name != "run_state.json"])


def terminate_worker(proc: subprocess.Popen) -> None:
    try:
        os.killpg(os.getpgid(proc.pid), signal.SIGTERM)
    except (ProcessLookupError, PermissionError):
        pass
    for _ in range(15):
        if proc.poll() is not None:
            return
        time.sleep(2)
    try:
        os.killpg(os.getpgid(proc.pid), signal.SIGKILL)
    except (ProcessLookupError, PermissionError):
        pass
    proc.wait(timeout=30)


def run_worker(scope: str, spec: dict, attempt: int, mstate: dict) -> tuple[int, str]:
    """Run one worker attempt with watchdog; returns (exit_code, error)."""
    cmd = worker_cmd(scope, spec)
    log_path = LOGS_DIR / f"{spec['model'].replace('/', '__')}__{scope}__a{attempt}.log"
    log_f = log_path.open("w")
    log_f.write(f"cmd: {' '.join(cmd)}\nstarted: {utcnow()}\n")
    log_f.flush()
    kwargs: dict = {"stdout": log_f, "stderr": subprocess.STDOUT, "cwd": ROOT,
                    "start_new_session": True}  # own process group for clean kill
    proc = subprocess.Popen(cmd, **kwargs)

    mstate["last_scope"] = scope
    mstate["last_attempt"] = attempt
    mstate["last_progress_at"] = utcnow()
    threshold = HANG_THRESHOLD_S[scope]
    last_pages = -1
    last_progress_ts = time.monotonic()
    while True:
        rc = proc.poll()
        run_dir = find_run_dir(spec["model"], scope)
        done = pages_done(run_dir)
        if done > last_pages:
            if last_pages >= 0:
                mstate["pages_done"] = done
                mstate["run_dir"] = str(run_dir)
                mstate["last_progress_at"] = utcnow()
                save_state_st(mstate)
            last_pages = done
            last_progress_ts = time.monotonic()
        if rc is not None:
            log_f.close()
            mstate["last_exit"] = rc
            return rc, "" if rc == 0 else f"worker exit {rc} (see {log_path.name})"
        if time.monotonic() - last_progress_ts > threshold:
            log(f"WATCHDOG: no page progress for {threshold}s on "
                f"{spec['model']} {scope}; terminating worker")
            log_f.write(f"watchdog: killed at {utcnow()}\n")
            log_f.flush()
            terminate_worker(proc)
            log_f.close()
            mstate["last_exit"] = None
            return 124, f"watchdog timeout: no progress for {threshold}s"
        time.sleep(WATCHDOG_POLL_S)


def save_state_st(mstate: dict) -> None:  # helper to persist model substate
    st = json.loads(STATE_PATH.read_text())
    st["models"][mstate["model_id"]] = mstate
    st["updated_at"] = utcnow()
    save_state(st)


# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------

def validate_full(spec: dict, mstate: dict) -> tuple[str, str]:
    """Returns (terminal_status, detail)."""
    run_dir = Path(mstate["run_dir"]) if mstate["run_dir"] else find_run_dir(
        spec["model"], "full")
    if not run_dir:
        return "FAILED_FINAL", "no full-run output directory"
    recs = [json.loads(f.read_text())
            for f in run_dir.glob("*.json") if f.name != "run_state.json"]
    ids = [r["page_id"] for r in recs]
    dupes = len(ids) - len(set(ids))
    counts: dict[str, int] = {}
    for r in recs:
        counts[r["status"]] = counts.get(r["status"], 0) + 1
    empty = sum(1 for r in recs if r["status"] == "PASS"
                and not (r.get("raw_output") or "").strip())
    detail = (f"pages={len(recs)}/{TOTAL_PAGES} statuses={counts} "
              f"duplicates={dupes} empty_pass={empty}")
    if len(recs) < TOTAL_PAGES or dupes:
        return "INCOMPLETE", detail
    mstate["pages_done"] = len(recs)
    transient = counts.get("OOM", 0) + counts.get("TIMEOUT", 0)
    if counts.get("PASS", 0) == TOTAL_PAGES:
        return "COMPLETE", detail
    if transient and mstate["attempts_full"] < FULL_ATTEMPTS:
        return "RETRY", detail + f" (transient failures={transient})"
    return "COMPLETE_WITH_PAGE_FAILURES", detail


# ---------------------------------------------------------------------------
# Main loop
# ---------------------------------------------------------------------------

def process_model(st: dict, spec: dict) -> bool:
    """Advance one model one step. Returns False when model reached terminal."""
    model = spec["model"]
    m = st["models"][model]
    m["model_id"] = model

    if m["status"] in ("COMPLETE", "COMPLETE_WITH_PAGE_FAILURES",
                       "FAILED_FINAL", "BLOCKED"):
        return False

    if m["status"] == "PENDING":
        m["status"], m["stage"] = "PREFLIGHT", "PREFLIGHT"
        m["started_at"] = utcnow()
        st["current_model"] = model
        save_state(st)

    if m["stage"] == "PREFLIGHT":
        ok, detail = preflight(model, spec)
        if ok:
            m["stage"], m["status"] = "SMOKE", "RUNNING"
            log(f"{model}: preflight ok -> SMOKE")
        else:
            m["attempts_smoke"] += 1
            if m["attempts_smoke"] >= SMOKE_ATTEMPTS:
                m["status"], m["stage"] = "FAILED_FINAL", "FAILED_FINAL"
                m["last_error"] = f"preflight failed x{m['attempts_smoke']}: {detail}"
                log(f"{model}: FAILED_FINAL (preflight): {detail}")
            else:
                m["last_error"] = f"preflight: {detail}"
                m["status"] = "RETRY_WAIT"
                log(f"{model}: preflight retry in {BACKOFF_S[0]}s: {detail}")
        m["updated_at"] = utcnow()
        save_state(st)
        return True

    if m["stage"] == "SMOKE":
        m["attempts_smoke"] += 1
        log(f"{model}: smoke attempt {m['attempts_smoke']}/{SMOKE_ATTEMPTS}")
        rc, err = run_worker("smoke", spec, m["attempts_smoke"], m)
        m["updated_at"] = utcnow()
        if rc == 0:
            m["stage"], m["status"] = "FULL", "RUNNING"
            m["last_error"] = None
            log(f"{model}: smoke PASS -> FULL")
        elif rc == 124 or _transient(err):
            m["last_error"] = err
            if m["attempts_smoke"] >= SMOKE_ATTEMPTS:
                m["status"] = m["stage"] = "FAILED_FINAL"
                log(f"{model}: FAILED_FINAL after {m['attempts_smoke']} smoke attempts: {err}")
            else:
                m["status"] = "RETRY_WAIT"
                log(f"{model}: smoke retryable failure: {err}")
        else:
            m["last_error"] = err
            m["status"] = m["stage"] = "FAILED_FINAL"
            log(f"{model}: FAILED_FINAL (smoke, non-retryable): {err}")
        save_state(st)
        return True

    if m["stage"] == "FULL":
        m["attempts_full"] += 1
        log(f"{model}: full attempt {m['attempts_full']}/{FULL_ATTEMPTS}")
        rc, err = run_worker("full", spec, m["attempts_full"], m)
        m["updated_at"] = utcnow()
        if rc == 0:
            verdict, detail = validate_full(spec, m)
            if verdict == "COMPLETE":
                m["status"] = "COMPLETE"
                m["stage"] = "COMPLETE"
                m["completed_at"] = utcnow()
                m["last_error"] = None
                log(f"{model}: COMPLETE — {detail}")
                st["current_model"] = None
            elif verdict == "COMPLETE_WITH_PAGE_FAILURES":
                m["status"] = "COMPLETE_WITH_PAGE_FAILURES"
                m["stage"] = "COMPLETE"
                m["completed_at"] = utcnow()
                m["last_error"] = detail
                log(f"{model}: COMPLETE_WITH_PAGE_FAILURES — {detail}")
                st["current_model"] = None
            elif verdict == "RETRY":
                m["status"] = "RETRY_WAIT"
                m["last_error"] = detail
                log(f"{model}: full retry warranted: {detail}")
            else:  # INCOMPLETE with rc==0 shouldn't happen; treat as retry
                m["status"] = "RETRY_WAIT"
                m["last_error"] = f"rc=0 but {detail}"
        elif rc == 124 or _transient(err):
            m["last_error"] = err
            if m["attempts_full"] >= FULL_ATTEMPTS:
                m["status"] = m["stage"] = "FAILED_FINAL"
                log(f"{model}: FAILED_FINAL after {m['attempts_full']} full attempts: {err}")
            else:
                m["status"] = "RETRY_WAIT"
                log(f"{model}: full retryable failure: {err}")
        else:
            m["last_error"] = err
            m["status"] = m["stage"] = "FAILED_FINAL"
            log(f"{model}: FAILED_FINAL (full, non-retryable): {err}")
        save_state(st)
        return True

    if m["status"] == "RETRY_WAIT":
        backoff = BACKOFF_S[min(m["attempts_full"], len(BACKOFF_S) - 1)
                            if m["stage"] == "FULL" else 0]
        log(f"{model}: retrying in {backoff}s")
        time.sleep(backoff)
        m["status"] = "RUNNING"
        save_state(st)
        return True

    return False


def _transient(err: str) -> bool:
    markers = ("watchdog", "cuda error", "out of memory", "oom",
               "connection", "timeout", "timed out", "exit 124", "exit -9",
               "network", "killed", "worker exit")
    e = err.lower()
    return any(k in e for k in markers)


def run_loop(once: bool = False) -> int:
    if not acquire_lock():
        return 3
    st = load_state()
    log(f"supervisor start run_uid={st['run_uid']} git={st['git_sha']} "
        f"queue={len(QUEUE)} precompleted={len(PRECOMPLETED)}")
    exit_code = 0
    try:
        while True:
            if st.get("stop_requested"):
                log("stop requested; exiting cleanly (state preserved)")
                exit_code = 0
                break
            progressed = False
            terminal = 0
            for spec in QUEUE:
                m = st["models"][spec["model"]]
                if m["status"] in ("COMPLETE", "COMPLETE_WITH_PAGE_FAILURES",
                                   "FAILED_FINAL", "BLOCKED"):
                    terminal += 1
                    continue
                process_model(st, spec)
                progressed = True
                if st["models"][spec["model"]]["status"] in (
                        "COMPLETE", "COMPLETE_WITH_PAGE_FAILURES",
                        "FAILED_FINAL", "BLOCKED"):
                    terminal += 1
                break  # one model at a time
            if terminal == len(QUEUE):
                log("QUEUE COMPLETE: every model reached a terminal state")
                write_final_summary(st)
                bad = [mo for mo, m in st["models"].items()
                       if m["status"] in ("FAILED_FINAL",
                                          "COMPLETE_WITH_PAGE_FAILURES")]
                exit_code = 0 if not bad else 1
                log(f"exit code {exit_code}"
                    + (f" (failed/partial: {bad})" if bad else " (all clean)"))
                break
            if once and not _in_retry_wait(st):
                break
            if not progressed:
                time.sleep(WATCHDOG_POLL_S)
    finally:
        release_lock()
    return exit_code


def _in_retry_wait(st: dict) -> bool:
    return any(m["status"] == "RETRY_WAIT" for m in st["models"].values())


def write_final_summary(st: dict) -> None:
    rows = []
    for model in sorted(st["models"]):
        m = st["models"][model]
        rows.append({
            "model": model, "status": m["status"],
            "pages_done": m.get("pages_done", 0),
            "attempts_smoke": m["attempts_smoke"],
            "attempts_full": m["attempts_full"],
            "last_error": m.get("last_error"),
            "run_id": m.get("run_id") or (Path(m["run_dir"]).name if m.get("run_dir") else None),
        })
    summary = {
        "run_uid": st["run_uid"], "finished_at": utcnow(),
        "git_sha": st["git_sha"], "manifest_sha256": st["manifest_sha256"],
        "models": rows,
    }
    atomic_write_json(ORCH_DIR / "final_summary.json", summary)
    log(f"final summary -> {ORCH_DIR / 'final_summary.json'}")


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def cmd_status() -> int:
    if not STATE_PATH.exists():
        print("no orchestrator state yet")
        return 1
    st = json.loads(STATE_PATH.read_text())
    print(f"run_uid {st['run_uid']}  git {st['git_sha']}  "
          f"manifest {st['manifest_sha256'][:12]}  current: {st.get('current_model')}")
    print(f"{'model':44s} {'status':28s} {'stage':10s} {'pages':>5s} s/f att")
    for model in st["queue_order"] + st.get("precompleted", []):
        m = st["models"][model]
        print(f"{model:44s} {m['status']:28s} {m['stage']:10s} "
              f"{m.get('pages_done', 0):5d} {m['attempts_smoke']}/{m['attempts_full']}"
              + (f"  err={m['last_error'][:60]}" if m.get("last_error") else ""))
    lock = json.loads(LOCK_PATH.read_text()) if LOCK_PATH.exists() else None
    if lock:
        try:
            os.kill(lock["pid"], 0)
            alive = f"alive pid={lock['pid']}"
        except OSError:
            alive = f"STALE pid={lock['pid']}"
        print(f"lock: {alive} since {lock['started_at']}")
    else:
        print("lock: none")
    return 0


def cmd_stop() -> int:
    if not LOCK_PATH.exists():
        print("no supervisor running")
        return 1
    lock = json.loads(LOCK_PATH.read_text())
    st = json.loads(STATE_PATH.read_text()) if STATE_PATH.exists() else {}
    st["stop_requested"] = True
    save_state(st)
    try:
        os.kill(lock["pid"], signal.SIGTERM)
        print(f"SIGTERM sent to supervisor pid {lock['pid']}; "
              "current worker page will finish or be retried on resume")
    except OSError as exc:
        print(f"could not signal: {exc}")
        return 1
    return 0


def cmd_kill_worker() -> int:
    out = subprocess.run(["ps", "-eo", "pid,args"], capture_output=True, text=True)
    killed = 0
    for line in out.stdout.splitlines():
        if "run_official.py" in line and "grep" not in line:
            pid = int(line.split()[0])
            os.kill(pid, signal.SIGTERM)
            print(f"terminated worker pid {pid}")
            killed += 1
    if not killed:
        print("no worker process found")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("run")
    p.add_argument("--once", action="store_true",
                   help="single pass (testing)")
    sub.add_parser("status")
    sub.add_parser("stop")
    sub.add_parser("kill-worker")
    args = ap.parse_args()
    if args.cmd == "run":
        return run_loop(once=args.once)
    if args.cmd == "status":
        return cmd_status()
    if args.cmd == "stop":
        return cmd_stop()
    if args.cmd == "kill-worker":
        return cmd_kill_worker()
    return 2


if __name__ == "__main__":
    sys.exit(main())
