import { render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { MetersModule } from "./meters-module";
import { OperationalShell } from "../operational-shell";

function jsonResponse(payload: unknown, status = 200) {
  return new Response(JSON.stringify(payload), {
    status,
    headers: { "Content-Type": "application/json" },
  });
}

function createMockApi({
  items = [
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
  status = 200,
  detail = "Unable to load meters.",
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

    if (url.includes("/api/v1/meters?")) {
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

function renderMetersModuleInShell() {
  render(
    <OperationalShell
      eyebrow="Operational Pages"
      title="Meters Module MVP"
      description="Bounded meters module"
    >
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

  it("renders a compact meter list inside the shared shell", async () => {
    const { fetchMock } = createMockApi();
    vi.stubGlobal("fetch", fetchMock);

    renderMetersModuleInShell();

    expect(await screen.findByRole("link", { name: "Meters" })).toBeInTheDocument();
    expect(await screen.findByRole("link", { name: /SN-1001/i })).toHaveAttribute(
      "href",
      "/meters/meter-1",
    );
    expect(screen.getByRole("link", { name: /SN-1002/i })).toHaveAttribute(
      "href",
      "/meters/meter-2",
    );
  });

  it("keeps the navigation path into the existing meter details page clear", async () => {
    const { fetchMock } = createMockApi();
    vi.stubGlobal("fetch", fetchMock);

    renderMetersModuleInShell();

    const meterLink = await screen.findByRole("link", { name: /SN-1001/i });
    expect(meterLink).toHaveAttribute("href", "/meters/meter-1");
  });

  it("renders an empty state when no meters are available", async () => {
    const { fetchMock } = createMockApi({ items: [] });
    vi.stubGlobal("fetch", fetchMock);

    renderMetersModuleInShell();

    await waitFor(() => {
      expect(
        screen.getByText("No meters available for the current query."),
      ).toBeInTheDocument();
    });
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
