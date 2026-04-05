import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { OperationalShell } from "../operational-shell";
import { JobsEventsAlertsModule } from "./jobs-events-alerts-module";

function jsonResponse(payload: unknown, status = 200) {
  return new Response(JSON.stringify(payload), {
    status,
    headers: { "Content-Type": "application/json" },
  });
}

function createMockApi({
  jobDefinitions = [
    {
      id: "job-definition-1",
      code: "profile-capture-daily",
      name: "Profile capture daily",
      category: "command",
      target_type: "meter",
      schedule_type: "once",
      run_at: "2026-03-31T09:55:00.000Z",
      cron_expression: null,
      interval_seconds: null,
      command_template_id: "template-1",
      default_payload: null,
      priority: "normal",
      timeout_seconds: 120,
      max_retries: 3,
      is_active: true,
      notes: "Daily planning anchor",
    },
    {
      id: "job-definition-2",
      code: "relay-health-interval",
      name: "Relay health interval",
      category: "connectivity_check",
      target_type: "meter",
      schedule_type: "interval",
      run_at: "2026-03-31T09:00:00.000Z",
      cron_expression: null,
      interval_seconds: 900,
      command_template_id: null,
      default_payload: null,
      priority: "normal",
      timeout_seconds: 180,
      max_retries: 1,
      is_active: true,
      notes: null,
    },
    {
      id: "job-definition-3",
      code: "nightly-maintenance",
      name: "Nightly maintenance",
      category: "system_maintenance",
      target_type: "system",
      schedule_type: "cron",
      run_at: null,
      cron_expression: "0 2 * * *",
      interval_seconds: null,
      command_template_id: null,
      default_payload: null,
      priority: "normal",
      timeout_seconds: 300,
      max_retries: 0,
      is_active: false,
      notes: "Paused pending review",
    },
    {
      id: "job-definition-4",
      code: "manual-investigation",
      name: "Manual investigation trigger",
      category: "command",
      target_type: "meter",
      schedule_type: "manual",
      run_at: null,
      cron_expression: null,
      interval_seconds: null,
      command_template_id: null,
      default_payload: null,
      priority: "normal",
      timeout_seconds: 240,
      max_retries: 0,
      is_active: true,
      notes: "Manual operator use",
    },
  ],
  jobRuns = [
    {
      id: "job-run-1",
      job_definition_id: "job-definition-1",
      target_meter_id: "meter-1",
      target_endpoint_id: null,
      related_command_id: "command-1",
      scheduled_for: "2026-03-31T09:55:00.000Z",
      available_at: "2026-03-31T09:55:00.000Z",
      claimed_at: "2026-03-31T09:56:00.000Z",
      claim_expires_at: null,
      worker_identifier: "worker-1",
      started_at: "2026-03-31T09:57:00.000Z",
      completed_at: "2026-03-31T09:57:30.000Z",
      cancelled_at: null,
      status: "failed",
      retry_count: 1,
      max_retries: 3,
      request_payload: { request: "payload" },
      result_summary: { error: "Association rejected" },
      latest_error_code: "AUTH_FAILED",
      latest_error_message: "Association rejected",
      correlation_id: "job-correlation-1",
      related_command: {
        id: "command-1",
        current_status: "failed",
        command_template_id: "template-1",
        command_template_code: "profile-capture-template",
      },
    },
  ],
  recentCommands = [
    {
      command_id: "command-1",
      command_family: "profile_capture",
      command_status: "failed",
      meter_id: "meter-1",
      command_template_code: "profile-capture-template",
      latest_command_execution_attempt_status: "failed",
      family_specific_outcome_summary: {
        terminal_status_category: "rejected",
      },
      latest_updated_at: "2026-03-31T09:58:00.000Z",
    },
    {
      command_id: "command-2",
      command_family: "relay_control",
      command_status: "queued",
      meter_id: "meter-2",
      command_template_code: "relay-disconnect-template",
      latest_command_execution_attempt_status: "queued",
      family_specific_outcome_summary: {
        relay_control_operation: "disconnect",
        relay_control_execution_outcome: "pending",
      },
      latest_updated_at: "2026-03-31T09:54:00.000Z",
    },
  ],
  recentEvents = [
    {
      id: "event-1",
      meter_id: "meter-2",
      event_code: "tamper_open",
      event_name: "Tamper Open",
      severity: "critical",
      event_state: "open",
      occurred_at: "2026-03-31T09:59:00.000Z",
      received_at: "2026-03-31T09:59:30.000Z",
    },
  ],
  jobDefinitionsStatus = 200,
  jobRunsStatus = 200,
  commandsStatus = 200,
  eventsStatus = 200,
  jobDefinitionsDetail = "Job definitions unavailable.",
  jobRunsDetail = "Job runs unavailable.",
  commandsDetail = "Commands unavailable.",
  eventsDetail = "Events unavailable.",
  delayedResponses = false,
}: {
  jobDefinitions?: Array<Record<string, unknown>>;
  jobRuns?: Array<Record<string, unknown>>;
  recentCommands?: Array<Record<string, unknown>>;
  recentEvents?: Array<Record<string, unknown>>;
  jobDefinitionsStatus?: number;
  jobRunsStatus?: number;
  commandsStatus?: number;
  eventsStatus?: number;
  jobDefinitionsDetail?: string;
  jobRunsDetail?: string;
  commandsDetail?: string;
  eventsDetail?: string;
  delayedResponses?: boolean;
} = {}) {
  const fetchMock = vi.fn(async (input: RequestInfo | URL) => {
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

    if (delayedResponses) {
      await new Promise((resolve) => window.setTimeout(resolve, 100));
    }

    if (url.endsWith("/api/v1/job-definitions")) {
      if (jobDefinitionsStatus !== 200) {
        return jsonResponse({ detail: jobDefinitionsDetail }, jobDefinitionsStatus);
      }
      return jsonResponse({ total: jobDefinitions.length, items: jobDefinitions });
    }

    if (url.includes("/api/v1/job-runs?")) {
      if (jobRunsStatus !== 200) {
        return jsonResponse({ detail: jobRunsDetail }, jobRunsStatus);
      }
      return jsonResponse({ total: jobRuns.length, items: jobRuns });
    }

    if (url.includes("/api/v1/commands/recent?")) {
      if (commandsStatus !== 200) {
        return jsonResponse({ detail: commandsDetail }, commandsStatus);
      }
      return jsonResponse({
        total: recentCommands.length,
        limit: 8,
        family_filter: null,
        items: recentCommands,
      });
    }

    if (url.includes("/api/v1/events/recent?")) {
      if (eventsStatus !== 200) {
        return jsonResponse({ detail: eventsDetail }, eventsStatus);
      }
      return jsonResponse({ total: recentEvents.length, items: recentEvents });
    }

    throw new Error(`Unhandled request: ${url}`);
  });

  return { fetchMock };
}

function renderJobsEventsAlertsModuleInShell({
  initialAttentionContext = null,
  initialRetryQueueRoundTripContext = null,
}: {
  initialAttentionContext?: {
    source: "dashboard_attention_queue";
    filter: "attention";
  } | null;
  initialRetryQueueRoundTripContext?: {
    source: "activity_detail_roundtrip";
    activityType: "job_run" | "command";
    activityId: string;
  } | null;
} = {}) {
  render(
    <OperationalShell
      eyebrow="Operational Pages"
      title="Jobs / Events / Alerts MVP"
      description="Bounded jobs, events, and alerts monitoring"
    >
      {({ authorizedFetch }) => (
        <JobsEventsAlertsModule
          authorizedFetch={authorizedFetch}
          initialAttentionContext={initialAttentionContext}
          initialRetryQueueRoundTripContext={initialRetryQueueRoundTripContext}
        />
      )}
    </OperationalShell>,
  );
}

describe("JobsEventsAlertsModule", () => {
  beforeEach(() => {
    window.localStorage.setItem("sunrise.web.apiBaseUrl", "http://localhost:8000");
    window.localStorage.setItem("sunrise.web.accessToken", "token-1");
  });

  afterEach(() => {
    vi.unstubAllGlobals();
    window.localStorage.clear();
  });

  it("renders a compact recent jobs, events, and alerts activity surface inside the shared shell", async () => {
    const { fetchMock } = createMockApi();
    vi.stubGlobal("fetch", fetchMock);

    renderJobsEventsAlertsModuleInShell();

    expect(
      await screen.findByRole("link", { name: "Jobs / Events / Alerts" }),
    ).toBeInTheDocument();
    expect(
      await screen.findByRole("heading", { name: "Operations monitoring center" }),
    ).toBeInTheDocument();

    await waitFor(() => {
      expect(screen.getByText("Recent job runs loaded")).toBeInTheDocument();
      expect(screen.getByText("Recent events loaded")).toBeInTheDocument();
      expect(screen.getByText("Derived alerts in current view")).toBeInTheDocument();
      expect(screen.getByText("Retry-worthy execution contexts")).toBeInTheDocument();
    });
  });

  it("renders a bounded job runs and retry queue surface with retry and attempt visibility", async () => {
    const { fetchMock } = createMockApi();
    vi.stubGlobal("fetch", fetchMock);

    renderJobsEventsAlertsModuleInShell();

    const retryPanel = (
      await screen.findByRole("heading", { name: "Job runs + retry queue" })
    ).closest("section");
    expect(retryPanel).not.toBeNull();

    await waitFor(() => {
      expect(
        within(retryPanel as HTMLElement).getByText("Job runs with retry capacity"),
      ).toBeInTheDocument();
      expect(within(retryPanel as HTMLElement).getByText("Retries 1/3")).toBeInTheDocument();
      expect(
        within(retryPanel as HTMLElement).getByText(
          "2 retry slots remaining in the current bounded runtime budget.",
        ),
      ).toBeInTheDocument();
      expect(
        within(retryPanel as HTMLElement).getByText("Latest attempt Failed"),
      ).toBeInTheDocument();
    });

    expect(
      within(retryPanel as HTMLElement).getAllByRole("link", {
        name: "Open remediation context",
      })[0],
    ).toHaveAttribute(
      "href",
      "/commands?selectedCommandId=command-1&retrySource=jobs_retry_queue&retryItemType=command&retryReason=rejected&retryContext=Meter+meter-1.+Latest+attempt+Failed.",
    );
    expect(
      within(retryPanel as HTMLElement).getAllByRole("link", {
        name: "Open remediation context",
      })[1],
    ).toHaveAttribute(
      "href",
      "/commands?selectedCommandId=command-1&retrySource=jobs_retry_queue&retryItemType=job_run&retryReason=Association+rejected&retryContext=Meter+meter-1.+Retries+1%2F3.",
    );
    expect(
      within(retryPanel as HTMLElement).getAllByRole("link", { name: "Open retry detail" })[0],
    ).toHaveAttribute(
      "href",
      "/jobs-events-alerts/activity/command/command-1?retryEntrySource=jobs_retry_queue",
    );
    expect(
      within(retryPanel as HTMLElement).getAllByRole("link", { name: "Open retry detail" })[1],
    ).toHaveAttribute(
      "href",
      "/jobs-events-alerts/activity/job_run/job-run-1?retryEntrySource=jobs_retry_queue",
    );
    expect(
      within(retryPanel as HTMLElement).getAllByRole("link", { name: "Open commands page" })[0],
    ).toHaveAttribute("href", "/commands");
  });

  it("renders a scheduler calendar workspace with calendar anchors and planning lanes", async () => {
    const { fetchMock } = createMockApi();
    vi.stubGlobal("fetch", fetchMock);

    renderJobsEventsAlertsModuleInShell();

    const schedulerPanel = (
      await screen.findByRole("heading", { name: "Scheduler calendar workspace" })
    ).closest("section");
    expect(schedulerPanel).not.toBeNull();

    await waitFor(() => {
      expect(
        within(schedulerPanel as HTMLElement).getByText("Loaded schedules"),
      ).toBeInTheDocument();
      expect(
        within(schedulerPanel as HTMLElement).getByText("Active schedules"),
      ).toBeInTheDocument();
      expect(
        within(schedulerPanel as HTMLElement).getByText("One-time calendar anchors"),
      ).toBeInTheDocument();
      expect(
        within(schedulerPanel as HTMLElement).getByText("Recurring schedules"),
      ).toBeInTheDocument();
      expect(
        within(schedulerPanel as HTMLElement).getByText("Calendar anchors"),
      ).toBeInTheDocument();
      expect(
        within(schedulerPanel as HTMLElement).getByText("Recurring cadence lane"),
      ).toBeInTheDocument();
      expect(
        within(schedulerPanel as HTMLElement).getByText("Manual planning lane"),
      ).toBeInTheDocument();
      expect(
        within(schedulerPanel as HTMLElement).getByText("Profile capture daily"),
      ).toBeInTheDocument();
      expect(
        within(schedulerPanel as HTMLElement).getByText("Relay health interval"),
      ).toBeInTheDocument();
      expect(
        within(schedulerPanel as HTMLElement).getByText("Manual investigation trigger"),
      ).toBeInTheDocument();
      expect(
        within(schedulerPanel as HTMLElement).getByText("Every 15 min"),
      ).toBeInTheDocument();
      expect(
        within(schedulerPanel as HTMLElement).getByText("Cron 0 2 * * *"),
      ).toBeInTheDocument();
      expect(
        within(schedulerPanel as HTMLElement).getAllByText("Active schedule").length,
      ).toBeGreaterThan(0);
    });

    expect(
      within(schedulerPanel as HTMLElement).getByRole("link", { name: "Open latest run detail" }),
    ).toHaveAttribute("href", "/jobs-events-alerts/activity/job_run/job-run-1");
  });

  it("renders a job definition workspace and lets the scheduler lanes change the selected definition", async () => {
    const { fetchMock } = createMockApi();
    vi.stubGlobal("fetch", fetchMock);
    const user = userEvent.setup();

    renderJobsEventsAlertsModuleInShell();

    const workspacePanel = (
      await screen.findByRole("heading", { name: "Job definition workspace" })
    ).closest("section");
    expect(workspacePanel).not.toBeNull();

    await waitFor(() => {
      expect(
        within(workspacePanel as HTMLElement).getByText("Profile capture daily"),
      ).toBeInTheDocument();
      expect(
        within(workspacePanel as HTMLElement).getByText("Planning posture"),
      ).toBeInTheDocument();
      expect(
        within(workspacePanel as HTMLElement).getByText("Schedule summary"),
      ).toBeInTheDocument();
      expect(
        within(workspacePanel as HTMLElement).getByText("Visible execution context"),
      ).toBeInTheDocument();
      expect(
        within(workspacePanel as HTMLElement).getByText("Activity history workspace"),
      ).toBeInTheDocument();
      expect(
        within(workspacePanel as HTMLElement).getByText("Failure history lane"),
      ).toBeInTheDocument();
      expect(
        within(workspacePanel as HTMLElement).getByText(/Latest run Failed at .*2026/),
      ).toBeInTheDocument();
      expect(
        within(workspacePanel as HTMLElement).getByText("Recent runs in view"),
      ).toBeInTheDocument();
      expect(
        within(workspacePanel as HTMLElement).getByText("Failed runs in view"),
      ).toBeInTheDocument();
      expect(
        within(workspacePanel as HTMLElement).getByText("Successful runs in view"),
      ).toBeInTheDocument();
      expect(
        within(workspacePanel as HTMLElement).getByRole("link", {
          name: "Open execution log",
        }),
      ).toHaveAttribute("href", "/jobs-events-alerts/activity/job_run/job-run-1");
    });

    expect(
      within(workspacePanel as HTMLElement).getByRole("link", {
        name: "Open latest execution log",
      }),
    ).toHaveAttribute("href", "/jobs-events-alerts/activity/job_run/job-run-1");
    expect(
      within(workspacePanel as HTMLElement).getByRole("link", {
        name: "Review scheduler calendar",
      }),
    ).toHaveAttribute("href", "/jobs-events-alerts#scheduler-calendar-workspace");

    const manualLane = (
      await screen.findByRole("heading", { name: "Manual planning lane" })
    ).closest("section");
    expect(manualLane).not.toBeNull();

    await user.click(
      within(manualLane as HTMLElement).getByRole("button", { name: "Inspect workspace" }),
    );

    await waitFor(() => {
      expect(
        within(workspacePanel as HTMLElement).getByText("Manual investigation trigger"),
      ).toBeInTheDocument();
      expect(
        within(workspacePanel as HTMLElement).getByText(
          "No recent execution context is visible for this job definition.",
        ),
      ).toBeInTheDocument();
      expect(
        within(workspacePanel as HTMLElement).getByText("No failed run visible"),
      ).toBeInTheDocument();
      expect(
        within(workspacePanel as HTMLElement).getByText(
          "No recent job activity history is visible for this definition.",
        ),
      ).toBeInTheDocument();
      expect(
        within(workspacePanel as HTMLElement).getByText(
          "No failed job activity is currently visible for this definition.",
        ),
      ).toBeInTheDocument();
    });
  });

  it("renders a dedicated job runs workspace with status, timing, and outcome visibility", async () => {
    const { fetchMock } = createMockApi();
    vi.stubGlobal("fetch", fetchMock);

    renderJobsEventsAlertsModuleInShell();

    const jobRunsPanel = (
      await screen.findByRole("heading", { name: "Job runs workspace" })
    ).closest("section");
    expect(jobRunsPanel).not.toBeNull();

    await waitFor(() => {
      expect(
        within(jobRunsPanel as HTMLElement).getByText("Loaded job runs"),
      ).toBeInTheDocument();
      expect(within(jobRunsPanel as HTMLElement).getByText("Completed runs")).toBeInTheDocument();
      expect(
        within(jobRunsPanel as HTMLElement).getByText("Running or queued"),
      ).toBeInTheDocument();
      expect(
        within(jobRunsPanel as HTMLElement).getByText("Failed or timed out"),
      ).toBeInTheDocument();
      expect(
        within(jobRunsPanel as HTMLElement).getByText(/Completed .*2026/),
      ).toBeInTheDocument();
      expect(within(jobRunsPanel as HTMLElement).getByText("Duration 30 sec")).toBeInTheDocument();
      expect(
        within(jobRunsPanel as HTMLElement).getByText("Association rejected"),
      ).toBeInTheDocument();
      expect(within(jobRunsPanel as HTMLElement).getByText("Retries 1/3")).toBeInTheDocument();
    });

    expect(
      within(jobRunsPanel as HTMLElement).getByRole("link", { name: "Open job run detail" }),
    ).toHaveAttribute("href", "/jobs-events-alerts/activity/job_run/job-run-1");
    expect(
      within(jobRunsPanel as HTMLElement).getAllByRole("link", { name: "Open meter detail" })[0],
    ).toHaveAttribute("href", "/meters/meter-1");
  });

  it("renders a dedicated failed runs workspace with failure, retry, and remediation visibility", async () => {
    const { fetchMock } = createMockApi();
    vi.stubGlobal("fetch", fetchMock);

    renderJobsEventsAlertsModuleInShell();

    const failedRunsPanel = (
      await screen.findByRole("heading", { name: "Failed runs workspace" })
    ).closest("section");
    expect(failedRunsPanel).not.toBeNull();

    await waitFor(() => {
      expect(
        within(failedRunsPanel as HTMLElement).getByText("Visible failed runs"),
      ).toBeInTheDocument();
      expect(
        within(failedRunsPanel as HTMLElement).getByText("Retryable failed runs"),
      ).toBeInTheDocument();
      expect(
        within(failedRunsPanel as HTMLElement).getByText("Retry budget exhausted"),
      ).toBeInTheDocument();
      expect(
        within(failedRunsPanel as HTMLElement).getByText("Latest failed transition"),
      ).toBeInTheDocument();
      expect(
        within(failedRunsPanel as HTMLElement).getByText(/Failed .*2026/),
      ).toBeInTheDocument();
      expect(
        within(failedRunsPanel as HTMLElement).getByText(
          "2 retry slots remaining in the current bounded runtime budget.",
        ),
      ).toBeInTheDocument();
      expect(
        within(failedRunsPanel as HTMLElement).getByText("AUTH_FAILED"),
      ).toBeInTheDocument();
    });

    expect(
      within(failedRunsPanel as HTMLElement).getByRole("button", {
        name: "Inspect failed run",
      }),
    ).toBeInTheDocument();
    expect(
      within(failedRunsPanel as HTMLElement).getByRole("link", {
        name: "Open retry detail",
      }),
    ).toHaveAttribute("href", "/jobs-events-alerts/activity/job_run/job-run-1?retryEntrySource=jobs_retry_queue");
  });

  it("shows a round-trip cue on the retry queue after returning from activity detail", async () => {
    const { fetchMock } = createMockApi();
    vi.stubGlobal("fetch", fetchMock);

    renderJobsEventsAlertsModuleInShell({
      initialRetryQueueRoundTripContext: {
        source: "activity_detail_roundtrip",
        activityType: "job_run",
        activityId: "job-run-1",
      },
    });

    const retryPanel = (
      await screen.findByRole("heading", { name: "Job runs + retry queue" })
    ).closest("section");
    expect(retryPanel).not.toBeNull();

    await waitFor(() => {
      expect(
        within(retryPanel as HTMLElement).getByText(
          "Returned from the job run activity detail after bounded remediation review. The retry queue remains available below for the next follow-up.",
        ),
      ).toBeInTheDocument();
      expect(
        within(retryPanel as HTMLElement).getByText("Retry queue round-trip"),
      ).toBeInTheDocument();
      expect(
        within(retryPanel as HTMLElement).getAllByText("Job Run").length,
      ).toBeGreaterThan(0);
      expect(within(retryPanel as HTMLElement).getByText("job-run-1")).toBeInTheDocument();
    });
  });

  it("does not show a round-trip cue on the retry queue during direct entry", async () => {
    const { fetchMock } = createMockApi();
    vi.stubGlobal("fetch", fetchMock);

    renderJobsEventsAlertsModuleInShell();

    const retryPanel = (
      await screen.findByRole("heading", { name: "Job runs + retry queue" })
    ).closest("section");
    expect(retryPanel).not.toBeNull();

    expect(
      within(retryPanel as HTMLElement).queryByText("Retry queue round-trip"),
    ).not.toBeInTheDocument();
    expect(
      within(retryPanel as HTMLElement).queryByText(
        "Returned from the job run activity detail after bounded remediation review. The retry queue remains available below for the next follow-up.",
      ),
    ).not.toBeInTheDocument();
  });

  it("lands in an attention-only monitoring context from the dashboard handoff", async () => {
    const { fetchMock } = createMockApi();
    vi.stubGlobal("fetch", fetchMock);

    renderJobsEventsAlertsModuleInShell({
      initialAttentionContext: {
        source: "dashboard_attention_queue",
        filter: "attention",
      },
    });

    expect(
      await screen.findByText(
        "Dashboard attention handoff opened this monitoring surface with attention-oriented activity preselected.",
      ),
    ).toBeInTheDocument();
    expect(screen.getByText("Attention-only landing from the dashboard handoff. Review alert-like jobs, commands, and events first, or switch back to the full activity list.")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Attention only" })).toBeInTheDocument();

    const activityPanel = (
      await screen.findByRole("heading", { name: "Recent operational activity" })
    ).closest("section");
    expect(activityPanel).not.toBeNull();

    await waitFor(() => {
      expect(
        within(activityPanel as HTMLElement).queryByText("relay-disconnect-template"),
      ).not.toBeInTheDocument();
      expect(
        within(activityPanel as HTMLElement).getAllByText("profile-capture-template").length,
      ).toBeGreaterThan(0);
      expect(within(activityPanel as HTMLElement).getAllByText("Tamper Open").length).toBeGreaterThan(0);
    });
  });

  it("links recent activity rows into the bounded activity detail surface", async () => {
    const { fetchMock } = createMockApi();
    vi.stubGlobal("fetch", fetchMock);

    renderJobsEventsAlertsModuleInShell();

    const activityPanel = (
      await screen.findByRole("heading", { name: "Recent operational activity" })
    ).closest("section");
    expect(activityPanel).not.toBeNull();

    await waitFor(() => {
      expect(
        within(activityPanel as HTMLElement).getAllByRole("link", {
          name: "Open activity detail",
        })[0],
      ).toHaveAttribute(
        "href",
        "/jobs-events-alerts/activity/event/event-1",
      );
      expect(
        within(activityPanel as HTMLElement).getAllByRole("link", {
          name: "Open activity detail",
        })[1],
      ).toHaveAttribute(
        "href",
        "/jobs-events-alerts/activity/command/command-1",
      );
      expect(
        within(activityPanel as HTMLElement).getAllByRole("link", {
          name: "Open meter detail",
        })[0],
      ).toHaveAttribute("href", "/meters/meter-2");
    });
  });

  it("renders a bounded selected activity summary using existing activity data", async () => {
    const { fetchMock } = createMockApi();
    vi.stubGlobal("fetch", fetchMock);
    const user = userEvent.setup();

    renderJobsEventsAlertsModuleInShell();

    const inspectButtons = await screen.findAllByRole("button", {
      name: "Inspect summary",
    });
    await user.click(inspectButtons[1]);

    const summaryPanel = screen
      .getByRole("heading", { name: "Selected activity summary" })
      .closest("section");
    expect(summaryPanel).not.toBeNull();

    await waitFor(() => {
      expect(
        within(summaryPanel as HTMLElement).getByText("profile-capture-template"),
      ).toBeInTheDocument();
      expect(
        within(summaryPanel as HTMLElement).getByText("Command"),
      ).toBeInTheDocument();
      expect(
        within(summaryPanel as HTMLElement).getByRole("link", {
          name: "Open activity detail",
        }),
      ).toHaveAttribute("href", "/jobs-events-alerts/activity/command/command-1");
    });
  });

  it("renders a critical and unacknowledged events workspace with severity, acknowledgement, and meter visibility", async () => {
    const { fetchMock } = createMockApi({
      recentEvents: [
        {
          id: "event-1",
          meter_id: "meter-2",
          event_code: "tamper_open",
          event_name: "Tamper Open",
          severity: "critical",
          event_state: "open",
          occurred_at: "2026-03-31T09:59:00.000Z",
          received_at: "2026-03-31T09:59:30.000Z",
        },
        {
          id: "event-2",
          meter_id: "meter-3",
          event_code: "power_loss",
          event_name: "Power Loss",
          severity: "warning",
          event_state: "open",
          occurred_at: "2026-03-31T09:54:00.000Z",
          received_at: "2026-03-31T09:54:20.000Z",
        },
        {
          id: "event-3",
          meter_id: null,
          event_code: "voltage_restored",
          event_name: "Voltage Restored",
          severity: "warning",
          event_state: "closed",
          occurred_at: "2026-03-31T09:40:00.000Z",
          received_at: "2026-03-31T09:40:20.000Z",
        },
      ],
    });
    vi.stubGlobal("fetch", fetchMock);
    const user = userEvent.setup();

    renderJobsEventsAlertsModuleInShell();

    const urgentEventsPanel = (
      await screen.findByRole("heading", {
        name: "Critical / unacknowledged events workspace",
      })
    ).closest("section");
    expect(urgentEventsPanel).not.toBeNull();

    await waitFor(() => {
      expect(
        within(urgentEventsPanel as HTMLElement).getByText("Urgent events in view"),
      ).toBeInTheDocument();
      expect(
        within(urgentEventsPanel as HTMLElement).getByText("Critical severity"),
      ).toBeInTheDocument();
      expect(
        within(urgentEventsPanel as HTMLElement).getByText("Unacknowledged posture"),
      ).toBeInTheDocument();
      expect(
        within(urgentEventsPanel as HTMLElement).getByText("With affected meter"),
      ).toBeInTheDocument();
      expect(
        within(urgentEventsPanel as HTMLElement).getAllByText("Tamper Open").length,
      ).toBeGreaterThan(0);
      expect(
        within(urgentEventsPanel as HTMLElement).getAllByText("Power Loss").length,
      ).toBeGreaterThan(0);
      expect(
        within(urgentEventsPanel as HTMLElement).getAllByText("Unacknowledged").length,
      ).toBeGreaterThan(0);
      expect(
        within(urgentEventsPanel as HTMLElement).getByText("Critical and unacknowledged"),
      ).toBeInTheDocument();
      expect(
        within(urgentEventsPanel as HTMLElement).getByText(
          "Event acknowledgement posture is derived from `event_state`; open events are treated as unacknowledged in this bounded workspace.",
        ),
      ).toBeInTheDocument();
      expect(
        within(urgentEventsPanel as HTMLElement).getAllByRole("link", {
          name: "Open meter detail",
        })[0],
      ).toHaveAttribute("href", "/meters/meter-2");
    });

    await user.click(
      within(urgentEventsPanel as HTMLElement).getAllByRole("button", {
        name: "Inspect urgent event",
      })[0],
    );

    const summaryPanel = screen
      .getByRole("heading", { name: "Selected activity summary" })
      .closest("section");
    expect(summaryPanel).not.toBeNull();

    await waitFor(() => {
      expect(
        within(summaryPanel as HTMLElement).getByText("Acknowledgement posture"),
      ).toBeInTheDocument();
      expect(
        within(summaryPanel as HTMLElement).getAllByText("Unacknowledged").length,
      ).toBeGreaterThan(0);
      expect(within(summaryPanel as HTMLElement).getByText("tamper_open")).toBeInTheDocument();
      expect(within(summaryPanel as HTMLElement).getByText("Occurred")).toBeInTheDocument();
      expect(within(summaryPanel as HTMLElement).getByText("Received")).toBeInTheDocument();
    });
  });

  it("renders bounded job-run execution detail when a job run is selected", async () => {
    const { fetchMock } = createMockApi();
    vi.stubGlobal("fetch", fetchMock);
    const user = userEvent.setup();

    renderJobsEventsAlertsModuleInShell();

    const inspectButtons = await screen.findAllByRole("button", {
      name: "Inspect summary",
    });
    await user.click(inspectButtons[2]);

    const summaryPanel = screen
      .getByRole("heading", { name: "Selected activity summary" })
      .closest("section");
    expect(summaryPanel).not.toBeNull();

    await waitFor(() => {
      expect(
        within(summaryPanel as HTMLElement).getByText("AUTH_FAILED"),
      ).toBeInTheDocument();
      expect(within(summaryPanel as HTMLElement).getByText("worker-1")).toBeInTheDocument();
      expect(
        within(summaryPanel as HTMLElement).getByText("job-correlation-1"),
      ).toBeInTheDocument();
      expect(within(summaryPanel as HTMLElement).getByText("Started")).toBeInTheDocument();
      expect(within(summaryPanel as HTMLElement).getByText("Completed")).toBeInTheDocument();
      expect(within(summaryPanel as HTMLElement).getByText("30 sec")).toBeInTheDocument();
      expect(
        within(summaryPanel as HTMLElement).getByText(
          "2 retry slots remaining in the current bounded runtime budget.",
        ),
      ).toBeInTheDocument();
      expect(
        within(summaryPanel as HTMLElement).getAllByText("Association rejected").length,
      ).toBeGreaterThan(0);
    });
  });

  it("renders bounded loading states while the monitoring surface is bootstrapping", async () => {
    const { fetchMock } = createMockApi({ delayedResponses: true });
    vi.stubGlobal("fetch", fetchMock);

    renderJobsEventsAlertsModuleInShell();

    expect(
      await screen.findByText("Loading jobs, events, and alerts overview..."),
    ).toBeInTheDocument();
    expect(screen.getByText("Loading scheduler calendar workspace...")).toBeInTheDocument();
    expect(screen.getByText("Loading job definition workspace...")).toBeInTheDocument();
    expect(screen.getByText("Loading job runs workspace...")).toBeInTheDocument();
    expect(screen.getByText("Loading failed runs workspace...")).toBeInTheDocument();
    expect(screen.getByText("Loading job runs and retry queue...")).toBeInTheDocument();
    expect(
      screen.getByText("Loading critical and unacknowledged events workspace..."),
    ).toBeInTheDocument();
    expect(screen.getByText("Loading recent operational activity...")).toBeInTheDocument();
  });

  it("renders bounded empty states when recent jobs, commands, and events are empty", async () => {
    const { fetchMock } = createMockApi({
      jobDefinitions: [],
      jobRuns: [],
      recentCommands: [],
      recentEvents: [],
    });
    vi.stubGlobal("fetch", fetchMock);

    renderJobsEventsAlertsModuleInShell();

    const alertsPanel = (
      await screen.findByRole("heading", { name: "Derived alerts" })
    ).closest("section");
    const retryPanel = screen
      .getByRole("heading", { name: "Job runs + retry queue" })
      .closest("section");
    const schedulerPanel = screen
      .getByRole("heading", { name: "Scheduler calendar workspace" })
      .closest("section");
    const jobDefinitionPanel = screen
      .getByRole("heading", { name: "Job definition workspace" })
      .closest("section");
    const jobRunsPanel = screen
      .getByRole("heading", { name: "Job runs workspace" })
      .closest("section");
    const failedRunsPanel = screen
      .getByRole("heading", { name: "Failed runs workspace" })
      .closest("section");
    const urgentEventsPanel = screen
      .getByRole("heading", { name: "Critical / unacknowledged events workspace" })
      .closest("section");
    const activityPanel = screen
      .getByRole("heading", { name: "Recent operational activity" })
      .closest("section");
    expect(alertsPanel).not.toBeNull();
    expect(retryPanel).not.toBeNull();
    expect(schedulerPanel).not.toBeNull();
    expect(jobDefinitionPanel).not.toBeNull();
    expect(jobRunsPanel).not.toBeNull();
    expect(failedRunsPanel).not.toBeNull();
    expect(urgentEventsPanel).not.toBeNull();
    expect(activityPanel).not.toBeNull();

    await waitFor(() => {
      expect(
        within(schedulerPanel as HTMLElement).getByText(
          "No job schedules are currently visible.",
        ),
      ).toBeInTheDocument();
      expect(
        within(schedulerPanel as HTMLElement).getByText(
          "No recurring schedules are currently visible.",
        ),
      ).toBeInTheDocument();
      expect(
        within(schedulerPanel as HTMLElement).getByText(
          "No manual-only job definitions are currently visible.",
        ),
      ).toBeInTheDocument();
      expect(
        within(jobDefinitionPanel as HTMLElement).getByText(
          "No job definition selected for workspace review.",
        ),
      ).toBeInTheDocument();
      expect(
        within(jobRunsPanel as HTMLElement).getByText("No recent job runs are currently visible."),
      ).toBeInTheDocument();
      expect(
        within(failedRunsPanel as HTMLElement).getByText(
          "No failed job runs are currently visible.",
        ),
      ).toBeInTheDocument();
      expect(
        within(retryPanel as HTMLElement).getByText(
          "No retry-worthy job runs or problematic command execution contexts are currently visible.",
        ),
      ).toBeInTheDocument();
      expect(
        within(urgentEventsPanel as HTMLElement).getByText(
          "No critical or unacknowledged events are currently visible.",
        ),
      ).toBeInTheDocument();
      expect(
        within(alertsPanel as HTMLElement).getByText(
          "No alert-like operational activity is currently visible.",
        ),
      ).toBeInTheDocument();
      expect(
        within(activityPanel as HTMLElement).getByText(
          "No recent operational activity available.",
        ),
      ).toBeInTheDocument();
    });
  });

  it("renders a bounded empty state for an attention-only landing with no alert-like activity", async () => {
    const { fetchMock } = createMockApi({
      jobRuns: [],
      recentCommands: [
        {
          command_id: "command-healthy",
          command_family: "relay_control",
          command_status: "queued",
          meter_id: "meter-2",
          command_template_code: "relay-disconnect-template",
          latest_command_execution_attempt_status: "queued",
          family_specific_outcome_summary: {
            relay_control_operation: "disconnect",
            relay_control_execution_outcome: "pending",
          },
          latest_updated_at: "2026-03-31T09:54:00.000Z",
        },
      ],
      recentEvents: [
        {
          id: "event-closed",
          meter_id: "meter-2",
          event_code: "tamper_open",
          event_name: "Tamper Open",
          severity: "warning",
          event_state: "closed",
          occurred_at: "2026-03-31T09:59:00.000Z",
          received_at: "2026-03-31T09:59:30.000Z",
        },
      ],
    });
    vi.stubGlobal("fetch", fetchMock);

    renderJobsEventsAlertsModuleInShell({
      initialAttentionContext: {
        source: "dashboard_attention_queue",
        filter: "attention",
      },
    });

    const activityPanel = (
      await screen.findByRole("heading", { name: "Recent operational activity" })
    ).closest("section");
    expect(activityPanel).not.toBeNull();

    await waitFor(() => {
      expect(
        within(activityPanel as HTMLElement).getByText(
          "No attention-oriented operational activity is currently visible.",
        ),
      ).toBeInTheDocument();
      expect(
        within(activityPanel as HTMLElement).queryByRole("button", { name: "Inspect summary" }),
      ).not.toBeInTheDocument();
    });
  });

  it("renders a bounded error state when all monitoring sources fail", async () => {
    const { fetchMock } = createMockApi({
      jobDefinitionsStatus: 503,
      jobRunsStatus: 503,
      commandsStatus: 503,
      eventsStatus: 503,
      jobDefinitionsDetail: "Job definitions unavailable.",
      jobRunsDetail: "Job runs unavailable.",
      commandsDetail: "Commands unavailable.",
      eventsDetail: "Events unavailable.",
    });
    vi.stubGlobal("fetch", fetchMock);

    renderJobsEventsAlertsModuleInShell();

    expect(await screen.findByText("Job runs unavailable.")).toBeInTheDocument();
    expect(await screen.findByText("No recent operational activity available.")).toBeInTheDocument();
  });
});
