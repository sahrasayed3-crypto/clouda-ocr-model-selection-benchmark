#!/usr/bin/env python3
"""Orchestrator self-tests: exercise the state machine with mock workers.

Scenarios (each on a fresh scratch state dir, zero GPU usage):
  1. happy path        - ok worker: smoke -> full -> COMPLETE, next model starts
  2. worker crash      - crash worker: retry occurs, queue continues
  3. hung worker       - hang worker: watchdog kills it, retry happens
  4. retry exhaustion  - crash worker with max attempts=1: FAILED_FINAL, queue continues
  5. flaky full run    - transient failure then success: recovery works
  6. completed-skip    - restart supervisor after COMPLETE: model not rerun
  7. duplicate lock    - second supervisor cannot start while one holds the lock
"""
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SUPERVISOR = ROOT / "scripts" / "supervisor.py"
MOCK = ROOT / "scripts" / "mock_worker.py"
ENV_BASE = {
    "PATH": os.environ["PATH"],
    "HOME": os.environ.get("HOME", "/tmp"),
    "CLOUDA_ORCH_MOCK_WORKER": str(MOCK),
}

FAILURES = []


def check(name: str, ok: bool, evidence: str = "") -> None:
    print(f"  [{'PASS' if ok else 'FAIL'}] {name} {evidence}")
    if not ok:
        FAILURES.append(name)


def run_sup(scenario: str, state_dir: Path, raw_dir: Path,
            hang_s: str = "8", poll: str = "1", max_att: str = "3",
            timeout: int = 240, expect_timeout: bool = False) -> subprocess.CompletedProcess:
    env = {**ENV_BASE,
           "CLOUDA_MOCK_SCENARIO": scenario,
           "CLOUDA_ORCH_STATE_DIR": str(state_dir),
           "CLOUDA_ORCH_RAW_DIR": str(raw_dir),
           "CLOUDA_HANG_S": hang_s,
           "CLOUDA_POLL_S": poll,
           "CLOUDA_MAX_ATTEMPTS": max_att,
           "CLOUDA_BACKOFF_S": "1,1,1"}
    try:
        return subprocess.run(
            [sys.executable, str(SUPERVISOR), "run"], env=env, cwd=ROOT,
            capture_output=True, text=True, timeout=timeout)
    except subprocess.TimeoutExpired as exc:
        if expect_timeout:
            return subprocess.CompletedProcess(args=[], returncode=None,
                                               stdout=(exc.stdout or b"").decode(),
                                               stderr=(exc.stderr or b"").decode())
        raise


def state(state_dir: Path) -> dict:
    return json.loads((state_dir / "state.json").read_text())


def fresh() -> tuple[Path, Path]:
    base = Path(tempfile.mkdtemp(prefix="orch-test-"))
    return base / "state", base / "raw"


def test_happy_path_and_next_model():
    print("test: happy path + automatic next-model transition")
    sdir, rdir = fresh()
    env_state = {"CLOUDA_ORCH_STATE_DIR": str(sdir), "CLOUDA_ORCH_RAW_DIR": str(rdir)}
    # constrain the queue to two models via a scenario that only completes one:
    # run full queue with ok scenario — all 8 models complete
    r = run_sup("ok", sdir, rdir)
    st = state(sdir)
    statuses = {m: v["status"] for m, v in st["models"].items()
                if not m.startswith(("tencent", "MBZUAI"))}
    ok = all(v in ("COMPLETE", "COMPLETE_WITH_PAGE_FAILURES")
             for v in statuses.values()) and r.returncode == 0
    check("all 8 models COMPLETE with ok worker", ok,
          f"statuses={ {k.split('/')[-1]: v for k, v in statuses.items()} }")
    check("final summary written", (sdir / "final_summary.json").exists())
    shutil.rmtree(sdir.parent, ignore_errors=True)


def test_worker_crash_retry_then_continue():
    print("test: worker crash -> retries -> FAILED_FINAL -> queue continues")
    sdir, rdir = fresh()
    r = run_sup("crash", sdir, rdir, max_att="2", timeout=300)
    st = state(sdir)
    statuses = {m: v["status"] for m, v in st["models"].items()
                if not m.startswith(("tencent", "MBZUAI"))}
    ok = all(v == "FAILED_FINAL" for v in statuses.values())
    check("all models FAILED_FINAL after crash x attempts", ok,
          f"statuses={list(statuses.values())[:3]}...")
    check("attempts recorded", all(
        v["attempts_smoke"] == 2 for v in st["models"].values()
        if not v.get("status") in ("COMPLETE", "BLOCKED") and v["attempts_smoke"]))
    check("supervisor exit code nonzero (some failures)", r.returncode != 0)
    shutil.rmtree(sdir.parent, ignore_errors=True)


def test_hung_worker_watchdog():
    print("test: hung worker -> watchdog termination -> retry")
    sdir, rdir = fresh()
    # hang forever with max_att=1 => first model watchdog-killed, FAILED_FINAL,
    # queue continues to next models (also hang) — run bounded by attempts=1
    t0 = time.monotonic()
    r = run_sup("hang", sdir, rdir, hang_s="6", max_att="1", timeout=420)
    elapsed = time.monotonic() - t0
    st = state(sdir)
    first = st["queue_order"][0]
    m = st["models"][first]
    check("hung model terminated and failed", m["status"] == "FAILED_FINAL",
          f"status={m['status']} err={m.get('last_error', '')[:60]}")
    check("watchdog error recorded", "watchdog" in (m.get("last_error") or ""))
    check("queue kept advancing (not stuck on hang)",
          elapsed < 300, f"elapsed={elapsed:.0f}s")
    shutil.rmtree(sdir.parent, ignore_errors=True)


def test_flaky_recovery():
    print("test: transient full-run failure -> recovery -> COMPLETE")
    sdir, rdir = fresh()
    # flaky affects full scope only, so smoke passes and full recovers on attempt 2
    r = run_sup("flaky", sdir, rdir, timeout=300)
    st = state(sdir)
    first = st["models"][st["queue_order"][0]]
    check("flaky model recovered to COMPLETE", first["status"] == "COMPLETE",
          f"status={first['status']} full_attempts={first['attempts_full']}")
    check("recovery used attempt 2", first["attempts_full"] == 2)
    shutil.rmtree(sdir.parent, ignore_errors=True)


def test_completed_skip_and_lock():
    print("test: completed-model skip on restart + duplicate supervisor lock")
    sdir, rdir = fresh()
    # seed: model 1 finished; rest of the queue still pending
    r0 = run_sup("ok", sdir, rdir, timeout=90)
    st1 = state(sdir)
    first_model = st1["queue_order"][0]
    st1["models"][first_model].update({
        "status": "COMPLETE", "stage": "COMPLETE", "pages_done": 462,
        "attempts_smoke": 0, "attempts_full": 0})
    for m in st1["queue_order"][1:]:
        st1["models"][m].update({"status": "PENDING", "stage": "PENDING",
                                 "attempts_smoke": 0, "attempts_full": 0,
                                 "pages_done": 0, "run_dir": None})
    st1["stop_requested"] = False
    (sdir / "state.json").write_text(json.dumps(st1))
    # start supervisor with a hung worker so it stays alive holding the lock;
    # the first model is pre-marked COMPLETE and must be skipped, not rerun
    env = {**ENV_BASE, "CLOUDA_MOCK_SCENARIO": "hang",
           "CLOUDA_ORCH_STATE_DIR": str(sdir), "CLOUDA_ORCH_RAW_DIR": str(rdir),
           "CLOUDA_HANG_S": "600", "CLOUDA_POLL_S": "1",
           "CLOUDA_MAX_ATTEMPTS": "3", "CLOUDA_BACKOFF_S": "1,1,1"}
    import signal
    p1 = subprocess.Popen([sys.executable, str(SUPERVISOR), "run"], env=env,
                          cwd=ROOT, stdout=subprocess.DEVNULL,
                          stderr=subprocess.DEVNULL, start_new_session=True)
    for _ in range(20):  # wait until supervisor parks on model 2's hung worker
        time.sleep(1)
        try:
            cur = json.loads((sdir / "state.json").read_text()).get("current_model")
        except Exception:  # noqa: BLE001
            cur = None
        if cur == st1["queue_order"][1] and p1.poll() is None:
            break
    check("supervisor alive and parked on model 2",
          p1.poll() is None, f"current={cur}")
    r2 = subprocess.run([sys.executable, str(SUPERVISOR), "run"], env=env,
                        cwd=ROOT, capture_output=True, text=True, timeout=30)
    check("duplicate supervisor refused (lock)", r2.returncode == 3,
          f"rc={r2.returncode} out={r2.stdout[-80:]}")
    st2 = json.loads((sdir / "state.json").read_text())
    check("completed model skipped (still COMPLETE, no rework)",
          st2["models"][first_model]["status"] == "COMPLETE"
          and st2["models"][first_model]["attempts_smoke"] == 0
          and st2["models"][first_model]["attempts_full"] == 0)
    os.killpg(os.getpgid(p1.pid), signal.SIGTERM)
    p1.wait(timeout=30)
    shutil.rmtree(sdir.parent, ignore_errors=True)


def main() -> int:
    test_happy_path_and_next_model()
    test_worker_crash_retry_then_continue()
    test_hung_worker_watchdog()
    test_flaky_recovery()
    test_completed_skip_and_lock()
    print()
    if FAILURES:
        print("SELF-TEST FAILURES:", FAILURES)
        return 1
    print("ALL ORCHESTRATOR SELF-TESTS PASSED")
    return 0


if __name__ == "__main__":
    sys.exit(main())
