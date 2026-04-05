import { render, screen, within } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { ConnectivityPageClient } from "./connectivity-page-client";

vi.mock("next/navigation", () => ({
  usePathname: () => "/connectivity",
}));

function jsonResponse(payload: unknown, status = 200) {
  return new Response(JSON.stringify(payload), {
    status,
    headers: { "Content-Type": "application/json" },
  });
}

const userPayload = {
  id: "user-1",
  username: "ops.user",
  email: "ops@example.com",
  full_name: "Ops User",
  status: "active",
  is_superuser: true,
};

function gisEntity(overrides: Partial<Record<string, unknown>> = {}) {
  return {
    meter_id: "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa",
    meter_serial_number: "SN-ATTN",
    meter_status: "active",
    meter_last_seen_at: "2020-01-01T00:00:00.000Z",
    service_point_code: "SP-1",
    has_coordinates: true,
    location_presence: "coordinates_available",
    ...overrides,
  };
}

describe("ConnectivityPageClient", () => {
  beforeEach(() => {
    window.localStorage.setItem("sunrise.web.apiBaseUrl", "http://localhost:8000");
  });

  afterEach(() => {
    vi.unstubAllGlobals();
    window.localStorage.clear();
  });

  it("renders connectivity operations layout when APIs succeed", async () => {
    window.localStorage.setItem("sunrise.web.accessToken", "token-1");
    const now = "2026-04-05T15:00:00.000Z";
    vi.stubGlobal(
      "fetch",
      vi.fn(async (input: RequestInfo | URL) => {
        const u = input.toString();
        if (u.includes("/api/v1/auth/me")) {
          return jsonResponse(userPayload);
        }
        if (u.includes("/api/v1/meters?") && u.includes("limit=1")) {
          return jsonResponse({ total: 42, items: [] });
        }
        if (u.includes("/api/v1/gis-lite/entities")) {
          return jsonResponse({
            total: 100,
            items: [
              gisEntity({
                meter_id: "11111111-1111-1111-1111-111111111111",
                meter_serial_number: "SN-ON",
                meter_last_seen_at: now,
              }),
              gisEntity(),
            ],
          });
        }
        if (u.includes("/api/v1/communication-endpoints")) {
          return jsonResponse({ total: 3 });
        }
        return jsonResponse({ detail: "unmocked" }, 404);
      }),
    );

    render(<ConnectivityPageClient />);

    expect(await screen.findByRole("heading", { name: "Connectivity" })).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "Connectivity overview" })).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "Live sessions" })).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "Recent check-ins" })).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "Meters needing attention" })).toBeInTheDocument();

    expect(await screen.findByRole("link", { name: "SN-ON" })).toHaveAttribute(
      "href",
      "/meters/11111111-1111-1111-1111-111111111111",
    );
    expect(screen.getByRole("link", { name: "SN-ATTN" })).toHaveAttribute(
      "href",
      "/meters/aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa",
    );
    const livePanel = screen.getByRole("heading", { name: "Live sessions" }).closest("section");
    expect(livePanel).toBeTruthy();
    expect(within(livePanel!).getByText("Data not available yet.")).toBeInTheDocument();
  });
});
