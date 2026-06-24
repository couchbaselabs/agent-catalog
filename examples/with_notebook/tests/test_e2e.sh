#!/usr/bin/env bash

# End-to-end runner for examples/with_notebook.
# Steps:
# 1) run directly in the example directory
# 2) start local Couchbase in Docker and initialize cluster + travel-sample bucket
# 3) run poetry install, agentc init, and first git commit
# 4) start Jupyter notebook server and verify API status endpoint

set -euo pipefail

EXAMPLE_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
CB_CONTAINER="agentc-e2e-cb-notebook-$$"
JUPYTER_PID=""
GIT_BACKUP_DIR=""
GIT_CREATED=0
RUN_POETRY_INSTALL="${RUN_POETRY_INSTALL:-0}"
USE_POETRY_RUN="${USE_POETRY_RUN:-0}"

log() {
  echo "[e2e-notebook] $*"
}

fail() {
  echo "[e2e-notebook] ERROR: $*" >&2
  exit 1
}

cleanup() {
  local ec=$?
  if [ -n "$JUPYTER_PID" ] && kill -0 "$JUPYTER_PID" 2>/dev/null; then
    kill "$JUPYTER_PID" 2>/dev/null || true
    wait "$JUPYTER_PID" 2>/dev/null || true
  fi

  if docker ps -a --format '{{.Names}}' | grep -Fxq "$CB_CONTAINER"; then
    docker rm -f "$CB_CONTAINER" >/dev/null 2>&1 || true
  fi

  if [ "$GIT_CREATED" = "1" ] && [ -d "$EXAMPLE_DIR/.git" ]; then
    rm -rf "$EXAMPLE_DIR/.git"
  fi

  if [ -n "$GIT_BACKUP_DIR" ] && [ -d "$GIT_BACKUP_DIR" ]; then
    mv "$GIT_BACKUP_DIR" "$EXAMPLE_DIR/.git"
  fi

  exit "$ec"
}
trap cleanup EXIT

wait_http() {
  local url="$1"
  local timeout_secs="$2"
  python3 - "$url" "$timeout_secs" <<'PY'
import sys
import time
import urllib.request

url = sys.argv[1]
timeout_secs = int(sys.argv[2])
end = time.time() + timeout_secs
last_error = None

while time.time() < end:
    try:
        with urllib.request.urlopen(url, timeout=3) as resp:
            if 200 <= resp.status < 500:
                sys.exit(0)
    except Exception as exc:
        last_error = exc
    time.sleep(1)

print(f"Timed out waiting for {url}; last_error={last_error}", file=sys.stderr)
sys.exit(1)
PY
}

require_cmd() {
  command -v "$1" >/dev/null 2>&1 || fail "Missing required command: $1"
}

run_app_cmd() {
  if [ "$USE_POETRY_RUN" = "1" ]; then
    poetry run "$@"
  else
    "$@"
  fi
}

log "Validating prerequisites"
require_cmd docker
require_cmd git
require_cmd curl
require_cmd python3
if [ "$USE_POETRY_RUN" = "1" ] || [ "$RUN_POETRY_INSTALL" = "1" ]; then
  require_cmd poetry
fi

[ -f "$EXAMPLE_DIR/.env" ] || fail "Missing $EXAMPLE_DIR/.env"

log "Running in example directory: $EXAMPLE_DIR"
cd "$EXAMPLE_DIR"

set -a
. "$EXAMPLE_DIR/.env"
set +a

CB_USER="${AGENT_CATALOG_USERNAME:-Administrator}"
CB_PASS="${AGENT_CATALOG_PASSWORD:-password}"

log "Starting Couchbase container: $CB_CONTAINER"
docker run -d --name "$CB_CONTAINER" \
  -p 8091-8096:8091-8096 \
  -p 11210-11211:11210-11211 \
  couchbase >/dev/null

log "Waiting for Couchbase management endpoint"
wait_http "http://127.0.0.1:8091/ui/index.html" 240

log "Initializing Couchbase cluster"
docker exec "$CB_CONTAINER" couchbase-cli cluster-init \
  -c 127.0.0.1:8091 \
  --cluster-username "$CB_USER" \
  --cluster-password "$CB_PASS" \
  --services data,index,query,fts,analytics \
  --cluster-ramsize 2048 \
  --cluster-index-ramsize 512 >/dev/null

log "Installing travel-sample bucket"
curl -sS -u "$CB_USER:$CB_PASS" \
  -H "Content-Type: application/json" \
  -X POST "http://127.0.0.1:8091/sampleBuckets/install" \
  -d '["travel-sample"]' >/dev/null

log "Waiting for travel-sample bucket"
python3 - <<'PY'
import base64
import os
import sys
import time
import urllib.request

user = os.environ.get("AGENT_CATALOG_USERNAME", "Administrator")
password = os.environ.get("AGENT_CATALOG_PASSWORD", "password")
url = "http://127.0.0.1:8091/pools/default/buckets/travel-sample"
req = urllib.request.Request(url)
auth = (f"{user}:{password}").encode("utf-8")
req.add_header("Authorization", "Basic " + base64.b64encode(auth).decode("ascii"))

end = time.time() + 300
while time.time() < end:
    try:
        with urllib.request.urlopen(req, timeout=4) as resp:
            if resp.status == 200:
                sys.exit(0)
    except Exception:
        pass
    time.sleep(2)

print("Timed out waiting for travel-sample bucket", file=sys.stderr)
sys.exit(1)
PY

if [ "$RUN_POETRY_INSTALL" = "1" ]; then
  log "Installing example dependencies"
  # Ensure clean environment
  if [ -n "${VIRTUAL_ENV:-}" ]; then
    log "Deactivating existing virtual environment"
    deactivate 2>/dev/null || true
  fi

  # Remove lock file to ensure fresh install
  log "Cleaning Poetry cache and lock files"
  rm -f poetry.lock
  poetry install
fi

log "Preparing git repository in example directory"
if [ -d "$EXAMPLE_DIR/.git" ]; then
  GIT_BACKUP_DIR="$EXAMPLE_DIR/.git.e2e_backup_$$"
  mv "$EXAMPLE_DIR/.git" "$GIT_BACKUP_DIR"
fi

git init >/dev/null
GIT_CREATED=1
git config user.name "agentc-e2e"
git config user.email "agentc-e2e@example.com"

log "Running agentc init"
run_app_cmd agentc init --add-hook-for .

log "Creating initial commit"
git add -A
git commit --no-gpg-sign -m "Initial commit (e2e)" >/dev/null

log "Starting Jupyter notebook server"
run_app_cmd jupyter notebook \
  --no-browser \
  --ip=127.0.0.1 \
  --port=8888 \
  --NotebookApp.token=e2e \
  --NotebookApp.password='' > "$EXAMPLE_DIR/.e2e_notebook.log" 2>&1 &
JUPYTER_PID=$!

log "Waiting for Jupyter API endpoint"
wait_http "http://127.0.0.1:8888/api/status?token=e2e" 180

log "E2E success: Jupyter notebook server is up"
log "Server log: $EXAMPLE_DIR/.e2e_notebook.log"

# Keep script running in foreground, waiting for Ctrl-C
echo "$JUPYTER_PID"
wait "$JUPYTER_PID"

