import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { SessionProvider } from "../session-provider";
import { LoginModule } from "./login-module";

function jsonResponse(payload: unknown, status = 200) {
  return new Response(JSON.stringify(payload), {
    status,
    headers: { "Content-Type": "application/json" },
  });
}

describe("LoginModule", () => {
  beforeEach(() => {
    window.localStorage.setItem("sunrise.web.apiBaseUrl", "http://localhost:8000");
  });

  afterEach(() => {
    vi.unstubAllGlobals();
    window.localStorage.clear();
  });

  it("submits credentials through the session login API", async () => {
    const onLoginSuccess = vi.fn();
    const fetchMock = vi.fn(async (input: RequestInfo | URL) => {
      const url = input.toString();
      if (url.endsWith("/api/v1/auth/login")) {
        return jsonResponse({
          access_token: "token-1",
          token_type: "bearer",
          expires_in: 1800,
          user: {
            id: "user-1",
            username: "ops.user",
            email: "ops@example.com",
            full_name: "Ops User",
            status: "active",
            is_superuser: true,
          },
        });
      }
      throw new Error(`Unhandled request: ${url}`);
    });
    vi.stubGlobal("fetch", fetchMock);

    render(
      <SessionProvider>
        <LoginModule onLoginSuccess={onLoginSuccess} />
      </SessionProvider>,
    );

    const user = userEvent.setup();
    await user.type(screen.getByLabelText(/username or email/i), "ops@example.com");
    await user.type(screen.getByLabelText(/^password$/i), "secret");
    await user.click(screen.getByRole("button", { name: "Sign in" }));

    expect(await screen.findByText(/signed in as ops\.user/i)).toBeInTheDocument();
    expect(onLoginSuccess).toHaveBeenCalled();
  });
});
