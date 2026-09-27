#!/usr/bin/env bash
# One-command control interface for the autonomous benchmark orchestrator.
#   benchmark_ctl.sh start    - launch the supervisor detached (survives session end)
#   benchmark_ctl.sh status   - queue status table
#   benchmark_ctl.sh stop     - graceful stop (state preserved, resume continues)
#   benchmark_ctl.sh resume   - alias of start (state-aware; skips completed)
#   benchmark_ctl.sh progress - current model + page progress
set -u
cd "$(dirname "$0")/.."
ORCH=outputs/orchestrator
mkdir -p "$ORCH/logs"

case "${1:-}" in
  start|resume)
    if [ -f "$ORCH/lock.json" ]; then
      PID=$(python3 -c "import json;print(json.load(open('$ORCH/lock.json'))['pid'])" 2>/dev/null || echo dead)
      if kill -0 "$PID" 2>/dev/null; then
        echo "supervisor already running (pid $PID)"; exit 0
      else
        echo "removing stale lock (owner pid $PID is dead)"
        rm -f "$ORCH/lock.json"
      fi
    fi
    setsid nohup .venv-gpu/bin/python scripts/supervisor.py run \
      >>"$ORCH/logs/supervisor.log" 2>&1 &
    disown
    sleep 2
    NEWPID=$(python3 -c "import json;print(json.load(open('$ORCH/lock.json'))['pid'])" 2>/dev/null || echo "?")
    echo "supervisor launched detached (pid $NEWPID, own session — survives ZCode/SSH disconnect)"
    ;;
  status)
    exec .venv-gpu/bin/python scripts/supervisor.py status
    ;;
  stop)
    exec .venv-gpu/bin/python scripts/supervisor.py stop
    ;;
  progress)
    .venv-gpu/bin/python scripts/supervisor.py status | head -8
    echo "---"
    tail -3 "$ORCH/logs/supervisor.log"
    ;;
  *)
    echo "usage: scripts/benchmark_ctl.sh {start|status|stop|resume|progress}"; exit 2
    ;;
esac
