"use client";

import { useState } from "react";

import { useSession } from "../session-provider";

export function LoginModule({
  onLoginSuccess,
}: {
  onLoginSuccess?: () => void;
}) {
  const { apiBaseUrl, setApiBaseUrl, login, apiConnectivity } = useSession();
  const [usernameOrEmail, setUsernameOrEmail] = useState("");
  const [password, setPassword] = useState("");
  const [formError, setFormError] = useState<string | null>(null);
  const [formSuccess, setFormSuccess] = useState<string | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);

  return (
    <form
      className="ws-form"
      onSubmit={async (event) => {
        event.preventDefault();
        setFormError(null);
        setFormSuccess(null);
        setIsSubmitting(true);

        try {
          const response = await login({ usernameOrEmail, password });
          setFormSuccess(`Signed in as ${response.user.username}.`);
          onLoginSuccess?.();
        } catch (error) {
          setFormError(error instanceof Error ? error.message : "Unable to authenticate.");
        } finally {
          setIsSubmitting(false);
        }
      }}
    >
      <label className="ws-field">
        <span>API base URL</span>
        <input
          value={apiBaseUrl}
          onChange={(event) => setApiBaseUrl(event.target.value)}
          autoComplete="off"
        />
      </label>

      <div className="ws-login-meta">
        <span className="ws-muted">Target</span>
        <strong>{apiBaseUrl}</strong>
        {apiConnectivity.status === "unreachable" && apiConnectivity.message ? (
          <p className="ws-alert">{apiConnectivity.message}</p>
        ) : null}
      </div>

      <label className="ws-field">
        <span>Username or email</span>
        <input
          value={usernameOrEmail}
          onChange={(event) => setUsernameOrEmail(event.target.value)}
          autoComplete="username"
        />
      </label>

      <label className="ws-field">
        <span>Password</span>
        <input
          type="password"
          value={password}
          onChange={(event) => setPassword(event.target.value)}
          autoComplete="current-password"
        />
      </label>

      <button className="ws-btn ws-btn-primary ws-btn-block" disabled={isSubmitting} type="submit">
        {isSubmitting ? "Signing in…" : "Sign in"}
      </button>

      {formSuccess ? <p className="ws-success">{formSuccess}</p> : null}
      {formError ? <p className="ws-alert">{formError}</p> : null}
    </form>
  );
}
