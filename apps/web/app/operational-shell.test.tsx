import { render, screen, waitFor } from "@testing-library/react";
import { act, type ReactElement } from "react";
import { hydrateRoot } from "react-dom/client";
import { renderToString } from "react-dom/server";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { OperationalShell } from "./operational-shell";

function jsonResponse(payload: unknown, status = 200) {
  return new Response(JSON.stringify(payload), {
    status,
    headers: { "Content-Type": "application/json" },
  });
}

async function expectNoHydrationMismatch(ui: ReactElement) {
  const container = document.createElement("div");
  container.innerHTML = renderToString(ui);
  document.body.appendChild(container);

  const consoleErrorSpy = vi.spyOn(console, "error").mockImplementation(() => {});

  await act(async () => {
    hydrateRoot(container, ui);
    await Promise.resolve();
  });

  expect(
    consoleErrorSpy.mock.calls.some(([value]) => {
      const message = String(value);
      return (
        message.includes("Hydration failed") ||
        message.includes("didn't match") ||
        message.includes("server rendered text didn't match")
      );
    }),
  ).toBe(false);

  consoleErrorSpy.mockRestore();
  container.remove();
}

describe("OperationalShell", () => {
  beforeEach(() => {
    window.localStorage.setItem("sunrise.web.apiBaseUrl", "http://localhost:8000");
  });

  afterEach(() => {
    vi.unstubAllGlobals();
    window.localStorage.clear();
  });

  it("shows the bounded session gate when no session is available", async () => {
    const fetchMock = vi.fn();
    vi.stubGlobal("fetch", fetchMock);

    render(
      <OperationalShell
        eyebrow="Operational Pages"
        title="Commands"
        description="Shell test"
      >
        {() => <div>Protected child</div>}
      </OperationalShell>,
    );

    expect(await screen.findByText("Session required")).toBeInTheDocument();
    expect(screen.queryByText("Protected child")).not.toBeInTheDocument();
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
      <OperationalShell
        eyebrow="Operational Pages"
        title="Commands"
        description="Shell test"
      >
        {() => <div>Protected child</div>}
      </OperationalShell>,
    );

    expect(
      await screen.findByText("Session is missing or no longer valid."),
    ).toBeInTheDocument();
    expect(screen.queryByText("Protected child")).not.toBeInTheDocument();
  });

  it("bootstraps the stored session once using the stored API base URL", async () => {
    window.localStorage.setItem("sunrise.web.apiBaseUrl", "http://localhost:9000/");
    window.localStorage.setItem("sunrise.web.accessToken", "token-1");

    const fetchMock = vi.fn(async (input: RequestInfo | URL) => {
      const url = input.toString();
      if (url === "http://localhost:9000/api/v1/auth/me") {
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
    });
    vi.stubGlobal("fetch", fetchMock);

    render(
      <OperationalShell
        eyebrow="Operational Pages"
        title="Commands"
        description="Shell test"
      >
        {() => <div>Protected child</div>}
      </OperationalShell>,
    );

    expect(await screen.findByText("Protected child")).toBeInTheDocument();
    await waitFor(() => {
      expect(fetchMock).toHaveBeenCalledTimes(1);
    });
    expect(fetchMock).toHaveBeenCalledWith(
      "http://localhost:9000/api/v1/auth/me",
      expect.objectContaining({
        cache: "no-store",
        headers: {
          Authorization: "Bearer token-1",
        },
      }),
    );
  });

  it("hydrates the shell without mismatching stored API base URL text", async () => {
    window.localStorage.setItem("sunrise.web.apiBaseUrl", "http://localhost:9000/");
    const fetchMock = vi.fn();
    vi.stubGlobal("fetch", fetchMock);

    const ui = (
      <OperationalShell
        eyebrow="Operational Pages"
        title="Commands"
        description="Shell test"
      >
        {() => <div>Protected child</div>}
      </OperationalShell>
    );

    await expectNoHydrationMismatch(ui);
    expect(fetchMock).not.toHaveBeenCalled();
  });
});
