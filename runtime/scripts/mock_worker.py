#!/usr/bin/env python3
"""Mock worker for orchestrator self-tests (never touches the GPU).

Usage (invoked by the supervisor via CLOUDA_ORCH_MOCK_WORKER):
  mock_worker.py <model> <scope>

Scenario comes from CLOUDA_MOCK_SCENARIO:
  ok      - write expected pages, exit 0
  crash   - write half the pages, exit 1
  hang    - write one page, then sleep forever (watchdog must kill it)
  flaky   - full scope: exit 1 on first attempt, succeed on later attempts
Writes fake page records into CLOUDA_ORCH_RAW_DIR with the standard run-dir
naming so the supervisor's discovery/validation see realistic artifacts.
"""
import json
import os
import sys
import time
import uuid
from pathlib import Path

model, scope = sys.argv[1], sys.argv[2]
scenario = os.environ.get("CLOUDA_MOCK_SCENARIO", "ok")
raw_root = Path(os.environ["CLOUDA_ORCH_RAW_DIR"])
expected = 5 if scope == "smoke" else 462

slug = model.replace("/", "-").replace("_", "-").replace(".", "-").lower()
run_dir = raw_root / f"{slug}__{scope}__mockrun"
run_dir.mkdir(parents=True, exist_ok=True)
counter = run_dir / ".attempts"
n = int(counter.read_text()) + 1 if counter.exists() else 1
counter.write_text(str(n))

if scenario == "flaky" and scope == "full" and n == 1:
    print("flaky: simulated transient failure", flush=True)
    sys.exit(1)

count = expected if scenario != "crash" else expected // 2
if scenario == "hang":
    count = 1
for i in range(count):
    page = {
        "page_id": f"PAGE-{i:04d}", "status": "PASS",
        "raw_output": "mock", "run_id": run_dir.name,
    }
    tmp = run_dir / f"PAGE-{i:04d}.json.tmp-{uuid.uuid4().hex[:6]}"
    tmp.write_text(json.dumps(page))
    os.replace(tmp, run_dir / f"PAGE-{i:04d}.json")
    time.sleep(0.01)

if scenario == "hang":
    print("hanging forever", flush=True)
    time.sleep(10_000)

if scenario == "crash":
    print("crash: simulated worker death", flush=True)
    sys.exit(1)
print("mock ok", flush=True)
