#!/usr/bin/env bash
set -euo pipefail

repo_root="$(cd "$(dirname "$0")/../../.." && pwd)"
api_port="${SENSEMU_E2E_API_PORT:-8001}"
web_port="${SENSEMU_E2E_WEB_PORT:-3102}"
e2e_dir="$(mktemp -d "${TMPDIR:-/tmp}/sensemu-e2e.XXXXXX")"
api_pid=""

cleanup() {
  if [[ -n "$api_pid" ]]; then
    kill "$api_pid" 2>/dev/null || true
    wait "$api_pid" 2>/dev/null || true
  fi
  rm -rf "$e2e_dir"
}
trap cleanup EXIT INT TERM

export PYTHONPATH="$repo_root/apps/api/src"
export SENSEMU_ENVIRONMENT="development"
export SENSEMU_AUTH_MODE="development"
export SENSEMU_DATABASE_URL="sqlite+pysqlite:///$e2e_dir/sensemu.db"
export SENSEMU_OBJECT_STORAGE_ENDPOINT="local://"
export SENSEMU_OBJECT_STORAGE_LOCAL_PATH="$e2e_dir/objects"
export SENSEMU_API_PUBLIC_URL="http://127.0.0.1:${api_port}"
export SENSEMU_WEB_ORIGIN="http://127.0.0.1:${web_port}"
export SENSEMU_CELERY_BROKER_URL="memory://"

cd "$repo_root/apps/api"
"$repo_root/.venv/bin/python" -m alembic upgrade head
"$repo_root/.venv/bin/python" -m uvicorn sensemu_api.main:app \
  --host 127.0.0.1 \
  --port "$api_port" &
api_pid="$!"
wait "$api_pid"
