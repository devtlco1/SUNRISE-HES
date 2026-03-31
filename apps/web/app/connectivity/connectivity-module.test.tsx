import { render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { OperationalShell } from "../operational-shell";
import { ConnectivityModule } from "./connectivity-module";

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
      last_seen_at: "2026-03-30T11:00:00.000Z",
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
    expect(await screen.findByRole("heading", { name: "Connectivity overview" })).toBeInTheDocument();

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

    expect(await screen.findByRole("link", { name: /SN-1001/i })).toHaveAttribute(
      "href",
      "/meters/meter-1",
    );
    expect(screen.getByRole("link", { name: /SN-1002/i })).toHaveAttribute(
      "href",
      "/meters/meter-2",
    );
    expect(screen.getByText("TCP Primary")).toBeInTheDocument();
    expect(screen.getByText("succeeded (connectivity_test)")).toBeInTheDocument();
  });

  it("renders a bounded loading state while the overview is bootstrapping", async () => {
    const { fetchMock } = createMockApi({ delayedMeters: true });
    vi.stubGlobal("fetch", fetchMock);

    renderConnectivityModuleInShell();

    expect(
      await screen.findByText("Loading connectivity overview..."),
    ).toBeInTheDocument();

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
