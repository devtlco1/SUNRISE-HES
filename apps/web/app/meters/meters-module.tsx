"use client";

import Link from "next/link";
import { useCallback, useEffect, useMemo, useState } from "react";

import {
  DataTableShell,
  FilterToolbar,
  StatCard,
  StatusChip,
  formatDateTime,
  formatStatusLabel,
  getStatusTone,
  type StatusTone,
} from "../operational-ui";
import type { AuthorizedFetch } from "../operational-shell";
import { FourCircleIcon, PieChartIcon, TableIcon, UserIcon } from "../nextadmin-icons";

type MeterItem = {
  id: string;
  serial_number: string;
  utility_meter_number: string | null;
  badge_number: string | null;
  manufacturer_code: string;
  meter_model_code: string;
  firmware_version: string | null;
  communication_profile_code: string | null;
  meter_profile_code: string | null;
  current_status: string;
  transformer_id: string | null;
  service_point_id: string | null;
  is_active: boolean;
  last_seen_at: string | null;
};

type MeterListResponse = {
  total: number;
  items: MeterItem[];
};

type CommunicationProfile = {
  code: string;
  name: string;
  transport_type: string;
};

type CommunicationProfileListResponse = {
  total: number;
  items: CommunicationProfile[];
};

type MeterProfile = {
  code: string;
  protocol_family: string | null;
};

type MeterProfileListResponse = {
  total: number;
  items: MeterProfile[];
};

type CommandRecentItem = {
  command_id: string;
  command_status: string;
  command_template_code: string;
  latest_updated_at: string;
};

type MeterRecentCommandsResponse = {
  meter_id: string;
  total: number;
  items: CommandRecentItem[];
};

type MeterEventItem = {
  id: string;
  severity: string;
  event_state: string;
  event_name: string | null;
  occurred_at: string;
};

type MeterEventListResponse = {
  total: number;
  items: MeterEventItem[];
};

type MeterReadingItem = {
  id: string;
  captured_at: string;
  quality: string | null;
};

type MeterReadingListResponse = {
  total: number;
  items: MeterReadingItem[];
};

type GisLiteEntity = {
  meter_id: string;
  service_point_code: string | null;
  has_coordinates: boolean;
  subscriber_display_name: string | null;
  account_number: string | null;
  location_presence: "coordinates_available" | "service_point_only" | "unlinked";
};

type GisLiteEntityListResponse = {
  total: number;
  items: GisLiteEntity[];
};

type EnrichedMeterRow = {
  meter: MeterItem;
  communicationType: string;
  protocolType: string;
  signalLabel: string;
  signalTone: StatusTone;
  lastReadAt: string | null;
  lastReadTone: StatusTone;
  commandStateLabel: string;
  commandStateTone: StatusTone;
  commandUpdatedAt: string | null;
  alarmStateLabel: string;
  alarmStateTone: StatusTone;
  linkedConsumer: string;
  linkedAccount: string;
  servicePointCode: string | null;
  gisLabel: string;
  gisTone: StatusTone;
};

type LifecycleFilter = "all" | "active" | "maintenance" | "inactive" | "registered";
type SignalFilter = "all" | "online" | "warning" | "offline";
type MappingFilter = "all" | "mapped" | "service_point_only" | "unlinked";

const PAGE_SIZE = 20;
const STALE_SIGNAL_THRESHOLD_MS = 1000 * 60 * 60 * 24;

function buildSignalState(lastSeenAt: string | null): { label: string; tone: StatusTone } {
  if (!lastSeenAt) {
    return { label: "Offline", tone: "danger" };
  }

  const date = new Date(lastSeenAt);
  if (Number.isNaN(date.getTime())) {
    return { label: "Unknown", tone: "neutral" };
  }

  const ageMs = Date.now() - date.getTime();
  if (ageMs >= STALE_SIGNAL_THRESHOLD_MS) {
    return { label: "Stale", tone: "warning" };
  }

  return { label: "Online", tone: "positive" };
}

function formatMappingStatus(entity: GisLiteEntity | null): { label: string; tone: StatusTone } {
  if (!entity) {
    return { label: "Unknown", tone: "neutral" };
  }
  if (entity.has_coordinates) {
    return { label: "Mapped", tone: "positive" };
  }
  if (entity.location_presence === "service_point_only") {
    return { label: "Service point only", tone: "warning" };
  }
  if (entity.location_presence === "unlinked") {
    return { label: "Unlinked", tone: "danger" };
  }
  return { label: "Unknown", tone: "neutral" };
}

export function MetersModule({
  authorizedFetch,
}: {
  authorizedFetch: AuthorizedFetch;
}) {
  const [searchDraft, setSearchDraft] = useState("");
  const [appliedSearch, setAppliedSearch] = useState("");
  const [pageIndex, setPageIndex] = useState(0);
  const [lifecycleFilter, setLifecycleFilter] = useState<LifecycleFilter>("all");
  const [signalFilter, setSignalFilter] = useState<SignalFilter>("all");
  const [mappingFilter, setMappingFilter] = useState<MappingFilter>("all");
  const [rows, setRows] = useState<EnrichedMeterRow[]>([]);
  const [totalMeters, setTotalMeters] = useState(0);
  const [selectedMeterIds, setSelectedMeterIds] = useState<string[]>([]);
  const [pageError, setPageError] = useState<string | null>(null);
  const [isLoadingMeters, setIsLoadingMeters] = useState(false);

  const loadMeters = useCallback(async () => {
    setIsLoadingMeters(true);
    setPageError(null);

    try {
      const params = new URLSearchParams({
        offset: String(pageIndex * PAGE_SIZE),
        limit: String(PAGE_SIZE),
      });

      if (appliedSearch.trim()) {
        params.set("search", appliedSearch.trim());
      }

      const [metersResponse, communicationProfilesResponse, meterProfilesResponse] =
        await Promise.all([
          authorizedFetch<MeterListResponse>(`/api/v1/meters?${params.toString()}`),
          authorizedFetch<CommunicationProfileListResponse>("/api/v1/communication-profiles"),
          authorizedFetch<MeterProfileListResponse>("/api/v1/meter-profiles"),
        ]);

      const communicationTypes = new Map(
        communicationProfilesResponse.items.map((profile) => [
          profile.code,
          formatStatusLabel(profile.transport_type),
        ]),
      );
      const protocolTypes = new Map(
        meterProfilesResponse.items.map((profile) => [
          profile.code,
          profile.protocol_family ? formatStatusLabel(profile.protocol_family) : "Not set",
        ]),
      );

      const contextResults = await Promise.all(
        metersResponse.items.map(async (meter) => {
          const [gisResult, readingsResult, commandsResult, eventsResult] = await Promise.allSettled([
            authorizedFetch<GisLiteEntityListResponse>(
              `/api/v1/gis-lite/entities?limit=1&meter_id=${meter.id}`,
            ),
            authorizedFetch<MeterReadingListResponse>(`/api/v1/meters/${meter.id}/readings?limit=1`),
            authorizedFetch<MeterRecentCommandsResponse>(
              `/api/v1/meters/${meter.id}/commands/recent?limit=1`,
            ),
            authorizedFetch<MeterEventListResponse>(
              `/api/v1/meters/${meter.id}/ingested-events?limit=1`,
            ),
          ]);

          const signal = buildSignalState(meter.last_seen_at);
          const gisEntity = gisResult.status === "fulfilled" ? gisResult.value.items[0] ?? null : null;
          const latestReading =
            readingsResult.status === "fulfilled" ? readingsResult.value.items[0] ?? null : null;
          const latestCommand =
            commandsResult.status === "fulfilled" ? commandsResult.value.items[0] ?? null : null;
          const latestEvent =
            eventsResult.status === "fulfilled" ? eventsResult.value.items[0] ?? null : null;
          const mapping = formatMappingStatus(gisEntity);

          return {
            meter,
            communicationType: meter.communication_profile_code
              ? communicationTypes.get(meter.communication_profile_code) ??
                meter.communication_profile_code
              : "Not assigned",
            protocolType: meter.meter_profile_code
              ? protocolTypes.get(meter.meter_profile_code) ?? meter.meter_profile_code
              : "Not assigned",
            signalLabel: signal.label,
            signalTone: signal.tone,
            lastReadAt: latestReading?.captured_at ?? null,
            lastReadTone:
              latestReading && latestReading.quality && !["actual", "valid"].includes(latestReading.quality)
                ? "warning"
                : latestReading
                  ? "info"
                  : "neutral",
            commandStateLabel: latestCommand
              ? formatStatusLabel(latestCommand.command_status)
              : "No recent command",
            commandStateTone: latestCommand
              ? getStatusTone(latestCommand.command_status)
              : "neutral",
            commandUpdatedAt: latestCommand?.latest_updated_at ?? null,
            alarmStateLabel: latestEvent
              ? `${formatStatusLabel(latestEvent.severity)} / ${formatStatusLabel(latestEvent.event_state)}`
              : "No recent alarm",
            alarmStateTone: latestEvent ? getStatusTone(latestEvent.severity) : "neutral",
            linkedConsumer: gisEntity?.subscriber_display_name ?? "Not linked",
            linkedAccount: gisEntity?.account_number ?? "Not linked",
            servicePointCode: gisEntity?.service_point_code ?? null,
            gisLabel: mapping.label,
            gisTone: mapping.tone,
          } satisfies EnrichedMeterRow;
        }),
      );

      setRows(contextResults);
      setTotalMeters(metersResponse.total);
      setSelectedMeterIds((current) =>
        current.filter((meterId) => contextResults.some((row) => row.meter.id === meterId)),
      );

      if (
        contextResults.length > 0 &&
        contextResults.some(
          (row) =>
            row.commandStateLabel === "No recent command" ||
            row.alarmStateLabel === "No recent alarm",
        )
      ) {
        setPageError(null);
      }
    } catch (error) {
      setRows([]);
      setTotalMeters(0);
      setSelectedMeterIds([]);
      setPageError(error instanceof Error ? error.message : "Unable to load meters.");
    } finally {
      setIsLoadingMeters(false);
    }
  }, [appliedSearch, authorizedFetch, pageIndex]);

  useEffect(() => {
    void loadMeters();
  }, [loadMeters]);

  const filteredRows = useMemo(() => {
    return rows.filter((row) => {
      const lifecycleMatches =
        lifecycleFilter === "all"
          ? true
          : lifecycleFilter === "active"
            ? row.meter.current_status === "active"
            : lifecycleFilter === "maintenance"
              ? row.meter.current_status === "maintenance"
              : lifecycleFilter === "inactive"
                ? row.meter.current_status === "inactive"
                : row.meter.current_status === "registered";

      const signalMatches =
        signalFilter === "all"
          ? true
          : signalFilter === "online"
            ? row.signalLabel === "Online"
            : signalFilter === "warning"
              ? row.signalTone === "warning"
              : row.signalLabel === "Offline";

      const mappingMatches =
        mappingFilter === "all"
          ? true
          : mappingFilter === "mapped"
            ? row.gisLabel === "Mapped"
            : mappingFilter === "service_point_only"
              ? row.gisLabel === "Service point only"
              : row.gisLabel === "Unlinked";

      return lifecycleMatches && signalMatches && mappingMatches;
    });
  }, [lifecycleFilter, mappingFilter, rows, signalFilter]);

  const selectedMetersCommandsHref = useMemo(() => {
    if (selectedMeterIds.length === 0) {
      return "/commands";
    }

    const params = new URLSearchParams({
      meterIds: selectedMeterIds.join(","),
      meterScopeSource: "meter_registry_current_page",
    });
    return `/commands?${params.toString()}`;
  }, [selectedMeterIds]);

  const summaryCards = useMemo(() => {
    const onlineCount = filteredRows.filter((row) => row.signalLabel === "Online").length;
    const flaggedCount = filteredRows.filter((row) => row.signalTone !== "positive").length;
    const mappedCount = filteredRows.filter((row) => row.gisLabel === "Mapped").length;
    const commandAttentionCount = filteredRows.filter(
      (row) => row.commandStateTone === "warning" || row.commandStateTone === "danger",
    ).length;

    return [
      {
        label: "Inventory result",
        value: String(totalMeters),
        note: `${filteredRows.length} rows visible on this page after current refiners`,
        tone: "neutral" as const,
        icon: TableIcon,
      },
      {
        label: "Online on this page",
        value: String(onlineCount),
        note: `${flaggedCount} rows need signal review`,
        tone: onlineCount > 0 ? ("positive" as const) : ("warning" as const),
        icon: PieChartIcon,
      },
      {
        label: "Mapped on this page",
        value: String(mappedCount),
        note: `${filteredRows.length - mappedCount} rows need GIS completion`,
        tone: mappedCount > 0 ? ("positive" as const) : ("warning" as const),
        icon: UserIcon,
      },
      {
        label: "Command attention",
        value: String(commandAttentionCount),
        note: `${selectedMeterIds.length} rows selected for bulk action`,
        tone: commandAttentionCount > 0 ? ("warning" as const) : ("neutral" as const),
        icon: FourCircleIcon,
      },
    ];
  }, [filteredRows, selectedMeterIds.length, totalMeters]);

  const totalPages = Math.max(1, Math.ceil(totalMeters / PAGE_SIZE));

  function toggleMeterSelection(meterId: string) {
    setSelectedMeterIds((current) =>
      current.includes(meterId) ? current.filter((item) => item !== meterId) : [...current, meterId],
    );
  }

  function selectVisibleMeters() {
    setSelectedMeterIds(filteredRows.map((row) => row.meter.id));
  }

  return (
    <div className="hes-page-stack">
      {pageError ? <p className="error-banner">{pageError}</p> : null}

      <div className="hes-stat-grid">
        {summaryCards.map((card) => (
          <StatCard
            key={card.label}
            icon={card.icon}
            label={card.label}
            note={card.note}
            tone={card.tone}
            value={card.value}
          />
        ))}
      </div>

      <div className="hes-toolbar-stack">
        <FilterToolbar
          summary={
            <>
              <span className="artifact-pill">{filteredRows.length} rows visible</span>
              <span className="artifact-pill">{selectedMeterIds.length} selected</span>
              <span className="artifact-pill">Search queries the meter API</span>
            </>
          }
        >
          <form
            className="hes-filter-toolbar-controls"
            onSubmit={(event) => {
              event.preventDefault();
              setPageIndex(0);
              setAppliedSearch(searchDraft);
            }}
          >
            <label className="hes-toolbar-field">
              <span>Search</span>
              <input
                aria-label="Search"
                placeholder="Serial, utility number, badge, or internal ID"
                value={searchDraft}
                onChange={(event) => setSearchDraft(event.target.value)}
              />
            </label>

            <label className="hes-toolbar-field">
              <span>Lifecycle</span>
              <select
                aria-label="Lifecycle filter"
                value={lifecycleFilter}
                onChange={(event) => setLifecycleFilter(event.target.value as LifecycleFilter)}
              >
                <option value="all">All lifecycle states</option>
                <option value="active">Active</option>
                <option value="maintenance">Maintenance</option>
                <option value="inactive">Inactive</option>
                <option value="registered">Registered</option>
              </select>
            </label>

            <label className="hes-toolbar-field">
              <span>Signal</span>
              <select
                aria-label="Signal filter"
                value={signalFilter}
                onChange={(event) => setSignalFilter(event.target.value as SignalFilter)}
              >
                <option value="all">All signal states</option>
                <option value="online">Online</option>
                <option value="warning">Stale / degraded</option>
                <option value="offline">Offline</option>
              </select>
            </label>

            <label className="hes-toolbar-field">
              <span>GIS mapping</span>
              <select
                aria-label="GIS mapping filter"
                value={mappingFilter}
                onChange={(event) => setMappingFilter(event.target.value as MappingFilter)}
              >
                <option value="all">All mapping states</option>
                <option value="mapped">Mapped</option>
                <option value="service_point_only">Service point only</option>
                <option value="unlinked">Unlinked</option>
              </select>
            </label>

            <button className="primary-button" disabled={isLoadingMeters} type="submit">
              {isLoadingMeters ? "Loading..." : "Apply search"}
            </button>
          </form>
        </FilterToolbar>

        <div className="artifact-row">
          <button
            className="secondary-button"
            disabled={filteredRows.length === 0}
            onClick={selectVisibleMeters}
            type="button"
          >
            Select visible
          </button>
          <button
            className="secondary-button"
            disabled={selectedMeterIds.length === 0}
            onClick={() => setSelectedMeterIds([])}
            type="button"
          >
            Clear selection
          </button>
          {selectedMeterIds.length > 0 ? (
            <Link className="primary-button" href={selectedMetersCommandsHref}>
              Open bulk commands
            </Link>
          ) : (
            <button className="primary-button" disabled type="button">
              Open bulk commands
            </button>
          )}
        </div>
      </div>

      <DataTableShell
        title="Meter registry"
        description="Authoritative inventory table using the current meter, GIS, readings, command, and alarm contracts."
        aside={
          <div className="artifact-row">
            <Link className="secondary-button" href="/meters/import">
              Import meters
            </Link>
          </div>
        }
        footer={
          <div className="hes-table-pagination">
            <div>
              Showing {pageIndex * PAGE_SIZE + 1}-{Math.min((pageIndex + 1) * PAGE_SIZE, totalMeters)} of{" "}
              {totalMeters}
            </div>
            <div className="artifact-row">
              <button
                className="secondary-button"
                disabled={pageIndex === 0}
                onClick={() => setPageIndex((current) => Math.max(current - 1, 0))}
                type="button"
              >
                Previous
              </button>
              <span className="artifact-pill">
                Page {pageIndex + 1} of {totalPages}
              </span>
              <button
                className="secondary-button"
                disabled={pageIndex >= totalPages - 1}
                onClick={() =>
                  setPageIndex((current) => (current < totalPages - 1 ? current + 1 : current))
                }
                type="button"
              >
                Next
              </button>
            </div>
          </div>
        }
      >
        {isLoadingMeters && rows.length === 0 ? (
          <p className="hes-empty-copy">Loading meter registry...</p>
        ) : filteredRows.length === 0 ? (
          <p className="hes-empty-copy">No meters matched the current search and filters.</p>
        ) : (
          <table className="hes-data-table">
            <thead>
              <tr>
                <th aria-label="Select meter" />
                <th>Meter</th>
                <th>Internal ID</th>
                <th>Manufacturer / model</th>
                <th>Comm / protocol</th>
                <th>Firmware</th>
                <th>Signal</th>
                <th>Last seen</th>
                <th>Last read</th>
                <th>Command state</th>
                <th>Alarm state</th>
                <th>Consumer / account</th>
                <th>Transformer / service point</th>
                <th>GIS</th>
                <th>Lifecycle</th>
                <th>Actions</th>
              </tr>
            </thead>
            <tbody>
              {filteredRows.map((row) => (
                <tr key={row.meter.id}>
                  <td>
                    <input
                      aria-label={`Select ${row.meter.serial_number}`}
                      checked={selectedMeterIds.includes(row.meter.id)}
                      onChange={() => toggleMeterSelection(row.meter.id)}
                      type="checkbox"
                    />
                  </td>
                  <td>
                    <div className="hes-table-identity">
                      <strong>{row.meter.serial_number}</strong>
                      <span>{row.meter.utility_meter_number ?? row.meter.badge_number ?? "No utility number"}</span>
                    </div>
                  </td>
                  <td className="hes-mono">{row.meter.id}</td>
                  <td>
                    <div className="hes-table-identity">
                      <strong>{row.meter.manufacturer_code}</strong>
                      <span>{row.meter.meter_model_code}</span>
                    </div>
                  </td>
                  <td>
                    <div className="hes-table-identity">
                      <strong>{row.communicationType}</strong>
                      <span>{row.protocolType}</span>
                    </div>
                  </td>
                  <td>{row.meter.firmware_version ?? "Not assigned"}</td>
                  <td>
                    <StatusChip label={row.signalLabel} tone={row.signalTone} />
                  </td>
                  <td>{formatDateTime(row.meter.last_seen_at)}</td>
                  <td>
                    <div className="hes-table-identity">
                      <strong className={`hes-tone-${row.lastReadTone}`}>
                        {row.lastReadAt ? formatDateTime(row.lastReadAt) : "No recent read"}
                      </strong>
                      <span>{row.lastReadAt ? "Latest captured read" : "Read activity unavailable"}</span>
                    </div>
                  </td>
                  <td>
                    <div className="hes-table-identity">
                      <strong className={`hes-tone-${row.commandStateTone}`}>{row.commandStateLabel}</strong>
                      <span>{row.commandUpdatedAt ? formatDateTime(row.commandUpdatedAt) : "No recent command"}</span>
                    </div>
                  </td>
                  <td>
                    <StatusChip label={row.alarmStateLabel} tone={row.alarmStateTone} />
                  </td>
                  <td>
                    <div className="hes-table-identity">
                      <strong>{row.linkedConsumer}</strong>
                      <span>{row.linkedAccount}</span>
                    </div>
                  </td>
                  <td>
                    <div className="hes-table-identity">
                      <strong>{row.meter.transformer_id ?? "No transformer"}</strong>
                      <span>{row.servicePointCode ?? "No service point"}</span>
                    </div>
                  </td>
                  <td>
                    <StatusChip label={row.gisLabel} tone={row.gisTone} />
                  </td>
                  <td>
                    <StatusChip
                      label={formatStatusLabel(row.meter.current_status)}
                      tone={getStatusTone(row.meter.current_status)}
                    />
                  </td>
                  <td>
                    <div className="artifact-row">
                      <Link className="secondary-button" href={`/meters/${row.meter.id}`}>
                        Open detail
                      </Link>
                      <Link
                        className="secondary-button"
                        href={`/commands?meterIds=${encodeURIComponent(row.meter.id)}&meterScopeSource=single_meter_row`}
                      >
                        Commands
                      </Link>
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </DataTableShell>
    </div>
  );
}
