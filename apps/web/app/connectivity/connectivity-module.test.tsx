import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { OperationalShell } from "../operational-shell";
import { ConnectivityModule } from "./connectivity-module";

function includesText(text: string) {
  return (_content: string, element: Element | null) => element?.textContent?.includes(text) ?? false;
}

function jsonResponse(payload: unknown, status = 200) {
  return new Response(JSON.stringify(payload), {
    status,
    headers: { "Content-Type": "application/json" },
  });
}

function createMockApi({
  meterItems = [
    {
      id: "meter-1",
      serial_number: "SN-1001",
      utility_meter_number: "UMN-1001",
      manufacturer_code: "GENERIC",
      meter_model_code: "GM-1",
      communication_profile_code: "dlms-primary",
      meter_profile_code: "residential-default",
      current_status: "commissioned",
      last_seen_at: "2099-01-01T11:00:00.000Z",
      is_active: true,
    },
    {
      id: "meter-2",
      serial_number: "SN-1002",
      utility_meter_number: null,
      manufacturer_code: "GENERIC",
      meter_model_code: "GM-2",
      communication_profile_code: null,
      meter_profile_code: "industrial-default",
      current_status: "registered",
      last_seen_at: null,
      is_active: false,
    },
  ],
  meterStatus = 200,
  meterDetail = "Unable to load connectivity overview.",
  endpointAssignmentsByMeter = {
    "meter-1": [
      {
        id: "assignment-1",
        endpoint_code: "tcp-primary",
        endpoint_display_name: "TCP Primary",
        assignment_status: "active",
        is_primary: true,
      },
    ],
    "meter-2": [],
  } as Record<string, Array<Record<string, unknown>>>,
  sessionsByMeter = {
    "meter-1": [
      {
        id: "session-1",
        started_at: "2026-03-30T11:05:00.000Z",
        ended_at: "2026-03-30T11:06:00.000Z",
        status: "succeeded",
        session_purpose: "connectivity_test",
      },
    ],
    "meter-2": [],
  } as Record<string, Array<Record<string, unknown>>>,
  delayedMeters = false,
}: {
  meterItems?: Array<Record<string, unknown>>;
  meterStatus?: number;
  meterDetail?: string;
  endpointAssignmentsByMeter?: Record<string, Array<Record<string, unknown>>>;
  sessionsByMeter?: Record<string, Array<Record<string, unknown>>>;
  delayedMeters?: boolean;
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
      if (delayedMeters) {
        await new Promise((resolve) => window.setTimeout(resolve, 20));
      }

      if (meterStatus !== 200) {
        return jsonResponse({ detail: meterDetail }, meterStatus);
      }

      return jsonResponse({
        total: meterItems.length,
        items: meterItems,
      });
    }

    const endpointAssignmentsMatch = url.match(
      /\/api\/v1\/meters\/([^/]+)\/endpoint-assignments$/,
    );
    if (endpointAssignmentsMatch) {
      const meterId = endpointAssignmentsMatch[1];
      return jsonResponse({
        total: endpointAssignmentsByMeter[meterId]?.length ?? 0,
        items: endpointAssignmentsByMeter[meterId] ?? [],
      });
    }

    const sessionsMatch = url.match(/\/api\/v1\/meters\/([^/]+)\/sessions\?limit=1$/);
    if (sessionsMatch) {
      const meterId = sessionsMatch[1];
      return jsonResponse({
        total: sessionsByMeter[meterId]?.length ?? 0,
        items: sessionsByMeter[meterId] ?? [],
      });
    }

    throw new Error(`Unhandled request: ${url}`);
  });

  return { fetchMock };
}

function renderConnectivityModuleInShell() {
  render(
    <OperationalShell
      eyebrow="Operational Pages"
      title="Connectivity Overview MVP"
      description="Bounded connectivity overview"
    >
      {({ authorizedFetch }) => (
        <ConnectivityModule authorizedFetch={authorizedFetch} />
      )}
    </OperationalShell>,
  );
}

describe("ConnectivityModule", () => {
  beforeEach(() => {
    window.localStorage.setItem("sunrise.web.apiBaseUrl", "http://localhost:8000");
    window.localStorage.setItem("sunrise.web.accessToken", "token-1");
  });

  afterEach(() => {
    vi.unstubAllGlobals();
    window.localStorage.clear();
  });

  it("renders a compact connectivity overview inside the shared shell", async () => {
    const { fetchMock } = createMockApi();
    vi.stubGlobal("fetch", fetchMock);

    renderConnectivityModuleInShell();

    expect(await screen.findByRole("link", { name: "Connectivity" })).toBeInTheDocument();
    expect(
      await screen.findByRole("heading", { name: "Connectivity operations center" }),
    ).toBeInTheDocument();

    await waitFor(() => {
      expect(screen.getByText("Meters in result set")).toBeInTheDocument();
      expect(screen.getByText("With active endpoint hint")).toBeInTheDocument();
      expect(screen.getByText("Latest session succeeded")).toBeInTheDocument();
    });
  });

  it("renders the connectivity-focused list with links into the existing meter details page", async () => {
    const { fetchMock } = createMockApi();
    vi.stubGlobal("fetch", fetchMock);

    renderConnectivityModuleInShell();

    const connectivityListPanel = await screen.findByRole("heading", {
      name: "Connectivity-focused meters",
    });
    const connectivityListSection = connectivityListPanel.closest("section");
    expect(connectivityListSection).not.toBeNull();

    const meterDetailLinks = await within(connectivityListSection as HTMLElement).findAllByRole("link", {
      name: "Open meter detail",
    });
    expect(meterDetailLinks[0]).toHaveAttribute("href", "/meters/meter-1");
    expect(meterDetailLinks[1]).toHaveAttribute(
      "href",
      "/meters/meter-2",
    );
    expect(screen.getAllByText("TCP Primary")).not.toHaveLength(0);
    expect(screen.getAllByText("succeeded (connectivity_test)")).not.toHaveLength(0);
  });

  it("renders a bounded offline meters and connectivity incidents surface", async () => {
    const { fetchMock } = createMockApi();
    vi.stubGlobal("fetch", fetchMock);
    const user = userEvent.setup();

    renderConnectivityModuleInShell();

    const incidentsSection = await screen.findByRole("heading", {
      name: "Offline meters / connectivity incidents",
    });
    const incidentsPanel = incidentsSection.closest("section");
    expect(incidentsPanel).not.toBeNull();

    await waitFor(() => {
      expect(
        within(incidentsPanel as HTMLElement).getAllByText(includesText("1 incident contexts")).length,
      ).toBeGreaterThan(0);
      expect(within(incidentsPanel as HTMLElement).getAllByText("Offline").length).toBeGreaterThan(0);
      expect(within(incidentsPanel as HTMLElement).getByText("Severity Critical")).toBeInTheDocument();
      expect(within(incidentsPanel as HTMLElement).getByText("No recent signal")).toBeInTheDocument();
    });

    await user.click(
      within(incidentsPanel as HTMLElement).getByRole("button", { name: "Inspect incident" }),
    );

    const detailPanel = screen.getByRole("heading", { name: "Connectivity detail" }).closest("section");
    expect(detailPanel).not.toBeNull();
    await waitFor(() => {
      expect(
        within(detailPanel as HTMLElement).getAllByText("SN-1002"),
      ).not.toHaveLength(0);
      expect(
        within(detailPanel as HTMLElement).getByText("Incident Offline"),
      ).toBeInTheDocument();
      expect(
        within(detailPanel as HTMLElement).getByText("Severity Critical"),
      ).toBeInTheDocument();
    });
  });

  it("renders a dedicated live sessions workspace with identity, freshness, and health visibility", async () => {
    const { fetchMock } = createMockApi({
      meterItems: [
        {
          id: "meter-1",
          serial_number: "SN-1001",
          utility_meter_number: "UMN-1001",
          manufacturer_code: "GENERIC",
          meter_model_code: "GM-1",
          communication_profile_code: "dlms-primary",
          meter_profile_code: "residential-default",
          current_status: "commissioned",
          last_seen_at: "2099-01-01T11:45:00.000Z",
          is_active: true,
        },
        {
          id: "meter-2",
          serial_number: "SN-1002",
          utility_meter_number: null,
          manufacturer_code: "GENERIC",
          meter_model_code: "GM-2",
          communication_profile_code: null,
          meter_profile_code: "industrial-default",
          current_status: "registered",
          last_seen_at: null,
          is_active: false,
        },
      ],
      endpointAssignmentsByMeter: {
        "meter-1": [
          {
            id: "assignment-1",
            endpoint_code: "tcp-primary",
            endpoint_display_name: "TCP Primary",
            assignment_status: "active",
            is_primary: true,
          },
        ],
        "meter-2": [],
      },
      sessionsByMeter: {
        "meter-1": [
          {
            id: "session-1",
            started_at: "2026-03-31T11:46:00.000Z",
            ended_at: null,
            status: "started",
            session_purpose: "manual_diagnostic",
          },
        ],
        "meter-2": [
          {
            id: "session-2",
            started_at: "2026-03-31T11:40:00.000Z",
            ended_at: "2026-03-31T11:41:00.000Z",
            status: "failed",
            session_purpose: "connectivity_test",
          },
        ],
      },
    });
    vi.stubGlobal("fetch", fetchMock);
    const user = userEvent.setup();

    renderConnectivityModuleInShell();

    const liveSessionsSection = await screen.findByRole("heading", {
      name: "Connectivity live sessions workspace",
    });
    const liveSessionsPanel = liveSessionsSection.closest("section");
    expect(liveSessionsPanel).not.toBeNull();

    await waitFor(() => {
      expect(
        within(liveSessionsPanel as HTMLElement).getAllByText(includesText("1 live sessions")).length,
      ).toBeGreaterThan(0);
      expect(
        within(liveSessionsPanel as HTMLElement).getByText("Live sessions in view"),
      ).toBeInTheDocument();
      expect(within(liveSessionsPanel as HTMLElement).getByText("SN-1001")).toBeInTheDocument();
      expect(
        within(liveSessionsPanel as HTMLElement).getByText("Session Started"),
      ).toBeInTheDocument();
      expect(
        within(liveSessionsPanel as HTMLElement).getByText("Live session healthy"),
      ).toBeInTheDocument();
      expect(
        within(liveSessionsPanel as HTMLElement).getByText("Manual Diagnostic session"),
      ).toBeInTheDocument();
      expect(within(liveSessionsPanel as HTMLElement).getByText("TCP Primary")).toBeInTheDocument();
    });

    await user.click(
      within(liveSessionsPanel as HTMLElement).getByRole("button", { name: "Inspect live session" }),
    );

    const detailPanel = screen.getByRole("heading", { name: "Connectivity detail" }).closest("section");
    expect(detailPanel).not.toBeNull();
    await waitFor(() => {
      expect(
        within(detailPanel as HTMLElement).getAllByText("SN-1001"),
      ).not.toHaveLength(0);
      expect(within(detailPanel as HTMLElement).getByText("Session Started")).toBeInTheDocument();
    });
  });

  it("renders incident-state filters inside the connectivity incidents section", async () => {
    const { fetchMock } = createMockApi();
    vi.stubGlobal("fetch", fetchMock);

    renderConnectivityModuleInShell();

    const incidentsSection = await screen.findByRole("heading", {
      name: "Offline meters / connectivity incidents",
    });
    const incidentsPanel = incidentsSection.closest("section");
    expect(incidentsPanel).not.toBeNull();

    expect(
      within(incidentsPanel as HTMLElement).getByRole("button", { name: "All incidents" }),
    ).toBeInTheDocument();
    expect(
      within(incidentsPanel as HTMLElement).getByRole("button", { name: "Offline" }),
    ).toBeInTheDocument();
    expect(
      within(incidentsPanel as HTMLElement).getByRole("button", { name: "Stale" }),
    ).toBeInTheDocument();
    expect(
      within(incidentsPanel as HTMLElement).getByRole("button", { name: "Degraded" }),
    ).toBeInTheDocument();
    expect(
      within(incidentsPanel as HTMLElement).getByText(
        "All incident states in the current bounded connectivity scope.",
      ),
    ).toBeInTheDocument();
  });

  it("shows stale and degraded incident states with visible severity and freshness cues", async () => {
    const { fetchMock } = createMockApi({
      meterItems: [
        {
          id: "meter-1",
          serial_number: "SN-1001",
          utility_meter_number: "UMN-1001",
          manufacturer_code: "GENERIC",
          meter_model_code: "GM-1",
          communication_profile_code: "dlms-primary",
          meter_profile_code: "residential-default",
          current_status: "commissioned",
          last_seen_at: "2099-01-01T11:30:00.000Z",
          is_active: true,
        },
        {
          id: "meter-2",
          serial_number: "SN-1002",
          utility_meter_number: null,
          manufacturer_code: "GENERIC",
          meter_model_code: "GM-2",
          communication_profile_code: null,
          meter_profile_code: "industrial-default",
          current_status: "commissioned",
          last_seen_at: "2020-01-01T00:00:00.000Z",
          is_active: true,
        },
        {
          id: "meter-3",
          serial_number: "SN-1003",
          utility_meter_number: "UMN-1003",
          manufacturer_code: "GENERIC",
          meter_model_code: "GM-3",
          communication_profile_code: "rf-mesh",
          meter_profile_code: "commercial-default",
          current_status: "active",
          last_seen_at: "2099-01-01T11:45:00.000Z",
          is_active: true,
        },
      ],
      sessionsByMeter: {
        "meter-1": [
          {
            id: "session-1",
            started_at: "2026-03-31T11:40:00.000Z",
            ended_at: "2026-03-31T11:41:00.000Z",
            status: "succeeded",
            session_purpose: "connectivity_test",
          },
        ],
        "meter-2": [],
        "meter-3": [
          {
            id: "session-3",
            started_at: "2026-03-31T11:46:00.000Z",
            ended_at: "2026-03-31T11:47:00.000Z",
            status: "failed",
            session_purpose: "connectivity_test",
          },
        ],
      },
      endpointAssignmentsByMeter: {
        "meter-1": [
          {
            id: "assignment-1",
            endpoint_code: "tcp-primary",
            endpoint_display_name: "TCP Primary",
            assignment_status: "active",
            is_primary: true,
          },
        ],
        "meter-2": [],
        "meter-3": [
          {
            id: "assignment-3",
            endpoint_code: "rf-backhaul",
            endpoint_display_name: "RF Backhaul",
            assignment_status: "active",
            is_primary: true,
          },
        ],
      },
    });
    vi.stubGlobal("fetch", fetchMock);

    renderConnectivityModuleInShell();

    const incidentsSection = await screen.findByRole("heading", {
      name: "Offline meters / connectivity incidents",
    });
    const incidentsPanel = incidentsSection.closest("section");
    expect(incidentsPanel).not.toBeNull();

    await waitFor(() => {
      expect(
        within(incidentsPanel as HTMLElement).getAllByText(includesText("2 incident contexts")).length,
      ).toBeGreaterThan(0);
      expect(within(incidentsPanel as HTMLElement).getAllByText("Stale").length).toBeGreaterThan(0);
      expect(within(incidentsPanel as HTMLElement).getAllByText("Degraded").length).toBeGreaterThan(0);
      expect(
        within(incidentsPanel as HTMLElement).getAllByText("Severity Warning"),
      ).not.toHaveLength(0);
      expect(
        within(incidentsPanel as HTMLElement).getByText(/Signal stale for/i),
      ).toBeInTheDocument();
      expect(
        within(incidentsPanel as HTMLElement).getByText("Latest session Failed"),
      ).toBeInTheDocument();
    });
  });

  it("switches between all, offline, stale, and degraded incident filters", async () => {
    const { fetchMock } = createMockApi({
      meterItems: [
        {
          id: "meter-1",
          serial_number: "SN-1001",
          utility_meter_number: "UMN-1001",
          manufacturer_code: "GENERIC",
          meter_model_code: "GM-1",
          communication_profile_code: "dlms-primary",
          meter_profile_code: "residential-default",
          current_status: "commissioned",
          last_seen_at: null,
          is_active: true,
        },
        {
          id: "meter-2",
          serial_number: "SN-1002",
          utility_meter_number: null,
          manufacturer_code: "GENERIC",
          meter_model_code: "GM-2",
          communication_profile_code: null,
          meter_profile_code: "industrial-default",
          current_status: "commissioned",
          last_seen_at: "2020-01-01T00:00:00.000Z",
          is_active: true,
        },
        {
          id: "meter-3",
          serial_number: "SN-1003",
          utility_meter_number: "UMN-1003",
          manufacturer_code: "GENERIC",
          meter_model_code: "GM-3",
          communication_profile_code: "rf-mesh",
          meter_profile_code: "commercial-default",
          current_status: "active",
          last_seen_at: "2099-01-01T11:45:00.000Z",
          is_active: true,
        },
      ],
      sessionsByMeter: {
        "meter-1": [],
        "meter-2": [],
        "meter-3": [
          {
            id: "session-3",
            started_at: "2026-03-31T11:46:00.000Z",
            ended_at: "2026-03-31T11:47:00.000Z",
            status: "failed",
            session_purpose: "connectivity_test",
          },
        ],
      },
      endpointAssignmentsByMeter: {
        "meter-1": [],
        "meter-2": [],
        "meter-3": [
          {
            id: "assignment-3",
            endpoint_code: "rf-backhaul",
            endpoint_display_name: "RF Backhaul",
            assignment_status: "active",
            is_primary: true,
          },
        ],
      },
    });
    vi.stubGlobal("fetch", fetchMock);
    const user = userEvent.setup();

    renderConnectivityModuleInShell();

    const incidentsSection = await screen.findByRole("heading", {
      name: "Offline meters / connectivity incidents",
    });
    const incidentsPanel = incidentsSection.closest("section");
    expect(incidentsPanel).not.toBeNull();

    await waitFor(() => {
      expect(
        within(incidentsPanel as HTMLElement).getAllByText(includesText("3 incident contexts")).length,
      ).toBeGreaterThan(0);
      expect(within(incidentsPanel as HTMLElement).getAllByText("Offline").length).toBeGreaterThan(0);
      expect(within(incidentsPanel as HTMLElement).getAllByText("Stale").length).toBeGreaterThan(0);
      expect(within(incidentsPanel as HTMLElement).getAllByText("Degraded").length).toBeGreaterThan(0);
    });

    await user.click(within(incidentsPanel as HTMLElement).getByRole("button", { name: "Offline" }));

    await waitFor(() => {
      expect(
        within(incidentsPanel as HTMLElement).getAllByText(includesText("1 incident contexts")).length,
      ).toBeGreaterThan(0);
      expect(within(incidentsPanel as HTMLElement).getByText("Showing offline incidents only in the current bounded connectivity scope.")).toBeInTheDocument();
      expect(within(incidentsPanel as HTMLElement).getByText("SN-1001")).toBeInTheDocument();
      expect(within(incidentsPanel as HTMLElement).queryByText("SN-1002")).not.toBeInTheDocument();
      expect(within(incidentsPanel as HTMLElement).queryByText("SN-1003")).not.toBeInTheDocument();
    });

    await user.click(within(incidentsPanel as HTMLElement).getByRole("button", { name: "Stale" }));

    await waitFor(() => {
      expect(within(incidentsPanel as HTMLElement).getByText("SN-1002")).toBeInTheDocument();
      expect(within(incidentsPanel as HTMLElement).queryByText("SN-1001")).not.toBeInTheDocument();
      expect(within(incidentsPanel as HTMLElement).queryByText("SN-1003")).not.toBeInTheDocument();
    });

    await user.click(within(incidentsPanel as HTMLElement).getByRole("button", { name: "Degraded" }));

    await waitFor(() => {
      expect(within(incidentsPanel as HTMLElement).getByText("SN-1003")).toBeInTheDocument();
      expect(within(incidentsPanel as HTMLElement).queryByText("SN-1001")).not.toBeInTheDocument();
      expect(within(incidentsPanel as HTMLElement).queryByText("SN-1002")).not.toBeInTheDocument();
    });

    await user.click(
      within(incidentsPanel as HTMLElement).getByRole("button", { name: "Inspect incident" }),
    );

    const detailPanel = screen.getByRole("heading", { name: "Connectivity detail" }).closest("section");
    expect(detailPanel).not.toBeNull();
    await waitFor(() => {
      expect(
        within(detailPanel as HTMLElement).getAllByText("SN-1003"),
      ).not.toHaveLength(0);
      expect(
        within(detailPanel as HTMLElement).getByText("Incident Degraded"),
      ).toBeInTheDocument();
    });
  });

  it("renders bounded connectivity detail when a meter summary is selected", async () => {
    const { fetchMock } = createMockApi();
    vi.stubGlobal("fetch", fetchMock);
    const user = userEvent.setup();

    renderConnectivityModuleInShell();

    const inspectButtons = await screen.findAllByRole("button", {
      name: "Inspect summary",
    });
    await user.click(inspectButtons[1]);

    const detailPanel = screen.getByRole("heading", { name: "Connectivity detail" }).closest("section");
    expect(detailPanel).not.toBeNull();
    await waitFor(() => {
      expect(
        within(detailPanel as HTMLElement).getAllByText("SN-1002"),
      ).not.toHaveLength(0);
      expect(within(detailPanel as HTMLElement).getByText("No active endpoint")).toBeInTheDocument();
      expect(
        within(detailPanel as HTMLElement).getAllByText("No recent session"),
      ).not.toHaveLength(0);
    });
  });

  it("renders a bounded loading state while the overview is bootstrapping", async () => {
    const { fetchMock } = createMockApi({ delayedMeters: true });
    vi.stubGlobal("fetch", fetchMock);

    renderConnectivityModuleInShell();

    expect(
      await screen.findByText("Loading connectivity overview..."),
    ).toBeInTheDocument();
    expect(await screen.findByText("Loading live sessions workspace...")).toBeInTheDocument();

    await waitFor(() => {
      expect(screen.getByText("Connectivity-focused meters")).toBeInTheDocument();
    });
  });

  it("renders an empty state when no meters are available", async () => {
    const { fetchMock } = createMockApi({ meterItems: [] });
    vi.stubGlobal("fetch", fetchMock);

    renderConnectivityModuleInShell();

    await waitFor(() => {
      expect(
        screen.getByText("No connectivity overview items available."),
      ).toBeInTheDocument();
      expect(
        screen.getByText("No active connectivity sessions are currently visible in the bounded scope."),
      ).toBeInTheDocument();
      expect(
        screen.getByText("No offline meters or connectivity incidents match the current bounded scope."),
      ).toBeInTheDocument();
    });
  });

  it("renders an empty offline incidents state when every meter has healthy recent connectivity", async () => {
    const { fetchMock } = createMockApi({
      meterItems: [
        {
          id: "meter-1",
          serial_number: "SN-1001",
          utility_meter_number: "UMN-1001",
          manufacturer_code: "GENERIC",
          meter_model_code: "GM-1",
          communication_profile_code: "dlms-primary",
          meter_profile_code: "residential-default",
          current_status: "commissioned",
          last_seen_at: "2099-01-01T11:30:00.000Z",
          is_active: true,
        },
      ],
      sessionsByMeter: {
        "meter-1": [
          {
            id: "session-1",
            started_at: "2026-03-31T11:40:00.000Z",
            ended_at: "2026-03-31T11:41:00.000Z",
            status: "succeeded",
            session_purpose: "connectivity_test",
          },
        ],
      },
      endpointAssignmentsByMeter: {
        "meter-1": [
          {
            id: "assignment-1",
            endpoint_code: "tcp-primary",
            endpoint_display_name: "TCP Primary",
            assignment_status: "active",
            is_primary: true,
          },
        ],
      },
    });
    vi.stubGlobal("fetch", fetchMock);

    renderConnectivityModuleInShell();

    await waitFor(() => {
      expect(
        screen.getByText("No offline meters or connectivity incidents match the current bounded scope."),
      ).toBeInTheDocument();
      expect(
        screen.getByText("No active connectivity sessions are currently visible in the bounded scope."),
      ).toBeInTheDocument();
    });
  });

  it("renders a bounded empty state for an incident filter with no matches", async () => {
    const { fetchMock } = createMockApi({
      meterItems: [
        {
          id: "meter-1",
          serial_number: "SN-1001",
          utility_meter_number: null,
          manufacturer_code: "GENERIC",
          meter_model_code: "GM-1",
          communication_profile_code: "dlms-primary",
          meter_profile_code: "residential-default",
          current_status: "commissioned",
          last_seen_at: null,
          is_active: true,
        },
      ],
      sessionsByMeter: {
        "meter-1": [],
      },
      endpointAssignmentsByMeter: {
        "meter-1": [],
      },
    });
    vi.stubGlobal("fetch", fetchMock);
    const user = userEvent.setup();

    renderConnectivityModuleInShell();

    const incidentsSection = await screen.findByRole("heading", {
      name: "Offline meters / connectivity incidents",
    });
    const incidentsPanel = incidentsSection.closest("section");
    expect(incidentsPanel).not.toBeNull();

    await user.click(within(incidentsPanel as HTMLElement).getByRole("button", { name: "Degraded" }));

    await waitFor(() => {
      expect(
        within(incidentsPanel as HTMLElement).getByText(
          "No degraded incidents match the current bounded scope.",
        ),
      ).toBeInTheDocument();
    });
  });

  it("renders a bounded error state when the meter list fails", async () => {
    const { fetchMock } = createMockApi({
      meterStatus: 503,
      meterDetail: "Connectivity overview unavailable.",
    });
    vi.stubGlobal("fetch", fetchMock);

    renderConnectivityModuleInShell();

    expect(
      await screen.findByText("Connectivity overview unavailable."),
    ).toBeInTheDocument();
  });
});
