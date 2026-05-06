#!/usr/bin/env bash
set -euo pipefail

ALERTMANAGER_URL="${ALERTMANAGER_URL:-http://localhost:9093}"

echo "Starting Anti-DDoS alert simulation."

if command -v docker >/dev/null 2>&1; then
  if docker ps --format '{{.Names}}' | grep -qx 'wanguard_exporter'; then
    docker stop wanguard_exporter >/dev/null
    echo "Stopped wanguard_exporter to trigger scrape/exporter alerts."
  else
    echo "wanguard_exporter container is not running; skipping container stop."
  fi
fi

curl -fsS -H "Content-Type: application/json" -d '[
  {
    "labels": {
      "alertname": "BGPBlastRadiusExceeded",
      "severity": "critical",
      "tier": "vip",
      "team": "network",
      "instance": "edge-router-1"
    },
    "annotations": {
      "summary": "MOCK TEST: BGP route leak or mass blackhole suspected",
      "description": "Chaos test injected more than 500 mock routes in 5 minutes."
    }
  }
]' "$ALERTMANAGER_URL/api/v1/alerts"

echo "Injected mock BGP blast-radius alert into Alertmanager."

if command -v docker >/dev/null 2>&1; then
  echo "Restarting wanguard_exporter in 30 seconds."
  sleep 30
  docker start wanguard_exporter >/dev/null || true
fi

echo "Simulation completed."
