#!/usr/bin/env bash
# Seeds the DPI-LS demo by POSTing every fixture through the right ingest path.
# Run after `uvicorn api.app:app` is listening.
#
#   ./scripts/demo_seed.sh                      # uses http://localhost:8000
#   ./scripts/demo_seed.sh http://host:port     # custom base URL
#
# After this runs, open the API root in a browser — it redirects to the live
# board and per-agent demo.
set -euo pipefail

BASE="${1:-http://localhost:8000}"
REPO_ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_ROOT"

# We rely on `jq` or Python to strip the human-friendly _label field from each fixture
# before posting. The engine doesn't care about _label but Pydantic would.
USE_JQ=false
if command -v jq >/dev/null; then
  USE_JQ=true
elif command -v python >/dev/null; then
  PYTHON_CMD=python
elif command -v python3 >/dev/null; then
  PYTHON_CMD=python3
else
  echo "ERROR: this script needs jq or Python (python/python3) installed" >&2
  exit 1
fi

strip_label() {
  local file="$1"
  if [ "$USE_JQ" = true ]; then
    jq 'del(._label)' "$file"
  else
    "$PYTHON_CMD" -c 'import json, sys; obj=json.load(open(sys.argv[1])); obj.pop("_label", None); json.dump(obj, sys.stdout, separators=(",", ":"))' "$file"
  fi
}

post() {
  local path="$1" file="$2"
  strip_label "$file" | curl -fsS -X POST "${BASE}${path}" \
      -H 'Content-Type: application/json' --data-binary @- > /dev/null
}

adapter_registered() {
  local name="$1"
  if command -v curl >/dev/null; then
    curl -fsS "${BASE}/adapters" | "$PYTHON_CMD" -c 'import json, sys; names=[a.get("name") for a in json.load(sys.stdin)]; print("true" if "'"$name"'" in names else "false")'
  else
    echo false
  fi
}

echo "=> Waiting for ${BASE}/healthz ..."
until curl -fsS "${BASE}/healthz" >/dev/null 2>&1; do sleep 0.3; done

echo "=> Seeding canonical observations (M0–M3 path)"
for name in strong baseline unsafe; do
  post "/ingest" "fixtures/obs_${name}.json"
done

echo "=> Seeding Acme via YAML mapping (M2 universal fallback)"
if [ "$(adapter_registered "webhook:acme")" = "true" ]; then
  post "/ingest/webhook:acme" "fixtures/raw_acme_payload.json"
else
  echo "WARNING: webhook:acme adapter is not registered on ${BASE}. Skipping Acme mapping seed."
  echo "         Start the server with MAPPINGS_DIR=./fixtures to enable it."
fi

echo "=> Seeding OTel spans (M2)"
curl -fsS -X POST "${BASE}/ingest/otel" \
    -H 'Content-Type: application/json' \
    --data-binary @fixtures/otel_spans.json > /dev/null

echo "=> Seeding multi-source story (M5): aws_cost, puvi_noise, arize, servicenow, jira"
for src in aws_cost puvi_noise arize servicenow jira; do
  post "/ingest/source/${src}" "fixtures/source_${src}.json"
done

echo
echo "=> Done. Visit ${BASE}/ in a browser."
echo "   The board polls every 3s. Try the SME widget on agent-multi-001."
