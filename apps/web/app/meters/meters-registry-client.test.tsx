import { render, screen } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { MetersRegistryClient } from "./meters-registry-client";

vi.mock("next/navigation", () => ({
  usePathname: () => "/meters",
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

describe("MetersRegistryClient", () => {
  beforeEach(() => {
    window.localStorage.setItem("sunrise.web.apiBaseUrl", "http://localhost:8000");
  });

  afterEach(() => {
    vi.unstubAllGlobals();
    window.localStorage.clear();
  });

  it("renders meters table when session and APIs succeed", async () => {
    window.localStorage.setItem("sunrise.web.accessToken", "token-1");
    const now = "2026-04-05T15:00:00.000Z";
    vi.stubGlobal(
      "fetch",
      vi.fn(async (input: RequestInfo | URL) => {
        const u = input.toString();
        if (u.includes("/api/v1/auth/me")) {
          return jsonResponse(userPayload);
        }
        if (u.includes("/api/v1/meters?")) {
          return jsonResponse({
            total: 1,
            items: [
              {
                id: "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa",
                serial_number: "SN-1",
                utility_meter_number: null,
                manufacturer_code: "ACME",
                meter_model_code: "M100",
                firmware_version: "1.0",
                communication_profile_code: "CELL-A",
                meter_profile_code: "PROF-1",
                current_status: "active",
                service_point_id: null,
                transformer_id: null,
                last_seen_at: now,
                is_active: true,
              },
            ],
          });
        }
        if (u.includes("/api/v1/gis-lite/entities")) {
          return jsonResponse({
            total: 1,
            items: [
              {
                meter_id: "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa",
                has_coordinates: true,
              },
            ],
          });
        }
        return jsonResponse({ detail: "unmocked" }, 404);
      }),
    );

    render(<MetersRegistryClient />);

    expect(await screen.findByRole("heading", { name: "Meters" })).toBeInTheDocument();
    expect(await screen.findByText("SN-1")).toBeInTheDocument();
    expect(screen.getByRole("columnheader", { name: "Serial" })).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Meters" })).toBeInTheDocument();
  });
});
