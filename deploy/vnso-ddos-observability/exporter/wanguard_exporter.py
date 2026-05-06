import os
import re
import time
from collections import Counter as LabelCounter
from typing import Any

import requests
from prometheus_client import Counter, Gauge, start_http_server


API_REQUESTS = Counter(
    "wanguard_api_http_requests",
    "Wanguard API requests made by the exporter.",
    ["api_endpoint", "status"],
)
EXPORTER_UP = Gauge("wanguard_exporter_up", "Whether the exporter can poll Wanguard successfully.")
LAST_SUCCESS = Gauge("wanguard_exporter_last_success_timestamp_seconds", "Last successful Wanguard poll timestamp.")
ACTIVE_RESPONSES = Gauge(
    "wanguard_active_responses",
    "Active mitigation responses by bounded type, tier, and action labels.",
    ["response_type", "tier", "mitigation_action"],
)
ACTIVE_ANOMALIES = Gauge(
    "wanguard_active_anomalies",
    "Active anomalies by bounded protocol, TCP flag, country, and tier labels.",
    ["protocol", "tcp_flag", "country", "tier"],
)
LICENSE_DAYS = Gauge("wanguard_license_days_remaining", "Days remaining before the Wanguard license expires.")
SENSOR_STATUS = Gauge(
    "wanguard_sensor_status",
    "Sensor connectivity status. The active state is 1 and inactive states are 0.",
    ["sensor_id", "sensor_name", "state"],
)

SAFE_LABEL = re.compile(r"[^a-zA-Z0-9_.:-]+")
ACTIVE_STATES = {"active", "enabled", "running", "mitigating", "firing"}
KNOWN_STATES = ("connected", "disconnected", "unknown")


def bounded_label(value: Any, default: str = "unknown", max_length: int = 64) -> str:
    if value is None:
        return default
    label = SAFE_LABEL.sub("_", str(value).strip().lower())[:max_length]
    return label or default


def endpoint_name(path: str) -> str:
    return bounded_label(path.strip("/").replace("/", "_"), "root")


class WanguardClient:
    def __init__(self) -> None:
        base_url = os.environ.get("WANGUARD_API_URL", "").rstrip("/")
        token = os.environ.get("WANGUARD_API_TOKEN", "")
        if not base_url:
            raise RuntimeError("WANGUARD_API_URL is required")
        if not token:
            raise RuntimeError("WANGUARD_API_TOKEN is required")
        self.base_url = base_url
        self.session = requests.Session()
        self.session.headers.update({"Authorization": f"Bearer {token}"})
        self.timeout = float(os.environ.get("WANGUARD_API_TIMEOUT_SECONDS", "3"))
        verify_tls = os.environ.get("WANGUARD_VERIFY_TLS", "true").lower()
        self.verify_tls = verify_tls not in {"0", "false", "no"}

    def get_json(self, path: str) -> Any:
        response = self.session.get(f"{self.base_url}/{path.lstrip('/')}", timeout=self.timeout, verify=self.verify_tls)
        API_REQUESTS.labels(api_endpoint=endpoint_name(path), status=str(response.status_code)).inc()
        response.raise_for_status()
        return response.json()


def items_from_payload(payload: Any, keys: tuple[str, ...]) -> list[dict[str, Any]]:
    if isinstance(payload, list):
        return [item for item in payload if isinstance(item, dict)]
    if isinstance(payload, dict):
        for key in keys:
            value = payload.get(key)
            if isinstance(value, list):
                return [item for item in value if isinstance(item, dict)]
        value = payload.get("data")
        if isinstance(value, list):
            return [item for item in value if isinstance(item, dict)]
    return []


def refresh_responses(client: WanguardClient) -> None:
    payload = client.get_json("responses")
    responses = items_from_payload(payload, ("responses", "items"))
    response_counts: LabelCounter[tuple[str, str, str]] = LabelCounter()

    for response in responses:
        status = bounded_label(response.get("status") or response.get("state"))
        if status not in ACTIVE_STATES:
            continue
        response_type = bounded_label(response.get("type") or response.get("response_type"))
        tier = bounded_label(response.get("tier") or response.get("customer_tier"), "standard")
        action = bounded_label(response.get("action") or response.get("mitigation_action"))
        response_counts[(response_type, tier, action)] += 1

    ACTIVE_RESPONSES.clear()
    if not response_counts:
        ACTIVE_RESPONSES.labels(response_type="none", tier="standard", mitigation_action="none").set(0)
        return
    for labels, count in response_counts.items():
        ACTIVE_RESPONSES.labels(response_type=labels[0], tier=labels[1], mitigation_action=labels[2]).set(count)


def refresh_anomalies(client: WanguardClient) -> None:
    payload = client.get_json("anomalies")
    anomalies = items_from_payload(payload, ("anomalies", "items"))
    anomaly_counts: LabelCounter[tuple[str, str, str, str]] = LabelCounter()

    for anomaly in anomalies:
        status = bounded_label(anomaly.get("status") or anomaly.get("state"))
        if status not in ACTIVE_STATES:
            continue
        protocol = bounded_label(anomaly.get("protocol"))
        tcp_flag = bounded_label(anomaly.get("tcp_flag") or anomaly.get("tcp_flags"), "none")
        country = bounded_label(anomaly.get("country"), "unknown")
        tier = bounded_label(anomaly.get("tier") or anomaly.get("customer_tier"), "standard")
        anomaly_counts[(protocol, tcp_flag, country, tier)] += 1

    ACTIVE_ANOMALIES.clear()
    if not anomaly_counts:
        ACTIVE_ANOMALIES.labels(protocol="none", tcp_flag="none", country="unknown", tier="standard").set(0)
        return
    for labels, count in anomaly_counts.items():
        ACTIVE_ANOMALIES.labels(protocol=labels[0], tcp_flag=labels[1], country=labels[2], tier=labels[3]).set(count)


def refresh_license(client: WanguardClient) -> None:
    payload = client.get_json("license")
    if not isinstance(payload, dict):
        return
    days_remaining = payload.get("days_remaining") or payload.get("license_days_remaining")
    if days_remaining is not None:
        LICENSE_DAYS.set(float(days_remaining))


def refresh_sensors(client: WanguardClient) -> None:
    payload = client.get_json("sensors")
    sensors = items_from_payload(payload, ("sensors", "items"))
    SENSOR_STATUS.clear()

    if not sensors:
        SENSOR_STATUS.labels(sensor_id="unknown", sensor_name="none", state="unknown").set(1)
        return

    for sensor in sensors:
        sensor_id = bounded_label(sensor.get("id") or sensor.get("sensor_id"))
        sensor_name = bounded_label(sensor.get("name") or sensor.get("sensor_name"))
        raw_state = bounded_label(sensor.get("state") or sensor.get("status"), "unknown")
        state = raw_state if raw_state in KNOWN_STATES else "unknown"
        for candidate in KNOWN_STATES:
            SENSOR_STATUS.labels(sensor_id=sensor_id, sensor_name=sensor_name, state=candidate).set(1 if candidate == state else 0)


def poll_once(client: WanguardClient) -> None:
    refresh_responses(client)
    refresh_anomalies(client)
    refresh_license(client)
    refresh_sensors(client)
    EXPORTER_UP.set(1)
    LAST_SUCCESS.set(time.time())


def main() -> None:
    port = int(os.environ.get("WANGUARD_EXPORTER_PORT", "9100"))
    poll_seconds = float(os.environ.get("WANGUARD_EXPORTER_POLL_SECONDS", "5"))
    start_http_server(port)
    client = WanguardClient()
    while True:
        try:
            poll_once(client)
        except requests.RequestException as error:
            status = getattr(error.response, "status_code", "error")
            API_REQUESTS.labels(api_endpoint="poll", status=str(status)).inc()
            EXPORTER_UP.set(0)
            print(f"Wanguard poll failed: {error}", flush=True)
        except Exception as error:
            EXPORTER_UP.set(0)
            print(f"Unexpected exporter failure: {error}", flush=True)
        time.sleep(poll_seconds)


if __name__ == "__main__":
    main()
