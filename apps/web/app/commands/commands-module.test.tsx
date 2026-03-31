import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { CommandsModule } from "./commands-module";

function jsonResponse(payload: unknown, status = 200) {
  return new Response(JSON.stringify(payload), {
    status,
    headers: { "Content-Type": "application/json" },
  });
}

function createMockApi() {
  const fetchMock = vi.fn(async (input: RequestInfo | URL) => {
    const url = input.toString();

    if (url.includes("/api/v1/commands/recent")) {
      const parsedUrl = new URL(url);
      const family = parsedUrl.searchParams.get("family");
      const allItems = [
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
          meter_id: "meter-2",
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
      ];

      const items =
        family === null
          ? allItems
          : allItems.filter((item) => item.command_family === family);

      return jsonResponse({
        total: items.length,
        limit: Number(parsedUrl.searchParams.get("limit") ?? "20"),
        family_filter: family,
        items,
      });
    }

    if (url.endsWith("/api/v1/commands/cmd-profile-1/detail")) {
      return jsonResponse({
        result: {
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
      });
    }

    if (url.endsWith("/api/v1/commands/cmd-relay-1/detail")) {
      return jsonResponse({
        result: {
          command_id: "cmd-relay-1",
          command_family: "relay_control",
          command_category: "remote_disconnect",
          command_status: "succeeded",
          meter_id: "meter-2",
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
      });
    }

    throw new Error(`Unhandled request: ${url}`);
  });

  return { fetchMock };
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

  it("renders recent commands", async () => {
    const { fetchMock } = createMockApi();
    vi.stubGlobal("fetch", fetchMock);

    render(<CommandsModule />);

    expect(await screen.findAllByText("profile-capture-template")).not.toHaveLength(0);
    expect(screen.getAllByText("relay-disconnect-template")).not.toHaveLength(0);
  });

  it("loads bounded command detail when a recent command is selected", async () => {
    const { fetchMock } = createMockApi();
    vi.stubGlobal("fetch", fetchMock);
    const user = userEvent.setup();

    render(<CommandsModule />);

    const relayRow = await screen.findByRole("button", {
      name: /relay-disconnect-template/i,
    });
    await user.click(relayRow);

    const detailPanel = screen.getAllByRole("heading", { name: "Command detail" })[0]
      .closest("section");
    expect(detailPanel).not.toBeNull();
    await waitFor(() => {
      expect(within(detailPanel as HTMLElement).getByText("meter-2")).toBeInTheDocument();
      expect(within(detailPanel as HTMLElement).getByText("runtime-relay-1")).toBeInTheDocument();
    });
  });

  it("renders profile capture and relay control summaries correctly", async () => {
    const { fetchMock } = createMockApi();
    vi.stubGlobal("fetch", fetchMock);

    render(<CommandsModule />);

    expect(await screen.findByText("acknowledged")).toBeInTheDocument();
    expect(screen.getByText("disconnect (succeeded)")).toBeInTheDocument();
  });

  it("does not surface unsupported family actions", async () => {
    const { fetchMock } = createMockApi();
    vi.stubGlobal("fetch", fetchMock);

    render(<CommandsModule />);

    await screen.findByText("Recent commands");
    expect(screen.queryByText(/execute profile capture now/i)).not.toBeInTheDocument();
    expect(screen.queryByText(/execute relay disconnect now/i)).not.toBeInTheDocument();
    expect(screen.queryByText(/on-demand-read-hidden-template/i)).not.toBeInTheDocument();
  });
});
