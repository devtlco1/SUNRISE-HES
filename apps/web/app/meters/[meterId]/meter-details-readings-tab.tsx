"use client";

import Link from "next/link";
import { useMemo } from "react";

type MeterDetail = {
  id: string;
  serial_number: string;
};

type LoadProfileChannel = {
  id: string;
  channel_code: string;
  obis_code: string;
  interval_seconds: number;
  unit?: string | null;
  is_active: boolean;
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

type MeterRegisterSnapshotItem = {
  id: string;
  meter_id: string;
  related_batch_id: string;
  snapshot_type: string;
  captured_at: string;
  payload: Record<string, unknown>;
  checksum: string | null;
};

type LoadProfileIntervalItem = {
  id: string;
  meter_id: string;
  channel_id: string;
  interval_start: string;
  interval_end: string;
  value_numeric: string | null;
  quality: string | null;
  source_batch_id: string | null;
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
    .split(/[_\s/.-]+/)
    .filter(Boolean)
    .map((part) => part.charAt(0).toUpperCase() + part.slice(1))
    .join(" ");
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

function formatIntervalValue(
  interval: LoadProfileIntervalItem,
  channel: LoadProfileChannel | null,
): string {
  if (interval.value_numeric === null) {
    return "Not available";
  }

  return `${interval.value_numeric}${channel?.unit ? ` ${channel.unit}` : ""}`;
}

function formatIntervalWindow(interval: LoadProfileIntervalItem): string {
  return `${formatDateTime(interval.interval_start)} to ${formatDateTime(interval.interval_end)}`;
}

function formatDurationFromMs(durationMs: number): string {
  const clampedDurationMs = Math.max(durationMs, 0);
  const totalMinutes = Math.floor(clampedDurationMs / 60_000);

  if (totalMinutes < 60) {
    return totalMinutes <= 1 ? "1 minute" : `${totalMinutes} minutes`;
  }

  const totalHours = Math.floor(totalMinutes / 60);
  if (totalHours < 24) {
    return totalHours === 1 ? "1 hour" : `${totalHours} hours`;
  }

  const totalDays = Math.floor(totalHours / 24);
  return totalDays === 1 ? "1 day" : `${totalDays} days`;
}

function buildReadingFreshnessLabel(latestReading: MeterReadingItem | null): string {
  if (!latestReading) {
    return "No raw reading recorded";
  }

  const capturedAt = new Date(latestReading.captured_at);
  if (Number.isNaN(capturedAt.getTime())) {
    return "Freshness unavailable";
  }

  const ageMs = Date.now() - capturedAt.getTime();
  if (ageMs <= 4 * 60 * 60 * 1000) {
    return `Fresh within ${formatDurationFromMs(ageMs)}`;
  }
  if (ageMs <= 24 * 60 * 60 * 1000) {
    return `Recent within ${formatDurationFromMs(ageMs)}`;
  }
  return `Stale for ${formatDurationFromMs(ageMs)}`;
}

export function MeterDetailsReadingsTab({
  meterId,
  meter,
  meterReadings,
  billingSnapshots,
  loadProfileIntervals,
  loadProfileChannels,
  isLoadingReadingsContext,
  readingsContextError,
}: {
  meterId: string;
  meter: MeterDetail | null;
  meterReadings: MeterReadingItem[];
  billingSnapshots: MeterRegisterSnapshotItem[];
  loadProfileIntervals: LoadProfileIntervalItem[];
  loadProfileChannels: LoadProfileChannel[];
  isLoadingReadingsContext: boolean;
  readingsContextError: string | null;
}) {
  const loadProfileChannelById = useMemo(
    () => new Map(loadProfileChannels.map((channel) => [channel.id, channel])),
    [loadProfileChannels],
  );
  const activeLoadProfileChannels = useMemo(
    () => loadProfileChannels.filter((channel) => channel.is_active),
    [loadProfileChannels],
  );
  const latestReading = meterReadings[0] ?? null;
  const latestBillingSnapshot = billingSnapshots[0] ?? null;
  const latestInterval = loadProfileIntervals[0] ?? null;
  const latestIntervalChannel = latestInterval
    ? loadProfileChannelById.get(latestInterval.channel_id) ?? null
    : null;
  const hasReadingsContext =
    latestReading !== null ||
    latestBillingSnapshot !== null ||
    latestInterval !== null ||
    activeLoadProfileChannels.length > 0;

  const overviewCards = useMemo(
    () => [
      {
        label: "Latest raw reading",
        value: latestReading ? formatReadingValue(latestReading) : "Not available",
        note: latestReading
          ? `${latestReading.obis_code} • ${formatDateTime(latestReading.captured_at)}`
          : "No raw reading recorded for this meter",
      },
      {
        label: "Reading freshness",
        value: buildReadingFreshnessLabel(latestReading),
        note: latestReading
          ? `${formatStatusLabel(latestReading.quality)} quality`
          : "Awaiting a current raw reading",
      },
      {
        label: "Latest billing snapshot",
        value: latestBillingSnapshot
          ? formatBillingPrimaryValue(latestBillingSnapshot.payload)
          : "Not available",
        note: latestBillingSnapshot
          ? formatDateTime(latestBillingSnapshot.captured_at)
          : "No billing snapshot recorded",
      },
      {
        label: "Latest interval",
        value: latestInterval
          ? formatIntervalValue(latestInterval, latestIntervalChannel)
          : "Not available",
        note: latestInterval
          ? `${latestIntervalChannel?.channel_code ?? latestInterval.channel_id} • ${formatIntervalWindow(latestInterval)}`
          : "No interval row recorded",
      },
      {
        label: "Active load-profile channels",
        value: String(activeLoadProfileChannels.length),
        note:
          activeLoadProfileChannels.length > 0
            ? activeLoadProfileChannels
                .slice(0, 3)
                .map((channel) => channel.channel_code)
                .join(", ")
            : "No active load-profile channels",
      },
      {
        label: "Context rows in scope",
        value: `${meterReadings.length} / ${billingSnapshots.length} / ${loadProfileIntervals.length}`,
        note: "Raw readings / billing snapshots / interval rows",
      },
    ],
    [
      activeLoadProfileChannels,
      billingSnapshots.length,
      latestBillingSnapshot,
      latestInterval,
      latestIntervalChannel,
      latestReading,
      loadProfileIntervals.length,
      meterReadings.length,
    ],
  );

  const rawReadingRows = meterReadings.slice(0, 3);

  return (
    <div className="detail-stack">
      {readingsContextError ? <p className="error-banner">{readingsContextError}</p> : null}

      <section className="subpanel audit-center-overview-panel">
        <div className="section-heading">
          <div>
            <h2>Readings context</h2>
            <p className="muted">
              Meter-scoped raw reading, billing snapshot, and interval visibility using
              the existing readings read models only.
            </p>
          </div>
          <div className="artifact-row">
            <span className="artifact-pill">
              {meter ? meter.serial_number : "Meter readings in scope"}
            </span>
            <Link className="secondary-button" href={`/readings?meterId=${meterId}`}>
              Open readings workspace
            </Link>
          </div>
        </div>

        {isLoadingReadingsContext ? <p className="muted">Loading readings context...</p> : null}

        {!isLoadingReadingsContext && hasReadingsContext ? (
          <div className="detail-stack">
            <div className="meter-summary-grid">
              {overviewCards.map((card) => (
                <div key={card.label} className="stat-card">
                  <span className="stat-label">{card.label}</span>
                  <strong>{card.value}</strong>
                  <p className="muted">{card.note}</p>
                </div>
              ))}
            </div>

            <div className="artifact-row">
              <span className="artifact-pill">
                {latestReading
                  ? `Latest reading ${formatStatusLabel(latestReading.reading_type)}`
                  : "No raw reading type recorded"}
              </span>
              <span className="artifact-pill">
                {latestBillingSnapshot
                  ? `Billing snapshot ${formatDateTime(latestBillingSnapshot.captured_at)}`
                  : "No billing snapshot recorded"}
              </span>
              <span className="artifact-pill">
                {latestInterval
                  ? `Latest interval quality ${formatStatusLabel(latestInterval.quality)}`
                  : "No interval quality yet"}
              </span>
            </div>
          </div>
        ) : null}

        {!isLoadingReadingsContext && !hasReadingsContext ? (
          <p className="muted">Readings context not available for this meter yet.</p>
        ) : null}
      </section>

      <section className="subpanel meter-summary-panel">
        <div className="section-heading">
          <div>
            <h2>Recent raw readings</h2>
            <p className="muted">
              Latest raw reading rows for this meter with value, OBIS identity, capture
              time, and quality.
            </p>
          </div>
        </div>

        {isLoadingReadingsContext ? (
          <p className="muted">Loading recent raw readings...</p>
        ) : rawReadingRows.length === 0 ? (
          <section className="audit-center-empty-state">
            <p className="eyebrow">Raw Readings Empty</p>
            <h3>No raw readings are currently recorded for this meter</h3>
            <p className="muted">
              Billing or interval context may still be available, but there is no recent
              raw reading row to review in this bounded meter workspace.
            </p>
          </section>
        ) : (
          <div className="meter-summary-grid">
            {rawReadingRows.map((reading) => (
              <div key={reading.id} className="stat-card">
                <span className="stat-label">{reading.obis_code}</span>
                <strong>{formatReadingValue(reading)}</strong>
                <p className="muted">{formatStatusLabel(reading.reading_type)}</p>
                <p className="muted">Captured {formatDateTime(reading.captured_at)}</p>
                <p className="muted">Quality {formatStatusLabel(reading.quality)}</p>
              </div>
            ))}
          </div>
        )}
      </section>

      <section className="subpanel meter-summary-panel">
        <div className="section-heading">
          <div>
            <h2>Billing and interval follow-through</h2>
            <p className="muted">
              Latest billing and load-profile context for operator follow-through without
              leaving the current meter workspace.
            </p>
          </div>
        </div>

        {isLoadingReadingsContext ? (
          <p className="muted">Loading billing and interval context...</p>
        ) : (
          <div className="meter-summary-grid">
            <div className="stat-card">
              <span className="stat-label">Billing summary</span>
              <strong>
                {latestBillingSnapshot
                  ? formatBillingPrimaryValue(latestBillingSnapshot.payload)
                  : "Not available"}
              </strong>
              <p className="muted">
                {latestBillingSnapshot
                  ? formatBillingSummary(latestBillingSnapshot.payload)
                  : "No billing snapshot recorded for this meter."}
              </p>
            </div>
            <div className="stat-card">
              <span className="stat-label">Interval visibility</span>
              <strong>
                {latestInterval
                  ? formatIntervalValue(latestInterval, latestIntervalChannel)
                  : "Not available"}
              </strong>
              <p className="muted">
                {latestInterval
                  ? formatIntervalWindow(latestInterval)
                  : "No interval row recorded for this meter."}
              </p>
            </div>
            <div className="stat-card">
              <span className="stat-label">Active channels</span>
              <strong>{activeLoadProfileChannels.length}</strong>
              <p className="muted">
                {activeLoadProfileChannels.length > 0
                  ? activeLoadProfileChannels
                      .slice(0, 3)
                      .map((channel) => `${channel.channel_code} (${channel.obis_code})`)
                      .join(", ")
                  : "No active load-profile channel context."}
              </p>
            </div>
          </div>
        )}
      </section>
    </div>
  );
}
