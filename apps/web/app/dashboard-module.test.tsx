import { render, screen } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { DashboardModule } from "./dashboard-module";
import { OperationalShell } from "./operational-shell";

function jsonResponse(payload: unknown, status = 200) {
  return new Response(JSON.stringify(payload), {
    status,
    headers: { "Content-Type": "application/json" },
  });
}

function renderBlankDashboardInShell() {
  render(
    <OperationalShell
      eyebrow="Sunrise HES"
      title="Dashboard"
      description="Blank operator canvas during frontend rebuild."
    >
      {() => <DashboardModule />}
    </OperationalShell>,
  );
}

describe("DashboardModule", () => {
  beforeEach(() => {
    window.localStorage.setItem("sunrise.web.apiBaseUrl", "http://localhost:8000");
    window.localStorage.setItem("sunrise.web.accessToken", "token-1");
  });

  afterEach(() => {
    vi.unstubAllGlobals();
    window.localStorage.clear();
  });

  it("renders an intentionally empty desk with rebuild notice", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async (input: RequestInfo | URL) => {
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
        throw new Error(`Unhandled request: ${url}`);
      }),
    );

    renderBlankDashboardInShell();

    expect(await screen.findByRole("heading", { name: "Operational desk" })).toBeInTheDocument();
    expect(
      screen.getByText(/controlled rebuild/i),
    ).toBeInTheDocument();
    expect(
      screen.getByRole("link", { name: "Meters (first rebuild target)" }),
    ).toHaveAttribute("href", "/meters");
  });
});
