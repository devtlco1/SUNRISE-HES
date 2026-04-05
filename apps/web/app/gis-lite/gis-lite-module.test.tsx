import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { OperationalShell } from "../operational-shell";
import { GisLiteModule } from "./gis-lite-module";

function jsonResponse(payload: unknown, status = 200) {
  return new Response(JSON.stringify(payload), {
    status,
    headers: { "Content-Type": "application/json" },
  });
}

function createMockApi({
  items = [
    {
      meter_id: "meter-1",
      meter_serial_number: "SN-1001",
      meter_status: "commissioned",
      meter_last_seen_at: "2026-04-01T10:00:00.000Z",
      service_point_id: "service-point-1",
      service_point_code: "SP-1001",
      address_line: "Muscat Block A",
      latitude: 23.588,
      longitude: 58.3829,
      has_coordinates: true,
      subscriber_id: "subscriber-1",
      subscriber_display_name: "Amina Al Balushi",
      subscriber_type: "residential",
      account_id: "account-1",
      account_number: "ACC-1001",
      location_presence: "coordinates_available",
    },
    {
      meter_id: "meter-2",
      meter_serial_number: "SN-1002",
      meter_status: "registered",
      meter_last_seen_at: null,
      service_point_id: "service-point-2",
      service_point_code: "SP-1002",
      address_line: "Nizwa Block B",
      latitude: null,
      longitude: null,
      has_coordinates: false,
      subscriber_id: null,
      subscriber_display_name: null,
      subscriber_type: null,
      account_id: null,
      account_number: null,
      location_presence: "service_point_only",
    },
  ],
  endpointStatus = 200,
  endpointDetail = "GIS Lite unavailable.",
  delayedResponses = false,
}: {
  items?: Array<Record<string, unknown>>;
  endpointStatus?: number;
  endpointDetail?: string;
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

    if (url.includes("/api/v1/gis-lite/entities?")) {
      if (endpointStatus !== 200) {
        return jsonResponse({ detail: endpointDetail }, endpointStatus);
      }
      const parsedUrl = new URL(url);
      const meterIdFilter = parsedUrl.searchParams.get("meter_id");
      const filteredItems = meterIdFilter
        ? items.filter((item) => item.meter_id === meterIdFilter)
        : items;
      return jsonResponse({
        total: filteredItems.length,
        items: filteredItems,
      });
    }

    throw new Error(`Unhandled request: ${url}`);
  });

  return { fetchMock };
}

function renderGisLiteModuleInShell(initialMeterId?: string | null) {
  render(
    <OperationalShell
      eyebrow="Operational Pages"
      title="GIS Lite MVP"
      description="Bounded GIS Lite view"
    >
      {({ authorizedFetch }) => (
        <GisLiteModule authorizedFetch={authorizedFetch} initialMeterId={initialMeterId} />
      )}
    </OperationalShell>,
  );
}

describe("GisLiteModule", () => {
  beforeEach(() => {
    window.localStorage.setItem("sunrise.web.apiBaseUrl", "http://localhost:8000");
    window.localStorage.setItem("sunrise.web.accessToken", "token-1");
  });

  afterEach(() => {
    vi.unstubAllGlobals();
    window.localStorage.clear();
  });

  it("renders bounded spatial and list visibility inside the shared shell", async () => {
    const { fetchMock } = createMockApi();
    vi.stubGlobal("fetch", fetchMock);

    renderGisLiteModuleInShell();

    expect(
      await screen.findByRole("heading", { name: "GIS operations center" }),
    ).toBeInTheDocument();

    await waitFor(() => {
      expect(screen.getByText("With coordinates")).toBeInTheDocument();
      expect(screen.getByText("With linked subscriber")).toBeInTheDocument();
      expect(screen.getByText("With linked account")).toBeInTheDocument();
      expect(screen.getByText("GIS-linked entities")).toBeInTheDocument();
    });
  });

  it("renders a bounded selected GIS entity summary from existing list data", async () => {
    const { fetchMock } = createMockApi();
    vi.stubGlobal("fetch", fetchMock);
    const user = userEvent.setup();

    renderGisLiteModuleInShell();

    const inspectButtons = await screen.findAllByRole("button", {
      name: "Inspect summary",
    });
    await user.click(inspectButtons[1]);

    const summaryPanel = screen
      .getByRole("heading", { name: "Selected spatial entity" })
      .closest("section");
    expect(summaryPanel).not.toBeNull();

    await waitFor(() => {
      expect(within(summaryPanel as HTMLElement).getByText("SN-1002")).toBeInTheDocument();
      expect(
        within(summaryPanel as HTMLElement).getByRole("link", {
          name: "Open meter GIS detail",
        }),
      ).toHaveAttribute("href", "/meters/meter-2?tab=gis");
    });
  });

  it("links GIS items into existing bounded meter and subscriber detail surfaces", async () => {
    const { fetchMock } = createMockApi();
    vi.stubGlobal("fetch", fetchMock);

    renderGisLiteModuleInShell();

    const entitiesPanel = (
      await screen.findByRole("heading", { name: "GIS-linked entities" })
    ).closest("section");
    expect(entitiesPanel).not.toBeNull();

    await waitFor(() => {
      expect(
        within(entitiesPanel as HTMLElement).getAllByRole("link", {
          name: "Open meter GIS detail",
        })[0],
      ).toHaveAttribute("href", "/meters/meter-1?tab=gis");
      expect(
        within(entitiesPanel as HTMLElement).getAllByRole("link", {
          name: "Open service point detail",
        })[0],
      ).toHaveAttribute("href", "/service-points/service-point-1");
      expect(
        within(entitiesPanel as HTMLElement).getByRole("link", {
          name: "Open account detail",
        }),
      ).toHaveAttribute("href", "/accounts/account-1");
      expect(
        within(entitiesPanel as HTMLElement).getByRole("link", {
          name: "Open subscriber detail",
        }),
      ).toHaveAttribute("href", "/subscribers/subscriber-1");
    });
  });

  it("preserves a focused meter handoff and exposes GIS return links", async () => {
    const { fetchMock } = createMockApi();
    vi.stubGlobal("fetch", fetchMock);

    renderGisLiteModuleInShell("meter-1");

    expect(
      await screen.findByText("Focused handoff preserved for SN-1001"),
    ).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Open full GIS Lite surface" })).toHaveAttribute(
      "href",
      "/gis-lite",
    );

    const summaryPanel = screen
      .getByRole("heading", { name: "Selected spatial entity" })
      .closest("section");
    expect(summaryPanel).not.toBeNull();

    await waitFor(() => {
      expect(
        within(summaryPanel as HTMLElement).getByRole("link", {
          name: "Open meter GIS detail",
        }),
      ).toHaveAttribute("href", "/meters/meter-1?tab=gis");
      expect(
        within(summaryPanel as HTMLElement).getByRole("link", {
          name: "Open service point detail",
        }),
      ).toHaveAttribute("href", "/service-points/service-point-1");
      expect(
        within(summaryPanel as HTMLElement).getByRole("link", {
          name: "Open account detail",
        }),
      ).toHaveAttribute("href", "/accounts/account-1");
      expect(
        within(summaryPanel as HTMLElement).getByRole("link", {
          name: "Open subscriber detail",
        }),
      ).toHaveAttribute("href", "/subscribers/subscriber-1");
    });
  });

  it("renders a bounded loading state while GIS Lite is bootstrapping", async () => {
    const { fetchMock } = createMockApi({ delayedResponses: true });
    vi.stubGlobal("fetch", fetchMock);

    renderGisLiteModuleInShell();

    expect(await screen.findByText("Loading GIS Lite overview...")).toBeInTheDocument();
    expect(screen.getByText("Loading GIS Lite markers...")).toBeInTheDocument();
  });

  it("renders a bounded empty state when no GIS-linked entities are available", async () => {
    const { fetchMock } = createMockApi({ items: [] });
    vi.stubGlobal("fetch", fetchMock);

    renderGisLiteModuleInShell();

    const markerPanel = (
      await screen.findByRole("heading", { name: "Marker view" })
    ).closest("section");
    const entitiesPanel = screen
      .getByRole("heading", { name: "GIS-linked entities" })
      .closest("section");
    expect(markerPanel).not.toBeNull();
    expect(entitiesPanel).not.toBeNull();

    await waitFor(() => {
      expect(
        within(markerPanel as HTMLElement).getByText(
          "No coordinates are currently available. Showing list-first GIS Lite visibility only.",
        ),
      ).toBeInTheDocument();
      expect(
        within(entitiesPanel as HTMLElement).getByText(
          "No GIS-linked entities available.",
        ),
      ).toBeInTheDocument();
    });
  });

  it("renders a bounded error state when the GIS Lite endpoint fails", async () => {
    const { fetchMock } = createMockApi({
      endpointStatus: 503,
      endpointDetail: "GIS Lite unavailable.",
    });
    vi.stubGlobal("fetch", fetchMock);

    renderGisLiteModuleInShell();

    expect(await screen.findByText("GIS Lite unavailable.")).toBeInTheDocument();
    expect(await screen.findByText("No GIS-linked entities available.")).toBeInTheDocument();
  });
});
