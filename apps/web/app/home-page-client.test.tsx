import { render, screen } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { HomePageClient } from "./home-page-client";

vi.mock("next/navigation", () => ({
  usePathname: () => "/",
}));

function jsonResponse(payload: unknown, status = 200) {
  return new Response(JSON.stringify(payload), {
    status,
    headers: { "Content-Type": "application/json" },
  });
}

describe("HomePageClient", () => {
  beforeEach(() => {
    window.localStorage.setItem("sunrise.web.apiBaseUrl", "http://localhost:8000");
  });

  afterEach(() => {
    vi.unstubAllGlobals();
    window.localStorage.clear();
  });

  it("shows empty dashboard copy when signed in", async () => {
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

    render(<HomePageClient />);

    expect(await screen.findByRole("heading", { name: "Dashboard" })).toBeInTheDocument();
    expect(screen.getByText(/empty workspace/i)).toBeInTheDocument();
  });
});
