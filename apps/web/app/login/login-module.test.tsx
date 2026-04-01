import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { AuthEntryShell } from "../auth-entry-shell";
import { LoginModule } from "./login-module";

function jsonResponse(payload: unknown, status = 200) {
  return new Response(JSON.stringify(payload), {
    status,
    headers: { "Content-Type": "application/json" },
  });
}

function renderLoginModule(onLoginSuccess?: () => void) {
  render(
    <AuthEntryShell
      eyebrow="Auth Entry MVP"
      title="Welcome back"
      description="Sign in to access the platform."
    >
      <LoginModule onLoginSuccess={onLoginSuccess} />
    </AuthEntryShell>,
  );
}

describe("LoginModule", () => {
  beforeEach(() => {
    window.localStorage.setItem("sunrise.web.apiBaseUrl", "http://localhost:8000");
  });

  afterEach(() => {
    vi.unstubAllGlobals();
    window.localStorage.clear();
  });

  it("renders and submits the bounded login flow", async () => {
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

    renderLoginModule(onLoginSuccess);
    expect(fetchMock).not.toHaveBeenCalled();
    expect(
      screen.getByText("Connectivity is checked when you submit the login form."),
    ).toBeInTheDocument();

    const user = userEvent.setup();
    await user.type(screen.getByLabelText("Username or email"), "ops.user");
    await user.type(
      screen.getByLabelText("Password"),
      "ChangeThisPassword123!",
    );
    await user.click(screen.getByRole("button", { name: "Sign in" }));

    expect(await screen.findByText("Signed in as ops.user.")).toBeInTheDocument();
    expect(onLoginSuccess).toHaveBeenCalledTimes(1);
  });

  it("renders an error when login fails", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async (input: RequestInfo | URL) => {
        const url = input.toString();
        if (url.endsWith("/api/v1/auth/login")) {
          return jsonResponse(
            { detail: "Invalid username/email or password." },
            401,
          );
        }
        throw new Error(`Unhandled request: ${url}`);
      }),
    );

    renderLoginModule();

    const user = userEvent.setup();
    await user.type(screen.getByLabelText("Username or email"), "ops.user");
    await user.type(
      screen.getByLabelText("Password"),
      "WrongPassword123!",
    );
    await user.click(screen.getByRole("button", { name: "Sign in" }));

    expect(
      await screen.findByText("Invalid username/email or password."),
    ).toBeInTheDocument();
  });

  it("shows a clear bounded error when the backend API is unreachable", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async (input: RequestInfo | URL) => {
        const url = input.toString();
        if (url.endsWith("/api/v1/auth/login")) {
          throw new TypeError("Failed to fetch");
        }
        throw new Error(`Unhandled request: ${url}`);
      }),
    );

    renderLoginModule();

    const user = userEvent.setup();
    await user.type(screen.getByLabelText("Username or email"), "ops.user");
    await user.type(
      screen.getByLabelText("Password"),
      "ChangeThisPassword123!",
    );
    await user.click(screen.getByRole("button", { name: "Sign in" }));

    expect(
      await screen.findAllByText(
        "Cannot reach API at http://localhost:8000. Start the backend server or update API base URL.",
      ),
    ).not.toHaveLength(0);
    expect(
      screen.queryByText("Invalid username/email or password."),
    ).not.toBeInTheDocument();
  });

  it("does not perform a health probe during login page mount", () => {
    const fetchMock = vi.fn();
    vi.stubGlobal("fetch", fetchMock);

    renderLoginModule();

    expect(fetchMock).not.toHaveBeenCalled();
    expect(
      screen.getByText("Connectivity is checked when you submit the login form."),
    ).toBeInTheDocument();
  });
});
