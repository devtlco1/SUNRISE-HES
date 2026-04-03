import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { OperationalShell } from "../operational-shell";
import { AuditCenterModule } from "./audit-center-module";

function jsonResponse(payload: unknown, status = 200) {
  return new Response(JSON.stringify(payload), {
    status,
    headers: { "Content-Type": "application/json" },
  });
}

function createMockApi({
  auditLogs = [
    {
      id: "audit-1",
      created_at: "2026-04-03T10:00:00.000Z",
      actor_user_id: "user-1",
      actor_username: "ops.user",
      actor_full_name: "Ops User",
      action: "auth.login.success",
      entity_type: "auth",
      entity_id: null,
      request_id: "req-1",
      ip_address: "127.0.0.1",
      description: "Authentication succeeded.",
      payload: {
        outcome: "success",
        http: {
          method: "POST",
          path: "/api/v1/auth/login",
          user_agent: "vitest",
        },
        details: {
          username: "ops.user",
        },
      },
    },
    {
      id: "audit-2",
      created_at: "2026-04-03T09:45:00.000Z",
      actor_user_id: "user-2",
      actor_username: "ops.trace",
      actor_full_name: "Ops Trace",
      action: "commands.approvals.approve",
      entity_type: "commands",
      entity_id: "command-1",
      request_id: "req-2",
      ip_address: "127.0.0.2",
      description: "Command approval failed.",
      payload: {
        outcome: "failure",
        http: {
          method: "POST",
          path: "/api/v1/commands/command-1/approvals/approve",
          user_agent: "vitest",
        },
        details: {
          reason: "validation_error",
        },
      },
    },
  ],
  auditLogsStatus = 200,
  auditLogsDetail = "Audit logs unavailable.",
}: {
  auditLogs?: Array<Record<string, unknown>>;
  auditLogsStatus?: number;
  auditLogsDetail?: string;
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

    if (url.includes("/api/v1/audit-logs?")) {
      if (auditLogsStatus !== 200) {
        return jsonResponse({ detail: auditLogsDetail }, auditLogsStatus);
      }

      const parsedUrl = new URL(url);
      const actorFilter = parsedUrl.searchParams.get("actor")?.toLowerCase() ?? "";
      const actionFilter = parsedUrl.searchParams.get("action")?.toLowerCase() ?? "";
      const entityTypeFilter = parsedUrl.searchParams.get("entity_type")?.toLowerCase() ?? "";
      const outcomeFilter = parsedUrl.searchParams.get("outcome")?.toLowerCase() ?? "";

      const filteredItems = auditLogs.filter((item) => {
        const actorMatch =
          actorFilter.length === 0 ||
          `${item.actor_full_name ?? ""} ${item.actor_username ?? ""}`
            .toLowerCase()
            .includes(actorFilter);
        const actionMatch =
          actionFilter.length === 0 ||
          String(item.action ?? "")
            .toLowerCase()
            .includes(actionFilter);
        const entityMatch =
          entityTypeFilter.length === 0 ||
          String(item.entity_type ?? "")
            .toLowerCase()
            .includes(entityTypeFilter);
        const outcomeMatch =
          outcomeFilter.length === 0 ||
          String((item.payload as { outcome?: string } | undefined)?.outcome ?? "")
            .toLowerCase()
            .includes(outcomeFilter);
        return actorMatch && actionMatch && entityMatch && outcomeMatch;
      });

      return jsonResponse({
        total: filteredItems.length,
        items: filteredItems,
      });
    }

    throw new Error(`Unhandled request: ${url}`);
  });

  return { fetchMock };
}

function renderAuditCenterModuleInShell() {
  render(
    <OperationalShell
      eyebrow="Operational Traceability"
      title="Audit Center MVP"
      description="Bounded audit center"
    >
      {({ authorizedFetch }) => <AuditCenterModule authorizedFetch={authorizedFetch} />}
    </OperationalShell>,
  );
}

describe("AuditCenterModule", () => {
  beforeEach(() => {
    window.localStorage.setItem("sunrise.web.apiBaseUrl", "http://localhost:8000");
    window.localStorage.setItem("sunrise.web.accessToken", "token-1");
  });

  afterEach(() => {
    vi.unstubAllGlobals();
    window.localStorage.clear();
  });

  it("renders the audit center inside the shared shell", async () => {
    const { fetchMock } = createMockApi();
    vi.stubGlobal("fetch", fetchMock);

    renderAuditCenterModuleInShell();

    expect(await screen.findByRole("link", { name: "Audit Center" })).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "Audit Center MVP" })).toBeInTheDocument();
    expect(
      await screen.findByRole("heading", { name: "Audit traceability center" }),
    ).toBeInTheDocument();

    await waitFor(() => {
      expect(screen.getByText("Visible audit records")).toBeInTheDocument();
      expect(screen.getByText("Actors represented")).toBeInTheDocument();
      expect(screen.getByText("Actions represented")).toBeInTheDocument();
      expect(screen.getByText("Failure outcomes")).toBeInTheDocument();
      expect(screen.getByText("Audit feed")).toBeInTheDocument();
      expect(screen.getByText("Authentication succeeded.")).toBeInTheDocument();
      expect(screen.getByText("Command approval failed.")).toBeInTheDocument();
      expect(screen.getByText("Ops Trace")).toBeInTheDocument();
      expect(screen.getAllByText("Failure")).not.toHaveLength(0);
    });
  });

  it("applies bounded actor and outcome filters to the audit feed", async () => {
    const { fetchMock } = createMockApi();
    vi.stubGlobal("fetch", fetchMock);
    const user = userEvent.setup();

    renderAuditCenterModuleInShell();

    await user.type(await screen.findByRole("searchbox", { name: "Actor filter" }), "Ops Trace");
    await user.selectOptions(screen.getByRole("combobox", { name: "Outcome filter" }), "failure");
    await user.click(screen.getByRole("button", { name: "Apply filters" }));

    const auditFeedPanel = screen.getByRole("heading", { name: "Audit feed" }).closest("section");
    expect(auditFeedPanel).not.toBeNull();

    await waitFor(() => {
      expect(within(auditFeedPanel as HTMLElement).getByText("Ops Trace")).toBeInTheDocument();
      expect(
        within(auditFeedPanel as HTMLElement).getByText("Command approval failed."),
      ).toBeInTheDocument();
      expect(
        within(auditFeedPanel as HTMLElement).queryByText("Authentication succeeded."),
      ).not.toBeInTheDocument();
      expect(screen.getByText("Actor Ops Trace")).toBeInTheDocument();
      expect(screen.getByText("Outcome Failure")).toBeInTheDocument();
    });
  });

  it("renders a bounded empty state when filters return no audit rows", async () => {
    const { fetchMock } = createMockApi();
    vi.stubGlobal("fetch", fetchMock);
    const user = userEvent.setup();

    renderAuditCenterModuleInShell();

    await user.type(await screen.findByRole("searchbox", { name: "Entity type filter" }), "meters");
    await user.click(screen.getByRole("button", { name: "Apply filters" }));

    await waitFor(() => {
      expect(
        screen.getByText("No audit records match the current bounded query"),
      ).toBeInTheDocument();
      expect(
        screen.getByText("Adjust or clear the current filters to restore persisted traceability rows."),
      ).toBeInTheDocument();
    });
  });

  it("renders a bounded error state when the audit endpoint fails", async () => {
    const { fetchMock } = createMockApi({
      auditLogsStatus: 503,
      auditLogsDetail: "Audit logs unavailable.",
    });
    vi.stubGlobal("fetch", fetchMock);

    renderAuditCenterModuleInShell();

    expect(await screen.findByText("Audit logs unavailable.")).toBeInTheDocument();
  });
});
