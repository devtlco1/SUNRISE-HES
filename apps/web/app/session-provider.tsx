"use client";

import {
  createContext,
  useRef,
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

type ApiConnectivityStatus = "unknown" | "checking" | "reachable" | "unreachable";

type ApiConnectivity = {
  status: ApiConnectivityStatus;
  message: string | null;
  checkedBaseUrl: string | null;
};

type SessionContextValue = {
  apiBaseUrl: string;
  setApiBaseUrl: (value: string) => void;
  accessToken: string;
  currentUser: CurrentUser | null;
  isCheckingSession: boolean;
  sessionError: string | null;
  apiConnectivity: ApiConnectivity;
  authorizedFetch: AuthorizedFetch;
  login: (payload: {
    usernameOrEmail: string;
    password: string;
  }) => Promise<LoginResponse>;
  requestPasswordReset: (payload: {
    usernameOrEmail: string;
  }) => Promise<ForgotPasswordResponse>;
  probeApiConnectivity: (apiBaseUrlOverride?: string) => Promise<boolean>;
  logout: () => void;
};

const ACCESS_TOKEN_STORAGE_KEY = "sunrise.web.accessToken";
const API_BASE_URL_STORAGE_KEY = "sunrise.web.apiBaseUrl";
const DEFAULT_API_BASE_URL =
  process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000";
const INITIAL_API_CONNECTIVITY: ApiConnectivity = {
  status: "unknown",
  message: null,
  checkedBaseUrl: null,
};

const SessionContext = createContext<SessionContextValue | null>(null);

function normalizeApiBaseUrl(value: string): string {
  const trimmed = value.trim();
  const fallback = trimmed || DEFAULT_API_BASE_URL;
  return fallback.replace(/\/+$/, "");
}

function readStoredApiBaseUrl(): string {
  if (typeof window === "undefined") {
    return normalizeApiBaseUrl(DEFAULT_API_BASE_URL);
  }
  return normalizeApiBaseUrl(
    window.localStorage.getItem(API_BASE_URL_STORAGE_KEY) ?? DEFAULT_API_BASE_URL,
  );
}

function readStoredAccessToken(): string {
  if (typeof window === "undefined") {
    return "";
  }
  return window.localStorage.getItem(ACCESS_TOKEN_STORAGE_KEY) ?? "";
}

function buildApiUrl(apiBaseUrl: string, path: string): string {
  return `${normalizeApiBaseUrl(apiBaseUrl)}${path}`;
}

function buildApiUnreachableMessage(apiBaseUrl: string): string {
  const normalizedApiBaseUrl = normalizeApiBaseUrl(apiBaseUrl);
  return `Cannot reach API at ${normalizedApiBaseUrl}. Start the backend server or update API base URL.`;
}

function isLikelyNetworkError(error: unknown): boolean {
  if (!(error instanceof Error)) {
    return false;
  }
  const message = error.message.toLowerCase();
  return (
    error.name === "TypeError" ||
    message.includes("failed to fetch") ||
    message.includes("networkerror") ||
    message.includes("load failed")
  );
}

export function SessionProvider({ children }: PropsWithChildren) {
  const [apiBaseUrlState, setApiBaseUrlState] = useState(readStoredApiBaseUrl);
  const [accessToken, setAccessToken] = useState(readStoredAccessToken);
  const [currentUser, setCurrentUser] = useState<CurrentUser | null>(null);
  const [isCheckingSession, setIsCheckingSession] = useState(true);
  const [sessionError, setSessionError] = useState<string | null>(null);
  const [apiConnectivity, setApiConnectivity] =
    useState<ApiConnectivity>(INITIAL_API_CONNECTIVITY);
  const apiConnectivityRef = useRef<ApiConnectivity>(INITIAL_API_CONNECTIVITY);

  const apiBaseUrl = normalizeApiBaseUrl(apiBaseUrlState);
  const apiBaseUrlRef = useRef(apiBaseUrl);
  const initialAccessTokenRef = useRef(accessToken);
  const initialApiBaseUrlRef = useRef(apiBaseUrl);
  apiBaseUrlRef.current = apiBaseUrl;

  const setApiConnectivityIfChanged = useCallback((next: ApiConnectivity) => {
    const current = apiConnectivityRef.current;
    if (
      current.status === next.status &&
      current.message === next.message &&
      current.checkedBaseUrl === next.checkedBaseUrl
    ) {
      return;
    }
    apiConnectivityRef.current = next;
    setApiConnectivity(next);
  }, []);

  const setApiBaseUrl = useCallback(
    (value: string) => {
      const normalizedValue = normalizeApiBaseUrl(value);
      if (normalizedValue === apiBaseUrlRef.current) {
        return;
      }
      apiBaseUrlRef.current = normalizedValue;
      setApiBaseUrlState(normalizedValue);
      setApiConnectivityIfChanged(INITIAL_API_CONNECTIVITY);
    },
    [setApiConnectivityIfChanged],
  );

  const probeApiConnectivity = useCallback(
    async (apiBaseUrlOverride?: string) => {
      const resolvedApiBaseUrl = normalizeApiBaseUrl(
        apiBaseUrlOverride ?? apiBaseUrlRef.current,
      );
      setApiConnectivityIfChanged({
        status: "checking",
        message: null,
        checkedBaseUrl: resolvedApiBaseUrl,
      });
      try {
        const response = await fetch(
          buildApiUrl(resolvedApiBaseUrl, "/api/v1/platform/health"),
          {
            cache: "no-store",
          },
        );
        if (!response.ok) {
          throw new Error(
            `API health probe failed with status ${response.status}.`,
          );
        }
        setApiConnectivityIfChanged({
          status: "reachable",
          message: null,
          checkedBaseUrl: resolvedApiBaseUrl,
        });
        return true;
      } catch (error) {
        const message = isLikelyNetworkError(error)
          ? buildApiUnreachableMessage(resolvedApiBaseUrl)
          : error instanceof Error
            ? error.message
            : buildApiUnreachableMessage(resolvedApiBaseUrl);
        setApiConnectivityIfChanged({
          status: "unreachable",
          message,
          checkedBaseUrl: resolvedApiBaseUrl,
        });
        return false;
      }
    },
    [setApiConnectivityIfChanged],
  );

  const authorizedFetch = useCallback<AuthorizedFetch>(
    async <T,>(path: string, init?: RequestInit): Promise<T> => {
      const headers = new Headers(init?.headers);
      if (init?.body && !headers.has("Content-Type")) {
        headers.set("Content-Type", "application/json");
      }
      if (accessToken) {
        headers.set("Authorization", `Bearer ${accessToken}`);
      }

      let response: Response;
      try {
        response = await fetch(buildApiUrl(apiBaseUrl, path), {
          ...init,
          headers,
          cache: "no-store",
        });
      } catch (error) {
        if (isLikelyNetworkError(error)) {
          throw new Error(buildApiUnreachableMessage(apiBaseUrl));
        }
        throw error;
      }

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

  useEffect(() => {
    const storedAccessToken = initialAccessTokenRef.current;
    const resolvedApiBaseUrl = initialApiBaseUrlRef.current;

    if (!storedAccessToken) {
      setSessionError(null);
      setIsCheckingSession(false);
      return;
    }

    let isCancelled = false;

    const bootstrapSession = async () => {
      try {
        const response = await fetch(
          buildApiUrl(resolvedApiBaseUrl, "/api/v1/auth/me"),
          {
            headers: {
              Authorization: `Bearer ${storedAccessToken}`,
            },
            cache: "no-store",
          },
        );

        if (!response.ok) {
          throw new Error("Session is missing or no longer valid.");
        }

        const payload = (await response.json()) as CurrentUser;
        if (isCancelled) {
          return;
        }
        setCurrentUser(payload);
        setSessionError(null);
      } catch (error) {
        if (isCancelled) {
          return;
        }
        setCurrentUser(null);
        setAccessToken("");
        setSessionError(
          isLikelyNetworkError(error)
            ? buildApiUnreachableMessage(resolvedApiBaseUrl)
            : error instanceof Error
              ? error.message
              : "Session is missing or no longer valid.",
        );
      } finally {
        if (!isCancelled) {
          setIsCheckingSession(false);
        }
      }
    };

    void bootstrapSession();

    return () => {
      isCancelled = true;
    };
  }, []);

  useEffect(() => {
    if (typeof window === "undefined") {
      return;
    }
    window.localStorage.setItem(API_BASE_URL_STORAGE_KEY, normalizeApiBaseUrl(apiBaseUrl));
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
      let response: Response;
      try {
        response = await fetch(buildApiUrl(apiBaseUrl, "/api/v1/auth/login"), {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            username_or_email: usernameOrEmail,
            password,
          }),
        });
      } catch (error) {
        if (isLikelyNetworkError(error)) {
          const message = buildApiUnreachableMessage(apiBaseUrl);
          setApiConnectivityIfChanged({
            status: "unreachable",
            message,
            checkedBaseUrl: apiBaseUrl,
          });
          throw new Error(message);
        }
        throw error;
      }

      if (!response.ok) {
        const errorPayload = (await response.json()) as { detail?: string };
        throw new Error(errorPayload.detail ?? "Unable to authenticate.");
      }

      const payload = (await response.json()) as LoginResponse;
      setAccessToken(payload.access_token);
      setCurrentUser(payload.user);
      setSessionError(null);
      setApiConnectivityIfChanged({
        status: "reachable",
        message: null,
        checkedBaseUrl: apiBaseUrl,
      });
      return payload;
    },
    [apiBaseUrl, setApiConnectivityIfChanged],
  );

  const requestPasswordReset = useCallback(
    async ({ usernameOrEmail }: { usernameOrEmail: string }) => {
      let response: Response;
      try {
        response = await fetch(
          buildApiUrl(apiBaseUrl, "/api/v1/auth/forgot-password"),
          {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
              username_or_email: usernameOrEmail,
            }),
          },
        );
      } catch (error) {
        if (isLikelyNetworkError(error)) {
          throw new Error(buildApiUnreachableMessage(apiBaseUrl));
        }
        throw error;
      }

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
      apiConnectivity,
      authorizedFetch,
      login,
      requestPasswordReset,
      probeApiConnectivity,
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
      apiConnectivity,
      probeApiConnectivity,
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
