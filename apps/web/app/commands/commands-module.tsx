"use client";

import { useCallback, useEffect, useState, type FormEvent } from "react";

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

type LoginResponse = {
  access_token: string;
  user: {
    username: string;
    full_name: string;
  };
};

const ACCESS_TOKEN_STORAGE_KEY = "sunrise.web.accessToken";
const API_BASE_URL_STORAGE_KEY = "sunrise.web.apiBaseUrl";
const DEFAULT_API_BASE_URL =
  process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000";

function buildApiUrl(apiBaseUrl: string, path: string): string {
  return `${apiBaseUrl.replace(/\/$/, "")}${path}`;
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

export function CommandsModule() {
  const [apiBaseUrl, setApiBaseUrl] = useState(DEFAULT_API_BASE_URL);
  const [accessToken, setAccessToken] = useState("");
  const [loginUsername, setLoginUsername] = useState("");
  const [loginPassword, setLoginPassword] = useState("");
  const [sessionLabel, setSessionLabel] = useState<string | null>(null);
  const [recentFamilyFilter, setRecentFamilyFilter] = useState<FamilyFilter>("all");
  const [recentCommands, setRecentCommands] = useState<CommandRecentItem[]>([]);
  const [selectedCommandId, setSelectedCommandId] = useState<string | null>(null);
  const [selectedCommandDetail, setSelectedCommandDetail] =
    useState<CommandDetail | null>(null);
  const [pageError, setPageError] = useState<string | null>(null);
  const [detailError, setDetailError] = useState<string | null>(null);
  const [actionError, setActionError] = useState<string | null>(null);
  const [actionSuccess, setActionSuccess] = useState<string | null>(null);
  const [isAuthenticating, setIsAuthenticating] = useState(false);
  const [isLoadingRecentCommands, setIsLoadingRecentCommands] = useState(false);
  const [isLoadingDetail, setIsLoadingDetail] = useState(false);

  const authorizedFetch = useCallback(
    async <T,>(path: string, init?: RequestInit): Promise<T> => {
      const headers = new Headers(init?.headers);
      if (init?.body && !headers.has("Content-Type")) {
        headers.set("Content-Type", "application/json");
      }
      if (accessToken) {
        headers.set("Authorization", `Bearer ${accessToken}`);
      }

      const response = await fetch(buildApiUrl(apiBaseUrl, path), {
        ...init,
        headers,
        cache: "no-store",
      });

      if (!response.ok) {
        let errorMessage = `Request failed with status ${response.status}.`;
        try {
          const errorPayload = (await response.json()) as {
            detail?: string;
            message?: string;
          };
          errorMessage =
            errorPayload.detail ??
            errorPayload.message ??
            `Request failed with status ${response.status}.`;
        } catch {
          const fallbackText = await response.text();
          if (fallbackText) {
            errorMessage = fallbackText;
          }
        }
        throw new Error(errorMessage);
      }

      return (await response.json()) as T;
    },
    [accessToken, apiBaseUrl],
  );

  useEffect(() => {
    if (typeof window === "undefined") {
      return;
    }

    const storedApiBaseUrl = window.localStorage.getItem(API_BASE_URL_STORAGE_KEY);
    const storedAccessToken = window.localStorage.getItem(ACCESS_TOKEN_STORAGE_KEY);

    if (storedApiBaseUrl) {
      setApiBaseUrl(storedApiBaseUrl);
    }
    if (storedAccessToken) {
      setAccessToken(storedAccessToken);
    }
  }, []);

  useEffect(() => {
    if (typeof window === "undefined") {
      return;
    }
    window.localStorage.setItem(API_BASE_URL_STORAGE_KEY, apiBaseUrl);
  }, [apiBaseUrl]);

  useEffect(() => {
    if (typeof window === "undefined") {
      return;
    }
    if (accessToken) {
      window.localStorage.setItem(ACCESS_TOKEN_STORAGE_KEY, accessToken);
      return;
    }
    window.localStorage.removeItem(ACCESS_TOKEN_STORAGE_KEY);
  }, [accessToken]);

  const loadRecentCommands = useCallback(
    async (preferredCommandId?: string) => {
      if (!accessToken) {
        return;
      }

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
    [accessToken, authorizedFetch, recentFamilyFilter],
  );

  const loadCommandDetail = useCallback(
    async (commandId: string) => {
      if (!accessToken) {
        return;
      }

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
    [accessToken, authorizedFetch],
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

  const handleLogin = useCallback(
    async (event: FormEvent<HTMLFormElement>) => {
      event.preventDefault();
      setIsAuthenticating(true);
      setActionError(null);
      setActionSuccess(null);

      try {
        const response = await fetch(buildApiUrl(apiBaseUrl, "/api/v1/auth/login"), {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            username_or_email: loginUsername,
            password: loginPassword,
          }),
        });

        if (!response.ok) {
          const errorPayload = (await response.json()) as { detail?: string };
          throw new Error(errorPayload.detail ?? "Unable to authenticate.");
        }

        const payload = (await response.json()) as LoginResponse;
        setAccessToken(payload.access_token);
        setSessionLabel(payload.user.full_name || payload.user.username);
        setActionSuccess(`Signed in as ${payload.user.username}.`);
      } catch (error) {
        setActionError(
          error instanceof Error ? error.message : "Unable to authenticate.",
        );
      } finally {
        setIsAuthenticating(false);
      }
    },
    [apiBaseUrl, loginPassword, loginUsername],
  );

  const handleManualRefresh = useCallback(async () => {
    setActionSuccess(null);
    setActionError(null);
    await loadRecentCommands();
  }, [loadRecentCommands]);

  return (
    <main className="meter-page-shell">
      <section className="hero">
        <p className="eyebrow">Commands Module</p>
        <h1>Global Commands MVP</h1>
        <p className="lead">
          Compact global commands view over the stable operational read-model APIs
          for profile capture and relay control.
        </p>
      </section>

      <section className="panel">
        <div className="section-heading">
          <div>
            <h2>Access</h2>
            <p className="muted">
              Use an existing bearer token or sign in to the API directly for this
              page.
            </p>
          </div>
          <button className="secondary-button" onClick={() => setAccessToken("")} type="button">
            Clear token
          </button>
        </div>

        <div className="settings-grid">
          <label className="field">
            <span>API base URL</span>
            <input
              value={apiBaseUrl}
              onChange={(event) => setApiBaseUrl(event.target.value)}
              placeholder="http://localhost:8000"
            />
          </label>

          <label className="field">
            <span>Bearer token</span>
            <textarea
              value={accessToken}
              onChange={(event) => setAccessToken(event.target.value)}
              placeholder="Paste an access token"
              rows={3}
            />
          </label>
        </div>

        <form className="inline-form" onSubmit={handleLogin}>
          <label className="field">
            <span>Username or email</span>
            <input
              value={loginUsername}
              onChange={(event) => setLoginUsername(event.target.value)}
              placeholder="ops@example.com"
            />
          </label>
          <label className="field">
            <span>Password</span>
            <input
              type="password"
              value={loginPassword}
              onChange={(event) => setLoginPassword(event.target.value)}
              placeholder="Enter password"
            />
          </label>
          <button className="primary-button" disabled={isAuthenticating} type="submit">
            {isAuthenticating ? "Signing in..." : "Sign in"}
          </button>
          <button
            className="secondary-button"
            disabled={!accessToken}
            onClick={() => void handleManualRefresh()}
            type="button"
          >
            Refresh commands
          </button>
        </form>

        {sessionLabel ? <p className="success-banner">Authenticated as {sessionLabel}.</p> : null}
        {actionSuccess ? <p className="success-banner">{actionSuccess}</p> : null}
        {actionError ? <p className="error-banner">{actionError}</p> : null}
        {pageError ? <p className="error-banner">{pageError}</p> : null}
      </section>

      <section className="panel">
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
    </main>
  );
}
