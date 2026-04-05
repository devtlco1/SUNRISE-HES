import { render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { OperationalHomeModule } from "./operational-home-module";
import { OperationalShell } from "./operational-shell";

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
      current_status: "commissioned",
      last_seen_at: "2026-03-30T11:00:00.000Z",
      is_active: true,
    },
    {
      id: "meter-2",
      serial_number: "SN-1002",
      current_status: "registered",
      last_seen_at: null,
      is_active: true,
    },
    {
      id: "meter-3",
      serial_number: "SN-1003",
      current_status: "commissioned",
      last_seen_at: "2026-03-27T08:00:00.000Z",
      is_active: true,
    },
    {
      id: "meter-4",
      serial_number: "SN-1004",
      current_status: "commissioned",
      last_seen_at: "2026-03-30T10:30:00.000Z",
      is_active: false,
    },
  ],
  metersStatus = 200,
  metersDetail = "Meter overview unavailable.",
  recentCommands = [
    {
      command_id: "command-1",
      command_family: "profile_capture",
      command_status: "completed",
      meter_id: "meter-1",
      command_template_code: "profile-capture-template",
      family_specific_outcome_summary: {
        terminal_status_category: "completed",
      },
      latest_updated_at: "2026-03-30T11:05:00.000Z",
    },
    {
      command_id: "command-2",
      command_family: "relay_control",
      command_status: "queued",
      meter_id: "meter-2",
      command_template_code: "relay-disconnect-template",
      family_specific_outcome_summary: {
        relay_control_operation: "disconnect",
        relay_control_execution_outcome: "pending",
      },
      latest_updated_at: "2026-03-30T11:06:00.000Z",
    },
    {
      command_id: "command-3",
      command_family: "on_demand_read",
      command_status: "failed",
      meter_id: "meter-4",
      command_template_code: "on-demand-read-template",
      family_specific_outcome_summary: {
        on_demand_read_operation: "read_billing_snapshot",
        snapshot_type: "billing",
        on_demand_read_execution_outcome: "pending",
      },
      latest_updated_at: "2026-03-30T11:10:00.000Z",
    },
  ],
  commandsStatus = 200,
  commandsDetail = "Recent commands unavailable.",
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
    {
      command_id: "pending-2",
      command_family: "on_demand_read",
      command_status: "pending",
      meter_id: "meter-4",
      command_template_code: "on-demand-read-template",
      family_specific_outcome_summary: {
        on_demand_read_operation: "read_billing_snapshot",
        snapshot_type: "billing",
        on_demand_read_execution_outcome: "pending",
      },
      latest_updated_at: "2026-03-30T11:12:00.000Z",
    },
  ],
  pendingApprovalsStatus = 200,
  pendingApprovalsDetail = "Pending approvals unavailable.",
  sessionsByMeterId = {
    "meter-1": [
      {
        id: "session-1",
        started_at: "2026-03-30T10:50:00.000Z",
        ended_at: "2026-03-30T11:00:00.000Z",
        status: "succeeded",
        session_purpose: "scheduled_poll",
      },
    ],
    "meter-2": [],
    "meter-3": [
      {
        id: "session-3",
        started_at: "2026-03-27T07:30:00.000Z",
        ended_at: "2026-03-27T07:40:00.000Z",
        status: "succeeded",
        session_purpose: "scheduled_poll",
      },
    ],
    "meter-4": [
      {
        id: "session-4",
        started_at: "2026-03-30T10:00:00.000Z",
        ended_at: "2026-03-30T10:05:00.000Z",
        status: "failed",
        session_purpose: "on_demand_check",
      },
    ],
  } as Record<string, Array<Record<string, unknown>>>,
  readingsByMeterId = {
    "meter-1": [
      {
        id: "reading-1",
        captured_at: "2026-03-30T11:05:00.000Z",
      },
    ],
    "meter-2": [],
    "meter-3": [
      {
        id: "reading-3",
        captured_at: "2026-03-30T11:00:00.000Z",
      },
    ],
    "meter-4": [
      {
        id: "reading-4",
        captured_at: "2026-03-30T11:00:00.000Z",
      },
    ],
  } as Record<string, Array<Record<string, unknown>>>,
  snapshotsByMeterId = {
    "meter-1": [
      {
        id: "snapshot-1",
        snapshot_type: "billing",
      },
    ],
    "meter-2": [],
    "meter-3": [
      {
        id: "snapshot-3",
        snapshot_type: "billing",
      },
    ],
    "meter-4": [],
  } as Record<string, Array<Record<string, unknown>>>,
  channelsByMeterId = {
    "meter-1": [
      {
        id: "channel-1",
        channel_code: "kwh-delivered",
      },
    ],
    "meter-2": [],
    "meter-3": [
      {
        id: "channel-3",
        channel_code: "kwh-delivered",
      },
    ],
    "meter-4": [
      {
        id: "channel-4",
        channel_code: "kwh-delivered",
      },
    ],
  } as Record<string, Array<Record<string, unknown>>>,
  intervalsByMeterId = {
    "meter-1": [
      {
        id: "interval-1",
        channel_id: "channel-1",
        interval_start: "2026-03-30T10:00:00.000Z",
        interval_end: "2026-03-30T11:00:00.000Z",
        value_numeric: "12.4",
        quality: "actual",
      },
    ],
    "meter-2": [],
    "meter-3": [
      {
        id: "interval-3",
        channel_id: "channel-3",
        interval_start: "2026-03-29T09:00:00.000Z",
        interval_end: "2026-03-29T10:00:00.000Z",
        value_numeric: "8.5",
        quality: "suspect",
      },
    ],
    "meter-4": [
      {
        id: "interval-4-new",
        channel_id: "channel-4",
        interval_start: "2026-03-30T10:30:00.000Z",
        interval_end: "2026-03-30T10:45:00.000Z",
        value_numeric: null,
        quality: "missing",
      },
      {
        id: "interval-4-old",
        channel_id: "channel-4",
        interval_start: "2026-03-30T10:00:00.000Z",
        interval_end: "2026-03-30T10:15:00.000Z",
        value_numeric: "4.0",
        quality: "actual",
      },
    ],
  } as Record<string, Array<Record<string, unknown>>>,
  delayedResponses = false,
}: {
  meterItems?: Array<Record<string, unknown>>;
  metersStatus?: number;
  metersDetail?: string;
  recentCommands?: Array<Record<string, unknown>>;
  commandsStatus?: number;
  commandsDetail?: string;
  pendingApprovals?: Array<Record<string, unknown>>;
  pendingApprovalsStatus?: number;
  pendingApprovalsDetail?: string;
  sessionsByMeterId?: Record<string, Array<Record<string, unknown>>>;
  readingsByMeterId?: Record<string, Array<Record<string, unknown>>>;
  snapshotsByMeterId?: Record<string, Array<Record<string, unknown>>>;
  channelsByMeterId?: Record<string, Array<Record<string, unknown>>>;
  intervalsByMeterId?: Record<string, Array<Record<string, unknown>>>;
  delayedResponses?: boolean;
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

    if (delayedResponses) {
      await new Promise((resolve) => window.setTimeout(resolve, 100));
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
      if (pendingApprovalsStatus !== 200) {
        return jsonResponse({ detail: pendingApprovalsDetail }, pendingApprovalsStatus);
      }

      return jsonResponse({
        total: pendingApprovals.length,
        limit: 20,
        family_filter: null,
        items: pendingApprovals,
      });
    }

    if (url.includes("/api/v1/commands/recent?")) {
      if (commandsStatus !== 200) {
        return jsonResponse({ detail: commandsDetail }, commandsStatus);
      }

      return jsonResponse({
        total: recentCommands.length,
        limit: 5,
        family_filter: null,
        items: recentCommands,
      });
    }

    const sessionsMatch = url.match(/\/api\/v1\/meters\/([^/]+)\/sessions\?limit=1$/);
    if (sessionsMatch) {
      const meterId = sessionsMatch[1];
      const items = sessionsByMeterId[meterId] ?? [];
      return jsonResponse({
        total: items.length,
        items,
      });
    }

    const readingsMatch = url.match(/\/api\/v1\/meters\/([^/]+)\/readings\?limit=10$/);
    if (readingsMatch) {
      const meterId = readingsMatch[1];
      const items = readingsByMeterId[meterId] ?? [];
      return jsonResponse({
        total: items.length,
        items,
      });
    }

    const snapshotsMatch = url.match(/\/api\/v1\/meters\/([^/]+)\/register-snapshots\?limit=25$/);
    if (snapshotsMatch) {
      const meterId = snapshotsMatch[1];
      const items = snapshotsByMeterId[meterId] ?? [];
      return jsonResponse({
        total: items.length,
        items,
      });
    }

    const channelsMatch = url.match(/\/api\/v1\/meters\/([^/]+)\/load-profile-channels$/);
    if (channelsMatch) {
      const meterId = channelsMatch[1];
      const items = channelsByMeterId[meterId] ?? [];
      return jsonResponse({
        total: items.length,
        items,
      });
    }

    const intervalsMatch = url.match(/\/api\/v1\/meters\/([^/]+)\/load-profile-intervals\?limit=96$/);
    if (intervalsMatch) {
      const meterId = intervalsMatch[1];
      const items = intervalsByMeterId[meterId] ?? [];
      return jsonResponse({
        total: items.length,
        items,
      });
    }

    throw new Error(`Unhandled request: ${url}`);
  });

  return { fetchMock };
}

function renderOperationalHomeInShell() {
  render(
    <OperationalShell
      eyebrow="Dashboard Foundation"
      title="Dashboard foundation test"
      description="Bounded operational home"
      navigationVariant="dashboard-home"
    >
      {({ authorizedFetch }) => (
        <OperationalHomeModule authorizedFetch={authorizedFetch} />
      )}
    </OperationalShell>,
  );
}

describe("OperationalHomeModule", () => {
  beforeEach(() => {
    window.localStorage.setItem("sunrise.web.apiBaseUrl", "http://localhost:8000");
    window.localStorage.setItem("sunrise.web.accessToken", "token-1");
  });

  afterEach(() => {
    vi.unstubAllGlobals();
    window.localStorage.clear();
  });

  it("renders the operational home dashboard inside the shared shell", async () => {
    const { fetchMock } = createMockApi();
    vi.stubGlobal("fetch", fetchMock);

    renderOperationalHomeInShell();

    expect(
      await screen.findByRole("link", { name: "Dashboard home" }),
    ).toBeInTheDocument();
    expect(
      await screen.findByRole("heading", { name: "Operations control center" }),
    ).toBeInTheDocument();

    await waitFor(() => {
      expect(screen.getByText("One complete dashboard experience before broader page migration.")).toBeInTheDocument();
      expect(screen.getAllByText("Pending approvals").length).toBeGreaterThan(0);
      expect(screen.getByText("Open validation issues")).toBeInTheDocument();
      expect(screen.getByText("Open recovery issues")).toBeInTheDocument();
      expect(screen.getByRole("heading", { name: "Workspace launchpads" })).toBeInTheDocument();
      expect(screen.getByRole("heading", { name: "Queues and live activity" })).toBeInTheDocument();
      expect(screen.getByRole("heading", { name: "Primary operational lanes" })).toBeInTheDocument();
    });
  });

  it("keeps clear drill-down links into the stable operational surfaces", async () => {
    const { fetchMock } = createMockApi();
    vi.stubGlobal("fetch", fetchMock);

    renderOperationalHomeInShell();

    expect(
      (await screen.findAllByRole("link", { name: "Open meters" })).some(
        (link) => link.getAttribute("href") === "/meters",
      ),
    ).toBe(true);
    expect(await screen.findByRole("link", { name: "Open subscribers" })).toHaveAttribute(
      "href",
      "/subscribers",
    );
    expect(await screen.findByRole("link", { name: "Open accounts" })).toHaveAttribute(
      "href",
      "/accounts",
    );
    expect(await screen.findByRole("link", { name: "Open service points" })).toHaveAttribute(
      "href",
      "/service-points",
    );
    expect(await screen.findByRole("link", { name: "Open GIS Lite" })).toHaveAttribute(
      "href",
      "/gis-lite",
    );
    expect(
      await screen.findByRole("link", { name: "Open transformers / substations" }),
    ).toHaveAttribute("href", "/transformers-substations");
    expect(
      (await screen.findAllByRole("link", { name: "Open readings" })).some(
        (link) => link.getAttribute("href") === "/readings",
      ),
    ).toBe(true);
    expect(
      (await screen.findAllByRole("link", { name: "Open commands" })).some(
        (link) => link.getAttribute("href") === "/commands",
      ),
    ).toBe(true);
    expect(
      (await screen.findAllByRole("link", { name: "Open connectivity" })).some(
        (link) => link.getAttribute("href") === "/connectivity",
      ),
    ).toBe(true);
    expect(
      (await screen.findAllByRole("link", { name: "Open monitoring center" })).some(
        (link) =>
          link.getAttribute("href") ===
          "/jobs-events-alerts?attentionContext=dashboard_attention_queue&activityFilter=attention",
      ),
    ).toBe(true);
  });

  it("renders KPI cards, operational summary panels, and recent activity snippets when data is available", async () => {
    const { fetchMock } = createMockApi();
    vi.stubGlobal("fetch", fetchMock);

    renderOperationalHomeInShell();

    expect(await screen.findByText("profile-capture-template")).toBeInTheDocument();
    expect(screen.getByText("relay-disconnect-template")).toBeInTheDocument();
    expect(screen.getByText("on-demand-read-template")).toBeInTheDocument();
    expect(
      screen.getByText("3 active inventory items visible in the current bounded meter result set."),
    ).toBeInTheDocument();
    expect(
      screen.getByText(
        "Bulk command requests currently waiting in the stable approvals queue.",
      ),
    ).toBeInTheDocument();
    expect(
      screen.getByText(
        "First fully rebuilt dashboard home for the new admin-style direction. It keeps the product truthful to current routes while establishing the shell, hierarchy, and launch rhythm later pages will inherit.",
      ),
    ).toBeInTheDocument();
    expect(screen.getAllByText(/validation issues/).length).toBeGreaterThan(0);
    expect(
      screen.getAllByRole("link", { name: "Open readings" }).some((link) => link.getAttribute("href") === "/readings"),
    ).toBe(true);
    expect(screen.getAllByText("Pending approvals").length).toBeGreaterThan(0);
    expect(screen.getByText("Validation issues")).toBeInTheDocument();
    expect(screen.getByText("Recovery issues")).toBeInTheDocument();
    expect(screen.getByText("Problem command activity")).toBeInTheDocument();
    expect(screen.getByText("1 attention")).toBeInTheDocument();
    expect(screen.getByText("disconnect (pending)")).toBeInTheDocument();
    expect(screen.getByText("read_billing_snapshot billing (pending)")).toBeInTheDocument();
  });

  it("renders bounded loading states while the overview is bootstrapping", async () => {
    const { fetchMock } = createMockApi({ delayedResponses: true });
    vi.stubGlobal("fetch", fetchMock);

    renderOperationalHomeInShell();

    expect(await screen.findByText("Loading operations dashboard...")).toBeInTheDocument();
    expect(screen.getByText("Loading operator attention handoff...")).toBeInTheDocument();
    expect(screen.getByText("Loading recent command activity...")).toBeInTheDocument();
  });

  it("renders bounded empty states when overview sources are empty", async () => {
    const { fetchMock } = createMockApi({
      meterItems: [],
      recentCommands: [],
      pendingApprovals: [],
      sessionsByMeterId: {},
      readingsByMeterId: {},
      snapshotsByMeterId: {},
      channelsByMeterId: {},
      intervalsByMeterId: {},
    });
    vi.stubGlobal("fetch", fetchMock);

    renderOperationalHomeInShell();

    expect(await screen.findByText("No recent command activity.")).toBeInTheDocument();
    expect(
      screen.getByText(
        "No bounded operator attention items are currently derived from the stable dashboard signals.",
      ),
    ).toBeInTheDocument();
    expect(
      screen.getByText(
        "No recent command activity is currently visible, but the stable drill-down surfaces remain available from the launch areas above.",
      ),
    ).toBeInTheDocument();
  });

  it("renders a bounded error state when overview sources fail", async () => {
    const { fetchMock } = createMockApi({
      metersStatus: 503,
      metersDetail: "Meter overview unavailable.",
      commandsStatus: 503,
      commandsDetail: "Recent commands unavailable.",
      pendingApprovalsStatus: 503,
      pendingApprovalsDetail: "Pending approvals unavailable.",
    });
    vi.stubGlobal("fetch", fetchMock);

    renderOperationalHomeInShell();

    expect(await screen.findByText("Meter overview unavailable.")).toBeInTheDocument();
    expect((await screen.findAllByText("Recent command activity not available.")).length).toBeGreaterThan(0);
    expect(screen.getAllByText("Not available").length).toBeGreaterThan(0);
  });
});
