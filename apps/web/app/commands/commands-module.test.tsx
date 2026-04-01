import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { OperationalShell } from "../operational-shell";
import { CommandsModule } from "./commands-module";

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

  const templates = [
    {
      id: "template-relay-disconnect",
      code: "relay-disconnect-template",
      name: "Relay disconnect template",
      category: "remote_disconnect",
      is_active: true,
    },
    {
      id: "template-relay-reconnect",
      code: "relay-reconnect-template",
      name: "Relay reconnect template",
      category: "remote_reconnect",
      is_active: true,
    },
    {
      id: "template-on-demand-read",
      code: "on-demand-read-template",
      name: "On-demand read template",
      category: "on_demand_read",
      is_active: true,
    },
    {
      id: "template-profile-capture",
      code: "profile-capture-template",
      name: "Profile capture template",
      category: "profile_capture",
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

function renderCommandsModuleInShell({ initialMeterIds = [] }: { initialMeterIds?: string[] } = {}) {
  render(
    <OperationalShell
      eyebrow="Operational Pages"
      title="Global Commands MVP"
      description="Bounded commands module"
    >
      {({ authorizedFetch }) => (
        <CommandsModule authorizedFetch={authorizedFetch} initialMeterIds={initialMeterIds} />
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

    renderCommandsModuleInShell({ initialMeterIds: ["meter-2", "meter-3"] });

    expect(await screen.findByText("2 handed-off targets loaded")).toBeInTheDocument();

    const selectedTargetReviewHeading = screen.getByRole("heading", {
      name: "Selected target review",
    });
    const selectedTargetReview = selectedTargetReviewHeading.closest(".detail-stack");
    expect(selectedTargetReview).not.toBeNull();

    await waitFor(() => {
      expect(screen.getByRole("button", { name: "Restore handed-off targets" })).toBeInTheDocument();
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

    await user.click(
      within(selectedTargetReview as HTMLElement).getByRole("button", {
        name: "Remove SN-1002",
      }),
    );

    await waitFor(() => {
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
