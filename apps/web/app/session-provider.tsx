"use client";

import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
  type PropsWithChildren,
} from "react";

export type AuthorizedFetch = <T>(
  path: string,
  init?: RequestInit,
) => Promise<T>;

export type CurrentUser = {
  id: string;
  username: string;
  email: string;
  full_name: string;
  status: string;
  is_superuser: boolean;
  roles?: Array<{ id: string; code: string; name: string }>;
  permissions?: Array<{ code: string }>;
};

type LoginResponse = {
  access_token: string;
  token_type: string;
  expires_in: number;
  user: CurrentUser;
};

type ForgotPasswordResponse = {
  message: string;
};

type SessionContextValue = {
  apiBaseUrl: string;
  setApiBaseUrl: (value: string) => void;
  accessToken: string;
  currentUser: CurrentUser | null;
  isCheckingSession: boolean;
  sessionError: string | null;
  authorizedFetch: AuthorizedFetch;
  login: (payload: {
    usernameOrEmail: string;
    password: string;
  }) => Promise<LoginResponse>;
  requestPasswordReset: (payload: {
    usernameOrEmail: string;
  }) => Promise<ForgotPasswordResponse>;
  logout: () => void;
};

const ACCESS_TOKEN_STORAGE_KEY = "sunrise.web.accessToken";
const API_BASE_URL_STORAGE_KEY = "sunrise.web.apiBaseUrl";
const DEFAULT_API_BASE_URL =
  process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000";

const SessionContext = createContext<SessionContextValue | null>(null);

function buildApiUrl(apiBaseUrl: string, path: string): string {
  return `${apiBaseUrl.replace(/\/$/, "")}${path}`;
}

export function SessionProvider({ children }: PropsWithChildren) {
  const [apiBaseUrl, setApiBaseUrl] = useState(DEFAULT_API_BASE_URL);
  const [accessToken, setAccessToken] = useState("");
  const [currentUser, setCurrentUser] = useState<CurrentUser | null>(null);
  const [isCheckingSession, setIsCheckingSession] = useState(true);
  const [sessionError, setSessionError] = useState<string | null>(null);

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
        setSessionError(null);
      } catch (error) {
        setCurrentUser(null);
        setAccessToken("");
        setSessionError(
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

    setSessionError(null);
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

  const login = useCallback(
    async ({
      usernameOrEmail,
      password,
    }: {
      usernameOrEmail: string;
      password: string;
    }) => {
      const response = await fetch(buildApiUrl(apiBaseUrl, "/api/v1/auth/login"), {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          username_or_email: usernameOrEmail,
          password,
        }),
      });

      if (!response.ok) {
        const errorPayload = (await response.json()) as { detail?: string };
        throw new Error(errorPayload.detail ?? "Unable to authenticate.");
      }

      const payload = (await response.json()) as LoginResponse;
      setAccessToken(payload.access_token);
      setCurrentUser(payload.user);
      setSessionError(null);
      return payload;
    },
    [apiBaseUrl],
  );

  const requestPasswordReset = useCallback(
    async ({ usernameOrEmail }: { usernameOrEmail: string }) => {
      const response = await fetch(
        buildApiUrl(apiBaseUrl, "/api/v1/auth/forgot-password"),
        {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            username_or_email: usernameOrEmail,
          }),
        },
      );

      if (!response.ok) {
        const errorPayload = (await response.json()) as { detail?: string };
        throw new Error(
          errorPayload.detail ?? "Unable to start forgot-password flow.",
        );
      }

      return (await response.json()) as ForgotPasswordResponse;
    },
    [apiBaseUrl],
  );

  const logout = useCallback(() => {
    setAccessToken("");
    setCurrentUser(null);
    setSessionError(null);
  }, []);

  const value = useMemo<SessionContextValue>(
    () => ({
      apiBaseUrl,
      setApiBaseUrl,
      accessToken,
      currentUser,
      isCheckingSession,
      sessionError,
      authorizedFetch,
      login,
      requestPasswordReset,
      logout,
    }),
    [
      accessToken,
      apiBaseUrl,
      authorizedFetch,
      currentUser,
      isCheckingSession,
      login,
      logout,
      requestPasswordReset,
      sessionError,
    ],
  );

  return (
    <SessionContext.Provider value={value}>{children}</SessionContext.Provider>
  );
}

export function useSession() {
  const context = useContext(SessionContext);
  if (context === null) {
    throw new Error("useSession must be used within SessionProvider.");
  }
  return context;
}
