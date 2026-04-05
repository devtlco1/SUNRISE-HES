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

type ValidationIssueSeverity = "critical" | "warning";

type OperationalVisibilityCue = {
  id: string;
  issueType: string;
  severity: ValidationIssueSeverity;
  reason: string;
  observedAt: string | null;
  relatedContext: string;
  relatedSource: string;
  relatedSectionHref: string;
  relatedActionLabel: string;
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
  if (durationMs < 60_000) {
    return `${Math.round(durationMs / 1000)} sec`;
  }
  if (durationMs < 3_600_000) {
    return `${Math.round(durationMs / 60_000)} min`;
  }
  return `${Math.round(durationMs / 3_600_000)} hr`;
}

function formatCountLabel(count: number, singular: string, plural: string): string {
  return `${count} ${count === 1 ? singular : plural}`;
}

function formatIntervalCadenceLabel(intervalSeconds: number | null): string {
  if (!intervalSeconds || intervalSeconds <= 0) {
    return "No interval cadence visible";
  }
  if (intervalSeconds % 3600 === 0) {
    const hours = intervalSeconds / 3600;
    return `${hours} hr cadence`;
  }
  if (intervalSeconds % 60 === 0) {
    const minutes = intervalSeconds / 60;
    return `${minutes} min cadence`;
  }
  return `${intervalSeconds} sec cadence`;
}

function formatValidationIssueType(issueType: string): string {
  return issueType
    .split("_")
    .filter(Boolean)
    .map((part) => part.charAt(0).toUpperCase() + part.slice(1))
    .join(" ");
}

function buildValidationSeverityTone(
  severity: ValidationIssueSeverity,
): "danger" | "warning" {
  return severity === "critical" ? "danger" : "warning";
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
  const readingFreshnessLabel = latestReading
    ? `Captured ${formatDateTime(latestReading.captured_at)}`
    : "No recent raw reading visible";
  const intervalFreshnessLabel = latestInterval
    ? `Window ended ${formatDateTime(latestInterval.interval_end)}`
    : "No interval horizon visible";
  const intervalCadenceLabel = latestIntervalChannel
    ? formatIntervalCadenceLabel(latestIntervalChannel.interval_seconds)
    : activeLoadProfileChannels[0]
      ? formatIntervalCadenceLabel(activeLoadProfileChannels[0].interval_seconds)
      : "No interval cadence visible";
  const intervalLagMs =
    latestInterval && latestReading
      ? new Date(latestReading.captured_at).getTime() -
        new Date(latestInterval.interval_end).getTime()
      : null;
  const intervalLagLabel =
    intervalLagMs === null
      ? "Not available"
      : intervalLagMs > 0
        ? `Lag ${formatDurationFromMs(intervalLagMs)}`
        : intervalLagMs < 0
          ? `Lead ${formatDurationFromMs(Math.abs(intervalLagMs))}`
          : "Aligned";
  const latestBillingContextLabel = latestBillingSnapshot
    ? "Billing snapshot context available"
    : "Billing snapshot context missing";
  const hasReadingsContext =
    latestReading !== null ||
    latestBillingSnapshot !== null ||
    latestInterval !== null ||
    activeLoadProfileChannels.length > 0;
  const validationIssues = useMemo(() => {
    const nextIssues: OperationalVisibilityCue[] = [];

    if (latestBillingSnapshot === null) {
      nextIssues.push({
        id: `billing-context-missing-${meterId}`,
        issueType: "billing_context_missing",
        severity: "warning",
        reason: "No billing snapshot is currently available in the meter-scoped readings view.",
        observedAt: null,
        relatedContext: meter?.serial_number ?? meterId,
        relatedSource: "Billing and interval follow-through",
        relatedSectionHref: "#meter-billing-interval-follow-through-section",
        relatedActionLabel: "Review billing follow-through",
      });
    }

    loadProfileIntervals.forEach((interval) => {
      const channel = loadProfileChannelById.get(interval.channel_id) ?? null;
      const relatedContext = channel
        ? `${channel.channel_code} • ${formatIntervalWindow(interval)}`
        : formatIntervalWindow(interval);

      if (interval.value_numeric === null) {
        nextIssues.push({
          id: `interval-value-missing-${interval.id}`,
          issueType: "interval_value_missing",
          severity: "critical",
          reason: "Interval value is missing for the recorded load-profile window.",
          observedAt: interval.interval_end,
          relatedContext,
          relatedSource: "Billing and interval follow-through",
          relatedSectionHref: "#meter-billing-interval-follow-through-section",
          relatedActionLabel: "Review interval follow-through",
        });
      }

      if (
        interval.quality === "suspect" ||
        interval.quality === "estimated" ||
        interval.quality === "missing"
      ) {
        nextIssues.push({
          id: `interval-quality-${interval.id}`,
          issueType: "interval_quality_flagged",
          severity: interval.quality === "estimated" ? "warning" : "critical",
          reason: `Interval quality is marked ${formatStatusLabel(interval.quality)}.`,
          observedAt: interval.interval_end,
          relatedContext,
          relatedSource: "Billing and interval follow-through",
          relatedSectionHref: "#meter-billing-interval-follow-through-section",
          relatedActionLabel: "Review interval follow-through",
        });
      }
    });

    const intervalsByChannel = new Map<string, LoadProfileIntervalItem[]>();
    loadProfileIntervals.forEach((interval) => {
      const items = intervalsByChannel.get(interval.channel_id) ?? [];
      items.push(interval);
      intervalsByChannel.set(interval.channel_id, items);
    });

    intervalsByChannel.forEach((intervals, channelId) => {
      const sortedIntervals = [...intervals].sort(
        (left, right) =>
          new Date(right.interval_start).getTime() -
          new Date(left.interval_start).getTime(),
      );
      const channel = loadProfileChannelById.get(channelId) ?? null;

      for (let index = 0; index < sortedIntervals.length - 1; index += 1) {
        const newerInterval = sortedIntervals[index];
        const olderInterval = sortedIntervals[index + 1];
        const gapMs =
          new Date(newerInterval.interval_start).getTime() -
          new Date(olderInterval.interval_end).getTime();

        if (gapMs > 0) {
          nextIssues.push({
            id: `interval-gap-${channelId}-${newerInterval.id}-${olderInterval.id}`,
            issueType: "interval_gap_detected",
            severity: "warning",
            reason: `Gap of ${formatDurationFromMs(gapMs)} detected between consecutive interval windows.`,
            observedAt: newerInterval.interval_start,
            relatedContext: channel
              ? `${channel.channel_code} • ${formatDateTime(newerInterval.interval_start)}`
              : formatDateTime(newerInterval.interval_start),
            relatedSource: channel
              ? `${formatIntervalCadenceLabel(channel.interval_seconds)} expected`
              : "Channel cadence unavailable",
            relatedSectionHref: "#meter-billing-interval-follow-through-section",
            relatedActionLabel: "Review interval follow-through",
          });
        }
      }
    });

    return nextIssues.sort((left, right) => {
      const severityWeight =
        (left.severity === "critical" ? 0 : 1) -
        (right.severity === "critical" ? 0 : 1);
      if (severityWeight !== 0) {
        return severityWeight;
      }

      const rightTime = right.observedAt ? new Date(right.observedAt).getTime() : 0;
      const leftTime = left.observedAt ? new Date(left.observedAt).getTime() : 0;
      return rightTime - leftTime;
    });
  }, [
    latestBillingSnapshot,
    loadProfileChannelById,
    loadProfileIntervals,
    meter?.serial_number,
    meterId,
  ]);
  const recoveryIssues = useMemo(() => {
    const nextIssues: OperationalVisibilityCue[] = [];

    if (meterReadings.length === 0) {
      nextIssues.push({
        id: `missing-raw-reading-${meterId}`,
        issueType: "missing_recent_raw_reading",
        severity: "warning",
        reason: "No recent raw reading is currently available for this meter.",
        observedAt: null,
        relatedContext: meter?.serial_number ?? meterId,
        relatedSource: "Recent raw readings",
        relatedSectionHref: "#meter-raw-readings-section",
        relatedActionLabel: "Review raw readings",
      });
    }

    if (activeLoadProfileChannels.length > 0 && loadProfileIntervals.length === 0) {
      nextIssues.push({
        id: `missing-interval-horizon-${meterId}`,
        issueType: "missing_interval_horizon",
        severity: "critical",
        reason:
          "Interval channel context is visible, but no recent interval rows are loaded for this meter.",
        observedAt: null,
        relatedContext: `${meter?.serial_number ?? meterId} • ${formatCountLabel(
          activeLoadProfileChannels.length,
          "active channel",
          "active channels",
        )}`,
        relatedSource: "Billing and interval follow-through",
        relatedSectionHref: "#meter-billing-interval-follow-through-section",
        relatedActionLabel: "Review interval follow-through",
      });
    }

    if (latestInterval && latestReading && intervalLagMs !== null && intervalLagMs > 0) {
      nextIssues.push({
        id: `stale-interval-horizon-${meterId}`,
        issueType: "stale_interval_horizon",
        severity: "warning",
        reason:
          "The latest interval horizon ends before the most recent raw reading update for this meter.",
        observedAt: latestReading.captured_at,
        relatedContext: latestIntervalChannel
          ? `${latestIntervalChannel.channel_code} • ${formatIntervalWindow(latestInterval)}`
          : formatIntervalWindow(latestInterval),
        relatedSource: `Interval posture ${intervalLagLabel}`,
        relatedSectionHref: "#meter-billing-interval-follow-through-section",
        relatedActionLabel: "Review interval follow-through",
      });
    }

    return nextIssues.sort((left, right) => {
      const severityWeight =
        (left.severity === "critical" ? 0 : 1) -
        (right.severity === "critical" ? 0 : 1);
      if (severityWeight !== 0) {
        return severityWeight;
      }

      const rightTime = right.observedAt ? new Date(right.observedAt).getTime() : 0;
      const leftTime = left.observedAt ? new Date(left.observedAt).getTime() : 0;
      return rightTime - leftTime;
    });
  }, [
    activeLoadProfileChannels.length,
    intervalLagLabel,
    intervalLagMs,
    latestInterval,
    latestIntervalChannel,
    latestReading,
    loadProfileIntervals.length,
    meter?.serial_number,
    meterId,
    meterReadings.length,
  ]);
  const visibilityCues = useMemo(
    () => [...validationIssues, ...recoveryIssues].slice(0, 5),
    [recoveryIssues, validationIssues],
  );
  const criticalValidationIssueCount = validationIssues.filter(
    (issue) => issue.severity === "critical",
  ).length;
  const warningValidationIssueCount = validationIssues.filter(
    (issue) => issue.severity === "warning",
  ).length;
  const intervalVisibilityNarrative = latestInterval
    ? intervalLagMs !== null && intervalLagMs > 0
      ? `Latest interval horizon trails the newest raw reading by ${formatDurationFromMs(intervalLagMs)}.`
      : `Latest interval horizon is visible with ${intervalCadenceLabel} and posture ${intervalLagLabel}.`
    : activeLoadProfileChannels.length > 0
      ? `Interval channel context is visible, but the current meter-scoped horizon has no interval rows loaded.`
      : "No interval channel or horizon is currently visible for this meter.";
  const billingContextNarrative = latestBillingSnapshot
    ? `Latest billing snapshot captured ${formatDateTime(latestBillingSnapshot.captured_at)} with ${formatBillingPrimaryValue(latestBillingSnapshot.payload)}.`
    : "No billing snapshot context is currently available for this meter.";

  const overviewCards = useMemo(
    () => [
      {
        label: "Latest raw reading freshness",
        value: readingFreshnessLabel,
        note: latestReading
          ? `${latestReading.obis_code} • ${formatReadingValue(latestReading)}`
          : "No recent raw reading recorded for this meter",
      },
      {
        label: "Interval horizon freshness",
        value: intervalFreshnessLabel,
        note: latestInterval
          ? `${latestIntervalChannel?.channel_code ?? latestInterval.channel_id} • ${formatIntervalValue(latestInterval, latestIntervalChannel)}`
          : "No current interval horizon recorded",
      },
      {
        label: "Interval cadence",
        value: intervalCadenceLabel,
        note:
          activeLoadProfileChannels.length > 0
            ? `${formatCountLabel(activeLoadProfileChannels.length, "active channel", "active channels")} in scope`
            : "No active load-profile channels",
      },
      {
        label: "Interval lag posture",
        value: intervalLagLabel,
        note: intervalVisibilityNarrative,
      },
      {
        label: "Billing snapshot context",
        value: latestBillingContextLabel,
        note: latestReading
          ? billingContextNarrative
          : billingContextNarrative,
      },
      {
        label: "Critical validation cues",
        value: String(criticalValidationIssueCount),
        note:
          criticalValidationIssueCount > 0
            ? "Critical interval or visibility issues are currently derived."
            : "No critical validation cues derived.",
      },
      {
        label: "Warning validation cues",
        value: String(warningValidationIssueCount),
        note:
          warningValidationIssueCount > 0
            ? "Warning-level validation posture is visible."
            : "No warning validation cues derived.",
      },
      {
        label: "Bounded anomaly cues",
        value: String(visibilityCues.length),
        note:
          visibilityCues.length > 0
            ? "Derived from the current meter-scoped readings context only."
            : "No anomaly cues are currently derived.",
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
      billingContextNarrative,
      criticalValidationIssueCount,
      intervalCadenceLabel,
      intervalFreshnessLabel,
      intervalLagLabel,
      intervalVisibilityNarrative,
      latestInterval,
      latestIntervalChannel,
      latestReading,
      latestBillingContextLabel,
      loadProfileIntervals.length,
      meterReadings.length,
      readingFreshnessLabel,
      visibilityCues.length,
      warningValidationIssueCount,
    ],
  );

  const rawReadingRows = meterReadings.slice(0, 3);

  return (
    <div className="detail-stack">
      {readingsContextError ? <p className="error-banner">{readingsContextError}</p> : null}

      <section
        className="subpanel audit-center-overview-panel"
        id="meter-readings-context-section"
      >
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
                {readingFreshnessLabel}
              </span>
              <span className="artifact-pill">
                {intervalFreshnessLabel}
              </span>
              <span className="artifact-pill">
                {intervalCadenceLabel}
              </span>
              <span className="artifact-pill">
                {`Interval posture ${intervalLagLabel}`}
              </span>
              <span className="artifact-pill">{latestBillingContextLabel}</span>
              <span className="artifact-pill">
                {formatCountLabel(visibilityCues.length, "visibility cue", "visibility cues")}
              </span>
            </div>

            <p className="muted">{intervalVisibilityNarrative}</p>
            <p className="muted">{billingContextNarrative}</p>

            {visibilityCues.length === 0 ? (
              <p className="muted">
                No meter-scoped validation or anomaly cues are currently derived from the loaded
                readings context.
              </p>
            ) : (
              <div className="command-list">
                {visibilityCues.map((cue) => (
                  <div key={cue.id} className="command-list-item">
                    <div className="command-list-item-header">
                      <strong>{formatValidationIssueType(cue.issueType)}</strong>
                      <span
                        className={`status-pill ${buildValidationSeverityTone(cue.severity)}`}
                      >
                        {formatStatusLabel(cue.severity)}
                      </span>
                    </div>
                    <div className="command-list-item-meta">
                      <span>{cue.reason}</span>
                      <span>{formatDateTime(cue.observedAt)}</span>
                    </div>
                    <div className="command-list-item-meta">
                      <span>{cue.relatedContext}</span>
                      <span>{cue.relatedSource}</span>
                    </div>
                    <div className="artifact-row">
                      <Link className="secondary-button" href={cue.relatedSectionHref}>
                        {cue.relatedActionLabel}
                      </Link>
                      <Link className="secondary-button" href={`/readings?meterId=${meterId}`}>
                        Open readings workspace
                      </Link>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>
        ) : null}

        {!isLoadingReadingsContext && !hasReadingsContext ? (
          <p className="muted">Readings context not available for this meter yet.</p>
        ) : null}
      </section>

      <section className="subpanel meter-summary-panel" id="meter-raw-readings-section">
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
          <div className="detail-stack">
            <div className="artifact-row">
              <span className="artifact-pill">
                {latestReading
                  ? `Latest reading ${formatStatusLabel(latestReading.reading_type)}`
                  : "No raw reading type recorded"}
              </span>
              <span className="artifact-pill">
                {latestReading
                  ? `Latest quality ${formatStatusLabel(latestReading.quality)}`
                  : "No raw reading quality recorded"}
              </span>
            </div>

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
          </div>
        )}
      </section>

      <section
        className="subpanel meter-summary-panel"
        id="meter-billing-interval-follow-through-section"
      >
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
          <div className="detail-stack">
            <div className="artifact-row">
              <span className="artifact-pill">{latestBillingContextLabel}</span>
              <span className="artifact-pill">{intervalCadenceLabel}</span>
              <span className="artifact-pill">{`Interval posture ${intervalLagLabel}`}</span>
            </div>

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
                <span className="stat-label">Latest billing snapshot</span>
                <strong>
                  {latestBillingSnapshot
                    ? formatDateTime(latestBillingSnapshot.captured_at)
                    : "Not available"}
                </strong>
                <p className="muted">{billingContextNarrative}</p>
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
                <span className="stat-label">Interval horizon freshness</span>
                <strong>{intervalFreshnessLabel}</strong>
                <p className="muted">{intervalVisibilityNarrative}</p>
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
          </div>
        )}
      </section>
    </div>
  );
}
