import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { OperationalShell } from "../operational-shell";
import { AccountsModule } from "./accounts-module";

function jsonResponse(payload: unknown, status = 200) {
  return new Response(JSON.stringify(payload), {
    status,
    headers: { "Content-Type": "application/json" },
  });
}

function createMockApi({
  items = [
    {
      id: "account-1",
      account_number: "ACC-1001",
      status: "active",
      billing_cycle: "monthly",
      subscriber_id: "consumer-1",
      subscriber_display_name: "Amina Al Balushi",
      service_point_id: "service-point-1",
      service_point_code: "SP-1001",
      linked_meter_count: 1,
      primary_meter_serial_number: "SN-1001",
    },
    {
      id: "account-2",
      account_number: "ACC-1002",
      status: "inactive",
      billing_cycle: null,
      subscriber_id: "consumer-2",
      subscriber_display_name: "Beacon Bakery LLC",
      service_point_id: null,
      service_point_code: null,
      linked_meter_count: 0,
      primary_meter_serial_number: null,
    },
  ],
  status = 200,
  detail = "Unable to load accounts.",
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

    if (url.includes("/api/v1/accounts?")) {
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

function renderAccountsModuleInShell() {
  render(
    <OperationalShell
      eyebrow="Operational Pages"
      title="Account Visibility MVP"
      description="Bounded accounts module"
    >
      {({ authorizedFetch }) => <AccountsModule authorizedFetch={authorizedFetch} />}
    </OperationalShell>,
  );
}

describe("AccountsModule", () => {
  beforeEach(() => {
    window.localStorage.setItem("sunrise.web.apiBaseUrl", "http://localhost:8000");
    window.localStorage.setItem("sunrise.web.accessToken", "token-1");
  });

  afterEach(() => {
    vi.unstubAllGlobals();
    window.localStorage.clear();
  });

  it("renders a compact account list inside the shared shell", async () => {
    const { fetchMock } = createMockApi();
    vi.stubGlobal("fetch", fetchMock);

    renderAccountsModuleInShell();

    expect(await screen.findByRole("link", { name: "Accounts" })).toBeInTheDocument();
    expect(
      await screen.findByRole("heading", { name: "Account operations center" }),
    ).toBeInTheDocument();
    expect(await screen.findByText("2 accounts in scope")).toBeInTheDocument();
    expect(await screen.findAllByText("ACC-1001")).not.toHaveLength(0);
    expect(screen.getAllByText("ACC-1002")).not.toHaveLength(0);
    expect(
      screen.getAllByText("Subscriber, service, and meter cues visible").length,
    ).toBeGreaterThan(0);
    expect(screen.getAllByRole("link", { name: "Open account detail" })).not.toHaveLength(0);
    expect(screen.getAllByRole("link", { name: "Open subscriber detail" }).length).toBeGreaterThan(0);
  });

  it("keeps the bounded navigation path into account detail clear", async () => {
    const { fetchMock } = createMockApi();
    vi.stubGlobal("fetch", fetchMock);
    const user = userEvent.setup();

    renderAccountsModuleInShell();

    const inspectButtons = await screen.findAllByRole("button", {
      name: "Inspect summary",
    });
    await user.click(inspectButtons[1]);

    const summaryPanel = screen
      .getByRole("heading", { name: "Selected account summary" })
      .closest("section");
    expect(summaryPanel).not.toBeNull();

    expect(within(summaryPanel as HTMLElement).getAllByText("ACC-1002").length).toBeGreaterThan(0);
    expect(
      within(summaryPanel as HTMLElement).getByRole("link", {
        name: "Open account detail",
      }),
    ).toHaveAttribute("href", "/accounts/account-2");
    expect(
      within(summaryPanel as HTMLElement).getAllByText("Subscriber cue only").length,
    ).toBeGreaterThan(0);
    expect(
      within(summaryPanel as HTMLElement).getByRole("link", {
        name: "Open subscriber detail",
      }),
    ).toHaveAttribute("href", "/subscribers/consumer-2");
    expect(
      within(summaryPanel as HTMLElement).queryByRole("link", {
        name: "Open service point detail",
      }),
    ).not.toBeInTheDocument();
  });

  it("renders an empty state when no accounts are available", async () => {
    const { fetchMock } = createMockApi({ items: [] });
    vi.stubGlobal("fetch", fetchMock);

    renderAccountsModuleInShell();

    await waitFor(() => {
      expect(screen.getByText("No accounts available in the current scope.")).toBeInTheDocument();
    });
  });

  it("renders a bounded error state when the account list fails", async () => {
    const { fetchMock } = createMockApi({
      status: 503,
      detail: "Account list unavailable.",
    });
    vi.stubGlobal("fetch", fetchMock);

    renderAccountsModuleInShell();

    expect(await screen.findByText("Account list unavailable.")).toBeInTheDocument();
  });
});
