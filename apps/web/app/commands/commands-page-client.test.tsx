import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { CommandsPageClient } from "./commands-page-client";

vi.mock("next/navigation", () => ({
  usePathname: () => "/commands",
}));

function jsonResponse(payload: unknown, status = 200) {
  return new Response(JSON.stringify(payload), {
    status,
    headers: { "Content-Type": "application/json" },
  });
}

const userPayload = {
  id: "user-1",
  username: "ops.user",
  email: "ops@example.com",
  full_name: "Ops User",
  status: "active",
  is_superuser: true,
};

const recentItem = {
  command_id: "cccccccc-cccc-cccc-cccc-cccccccccccc",
  command_family: "on_demand_read",
  command_category: "on_demand_read",
  command_status: "succeeded",
  approval_status: "not_required",
  approval_reviewed_at: null,
  approval_notes: null,
  meter_id: "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa",
  command_template_code: "ODR-1",
  latest_command_execution_attempt_id: null,
  latest_command_execution_attempt_status: "succeeded",
  runtime_execution_record_id: null,
  family_specific_outcome_summary: {},
  orchestration_artifact_present: false,
  terminalization_artifact_present: false,
  execute_now_artifact_present: false,
  created_at: "2026-04-05T12:00:00.000Z",
  latest_updated_at: "2026-04-05T12:01:00.000Z",
};

describe("CommandsPageClient", () => {
  beforeEach(() => {
    window.localStorage.setItem("sunrise.web.apiBaseUrl", "http://localhost:8000");
  });

  afterEach(() => {
    vi.unstubAllGlobals();
    window.localStorage.clear();
  });

  it("renders commands operations layout when APIs succeed", async () => {
    window.localStorage.setItem("sunrise.web.accessToken", "token-1");
    vi.stubGlobal(
      "fetch",
      vi.fn(async (input: RequestInfo | URL) => {
        const u = input.toString();
        if (u.includes("/api/v1/auth/me")) {
          return jsonResponse(userPayload);
        }
        if (u.includes("/api/v1/commands/recent")) {
          return jsonResponse({
            total: 1,
            limit: 100,
            family_filter: null,
            approval_filter: null,
            items: [recentItem],
          });
        }
        if (u.includes("/api/v1/commands/approvals/pending")) {
          return jsonResponse({
            total: 0,
            limit: 50,
            family_filter: null,
            approval_filter: "submitted_for_approval",
            items: [],
          });
        }
        if (u.includes("/api/v1/gis-lite/entities")) {
          return jsonResponse({
            total: 1,
            items: [
              {
                meter_id: "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa",
                meter_serial_number: "SN-CMD-1",
              },
            ],
          });
        }
        return jsonResponse({ detail: "unmocked" }, 404);
      }),
    );

    render(<CommandsPageClient />);

    expect(await screen.findByRole("heading", { name: "Commands" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Request commands" })).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "Command registry" })).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "Pending approvals" })).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "Execution issues" })).toBeInTheDocument();

    expect(await screen.findByRole("link", { name: "SN-CMD-1" })).toHaveAttribute(
      "href",
      "/meters/aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa",
    );

    const pendingPanel = screen.getByRole("heading", { name: "Pending approvals" }).closest("section");
    expect(pendingPanel).toBeTruthy();
    expect(within(pendingPanel!).getByText("None awaiting approval.")).toBeInTheDocument();
  });

  it("surfaces approve and reject for commands awaiting approval", async () => {
    const user = userEvent.setup();
    const pendingItem = {
      ...recentItem,
      command_id: "dddddddd-dddd-dddd-dddd-dddddddddddd",
      approval_status: "submitted_for_approval",
      command_status: "pending",
    };
    window.localStorage.setItem("sunrise.web.accessToken", "token-1");
    vi.stubGlobal(
      "fetch",
      vi.fn(async (input: RequestInfo | URL) => {
        const u = input.toString();
        if (u.includes("/api/v1/auth/me")) {
          return jsonResponse(userPayload);
        }
        if (u.includes("/api/v1/commands/recent")) {
          return jsonResponse({
            total: 0,
            limit: 100,
            family_filter: null,
            approval_filter: null,
            items: [],
          });
        }
        if (u.includes("/api/v1/commands/approvals/pending")) {
          return jsonResponse({
            total: 1,
            limit: 50,
            family_filter: null,
            approval_filter: "submitted_for_approval",
            items: [pendingItem],
          });
        }
        if (u.includes("/api/v1/gis-lite/entities")) {
          return jsonResponse({ total: 0, items: [] });
        }
        return jsonResponse({ detail: "unmocked" }, 404);
      }),
    );

    render(<CommandsPageClient />);

    expect(await screen.findByRole("button", { name: "Approve" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Reject" })).toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: "Approve" }));
    expect(await screen.findByRole("heading", { name: "Approve command" })).toBeInTheDocument();
  });
});
