#!/usr/bin/env bash
# Start Cloud SQL Auth Proxy for local Django development.
# Auth uses Application Default Credentials (gcloud auth application-default login)
# or GOOGLE_APPLICATION_CREDENTIALS. No authorized-network IP is required.
set -euo pipefail

INSTANCE="${CLOUD_SQL_INSTANCE:-esaasolution:us-central1:sbtacedemy}"
PORT="${CLOUD_SQL_PROXY_PORT:-5433}"
CREDENTIALS_ARGS=()

if ! command -v cloud-sql-proxy >/dev/null 2>&1; then
  echo "cloud-sql-proxy not found. Install with:"
  echo "  brew install cloud-sql-proxy"
  exit 1
fi

if [[ -n "${GOOGLE_APPLICATION_CREDENTIALS:-}" && -f "${GOOGLE_APPLICATION_CREDENTIALS}" ]]; then
  CREDENTIALS_ARGS+=(--credentials-file="${GOOGLE_APPLICATION_CREDENTIALS}")
  echo "Using GOOGLE_APPLICATION_CREDENTIALS=${GOOGLE_APPLICATION_CREDENTIALS}"
elif [[ -f ".credentials/esaasolution-a507eae37ccb.json" ]]; then
  CREDENTIALS_ARGS+=(--credentials-file="$(pwd)/.credentials/esaasolution-a507eae37ccb.json")
  echo "Using $(pwd)/.credentials/esaasolution-a507eae37ccb.json"
else
  echo "Using Application Default Credentials (gcloud auth application-default login)"
fi

if lsof -nP -iTCP:"${PORT}" -sTCP:LISTEN >/dev/null 2>&1; then
  echo "Port ${PORT} is already in use. Proxy may already be running."
  echo "Point local Django at: DB_HOST=127.0.0.1 DB_PORT=${PORT}"
  exit 0
fi

echo "Starting Cloud SQL Auth Proxy"
echo "  instance: ${INSTANCE}"
echo "  listen:   127.0.0.1:${PORT}"
echo
echo "In .env use:"
echo "  DB_ENGINE=postgresql"
echo "  DB_HOST=127.0.0.1"
echo "  DB_PORT=${PORT}"
echo "  DB_SSLMODE=disable"
echo
echo "Press Ctrl+C to stop."
echo

exec cloud-sql-proxy "${INSTANCE}" \
  --address=127.0.0.1 \
  --port="${PORT}" \
  "${CREDENTIALS_ARGS[@]}"