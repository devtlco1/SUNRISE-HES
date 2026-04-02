"use client";

import Link from "next/link";
import { useCallback, useEffect, useMemo, useState } from "react";

import type { AuthorizedFetch } from "./operational-shell";

type MeterListItem = {
  id: string;
  serial_number: string;
  current_status: string;
  last_seen_at: string | null;
  is_active: boolean;
};

type MeterListResponse = {
  total: number;
  items: MeterListItem[];
};

type CommandRecentItem = {
  command_id: string;
  command_family: "profile_capture" | "relay_control" | "on_demand_read";
  command_status: string;
  meter_id: string;
  command_template_code: string;
  family_specific_outcome_summary: Record<string, string | null>;
  latest_updated_at: string;
};

type CommandRecentListResponse = {
  total: number;
  items: CommandRecentItem[];
};

type ConnectivitySession = {
  id: string;
  started_at: string;
  ended_at: string | null;
  status: string;
  session_purpose: string;
};

type ConnectivitySessionHistoryListResponse = {
  total: number;
  items: ConnectivitySession[];
};

type MeterReadingItem = {
  id: string;
  captured_at: string;
};

type MeterReadingListResponse = {
  total: number;
  items: MeterReadingItem[];
};

type MeterRegisterSnapshotItem = {
  id: string;
  snapshot_type: string;
};

type MeterRegisterSnapshotListResponse = {
  total: number;
  items: MeterRegisterSnapshotItem[];
};

type LoadProfileChannelItem = {
  id: string;
  channel_code: string;
};

type LoadProfileChannelListResponse = {
  total: number;
  items: LoadProfileChannelItem[];
};

type LoadProfileIntervalItem = {
  id: string;
  channel_id: string;
  interval_start: string;
  interval_end: string;
  value_numeric: string | null;
  quality: string | null;
};

type LoadProfileIntervalListResponse = {
  total: number;
  items: LoadProfileIntervalItem[];
};

type MeterOverview = {
  total: number;
  activeInventoryCount: number;
  metersWithRecentSignal: number;
};

type ConnectivityIncidentState = "offline" | "stale" | "degraded";

type ConnectivitySummary = {
  incidentCount: number;
  offlineCount: number;
  staleCount: number;
  degradedCount: number;
  metersWithRecentSignal: number;
  contextLoadedMeters: number;
};

type ReadingsSummary = {
  validationIssueCount: number;
  missingReadsIssueCount: number;
  metersWithValidationIssues: number;
  metersWithRecoveryIssues: number;
  evaluatedMeters: number;
};

type AttentionQueueItem = {
  id: string;
  label: string;
  count: number;
  summary: string;
};

const STALE_SIGNAL_THRESHOLD_MS = 1000 * 60 * 60 * 24;

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

function formatDurationFromMs(durationMs: number): string {
  const clampedDurationMs = Math.max(durationMs, 0);
  const totalMinutes = Math.floor(clampedDurationMs / (1000 * 60));
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

function formatFamilySummary(item: Record<string, string | null>): string {
  if ("terminal_status_category" in item) {
    return item.terminal_status_category ?? "No terminal status yet";
  }
  if ("relay_control_operation" in item) {
    const operation = item.relay_control_operation ?? "relay";
    const outcome = item.relay_control_execution_outcome ?? "pending";
    return `${operation} (${outcome})`;
  }
  if ("on_demand_read_operation" in item) {
    const operation = item.on_demand_read_operation ?? "read";
    const snapshotType = item.snapshot_type ?? "snapshot";
    const outcome = item.on_demand_read_execution_outcome ?? "pending";
    return `${operation} ${snapshotType} (${outcome})`;
  }
  return "No operational summary yet";
}

function formatCountLabel(count: number, singular: string, plural: string): string {
  return `${count} ${count === 1 ? singular : plural}`;
}

function buildConnectivityIncidentState(
  meter: MeterListItem,
  latestSession: ConnectivitySession | null,
): ConnectivityIncidentState | null {
  if (meter.last_seen_at === null) {
    return "offline";
  }

  const latestSessionStatus = latestSession?.status.toLowerCase() ?? "";
  if (
    latestSessionStatus === "failed" ||
    latestSessionStatus === "timed_out" ||
    latestSessionStatus === "cancelled"
  ) {
    return "degraded";
  }

  const lastSeenDate = new Date(meter.last_seen_at);
  if (Number.isNaN(lastSeenDate.getTime())) {
    return null;
  }

  return Date.now() - lastSeenDate.getTime() >= STALE_SIGNAL_THRESHOLD_MS ? "stale" : null;
}

function buildReadingsMeterSummary({
  readings,
  billingSnapshots,
  loadProfileChannels,
  loadProfileIntervals,
}: {
  readings: MeterReadingItem[];
  billingSnapshots: MeterRegisterSnapshotItem[];
  loadProfileChannels: LoadProfileChannelItem[];
  loadProfileIntervals: LoadProfileIntervalItem[];
}): {
  validationIssueCount: number;
  missingReadsIssueCount: number;
} {
  let validationIssueCount = 0;
  let missingReadsIssueCount = 0;

  if (billingSnapshots.length === 0) {
    validationIssueCount += 1;
    missingReadsIssueCount += 1;
  }

  loadProfileIntervals.forEach((interval) => {
    if (interval.value_numeric === null) {
      validationIssueCount += 1;
    }

    if (
      interval.quality === "suspect" ||
      interval.quality === "estimated" ||
      interval.quality === "missing"
    ) {
      validationIssueCount += 1;
    }
  });

  const intervalsByChannel = new Map<string, LoadProfileIntervalItem[]>();
  loadProfileIntervals.forEach((interval) => {
    const channelIntervals = intervalsByChannel.get(interval.channel_id) ?? [];
    channelIntervals.push(interval);
    intervalsByChannel.set(interval.channel_id, channelIntervals);
  });

  intervalsByChannel.forEach((intervals) => {
    const sortedIntervals = [...intervals].sort(
      (left, right) =>
        new Date(right.interval_start).getTime() - new Date(left.interval_start).getTime(),
    );

    for (let index = 0; index < sortedIntervals.length - 1; index += 1) {
      const newerInterval = sortedIntervals[index];
      const olderInterval = sortedIntervals[index + 1];
      const gapMs =
        new Date(newerInterval.interval_start).getTime() -
        new Date(olderInterval.interval_end).getTime();

      if (gapMs > 0) {
        validationIssueCount += 1;
      }
    }
  });

  if (loadProfileChannels.length > 0 && loadProfileIntervals.length === 0) {
    missingReadsIssueCount += 1;
  }

  if (readings.length === 0) {
    missingReadsIssueCount += 1;
  }

  const latestReading =
    [...readings].sort(
      (left, right) =>
        new Date(right.captured_at).getTime() - new Date(left.captured_at).getTime(),
    )[0] ?? null;
  const latestInterval =
    [...loadProfileIntervals].sort(
      (left, right) =>
        new Date(right.interval_end).getTime() - new Date(left.interval_end).getTime(),
    )[0] ?? null;

  if (latestReading && latestInterval) {
    const staleGapMs =
      new Date(latestReading.captured_at).getTime() -
      new Date(latestInterval.interval_end).getTime();

    if (staleGapMs > 0) {
      missingReadsIssueCount += 1;
    }
  }

  return {
    validationIssueCount,
    missingReadsIssueCount,
  };
}

export function OperationalHomeModule({
  authorizedFetch,
}: {
  authorizedFetch: AuthorizedFetch;
}) {
  const [meterOverview, setMeterOverview] = useState<MeterOverview | null>(null);
  const [recentCommands, setRecentCommands] = useState<CommandRecentItem[] | null>(null);
  const [pendingApprovalsCount, setPendingApprovalsCount] = useState<number | null>(null);
  const [connectivitySummary, setConnectivitySummary] = useState<ConnectivitySummary | null>(null);
  const [readingsSummary, setReadingsSummary] = useState<ReadingsSummary | null>(null);
  const [pageError, setPageError] = useState<string | null>(null);
  const [isLoadingOverview, setIsLoadingOverview] = useState(false);

  const loadConnectivitySummary = useCallback(
    async (
      meters: MeterListItem[],
    ): Promise<{ summary: ConnectivitySummary; contextIncomplete: boolean }> => {
      const sessionResults = await Promise.all(
        meters.map(async (meter) => {
          try {
            const response = await authorizedFetch<ConnectivitySessionHistoryListResponse>(
              `/api/v1/meters/${meter.id}/sessions?limit=1`,
            );
            return {
              meter,
              latestSession: response.items[0] ?? null,
              contextUnavailable: false,
            };
          } catch (_error) {
            return {
              meter,
              latestSession: null,
              contextUnavailable: true,
            };
          }
        }),
      );

      const incidentStateCounts = sessionResults.reduce(
        (counts, item) => {
          const incidentState = buildConnectivityIncidentState(item.meter, item.latestSession);
          if (incidentState === null) {
            return counts;
          }

          counts[incidentState] += 1;
          return counts;
        },
        {
          offline: 0,
          stale: 0,
          degraded: 0,
        },
      );

      return {
        summary: {
          incidentCount:
            incidentStateCounts.offline +
            incidentStateCounts.stale +
            incidentStateCounts.degraded,
          offlineCount: incidentStateCounts.offline,
          staleCount: incidentStateCounts.stale,
          degradedCount: incidentStateCounts.degraded,
          metersWithRecentSignal: meters.filter((meter) => meter.last_seen_at !== null).length,
          contextLoadedMeters: sessionResults.filter((item) => !item.contextUnavailable).length,
        },
        contextIncomplete: sessionResults.some((item) => item.contextUnavailable),
      };
    },
    [authorizedFetch],
  );

  const loadReadingsSummary = useCallback(
    async (
      meters: MeterListItem[],
    ): Promise<{ summary: ReadingsSummary; contextIncomplete: boolean }> => {
      const meterResults = await Promise.all(
        meters.map(async (meter) => {
          const [readingsResult, snapshotsResult, channelsResult, intervalsResult] =
            await Promise.allSettled([
              authorizedFetch<MeterReadingListResponse>(`/api/v1/meters/${meter.id}/readings?limit=10`),
              authorizedFetch<MeterRegisterSnapshotListResponse>(
                `/api/v1/meters/${meter.id}/register-snapshots?limit=25`,
              ),
              authorizedFetch<LoadProfileChannelListResponse>(
                `/api/v1/meters/${meter.id}/load-profile-channels`,
              ),
              authorizedFetch<LoadProfileIntervalListResponse>(
                `/api/v1/meters/${meter.id}/load-profile-intervals?limit=96`,
              ),
            ]);

          const contextUnavailable =
            readingsResult.status === "rejected" ||
            snapshotsResult.status === "rejected" ||
            channelsResult.status === "rejected" ||
            intervalsResult.status === "rejected";

          if (contextUnavailable) {
            return {
              meter,
              contextUnavailable,
              validationIssueCount: 0,
              missingReadsIssueCount: 0,
            };
          }

          const summary = buildReadingsMeterSummary({
            readings: readingsResult.value.items,
            billingSnapshots: snapshotsResult.value.items.filter(
              (item) => item.snapshot_type === "billing",
            ),
            loadProfileChannels: channelsResult.value.items,
            loadProfileIntervals: intervalsResult.value.items,
          });

          return {
            meter,
            contextUnavailable,
            validationIssueCount: summary.validationIssueCount,
            missingReadsIssueCount: summary.missingReadsIssueCount,
          };
        }),
      );

      return {
        summary: {
          validationIssueCount: meterResults.reduce(
            (total, item) => total + item.validationIssueCount,
            0,
          ),
          missingReadsIssueCount: meterResults.reduce(
            (total, item) => total + item.missingReadsIssueCount,
            0,
          ),
          metersWithValidationIssues: meterResults.filter(
            (item) => item.validationIssueCount > 0,
          ).length,
          metersWithRecoveryIssues: meterResults.filter(
            (item) => item.missingReadsIssueCount > 0,
          ).length,
          evaluatedMeters: meterResults.filter((item) => !item.contextUnavailable).length,
        },
        contextIncomplete: meterResults.some((item) => item.contextUnavailable),
      };
    },
    [authorizedFetch],
  );

  const loadOverview = useCallback(async () => {
    setIsLoadingOverview(true);
    setPageError(null);

    try {
      const [metersResult, recentCommandsResult, pendingApprovalsResult] = await Promise.allSettled([
        authorizedFetch<MeterListResponse>("/api/v1/meters?offset=0&limit=20"),
        authorizedFetch<CommandRecentListResponse>("/api/v1/commands/recent?limit=8"),
        authorizedFetch<CommandRecentListResponse>("/api/v1/commands/approvals/pending?limit=20"),
      ]);

      const hasMeterOverview = metersResult.status === "fulfilled";
      const hasRecentCommands = recentCommandsResult.status === "fulfilled";
      const hasPendingApprovals = pendingApprovalsResult.status === "fulfilled";

      if (hasMeterOverview) {
        setMeterOverview({
          total: metersResult.value.total,
          activeInventoryCount: metersResult.value.items.filter((item) => item.is_active).length,
          metersWithRecentSignal: metersResult.value.items.filter(
            (item) => item.last_seen_at !== null,
          ).length,
        });
      } else {
        setMeterOverview(null);
      }

      if (hasRecentCommands) {
        setRecentCommands(recentCommandsResult.value.items);
      } else {
        setRecentCommands(null);
      }

      if (hasPendingApprovals) {
        setPendingApprovalsCount(pendingApprovalsResult.value.items.length);
      } else {
        setPendingApprovalsCount(null);
      }

      let connectivityContextIncomplete = false;
      let readingsContextIncomplete = false;

      if (hasMeterOverview) {
        const [nextConnectivitySummary, nextReadingsSummary] = await Promise.all([
          loadConnectivitySummary(metersResult.value.items),
          loadReadingsSummary(metersResult.value.items),
        ]);
        setConnectivitySummary(nextConnectivitySummary.summary);
        setReadingsSummary(nextReadingsSummary.summary);
        connectivityContextIncomplete = nextConnectivitySummary.contextIncomplete;
        readingsContextIncomplete = nextReadingsSummary.contextIncomplete;
      } else {
        setConnectivitySummary(null);
        setReadingsSummary(null);
      }

      const topLevelFailures = [metersResult, recentCommandsResult, pendingApprovalsResult].filter(
        (result): result is PromiseRejectedResult => result.status === "rejected",
      );

      if (topLevelFailures.length === 3) {
        const firstError = topLevelFailures[0]?.reason;
        setPageError(
          firstError instanceof Error
            ? firstError.message
            : "Unable to load operations dashboard context.",
        );
        return;
      }

      if (
        topLevelFailures.length > 0 ||
        connectivityContextIncomplete ||
        readingsContextIncomplete
      ) {
        setPageError("Unable to load complete operations dashboard context.");
      }
    } finally {
      setIsLoadingOverview(false);
    }
  }, [authorizedFetch, loadConnectivitySummary, loadReadingsSummary]);

  useEffect(() => {
    void loadOverview();
  }, [loadOverview]);

  const overviewStatus = useMemo(() => {
    if (isLoadingOverview) {
      return "Loading overview";
    }
    if (pageError && (meterOverview || recentCommands || connectivitySummary || readingsSummary)) {
      return "Partial context";
    }
    if (pageError) {
      return "Overview unavailable";
    }
    return "Overview ready";
  }, [connectivitySummary, isLoadingOverview, meterOverview, pageError, readingsSummary, recentCommands]);

  const overviewCards = useMemo(
    () => [
      {
        label: "Meters in current dashboard scope",
        value: meterOverview ? String(meterOverview.total) : "Not available",
        note: meterOverview
          ? `${formatCountLabel(meterOverview.activeInventoryCount, "active inventory item", "active inventory items")} visible in the current bounded meter result set.`
          : "Meter inventory summary not available.",
      },
      {
        label: "Pending approvals",
        value: pendingApprovalsCount !== null ? String(pendingApprovalsCount) : "Not available",
        note:
          pendingApprovalsCount !== null
            ? "Bulk command requests currently waiting in the stable approvals queue."
            : "Pending approval summary not available.",
      },
      {
        label: "Connectivity incidents",
        value: connectivitySummary ? String(connectivitySummary.incidentCount) : "Not available",
        note: connectivitySummary
          ? `${connectivitySummary.offlineCount} offline • ${connectivitySummary.staleCount} stale • ${connectivitySummary.degradedCount} degraded in the current bounded connectivity scope.`
          : "Connectivity incident summary not available.",
      },
      {
        label: "Open validation issues",
        value: readingsSummary ? String(readingsSummary.validationIssueCount) : "Not available",
        note: readingsSummary
          ? `${formatCountLabel(readingsSummary.metersWithValidationIssues, "meter", "meters")} currently carry validation-derived issues in the bounded readings scope.`
          : "Readings validation summary not available.",
      },
      {
        label: "Open recovery issues",
        value: readingsSummary ? String(readingsSummary.missingReadsIssueCount) : "Not available",
        note: readingsSummary
          ? `${formatCountLabel(readingsSummary.metersWithRecoveryIssues, "meter", "meters")} currently carry missing-reads or stale-window recovery issues.`
          : "Recovery queue summary not available.",
      },
      {
        label: "Recent command activity",
        value: recentCommands ? String(recentCommands.length) : "Not available",
        note: recentCommands
          ? `${new Set(recentCommands.map((item) => item.command_family)).size} stable command families are represented in recent activity.`
          : "Recent command activity not available.",
      },
    ],
    [connectivitySummary, meterOverview, pendingApprovalsCount, readingsSummary, recentCommands],
  );
  const problematicRecentCommandCount = useMemo(
    () =>
      recentCommands?.filter((command) =>
        ["failed", "timed_out", "cancelled"].includes(command.command_status),
      ).length ?? null,
    [recentCommands],
  );
  const attentionQueueItems = useMemo(() => {
    const items: AttentionQueueItem[] = [];

    if ((pendingApprovalsCount ?? 0) > 0) {
      items.push({
        id: "pending-approvals",
        label: "Pending approvals",
        count: pendingApprovalsCount ?? 0,
        summary: "Bulk command requests are waiting in the stable approvals queue.",
      });
    }

    if ((connectivitySummary?.incidentCount ?? 0) > 0) {
      items.push({
        id: "connectivity-incidents",
        label: "Connectivity incidents",
        count: connectivitySummary?.incidentCount ?? 0,
        summary: `${connectivitySummary?.offlineCount ?? 0} offline, ${connectivitySummary?.staleCount ?? 0} stale, and ${connectivitySummary?.degradedCount ?? 0} degraded contexts need review.`,
      });
    }

    if ((readingsSummary?.validationIssueCount ?? 0) > 0) {
      items.push({
        id: "validation-issues",
        label: "Validation issues",
        count: readingsSummary?.validationIssueCount ?? 0,
        summary: `${readingsSummary?.metersWithValidationIssues ?? 0} meters currently carry validation-derived issues in the bounded readings scope.`,
      });
    }

    if ((readingsSummary?.missingReadsIssueCount ?? 0) > 0) {
      items.push({
        id: "recovery-issues",
        label: "Recovery issues",
        count: readingsSummary?.missingReadsIssueCount ?? 0,
        summary: `${readingsSummary?.metersWithRecoveryIssues ?? 0} meters currently carry missing-reads or stale-window recovery issues.`,
      });
    }

    if ((problematicRecentCommandCount ?? 0) > 0) {
      items.push({
        id: "problematic-commands",
        label: "Problem command activity",
        count: problematicRecentCommandCount ?? 0,
        summary: "Recent command activity includes failed, timed-out, or cancelled outcomes.",
      });
    }

    return items;
  }, [
    connectivitySummary,
    pendingApprovalsCount,
    problematicRecentCommandCount,
    readingsSummary,
  ]);

  return (
    <section className="panel">
      {pageError ? <p className="error-banner">{pageError}</p> : null}

      <div className="detail-stack">
        <section className="subpanel">
          <div className="section-heading">
            <div>
              <h2>Operations dashboard</h2>
              <p className="muted">
                First bounded operational dashboard for the home surface, summarizing the
                already-stable commands, connectivity, readings, and meter foundations.
              </p>
            </div>
            <span className="artifact-pill">{overviewStatus}</span>
          </div>

          {isLoadingOverview ? <p className="muted">Loading operations dashboard...</p> : null}

          {!isLoadingOverview ? (
            <div className="meter-summary-grid">
              {overviewCards.map((card) => (
                <div key={card.label} className="stat-card">
                  <span className="stat-label">{card.label}</span>
                  <strong>{card.value}</strong>
                  <p className="muted">{card.note}</p>
                </div>
              ))}
            </div>
          ) : null}
        </section>

        <section className="subpanel">
          <div className="section-heading">
            <div>
              <h2>Needs operator attention</h2>
              <p className="muted">
                Compact handoff queue derived from existing dashboard signals before drilling into
                the stable Jobs / Events / Alerts surface.
              </p>
            </div>
            <span className="artifact-pill">
              {attentionQueueItems.length} attention item
              {attentionQueueItems.length === 1 ? "" : "s"}
            </span>
          </div>

          {isLoadingOverview ? <p className="muted">Loading operator attention handoff...</p> : null}

          {!isLoadingOverview ? (
            <>
              {attentionQueueItems.length === 0 ? (
                <p className="muted">
                  No bounded operator attention items are currently derived from the stable
                  dashboard signals.
                </p>
              ) : (
                <div className="command-list">
                  {attentionQueueItems.map((item) => (
                    <article key={item.id} className="command-list-item">
                      <div className="command-list-item-header">
                        <strong>{item.label}</strong>
                        <span className="status-pill warning">{item.count} attention</span>
                      </div>
                      <div className="command-list-item-meta">
                        <span>
                          {formatCountLabel(item.count, "derived context", "derived contexts")}
                        </span>
                        <span>Home dashboard handoff</span>
                      </div>
                      <p className="muted">{item.summary}</p>
                    </article>
                  ))}
                </div>
              )}

              <div className="artifact-row">
                <Link className="secondary-button" href="/jobs-events-alerts">
                  Open jobs / events / alerts
                </Link>
                <span className="muted">
                  Use the monitoring center for the bounded activity list and alert-oriented review.
                </span>
              </div>
            </>
          ) : null}
        </section>

        <section className="subpanel">
          <div className="section-heading">
            <div>
              <h2>Operational summary panels</h2>
              <p className="muted">
                Summary plus drill-down across the current stable operational slices, without
                opening any new workflow architecture.
              </p>
            </div>
          </div>

          <div className="meter-summary-grid dashboard-module-grid">
            <article className="stat-card">
              <span className="stat-label">Commands queue</span>
              <strong>
                {pendingApprovalsCount !== null ? String(pendingApprovalsCount) : "Not available"}
              </strong>
              <p className="muted">
                Pending approvals remain in the stable bulk commands and approvals flow.
              </p>
              <div className="command-list-item-meta">
                <span>
                  {recentCommands
                    ? `${recentCommands.length} recent command items`
                    : "Recent command activity unavailable"}
                </span>
                <span>
                  {recentCommands
                    ? `${new Set(recentCommands.map((item) => item.command_family)).size} stable families visible`
                    : "Family mix unavailable"}
                </span>
              </div>
              <div className="artifact-row">
                <Link className="secondary-button" href="/commands">
                  Open commands
                </Link>
              </div>
            </article>

            <article className="stat-card">
              <span className="stat-label">Connectivity incidents</span>
              <strong>
                {connectivitySummary ? String(connectivitySummary.incidentCount) : "Not available"}
              </strong>
              <p className="muted">
                Offline, stale, and degraded signals stay bounded to the current connectivity scope.
              </p>
              <div className="command-list-item-meta">
                <span>
                  {connectivitySummary
                    ? `${connectivitySummary.offlineCount} offline • ${connectivitySummary.staleCount} stale`
                    : "Incident state mix unavailable"}
                </span>
                <span>
                  {connectivitySummary
                    ? `${connectivitySummary.degradedCount} degraded • ${connectivitySummary.metersWithRecentSignal} with recent signal`
                    : "Signal freshness unavailable"}
                </span>
              </div>
              <div className="artifact-row">
                <Link className="secondary-button" href="/connectivity">
                  Open connectivity
                </Link>
              </div>
            </article>

            <article className="stat-card">
              <span className="stat-label">Readings review</span>
              <strong>
                {readingsSummary ? String(readingsSummary.validationIssueCount) : "Not available"}
              </strong>
              <p className="muted">
                Validation and missing-reads recovery counts mirror the existing readings language.
              </p>
              <div className="command-list-item-meta">
                <span>
                  {readingsSummary
                    ? `${readingsSummary.validationIssueCount} validation issues`
                    : "Validation context unavailable"}
                </span>
                <span>
                  {readingsSummary
                    ? `${readingsSummary.missingReadsIssueCount} recovery issues`
                    : "Recovery queue unavailable"}
                </span>
              </div>
              <div className="artifact-row">
                <Link className="secondary-button" href="/readings">
                  Open readings
                </Link>
              </div>
            </article>

            <article className="stat-card">
              <span className="stat-label">Meter inventory</span>
              <strong>{meterOverview ? String(meterOverview.total) : "Not available"}</strong>
              <p className="muted">
                Current meter inventory context remains the bounded source for the dashboard scope.
              </p>
              <div className="command-list-item-meta">
                <span>
                  {meterOverview
                    ? `${meterOverview.activeInventoryCount} active inventory items`
                    : "Inventory state unavailable"}
                </span>
                <span>
                  {meterOverview
                    ? `${meterOverview.metersWithRecentSignal} with recent signal`
                    : "Signal context unavailable"}
                </span>
              </div>
              <div className="artifact-row">
                <Link className="secondary-button" href="/meters">
                  Open meters
                </Link>
                <Link className="secondary-button" href="/meters/import">
                  Open import wizard
                </Link>
              </div>
            </article>
          </div>

          {!isLoadingOverview && recentCommands?.length === 0 ? (
            <p className="muted">
              No recent command activity is currently visible, but the stable drill-down surfaces
              remain available from the summary panels above.
            </p>
          ) : null}
        </section>

        <section className="subpanel">
          <div className="section-heading">
            <div>
              <h2>Recent command activity</h2>
              <p className="muted">
                Lightweight command activity snippets from the stable recent-commands read model.
              </p>
            </div>
            <span className="artifact-pill">
              {recentCommands ? formatCountLabel(recentCommands.length, "item", "items") : "Unavailable"}
            </span>
          </div>

          {isLoadingOverview ? <p className="muted">Loading recent command activity...</p> : null}

          {!isLoadingOverview ? (
            <div className="command-list">
              {recentCommands === null ? <p className="muted">Recent command activity not available.</p> : null}

              {recentCommands !== null && recentCommands.length === 0 ? (
                <p className="muted">No recent command activity available.</p>
              ) : null}

              {recentCommands?.map((command) => (
                <div key={command.command_id} className="command-list-item">
                  <div className="command-list-item-header">
                    <strong>{command.command_template_code}</strong>
                    <span className="status-pill">{formatStatusLabel(command.command_status)}</span>
                  </div>
                  <div className="command-list-item-meta">
                    <span>{formatStatusLabel(command.command_family)}</span>
                    <span>Meter {command.meter_id}</span>
                  </div>
                  <div className="command-list-item-meta">
                    <span>{formatFamilySummary(command.family_specific_outcome_summary)}</span>
                    <span>Updated {formatDateTime(command.latest_updated_at)}</span>
                  </div>
                </div>
              ))}
            </div>
          ) : null}

          {!isLoadingOverview && connectivitySummary?.contextLoadedMeters !== undefined ? (
            <p className="muted">
              Connectivity incidents were derived for{" "}
              {formatCountLabel(
                connectivitySummary.contextLoadedMeters,
                "meter session context",
                "meter session contexts",
              )}
              . Readings review was derived for{" "}
              {readingsSummary
                ? formatCountLabel(readingsSummary.evaluatedMeters, "meter context", "meter contexts")
                : "0 meter contexts"}
              {" "}inside the current bounded dashboard scope.
            </p>
          ) : null}
        </section>
      </div>
    </section>
  );
}
