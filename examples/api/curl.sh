#!/usr/bin/env bash
# REST API examples using curl.
#
# Start a server first (in another terminal):
#   python examples/api/serve.py --db atlas.db --port 8000
#
# Then run:
#   bash examples/api/curl.sh
set -euo pipefail

BASE="${BASE_URL:-http://127.0.0.1:8000}"

echo "== health =="
curl -s "${BASE}/health"; echo

echo "== version =="
curl -s "${BASE}/version"; echo

echo "== import a directory (server-side path) =="
curl -s -X POST "${BASE}/meetings/import" \
  -H 'Content-Type: application/json' \
  -d '{"path": "examples/history", "recursive": true}'; echo

echo "== list meetings =="
curl -s "${BASE}/meetings?limit=5"; echo

echo "== search =="
curl -s "${BASE}/search?q=postgres&limit=5"; echo

echo "== memories filtered by type =="
curl -s "${BASE}/memories?type=decision&limit=5"; echo

echo "== graph summary =="
curl -s "${BASE}/graph"; echo

echo "== insights =="
curl -s "${BASE}/insights?limit=5"; echo

echo "== metrics =="
curl -s "${BASE}/metrics"; echo

echo "== recommendations =="
curl -s "${BASE}/recommendations?limit=5"; echo

echo "== rendered report (markdown) =="
curl -s "${BASE}/reports?format=markdown"; echo

echo "== run an inline automation pipeline =="
curl -s -X POST "${BASE}/automation/run" \
  -H 'Content-Type: application/json' \
  -d '{"pipeline": {"name": "report", "steps": [{"type": "graph"}, {"type": "intelligence"}]}}'; echo

echo "== OpenAPI document =="
curl -s "${BASE}/openapi.json" | head -c 200; echo
