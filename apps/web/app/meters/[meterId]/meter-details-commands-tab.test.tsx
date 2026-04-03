import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { MeterDetailsCommandsTab } from "./meter-details-commands-tab";
import { OperationalShell } from "../../operational-shell";

type RequestLog = {
  method: string;
  url: string;
  body: Record<string, unknown> | null;
};

type MockAuditLogItem = {
  id: string;
  created_at: string;
  actor_user_id: string | null;
  actor_username: string | null;
  actor_full_name: string | null;
  action: string;
  entity_type: string;
  entity_id: string | null;
  request_id: string | null;
  ip_address: string | null;
  description: string | null;
  payload: {
    outcome: string;
    http: {
      method: string | null;
      path: string | null;
      user_agent: string | null;
    };
    details: Record<string, unknown> | null;
  } | null;
};

type MockMeterResponse = {
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

type MockEndpointAssignment = {
  id: string;
  endpoint_id: string;
  endpoint_code: string;
  endpoint_display_name: string;
  assignment_status: string;
  is_primary: boolean;
};

type MockProtocolProfile = {
  id: string;
  code: string;
  name: string;
  protocol_family: string;
  is_active: boolean;
};

type MockConsumerLinkage = {
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

type MockCommandTemplate = {
  id: string;
  code: string;
  name: string;
  category: string;
  is_active: boolean;
};

type MockLoadProfileChannel = {
  id: string;
  channel_code: string;
  obis_code: string;
  interval_seconds: number;
  unit?: string | null;
  is_active: boolean;
};

type MockMeterReadingItem = {
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

type MockRegisterSnapshotItem = {
  id: string;
  meter_id: string;
  related_batch_id: string;
  snapshot_type: string;
  captured_at: string;
  payload: Record<string, unknown>;
  checksum: string | null;
};

type MockLoadProfileIntervalItem = {
  id: string;
  meter_id: string;
  channel_id: string;
  interval_start: string;
  interval_end: string;
  value_numeric: string | null;
  quality: string | null;
  source_batch_id: string | null;
};

type MockMeterEventItem = {
  id: string;
  meter_id: string | null;
  related_batch_id: string | null;
  related_attempt_id: string | null;
  event_code: string;
  event_name: string | null;
  severity: string;
  event_state: string;
  occurred_at: string;
  received_at: string;
  raw_payload: Record<string, unknown> | null;
  normalized_payload: Record<string, unknown> | null;
  correlation_id: string | null;
};

type MockConnectivitySessionItem = {
  id: string;
  meter_id: string | null;
  endpoint_id: string | null;
  protocol_association_profile_id: string | null;
  started_at: string;
  ended_at: string | null;
  status: string;
  session_purpose: string;
  request_id: string | null;
  correlation_id: string | null;
  error_code: string | null;
  error_message: string | null;
  bytes_sent: number | null;
  bytes_received: number | null;
  transport_latency_ms: number | null;
  handshake_stage: string | null;
  metadata: Record<string, unknown> | null;
};

type MockGisLiteEntity = {
  meter_id: string;
  meter_serial_number: string;
  meter_status: string;
  meter_last_seen_at: string | null;
  service_point_id: string | null;
  service_point_code: string | null;
  address_line: string | null;
  latitude: number | null;
  longitude: number | null;
  has_coordinates: boolean;
  subscriber_id: string | null;
  subscriber_display_name: string | null;
  subscriber_type: string | null;
  account_id: string | null;
  account_number: string | null;
  location_presence: "coordinates_available" | "service_point_only" | "unlinked";
};

type MockRecentCommandItem = {
  command_id: string;
  command_family: "profile_capture" | "relay_control" | "on_demand_read";
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

function jsonResponse(payload: unknown, status = 200) {
  return new Response(JSON.stringify(payload), {
    status,
    headers: { "Content-Type": "application/json" },
  });
}

function createMockApi({
  meterResponse = {
    id: "meter-1",
    serial_number: "SN-1001",
    utility_meter_number: "UMN-1001",
    manufacturer_code: "GENERIC",
    meter_model_code: "GM-1",
    meter_profile_code: "default",
    communication_profile_code: "dlms-default",
    current_status: "commissioned",
    transformer_id: "transformer-1",
    service_point_id: "sp-1",
    last_seen_at: "2026-03-30T11:00:00.000Z",
  },
  meterStatus = 200,
  meterErrorDetail = "Meter not found.",
  endpointAssignmentsStatus = 200,
  endpointAssignmentsErrorDetail = "Endpoint assignments unavailable.",
  protocolProfilesStatus = 200,
  protocolProfilesErrorDetail = "Protocol profiles unavailable.",
  loadProfileChannelsStatus = 200,
  loadProfileChannelsErrorDetail = "Load profile channels unavailable.",
  readingsStatus = 200,
  readingsErrorDetail = "Meter readings unavailable.",
  registerSnapshotsStatus = 200,
  registerSnapshotsErrorDetail = "Register snapshots unavailable.",
  loadProfileIntervalsStatus = 200,
  loadProfileIntervalsErrorDetail = "Load profile intervals unavailable.",
  gisLiteStatus = 200,
  gisLiteDetail = "Meter GIS context unavailable.",
  recentCommandsItems,
  recentCommandsStatus = 200,
  recentCommandsDetail = "Recent meter commands unavailable.",
  commandDetailStatus = 200,
  commandDetailDetail = "Command detail unavailable.",
  consumerLinkageStatus = 200,
  consumerLinkageErrorDetail = "Consumer linkage unavailable.",
  auditLogsStatus = 200,
  auditLogsDetail = "Meter audit history unavailable.",
  meterEventsStatus = 200,
  meterEventsDetail = "Meter events unavailable.",
  meterSessionsStatus = 200,
  meterSessionsDetail = "Connectivity session history unavailable.",
  endpointAssignments = [
    {
      id: "assignment-1",
      endpoint_id: "endpoint-1",
      endpoint_code: "tcp-primary",
      endpoint_display_name: "TCP Primary",
      assignment_status: "active",
      is_primary: true,
    },
  ],
  protocolProfiles = [
    {
      id: "protocol-profile-1",
      code: "dlms-profile",
      name: "DLMS Profile",
      protocol_family: "dlms_cosem",
      is_active: true,
    },
  ],
  templateItems = [
    {
      id: "template-profile-1",
      code: "profile-capture-template",
      name: "Profile Capture",
      category: "profile_capture",
      is_active: true,
    },
    {
      id: "template-relay-disconnect-1",
      code: "relay-disconnect-template",
      name: "Relay Disconnect",
      category: "remote_disconnect",
      is_active: true,
    },
    {
      id: "template-relay-reconnect-1",
      code: "relay-reconnect-template",
      name: "Relay Reconnect",
      category: "remote_reconnect",
      is_active: true,
    },
    {
      id: "template-on-demand-read-1",
      code: "on-demand-read-template",
      name: "On Demand Read",
      category: "on_demand_read",
      is_active: true,
    },
  ],
  loadProfileChannels = [
    {
      id: "channel-1",
      channel_code: "import-wh",
      obis_code: "1.0.1.8.0.255",
      interval_seconds: 900,
      unit: "kWh",
      is_active: true,
    },
    {
      id: "channel-2",
      channel_code: "export-wh",
      obis_code: "1.0.2.8.0.255",
      interval_seconds: 900,
      unit: "kWh",
      is_active: true,
    },
  ],
  readingsItems = [
    {
      id: "reading-1",
      batch_id: "batch-1",
      meter_id: "meter-1",
      obis_code: "1.0.1.8.0.255",
      reading_type: "register",
      value_numeric: "1552.41",
      value_text: null,
      value_timestamp: null,
      unit: "kWh",
      quality: "validated",
      captured_at: "2026-03-30T11:05:00.000Z",
      metadata: null,
    },
  ],
  registerSnapshots = [
    {
      id: "snapshot-1",
      meter_id: "meter-1",
      related_batch_id: "batch-2",
      snapshot_type: "billing",
      captured_at: "2026-03-30T10:55:00.000Z",
      payload: {
        total_import_kwh: 1552.41,
        md_kw: 7.2,
      },
      checksum: null,
    },
  ],
  loadProfileIntervals = [
    {
      id: "interval-1",
      meter_id: "meter-1",
      channel_id: "channel-1",
      interval_start: "2026-03-30T10:00:00.000Z",
      interval_end: "2026-03-30T10:15:00.000Z",
      value_numeric: "11.50",
      quality: "valid",
      source_batch_id: "batch-3",
    },
  ],
  gisLiteEntities = [
    {
      meter_id: "meter-1",
      meter_serial_number: "SN-1001",
      meter_status: "commissioned",
      meter_last_seen_at: "2026-03-30T11:00:00.000Z",
      service_point_id: "sp-1",
      service_point_code: "SP-1001",
      address_line: "Muscat Block A",
      latitude: 23.588,
      longitude: 58.3829,
      has_coordinates: true,
      subscriber_id: "consumer-1",
      subscriber_display_name: "Amina Al Balushi",
      subscriber_type: "residential",
      account_id: "account-1",
      account_number: "ACC-1001",
      location_presence: "coordinates_available",
    },
  ],
  auditLogs = [
    {
      id: "audit-meter-1",
      created_at: "2026-03-30T11:10:00.000Z",
      actor_user_id: "user-1",
      actor_username: "ops.user",
      actor_full_name: "Ops User",
      action: "meters.update",
      entity_type: "meters",
      entity_id: "meter-1",
      request_id: "req-meter-1",
      ip_address: "127.0.0.1",
      description: "Meter communication profile updated.",
      payload: {
        outcome: "success",
        http: {
          method: "PATCH",
          path: "/api/v1/meters/meter-1",
          user_agent: "vitest",
        },
        details: {
          field: "communication_profile_code",
        },
      },
    },
    {
      id: "audit-meter-2",
      created_at: "2026-03-30T10:40:00.000Z",
      actor_user_id: "user-2",
      actor_username: "ops.audit",
      actor_full_name: "Ops Audit",
      action: "meters.status.change",
      entity_type: "meters",
      entity_id: "meter-1",
      request_id: "req-meter-2",
      ip_address: "127.0.0.2",
      description: "Meter status changed to commissioned.",
      payload: {
        outcome: "success",
        http: {
          method: "POST",
          path: "/api/v1/meters/meter-1/status",
          user_agent: "vitest",
        },
        details: {
          status: "commissioned",
        },
      },
    },
  ],
  meterEvents = [
    {
      id: "event-meter-1",
      meter_id: "meter-1",
      related_batch_id: "batch-event-1",
      related_attempt_id: null,
      event_code: "tamper_open",
      event_name: "Tamper Open",
      severity: "critical",
      event_state: "open",
      occurred_at: "2026-03-30T11:20:00.000Z",
      received_at: "2026-03-30T11:20:30.000Z",
      raw_payload: null,
      normalized_payload: {
        phase: "A",
        source: "tamper_switch",
      },
      correlation_id: "corr-event-1",
    },
    {
      id: "event-meter-2",
      meter_id: "meter-1",
      related_batch_id: null,
      related_attempt_id: "attempt-event-2",
      event_code: "power_restore",
      event_name: "Power Restore",
      severity: "info",
      event_state: "closed",
      occurred_at: "2026-03-30T10:20:00.000Z",
      received_at: "2026-03-30T10:20:10.000Z",
      raw_payload: null,
      normalized_payload: {
        restoration_reason: "voltage_normalized",
      },
      correlation_id: null,
    },
  ],
  meterSessions = [
    {
      id: "session-1",
      meter_id: "meter-1",
      endpoint_id: "endpoint-1",
      protocol_association_profile_id: "protocol-profile-1",
      started_at: "2026-03-30T11:10:00.000Z",
      ended_at: "2026-03-30T11:12:00.000Z",
      status: "succeeded",
      session_purpose: "on_demand_read",
      request_id: "req-session-1",
      correlation_id: "corr-session-1",
      error_code: null,
      error_message: null,
      bytes_sent: 512,
      bytes_received: 1024,
      transport_latency_ms: 180,
      handshake_stage: "association",
      metadata: null,
    },
    {
      id: "session-2",
      meter_id: "meter-1",
      endpoint_id: "endpoint-1",
      protocol_association_profile_id: "protocol-profile-1",
      started_at: "2026-03-30T09:30:00.000Z",
      ended_at: "2026-03-30T09:31:00.000Z",
      status: "failed",
      session_purpose: "profile_capture",
      request_id: "req-session-2",
      correlation_id: null,
      error_code: "ASSOCIATION_REJECTED",
      error_message: "Association rejected",
      bytes_sent: 120,
      bytes_received: 64,
      transport_latency_ms: null,
      handshake_stage: "association",
      metadata: null,
    },
  ],
  consumerLinkageResponse = {
    meter_id: "meter-1",
    linkage_status: "linked",
    linkage_source: "meter_account_assignment",
    consumer_id: "consumer-1",
    consumer_display_name: "Amina Al Balushi",
    consumer_type: "residential",
    consumer_external_ref: "CON-1001",
    account_id: "account-1",
    account_number: "ACC-1001",
    account_status: "active",
    service_point_id: "sp-1",
    service_point_code: "SP-1001",
  },
}: {
  meterResponse?: MockMeterResponse;
  meterStatus?: number;
  meterErrorDetail?: string;
  endpointAssignmentsStatus?: number;
  endpointAssignmentsErrorDetail?: string;
  protocolProfilesStatus?: number;
  protocolProfilesErrorDetail?: string;
  loadProfileChannelsStatus?: number;
  loadProfileChannelsErrorDetail?: string;
  readingsStatus?: number;
  readingsErrorDetail?: string;
  registerSnapshotsStatus?: number;
  registerSnapshotsErrorDetail?: string;
  loadProfileIntervalsStatus?: number;
  loadProfileIntervalsErrorDetail?: string;
  gisLiteStatus?: number;
  gisLiteDetail?: string;
  consumerLinkageStatus?: number;
  consumerLinkageErrorDetail?: string;
  recentCommandsStatus?: number;
  recentCommandsDetail?: string;
  commandDetailStatus?: number;
  commandDetailDetail?: string;
  auditLogsStatus?: number;
  auditLogsDetail?: string;
  meterEventsStatus?: number;
  meterEventsDetail?: string;
  meterSessionsStatus?: number;
  meterSessionsDetail?: string;
  endpointAssignments?: MockEndpointAssignment[];
  protocolProfiles?: MockProtocolProfile[];
  templateItems?: MockCommandTemplate[];
  loadProfileChannels?: MockLoadProfileChannel[];
  readingsItems?: MockMeterReadingItem[];
  registerSnapshots?: MockRegisterSnapshotItem[];
  loadProfileIntervals?: MockLoadProfileIntervalItem[];
  gisLiteEntities?: MockGisLiteEntity[];
  recentCommandsItems?: MockRecentCommandItem[];
  auditLogs?: MockAuditLogItem[];
  meterEvents?: MockMeterEventItem[];
  meterSessions?: MockConnectivitySessionItem[];
  consumerLinkageResponse?: MockConsumerLinkage;
} = {}) {
  const requests: RequestLog[] = [];
  const recentCommands = (
    recentCommandsItems ?? [
    {
      command_id: "cmd-profile-1",
      command_family: "profile_capture",
      command_category: "profile_capture",
      command_status: "succeeded",
      meter_id: "meter-1",
      command_template_code: "profile-capture-template",
      latest_command_execution_attempt_id: "attempt-profile-1",
      latest_command_execution_attempt_status: "succeeded",
      runtime_execution_record_id: "runtime-profile-1",
      family_specific_outcome_summary: { terminal_status_category: "acknowledged" },
      orchestration_artifact_present: true,
      terminalization_artifact_present: true,
      execute_now_artifact_present: true,
      created_at: "2026-03-30T10:00:00.000Z",
      latest_updated_at: "2026-03-30T10:05:00.000Z",
    },
    {
      command_id: "cmd-relay-1",
      command_family: "relay_control",
      command_category: "remote_disconnect",
      command_status: "succeeded",
      meter_id: "meter-1",
      command_template_code: "relay-disconnect-template",
      latest_command_execution_attempt_id: "attempt-relay-1",
      latest_command_execution_attempt_status: "succeeded",
      runtime_execution_record_id: "runtime-relay-1",
      family_specific_outcome_summary: {
        relay_control_operation: "disconnect",
        relay_control_execution_outcome: "succeeded",
      },
      orchestration_artifact_present: true,
      terminalization_artifact_present: true,
      execute_now_artifact_present: true,
      created_at: "2026-03-30T09:00:00.000Z",
      latest_updated_at: "2026-03-30T09:03:00.000Z",
    },
    {
      command_id: "cmd-on-demand-1",
      command_family: "on_demand_read",
      command_category: "on_demand_read",
      command_status: "succeeded",
      meter_id: "meter-1",
      command_template_code: "on-demand-read-template",
      latest_command_execution_attempt_id: "attempt-on-demand-1",
      latest_command_execution_attempt_status: "succeeded",
      runtime_execution_record_id: "runtime-on-demand-1",
      family_specific_outcome_summary: {
        on_demand_read_operation: "read_billing_snapshot",
        snapshot_type: "billing",
        on_demand_read_execution_outcome: "succeeded",
      },
      orchestration_artifact_present: true,
      terminalization_artifact_present: true,
      execute_now_artifact_present: true,
      created_at: "2026-03-30T08:00:00.000Z",
      latest_updated_at: "2026-03-30T08:02:00.000Z",
    },
  ]
  ).map((item: MockRecentCommandItem) => ({ ...item }));

  const detailById: Record<string, Record<string, unknown>> = {
    "cmd-profile-1": {
      command_id: "cmd-profile-1",
      command_family: "profile_capture",
      command_category: "profile_capture",
      command_status: "succeeded",
      meter_id: "meter-1",
      command_template_code: "profile-capture-template",
      latest_command_execution_attempt_id: "attempt-profile-1",
      latest_command_execution_attempt_status: "succeeded",
      runtime_execution_record_id: "runtime-profile-1",
      family_specific_outcome_summary: { terminal_status_category: "acknowledged" },
      orchestration_artifact_present: true,
      terminalization_artifact_present: true,
      execute_now_artifact_present: true,
      created_at: "2026-03-30T10:00:00.000Z",
      latest_updated_at: "2026-03-30T10:05:00.000Z",
      projection_record: { runtime_execution_record_id: "runtime-profile-1" },
    },
    "cmd-relay-1": {
      command_id: "cmd-relay-1",
      command_family: "relay_control",
      command_category: "remote_disconnect",
      command_status: "succeeded",
      meter_id: "meter-1",
      command_template_code: "relay-disconnect-template",
      latest_command_execution_attempt_id: "attempt-relay-1",
      latest_command_execution_attempt_status: "succeeded",
      runtime_execution_record_id: "runtime-relay-1",
      family_specific_outcome_summary: {
        relay_control_operation: "disconnect",
        relay_control_execution_outcome: "succeeded",
      },
      orchestration_artifact_present: true,
      terminalization_artifact_present: true,
      execute_now_artifact_present: true,
      created_at: "2026-03-30T09:00:00.000Z",
      latest_updated_at: "2026-03-30T09:03:00.000Z",
      projection_record: { runtime_execution_record_id: "runtime-relay-1" },
    },
    "cmd-on-demand-1": {
      command_id: "cmd-on-demand-1",
      command_family: "on_demand_read",
      command_category: "on_demand_read",
      command_status: "succeeded",
      meter_id: "meter-1",
      command_template_code: "on-demand-read-template",
      latest_command_execution_attempt_id: "attempt-on-demand-1",
      latest_command_execution_attempt_status: "succeeded",
      runtime_execution_record_id: "runtime-on-demand-1",
      family_specific_outcome_summary: {
        on_demand_read_operation: "read_billing_snapshot",
        snapshot_type: "billing",
        on_demand_read_execution_outcome: "succeeded",
      },
      orchestration_artifact_present: true,
      terminalization_artifact_present: true,
      execute_now_artifact_present: true,
      created_at: "2026-03-30T08:00:00.000Z",
      latest_updated_at: "2026-03-30T08:02:00.000Z",
      projection_record: { runtime_execution_record_id: "runtime-on-demand-1" },
    },
  };

  const fetchMock = vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
    const url = input.toString();
    const method = init?.method ?? "GET";
    const body = init?.body ? (JSON.parse(String(init.body)) as Record<string, unknown>) : null;

    if (method !== "GET") {
      requests.push({ method, url, body });
    }

    if (url.endsWith("/api/v1/auth/me")) {
      return jsonResponse({
        id: "user-1",
        username: "ops.user",
        email: "ops@example.com",
        full_name: "Ops User",
        status: "active",
        is_superuser: true,
      });
    }

    if (url.endsWith("/api/v1/meters/meter-1")) {
      if (meterStatus !== 200) {
        return jsonResponse({ detail: meterErrorDetail }, meterStatus);
      }
      return jsonResponse(meterResponse);
    }

    if (url.endsWith("/api/v1/meters/meter-1/consumer-linkage")) {
      if (consumerLinkageStatus !== 200) {
        return jsonResponse({ detail: consumerLinkageErrorDetail }, consumerLinkageStatus);
      }
      return jsonResponse(consumerLinkageResponse);
    }

    if (url.endsWith("/api/v1/command-templates")) {
      return jsonResponse({
        total: templateItems.length,
        items: templateItems,
      });
    }

    if (url.endsWith("/api/v1/meters/meter-1/endpoint-assignments")) {
      if (endpointAssignmentsStatus !== 200) {
        return jsonResponse(
          { detail: endpointAssignmentsErrorDetail },
          endpointAssignmentsStatus,
        );
      }
      return jsonResponse({
        total: endpointAssignments.length,
        items: endpointAssignments,
      });
    }

    if (url.endsWith("/api/v1/protocol-association-profiles")) {
      if (protocolProfilesStatus !== 200) {
        return jsonResponse(
          { detail: protocolProfilesErrorDetail },
          protocolProfilesStatus,
        );
      }
      return jsonResponse({
        total: protocolProfiles.length,
        items: protocolProfiles,
      });
    }

    if (url.endsWith("/api/v1/meters/meter-1/load-profile-channels")) {
      if (loadProfileChannelsStatus !== 200) {
        return jsonResponse(
          { detail: loadProfileChannelsErrorDetail },
          loadProfileChannelsStatus,
        );
      }
      return jsonResponse({
        total: loadProfileChannels.length,
        items: loadProfileChannels,
      });
    }

    if (url.includes("/api/v1/meters/meter-1/readings")) {
      if (readingsStatus !== 200) {
        return jsonResponse({ detail: readingsErrorDetail }, readingsStatus);
      }
      return jsonResponse({
        total: readingsItems.length,
        items: readingsItems,
      });
    }

    if (url.includes("/api/v1/meters/meter-1/register-snapshots")) {
      if (registerSnapshotsStatus !== 200) {
        return jsonResponse(
          { detail: registerSnapshotsErrorDetail },
          registerSnapshotsStatus,
        );
      }
      return jsonResponse({
        total: registerSnapshots.length,
        items: registerSnapshots,
      });
    }

    if (url.includes("/api/v1/meters/meter-1/load-profile-intervals")) {
      if (loadProfileIntervalsStatus !== 200) {
        return jsonResponse(
          { detail: loadProfileIntervalsErrorDetail },
          loadProfileIntervalsStatus,
        );
      }
      return jsonResponse({
        total: loadProfileIntervals.length,
        items: loadProfileIntervals,
      });
    }

    if (url.includes("/api/v1/gis-lite/entities?")) {
      if (gisLiteStatus !== 200) {
        return jsonResponse({ detail: gisLiteDetail }, gisLiteStatus);
      }
      const parsedUrl = new URL(url);
      const meterIdFilter = parsedUrl.searchParams.get("meter_id");
      const filteredItems = meterIdFilter
        ? gisLiteEntities.filter((item) => item.meter_id === meterIdFilter)
        : gisLiteEntities;
      return jsonResponse({
        total: filteredItems.length,
        items: filteredItems,
      });
    }

    if (url.includes("/api/v1/audit-logs?")) {
      if (auditLogsStatus !== 200) {
        return jsonResponse({ detail: auditLogsDetail }, auditLogsStatus);
      }

      const parsedUrl = new URL(url);
      const entityTypeFilter = parsedUrl.searchParams.get("entity_type")?.toLowerCase() ?? "";
      const entityIdFilter = parsedUrl.searchParams.get("entity_id") ?? "";
      const filteredItems = auditLogs.filter((item) => {
        const entityTypeMatch =
          entityTypeFilter.length === 0 ||
          item.entity_type.toLowerCase().includes(entityTypeFilter);
        const entityIdMatch = entityIdFilter.length === 0 || item.entity_id === entityIdFilter;
        return entityTypeMatch && entityIdMatch;
      });

      return jsonResponse({
        total: filteredItems.length,
        items: filteredItems,
      });
    }

    if (url.includes("/api/v1/meters/meter-1/ingested-events?")) {
      if (meterEventsStatus !== 200) {
        return jsonResponse({ detail: meterEventsDetail }, meterEventsStatus);
      }
      return jsonResponse({
        total: meterEvents.length,
        items: meterEvents,
      });
    }

    if (url.includes("/api/v1/meters/meter-1/sessions?")) {
      if (meterSessionsStatus !== 200) {
        return jsonResponse({ detail: meterSessionsDetail }, meterSessionsStatus);
      }
      return jsonResponse({
        total: meterSessions.length,
        items: meterSessions,
      });
    }

    if (url.includes("/api/v1/meters/meter-1/commands/recent")) {
      if (recentCommandsStatus !== 200) {
        return jsonResponse({ detail: recentCommandsDetail }, recentCommandsStatus);
      }
      const parsedUrl = new URL(url);
      const family = parsedUrl.searchParams.get("family");
      const items =
        family === null
          ? recentCommands
          : recentCommands.filter(
              (item: MockRecentCommandItem) => item.command_family === family,
            );

      return jsonResponse({
        meter_id: "meter-1",
        total: items.length,
        limit: Number(parsedUrl.searchParams.get("limit") ?? "20"),
        family_filter: family,
        items,
      });
    }

    if (url.includes("/api/v1/commands/") && url.endsWith("/detail")) {
      if (commandDetailStatus !== 200) {
        return jsonResponse({ detail: commandDetailDetail }, commandDetailStatus);
      }
      const commandId = url.split("/api/v1/commands/")[1].replace("/detail", "");
      return jsonResponse({ result: detailById[commandId] });
    }

    if (method === "POST" && url.endsWith("/api/v1/meters/meter-1/commands/profile-capture/execute-now")) {
      recentCommands.unshift({
        command_id: "cmd-profile-action",
        command_family: "profile_capture",
        command_category: "profile_capture",
        command_status: "succeeded",
        meter_id: "meter-1",
        command_template_code: "profile-capture-template",
        latest_command_execution_attempt_id: "attempt-profile-action",
        latest_command_execution_attempt_status: "succeeded",
        runtime_execution_record_id: "runtime-profile-action",
        family_specific_outcome_summary: { terminal_status_category: "acknowledged" },
        orchestration_artifact_present: true,
        terminalization_artifact_present: true,
        execute_now_artifact_present: true,
        created_at: "2026-03-30T12:00:00.000Z",
        latest_updated_at: "2026-03-30T12:02:00.000Z",
      });
      detailById["cmd-profile-action"] = {
        command_id: "cmd-profile-action",
        command_family: "profile_capture",
        command_category: "profile_capture",
        command_status: "succeeded",
        meter_id: "meter-1",
        command_template_code: "profile-capture-template",
        latest_command_execution_attempt_id: "attempt-profile-action",
        latest_command_execution_attempt_status: "succeeded",
        runtime_execution_record_id: "runtime-profile-action",
        family_specific_outcome_summary: { terminal_status_category: "acknowledged" },
        orchestration_artifact_present: true,
        terminalization_artifact_present: true,
        execute_now_artifact_present: true,
        created_at: "2026-03-30T12:00:00.000Z",
        latest_updated_at: "2026-03-30T12:02:00.000Z",
        projection_record: { runtime_execution_record_id: "runtime-profile-action" },
      };
      return jsonResponse({ result: { command_id: "cmd-profile-action" } });
    }

    if (method === "POST" && url.endsWith("/api/v1/meters/meter-1/commands/relay-control/execute-now")) {
      const operation = String(body?.relay_operation ?? "disconnect");
      const templateCode =
        operation === "reconnect"
          ? "relay-reconnect-template"
          : "relay-disconnect-template";
      return jsonResponse({
        result: { command_id: `cmd-relay-${operation}-action` },
      });
    }

    if (method === "POST" && url.endsWith("/api/v1/meters/meter-1/commands/on-demand-read/execute-now")) {
      recentCommands.unshift({
        command_id: "cmd-on-demand-action",
        command_family: "on_demand_read",
        command_category: "on_demand_read",
        command_status: "succeeded",
        meter_id: "meter-1",
        command_template_code: "on-demand-read-template",
        latest_command_execution_attempt_id: "attempt-on-demand-action",
        latest_command_execution_attempt_status: "succeeded",
        runtime_execution_record_id: "runtime-on-demand-action",
        family_specific_outcome_summary: {
          on_demand_read_operation: "read_billing_snapshot",
          snapshot_type: "billing",
          on_demand_read_execution_outcome: "succeeded",
        },
        orchestration_artifact_present: true,
        terminalization_artifact_present: true,
        execute_now_artifact_present: true,
        created_at: "2026-03-30T12:10:00.000Z",
        latest_updated_at: "2026-03-30T12:11:00.000Z",
      });
      detailById["cmd-on-demand-action"] = {
        command_id: "cmd-on-demand-action",
        command_family: "on_demand_read",
        command_category: "on_demand_read",
        command_status: "succeeded",
        meter_id: "meter-1",
        command_template_code: "on-demand-read-template",
        latest_command_execution_attempt_id: "attempt-on-demand-action",
        latest_command_execution_attempt_status: "succeeded",
        runtime_execution_record_id: "runtime-on-demand-action",
        family_specific_outcome_summary: {
          on_demand_read_operation: "read_billing_snapshot",
          snapshot_type: "billing",
          on_demand_read_execution_outcome: "succeeded",
        },
        orchestration_artifact_present: true,
        terminalization_artifact_present: true,
        execute_now_artifact_present: true,
        created_at: "2026-03-30T12:10:00.000Z",
        latest_updated_at: "2026-03-30T12:11:00.000Z",
        projection_record: { runtime_execution_record_id: "runtime-on-demand-action" },
      };
      return jsonResponse({ result: { command_id: "cmd-on-demand-action" } });
    }

    throw new Error(`Unhandled request: ${method} ${url}`);
  });

  return { fetchMock, requests };
}

function renderMeterTabInShell() {
  render(
    <OperationalShell
      eyebrow="Operational Pages"
      title="Meter meter-1"
      description="Bounded meter details"
      currentMeterId="meter-1"
    >
      {({ authorizedFetch }) => (
        <MeterDetailsCommandsTab
          meterId="meter-1"
          authorizedFetch={authorizedFetch}
        />
      )}
    </OperationalShell>,
  );
}

async function openMeterWorkspaceTab(
  user: ReturnType<typeof userEvent.setup>,
  tabName:
    | "Summary"
    | "Configuration"
    | "Connectivity"
    | "GIS"
    | "Consumer / Commercial"
    | "Events"
    | "Readings"
    | "Audit"
    | "Commands",
) {
  await user.click(
    await screen.findByRole("tab", { name: new RegExp(tabName, "i") }),
  );
}

describe("MeterDetailsCommandsTab", () => {
  beforeEach(() => {
    window.localStorage.setItem("sunrise.web.apiBaseUrl", "http://localhost:8000");
    window.localStorage.setItem("sunrise.web.accessToken", "token-1");
  });

  afterEach(() => {
    vi.unstubAllGlobals();
    window.localStorage.clear();
  });

  it("renders recent commands for the meter and hides unsupported families", async () => {
    const { fetchMock } = createMockApi();
    vi.stubGlobal("fetch", fetchMock);
    const user = userEvent.setup();

    renderMeterTabInShell();
    await openMeterWorkspaceTab(user, "Commands");

    expect(await screen.findByRole("heading", { name: "Command operations center" })).toBeInTheDocument();
    expect(await screen.findByRole("link", { name: "Current meter" })).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Open commands workspace" })).toHaveAttribute(
      "href",
      "/commands?meterId=meter-1",
    );
    expect(await screen.findAllByText("profile-capture-template")).not.toHaveLength(0);
    expect(screen.getAllByText("relay-disconnect-template")).not.toHaveLength(0);
    expect(screen.getAllByText("on-demand-read-template")).not.toHaveLength(0);
    expect(screen.getAllByText("Succeeded")).not.toHaveLength(0);
  });

  it("renders the operational summary panel with current meter context", async () => {
    const { fetchMock } = createMockApi();
    vi.stubGlobal("fetch", fetchMock);

    renderMeterTabInShell();

    expect(await screen.findAllByText("SN-1001")).not.toHaveLength(0);

    const summaryPanel = screen
      .getByRole("heading", { name: "Operational summary" })
      .closest("section");
    expect(summaryPanel).not.toBeNull();

    expect(within(summaryPanel as HTMLElement).getByText("meter-1")).toBeInTheDocument();
    expect(within(summaryPanel as HTMLElement).getByText("commissioned")).toBeInTheDocument();
    expect(within(summaryPanel as HTMLElement).getByText("dlms-default")).toBeInTheDocument();
    expect(within(summaryPanel as HTMLElement).getByText("tcp-primary")).toBeInTheDocument();
    expect(within(summaryPanel as HTMLElement).getByText("dlms-profile")).toBeInTheDocument();
  });

  it("renders the refined meter header with linked operational context and navigation hints", async () => {
    const { fetchMock } = createMockApi();
    vi.stubGlobal("fetch", fetchMock);

    renderMeterTabInShell();

    expect(await screen.findByText("Authoritative Meter Record")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Open readings" })).toHaveAttribute(
      "href",
      "/readings?meterId=meter-1",
    );
    expect(screen.getByRole("link", { name: "Open bulk commands" })).toHaveAttribute(
      "href",
      "/commands?meterId=meter-1",
    );
    expect(screen.getByRole("link", { name: "Open account detail" })).toHaveAttribute(
      "href",
      "/accounts/account-1",
    );
    expect(
      screen.getByRole("link", { name: "Open service point detail" }),
    ).toHaveAttribute("href", "/service-points/sp-1");
    expect(
      screen.getByRole("link", { name: "Open transformer detail" }),
    ).toHaveAttribute("href", "/transformers-substations/transformer-1");
  });

  it("renders a bounded loading state while the meter summary is bootstrapping", async () => {
    const { fetchMock } = createMockApi();
    vi.stubGlobal(
      "fetch",
      vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
        const url = input.toString();
        if (url.endsWith("/api/v1/meters/meter-1")) {
          await new Promise((resolve) => setTimeout(resolve, 100));
        }
        return fetchMock(input, init);
      }),
    );

    renderMeterTabInShell();

    await waitFor(() => {
      expect(
        screen.queryByText("Loading meter summary...") ??
          screen.queryByText("meter-1"),
      ).toBeInTheDocument();
    });
    expect(await screen.findByText("meter-1")).toBeInTheDocument();
  });

  it("renders the connectivity tab with current endpoint, freshness, and recent session history", async () => {
    const { fetchMock } = createMockApi();
    vi.stubGlobal("fetch", fetchMock);
    const user = userEvent.setup();

    renderMeterTabInShell();
    await openMeterWorkspaceTab(user, "Connectivity");

    expect(await screen.findByText("Connectivity context")).toBeInTheDocument();

    const connectivityPanel = screen
      .getByRole("heading", { name: "Connectivity context" })
      .closest("section");
    expect(connectivityPanel).not.toBeNull();

    await waitFor(() => {
      expect(
        within(connectivityPanel as HTMLElement).getByText("TCP Primary"),
      ).toBeInTheDocument();
      expect(
        within(connectivityPanel as HTMLElement).getAllByText("Succeeded"),
      ).not.toHaveLength(0);
      expect(
        within(connectivityPanel as HTMLElement).getByText("Active • Primary assignment"),
      ).toBeInTheDocument();
      expect(
        within(connectivityPanel as HTMLElement).getByText("dlms-profile"),
      ).toBeInTheDocument();
      expect(
        within(connectivityPanel as HTMLElement).getAllByText("Recent connectivity signal recorded"),
      ).not.toHaveLength(0);
      expect(
        within(connectivityPanel as HTMLElement).getByText("Association"),
      ).toBeInTheDocument();
      expect(
        within(connectivityPanel as HTMLElement).getAllByText(/On Demand Read/i),
      ).not.toHaveLength(0);
    });

    const sessionsPanel = screen
      .getByRole("heading", { name: "Recent session history" })
      .closest("section");
    expect(sessionsPanel).not.toBeNull();
    expect(within(sessionsPanel as HTMLElement).getByText("Succeeded")).toBeInTheDocument();
    expect(within(sessionsPanel as HTMLElement).getByText("Association rejected")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Open connectivity surface" })).toHaveAttribute(
      "href",
      "/connectivity",
    );
  });

  it("renders the configuration tab with meter model, profile, and protocol context", async () => {
    const { fetchMock } = createMockApi();
    vi.stubGlobal("fetch", fetchMock);
    const user = userEvent.setup();

    renderMeterTabInShell();
    await openMeterWorkspaceTab(user, "Configuration");

    const configurationPanel = screen
      .getByRole("heading", { name: "Configuration context" })
      .closest("section");
    expect(configurationPanel).not.toBeNull();

    await waitFor(() => {
      expect(
        within(configurationPanel as HTMLElement).getByText("GENERIC / GM-1"),
      ).toBeInTheDocument();
      expect(
        within(configurationPanel as HTMLElement).getByText("default"),
      ).toBeInTheDocument();
      expect(
        within(configurationPanel as HTMLElement).getByText("dlms-default"),
      ).toBeInTheDocument();
      expect(
        within(configurationPanel as HTMLElement).getByText("dlms-profile"),
      ).toBeInTheDocument();
      expect(
        within(configurationPanel as HTMLElement).getByText("Not recorded"),
      ).toBeInTheDocument();
    });

    const recordPanel = screen
      .getByRole("heading", { name: "Operational configuration record" })
      .closest("section");
    expect(recordPanel).not.toBeNull();
    expect(
      within(recordPanel as HTMLElement).getByRole("link", {
        name: "Open service point detail",
      }),
    ).toHaveAttribute("href", "/service-points/sp-1");
    expect(
      within(recordPanel as HTMLElement).getByRole("link", {
        name: "Open transformer detail",
      }),
    ).toHaveAttribute("href", "/transformers-substations/transformer-1");
  });

  it("renders a bounded configuration gap state when active profile context is unavailable", async () => {
    const { fetchMock } = createMockApi({
      meterResponse: {
        id: "meter-1",
        serial_number: "SN-1001",
        utility_meter_number: "UMN-1001",
        manufacturer_code: "GENERIC",
        meter_model_code: "GM-1",
        meter_profile_code: null,
        communication_profile_code: null,
        current_status: "commissioned",
        transformer_id: null,
        service_point_id: null,
        last_seen_at: "2026-03-30T11:00:00.000Z",
      },
      endpointAssignments: [],
      protocolProfiles: [],
      consumerLinkageResponse: {
        meter_id: "meter-1",
        linkage_status: "unlinked",
        linkage_source: null,
        consumer_id: null,
        consumer_display_name: null,
        consumer_type: null,
        consumer_external_ref: null,
        account_id: null,
        account_number: null,
        account_status: null,
        service_point_id: null,
        service_point_code: null,
      },
    });
    vi.stubGlobal("fetch", fetchMock);
    const user = userEvent.setup();

    renderMeterTabInShell();
    await openMeterWorkspaceTab(user, "Configuration");

    expect(
      await screen.findByText(
        "No active profile or endpoint configuration is currently recorded for this meter. The bounded catalog record is still shown below.",
      ),
    ).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "Operational configuration record" })).toBeInTheDocument();
  });

  it("renders a bounded meter configuration error state without disturbing the workspace", async () => {
    const { fetchMock } = createMockApi({
      endpointAssignmentsStatus: 503,
      protocolProfilesStatus: 503,
    });
    vi.stubGlobal("fetch", fetchMock);
    const user = userEvent.setup();

    renderMeterTabInShell();
    await openMeterWorkspaceTab(user, "Configuration");

    expect(
      await screen.findByText("Unable to load complete meter configuration context."),
    ).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "Configuration context" })).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "Operational configuration record" })).toBeInTheDocument();
  });

  it("renders the consumer linkage card when a linked subscriber exists", async () => {
    const { fetchMock } = createMockApi();
    vi.stubGlobal("fetch", fetchMock);

    renderMeterTabInShell();

    const linkagePanel = (await screen.findByRole("heading", {
      name: "Consumer linkage",
    })).closest("section");
    expect(linkagePanel).not.toBeNull();

    await waitFor(() => {
      expect(
        within(linkagePanel as HTMLElement).getByText("Amina Al Balushi"),
      ).toBeInTheDocument();
      expect(
        within(linkagePanel as HTMLElement).getByText("consumer-1"),
      ).toBeInTheDocument();
      expect(
        within(linkagePanel as HTMLElement).getByText("ACC-1001"),
      ).toBeInTheDocument();
      expect(
        within(linkagePanel as HTMLElement).getByText("SP-1001"),
      ).toBeInTheDocument();
    });

    expect(
      within(linkagePanel as HTMLElement).getByRole("link", {
        name: "Open subscriber detail",
      }),
    ).toHaveAttribute("href", "/subscribers/consumer-1");
  });

  it("renders a bounded unlinked state when no subscriber is linked to the meter", async () => {
    const { fetchMock } = createMockApi({
      consumerLinkageResponse: {
        meter_id: "meter-1",
        linkage_status: "unlinked",
        linkage_source: null,
        consumer_id: null,
        consumer_display_name: null,
        consumer_type: null,
        consumer_external_ref: null,
        account_id: null,
        account_number: null,
        account_status: null,
        service_point_id: null,
        service_point_code: null,
      },
    });
    vi.stubGlobal("fetch", fetchMock);

    renderMeterTabInShell();

    const linkagePanel = (await screen.findByRole("heading", {
      name: "Consumer linkage",
    })).closest("section");
    expect(linkagePanel).not.toBeNull();

    await waitFor(() => {
      expect(
        within(linkagePanel as HTMLElement).getByText(
          /No current subscriber linkage available for this meter\./i,
        ),
      ).toBeInTheDocument();
    });
  });

  it("renders a bounded consumer linkage error without disturbing the existing meter panels", async () => {
    const { fetchMock } = createMockApi({
      consumerLinkageStatus: 503,
      consumerLinkageErrorDetail: "Consumer linkage temporarily unavailable.",
    });
    vi.stubGlobal("fetch", fetchMock);
    const user = userEvent.setup();

    renderMeterTabInShell();

    expect(
      await screen.findByText("Consumer linkage temporarily unavailable."),
    ).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "Operational summary" })).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "Action readiness" })).toBeInTheDocument();
    await openMeterWorkspaceTab(user, "Connectivity");
    expect(screen.getByRole("heading", { name: "Connectivity context" })).toBeInTheDocument();
  });

  it("renders a bounded loading state while consumer linkage is bootstrapping", async () => {
    const { fetchMock } = createMockApi();
    vi.stubGlobal(
      "fetch",
      vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
        const url = input.toString();
        if (url.endsWith("/api/v1/meters/meter-1/consumer-linkage")) {
          await new Promise((resolve) => setTimeout(resolve, 100));
        }
        return fetchMock(input, init);
      }),
    );

    renderMeterTabInShell();

    expect(await screen.findByText("Loading consumer linkage...")).toBeInTheDocument();
    expect(await screen.findAllByText("Amina Al Balushi")).not.toHaveLength(0);
  });

  it("renders a bounded loading state while connectivity context is bootstrapping", async () => {
    const { fetchMock } = createMockApi();
    const user = userEvent.setup();
    vi.stubGlobal(
      "fetch",
      vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
        const url = input.toString();
        if (url.endsWith("/api/v1/meters/meter-1/endpoint-assignments")) {
          await new Promise((resolve) => setTimeout(resolve, 100));
        }
        return fetchMock(input, init);
      }),
    );

    renderMeterTabInShell();
    await openMeterWorkspaceTab(user, "Connectivity");

    expect(await screen.findByText("Loading connectivity context...")).toBeInTheDocument();
    expect(await screen.findByText("TCP Primary")).toBeInTheDocument();
  });

  it("renders the readings tab with latest reading, freshness, and billing interval follow-through", async () => {
    const { fetchMock } = createMockApi();
    vi.stubGlobal("fetch", fetchMock);
    const user = userEvent.setup();

    renderMeterTabInShell();
    await openMeterWorkspaceTab(user, "Readings");

    const readingsPanel = (
      await screen.findByRole("heading", { name: "Readings context" })
    ).closest("section");
    expect(readingsPanel).not.toBeNull();
    expect(within(readingsPanel as HTMLElement).getByText("1552.41 kWh")).toBeInTheDocument();
    expect(
      within(readingsPanel as HTMLElement).getByText(/Fresh within|Recent within|Stale for/i),
    ).toBeInTheDocument();
    expect(
      within(readingsPanel as HTMLElement).getByText(/Total Import Kwh: 1552.41/i),
    ).toBeInTheDocument();
    expect(within(readingsPanel as HTMLElement).getByText("11.50 kWh")).toBeInTheDocument();
    expect(
      within(readingsPanel as HTMLElement).getByText("Raw readings / billing snapshots / interval rows"),
    ).toBeInTheDocument();

    const rawReadingsPanel = screen
      .getByRole("heading", { name: "Recent raw readings" })
      .closest("section");
    expect(rawReadingsPanel).not.toBeNull();
    expect(within(rawReadingsPanel as HTMLElement).getByText("1.0.1.8.0.255")).toBeInTheDocument();
    expect(within(rawReadingsPanel as HTMLElement).getByText(/Quality Validated/i)).toBeInTheDocument();

    const followThroughPanel = screen
      .getByRole("heading", { name: "Billing and interval follow-through" })
      .closest("section");
    expect(followThroughPanel).not.toBeNull();
    expect(
      within(followThroughPanel as HTMLElement).getByText(/Total Import Kwh: 1552.41/i),
    ).toBeInTheDocument();
    expect(within(followThroughPanel as HTMLElement).getByText(/import-wh/i)).toBeInTheDocument();
    expect(
      screen.getByRole("link", { name: "Open readings workspace" }),
    ).toHaveAttribute("href", "/readings?meterId=meter-1");
  });

  it("renders the GIS tab with meter-scoped mapping and network context", async () => {
    const { fetchMock } = createMockApi();
    vi.stubGlobal("fetch", fetchMock);
    const user = userEvent.setup();

    renderMeterTabInShell();
    await openMeterWorkspaceTab(user, "GIS");

    const gisPanel = (
      await screen.findByRole("heading", { name: "GIS context" })
    ).closest("section");
    expect(gisPanel).not.toBeNull();
    expect(
      within(gisPanel as HTMLElement).getAllByText("Coordinates available"),
    ).not.toHaveLength(0);
    expect(within(gisPanel as HTMLElement).getByText("23.588, 58.3829")).toBeInTheDocument();
    expect(within(gisPanel as HTMLElement).getByText("SP-1001")).toBeInTheDocument();
    expect(within(gisPanel as HTMLElement).getByText("transformer-1")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Open GIS Lite surface" })).toHaveAttribute(
      "href",
      "/gis-lite",
    );

    const navigationPanel = screen
      .getByRole("heading", { name: "Network and location navigation" })
      .closest("section");
    expect(navigationPanel).not.toBeNull();
    expect(
      within(navigationPanel as HTMLElement).getByRole("link", {
        name: "Open service point detail",
      }),
    ).toHaveAttribute("href", "/service-points/sp-1");
    expect(
      within(navigationPanel as HTMLElement).getByRole("link", {
        name: "Open transformer detail",
      }),
    ).toHaveAttribute("href", "/transformers-substations/transformer-1");
  });

  it("renders a bounded GIS empty state when no meter-scoped GIS entity is available", async () => {
    const { fetchMock } = createMockApi({ gisLiteEntities: [] });
    vi.stubGlobal("fetch", fetchMock);
    const user = userEvent.setup();

    renderMeterTabInShell();
    await openMeterWorkspaceTab(user, "GIS");

    expect(await screen.findByText("GIS context not available for this meter yet.")).toBeInTheDocument();
    expect(
      screen.getByRole("heading", { name: "Network and location navigation" }),
    ).toBeInTheDocument();
  });

  it("renders a bounded meter GIS error state without disturbing the workspace", async () => {
    const { fetchMock } = createMockApi({
      gisLiteStatus: 503,
      gisLiteDetail: "Meter GIS context unavailable.",
    });
    vi.stubGlobal("fetch", fetchMock);
    const user = userEvent.setup();

    renderMeterTabInShell();
    await openMeterWorkspaceTab(user, "GIS");

    expect(await screen.findByText("Meter GIS context unavailable.")).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "GIS context" })).toBeInTheDocument();
    expect(
      screen.getByRole("heading", { name: "Network and location navigation" }),
    ).toBeInTheDocument();
  });

  it("renders a bounded readings empty state when no meter-scoped readings context is available", async () => {
    const { fetchMock } = createMockApi({
      loadProfileChannels: [],
      readingsItems: [],
      registerSnapshots: [],
      loadProfileIntervals: [],
    });
    vi.stubGlobal("fetch", fetchMock);
    const user = userEvent.setup();

    renderMeterTabInShell();
    await openMeterWorkspaceTab(user, "Readings");

    expect(await screen.findByText("Readings context not available for this meter yet.")).toBeInTheDocument();
    expect(
      screen.getByText("No raw readings are currently recorded for this meter"),
    ).toBeInTheDocument();
    expect(
      screen.getByRole("heading", { name: "Billing and interval follow-through" }),
    ).toBeInTheDocument();
  });

  it("renders a bounded meter readings error state without disturbing the workspace", async () => {
    const { fetchMock } = createMockApi({
      readingsStatus: 503,
      readingsErrorDetail: "Meter readings unavailable.",
    });
    vi.stubGlobal("fetch", fetchMock);
    const user = userEvent.setup();

    renderMeterTabInShell();
    await openMeterWorkspaceTab(user, "Readings");

    expect(await screen.findByText("Unable to load complete meter readings context.")).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "Readings context" })).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "Recent raw readings" })).toBeInTheDocument();
  });

  it("renders the audit tab with meter-scoped audit rows", async () => {
    const { fetchMock } = createMockApi();
    vi.stubGlobal("fetch", fetchMock);
    const user = userEvent.setup();

    renderMeterTabInShell();
    await openMeterWorkspaceTab(user, "Audit");

    const auditPanel = (
      await screen.findByRole("heading", { name: "Meter audit feed" })
    ).closest("section");
    expect(auditPanel).not.toBeNull();

    await waitFor(() => {
      expect(
        within(auditPanel as HTMLElement).getByText("Meter communication profile updated."),
      ).toBeInTheDocument();
      expect(within(auditPanel as HTMLElement).getByText("Ops User")).toBeInTheDocument();
      expect(within(auditPanel as HTMLElement).getAllByText("Success")).not.toHaveLength(0);
    });

    expect(screen.getByRole("link", { name: "Open audit center" })).toHaveAttribute(
      "href",
      "/audit-center",
    );
  });

  it("renders the consumer commercial tab with linked subscriber, account, and service context", async () => {
    const { fetchMock } = createMockApi();
    vi.stubGlobal("fetch", fetchMock);
    const user = userEvent.setup();

    renderMeterTabInShell();
    await openMeterWorkspaceTab(user, "Consumer / Commercial");

    const commercialPanel = (
      await screen.findByRole("heading", { name: "Consumer / commercial context" })
    ).closest("section");
    expect(commercialPanel).not.toBeNull();

    await waitFor(() => {
      expect(
        within(commercialPanel as HTMLElement).getByText("Amina Al Balushi"),
      ).toBeInTheDocument();
      expect(within(commercialPanel as HTMLElement).getByText("ACC-1001")).toBeInTheDocument();
      expect(within(commercialPanel as HTMLElement).getByText("SP-1001")).toBeInTheDocument();
      expect(
        within(commercialPanel as HTMLElement).getAllByText(/Source Meter Account Assignment/i),
      ).not.toHaveLength(0);
    });

    const navigationPanel = screen
      .getByRole("heading", { name: "Commercial navigation" })
      .closest("section");
    expect(navigationPanel).not.toBeNull();

    expect(
      within(navigationPanel as HTMLElement).getByRole("link", { name: "Open subscriber detail" }),
    ).toHaveAttribute(
      "href",
      "/subscribers/consumer-1",
    );
    expect(
      within(navigationPanel as HTMLElement).getByRole("link", { name: "Open account detail" }),
    ).toHaveAttribute(
      "href",
      "/accounts/account-1",
    );
    expect(
      within(navigationPanel as HTMLElement).getByRole("link", { name: "Open service point detail" }),
    ).toHaveAttribute("href", "/service-points/sp-1");
  });

  it("renders a bounded commercial empty state when no subscriber or account is linked", async () => {
    const { fetchMock } = createMockApi({
      consumerLinkageResponse: {
        meter_id: "meter-1",
        linkage_status: "unlinked",
        linkage_source: null,
        consumer_id: null,
        consumer_display_name: null,
        consumer_type: null,
        consumer_external_ref: null,
        account_id: null,
        account_number: null,
        account_status: null,
        service_point_id: null,
        service_point_code: null,
      },
    });
    vi.stubGlobal("fetch", fetchMock);
    const user = userEvent.setup();

    renderMeterTabInShell();
    await openMeterWorkspaceTab(user, "Consumer / Commercial");

    expect(
      await screen.findByText("No linked subscriber or account is currently attached to this meter"),
    ).toBeInTheDocument();
    expect(screen.getByText("Commercial Context Empty")).toBeInTheDocument();
  });

  it("renders a bounded commercial error state when consumer linkage fails", async () => {
    const { fetchMock } = createMockApi({
      consumerLinkageStatus: 503,
      consumerLinkageErrorDetail: "Consumer linkage temporarily unavailable.",
    });
    vi.stubGlobal("fetch", fetchMock);
    const user = userEvent.setup();

    renderMeterTabInShell();
    await openMeterWorkspaceTab(user, "Consumer / Commercial");

    expect(
      await screen.findByText("Consumer linkage temporarily unavailable."),
    ).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "Commercial navigation" })).toBeInTheDocument();
  });

  it("renders the events tab with meter-scoped event history", async () => {
    const { fetchMock } = createMockApi();
    vi.stubGlobal("fetch", fetchMock);
    const user = userEvent.setup();

    renderMeterTabInShell();
    await openMeterWorkspaceTab(user, "Events");

    const eventsPanel = (
      await screen.findByRole("heading", { name: "Meter event feed" })
    ).closest("section");
    expect(eventsPanel).not.toBeNull();

    await waitFor(() => {
      expect(within(eventsPanel as HTMLElement).getByText("Tamper Open")).toBeInTheDocument();
      expect(within(eventsPanel as HTMLElement).getByText("Power Restore")).toBeInTheDocument();
      expect(within(eventsPanel as HTMLElement).getAllByText("Critical")).not.toHaveLength(0);
      expect(within(eventsPanel as HTMLElement).getAllByText("Open")).not.toHaveLength(0);
      expect(
        within(eventsPanel as HTMLElement).getByText(/Phase A • Source tamper_switch/i),
      ).toBeInTheDocument();
    });

    expect(screen.getByRole("link", { name: "Open jobs / events / alerts" })).toHaveAttribute(
      "href",
      "/jobs-events-alerts",
    );
    expect(
      within(eventsPanel as HTMLElement).getAllByRole("link", { name: "Open activity detail" })[0],
    ).toHaveAttribute("href", "/jobs-events-alerts/activity/event/event-meter-1");
  });

  it("renders a bounded empty state when no meter-scoped events are available", async () => {
    const { fetchMock } = createMockApi({
      meterEvents: [],
    });
    vi.stubGlobal("fetch", fetchMock);
    const user = userEvent.setup();

    renderMeterTabInShell();
    await openMeterWorkspaceTab(user, "Events");

    expect(
      await screen.findByText("No ingested events are currently tied to this meter"),
    ).toBeInTheDocument();
    expect(screen.getByText("Meter Events Empty")).toBeInTheDocument();
  });

  it("renders a bounded meter events error state when event history fails", async () => {
    const { fetchMock } = createMockApi({
      meterEventsStatus: 503,
      meterEventsDetail: "Meter events unavailable.",
    });
    vi.stubGlobal("fetch", fetchMock);
    const user = userEvent.setup();

    renderMeterTabInShell();
    await openMeterWorkspaceTab(user, "Events");

    expect(await screen.findByText("Meter events unavailable.")).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "Meter events visibility" })).toBeInTheDocument();
  });

  it("renders a bounded empty state when no meter-scoped audit rows are available", async () => {
    const { fetchMock } = createMockApi({
      auditLogs: [],
    });
    vi.stubGlobal("fetch", fetchMock);
    const user = userEvent.setup();

    renderMeterTabInShell();
    await openMeterWorkspaceTab(user, "Audit");

    expect(
      await screen.findByText("No audit records are currently tied to this meter"),
    ).toBeInTheDocument();
    expect(
      screen.getByText(
        "Meter-scoped traceability will appear here when persisted audit rows reference this meter entity directly.",
      ),
    ).toBeInTheDocument();
  });

  it("renders the action readiness panel for the existing execute-now flows", async () => {
    const { fetchMock } = createMockApi();
    vi.stubGlobal("fetch", fetchMock);

    renderMeterTabInShell();

    const readinessHeading = await screen.findByRole("heading", {
      name: "Action readiness",
    });
    const readinessPanel = readinessHeading
      .closest("section");
    expect(readinessPanel).not.toBeNull();

    await waitFor(() => {
      expect(
        within(readinessPanel as HTMLElement).getByText("Profile capture execute-now"),
      ).toBeInTheDocument();
      expect(
        within(readinessPanel as HTMLElement).getByText("Relay disconnect execute-now"),
      ).toBeInTheDocument();
      expect(
        within(readinessPanel as HTMLElement).getByText("Relay reconnect execute-now"),
      ).toBeInTheDocument();
      expect(
        within(readinessPanel as HTMLElement).getByText("On-demand read execute-now"),
      ).toBeInTheDocument();
    });

    expect(
      within(readinessPanel as HTMLElement).getAllByText("ready"),
    ).toHaveLength(4);
    expect(
      within(readinessPanel as HTMLElement).getAllByText(
        "All minimum prerequisites available.",
      ),
    ).toHaveLength(4);
  });

  it("renders a bounded loading state while action readiness is bootstrapping", async () => {
    const { fetchMock } = createMockApi();
    vi.stubGlobal(
      "fetch",
      vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
        const url = input.toString();
        if (url.endsWith("/api/v1/command-templates")) {
          await new Promise((resolve) => setTimeout(resolve, 100));
        }
        return fetchMock(input, init);
      }),
    );

    renderMeterTabInShell();

    expect(await screen.findByText("Loading action readiness...")).toBeInTheDocument();
    expect(await screen.findByText("Profile capture execute-now")).toBeInTheDocument();
  });

  it("renders bounded summary fallbacks when optional meter context is unavailable", async () => {
    const { fetchMock } = createMockApi({
      meterResponse: {
        id: "meter-1",
        serial_number: "SN-1001",
        utility_meter_number: null,
        manufacturer_code: "GENERIC",
        meter_model_code: "GM-1",
        meter_profile_code: null,
        communication_profile_code: null,
        current_status: "commissioned",
        transformer_id: null,
        service_point_id: null,
        last_seen_at: null,
      },
      endpointAssignments: [],
      protocolProfiles: [],
    });
    vi.stubGlobal("fetch", fetchMock);

    renderMeterTabInShell();

    expect(await screen.findAllByText("Not available")).not.toHaveLength(0);
    expect(screen.getByText("No active endpoint")).toBeInTheDocument();
    expect(screen.getByText("No active protocol profile")).toBeInTheDocument();
  });

  it("renders bounded connectivity fallbacks when endpoint and protocol context is unavailable", async () => {
    const { fetchMock } = createMockApi({
      meterResponse: {
        id: "meter-1",
        serial_number: "SN-1001",
        utility_meter_number: "UMN-1001",
        manufacturer_code: "GENERIC",
        meter_model_code: "GM-1",
        meter_profile_code: "default",
        communication_profile_code: null,
        current_status: "commissioned",
        transformer_id: null,
        service_point_id: null,
        last_seen_at: null,
      },
      endpointAssignments: [],
      protocolProfiles: [],
      meterSessions: [],
    });
    vi.stubGlobal("fetch", fetchMock);
    const user = userEvent.setup();

    renderMeterTabInShell();
    await openMeterWorkspaceTab(user, "Connectivity");

    await waitFor(() => {
      expect(
        screen.getByText("Connectivity context not available."),
      ).toBeInTheDocument();
    });
    expect(
      screen.getByRole("heading", { name: "Recent session history" }),
    ).toBeInTheDocument();
    expect(
      screen.getByText("No connectivity sessions are currently recorded for this meter"),
    ).toBeInTheDocument();
  });

  it("renders bounded action readiness states when prerequisites are missing", async () => {
    const { fetchMock } = createMockApi({
      endpointAssignments: [],
      protocolProfiles: [],
      loadProfileChannels: [],
    });
    vi.stubGlobal("fetch", fetchMock);

    renderMeterTabInShell();

    const readinessHeading = await screen.findByRole("heading", {
      name: "Action readiness",
    });
    const readinessPanel = readinessHeading
      .closest("section");
    expect(readinessPanel).not.toBeNull();

    await waitFor(() => {
      expect(
        within(readinessPanel as HTMLElement).getAllByText("partially ready"),
      ).toHaveLength(4);
    });

    expect(
      within(readinessPanel as HTMLElement).getByText(
        "Missing: active endpoint assignment, active protocol profile, active load-profile channel.",
      ),
    ).toBeInTheDocument();
    expect(
      within(readinessPanel as HTMLElement).getAllByText(
        "Missing: active endpoint assignment, active protocol profile.",
      ),
    ).toHaveLength(3);
  });

  it("renders a bounded summary unavailable state when meter context fails to load", async () => {
    const { fetchMock } = createMockApi({
      meterStatus: 404,
      meterErrorDetail: "Meter not found.",
    });
    vi.stubGlobal("fetch", fetchMock);

    renderMeterTabInShell();

    expect(await screen.findByText("Meter not found.")).toBeInTheDocument();
    expect(screen.getAllByText("Meter summary not available.")).not.toHaveLength(0);
  });

  it("renders a bounded action readiness unavailable state when meter context fails to load", async () => {
    const { fetchMock } = createMockApi({
      meterStatus: 404,
      meterErrorDetail: "Meter not found.",
    });
    vi.stubGlobal("fetch", fetchMock);

    renderMeterTabInShell();

    expect(await screen.findByText("Meter not found.")).toBeInTheDocument();
    expect(await screen.findByText("Action readiness not available.")).toBeInTheDocument();
  });

  it("renders a bounded connectivity error state while preserving partial context", async () => {
    const { fetchMock } = createMockApi({
      endpointAssignmentsStatus: 503,
      endpointAssignmentsErrorDetail: "Endpoint assignments unavailable.",
    });
    vi.stubGlobal("fetch", fetchMock);
    const user = userEvent.setup();

    renderMeterTabInShell();

    expect(
      await screen.findByText(
        "Unable to load complete meter detail context.",
      ),
    ).toBeInTheDocument();
    await openMeterWorkspaceTab(user, "Connectivity");

    const connectivityPanel = screen
      .getByRole("heading", { name: "Connectivity context" })
      .closest("section");
    expect(connectivityPanel).not.toBeNull();

    expect(
      within(connectivityPanel as HTMLElement).getByText("dlms-profile"),
    ).toBeInTheDocument();
    expect(
      within(connectivityPanel as HTMLElement).queryByText("Connectivity context not available."),
    ).not.toBeInTheDocument();
    expect(screen.getAllByText("SN-1001")).not.toHaveLength(0);
  });

  it("renders a bounded meter connectivity session error state without disturbing the workspace", async () => {
    const { fetchMock } = createMockApi({
      meterSessionsStatus: 503,
      meterSessionsDetail: "Connectivity session history unavailable.",
    });
    vi.stubGlobal("fetch", fetchMock);
    const user = userEvent.setup();

    renderMeterTabInShell();
    await openMeterWorkspaceTab(user, "Connectivity");

    expect(
      await screen.findByText("Connectivity session history unavailable."),
    ).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "Connectivity context" })).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "Recent session history" })).toBeInTheDocument();
  });

  it("renders a bounded meter audit error state without disturbing the workspace", async () => {
    const { fetchMock } = createMockApi({
      auditLogsStatus: 503,
      auditLogsDetail: "Meter audit history unavailable.",
    });
    vi.stubGlobal("fetch", fetchMock);
    const user = userEvent.setup();

    renderMeterTabInShell();
    await openMeterWorkspaceTab(user, "Audit");

    expect(await screen.findByText("Meter audit history unavailable.")).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "Meter audit traceability" })).toBeInTheDocument();
  });

  it("loads bounded command detail when a recent command is selected", async () => {
    const { fetchMock } = createMockApi();
    vi.stubGlobal("fetch", fetchMock);
    const user = userEvent.setup();

    renderMeterTabInShell();
    await openMeterWorkspaceTab(user, "Commands");

    const relayRow = await screen.findByRole("button", {
      name: /relay-disconnect-template/i,
    });
    await user.click(relayRow);

    const detailPanel = screen
      .getByRole("heading", { name: "Command detail" })
      .closest("section");
    expect(detailPanel).not.toBeNull();
    await waitFor(() => {
      expect(within(detailPanel as HTMLElement).getByText("runtime-relay-1")).toBeInTheDocument();
    });
  });

  it("loads bounded on-demand-read command detail when a recent command is selected", async () => {
    const { fetchMock } = createMockApi();
    vi.stubGlobal("fetch", fetchMock);
    const user = userEvent.setup();

    renderMeterTabInShell();
    await openMeterWorkspaceTab(user, "Commands");

    const onDemandRow = await screen.findByRole("button", {
      name: /on-demand-read-template/i,
    });
    await user.click(onDemandRow);

    const detailPanel = screen
      .getByRole("heading", { name: "Command detail" })
      .closest("section");
    expect(detailPanel).not.toBeNull();
    await waitFor(() => {
      expect(
        within(detailPanel as HTMLElement).getByText("runtime-on-demand-1"),
      ).toBeInTheDocument();
      expect(
        within(detailPanel as HTMLElement).getByText(
          "read_billing_snapshot billing (succeeded)",
        ),
      ).toBeInTheDocument();
    });
  });

  it("renders a bounded command history empty state when no recent meter commands are available", async () => {
    const { fetchMock } = createMockApi({ recentCommandsItems: [] });
    vi.stubGlobal("fetch", fetchMock);
    const user = userEvent.setup();

    renderMeterTabInShell();
    await openMeterWorkspaceTab(user, "Commands");

    expect(await screen.findByText("No supported commands recorded for this meter yet.")).toBeInTheDocument();
    expect(
      screen.getByText("Select a recent command to load bounded command detail."),
    ).toBeInTheDocument();
  });

  it("renders a bounded meter commands history error state without disturbing execute-now actions", async () => {
    const { fetchMock } = createMockApi({
      recentCommandsStatus: 503,
      recentCommandsDetail: "Recent meter commands unavailable.",
    });
    vi.stubGlobal("fetch", fetchMock);
    const user = userEvent.setup();

    renderMeterTabInShell();
    await openMeterWorkspaceTab(user, "Commands");

    expect(await screen.findAllByText("Recent meter commands unavailable.")).not.toHaveLength(0);
    expect(screen.getByRole("heading", { name: "Command operations center" })).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "Execute now" })).toBeInTheDocument();
  });

  it("triggers the existing profile capture execute-now path and refreshes the selected detail", async () => {
    const { fetchMock, requests } = createMockApi();
    vi.stubGlobal("fetch", fetchMock);
    const user = userEvent.setup();

    renderMeterTabInShell();
    await openMeterWorkspaceTab(user, "Commands");
    await screen.findByText("Recent commands");

    const profileForm = screen
      .getByRole("heading", { name: "Profile capture" })
      .closest("form");
    expect(profileForm).not.toBeNull();

    await waitFor(() => {
      expect(
        within(profileForm as HTMLElement).getByRole("button", {
          name: /execute profile capture now/i,
        }),
      ).toBeEnabled();
    });

    await user.click(
      within(profileForm as HTMLElement).getByRole("button", {
        name: /execute profile capture now/i,
      }),
    );

    expect(
      await screen.findByText("Profile capture execute-now command requested."),
    ).toBeInTheDocument();

    const request = requests.find((entry) =>
      entry.url.endsWith("/api/v1/meters/meter-1/commands/profile-capture/execute-now"),
    );
    expect(request?.body?.command_template_id).toBe("template-profile-1");
    expect(request?.body?.endpoint_assignment_id).toBe("assignment-1");
    expect(request?.body?.protocol_association_profile_id).toBe("protocol-profile-1");
    expect(request?.body?.channel_ids).toEqual(["channel-1"]);

    const detailPanel = screen
      .getByRole("heading", { name: "Command detail" })
      .closest("section");
    await waitFor(() => {
      expect(
        within(detailPanel as HTMLElement).getByText("runtime-profile-action"),
      ).toBeInTheDocument();
    });
  });

  it("triggers the existing relay disconnect execute-now path", async () => {
    const { fetchMock, requests } = createMockApi();
    vi.stubGlobal("fetch", fetchMock);
    const user = userEvent.setup();

    renderMeterTabInShell();
    await openMeterWorkspaceTab(user, "Commands");
    await screen.findByText("Recent commands");

    const relayForm = screen
      .getByRole("heading", { name: "Relay control" })
      .closest("form");
    expect(relayForm).not.toBeNull();

    await waitFor(() => {
      expect(
        within(relayForm as HTMLElement).getByRole("button", {
          name: /execute relay disconnect now/i,
        }),
      ).toBeEnabled();
    });

    await user.click(
      within(relayForm as HTMLElement).getByRole("button", {
        name: /execute relay disconnect now/i,
      }),
    );

    const request = requests.find((entry) =>
      entry.url.endsWith("/api/v1/meters/meter-1/commands/relay-control/execute-now"),
    );
    expect(request?.body?.relay_operation).toBe("disconnect");
    expect(request?.body?.command_template_id).toBe("template-relay-disconnect-1");
  });

  it("triggers the existing relay reconnect execute-now path", async () => {
    const { fetchMock, requests } = createMockApi();
    vi.stubGlobal("fetch", fetchMock);
    const user = userEvent.setup();

    renderMeterTabInShell();
    await openMeterWorkspaceTab(user, "Commands");
    await screen.findByText("Recent commands");

    const relayForm = screen
      .getByRole("heading", { name: "Relay control" })
      .closest("form");
    expect(relayForm).not.toBeNull();

    await user.selectOptions(
      within(relayForm as HTMLElement).getByLabelText("Operation"),
      "reconnect",
    );

    await waitFor(() => {
      expect(
        within(relayForm as HTMLElement).getByRole("button", {
          name: /execute relay reconnect now/i,
        }),
      ).toBeEnabled();
    });

    await user.click(
      within(relayForm as HTMLElement).getByRole("button", {
        name: /execute relay reconnect now/i,
      }),
    );

    const relayRequests = requests.filter((entry) =>
      entry.url.endsWith("/api/v1/meters/meter-1/commands/relay-control/execute-now"),
    );
    const reconnectRequest = relayRequests.at(-1);
    expect(reconnectRequest?.body?.relay_operation).toBe("reconnect");
    expect(reconnectRequest?.body?.command_template_id).toBe(
      "template-relay-reconnect-1",
    );
  });

  it("triggers the existing on-demand-read execute-now path and refreshes the selected detail", async () => {
    const { fetchMock, requests } = createMockApi();
    vi.stubGlobal("fetch", fetchMock);
    const user = userEvent.setup();

    renderMeterTabInShell();
    await openMeterWorkspaceTab(user, "Commands");
    await screen.findByText("Recent commands");

    const onDemandForm = screen
      .getByRole("heading", { name: "On-demand read" })
      .closest("form");
    expect(onDemandForm).not.toBeNull();

    await waitFor(() => {
      expect(
        within(onDemandForm as HTMLElement).getByRole("button", {
          name: /execute on-demand read now/i,
        }),
      ).toBeEnabled();
    });

    await user.click(
      within(onDemandForm as HTMLElement).getByRole("button", {
        name: /execute on-demand read now/i,
      }),
    );

    expect(
      await screen.findByText("On-demand read execute-now command requested."),
    ).toBeInTheDocument();

    const request = requests.find((entry) =>
      entry.url.endsWith("/api/v1/meters/meter-1/commands/on-demand-read/execute-now"),
    );
    expect(request?.body?.command_template_id).toBe("template-on-demand-read-1");
    expect(request?.body?.endpoint_assignment_id).toBe("assignment-1");
    expect(request?.body?.protocol_association_profile_id).toBe("protocol-profile-1");
    expect(request?.body?.on_demand_read_operation).toBe("read_billing_snapshot");

    const detailPanel = screen
      .getByRole("heading", { name: "Command detail" })
      .closest("section");
    await waitFor(() => {
      expect(
        within(detailPanel as HTMLElement).getByText("runtime-on-demand-action"),
      ).toBeInTheDocument();
    });
  });
});
