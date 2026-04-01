import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { OperationalShell } from "../operational-shell";
import { ReadingsModule } from "./readings-module";

function jsonResponse(payload: unknown, status = 200) {
  return new Response(JSON.stringify(payload), {
    status,
    headers: { "Content-Type": "application/json" },
  });
}

function createMockApi({
  meterItems = [
    {
      id: "meter-1",
      serial_number: "SN-1001",
      utility_meter_number: "UMN-1001",
      manufacturer_code: "GENERIC",
      meter_model_code: "GM-1",
      communication_profile_code: "dlms-primary",
      meter_profile_code: "residential-default",
      current_status: "commissioned",
      last_seen_at: "2026-04-02T11:00:00.000Z",
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
  meterStatus = 200,
  meterDetail = "Readings overview unavailable.",
  readingsByMeter = {
    "meter-1": [
      {
        id: "reading-1",
        batch_id: "batch-billing-1",
        meter_id: "meter-1",
        obis_code: "1.0.1.8.0.255",
        reading_type: "register",
        value_numeric: "123.456",
        value_text: null,
        value_timestamp: null,
        unit: "kWh",
        quality: "good",
        captured_at: "2026-04-02T10:58:00.000Z",
        metadata: null,
      },
    ],
    "meter-2": [],
  } as Record<string, Array<Record<string, unknown>>>,
  registerSnapshotsByMeter = {
    "meter-1": [
      {
        id: "snapshot-billing-1",
        meter_id: "meter-1",
        related_batch_id: "batch-billing-1",
        snapshot_type: "billing",
        captured_at: "2026-04-02T10:58:00.000Z",
        payload: {
          total_import: "123.456",
          reset_reason: "scheduled_cycle",
        },
        checksum: "checksum-1",
      },
      {
        id: "snapshot-instant-1",
        meter_id: "meter-1",
        related_batch_id: "batch-instant-1",
        snapshot_type: "instantaneous",
        captured_at: "2026-04-02T10:55:00.000Z",
        payload: {
          current: "2.4",
        },
        checksum: null,
      },
    ],
    "meter-2": [],
  } as Record<string, Array<Record<string, unknown>>>,
  readingBatchesByMeter = {
    "meter-1": [
      {
        id: "batch-billing-1",
        meter_id: "meter-1",
        source_type: "manual_read",
        captured_at: "2026-04-02T10:58:00.000Z",
        received_at: "2026-04-02T10:59:00.000Z",
        status: "received",
        reading_context: null,
        correlation_id: "corr-1",
      },
    ],
    "meter-2": [],
  } as Record<string, Array<Record<string, unknown>>>,
  delayedMeters = false,
  delayedDetail = false,
}: {
  meterItems?: Array<Record<string, unknown>>;
  meterStatus?: number;
  meterDetail?: string;
  readingsByMeter?: Record<string, Array<Record<string, unknown>>>;
  registerSnapshotsByMeter?: Record<string, Array<Record<string, unknown>>>;
  readingBatchesByMeter?: Record<string, Array<Record<string, unknown>>>;
  delayedMeters?: boolean;
  delayedDetail?: boolean;
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
      if (delayedMeters) {
        await new Promise((resolve) => window.setTimeout(resolve, 20));
      }

      if (meterStatus !== 200) {
        return jsonResponse({ detail: meterDetail }, meterStatus);
      }

      return jsonResponse({
        total: meterItems.length,
        items: meterItems,
      });
    }

    const readingsMatch = url.match(/\/api\/v1\/meters\/([^/]+)\/readings\?limit=10$/);
    if (readingsMatch) {
      if (delayedDetail) {
        await new Promise((resolve) => window.setTimeout(resolve, 20));
      }
      const meterId = readingsMatch[1];
      return jsonResponse({
        total: readingsByMeter[meterId]?.length ?? 0,
        items: readingsByMeter[meterId] ?? [],
      });
    }

    const snapshotsMatch = url.match(
      /\/api\/v1\/meters\/([^/]+)\/register-snapshots\?limit=25$/,
    );
    if (snapshotsMatch) {
      if (delayedDetail) {
        await new Promise((resolve) => window.setTimeout(resolve, 20));
      }
      const meterId = snapshotsMatch[1];
      return jsonResponse({
        total: registerSnapshotsByMeter[meterId]?.length ?? 0,
        items: registerSnapshotsByMeter[meterId] ?? [],
      });
    }

    const batchesMatch = url.match(/\/api\/v1\/meters\/([^/]+)\/reading-batches\?limit=25$/);
    if (batchesMatch) {
      if (delayedDetail) {
        await new Promise((resolve) => window.setTimeout(resolve, 20));
      }
      const meterId = batchesMatch[1];
      return jsonResponse({
        total: readingBatchesByMeter[meterId]?.length ?? 0,
        items: readingBatchesByMeter[meterId] ?? [],
      });
    }

    throw new Error(`Unhandled request: ${url}`);
  });

  return { fetchMock };
}

function renderReadingsModuleInShell(initialMeterId?: string | null) {
  render(
    <OperationalShell
      eyebrow="Operational Pages"
      title="Readings Overview MVP"
      description="Bounded readings module"
    >
      {({ authorizedFetch }) => (
        <ReadingsModule authorizedFetch={authorizedFetch} initialMeterId={initialMeterId} />
      )}
    </OperationalShell>,
  );
}

describe("ReadingsModule", () => {
  beforeEach(() => {
    window.localStorage.setItem("sunrise.web.apiBaseUrl", "http://localhost:8000");
    window.localStorage.setItem("sunrise.web.accessToken", "token-1");
  });

  afterEach(() => {
    vi.unstubAllGlobals();
    window.localStorage.clear();
  });

  it("renders the readings overview and billing reads inside the shared shell", async () => {
    const { fetchMock } = createMockApi();
    vi.stubGlobal("fetch", fetchMock);

    renderReadingsModuleInShell();

    expect(await screen.findByRole("link", { name: "Readings" })).toBeInTheDocument();
    expect(
      await screen.findByRole("heading", { name: "Readings operations center" }),
    ).toBeInTheDocument();

    await waitFor(() => {
      expect(screen.getByText("Billing reads loaded")).toBeInTheDocument();
      expect(screen.getByText("Recent raw readings loaded")).toBeInTheDocument();
      expect(screen.getAllByText("Total Import: 123.456")).not.toHaveLength(0);
      expect(screen.getAllByText("Received")).not.toHaveLength(0);
    });

    expect(
      screen.getAllByRole("link", { name: "Open meter detail" })[0],
    ).toHaveAttribute("href", "/meters/meter-1");
    expect(screen.getByRole("link", { name: "Return to meter detail" })).toHaveAttribute(
      "href",
      "/meters/meter-1",
    );
    expect(screen.getByText("Billing reads table")).toBeInTheDocument();
    expect(screen.getByText("Total Import 123.456 • Reset Reason scheduled_cycle")).toBeInTheDocument();
  });

  it("switches the bounded billing reads surface when a different meter is selected", async () => {
    const { fetchMock } = createMockApi();
    vi.stubGlobal("fetch", fetchMock);
    const user = userEvent.setup();

    renderReadingsModuleInShell();

    const inspectButtons = await screen.findAllByRole("button", {
      name: "Inspect readings",
    });
    await user.click(inspectButtons[1]);

    const billingPanel = screen.getByRole("heading", { name: "Billing reads" }).closest("section");
    expect(billingPanel).not.toBeNull();

    await waitFor(() => {
      expect(within(billingPanel as HTMLElement).getAllByText("SN-1002")).not.toHaveLength(0);
      expect(
        within(billingPanel as HTMLElement).getByText(
          "No billing reads available for the selected meter.",
        ),
      ).toBeInTheDocument();
      expect(
        within(billingPanel as HTMLElement).getByText(
          "No recent reading values available for the selected meter.",
        ),
      ).toBeInTheDocument();
    });
  });

  it("preserves a handed-off meter context and loads its billing reads on arrival", async () => {
    const { fetchMock } = createMockApi({
      readingsByMeter: {
        "meter-1": [
          {
            id: "reading-1",
            batch_id: "batch-billing-1",
            meter_id: "meter-1",
            obis_code: "1.0.1.8.0.255",
            reading_type: "register",
            value_numeric: "123.456",
            value_text: null,
            value_timestamp: null,
            unit: "kWh",
            quality: "good",
            captured_at: "2026-04-02T10:58:00.000Z",
            metadata: null,
          },
        ],
        "meter-2": [
          {
            id: "reading-2",
            batch_id: "batch-billing-2",
            meter_id: "meter-2",
            obis_code: "1.0.1.8.0.255",
            reading_type: "register",
            value_numeric: "456.789",
            value_text: null,
            value_timestamp: null,
            unit: "kWh",
            quality: "good",
            captured_at: "2026-04-03T10:58:00.000Z",
            metadata: null,
          },
        ],
      },
      registerSnapshotsByMeter: {
        "meter-1": [
          {
            id: "snapshot-billing-1",
            meter_id: "meter-1",
            related_batch_id: "batch-billing-1",
            snapshot_type: "billing",
            captured_at: "2026-04-02T10:58:00.000Z",
            payload: {
              total_import: "123.456",
              reset_reason: "scheduled_cycle",
            },
            checksum: "checksum-1",
          },
        ],
        "meter-2": [
          {
            id: "snapshot-billing-2",
            meter_id: "meter-2",
            related_batch_id: "batch-billing-2",
            snapshot_type: "billing",
            captured_at: "2026-04-03T10:58:00.000Z",
            payload: {
              total_import: "456.789",
              reset_reason: "manual_close",
            },
            checksum: "checksum-2",
          },
        ],
      },
      readingBatchesByMeter: {
        "meter-1": [
          {
            id: "batch-billing-1",
            meter_id: "meter-1",
            source_type: "manual_read",
            captured_at: "2026-04-02T10:58:00.000Z",
            received_at: "2026-04-02T10:59:00.000Z",
            status: "received",
            reading_context: null,
            correlation_id: "corr-1",
          },
        ],
        "meter-2": [
          {
            id: "batch-billing-2",
            meter_id: "meter-2",
            source_type: "scheduled_read",
            captured_at: "2026-04-03T10:58:00.000Z",
            received_at: "2026-04-03T10:59:00.000Z",
            status: "received",
            reading_context: null,
            correlation_id: "corr-2",
          },
        ],
      },
    });
    vi.stubGlobal("fetch", fetchMock);

    renderReadingsModuleInShell("meter-2");

    expect(
      await screen.findByText("Meter handoff preserved for SN-1002"),
    ).toBeInTheDocument();

    await waitFor(() => {
      expect(screen.getAllByText("SN-1002")).not.toHaveLength(0);
      expect(screen.getAllByText("Total Import: 456.789")).not.toHaveLength(0);
      expect(
        screen.getByText("Total Import 456.789 • Reset Reason manual_close"),
      ).toBeInTheDocument();
    });
    expect(screen.getByRole("link", { name: "Return to meter detail" })).toHaveAttribute(
      "href",
      "/meters/meter-2",
    );
  });

  it("renders a bounded loading state while selected meter readings are bootstrapping", async () => {
    const { fetchMock } = createMockApi({ delayedDetail: true });
    vi.stubGlobal("fetch", fetchMock);

    renderReadingsModuleInShell();

    expect(
      await screen.findByText("Loading selected meter readings..."),
    ).toBeInTheDocument();

    await waitFor(() => {
      expect(screen.getByText("Billing reads table")).toBeInTheDocument();
    });
  });

  it("renders an empty state when no meters are available", async () => {
    const { fetchMock } = createMockApi({ meterItems: [] });
    vi.stubGlobal("fetch", fetchMock);

    renderReadingsModuleInShell();

    await waitFor(() => {
      expect(screen.getByText("No readings overview items available.")).toBeInTheDocument();
    });
  });

  it("renders a bounded error state when the meter list fails", async () => {
    const { fetchMock } = createMockApi({
      meterStatus: 503,
      meterDetail: "Readings overview unavailable.",
    });
    vi.stubGlobal("fetch", fetchMock);

    renderReadingsModuleInShell();

    expect(
      await screen.findByText("Readings overview unavailable."),
    ).toBeInTheDocument();
  });
});
