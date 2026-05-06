# VNSO Anti-DDoS Observability Overlay

This overlay deploys a Prometheus-based observability stack for a Wanguard-equivalent Anti-DDoS environment. It is intentionally kept under `deploy/vnso-ddos-observability/` so the Prometheus upstream source tree stays clean.

## Quick Start

Run commands from the repo root (`/root/prometheus`).

```bash
cp .env.example .env
docker compose -f deploy/vnso-ddos-observability/docker-compose.yml --env-file .env up -d --build
```

The root `.env` file is ignored by git. It should contain the Grafana admin user/password and Wanguard API token.

## URLs

- Prometheus: `http://localhost:9090`
- Alertmanager: `http://localhost:9093`
- Grafana: `http://localhost:3000`
- Wanguard exporter metrics: `http://localhost:9100/metrics`
- Blackbox exporter: `http://localhost:9115`

## Validate

```bash
deploy/vnso-ddos-observability/scripts/validate.sh
```

## Service Discovery

Prometheus uses file-based service discovery. Edit these files instead of editing `prometheus.yml` for each node:

- `prometheus/targets/routers/router-nodes.json`
- `prometheus/targets/filters/filter-nodes.json`
- `prometheus/targets/sensors/sensor-nodes.json`
- `prometheus/targets/vips/vip-targets.json`

Prometheus reloads these target files automatically.

## Network Layer Blocking

Prometheus does not block traffic. It monitors and alerts. Blocking belongs to BGP Flowspec/RTBH, router ACLs, Wanguard Console actions, and XDP/eBPF/DPDK filters. See `docs/network-layer-coverage.md` for the current monitoring and mitigation matrix.

## Alert Receiver Secrets

The committed Alertmanager config uses valid placeholder Slack and PagerDuty values so validation can run without secrets. Replace those placeholders through your secret-rendering process or deployment platform before production.
