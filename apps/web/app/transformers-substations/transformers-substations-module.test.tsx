import { render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { OperationalShell } from "../operational-shell";
import { TransformersSubstationsModule } from "./transformers-substations-module";

function jsonResponse(payload: unknown, status = 200) {
  return new Response(JSON.stringify(payload), {
    status,
    headers: { "Content-Type": "application/json" },
  });
}

function createMockApi({
  items = [
    {
      id: "transformer-1",
      code: "TX-1001",
      name: "Airport Transformer",
      status: "active",
      feeder_code: "FDR-101",
      substation_id: "substation-1",
      substation_code: "SUB-101",
      substation_name: "Airport Primary",
      linked_meter_count: 2,
      linked_service_point_count: 1,
      primary_meter_serial_number: "SN-1001",
      primary_service_point_code: "SP-1001",
      location_hint: "Airport Road",
    },
    {
      id: "transformer-2",
      code: "TX-1002",
      name: "Harbor Transformer",
      status: "inactive",
      feeder_code: "FDR-102",
      substation_id: "substation-2",
      substation_code: "SUB-102",
      substation_name: "Harbor Primary",
      linked_meter_count: 0,
      linked_service_point_count: 0,
      primary_meter_serial_number: null,
      primary_service_point_code: null,
      location_hint: null,
    },
  ],
  status = 200,
  detail = "Infrastructure list unavailable.",
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

    if (url.includes("/api/v1/transformers-substations?")) {
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

function renderTransformersSubstationsModuleInShell() {
  render(
    <OperationalShell
      eyebrow="Operational Pages"
      title="Transformer / Substation Visibility MVP"
      description="Bounded infrastructure module"
    >
      {({ authorizedFetch }) => (
        <TransformersSubstationsModule authorizedFetch={authorizedFetch} />
      )}
    </OperationalShell>,
  );
}

describe("TransformersSubstationsModule", () => {
  beforeEach(() => {
    window.localStorage.setItem("sunrise.web.apiBaseUrl", "http://localhost:8000");
    window.localStorage.setItem("sunrise.web.accessToken", "token-1");
  });

  afterEach(() => {
    vi.unstubAllGlobals();
    window.localStorage.clear();
  });

  it("renders a compact infrastructure list inside the shared shell", async () => {
    const { fetchMock } = createMockApi();
    vi.stubGlobal("fetch", fetchMock);

    renderTransformersSubstationsModuleInShell();

    expect(
      await screen.findByRole("link", { name: "Transformers / Substations" }),
    ).toBeInTheDocument();
    expect(await screen.findByRole("link", { name: /TX-1001/i })).toHaveAttribute(
      "href",
      "/transformers-substations/transformer-1",
    );
    expect(screen.getByRole("link", { name: /TX-1002/i })).toHaveAttribute(
      "href",
      "/transformers-substations/transformer-2",
    );
  });

  it("keeps the bounded navigation path into infrastructure detail clear", async () => {
    const { fetchMock } = createMockApi();
    vi.stubGlobal("fetch", fetchMock);

    renderTransformersSubstationsModuleInShell();

    const detailLink = await screen.findByRole("link", {
      name: /TX-1001/i,
    });
    expect(detailLink).toHaveAttribute("href", "/transformers-substations/transformer-1");
  });

  it("renders an empty state when no infrastructure items are available", async () => {
    const { fetchMock } = createMockApi({ items: [] });
    vi.stubGlobal("fetch", fetchMock);

    renderTransformersSubstationsModuleInShell();

    await waitFor(() => {
      expect(
        screen.getByText(
          "No transformer or substation visibility is available for the current query.",
        ),
      ).toBeInTheDocument();
    });
  });

  it("renders a bounded error state when the infrastructure list fails", async () => {
    const { fetchMock } = createMockApi({
      status: 503,
      detail: "Infrastructure list unavailable.",
    });
    vi.stubGlobal("fetch", fetchMock);

    renderTransformersSubstationsModuleInShell();

    expect(await screen.findByText("Infrastructure list unavailable.")).toBeInTheDocument();
  });
});
