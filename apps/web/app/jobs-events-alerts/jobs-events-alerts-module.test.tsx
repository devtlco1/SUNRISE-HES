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
  jobRuns = [
    {
      id: "job-run-1",
      job_definition_id: "job-definition-1",
      target_meter_id: "meter-1",
      related_command_id: "command-1",
      scheduled_for: "2026-03-31T09:55:00.000Z",
      available_at: "2026-03-31T09:55:00.000Z",
      claimed_at: "2026-03-31T09:56:00.000Z",
      started_at: "2026-03-31T09:57:00.000Z",
      completed_at: null,
      status: "failed",
      latest_error_message: "Association rejected",
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
  jobRunsStatus = 200,
  commandsStatus = 200,
  eventsStatus = 200,
  jobRunsDetail = "Job runs unavailable.",
  commandsDetail = "Commands unavailable.",
  eventsDetail = "Events unavailable.",
  delayedResponses = false,
}: {
  jobRuns?: Array<Record<string, unknown>>;
  recentCommands?: Array<Record<string, unknown>>;
  recentEvents?: Array<Record<string, unknown>>;
  jobRunsStatus?: number;
  commandsStatus?: number;
  eventsStatus?: number;
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

function renderJobsEventsAlertsModuleInShell() {
  render(
    <OperationalShell
      eyebrow="Operational Pages"
      title="Jobs / Events / Alerts MVP"
      description="Bounded jobs, events, and alerts monitoring"
    >
      {({ authorizedFetch }) => (
        <JobsEventsAlertsModule authorizedFetch={authorizedFetch} />
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

  it("renders bounded loading states while the monitoring surface is bootstrapping", async () => {
    const { fetchMock } = createMockApi({ delayedResponses: true });
    vi.stubGlobal("fetch", fetchMock);

    renderJobsEventsAlertsModuleInShell();

    expect(
      await screen.findByText("Loading jobs, events, and alerts overview..."),
    ).toBeInTheDocument();
    expect(screen.getByText("Loading recent operational activity...")).toBeInTheDocument();
  });

  it("renders bounded empty states when recent jobs, commands, and events are empty", async () => {
    const { fetchMock } = createMockApi({
      jobRuns: [],
      recentCommands: [],
      recentEvents: [],
    });
    vi.stubGlobal("fetch", fetchMock);

    renderJobsEventsAlertsModuleInShell();

    const alertsPanel = (
      await screen.findByRole("heading", { name: "Derived alerts" })
    ).closest("section");
    const activityPanel = screen
      .getByRole("heading", { name: "Recent operational activity" })
      .closest("section");
    expect(alertsPanel).not.toBeNull();
    expect(activityPanel).not.toBeNull();

    await waitFor(() => {
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

  it("renders a bounded error state when all monitoring sources fail", async () => {
    const { fetchMock } = createMockApi({
      jobRunsStatus: 503,
      commandsStatus: 503,
      eventsStatus: 503,
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
