import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { AuthEntryShell } from "../auth-entry-shell";
import { ForgotPasswordModule } from "./forgot-password-module";

function jsonResponse(payload: unknown, status = 200) {
  return new Response(JSON.stringify(payload), {
    status,
    headers: { "Content-Type": "application/json" },
  });
}

function renderForgotPasswordModule() {
  render(
    <AuthEntryShell
      eyebrow="Auth Entry MVP"
      title="Reset access"
      description="Recover access."
    >
      <ForgotPasswordModule />
    </AuthEntryShell>,
  );
}

describe("ForgotPasswordModule", () => {
  beforeEach(() => {
    window.localStorage.setItem("sunrise.web.apiBaseUrl", "http://localhost:8000");
  });

  afterEach(() => {
    vi.unstubAllGlobals();
    window.localStorage.clear();
  });

  it("renders and submits the bounded forgot-password flow", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async (input: RequestInfo | URL) => {
        const url = input.toString();
        if (url.endsWith("/api/v1/auth/forgot-password")) {
          return jsonResponse({
            message:
              "If an account matches that username or email, reset instructions will be sent through the configured recovery channel.",
          });
        }
        throw new Error(`Unhandled request: ${url}`);
      }),
    );

    renderForgotPasswordModule();

    const user = userEvent.setup();
    await user.type(
      screen.getByLabelText("Username or email"),
      "ops@example.com",
    );
    await user.click(
      screen.getByRole("button", { name: "Send reset instructions" }),
    );

    expect(
      await screen.findByText(/If an account matches that username or email/i),
    ).toBeInTheDocument();
  });

  it("renders an error when forgot-password initiation fails", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async (input: RequestInfo | URL) => {
        const url = input.toString();
        if (url.endsWith("/api/v1/auth/forgot-password")) {
          return jsonResponse(
            { detail: "Unable to start forgot-password flow." },
            503,
          );
        }
        throw new Error(`Unhandled request: ${url}`);
      }),
    );

    renderForgotPasswordModule();

    const user = userEvent.setup();
    await user.type(
      screen.getByLabelText("Username or email"),
      "ops@example.com",
    );
    await user.click(
      screen.getByRole("button", { name: "Send reset instructions" }),
    );

    expect(
      await screen.findByText("Unable to start forgot-password flow."),
    ).toBeInTheDocument();
  });
});
