import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { OperationalShell } from "./operational-shell";

function jsonResponse(payload: unknown, status = 200) {
  return new Response(JSON.stringify(payload), {
    status,
    headers: { "Content-Type": "application/json" },
  });
}

describe("OperationalShell", () => {
  beforeEach(() => {
    window.localStorage.setItem("sunrise.web.apiBaseUrl", "http://localhost:8000");
  });

  afterEach(() => {
    vi.unstubAllGlobals();
    window.localStorage.clear();
  });

  it("shows the session gate when no session is available", async () => {
    const fetchMock = vi.fn();
    vi.stubGlobal("fetch", fetchMock);

    render(
      <OperationalShell eyebrow="Operations" title="Dashboard" description="Shell test">
        {() => <div>Protected child</div>}
      </OperationalShell>,
    );

    expect(await screen.findByRole("heading", { name: "Session required" })).toBeInTheDocument();
    expect(screen.queryByText("Protected child")).not.toBeInTheDocument();
    expect(screen.getAllByText("Sunrise HES").length).toBeGreaterThan(0);
    expect(screen.getByRole("link", { name: "Sign in" })).toHaveAttribute("href", "/login");
    expect(fetchMock).not.toHaveBeenCalled();
  });

  it("shows an invalid session state when auth/me rejects the stored token", async () => {
    window.localStorage.setItem("sunrise.web.accessToken", "stale-token");
    vi.stubGlobal(
      "fetch",
      vi.fn(async (input: RequestInfo | URL) => {
        const url = input.toString();
        if (url.endsWith("/api/v1/auth/me")) {
          return jsonResponse({ detail: "Not authenticated." }, 401);
        }
        throw new Error(`Unhandled request: ${url}`);
      }),
    );

    render(
      <OperationalShell eyebrow="Operations" title="Dashboard" description="Shell test">
        {() => <div>Protected child</div>}
      </OperationalShell>,
    );

    expect(
      await screen.findByText("Session is missing or no longer valid."),
    ).toBeInTheDocument();
    expect(screen.queryByText("Protected child")).not.toBeInTheDocument();
  });

  it("keeps dashboard and meters first-class in the navigation", async () => {
    window.localStorage.setItem("sunrise.web.accessToken", "token-1");
    window.localStorage.setItem(
      "sunrise.web.currentUser",
      JSON.stringify({
        id: "user-1",
        username: "ops.user",
        email: "ops@example.com",
        full_name: "Ops User",
        status: "active",
        is_superuser: true,
      }),
    );
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
      <OperationalShell
        eyebrow="Operations"
        title="Meters"
        description="Shell test"
        currentMeterId="meter-1"
      >
        {() => <div>Protected child</div>}
      </OperationalShell>,
    );

    expect(await screen.findByText("Protected child")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Dashboard" })).toHaveAttribute("href", "/");
    expect(screen.getByRole("link", { name: "Meters" })).toHaveAttribute("href", "/meters");
    expect(screen.getByRole("link", { name: "Current meter" })).toHaveAttribute(
      "href",
      "/meters/meter-1",
    );
    expect(screen.getByText("Signed in")).toBeInTheDocument();
  });

  it("clears the stored session snapshot on logout", async () => {
    window.localStorage.setItem("sunrise.web.accessToken", "token-1");
    window.localStorage.setItem(
      "sunrise.web.currentUser",
      JSON.stringify({
        id: "user-1",
        username: "ops.user",
        email: "ops@example.com",
        full_name: "Ops User",
        status: "active",
        is_superuser: true,
      }),
    );
    const fetchMock = vi.fn(async () =>
      jsonResponse({
        id: "user-1",
        username: "ops.user",
        email: "ops@example.com",
        full_name: "Ops User",
        status: "active",
        is_superuser: true,
      }),
    );
    vi.stubGlobal("fetch", fetchMock);

    render(
      <OperationalShell eyebrow="Operations" title="Dashboard" description="Shell test">
        {() => <div>Protected child</div>}
      </OperationalShell>,
    );

    const user = userEvent.setup();
    await user.click(await screen.findByRole("button", { name: "Sign out" }));

    await waitFor(() => {
      expect(screen.getByRole("heading", { name: "Session required" })).toBeInTheDocument();
    });
    expect(window.localStorage.getItem("sunrise.web.accessToken")).toBeNull();
    expect(window.localStorage.getItem("sunrise.web.currentUser")).toBeNull();
  });
});
