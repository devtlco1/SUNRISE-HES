"use client";

import Link from "next/link";
import { useCallback, useEffect, useMemo, useState } from "react";

import {
  DashboardLaunchCard,
  DashboardMetricCard,
  DashboardPanel,
  DashboardTableShell,
} from "./dashboard-foundation-ui";
import {
  OverviewProductIcon,
  OverviewProfitIcon,
  OverviewUsersIcon,
  OverviewViewsIcon,
} from "./nextadmin-icons";
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
  href: string;
  action: string;
};

type DashboardMetricAccent = "default" | "positive" | "warning" | "danger";

type WorkspaceLaunchGroup = {
  id: string;
  label: string;
  title: string;
  summary: string;
  highlights: string[];
  links: Array<{
    href: string;
    label: string;
  }>;
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

  const overviewCards = useMemo<
    Array<{
      label: string;
      value: string;
      note: string;
      meta: string;
      accent: DashboardMetricAccent;
      icon:
        | typeof OverviewProductIcon
        | typeof OverviewProfitIcon
        | typeof OverviewUsersIcon
        | typeof OverviewViewsIcon;
    }>
  >(
    () => [
      {
        label: "Meters in current scope",
        value: meterOverview ? String(meterOverview.total) : "Not available",
        note: meterOverview
          ? `${formatCountLabel(meterOverview.activeInventoryCount, "active meter", "active meters")} are visible in the current result set.`
          : "Meter inventory summary is unavailable.",
        meta: meterOverview ? "Live inventory" : "Unavailable",
        accent: "default" as DashboardMetricAccent,
        icon: OverviewProductIcon,
      },
      {
        label: "Pending approvals",
        value: pendingApprovalsCount !== null ? String(pendingApprovalsCount) : "Not available",
        note:
          pendingApprovalsCount !== null
            ? "Bulk command requests currently waiting in the existing approvals queue."
            : "Pending approval summary is unavailable.",
        meta: pendingApprovalsCount !== null ? "Command queue" : "Unavailable",
        accent:
          pendingApprovalsCount && pendingApprovalsCount > 0 ? "warning" : "positive",
        icon: OverviewProfitIcon,
      },
      {
        label: "Connectivity incidents",
        value: connectivitySummary ? String(connectivitySummary.incidentCount) : "Not available",
        note: connectivitySummary
          ? `${connectivitySummary.offlineCount} offline, ${connectivitySummary.staleCount} stale, ${connectivitySummary.degradedCount} degraded in the current scope.`
          : "Connectivity incident summary is unavailable.",
        meta: connectivitySummary ? "Watch list" : "Unavailable",
        accent:
          connectivitySummary && connectivitySummary.incidentCount > 0
            ? "warning"
            : "positive",
        icon: OverviewViewsIcon,
      },
      {
        label: "Validation issues",
        value: readingsSummary ? String(readingsSummary.validationIssueCount) : "Not available",
        note: readingsSummary
          ? `${formatCountLabel(readingsSummary.metersWithValidationIssues, "meter", "meters")} currently carry validation-derived issues.`
          : "Readings validation summary is unavailable.",
        meta: readingsSummary ? "Readings review" : "Unavailable",
        accent:
          readingsSummary && readingsSummary.validationIssueCount > 0
            ? "danger"
            : "positive",
        icon: OverviewUsersIcon,
      },
    ],
    [connectivitySummary, meterOverview, pendingApprovalsCount, readingsSummary],
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
        summary: "Bulk command requests are waiting in the existing approvals queue.",
        href: "/commands",
        action: "Open commands",
      });
    }

    if ((connectivitySummary?.incidentCount ?? 0) > 0) {
      items.push({
        id: "connectivity-incidents",
        label: "Connectivity incidents",
        count: connectivitySummary?.incidentCount ?? 0,
        summary: `${connectivitySummary?.offlineCount ?? 0} offline, ${connectivitySummary?.staleCount ?? 0} stale, and ${connectivitySummary?.degradedCount ?? 0} degraded contexts need review.`,
        href: "/connectivity",
        action: "Open connectivity",
      });
    }

    if ((readingsSummary?.validationIssueCount ?? 0) > 0) {
      items.push({
        id: "validation-issues",
        label: "Validation issues",
        count: readingsSummary?.validationIssueCount ?? 0,
        summary: `${readingsSummary?.metersWithValidationIssues ?? 0} meters currently carry validation-derived issues.`,
        href: "/readings",
        action: "Open readings",
      });
    }

    if ((readingsSummary?.missingReadsIssueCount ?? 0) > 0) {
      items.push({
        id: "recovery-issues",
        label: "Recovery issues",
        count: readingsSummary?.missingReadsIssueCount ?? 0,
        summary: `${readingsSummary?.metersWithRecoveryIssues ?? 0} meters currently carry missing-reads or stale-window recovery issues.`,
        href: "/readings",
        action: "Open readings",
      });
    }

    if ((problematicRecentCommandCount ?? 0) > 0) {
      items.push({
        id: "problematic-commands",
        label: "Problem command activity",
        count: problematicRecentCommandCount ?? 0,
        summary: "Recent command activity includes failed, timed-out, or cancelled outcomes.",
        href: "/jobs-events-alerts?attentionContext=dashboard_attention_queue&activityFilter=attention",
        action: "Open monitoring center",
      });
    }

    return items;
  }, [
    connectivitySummary,
    pendingApprovalsCount,
    problematicRecentCommandCount,
    readingsSummary,
  ]);

  const latestRecentCommandUpdatedAt = useMemo(() => {
    if (!recentCommands?.length) {
      return null;
    }

    return [...recentCommands]
      .sort(
        (left, right) =>
          new Date(right.latest_updated_at).getTime() -
          new Date(left.latest_updated_at).getTime(),
      )[0]?.latest_updated_at;
  }, [recentCommands]);

  const homeSignals = useMemo<
    Array<{
      label: string;
      value: string;
      note: string;
      accent: DashboardMetricAccent;
    }>
  >(
    () => [
      {
        label: "Overview status",
        value: overviewStatus,
        note:
          pageError && (meterOverview || recentCommands || connectivitySummary || readingsSummary)
            ? "Some dashboard sources are partial, but the workspace remains usable."
            : "The shell, dashboard cards, and launch areas are aligned around current Sunrise HES routes.",
        accent:
          pageError && !meterOverview && !recentCommands ? "danger" : pageError ? "warning" : "positive",
      },
      {
        label: "Attention queue",
        value: formatCountLabel(attentionQueueItems.length, "priority lane", "priority lanes"),
        note:
          attentionQueueItems.length > 0
            ? "Derived from approvals, connectivity, readings, and command outcome signals."
            : "No derived attention queues are currently elevated in the current dashboard scope.",
        accent: attentionQueueItems.length > 0 ? "warning" : "positive",
      },
      {
        label: "Context coverage",
        value: readingsSummary
          ? formatCountLabel(readingsSummary.evaluatedMeters, "meter context", "meter contexts")
          : "Coverage unavailable",
        note: connectivitySummary
          ? `${formatCountLabel(connectivitySummary.contextLoadedMeters, "connectivity context", "connectivity contexts")} currently feed this dashboard.`
          : "Connectivity and readings coverage will appear once the current scope resolves.",
        accent: readingsSummary || connectivitySummary ? "default" : "warning",
      },
    ],
    [
      attentionQueueItems.length,
      connectivitySummary,
      meterOverview,
      overviewStatus,
      pageError,
      readingsSummary,
      recentCommands,
    ],
  );

  const workspaceLaunchGroups = useMemo<WorkspaceLaunchGroup[]>(
    () => [
      {
        id: "commercial",
        label: "Commercial",
        title: "Customer and account follow-through",
        summary:
          "Subscribers, accounts, and service points remain the commercial follow-through routes from the dashboard.",
        highlights: [
          "Three customer-facing routes are grouped together.",
          "Use them when an operational issue needs subscriber, account, or premise context.",
          "They keep the product routes intact while the shell changes around them.",
        ],
        links: [
          { href: "/subscribers", label: "Open subscribers" },
          { href: "/accounts", label: "Open accounts" },
          { href: "/service-points", label: "Open service points" },
        ],
      },
      {
        id: "operations",
        label: "Operations",
        title: "Primary operational routes",
        summary:
          "Meters, readings, connectivity, commands, and monitoring remain the main Sunrise HES operational drill-down surfaces.",
        highlights: [
          pendingApprovalsCount !== null
            ? `${pendingApprovalsCount} pending approvals visible right now.`
            : "Pending approval context currently unavailable.",
          connectivitySummary
            ? `${connectivitySummary.incidentCount} connectivity incidents in the current scope.`
            : "Connectivity incident context currently unavailable.",
          readingsSummary
            ? `${readingsSummary.validationIssueCount} validation issues and ${readingsSummary.missingReadsIssueCount} recovery issues remain visible.`
            : "Readings issue context currently unavailable.",
        ],
        links: [
          { href: "/meters", label: "Open meters" },
          { href: "/readings", label: "Open readings" },
          { href: "/connectivity", label: "Open connectivity" },
          { href: "/commands", label: "Open commands" },
          { href: "/jobs-events-alerts", label: "Open jobs / events / alerts" },
        ],
      },
      {
        id: "network",
        label: "Network",
        title: "Network and location context",
        summary:
          "GIS Lite plus transformer and substation routes provide network and location follow-through from the dashboard.",
        highlights: [
          "GIS Lite and transformer/substation routes stay directly reachable from home.",
          "Use them when review needs feeder, location, or asset context.",
          "They remain unchanged functionally while the shell adopts the new system.",
        ],
        links: [
          { href: "/gis-lite", label: "Open GIS Lite" },
          {
            href: "/transformers-substations",
            label: "Open transformers / substations",
          },
        ],
      },
    ],
    [connectivitySummary, pendingApprovalsCount, readingsSummary],
  );

  const launchAreaCards = useMemo(
    () => [
      {
        label: "Readings review",
        value: readingsSummary ? String(readingsSummary.validationIssueCount) : "Not available",
        note: readingsSummary
          ? `${readingsSummary.missingReadsIssueCount} recovery issues remain available through the readings workspace.`
          : "Readings review context is not available right now.",
        href: "/readings",
        action: "Open readings",
      },
      {
        label: "Connectivity watch",
        value: connectivitySummary ? String(connectivitySummary.incidentCount) : "Not available",
        note: connectivitySummary
          ? `${connectivitySummary.offlineCount} offline, ${connectivitySummary.staleCount} stale, and ${connectivitySummary.degradedCount} degraded contexts are currently visible.`
          : "Connectivity watch context is not available right now.",
        href: "/connectivity",
        action: "Open connectivity",
      },
      {
        label: "Command center",
        value: pendingApprovalsCount !== null ? String(pendingApprovalsCount) : "Not available",
        note: pendingApprovalsCount !== null
          ? `${problematicRecentCommandCount ?? 0} recent command outcomes require closer review.`
          : "Command queue context is not available right now.",
        href: "/commands",
        action: "Open commands",
      },
      {
        label: "Monitoring center",
        value: recentCommands
          ? formatCountLabel(recentCommands.length, "recent command", "recent commands")
          : "Unavailable",
        note:
          recentCommands && latestRecentCommandUpdatedAt
            ? `Latest activity updated ${formatDurationFromMs(Date.now() - new Date(latestRecentCommandUpdatedAt).getTime())} ago in the current dashboard feed.`
            : "Jobs, events, and alert activity remain available through the monitoring center.",
        href: "/jobs-events-alerts?attentionContext=dashboard_attention_queue&activityFilter=attention",
        action: "Open monitoring center",
      },
    ],
    [
      connectivitySummary,
      latestRecentCommandUpdatedAt,
      pendingApprovalsCount,
      problematicRecentCommandCount,
      readingsSummary,
      recentCommands,
    ],
  );

  const commandFamilyCount = useMemo(
    () => (recentCommands ? new Set(recentCommands.map((item) => item.command_family)).size : null),
    [recentCommands],
  );

  return (
    <section className="na-home">
      {pageError ? <p className="error-banner">{pageError}</p> : null}

      <div className="na-home-overview-grid">
        {overviewCards.map((card) => (
          <DashboardMetricCard
            key={card.label}
            label={card.label}
            value={card.value}
            note={card.note}
            icon={card.icon}
            meta={card.meta}
            accent={card.accent}
          />
        ))}
      </div>

      <div className="na-home-grid">
        <DashboardPanel
          title="Operational overview"
          description="A truthful operator entry point into Sunrise HES workspaces, rebuilt on a NextAdmin-style dashboard rhythm without changing the underlying product flows."
          aside={<span className="na-status-pill na-status-pill-positive">{overviewStatus}</span>}
          className="na-span-8"
        >
          <div className="na-hero-card">
            <div className="na-hero-copy">
              <span className="na-section-eyebrow">Dashboard home</span>
              <h2>Operations control center</h2>
              <p className="na-card-copy">
                The new home page prioritizes real operational signals, structured launch
                areas, and a table-like activity surface so later page migrations inherit a
                consistent dashboard system.
              </p>
            </div>

            <div className="artifact-row">
              <Link className="primary-button" href="/readings">
                Open readings review
              </Link>
              <Link className="secondary-button" href="/connectivity">
                Open connectivity watch
              </Link>
              <Link
                className="secondary-button"
                href="/jobs-events-alerts?attentionContext=dashboard_attention_queue&activityFilter=attention"
              >
                Open monitoring center
              </Link>
            </div>

            <div className="na-mini-stat-grid">
              {homeSignals.map((signal) => (
                <div key={signal.label} className="na-mini-stat">
                  <span className={`na-status-pill na-status-pill-${signal.accent}`}>
                    {signal.label}
                  </span>
                  <strong>{signal.value}</strong>
                  <p className="na-card-copy">{signal.note}</p>
                </div>
              ))}
            </div>
          </div>
        </DashboardPanel>

        <DashboardPanel
          title="Attention queue"
          description="Derived work that should move operators into the right route quickly."
          aside={
            !isLoadingOverview ? (
              <span className="na-status-pill na-status-pill-warning">
                {formatCountLabel(attentionQueueItems.length, "lane", "lanes")}
              </span>
            ) : null
          }
          className="na-span-4"
        >
          {isLoadingOverview ? <p className="muted">Loading operator attention handoff...</p> : null}

          {!isLoadingOverview ? (
            <>
              {attentionQueueItems.length === 0 ? (
                <div className="na-empty-state">
                  <strong>Attention queue is clear.</strong>
                  <p className="na-card-copy">
                    No bounded operator attention items are currently derived from the stable
                    dashboard signals.
                  </p>
                </div>
              ) : (
                <div className="na-stack-list">
                  {attentionQueueItems.map((item) => (
                    <article key={item.id} className="na-list-card">
                      <div className="na-list-card-header">
                        <strong>{item.label}</strong>
                        <span className="na-status-pill na-status-pill-warning">
                          {item.count} attention
                        </span>
                      </div>
                      <p className="na-card-copy">{item.summary}</p>
                      <Link className="secondary-button" href={item.href}>
                        {item.action}
                      </Link>
                    </article>
                  ))}
                </div>
              )}
            </>
          ) : null}
        </DashboardPanel>

        <DashboardPanel
          title="Workspace launchpads"
          description="Route groups stay truthful to the current product while adopting a real dashboard shell and card rhythm."
          aside={
            <div className="artifact-row">
              {workspaceLaunchGroups.map((group) => (
                <span key={group.id} className="na-status-pill">
                  {group.label}
                </span>
              ))}
            </div>
          }
          className="na-span-7"
        >
          <div className="na-launch-grid">
            {workspaceLaunchGroups.map((group) => (
              <DashboardLaunchCard
                key={group.id}
                label={group.label}
                title={group.title}
                summary={group.summary}
                highlights={group.highlights}
                actions={
                  <>
                    {group.links.map((link) => (
                      <Link key={link.href} className="secondary-button" href={link.href}>
                        {link.label}
                      </Link>
                    ))}
                  </>
                }
              />
            ))}
          </div>
        </DashboardPanel>

        <DashboardPanel
          title="Current scope"
          description="Snapshot details that support the home page without inventing any analytics."
          aside={
            <span
              className={`na-status-pill ${
                pageError ? "na-status-pill-warning" : "na-status-pill-positive"
              }`}
            >
              {pageError ? "Partial" : "Healthy"}
            </span>
          }
          className="na-span-5"
        >
          <div className="na-mini-stat-grid">
            <div className="na-mini-stat">
              <span className="na-status-pill">Recent activity feed</span>
              <strong>
                {recentCommands
                  ? formatCountLabel(recentCommands.length, "item", "items")
                  : "Unavailable"}
              </strong>
              <p className="na-card-copy">
                {recentCommands
                  ? `${commandFamilyCount ?? 0} command families are represented in the current feed.`
                  : "Recent command activity is unavailable."}
              </p>
            </div>

            <div className="na-mini-stat">
              <span className="na-status-pill">Coverage notes</span>
              <strong>
                {readingsSummary
                  ? formatCountLabel(readingsSummary.evaluatedMeters, "meter context", "meter contexts")
                  : "Unavailable"}
              </strong>
              <p className="na-card-copy">
                {connectivitySummary
                  ? `${formatCountLabel(connectivitySummary.contextLoadedMeters, "connectivity context", "connectivity contexts")} currently feed this dashboard.`
                  : "Connectivity context is unavailable right now."}
              </p>
            </div>

            <div className="na-mini-stat">
              <span className="na-status-pill">Latest activity</span>
              <strong>
                {recentCommands && latestRecentCommandUpdatedAt
                  ? formatDurationFromMs(
                      Date.now() - new Date(latestRecentCommandUpdatedAt).getTime(),
                    )
                  : "Unavailable"}
              </strong>
              <p className="na-card-copy">
                {recentCommands && latestRecentCommandUpdatedAt
                  ? "Time since the most recent command update in the current feed."
                  : "Recent command activity has not been loaded yet."}
              </p>
            </div>
          </div>
        </DashboardPanel>

        <div className="na-span-8">
          <DashboardTableShell
            title="Recent command activity"
            description="A table-like operational feed using the current recent-commands read model."
            aside={
              !isLoadingOverview && recentCommands ? (
                <span className="na-status-pill">
                  {formatCountLabel(recentCommands.length, "item", "items")}
                </span>
              ) : null
            }
          >
            {isLoadingOverview ? <p className="muted">Loading recent command activity...</p> : null}

            {!isLoadingOverview ? (
              <>
                {recentCommands === null ? (
                  <div className="na-empty-state">
                    <strong>Recent activity is unavailable.</strong>
                    <p className="na-card-copy">Recent command activity is not available.</p>
                  </div>
                ) : null}

                {recentCommands !== null && recentCommands.length === 0 ? (
                  <div className="na-empty-state">
                    <strong>No recent command activity.</strong>
                    <p className="na-card-copy">
                      No recent command activity is currently visible, but the stable
                      drill-down surfaces remain available from the launch areas above.
                    </p>
                  </div>
                ) : null}

                {recentCommands?.length ? (
                  <div className="na-table-scroll">
                    <table className="na-data-table">
                      <thead>
                        <tr>
                          <th>Template</th>
                          <th>Family</th>
                          <th>Meter</th>
                          <th>Outcome</th>
                          <th>Updated</th>
                        </tr>
                      </thead>
                      <tbody>
                        {recentCommands.map((command) => (
                          <tr key={command.command_id}>
                            <td>
                              <strong>{command.command_template_code}</strong>
                            </td>
                            <td>{formatStatusLabel(command.command_family)}</td>
                            <td>{command.meter_id}</td>
                            <td>
                              <div className="command-list-item-meta">
                                <span className="status-pill">
                                  {formatStatusLabel(command.command_status)}
                                </span>
                                <span>{formatFamilySummary(command.family_specific_outcome_summary)}</span>
                              </div>
                            </td>
                            <td>{formatDateTime(command.latest_updated_at)}</td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                ) : null}
              </>
            ) : null}
          </DashboardTableShell>
        </div>

        <DashboardPanel
          title="Operator handoff"
          description="Quick route launches that mirror the main dashboard lanes."
          className="na-span-4"
        >
          {isLoadingOverview ? <p className="muted">Loading operations dashboard...</p> : null}

          {!isLoadingOverview ? (
            <div className="na-stack-list">
              {launchAreaCards.map((card) => (
                <article key={card.label} className="na-list-card">
                  <div className="na-list-card-header">
                    <strong>{card.label}</strong>
                    <span
                      className={`na-status-pill ${
                        card.label.includes("Connectivity")
                          ? "na-status-pill-warning"
                          : "na-status-pill-positive"
                      }`}
                    >
                      {card.value}
                    </span>
                  </div>
                  <p className="na-card-copy">{card.note}</p>
                  <Link className="secondary-button" href={card.href}>
                    {card.action}
                  </Link>
                </article>
              ))}
            </div>
          ) : null}
        </DashboardPanel>
      </div>
    </section>
  );
}
