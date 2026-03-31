"use client";

import { useCallback, useEffect, useState } from "react";

import type { AuthorizedFetch } from "../operational-shell";

type CommandOperationalFamily = "profile_capture" | "relay_control";
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
  return "No operational summary yet";
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
          error instanceof Error
            ? error.message
            : "Unable to load recent commands.",
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
          error instanceof Error
            ? error.message
            : "Unable to load command detail.",
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
      return;
    }
    void loadCommandDetail(selectedCommandId);
  }, [loadCommandDetail, selectedCommandId]);

  return (
    <section className="panel">
      {pageError ? <p className="error-banner">{pageError}</p> : null}

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
              </select>
            </label>
          </div>

          {isLoadingRecentCommands ? (
            <p className="muted">Loading recent commands...</p>
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
                  <span className="status-pill">{command.command_status}</span>
                </div>
                <div className="command-list-item-meta">
                  <span>{command.command_family}</span>
                  <span>Meter {command.meter_id}</span>
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
              <div className="detail-grid">
                <div className="stat-card">
                  <span className="stat-label">Meter ID</span>
                  <strong>{selectedCommandDetail.meter_id}</strong>
                </div>
                <div className="stat-card">
                  <span className="stat-label">Family</span>
                  <strong>{selectedCommandDetail.command_family}</strong>
                </div>
                <div className="stat-card">
                  <span className="stat-label">Category</span>
                  <strong>{selectedCommandDetail.command_category}</strong>
                </div>
                <div className="stat-card">
                  <span className="stat-label">Status</span>
                  <strong>{selectedCommandDetail.command_status}</strong>
                </div>
                <div className="stat-card">
                  <span className="stat-label">Latest attempt</span>
                  <strong>
                    {selectedCommandDetail.latest_command_execution_attempt_status ??
                      "No attempt"}
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
                    {selectedCommandDetail.runtime_execution_record_id ??
                      "Not recorded"}
                  </strong>
                </div>
                <div className="stat-card">
                  <span className="stat-label">Created</span>
                  <strong>{formatDateTime(selectedCommandDetail.created_at)}</strong>
                </div>
              </div>

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
    </section>
  );
}
