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

type LoadProfileChannelItem = {
  id: string;
  meter_id: string;
  channel_code: string;
  obis_code: string;
  unit: string | null;
  interval_seconds: number;
  is_active: boolean;
};

type LoadProfileChannelListResponse = {
  total: number;
  items: LoadProfileChannelItem[];
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

type LoadProfileIntervalListResponse = {
  total: number;
  items: LoadProfileIntervalItem[];
};

type ValidationIssueSeverity = "critical" | "warning";

type ValidationIssue = {
  id: string;
  issue_type: string;
  severity: ValidationIssueSeverity;
  state: "open";
  reason: string;
  observed_at: string | null;
  related_context: string;
  related_source: string;
  related_section_href: string;
  related_action_label: string;
};

type MissingReadsIssue = {
  id: string;
  issue_type: string;
  severity: ValidationIssueSeverity;
  state: "open";
  missing_window: string;
  reason: string;
  observed_at: string | null;
  related_context: string;
  related_source: string;
  related_section_href: string;
  related_action_label: string;
};

function buildRecoveryActionHref(meterId: string, issue: MissingReadsIssue): string {
  const searchParams = new URLSearchParams({
    meterId,
    commandFamily: "on_demand_read",
    recoverySource: "readings_missing_recovery_queue",
    recoveryIssueType: issue.issue_type,
    recoveryReason: issue.reason,
    recoveryContext: issue.related_context,
  });
  return `/commands?${searchParams.toString()}`;
}

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
    normalized.includes("inactive") ||
    normalized.includes("suspect") ||
    normalized.includes("missing")
  ) {
    return "danger";
  }
  if (
    normalized.includes("pending") ||
    normalized.includes("queued") ||
    normalized.includes("running") ||
    normalized.includes("review") ||
    normalized.includes("estimated") ||
    normalized.includes("stale") ||
    normalized.includes("gap")
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

function formatCountLabel(count: number, singular: string, plural: string): string {
  return `${count} ${count === 1 ? singular : plural}`;
}

function formatIntervalValue(
  interval: LoadProfileIntervalItem,
  channel: LoadProfileChannelItem | null,
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

function buildValidationSeverityTone(
  severity: ValidationIssueSeverity,
): "danger" | "warning" {
  return severity === "critical" ? "danger" : "warning";
}

function formatValidationIssueType(issueType: string): string {
  return issueType
    .split("_")
    .filter(Boolean)
    .map((part) => part.charAt(0).toUpperCase() + part.slice(1))
    .join(" ");
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
  const [loadProfileChannels, setLoadProfileChannels] = useState<LoadProfileChannelItem[]>([]);
  const [loadProfileIntervals, setLoadProfileIntervals] = useState<LoadProfileIntervalItem[]>([]);
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

      const [
        readingsResult,
        snapshotsResult,
        batchesResult,
        loadProfileChannelsResult,
        loadProfileIntervalsResult,
      ] = await Promise.allSettled([
        authorizedFetch<MeterReadingListResponse>(`/api/v1/meters/${meterId}/readings?limit=10`),
        authorizedFetch<MeterRegisterSnapshotListResponse>(
          `/api/v1/meters/${meterId}/register-snapshots?limit=25`,
        ),
        authorizedFetch<MeterReadingBatchListResponse>(
          `/api/v1/meters/${meterId}/reading-batches?limit=25`,
        ),
        authorizedFetch<LoadProfileChannelListResponse>(
          `/api/v1/meters/${meterId}/load-profile-channels`,
        ),
        authorizedFetch<LoadProfileIntervalListResponse>(
          `/api/v1/meters/${meterId}/load-profile-intervals?limit=96`,
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

      if (loadProfileChannelsResult.status === "fulfilled") {
        setLoadProfileChannels(loadProfileChannelsResult.value.items);
      } else {
        setLoadProfileChannels([]);
      }

      if (loadProfileIntervalsResult.status === "fulfilled") {
        setLoadProfileIntervals(loadProfileIntervalsResult.value.items);
      } else {
        setLoadProfileIntervals([]);
      }

      const failedResults = [
        readingsResult,
        snapshotsResult,
        batchesResult,
        loadProfileChannelsResult,
        loadProfileIntervalsResult,
      ].filter(
        (result): result is PromiseRejectedResult => result.status === "rejected",
      );

      if (failedResults.length === 5) {
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
      setLoadProfileChannels([]);
      setLoadProfileIntervals([]);
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
  const loadProfileChannelById = useMemo(
    () => new Map(loadProfileChannels.map((channel) => [channel.id, channel])),
    [loadProfileChannels],
  );

  const latestBillingSnapshot = billingSnapshots[0] ?? null;
  const latestReading = meterReadings[0] ?? null;
  const latestInterval = loadProfileIntervals[0] ?? null;
  const latestIntervalChannel = latestInterval
    ? loadProfileChannelById.get(latestInterval.channel_id) ?? null
    : null;
  const latestIntervalBatch = latestInterval?.source_batch_id
    ? batchById.get(latestInterval.source_batch_id) ?? null
    : null;
  const latestBillingBatch = latestBillingSnapshot
    ? batchById.get(latestBillingSnapshot.related_batch_id) ?? null
    : null;
  const latestBillingPrimaryValue = latestBillingSnapshot
    ? formatBillingPrimaryValue(latestBillingSnapshot.payload)
    : "No billing read recorded";
  const latestBillingSummary = latestBillingSnapshot
    ? formatBillingSummary(latestBillingSnapshot.payload)
    : "No structured billing payload recorded.";
  const latestBillingContextLabel = latestBillingSnapshot
    ? "Billing-read context available"
    : "Billing-read context missing";
  const latestBillingSourceLabel = latestBillingBatch
    ? formatStatusLabel(latestBillingBatch.source_type)
    : "Not available";
  const latestBillingStatusLabel = latestBillingBatch
    ? formatStatusLabel(latestBillingBatch.status)
    : "Not recorded";
  const latestBillingReceivedLabel = formatDateTime(latestBillingBatch?.received_at ?? null);
  const latestBillingNarrative = latestBillingSnapshot
    ? `Latest billing snapshot captured ${formatDateTime(
        latestBillingSnapshot.captured_at,
      )} for ${selectedMeter?.serial_number ?? "the selected meter"}, received ${latestBillingReceivedLabel}, and sourced from ${latestBillingSourceLabel}.`
    : "No billing-read context is recorded yet for the selected meter. Use the meter detail return path if you need to confirm whether a billing read should exist for this meter.";
  const selectedMeterStatusLabel = selectedMeter
    ? formatStatusLabel(selectedMeter.current_status)
    : "No selection";
  const selectedMeterSignalLabel = selectedMeter
    ? selectedMeter.last_seen_at
      ? `Last signal ${formatDateTime(selectedMeter.last_seen_at)}`
      : "No recent signal recorded"
    : "Select a meter to inspect readings";
  const latestBillingBatchSummary = latestBillingBatch
    ? `Source ${formatStatusLabel(latestBillingBatch.source_type)} • Received ${formatDateTime(
        latestBillingBatch.received_at,
      )}`
    : "No batch source or receipt recorded";
  const latestIntervalValueLabel = latestInterval
    ? formatIntervalValue(latestInterval, latestIntervalChannel)
    : "No interval value recorded";
  const latestIntervalQualityLabel = latestInterval
    ? formatStatusLabel(latestInterval.quality)
    : "No quality recorded";
  const latestIntervalNarrative = latestInterval
    ? `Latest interval captured for ${selectedMeter?.serial_number ?? "the selected meter"} spans ${formatIntervalWindow(
        latestInterval,
      )} with ${latestIntervalValueLabel} and quality ${latestIntervalQualityLabel}.`
    : "No interval-read context is recorded yet for the selected meter. The bounded interval surface remains empty until load profile intervals are available.";
  const latestIntervalSourceLabel = latestIntervalBatch
    ? formatStatusLabel(latestIntervalBatch.source_type)
    : "Not available";
  const latestIntervalStatusLabel = latestIntervalBatch
    ? formatStatusLabel(latestIntervalBatch.status)
    : "Not recorded";
  const latestIntervalReceivedLabel = formatDateTime(latestIntervalBatch?.received_at ?? null);
  const intervalChannelsSummary =
    loadProfileChannels.length > 0
      ? formatCountLabel(loadProfileChannels.length, "channel", "channels")
      : "No interval channels";
  const validationIssues = useMemo(() => {
    if (!selectedMeter) {
      return [] as ValidationIssue[];
    }

    const nextIssues: ValidationIssue[] = [];

    if (billingSnapshots.length === 0) {
      nextIssues.push({
        id: `billing-context-missing-${selectedMeter.id}`,
        issue_type: "billing_context_missing",
        severity: "warning",
        state: "open",
        reason:
          "No billing read is available for the selected meter in the current bounded readings scope.",
        observed_at: null,
        related_context: selectedMeter.serial_number,
        related_source: "Billing reads section",
        related_section_href: "#billing-reads-section",
        related_action_label: "Review billing reads",
      });
    }

    loadProfileIntervals.forEach((interval) => {
      const channel = loadProfileChannelById.get(interval.channel_id) ?? null;
      const relatedBatch = interval.source_batch_id
        ? batchById.get(interval.source_batch_id) ?? null
        : null;
      const relatedContext = channel
        ? `${channel.channel_code} • ${formatIntervalWindow(interval)}`
        : formatIntervalWindow(interval);
      const relatedSource = relatedBatch
        ? `Source ${formatStatusLabel(relatedBatch.source_type)}`
        : "Source batch unavailable";

      if (interval.value_numeric === null) {
        nextIssues.push({
          id: `interval-value-missing-${interval.id}`,
          issue_type: "interval_value_missing",
          severity: "critical",
          state: "open",
          reason: "Interval value is missing for the recorded load profile window.",
          observed_at: interval.interval_end,
          related_context: relatedContext,
          related_source: relatedSource,
          related_section_href: "#interval-reads-section",
          related_action_label: "Review interval reads",
        });
      }

      if (interval.quality === "suspect" || interval.quality === "estimated" || interval.quality === "missing") {
        nextIssues.push({
          id: `interval-quality-${interval.id}`,
          issue_type: "interval_quality_flagged",
          severity:
            interval.quality === "estimated" ? "warning" : "critical",
          state: "open",
          reason: `Interval quality is marked ${formatStatusLabel(interval.quality)}.`,
          observed_at: interval.interval_end,
          related_context: relatedContext,
          related_source: relatedSource,
          related_section_href: "#interval-reads-section",
          related_action_label: "Review interval reads",
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
            issue_type: "interval_gap_detected",
            severity: "warning",
            state: "open",
            reason: `Gap of ${formatDurationFromMs(gapMs)} detected between consecutive interval windows.`,
            observed_at: newerInterval.interval_start,
            related_context: channel
              ? `${channel.channel_code} • ${formatDateTime(newerInterval.interval_start)}`
              : formatDateTime(newerInterval.interval_start),
            related_source: channel
              ? `${channel.interval_seconds} second interval cadence`
              : "Channel cadence unavailable",
            related_section_href: "#interval-reads-section",
            related_action_label: "Review interval reads",
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

      const rightTime = right.observed_at ? new Date(right.observed_at).getTime() : 0;
      const leftTime = left.observed_at ? new Date(left.observed_at).getTime() : 0;
      return rightTime - leftTime;
    });
  }, [
    batchById,
    billingSnapshots.length,
    loadProfileChannelById,
    loadProfileIntervals,
    selectedMeter,
  ]);
  const missingReadsIssues = useMemo(() => {
    if (!selectedMeter) {
      return [] as MissingReadsIssue[];
    }

    const nextIssues: MissingReadsIssue[] = [];

    if (billingSnapshots.length === 0) {
      nextIssues.push({
        id: `missing-billing-${selectedMeter.id}`,
        issue_type: "missing_billing_read_context",
        severity: "warning",
        state: "open",
        missing_window: "Current bounded billing scope",
        reason: "No billing read is currently available for the selected meter.",
        observed_at: null,
        related_context: selectedMeter.serial_number,
        related_source: "Billing reads section",
        related_section_href: "#billing-reads-section",
        related_action_label: "Review billing reads",
      });
    }

    if (loadProfileChannels.length > 0 && loadProfileIntervals.length === 0) {
      nextIssues.push({
        id: `missing-intervals-${selectedMeter.id}`,
        issue_type: "missing_recent_interval_records",
        severity: "critical",
        state: "open",
        missing_window: "Recent interval window missing",
        reason:
          "No interval records are available even though interval channel context exists for the selected meter.",
        observed_at: null,
        related_context: `${selectedMeter.serial_number} • ${intervalChannelsSummary}`,
        related_source: "Interval reads section",
        related_section_href: "#interval-reads-section",
        related_action_label: "Review interval reads",
      });
    }

    if (meterReadings.length === 0) {
      nextIssues.push({
        id: `missing-recent-reading-${selectedMeter.id}`,
        issue_type: "missing_recent_reading_update",
        severity: "warning",
        state: "open",
        missing_window: "Recent raw reading unavailable",
        reason: "No recent raw reading update is available for the selected meter.",
        observed_at: null,
        related_context: selectedMeter.serial_number,
        related_source: "Recent reading context",
        related_section_href: "#recent-reading-context-section",
        related_action_label: "Review recent reading context",
      });
    }

    if (latestInterval && latestReading) {
      const staleGapMs =
        new Date(latestReading.captured_at).getTime() -
        new Date(latestInterval.interval_end).getTime();

      if (staleGapMs > 0) {
        nextIssues.push({
          id: `stale-interval-window-${selectedMeter.id}`,
          issue_type: "stale_interval_window",
          severity: "warning",
          state: "open",
          missing_window: `Lag ${formatDurationFromMs(staleGapMs)}`,
          reason:
            "The latest interval window ends before the most recent raw reading update, indicating a stale interval horizon.",
          observed_at: latestReading.captured_at,
          related_context: latestIntervalChannel
            ? `${latestIntervalChannel.channel_code} • ${formatIntervalWindow(latestInterval)}`
            : formatIntervalWindow(latestInterval),
          related_source: "Interval reads section",
          related_section_href: "#interval-reads-section",
          related_action_label: "Review interval reads",
        });
      }
    }

    return nextIssues.sort((left, right) => {
      const severityWeight =
        (left.severity === "critical" ? 0 : 1) -
        (right.severity === "critical" ? 0 : 1);
      if (severityWeight !== 0) {
        return severityWeight;
      }

      const rightTime = right.observed_at ? new Date(right.observed_at).getTime() : 0;
      const leftTime = left.observed_at ? new Date(left.observed_at).getTime() : 0;
      return rightTime - leftTime;
    });
  }, [
    billingSnapshots.length,
    intervalChannelsSummary,
    latestInterval,
    latestIntervalChannel,
    latestReading,
    loadProfileChannels.length,
    loadProfileIntervals.length,
    meterReadings.length,
    selectedMeter,
  ]);

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
        label: "Selected meter focus",
        value: selectedMeter?.serial_number ?? "No selection",
        note: selectedMeter
          ? `${selectedMeterStatusLabel} • ${selectedMeterSignalLabel}`
          : "Choose a meter to inspect readings",
      },
      {
        label: "Billing-read context",
        value: latestBillingContextLabel,
        note: selectedMeter
          ? latestBillingSnapshot
            ? `${formatCountLabel(
                billingSnapshots.length,
                "billing read",
                "billing reads",
              )} loaded for ${selectedMeter.serial_number}`
            : `No billing reads loaded for ${selectedMeter.serial_number}`
          : "No selected meter billing context",
      },
      {
        label: "Latest billing read",
        value: latestBillingSnapshot
          ? formatDateTime(latestBillingSnapshot.captured_at)
          : "Not available",
        note: latestBillingSnapshot
          ? latestBillingBatchSummary
          : "No billing read recorded",
      },
      {
        label: "Latest billing value",
        value: latestBillingPrimaryValue,
        note: latestBillingSnapshot
          ? formatBillingSummary(latestBillingSnapshot.payload)
          : "No billing payload recorded for the current selection",
      },
      {
        label: "Recent raw readings loaded",
        value: String(meterReadings.length),
        note: latestReading
          ? `${latestReading.obis_code} • ${formatReadingValue(latestReading)}`
          : "No recent reading value recorded",
      },
      {
        label: "Recent interval reads loaded",
        value: String(loadProfileIntervals.length),
        note: latestInterval
          ? `${latestIntervalChannel?.channel_code ?? latestInterval.channel_id} • ${latestIntervalValueLabel}`
          : "No interval reads recorded for the current selection",
      },
      {
        label: "Validation issues in focus",
        value: String(validationIssues.length),
        note: selectedMeter
          ? validationIssues.length > 0
            ? `${formatCountLabel(validationIssues.length, "issue", "issues")} derived for ${selectedMeter.serial_number}`
            : `No validation issues derived for ${selectedMeter.serial_number}`
          : "No selected meter validation context",
      },
      {
        label: "Missing reads in focus",
        value: String(missingReadsIssues.length),
        note: selectedMeter
          ? missingReadsIssues.length > 0
            ? `${formatCountLabel(missingReadsIssues.length, "recovery issue", "recovery issues")} derived for ${selectedMeter.serial_number}`
            : `No missing reads derived for ${selectedMeter.serial_number}`
          : "No selected meter recovery context",
      },
    ],
    [
      billingSnapshots.length,
      filteredMeters,
      latestBillingSnapshot,
      latestBillingBatchSummary,
      latestBillingContextLabel,
      latestBillingPrimaryValue,
      latestReading,
      latestInterval,
      latestIntervalChannel,
      latestIntervalValueLabel,
      loadProfileIntervals.length,
      meterReadings.length,
      meterSearchQuery,
      missingReadsIssues.length,
      selectedMeter,
      selectedMeterSignalLabel,
      selectedMeterStatusLabel,
      totalMeters,
      validationIssues.length,
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
            <div className="detail-stack">
              <div className="readings-overview-grid">
                {overviewCards.map((card) => (
                  <div key={card.label} className="stat-card readings-overview-card">
                    <span className="stat-label">{card.label}</span>
                    <strong>{card.value}</strong>
                    <p className="muted">{card.note}</p>
                  </div>
                ))}
              </div>

              <div className="artifact-row">
                <span className="artifact-pill">
                  {meterSearchQuery.trim()
                    ? `${formatCountLabel(filteredMeters.length, "filtered meter", "filtered meters")} in scope`
                    : `${formatCountLabel(totalMeters, "meter", "meters")} in current bounded scope`}
                </span>
                <span className="artifact-pill">
                  {selectedMeter
                    ? `Selected meter ${selectedMeter.serial_number}`
                    : "Awaiting selected meter context"}
                </span>
                <span
                  className={`status-pill ${buildStatusTone(
                    latestBillingBatch?.status ?? (latestBillingSnapshot ? "received" : null),
                  )}`}
                >
                  {selectedMeter
                    ? latestBillingSnapshot
                      ? `Overview reflects current billing context`
                      : "Overview reflects missing billing context"
                    : "Overview awaiting current billing context"}
                </span>
              </div>
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
                      {loadProfileIntervals.length} interval reads
                    </span>
                    <span className="artifact-pill">
                      {validationIssues.length} validation issues
                    </span>
                    <span className="artifact-pill">
                      {missingReadsIssues.length} missing reads
                    </span>
                    <span className="artifact-pill">
                      {meterReadings.length} recent raw readings
                    </span>
                    <span className="artifact-pill">
                      Last signal {formatDateTime(selectedMeter.last_seen_at)}
                    </span>
                  </div>
                </section>

                <section className="subpanel readings-billing-context-panel">
                  <div className="section-heading">
                    <div>
                      <h3>Current billing context</h3>
                      <p className="muted">{latestBillingNarrative}</p>
                    </div>
                    <span className={`status-pill ${buildStatusTone(latestBillingBatch?.status ?? null)}`}>
                      {latestBillingSnapshot
                        ? `Latest batch ${latestBillingStatusLabel}`
                        : "No billing batch yet"}
                    </span>
                  </div>

                  <div className="artifact-row">
                    <span className="artifact-pill">{latestBillingContextLabel}</span>
                    <span className="artifact-pill">
                      {latestBillingSnapshot
                        ? `Primary value ${latestBillingPrimaryValue}`
                        : "Primary value unavailable"}
                    </span>
                    <span className="artifact-pill">
                      {latestBillingSnapshot
                        ? `Source ${latestBillingSourceLabel}`
                        : "Source unavailable"}
                    </span>
                  </div>

                  <div className="detail-grid">
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
                      <span className="stat-label">Latest billing source</span>
                      <strong>{latestBillingSourceLabel}</strong>
                    </div>
                    <div className="stat-card">
                      <span className="stat-label">Latest billing status</span>
                      <strong>{latestBillingStatusLabel}</strong>
                    </div>
                    <div className="stat-card">
                      <span className="stat-label">Latest billing received</span>
                      <strong>{latestBillingReceivedLabel}</strong>
                    </div>
                    <div className="stat-card">
                      <span className="stat-label">Latest billing value</span>
                      <strong>{latestBillingPrimaryValue}</strong>
                    </div>
                    <div className="stat-card">
                      <span className="stat-label">Billing payload summary</span>
                      <strong>{latestBillingSummary}</strong>
                    </div>
                  </div>
                </section>

                <section className="subpanel" id="interval-reads-section">
                  <div className="section-heading">
                    <div>
                      <h3>Interval reads</h3>
                      <p className="muted">
                        Recent load profile interval visibility for the selected meter using
                        the existing interval and channel read models only.
                      </p>
                    </div>
                    <span className="artifact-pill">Newest interval first</span>
                  </div>

                  <div className="detail-stack">
                    <p className="muted">{latestIntervalNarrative}</p>

                    <div className="artifact-row">
                      <span className="artifact-pill">
                        {loadProfileIntervals.length} interval reads
                      </span>
                      <span className="artifact-pill">{intervalChannelsSummary}</span>
                      <span className="artifact-pill">
                        {latestInterval
                          ? `Latest value ${latestIntervalValueLabel}`
                          : "Latest value unavailable"}
                      </span>
                      <span
                        className={`status-pill ${buildStatusTone(
                          latestInterval?.quality ?? null,
                        )}`}
                      >
                        {latestInterval
                          ? `Latest quality ${latestIntervalQualityLabel}`
                          : "No interval quality yet"}
                      </span>
                    </div>

                    <div className="detail-grid">
                      <div className="stat-card">
                        <span className="stat-label">Latest interval window</span>
                        <strong>
                          {latestInterval ? formatIntervalWindow(latestInterval) : "Not available"}
                        </strong>
                      </div>
                      <div className="stat-card">
                        <span className="stat-label">Latest interval value</span>
                        <strong>{latestIntervalValueLabel}</strong>
                      </div>
                      <div className="stat-card">
                        <span className="stat-label">Latest interval quality</span>
                        <strong>{latestIntervalQualityLabel}</strong>
                      </div>
                      <div className="stat-card">
                        <span className="stat-label">Latest interval source</span>
                        <strong>{latestIntervalSourceLabel}</strong>
                      </div>
                      <div className="stat-card">
                        <span className="stat-label">Latest interval status</span>
                        <strong>{latestIntervalStatusLabel}</strong>
                      </div>
                      <div className="stat-card">
                        <span className="stat-label">Latest interval received</span>
                        <strong>{latestIntervalReceivedLabel}</strong>
                      </div>
                    </div>
                  </div>

                  {loadProfileIntervals.length === 0 ? (
                    <p className="muted">
                      No interval reads available for the selected meter yet. The interval
                      section remains bounded to current recent load profile records only.
                    </p>
                  ) : (
                    <div className="readings-table-shell">
                      <table className="readings-table">
                        <thead>
                          <tr>
                            <th scope="col">Interval window</th>
                            <th scope="col">Channel</th>
                            <th scope="col">Value</th>
                            <th scope="col">Quality</th>
                            <th scope="col">Source</th>
                          </tr>
                        </thead>
                        <tbody>
                          {loadProfileIntervals.map((interval, index) => {
                            const channel = loadProfileChannelById.get(interval.channel_id) ?? null;
                            const relatedBatch = interval.source_batch_id
                              ? batchById.get(interval.source_batch_id) ?? null
                              : null;
                            const isLatestInterval = index === 0;

                            return (
                              <tr
                                key={interval.id}
                                className={
                                  isLatestInterval
                                    ? "readings-table-row readings-table-row-latest"
                                    : "readings-table-row"
                                }
                              >
                                <td>
                                  <strong>{formatIntervalWindow(interval)}</strong>
                                  <div className="artifact-row">
                                    {isLatestInterval ? (
                                      <span className="artifact-pill">Latest interval</span>
                                    ) : null}
                                    <span className="muted">
                                      Ends {formatDateTime(interval.interval_end)}
                                    </span>
                                  </div>
                                </td>
                                <td>
                                  <strong>
                                    {channel
                                      ? `${channel.channel_code} • ${channel.obis_code}`
                                      : interval.channel_id}
                                  </strong>
                                  <div className="muted">
                                    {channel
                                      ? `${channel.interval_seconds} second interval`
                                      : "Channel metadata unavailable"}
                                  </div>
                                </td>
                                <td>
                                  <strong>{formatIntervalValue(interval, channel)}</strong>
                                  <div className="muted">
                                    {channel?.unit ? `Unit ${channel.unit}` : "Unit not recorded"}
                                  </div>
                                </td>
                                <td>
                                  <span
                                    className={`status-pill ${buildStatusTone(interval.quality ?? null)}`}
                                  >
                                    {formatStatusLabel(interval.quality)}
                                  </span>
                                  <div className="muted">Interval quality</div>
                                </td>
                                <td>
                                  <strong>
                                    {relatedBatch
                                      ? `Source ${formatStatusLabel(relatedBatch.source_type)}`
                                      : "Source unavailable"}
                                  </strong>
                                  <div className="muted">
                                    {relatedBatch
                                      ? `Batch ${formatStatusLabel(relatedBatch.status)} • Received ${formatDateTime(
                                          relatedBatch.received_at,
                                        )}`
                                      : "No source batch recorded"}
                                  </div>
                                </td>
                              </tr>
                            );
                          })}
                        </tbody>
                      </table>
                    </div>
                  )}
                </section>

                <section className="subpanel" id="validation-center-section">
                  <div className="section-heading">
                    <div>
                      <h3>Validation center</h3>
                      <p className="muted">
                        Derived validation queue for the selected meter using current
                        billing and interval-read context only.
                      </p>
                    </div>
                    <span className="artifact-pill">
                      {validationIssues.length} open validation issues
                    </span>
                  </div>

                  {validationIssues.length === 0 ? (
                    <p className="muted">
                      No validation issues match the current bounded selected-meter scope.
                    </p>
                  ) : (
                    <div className="readings-table-shell">
                      <table className="readings-table">
                        <thead>
                          <tr>
                            <th scope="col">Issue</th>
                            <th scope="col">Severity</th>
                            <th scope="col">State</th>
                            <th scope="col">Observed</th>
                            <th scope="col">Context</th>
                            <th scope="col">Action</th>
                          </tr>
                        </thead>
                        <tbody>
                          {validationIssues.map((issue) => (
                            <tr key={issue.id}>
                              <td>
                                <strong>{formatValidationIssueType(issue.issue_type)}</strong>
                                <div className="muted">{issue.reason}</div>
                              </td>
                              <td>
                                <span
                                  className={`status-pill ${buildValidationSeverityTone(
                                    issue.severity,
                                  )}`}
                                >
                                  {formatStatusLabel(issue.severity)}
                                </span>
                              </td>
                              <td>
                                <span className="status-pill warning">
                                  {formatStatusLabel(issue.state)}
                                </span>
                              </td>
                              <td>{formatDateTime(issue.observed_at)}</td>
                              <td>
                                <strong>{issue.related_context}</strong>
                                <div className="muted">{issue.related_source}</div>
                              </td>
                              <td>
                                <Link className="secondary-button" href={issue.related_section_href}>
                                  {issue.related_action_label}
                                </Link>
                              </td>
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    </div>
                  )}
                </section>

                <section className="subpanel" id="missing-reads-recovery-section">
                  <div className="section-heading">
                    <div>
                      <h3>Missing reads / recovery queue</h3>
                      <p className="muted">
                        Derived recovery queue for the selected meter using current
                        billing, interval, and raw-reading context only.
                      </p>
                    </div>
                    <span className="artifact-pill">
                      {missingReadsIssues.length} open recovery issues
                    </span>
                  </div>

                  {missingReadsIssues.length === 0 ? (
                    <p className="muted">
                      No missing reads or recovery issues match the current bounded selected-meter scope.
                    </p>
                  ) : (
                    <div className="readings-table-shell">
                      <table className="readings-table">
                        <thead>
                          <tr>
                            <th scope="col">Issue</th>
                            <th scope="col">Severity</th>
                            <th scope="col">State</th>
                            <th scope="col">Missing window</th>
                            <th scope="col">Observed</th>
                            <th scope="col">Context</th>
                            <th scope="col">Action</th>
                          </tr>
                        </thead>
                        <tbody>
                          {missingReadsIssues.map((issue) => (
                            <tr key={issue.id}>
                              <td>
                                <strong>{formatValidationIssueType(issue.issue_type)}</strong>
                                <div className="muted">{issue.reason}</div>
                              </td>
                              <td>
                                <span
                                  className={`status-pill ${buildValidationSeverityTone(
                                    issue.severity,
                                  )}`}
                                >
                                  {formatStatusLabel(issue.severity)}
                                </span>
                              </td>
                              <td>
                                <span className="status-pill warning">
                                  {formatStatusLabel(issue.state)}
                                </span>
                              </td>
                              <td>{issue.missing_window}</td>
                              <td>{formatDateTime(issue.observed_at)}</td>
                              <td>
                                <strong>{issue.related_context}</strong>
                                <div className="muted">{issue.related_source}</div>
                              </td>
                              <td>
                                <div className="artifact-row">
                                  <Link className="secondary-button" href={issue.related_section_href}>
                                    {issue.related_action_label}
                                  </Link>
                                  <Link
                                    className="primary-button"
                                    href={buildRecoveryActionHref(selectedMeter.id, issue)}
                                  >
                                    Open on-demand read handoff
                                  </Link>
                                </div>
                                <div className="muted">
                                  Opens the existing commands wizard with approvals behavior unchanged.
                                </div>
                              </td>
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    </div>
                  )}
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

                <section className="subpanel" id="billing-reads-section">
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

                <section className="subpanel" id="recent-reading-context-section">
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
