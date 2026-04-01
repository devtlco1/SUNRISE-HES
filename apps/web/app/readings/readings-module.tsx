"use client";

import Link from "next/link";
import { useCallback, useEffect, useMemo, useState } from "react";

import type { AuthorizedFetch } from "../operational-shell";

type MeterItem = {
  id: string;
  serial_number: string;
  utility_meter_number: string | null;
  manufacturer_code: string;
  meter_model_code: string;
  communication_profile_code: string | null;
  meter_profile_code: string | null;
  current_status: string;
  last_seen_at: string | null;
  is_active: boolean;
};

type MeterListResponse = {
  total: number;
  items: MeterItem[];
};

type MeterReadingItem = {
  id: string;
  batch_id: string;
  meter_id: string;
  obis_code: string;
  reading_type: string;
  value_numeric: string | null;
  value_text: string | null;
  value_timestamp: string | null;
  unit: string | null;
  quality: string | null;
  captured_at: string;
  metadata: Record<string, unknown> | null;
};

type MeterReadingListResponse = {
  total: number;
  items: MeterReadingItem[];
};

type MeterRegisterSnapshotItem = {
  id: string;
  meter_id: string;
  related_batch_id: string;
  snapshot_type: string;
  captured_at: string;
  payload: Record<string, unknown>;
  checksum: string | null;
};

type MeterRegisterSnapshotListResponse = {
  total: number;
  items: MeterRegisterSnapshotItem[];
};

type MeterReadingBatchItem = {
  id: string;
  meter_id: string;
  source_type: string;
  captured_at: string;
  received_at: string;
  status: string;
  reading_context: Record<string, unknown> | null;
  correlation_id: string | null;
};

type MeterReadingBatchListResponse = {
  total: number;
  items: MeterReadingBatchItem[];
};

function formatDateTime(value: string | null): string {
  if (!value) {
    return "Not available";
  }

  const date = new Date(value);
  if (Number.isNaN(date.getTime())) {
    return value;
  }
  return date.toLocaleString();
}

function formatStatusLabel(value: string | null): string {
  if (!value) {
    return "Not recorded";
  }

  return value
    .split("_")
    .filter(Boolean)
    .map((part) => part.charAt(0).toUpperCase() + part.slice(1))
    .join(" ");
}

function buildStatusTone(value: string | null): "positive" | "warning" | "danger" | "neutral" {
  const normalized = value?.toLowerCase() ?? "";
  if (
    normalized.includes("succeed") ||
    normalized.includes("complete") ||
    normalized.includes("processed") ||
    normalized.includes("received") ||
    normalized.includes("active")
  ) {
    return "positive";
  }
  if (
    normalized.includes("fail") ||
    normalized.includes("error") ||
    normalized.includes("invalid") ||
    normalized.includes("inactive")
  ) {
    return "danger";
  }
  if (
    normalized.includes("pending") ||
    normalized.includes("queued") ||
    normalized.includes("running") ||
    normalized.includes("review")
  ) {
    return "warning";
  }
  return "neutral";
}

function formatPayloadKey(value: string): string {
  return value
    .split("_")
    .filter(Boolean)
    .map((part) => part.charAt(0).toUpperCase() + part.slice(1))
    .join(" ");
}

function formatPayloadValue(value: unknown): string {
  if (value === null || value === undefined) {
    return "Not available";
  }
  if (typeof value === "string" || typeof value === "number" || typeof value === "boolean") {
    return String(value);
  }
  if (Array.isArray(value)) {
    return value.map((item) => formatPayloadValue(item)).join(", ");
  }
  return JSON.stringify(value);
}

function formatBillingPrimaryValue(payload: Record<string, unknown>): string {
  const firstEntry = Object.entries(payload).find(([, value]) => value !== null && value !== undefined);
  if (!firstEntry) {
    return "No payload value";
  }

  const [key, value] = firstEntry;
  return `${formatPayloadKey(key)}: ${formatPayloadValue(value)}`;
}

function formatBillingSummary(payload: Record<string, unknown>): string {
  const summaryEntries = Object.entries(payload)
    .filter(([, value]) => value !== null && value !== undefined)
    .slice(0, 2);

  if (summaryEntries.length === 0) {
    return "No structured billing payload recorded.";
  }

  return summaryEntries
    .map(([key, value]) => `${formatPayloadKey(key)} ${formatPayloadValue(value)}`)
    .join(" • ");
}

function formatReadingValue(reading: MeterReadingItem): string {
  if (reading.value_numeric !== null) {
    return `${reading.value_numeric}${reading.unit ? ` ${reading.unit}` : ""}`;
  }
  if (reading.value_text) {
    return reading.value_text;
  }
  if (reading.value_timestamp) {
    return formatDateTime(reading.value_timestamp);
  }
  return "Not available";
}

export function ReadingsModule({
  authorizedFetch,
  initialMeterId = null,
}: {
  authorizedFetch: AuthorizedFetch;
  initialMeterId?: string | null;
}) {
  const [meters, setMeters] = useState<MeterItem[]>([]);
  const [meterSearchQuery, setMeterSearchQuery] = useState("");
  const [selectedMeterId, setSelectedMeterId] = useState<string | null>(null);
  const [totalMeters, setTotalMeters] = useState(0);
  const [meterReadings, setMeterReadings] = useState<MeterReadingItem[]>([]);
  const [billingSnapshots, setBillingSnapshots] = useState<MeterRegisterSnapshotItem[]>([]);
  const [readingBatches, setReadingBatches] = useState<MeterReadingBatchItem[]>([]);
  const [pageError, setPageError] = useState<string | null>(null);
  const [detailError, setDetailError] = useState<string | null>(null);
  const [isLoadingOverview, setIsLoadingOverview] = useState(false);
  const [isLoadingDetail, setIsLoadingDetail] = useState(false);
  const handedOffMeterId = initialMeterId?.trim() || null;

  const loadMeters = useCallback(async () => {
    setIsLoadingOverview(true);
    setPageError(null);

    try {
      const response = await authorizedFetch<MeterListResponse>("/api/v1/meters?offset=0&limit=20");
      setMeters(response.items);
      setTotalMeters(response.total);
      setSelectedMeterId((currentSelectedMeterId) => {
        if (
          currentSelectedMeterId &&
          response.items.some((item) => item.id === currentSelectedMeterId)
        ) {
          return currentSelectedMeterId;
        }
        if (
          handedOffMeterId &&
          response.items.some((item) => item.id === handedOffMeterId)
        ) {
          return handedOffMeterId;
        }
        return response.items[0]?.id ?? null;
      });
    } catch (error) {
      setMeters([]);
      setTotalMeters(0);
      setSelectedMeterId(null);
      setPageError(
        error instanceof Error ? error.message : "Unable to load readings overview.",
      );
    } finally {
      setIsLoadingOverview(false);
    }
  }, [authorizedFetch, handedOffMeterId]);

  const loadSelectedMeterContext = useCallback(
    async (meterId: string) => {
      setIsLoadingDetail(true);
      setDetailError(null);

      const [readingsResult, snapshotsResult, batchesResult] = await Promise.allSettled([
        authorizedFetch<MeterReadingListResponse>(`/api/v1/meters/${meterId}/readings?limit=10`),
        authorizedFetch<MeterRegisterSnapshotListResponse>(
          `/api/v1/meters/${meterId}/register-snapshots?limit=25`,
        ),
        authorizedFetch<MeterReadingBatchListResponse>(
          `/api/v1/meters/${meterId}/reading-batches?limit=25`,
        ),
      ]);

      if (readingsResult.status === "fulfilled") {
        setMeterReadings(readingsResult.value.items);
      } else {
        setMeterReadings([]);
      }

      if (snapshotsResult.status === "fulfilled") {
        setBillingSnapshots(
          snapshotsResult.value.items.filter((item) => item.snapshot_type === "billing"),
        );
      } else {
        setBillingSnapshots([]);
      }

      if (batchesResult.status === "fulfilled") {
        setReadingBatches(
          batchesResult.value.items.map((item) => ({
            id: item.id,
            meter_id: item.meter_id,
            source_type: item.source_type,
            captured_at: item.captured_at,
            received_at: item.received_at,
            status: item.status,
            reading_context: item.reading_context,
            correlation_id: item.correlation_id,
          })),
        );
      } else {
        setReadingBatches([]);
      }

      const failedResults = [readingsResult, snapshotsResult, batchesResult].filter(
        (result): result is PromiseRejectedResult => result.status === "rejected",
      );

      if (failedResults.length === 3) {
        const firstError = failedResults[0]?.reason;
        setDetailError(
          firstError instanceof Error
            ? firstError.message
            : "Unable to load meter readings context.",
        );
      } else if (failedResults.length > 0) {
        setDetailError("Unable to load complete readings context.");
      }

      setIsLoadingDetail(false);
    },
    [authorizedFetch],
  );

  useEffect(() => {
    void loadMeters();
  }, [loadMeters]);

  useEffect(() => {
    if (!selectedMeterId) {
      setMeterReadings([]);
      setBillingSnapshots([]);
      setReadingBatches([]);
      setDetailError(null);
      return;
    }

    void loadSelectedMeterContext(selectedMeterId);
  }, [loadSelectedMeterContext, selectedMeterId]);

  const filteredMeters = useMemo(() => {
    const normalizedQuery = meterSearchQuery.trim().toLowerCase();
    if (!normalizedQuery) {
      return meters;
    }

    return meters.filter((meter) =>
      [
        meter.serial_number,
        meter.utility_meter_number,
        meter.manufacturer_code,
        meter.meter_model_code,
        meter.communication_profile_code,
        meter.meter_profile_code,
        meter.id,
      ]
        .filter(Boolean)
        .some((value) => String(value).toLowerCase().includes(normalizedQuery)),
    );
  }, [meterSearchQuery, meters]);

  useEffect(() => {
    setSelectedMeterId((currentSelectedMeterId) => {
      if (filteredMeters.length === 0) {
        return null;
      }
      if (
        currentSelectedMeterId &&
        filteredMeters.some((meter) => meter.id === currentSelectedMeterId)
      ) {
        return currentSelectedMeterId;
      }
      if (
        handedOffMeterId &&
        filteredMeters.some((meter) => meter.id === handedOffMeterId)
      ) {
        return handedOffMeterId;
      }
      return filteredMeters[0]?.id ?? null;
    });
  }, [filteredMeters, handedOffMeterId]);

  const selectedMeter = useMemo(
    () => meters.find((meter) => meter.id === selectedMeterId) ?? null,
    [meters, selectedMeterId],
  );

  const batchById = useMemo(
    () => new Map(readingBatches.map((batch) => [batch.id, batch])),
    [readingBatches],
  );

  const latestBillingSnapshot = billingSnapshots[0] ?? null;
  const latestReading = meterReadings[0] ?? null;
  const latestBillingBatch = latestBillingSnapshot
    ? batchById.get(latestBillingSnapshot.related_batch_id) ?? null
    : null;
  const latestBillingPrimaryValue = latestBillingSnapshot
    ? formatBillingPrimaryValue(latestBillingSnapshot.payload)
    : "No billing read recorded";
  const latestBillingContextLabel = latestBillingSnapshot
    ? "Billing-read context available"
    : "Billing-read context missing";

  const overviewCards = useMemo(
    () => [
      {
        label: "Meters in current result set",
        value: String(filteredMeters.length),
        note: meterSearchQuery.trim()
          ? `${filteredMeters.length} of ${totalMeters} meters match the current filter`
          : `${totalMeters} meters currently in scope`,
      },
      {
        label: "Meters with recent signal",
        value: String(filteredMeters.filter((meter) => meter.last_seen_at !== null).length),
        note: meterSearchQuery.trim()
          ? "Based on the current filtered meter list"
          : "Based on the current bounded meter list",
      },
      {
        label: "Selected meter",
        value: selectedMeter?.serial_number ?? "No selection",
        note: selectedMeter
          ? formatStatusLabel(selectedMeter.current_status)
          : "Choose a meter to inspect readings",
      },
      {
        label: "Billing reads loaded",
        value: String(billingSnapshots.length),
        note: selectedMeter
          ? `Billing register snapshots for ${selectedMeter.serial_number}`
          : "No selected meter billing context",
      },
      {
        label: "Latest billing read",
        value: latestBillingSnapshot
          ? formatDateTime(latestBillingSnapshot.captured_at)
          : "Not available",
        note: latestBillingSnapshot
          ? formatBillingPrimaryValue(latestBillingSnapshot.payload)
          : "No billing read recorded",
      },
      {
        label: "Recent raw readings loaded",
        value: String(meterReadings.length),
        note: latestReading
          ? `${latestReading.obis_code} • ${formatReadingValue(latestReading)}`
          : "No recent reading value recorded",
      },
    ],
    [
      billingSnapshots.length,
      filteredMeters,
      latestBillingSnapshot,
      latestReading,
      meterReadings.length,
      meterSearchQuery,
      selectedMeter,
      totalMeters,
    ],
  );

  return (
    <section className="panel">
      {pageError ? <p className="error-banner">{pageError}</p> : null}
      {detailError ? <p className="error-banner">{detailError}</p> : null}

      <div className="detail-stack">
        <section className="subpanel readings-overview-panel">
          <div className="section-heading">
            <div>
              <h2>Readings operations center</h2>
              <p className="muted">
                Phase 2 entry slice for meter readings visibility, starting with a bounded
                overview and billing-read scanability over the existing readings contracts.
              </p>
            </div>
            <span className="artifact-pill">
              {selectedMeter
                ? handedOffMeterId && selectedMeter.id === handedOffMeterId
                  ? `Meter handoff preserved for ${selectedMeter.serial_number}`
                  : `Focused on ${selectedMeter.serial_number}`
                : "Awaiting meter selection"}
            </span>
          </div>

          {isLoadingOverview ? <p className="muted">Loading readings overview...</p> : null}

          {!isLoadingOverview ? (
            <div className="readings-overview-grid">
              {overviewCards.map((card) => (
                <div key={card.label} className="stat-card readings-overview-card">
                  <span className="stat-label">{card.label}</span>
                  <strong>{card.value}</strong>
                  <p className="muted">{card.note}</p>
                </div>
              ))}
            </div>
          ) : null}
        </section>

        <div className="readings-module-layout">
          <section className="subpanel">
            <div className="section-heading">
              <div>
                <h2>Meters in readings scope</h2>
                <p className="muted">
                  Start from the bounded meter list, then inspect recent readings and
                  billing snapshots for one meter at a time.
                </p>
              </div>
            </div>

            <div className="inline-form">
              <label className="field">
                <span>Meter filter</span>
                <input
                  aria-label="Meter filter"
                  onChange={(event) => setMeterSearchQuery(event.target.value)}
                  placeholder="Search serial, utility number, profile, or meter ID"
                  type="search"
                  value={meterSearchQuery}
                />
              </label>
            </div>

            {isLoadingOverview ? <p className="muted">Loading readings-focused meters...</p> : null}

            <div className="meter-list">
              {!isLoadingOverview && meters.length === 0 ? (
                <p className="muted">No readings overview items available.</p>
              ) : null}

              {!isLoadingOverview && meters.length > 0 && filteredMeters.length === 0 ? (
                <p className="muted">
                  No meters match the current filter. Clear the search to inspect billing
                  reads.
                </p>
              ) : null}

              {filteredMeters.map((meter) => (
                <article
                  key={meter.id}
                  className={
                    selectedMeterId === meter.id
                      ? "meter-list-item readings-list-item selected"
                      : "meter-list-item readings-list-item"
                  }
                >
                  <div className="command-list-item-header">
                    <strong>{meter.serial_number}</strong>
                    <span className={`status-pill ${buildStatusTone(meter.current_status)}`}>
                      {formatStatusLabel(meter.current_status)}
                    </span>
                  </div>

                  <div className="connectivity-row-badges">
                    <span className="artifact-pill">
                      {meter.communication_profile_code ??
                        meter.meter_profile_code ??
                        "No profile summary"}
                    </span>
                    <span className="artifact-pill">
                      Last seen {formatDateTime(meter.last_seen_at)}
                    </span>
                  </div>

                  <div className="command-list-item-meta">
                    <span>Meter ID {meter.id}</span>
                    <span>{meter.utility_meter_number ?? "No utility meter number"}</span>
                  </div>
                  <div className="command-list-item-meta">
                    <span>
                      {meter.manufacturer_code} / {meter.meter_model_code}
                    </span>
                    <span>{meter.is_active ? "Active in scope" : "Inactive in scope"}</span>
                  </div>

                  <div className="connectivity-row-actions">
                    <button
                      className="secondary-button"
                      onClick={() => setSelectedMeterId(meter.id)}
                      type="button"
                    >
                      Inspect readings
                    </button>
                    <Link className="nav-link" href={`/meters/${meter.id}`}>
                      Open meter detail
                    </Link>
                  </div>
                </article>
              ))}
            </div>
          </section>

          <section className="subpanel">
            <div className="section-heading">
              <div>
                <h2>Billing reads</h2>
                <p className="muted">
                  Bounded billing snapshot visibility for the selected meter using the
                  existing register snapshot and reading-batch contracts.
                </p>
              </div>
            </div>

            {isLoadingDetail ? <p className="muted">Loading selected meter readings...</p> : null}

            {selectedMeter ? (
              <div className="detail-stack">
                <section className="readings-detail-hero">
                  <div className="readings-detail-title-row">
                    <div>
                      <p className="eyebrow">Selected Meter</p>
                      <h3>{selectedMeter.serial_number}</h3>
                      <p className="muted">
                        {latestBillingSnapshot
                          ? `Latest billing read captured ${formatDateTime(
                              latestBillingSnapshot.captured_at,
                            )} with ${latestBillingPrimaryValue}.`
                          : "No billing-read context recorded yet for the selected meter."}
                      </p>
                    </div>
                    <span className={`status-pill ${buildStatusTone(selectedMeter.current_status)}`}>
                      {formatStatusLabel(selectedMeter.current_status)}
                    </span>
                  </div>

                  <div className="connectivity-row-badges">
                    <span className="artifact-pill">
                      {billingSnapshots.length} billing reads
                    </span>
                    <span className="artifact-pill">{latestBillingContextLabel}</span>
                    <span className={`status-pill ${buildStatusTone(latestBillingBatch?.status ?? null)}`}>
                      {billingSnapshots.length > 0
                        ? `Latest batch ${formatStatusLabel(latestBillingBatch?.status ?? null)}`
                        : "No billing batch yet"}
                    </span>
                    <span className="artifact-pill">
                      {meterReadings.length} recent raw readings
                    </span>
                    <span className="artifact-pill">
                      Last signal {formatDateTime(selectedMeter.last_seen_at)}
                    </span>
                  </div>
                </section>

                <div className="detail-grid">
                  <div className="stat-card">
                    <span className="stat-label">Meter ID</span>
                    <strong>{selectedMeter.id}</strong>
                  </div>
                  <div className="stat-card">
                    <span className="stat-label">Utility meter number</span>
                    <strong>{selectedMeter.utility_meter_number ?? "Not available"}</strong>
                  </div>
                  <div className="stat-card">
                    <span className="stat-label">Manufacturer / model</span>
                    <strong>
                      {selectedMeter.manufacturer_code} / {selectedMeter.meter_model_code}
                    </strong>
                  </div>
                  <div className="stat-card">
                    <span className="stat-label">Profile summary</span>
                    <strong>
                      {selectedMeter.communication_profile_code ??
                        selectedMeter.meter_profile_code ??
                        "No profile summary"}
                    </strong>
                  </div>
                  <div className="stat-card">
                    <span className="stat-label">Latest billing read</span>
                    <strong>
                      {latestBillingSnapshot
                        ? formatDateTime(latestBillingSnapshot.captured_at)
                        : "Not available"}
                    </strong>
                  </div>
                  <div className="stat-card">
                    <span className="stat-label">Billing-read context</span>
                    <strong>{latestBillingContextLabel}</strong>
                  </div>
                  <div className="stat-card">
                    <span className="stat-label">Latest billing value</span>
                    <strong>{latestBillingPrimaryValue}</strong>
                  </div>
                  <div className="stat-card">
                    <span className="stat-label">Latest billing source</span>
                    <strong>
                      {latestBillingBatch
                        ? formatStatusLabel(latestBillingBatch.source_type)
                        : "Not available"}
                    </strong>
                  </div>
                  <div className="stat-card">
                    <span className="stat-label">Latest billing received</span>
                    <strong>{formatDateTime(latestBillingBatch?.received_at ?? null)}</strong>
                  </div>
                  <div className="stat-card">
                    <span className="stat-label">Latest raw reading</span>
                    <strong>
                      {latestReading
                        ? `${latestReading.obis_code} • ${formatReadingValue(latestReading)}`
                        : "Not available"}
                    </strong>
                  </div>
                </div>

                <div className="artifact-row">
                  <Link className="primary-button" href={`/meters/${selectedMeter.id}`}>
                    Return to meter detail
                  </Link>
                </div>

                <section className="subpanel">
                  <div className="section-heading">
                    <div>
                      <h3>Billing reads table</h3>
                      <p className="muted">
                        Status, value, and timestamp scanability for the latest billing
                        snapshots only.
                      </p>
                    </div>
                    <span className="artifact-pill">Newest first</span>
                  </div>

                  {billingSnapshots.length === 0 ? (
                    <p className="muted">
                      No billing reads available for the selected meter yet. The selected
                      meter summary above reflects the current missing billing-read context.
                    </p>
                  ) : (
                    <div className="readings-table-shell">
                      <table className="readings-table">
                        <thead>
                          <tr>
                            <th scope="col">Captured at</th>
                            <th scope="col">Batch status</th>
                            <th scope="col">Received at</th>
                            <th scope="col">Primary value</th>
                            <th scope="col">Summary</th>
                          </tr>
                        </thead>
                        <tbody>
                          {billingSnapshots.map((snapshot, index) => {
                            const relatedBatch = batchById.get(snapshot.related_batch_id) ?? null;
                            const isLatestSnapshot = index === 0;
                            return (
                              <tr
                                key={snapshot.id}
                                className={
                                  isLatestSnapshot
                                    ? "readings-table-row readings-table-row-latest"
                                    : "readings-table-row"
                                }
                              >
                                <td>
                                  <strong>{formatDateTime(snapshot.captured_at)}</strong>
                                  <div className="artifact-row">
                                    {isLatestSnapshot ? (
                                      <span className="artifact-pill">Latest billing read</span>
                                    ) : null}
                                    <span className="muted">Billing snapshot</span>
                                  </div>
                                </td>
                                <td>
                                  <div className="detail-stack">
                                    <span
                                      className={`status-pill ${buildStatusTone(
                                        relatedBatch?.status ?? null,
                                      )}`}
                                    >
                                      {formatStatusLabel(relatedBatch?.status ?? null)}
                                    </span>
                                    <span className="muted">
                                      {relatedBatch
                                        ? `Source ${formatStatusLabel(relatedBatch.source_type)}`
                                        : "No batch context"}
                                    </span>
                                  </div>
                                </td>
                                <td>
                                  <strong>{formatDateTime(relatedBatch?.received_at ?? null)}</strong>
                                  <div className="muted">
                                    {relatedBatch
                                      ? "Batch receipt recorded"
                                      : "Receipt not recorded"}
                                  </div>
                                </td>
                                <td>
                                  <strong>{formatBillingPrimaryValue(snapshot.payload)}</strong>
                                  <div className="muted">Current primary billing value</div>
                                </td>
                                <td>
                                  <strong>{formatBillingSummary(snapshot.payload)}</strong>
                                  {snapshot.checksum ? (
                                    <div className="muted">Checksum {snapshot.checksum}</div>
                                  ) : null}
                                </td>
                              </tr>
                            );
                          })}
                        </tbody>
                      </table>
                    </div>
                  )}
                </section>

                <section className="subpanel">
                  <div className="section-heading">
                    <div>
                      <h3>Recent reading context</h3>
                      <p className="muted">
                        Lightweight raw-reading context to keep the overview truthful without
                        broadening into the full readings architecture.
                      </p>
                    </div>
                  </div>

                  {meterReadings.length === 0 ? (
                    <p className="muted">No recent reading values available for the selected meter.</p>
                  ) : (
                    <div className="readings-table-shell">
                      <table className="readings-table">
                        <thead>
                          <tr>
                            <th scope="col">OBIS</th>
                            <th scope="col">Type</th>
                            <th scope="col">Value</th>
                            <th scope="col">Captured</th>
                          </tr>
                        </thead>
                        <tbody>
                          {meterReadings.map((reading) => (
                            <tr key={reading.id}>
                              <td>{reading.obis_code}</td>
                              <td>{formatStatusLabel(reading.reading_type)}</td>
                              <td>{formatReadingValue(reading)}</td>
                              <td>{formatDateTime(reading.captured_at)}</td>
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    </div>
                  )}
                </section>
              </div>
            ) : (
              <p className="muted">
                {meters.length > 0 && filteredMeters.length === 0
                  ? "Adjust or clear the meter filter to restore a selected meter."
                  : "Select a meter to inspect its readings overview and billing reads."}
              </p>
            )}
          </section>
        </div>
      </div>
    </section>
  );
}
