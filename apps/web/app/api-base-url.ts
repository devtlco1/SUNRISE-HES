"use client";

type BrowserLocationLike = {
  protocol: string;
  hostname: string;
};

const LOCAL_API_BASE_URL = "http://localhost:8000";
const DEFAULT_REMOTE_API_PORT = "8000";

export function normalizeApiBaseUrl(value: string): string {
  return value.trim().replace(/\/+$/, "");
}

function getConfiguredApiBaseUrl(): string | null {
  const configuredValue = process.env.NEXT_PUBLIC_API_BASE_URL?.trim();
  return configuredValue ? normalizeApiBaseUrl(configuredValue) : null;
}

function isLocalHostname(hostname: string): boolean {
  const normalizedHostname = hostname.toLowerCase();
  return (
    normalizedHostname === "localhost" ||
    normalizedHostname === "127.0.0.1" ||
    normalizedHostname === "0.0.0.0" ||
    normalizedHostname === "::1"
  );
}

function isLoopbackApiBaseUrl(value: string): boolean {
  try {
    return isLocalHostname(new URL(normalizeApiBaseUrl(value)).hostname);
  } catch {
    return false;
  }
}

function buildBrowserApiBaseUrl(locationLike: BrowserLocationLike): string {
  if (isLocalHostname(locationLike.hostname)) {
    return LOCAL_API_BASE_URL;
  }

  const protocol = locationLike.protocol === "https:" ? "https:" : "http:";
  return `${protocol}//${locationLike.hostname}:${DEFAULT_REMOTE_API_PORT}`;
}

export function getInitialApiBaseUrlForRender(): string {
  return getConfiguredApiBaseUrl() ?? LOCAL_API_BASE_URL;
}

export function resolveApiBaseUrl(
  storedApiBaseUrl: string | null,
  locationLike?: BrowserLocationLike,
): string {
  const configuredApiBaseUrl = getConfiguredApiBaseUrl();
  if (configuredApiBaseUrl) {
    return configuredApiBaseUrl;
  }

  const resolvedLocation =
    locationLike ?? (typeof window !== "undefined" ? window.location : undefined);
  const normalizedStoredApiBaseUrl = storedApiBaseUrl
    ? normalizeApiBaseUrl(storedApiBaseUrl)
    : "";

  if (normalizedStoredApiBaseUrl) {
    if (!resolvedLocation) {
      return normalizedStoredApiBaseUrl;
    }

    if (
      isLocalHostname(resolvedLocation.hostname) ||
      !isLoopbackApiBaseUrl(normalizedStoredApiBaseUrl)
    ) {
      return normalizedStoredApiBaseUrl;
    }
  }

  if (resolvedLocation) {
    return buildBrowserApiBaseUrl(resolvedLocation);
  }

  return LOCAL_API_BASE_URL;
}
