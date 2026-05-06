# `prometheus` - AI Context Pack (VNSO PRO v4.1)

> **Purpose.** Complete operational and technical context for AI agents, SREs, and network engineers working with the Prometheus-based observability overlay for VNSO's Wanguard-equivalent Anti-DDoS environment. Read this file before changing monitoring, alerting, dashboards, exporters, or deployment files.
>
> **Audience.** AI coding agents (Copilot, Claude, Cursor), Network SREs, Security Architects, on-call engineers.
>
> **Current date.** 2026-05-04.
>
> **Code is truth.** The Prometheus source tree remains upstream-compatible. VNSO deployment assets live under `deploy/vnso-ddos-observability/`.

---

## §1 - Security Hard Rules

**Grafana admin user:** `admin@vnso.vn`.

**Grafana admin password:** never write the real password in Markdown, YAML, JSON, source code, or committed examples. For local operations this repo uses root `.env`, which is ignored by git. For production, retrieve the value from AWS Secrets Manager or Vault, path `secret/grafana/admin`.

**Hard rule:** do not reintroduce raw passwords into `AI_CONTEXT.md`, compose files, Prometheus configs, Alertmanager configs, dashboard JSON, exporter source, or CI files.

**Secret injection model:**

- Local/dev: root `.env` provides `GRAFANA_ADMIN_USER`, `GRAFANA_ADMIN_PASSWORD`, `WANGUARD_API_TOKEN`, and ClickHouse values.
- Alertmanager receivers in git use safe placeholder URLs. Replace them through your secret-rendering process or deployment platform before production.
- Production: CI/CD or orchestration should inject these values from a secrets manager.
- Committed sample: root `.env.example` documents required variable names only.

---

## §2 - System Purpose & Scope

**What.** Prometheus is the observability and alerting plane for the Anti-DDoS stack. It monitors health, capacity, API state, BGP mitigation signals, external reachability, and aggregate packet/traffic counters.

**What Prometheus does not do.** Prometheus does not block traffic, inject BGP routes, parse raw NetFlow into per-IP labels, or execute mitigation actions. It observes and alerts. Blocking is performed by Wanguard/Console actions, router BGP Flowspec/RTBH, ACLs, or XDP/eBPF/DPDK filters.

**Data strategy:**

- **Prometheus scope in:** CPU, RAM, disk, SoftIRQ, NIC drops, SNMP interface counters, BGP session/export state, Wanguard API health, active mitigations, XDP/eBPF drop/pass counters, external blackbox probes.
- **Prometheus scope out:** raw NetFlow/sFlow/IPFIX, source IP, destination IP, source/destination port, flow ID, packet payload, packet logs.
- **ClickHouse/Flow DB scope:** raw flow analytics, top talkers, source/destination IP investigation, historical attack forensics.

**Risk class:** CRITICAL. Prometheus downtime during a volumetric DDoS event means the NOC/SRE team loses visibility.

---

## §3 - Repository Layout

This repo is the Prometheus source tree plus a VNSO deployment overlay.

```text
.
├── AI_CONTEXT.md
├── .env                         # local secrets, ignored by git
├── .env.example                 # committed variable names only
└── deploy/
    └── vnso-ddos-observability/
        ├── docker-compose.yml
        ├── README.md
        ├── alertmanager/alertmanager.yml
        ├── blackbox/config.yml
        ├── clickhouse/init-flow-db.sql
        ├── docs/network-layer-coverage.md
        ├── exporter/
        │   ├── Dockerfile
        │   ├── requirements.txt
        │   └── wanguard_exporter.py
        ├── grafana/
        │   ├── dashboards/ddos_overview.json
        │   └── provisioning/
        │       ├── dashboards/dashboard.yml
        │       └── datasources/datasource.yml
        ├── prometheus/
        │   ├── prometheus.yml
        │   ├── rules/
        │   │   ├── ddos_alerts.yml
        │   │   ├── infra_alerts.yml
        │   │   └── recording.yml
        │   └── targets/
        │       ├── filters/filter-nodes.json
        │       ├── routers/router-nodes.json
        │       ├── sensors/sensor-nodes.json
        │       └── vips/vip-targets.json
        └── scripts/
            ├── simulate_attack.sh
            └── validate.sh
```

AI agents must place VNSO observability changes under `deploy/vnso-ddos-observability/` unless the user explicitly asks to modify Prometheus core source code.

---

## §4 - Anti-DDoS Architecture & Traffic Flow

```text
[Internet / Transit / Peering]
          |
          v
   [Edge Routers]
   - Monitor: snmp_exporter, bgp_exporter
   - Mitigation: BGP Flowspec / RTBH / upstream blackhole
          |
          v
   [Core Switches]
   - Monitor: SNMP counters, interface drops/errors
   - Flow analytics: NetFlow/sFlow/IPFIX to ClickHouse pipeline
          |
          +--> [Sensors]
          |    - Monitor: node_exporter, SoftIRQ, flow ingest status
          |    - Role: detection only, no packet blocking
          |
          +--> [Console / Wanguard API]
          |    - Monitor: wanguard_exporter middleware on :9100
          |    - Role: response/action/precondition orchestration
          |
          +--> [Filters / Scrubbing Nodes]
               - Monitor: node_exporter, eBPF/XDP counters, NIC drops
               - Mitigation: XDP/eBPF/DPDK/nftables controlled by Console

[External vantage point]
          |
          v
   [blackbox_exporter]
   - Monitor: VIP HTTP/TCP/ICMP reachability and false positives

[Out-of-Band Management Network]
   Prometheus, exporters, Alertmanager, Grafana, Console API, and routers must use OOB or high-priority management VLAN paths for scraping and control traffic.
```

---

## §5 - Network Layer Coverage

| Layer | Monitoring in this repo | Blocking/mitigation path | Status |
| --- | --- | --- | --- |
| Edge router / L3 | `bgp_routers`, `snmp_exporter`, `bgp_session_up`, `bgp_prefixes_exported` | BGP Flowspec, RTBH, upstream blackhole | Config and alerts included; router policy must exist outside Prometheus |
| Core switch / L2-L3 | SNMP interface counters, errors, drops; flow pipeline documented | ACL/storm-control/manual NMS, not Prometheus | Monitoring hooks included; blocking remains network-device policy |
| Sensor / detection | `ddos_sensors`, SoftIRQ, sensor status via Wanguard exporter | No blocking; detection only | Config and alerts included |
| Console/API control plane | `wanguard_exporter` converts REST JSON to OpenMetrics | Response -> Action -> Precondition engine controls BGP/filter actions | Exporter included; actual API credentials required |
| Filter / scrubbing | `ddos_filters`, XDP/eBPF drop/pass counters, capacity alerts | XDP/eBPF/DPDK/nftables/ACL applied by Console/actions | Monitoring included; packet filters must be deployed on filter nodes |
| Protected VIP reachability | `blackbox_vip_check` | Alert only; no direct blocking | Config included |
| Flow analytics | ClickHouse schema for raw flows | No blocking; forensics and top talkers | Schema included; collector such as goflow2/pmacct still required |

**Answer to the current review question:** the project now has monitoring coverage for the main network layers at configuration and alerting level. Actual packet blocking is not implemented by Prometheus; it is delegated to BGP Flowspec/RTBH and filter-node XDP/eBPF/DPDK controls driven by the Console/Wanguard action layer.

---

## §6 - Cardinality & Data Contracts

**Anti-DDoS cardinality rule:** never put raw IPs or ports into Prometheus labels.

Forbidden labels:

- `source_ip`
- `dest_ip`
- `src_port`
- `dst_port`
- `flow_id`
- `packet_id`
- raw URL paths with customer IDs or request IDs

Allowed bounded labels:

- `protocol`
- `tcp_flag`
- `asn`
- `country`
- `protected_subnet`
- `mitigation_action`
- `api_endpoint`
- `sensor_id`
- `filter_id`
- `router_id`
- `tier` (`vip` or `standard`)

Raw IP/port analytics belong in ClickHouse, not Prometheus.

---

## §7 - Configuration Surface

Key files:

- `deploy/vnso-ddos-observability/docker-compose.yml`: Prometheus, Alertmanager, Grafana, blackbox exporter, Wanguard exporter, optional ClickHouse.
- `deploy/vnso-ddos-observability/prometheus/prometheus.yml`: scrape tiers, `file_sd_configs`, alertmanager wiring.
- `deploy/vnso-ddos-observability/prometheus/rules/ddos_alerts.yml`: Anti-DDoS, Wanguard, BGP, false positive, license, sensor alerts.
- `deploy/vnso-ddos-observability/prometheus/rules/infra_alerts.yml`: host down, disk, CPU, SoftIRQ, NIC drops, Prometheus meta-monitoring.
- `deploy/vnso-ddos-observability/prometheus/rules/recording.yml`: precomputed PromQL for dashboards.
- `deploy/vnso-ddos-observability/alertmanager/alertmanager.yml`: tiered alert routing.
- `deploy/vnso-ddos-observability/exporter/wanguard_exporter.py`: REST JSON -> OpenMetrics middleware.
- `deploy/vnso-ddos-observability/docs/network-layer-coverage.md`: monitoring versus mitigation coverage by network layer.

Prometheus startup requirements in compose:

- `--storage.tsdb.wal-compression`
- `--web.enable-lifecycle` for `POST /-/reload`
- `--web.enable-admin-api` for TSDB snapshot API
- `--storage.tsdb.retention.time=30d`

---

## §8 - Scrape Tiering

| Tier | Interval | Jobs | Purpose |
| --- | --- | --- | --- |
| Tier 0 | 15s | `prometheus` | self-monitoring |
| Tier 1 | 5s | `wanguard_console_api`, `bgp_routers` | mitigation/control-plane detection latency |
| Tier 2 | 15s | `ddos_filters`, `ddos_sensors`, `node_exporters` | scrubbing and host health |
| Tier 3 | 15s | `blackbox_vip_check` | customer reachability and false positive detection |

Hard invariant: `scrape_timeout` must always be lower than `scrape_interval`.

---

## §9 - Wanguard API Middleware Rule

Prometheus cannot scrape the Wanguard REST API directly because Wanguard returns JSON and Prometheus expects OpenMetrics/Text exposition. The `wanguard_exporter` service polls REST endpoints and exposes safe, bounded metrics on `:9100`.

Expected logical hierarchy:

1. Anomaly: detected by Sensor.
2. Response: mitigation strategy.
3. Action: concrete step such as BGP Flowspec injection or script execution.
4. Precondition: guard rule such as traffic threshold, customer tier, or approval mode.

Exporter metrics must stay aggregate and bounded. Do not emit source/destination IP labels.

---

## §10 - State & Persistence

- Prometheus TSDB lives in Docker volume `prometheus_data`.
- WAL compression is enabled to reduce write amplification.
- Alertmanager state lives in `alertmanager_data`.
- Alertmanager HA gossip requires both TCP and UDP on port `9094` when multiple replicas are deployed.
- ClickHouse flow storage is optional and enabled via Docker Compose profile `flow-analytics`.

Snapshot command:

```bash
curl -X POST http://localhost:9090/api/v1/admin/tsdb/snapshot
```

The snapshot API requires `--web.enable-admin-api`.

---

## §11 - Operational Runbook

| Scenario | First action | Likely cause | Mitigation |
| --- | --- | --- | --- |
| Wanguard API 5xx | Check `WanguardApiFailure` and exporter logs | Console API overload, DB lock, token issue | Restart/fix Console API; verify token and ClickHouse/DB connectivity |
| BGP session down | Check `bgp_session_up` | Router session reset, FRR/BIRD/ExaBGP failure | Escalate to Network, restart daemon only with approval |
| BGP blast radius | Check `BGPBlastRadiusExceeded` | Route leak or bad precondition | Freeze automation, verify route diff, rollback bad action |
| VIP blackbox failure during mitigation | Check `FalsePositiveDetected` | Filter dropping clean traffic | Tune preconditions/signatures, bypass affected VIP if needed |
| High SoftIRQ | Check `HostHighSoftIRQ` | High PPS attack or NIC queue bottleneck | Tune RSS/RPS/XDP, scale filters, verify offload |
| Prometheus OOM | Check cardinality and dropped labels | New unbounded metric | Add metric relabel drops, move raw flow data to ClickHouse |
| Disk I/O bottleneck | Check `PrometheusWalFsyncSlow` | Slow disk or uncompressed WAL | Verify WAL compression and move TSDB to NVMe |
| Sensor disconnected | Check `WanguardSensorDisconnected` | Sensor cannot reach Console | Restore OOB path, service, or API registration |
| License expiring | Check `WanguardLicenseExpiring` | License renewal gap | Procurement/vendor renewal before cutoff |

---

## §12 - AI Agent Directives

AI agents must follow these rules when editing this project:

1. Do not output raw passwords or tokens.
2. Do not use placeholders like `# ... rest of config ...` in YAML changes. Output complete blocks.
3. Do not add unbounded labels to Prometheus metrics or alerts.
4. Prefer `file_sd_configs` for dynamic router/filter/sensor/VIP targets.
5. Use `rate()` for alerting, not `irate()`, unless an SRE explicitly asks for spike-sensitive debugging.
6. Use recording rules for dashboard queries that aggregate many series.
7. If generating Grafana dashboard JSON, keep `uid` stable only when this repo owns the dashboard. For copied/imported dashboards, use `uid: null`.
8. If touching Alertmanager routing, preserve VIP critical -> urgent escalation.
9. Prometheus observes and alerts; it must not run mitigation scripts directly.
10. Any direct BGP, XDP, nftables, or ACL action needs explicit SRE/Network approval outside Prometheus.

---

## §13 - PromQL & Query Performance Rules

- Use `rate(metric_total[5m])` for counters in alerts.
- Use `or vector(0)` only when absence genuinely means zero; otherwise alert on missing telemetry.
- Do not use `chunkenc` as a query optimization concept. Users cannot tune internal chunk encoding from PromQL.
- Prefer recording rules for high-cardinality or multi-day dashboard queries.
- Reduce time resolution (`step`) and label cardinality before increasing Prometheus resources.
- Monitor these meta metrics: `prometheus_tsdb_wal_fsync_duration_seconds`, `prometheus_target_interval_length_seconds`, `prometheus_sd_discovered_targets`, and `prometheus_rule_evaluation_duration_seconds`.

---

## §14 - Build, Test, Run Commands

Run from repo root unless stated otherwise.

```bash
# Start the observability overlay with root .env
docker compose -f deploy/vnso-ddos-observability/docker-compose.yml --env-file .env up -d --build

# Optional flow analytics layer
docker compose -f deploy/vnso-ddos-observability/docker-compose.yml --env-file .env --profile flow-analytics up -d clickhouse

# Validate local overlay files
deploy/vnso-ddos-observability/scripts/validate.sh

# Validate inside running containers
docker exec prometheus promtool check config /etc/prometheus/prometheus.yml
docker exec prometheus promtool check rules /etc/prometheus/rules/*.yml
docker exec alertmanager amtool check-config /etc/alertmanager/alertmanager.yml

# Reload Prometheus, requires --web.enable-lifecycle
curl -X POST http://localhost:9090/-/reload

# TSDB snapshot, requires --web.enable-admin-api
curl -X POST http://localhost:9090/api/v1/admin/tsdb/snapshot

# Docker compose v2 commands
docker compose -f deploy/vnso-ddos-observability/docker-compose.yml --env-file .env restart prometheus alertmanager grafana
docker compose -f deploy/vnso-ddos-observability/docker-compose.yml --env-file .env logs prometheus --tail=50 -f
```

Do not use deprecated `docker-compose` v1 syntax in docs or runbooks.

---

## §15 - Deployment Checklist

- [ ] Root `.env` exists locally and is not tracked by git.
- [ ] `GRAFANA_ADMIN_USER` and `GRAFANA_ADMIN_PASSWORD` are populated from secrets manager or local `.env`.
- [ ] Prometheus config validates with `promtool`.
- [ ] Alert rules validate with `promtool`.
- [ ] Alertmanager config validates with `amtool`.
- [ ] `wanguard_exporter` can reach Console API over OOB/mgmt network.
- [ ] Router, filter, sensor, and VIP target files are reviewed.
- [ ] No raw IP or port labels are exposed to Prometheus for raw flows.
- [ ] ClickHouse/flow collector is used for source/destination IP forensics.
- [ ] Grafana datasource and dashboard provisioning load on boot.
- [ ] Slack/PagerDuty receiver values are injected securely.
- [ ] TSDB snapshot or backup strategy is active.

---

## §16 - Roadmap & Evolution

| Phase | Goal | Tech |
| --- | --- | --- |
| v1 | Single overlay stack for Anti-DDoS monitoring | Prometheus, Alertmanager, Grafana, blackbox, Wanguard exporter |
| v1.1 | HA Prometheus pair and Alertmanager cluster | Duplicate scrape, deduped alerts, TCP/UDP 9094 gossip |
| v1.2 | Flow analytics production path | goflow2/pmacct -> ClickHouse -> Grafana |
| v2.1 | Long-term storage evaluation | VictoriaMetrics, Grafana Mimir, or Thanos |
| v2.2 | High-speed packet-drop telemetry | eBPF/XDP exporter, Cilium/Beyla evaluation |
| v2.3 | Kubernetes-native operations | Prometheus Operator, ServiceMonitor, PodMonitor |
| v2.4 | Edge collection mode | Prometheus Agent mode with remote_write |

Note: native histograms are already part of modern Prometheus 3.x behavior. Review feature flags against the running binary before adding obsolete flags.

---

## §17 - Change Log

| Date | Author | Change |
| --- | --- | --- |
| 2026-05-04 | GitHub Copilot | v4.1 rewrite. Removed hardcoded Grafana password from docs, aligned docs to `deploy/vnso-ddos-observability/`, added Anti-DDoS layer coverage, Wanguard exporter middleware rule, file service discovery, docker compose v2 commands, lifecycle/admin API notes, WAL compression, Alertmanager TCP/UDP gossip, ClickHouse boundary, AI directives, and network monitoring versus mitigation clarification. |
| 2026-05-01 | AI bootstrap | v2 PRO context pack for production Prometheus operations. |

---

**END OF PROMETHEUS AI CONTEXT PACK (VNSO PRO v4.1)**