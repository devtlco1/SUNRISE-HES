import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { OperationalShell } from "../operational-shell";
import { SubscribersModule } from "./subscribers-module";

function jsonResponse(payload: unknown, status = 200) {
  return new Response(JSON.stringify(payload), {
    status,
    headers: { "Content-Type": "application/json" },
  });
}

function createMockApi({
  items = [
    {
      id: "consumer-1",
      full_name: "Amina Al Balushi",
      consumer_type: "residential",
      external_ref: "CON-1001",
      national_id: "NID-1001",
      primary_account_number: "ACC-1001",
      account_status_summary: "active",
      active_account_count: 1,
      linked_meter_count: 2,
      primary_service_point_code: "SP-1001",
    },
    {
      id: "consumer-2",
      full_name: "Beacon Bakery LLC",
      consumer_type: "commercial",
      external_ref: "CON-1002",
      national_id: null,
      primary_account_number: null,
      account_status_summary: null,
      active_account_count: 0,
      linked_meter_count: 0,
      primary_service_point_code: null,
    },
  ],
  status = 200,
  detail = "Unable to load subscribers.",
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

    if (url.includes("/api/v1/consumers?")) {
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

function renderSubscribersModuleInShell() {
  render(
    <OperationalShell
      eyebrow="Operational Pages"
      title="Subscribers / Consumers MVP"
      description="Bounded subscribers module"
    >
      {({ authorizedFetch }) => (
        <SubscribersModule authorizedFetch={authorizedFetch} />
      )}
    </OperationalShell>,
  );
}

describe("SubscribersModule", () => {
  beforeEach(() => {
    window.localStorage.setItem("sunrise.web.apiBaseUrl", "http://localhost:8000");
    window.localStorage.setItem("sunrise.web.accessToken", "token-1");
  });

  afterEach(() => {
    vi.unstubAllGlobals();
    window.localStorage.clear();
  });

  it("renders a compact subscriber list inside the shared shell", async () => {
    const { fetchMock } = createMockApi();
    vi.stubGlobal("fetch", fetchMock);

    renderSubscribersModuleInShell();

    expect(
      await screen.findByRole("link", { name: "Subscribers" }),
    ).toBeInTheDocument();
    expect(
      await screen.findByRole("heading", { name: "Subscriber operations center" }),
    ).toBeInTheDocument();
    expect(await screen.findAllByText("Amina Al Balushi")).not.toHaveLength(0);
    expect(screen.getAllByText("Beacon Bakery LLC")).not.toHaveLength(0);
    expect(
      screen.getAllByRole("link", { name: "Open subscriber detail" }),
    ).not.toHaveLength(0);
  });

  it("keeps the bounded navigation path into subscriber detail clear", async () => {
    const { fetchMock } = createMockApi();
    vi.stubGlobal("fetch", fetchMock);
    const user = userEvent.setup();

    renderSubscribersModuleInShell();

    const inspectButtons = await screen.findAllByRole("button", {
      name: "Inspect summary",
    });
    await user.click(inspectButtons[1]);

    const summaryPanel = screen
      .getByRole("heading", { name: "Selected subscriber summary" })
      .closest("section");
    expect(summaryPanel).not.toBeNull();

    expect(
      within(summaryPanel as HTMLElement).getByText("Beacon Bakery LLC"),
    ).toBeInTheDocument();
    expect(
      within(summaryPanel as HTMLElement).getByRole("link", {
        name: "Open subscriber detail",
      }),
    ).toHaveAttribute("href", "/subscribers/consumer-2");
  });

  it("renders an empty state when no subscribers are available", async () => {
    const { fetchMock } = createMockApi({ items: [] });
    vi.stubGlobal("fetch", fetchMock);

    renderSubscribersModuleInShell();

    await waitFor(() => {
      expect(
        screen.getByText("No subscribers available for the current query."),
      ).toBeInTheDocument();
    });
  });

  it("renders a bounded error state when the subscriber list fails", async () => {
    const { fetchMock } = createMockApi({
      status: 503,
      detail: "Subscriber list unavailable.",
    });
    vi.stubGlobal("fetch", fetchMock);

    renderSubscribersModuleInShell();

    expect(
      await screen.findByText("Subscriber list unavailable."),
    ).toBeInTheDocument();
  });
});
