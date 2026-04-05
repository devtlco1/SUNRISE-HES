import { render, screen } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { MeterDetailClient } from "./meter-detail-client";

vi.mock("next/navigation", () => ({
  usePathname: () => "/meters/test-id",
}));

function jsonResponse(payload: unknown, status = 200) {
  return new Response(JSON.stringify(payload), {
    status,
    headers: { "Content-Type": "application/json" },
  });
}

const meterId = "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa";

const userPayload = {
  id: "user-1",
  username: "ops.user",
  email: "ops@example.com",
  full_name: "Ops User",
  status: "active",
  is_superuser: true,
};

const meterDetailPayload = {
  id: meterId,
  serial_number: "SN-DETAIL",
  utility_meter_number: "U-1",
  badge_number: null,
  manufacturer_id: "bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb",
  manufacturer_code: "ACME",
  meter_model_id: "cccccccc-cccc-cccc-cccc-cccccccccccc",
  meter_model_code: "M100",
  firmware_version_id: null,
  firmware_version: "1.0",
  communication_profile_id: null,
  communication_profile_code: "CELL-A",
  meter_profile_id: null,
  meter_profile_code: "PROF-1",
  current_status: "active",
  transformer_id: null,
  service_point_id: null,
  notes: null,
  is_active: true,
  installed_at: null,
  commissioned_at: null,
  last_seen_at: "2026-04-05T12:00:00.000Z",
  metadata_json: null,
  status_history: [],
};

describe("MeterDetailClient", () => {
  beforeEach(() => {
    window.localStorage.setItem("sunrise.web.apiBaseUrl", "http://localhost:8000");
  });

  afterEach(() => {
    vi.unstubAllGlobals();
    window.localStorage.clear();
  });

  it("renders meter header and summary tab when APIs succeed", async () => {
    window.localStorage.setItem("sunrise.web.accessToken", "token-1");
    vi.stubGlobal(
      "fetch",
      vi.fn(async (input: RequestInfo | URL) => {
        const u = input.toString();
        if (u.includes("/api/v1/auth/me")) {
          return jsonResponse(userPayload);
        }
        if (u.includes("/readings?")) {
          return jsonResponse({ total: 0, items: [] });
        }
        if (u.includes("/commands/recent")) {
          return jsonResponse({ meter_id: meterId, total: 0, limit: 40, items: [] });
        }
        if (u.includes("/endpoint-assignments")) {
          return jsonResponse({ total: 0, items: [] });
        }
        if (u.includes("/sessions?")) {
          return jsonResponse({ total: 0, items: [] });
        }
        if (u.includes("/audit-logs?")) {
          return jsonResponse({ total: 0, items: [] });
        }
        if (u.includes("/consumer-linkage")) {
          return jsonResponse({
            meter_id: meterId,
            linkage_status: "unlinked",
          });
        }
        if (u.includes("/gis-lite/entities?")) {
          return jsonResponse({ total: 0, items: [] });
        }
        const metersTail = u.includes("/api/v1/meters/")
          ? (u.split("/api/v1/meters/")[1]?.split("?")[0] ?? "")
          : "";
        if (metersTail === meterId) {
          return jsonResponse(meterDetailPayload);
        }
        return jsonResponse({ detail: "unmocked" }, 404);
      }),
    );

    render(<MeterDetailClient meterId={meterId} />);

    expect(await screen.findByRole("heading", { name: "SN-DETAIL" })).toBeInTheDocument();
    expect(screen.getByRole("tab", { name: "Summary" })).toHaveAttribute("aria-selected", "true");
    expect(await screen.findByText("Registry")).toBeInTheDocument();
    expect(screen.getByText("ACME M100")).toBeInTheDocument();
  });
});
