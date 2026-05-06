#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

echo "Validating JSON service-discovery and dashboard files..."
find "$ROOT_DIR" -name "*.json" -print0 | while IFS= read -r -d '' json_file; do
  python3 -m json.tool "$json_file" >/dev/null
done

echo "Validating Wanguard exporter Python syntax..."
python3 - <<PY
from pathlib import Path

source_path = Path("$ROOT_DIR/exporter/wanguard_exporter.py")
compile(source_path.read_text(), str(source_path), "exec")
PY

if command -v docker >/dev/null 2>&1; then
  echo "Validating Prometheus config with promtool..."
  docker run --rm --entrypoint promtool -v "$ROOT_DIR/prometheus:/etc/prometheus:ro" prom/prometheus:v3.11.2 \
    check config /etc/prometheus/prometheus.yml

  echo "Validating Prometheus rules with promtool..."
  for rule_file in "$ROOT_DIR"/prometheus/rules/*.yml; do
    docker run --rm --entrypoint promtool -v "$ROOT_DIR/prometheus:/etc/prometheus:ro" prom/prometheus:v3.11.2 \
      check rules "/etc/prometheus/rules/$(basename "$rule_file")"
  done

  echo "Validating Alertmanager config with amtool..."
  docker run --rm --entrypoint amtool -v "$ROOT_DIR/alertmanager:/etc/alertmanager:ro" prom/alertmanager:v0.28.1 \
    check-config /etc/alertmanager/alertmanager.yml
else
  echo "Docker is not installed; skipped promtool and amtool validation."
fi

echo "Validation completed."
