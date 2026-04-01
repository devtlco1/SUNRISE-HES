"use client";

import { useCallback, useEffect, useMemo, useState } from "react";

import type { AuthorizedFetch } from "../operational-shell";

type CommandOperationalFamily =
  | "profile_capture"
  | "relay_control"
  | "on_demand_read";
type FamilyFilter = "all" | CommandOperationalFamily;

type CommandRecentItem = {
  command_id: string;
  command_family: CommandOperationalFamily;
  command_category: string;
  command_status: string;
  meter_id: string;
  command_template_code: string;
  latest_command_execution_attempt_id: string | null;
  latest_command_execution_attempt_status: string | null;
  runtime_execution_record_id: string | null;
  family_specific_outcome_summary: Record<string, string | null>;
  orchestration_artifact_present: boolean;
  terminalization_artifact_present: boolean;
  execute_now_artifact_present: boolean;
  created_at: string;
  latest_updated_at: string;
};

type CommandRecentListResponse = {
  total: number;
  limit: number;
  family_filter: CommandOperationalFamily | null;
  items: CommandRecentItem[];
};

type CommandDetail = {
  command_id: string;
  command_family: CommandOperationalFamily;
  command_category: string;
  command_status: string;
  meter_id: string;
  command_template_code: string;
  latest_command_execution_attempt_id: string | null;
  latest_command_execution_attempt_status: string | null;
  runtime_execution_record_id: string | null;
  family_specific_outcome_summary: Record<string, string | null>;
  orchestration_artifact_present: boolean;
  terminalization_artifact_present: boolean;
  execute_now_artifact_present: boolean;
  created_at: string;
  latest_updated_at: string;
  projection_record: Record<string, unknown>;
};

type CommandDetailResponse = {
  result: CommandDetail;
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
  if ("on_demand_read_operation" in item) {
    const operation = item.on_demand_read_operation ?? "read";
    const snapshotType = item.snapshot_type ?? "snapshot";
    const outcome = item.on_demand_read_execution_outcome ?? "pending";
    return `${operation} ${snapshotType} (${outcome})`;
  }
  return "No operational summary yet";
}

function formatCommandFamilyLabel(value: CommandOperationalFamily): string {
  switch (value) {
    case "profile_capture":
      return "Profile capture";
    case "relay_control":
      return "Relay control";
    case "on_demand_read":
      return "On-demand read";
  }
}

function formatCommandCategoryLabel(value: string): string {
  return value
    .split("_")
    .filter(Boolean)
    .map((part) => part.charAt(0).toUpperCase() + part.slice(1))
    .join(" ");
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
    normalized.includes("acknowledged") ||
    normalized.includes("active")
  ) {
    return "positive";
  }
  if (
    normalized.includes("fail") ||
    normalized.includes("error") ||
    normalized.includes("cancel") ||
    normalized.includes("reject")
  ) {
    return "danger";
  }
  if (
    normalized.includes("pending") ||
    normalized.includes("queued") ||
    normalized.includes("running") ||
    normalized.includes("progress")
  ) {
    return "warning";
  }
  return "neutral";
}

function formatProjectionKey(value: string): string {
  return value
    .split("_")
    .filter(Boolean)
    .map((part) => part.charAt(0).toUpperCase() + part.slice(1))
    .join(" ");
}

export function CommandsModule({
  authorizedFetch,
}: {
  authorizedFetch: AuthorizedFetch;
}) {
  const [recentFamilyFilter, setRecentFamilyFilter] = useState<FamilyFilter>("all");
  const [recentCommands, setRecentCommands] = useState<CommandRecentItem[]>([]);
  const [selectedCommandId, setSelectedCommandId] = useState<string | null>(null);
  const [selectedCommandDetail, setSelectedCommandDetail] =
    useState<CommandDetail | null>(null);
  const [pageError, setPageError] = useState<string | null>(null);
  const [detailError, setDetailError] = useState<string | null>(null);
  const [isLoadingRecentCommands, setIsLoadingRecentCommands] = useState(false);
  const [isLoadingDetail, setIsLoadingDetail] = useState(false);

  const loadRecentCommands = useCallback(
    async (preferredCommandId?: string) => {
      setIsLoadingRecentCommands(true);
      setPageError(null);

      try {
        const familyQuery =
          recentFamilyFilter === "all" ? "" : `&family=${recentFamilyFilter}`;
        const response = await authorizedFetch<CommandRecentListResponse>(
          `/api/v1/commands/recent?limit=20${familyQuery}`,
        );
        setRecentCommands(response.items);
        setSelectedCommandId((currentSelectedCommandId) => {
          if (
            preferredCommandId &&
            response.items.some((item) => item.command_id === preferredCommandId)
          ) {
            return preferredCommandId;
          }
          if (
            currentSelectedCommandId &&
            response.items.some((item) => item.command_id === currentSelectedCommandId)
          ) {
            return currentSelectedCommandId;
          }
          return response.items[0]?.command_id ?? null;
        });
      } catch (error) {
        setPageError(
          error instanceof Error ? error.message : "Unable to load recent commands.",
        );
      } finally {
        setIsLoadingRecentCommands(false);
      }
    },
    [authorizedFetch, recentFamilyFilter],
  );

  const loadCommandDetail = useCallback(
    async (commandId: string) => {
      setIsLoadingDetail(true);
      setDetailError(null);

      try {
        const response = await authorizedFetch<CommandDetailResponse>(
          `/api/v1/commands/${commandId}/detail`,
        );
        setSelectedCommandDetail(response.result);
      } catch (error) {
        setSelectedCommandDetail(null);
        setDetailError(
          error instanceof Error ? error.message : "Unable to load command detail.",
        );
      } finally {
        setIsLoadingDetail(false);
      }
    },
    [authorizedFetch],
  );

  useEffect(() => {
    void loadRecentCommands();
  }, [loadRecentCommands]);

  useEffect(() => {
    if (!selectedCommandId) {
      setSelectedCommandDetail(null);
      setDetailError(null);
      return;
    }
    void loadCommandDetail(selectedCommandId);
  }, [loadCommandDetail, selectedCommandId]);

  const selectedRecentCommand = useMemo(
    () =>
      recentCommands.find((command) => command.command_id === selectedCommandId) ??
      recentCommands[0] ??
      null,
    [recentCommands, selectedCommandId],
  );

  const overviewCards = useMemo(
    () => [
      {
        label: "Commands in current result set",
        value: String(recentCommands.length),
        note:
          recentFamilyFilter === "all"
            ? "All stable command families"
            : `${formatCommandFamilyLabel(recentFamilyFilter)} only`,
      },
      {
        label: "Families represented",
        value: String(new Set(recentCommands.map((item) => item.command_family)).size),
        note: "Profile capture, relay control, on-demand read",
      },
      {
        label: "Commands with runtime records",
        value: String(
          recentCommands.filter((item) => item.runtime_execution_record_id !== null).length,
        ),
        note: "Visible from the current command projection",
      },
      {
        label: "Selected command status",
        value: selectedRecentCommand
          ? formatStatusLabel(selectedRecentCommand.command_status)
          : "No selection",
        note: selectedRecentCommand
          ? formatFamilySummary(selectedRecentCommand.family_specific_outcome_summary)
          : "Choose a command to inspect bounded detail",
      },
    ],
    [recentCommands, recentFamilyFilter, selectedRecentCommand],
  );

  const projectionEntries = useMemo(
    () =>
      selectedCommandDetail
        ? Object.entries(selectedCommandDetail.family_specific_outcome_summary).filter(
            ([, value]) => value !== null,
          )
        : [],
    [selectedCommandDetail],
  );

  return (
    <section className="panel">
      {pageError ? <p className="error-banner">{pageError}</p> : null}

      <div className="detail-stack">
        <section className="subpanel commands-overview-panel">
          <div className="section-heading">
            <div>
              <h2>Commands command center</h2>
              <p className="muted">
                Operational command visibility aligned with the adopted shell while
                staying bounded to the stable command families and current read models.
              </p>
            </div>
            <span className="artifact-pill">
              {recentFamilyFilter === "all"
                ? "All supported families"
                : `${formatCommandFamilyLabel(recentFamilyFilter)} filter`}
            </span>
          </div>

          <div className="commands-overview-grid">
            {overviewCards.map((card) => (
              <div key={card.label} className="stat-card commands-overview-card">
                <span className="stat-label">{card.label}</span>
                <strong>{card.value}</strong>
                <p className="muted">{card.note}</p>
              </div>
            ))}
          </div>
        </section>

        <div className="commands-module-layout">
          <section className="subpanel">
            <div className="section-heading">
              <div>
                <h2>Recent commands</h2>
                <p className="muted">
                  Global operational list for the stable command families only.
                </p>
              </div>
              <label className="inline-select">
                <span>Family</span>
                <select
                  value={recentFamilyFilter}
                  onChange={(event) =>
                    setRecentFamilyFilter(event.target.value as FamilyFilter)
                  }
                >
                  <option value="all">All supported</option>
                  <option value="profile_capture">Profile capture</option>
                  <option value="relay_control">Relay control</option>
                  <option value="on_demand_read">On-demand read</option>
                </select>
              </label>
            </div>

            {isLoadingRecentCommands ? (
              <p className="muted">Loading recent commands...</p>
            ) : null}

            {!isLoadingRecentCommands && recentCommands.length > 0 ? (
              <div className="commands-selection-summary">
                <span className="muted">
                  {recentCommands.length} commands loaded from the current operational
                  view.
                </span>
                {selectedRecentCommand ? (
                  <span className="artifact-pill">
                    Selected: {selectedRecentCommand.command_template_code}
                  </span>
                ) : null}
              </div>
            ) : null}

            <div className="command-list">
              {recentCommands.length === 0 ? (
                <p className="muted">No supported recent commands available.</p>
              ) : null}

              {recentCommands.map((command) => (
                <button
                  key={command.command_id}
                  className={
                    selectedCommandId === command.command_id
                      ? "command-list-item selected"
                      : "command-list-item"
                  }
                  onClick={() => setSelectedCommandId(command.command_id)}
                  type="button"
                >
                  <div className="command-list-item-header">
                    <strong>{command.command_template_code}</strong>
                    <span className={`status-pill ${buildStatusTone(command.command_status)}`}>
                      {formatStatusLabel(command.command_status)}
                    </span>
                  </div>
                  <div className="command-list-item-badges">
                    <span className="artifact-pill">
                      {formatCommandFamilyLabel(command.command_family)}
                    </span>
                    <span className="artifact-pill">
                      {formatCommandCategoryLabel(command.command_category)}
                    </span>
                  </div>
                  <div className="command-list-item-meta">
                    <span>Meter {command.meter_id}</span>
                    <span>
                      Attempt {formatStatusLabel(command.latest_command_execution_attempt_status)}
                    </span>
                  </div>
                  <div className="command-list-item-meta">
                    <span>{formatFamilySummary(command.family_specific_outcome_summary)}</span>
                    <span>Updated {formatDateTime(command.latest_updated_at)}</span>
                  </div>
                </button>
              ))}
            </div>
          </section>

          <section className="subpanel">
            <div className="section-heading">
              <div>
                <h2>Command detail</h2>
                <p className="muted">
                  Bounded detail projection for the selected recent command.
                </p>
              </div>
            </div>

            {isLoadingDetail ? <p className="muted">Loading command detail...</p> : null}
            {detailError ? <p className="error-banner">{detailError}</p> : null}

            {selectedCommandDetail ? (
              <div className="detail-stack">
                <section className="commands-detail-hero">
                  <div className="commands-detail-title-row">
                    <div>
                      <p className="eyebrow">Selected Command</p>
                      <h3>{selectedCommandDetail.command_template_code}</h3>
                      <p className="muted">
                        {formatCommandFamilyLabel(selectedCommandDetail.command_family)} routed
                        through the current{" "}
                        {formatCommandCategoryLabel(selectedCommandDetail.command_category)}{" "}
                        projection.
                      </p>
                    </div>
                    <span
                      className={`status-pill ${buildStatusTone(
                        selectedCommandDetail.command_status,
                      )}`}
                    >
                      {formatStatusLabel(selectedCommandDetail.command_status)}
                    </span>
                  </div>

                  <div className="commands-detail-badges">
                    <span className="artifact-pill">
                      {formatCommandFamilyLabel(selectedCommandDetail.command_family)}
                    </span>
                    <span className="artifact-pill">
                      {formatCommandCategoryLabel(selectedCommandDetail.command_category)}
                    </span>
                    <span className="artifact-pill">
                      Outcome:{" "}
                      {formatFamilySummary(
                        selectedCommandDetail.family_specific_outcome_summary,
                      )}
                    </span>
                  </div>
                </section>

                <div className="detail-grid">
                  <div className="stat-card">
                    <span className="stat-label">Meter ID</span>
                    <strong>{selectedCommandDetail.meter_id}</strong>
                  </div>
                  <div className="stat-card">
                    <span className="stat-label">Family</span>
                    <strong>
                      {formatCommandFamilyLabel(selectedCommandDetail.command_family)}
                    </strong>
                  </div>
                  <div className="stat-card">
                    <span className="stat-label">Category</span>
                    <strong>
                      {formatCommandCategoryLabel(selectedCommandDetail.command_category)}
                    </strong>
                  </div>
                  <div className="stat-card">
                    <span className="stat-label">Status</span>
                    <strong>{formatStatusLabel(selectedCommandDetail.command_status)}</strong>
                  </div>
                  <div className="stat-card">
                    <span className="stat-label">Latest attempt</span>
                    <strong>
                      {formatStatusLabel(
                        selectedCommandDetail.latest_command_execution_attempt_status,
                      )}
                    </strong>
                  </div>
                  <div className="stat-card">
                    <span className="stat-label">Outcome summary</span>
                    <strong>
                      {formatFamilySummary(
                        selectedCommandDetail.family_specific_outcome_summary,
                      )}
                    </strong>
                  </div>
                  <div className="stat-card">
                    <span className="stat-label">Runtime execution record</span>
                    <strong>
                      {selectedCommandDetail.runtime_execution_record_id ?? "Not recorded"}
                    </strong>
                  </div>
                  <div className="stat-card">
                    <span className="stat-label">Created</span>
                    <strong>{formatDateTime(selectedCommandDetail.created_at)}</strong>
                  </div>
                  <div className="stat-card">
                    <span className="stat-label">Last updated</span>
                    <strong>{formatDateTime(selectedCommandDetail.latest_updated_at)}</strong>
                  </div>
                </div>

                <section className="subpanel commands-detail-subpanel">
                  <div className="section-heading">
                    <div>
                      <h3>Outcome and artifacts</h3>
                      <p className="muted">
                        Family-specific outcome summary and orchestration artifact presence
                        from the current stable commands read model.
                      </p>
                    </div>
                  </div>

                  {projectionEntries.length > 0 ? (
                    <div className="detail-grid">
                      {projectionEntries.map(([key, value]) => (
                        <div key={key} className="stat-card">
                          <span className="stat-label">{formatProjectionKey(key)}</span>
                          <strong>{value}</strong>
                        </div>
                      ))}
                    </div>
                  ) : (
                    <p className="muted">
                      No family-specific outcome fields are currently recorded.
                    </p>
                  )}

                  <div className="artifact-row">
                    <span className="artifact-pill">
                      execute-now:{" "}
                      {selectedCommandDetail.execute_now_artifact_present
                        ? "present"
                        : "absent"}
                    </span>
                    <span className="artifact-pill">
                      orchestration:{" "}
                      {selectedCommandDetail.orchestration_artifact_present
                        ? "present"
                        : "absent"}
                    </span>
                    <span className="artifact-pill">
                      terminalization:{" "}
                      {selectedCommandDetail.terminalization_artifact_present
                        ? "present"
                        : "absent"}
                    </span>
                  </div>
                </section>

                <div className="json-panel">
                  <h3>Projection record</h3>
                  <pre>
                    {JSON.stringify(selectedCommandDetail.projection_record, null, 2)}
                  </pre>
                </div>
              </div>
            ) : (
              <p className="muted">Select a recent command to load bounded command detail.</p>
            )}
          </section>
        </div>
      </div>
    </section>
  );
}
