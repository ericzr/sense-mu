#!/usr/bin/env bash
set -euo pipefail

api_port="${SENSEMU_E2E_API_PORT:-8001}"
web_port="${SENSEMU_E2E_WEB_PORT:-3102}"

export SENSEMU_E2E_API_PORT="$api_port"
export SENSEMU_E2E_WEB_PORT="$web_port"
export SENSEMU_API_URL="http://127.0.0.1:${api_port}"
export VITE_SENSEMU_API_URL="$SENSEMU_API_URL"
export NEXT_PUBLIC_SENSEMU_API_URL="$SENSEMU_API_URL"
export SENSEMU_PREVIEW_MODE="false"
export NEXT_PUBLIC_SENSEMU_PREVIEW_MODE="false"

npm run build
npx --no-install playwright test --config=playwright.local.config.ts
