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
    },
    {
      id: "meter-2",
      serial_number: "SN-1002",
      current_status: "registered",
      last_seen_at: null,
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
  ],
  commandsStatus = 200,
  commandsDetail = "Recent commands unavailable.",
  delayedResponses = false,
}: {
  meterItems?: Array<Record<string, unknown>>;
  metersStatus?: number;
  metersDetail?: string;
  recentCommands?: Array<Record<string, unknown>>;
  commandsStatus?: number;
  commandsDetail?: string;
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

    throw new Error(`Unhandled request: ${url}`);
  });

  return { fetchMock };
}

function renderOperationalHomeInShell() {
  render(
    <OperationalShell
      eyebrow="Operational Pages"
      title="Operational Home / Dashboard MVP"
      description="Bounded operational home"
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
      await screen.findByRole("heading", { name: "Operational overview" }),
    ).toBeInTheDocument();

    await waitFor(() => {
      expect(screen.getByText("Meters in current result set")).toBeInTheDocument();
      expect(screen.getByText("Recent commands loaded")).toBeInTheDocument();
      expect(screen.getByText("Operational families in recent activity")).toBeInTheDocument();
    });
  });

  it("keeps clear entry links into meters, commands, and connectivity", async () => {
    const { fetchMock } = createMockApi();
    vi.stubGlobal("fetch", fetchMock);

    renderOperationalHomeInShell();

    expect(await screen.findByRole("link", { name: "Meters" })).toHaveAttribute(
      "href",
      "/meters",
    );
    expect(screen.getByRole("link", { name: "Readings" })).toHaveAttribute(
      "href",
      "/readings",
    );
    expect(screen.getByRole("link", { name: "Commands" })).toHaveAttribute(
      "href",
      "/commands",
    );
    expect(screen.getByRole("link", { name: "Connectivity" })).toHaveAttribute(
      "href",
      "/connectivity",
    );
    expect(screen.getByRole("link", { name: "Subscribers" })).toHaveAttribute(
      "href",
      "/subscribers",
    );
    expect(screen.getByRole("link", { name: "Accounts" })).toHaveAttribute(
      "href",
      "/accounts",
    );
    expect(
      screen.getByRole("link", { name: "Transformers / Substations" }),
    ).toHaveAttribute("href", "/transformers-substations");
  });

  it("renders compact overview blocks and recent activity snippets when data is available", async () => {
    const { fetchMock } = createMockApi();
    vi.stubGlobal("fetch", fetchMock);

    renderOperationalHomeInShell();

    expect(
      await screen.findByText("profile-capture-template"),
    ).toBeInTheDocument();
    expect(screen.getByText("relay-disconnect-template")).toBeInTheDocument();
    expect(screen.getAllByText("completed")).not.toHaveLength(0);
    expect(screen.getByText("disconnect (pending)")).toBeInTheDocument();
  });

  it("renders bounded loading states while the overview is bootstrapping", async () => {
    const { fetchMock } = createMockApi({ delayedResponses: true });
    vi.stubGlobal("fetch", fetchMock);

    renderOperationalHomeInShell();

    expect(
      await screen.findByText("Loading operational overview..."),
    ).toBeInTheDocument();
    expect(
      screen.getByText("Loading recent operational activity..."),
    ).toBeInTheDocument();
  });

  it("renders bounded empty states when overview sources are empty", async () => {
    const { fetchMock } = createMockApi({ meterItems: [], recentCommands: [] });
    vi.stubGlobal("fetch", fetchMock);

    renderOperationalHomeInShell();

    expect(
      await screen.findByText("No recent command activity available."),
    ).toBeInTheDocument();
  });

  it("renders a bounded error state when overview sources fail", async () => {
    const { fetchMock } = createMockApi({
      metersStatus: 503,
      metersDetail: "Meter overview unavailable.",
      commandsStatus: 503,
      commandsDetail: "Recent commands unavailable.",
    });
    vi.stubGlobal("fetch", fetchMock);

    renderOperationalHomeInShell();

    expect(await screen.findByText("Meter overview unavailable.")).toBeInTheDocument();
    expect(await screen.findByText("Recent activity not available.")).toBeInTheDocument();
  });
});
