"use client";

import Link from "next/link";
import {
  useCallback,
  useEffect,
  useState,
  type FormEvent,
  type ReactNode,
} from "react";

export type AuthorizedFetch = <T>(
  path: string,
  init?: RequestInit,
) => Promise<T>;

type CurrentUser = {
  id: string;
  username: string;
  email: string;
  full_name: string;
  status: string;
  is_superuser: boolean;
};

type LoginResponse = {
  access_token: string;
  token_type: string;
  expires_in: number;
  user: CurrentUser;
};

type OperationalShellRenderProps = {
  authorizedFetch: AuthorizedFetch;
  apiBaseUrl: string;
  currentUser: CurrentUser;
};

const ACCESS_TOKEN_STORAGE_KEY = "sunrise.web.accessToken";
const API_BASE_URL_STORAGE_KEY = "sunrise.web.apiBaseUrl";
const DEFAULT_API_BASE_URL =
  process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000";

function buildApiUrl(apiBaseUrl: string, path: string): string {
  return `${apiBaseUrl.replace(/\/$/, "")}${path}`;
}

type OperationalShellProps = {
  eyebrow: string;
  title: string;
  description: string;
  currentMeterId?: string;
  children: (props: OperationalShellRenderProps) => ReactNode;
};

export function OperationalShell({
  eyebrow,
  title,
  description,
  currentMeterId,
  children,
}: OperationalShellProps) {
  const [apiBaseUrl, setApiBaseUrl] = useState(DEFAULT_API_BASE_URL);
  const [accessToken, setAccessToken] = useState("");
  const [currentUser, setCurrentUser] = useState<CurrentUser | null>(null);
  const [loginUsername, setLoginUsername] = useState("");
  const [loginPassword, setLoginPassword] = useState("");
  const [shellError, setShellError] = useState<string | null>(null);
  const [shellSuccess, setShellSuccess] = useState<string | null>(null);
  const [isCheckingSession, setIsCheckingSession] = useState(true);
  const [isAuthenticating, setIsAuthenticating] = useState(false);

  const authorizedFetch = useCallback<AuthorizedFetch>(
    async <T,>(path: string, init?: RequestInit): Promise<T> => {
      const headers = new Headers(init?.headers);
      if (init?.body && !headers.has("Content-Type")) {
        headers.set("Content-Type", "application/json");
      }
      if (accessToken) {
        headers.set("Authorization", `Bearer ${accessToken}`);
      }

      const response = await fetch(buildApiUrl(apiBaseUrl, path), {
        ...init,
        headers,
        cache: "no-store",
      });

      if (!response.ok) {
        let errorMessage = `Request failed with status ${response.status}.`;
        try {
          const errorPayload = (await response.json()) as {
            detail?: string;
            message?: string;
          };
          errorMessage =
            errorPayload.detail ??
            errorPayload.message ??
            `Request failed with status ${response.status}.`;
        } catch {
          const fallbackText = await response.text();
          if (fallbackText) {
            errorMessage = fallbackText;
          }
        }
        throw new Error(errorMessage);
      }

      return (await response.json()) as T;
    },
    [accessToken, apiBaseUrl],
  );

  const hydrateSession = useCallback(
    async (tokenToUse: string, apiBaseUrlOverride?: string) => {
      const resolvedApiBaseUrl = apiBaseUrlOverride ?? apiBaseUrl;
      setIsCheckingSession(true);
      try {
        const response = await fetch(
          buildApiUrl(resolvedApiBaseUrl, "/api/v1/auth/me"),
          {
          headers: {
            Authorization: `Bearer ${tokenToUse}`,
          },
          cache: "no-store",
          },
        );

        if (!response.ok) {
          throw new Error("Session is missing or no longer valid.");
        }

        const payload = (await response.json()) as CurrentUser;
        setCurrentUser(payload);
        setShellError(null);
      } catch (error) {
        setCurrentUser(null);
        setAccessToken("");
        setShellError(
          error instanceof Error
            ? error.message
            : "Session is missing or no longer valid.",
        );
      } finally {
        setIsCheckingSession(false);
      }
    },
    [apiBaseUrl],
  );

  useEffect(() => {
    if (typeof window === "undefined") {
      return;
    }

    const storedApiBaseUrl = window.localStorage.getItem(API_BASE_URL_STORAGE_KEY);
    const storedAccessToken = window.localStorage.getItem(ACCESS_TOKEN_STORAGE_KEY);
    const resolvedApiBaseUrl = storedApiBaseUrl ?? DEFAULT_API_BASE_URL;

    if (storedApiBaseUrl) {
      setApiBaseUrl(resolvedApiBaseUrl);
    }
    if (storedAccessToken) {
      setAccessToken(storedAccessToken);
      void hydrateSession(storedAccessToken, resolvedApiBaseUrl);
      return;
    }
    setIsCheckingSession(false);
  }, [hydrateSession]);

  useEffect(() => {
    if (typeof window === "undefined") {
      return;
    }
    window.localStorage.setItem(API_BASE_URL_STORAGE_KEY, apiBaseUrl);
  }, [apiBaseUrl]);

  useEffect(() => {
    if (typeof window === "undefined") {
      return;
    }
    if (accessToken) {
      window.localStorage.setItem(ACCESS_TOKEN_STORAGE_KEY, accessToken);
      return;
    }
    window.localStorage.removeItem(ACCESS_TOKEN_STORAGE_KEY);
  }, [accessToken]);

  const handleLogin = useCallback(
    async (event: FormEvent<HTMLFormElement>) => {
      event.preventDefault();
      setIsAuthenticating(true);
      setShellError(null);
      setShellSuccess(null);

      try {
        const response = await fetch(buildApiUrl(apiBaseUrl, "/api/v1/auth/login"), {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            username_or_email: loginUsername,
            password: loginPassword,
          }),
        });

        if (!response.ok) {
          const errorPayload = (await response.json()) as { detail?: string };
          throw new Error(errorPayload.detail ?? "Unable to authenticate.");
        }

        const payload = (await response.json()) as LoginResponse;
        setAccessToken(payload.access_token);
        setCurrentUser(payload.user);
        setShellSuccess(`Signed in as ${payload.user.username}.`);
      } catch (error) {
        setShellError(
          error instanceof Error ? error.message : "Unable to authenticate.",
        );
      } finally {
        setIsAuthenticating(false);
      }
    },
    [apiBaseUrl, loginPassword, loginUsername],
  );

  const handleLogout = useCallback(() => {
    setAccessToken("");
    setCurrentUser(null);
    setShellSuccess(null);
  }, []);

  return (
    <main className="meter-page-shell">
      <section className="hero">
        <p className="eyebrow">{eyebrow}</p>
        <h1>{title}</h1>
        <p className="lead">{description}</p>
      </section>

      <section className="panel operational-shell-panel">
        <div className="operational-nav">
          <div className="operational-nav-links">
            <Link className="nav-link" href="/">
              Home
            </Link>
            <Link className="nav-link" href="/connectivity">
              Connectivity
            </Link>
            <Link className="nav-link" href="/meters">
              Meters
            </Link>
            <Link className="nav-link" href="/commands">
              Commands
            </Link>
            {currentMeterId ? (
              <Link className="nav-link" href={`/meters/${currentMeterId}`}>
                Current meter
              </Link>
            ) : null}
          </div>
          <div className="operational-nav-session">
            <span className="muted">
              {currentUser
                ? `Signed in as ${currentUser.full_name || currentUser.username}`
                : "No active session"}
            </span>
            {currentUser ? (
              <button className="secondary-button" onClick={handleLogout} type="button">
                Sign out
              </button>
            ) : null}
          </div>
        </div>
      </section>

      {isCheckingSession ? (
        <section className="panel">
          <h2>Checking session</h2>
          <p className="muted">
            Verifying the current operational session before loading the page.
          </p>
        </section>
      ) : null}

      {!isCheckingSession && !currentUser ? (
        <section className="panel">
          <div className="section-heading">
            <div>
              <h2>Session required</h2>
              <p className="muted">
                Sign in with the existing backend auth flow to access the operational
                pages.
              </p>
            </div>
          </div>

          <div className="settings-grid">
            <label className="field">
              <span>API base URL</span>
              <input
                value={apiBaseUrl}
                onChange={(event) => setApiBaseUrl(event.target.value)}
                placeholder="http://localhost:8000"
              />
            </label>
          </div>

          <form className="inline-form" onSubmit={handleLogin}>
            <label className="field">
              <span>Username or email</span>
              <input
                value={loginUsername}
                onChange={(event) => setLoginUsername(event.target.value)}
                placeholder="ops@example.com"
              />
            </label>
            <label className="field">
              <span>Password</span>
              <input
                type="password"
                value={loginPassword}
                onChange={(event) => setLoginPassword(event.target.value)}
                placeholder="Enter password"
              />
            </label>
            <button className="primary-button" disabled={isAuthenticating} type="submit">
              {isAuthenticating ? "Signing in..." : "Sign in"}
            </button>
          </form>

          {shellSuccess ? <p className="success-banner">{shellSuccess}</p> : null}
          {shellError ? <p className="error-banner">{shellError}</p> : null}
        </section>
      ) : null}

      {!isCheckingSession && currentUser ? (
        <>{children({ authorizedFetch, apiBaseUrl, currentUser })}</>
      ) : null}
    </main>
  );
}
