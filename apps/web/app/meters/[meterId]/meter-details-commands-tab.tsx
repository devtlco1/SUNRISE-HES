"use client";

import { useCallback, useEffect, useMemo, useState, type FormEvent } from "react";

type MeterDetail = {
  id: string;
  serial_number: string;
  utility_meter_number: string | null;
  manufacturer_code: string;
  meter_model_code: string;
  meter_profile_code: string | null;
  communication_profile_code: string | null;
  current_status: string;
  last_seen_at: string | null;
};

type CommandOperationalFamily = "profile_capture" | "relay_control";

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

type MeterRecentCommandsResponse = {
  meter_id: string;
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

type CommandTemplate = {
  id: string;
  code: string;
  name: string;
  category: string;
  is_active: boolean;
};

type CommandTemplateListResponse = {
  total: number;
  items: CommandTemplate[];
};

type MeterEndpointAssignment = {
  id: string;
  endpoint_id: string;
  endpoint_code: string;
  endpoint_display_name: string;
  assignment_status: string;
  is_primary: boolean;
};

type MeterEndpointAssignmentListResponse = {
  total: number;
  items: MeterEndpointAssignment[];
};

type ProtocolAssociationProfile = {
  id: string;
  code: string;
  name: string;
  protocol_family: string;
  is_active: boolean;
};

type ProtocolAssociationProfileListResponse = {
  total: number;
  items: ProtocolAssociationProfile[];
};

type LoadProfileChannel = {
  id: string;
  channel_code: string;
  obis_code: string;
  interval_seconds: number;
  is_active: boolean;
};

type LoadProfileChannelListResponse = {
  total: number;
  items: LoadProfileChannel[];
};

type LoginResponse = {
  access_token: string;
  token_type: string;
  expires_in: number;
  user: {
    username: string;
    full_name: string;
  };
};

type ExecuteNowResponse = {
  result: {
    command_id: string;
  };
};

type TabKey = "overview" | "commands";
type FamilyFilter = "all" | CommandOperationalFamily;
type RelayOperation = "disconnect" | "reconnect";

const ACCESS_TOKEN_STORAGE_KEY = "sunrise.web.accessToken";
const API_BASE_URL_STORAGE_KEY = "sunrise.web.apiBaseUrl";
const DEFAULT_API_BASE_URL =
  process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000";

function toLocalDatetimeInputValue(value: Date): string {
  const adjusted = new Date(value.getTime() - value.getTimezoneOffset() * 60_000);
  return adjusted.toISOString().slice(0, 16);
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

function buildApiUrl(apiBaseUrl: string, path: string): string {
  return `${apiBaseUrl.replace(/\/$/, "")}${path}`;
}

export function MeterDetailsCommandsTab({
  meterId,
}: {
  meterId: string;
}) {
  const [activeTab, setActiveTab] = useState<TabKey>("commands");
  const [apiBaseUrl, setApiBaseUrl] = useState(DEFAULT_API_BASE_URL);
  const [accessToken, setAccessToken] = useState("");
  const [loginUsername, setLoginUsername] = useState("");
  const [loginPassword, setLoginPassword] = useState("");
  const [sessionLabel, setSessionLabel] = useState<string | null>(null);
  const [meter, setMeter] = useState<MeterDetail | null>(null);
  const [recentCommands, setRecentCommands] = useState<CommandRecentItem[]>([]);
  const [selectedCommandId, setSelectedCommandId] = useState<string | null>(null);
  const [selectedCommandDetail, setSelectedCommandDetail] =
    useState<CommandDetail | null>(null);
  const [templates, setTemplates] = useState<CommandTemplate[]>([]);
  const [endpointAssignments, setEndpointAssignments] = useState<
    MeterEndpointAssignment[]
  >([]);
  const [protocolProfiles, setProtocolProfiles] = useState<
    ProtocolAssociationProfile[]
  >([]);
  const [loadProfileChannels, setLoadProfileChannels] = useState<
    LoadProfileChannel[]
  >([]);
  const [recentFamilyFilter, setRecentFamilyFilter] = useState<FamilyFilter>("all");
  const [pageError, setPageError] = useState<string | null>(null);
  const [detailError, setDetailError] = useState<string | null>(null);
  const [actionError, setActionError] = useState<string | null>(null);
  const [actionSuccess, setActionSuccess] = useState<string | null>(null);
  const [isAuthenticating, setIsAuthenticating] = useState(false);
  const [isBootstrappingPage, setIsBootstrappingPage] = useState(false);
  const [isLoadingRecentCommands, setIsLoadingRecentCommands] = useState(false);
  const [isLoadingDetail, setIsLoadingDetail] = useState(false);
  const [isExecutingProfileCapture, setIsExecutingProfileCapture] = useState(false);
  const [isExecutingRelayControl, setIsExecutingRelayControl] = useState(false);
  const [profileCaptureTemplateId, setProfileCaptureTemplateId] = useState("");
  const [profileCaptureEndpointAssignmentId, setProfileCaptureEndpointAssignmentId] =
    useState("");
  const [profileCaptureProtocolProfileId, setProfileCaptureProtocolProfileId] =
    useState("");
  const [profileCaptureChannelIds, setProfileCaptureChannelIds] = useState<string[]>(
    [],
  );
  const [relayTemplateId, setRelayTemplateId] = useState("");
  const [relayEndpointAssignmentId, setRelayEndpointAssignmentId] = useState("");
  const [relayProtocolProfileId, setRelayProtocolProfileId] = useState("");
  const [relayOperation, setRelayOperation] = useState<RelayOperation>("disconnect");
  const [profileCaptureIntervalStart, setProfileCaptureIntervalStart] = useState(() => {
    const end = new Date();
    end.setSeconds(0, 0);
    end.setMinutes(end.getMinutes() - 15);
    return toLocalDatetimeInputValue(end);
  });
  const [profileCaptureIntervalEnd, setProfileCaptureIntervalEnd] = useState(() => {
    const end = new Date();
    end.setSeconds(0, 0);
    return toLocalDatetimeInputValue(end);
  });

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

  const activeEndpointAssignments = useMemo(
    () =>
      endpointAssignments.filter(
        (assignment) => assignment.assignment_status === "active",
      ),
    [endpointAssignments],
  );

  const activeProtocolProfiles = useMemo(
    () =>
      protocolProfiles.filter(
        (profile) =>
          profile.is_active && profile.protocol_family === "dlms_cosem",
      ),
    [protocolProfiles],
  );

  const activeLoadProfileChannels = useMemo(
    () => loadProfileChannels.filter((channel) => channel.is_active),
    [loadProfileChannels],
  );

  const profileCaptureTemplates = useMemo(
    () =>
      templates.filter(
        (template) => template.is_active && template.category === "profile_capture",
      ),
    [templates],
  );

  const relayDisconnectTemplates = useMemo(
    () =>
      templates.filter(
        (template) =>
          template.is_active && template.category === "remote_disconnect",
      ),
    [templates],
  );

  const relayReconnectTemplates = useMemo(
    () =>
      templates.filter(
        (template) =>
          template.is_active && template.category === "remote_reconnect",
      ),
    [templates],
  );

  const relayTemplates = useMemo(
    () =>
      relayOperation === "disconnect"
        ? relayDisconnectTemplates
        : relayReconnectTemplates,
    [relayDisconnectTemplates, relayOperation, relayReconnectTemplates],
  );

  useEffect(() => {
    if (!profileCaptureTemplateId && profileCaptureTemplates[0]) {
      setProfileCaptureTemplateId(profileCaptureTemplates[0].id);
    }
  }, [profileCaptureTemplateId, profileCaptureTemplates]);

  useEffect(() => {
    if (!profileCaptureEndpointAssignmentId && activeEndpointAssignments[0]) {
      setProfileCaptureEndpointAssignmentId(activeEndpointAssignments[0].id);
    }
    if (!relayEndpointAssignmentId && activeEndpointAssignments[0]) {
      setRelayEndpointAssignmentId(activeEndpointAssignments[0].id);
    }
  }, [
    activeEndpointAssignments,
    profileCaptureEndpointAssignmentId,
    relayEndpointAssignmentId,
  ]);

  useEffect(() => {
    if (!profileCaptureProtocolProfileId && activeProtocolProfiles[0]) {
      setProfileCaptureProtocolProfileId(activeProtocolProfiles[0].id);
    }
    if (!relayProtocolProfileId && activeProtocolProfiles[0]) {
      setRelayProtocolProfileId(activeProtocolProfiles[0].id);
    }
  }, [
    activeProtocolProfiles,
    profileCaptureProtocolProfileId,
    relayProtocolProfileId,
  ]);

  useEffect(() => {
    if (
      profileCaptureChannelIds.length === 0 &&
      activeLoadProfileChannels[0] !== undefined
    ) {
      setProfileCaptureChannelIds([activeLoadProfileChannels[0].id]);
    }
  }, [activeLoadProfileChannels, profileCaptureChannelIds.length]);

  useEffect(() => {
    if (!relayTemplates[0]) {
      setRelayTemplateId("");
      return;
    }
    if (!relayTemplates.some((template) => template.id === relayTemplateId)) {
      setRelayTemplateId(relayTemplates[0].id);
    }
  }, [relayTemplateId, relayTemplates]);

  const loadReferenceData = useCallback(async () => {
    if (!accessToken) {
      return;
    }

    setIsBootstrappingPage(true);
    setPageError(null);

    try {
      const [
        meterResponse,
        templatesResponse,
        assignmentsResponse,
        profilesResponse,
        channelsResponse,
      ] = await Promise.all([
        authorizedFetch<MeterDetail>(`/api/v1/meters/${meterId}`),
        authorizedFetch<CommandTemplateListResponse>("/api/v1/command-templates"),
        authorizedFetch<MeterEndpointAssignmentListResponse>(
          `/api/v1/meters/${meterId}/endpoint-assignments`,
        ),
        authorizedFetch<ProtocolAssociationProfileListResponse>(
          "/api/v1/protocol-association-profiles",
        ),
        authorizedFetch<LoadProfileChannelListResponse>(
          `/api/v1/meters/${meterId}/load-profile-channels`,
        ),
      ]);

      setMeter(meterResponse);
      setTemplates(templatesResponse.items);
      setEndpointAssignments(assignmentsResponse.items);
      setProtocolProfiles(profilesResponse.items);
      setLoadProfileChannels(channelsResponse.items);
    } catch (error) {
      setPageError(
        error instanceof Error
          ? error.message
          : "Unable to load meter command dependencies.",
      );
    } finally {
      setIsBootstrappingPage(false);
    }
  }, [accessToken, authorizedFetch, meterId]);

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
        const response = await authorizedFetch<MeterRecentCommandsResponse>(
          `/api/v1/meters/${meterId}/commands/recent?limit=20${familyQuery}`,
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
            : "Unable to load recent meter commands.",
        );
      } finally {
        setIsLoadingRecentCommands(false);
      }
    },
    [accessToken, authorizedFetch, meterId, recentFamilyFilter],
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
    void loadReferenceData();
  }, [loadReferenceData]);

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
    await Promise.all([loadReferenceData(), loadRecentCommands()]);
  }, [loadRecentCommands, loadReferenceData]);

  const handleProfileCaptureExecuteNow = useCallback(
    async (event: FormEvent<HTMLFormElement>) => {
      event.preventDefault();
      setIsExecutingProfileCapture(true);
      setActionError(null);
      setActionSuccess(null);

      try {
        const response = await authorizedFetch<ExecuteNowResponse>(
          `/api/v1/meters/${meterId}/commands/profile-capture/execute-now`,
          {
            method: "POST",
            body: JSON.stringify({
              command_template_id: profileCaptureTemplateId,
              endpoint_assignment_id: profileCaptureEndpointAssignmentId,
              protocol_association_profile_id: profileCaptureProtocolProfileId,
              channel_ids: profileCaptureChannelIds,
              interval_start: new Date(profileCaptureIntervalStart).toISOString(),
              interval_end: new Date(profileCaptureIntervalEnd).toISOString(),
              priority: "high",
              notes: "Meter details commands tab profile capture request",
              execute_now_reason: "meter-details-commands-tab",
            }),
          },
        );

        await loadRecentCommands(response.result.command_id);
        setActionSuccess("Profile capture execute-now command requested.");
      } catch (error) {
        setActionError(
          error instanceof Error
            ? error.message
            : "Unable to execute profile capture command.",
        );
      } finally {
        setIsExecutingProfileCapture(false);
      }
    },
    [
      authorizedFetch,
      loadRecentCommands,
      meterId,
      profileCaptureChannelIds,
      profileCaptureEndpointAssignmentId,
      profileCaptureIntervalEnd,
      profileCaptureIntervalStart,
      profileCaptureProtocolProfileId,
      profileCaptureTemplateId,
    ],
  );

  const handleRelayControlExecuteNow = useCallback(
    async (event: FormEvent<HTMLFormElement>) => {
      event.preventDefault();
      setIsExecutingRelayControl(true);
      setActionError(null);
      setActionSuccess(null);

      try {
        const response = await authorizedFetch<ExecuteNowResponse>(
          `/api/v1/meters/${meterId}/commands/relay-control/execute-now`,
          {
            method: "POST",
            body: JSON.stringify({
              command_template_id: relayTemplateId,
              relay_operation: relayOperation,
              endpoint_assignment_id: relayEndpointAssignmentId,
              protocol_association_profile_id: relayProtocolProfileId,
              priority: "high",
              notes: "Meter details commands tab relay control request",
              execute_now_reason: "meter-details-commands-tab",
            }),
          },
        );

        await loadRecentCommands(response.result.command_id);
        setActionSuccess(
          relayOperation === "disconnect"
            ? "Relay disconnect command requested."
            : "Relay reconnect command requested.",
        );
      } catch (error) {
        setActionError(
          error instanceof Error
            ? error.message
            : "Unable to execute relay control command.",
        );
      } finally {
        setIsExecutingRelayControl(false);
      }
    },
    [
      authorizedFetch,
      loadRecentCommands,
      meterId,
      relayEndpointAssignmentId,
      relayOperation,
      relayProtocolProfileId,
      relayTemplateId,
    ],
  );

  const canSubmitProfileCapture =
    profileCaptureTemplateId !== "" &&
    profileCaptureEndpointAssignmentId !== "" &&
    profileCaptureProtocolProfileId !== "" &&
    profileCaptureChannelIds.length > 0;

  const canSubmitRelayControl =
    relayTemplateId !== "" &&
    relayEndpointAssignmentId !== "" &&
    relayProtocolProfileId !== "";

  return (
    <main className="meter-page-shell">
      <section className="hero">
        <p className="eyebrow">Meter Details</p>
        <h1>Meter {meterId}</h1>
        <p className="lead">
          Bounded meter details MVP with command visibility and execute-now actions
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
        <div className="tab-row" role="tablist" aria-label="Meter details tabs">
          <button
            className={activeTab === "overview" ? "tab-button active" : "tab-button"}
            onClick={() => setActiveTab("overview")}
            role="tab"
            type="button"
          >
            Overview
          </button>
          <button
            className={activeTab === "commands" ? "tab-button active" : "tab-button"}
            onClick={() => setActiveTab("commands")}
            role="tab"
            type="button"
          >
            Commands
          </button>
        </div>

        {activeTab === "overview" ? (
          <div className="meter-overview-grid">
            <div className="stat-card">
              <span className="stat-label">Serial number</span>
              <strong>{meter?.serial_number ?? meterId}</strong>
            </div>
            <div className="stat-card">
              <span className="stat-label">Utility meter number</span>
              <strong>{meter?.utility_meter_number ?? "Not available"}</strong>
            </div>
            <div className="stat-card">
              <span className="stat-label">Status</span>
              <strong>{meter?.current_status ?? "Unknown"}</strong>
            </div>
            <div className="stat-card">
              <span className="stat-label">Last seen</span>
              <strong>{formatDateTime(meter?.last_seen_at ?? null)}</strong>
            </div>
            <div className="stat-card">
              <span className="stat-label">Manufacturer</span>
              <strong>{meter?.manufacturer_code ?? "Unknown"}</strong>
            </div>
            <div className="stat-card">
              <span className="stat-label">Meter model</span>
              <strong>{meter?.meter_model_code ?? "Unknown"}</strong>
            </div>
          </div>
        ) : null}

        {activeTab === "commands" ? (
          <div className="commands-tab-layout">
            <section className="subpanel">
              <div className="section-heading">
                <div>
                  <h2>Recent commands</h2>
                  <p className="muted">
                    Meter-scoped operational read model for profile capture and relay
                    control.
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

              {isBootstrappingPage || isLoadingRecentCommands ? (
                <p className="muted">Loading recent commands...</p>
              ) : null}

              <div className="command-list">
                {recentCommands.length === 0 ? (
                  <p className="muted">No supported commands recorded for this meter yet.</p>
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
                      <span>{formatFamilySummary(command.family_specific_outcome_summary)}</span>
                    </div>
                    <div className="command-list-item-meta">
                      <span>Created {formatDateTime(command.created_at)}</span>
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
                    Latest execution status projection for the selected recent command.
                  </p>
                </div>
              </div>

              {isLoadingDetail ? <p className="muted">Loading command detail...</p> : null}
              {detailError ? <p className="error-banner">{detailError}</p> : null}

              {selectedCommandDetail ? (
                <div className="detail-stack">
                  <div className="detail-grid">
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
                      <span className="stat-label">Runtime execution record</span>
                      <strong>
                        {selectedCommandDetail.runtime_execution_record_id ??
                          "Not recorded"}
                      </strong>
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

            <section className="subpanel action-section">
              <div className="section-heading">
                <div>
                  <h2>Execute now</h2>
                  <p className="muted">
                    Thin action layer over the existing profile capture and relay
                    control application APIs.
                  </p>
                </div>
              </div>

              <div className="action-forms">
                <form className="action-form" onSubmit={handleProfileCaptureExecuteNow}>
                  <h3>Profile capture</h3>
                  <label className="field">
                    <span>Command template</span>
                    <select
                      value={profileCaptureTemplateId}
                      onChange={(event) => setProfileCaptureTemplateId(event.target.value)}
                    >
                      {profileCaptureTemplates.map((template) => (
                        <option key={template.id} value={template.id}>
                          {template.code}
                        </option>
                      ))}
                    </select>
                  </label>
                  <label className="field">
                    <span>Endpoint assignment</span>
                    <select
                      value={profileCaptureEndpointAssignmentId}
                      onChange={(event) =>
                        setProfileCaptureEndpointAssignmentId(event.target.value)
                      }
                    >
                      {activeEndpointAssignments.map((assignment) => (
                        <option key={assignment.id} value={assignment.id}>
                          {assignment.endpoint_code}
                          {assignment.is_primary ? " (primary)" : ""}
                        </option>
                      ))}
                    </select>
                  </label>
                  <label className="field">
                    <span>Protocol profile</span>
                    <select
                      value={profileCaptureProtocolProfileId}
                      onChange={(event) =>
                        setProfileCaptureProtocolProfileId(event.target.value)
                      }
                    >
                      {activeProtocolProfiles.map((profile) => (
                        <option key={profile.id} value={profile.id}>
                          {profile.code}
                        </option>
                      ))}
                    </select>
                  </label>
                  <label className="field">
                    <span>Interval start</span>
                    <input
                      type="datetime-local"
                      value={profileCaptureIntervalStart}
                      onChange={(event) => setProfileCaptureIntervalStart(event.target.value)}
                    />
                  </label>
                  <label className="field">
                    <span>Interval end</span>
                    <input
                      type="datetime-local"
                      value={profileCaptureIntervalEnd}
                      onChange={(event) => setProfileCaptureIntervalEnd(event.target.value)}
                    />
                  </label>

                  <fieldset className="channel-selector">
                    <legend>Load profile channels</legend>
                    {activeLoadProfileChannels.length === 0 ? (
                      <p className="muted">No active channels available for this meter.</p>
                    ) : null}
                    {activeLoadProfileChannels.map((channel) => (
                      <label key={channel.id} className="checkbox-option">
                        <input
                          checked={profileCaptureChannelIds.includes(channel.id)}
                          onChange={(event) => {
                            setProfileCaptureChannelIds((currentValue) => {
                              if (event.target.checked) {
                                return [...currentValue, channel.id];
                              }
                              return currentValue.filter(
                                (channelId) => channelId !== channel.id,
                              );
                            });
                          }}
                          type="checkbox"
                        />
                        <span>
                          {channel.channel_code} ({channel.obis_code})
                        </span>
                      </label>
                    ))}
                  </fieldset>

                  <button
                    className="primary-button"
                    disabled={!canSubmitProfileCapture || isExecutingProfileCapture}
                    type="submit"
                  >
                    {isExecutingProfileCapture
                      ? "Executing profile capture..."
                      : "Execute profile capture now"}
                  </button>
                </form>

                <form className="action-form" onSubmit={handleRelayControlExecuteNow}>
                  <h3>Relay control</h3>
                  <label className="field">
                    <span>Operation</span>
                    <select
                      value={relayOperation}
                      onChange={(event) =>
                        setRelayOperation(event.target.value as RelayOperation)
                      }
                    >
                      <option value="disconnect">Disconnect</option>
                      <option value="reconnect">Reconnect</option>
                    </select>
                  </label>
                  <label className="field">
                    <span>Command template</span>
                    <select
                      value={relayTemplateId}
                      onChange={(event) => setRelayTemplateId(event.target.value)}
                    >
                      {relayTemplates.map((template) => (
                        <option key={template.id} value={template.id}>
                          {template.code}
                        </option>
                      ))}
                    </select>
                  </label>
                  <label className="field">
                    <span>Endpoint assignment</span>
                    <select
                      value={relayEndpointAssignmentId}
                      onChange={(event) =>
                        setRelayEndpointAssignmentId(event.target.value)
                      }
                    >
                      {activeEndpointAssignments.map((assignment) => (
                        <option key={assignment.id} value={assignment.id}>
                          {assignment.endpoint_code}
                          {assignment.is_primary ? " (primary)" : ""}
                        </option>
                      ))}
                    </select>
                  </label>
                  <label className="field">
                    <span>Protocol profile</span>
                    <select
                      value={relayProtocolProfileId}
                      onChange={(event) => setRelayProtocolProfileId(event.target.value)}
                    >
                      {activeProtocolProfiles.map((profile) => (
                        <option key={profile.id} value={profile.id}>
                          {profile.code}
                        </option>
                      ))}
                    </select>
                  </label>

                  <button
                    className="primary-button"
                    disabled={!canSubmitRelayControl || isExecutingRelayControl}
                    type="submit"
                  >
                    {isExecutingRelayControl
                      ? "Executing relay control..."
                      : relayOperation === "disconnect"
                        ? "Execute relay disconnect now"
                        : "Execute relay reconnect now"}
                  </button>
                </form>
              </div>
            </section>
          </div>
        ) : null}
      </section>
    </main>
  );
}
