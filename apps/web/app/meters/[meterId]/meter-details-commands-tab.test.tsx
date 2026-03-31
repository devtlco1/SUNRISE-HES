import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { MeterDetailsCommandsTab } from "./meter-details-commands-tab";

type RequestLog = {
  method: string;
  url: string;
  body: Record<string, unknown> | null;
};

function jsonResponse(payload: unknown, status = 200) {
  return new Response(JSON.stringify(payload), {
    status,
    headers: { "Content-Type": "application/json" },
  });
}

function createMockApi() {
  const requests: RequestLog[] = [];
  const recentCommands = [
    {
      command_id: "cmd-profile-1",
      command_family: "profile_capture",
      command_category: "profile_capture",
      command_status: "succeeded",
      meter_id: "meter-1",
      command_template_code: "profile-capture-template",
      latest_command_execution_attempt_id: "attempt-profile-1",
      latest_command_execution_attempt_status: "succeeded",
      runtime_execution_record_id: "runtime-profile-1",
      family_specific_outcome_summary: { terminal_status_category: "acknowledged" },
      orchestration_artifact_present: true,
      terminalization_artifact_present: true,
      execute_now_artifact_present: true,
      created_at: "2026-03-30T10:00:00.000Z",
      latest_updated_at: "2026-03-30T10:05:00.000Z",
    },
    {
      command_id: "cmd-relay-1",
      command_family: "relay_control",
      command_category: "remote_disconnect",
      command_status: "succeeded",
      meter_id: "meter-1",
      command_template_code: "relay-disconnect-template",
      latest_command_execution_attempt_id: "attempt-relay-1",
      latest_command_execution_attempt_status: "succeeded",
      runtime_execution_record_id: "runtime-relay-1",
      family_specific_outcome_summary: {
        relay_control_operation: "disconnect",
        relay_control_execution_outcome: "succeeded",
      },
      orchestration_artifact_present: true,
      terminalization_artifact_present: true,
      execute_now_artifact_present: true,
      created_at: "2026-03-30T09:00:00.000Z",
      latest_updated_at: "2026-03-30T09:03:00.000Z",
    },
  ];

  const detailById: Record<string, Record<string, unknown>> = {
    "cmd-profile-1": {
      command_id: "cmd-profile-1",
      command_family: "profile_capture",
      command_category: "profile_capture",
      command_status: "succeeded",
      meter_id: "meter-1",
      command_template_code: "profile-capture-template",
      latest_command_execution_attempt_id: "attempt-profile-1",
      latest_command_execution_attempt_status: "succeeded",
      runtime_execution_record_id: "runtime-profile-1",
      family_specific_outcome_summary: { terminal_status_category: "acknowledged" },
      orchestration_artifact_present: true,
      terminalization_artifact_present: true,
      execute_now_artifact_present: true,
      created_at: "2026-03-30T10:00:00.000Z",
      latest_updated_at: "2026-03-30T10:05:00.000Z",
      projection_record: { runtime_execution_record_id: "runtime-profile-1" },
    },
    "cmd-relay-1": {
      command_id: "cmd-relay-1",
      command_family: "relay_control",
      command_category: "remote_disconnect",
      command_status: "succeeded",
      meter_id: "meter-1",
      command_template_code: "relay-disconnect-template",
      latest_command_execution_attempt_id: "attempt-relay-1",
      latest_command_execution_attempt_status: "succeeded",
      runtime_execution_record_id: "runtime-relay-1",
      family_specific_outcome_summary: {
        relay_control_operation: "disconnect",
        relay_control_execution_outcome: "succeeded",
      },
      orchestration_artifact_present: true,
      terminalization_artifact_present: true,
      execute_now_artifact_present: true,
      created_at: "2026-03-30T09:00:00.000Z",
      latest_updated_at: "2026-03-30T09:03:00.000Z",
      projection_record: { runtime_execution_record_id: "runtime-relay-1" },
    },
  };

  const fetchMock = vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
    const url = input.toString();
    const method = init?.method ?? "GET";
    const body = init?.body ? (JSON.parse(String(init.body)) as Record<string, unknown>) : null;

    if (method !== "GET") {
      requests.push({ method, url, body });
    }

    if (url.endsWith("/api/v1/meters/meter-1")) {
      return jsonResponse({
        id: "meter-1",
        serial_number: "SN-1001",
        utility_meter_number: "UMN-1001",
        manufacturer_code: "GENERIC",
        meter_model_code: "GM-1",
        meter_profile_code: "default",
        communication_profile_code: "dlms-default",
        current_status: "commissioned",
        last_seen_at: "2026-03-30T11:00:00.000Z",
      });
    }

    if (url.endsWith("/api/v1/command-templates")) {
      return jsonResponse({
        total: 4,
        items: [
          {
            id: "template-profile-1",
            code: "profile-capture-template",
            name: "Profile Capture",
            category: "profile_capture",
            is_active: true,
          },
          {
            id: "template-relay-disconnect-1",
            code: "relay-disconnect-template",
            name: "Relay Disconnect",
            category: "remote_disconnect",
            is_active: true,
          },
          {
            id: "template-relay-reconnect-1",
            code: "relay-reconnect-template",
            name: "Relay Reconnect",
            category: "remote_reconnect",
            is_active: true,
          },
          {
            id: "template-on-demand-read-1",
            code: "on-demand-read-hidden-template",
            name: "On Demand Read",
            category: "on_demand_read",
            is_active: true,
          },
        ],
      });
    }

    if (url.endsWith("/api/v1/meters/meter-1/endpoint-assignments")) {
      return jsonResponse({
        total: 1,
        items: [
          {
            id: "assignment-1",
            endpoint_id: "endpoint-1",
            endpoint_code: "tcp-primary",
            endpoint_display_name: "TCP Primary",
            assignment_status: "active",
            is_primary: true,
          },
        ],
      });
    }

    if (url.endsWith("/api/v1/protocol-association-profiles")) {
      return jsonResponse({
        total: 1,
        items: [
          {
            id: "protocol-profile-1",
            code: "dlms-profile",
            name: "DLMS Profile",
            protocol_family: "dlms_cosem",
            is_active: true,
          },
        ],
      });
    }

    if (url.endsWith("/api/v1/meters/meter-1/load-profile-channels")) {
      return jsonResponse({
        total: 2,
        items: [
          {
            id: "channel-1",
            channel_code: "import-wh",
            obis_code: "1.0.1.8.0.255",
            interval_seconds: 900,
            is_active: true,
          },
          {
            id: "channel-2",
            channel_code: "export-wh",
            obis_code: "1.0.2.8.0.255",
            interval_seconds: 900,
            is_active: true,
          },
        ],
      });
    }

    if (url.includes("/api/v1/meters/meter-1/commands/recent")) {
      const parsedUrl = new URL(url);
      const family = parsedUrl.searchParams.get("family");
      const items =
        family === null
          ? recentCommands
          : recentCommands.filter((item) => item.command_family === family);

      return jsonResponse({
        meter_id: "meter-1",
        total: items.length,
        limit: Number(parsedUrl.searchParams.get("limit") ?? "20"),
        family_filter: family,
        items,
      });
    }

    if (url.includes("/api/v1/commands/") && url.endsWith("/detail")) {
      const commandId = url.split("/api/v1/commands/")[1].replace("/detail", "");
      return jsonResponse({ result: detailById[commandId] });
    }

    if (method === "POST" && url.endsWith("/api/v1/meters/meter-1/commands/profile-capture/execute-now")) {
      recentCommands.unshift({
        command_id: "cmd-profile-action",
        command_family: "profile_capture",
        command_category: "profile_capture",
        command_status: "succeeded",
        meter_id: "meter-1",
        command_template_code: "profile-capture-template",
        latest_command_execution_attempt_id: "attempt-profile-action",
        latest_command_execution_attempt_status: "succeeded",
        runtime_execution_record_id: "runtime-profile-action",
        family_specific_outcome_summary: { terminal_status_category: "acknowledged" },
        orchestration_artifact_present: true,
        terminalization_artifact_present: true,
        execute_now_artifact_present: true,
        created_at: "2026-03-30T12:00:00.000Z",
        latest_updated_at: "2026-03-30T12:02:00.000Z",
      });
      detailById["cmd-profile-action"] = {
        command_id: "cmd-profile-action",
        command_family: "profile_capture",
        command_category: "profile_capture",
        command_status: "succeeded",
        meter_id: "meter-1",
        command_template_code: "profile-capture-template",
        latest_command_execution_attempt_id: "attempt-profile-action",
        latest_command_execution_attempt_status: "succeeded",
        runtime_execution_record_id: "runtime-profile-action",
        family_specific_outcome_summary: { terminal_status_category: "acknowledged" },
        orchestration_artifact_present: true,
        terminalization_artifact_present: true,
        execute_now_artifact_present: true,
        created_at: "2026-03-30T12:00:00.000Z",
        latest_updated_at: "2026-03-30T12:02:00.000Z",
        projection_record: { runtime_execution_record_id: "runtime-profile-action" },
      };
      return jsonResponse({ result: { command_id: "cmd-profile-action" } });
    }

    if (method === "POST" && url.endsWith("/api/v1/meters/meter-1/commands/relay-control/execute-now")) {
      const operation = String(body?.relay_operation ?? "disconnect");
      const templateCode =
        operation === "reconnect"
          ? "relay-reconnect-template"
          : "relay-disconnect-template";
      return jsonResponse({
        result: { command_id: `cmd-relay-${operation}-action` },
      });
    }

    throw new Error(`Unhandled request: ${method} ${url}`);
  });

  return { fetchMock, requests };
}

describe("MeterDetailsCommandsTab", () => {
  beforeEach(() => {
    window.localStorage.setItem("sunrise.web.apiBaseUrl", "http://localhost:8000");
    window.localStorage.setItem("sunrise.web.accessToken", "token-1");
  });

  afterEach(() => {
    vi.unstubAllGlobals();
    window.localStorage.clear();
  });

  it("renders recent commands for the meter and hides unsupported families", async () => {
    const { fetchMock } = createMockApi();
    vi.stubGlobal("fetch", fetchMock);

    render(<MeterDetailsCommandsTab meterId="meter-1" />);

    expect(await screen.findAllByText("profile-capture-template")).not.toHaveLength(0);
    expect(screen.getAllByText("relay-disconnect-template")).not.toHaveLength(0);
    expect(
      screen.queryByText("on-demand-read-hidden-template"),
    ).not.toBeInTheDocument();
  });

  it("loads bounded command detail when a recent command is selected", async () => {
    const { fetchMock } = createMockApi();
    vi.stubGlobal("fetch", fetchMock);
    const user = userEvent.setup();

    render(<MeterDetailsCommandsTab meterId="meter-1" />);

    const relayRow = await screen.findByRole("button", {
      name: /relay-disconnect-template/i,
    });
    await user.click(relayRow);

    const detailPanel = screen
      .getByRole("heading", { name: "Command detail" })
      .closest("section");
    expect(detailPanel).not.toBeNull();
    await waitFor(() => {
      expect(within(detailPanel as HTMLElement).getByText("runtime-relay-1")).toBeInTheDocument();
    });
  });

  it("triggers the existing profile capture execute-now path and refreshes the selected detail", async () => {
    const { fetchMock, requests } = createMockApi();
    vi.stubGlobal("fetch", fetchMock);
    const user = userEvent.setup();

    render(<MeterDetailsCommandsTab meterId="meter-1" />);

    const profileForm = screen
      .getByRole("heading", { name: "Profile capture" })
      .closest("form");
    expect(profileForm).not.toBeNull();

    await waitFor(() => {
      expect(
        within(profileForm as HTMLElement).getByRole("button", {
          name: /execute profile capture now/i,
        }),
      ).toBeEnabled();
    });

    await user.click(
      within(profileForm as HTMLElement).getByRole("button", {
        name: /execute profile capture now/i,
      }),
    );

    expect(
      await screen.findByText("Profile capture execute-now command requested."),
    ).toBeInTheDocument();

    const request = requests.find((entry) =>
      entry.url.endsWith("/api/v1/meters/meter-1/commands/profile-capture/execute-now"),
    );
    expect(request?.body?.command_template_id).toBe("template-profile-1");
    expect(request?.body?.endpoint_assignment_id).toBe("assignment-1");
    expect(request?.body?.protocol_association_profile_id).toBe("protocol-profile-1");
    expect(request?.body?.channel_ids).toEqual(["channel-1"]);

    const detailPanel = screen
      .getByRole("heading", { name: "Command detail" })
      .closest("section");
    await waitFor(() => {
      expect(
        within(detailPanel as HTMLElement).getByText("runtime-profile-action"),
      ).toBeInTheDocument();
    });
  });

  it("triggers the existing relay disconnect execute-now path", async () => {
    const { fetchMock, requests } = createMockApi();
    vi.stubGlobal("fetch", fetchMock);
    const user = userEvent.setup();

    render(<MeterDetailsCommandsTab meterId="meter-1" />);

    const relayForm = screen
      .getByRole("heading", { name: "Relay control" })
      .closest("form");
    expect(relayForm).not.toBeNull();

    await waitFor(() => {
      expect(
        within(relayForm as HTMLElement).getByRole("button", {
          name: /execute relay disconnect now/i,
        }),
      ).toBeEnabled();
    });

    await user.click(
      within(relayForm as HTMLElement).getByRole("button", {
        name: /execute relay disconnect now/i,
      }),
    );

    const request = requests.find((entry) =>
      entry.url.endsWith("/api/v1/meters/meter-1/commands/relay-control/execute-now"),
    );
    expect(request?.body?.relay_operation).toBe("disconnect");
    expect(request?.body?.command_template_id).toBe("template-relay-disconnect-1");
  });

  it("triggers the existing relay reconnect execute-now path", async () => {
    const { fetchMock, requests } = createMockApi();
    vi.stubGlobal("fetch", fetchMock);
    const user = userEvent.setup();

    render(<MeterDetailsCommandsTab meterId="meter-1" />);

    const relayForm = screen
      .getByRole("heading", { name: "Relay control" })
      .closest("form");
    expect(relayForm).not.toBeNull();

    await user.selectOptions(
      within(relayForm as HTMLElement).getByLabelText("Operation"),
      "reconnect",
    );

    await waitFor(() => {
      expect(
        within(relayForm as HTMLElement).getByRole("button", {
          name: /execute relay reconnect now/i,
        }),
      ).toBeEnabled();
    });

    await user.click(
      within(relayForm as HTMLElement).getByRole("button", {
        name: /execute relay reconnect now/i,
      }),
    );

    const relayRequests = requests.filter((entry) =>
      entry.url.endsWith("/api/v1/meters/meter-1/commands/relay-control/execute-now"),
    );
    const reconnectRequest = relayRequests.at(-1);
    expect(reconnectRequest?.body?.relay_operation).toBe("reconnect");
    expect(reconnectRequest?.body?.command_template_id).toBe(
      "template-relay-reconnect-1",
    );
  });
});
