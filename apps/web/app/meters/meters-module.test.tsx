import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { OperationalShell } from "../operational-shell";
import { MetersModule } from "./meters-module";

function jsonResponse(payload: unknown, status = 200) {
  return new Response(JSON.stringify(payload), {
    status,
    headers: { "Content-Type": "application/json" },
  });
}

function createMockApi({
  status = 200,
  detail = "Unable to load meters.",
  items = [
    {
      id: "meter-1",
      serial_number: "SN-1001",
      utility_meter_number: "UMN-1001",
      badge_number: "BDG-1001",
      manufacturer_code: "GENERIC",
      meter_model_code: "GM-1",
      firmware_version: "FW-1.0.0",
      communication_profile_code: "gprs-primary",
      meter_profile_code: "dlms-main",
      current_status: "active",
      transformer_id: "TR-01",
      service_point_id: "sp-1",
      is_active: true,
      last_seen_at: "2026-03-30T11:00:00.000Z",
    },
    {
      id: "meter-2",
      serial_number: "SN-1002",
      utility_meter_number: "UMN-1002",
      badge_number: null,
      manufacturer_code: "GENERIC",
      meter_model_code: "GM-2",
      firmware_version: null,
      communication_profile_code: "rf-primary",
      meter_profile_code: "iec-main",
      current_status: "maintenance",
      transformer_id: null,
      service_point_id: null,
      is_active: true,
      last_seen_at: null,
    },
  ],
}: {
  status?: number;
  detail?: string;
  items?: Array<Record<string, unknown>>;
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

    if (url.includes("/api/v1/communication-profiles")) {
      return jsonResponse({
        total: 2,
        items: [
          { code: "gprs-primary", name: "GPRS", transport_type: "cellular" },
          { code: "rf-primary", name: "RF", transport_type: "radio_frequency" },
        ],
      });
    }

    if (url.includes("/api/v1/meter-profiles")) {
      return jsonResponse({
        total: 2,
        items: [
          { code: "dlms-main", protocol_family: "dlms_cosem" },
          { code: "iec-main", protocol_family: "iec_62056" },
        ],
      });
    }

    if (url.includes("/api/v1/meters?")) {
      if (status !== 200) {
        return jsonResponse({ detail }, status);
      }

      const parsedUrl = new URL(url);
      const search = parsedUrl.searchParams.get("search")?.trim().toLowerCase() ?? "";
      const filteredItems =
        search.length === 0
          ? items
          : items.filter((item) =>
              [item.id, item.serial_number, item.utility_meter_number, item.badge_number]
                .filter(Boolean)
                .some((value) => String(value).toLowerCase().includes(search)),
            );

      return jsonResponse({
        total: filteredItems.length,
        items: filteredItems,
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
            service_point_code: meterId === "meter-1" ? "SP-1001" : null,
            has_coordinates: meterId === "meter-1",
            subscriber_display_name: meterId === "meter-1" ? "Amina Al Balushi" : null,
            account_number: meterId === "meter-1" ? "ACC-1001" : null,
            location_presence: meterId === "meter-1" ? "coordinates_available" : "unlinked",
          },
        ],
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

    const commandsMatch = url.match(/\/api\/v1\/meters\/([^/]+)\/commands\/recent\?limit=1$/);
    if (commandsMatch) {
      const meterId = commandsMatch[1];
      return jsonResponse({
        meter_id: meterId,
        total: meterId === "meter-1" ? 1 : 0,
        items:
          meterId === "meter-1"
            ? [
                {
                  command_id: "command-1",
                  command_status: "queued",
                  command_template_code: "profile-capture-template",
                  latest_updated_at: "2026-03-30T11:10:00.000Z",
                },
              ]
            : [],
      });
    }

    const eventsMatch = url.match(/\/api\/v1\/meters\/([^/]+)\/ingested-events\?limit=1$/);
    if (eventsMatch) {
      const meterId = eventsMatch[1];
      return jsonResponse({
        total: meterId === "meter-2" ? 1 : 0,
        items:
          meterId === "meter-2"
            ? [
                {
                  id: "event-2",
                  severity: "critical",
                  event_state: "new",
                  event_name: "Tamper detected",
                  occurred_at: "2026-03-30T11:10:00.000Z",
                },
              ]
            : [],
      });
    }

    throw new Error(`Unhandled request: ${url}`);
  });

  return { fetchMock };
}

function renderMetersModuleInShell() {
  render(
    <OperationalShell eyebrow="Operations" title="Meters" description="Bounded meters module">
      {({ authorizedFetch }) => <MetersModule authorizedFetch={authorizedFetch} />}
    </OperationalShell>,
  );
}

describe("MetersModule", () => {
  beforeEach(() => {
    window.localStorage.setItem("sunrise.web.apiBaseUrl", "http://localhost:8000");
    window.localStorage.setItem("sunrise.web.accessToken", "token-1");
  });

  afterEach(() => {
    vi.unstubAllGlobals();
    window.localStorage.clear();
  });

  it("renders the enterprise registry table inside the shared shell", async () => {
    const { fetchMock } = createMockApi();
    vi.stubGlobal("fetch", fetchMock);

    renderMetersModuleInShell();

    expect(await screen.findByText("Meter registry")).toBeInTheDocument();
    expect(await screen.findByText("Amina Al Balushi")).toBeInTheDocument();
    expect(screen.getByText("Inventory result")).toBeInTheDocument();
    expect(screen.getAllByRole("link", { name: "Open detail" }).length).toBeGreaterThan(0);
    expect(screen.getAllByText("SN-1001").length).toBeGreaterThan(0);
    expect(screen.getAllByText("SN-1002").length).toBeGreaterThan(0);
    expect(screen.getAllByText("Mapped").length).toBeGreaterThan(0);
    expect(screen.getByRole("link", { name: "Import meters" })).toHaveAttribute(
      "href",
      "/meters/import",
    );
  });

  it("supports bounded multi-meter selection for bulk commands", async () => {
    const { fetchMock } = createMockApi();
    vi.stubGlobal("fetch", fetchMock);
    const user = userEvent.setup();

    renderMetersModuleInShell();

    expect(await screen.findByText("SN-1001")).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Select visible" }));

    await waitFor(() => {
      expect(screen.getByText("2 selected")).toBeInTheDocument();
    });
    expect(screen.getByRole("link", { name: "Open bulk commands" })).toHaveAttribute(
      "href",
      "/commands?meterIds=meter-1%2Cmeter-2&meterScopeSource=meter_registry_current_page",
    );
  });

  it("applies server-side search to the registry query", async () => {
    const { fetchMock } = createMockApi();
    vi.stubGlobal("fetch", fetchMock);
    const user = userEvent.setup();

    renderMetersModuleInShell();

    expect(await screen.findByText("SN-1001")).toBeInTheDocument();
    await user.type(screen.getByRole("textbox", { name: "Search" }), "SN-1001");
    await user.click(screen.getByRole("button", { name: "Apply search" }));

    await waitFor(() => {
      expect(screen.getByText("1 rows visible")).toBeInTheDocument();
    });
    expect(screen.getByText("SN-1001")).toBeInTheDocument();
    expect(screen.queryByText("SN-1002")).not.toBeInTheDocument();
  });

  it("renders a bounded error state when the meter list fails", async () => {
    const { fetchMock } = createMockApi({
      status: 503,
      detail: "Meter list unavailable.",
    });
    vi.stubGlobal("fetch", fetchMock);

    renderMetersModuleInShell();

    expect(await screen.findByText("Meter list unavailable.")).toBeInTheDocument();
  });
});
