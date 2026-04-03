"use client";

import Link from "next/link";
import { useCallback, useEffect, useMemo, useState, type FormEvent } from "react";

import type { AuthorizedFetch } from "../../operational-shell";
import { MeterDetailsAttachmentsTab } from "./meter-details-attachments-tab";
import { MeterDetailsAuditTab } from "./meter-details-audit-tab";
import { MeterDetailsCommercialTab } from "./meter-details-commercial-tab";
import { MeterDetailsConfigurationTab } from "./meter-details-configuration-tab";
import { MeterDetailsConnectivityTab } from "./meter-details-connectivity-tab";
import { MeterDetailsEventsTab } from "./meter-details-events-tab";
import { MeterDetailsGisTab } from "./meter-details-gis-tab";
import { MeterDetailsReadingsTab } from "./meter-details-readings-tab";

type MeterDetail = {
  id: string;
  serial_number: string;
  utility_meter_number: string | null;
  manufacturer_code: string;
  meter_model_code: string;
  meter_profile_code: string | null;
  communication_profile_code: string | null;
  current_status: string;
  transformer_id: string | null;
  service_point_id: string | null;
  last_seen_at: string | null;
};

type MeterConsumerLinkage = {
  meter_id: string;
  linkage_status: string;
  linkage_source: string | null;
  consumer_id: string | null;
  consumer_display_name: string | null;
  consumer_type: string | null;
  consumer_external_ref: string | null;
  account_id: string | null;
  account_number: string | null;
  account_status: string | null;
  service_point_id: string | null;
  service_point_code: string | null;
};

type CommandOperationalFamily =
  | "profile_capture"
  | "relay_control"
  | "on_demand_read";

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
  unit?: string | null;
  is_active: boolean;
};

type LoadProfileChannelListResponse = {
  total: number;
  items: LoadProfileChannel[];
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

type ExecuteNowResponse = {
  result: {
    command_id: string;
  };
};

type TabKey =
  | "summary"
  | "attachments"
  | "configuration"
  | "connectivity"
  | "gis"
  | "commercial"
  | "events"
  | "readings"
  | "audit"
  | "commands";
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

function formatConnectivityFreshnessHint(lastSeenAt: string | null): string {
  return lastSeenAt
    ? "Recent connectivity signal recorded"
    : "No recent connectivity signal";
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
  const [activeTab, setActiveTab] = useState<TabKey>("summary");
  const [meter, setMeter] = useState<MeterDetail | null>(null);
  const [consumerLinkage, setConsumerLinkage] =
    useState<MeterConsumerLinkage | null>(null);
  const [meterReadings, setMeterReadings] = useState<MeterReadingItem[]>([]);
  const [billingSnapshots, setBillingSnapshots] = useState<
    MeterRegisterSnapshotItem[]
  >([]);
  const [loadProfileIntervals, setLoadProfileIntervals] = useState<
    LoadProfileIntervalItem[]
  >([]);
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
  const [consumerLinkageError, setConsumerLinkageError] = useState<string | null>(
    null,
  );
  const [configurationContextError, setConfigurationContextError] = useState<string | null>(
    null,
  );
  const [readingsContextError, setReadingsContextError] = useState<string | null>(null);
  const [recentCommandsError, setRecentCommandsError] = useState<string | null>(null);
  const [detailError, setDetailError] = useState<string | null>(null);
  const [actionError, setActionError] = useState<string | null>(null);
  const [actionSuccess, setActionSuccess] = useState<string | null>(null);
  const [isBootstrappingPage, setIsBootstrappingPage] = useState(false);
  const [isLoadingRecentCommands, setIsLoadingRecentCommands] = useState(false);
  const [isLoadingDetail, setIsLoadingDetail] = useState(false);
  const [isExecutingProfileCapture, setIsExecutingProfileCapture] = useState(false);
  const [isExecutingRelayControl, setIsExecutingRelayControl] = useState(false);
  const [isExecutingOnDemandRead, setIsExecutingOnDemandRead] = useState(false);
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
  const [onDemandReadTemplateId, setOnDemandReadTemplateId] = useState("");
  const [onDemandReadEndpointAssignmentId, setOnDemandReadEndpointAssignmentId] = useState("");
  const [onDemandReadProtocolProfileId, setOnDemandReadProtocolProfileId] = useState("");
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
  const loadProfileChannelById = useMemo(
    () => new Map(loadProfileChannels.map((channel) => [channel.id, channel])),
    [loadProfileChannels],
  );
  const latestReading = meterReadings[0] ?? null;
  const latestBillingSnapshot = billingSnapshots[0] ?? null;
  const latestInterval = loadProfileIntervals[0] ?? null;
  const latestIntervalChannel = latestInterval
    ? loadProfileChannelById.get(latestInterval.channel_id) ?? null
    : null;

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

  const onDemandReadTemplates = useMemo(
    () =>
      templates.filter(
        (template) => template.is_active && template.category === "on_demand_read",
      ),
    [templates],
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
  const isConfigurationContextLoading =
    isBootstrappingPage &&
    meter === null &&
    endpointAssignments.length === 0 &&
    protocolProfiles.length === 0;

  const hasConnectivityContext =
    primaryEndpointAssignment !== null ||
    defaultProtocolProfile !== null ||
    meter?.communication_profile_code != null;
  const hasConfigurationContext =
    meter?.meter_profile_code != null ||
    meter?.communication_profile_code != null ||
    primaryEndpointAssignment !== null ||
    defaultProtocolProfile !== null;

  const isConsumerLinkageLoading =
    isBootstrappingPage && consumerLinkage === null && consumerLinkageError === null;

  const isReadingsContextLoading =
    isBootstrappingPage &&
    meterReadings.length === 0 &&
    billingSnapshots.length === 0 &&
    loadProfileIntervals.length === 0;

  const hasReadingsContext =
    latestReading !== null ||
    latestBillingSnapshot !== null ||
    latestInterval !== null ||
    activeLoadProfileChannels.length > 0;

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
      buildActionReadinessItem("On-demand read execute-now", [
        {
          label: "on-demand read template",
          available: onDemandReadTemplates.length > 0,
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
      onDemandReadTemplates.length,
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
    if (!onDemandReadTemplateId && onDemandReadTemplates[0]) {
      setOnDemandReadTemplateId(onDemandReadTemplates[0].id);
    }
  }, [onDemandReadTemplateId, onDemandReadTemplates]);

  useEffect(() => {
    if (!profileCaptureEndpointAssignmentId && activeEndpointAssignments[0]) {
      setProfileCaptureEndpointAssignmentId(activeEndpointAssignments[0].id);
    }
    if (!relayEndpointAssignmentId && activeEndpointAssignments[0]) {
      setRelayEndpointAssignmentId(activeEndpointAssignments[0].id);
    }
    if (!onDemandReadEndpointAssignmentId && activeEndpointAssignments[0]) {
      setOnDemandReadEndpointAssignmentId(activeEndpointAssignments[0].id);
    }
  }, [
    activeEndpointAssignments,
    onDemandReadEndpointAssignmentId,
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
    if (!onDemandReadProtocolProfileId && activeProtocolProfiles[0]) {
      setOnDemandReadProtocolProfileId(activeProtocolProfiles[0].id);
    }
  }, [
    activeProtocolProfiles,
    onDemandReadProtocolProfileId,
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
    setConsumerLinkageError(null);
    setConfigurationContextError(null);
    setReadingsContextError(null);

    try {
      const meterResponse = await authorizedFetch<MeterDetail>(`/api/v1/meters/${meterId}`);
      setMeter(meterResponse);

      const [
        templatesResult,
        assignmentsResult,
        profilesResult,
        channelsResult,
        consumerLinkageResult,
        readingsResult,
        snapshotsResult,
        intervalsResult,
      ] =
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
          authorizedFetch<MeterConsumerLinkage>(
            `/api/v1/meters/${meterId}/consumer-linkage`,
          ),
          authorizedFetch<MeterReadingListResponse>(
            `/api/v1/meters/${meterId}/readings?limit=5`,
          ),
          authorizedFetch<MeterRegisterSnapshotListResponse>(
            `/api/v1/meters/${meterId}/register-snapshots?limit=5`,
          ),
          authorizedFetch<LoadProfileIntervalListResponse>(
            `/api/v1/meters/${meterId}/load-profile-intervals?limit=5`,
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
      setMeterReadings(
        readingsResult.status === "fulfilled" ? readingsResult.value.items : [],
      );
      setBillingSnapshots(
        snapshotsResult.status === "fulfilled"
          ? snapshotsResult.value.items.filter(
              (item) => item.snapshot_type === "billing",
            )
          : [],
      );
      setLoadProfileIntervals(
        intervalsResult.status === "fulfilled" ? intervalsResult.value.items : [],
      );
      setConsumerLinkage(
        consumerLinkageResult.status === "fulfilled"
          ? consumerLinkageResult.value
          : null,
      );
      setConsumerLinkageError(
        consumerLinkageResult.status === "rejected"
          ? consumerLinkageResult.reason instanceof Error
            ? consumerLinkageResult.reason.message
            : "Unable to load consumer linkage."
          : null,
      );
      setConfigurationContextError(
        assignmentsResult.status === "rejected" || profilesResult.status === "rejected"
          ? "Unable to load complete meter configuration context."
          : null,
      );
      setReadingsContextError(
        channelsResult.status === "rejected" ||
          readingsResult.status === "rejected" ||
          snapshotsResult.status === "rejected" ||
          intervalsResult.status === "rejected"
          ? "Unable to load complete meter readings context."
          : null,
      );

      if (
        templatesResult.status === "rejected" ||
        assignmentsResult.status === "rejected" ||
        profilesResult.status === "rejected" ||
        channelsResult.status === "rejected" ||
        readingsResult.status === "rejected" ||
        snapshotsResult.status === "rejected" ||
        intervalsResult.status === "rejected"
      ) {
        setPageError("Unable to load complete meter detail context.");
      }
    } catch (error) {
      setMeter(null);
      setConsumerLinkage(null);
      setMeterReadings([]);
      setBillingSnapshots([]);
      setLoadProfileIntervals([]);
      setTemplates([]);
      setEndpointAssignments([]);
      setProtocolProfiles([]);
      setLoadProfileChannels([]);
      setConsumerLinkageError(null);
      setConfigurationContextError(
        error instanceof Error
          ? error.message
          : "Unable to load meter configuration context.",
      );
      setReadingsContextError(null);
      setPageError(
        error instanceof Error
          ? error.message
          : "Unable to load meter detail dependencies.",
      );
    } finally {
      setIsBootstrappingPage(false);
    }
  }, [authorizedFetch, meterId]);

  const loadRecentCommands = useCallback(
    async (preferredCommandId?: string) => {
      setIsLoadingRecentCommands(true);
      setRecentCommandsError(null);

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
        setRecentCommands([]);
        setSelectedCommandId(null);
        setRecentCommandsError(
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

  const handleOnDemandReadExecuteNow = useCallback(
    async (event: FormEvent<HTMLFormElement>) => {
      event.preventDefault();
      setIsExecutingOnDemandRead(true);
      setActionError(null);
      setActionSuccess(null);

      try {
        const response = await authorizedFetch<ExecuteNowResponse>(
          `/api/v1/meters/${meterId}/commands/on-demand-read/execute-now`,
          {
            method: "POST",
            body: JSON.stringify({
              command_template_id: onDemandReadTemplateId,
              on_demand_read_operation: "read_billing_snapshot",
              endpoint_assignment_id: onDemandReadEndpointAssignmentId,
              protocol_association_profile_id: onDemandReadProtocolProfileId,
              priority: "high",
              notes: "Meter details commands tab on-demand-read request",
              execute_now_reason: "meter-details-commands-tab",
            }),
          },
        );

        await loadRecentCommands(response.result.command_id);
        setActionSuccess("On-demand read execute-now command requested.");
      } catch (error) {
        setActionError(
          error instanceof Error
            ? error.message
            : "Unable to execute on-demand read command.",
        );
      } finally {
        setIsExecutingOnDemandRead(false);
      }
    },
    [
      authorizedFetch,
      loadRecentCommands,
      meterId,
      onDemandReadEndpointAssignmentId,
      onDemandReadProtocolProfileId,
      onDemandReadTemplateId,
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

  const canSubmitOnDemandRead =
    onDemandReadTemplateId !== "" &&
    onDemandReadEndpointAssignmentId !== "" &&
    onDemandReadProtocolProfileId !== "";

  const latestRecentCommand = recentCommands[0] ?? null;
  const selectedRecentCommand =
    recentCommands.find((item) => item.command_id === selectedCommandId) ??
    latestRecentCommand;
  const linkedServicePointId =
    consumerLinkage?.service_point_id ?? meter?.service_point_id ?? null;
  const linkedServicePointCode = consumerLinkage?.service_point_code ?? null;
  const commandOverviewCards = useMemo(
    () => [
      {
        label: "Visible commands",
        value: String(recentCommands.length),
        note: `${recentFamilyFilter === "all" ? "All supported families" : formatCommandFamilyLabel(recentFamilyFilter)} in the current bounded result set`,
      },
      {
        label: "Latest command",
        value: latestRecentCommand?.command_template_code ?? "No recent command",
        note: latestRecentCommand
          ? `${formatCommandFamilyLabel(latestRecentCommand.command_family)} • ${formatDateTime(
              latestRecentCommand.created_at,
            )}`
          : "No recent supported commands recorded for this meter",
      },
      {
        label: "Latest lifecycle",
        value: latestRecentCommand
          ? formatStatusLabel(latestRecentCommand.command_status)
          : "Not available",
        note: latestRecentCommand
          ? formatFamilySummary(latestRecentCommand.family_specific_outcome_summary)
          : "No command outcome summary recorded",
      },
      {
        label: "Selected command",
        value: selectedRecentCommand?.command_template_code ?? "No selection",
        note: selectedRecentCommand
          ? `${formatStatusLabel(selectedRecentCommand.latest_command_execution_attempt_status)} latest attempt`
          : "Choose a command below to inspect bounded detail",
      },
      {
        label: "Selected target",
        value: selectedCommandDetail?.meter_id ?? meterId,
        note: selectedCommandDetail
          ? `${formatCommandCategoryLabel(selectedCommandDetail.command_category)} • ${formatDateTime(
              selectedCommandDetail.latest_updated_at,
            )}`
          : "Meter-scoped command detail remains bounded to the current meter",
      },
      {
        label: "Execution artifacts",
        value: selectedCommandDetail
          ? [
              selectedCommandDetail.execute_now_artifact_present ? "execute-now" : null,
              selectedCommandDetail.orchestration_artifact_present ? "orchestration" : null,
              selectedCommandDetail.terminalization_artifact_present ? "terminalization" : null,
            ]
              .filter(Boolean)
              .join(", ") || "No artifacts"
          : "Awaiting selection",
        note: selectedCommandDetail
          ? "Current detail reflects the selected command projection"
          : "Artifacts appear after a recent command is selected",
      },
    ],
    [
      latestRecentCommand,
      meterId,
      recentCommands.length,
      recentFamilyFilter,
      selectedCommandDetail,
      selectedRecentCommand,
    ],
  );
  const workspaceCards = useMemo(
    () => [
      {
        label: "Meter identity",
        value: meter?.serial_number ?? meterId,
        note: meter
          ? `${meter.current_status} • ${meter.utility_meter_number ?? "No utility number"}`
          : "Meter detail context is still loading.",
      },
      {
        label: "Attachments",
        value: "No current attachment source",
        note: "No meter-linked documents or files are exposed by the current repo contracts.",
      },
      {
        label: "Configuration",
        value: meter
          ? `${meter.manufacturer_code} / ${meter.meter_model_code}`
          : "Configuration loading",
        note: defaultProtocolProfile
          ? `${defaultProtocolProfile.code} • ${meter?.meter_profile_code ?? "No meter profile"}`
          : hasConfigurationContext
            ? `${meter?.communication_profile_code ?? "Communication profile only"} • bounded read-only visibility`
            : "No active meter configuration profile context recorded.",
      },
      {
        label: "Connectivity",
        value:
          primaryEndpointAssignment?.endpoint_code ??
          meter?.communication_profile_code ??
          "No active context",
        note: defaultProtocolProfile
          ? `${defaultProtocolProfile.code} • ${formatConnectivityFreshnessHint(
              meter?.last_seen_at ?? null,
            )}`
          : formatConnectivityFreshnessHint(meter?.last_seen_at ?? null),
      },
      {
        label: "Readings",
        value: latestReading
          ? formatReadingValue(latestReading)
          : latestBillingSnapshot
            ? formatBillingPrimaryValue(latestBillingSnapshot.payload)
            : latestInterval
              ? formatIntervalValue(latestInterval, latestIntervalChannel)
              : "No recent reading context",
        note: latestReading
          ? `Latest raw reading ${formatDateTime(latestReading.captured_at)}`
          : latestBillingSnapshot
            ? `Latest billing snapshot ${formatDateTime(latestBillingSnapshot.captured_at)}`
            : latestInterval
              ? `Latest interval ${formatIntervalWindow(latestInterval)}`
              : "Readings context is currently empty for this meter.",
      },
      {
        label: "GIS",
        value:
          linkedServicePointCode ??
          meter?.service_point_id ??
          meter?.transformer_id ??
          "No GIS context",
        note: meter?.transformer_id
          ? `Transformer ${meter.transformer_id} with existing GIS/service-point follow-through`
          : linkedServicePointCode
            ? `Linked service point ${linkedServicePointCode}`
            : "GIS context is currently empty for this meter.",
      },
      {
        label: "Commercial",
        value:
          consumerLinkage?.consumer_display_name ??
          consumerLinkage?.account_number ??
          "No linked commercial context",
        note:
          consumerLinkage?.linkage_status === "linked"
            ? `${linkedServicePointCode ?? linkedServicePointId ?? "Service point pending"} • ${consumerLinkage.account_status ?? "Account status pending"}`
            : "Subscriber/account linkage is currently unavailable for this meter.",
      },
      {
        label: "Events",
        value: "Meter event visibility",
        note: "Alert and event history available in the existing monitoring surface.",
      },
      {
        label: "Commands",
        value: latestRecentCommand
          ? formatFamilySummary(latestRecentCommand.family_specific_outcome_summary)
          : "No command activity",
        note: latestRecentCommand
          ? `${latestRecentCommand.command_template_code} • ${latestRecentCommand.command_status}`
          : "No recent supported commands recorded for this meter.",
      },
    ],
    [
      defaultProtocolProfile,
      latestBillingSnapshot,
      latestInterval,
      latestIntervalChannel,
      latestReading,
      latestRecentCommand,
      linkedServicePointCode,
      linkedServicePointId,
      meter,
      meterId,
      primaryEndpointAssignment,
      consumerLinkage,
      hasConfigurationContext,
    ],
  );
  const tabCards = useMemo(
    () => [
      {
        key: "summary" as const,
        label: "Summary",
        value: meter ? "Identity + consumer context" : "Meter context loading",
        note: consumerLinkage?.linkage_status === "linked" ? "Linked consumer context available" : "Linked consumer context bounded",
      },
      {
        key: "attachments" as const,
        label: "Attachments",
        value: "Read-only attachment visibility",
        note: "Honest bounded empty state until a real meter attachment foundation exists",
      },
      {
        key: "configuration" as const,
        label: "Configuration",
        value: hasConfigurationContext ? "Model + profile context" : "Configuration gaps visible",
        note: defaultProtocolProfile
          ? `${defaultProtocolProfile.code} with current protocol context`
          : meter?.meter_profile_code ?? "No active meter/profile protocol pairing in scope",
      },
      {
        key: "connectivity" as const,
        label: "Connectivity",
        value: hasConnectivityContext ? "Endpoint + protocol context" : "Connectivity gaps visible",
        note: activeEndpointAssignments.length > 0 ? `${activeEndpointAssignments.length} active endpoint assignments in scope` : "No active endpoint assignment in scope",
      },
      {
        key: "gis" as const,
        label: "GIS",
        value:
          linkedServicePointId || meter?.transformer_id
            ? "Location + network context"
            : "No current GIS context",
        note:
          linkedServicePointId || meter?.transformer_id
            ? "Existing GIS Lite, service-point, and transformer visibility"
            : "No service-point or transformer GIS context in scope",
      },
      {
        key: "commercial" as const,
        label: "Consumer / Commercial",
        value:
          consumerLinkage?.linkage_status === "linked"
            ? "Subscriber + account context"
            : "Commercial linkage gaps visible",
        note:
          consumerLinkage?.linkage_status === "linked"
            ? "Existing subscriber, account, and service context in scope"
            : "No active subscriber/account linkage recorded",
      },
      {
        key: "events" as const,
        label: "Events",
        value: "Event and alert visibility",
        note: "Existing ingested meter events and alert-like history",
      },
      {
        key: "readings" as const,
        label: "Readings",
        value: hasReadingsContext ? "Latest reads in scope" : "No current readings context",
        note: `${meterReadings.length} raw • ${billingSnapshots.length} billing • ${loadProfileIntervals.length} interval`,
      },
      {
        key: "audit" as const,
        label: "Audit",
        value: "Meter-scoped traceability",
        note: "Existing audit_logs history for direct meter activity",
      },
      {
        key: "commands" as const,
        label: "Commands",
        value: `${recentCommands.length} recent command${recentCommands.length === 1 ? "" : "s"}`,
        note: "Recent command detail and execute-now actions remain available",
      },
    ],
    [
      activeEndpointAssignments.length,
      billingSnapshots.length,
      consumerLinkage?.linkage_status,
      defaultProtocolProfile,
      hasConfigurationContext,
      hasConnectivityContext,
      hasReadingsContext,
      loadProfileIntervals.length,
      meter,
      meterReadings.length,
      recentCommands.length,
    ],
  );

  return (
    <section className="panel">
      {actionSuccess ? <p className="success-banner">{actionSuccess}</p> : null}
      {actionError ? <p className="error-banner">{actionError}</p> : null}
      {pageError ? <p className="error-banner">{pageError}</p> : null}

      <section className="subpanel meter-hero-panel">
        {isBootstrappingPage && !meter ? (
          <p className="muted">Loading meter header...</p>
        ) : null}

        {!isBootstrappingPage && meter ? (
          <div className="detail-stack">
            <div className="meter-hero-shell">
              <div className="meter-hero-primary">
                <p className="eyebrow">Authoritative Meter Record</p>
                <div className="meter-hero-title-row">
                  <div>
                    <h2>{meter.serial_number}</h2>
                    <p className="muted">Meter ID {meter.id}</p>
                  </div>
                  <span className="status-pill">{meter.current_status}</span>
                </div>
                <p className="muted">
                  {primaryEndpointAssignment?.endpoint_display_name ??
                    primaryEndpointAssignment?.endpoint_code ??
                    "No active endpoint"}{" "}
                  operational path with{" "}
                  {formatConnectivityFreshnessHint(meter.last_seen_at).toLowerCase()}.
                </p>
                <div className="meter-hero-badges">
                  <span className="artifact-pill">
                    {formatConnectivityFreshnessHint(meter.last_seen_at)}
                  </span>
                  <span className="artifact-pill">
                    {meter.communication_profile_code ?? "No communication profile"}
                  </span>
                  <span className="artifact-pill">
                    {latestRecentCommand
                      ? `Latest command ${latestRecentCommand.command_status}`
                      : "No recent command summary"}
                  </span>
                </div>
              </div>

              <div className="meter-hero-grid">
                <div className="stat-card">
                  <span className="stat-label">Utility meter number</span>
                  <strong>{meter.utility_meter_number ?? "Not available"}</strong>
                </div>
                <div className="stat-card">
                  <span className="stat-label">Catalog</span>
                  <strong>
                    {meter.manufacturer_code} / {meter.meter_model_code}
                  </strong>
                </div>
                <div className="stat-card">
                  <span className="stat-label">Last seen</span>
                  <strong>{formatDateTime(meter.last_seen_at)}</strong>
                </div>
                <div className="stat-card">
                  <span className="stat-label">Linked subscriber</span>
                  <strong>
                    {consumerLinkage?.consumer_display_name ?? "Not available"}
                  </strong>
                </div>
                <div className="stat-card">
                  <span className="stat-label">Linked account</span>
                  <strong>{consumerLinkage?.account_number ?? "Not available"}</strong>
                </div>
                <div className="stat-card">
                  <span className="stat-label">Service point</span>
                  <strong>
                    {linkedServicePointCode ?? linkedServicePointId ?? "Not available"}
                  </strong>
                </div>
                <div className="stat-card">
                  <span className="stat-label">Transformer</span>
                  <strong>{meter.transformer_id ?? "Not available"}</strong>
                </div>
                <div className="stat-card">
                  <span className="stat-label">Latest command summary</span>
                  <strong>
                    {latestRecentCommand
                      ? formatFamilySummary(
                          latestRecentCommand.family_specific_outcome_summary,
                        )
                      : "Not available"}
                  </strong>
                </div>
              </div>
            </div>

            <div className="artifact-row">
              <Link className="primary-button" href={`/readings?meterId=${meter.id}`}>
                Open readings
              </Link>
              <Link className="secondary-button" href={`/commands?meterId=${meter.id}`}>
                Open bulk commands
              </Link>
              {consumerLinkage?.consumer_id ? (
                <Link
                  className="secondary-button"
                  href={`/subscribers/${consumerLinkage.consumer_id}`}
                >
                  Open subscriber detail
                </Link>
              ) : null}
              {consumerLinkage?.account_id ? (
                <Link
                  className="secondary-button"
                  href={`/accounts/${consumerLinkage.account_id}`}
                >
                  Open account detail
                </Link>
              ) : null}
              {linkedServicePointId ? (
                <Link
                  className="secondary-button"
                  href={`/service-points/${linkedServicePointId}`}
                >
                  Open service point detail
                </Link>
              ) : null}
              {meter.transformer_id ? (
                <Link
                  className="secondary-button"
                  href={`/transformers-substations/${meter.transformer_id}`}
                >
                  Open transformer detail
                </Link>
              ) : null}
            </div>
          </div>
        ) : null}

        {!isBootstrappingPage && !meter ? (
          <p className="muted">Meter summary not available.</p>
        ) : null}
      </section>

      <section className="subpanel meter-detail-workspace-panel">
        <div className="section-heading">
          <div>
            <h2>Meter workspace</h2>
            <p className="muted">
              Unified operator foundation for identity, attachments, configuration,
              connectivity, readings, and commands using the current meter-scoped truth.
            </p>
          </div>
        </div>

        <div className="meter-detail-workspace-grid">
          {workspaceCards.map((card) => (
            <div key={card.label} className="stat-card">
              <span className="stat-label">{card.label}</span>
              <strong>{card.value}</strong>
              <p className="muted">{card.note}</p>
            </div>
          ))}
        </div>

        <div className="meter-detail-tab-row" role="tablist" aria-label="Meter detail workspace tabs">
          {tabCards.map((tab) => (
            <button
              key={tab.key}
              aria-selected={activeTab === tab.key}
              className={
                activeTab === tab.key ? "meter-detail-tab-button active" : "meter-detail-tab-button"
              }
              onClick={() => setActiveTab(tab.key)}
              role="tab"
              type="button"
            >
              <span className="meter-detail-tab-label">{tab.label}</span>
              <strong>{tab.value}</strong>
              <span className="muted">{tab.note}</span>
            </button>
          ))}
        </div>
      </section>

      {activeTab === "summary" ? (
        <div className="detail-stack">
          <section className="subpanel meter-summary-panel">
            <div className="section-heading">
              <div>
                <h2>Operational summary</h2>
                <p className="muted">
                  Current meter identity, topology context, and bounded operational
                  cues for this central truth page.
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
                  <span className="stat-label">Transformer ID</span>
                  <strong>{meter.transformer_id ?? "Not available"}</strong>
                </div>
                <div className="stat-card">
                  <span className="stat-label">Service point ID</span>
                  <strong>{meter.service_point_id ?? "Not available"}</strong>
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
                <h2>Consumer linkage</h2>
                <p className="muted">
                  Current linked subscriber and account context available for
                  downstream navigation.
                </p>
              </div>
            </div>

            {isConsumerLinkageLoading ? (
              <p className="muted">Loading consumer linkage...</p>
            ) : null}

            {!isConsumerLinkageLoading && consumerLinkageError ? (
              <p className="error-banner">{consumerLinkageError}</p>
            ) : null}

            {!isConsumerLinkageLoading &&
            !consumerLinkageError &&
            consumerLinkage?.linkage_status === "linked" ? (
              <div className="detail-stack">
                <div className="meter-summary-grid">
                  <div className="stat-card">
                    <span className="stat-label">Subscriber</span>
                    <strong>
                      {consumerLinkage.consumer_display_name ?? "Linked consumer"}
                    </strong>
                  </div>
                  <div className="stat-card">
                    <span className="stat-label">Consumer ID</span>
                    <strong>{consumerLinkage.consumer_id ?? "Not available"}</strong>
                  </div>
                  <div className="stat-card">
                    <span className="stat-label">Account</span>
                    <strong>
                      {consumerLinkage.account_number ?? "No current account"}
                    </strong>
                  </div>
                  <div className="stat-card">
                    <span className="stat-label">Account status</span>
                    <strong>{consumerLinkage.account_status ?? "Not available"}</strong>
                  </div>
                  <div className="stat-card">
                    <span className="stat-label">Service point</span>
                    <strong>
                      {consumerLinkage.service_point_code ?? "Not available"}
                    </strong>
                  </div>
                  <div className="stat-card">
                    <span className="stat-label">Operational identifier</span>
                    <strong>
                      {consumerLinkage.consumer_external_ref ??
                        consumerLinkage.consumer_type ??
                        "Not available"}
                    </strong>
                  </div>
                </div>

                {consumerLinkage.consumer_id ? (
                  <div className="artifact-row">
                    <Link
                      className="primary-button"
                      href={`/subscribers/${consumerLinkage.consumer_id}`}
                    >
                      Open subscriber detail
                    </Link>
                  </div>
                ) : null}
              </div>
            ) : null}

            {!isConsumerLinkageLoading &&
            !consumerLinkageError &&
            consumerLinkage?.linkage_status !== "linked" ? (
              <p className="muted">
                No current subscriber linkage available for this meter.
              </p>
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
        </div>
      ) : null}

      {activeTab === "attachments" ? (
        <MeterDetailsAttachmentsTab
          meter={
            meter
              ? {
                  id: meter.id,
                  serial_number: meter.serial_number,
                  utility_meter_number: meter.utility_meter_number,
                  current_status: meter.current_status,
                  transformer_id: meter.transformer_id,
                  service_point_id: meter.service_point_id,
                  last_seen_at: meter.last_seen_at,
                }
              : null
          }
          linkedServicePointId={linkedServicePointId}
          linkedServicePointCode={linkedServicePointCode}
          isAttachmentsContextLoading={isBootstrappingPage && !meter}
          attachmentsContextError={!meter ? pageError : null}
        />
      ) : null}

      {activeTab === "configuration" ? (
        <MeterDetailsConfigurationTab
          meter={meter}
          primaryEndpointAssignment={primaryEndpointAssignment}
          activeEndpointAssignments={activeEndpointAssignments}
          defaultProtocolProfile={defaultProtocolProfile}
          activeProtocolProfiles={activeProtocolProfiles}
          linkedServicePointId={linkedServicePointId}
          linkedServicePointCode={linkedServicePointCode}
          isConfigurationContextLoading={isConfigurationContextLoading}
          configurationContextError={configurationContextError}
        />
      ) : null}

      {activeTab === "connectivity" ? (
        <MeterDetailsConnectivityTab
          meterId={meterId}
          meter={
            meter
              ? {
                  id: meter.id,
                  communication_profile_code: meter.communication_profile_code,
                  last_seen_at: meter.last_seen_at,
                  current_status: meter.current_status,
                }
              : null
          }
          primaryEndpointAssignment={primaryEndpointAssignment}
          defaultProtocolProfile={defaultProtocolProfile}
          hasConnectivityContext={hasConnectivityContext}
          isConnectivityContextLoading={isConnectivityContextLoading}
          authorizedFetch={authorizedFetch}
        />
      ) : null}

      {activeTab === "gis" ? (
        <MeterDetailsGisTab
          meter={
            meter
              ? {
                  id: meter.id,
                  serial_number: meter.serial_number,
                  transformer_id: meter.transformer_id,
                }
              : null
          }
          meterId={meterId}
          linkedServicePointId={linkedServicePointId}
          linkedServicePointCode={linkedServicePointCode}
          authorizedFetch={authorizedFetch}
        />
      ) : null}

      {activeTab === "commercial" ? (
        <MeterDetailsCommercialTab
          consumerLinkage={consumerLinkage}
          isLoadingConsumerLinkage={isConsumerLinkageLoading}
          consumerLinkageError={consumerLinkageError}
          linkedServicePointId={linkedServicePointId}
          linkedServicePointCode={linkedServicePointCode}
        />
      ) : null}

      {activeTab === "events" ? (
        <MeterDetailsEventsTab authorizedFetch={authorizedFetch} meterId={meterId} />
      ) : null}

      {activeTab === "readings" ? (
        <MeterDetailsReadingsTab
          meter={meter ? { id: meter.id, serial_number: meter.serial_number } : null}
          meterId={meterId}
          meterReadings={meterReadings}
          billingSnapshots={billingSnapshots}
          loadProfileIntervals={loadProfileIntervals}
          loadProfileChannels={loadProfileChannels}
          isLoadingReadingsContext={isReadingsContextLoading}
          readingsContextError={readingsContextError}
        />
      ) : null}

      {activeTab === "audit" ? (
        <MeterDetailsAuditTab authorizedFetch={authorizedFetch} meterId={meterId} />
      ) : null}

      {activeTab === "commands" ? (
        <div className="detail-stack">
            <section className="subpanel audit-center-overview-panel">
              <div className="section-heading">
                <div>
                  <h2>Command operations center</h2>
                  <p className="muted">
                    Meter-scoped command history, bounded execution detail, and existing
                    execute-now actions using the current commands read model.
                  </p>
                </div>
                <div className="artifact-row">
                  <span className="artifact-pill">
                    {recentCommands.length} command{recentCommands.length === 1 ? "" : "s"} in scope
                  </span>
                  <Link className="secondary-button" href={`/commands?meterId=${meterId}`}>
                    Open commands workspace
                  </Link>
                </div>
              </div>

              {recentCommandsError ? <p className="error-banner">{recentCommandsError}</p> : null}
              {isBootstrappingPage || isLoadingRecentCommands ? (
                <p className="muted">Loading command operations context...</p>
              ) : null}

              {!isBootstrappingPage && !isLoadingRecentCommands ? (
                <div className="detail-stack">
                  <div className="meter-summary-grid">
                    {commandOverviewCards.map((card) => (
                      <div key={card.label} className="stat-card">
                        <span className="stat-label">{card.label}</span>
                        <strong>{card.value}</strong>
                        <p className="muted">{card.note}</p>
                      </div>
                    ))}
                  </div>

                  <div className="artifact-row">
                    <span
                      className={`status-pill ${buildStatusTone(
                        selectedRecentCommand?.command_status ?? null,
                      )}`}
                    >
                      {selectedRecentCommand
                        ? formatStatusLabel(selectedRecentCommand.command_status)
                        : "No current selection"}
                    </span>
                    <span className="artifact-pill">
                      {selectedRecentCommand
                        ? `${formatCommandFamilyLabel(selectedRecentCommand.command_family)} • ${formatFamilySummary(
                            selectedRecentCommand.family_specific_outcome_summary,
                          )}`
                        : "Select a recent command to inspect bounded lifecycle detail"}
                    </span>
                    <span className="artifact-pill">
                      {selectedRecentCommand
                        ? `Created ${formatDateTime(selectedRecentCommand.created_at)}`
                        : "No command timestamp in scope"}
                    </span>
                  </div>
                </div>
              ) : null}
            </section>

        <div className="commands-tab-layout">
            <section className="subpanel">
              <div className="section-heading">
                <div>
                  <h2>Recent commands</h2>
                  <p className="muted">
                    Meter-scoped operational read model for profile capture, relay
                    control, and on-demand read.
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

              {recentCommandsError ? <p className="error-banner">{recentCommandsError}</p> : null}
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
                  <section className="commands-detail-hero">
                    <div className="commands-detail-title-row">
                      <div>
                        <p className="eyebrow">Selected Command</p>
                        <h3>{selectedCommandDetail.command_template_code}</h3>
                        <p className="muted">
                          {formatCommandFamilyLabel(selectedCommandDetail.command_family)} routed
                          through the current{" "}
                          {formatCommandCategoryLabel(selectedCommandDetail.command_category).toLowerCase()}{" "}
                          path for meter {selectedCommandDetail.meter_id}.
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

                    <div className="command-list-item-badges">
                      <span className="artifact-pill">
                        Created {formatDateTime(selectedCommandDetail.created_at)}
                      </span>
                      <span className="artifact-pill">
                        Updated {formatDateTime(selectedCommandDetail.latest_updated_at)}
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
                      <span className="stat-label">Family</span>
                      <strong>{formatCommandFamilyLabel(selectedCommandDetail.command_family)}</strong>
                    </div>
                    <div className="stat-card">
                      <span className="stat-label">Category</span>
                      <strong>{formatCommandCategoryLabel(selectedCommandDetail.command_category)}</strong>
                    </div>
                    <div className="stat-card">
                      <span className="stat-label">Status</span>
                      <strong>{formatStatusLabel(selectedCommandDetail.command_status)}</strong>
                    </div>
                    <div className="stat-card">
                      <span className="stat-label">Created at</span>
                      <strong>{formatDateTime(selectedCommandDetail.created_at)}</strong>
                    </div>
                    <div className="stat-card">
                      <span className="stat-label">Last updated</span>
                      <strong>{formatDateTime(selectedCommandDetail.latest_updated_at)}</strong>
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
                    Thin action layer over the existing profile capture, relay
                    control, and on-demand read application APIs.
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

                <form className="action-form" onSubmit={handleOnDemandReadExecuteNow}>
                  <h3>On-demand read</h3>
                  <label className="field">
                    <span>Command template</span>
                    <select
                      value={onDemandReadTemplateId}
                      onChange={(event) => setOnDemandReadTemplateId(event.target.value)}
                    >
                      {onDemandReadTemplates.map((template) => (
                        <option key={template.id} value={template.id}>
                          {template.code}
                        </option>
                      ))}
                    </select>
                  </label>
                  <label className="field">
                    <span>Endpoint assignment</span>
                    <select
                      value={onDemandReadEndpointAssignmentId}
                      onChange={(event) =>
                        setOnDemandReadEndpointAssignmentId(event.target.value)
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
                      value={onDemandReadProtocolProfileId}
                      onChange={(event) =>
                        setOnDemandReadProtocolProfileId(event.target.value)
                      }
                    >
                      {activeProtocolProfiles.map((profile) => (
                        <option key={profile.id} value={profile.id}>
                          {profile.code}
                        </option>
                      ))}
                    </select>
                  </label>
                  <div className="field">
                    <span>Operation</span>
                    <strong>read_billing_snapshot</strong>
                    <p className="muted">Fixed bounded billing snapshot execute-now flow.</p>
                  </div>

                  <button
                    className="primary-button"
                    disabled={!canSubmitOnDemandRead || isExecutingOnDemandRead}
                    type="submit"
                  >
                    {isExecutingOnDemandRead
                      ? "Executing on-demand read..."
                      : "Execute on-demand read now"}
                  </button>
                </form>
              </div>
            </section>
        </div>
        </div>
      ) : null}
    </section>
  );
}
