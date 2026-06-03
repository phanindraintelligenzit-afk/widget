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

# We rely on `jq` to strip the human-friendly _label field from each fixture
# before posting. The engine doesn't care about _label but Pydantic would.
if ! command -v jq >/dev/null; then
  echo "ERROR: this script needs jq (apt install jq / brew install jq)" >&2
  exit 1
fi

post() {
  local path="$1" file="$2"
  jq 'del(._label)' "$file" | curl -fsS -X POST "${BASE}${path}" \
      -H 'Content-Type: application/json' --data-binary @- > /dev/null
}

echo "=> Waiting for ${BASE}/healthz ..."
until curl -fsS "${BASE}/healthz" >/dev/null 2>&1; do sleep 0.3; done

echo "=> Seeding canonical observations (M0–M3 path)"
for name in strong baseline unsafe; do
  post "/ingest" "fixtures/obs_${name}.json"
done

echo "=> Seeding Acme via YAML mapping (M2 universal fallback)"
post "/ingest/webhook:acme" "fixtures/raw_acme_payload.json"

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
