import { render, screen } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { ReadingsPageClient } from "./readings-page-client";

vi.mock("next/navigation", () => ({
  usePathname: () => "/readings",
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

describe("ReadingsPageClient", () => {
  beforeEach(() => {
    window.localStorage.setItem("sunrise.web.apiBaseUrl", "http://localhost:8000");
  });

  afterEach(() => {
    vi.unstubAllGlobals();
    window.localStorage.clear();
  });

  it("renders readings layout when meters and readings APIs succeed", async () => {
    window.localStorage.setItem("sunrise.web.accessToken", "token-1");
    vi.stubGlobal(
      "fetch",
      vi.fn(async (input: RequestInfo | URL) => {
        const u = input.toString();
        if (u.includes("/api/v1/auth/me")) {
          return jsonResponse(userPayload);
        }
        if (u.includes("/api/v1/meters?") && u.includes("limit=")) {
          return jsonResponse({
            total: 1,
            items: [
              {
                id: "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa",
                serial_number: "SN-R1",
              },
            ],
          });
        }
        if (u.includes("/api/v1/meters/") && u.includes("/readings")) {
          return jsonResponse({
            total: 1,
            items: [
              {
                id: "bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb",
                batch_id: "cccccccc-cccc-cccc-cccc-cccccccccccc",
                meter_id: "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa",
                obis_code: "1.0.0.0.0.255",
                reading_type: "register",
                value_numeric: "120.5",
                value_text: null,
                value_timestamp: "2026-04-05T14:00:00.000Z",
                unit: "kWh",
                quality: "good",
                captured_at: "2026-04-05T14:05:00.000Z",
                metadata: null,
              },
            ],
          });
        }
        return jsonResponse({ detail: "unmocked" }, 404);
      }),
    );

    render(<ReadingsPageClient />);

    expect(await screen.findByRole("heading", { name: "Readings" })).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "Readings overview" })).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "Reading registry" })).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "Attention" })).toBeInTheDocument();

    expect(await screen.findByRole("link", { name: "SN-R1" })).toHaveAttribute(
      "href",
      "/meters/aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa",
    );
    expect(screen.getByText("1.0.0.0.0.255")).toBeInTheDocument();
    expect(screen.getByText("No meters need attention.")).toBeInTheDocument();
  });
});
