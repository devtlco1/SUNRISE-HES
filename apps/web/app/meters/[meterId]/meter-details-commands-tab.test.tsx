import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { MeterDetailsCommandsTab } from "./meter-details-commands-tab";
import { OperationalShell } from "../../operational-shell";

type RequestLog = {
  method: string;
  url: string;
  body: Record<string, unknown> | null;
};

type MockMeterResponse = {
  id: string;
  serial_number: string;
  utility_meter_number: string | null;
  manufacturer_code: string;
  meter_model_code: string;
  meter_profile_code: string | null;
  communication_profile_code: string | null;
  current_status: string;
  last_seen_at: string | null;
};

type MockEndpointAssignment = {
  id: string;
  endpoint_id: string;
  endpoint_code: string;
  endpoint_display_name: string;
  assignment_status: string;
  is_primary: boolean;
};

type MockProtocolProfile = {
  id: string;
  code: string;
  name: string;
  protocol_family: string;
  is_active: boolean;
};

type MockConsumerLinkage = {
  meter_id: string;
  linkage_status: string;
  linkage_source: string | null;
  consumer_id: string | null;
  consumer_display_name: string | null;
  consumer_type: string | null;
  consumer_external_ref: string | null;
  account_id: string | null;
  account_number: string | null;
  account_status: string | null;
  service_point_id: string | null;
  service_point_code: string | null;
};

type MockCommandTemplate = {
  id: string;
  code: string;
  name: string;
  category: string;
  is_active: boolean;
};

type MockLoadProfileChannel = {
  id: string;
  channel_code: string;
  obis_code: string;
  interval_seconds: number;
  is_active: boolean;
};

function jsonResponse(payload: unknown, status = 200) {
  return new Response(JSON.stringify(payload), {
    status,
    headers: { "Content-Type": "application/json" },
  });
}

function createMockApi({
  meterResponse = {
    id: "meter-1",
    serial_number: "SN-1001",
    utility_meter_number: "UMN-1001",
    manufacturer_code: "GENERIC",
    meter_model_code: "GM-1",
    meter_profile_code: "default",
    communication_profile_code: "dlms-default",
    current_status: "commissioned",
    last_seen_at: "2026-03-30T11:00:00.000Z",
  },
  meterStatus = 200,
  meterErrorDetail = "Meter not found.",
  endpointAssignmentsStatus = 200,
  endpointAssignmentsErrorDetail = "Endpoint assignments unavailable.",
  protocolProfilesStatus = 200,
  protocolProfilesErrorDetail = "Protocol profiles unavailable.",
  consumerLinkageStatus = 200,
  consumerLinkageErrorDetail = "Consumer linkage unavailable.",
  endpointAssignments = [
    {
      id: "assignment-1",
      endpoint_id: "endpoint-1",
      endpoint_code: "tcp-primary",
      endpoint_display_name: "TCP Primary",
      assignment_status: "active",
      is_primary: true,
    },
  ],
  protocolProfiles = [
    {
      id: "protocol-profile-1",
      code: "dlms-profile",
      name: "DLMS Profile",
      protocol_family: "dlms_cosem",
      is_active: true,
    },
  ],
  templateItems = [
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
      code: "on-demand-read-template",
      name: "On Demand Read",
      category: "on_demand_read",
      is_active: true,
    },
  ],
  loadProfileChannels = [
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
  consumerLinkageResponse = {
    meter_id: "meter-1",
    linkage_status: "linked",
    linkage_source: "meter_account_assignment",
    consumer_id: "consumer-1",
    consumer_display_name: "Amina Al Balushi",
    consumer_type: "residential",
    consumer_external_ref: "CON-1001",
    account_id: "account-1",
    account_number: "ACC-1001",
    account_status: "active",
    service_point_id: "sp-1",
    service_point_code: "SP-1001",
  },
}: {
  meterResponse?: MockMeterResponse;
  meterStatus?: number;
  meterErrorDetail?: string;
  endpointAssignmentsStatus?: number;
  endpointAssignmentsErrorDetail?: string;
  protocolProfilesStatus?: number;
  protocolProfilesErrorDetail?: string;
  consumerLinkageStatus?: number;
  consumerLinkageErrorDetail?: string;
  endpointAssignments?: MockEndpointAssignment[];
  protocolProfiles?: MockProtocolProfile[];
  templateItems?: MockCommandTemplate[];
  loadProfileChannels?: MockLoadProfileChannel[];
  consumerLinkageResponse?: MockConsumerLinkage;
} = {}) {
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
    {
      command_id: "cmd-on-demand-1",
      command_family: "on_demand_read",
      command_category: "on_demand_read",
      command_status: "succeeded",
      meter_id: "meter-1",
      command_template_code: "on-demand-read-template",
      latest_command_execution_attempt_id: "attempt-on-demand-1",
      latest_command_execution_attempt_status: "succeeded",
      runtime_execution_record_id: "runtime-on-demand-1",
      family_specific_outcome_summary: {
        on_demand_read_operation: "read_billing_snapshot",
        snapshot_type: "billing",
        on_demand_read_execution_outcome: "succeeded",
      },
      orchestration_artifact_present: true,
      terminalization_artifact_present: true,
      execute_now_artifact_present: true,
      created_at: "2026-03-30T08:00:00.000Z",
      latest_updated_at: "2026-03-30T08:02:00.000Z",
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
    "cmd-on-demand-1": {
      command_id: "cmd-on-demand-1",
      command_family: "on_demand_read",
      command_category: "on_demand_read",
      command_status: "succeeded",
      meter_id: "meter-1",
      command_template_code: "on-demand-read-template",
      latest_command_execution_attempt_id: "attempt-on-demand-1",
      latest_command_execution_attempt_status: "succeeded",
      runtime_execution_record_id: "runtime-on-demand-1",
      family_specific_outcome_summary: {
        on_demand_read_operation: "read_billing_snapshot",
        snapshot_type: "billing",
        on_demand_read_execution_outcome: "succeeded",
      },
      orchestration_artifact_present: true,
      terminalization_artifact_present: true,
      execute_now_artifact_present: true,
      created_at: "2026-03-30T08:00:00.000Z",
      latest_updated_at: "2026-03-30T08:02:00.000Z",
      projection_record: { runtime_execution_record_id: "runtime-on-demand-1" },
    },
  };

  const fetchMock = vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
    const url = input.toString();
    const method = init?.method ?? "GET";
    const body = init?.body ? (JSON.parse(String(init.body)) as Record<string, unknown>) : null;

    if (method !== "GET") {
      requests.push({ method, url, body });
    }

    if (url.endsWith("/api/v1/auth/me")) {
      return jsonResponse({
        id: "user-1",
        username: "ops.user",
        email: "ops@example.com",
        full_name: "Ops User",
        status: "active",
        is_superuser: true,
      });
    }

    if (url.endsWith("/api/v1/meters/meter-1")) {
      if (meterStatus !== 200) {
        return jsonResponse({ detail: meterErrorDetail }, meterStatus);
      }
      return jsonResponse(meterResponse);
    }

    if (url.endsWith("/api/v1/meters/meter-1/consumer-linkage")) {
      if (consumerLinkageStatus !== 200) {
        return jsonResponse({ detail: consumerLinkageErrorDetail }, consumerLinkageStatus);
      }
      return jsonResponse(consumerLinkageResponse);
    }

    if (url.endsWith("/api/v1/command-templates")) {
      return jsonResponse({
        total: templateItems.length,
        items: templateItems,
      });
    }

    if (url.endsWith("/api/v1/meters/meter-1/endpoint-assignments")) {
      if (endpointAssignmentsStatus !== 200) {
        return jsonResponse(
          { detail: endpointAssignmentsErrorDetail },
          endpointAssignmentsStatus,
        );
      }
      return jsonResponse({
        total: endpointAssignments.length,
        items: endpointAssignments,
      });
    }

    if (url.endsWith("/api/v1/protocol-association-profiles")) {
      if (protocolProfilesStatus !== 200) {
        return jsonResponse(
          { detail: protocolProfilesErrorDetail },
          protocolProfilesStatus,
        );
      }
      return jsonResponse({
        total: protocolProfiles.length,
        items: protocolProfiles,
      });
    }

    if (url.endsWith("/api/v1/meters/meter-1/load-profile-channels")) {
      return jsonResponse({
        total: loadProfileChannels.length,
        items: loadProfileChannels,
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

    if (method === "POST" && url.endsWith("/api/v1/meters/meter-1/commands/on-demand-read/execute-now")) {
      recentCommands.unshift({
        command_id: "cmd-on-demand-action",
        command_family: "on_demand_read",
        command_category: "on_demand_read",
        command_status: "succeeded",
        meter_id: "meter-1",
        command_template_code: "on-demand-read-template",
        latest_command_execution_attempt_id: "attempt-on-demand-action",
        latest_command_execution_attempt_status: "succeeded",
        runtime_execution_record_id: "runtime-on-demand-action",
        family_specific_outcome_summary: {
          on_demand_read_operation: "read_billing_snapshot",
          snapshot_type: "billing",
          on_demand_read_execution_outcome: "succeeded",
        },
        orchestration_artifact_present: true,
        terminalization_artifact_present: true,
        execute_now_artifact_present: true,
        created_at: "2026-03-30T12:10:00.000Z",
        latest_updated_at: "2026-03-30T12:11:00.000Z",
      });
      detailById["cmd-on-demand-action"] = {
        command_id: "cmd-on-demand-action",
        command_family: "on_demand_read",
        command_category: "on_demand_read",
        command_status: "succeeded",
        meter_id: "meter-1",
        command_template_code: "on-demand-read-template",
        latest_command_execution_attempt_id: "attempt-on-demand-action",
        latest_command_execution_attempt_status: "succeeded",
        runtime_execution_record_id: "runtime-on-demand-action",
        family_specific_outcome_summary: {
          on_demand_read_operation: "read_billing_snapshot",
          snapshot_type: "billing",
          on_demand_read_execution_outcome: "succeeded",
        },
        orchestration_artifact_present: true,
        terminalization_artifact_present: true,
        execute_now_artifact_present: true,
        created_at: "2026-03-30T12:10:00.000Z",
        latest_updated_at: "2026-03-30T12:11:00.000Z",
        projection_record: { runtime_execution_record_id: "runtime-on-demand-action" },
      };
      return jsonResponse({ result: { command_id: "cmd-on-demand-action" } });
    }

    throw new Error(`Unhandled request: ${method} ${url}`);
  });

  return { fetchMock, requests };
}

function renderMeterTabInShell() {
  render(
    <OperationalShell
      eyebrow="Operational Pages"
      title="Meter meter-1"
      description="Bounded meter details"
      currentMeterId="meter-1"
    >
      {({ authorizedFetch }) => (
        <MeterDetailsCommandsTab
          meterId="meter-1"
          authorizedFetch={authorizedFetch}
        />
      )}
    </OperationalShell>,
  );
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

    renderMeterTabInShell();

    expect(await screen.findByRole("link", { name: "Current meter" })).toBeInTheDocument();
    expect(await screen.findAllByText("profile-capture-template")).not.toHaveLength(0);
    expect(screen.getAllByText("relay-disconnect-template")).not.toHaveLength(0);
    expect(screen.getAllByText("on-demand-read-template")).not.toHaveLength(0);
  });

  it("renders the operational summary panel with current meter context", async () => {
    const { fetchMock } = createMockApi();
    vi.stubGlobal("fetch", fetchMock);

    renderMeterTabInShell();

    expect(await screen.findByText("SN-1001")).toBeInTheDocument();

    const summaryPanel = screen
      .getByRole("heading", { name: "Operational summary" })
      .closest("section");
    expect(summaryPanel).not.toBeNull();

    expect(within(summaryPanel as HTMLElement).getByText("meter-1")).toBeInTheDocument();
    expect(within(summaryPanel as HTMLElement).getByText("commissioned")).toBeInTheDocument();
    expect(within(summaryPanel as HTMLElement).getByText("dlms-default")).toBeInTheDocument();
    expect(within(summaryPanel as HTMLElement).getByText("tcp-primary")).toBeInTheDocument();
    expect(within(summaryPanel as HTMLElement).getByText("dlms-profile")).toBeInTheDocument();
  });

  it("renders a bounded loading state while the meter summary is bootstrapping", async () => {
    const { fetchMock } = createMockApi();
    vi.stubGlobal(
      "fetch",
      vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
        const url = input.toString();
        if (url.endsWith("/api/v1/meters/meter-1")) {
          await new Promise((resolve) => setTimeout(resolve, 100));
        }
        return fetchMock(input, init);
      }),
    );

    renderMeterTabInShell();

    await waitFor(() => {
      expect(
        screen.queryByText("Loading meter summary...") ??
          screen.queryByText("meter-1"),
      ).toBeInTheDocument();
    });
    expect(await screen.findByText("meter-1")).toBeInTheDocument();
  });

  it("renders the connectivity context panel with current endpoint and protocol state", async () => {
    const { fetchMock } = createMockApi();
    vi.stubGlobal("fetch", fetchMock);

    renderMeterTabInShell();

    expect(await screen.findByText("Connectivity context")).toBeInTheDocument();

    const connectivityPanel = screen
      .getByRole("heading", { name: "Connectivity context" })
      .closest("section");
    expect(connectivityPanel).not.toBeNull();

    await waitFor(() => {
      expect(
        within(connectivityPanel as HTMLElement).getByText("TCP Primary"),
      ).toBeInTheDocument();
      expect(
        within(connectivityPanel as HTMLElement).getByText("tcp-primary"),
      ).toBeInTheDocument();
      expect(
        within(connectivityPanel as HTMLElement).getByText("active"),
      ).toBeInTheDocument();
      expect(
        within(connectivityPanel as HTMLElement).getByText("Primary"),
      ).toBeInTheDocument();
      expect(
        within(connectivityPanel as HTMLElement).getByText("dlms-default"),
      ).toBeInTheDocument();
      expect(
        within(connectivityPanel as HTMLElement).getByText("dlms-profile"),
      ).toBeInTheDocument();
      expect(
        within(connectivityPanel as HTMLElement).getByText("dlms_cosem"),
      ).toBeInTheDocument();
      expect(
        within(connectivityPanel as HTMLElement).getByText(
          "Recent connectivity signal recorded",
        ),
      ).toBeInTheDocument();
    });
  });

  it("renders the consumer linkage card when a linked subscriber exists", async () => {
    const { fetchMock } = createMockApi();
    vi.stubGlobal("fetch", fetchMock);

    renderMeterTabInShell();

    const linkagePanel = (await screen.findByRole("heading", {
      name: "Consumer linkage",
    })).closest("section");
    expect(linkagePanel).not.toBeNull();

    await waitFor(() => {
      expect(
        within(linkagePanel as HTMLElement).getByText("Amina Al Balushi"),
      ).toBeInTheDocument();
      expect(
        within(linkagePanel as HTMLElement).getByText("consumer-1"),
      ).toBeInTheDocument();
      expect(
        within(linkagePanel as HTMLElement).getByText("ACC-1001"),
      ).toBeInTheDocument();
      expect(
        within(linkagePanel as HTMLElement).getByText("SP-1001"),
      ).toBeInTheDocument();
    });

    expect(
      within(linkagePanel as HTMLElement).getByRole("link", {
        name: "Open subscriber detail",
      }),
    ).toHaveAttribute("href", "/subscribers/consumer-1");
  });

  it("renders a bounded unlinked state when no subscriber is linked to the meter", async () => {
    const { fetchMock } = createMockApi({
      consumerLinkageResponse: {
        meter_id: "meter-1",
        linkage_status: "unlinked",
        linkage_source: null,
        consumer_id: null,
        consumer_display_name: null,
        consumer_type: null,
        consumer_external_ref: null,
        account_id: null,
        account_number: null,
        account_status: null,
        service_point_id: null,
        service_point_code: null,
      },
    });
    vi.stubGlobal("fetch", fetchMock);

    renderMeterTabInShell();

    const linkagePanel = (await screen.findByRole("heading", {
      name: "Consumer linkage",
    })).closest("section");
    expect(linkagePanel).not.toBeNull();

    await waitFor(() => {
      expect(
        within(linkagePanel as HTMLElement).getByText(
          /No current subscriber linkage available for this meter\./i,
        ),
      ).toBeInTheDocument();
    });
  });

  it("renders a bounded consumer linkage error without disturbing the existing meter panels", async () => {
    const { fetchMock } = createMockApi({
      consumerLinkageStatus: 503,
      consumerLinkageErrorDetail: "Consumer linkage temporarily unavailable.",
    });
    vi.stubGlobal("fetch", fetchMock);

    renderMeterTabInShell();

    expect(
      await screen.findByText("Consumer linkage temporarily unavailable."),
    ).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "Operational summary" })).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "Connectivity context" })).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "Action readiness" })).toBeInTheDocument();
  });

  it("renders a bounded loading state while consumer linkage is bootstrapping", async () => {
    const { fetchMock } = createMockApi();
    vi.stubGlobal(
      "fetch",
      vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
        const url = input.toString();
        if (url.endsWith("/api/v1/meters/meter-1/consumer-linkage")) {
          await new Promise((resolve) => setTimeout(resolve, 100));
        }
        return fetchMock(input, init);
      }),
    );

    renderMeterTabInShell();

    expect(await screen.findByText("Loading consumer linkage...")).toBeInTheDocument();
    expect(await screen.findByText("Amina Al Balushi")).toBeInTheDocument();
  });

  it("renders a bounded loading state while connectivity context is bootstrapping", async () => {
    const { fetchMock } = createMockApi();
    vi.stubGlobal(
      "fetch",
      vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
        const url = input.toString();
        if (url.endsWith("/api/v1/meters/meter-1/endpoint-assignments")) {
          await new Promise((resolve) => setTimeout(resolve, 100));
        }
        return fetchMock(input, init);
      }),
    );

    renderMeterTabInShell();

    expect(await screen.findByText("Loading connectivity context...")).toBeInTheDocument();
    expect(await screen.findByText("TCP Primary")).toBeInTheDocument();
  });

  it("renders the action readiness panel for the existing execute-now flows", async () => {
    const { fetchMock } = createMockApi();
    vi.stubGlobal("fetch", fetchMock);

    renderMeterTabInShell();

    const readinessHeading = await screen.findByRole("heading", {
      name: "Action readiness",
    });
    const readinessPanel = readinessHeading
      .closest("section");
    expect(readinessPanel).not.toBeNull();

    await waitFor(() => {
      expect(
        within(readinessPanel as HTMLElement).getByText("Profile capture execute-now"),
      ).toBeInTheDocument();
      expect(
        within(readinessPanel as HTMLElement).getByText("Relay disconnect execute-now"),
      ).toBeInTheDocument();
      expect(
        within(readinessPanel as HTMLElement).getByText("Relay reconnect execute-now"),
      ).toBeInTheDocument();
      expect(
        within(readinessPanel as HTMLElement).getByText("On-demand read execute-now"),
      ).toBeInTheDocument();
    });

    expect(
      within(readinessPanel as HTMLElement).getAllByText("ready"),
    ).toHaveLength(4);
    expect(
      within(readinessPanel as HTMLElement).getAllByText(
        "All minimum prerequisites available.",
      ),
    ).toHaveLength(4);
  });

  it("renders a bounded loading state while action readiness is bootstrapping", async () => {
    const { fetchMock } = createMockApi();
    vi.stubGlobal(
      "fetch",
      vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
        const url = input.toString();
        if (url.endsWith("/api/v1/command-templates")) {
          await new Promise((resolve) => setTimeout(resolve, 100));
        }
        return fetchMock(input, init);
      }),
    );

    renderMeterTabInShell();

    expect(await screen.findByText("Loading action readiness...")).toBeInTheDocument();
    expect(await screen.findByText("Profile capture execute-now")).toBeInTheDocument();
  });

  it("renders bounded summary fallbacks when optional meter context is unavailable", async () => {
    const { fetchMock } = createMockApi({
      meterResponse: {
        id: "meter-1",
        serial_number: "SN-1001",
        utility_meter_number: null,
        manufacturer_code: "GENERIC",
        meter_model_code: "GM-1",
        meter_profile_code: null,
        communication_profile_code: null,
        current_status: "commissioned",
        last_seen_at: null,
      },
      endpointAssignments: [],
      protocolProfiles: [],
    });
    vi.stubGlobal("fetch", fetchMock);

    renderMeterTabInShell();

    expect(await screen.findAllByText("Not available")).not.toHaveLength(0);
    expect(screen.getByText("No active endpoint")).toBeInTheDocument();
    expect(screen.getByText("No active protocol profile")).toBeInTheDocument();
  });

  it("renders bounded connectivity fallbacks when endpoint and protocol context is unavailable", async () => {
    const { fetchMock } = createMockApi({
      meterResponse: {
        id: "meter-1",
        serial_number: "SN-1001",
        utility_meter_number: "UMN-1001",
        manufacturer_code: "GENERIC",
        meter_model_code: "GM-1",
        meter_profile_code: "default",
        communication_profile_code: null,
        current_status: "commissioned",
        last_seen_at: null,
      },
      endpointAssignments: [],
      protocolProfiles: [],
    });
    vi.stubGlobal("fetch", fetchMock);

    renderMeterTabInShell();

    await waitFor(() => {
      expect(
        screen.getByText("Connectivity context not available."),
      ).toBeInTheDocument();
    });
  });

  it("renders bounded action readiness states when prerequisites are missing", async () => {
    const { fetchMock } = createMockApi({
      endpointAssignments: [],
      protocolProfiles: [],
      loadProfileChannels: [],
    });
    vi.stubGlobal("fetch", fetchMock);

    renderMeterTabInShell();

    const readinessHeading = await screen.findByRole("heading", {
      name: "Action readiness",
    });
    const readinessPanel = readinessHeading
      .closest("section");
    expect(readinessPanel).not.toBeNull();

    await waitFor(() => {
      expect(
        within(readinessPanel as HTMLElement).getAllByText("partially ready"),
      ).toHaveLength(4);
    });

    expect(
      within(readinessPanel as HTMLElement).getByText(
        "Missing: active endpoint assignment, active protocol profile, active load-profile channel.",
      ),
    ).toBeInTheDocument();
    expect(
      within(readinessPanel as HTMLElement).getAllByText(
        "Missing: active endpoint assignment, active protocol profile.",
      ),
    ).toHaveLength(3);
  });

  it("renders a bounded summary unavailable state when meter context fails to load", async () => {
    const { fetchMock } = createMockApi({
      meterStatus: 404,
      meterErrorDetail: "Meter not found.",
    });
    vi.stubGlobal("fetch", fetchMock);

    renderMeterTabInShell();

    expect(await screen.findByText("Meter not found.")).toBeInTheDocument();
    expect(screen.getByText("Meter summary not available.")).toBeInTheDocument();
  });

  it("renders a bounded action readiness unavailable state when meter context fails to load", async () => {
    const { fetchMock } = createMockApi({
      meterStatus: 404,
      meterErrorDetail: "Meter not found.",
    });
    vi.stubGlobal("fetch", fetchMock);

    renderMeterTabInShell();

    expect(await screen.findByText("Meter not found.")).toBeInTheDocument();
    expect(await screen.findByText("Action readiness not available.")).toBeInTheDocument();
  });

  it("renders a bounded connectivity error state while preserving partial context", async () => {
    const { fetchMock } = createMockApi({
      endpointAssignmentsStatus: 503,
      endpointAssignmentsErrorDetail: "Endpoint assignments unavailable.",
    });
    vi.stubGlobal("fetch", fetchMock);

    renderMeterTabInShell();

    expect(
      await screen.findByText(
        "Unable to load complete meter connectivity and command context.",
      ),
    ).toBeInTheDocument();

    const connectivityPanel = screen
      .getByRole("heading", { name: "Connectivity context" })
      .closest("section");
    expect(connectivityPanel).not.toBeNull();

    expect(
      within(connectivityPanel as HTMLElement).getByText("dlms-default"),
    ).toBeInTheDocument();
    expect(
      within(connectivityPanel as HTMLElement).getByText("dlms-profile"),
    ).toBeInTheDocument();
    expect(
      within(connectivityPanel as HTMLElement).queryByText("Connectivity context not available."),
    ).not.toBeInTheDocument();
    expect(screen.getByText("SN-1001")).toBeInTheDocument();
  });

  it("loads bounded command detail when a recent command is selected", async () => {
    const { fetchMock } = createMockApi();
    vi.stubGlobal("fetch", fetchMock);
    const user = userEvent.setup();

    renderMeterTabInShell();

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

  it("loads bounded on-demand-read command detail when a recent command is selected", async () => {
    const { fetchMock } = createMockApi();
    vi.stubGlobal("fetch", fetchMock);
    const user = userEvent.setup();

    renderMeterTabInShell();

    const onDemandRow = await screen.findByRole("button", {
      name: /on-demand-read-template/i,
    });
    await user.click(onDemandRow);

    const detailPanel = screen
      .getByRole("heading", { name: "Command detail" })
      .closest("section");
    expect(detailPanel).not.toBeNull();
    await waitFor(() => {
      expect(
        within(detailPanel as HTMLElement).getByText("runtime-on-demand-1"),
      ).toBeInTheDocument();
      expect(
        within(detailPanel as HTMLElement).getByText(
          "read_billing_snapshot billing (succeeded)",
        ),
      ).toBeInTheDocument();
    });
  });

  it("triggers the existing profile capture execute-now path and refreshes the selected detail", async () => {
    const { fetchMock, requests } = createMockApi();
    vi.stubGlobal("fetch", fetchMock);
    const user = userEvent.setup();

    renderMeterTabInShell();
    await screen.findByText("Recent commands");

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

    renderMeterTabInShell();
    await screen.findByText("Recent commands");

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

    renderMeterTabInShell();
    await screen.findByText("Recent commands");

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

  it("triggers the existing on-demand-read execute-now path and refreshes the selected detail", async () => {
    const { fetchMock, requests } = createMockApi();
    vi.stubGlobal("fetch", fetchMock);
    const user = userEvent.setup();

    renderMeterTabInShell();
    await screen.findByText("Recent commands");

    const onDemandForm = screen
      .getByRole("heading", { name: "On-demand read" })
      .closest("form");
    expect(onDemandForm).not.toBeNull();

    await waitFor(() => {
      expect(
        within(onDemandForm as HTMLElement).getByRole("button", {
          name: /execute on-demand read now/i,
        }),
      ).toBeEnabled();
    });

    await user.click(
      within(onDemandForm as HTMLElement).getByRole("button", {
        name: /execute on-demand read now/i,
      }),
    );

    expect(
      await screen.findByText("On-demand read execute-now command requested."),
    ).toBeInTheDocument();

    const request = requests.find((entry) =>
      entry.url.endsWith("/api/v1/meters/meter-1/commands/on-demand-read/execute-now"),
    );
    expect(request?.body?.command_template_id).toBe("template-on-demand-read-1");
    expect(request?.body?.endpoint_assignment_id).toBe("assignment-1");
    expect(request?.body?.protocol_association_profile_id).toBe("protocol-profile-1");
    expect(request?.body?.on_demand_read_operation).toBe("read_billing_snapshot");

    const detailPanel = screen
      .getByRole("heading", { name: "Command detail" })
      .closest("section");
    await waitFor(() => {
      expect(
        within(detailPanel as HTMLElement).getByText("runtime-on-demand-action"),
      ).toBeInTheDocument();
    });
  });
});
