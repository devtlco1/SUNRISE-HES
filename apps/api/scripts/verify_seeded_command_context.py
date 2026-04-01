from __future__ import annotations

import json
import sys
import urllib.parse

from seed_real_command_execution import API_BASE_URL, SEED_SPEC, login, list_items


def find_seeded_meter(token: str) -> dict[str, object]:
    search = urllib.parse.quote(SEED_SPEC["meter_serial"])
    items = list_items(
        token,
        f"/meters?limit=20&search={search}",
        context="verify seeded meter visibility",
    )
    for item in items:
        if item.get("serial_number") == SEED_SPEC["meter_serial"]:
            return item
    raise RuntimeError(
        "Seeded meter context is missing. Run 'make seed-command-execution' first."
    )


def require_succeeded_recent_command(
    recent_commands: list[dict[str, object]],
    *,
    template_code: str,
    description: str,
) -> dict[str, object]:
    for command in recent_commands:
        if (
            command.get("command_template_code") == template_code
            and command.get("command_status") == "succeeded"
        ):
            return command
    raise RuntimeError(
        f"Seeded {description} history is missing. Run 'make seed-command-execution' first."
    )


def main() -> int:
    token = login()
    meter = find_seeded_meter(token)
    meter_id = str(meter["id"])
    meter_recent_commands = list_items(
        token,
        f"/meters/{meter_id}/commands/recent?limit=20",
        context="verify seeded meter recent command history",
    )
    global_recent_commands = list_items(
        token,
        "/commands/recent?limit=20",
        context="verify global recent command history",
    )

    relay_command = require_succeeded_recent_command(
        meter_recent_commands,
        template_code=SEED_SPEC["relay_disconnect_template_code"],
        description="relay-control",
    )
    on_demand_command = require_succeeded_recent_command(
        meter_recent_commands,
        template_code=SEED_SPEC["on_demand_template_code"],
        description="on-demand-read",
    )

    global_meter_command_count = sum(
        1
        for command in global_recent_commands
        if command.get("meter_id") == meter_id
    )
    if global_meter_command_count == 0:
        raise RuntimeError(
            "Global recent command history does not include the seeded meter context."
        )

    summary = {
        "api_base_url": API_BASE_URL,
        "seeded_meter": {
            "id": meter_id,
            "serial_number": meter["serial_number"],
        },
        "meter_recent_command_count": len(meter_recent_commands),
        "global_recent_command_count": len(global_recent_commands),
        "global_seeded_meter_command_count": global_meter_command_count,
        "verified_relay_command_id": relay_command["command_id"],
        "verified_on_demand_command_id": on_demand_command["command_id"],
    }
    print(json.dumps(summary, indent=2))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as error:  # pragma: no cover - script failure path
        print(f"verify_seeded_command_context failed: {error}", file=sys.stderr)
        raise SystemExit(1) from error
