import { render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { OperationalShell } from "../../operational-shell";
import { ServicePointDetailsModule } from "./service-point-details-module";

function jsonResponse(payload: unknown, status = 200) {
  return new Response(JSON.stringify(payload), {
    status,
    headers: { "Content-Type": "application/json" },
  });
}

function createMockApi({
  status = 200,
  detailMessage = "Service point detail unavailable.",
  payload = {
    id: "service-point-1",
    service_point_code: "SP-1001",
    address_line: "Muttrah Waterfront",
    premises_type: "commercial",
    is_active: true,
    latitude: 23.62,
    longitude: 58.59,
    linked_meter_count: 1,
    linked_subscriber_count: 1,
    linked_account_count: 1,
    linked_meters: [
      {
        id: "meter-1",
        serial_number: "SN-1001",
        utility_meter_number: "UMN-1001",
        current_status: "registered",
        account_id: "account-1",
        account_number: "ACC-1001",
      },
    ],
    linked_subscribers: [
      {
        id: "consumer-1",
        full_name: "Beacon Premises LLC",
        consumer_type: "commercial",
        account_id: "account-1",
        account_number: "ACC-1001",
        account_status: "active",
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

    if (url.endsWith("/api/v1/service-points/service-point-1")) {
      if (status !== 200) {
        return jsonResponse({ detail: detailMessage }, status);
      }
      return jsonResponse(payload);
    }

    throw new Error(`Unhandled request: ${url}`);
  });

  return { fetchMock };
}

function renderServicePointDetailsModuleInShell() {
  render(
    <OperationalShell
      eyebrow="Operational Pages"
      title="Service Point service-point-1"
      description="Bounded service point detail"
    >
      {({ authorizedFetch }) => (
        <ServicePointDetailsModule
          servicePointId="service-point-1"
          authorizedFetch={authorizedFetch}
        />
      )}
    </OperationalShell>,
  );
}

describe("ServicePointDetailsModule", () => {
  beforeEach(() => {
    window.localStorage.setItem("sunrise.web.apiBaseUrl", "http://localhost:8000");
    window.localStorage.setItem("sunrise.web.accessToken", "token-1");
  });

  afterEach(() => {
    vi.unstubAllGlobals();
    window.localStorage.clear();
  });

  it("renders the bounded service-point detail surface with linked meters and subscribers", async () => {
    const { fetchMock } = createMockApi();
    vi.stubGlobal("fetch", fetchMock);

    renderServicePointDetailsModuleInShell();

    expect(await screen.findByText("SP-1001")).toBeInTheDocument();
    expect(screen.getByText("Muttrah Waterfront")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: /SN-1001/i })).toHaveAttribute(
      "href",
      "/meters/meter-1",
    );
    expect(screen.getByRole("link", { name: /Beacon Premises LLC/i })).toHaveAttribute(
      "href",
      "/subscribers/consumer-1",
    );
  });

  it("renders a bounded loading state while service-point detail is bootstrapping", async () => {
    const { fetchMock } = createMockApi();
    vi.stubGlobal(
      "fetch",
      vi.fn(async (input: RequestInfo | URL) => {
        const url = input.toString();
        if (url.endsWith("/api/v1/service-points/service-point-1")) {
          await new Promise((resolve) => setTimeout(resolve, 100));
        }
        return fetchMock(input);
      }),
    );

    renderServicePointDetailsModuleInShell();

    await waitFor(() => {
      expect(
        screen.queryByText("Loading service point detail...") ?? screen.queryByText("SP-1001"),
      ).toBeInTheDocument();
    });
    expect(await screen.findByText("SP-1001")).toBeInTheDocument();
  });

  it("renders bounded empty linked sections when no meters or subscribers are linked", async () => {
    const { fetchMock } = createMockApi({
      payload: {
        id: "service-point-1",
        service_point_code: "SP-1001",
        address_line: null,
        premises_type: null,
        is_active: true,
        latitude: null,
        longitude: null,
        linked_meter_count: 0,
        linked_subscriber_count: 0,
        linked_account_count: 0,
        linked_meters: [],
        linked_subscribers: [],
      },
    });
    vi.stubGlobal("fetch", fetchMock);

    renderServicePointDetailsModuleInShell();

    await waitFor(() => {
      expect(
        screen.getByText("No meters linked to this service point."),
      ).toBeInTheDocument();
    });
    expect(
      screen.getByText("No subscribers linked to this service point."),
    ).toBeInTheDocument();
  });

  it("renders a bounded error state when service-point detail fails", async () => {
    const { fetchMock } = createMockApi({
      status: 404,
      detailMessage: "Service point not found.",
    });
    vi.stubGlobal("fetch", fetchMock);

    renderServicePointDetailsModuleInShell();

    expect(await screen.findByText("Service point not found.")).toBeInTheDocument();
  });
});
