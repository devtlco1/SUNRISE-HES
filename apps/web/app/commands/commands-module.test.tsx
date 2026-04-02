import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { OperationalShell } from "../operational-shell";
import { CommandsModule } from "./commands-module";

function includesText(text: string) {
  return (_content: string, element: Element | null) => element?.textContent?.includes(text) ?? false;
}

function jsonResponse(payload: unknown, status = 200) {
  return new Response(JSON.stringify(payload), {
    status,
    headers: { "Content-Type": "application/json" },
  });
}

function createCommandRecord({
  commandId,
  family,
  category,
  status,
  approvalStatus = "not_required",
  meterId,
  templateCode,
  latestAttemptId,
  latestAttemptStatus,
  runtimeRecordId,
  familySpecificOutcomeSummary,
  createdAt,
  updatedAt,
  approvalNotes = null,
}: {
  commandId: string;
  family: "profile_capture" | "relay_control" | "on_demand_read";
  category: string;
  status: string;
  approvalStatus?: string;
  meterId: string;
  templateCode: string;
  latestAttemptId: string | null;
  latestAttemptStatus: string | null;
  runtimeRecordId: string | null;
  familySpecificOutcomeSummary: Record<string, string | null>;
  createdAt: string;
  updatedAt: string;
  approvalNotes?: string | null;
}) {
  const recent = {
    command_id: commandId,
    command_family: family,
    command_category: category,
    command_status: status,
    approval_status: approvalStatus,
    approval_reviewed_at: approvalStatus === "not_required" ? null : updatedAt,
    approval_notes: approvalNotes,
    meter_id: meterId,
    command_template_code: templateCode,
    latest_command_execution_attempt_id: latestAttemptId,
    latest_command_execution_attempt_status: latestAttemptStatus,
    runtime_execution_record_id: runtimeRecordId,
    family_specific_outcome_summary: familySpecificOutcomeSummary,
    orchestration_artifact_present: runtimeRecordId !== null,
    terminalization_artifact_present: runtimeRecordId !== null,
    execute_now_artifact_present: runtimeRecordId !== null,
    created_at: createdAt,
    latest_updated_at: updatedAt,
  };

  const detail = {
    ...recent,
    approval_reviewed_by_user_id:
      approvalStatus === "approved" || approvalStatus === "rejected" ? "user-1" : null,
    approval_notes: approvalNotes,
    projection_record: {
      command_family: family,
      command_status: status,
      approval_status: approvalStatus,
      runtime_execution_record_id: runtimeRecordId,
    },
  };

  return { recent, detail };
}

function createMockApi() {
  const meters = [
    {
      id: "meter-1",
      serial_number: "SN-1001",
      utility_meter_number: "UMN-1001",
      communication_profile_code: "dlms-primary",
      meter_profile_code: "residential-default",
      current_status: "commissioned",
      last_seen_at: "2026-03-30T10:10:00.000Z",
    },
    {
      id: "meter-2",
      serial_number: "SN-1002",
      utility_meter_number: "UMN-1002",
      communication_profile_code: "dlms-primary",
      meter_profile_code: "commercial-default",
      current_status: "registered",
      last_seen_at: "2026-03-30T10:05:00.000Z",
    },
    {
      id: "meter-3",
      serial_number: "SN-1003",
      utility_meter_number: null,
      communication_profile_code: null,
      meter_profile_code: "industrial-default",
      current_status: "commissioned",
      last_seen_at: null,
    },
  ];

  const templates: Array<{
    id: string;
    code: string;
    name: string;
    category: string;
    description: string | null;
    payload_schema: Record<string, unknown> | null;
    target_scope: string;
    timeout_seconds: number;
    max_retries: number;
    is_active: boolean;
  }> = [
    {
      id: "template-relay-disconnect",
      code: "relay-disconnect-template",
      name: "Relay disconnect template",
      category: "remote_disconnect",
      description: "Default disconnect notes.",
      payload_schema: {
        default_bulk_notes: "Disconnect after the current approvals review.",
      },
      target_scope: "meter",
      timeout_seconds: 120,
      max_retries: 0,
      is_active: true,
    },
    {
      id: "template-relay-reconnect",
      code: "relay-reconnect-template",
      name: "Relay reconnect template",
      category: "remote_reconnect",
      description: "Default reconnect notes.",
      payload_schema: {
        default_bulk_notes: "Reconnect after the service verification completes.",
      },
      target_scope: "meter",
      timeout_seconds: 120,
      max_retries: 0,
      is_active: true,
    },
    {
      id: "template-on-demand-read",
      code: "on-demand-read-template",
      name: "On-demand read template",
      category: "on_demand_read",
      description: "Default billing snapshot notes.",
      payload_schema: {
        default_bulk_notes: "Capture a billing snapshot for bounded recovery follow-up.",
      },
      target_scope: "meter",
      timeout_seconds: 120,
      max_retries: 0,
      is_active: true,
    },
    {
      id: "template-profile-capture",
      code: "profile-capture-template",
      name: "Profile capture template",
      category: "profile_capture",
      description: null,
      payload_schema: null,
      target_scope: "meter",
      timeout_seconds: 120,
      max_retries: 0,
      is_active: true,
    },
  ];

  const commandRecords = new Map<string, ReturnType<typeof createCommandRecord>>([
    [
      "cmd-profile-1",
      createCommandRecord({
        commandId: "cmd-profile-1",
        family: "profile_capture",
        category: "profile_capture",
        status: "succeeded",
        meterId: "meter-1",
        templateCode: "profile-capture-template",
        latestAttemptId: "attempt-profile-1",
        latestAttemptStatus: "succeeded",
        runtimeRecordId: "runtime-profile-1",
        familySpecificOutcomeSummary: { terminal_status_category: "acknowledged" },
        createdAt: "2026-03-30T10:00:00.000Z",
        updatedAt: "2026-03-30T10:05:00.000Z",
      }),
    ],
    [
      "cmd-relay-1",
      createCommandRecord({
        commandId: "cmd-relay-1",
        family: "relay_control",
        category: "remote_disconnect",
        status: "succeeded",
        meterId: "meter-2",
        templateCode: "relay-disconnect-template",
        latestAttemptId: "attempt-relay-1",
        latestAttemptStatus: "succeeded",
        runtimeRecordId: "runtime-relay-1",
        familySpecificOutcomeSummary: {
          relay_control_operation: "disconnect",
          relay_control_execution_outcome: "succeeded",
        },
        createdAt: "2026-03-30T09:00:00.000Z",
        updatedAt: "2026-03-30T09:03:00.000Z",
      }),
    ],
    [
      "cmd-on-demand-1",
      createCommandRecord({
        commandId: "cmd-on-demand-1",
        family: "on_demand_read",
        category: "on_demand_read",
        status: "succeeded",
        meterId: "meter-3",
        templateCode: "on-demand-read-template",
        latestAttemptId: "attempt-on-demand-1",
        latestAttemptStatus: "succeeded",
        runtimeRecordId: "runtime-on-demand-1",
        familySpecificOutcomeSummary: {
          on_demand_read_operation: "read_billing_snapshot",
          snapshot_type: "billing",
          on_demand_read_execution_outcome: "succeeded",
        },
        createdAt: "2026-03-30T08:00:00.000Z",
        updatedAt: "2026-03-30T08:02:00.000Z",
      }),
    ],
    [
      "cmd-approved-1",
      createCommandRecord({
        commandId: "cmd-approved-1",
        family: "relay_control",
        category: "remote_disconnect",
        status: "pending",
        approvalStatus: "approved",
        meterId: "meter-1",
        templateCode: "relay-disconnect-template",
        latestAttemptId: null,
        latestAttemptStatus: null,
        runtimeRecordId: null,
        familySpecificOutcomeSummary: {
          relay_control_operation: "disconnect",
          relay_control_execution_outcome: "pending",
        },
        createdAt: "2026-03-30T07:30:00.000Z",
        updatedAt: "2026-03-30T07:45:00.000Z",
        approvalNotes: "Approved by the duty operator.",
      }),
    ],
    [
      "cmd-rejected-1",
      createCommandRecord({
        commandId: "cmd-rejected-1",
        family: "on_demand_read",
        category: "on_demand_read",
        status: "cancelled",
        approvalStatus: "rejected",
        meterId: "meter-2",
        templateCode: "on-demand-read-template",
        latestAttemptId: null,
        latestAttemptStatus: null,
        runtimeRecordId: null,
        familySpecificOutcomeSummary: {
          on_demand_read_operation: "read_billing_snapshot",
          snapshot_type: "billing",
          on_demand_read_execution_outcome: "pending",
        },
        createdAt: "2026-03-30T07:00:00.000Z",
        updatedAt: "2026-03-30T07:10:00.000Z",
        approvalNotes: "Rejected while awaiting meter-side confirmation.",
      }),
    ],
  ]);

  let bulkCounter = 0;

  const listRecentItems = () => Array.from(commandRecords.values()).map((item) => item.recent);

  const fetchMock = vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
    const url = input.toString();

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

    if (url.includes("/api/v1/meters?")) {
      return jsonResponse({ total: meters.length, items: meters });
    }

    if (url.endsWith("/api/v1/command-templates")) {
      if (init?.method === "POST") {
        const payload = JSON.parse(String(init.body ?? "{}")) as {
          code: string;
          name: string;
          category: string;
          description?: string | null;
          payload_schema?: Record<string, unknown> | null;
        };
        const createdTemplate = {
          id: `template-saved-${templates.length + 1}`,
          code: payload.code,
          name: payload.name,
          category: payload.category,
          description: payload.description ?? null,
          payload_schema: payload.payload_schema ?? null,
          target_scope: "meter",
          timeout_seconds: 120,
          max_retries: 0,
          is_active: true,
        };
        templates.push(createdTemplate);
        return jsonResponse(createdTemplate, 201);
      }
      return jsonResponse({ total: templates.length, items: templates });
    }

    if (url.includes("/api/v1/commands/recent")) {
      const parsedUrl = new URL(url);
      const family = parsedUrl.searchParams.get("family");
      const approval = parsedUrl.searchParams.get("approval");
      const items = listRecentItems().filter((item) => {
        const matchesFamily = family === null ? true : item.command_family === family;
        const matchesApproval = approval === null ? true : item.approval_status === approval;
        return matchesFamily && matchesApproval;
      });
      return jsonResponse({
        total: items.length,
        limit: Number(parsedUrl.searchParams.get("limit") ?? "20"),
        family_filter: family,
        approval_filter: approval,
        items,
      });
    }

    if (url.includes("/api/v1/commands/approvals/pending")) {
      const parsedUrl = new URL(url);
      const family = parsedUrl.searchParams.get("family");
      const items = listRecentItems().filter((item) => {
        const matchesFamily = family === null ? true : item.command_family === family;
        return item.approval_status === "submitted_for_approval" && matchesFamily;
      });
      return jsonResponse({
        total: items.length,
        limit: 20,
        family_filter: family,
        items,
      });
    }

    if (url.endsWith("/api/v1/commands/bulk-requests") && init?.method === "POST") {
      const payload = JSON.parse(String(init.body ?? "{}")) as {
        family: "relay_control" | "on_demand_read";
        meter_ids: string[];
        command_template_id: string;
        relay_operation?: "disconnect" | "reconnect";
      };
      const template = templates.find((item) => item.id === payload.command_template_id) ?? null;

      const items = payload.meter_ids.map((meterId) => {
        bulkCounter += 1;
        const commandId = `bulk-${payload.family}-${bulkCounter}`;
        const createdAt = `2026-03-30T11:0${bulkCounter}:00.000Z`;
        const templateCode = template?.code ?? "bulk-template";
        const record = createCommandRecord({
          commandId,
          family: payload.family,
          category:
            payload.family === "relay_control"
              ? payload.relay_operation === "reconnect"
                ? "remote_reconnect"
                : "remote_disconnect"
              : "on_demand_read",
          status: "pending",
          approvalStatus: "submitted_for_approval",
          meterId,
          templateCode,
          latestAttemptId: null,
          latestAttemptStatus: null,
          runtimeRecordId: null,
          familySpecificOutcomeSummary:
            payload.family === "relay_control"
              ? {
                  relay_control_operation: payload.relay_operation ?? "disconnect",
                  relay_control_execution_outcome: "pending",
                }
              : {
                  on_demand_read_operation: "read_billing_snapshot",
                  snapshot_type: "billing",
                  on_demand_read_execution_outcome: "pending",
                },
          createdAt,
          updatedAt: createdAt,
        });
        commandRecords.set(commandId, record);
        return {
          meter_id: meterId,
          command_id: commandId,
          command_template_code: templateCode,
          command_family: payload.family,
          command_status: "pending",
          approval_status: "submitted_for_approval",
          submission_status: "submitted_for_approval",
          detail: "Command request created and routed into the bounded approvals queue.",
        };
      });

      return jsonResponse({
        submitted_total: items.length,
        failed_total: 0,
        items,
      }, 201);
    }

    const approvalActionMatch = url.match(/\/api\/v1\/commands\/([^/]+)\/approvals\/(approve|reject)$/);
    if (approvalActionMatch && init?.method === "POST") {
      const [, commandId, action] = approvalActionMatch;
      const existing = commandRecords.get(commandId);
      if (!existing) {
        throw new Error(`Unknown command for approval action: ${commandId}`);
      }
      const payload = JSON.parse(String(init.body ?? "{}")) as { approval_notes?: string };
      const reviewedAt = "2026-03-30T12:00:00.000Z";
      const approvalStatus = action === "approve" ? "approved" : "rejected";
      const commandStatus = action === "approve" ? existing.recent.command_status : "cancelled";
      const updatedRecord = createCommandRecord({
        commandId,
        family: existing.recent.command_family,
        category: existing.recent.command_category,
        status: commandStatus,
        approvalStatus,
        meterId: existing.recent.meter_id,
        templateCode: existing.recent.command_template_code,
        latestAttemptId: existing.recent.latest_command_execution_attempt_id,
        latestAttemptStatus: existing.recent.latest_command_execution_attempt_status,
        runtimeRecordId: existing.recent.runtime_execution_record_id,
        familySpecificOutcomeSummary: existing.recent.family_specific_outcome_summary,
        createdAt: existing.recent.created_at,
        updatedAt: reviewedAt,
        approvalNotes: payload.approval_notes ?? null,
      });
      commandRecords.set(commandId, updatedRecord);
      return jsonResponse({
        id: commandId,
        meter_id: existing.recent.meter_id,
        command_template_id: "template-id",
        command_template_code: existing.recent.command_template_code,
        command_template_name: existing.recent.command_template_code,
        current_status: commandStatus,
        approval_status: approvalStatus,
        approval_reviewed_at: reviewedAt,
        approval_reviewed_by_user_id: "user-1",
        approval_notes: payload.approval_notes ?? null,
        priority: "high",
        requested_by_user_id: "user-1",
        requested_at: existing.recent.created_at,
        scheduled_at: null,
        queued_at: null,
        started_at: null,
        completed_at: null,
        timeout_at: null,
        correlation_id: null,
        idempotency_key: null,
        request_payload: null,
        normalized_payload: null,
        result_summary: null,
        latest_error_code: null,
        latest_error_message: null,
        max_retries: 0,
        retry_count: 0,
        endpoint_assignment_id: null,
        protocol_association_profile_id: null,
        notes: null,
      });
    }

    const detailMatch = url.match(/\/api\/v1\/commands\/([^/]+)\/detail$/);
    if (detailMatch) {
      const commandId = detailMatch[1];
      const record = commandRecords.get(commandId);
      if (!record) {
        throw new Error(`Unhandled command detail: ${url}`);
      }
      return jsonResponse({ result: record.detail });
    }

    throw new Error(`Unhandled request: ${url}`);
  });

  return { fetchMock };
}

function renderCommandsModuleInShell({
  initialCommandFamily = null,
  initialMeterIds = [],
  initialRecoveryAction = null,
  initialMeterScopeSource = null,
  initialSelectedCommandId = null,
  initialRetryRemediation = null,
}: {
  initialCommandFamily?: "relay_control" | "on_demand_read" | null;
  initialMeterIds?: string[];
  initialRecoveryAction?: {
    source: "readings_missing_recovery_queue";
    issueType: string | null;
    reason: string | null;
    context: string | null;
  } | null;
  initialMeterScopeSource?: "visible_filtered_result_set" | null;
  initialSelectedCommandId?: string | null;
  initialRetryRemediation?: {
    source: "jobs_retry_queue";
    itemType: "job_run" | "command";
    reason: string | null;
    context: string | null;
  } | null;
} = {}) {
  render(
    <OperationalShell
      eyebrow="Operational Pages"
      title="Global Commands MVP"
      description="Bounded commands module"
    >
      {({ authorizedFetch }) => (
        <CommandsModule
          authorizedFetch={authorizedFetch}
          initialCommandFamily={initialCommandFamily}
          initialMeterIds={initialMeterIds}
          initialRecoveryAction={initialRecoveryAction}
          initialMeterScopeSource={initialMeterScopeSource}
          initialSelectedCommandId={initialSelectedCommandId}
          initialRetryRemediation={initialRetryRemediation}
        />
      )}
    </OperationalShell>,
  );
}

describe("CommandsModule", () => {
  beforeEach(() => {
    window.localStorage.setItem("sunrise.web.apiBaseUrl", "http://localhost:8000");
    window.localStorage.setItem("sunrise.web.accessToken", "token-1");
  });

  afterEach(() => {
    vi.unstubAllGlobals();
    window.localStorage.clear();
  });

  it("renders the commands hub with bulk wizard and approvals entry surfaces", async () => {
    const { fetchMock } = createMockApi();
    vi.stubGlobal("fetch", fetchMock);

    renderCommandsModuleInShell();

    expect(await screen.findByRole("link", { name: "Commands" })).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "Commands command center" })).toBeInTheDocument();
    expect(screen.getByText("Bulk command wizard")).toBeInTheDocument();
    expect(screen.getByText("Command templates")).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "Approvals queue" })).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "Recent approval decisions" })).toBeInTheDocument();
    expect(await screen.findByText("Approved by the duty operator.")).toBeInTheDocument();
    expect(
      screen.getByText("Rejected while awaiting meter-side confirmation."),
    ).toBeInTheDocument();
    expect(await screen.findAllByText("profile-capture-template")).not.toHaveLength(0);
    expect(screen.getAllByText("relay-disconnect-template")).not.toHaveLength(0);
    expect(screen.getAllByText("on-demand-read-template")).not.toHaveLength(0);
  });

  it("saves the current wizard configuration as a reusable command template", async () => {
    const { fetchMock } = createMockApi();
    vi.stubGlobal("fetch", fetchMock);
    const user = userEvent.setup();

    renderCommandsModuleInShell({
      initialCommandFamily: "on_demand_read",
      initialRecoveryAction: {
        source: "readings_missing_recovery_queue",
        issueType: "missing_billing_read_context",
        reason: "Capture a billing snapshot after recovery follow-up.",
        context: "SN-1002",
      },
    });

    const bulkNotesInput = await screen.findByRole("textbox", { name: "Bulk notes" });
    const templateNameInput = await screen.findByRole("textbox", { name: "Template name" });
    expect(await screen.findByRole("combobox", { name: "Command family" })).toHaveValue(
      "on_demand_read",
    );
    expect(bulkNotesInput).toHaveValue(
      "Recovery action seeded from the readings missing-reads queue. Issue Missing Billing Read Context. Capture a billing snapshot after recovery follow-up. Context SN-1002.",
    );
    await user.type(templateNameInput, "Recovery follow-up read");
    await user.click(screen.getByRole("button", { name: "Save current as template" }));

    await waitFor(() => {
      expect(
        screen.getByText("Command template saved for reuse in the bulk wizard."),
      ).toBeInTheDocument();
      expect(screen.getByText("Recovery follow-up read")).toBeInTheDocument();
      expect(screen.getByRole("combobox", { name: "Command template" })).toHaveValue(
        "template-saved-5",
      );
    });

    const templateCreateCall = fetchMock.mock.calls.find(
      ([input, init]) =>
        input.toString().endsWith("/api/v1/command-templates") && init?.method === "POST",
    );
    expect(templateCreateCall).toBeDefined();
    const requestBody = JSON.parse(String(templateCreateCall?.[1]?.body ?? "{}")) as {
      code?: string;
      name?: string;
      category?: string;
      description?: string;
      payload_schema?: Record<string, unknown>;
    };
    expect(requestBody.code).toBe("recovery-follow-up-read-on-demand-read");
    expect(requestBody.name).toBe("Recovery follow-up read");
    expect(requestBody.category).toBe("on_demand_read");
    expect(requestBody.description).toBe(
      "Recovery action seeded from the readings missing-reads queue. Issue Missing Billing Read Context. Capture a billing snapshot after recovery follow-up. Context SN-1002.",
    );
    expect(requestBody.payload_schema?.default_bulk_notes).toBe(
      "Recovery action seeded from the readings missing-reads queue. Issue Missing Billing Read Context. Capture a billing snapshot after recovery follow-up. Context SN-1002.",
    );
  });

  it("reuses a saved template back into the bulk wizard", async () => {
    const { fetchMock } = createMockApi();
    vi.stubGlobal("fetch", fetchMock);
    const user = userEvent.setup();

    renderCommandsModuleInShell();

    const reconnectTemplateCard = (await screen.findByText("Relay reconnect template")).closest(
      "article",
    );
    expect(reconnectTemplateCard).not.toBeNull();

    await user.click(
      within(reconnectTemplateCard as HTMLElement).getByRole("button", { name: "Use template" }),
    );

    await waitFor(() => {
      expect(screen.getByText("Template Relay reconnect template loaded into the bulk wizard.")).toBeInTheDocument();
      expect(screen.getByRole("combobox", { name: "Command family" })).toHaveValue(
        "relay_control",
      );
      expect(screen.getByRole("combobox", { name: "Relay operation" })).toHaveValue("reconnect");
      expect(screen.getByRole("combobox", { name: "Command template" })).toHaveValue(
        "template-relay-reconnect",
      );
      expect(screen.getByRole("textbox", { name: "Bulk notes" })).toHaveValue(
        "Reconnect after the service verification completes.",
      );
    });
  });

  it("loads bounded command detail when a recent command is selected", async () => {
    const { fetchMock } = createMockApi();
    vi.stubGlobal("fetch", fetchMock);
    const user = userEvent.setup();

    renderCommandsModuleInShell();

    const recentCommandsHeading = await screen.findByText("Recent commands");
    const recentCommandsPanel = recentCommandsHeading.closest("section");
    expect(recentCommandsPanel).not.toBeNull();
    const relayRows = await within(recentCommandsPanel as HTMLElement).findAllByRole("button", {
      name: /relay-disconnect-template/i,
    });
    await user.click(relayRows[0]);

    const detailPanel = screen.getAllByRole("heading", { name: "Command detail" })[0]
      .closest("section");
    expect(detailPanel).not.toBeNull();
    await waitFor(() => {
      expect(within(detailPanel as HTMLElement).getByText("meter-2")).toBeInTheDocument();
      expect(within(detailPanel as HTMLElement).getByText("runtime-relay-1")).toBeInTheDocument();
      expect(within(detailPanel as HTMLElement).getByText("Approval context")).toBeInTheDocument();
    });
  });

  it("lands in the selected command detail from a retry remediation handoff", async () => {
    const { fetchMock } = createMockApi();
    vi.stubGlobal("fetch", fetchMock);

    renderCommandsModuleInShell({
      initialSelectedCommandId: "cmd-rejected-1",
      initialRetryRemediation: {
        source: "jobs_retry_queue",
        itemType: "job_run",
        reason: "Association rejected",
        context: "Meter meter-2. Retries 1/3.",
      },
    });

    expect(await screen.findByText("Retry remediation preselected")).toBeInTheDocument();
    expect(
      screen.getByText(
        "Retry remediation opened from the jobs retry queue. Queue item Job Run. Association rejected. Context Meter meter-2. Retries 1/3.",
      ),
    ).toBeInTheDocument();
    expect(screen.getByText("Retry remediation handoff")).toBeInTheDocument();
    expect(screen.getByText("Jobs retry queue")).toBeInTheDocument();

    const detailPanel = screen.getAllByRole("heading", { name: "Command detail" })[0].closest(
      "section",
    );
    expect(detailPanel).not.toBeNull();

    await waitFor(() => {
      expect(within(detailPanel as HTMLElement).getByText("on-demand-read-template")).toBeInTheDocument();
      expect(within(detailPanel as HTMLElement).getByText("meter-2")).toBeInTheDocument();
      expect(within(detailPanel as HTMLElement).getAllByText("Cancelled").length).toBeGreaterThan(0);
    });
  });

  it("renders profile capture, relay control, and on-demand summaries correctly", async () => {
    const { fetchMock } = createMockApi();
    vi.stubGlobal("fetch", fetchMock);

    renderCommandsModuleInShell();

    expect(await screen.findAllByText("acknowledged")).not.toHaveLength(0);
    expect(screen.getByText("disconnect (succeeded)")).toBeInTheDocument();
    expect(
      await screen.findByText("read_billing_snapshot billing (succeeded)"),
    ).toBeInTheDocument();
    expect(screen.getAllByText("Profile capture")).not.toHaveLength(0);
    expect(screen.getAllByText("Relay control")).not.toHaveLength(0);
    expect(screen.getAllByText("On-demand read")).not.toHaveLength(0);
  });

  it("initializes bulk target scope from handed-off meter context and supports removal", async () => {
    const { fetchMock } = createMockApi();
    vi.stubGlobal("fetch", fetchMock);
    const user = userEvent.setup();

    renderCommandsModuleInShell({
      initialMeterIds: ["meter-2", "meter-3"],
      initialMeterScopeSource: "visible_filtered_result_set",
    });

    expect(await screen.findByText("2 handed-off targets loaded")).toBeInTheDocument();
    expect(
      screen.getByText(
        "2 handed-off targets arrived from the visible filtered meter result set. Review the scope below before continuing with the bulk wizard.",
      ),
    ).toBeInTheDocument();

    const selectedTargetReviewHeading = screen.getByRole("heading", {
      name: "Selected target review",
    });
    const selectedTargetReview = selectedTargetReviewHeading.closest(".detail-stack");
    expect(selectedTargetReview).not.toBeNull();

    await waitFor(() => {
      expect(screen.getByRole("button", { name: "Restore handed-off targets" })).toBeInTheDocument();
      expect(
        within(selectedTargetReview as HTMLElement).getByText("2 handed-off targets"),
      ).toBeInTheDocument();
      expect(
        within(selectedTargetReview as HTMLElement).getByText("0 manually added targets"),
      ).toBeInTheDocument();
      expect(
        within(selectedTargetReview as HTMLElement).getAllByText("Handed-off target"),
      ).toHaveLength(2);
      expect(
        within(selectedTargetReview as HTMLElement).getByRole("button", {
          name: "Remove SN-1002",
        }),
      ).toBeInTheDocument();
      expect(
        within(selectedTargetReview as HTMLElement).getByRole("button", {
          name: "Remove SN-1003",
        }),
      ).toBeInTheDocument();
    });

    await user.type(screen.getByRole("searchbox", { name: "Bulk target filter" }), "SN-1001");
    await user.click(screen.getByRole("checkbox", { name: "Include in bulk request" }));

    await waitFor(() => {
      expect(
        within(selectedTargetReview as HTMLElement).getByText("2 handed-off targets"),
      ).toBeInTheDocument();
      expect(
        within(selectedTargetReview as HTMLElement).getByText("1 manually added target"),
      ).toBeInTheDocument();
      expect(
        within(selectedTargetReview as HTMLElement).getByText(
          "Handed-off and manually added targets are both included in the current review scope.",
        ),
      ).toBeInTheDocument();
      expect(
        within(selectedTargetReview as HTMLElement).getByRole("button", {
          name: "Remove SN-1001",
        }),
      ).toBeInTheDocument();
      expect(
        within(selectedTargetReview as HTMLElement).getAllByText("Handed-off target"),
      ).toHaveLength(2);
      expect(
        within(selectedTargetReview as HTMLElement).getByText("Manually added target"),
      ).toBeInTheDocument();
    });

    await user.click(screen.getByRole("button", { name: "Restore handed-off targets" }));

    await user.click(
      within(selectedTargetReview as HTMLElement).getByRole("button", {
        name: "Remove SN-1002",
      }),
    );

    await waitFor(() => {
      expect(
        within(selectedTargetReview as HTMLElement).queryByRole("button", {
          name: "Remove SN-1001",
        }),
      ).not.toBeInTheDocument();
      expect(
        within(selectedTargetReview as HTMLElement).getByText("1 handed-off target"),
      ).toBeInTheDocument();
      expect(
        within(selectedTargetReview as HTMLElement).getByText("0 manually added targets"),
      ).toBeInTheDocument();
      expect(
        within(selectedTargetReview as HTMLElement).queryByRole("button", {
          name: "Remove SN-1002",
        }),
      ).not.toBeInTheDocument();
      expect(
        within(selectedTargetReview as HTMLElement).getByRole("button", {
          name: "Remove SN-1003",
        }),
      ).toBeInTheDocument();
    });
  });

  it("hydrates the bulk wizard from a readings recovery handoff into on-demand read", async () => {
    const { fetchMock } = createMockApi();
    vi.stubGlobal("fetch", fetchMock);
    const user = userEvent.setup();

    renderCommandsModuleInShell({
      initialCommandFamily: "on_demand_read",
      initialMeterIds: ["meter-2"],
      initialRecoveryAction: {
        source: "readings_missing_recovery_queue",
        issueType: "missing_billing_read_context",
        reason: "No billing read is currently available for the selected meter.",
        context: "SN-1002",
      },
    });

    expect(
      (await screen.findAllByText(includesText("Recovery action handoff"))).length,
    ).toBeGreaterThan(0);
    await waitFor(() => {
      expect(screen.getByRole("combobox", { name: "Command family" })).toHaveValue(
        "on_demand_read",
      );
      expect(screen.getByRole("combobox", { name: "Command template" })).toHaveValue(
        "template-on-demand-read",
      );
      expect(screen.getByRole("textbox", { name: "Bulk notes" })).toHaveValue(
        "Recovery action seeded from the readings missing-reads queue. Issue Missing Billing Read Context. No billing read is currently available for the selected meter. Context SN-1002.",
      );
      expect(screen.getByText("1 handed-off target loaded")).toBeInTheDocument();
      expect(screen.getByRole("button", { name: "Submit for approval" })).toBeEnabled();
    });

    await user.click(screen.getByRole("button", { name: "Submit for approval" }));

    await waitFor(() => {
      expect(screen.getByText("1 bulk command requests submitted for approval.")).toBeInTheDocument();
      expect(screen.getAllByText("Submitted For Approval")).not.toHaveLength(0);
    });

    const bulkRequestCall = fetchMock.mock.calls.find(
      ([input, init]) =>
        input.toString().endsWith("/api/v1/commands/bulk-requests") && init?.method === "POST",
    );
    expect(bulkRequestCall).toBeDefined();
    const requestBody = JSON.parse(String(bulkRequestCall?.[1]?.body ?? "{}")) as {
      family?: string;
      meter_ids?: string[];
      on_demand_read_operation?: string;
      notes?: string;
    };
    expect(requestBody.family).toBe("on_demand_read");
    expect(requestBody.meter_ids).toEqual(["meter-2"]);
    expect(requestBody.on_demand_read_operation).toBe("read_billing_snapshot");
    expect(requestBody.notes).toContain("Missing Billing Read Context");
  });

  it("hydrates the bulk wizard from a multi-meter bulk recovery handoff", async () => {
    const { fetchMock } = createMockApi();
    vi.stubGlobal("fetch", fetchMock);
    const user = userEvent.setup();

    renderCommandsModuleInShell({
      initialCommandFamily: "on_demand_read",
      initialMeterIds: ["meter-1", "meter-2"],
      initialRecoveryAction: {
        source: "readings_missing_recovery_queue",
        issueType: "bulk_recovery_selection",
        reason: "2 recovery items selected from the readings missing-reads queue for bounded ON_DEMAND_READ handoff.",
        context: "2 meters: SN-1001, SN-1002. Issue mix: Stale Interval Window, Missing Billing Read Context.",
      },
    });

    expect(
      (await screen.findAllByText(includesText("Recovery action handoff"))).length,
    ).toBeGreaterThan(0);
    await waitFor(() => {
      expect(screen.getByRole("combobox", { name: "Command family" })).toHaveValue(
        "on_demand_read",
      );
      expect(screen.getByRole("textbox", { name: "Bulk notes" })).toHaveValue(
        "Recovery action seeded from the readings missing-reads queue. Issue Bulk Recovery Selection. 2 recovery items selected from the readings missing-reads queue for bounded ON_DEMAND_READ handoff. Context 2 meters: SN-1001, SN-1002. Issue mix: Stale Interval Window, Missing Billing Read Context.",
      );
      expect(screen.getByText("2 handed-off targets loaded")).toBeInTheDocument();
      expect(screen.getByText("2 included meters")).toBeInTheDocument();
    });

    await user.click(screen.getByRole("button", { name: "Submit for approval" }));

    await waitFor(() => {
      expect(screen.getByText("2 bulk command requests submitted for approval.")).toBeInTheDocument();
      expect(screen.getByText("2 waiting")).toBeInTheDocument();
    });

    const bulkRequestCall = fetchMock.mock.calls.find(
      ([input, init]) =>
        input.toString().endsWith("/api/v1/commands/bulk-requests") && init?.method === "POST",
    );
    expect(bulkRequestCall).toBeDefined();
    const requestBody = JSON.parse(String(bulkRequestCall?.[1]?.body ?? "{}")) as {
      family?: string;
      meter_ids?: string[];
      on_demand_read_operation?: string;
      notes?: string;
    };
    expect(requestBody.family).toBe("on_demand_read");
    expect(requestBody.meter_ids).toEqual(["meter-1", "meter-2"]);
    expect(requestBody.on_demand_read_operation).toBe("read_billing_snapshot");
    expect(requestBody.notes).toContain("Bulk Recovery Selection");
  });

  it("submits a bounded bulk command request and shows it in the approvals queue", async () => {
    const { fetchMock } = createMockApi();
    vi.stubGlobal("fetch", fetchMock);
    const user = userEvent.setup();

    renderCommandsModuleInShell();

    await screen.findByText("SN-1001");
    const targetFilter = await screen.findByRole("searchbox", { name: "Bulk target filter" });
    await user.type(targetFilter, "SN-100");
    await user.click(screen.getByRole("button", { name: "Select filtered" }));
    await user.click(screen.getByRole("button", { name: "Submit for approval" }));

    await waitFor(() => {
      expect(
        screen.getByText("3 bulk command requests submitted for approval."),
      ).toBeInTheDocument();
      expect(screen.getAllByText("Submitted For Approval")).not.toHaveLength(0);
      expect(screen.getByText("3 waiting")).toBeInTheDocument();
    });
  });

  it("shows a keep-current action beside the replacement confirmation for non-empty selection changes", async () => {
    const { fetchMock } = createMockApi();
    vi.stubGlobal("fetch", fetchMock);
    const user = userEvent.setup();

    renderCommandsModuleInShell({
      initialMeterIds: ["meter-2", "meter-3"],
      initialMeterScopeSource: "visible_filtered_result_set",
    });

    const getSelectedTargetReview = () =>
      screen.getByRole("heading", { name: "Selected target review" }).closest(".detail-stack") as HTMLElement;

    expect(await screen.findByText("2 handed-off targets loaded")).toBeInTheDocument();
    await screen.findByText("SN-1001");
    await user.click(screen.getByRole("button", { name: "Restore handed-off targets" }));
    await user.type(screen.getByRole("searchbox", { name: "Bulk target filter" }), "SN-1001");

    await user.click(screen.getByRole("button", { name: "Select filtered" }));

    expect(
      screen.getByText(
        "Select filtered will replace the current 2 selected targets with the 1 meter currently visible in the target filter. Click Confirm replace with filtered to continue.",
      ),
    ).toBeInTheDocument();
    expect(
      screen.getByRole("button", { name: "Confirm replace with filtered" }),
    ).toBeInTheDocument();
    expect(
      screen.getByRole("button", { name: "Keep current selection" }),
    ).toBeInTheDocument();
    expect(
      screen.getByText("1 filtered target in pending replacement"),
    ).toBeInTheDocument();

    await waitFor(() => {
      expect(
        within(getSelectedTargetReview()).getAllByText("2 handed-off targets").length,
      ).toBeGreaterThan(0);
      expect(
        within(getSelectedTargetReview()).getAllByText("0 manually added targets").length,
      ).toBeGreaterThan(0);
      expect(
        within(getSelectedTargetReview()).getByRole("button", {
          name: "Remove SN-1002",
        }),
      ).toBeInTheDocument();
      expect(
        within(getSelectedTargetReview()).getByRole("button", {
          name: "Remove SN-1003",
        }),
      ).toBeInTheDocument();
    });
  });

  it("keeps the current selection when the pending replacement is dismissed", async () => {
    const { fetchMock } = createMockApi();
    vi.stubGlobal("fetch", fetchMock);
    const user = userEvent.setup();

    renderCommandsModuleInShell({
      initialMeterIds: ["meter-2", "meter-3"],
      initialMeterScopeSource: "visible_filtered_result_set",
    });

    const getSelectedTargetReview = () =>
      screen.getByRole("heading", { name: "Selected target review" }).closest(".detail-stack") as HTMLElement;

    expect(await screen.findByText("2 handed-off targets loaded")).toBeInTheDocument();
    await screen.findByText("SN-1001");
    await user.click(screen.getByRole("button", { name: "Restore handed-off targets" }));
    await user.type(screen.getByRole("searchbox", { name: "Bulk target filter" }), "SN-1001");
    await user.click(screen.getByRole("button", { name: "Select filtered" }));

    expect(
      screen.getByRole("button", { name: "Keep current selection" }),
    ).toBeInTheDocument();
    expect(
      screen.getByText("1 filtered target in pending replacement"),
    ).toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: "Keep current selection" }));

    expect(
      screen.queryByText(/Select filtered will replace the current/i),
    ).not.toBeInTheDocument();
    expect(
      screen.queryByRole("button", { name: "Confirm replace with filtered" }),
    ).not.toBeInTheDocument();
    expect(
      screen.queryByRole("button", { name: "Keep current selection" }),
    ).not.toBeInTheDocument();
    expect(
      screen.queryByText(/filtered target.*pending replacement/i),
    ).not.toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Select filtered" })).toBeInTheDocument();

    await waitFor(() => {
      expect(
        within(getSelectedTargetReview()).getAllByText("2 handed-off targets").length,
      ).toBeGreaterThan(0);
      expect(
        within(getSelectedTargetReview()).getAllByText("0 manually added targets").length,
      ).toBeGreaterThan(0);
      expect(
        within(getSelectedTargetReview()).getByRole("button", {
          name: "Remove SN-1002",
        }),
      ).toBeInTheDocument();
      expect(
        within(getSelectedTargetReview()).getByRole("button", {
          name: "Remove SN-1003",
        }),
      ).toBeInTheDocument();
      expect(
        within(getSelectedTargetReview()).queryByRole("button", {
          name: "Remove SN-1001",
        }),
      ).not.toBeInTheDocument();
    });
  });

  it("clarifies that select filtered replaces the current selection with the filtered result set", async () => {
    const { fetchMock } = createMockApi();
    vi.stubGlobal("fetch", fetchMock);
    const user = userEvent.setup();

    renderCommandsModuleInShell({
      initialMeterIds: ["meter-2", "meter-3"],
      initialMeterScopeSource: "visible_filtered_result_set",
    });

    const selectedTargetReviewHeading = await screen.findByRole("heading", {
      name: "Selected target review",
    });
    const selectedTargetReview = selectedTargetReviewHeading.closest(".detail-stack");
    expect(selectedTargetReview).not.toBeNull();
    const getSelectedTargetReview = () =>
      screen.getByRole("heading", { name: "Selected target review" }).closest(".detail-stack") as HTMLElement;

    expect(await screen.findByText("2 handed-off targets loaded")).toBeInTheDocument();
    await screen.findByText("SN-1001");
    await user.click(screen.getByRole("button", { name: "Restore handed-off targets" }));
    expect(
      screen.getAllByText(
        includesText(
          "Select filtered replaces the current selected target set with the 3 meters currently visible in the target filter.",
        ),
      ).length,
    ).toBeGreaterThan(0);

    await waitFor(() => {
      expect(
        within(getSelectedTargetReview()).getAllByText("2 handed-off targets").length,
      ).toBeGreaterThan(0);
      expect(
        within(getSelectedTargetReview()).getAllByText("0 manually added targets").length,
      ).toBeGreaterThan(0);
    });

    await user.type(screen.getByRole("searchbox", { name: "Bulk target filter" }), "SN-1001");

    await waitFor(() => {
      expect(
        screen.getAllByText(
          includesText(
            "Select filtered replaces the current selected target set with the 1 meter currently visible in the target filter.",
          ),
        ).length,
      ).toBeGreaterThan(0);
    });

    await user.click(screen.getByRole("checkbox", { name: "Include in bulk request" }));

    await waitFor(() => {
      expect(
        within(getSelectedTargetReview()).getAllByText("2 handed-off targets").length,
      ).toBeGreaterThan(0);
      expect(
        within(getSelectedTargetReview()).getAllByText("1 manually added target").length,
      ).toBeGreaterThan(0);
    });

    await user.click(screen.getByRole("button", { name: "Select filtered" }));
    expect(
      screen.getByText(
        "Select filtered will replace the current 3 selected targets with the 1 meter currently visible in the target filter. Click Confirm replace with filtered to continue.",
      ),
    ).toBeInTheDocument();
    expect(
      screen.getByText("1 filtered target in pending replacement"),
    ).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Confirm replace with filtered" }));

    await waitFor(() => {
      expect(
        within(getSelectedTargetReview()).getAllByText("0 handed-off targets").length,
      ).toBeGreaterThan(0);
      expect(
        within(getSelectedTargetReview()).getAllByText("1 manually added target").length,
      ).toBeGreaterThan(0);
      expect(
        within(getSelectedTargetReview()).queryAllByText("Handed-off target"),
      ).toHaveLength(0);
      expect(
        within(getSelectedTargetReview()).getByText("Manually added target"),
      ).toBeInTheDocument();
      expect(
        within(getSelectedTargetReview()).queryByRole("button", {
          name: "Remove SN-1002",
        }),
      ).not.toBeInTheDocument();
      expect(
        within(getSelectedTargetReview()).queryByRole("button", {
          name: "Remove SN-1003",
        }),
      ).not.toBeInTheDocument();
      expect(
        within(getSelectedTargetReview()).getByRole("button", {
          name: "Remove SN-1001",
        }),
      ).toBeInTheDocument();
    });
  });

  it("does not show a replacement confirmation when select filtered starts from no selection", async () => {
    const { fetchMock } = createMockApi();
    vi.stubGlobal("fetch", fetchMock);
    const user = userEvent.setup();

    renderCommandsModuleInShell();

    const getSelectedTargetReview = () =>
      screen.getByRole("heading", { name: "Selected target review" }).closest(".detail-stack") as HTMLElement;

    await screen.findByText("SN-1001");
    await user.type(screen.getByRole("searchbox", { name: "Bulk target filter" }), "SN-1001");
    await user.click(screen.getByRole("button", { name: "Select filtered" }));

    expect(
      screen.queryByText(/Select filtered will replace the current/i),
    ).not.toBeInTheDocument();
    expect(
      screen.queryByRole("button", { name: "Confirm replace with filtered" }),
    ).not.toBeInTheDocument();
    expect(
      screen.queryByRole("button", { name: "Keep current selection" }),
    ).not.toBeInTheDocument();
    expect(
      screen.queryByText(/filtered target.*pending replacement/i),
    ).not.toBeInTheDocument();

    await waitFor(() => {
      expect(
        within(getSelectedTargetReview()).getByRole("button", {
          name: "Remove SN-1001",
        }),
      ).toBeInTheDocument();
      expect(
        within(getSelectedTargetReview()).getAllByText("1 manually added target").length,
      ).toBeGreaterThan(0);
    });
  });

  it("supports approving a pending bulk command from the approvals queue", async () => {
    const { fetchMock } = createMockApi();
    vi.stubGlobal("fetch", fetchMock);
    const user = userEvent.setup();

    renderCommandsModuleInShell();

    await screen.findByText("SN-1001");
    await user.click(screen.getByRole("button", { name: "Select filtered" }));
    await user.click(screen.getByRole("button", { name: "Submit for approval" }));

    await screen.findByText("3 bulk command requests submitted for approval.");
    const approveButtons = await screen.findAllByRole("button", { name: "Approve" });
    await user.click(approveButtons[0]);

    await waitFor(() => {
      expect(screen.getByText("Selected command approval accepted.")).toBeInTheDocument();
      expect(screen.getAllByText("Approved")).not.toHaveLength(0);
    });
  });

  it("filters approval history visibility by decision state and family", async () => {
    const { fetchMock } = createMockApi();
    vi.stubGlobal("fetch", fetchMock);
    const user = userEvent.setup();

    renderCommandsModuleInShell();

    expect(await screen.findByText("Approved by the duty operator.")).toBeInTheDocument();
    expect(screen.getByText("Rejected while awaiting meter-side confirmation.")).toBeInTheDocument();

    await user.selectOptions(screen.getByLabelText("Decision state"), "rejected");

    await waitFor(() => {
      expect(screen.getByText("Rejected while awaiting meter-side confirmation.")).toBeInTheDocument();
      expect(screen.queryByText("Approved by the duty operator.")).not.toBeInTheDocument();
    });

    await user.selectOptions(screen.getByLabelText("Approval family"), "relay_control");

    await waitFor(() => {
      expect(
        screen.getByText("No recent approval decisions match the current filters."),
      ).toBeInTheDocument();
    });
  });

  it("does not surface unsupported family actions", async () => {
    const { fetchMock } = createMockApi();
    vi.stubGlobal("fetch", fetchMock);

    renderCommandsModuleInShell();

    await screen.findByText("Recent commands");
    expect(screen.queryByText(/execute profile capture now/i)).not.toBeInTheDocument();
    expect(screen.queryByText(/execute relay disconnect now/i)).not.toBeInTheDocument();
    expect(screen.queryByText(/execute on-demand read now/i)).not.toBeInTheDocument();
  });
});
