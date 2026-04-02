import { render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { OperationalShell } from "../../../../operational-shell";
import { ActivityDetailModule } from "./activity-detail-module";

function jsonResponse(payload: unknown, status = 200) {
  return new Response(JSON.stringify(payload), {
    status,
    headers: { "Content-Type": "application/json" },
  });
}

function createMockApi({
  commandDetailStatus = 200,
  commandDetailMessage = "Command detail unavailable.",
  eventDetailStatus = 200,
  eventDetailMessage = "Operational event not found.",
  jobRunStatus = 200,
  jobRunMessage = "Job run unavailable.",
  delayedResponses = false,
}: {
  commandDetailStatus?: number;
  commandDetailMessage?: string;
  eventDetailStatus?: number;
  eventDetailMessage?: string;
  jobRunStatus?: number;
  jobRunMessage?: string;
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
      await new Promise((resolve) => window.setTimeout(resolve, 20));
    }

    if (url.endsWith("/api/v1/commands/command-1/detail")) {
      if (commandDetailStatus !== 200) {
        return jsonResponse({ detail: commandDetailMessage }, commandDetailStatus);
      }
      return jsonResponse({
        result: {
          command_id: "command-1",
          command_family: "profile_capture",
          command_category: "read",
          command_status: "failed",
          meter_id: "meter-1",
          command_template_code: "profile-capture-template",
          latest_command_execution_attempt_id: "attempt-1",
          latest_command_execution_attempt_status: "failed",
          runtime_execution_record_id: "runtime-1",
          family_specific_outcome_summary: {
            terminal_status_category: "rejected",
          },
          orchestration_artifact_present: true,
          terminalization_artifact_present: true,
          execute_now_artifact_present: false,
          created_at: "2026-03-31T10:00:00.000Z",
          latest_updated_at: "2026-03-31T10:05:00.000Z",
          projection_record: {
            command_status: "failed",
            last_error: "Association rejected",
          },
        },
      });
    }

    if (url.endsWith("/api/v1/events/event-1")) {
      if (eventDetailStatus !== 200) {
        return jsonResponse({ detail: eventDetailMessage }, eventDetailStatus);
      }
      return jsonResponse({
        id: "event-1",
        meter_id: "meter-2",
        related_batch_id: "batch-1",
        related_attempt_id: "attempt-9",
        event_code: "tamper_open",
        event_name: "Tamper Open",
        severity: "critical",
        event_state: "open",
        occurred_at: "2026-03-31T10:06:00.000Z",
        received_at: "2026-03-31T10:06:30.000Z",
        raw_payload: { code: "tamper_open" },
        normalized_payload: { source: "test" },
        correlation_id: "event-correlation-1",
      });
    }

    if (url.endsWith("/api/v1/job-runs/job-run-1")) {
      if (jobRunStatus !== 200) {
        return jsonResponse({ detail: jobRunMessage }, jobRunStatus);
      }
      return jsonResponse({
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
        status: "failed",
        started_at: "2026-03-31T09:57:00.000Z",
        completed_at: "2026-03-31T09:58:00.000Z",
        cancelled_at: null,
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
      });
    }

    throw new Error(`Unhandled request: ${url}`);
  });

  return { fetchMock };
}

function renderActivityDetailModuleInShell({
  activityType,
  activityId,
}: {
  activityType: string;
  activityId: string;
}) {
  render(
    <OperationalShell
      eyebrow="Operational Pages"
      title={`Activity ${activityId}`}
      description="Bounded activity detail"
    >
      {({ authorizedFetch }) => (
        <ActivityDetailModule
          activityType={activityType}
          activityId={activityId}
          authorizedFetch={authorizedFetch}
        />
      )}
    </OperationalShell>,
  );
}

describe("ActivityDetailModule", () => {
  beforeEach(() => {
    window.localStorage.setItem("sunrise.web.apiBaseUrl", "http://localhost:8000");
    window.localStorage.setItem("sunrise.web.accessToken", "token-1");
  });

  afterEach(() => {
    vi.unstubAllGlobals();
    window.localStorage.clear();
  });

  it("renders bounded command activity detail with links to existing operational surfaces", async () => {
    const { fetchMock } = createMockApi();
    vi.stubGlobal("fetch", fetchMock);

    renderActivityDetailModuleInShell({
      activityType: "command",
      activityId: "command-1",
    });

    expect(await screen.findByRole("heading", { name: "Activity detail" })).toBeInTheDocument();

    await waitFor(() => {
      expect(screen.getAllByText("profile-capture-template")).not.toHaveLength(0);
      expect(screen.getByText("Profile Capture")).toBeInTheDocument();
      expect(screen.getByText("Projection record")).toBeInTheDocument();
    });

    expect(screen.getByRole("link", { name: "Open meter detail" })).toHaveAttribute(
      "href",
      "/meters/meter-1",
    );
    expect(screen.getByRole("link", { name: "Open commands page" })).toHaveAttribute(
      "href",
      "/commands",
    );
    expect(screen.getByRole("link", { name: "Open remediation context" })).toHaveAttribute(
      "href",
      "/commands?selectedCommandId=command-1&retrySource=jobs_retry_queue&retryItemType=command&retryReason=rejected&retryContext=Meter+meter-1.+Latest+attempt+Failed.&retryOriginActivityType=command&retryOriginActivityId=command-1",
    );
  });

  it("renders bounded job-run activity detail with linked command and payload context", async () => {
    const { fetchMock } = createMockApi();
    vi.stubGlobal("fetch", fetchMock);

    renderActivityDetailModuleInShell({
      activityType: "job_run",
      activityId: "job-run-1",
    });

    expect(await screen.findByText("job_run")).toBeInTheDocument();
    expect(screen.getByText("job-run-1")).toBeInTheDocument();
    expect(screen.getByText("command-1")).toBeInTheDocument();
    expect(screen.getByText("Result summary")).toBeInTheDocument();
    expect(screen.getAllByText("Failed")).not.toHaveLength(0);
    expect(screen.getByRole("link", { name: "Open remediation context" })).toHaveAttribute(
      "href",
      "/commands?selectedCommandId=command-1&retrySource=jobs_retry_queue&retryItemType=job_run&retryReason=Association+rejected&retryContext=Meter+meter-1.+Retries+1%2F3.&retryOriginActivityType=job_run&retryOriginActivityId=job-run-1",
    );
  });

  it("renders bounded event activity detail with meter linkage when available", async () => {
    const { fetchMock } = createMockApi();
    vi.stubGlobal("fetch", fetchMock);

    renderActivityDetailModuleInShell({
      activityType: "event",
      activityId: "event-1",
    });

    expect(await screen.findByText("tamper_open")).toBeInTheDocument();
    expect(screen.getByText("critical / open")).toBeInTheDocument();
    expect(screen.getByText("Normalized payload")).toBeInTheDocument();
    expect(screen.getAllByText("Critical Open")).not.toHaveLength(0);
    expect(screen.getByRole("link", { name: "Open meter detail" })).toHaveAttribute(
      "href",
      "/meters/meter-2",
    );
  });

  it("renders bounded loading states while activity detail is bootstrapping", async () => {
    const { fetchMock } = createMockApi({ delayedResponses: true });
    vi.stubGlobal("fetch", fetchMock);

    renderActivityDetailModuleInShell({
      activityType: "command",
      activityId: "command-1",
    });

    expect(await screen.findByText("Loading activity detail...")).toBeInTheDocument();
    expect(screen.getByText("Loading related operational surfaces...")).toBeInTheDocument();
  });

  it("renders a bounded not-found state when the activity detail endpoint returns an error", async () => {
    const { fetchMock } = createMockApi({
      eventDetailStatus: 404,
      eventDetailMessage: "Operational event not found.",
    });
    vi.stubGlobal("fetch", fetchMock);

    renderActivityDetailModuleInShell({
      activityType: "event",
      activityId: "event-1",
    });

    expect(await screen.findByText("Operational event not found.")).toBeInTheDocument();
  });
});
