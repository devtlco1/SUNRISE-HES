import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { OperationalShell } from "../operational-shell";
import { ReadingsModule } from "./readings-module";

function includesText(text: string) {
  return (_content: string, element: Element | null) => element?.textContent?.includes(text) ?? false;
}

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
  loadProfileChannelsByMeter = {
    "meter-1": [
      {
        id: "channel-1",
        meter_id: "meter-1",
        channel_code: "lp_import",
        obis_code: "1.0.99.1.0.255",
        unit: "kWh",
        interval_seconds: 900,
        is_active: true,
      },
    ],
    "meter-2": [],
  } as Record<string, Array<Record<string, unknown>>>,
  loadProfileIntervalsByMeter = {
    "meter-1": [
      {
        id: "interval-1",
        meter_id: "meter-1",
        channel_id: "channel-1",
        interval_start: "2026-04-02T10:45:00.000Z",
        interval_end: "2026-04-02T11:00:00.000Z",
        value_numeric: "1.250",
        quality: "good",
        source_batch_id: "batch-billing-1",
      },
      {
        id: "interval-2",
        meter_id: "meter-1",
        channel_id: "channel-1",
        interval_start: "2026-04-02T10:30:00.000Z",
        interval_end: "2026-04-02T10:45:00.000Z",
        value_numeric: "1.125",
        quality: "estimated",
        source_batch_id: "batch-billing-1",
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
  loadProfileChannelsByMeter?: Record<string, Array<Record<string, unknown>>>;
  loadProfileIntervalsByMeter?: Record<string, Array<Record<string, unknown>>>;
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
        await new Promise((resolve) => window.setTimeout(resolve, 100));
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
        await new Promise((resolve) => window.setTimeout(resolve, 100));
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
        await new Promise((resolve) => window.setTimeout(resolve, 100));
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
        await new Promise((resolve) => window.setTimeout(resolve, 100));
      }
      const meterId = batchesMatch[1];
      return jsonResponse({
        total: readingBatchesByMeter[meterId]?.length ?? 0,
        items: readingBatchesByMeter[meterId] ?? [],
      });
    }

    const channelsMatch = url.match(/\/api\/v1\/meters\/([^/]+)\/load-profile-channels$/);
    if (channelsMatch) {
      if (delayedDetail) {
        await new Promise((resolve) => window.setTimeout(resolve, 100));
      }
      const meterId = channelsMatch[1];
      return jsonResponse({
        total: loadProfileChannelsByMeter[meterId]?.length ?? 0,
        items: loadProfileChannelsByMeter[meterId] ?? [],
      });
    }

    const intervalsMatch = url.match(
      /\/api\/v1\/meters\/([^/]+)\/load-profile-intervals\?limit=96$/,
    );
    if (intervalsMatch) {
      if (delayedDetail) {
        await new Promise((resolve) => window.setTimeout(resolve, 100));
      }
      const meterId = intervalsMatch[1];
      return jsonResponse({
        total: loadProfileIntervalsByMeter[meterId]?.length ?? 0,
        items: loadProfileIntervalsByMeter[meterId] ?? [],
      });
    }

    throw new Error(`Unhandled request: ${url}`);
  });

  return { fetchMock };
}

function renderReadingsModuleInShell(initialMeterId?: string | null) {
  render(
    <OperationalShell
      eyebrow="Operational Reports"
      title="Reports Workspace"
      description="Shell-aligned reporting surface"
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

    expect(screen.getByRole("heading", { name: "Reports Workspace" })).toBeInTheDocument();
    expect(
      await screen.findByRole("heading", { name: "Reports workspace" }),
    ).toBeInTheDocument();

    await waitFor(() => {
      expect(screen.getAllByText("Billing report context")).not.toHaveLength(0);
      expect(screen.getByText("Recent raw readings loaded")).toBeInTheDocument();
      expect(screen.getAllByText("Total Import: 123.456")).not.toHaveLength(0);
      expect(screen.getAllByText("Received")).not.toHaveLength(0);
    });

    expect(screen.getByText("Billing report")).toBeInTheDocument();
    expect(screen.getByText("Interval report")).toBeInTheDocument();
    expect(screen.getByText("Validation queue")).toBeInTheDocument();
    expect(screen.getByText("Recovery queue")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Open billing report" })).toHaveAttribute(
      "href",
      "#billing-reads-section",
    );
    expect(
      screen.getAllByRole("link", { name: "Open meter detail readings" })[0],
    ).toHaveAttribute("href", "/meters/meter-1?tab=readings#meter-readings-context-section");
    expect(
      screen.getByRole("link", { name: "Return to meter detail readings" }),
    ).toHaveAttribute("href", "/meters/meter-1?tab=readings#meter-readings-context-section");
    expect(screen.getByRole("link", { name: "Open raw readings detail" })).toHaveAttribute(
      "href",
      "/meters/meter-1?tab=readings#meter-raw-readings-section",
    );
    expect(screen.getByRole("link", { name: "Open billing / interval detail" })).toHaveAttribute(
      "href",
      "/meters/meter-1?tab=readings#meter-billing-interval-follow-through-section",
    );
    expect(screen.getByText("Focused report subject")).toBeInTheDocument();
    expect(screen.getByText("Selected meter SN-1001")).toBeInTheDocument();
    expect(screen.getByText("Overview reflects current billing context")).toBeInTheDocument();
    expect(screen.getByText("Report scope")).toBeInTheDocument();
    expect(screen.getByText("Selected report pack")).toBeInTheDocument();
    expect(screen.getByText("Current billing context")).toBeInTheDocument();
    expect(screen.getByText("Validation / interval visibility workspace")).toBeInTheDocument();
    expect(screen.getByText(/Latest billing snapshot captured/)).toBeInTheDocument();
    expect(screen.getByText("Billing reads table")).toBeInTheDocument();
    expect(screen.getByText("Newest first")).toBeInTheDocument();
    expect(screen.getByText("Interval reads")).toBeInTheDocument();
    expect(screen.getByText("Newest interval first")).toBeInTheDocument();
    expect(screen.getAllByText("Latest interval").length).toBeGreaterThan(0);
    expect(screen.getByText("Recent interval reads loaded")).toBeInTheDocument();
    expect(screen.getAllByText("Latest quality Good")).not.toHaveLength(0);
    expect(screen.getAllByText("Latest value 1.250 kWh")).not.toHaveLength(0);
    expect(screen.getAllByText("lp_import • 1.0.99.1.0.255")).not.toHaveLength(0);
    expect(screen.getByText("Interval window")).toBeInTheDocument();
    expect(screen.getByText("Quality")).toBeInTheDocument();
    expect(screen.getByText("Validation center")).toBeInTheDocument();
    expect(screen.getByText("1 open validation issues")).toBeInTheDocument();
    expect(screen.getByText("Validation queue in focus")).toBeInTheDocument();
    expect(screen.getAllByText("Interval Quality Flagged").length).toBeGreaterThan(0);
    expect(screen.getAllByText("Warning")).not.toHaveLength(0);
    expect(screen.getByText("Open")).toBeInTheDocument();
    expect(screen.getAllByText("Interval quality is marked Estimated.").length).toBeGreaterThan(0);
    expect(
      screen.getAllByRole("link", { name: "Review interval reads" })[0],
    ).toHaveAttribute("href", "#interval-reads-section");
    expect(screen.getByText("Missing reads / recovery queue")).toBeInTheDocument();
    expect(
      screen.getByText(
        "No missing reads or recovery issues match the current bounded selected-meter scope.",
      ),
    ).toBeInTheDocument();
    expect(screen.getByText("Recovery queue in focus")).toBeInTheDocument();
    expect(screen.getAllByText("Latest billing read")).not.toHaveLength(0);
    expect(screen.getByText("Received at")).toBeInTheDocument();
    expect(screen.getAllByText("Latest batch Received")).not.toHaveLength(0);
    expect(screen.getAllByText("Billing-read context available")).not.toHaveLength(0);
    expect(screen.getByText("Latest billing status")).toBeInTheDocument();
    expect(screen.getAllByText("Latest billing value")).not.toHaveLength(0);
    expect(screen.getAllByText("Total Import: 123.456")).not.toHaveLength(0);
    expect(screen.getByText("Latest billing source")).toBeInTheDocument();
    expect(screen.getAllByText("Source Manual Read")).not.toHaveLength(0);
    expect(screen.getByText("Billing payload summary")).toBeInTheDocument();
    expect(screen.getByText("Primary value Total Import: 123.456")).toBeInTheDocument();
    expect(screen.getByText("Batch receipt recorded")).toBeInTheDocument();
    expect(screen.getByText("Current primary billing value")).toBeInTheDocument();
    expect(screen.getByText(/Source Manual Read • Received/)).toBeInTheDocument();
    expect(
      screen.getAllByText("Total Import 123.456 • Reset Reason scheduled_cycle"),
    ).not.toHaveLength(0);
  });

  it("renders a dedicated interval visibility workspace with freshness, cadence, and anomaly posture", async () => {
    const { fetchMock } = createMockApi();
    vi.stubGlobal("fetch", fetchMock);

    renderReadingsModuleInShell();

    expect(
      await screen.findByText("Validation / interval visibility workspace"),
    ).toBeInTheDocument();

    await waitFor(() => {
      expect(screen.getByText("Latest raw reading freshness")).toBeInTheDocument();
      expect(screen.getByText("Interval horizon freshness")).toBeInTheDocument();
      expect(screen.getAllByText("Interval cadence").length).toBeGreaterThan(0);
      expect(screen.getAllByText("Interval posture").length).toBeGreaterThan(0);
      expect(screen.getByText("Warning validation cues")).toBeInTheDocument();
      expect(screen.getByText("Interval validation cues")).toBeInTheDocument();
      expect(screen.getByText("Interval recovery cues")).toBeInTheDocument();
      expect(screen.getAllByText("15 min cadence").length).toBeGreaterThan(0);
      expect(screen.getAllByText("Lead 2 min").length).toBeGreaterThan(0);
      expect(screen.getAllByText("Interval Quality Flagged").length).toBeGreaterThan(0);
      expect(
        screen.getAllByRole("link", { name: "Open meter detail drill-through" })[0],
      ).toHaveAttribute("href", "/meters/meter-1?tab=readings#meter-billing-interval-follow-through-section");
    });
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

    const billingPanel = screen.getByRole("heading", { name: "Selected report pack" }).closest("section");
    expect(billingPanel).not.toBeNull();

    await waitFor(() => {
      expect(within(billingPanel as HTMLElement).getAllByText("SN-1002")).not.toHaveLength(0);
      expect(
        within(billingPanel as HTMLElement).getAllByText("Billing-read context missing"),
      ).not.toHaveLength(0);
      expect(
        within(billingPanel as HTMLElement).getByText("Validation center"),
      ).toBeInTheDocument();
      expect(
        within(billingPanel as HTMLElement).getByText("1 open validation issues"),
      ).toBeInTheDocument();
      expect(
        within(billingPanel as HTMLElement).getAllByText("Billing Context Missing").length,
      ).toBeGreaterThan(0);
      expect(
        within(
          billingPanel as HTMLElement,
        ).getAllByText(
          "No billing read is available for the selected meter in the current bounded readings scope.",
        ).length,
      ).toBeGreaterThan(0);
      expect(
        within(billingPanel as HTMLElement).getAllByRole("link", {
          name: "Review billing reads",
        })[0],
      ).toHaveAttribute("href", "#billing-reads-section");
      expect(
        within(billingPanel as HTMLElement).getByText("Missing reads / recovery queue"),
      ).toBeInTheDocument();
      expect(
        within(billingPanel as HTMLElement).getByText("2 open recovery issues"),
      ).toBeInTheDocument();
      expect(
        within(billingPanel as HTMLElement).getAllByText("Missing Billing Read Context").length,
      ).toBeGreaterThan(0);
      expect(
        within(billingPanel as HTMLElement).getAllByText("Missing Recent Reading Update").length,
      ).toBeGreaterThan(0);
      expect(
        within(
          billingPanel as HTMLElement,
        ).getAllByText("No billing read is currently available for the selected meter.").length,
      ).toBeGreaterThan(0);
      expect(
        within(
          billingPanel as HTMLElement,
        ).getAllByText(
          "No recent raw reading update is available for the selected meter.",
        ).length,
      ).toBeGreaterThan(0);
      expect(
        within(billingPanel as HTMLElement).getAllByRole("link", {
          name: "Review recent reading context",
        })[0],
      ).toHaveAttribute("href", "#recent-reading-context-section");
      const recoveryActionLinks = within(billingPanel as HTMLElement).getAllByRole("link", {
        name: "Open on-demand read handoff",
      });
      expect(recoveryActionLinks.length).toBeGreaterThan(0);
      expect(recoveryActionLinks[0].getAttribute("href")).toContain("/commands?meterId=meter-2");
      expect(recoveryActionLinks[0].getAttribute("href")).toContain(
        "commandFamily=on_demand_read",
      );
      expect(recoveryActionLinks[0].getAttribute("href")).toContain(
        "recoveryIssueType=missing_billing_read_context",
      );
      expect(
        within(billingPanel as HTMLElement).getAllByText(
          "Opens the existing commands wizard with approvals behavior unchanged.",
        ).length,
      ).toBeGreaterThan(0);
      expect(
        within(billingPanel as HTMLElement).getByText(
          "No billing reads available for the selected meter yet. The selected meter summary above reflects the current missing billing-read context.",
        ),
      ).toBeInTheDocument();
      expect(
        within(billingPanel as HTMLElement).getByText(
          "No recent reading values available for the selected meter.",
        ),
      ).toBeInTheDocument();
      expect(
        within(billingPanel as HTMLElement).getByText(
          "No interval reads available for the selected meter yet. The interval section remains bounded to current recent load profile records only.",
        ),
      ).toBeInTheDocument();
      expect(
        within(billingPanel as HTMLElement).getByText(
          "No billing-read context recorded yet for the selected meter.",
        ),
      ).toBeInTheDocument();
      expect(
        within(billingPanel as HTMLElement).getByText("Current billing context"),
      ).toBeInTheDocument();
      expect(within(billingPanel as HTMLElement).getByText("Interval reads")).toBeInTheDocument();
      expect(
        within(billingPanel as HTMLElement).getByText(
          "No billing-read context is recorded yet for the selected meter. Use the meter detail return path if you need to confirm whether a billing read should exist for this meter.",
        ),
      ).toBeInTheDocument();
      expect(
        within(billingPanel as HTMLElement).getByText(
          "No interval-read context is recorded yet for the selected meter. The bounded interval surface remains empty until load profile intervals are available.",
        ),
      ).toBeInTheDocument();
      expect(
        within(billingPanel as HTMLElement).getByText("Primary value unavailable"),
      ).toBeInTheDocument();
      expect(within(billingPanel as HTMLElement).getByText("Source unavailable")).toBeInTheDocument();
    });
  });

  it("filters the meter list and keeps selected meter context coherent", async () => {
    const { fetchMock } = createMockApi();
    vi.stubGlobal("fetch", fetchMock);
    const user = userEvent.setup();

    renderReadingsModuleInShell();

    const filterInput = await screen.findByRole("searchbox", { name: "Meter filter" });
    await user.type(filterInput, "1002");

    await waitFor(() => {
      expect(screen.getAllByText("SN-1002")).not.toHaveLength(0);
      expect(screen.getByText("1 of 2 meters match the current filter")).toBeInTheDocument();
      expect(screen.getByText("1 filtered meter in scope")).toBeInTheDocument();
      expect(screen.getByText("Selected meter SN-1002")).toBeInTheDocument();
      expect(screen.getByText("Overview reflects missing billing context")).toBeInTheDocument();
      expect(
        screen.getByRole("link", { name: "Return to meter detail readings" }),
      ).toHaveAttribute("href", "/meters/meter-2?tab=readings#meter-readings-context-section");
    });

    expect(screen.queryByText("SN-1001")).not.toBeInTheDocument();
  });

  it("renders a bounded empty state when the meter filter has no matches", async () => {
    const { fetchMock } = createMockApi();
    vi.stubGlobal("fetch", fetchMock);
    const user = userEvent.setup();

    renderReadingsModuleInShell();

    const filterInput = await screen.findByRole("searchbox", { name: "Meter filter" });
    await user.type(filterInput, "missing-meter");

    await waitFor(() => {
      expect(
        screen.getByText("No meters match the current filter. Clear the search to inspect billing reads."),
      ).toBeInTheDocument();
      expect(screen.getByText("Choose a meter to open its report pack")).toBeInTheDocument();
      expect(
        screen.getByText("Adjust or clear the meter filter to restore a report focus."),
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
      loadProfileChannelsByMeter: {
        "meter-1": [
          {
            id: "channel-1",
            meter_id: "meter-1",
            channel_code: "lp_import",
            obis_code: "1.0.99.1.0.255",
            unit: "kWh",
            interval_seconds: 900,
            is_active: true,
          },
        ],
        "meter-2": [
          {
            id: "channel-2",
            meter_id: "meter-2",
            channel_code: "lp_export",
            obis_code: "1.0.99.2.0.255",
            unit: "kWh",
            interval_seconds: 1800,
            is_active: true,
          },
        ],
      },
      loadProfileIntervalsByMeter: {
        "meter-1": [
          {
            id: "interval-1",
            meter_id: "meter-1",
            channel_id: "channel-1",
            interval_start: "2026-04-02T10:45:00.000Z",
            interval_end: "2026-04-02T11:00:00.000Z",
            value_numeric: "1.250",
            quality: "good",
            source_batch_id: "batch-billing-1",
          },
        ],
        "meter-2": [
          {
            id: "interval-2",
            meter_id: "meter-2",
            channel_id: "channel-2",
            interval_start: "2026-04-03T10:30:00.000Z",
            interval_end: "2026-04-03T11:00:00.000Z",
            value_numeric: "2.500",
            quality: "good",
            source_batch_id: "batch-billing-2",
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
      expect(screen.getAllByText("Billing-read context available")).not.toHaveLength(0);
      expect(screen.getAllByText("Total Import: 456.789")).not.toHaveLength(0);
      expect(screen.getByText("Selected meter SN-1002")).toBeInTheDocument();
      expect(screen.getByText("Overview reflects current billing context")).toBeInTheDocument();
      expect(screen.getAllByText("Source Scheduled Read")).not.toHaveLength(0);
      expect(screen.getAllByText("Latest quality Good")).not.toHaveLength(0);
      expect(screen.getAllByText("Latest value 2.500 kWh")).not.toHaveLength(0);
      expect(screen.getAllByText("lp_export • 1.0.99.2.0.255")).not.toHaveLength(0);
      expect(screen.getByText("Latest billing status")).toBeInTheDocument();
      expect(screen.getByText("Primary value Total Import: 456.789")).toBeInTheDocument();
      expect(screen.getAllByText("Total Import 456.789 • Reset Reason manual_close")).not.toHaveLength(0);
    });
    expect(
      screen.getByRole("link", { name: "Return to meter detail readings" }),
    ).toHaveAttribute("href", "/meters/meter-2?tab=readings#meter-readings-context-section");
  });

  it("renders a stale interval-window issue inside the recovery queue when interval coverage lags behind readings", async () => {
    const { fetchMock } = createMockApi({
      readingsByMeter: {
        "meter-1": [
          {
            id: "reading-stale-1",
            batch_id: "batch-billing-1",
            meter_id: "meter-1",
            obis_code: "1.0.1.8.0.255",
            reading_type: "register",
            value_numeric: "123.999",
            value_text: null,
            value_timestamp: null,
            unit: "kWh",
            quality: "good",
            captured_at: "2026-04-02T11:30:00.000Z",
            metadata: null,
          },
        ],
        "meter-2": [],
      },
      loadProfileIntervalsByMeter: {
        "meter-1": [
          {
            id: "interval-stale-1",
            meter_id: "meter-1",
            channel_id: "channel-1",
            interval_start: "2026-04-02T10:45:00.000Z",
            interval_end: "2026-04-02T11:00:00.000Z",
            value_numeric: "1.250",
            quality: "good",
            source_batch_id: "batch-billing-1",
          },
        ],
        "meter-2": [],
      },
    });
    vi.stubGlobal("fetch", fetchMock);

    renderReadingsModuleInShell();

    expect(await screen.findByText("Missing reads / recovery queue")).toBeInTheDocument();
    await waitFor(() => {
      expect(screen.getAllByText(includesText("Stale Interval Window")).length).toBeGreaterThan(0);
      expect(screen.getAllByText("Lag 30 min").length).toBeGreaterThan(0);
      expect(
        screen.getAllByText(
          "The latest interval window ends before the most recent raw reading update, indicating a stale interval horizon.",
        ).length,
      ).toBeGreaterThan(0);
      expect(
        screen.getAllByRole("link", { name: "Review interval reads" })[0],
      ).toHaveAttribute("href", "#interval-reads-section");
      const staleRecoveryActionLink = screen.getByRole("link", {
        name: "Open on-demand read handoff",
      });
      expect(staleRecoveryActionLink.getAttribute("href")).toContain("/commands?meterId=meter-1");
      expect(staleRecoveryActionLink.getAttribute("href")).toContain(
        "commandFamily=on_demand_read",
      );
      expect(staleRecoveryActionLink.getAttribute("href")).toContain(
        "recoveryIssueType=stale_interval_window",
      );
    });
  });

  it("preserves multi-meter recovery selections and hands them off through bulk commands", async () => {
    const { fetchMock } = createMockApi({
      readingsByMeter: {
        "meter-1": [
          {
            id: "reading-stale-1",
            batch_id: "batch-billing-1",
            meter_id: "meter-1",
            obis_code: "1.0.1.8.0.255",
            reading_type: "register",
            value_numeric: "123.999",
            value_text: null,
            value_timestamp: null,
            unit: "kWh",
            quality: "good",
            captured_at: "2026-04-02T11:30:00.000Z",
            metadata: null,
          },
        ],
        "meter-2": [],
      },
      loadProfileIntervalsByMeter: {
        "meter-1": [
          {
            id: "interval-stale-1",
            meter_id: "meter-1",
            channel_id: "channel-1",
            interval_start: "2026-04-02T10:45:00.000Z",
            interval_end: "2026-04-02T11:00:00.000Z",
            value_numeric: "1.250",
            quality: "good",
            source_batch_id: "batch-billing-1",
          },
        ],
        "meter-2": [],
      },
    });
    vi.stubGlobal("fetch", fetchMock);
    const user = userEvent.setup();

    renderReadingsModuleInShell();

    const staleSelection = await screen.findByRole("checkbox", {
      name: "Include Stale Interval Window for SN-1001 in bulk recovery handoff",
    });
    await user.click(staleSelection);

    await waitFor(() => {
      expect(staleSelection).toBeChecked();
      expect(screen.getByRole("link", { name: "Open bulk recovery handoff" })).toHaveAttribute(
        "href",
        expect.stringContaining("/commands?meterIds=meter-1"),
      );
    });

    const inspectButtons = await screen.findAllByRole("button", {
      name: "Inspect readings",
    });
    await user.click(inspectButtons[1]);

    const meterTwoSelection = await screen.findByRole("checkbox", {
      name: "Include Missing Billing Read Context for SN-1002 in bulk recovery handoff",
    });
    await user.click(meterTwoSelection);

    await waitFor(() => {
      expect(meterTwoSelection).toBeChecked();
      expect(screen.getByRole("link", { name: "Open bulk recovery handoff" })).toHaveAttribute(
        "href",
        expect.stringContaining("/commands?meterIds=meter-1%2Cmeter-2"),
      );
    });

    const bulkRecoveryLink = screen.getByRole("link", { name: "Open bulk recovery handoff" });
    expect(bulkRecoveryLink.getAttribute("href")).toContain("/commands?meterIds=meter-1%2Cmeter-2");
    expect(bulkRecoveryLink.getAttribute("href")).toContain("commandFamily=on_demand_read");
    expect(bulkRecoveryLink.getAttribute("href")).toContain(
      "recoveryIssueType=bulk_recovery_selection",
    );
  });

  it("renders a bounded empty validation state when no issues are derived", async () => {
    const { fetchMock } = createMockApi({
      loadProfileIntervalsByMeter: {
        "meter-1": [
          {
            id: "interval-clean-1",
            meter_id: "meter-1",
            channel_id: "channel-1",
            interval_start: "2026-04-02T10:45:00.000Z",
            interval_end: "2026-04-02T11:00:00.000Z",
            value_numeric: "1.250",
            quality: "good",
            source_batch_id: "batch-billing-1",
          },
        ],
        "meter-2": [],
      },
    });
    vi.stubGlobal("fetch", fetchMock);

    renderReadingsModuleInShell();

    expect(await screen.findByText("Validation center")).toBeInTheDocument();
    await waitFor(() => {
      expect(
        screen.getByText("No validation issues match the current bounded selected-meter scope."),
      ).toBeInTheDocument();
      expect(
        screen.getByText(
          "No interval or validation anomalies are currently derived for the selected meter.",
        ),
      ).toBeInTheDocument();
    });
  });

  it("renders a bounded loading state while selected meter readings are bootstrapping", async () => {
    const { fetchMock } = createMockApi({ delayedDetail: true });
    vi.stubGlobal("fetch", fetchMock);

    renderReadingsModuleInShell();

    await waitFor(() => {
      expect(
        screen.queryByText("Loading selected meter readings and validation workspace...") ??
          screen.queryByText("Billing reads table"),
      ).toBeInTheDocument();
    });

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
