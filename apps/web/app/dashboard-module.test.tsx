import { render, screen, waitFor, within } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { DashboardModule } from "./dashboard-module";
import { OperationalShell } from "./operational-shell";

function jsonResponse(payload: unknown, status = 200) {
  return new Response(JSON.stringify(payload), {
    status,
    headers: { "Content-Type": "application/json" },
  });
}

function createMockApi({
  metersStatus = 200,
  metersDetail = "Meter overview unavailable.",
  meterItems = [
    {
      id: "meter-1",
      serial_number: "SN-1001",
      utility_meter_number: "UMN-1001",
      manufacturer_code: "GENERIC",
      meter_model_code: "GM-1",
      communication_profile_code: "gprs-primary",
      meter_profile_code: "dlms-main",
      firmware_version: "FW-1.0.0",
      current_status: "active",
      transformer_id: "TR-01",
      service_point_id: "sp-1",
      last_seen_at: "2026-03-30T11:00:00.000Z",
      is_active: true,
    },
    {
      id: "meter-2",
      serial_number: "SN-1002",
      utility_meter_number: "UMN-1002",
      manufacturer_code: "GENERIC",
      meter_model_code: "GM-2",
      communication_profile_code: "gprs-primary",
      meter_profile_code: "dlms-main",
      firmware_version: "FW-1.1.0",
      current_status: "maintenance",
      transformer_id: "TR-02",
      service_point_id: "sp-2",
      last_seen_at: null,
      is_active: true,
    },
  ],
  recentCommands = [
    {
      command_id: "command-1",
      command_family: "profile_capture",
      command_status: "succeeded",
      meter_id: "meter-1",
      command_template_code: "profile-capture-template",
      family_specific_outcome_summary: { terminal_status_category: "completed" },
      latest_updated_at: "2026-03-30T11:05:00.000Z",
    },
  ],
  pendingApprovals = [
    {
      command_id: "pending-1",
      command_family: "relay_control",
      command_status: "pending",
      meter_id: "meter-2",
      command_template_code: "relay-disconnect-template",
      family_specific_outcome_summary: {
        relay_control_operation: "disconnect",
        relay_control_execution_outcome: "pending",
      },
      latest_updated_at: "2026-03-30T11:11:00.000Z",
    },
  ],
  recentEvents = [
    {
      id: "event-1",
      meter_id: "meter-2",
      event_code: "tamper",
      event_name: "Tamper detected",
      severity: "critical",
      event_state: "new",
      occurred_at: "2026-03-30T11:10:00.000Z",
      received_at: "2026-03-30T11:10:00.000Z",
    },
  ],
}: {
  metersStatus?: number;
  metersDetail?: string;
  meterItems?: Array<Record<string, unknown>>;
  recentCommands?: Array<Record<string, unknown>>;
  pendingApprovals?: Array<Record<string, unknown>>;
  recentEvents?: Array<Record<string, unknown>>;
} = {}) {
  const fetchMock = vi.fn(async (input: RequestInfo | URL) => {
    const url = input.toString();

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

    if (url.includes("/api/v1/meters?")) {
      if (metersStatus !== 200) {
        return jsonResponse({ detail: metersDetail }, metersStatus);
      }

      return jsonResponse({
        total: meterItems.length,
        items: meterItems,
      });
    }

    if (url.includes("/api/v1/commands/approvals/pending?")) {
      return jsonResponse({
        total: pendingApprovals.length,
        items: pendingApprovals,
      });
    }

    if (url.includes("/api/v1/commands/recent?")) {
      return jsonResponse({
        total: recentCommands.length,
        items: recentCommands,
      });
    }

    if (url.includes("/api/v1/events/recent?")) {
      return jsonResponse({
        total: recentEvents.length,
        items: recentEvents,
      });
    }

    const sessionsMatch = url.match(/\/api\/v1\/meters\/([^/]+)\/sessions\?limit=1$/);
    if (sessionsMatch) {
      const meterId = sessionsMatch[1];
      return jsonResponse({
        total: meterId === "meter-1" ? 1 : 0,
        items:
          meterId === "meter-1"
            ? [
                {
                  id: "session-1",
                  started_at: "2026-03-30T10:50:00.000Z",
                  ended_at: "2026-03-30T11:00:00.000Z",
                  status: "succeeded",
                  session_purpose: "scheduled_poll",
                },
              ]
            : [],
      });
    }

    const readingsMatch = url.match(/\/api\/v1\/meters\/([^/]+)\/readings\?limit=1$/);
    if (readingsMatch) {
      const meterId = readingsMatch[1];
      return jsonResponse({
        total: meterId === "meter-1" ? 1 : 0,
        items:
          meterId === "meter-1"
            ? [{ id: "reading-1", captured_at: "2026-03-30T11:05:00.000Z", quality: "actual" }]
            : [],
      });
    }

    const gisMatch = url.match(/\/api\/v1\/gis-lite\/entities\?limit=1&meter_id=([^&]+)$/);
    if (gisMatch) {
      const meterId = gisMatch[1];
      return jsonResponse({
        total: 1,
        items: [
          {
            meter_id: meterId,
            meter_status: "active",
            meter_last_seen_at: "2026-03-30T11:00:00.000Z",
            service_point_id: `sp-${meterId}`,
            service_point_code: meterId === "meter-1" ? "SP-1001" : "SP-1002",
            has_coordinates: meterId === "meter-1",
            subscriber_display_name: meterId === "meter-1" ? "Amina Al Balushi" : null,
            account_number: meterId === "meter-1" ? "ACC-1001" : null,
            location_presence: meterId === "meter-1" ? "coordinates_available" : "service_point_only",
          },
        ],
      });
    }

    throw new Error(`Unhandled request: ${url}`);
  });

  return { fetchMock };
}

function renderDashboardInShell() {
  render(
    <OperationalShell
      eyebrow="Operations control"
      title="AMI command desk"
      description="Fleet posture for tests."
    >
      {({ authorizedFetch }) => <DashboardModule authorizedFetch={authorizedFetch} />}
    </OperationalShell>,
  );
}

describe("DashboardModule", () => {
  beforeEach(() => {
    window.localStorage.setItem("sunrise.web.apiBaseUrl", "http://localhost:8000");
    window.localStorage.setItem("sunrise.web.accessToken", "token-1");
  });

  afterEach(() => {
    vi.unstubAllGlobals();
    window.localStorage.clear();
  });

  it("renders operator desk surfaces with live API-backed rows", async () => {
    const { fetchMock } = createMockApi();
    vi.stubGlobal("fetch", fetchMock);

    renderDashboardInShell();

    expect(await screen.findByText("profile-capture-template")).toBeInTheDocument();
    await waitFor(() => {
      expect(screen.getByText("Network posture")).toBeInTheDocument();
    });
    expect(screen.getByText("Remote action log")).toBeInTheDocument();
    expect(screen.getByText("Triage queue")).toBeInTheDocument();
    expect(screen.getByText("Event roll-up")).toBeInTheDocument();
    expect(screen.getByText("Registered endpoints")).toBeInTheDocument();
    expect(screen.getByText("Tamper detected")).toBeInTheDocument();
    expect(screen.getByLabelText("Operational shortcuts")).toBeInTheDocument();
  });

  it("exposes drill-down links into operational routes", async () => {
    const { fetchMock } = createMockApi();
    vi.stubGlobal("fetch", fetchMock);

    renderDashboardInShell();

    const shortcuts = await screen.findByLabelText("Operational shortcuts");
    expect(within(shortcuts).getByRole("link", { name: "Connectivity" })).toHaveAttribute(
      "href",
      "/connectivity",
    );
    expect(screen.getByRole("link", { name: "Commands" })).toHaveAttribute("href", "/commands");
    expect(screen.getByRole("link", { name: "Jobs / Events / Alerts" })).toHaveAttribute(
      "href",
      "/jobs-events-alerts",
    );
    expect(screen.getByRole("link", { name: "Readings" })).toHaveAttribute("href", "/readings");
  });

  it("surfaces meter scope errors from the API", async () => {
    const { fetchMock } = createMockApi({
      metersStatus: 503,
      metersDetail: "Meter overview unavailable.",
    });
    vi.stubGlobal("fetch", fetchMock);

    renderDashboardInShell();

    expect(await screen.findByText("Meter overview unavailable.")).toBeInTheDocument();
  });
});
