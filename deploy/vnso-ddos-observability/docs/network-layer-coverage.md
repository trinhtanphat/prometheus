# Network Layer Monitoring and Mitigation Coverage

This overlay gives Prometheus visibility across the Anti-DDoS network layers. It does not turn Prometheus into an enforcement point. Prometheus observes, evaluates rules, and routes alerts. Actual blocking must happen in routers, Console/Wanguard actions, or filter nodes.

| Layer | What is monitored | What can block | Implemented here |
| --- | --- | --- | --- |
| Edge routers | BGP session state, exported prefixes, SNMP interface traffic | BGP Flowspec, RTBH, upstream blackhole | Scrape job, target file, BGP alerts |
| Core switches | SNMP counters, interface errors/drops, flow export health | ACL, storm-control, vendor policy | Monitoring guidance and flow boundary |
| Sensors | CPU, SoftIRQ, node health, Console connectivity | None, detection only | Sensor target file and Wanguard sensor alert |
| Console/API | API 5xx, active responses, actions, preconditions, license | Orchestrates BGP/filter actions | `wanguard_exporter.py` and Wanguard alerts |
| Filters | Node health, NIC drops, XDP/eBPF pass/drop counters, capacity | XDP/eBPF, DPDK, nftables, ACLs | Filter target file and capacity/XDP alerts |
| VIP reachability | HTTP/TCP/ICMP probes from blackbox exporter | None, alert only | Blackbox job and false positive alert |
| Flow forensics | Raw NetFlow/sFlow/IPFIX in ClickHouse | None, analytics only | ClickHouse schema; collector still required |

## Current answer

The project now has monitoring coverage for edge, core, sensor, console/API, filter, VIP, and flow analytics layers at the configuration and alerting level. Blocking is intentionally not executed by Prometheus. The blocking path is:

1. Sensor detects anomaly.
2. Console/Wanguard validates response preconditions.
3. Console sends BGP Flowspec/RTBH to routers or filter rules to scrubbing nodes.
4. Prometheus monitors the result and alerts on failure, blast radius, false positives, or capacity pressure.

Before production, verify the actual router policies, Wanguard action scripts, XDP/eBPF programs, and OOB management paths outside this repo.
