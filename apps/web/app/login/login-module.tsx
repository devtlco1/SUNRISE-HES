"use client";

import Link from "next/link";
import { useState } from "react";

import { useSession } from "../session-provider";

export function LoginModule({
  onLoginSuccess,
}: {
  onLoginSuccess?: () => void;
}) {
  const {
    apiBaseUrl,
    setApiBaseUrl,
    login,
    apiConnectivity,
  } = useSession();
  const [usernameOrEmail, setUsernameOrEmail] = useState("");
  const [password, setPassword] = useState("");
  const [formError, setFormError] = useState<string | null>(null);
  const [formSuccess, setFormSuccess] = useState<string | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);

  return (
    <form
      className="auth-form"
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
          setFormError(
            error instanceof Error ? error.message : "Unable to authenticate.",
          );
        } finally {
          setIsSubmitting(false);
        }
      }}
    >
      <div className="section-heading">
        <div>
          <h2>Login</h2>
          <p className="muted">
            Use the existing backend auth flow to enter the operational platform.
          </p>
        </div>
      </div>

      <label className="field">
        <span>API base URL</span>
        <input
          value={apiBaseUrl}
          onChange={(event) => setApiBaseUrl(event.target.value)}
          placeholder="http://api.example.com"
        />
      </label>

      <div className="auth-connectivity-hint">
        <span className="stat-label">Current API target</span>
        <strong>{apiBaseUrl}</strong>
        {apiConnectivity.status === "unknown" ? (
          <p className="muted">
            Connectivity is checked when you submit the login form.
          </p>
        ) : null}
        {apiConnectivity.status === "checking" ? (
          <p className="muted">Checking API connectivity...</p>
        ) : null}
        {apiConnectivity.status === "unreachable" && apiConnectivity.message ? (
          <p className="error-banner">{apiConnectivity.message}</p>
        ) : null}
        {apiConnectivity.status === "reachable" ? (
          <p className="muted">API connectivity confirmed for the current target.</p>
        ) : null}
      </div>

      <label className="field">
        <span>Username or email</span>
        <input
          value={usernameOrEmail}
          onChange={(event) => setUsernameOrEmail(event.target.value)}
          placeholder="ops@example.com"
        />
      </label>

      <label className="field">
        <span>Password</span>
        <input
          type="password"
          value={password}
          onChange={(event) => setPassword(event.target.value)}
          placeholder="Enter password"
        />
      </label>

      <button className="primary-button" disabled={isSubmitting} type="submit">
        {isSubmitting ? "Signing in..." : "Sign in"}
      </button>

      <div className="auth-form-footer">
        <span className="muted">Need password help?</span>
        <Link href="/forgot-password">Forgot password</Link>
      </div>

      {formSuccess ? <p className="success-banner">{formSuccess}</p> : null}
      {formError ? <p className="error-banner">{formError}</p> : null}
    </form>
  );
}
