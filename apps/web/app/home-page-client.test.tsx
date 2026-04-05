import { render, screen } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { HomePageClient } from "./home-page-client";

vi.mock("next/navigation", () => ({
  usePathname: () => "/",
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

describe("HomePageClient", () => {
  beforeEach(() => {
    window.localStorage.setItem("sunrise.web.apiBaseUrl", "http://localhost:8000");
  });

  afterEach(() => {
    vi.unstubAllGlobals();
    window.localStorage.clear();
  });

  it("shows dashboard KPIs when signed in and APIs respond", async () => {
    window.localStorage.setItem("sunrise.web.accessToken", "token-1");
    const now = "2026-04-05T14:00:00.000Z";
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
            total: 4,
            items: [
              {
                meter_serial_number: "M-1",
                meter_last_seen_at: now,
                has_coordinates: true,
                service_point_code: "SP1",
              },
              {
                meter_serial_number: "M-2",
                meter_last_seen_at: "2026-03-01T12:00:00.000Z",
                has_coordinates: false,
                service_point_code: "SP2",
              },
              {
                meter_serial_number: "M-3",
                meter_last_seen_at: null,
                has_coordinates: false,
                service_point_code: null,
              },
            ],
          });
        }
        if (u.includes("/api/v1/commands/recent")) {
          return jsonResponse({
            total: 2,
            limit: 100,
            items: [
              {
                command_id: "c1",
                command_status: "pending",
                command_template_code: "ODR",
                meter_id: "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa",
                latest_updated_at: now,
                created_at: now,
              },
              {
                command_id: "c2",
                command_status: "failed",
                command_template_code: "RELAY",
                meter_id: "bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb",
                latest_updated_at: now,
                created_at: now,
              },
            ],
          });
        }
        if (u.includes("/api/v1/commands/approvals/pending")) {
          return jsonResponse({ total: 1, limit: 50, items: [] });
        }
        if (u.includes("/api/v1/events/recent")) {
          return jsonResponse({
            total: 10,
            items: [
              {
                id: "e1",
                event_code: "TAMPER",
                event_name: "Tamper",
                severity: "critical",
                event_state: "open",
                occurred_at: now,
                meter_id: "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa",
              },
            ],
          });
        }
        if (u.includes("/api/v1/job-runs")) {
          return jsonResponse({
            total: 3,
            items: [
              {
                id: "j1",
                status: "running",
                scheduled_for: now,
                latest_error_message: null,
                target_meter_id: "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa",
              },
            ],
          });
        }
        if (u.includes("/api/v1/communication-endpoints")) {
          return jsonResponse({ total: 5, items: [] });
        }
        return jsonResponse({ error: "unmocked", url: u }, 404);
      }),
    );

    render(<HomePageClient />);

    expect(await screen.findByRole("heading", { name: "Dashboard" })).toBeInTheDocument();
    expect(await screen.findByText("42")).toBeInTheDocument();
    expect(screen.getByText("Total meters")).toBeInTheDocument();
    expect(screen.getByText(/Fleet status, commands, alarms/)).toBeInTheDocument();
  });
});
