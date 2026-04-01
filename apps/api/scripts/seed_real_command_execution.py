from __future__ import annotations

import json
import os
import sys
import time
import urllib.error
import urllib.parse
import urllib.request


API_BASE_URL = os.getenv(
    "SUNRISE_SEED_API_BASE_URL",
    "http://localhost:8000/api/v1",
).rstrip("/")
USERNAME = os.getenv("SUNRISE_SEED_USERNAME", "admin")
PASSWORD = os.getenv("SUNRISE_SEED_PASSWORD", "ChangeThisPassword123!")
LOGIN_RETRY_SECONDS = 10

SEED_SPEC = {
    "manufacturer_code": "SEED-MFG-01",
    "model_code": "SEED-MODEL-01",
    "communication_profile_code": "SEED-TCP-01",
    "meter_profile_code": "SEED-DLMS-01",
    "meter_serial": "SEED-CMD-1001",
    "endpoint_code": "SEED-ENDPOINT-01",
    "protocol_profile_code": "SEED-PROFILE-01",
    "relay_disconnect_template_code": "seed-relay-disconnect-template",
    "relay_reconnect_template_code": "seed-relay-reconnect-template",
    "on_demand_template_code": "seed-on-demand-read-template",
}


def request(
    method: str,
    path: str,
    *,
    token: str | None = None,
    payload: dict[str, object] | None = None,
) -> tuple[int, dict[str, object] | list[object] | None]:
    data = None if payload is None else json.dumps(payload).encode("utf-8")
    headers = {"Content-Type": "application/json"}
    if token is not None:
        headers["Authorization"] = f"Bearer {token}"
    request_obj = urllib.request.Request(
        f"{API_BASE_URL}{path}",
        data=data,
        headers=headers,
        method=method,
    )
    try:
        with urllib.request.urlopen(request_obj) as response:
            body = response.read().decode("utf-8")
            parsed = json.loads(body) if body else None
            return response.status, parsed
    except urllib.error.HTTPError as error:
        body = error.read().decode("utf-8")
        try:
            parsed = json.loads(body)
        except json.JSONDecodeError:
            parsed = {"detail": body}
        return error.code, parsed
    except (urllib.error.URLError, OSError) as error:
        return 0, {"detail": str(error)}


def require_dict(value: object, *, context: str) -> dict[str, object]:
    if not isinstance(value, dict):
        raise RuntimeError(f"{context} did not return an object payload.")
    return value


def require_items(payload: object, *, context: str) -> list[dict[str, object]]:
    data = require_dict(payload, context=context)
    items = data.get("items")
    if not isinstance(items, list):
        raise RuntimeError(f"{context} did not return an items list.")
    return [item for item in items if isinstance(item, dict)]


def login() -> str:
    last_error: tuple[int, dict[str, object] | list[object] | None] | None = None
    for _ in range(LOGIN_RETRY_SECONDS):
        status_code, payload = request(
            "POST",
            "/auth/login",
            payload={"username_or_email": USERNAME, "password": PASSWORD},
        )
        if status_code == 200:
            data = require_dict(payload, context="auth login")
            access_token = data.get("access_token")
            if not isinstance(access_token, str) or not access_token:
                raise RuntimeError("Auth login did not return an access token.")
            return access_token
        last_error = (status_code, payload)
        time.sleep(1)

    raise RuntimeError(
        f"Login failed against {API_BASE_URL}: {last_error[0]} {last_error[1]!r}"
    )


def list_items(token: str, path: str, *, context: str) -> list[dict[str, object]]:
    status_code, payload = request("GET", path, token=token)
    if status_code != 200:
        raise RuntimeError(f"{context} failed: {status_code} {payload!r}")
    return require_items(payload, context=context)


def ensure_by_code(
    token: str,
    *,
    list_path: str,
    create_path: str,
    create_payload: dict[str, object],
    code_field: str,
    code_value: str,
    context: str,
) -> dict[str, object]:
    normalized_code = code_value.strip().lower()
    for item in list_items(token, list_path, context=context):
        existing_code = item.get(code_field)
        if isinstance(existing_code, str) and existing_code.strip().lower() == normalized_code:
            return item

    status_code, payload = request(
        "POST",
        create_path,
        token=token,
        payload=create_payload,
    )
    if status_code not in (200, 201):
        raise RuntimeError(f"{context} create failed: {status_code} {payload!r}")
    return require_dict(payload, context=f"{context} create")


def ensure_meter(token: str, *, manufacturer_id: str, model_id: str, communication_profile_id: str, meter_profile_id: str) -> dict[str, object]:
    search = urllib.parse.quote(SEED_SPEC["meter_serial"])
    items = list_items(
        token,
        f"/meters?limit=100&search={search}",
        context="list seeded meters",
    )
    for item in items:
        if item.get("serial_number") == SEED_SPEC["meter_serial"]:
            return item

    status_code, payload = request(
        "POST",
        "/meters",
        token=token,
        payload={
            "serial_number": SEED_SPEC["meter_serial"],
            "utility_meter_number": "UTIL-SEED-1001",
            "badge_number": "BADGE-SEED-1001",
            "manufacturer_id": manufacturer_id,
            "meter_model_id": model_id,
            "communication_profile_id": communication_profile_id,
            "meter_profile_id": meter_profile_id,
            "current_status": "active",
            "notes": "Seeded for real command execution verification.",
            "is_active": True,
            "metadata_json": {"seeded_for": "real-command-execution"},
        },
    )
    if status_code not in (200, 201):
        raise RuntimeError(f"meter create failed: {status_code} {payload!r}")
    return require_dict(payload, context="meter create")


def ensure_assignment(
    token: str,
    *,
    meter_id: str,
    endpoint_id: str,
) -> dict[str, object]:
    items = list_items(
        token,
        f"/meters/{meter_id}/endpoint-assignments",
        context="list meter endpoint assignments",
    )
    for item in items:
        if (
            item.get("endpoint_id") == endpoint_id
            and item.get("assignment_status") == "active"
        ):
            return item

    status_code, payload = request(
        "POST",
        f"/meters/{meter_id}/endpoint-assignments",
        token=token,
        payload={
            "endpoint_id": endpoint_id,
            "is_primary": True,
            "assignment_status": "active",
            "notes": "Seeded primary assignment for command execution.",
        },
    )
    if status_code not in (200, 201):
        raise RuntimeError(f"assignment create failed: {status_code} {payload!r}")
    return require_dict(payload, context="assignment create")


def list_recent_meter_commands(token: str, meter_id: str) -> list[dict[str, object]]:
    return list_items(
        token,
        f"/meters/{meter_id}/commands/recent?limit=50",
        context="list recent seeded meter commands",
    )


def find_recent_command_by_template(
    recent_commands: list[dict[str, object]],
    *,
    template_code: str,
) -> dict[str, object] | None:
    for command in recent_commands:
        if command.get("command_template_code") == template_code:
            return command
    return None


def ensure_relay_disconnect_execution(
    token: str,
    *,
    meter_id: str,
    command_template_id: str,
    command_template_code: str,
    endpoint_assignment_id: str,
    protocol_profile_id: str,
) -> dict[str, object]:
    recent = list_recent_meter_commands(token, meter_id)
    existing = find_recent_command_by_template(
        recent,
        template_code=command_template_code,
    )
    if existing is not None and existing.get("command_status") == "succeeded":
        return {"status": "existing", "recent_command": existing}

    status_code, payload = request(
        "POST",
        f"/meters/{meter_id}/commands/relay-control/execute-now",
        token=token,
        payload={
            "command_template_id": command_template_id,
            "relay_operation": "disconnect",
            "endpoint_assignment_id": endpoint_assignment_id,
            "protocol_association_profile_id": protocol_profile_id,
            "notes": "Seeded relay control execute-now request.",
            "execute_now_reason": "seed-real-command-execution",
        },
    )
    if status_code != 200:
        raise RuntimeError(
            f"relay-control execute-now failed: {status_code} {payload!r}"
        )
    return {
        "status": "executed",
        "response": require_dict(payload, context="relay-control execute-now"),
    }


def ensure_on_demand_read_execution(
    token: str,
    *,
    meter_id: str,
    command_template_id: str,
    command_template_code: str,
    endpoint_assignment_id: str,
    protocol_profile_id: str,
) -> dict[str, object]:
    recent = list_recent_meter_commands(token, meter_id)
    existing = find_recent_command_by_template(
        recent,
        template_code=command_template_code,
    )
    if existing is not None and existing.get("command_status") == "succeeded":
        return {"status": "existing", "recent_command": existing}

    status_code, payload = request(
        "POST",
        f"/meters/{meter_id}/commands/on-demand-read/execute-now",
        token=token,
        payload={
            "command_template_id": command_template_id,
            "on_demand_read_operation": "read_billing_snapshot",
            "endpoint_assignment_id": endpoint_assignment_id,
            "protocol_association_profile_id": protocol_profile_id,
            "notes": "Seeded on-demand-read execute-now request.",
            "execute_now_reason": "seed-real-command-execution",
        },
    )
    if status_code != 200:
        raise RuntimeError(
            f"on-demand-read execute-now failed: {status_code} {payload!r}"
        )
    return {
        "status": "executed",
        "response": require_dict(payload, context="on-demand-read execute-now"),
    }


def main() -> int:
    token = login()

    manufacturer = ensure_by_code(
        token,
        list_path="/manufacturers",
        create_path="/manufacturers",
        create_payload={
            "name": "Seed Meter Manufacturer",
            "code": SEED_SPEC["manufacturer_code"],
            "country": "OM",
            "website": "https://example.invalid/seed",
            "is_active": True,
        },
        code_field="code",
        code_value=SEED_SPEC["manufacturer_code"],
        context="manufacturer seed",
    )

    model = ensure_by_code(
        token,
        list_path="/models",
        create_path="/models",
        create_payload={
            "manufacturer_id": manufacturer["id"],
            "model_code": SEED_SPEC["model_code"],
            "display_name": "Seed Command Model",
            "phase_type": "single_phase",
            "meter_category": "electricity",
            "dlms_capable": True,
            "is_active": True,
        },
        code_field="model_code",
        code_value=SEED_SPEC["model_code"],
        context="meter model seed",
    )

    communication_profile = ensure_by_code(
        token,
        list_path="/communication-profiles",
        create_path="/communication-profiles",
        create_payload={
            "code": SEED_SPEC["communication_profile_code"],
            "name": "Seed TCP Communication Profile",
            "transport_type": "tcp_ip",
            "ip_mode": "static",
            "port": 4059,
            "authentication_mode": "none",
            "protocol_settings": {"seeded_for": "real-command-execution"},
            "is_active": True,
        },
        code_field="code",
        code_value=SEED_SPEC["communication_profile_code"],
        context="communication profile seed",
    )

    meter_profile = ensure_by_code(
        token,
        list_path="/meter-profiles",
        create_path="/meter-profiles",
        create_payload={
            "code": SEED_SPEC["meter_profile_code"],
            "name": "Seed DLMS Meter Profile",
            "meter_model_id": model["id"],
            "communication_profile_id": communication_profile["id"],
            "protocol_family": "dlms_cosem",
            "protocol_defaults": {"seeded_for": "real-command-execution"},
            "description": "Seeded minimal profile for real command execution.",
            "is_active": True,
        },
        code_field="code",
        code_value=SEED_SPEC["meter_profile_code"],
        context="meter profile seed",
    )

    meter = ensure_meter(
        token,
        manufacturer_id=str(manufacturer["id"]),
        model_id=str(model["id"]),
        communication_profile_id=str(communication_profile["id"]),
        meter_profile_id=str(meter_profile["id"]),
    )

    endpoint = ensure_by_code(
        token,
        list_path="/communication-endpoints",
        create_path="/communication-endpoints",
        create_payload={
            "code": SEED_SPEC["endpoint_code"],
            "display_name": "Seed Command Endpoint",
            "endpoint_type": "tcp",
            "transport_type": "tcp_ip",
            "host": "127.0.0.1",
            "port": 4059,
            "ip_address": "127.0.0.1",
            "network_provider": "seed-local",
            "is_active": True,
            "notes": "Seeded local endpoint for runtime stub execution.",
        },
        code_field="code",
        code_value=SEED_SPEC["endpoint_code"],
        context="communication endpoint seed",
    )

    protocol_profile = ensure_by_code(
        token,
        list_path="/protocol-association-profiles",
        create_path="/protocol-association-profiles",
        create_payload={
            "code": SEED_SPEC["protocol_profile_code"],
            "name": "Seed DLMS Protocol Profile",
            "protocol_family": "dlms_cosem",
            "iec62056_21_enabled": False,
            "client_address": 16,
            "server_address": 1,
            "authentication_mode": "none",
            "profile_settings": {"seeded_for": "real-command-execution"},
            "is_active": True,
        },
        code_field="code",
        code_value=SEED_SPEC["protocol_profile_code"],
        context="protocol profile seed",
    )

    assignment = ensure_assignment(
        token,
        meter_id=str(meter["id"]),
        endpoint_id=str(endpoint["id"]),
    )

    relay_disconnect_template = ensure_by_code(
        token,
        list_path="/command-templates",
        create_path="/command-templates",
        create_payload={
            "code": SEED_SPEC["relay_disconnect_template_code"],
            "name": "Seed Relay Disconnect",
            "category": "remote_disconnect",
            "description": "Seeded relay disconnect template for real command execution.",
            "target_scope": "meter",
            "payload_schema": {"seeded_for": "real-command-execution"},
            "timeout_seconds": 120,
            "max_retries": 0,
            "is_active": True,
        },
        code_field="code",
        code_value=SEED_SPEC["relay_disconnect_template_code"],
        context="relay disconnect template seed",
    )

    relay_reconnect_template = ensure_by_code(
        token,
        list_path="/command-templates",
        create_path="/command-templates",
        create_payload={
            "code": SEED_SPEC["relay_reconnect_template_code"],
            "name": "Seed Relay Reconnect",
            "category": "remote_reconnect",
            "description": "Seeded relay reconnect template for real command execution.",
            "target_scope": "meter",
            "payload_schema": {"seeded_for": "real-command-execution"},
            "timeout_seconds": 120,
            "max_retries": 0,
            "is_active": True,
        },
        code_field="code",
        code_value=SEED_SPEC["relay_reconnect_template_code"],
        context="relay reconnect template seed",
    )

    on_demand_template = ensure_by_code(
        token,
        list_path="/command-templates",
        create_path="/command-templates",
        create_payload={
            "code": SEED_SPEC["on_demand_template_code"],
            "name": "Seed On-demand Read",
            "category": "on_demand_read",
            "description": "Seeded on-demand-read template for real command execution.",
            "target_scope": "meter",
            "payload_schema": {"seeded_for": "real-command-execution"},
            "timeout_seconds": 120,
            "max_retries": 0,
            "is_active": True,
        },
        code_field="code",
        code_value=SEED_SPEC["on_demand_template_code"],
        context="on-demand-read template seed",
    )

    relay_execution = ensure_relay_disconnect_execution(
        token,
        meter_id=str(meter["id"]),
        command_template_id=str(relay_disconnect_template["id"]),
        command_template_code=str(relay_disconnect_template["code"]),
        endpoint_assignment_id=str(assignment["id"]),
        protocol_profile_id=str(protocol_profile["id"]),
    )

    on_demand_execution = ensure_on_demand_read_execution(
        token,
        meter_id=str(meter["id"]),
        command_template_id=str(on_demand_template["id"]),
        command_template_code=str(on_demand_template["code"]),
        endpoint_assignment_id=str(assignment["id"]),
        protocol_profile_id=str(protocol_profile["id"]),
    )

    recent_commands = list_recent_meter_commands(token, str(meter["id"]))

    summary = {
        "api_base_url": API_BASE_URL,
        "seeded_meter": {
            "id": meter["id"],
            "serial_number": meter["serial_number"],
        },
        "endpoint_assignment_id": assignment["id"],
        "protocol_association_profile_id": protocol_profile["id"],
        "relay_disconnect_template_id": relay_disconnect_template["id"],
        "relay_reconnect_template_id": relay_reconnect_template["id"],
        "on_demand_read_template_id": on_demand_template["id"],
        "relay_disconnect_execution": relay_execution,
        "on_demand_read_execution": on_demand_execution,
        "recent_command_count": len(recent_commands),
    }
    print(json.dumps(summary, indent=2))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as error:  # pragma: no cover - script failure path
        print(f"seed_real_command_execution failed: {error}", file=sys.stderr)
        raise SystemExit(1) from error
