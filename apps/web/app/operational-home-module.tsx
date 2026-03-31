"use client";

import Link from "next/link";
import { useCallback, useEffect, useMemo, useState } from "react";

import type { AuthorizedFetch } from "./operational-shell";

type MeterListItem = {
  id: string;
  serial_number: string;
  current_status: string;
  last_seen_at: string | null;
};

type MeterListResponse = {
  total: number;
  items: MeterListItem[];
};

type CommandRecentItem = {
  command_id: string;
  command_family: "profile_capture" | "relay_control";
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

type MeterOverview = {
  total: number;
  metersWithRecentSignal: number;
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

function formatFamilySummary(item: Record<string, string | null>): string {
  if ("terminal_status_category" in item) {
    return item.terminal_status_category ?? "No terminal status yet";
  }
  if ("relay_control_operation" in item) {
    const operation = item.relay_control_operation ?? "relay";
    const outcome = item.relay_control_execution_outcome ?? "pending";
    return `${operation} (${outcome})`;
  }
  return "No operational summary yet";
}

export function OperationalHomeModule({
  authorizedFetch,
}: {
  authorizedFetch: AuthorizedFetch;
}) {
  const [meterOverview, setMeterOverview] = useState<MeterOverview | null>(null);
  const [recentCommands, setRecentCommands] = useState<CommandRecentItem[] | null>(null);
  const [pageError, setPageError] = useState<string | null>(null);
  const [isLoadingOverview, setIsLoadingOverview] = useState(false);

  const loadOverview = useCallback(async () => {
    setIsLoadingOverview(true);
    setPageError(null);

    const [metersResult, commandsResult] = await Promise.allSettled([
      authorizedFetch<MeterListResponse>("/api/v1/meters?offset=0&limit=20"),
      authorizedFetch<CommandRecentListResponse>("/api/v1/commands/recent?limit=5"),
    ]);

    const hasMeterOverview = metersResult.status === "fulfilled";
    const hasRecentCommands = commandsResult.status === "fulfilled";

    if (hasMeterOverview) {
      setMeterOverview({
        total: metersResult.value.total,
        metersWithRecentSignal: metersResult.value.items.filter(
          (item) => item.last_seen_at !== null,
        ).length,
      });
    } else {
      setMeterOverview(null);
    }

    if (hasRecentCommands) {
      setRecentCommands(commandsResult.value.items);
    } else {
      setRecentCommands(null);
    }

    if (!hasMeterOverview && !hasRecentCommands) {
      const errors = [metersResult, commandsResult]
        .filter((result): result is PromiseRejectedResult => result.status === "rejected")
        .map((result) =>
          result.reason instanceof Error
            ? result.reason.message
            : "Unable to load operational overview.",
        );
      setPageError(errors[0] ?? "Unable to load operational overview.");
    } else if (!hasMeterOverview || !hasRecentCommands) {
      setPageError("Unable to load complete operational overview context.");
    }

    setIsLoadingOverview(false);
  }, [authorizedFetch]);

  useEffect(() => {
    void loadOverview();
  }, [loadOverview]);

  const overviewCards = useMemo(
    () => [
      {
        label: "Meters in current result set",
        value: meterOverview ? String(meterOverview.total) : "Not available",
      },
      {
        label: "Meters with recent signal",
        value: meterOverview
          ? String(meterOverview.metersWithRecentSignal)
          : "Not available",
      },
      {
        label: "Recent commands loaded",
        value: recentCommands ? String(recentCommands.length) : "Not available",
      },
      {
        label: "Operational families in recent activity",
        value: recentCommands
          ? String(new Set(recentCommands.map((item) => item.command_family)).size)
          : "Not available",
      },
    ],
    [meterOverview, recentCommands],
  );

  const overviewStatus = useMemo(() => {
    if (isLoadingOverview) {
      return "Loading overview";
    }
    if (pageError && (meterOverview !== null || recentCommands !== null)) {
      return "Partial context";
    }
    return "Overview ready";
  }, [isLoadingOverview, meterOverview, pageError, recentCommands]);

  return (
    <section className="panel">
      {pageError ? <p className="error-banner">{pageError}</p> : null}

      <div className="detail-stack">
        <section className="subpanel">
          <div className="section-heading">
            <div>
              <h2>Operational overview</h2>
              <p className="muted">
                Compact operational entry context built from the current stable
                meter, command, and connectivity baselines.
              </p>
            </div>
            <span className="artifact-pill">{overviewStatus}</span>
          </div>

          {isLoadingOverview ? (
            <p className="muted">Loading operational overview...</p>
          ) : null}

          {!isLoadingOverview ? (
            <div className="meter-summary-grid">
              {overviewCards.map((card) => (
                <div key={card.label} className="stat-card">
                  <span className="stat-label">{card.label}</span>
                  <strong>{card.value}</strong>
                </div>
              ))}
            </div>
          ) : null}
        </section>

        <section className="subpanel">
          <div className="section-heading">
            <div>
              <h2>Operational modules</h2>
              <p className="muted">
                Clear entry paths into the current bounded operational pages.
              </p>
            </div>
          </div>

          <div className="meter-summary-grid">
            <Link className="meter-list-item" href="/meters">
              <strong>Meters</strong>
              <p className="muted">
                Browse the current bounded meter list and continue into meter
                details.
              </p>
            </Link>
            <Link className="meter-list-item" href="/commands">
              <strong>Commands</strong>
              <p className="muted">
                Review recent stable operational commands and bounded command
                detail.
              </p>
            </Link>
            <Link className="meter-list-item" href="/connectivity">
              <strong>Connectivity</strong>
              <p className="muted">
                Review compact connectivity context and navigate into existing
                meter details.
              </p>
            </Link>
          </div>
        </section>

        <section className="subpanel">
          <div className="section-heading">
            <div>
              <h2>Recent operational activity</h2>
              <p className="muted">
                Lightweight recent activity snippets from the existing recent
                command read model.
              </p>
            </div>
          </div>

          {isLoadingOverview ? (
            <p className="muted">Loading recent operational activity...</p>
          ) : null}

          {!isLoadingOverview ? (
            <div className="command-list">
              {recentCommands === null ? (
                <p className="muted">Recent activity not available.</p>
              ) : null}

              {recentCommands !== null && recentCommands.length === 0 ? (
                <p className="muted">No recent command activity available.</p>
              ) : null}

              {recentCommands?.map((command) => (
                <div key={command.command_id} className="command-list-item">
                  <div className="command-list-item-header">
                    <strong>{command.command_template_code}</strong>
                    <span className="status-pill">{command.command_status}</span>
                  </div>
                  <div className="command-list-item-meta">
                    <span>{command.command_family}</span>
                    <span>Meter {command.meter_id}</span>
                  </div>
                  <div className="command-list-item-meta">
                    <span>
                      {formatFamilySummary(command.family_specific_outcome_summary)}
                    </span>
                    <span>Updated {formatDateTime(command.latest_updated_at)}</span>
                  </div>
                </div>
              ))}
            </div>
          ) : null}
        </section>
      </div>
    </section>
  );
}
