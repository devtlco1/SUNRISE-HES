import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
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
    expect(screen.getByText("Meters in current result")).toBeInTheDocument();
    expect(screen.getByText("Active inventory items")).toBeInTheDocument();
    expect(await screen.findByText("SN-1001")).toBeInTheDocument();
    expect(screen.getByText("SN-1002")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Open bulk commands" })).toBeDisabled();
  });

  it("keeps the navigation path into the existing meter details page clear", async () => {
    const { fetchMock } = createMockApi();
    vi.stubGlobal("fetch", fetchMock);

    renderMetersModuleInShell();

    const meterRows = await screen.findAllByText(/SN-100/i);
    expect(meterRows).toHaveLength(2);
    const firstMeterCard = meterRows[0]?.closest("article");
    expect(firstMeterCard).not.toBeNull();
    expect(
      within(firstMeterCard as HTMLElement).getByRole("link", { name: "Open meter detail" }),
    ).toHaveAttribute("href", "/meters/meter-1");
  });

  it("supports bounded multi-meter selection and hands it off into bulk commands", async () => {
    const { fetchMock } = createMockApi();
    vi.stubGlobal("fetch", fetchMock);
    const user = userEvent.setup();

    renderMetersModuleInShell();

    expect(await screen.findByText("SN-1001")).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Select visible" }));

    await waitFor(() => {
      expect(screen.getByText("2 selected meters")).toBeInTheDocument();
      expect(screen.getAllByText("SN-1001").length).toBeGreaterThan(0);
      expect(screen.getAllByText("SN-1002").length).toBeGreaterThan(0);
    });

    expect(screen.getByRole("link", { name: "Open bulk commands" })).toHaveAttribute(
      "href",
      "/commands?meterIds=meter-1%2Cmeter-2",
    );
  });

  it("lets operators remove one meter from the bounded bulk handoff scope", async () => {
    const { fetchMock } = createMockApi();
    vi.stubGlobal("fetch", fetchMock);
    const user = userEvent.setup();

    renderMetersModuleInShell();

    const meterRows = await screen.findAllByText(/SN-100/i);
    const firstMeterCard = meterRows[0]?.closest("article");
    const secondMeterCard = meterRows[1]?.closest("article");
    expect(firstMeterCard).not.toBeNull();
    expect(secondMeterCard).not.toBeNull();

    await user.click(
      within(firstMeterCard as HTMLElement).getByRole("checkbox", {
        name: "Include in bulk target scope",
      }),
    );
    await user.click(
      within(secondMeterCard as HTMLElement).getByRole("checkbox", {
        name: "Include in bulk target scope",
      }),
    );

    expect(screen.getByRole("link", { name: "Open bulk commands" })).toHaveAttribute(
      "href",
      "/commands?meterIds=meter-1%2Cmeter-2",
    );

    await user.click(
      within(firstMeterCard as HTMLElement).getByRole("checkbox", {
        name: "Include in bulk target scope",
      }),
    );

    await waitFor(() => {
      expect(screen.getByText("1 selected meter")).toBeInTheDocument();
    });
    expect(screen.getByRole("link", { name: "Open bulk commands" })).toHaveAttribute(
      "href",
      "/commands?meterIds=meter-2",
    );
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
