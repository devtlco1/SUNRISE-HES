import { afterEach, describe, expect, it } from "vitest";

import {
  getInitialApiBaseUrlForRender,
  resolveApiBaseUrl,
} from "./api-base-url";

describe("api-base-url", () => {
  afterEach(() => {
    delete process.env.NEXT_PUBLIC_API_BASE_URL;
  });

  it("prefers the configured environment API base over stale stored localhost", () => {
    process.env.NEXT_PUBLIC_API_BASE_URL = "http://187.124.187.156:8000";

    expect(
      resolveApiBaseUrl("http://localhost:8000", {
        protocol: "http:",
        hostname: "187.124.187.156",
      }),
    ).toBe("http://187.124.187.156:8000");
  });

  it("uses localhost fallback during local development when no env override is set", () => {
    expect(
      resolveApiBaseUrl(null, {
        protocol: "http:",
        hostname: "localhost",
      }),
    ).toBe("http://localhost:8000");
  });

  it("avoids stale localhost storage on non-local browser hosts", () => {
    expect(
      resolveApiBaseUrl("http://localhost:8000", {
        protocol: "http:",
        hostname: "187.124.187.156",
      }),
    ).toBe("http://187.124.187.156:8000");
  });

  it("keeps an explicit stored non-local API base when no env override is set", () => {
    expect(
      resolveApiBaseUrl("http://10.0.0.5:8000", {
        protocol: "http:",
        hostname: "187.124.187.156",
      }),
    ).toBe("http://10.0.0.5:8000");
  });

  it("uses the configured environment base for initial render", () => {
    process.env.NEXT_PUBLIC_API_BASE_URL = "http://187.124.187.156:8000/";

    expect(getInitialApiBaseUrlForRender()).toBe("http://187.124.187.156:8000");
  });
});
