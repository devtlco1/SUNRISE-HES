import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { WorkspaceShell } from "./workspace-shell";

vi.mock("next/navigation", () => ({
  usePathname: () => "/",
}));

function jsonResponse(payload: unknown, status = 200) {
  return new Response(JSON.stringify(payload), {
    status,
    headers: { "Content-Type": "application/json" },
  });
}

describe("WorkspaceShell", () => {
  beforeEach(() => {
    window.localStorage.setItem("sunrise.web.apiBaseUrl", "http://localhost:8000");
  });

  afterEach(() => {
    vi.unstubAllGlobals();
    window.localStorage.clear();
  });

  it("shows sign-in in header when there is no session", async () => {
    const fetchMock = vi.fn();
    vi.stubGlobal("fetch", fetchMock);

    render(
      <WorkspaceShell>
        <p>Inner</p>
      </WorkspaceShell>,
    );

    expect(await screen.findByRole("link", { name: "Sign in" })).toHaveAttribute("href", "/login");
    expect(screen.getByRole("navigation", { name: "Primary" })).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Dashboard" })).toHaveAttribute("href", "/");
    expect(screen.getByRole("link", { name: "Meters" })).toHaveAttribute("href", "/meters");
    expect(fetchMock).not.toHaveBeenCalled();
  });

  it("shows user email and sign out when authenticated", async () => {
    window.localStorage.setItem("sunrise.web.accessToken", "token-1");
    vi.stubGlobal(
      "fetch",
      vi.fn(async () =>
        jsonResponse({
          id: "user-1",
          username: "ops.user",
          email: "ops@example.com",
          full_name: "Ops User",
          status: "active",
          is_superuser: true,
        }),
      ),
    );

    render(
      <WorkspaceShell>
        <p>Inner</p>
      </WorkspaceShell>,
    );

    expect(await screen.findByText("ops@example.com")).toBeInTheDocument();
    expect(screen.getByText("Inner")).toBeInTheDocument();

    const user = userEvent.setup();
    await user.click(screen.getByRole("button", { name: "Sign out" }));

    await waitFor(() => {
      expect(window.localStorage.getItem("sunrise.web.accessToken")).toBeNull();
    });
  });

  it("renders footer", async () => {
    vi.stubGlobal("fetch", vi.fn());
    render(
      <WorkspaceShell>
        <span>Content</span>
      </WorkspaceShell>,
    );

    expect(await screen.findByRole("contentinfo")).toBeInTheDocument();
    expect(screen.getByText("Operational workspace")).toBeInTheDocument();
  });
});
