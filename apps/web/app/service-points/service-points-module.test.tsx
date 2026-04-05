import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { OperationalShell } from "../operational-shell";
import { ServicePointsModule } from "./service-points-module";

function jsonResponse(payload: unknown, status = 200) {
  return new Response(JSON.stringify(payload), {
    status,
    headers: { "Content-Type": "application/json" },
  });
}

function createMockApi({
  items = [
    {
      id: "service-point-1",
      service_point_code: "SP-1001",
      address_line: "Muttrah Waterfront",
      premises_type: "commercial",
      is_active: true,
      latitude: 23.62,
      longitude: 58.59,
      linked_meter_count: 1,
      linked_subscriber_count: 1,
      linked_account_count: 1,
      primary_meter_serial_number: "SN-1001",
      primary_subscriber_display_name: "Beacon Premises LLC",
    },
    {
      id: "service-point-2",
      service_point_code: "SP-1002",
      address_line: null,
      premises_type: null,
      is_active: false,
      latitude: null,
      longitude: null,
      linked_meter_count: 0,
      linked_subscriber_count: 0,
      linked_account_count: 0,
      primary_meter_serial_number: null,
      primary_subscriber_display_name: null,
    },
  ],
  status = 200,
  detail = "Unable to load service points.",
}: {
  items?: Array<Record<string, unknown>>;
  status?: number;
  detail?: string;
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

    if (url.includes("/api/v1/service-points?")) {
      if (status !== 200) {
        return jsonResponse({ detail }, status);
      }

      return jsonResponse({
        total: items.length,
        items,
      });
    }

    throw new Error(`Unhandled request: ${url}`);
  });

  return { fetchMock };
}

function renderServicePointsModuleInShell() {
  render(
    <OperationalShell
      eyebrow="Operational Pages"
      title="Service Points / Premises MVP"
      description="Bounded service points module"
    >
      {({ authorizedFetch }) => (
        <ServicePointsModule authorizedFetch={authorizedFetch} />
      )}
    </OperationalShell>,
  );
}

describe("ServicePointsModule", () => {
  beforeEach(() => {
    window.localStorage.setItem("sunrise.web.apiBaseUrl", "http://localhost:8000");
    window.localStorage.setItem("sunrise.web.accessToken", "token-1");
  });

  afterEach(() => {
    vi.unstubAllGlobals();
    window.localStorage.clear();
  });

  it("renders a compact service-point list inside the shared shell", async () => {
    const { fetchMock } = createMockApi();
    vi.stubGlobal("fetch", fetchMock);

    renderServicePointsModuleInShell();

    expect(
      await screen.findByRole("link", { name: "Service Points" }),
    ).toBeInTheDocument();
    expect(
      await screen.findByRole("heading", { name: "Service point operations center" }),
    ).toBeInTheDocument();
    expect(
      await screen.findAllByText("SP-1001"),
    ).not.toHaveLength(0);
    expect(screen.getAllByText("SP-1002")).not.toHaveLength(0);
    expect(
      screen.getAllByText("Subscriber and account cues visible").length,
    ).toBeGreaterThan(0);
    expect(screen.getAllByText("Coordinates available").length).toBeGreaterThan(0);
    expect(
      screen.getAllByRole("link", { name: "Open service point detail" }),
    ).not.toHaveLength(0);
    expect(screen.getAllByRole("link", { name: "Open GIS Lite surface" }).length).toBeGreaterThan(0);
  });

  it("keeps the bounded navigation path into service-point detail clear", async () => {
    const { fetchMock } = createMockApi();
    vi.stubGlobal("fetch", fetchMock);
    const user = userEvent.setup();

    renderServicePointsModuleInShell();

    const inspectButtons = await screen.findAllByRole("button", {
      name: "Inspect summary",
    });
    await user.click(inspectButtons[1]);

    const summaryPanel = screen
      .getByRole("heading", { name: "Selected service point summary" })
      .closest("section");
    expect(summaryPanel).not.toBeNull();

    expect(within(summaryPanel as HTMLElement).getAllByText("SP-1002").length).toBeGreaterThan(0);
    expect(
      within(summaryPanel as HTMLElement).getByRole("link", {
        name: "Open service point detail",
      }),
    ).toHaveAttribute("href", "/service-points/service-point-2");
    expect(
      within(summaryPanel as HTMLElement).getAllByText("Location summary incomplete").length,
    ).toBeGreaterThan(0);
    expect(
      within(summaryPanel as HTMLElement).getAllByText("Limited commercial cues").length,
    ).toBeGreaterThan(0);
    expect(
      within(summaryPanel as HTMLElement).getByText("No primary meter"),
    ).toBeInTheDocument();
    expect(
      within(summaryPanel as HTMLElement).getByRole("link", {
        name: "Open GIS Lite surface",
      }),
    ).toHaveAttribute("href", "/gis-lite");
  });

  it("renders an empty state when no service points are available", async () => {
    const { fetchMock } = createMockApi({ items: [] });
    vi.stubGlobal("fetch", fetchMock);

    renderServicePointsModuleInShell();

    await waitFor(() => {
      expect(
        screen.getByText("No service points available for the current query."),
      ).toBeInTheDocument();
    });
  });

  it("renders a bounded error state when the service-point list fails", async () => {
    const { fetchMock } = createMockApi({
      status: 503,
      detail: "Service point list unavailable.",
    });
    vi.stubGlobal("fetch", fetchMock);

    renderServicePointsModuleInShell();

    expect(
      await screen.findByText("Service point list unavailable."),
    ).toBeInTheDocument();
  });
});
