import { render, screen, waitFor, within } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { OperationalShell } from "../../operational-shell";
import { TransformerSubstationDetailsModule } from "./transformer-substation-details-module";

function jsonResponse(payload: unknown, status = 200) {
  return new Response(JSON.stringify(payload), {
    status,
    headers: { "Content-Type": "application/json" },
  });
}

function createMockApi({
  status = 200,
  detailMessage = "Infrastructure detail unavailable.",
  payload = {
    id: "transformer-1",
    code: "TX-1001",
    name: "Airport Transformer",
    status: "active",
    description: "Bounded infrastructure fixture",
    feeder_code: "FDR-101",
    feeder_name: "Airport Feeder",
    latitude: 23.5884,
    longitude: 58.3829,
    substation: {
      id: "substation-1",
      code: "SUB-101",
      name: "Airport Primary",
      status: "active",
      sector_code: "SEC-101",
      sector_name: "Airport Sector",
      region_code: "REG-101",
      region_name: "North Region",
      latitude: 23.587,
      longitude: 58.381,
    },
    linked_meter_count: 1,
    linked_service_point_count: 1,
    linked_meters: [
      {
        id: "meter-1",
        serial_number: "SN-1001",
        utility_meter_number: "UMN-1001",
        current_status: "registered",
        service_point_id: "service-point-1",
        service_point_code: "SP-1001",
      },
    ],
    linked_service_points: [
      {
        id: "service-point-1",
        service_point_code: "SP-1001",
        address_line: "Airport Road",
        premises_type: "commercial",
        is_active: true,
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

    if (url.endsWith("/api/v1/transformers-substations/transformer-1")) {
      if (status !== 200) {
        return jsonResponse({ detail: detailMessage }, status);
      }
      return jsonResponse(payload);
    }

    throw new Error(`Unhandled request: ${url}`);
  });

  return { fetchMock };
}

function renderTransformerSubstationDetailsModuleInShell() {
  render(
    <OperationalShell
      eyebrow="Operational Pages"
      title="Infrastructure transformer-1"
      description="Bounded infrastructure detail"
    >
      {({ authorizedFetch }) => (
        <TransformerSubstationDetailsModule
          transformerId="transformer-1"
          authorizedFetch={authorizedFetch}
        />
      )}
    </OperationalShell>,
  );
}

describe("TransformerSubstationDetailsModule", () => {
  beforeEach(() => {
    window.localStorage.setItem("sunrise.web.apiBaseUrl", "http://localhost:8000");
    window.localStorage.setItem("sunrise.web.accessToken", "token-1");
  });

  afterEach(() => {
    vi.unstubAllGlobals();
    window.localStorage.clear();
  });

  it("renders the bounded infrastructure detail surface with linked substation, service points, meters, and gis access", async () => {
    const { fetchMock } = createMockApi();
    vi.stubGlobal("fetch", fetchMock);

    renderTransformerSubstationDetailsModuleInShell();

    expect(
      await screen.findAllByText("TX-1001 · Airport Transformer"),
    ).not.toHaveLength(0);
    expect(screen.getAllByText("Active")).not.toHaveLength(0);
    expect(screen.getByRole("link", { name: "Open GIS Lite context" })).toHaveAttribute(
      "href",
      "/gis-lite?meterId=meter-1",
    );
    const linkedServicePointsPanel = screen.getByRole("heading", {
      name: "Linked service points",
    }).closest("section");
    expect(linkedServicePointsPanel).not.toBeNull();
    expect(
      within(linkedServicePointsPanel as HTMLElement).getByRole("link", {
        name: /SP-1001/i,
      }),
    ).toHaveAttribute(
      "href",
      "/service-points/service-point-1",
    );
    expect(screen.getByRole("link", { name: /SN-1001/i })).toHaveAttribute(
      "href",
      "/meters/meter-1",
    );
  });

  it("renders a bounded loading state while infrastructure detail is bootstrapping", async () => {
    const { fetchMock } = createMockApi();
    vi.stubGlobal(
      "fetch",
      vi.fn(async (input: RequestInfo | URL) => {
        const url = input.toString();
        if (url.endsWith("/api/v1/transformers-substations/transformer-1")) {
          await new Promise((resolve) => setTimeout(resolve, 25));
        }
        return fetchMock(input);
      }),
    );

    renderTransformerSubstationDetailsModuleInShell();

    expect(
      await screen.findByText("Loading transformer and substation detail..."),
    ).toBeInTheDocument();
    expect(await screen.findByText("TX-1001 · Airport Transformer")).toBeInTheDocument();
  });

  it("renders bounded empty linked sections when no service points or meters are linked", async () => {
    const { fetchMock } = createMockApi({
      payload: {
        id: "transformer-1",
        code: "TX-1001",
        name: "Airport Transformer",
        status: "active",
        description: null,
        feeder_code: "FDR-101",
        feeder_name: "Airport Feeder",
        latitude: null,
        longitude: null,
        substation: {
          id: "substation-1",
          code: "SUB-101",
          name: "Airport Primary",
          status: "active",
          sector_code: "SEC-101",
          sector_name: "Airport Sector",
          region_code: "REG-101",
          region_name: "North Region",
          latitude: null,
          longitude: null,
        },
        linked_meter_count: 0,
        linked_service_point_count: 0,
        linked_meters: [],
        linked_service_points: [],
      },
    });
    vi.stubGlobal("fetch", fetchMock);

    renderTransformerSubstationDetailsModuleInShell();

    await waitFor(() => {
      expect(
        screen.getByText("No linked service points for this transformer."),
      ).toBeInTheDocument();
    });
    expect(screen.getByText("No linked meters for this transformer.")).toBeInTheDocument();
  });

  it("renders a bounded error state when infrastructure detail fails", async () => {
    const { fetchMock } = createMockApi({
      status: 404,
      detailMessage: "Transformer not found.",
    });
    vi.stubGlobal("fetch", fetchMock);

    renderTransformerSubstationDetailsModuleInShell();

    expect(await screen.findByText("Transformer not found.")).toBeInTheDocument();
  });
});
