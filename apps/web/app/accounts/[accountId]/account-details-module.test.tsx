import { render, screen, waitFor, within } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { OperationalShell } from "../../operational-shell";
import { AccountDetailsModule } from "./account-details-module";

function jsonResponse(payload: unknown, status = 200) {
  return new Response(JSON.stringify(payload), {
    status,
    headers: { "Content-Type": "application/json" },
  });
}

function createMockApi({
  status = 200,
  detailMessage = "Account detail unavailable.",
  payload = {
    id: "account-1",
    account_number: "ACC-1001",
    status: "active",
    billing_cycle: "monthly",
    subscriber: {
      id: "consumer-1",
      full_name: "Amina Al Balushi",
      consumer_type: "residential",
      external_ref: "CON-1001",
    },
    service_point: {
      id: "service-point-1",
      service_point_code: "SP-1001",
      address_line: "Muscat Block A",
      premises_type: "residential",
    },
    linked_meter_count: 1,
    linked_meters: [
      {
        id: "meter-1",
        serial_number: "SN-1001",
        utility_meter_number: "UMN-1001",
        current_status: "registered",
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

    if (url.endsWith("/api/v1/accounts/account-1")) {
      if (status !== 200) {
        return jsonResponse({ detail: detailMessage }, status);
      }
      return jsonResponse(payload);
    }

    throw new Error(`Unhandled request: ${url}`);
  });

  return { fetchMock };
}

function renderAccountDetailsModuleInShell() {
  render(
    <OperationalShell
      eyebrow="Operational Pages"
      title="Account account-1"
      description="Bounded account detail"
    >
      {({ authorizedFetch }) => (
        <AccountDetailsModule accountId="account-1" authorizedFetch={authorizedFetch} />
      )}
    </OperationalShell>,
  );
}

describe("AccountDetailsModule", () => {
  beforeEach(() => {
    window.localStorage.setItem("sunrise.web.apiBaseUrl", "http://localhost:8000");
    window.localStorage.setItem("sunrise.web.accessToken", "token-1");
  });

  afterEach(() => {
    vi.unstubAllGlobals();
    window.localStorage.clear();
  });

  it("renders the bounded account detail surface with linked subscriber, service point, and meters", async () => {
    const { fetchMock } = createMockApi();
    vi.stubGlobal("fetch", fetchMock);

    renderAccountDetailsModuleInShell();

    expect(await screen.findAllByText("ACC-1001")).not.toHaveLength(0);
    expect(screen.getAllByText("Active")).not.toHaveLength(0);
    const workspacePanel = screen
      .getByRole("heading", { name: "Account workspace" })
      .closest("section");
    expect(workspacePanel).not.toBeNull();
    expect(within(workspacePanel as HTMLElement).getByText("Amina Al Balushi")).toBeInTheDocument();
    expect(
      within(workspacePanel as HTMLElement).getByText("Residential • CON-1001"),
    ).toBeInTheDocument();
    expect(
      within(workspacePanel as HTMLElement).getByText("monthly billing • SP-1001"),
    ).toBeInTheDocument();
    expect(
      within(workspacePanel as HTMLElement).getByText("Service point SP-1001"),
    ).toBeInTheDocument();
    expect(
      screen.getByRole("link", { name: "Open linked subscriber detail" }),
    ).toHaveAttribute("href", "/subscribers/consumer-1");
    expect(
      screen.getByRole("link", { name: "Open linked service point detail" }),
    ).toHaveAttribute("href", "/service-points/service-point-1");
    expect(
      screen.getByRole("link", { name: "Open primary meter detail" }),
    ).toHaveAttribute("href", "/meters/meter-1");
    expect(screen.getByRole("link", { name: "Open subscriber detail" })).toHaveAttribute(
      "href",
      "/subscribers/consumer-1",
    );
    expect(screen.getByRole("link", { name: "Open service point detail" })).toHaveAttribute(
      "href",
      "/service-points/service-point-1",
    );
    expect(screen.getByRole("link", { name: /SN-1001/i })).toHaveAttribute(
      "href",
      "/meters/meter-1",
    );
  });

  it("renders a bounded loading state while account detail is bootstrapping", async () => {
    const { fetchMock } = createMockApi();
    vi.stubGlobal(
      "fetch",
      vi.fn(async (input: RequestInfo | URL) => {
        const url = input.toString();
        if (url.endsWith("/api/v1/accounts/account-1")) {
          await new Promise((resolve) => setTimeout(resolve, 25));
        }
        return fetchMock(input);
      }),
    );

    renderAccountDetailsModuleInShell();

    expect(await screen.findByText("Loading account detail...")).toBeInTheDocument();
    expect(await screen.findByRole("heading", { name: "ACC-1001" })).toBeInTheDocument();
  });

  it("renders bounded empty linked sections when no service point or meters are linked", async () => {
    const { fetchMock } = createMockApi({
      payload: {
        id: "account-1",
        account_number: "ACC-1001",
        status: "active",
        billing_cycle: null,
        subscriber: {
          id: "consumer-1",
          full_name: "Amina Al Balushi",
          consumer_type: "residential",
          external_ref: null,
        },
        service_point: null,
        linked_meter_count: 0,
        linked_meters: [],
      },
    });
    vi.stubGlobal("fetch", fetchMock);

    renderAccountDetailsModuleInShell();

    await waitFor(() => {
      expect(screen.getByText("No service point linked to this account.")).toBeInTheDocument();
    });
    expect(screen.getByText("No current meters linked to this account.")).toBeInTheDocument();
    expect(screen.getByText("No current linked meter")).toBeInTheDocument();
  });

  it("renders a bounded error state when account detail fails", async () => {
    const { fetchMock } = createMockApi({
      status: 404,
      detailMessage: "Account not found.",
    });
    vi.stubGlobal("fetch", fetchMock);

    renderAccountDetailsModuleInShell();

    expect(await screen.findByText("Account not found.")).toBeInTheDocument();
  });
});
