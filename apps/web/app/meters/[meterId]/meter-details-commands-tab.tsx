"use client";

import { useCallback, useEffect, useMemo, useState, type FormEvent } from "react";

import type { AuthorizedFetch } from "../../operational-shell";

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

type ExecuteNowResponse = {
  result: {
    command_id: string;
  };
};

type TabKey = "overview" | "commands";
type FamilyFilter = "all" | CommandOperationalFamily;
type RelayOperation = "disconnect" | "reconnect";

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

function formatConnectivityFreshnessHint(lastSeenAt: string | null): string {
  return lastSeenAt
    ? "Recent connectivity signal recorded"
    : "No recent connectivity signal";
}

type ActionReadinessLevel = "ready" | "partially ready" | "unavailable";

type ActionReadinessItem = {
  title: string;
  status: ActionReadinessLevel;
  summary: string;
};

function buildActionReadinessItem(
  title: string,
  requirements: Array<{ label: string; available: boolean }>,
): ActionReadinessItem {
  const missing = requirements
    .filter((requirement) => !requirement.available)
    .map((requirement) => requirement.label);

  if (missing.length === 0) {
    return {
      title,
      status: "ready",
      summary: "All minimum prerequisites available.",
    };
  }

  if (missing.length === requirements.length) {
    return {
      title,
      status: "unavailable",
      summary: `Missing: ${missing.join(", ")}.`,
    };
  }

  return {
    title,
    status: "partially ready",
    summary: `Missing: ${missing.join(", ")}.`,
  };
}

export function MeterDetailsCommandsTab({
  meterId,
  authorizedFetch,
}: {
  meterId: string;
  authorizedFetch: AuthorizedFetch;
}) {
  const [activeTab, setActiveTab] = useState<TabKey>("commands");
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

  const primaryEndpointAssignment = useMemo(
    () =>
      activeEndpointAssignments.find((assignment) => assignment.is_primary) ??
      activeEndpointAssignments[0] ??
      null,
    [activeEndpointAssignments],
  );

  const defaultProtocolProfile = useMemo(
    () => activeProtocolProfiles[0] ?? null,
    [activeProtocolProfiles],
  );

  const isConnectivityContextLoading =
    isBootstrappingPage &&
    endpointAssignments.length === 0 &&
    protocolProfiles.length === 0;

  const hasConnectivityContext =
    primaryEndpointAssignment !== null ||
    defaultProtocolProfile !== null ||
    meter?.communication_profile_code != null;

  const isActionReadinessLoading =
    isBootstrappingPage &&
    templates.length === 0 &&
    endpointAssignments.length === 0 &&
    protocolProfiles.length === 0 &&
    loadProfileChannels.length === 0;

  const actionReadinessItems = useMemo(
    () => [
      buildActionReadinessItem("Profile capture execute-now", [
        {
          label: "profile capture template",
          available: profileCaptureTemplates.length > 0,
        },
        {
          label: "active endpoint assignment",
          available: activeEndpointAssignments.length > 0,
        },
        {
          label: "active protocol profile",
          available: activeProtocolProfiles.length > 0,
        },
        {
          label: "active load-profile channel",
          available: activeLoadProfileChannels.length > 0,
        },
      ]),
      buildActionReadinessItem("Relay disconnect execute-now", [
        {
          label: "relay disconnect template",
          available: relayDisconnectTemplates.length > 0,
        },
        {
          label: "active endpoint assignment",
          available: activeEndpointAssignments.length > 0,
        },
        {
          label: "active protocol profile",
          available: activeProtocolProfiles.length > 0,
        },
      ]),
      buildActionReadinessItem("Relay reconnect execute-now", [
        {
          label: "relay reconnect template",
          available: relayReconnectTemplates.length > 0,
        },
        {
          label: "active endpoint assignment",
          available: activeEndpointAssignments.length > 0,
        },
        {
          label: "active protocol profile",
          available: activeProtocolProfiles.length > 0,
        },
      ]),
    ],
    [
      activeEndpointAssignments.length,
      activeLoadProfileChannels.length,
      activeProtocolProfiles.length,
      profileCaptureTemplates.length,
      relayDisconnectTemplates.length,
      relayReconnectTemplates.length,
    ],
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
    setIsBootstrappingPage(true);
    setPageError(null);

    try {
      const meterResponse = await authorizedFetch<MeterDetail>(`/api/v1/meters/${meterId}`);
      setMeter(meterResponse);

      const [templatesResult, assignmentsResult, profilesResult, channelsResult] =
        await Promise.allSettled([
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

      setTemplates(
        templatesResult.status === "fulfilled" ? templatesResult.value.items : [],
      );
      setEndpointAssignments(
        assignmentsResult.status === "fulfilled" ? assignmentsResult.value.items : [],
      );
      setProtocolProfiles(
        profilesResult.status === "fulfilled" ? profilesResult.value.items : [],
      );
      setLoadProfileChannels(
        channelsResult.status === "fulfilled" ? channelsResult.value.items : [],
      );

      if (
        templatesResult.status === "rejected" ||
        assignmentsResult.status === "rejected" ||
        profilesResult.status === "rejected" ||
        channelsResult.status === "rejected"
      ) {
        setPageError("Unable to load complete meter connectivity and command context.");
      }
    } catch (error) {
      setMeter(null);
      setTemplates([]);
      setEndpointAssignments([]);
      setProtocolProfiles([]);
      setLoadProfileChannels([]);
      setPageError(
        error instanceof Error
          ? error.message
          : "Unable to load meter command dependencies.",
      );
    } finally {
      setIsBootstrappingPage(false);
    }
  }, [authorizedFetch, meterId]);

  const loadRecentCommands = useCallback(
    async (preferredCommandId?: string) => {
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
    [authorizedFetch, meterId, recentFamilyFilter],
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
    <section className="panel">
      {actionSuccess ? <p className="success-banner">{actionSuccess}</p> : null}
      {actionError ? <p className="error-banner">{actionError}</p> : null}
      {pageError ? <p className="error-banner">{pageError}</p> : null}

      <section className="subpanel meter-summary-panel">
        <div className="section-heading">
          <div>
            <h2>Operational summary</h2>
            <p className="muted">
              Current meter context for the existing operational commands
              experience.
            </p>
          </div>
        </div>

        {isBootstrappingPage && !meter ? (
          <p className="muted">Loading meter summary...</p>
        ) : null}

        {!isBootstrappingPage && meter ? (
          <div className="meter-summary-grid">
            <div className="stat-card">
              <span className="stat-label">Meter ID</span>
              <strong>{meter.id}</strong>
            </div>
            <div className="stat-card">
              <span className="stat-label">Serial number</span>
              <strong>{meter.serial_number}</strong>
            </div>
            <div className="stat-card">
              <span className="stat-label">Utility meter number</span>
              <strong>{meter.utility_meter_number ?? "Not available"}</strong>
            </div>
            <div className="stat-card">
              <span className="stat-label">Status</span>
              <strong>{meter.current_status}</strong>
            </div>
            <div className="stat-card">
              <span className="stat-label">Communication profile</span>
              <strong>{meter.communication_profile_code ?? "Not available"}</strong>
            </div>
            <div className="stat-card">
              <span className="stat-label">Meter profile</span>
              <strong>{meter.meter_profile_code ?? "Not available"}</strong>
            </div>
            <div className="stat-card">
              <span className="stat-label">Manufacturer / model</span>
              <strong>
                {meter.manufacturer_code} / {meter.meter_model_code}
              </strong>
            </div>
            <div className="stat-card">
              <span className="stat-label">Last seen</span>
              <strong>{formatDateTime(meter.last_seen_at)}</strong>
            </div>
            <div className="stat-card">
              <span className="stat-label">Primary endpoint</span>
              <strong>
                {primaryEndpointAssignment?.endpoint_code ?? "No active endpoint"}
              </strong>
            </div>
            <div className="stat-card">
              <span className="stat-label">Protocol profile</span>
              <strong>
                {defaultProtocolProfile?.code ?? "No active protocol profile"}
              </strong>
            </div>
          </div>
        ) : null}

        {!isBootstrappingPage && !meter ? (
          <p className="muted">Meter summary not available.</p>
        ) : null}
      </section>

      <section className="subpanel meter-summary-panel">
        <div className="section-heading">
          <div>
            <h2>Connectivity context</h2>
            <p className="muted">
              Current endpoint and protocol context for this meter&apos;s
              operational path.
            </p>
          </div>
        </div>

        {isConnectivityContextLoading ? (
          <p className="muted">Loading connectivity context...</p>
        ) : null}

        {!isConnectivityContextLoading && hasConnectivityContext ? (
          <div className="meter-summary-grid">
            <div className="stat-card">
              <span className="stat-label">Primary endpoint</span>
              <strong>
                {primaryEndpointAssignment?.endpoint_display_name ??
                  primaryEndpointAssignment?.endpoint_code ??
                  "No active endpoint"}
              </strong>
            </div>
            <div className="stat-card">
              <span className="stat-label">Endpoint code</span>
              <strong>
                {primaryEndpointAssignment?.endpoint_code ?? "No active endpoint"}
              </strong>
            </div>
            <div className="stat-card">
              <span className="stat-label">Endpoint assignment status</span>
              <strong>
                {primaryEndpointAssignment?.assignment_status ?? "Not assigned"}
              </strong>
            </div>
            <div className="stat-card">
              <span className="stat-label">Primary assignment</span>
              <strong>
                {primaryEndpointAssignment
                  ? primaryEndpointAssignment.is_primary
                    ? "Primary"
                    : "Secondary"
                  : "Not available"}
              </strong>
            </div>
            <div className="stat-card">
              <span className="stat-label">Communication profile</span>
              <strong>{meter?.communication_profile_code ?? "Not available"}</strong>
            </div>
            <div className="stat-card">
              <span className="stat-label">Protocol profile</span>
              <strong>{defaultProtocolProfile?.code ?? "Not available"}</strong>
            </div>
            <div className="stat-card">
              <span className="stat-label">Protocol family</span>
              <strong>
                {defaultProtocolProfile?.protocol_family ?? "Not available"}
              </strong>
            </div>
            <div className="stat-card">
              <span className="stat-label">Connectivity freshness</span>
              <strong>
                {formatConnectivityFreshnessHint(meter?.last_seen_at ?? null)}
              </strong>
            </div>
          </div>
        ) : null}

        {!isConnectivityContextLoading && !hasConnectivityContext ? (
          <p className="muted">Connectivity context not available.</p>
        ) : null}
      </section>

      <section className="subpanel meter-summary-panel">
        <div className="section-heading">
          <div>
            <h2>Action readiness</h2>
            <p className="muted">
              Advisory summary for the existing execute-now paths. Final command
              validation remains on the backend.
            </p>
          </div>
        </div>

        {isActionReadinessLoading ? (
          <p className="muted">Loading action readiness...</p>
        ) : null}

        {!isActionReadinessLoading && meter ? (
          <div className="meter-summary-grid">
            {actionReadinessItems.map((item) => (
              <div key={item.title} className="stat-card">
                <span className="stat-label">{item.title}</span>
                <strong>{item.status}</strong>
                <p className="muted">{item.summary}</p>
              </div>
            ))}
          </div>
        ) : null}

        {!isActionReadinessLoading && !meter ? (
          <p className="muted">Action readiness not available.</p>
        ) : null}
      </section>

      <section>
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
    </section>
  );
}
