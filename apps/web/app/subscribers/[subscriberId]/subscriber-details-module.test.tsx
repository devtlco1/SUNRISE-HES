import { render, screen, waitFor, within } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { OperationalShell } from "../../operational-shell";
import { SubscriberDetailsModule } from "./subscriber-details-module";

function jsonResponse(payload: unknown, status = 200) {
  return new Response(JSON.stringify(payload), {
    status,
    headers: { "Content-Type": "application/json" },
  });
}

function createMockApi({
  status = 200,
  detailMessage = "Subscriber detail unavailable.",
  payload = {
    id: "consumer-1",
    full_name: "Amina Al Balushi",
    consumer_type: "residential",
    external_ref: "CON-1001",
    national_id: "NID-1001",
    phone_number: "+96890000001",
    email: "amina@example.com",
    account_status_summary: "active",
    active_account_count: 1,
    linked_meter_count: 1,
    current_operational_meter: {
      id: "meter-1",
      serial_number: "SN-1001",
      utility_meter_number: "UMN-1001",
      current_status: "registered",
      account_id: "account-1",
      account_number: "ACC-1001",
      service_point_id: "sp-1",
      service_point_code: "SP-1001",
    },
    accounts: [
      {
        id: "account-1",
        account_number: "ACC-1001",
        status: "active",
        billing_cycle: "monthly",
        service_point_id: "sp-1",
        service_point_code: "SP-1001",
        current_meter_count: 1,
      },
    ],
    linked_meters: [
      {
        id: "meter-1",
        serial_number: "SN-1001",
        utility_meter_number: "UMN-1001",
        current_status: "registered",
        account_id: "account-1",
        account_number: "ACC-1001",
        service_point_id: "sp-1",
        service_point_code: "SP-1001",
      },
    ],
  },
}: {
  status?: number;
  detailMessage?: string;
  payload?: Record<string, unknown>;
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

    if (url.endsWith("/api/v1/consumers/consumer-1")) {
      if (status !== 200) {
        return jsonResponse({ detail: detailMessage }, status);
      }
      return jsonResponse(payload);
    }

    throw new Error(`Unhandled request: ${url}`);
  });

  return { fetchMock };
}

function renderSubscriberDetailsModuleInShell() {
  render(
    <OperationalShell
      eyebrow="Operational Pages"
      title="Subscriber consumer-1"
      description="Bounded subscriber detail"
    >
      {({ authorizedFetch }) => (
        <SubscriberDetailsModule
          subscriberId="consumer-1"
          authorizedFetch={authorizedFetch}
        />
      )}
    </OperationalShell>,
  );
}

describe("SubscriberDetailsModule", () => {
  beforeEach(() => {
    window.localStorage.setItem("sunrise.web.apiBaseUrl", "http://localhost:8000");
    window.localStorage.setItem("sunrise.web.accessToken", "token-1");
  });

  afterEach(() => {
    vi.unstubAllGlobals();
    window.localStorage.clear();
  });

  it("renders the bounded subscriber detail surface with linked accounts and meters", async () => {
    const { fetchMock } = createMockApi();
    vi.stubGlobal("fetch", fetchMock);

    renderSubscriberDetailsModuleInShell();

    expect(await screen.findByRole("heading", { name: "Amina Al Balushi" })).toBeInTheDocument();
    expect(screen.getAllByText("Active")).not.toHaveLength(0);
    const workspacePanel = screen
      .getByRole("heading", { name: "Subscriber workspace" })
      .closest("section");
    expect(workspacePanel).not.toBeNull();
    expect(within(workspacePanel as HTMLElement).getByText("ACC-1001")).toBeInTheDocument();
    expect(within(workspacePanel as HTMLElement).getByText("SP-1001")).toBeInTheDocument();
    const currentMeterPanel = screen
      .getByRole("heading", { name: "Current operational meter" })
      .closest("section");
    expect(currentMeterPanel).not.toBeNull();
    expect(within(currentMeterPanel as HTMLElement).getByText("meter-1")).toBeInTheDocument();
    expect(within(currentMeterPanel as HTMLElement).getByText("ACC-1001")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: /SN-1001/i })).toHaveAttribute(
      "href",
      "/meters/meter-1",
    );
    expect(
      within(currentMeterPanel as HTMLElement).getByRole("link", {
        name: "Open meter detail",
      }),
    ).toHaveAttribute(
      "href",
      "/meters/meter-1",
    );
    expect(
      within(currentMeterPanel as HTMLElement).getByRole("link", {
        name: "Open account detail",
      }),
    ).toHaveAttribute("href", "/accounts/account-1");
    expect(
      within(currentMeterPanel as HTMLElement).getByRole("link", {
        name: "Open service point detail",
      }),
    ).toHaveAttribute("href", "/service-points/sp-1");

    const accountsPanel = screen.getByRole("heading", { name: "Accounts" }).closest("section");
    expect(accountsPanel).not.toBeNull();
    expect(
      within(accountsPanel as HTMLElement).getByRole("link", {
        name: "Open account detail",
      }),
    ).toHaveAttribute("href", "/accounts/account-1");
    expect(
      within(accountsPanel as HTMLElement).getByRole("link", {
        name: "Open service point detail",
      }),
    ).toHaveAttribute("href", "/service-points/sp-1");
  });

  it("renders a bounded loading state while subscriber detail is bootstrapping", async () => {
    const { fetchMock } = createMockApi();
    vi.stubGlobal(
      "fetch",
      vi.fn(async (input: RequestInfo | URL) => {
        const url = input.toString();
        if (url.endsWith("/api/v1/consumers/consumer-1")) {
          await new Promise((resolve) => setTimeout(resolve, 100));
        }
        return fetchMock(input);
      }),
    );

    renderSubscriberDetailsModuleInShell();

    expect(await screen.findByText("Loading subscriber detail...")).toBeInTheDocument();
    expect(await screen.findByRole("heading", { name: "Amina Al Balushi" })).toBeInTheDocument();
  });

  it("renders bounded empty sections when the subscriber has no linked accounts or meters", async () => {
    const { fetchMock } = createMockApi({
      payload: {
        id: "consumer-1",
        full_name: "Amina Al Balushi",
        consumer_type: "residential",
        external_ref: "CON-1001",
        national_id: null,
        phone_number: null,
        email: null,
        account_status_summary: null,
        active_account_count: 0,
        linked_meter_count: 0,
        current_operational_meter: null,
        accounts: [],
        linked_meters: [],
      },
    });
    vi.stubGlobal("fetch", fetchMock);

    renderSubscriberDetailsModuleInShell();

    await waitFor(() => {
      expect(
        screen.getByText("No accounts linked to this subscriber."),
      ).toBeInTheDocument();
    });
    expect(
      screen.getByText("No current operational meter available for this subscriber."),
    ).toBeInTheDocument();
    expect(screen.getByText("No meters linked to this subscriber.")).toBeInTheDocument();
    expect(
      screen.getByText("No current operational meter"),
    ).toBeInTheDocument();
  });

  it("renders a bounded error state when subscriber detail fails", async () => {
    const { fetchMock } = createMockApi({
      status: 404,
      detailMessage: "Consumer not found.",
    });
    vi.stubGlobal("fetch", fetchMock);

    renderSubscriberDetailsModuleInShell();

    expect(await screen.findByText("Consumer not found.")).toBeInTheDocument();
  });
});
